"""Collect the temporal-slider journey on one owned Chrome.

    python tests/browser/temporal_capture.py --url http://127.0.0.1:8606 \
        --label python-temporal --scope "PYTHON SIDE ONLY" --out target/temporal-python

WHAT THIS RECORDS
    The decoded bidirectional WebSocket frames of the official 1.66.1
    frontend across the thirteen measured stages (the initial load, then
    every date/time/datetime slider — scalar and range — driven with real
    End/Home keys on its hidden native range input), the DOM end state of
    each stage (repr echo lines, native range input values, exceptions), a
    PNG per stage, the driven application source identity, and the loaded
    capture sources. The verdict is computed by the strict contract
    (temporal_contract.py); this collector only records what the runtime did
    and exits by that verdict. ``--replay <raw>`` rejudges archived bytes
    read-only, without a browser or server.

BROWSER
    The collector starts its own Chrome on its own DevTools port with its own
    profile directory, shares no session with any other capture, opens one
    owned tab, and closes exactly that tab.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import pathlib
import subprocess
import sys
import time
import urllib.request

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "tests" / "reference"))
sys.path.insert(0, str(HERE))

from capture_browser_trace import CDP, require_decoder, summarise_back, summarise_forward  # noqa: E402
from numeric_capture import Page  # noqa: E402  the proven CDP input helper
from temporal_contract import TEMPORAL_CASE, TEMPORAL_CONTRACT, TEMPORAL_STAGES, temporal_result  # noqa: E402

DOM_EXPRESSION = r"""JSON.stringify({
markdowns:[...document.querySelectorAll("[data-testid=stMarkdown]")].map(e=>e.textContent.trim()),
sliders:[...document.querySelectorAll("[data-testid=stSlider]")].map(e=>{
 const label=(e.querySelector("label")?.textContent||"").trim();
 const inputs=[...e.querySelectorAll("input[type=range]")].map(i=>({id:i.id,min:i.min,max:i.max,
 step:i.step,value:i.value,text:i.getAttribute("aria-valuetext")}));
 const thumb=e.querySelector("[data-testid=stSliderThumbValue]")?.textContent||null;
 const ticks=[...e.querySelectorAll("[data-testid=stSliderTickBar] p")].map(p=>p.textContent.trim());
 return {label,inputs,thumb,ticks};}),
exceptions:[...document.querySelectorAll("[data-testid=stException]")].map(e=>e.innerText.slice(0,200))})"""

KEYS = {"End": ("End", "End", 35), "Home": ("Home", "Home", 36)}

# How the collector drives each stage the contract names: focus the hidden
# native range input of the requested thumb with a real key event. The load
# stage only waits for the page.
DRIVE = {
    "02-date-end": ("date", 0, "End"),
    "03-date-home": ("date", 0, "Home"),
    "04-time-end": ("time", 0, "End"),
    "05-time-home": ("time", 0, "Home"),
    "06-datetime-end": ("datetime", 0, "End"),
    "07-datetime-home": ("datetime", 0, "Home"),
    "08-date-range-left-home": ("date-range", 0, "Home"),
    "09-date-range-right-end": ("date-range", 1, "End"),
    "10-time-range-left-home": ("time-range", 0, "Home"),
    "11-time-range-right-end": ("time-range", 1, "End"),
    "12-datetime-range-left-home": ("datetime-range", 0, "Home"),
    "13-datetime-range-right-end": ("datetime-range", 1, "End"),
}

CHROME_CANDIDATES = (
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
)


def digest(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def http_json(url, method="GET"):
    request = urllib.request.Request(url, method=method)
    with urllib.request.urlopen(request, timeout=5) as response:
        return json.loads(response.read())


def frames_from_events(events):
    """Decode every binary WebSocket frame event into an ordered summary list."""
    frames = []
    for event in events:
        method = event.get("method")
        if method not in ("Network.webSocketFrameSent", "Network.webSocketFrameReceived"):
            continue
        params = event.get("params") or {}
        payload = (params.get("response") or {}).get("payloadData") or ""
        try:
            data = base64.b64decode(payload, validate=True)
            summary = summarise_back(data) if method.endswith("Sent") else summarise_forward(data)
        except Exception:
            continue
        frames.append({
            "direction": "client->server" if method.endswith("Sent") else "server->client",
            "timestamp": params.get("timestamp"),
            "summary": summary,
        })
    frames.sort(key=lambda frame: (frame["timestamp"] is None, frame["timestamp"]))
    return frames


def settle(recorder, seen, timeout=25):
    """Wait until no new frames arrive for ~1.5 seconds."""
    deadline = time.monotonic() + timeout
    last, stable = -1, 0
    while time.monotonic() < deadline:
        count = len(frames_from_events(recorder.take()))
        stable = stable + 1 if count == last else 0
        last = count
        if stable >= 15 and count > seen:
            return
        time.sleep(0.1)
    raise RuntimeError("frames did not settle")


def thumb_expression(label, index):
    """The visually hidden native range input of the requested thumb."""
    return (
        "[...document.querySelectorAll('[data-testid=stSlider]')].find(e=>"
        "((e.querySelector('label')?.textContent)||'').trim()===" + json.dumps(label) + ")"
        "?.querySelectorAll('input[type=range]')[" + str(index) + "]"
    )


def replay(path: str) -> int:
    raw = pathlib.Path(path).resolve()
    original = raw.read_bytes()
    trace = json.loads(original)
    observation = trace.get("observation")
    observation["ipc_dir"] = str(raw.parent)
    verdict = temporal_result(observation=observation)
    if raw.read_bytes() != original:
        raise RuntimeError("raw bytes changed during replay")
    print(json.dumps({"journey": trace.get("journey"), "raw_sha256": hashlib.sha256(original).hexdigest(),
                      **{key: verdict[key] for key in ("counts", "failures", "ok")}}, ensure_ascii=False))
    return 0 if verdict["ok"] else 1


def capture(args, out: pathlib.Path) -> int:
    side = "python" if args.scope == "PYTHON SIDE ONLY" else "native"
    source_path = ROOT / ("tests/reference/temporal_app.py" if side == "python" else "streamlit/examples/temporal.rs")
    observation = {
        "journey": TEMPORAL_CASE,
        "contract": TEMPORAL_CONTRACT,
        "scope": args.scope,
        "url": args.url,
        "binary": args.binary or None,
        "source": {"file": source_path.relative_to(ROOT).as_posix(), "sha256": digest(source_path)},
        "capture_sources": {name: digest(ROOT / "tests/browser" / name) for name in ("temporal_capture.py", "temporal_contract.py")},
        "stages": [],
        "ipc_dir": str(out.resolve()),
    }
    manifest = {"executable": sys.executable, "argv": sys.argv[1:], "cwd": str(pathlib.Path.cwd()),
                "started_unix": time.time(), "chrome_port": args.port, "exit_code": None}
    chrome = None
    recorder = None
    target_id = None
    try:
        chrome_path = next(candidate for candidate in CHROME_CANDIDATES if pathlib.Path(candidate).is_file())
        chrome = subprocess.Popen([chrome_path, f"--remote-debugging-port={args.port}",
                                   f"--user-data-dir={(out / 'chrome-profile').resolve()}", "--no-first-run",
                                   "--no-default-browser-check", "about:blank"],
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        for _ in range(60):
            try:
                version = http_json(f"http://127.0.0.1:{args.port}/json/version")
                break
            except Exception:
                time.sleep(0.5)
        else:
            chrome_stderr = b""
            try:
                chrome.terminate()
                chrome.wait(timeout=5)
                chrome_stderr = (chrome.stderr.read() if chrome.stderr else b"") or chrome.communicate()[1]
            except Exception:
                pass
            raise RuntimeError(f"owned Chrome did not start: {chrome_stderr[:300]!r}")
        manifest["chrome_version"] = version["Browser"]
        before = http_json(f"http://127.0.0.1:{args.port}/json/list")
        created = http_json(f"http://127.0.0.1:{args.port}/json/new?about:blank", method="PUT")
        target_id = created["id"]
        if target_id in {target["id"] for target in before}:
            raise RuntimeError("new tab id is not fresh; refusing attachment")
        recorder = CDP(created["webSocketDebuggerUrl"], label=args.label)
        recorder.start()
        recorder.call("Performance.enable")
        recorder.call("Emulation.setDeviceMetricsOverride", {"width": 1264, "height": 1000, "deviceScaleFactor": 1, "mobile": False})
        page = Page(recorder)
        recorder.call("Page.navigate", {"url": args.url})

        seen = 0
        for name in TEMPORAL_STAGES:
            if name in DRIVE:
                label, thumb, key = DRIVE[name]
                if not page.focus(thumb_expression(label, thumb)):
                    raise RuntimeError(f"slider thumb not found: {label}[{thumb}]")
                time.sleep(0.2)
                key_name, key_code, vk = KEYS[key]
                page.press(key_name, key_code, vk)
            settle(recorder, seen)
            frames = frames_from_events(recorder.take())
            new_frames = frames[seen:]
            seen = len(frames)
            dom = page.evaluate(DOM_EXPRESSION)
            png = f"{name}.png"
            if not page.screenshot(out / png, restore=False):
                raise RuntimeError(f"screenshot failed: {name}")
            observation["stages"].append({
                "name": name,
                "action": dict(zip(("slider", "thumb", "key"), DRIVE.get(name, (None, None, None)))),
                "new_frames": new_frames,
                "dom": dom,
                "screenshot": {"file": png, "sha256": digest(out / png)},
            })
            print(f"stage {name}: frames +{len(new_frames)}")
        verdict = temporal_result(observation=observation)
        trace = {"schema_version": 1, "journey": TEMPORAL_CASE, "contract": TEMPORAL_CONTRACT,
                 "scope": args.scope, "url": args.url, "observation": observation,
                 "counts": verdict["counts"], "failures": verdict["failures"]}
        (out / "trace-temporal.json").write_text(json.dumps(trace, ensure_ascii=False, indent=1), encoding="utf-8")
        manifest["exit_code"] = 0 if verdict["ok"] else 1
        print(json.dumps({"counts": verdict["counts"], "failures": verdict["failures"]}, ensure_ascii=False))
        return 0 if verdict["ok"] else 1
    except Exception as exc:
        (out / "trace-temporal.json").write_text(json.dumps({"journey": TEMPORAL_CASE, "observation": observation,
                                                             "producer_error": f"{type(exc).__name__}: {exc}"},
                                                            ensure_ascii=False, indent=1), encoding="utf-8")
        manifest["exit_code"] = 1
        print(json.dumps({"producer_error": f"{type(exc).__name__}: {exc}"}))
        return 1
    finally:
        if recorder is not None:
            recorder.stop()
        if target_id is not None:
            try:
                http_json(f"http://127.0.0.1:{args.port}/json/close/{target_id}", method="PUT")
            except Exception:
                pass
        if chrome is not None:
            chrome.terminate()
            chrome.wait(timeout=10)
        (out / "manifest.json").write_text(json.dumps({**manifest, "finished_unix": time.time()}, indent=1), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url")
    parser.add_argument("--label", default="temporal")
    parser.add_argument("--out", default="")
    parser.add_argument("--scope", default="PYTHON SIDE ONLY")
    parser.add_argument("--port", type=int, default=60933, help="DevTools port of the owned Chrome")
    parser.add_argument("--binary", default="", help="optional '<path> sha256 <hash>' fingerprint of the running binary")
    parser.add_argument("--replay", metavar="RAW", help="read-only replay of one archived trace; no Chrome")
    args = parser.parse_args()
    if args.replay:
        if args.url or args.out:
            parser.error("--replay cannot be combined with --url or --out")
        return replay(args.replay)
    if not args.url:
        parser.error("--url is required for a capture")
    require_decoder()
    out = pathlib.Path(args.out or f"target/temporal-{args.label}")
    out.mkdir(parents=True, exist_ok=True)
    return capture(args, out)


if __name__ == "__main__":
    raise SystemExit(main())
