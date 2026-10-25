"""Collect the execution-semantics journey (J04-S4) on one owned Chrome.

    python tests/browser/execution_capture.py --url http://127.0.0.1:8605 \
        --label python-execution --scope "PYTHON SIDE ONLY" --out target/execution-python

WHAT THIS RECORDS
    The decoded bidirectional WebSocket frames of the official 1.66.1
    frontend across three stages (plain load, one guarded st.rerun cascade,
    one st.stop), the DOM end state of each stage, a PNG per stage, the
    driven application source identity, and the loaded capture sources.
    The verdict is computed by the strict contract (execution_contract.py);
    this collector only records what the runtime did and exits by that
    verdict. ``--replay <raw>`` rejudges archived bytes read-only, without a
    browser or server.

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
from execution_contract import EXECUTION_STAGES, execution_result  # noqa: E402

DOM_EXPRESSION = r"""JSON.stringify({mode:document.querySelector("[data-testid=stSelectbox] input")?.value
?? document.querySelector("[data-testid=stSelectbox]")?.textContent,
markdowns:[...document.querySelectorAll("[data-testid=stMarkdown]")].map(e=>e.textContent.trim())})"""

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
            "bytes": len(payload),
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


def select_option(page, option, timeout=8):
    """Open the mode selectbox and click the option with real CDP input."""
    root = "[...document.querySelectorAll('[data-testid=stSelectbox]')].find(e=>e.textContent.includes('mode'))"
    if not page.click_visible(f"({root})?.querySelector(\"button[aria-label='Open']\")"):
        return False
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if page.option_rect(option):
            target = f"[...document.querySelectorAll('[role=option]')].find(e=>e.textContent.trim()==={json.dumps(option)})"
            return bool(page.click_visible(target))
        time.sleep(0.1)
    return False


def replay(path: str) -> int:
    raw = pathlib.Path(path).resolve()
    original = raw.read_bytes()
    trace = json.loads(original)
    observation = trace.get("observation")
    observation["ipc_dir"] = str(raw.parent)
    verdict = execution_result(observation=observation)
    if raw.read_bytes() != original:
        raise RuntimeError("raw bytes changed during replay")
    print(json.dumps({"journey": trace.get("journey"), "raw_sha256": hashlib.sha256(original).hexdigest(),
                      **{key: verdict[key] for key in ("counts", "failures", "ok")}}, ensure_ascii=False))
    return 0 if verdict["ok"] else 1


def capture(args, out: pathlib.Path) -> int:
    side = "python" if args.scope == "PYTHON SIDE ONLY" else "native"
    source_path = ROOT / ("tests/reference/execution_app.py" if side == "python" else "streamlit/examples/execution.rs")
    observation = {
        "journey": "execution-sequence",
        "contract": "journey-execution-v1",
        "scope": args.scope,
        "url": args.url,
        "binary": args.binary or None,
        "source": {"file": source_path.relative_to(ROOT).as_posix(), "sha256": digest(source_path)},
        "capture_sources": {name: digest(ROOT / "tests/browser" / name) for name in ("execution_capture.py", "execution_contract.py")},
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
        recorder.call("Emulation.setDeviceMetricsOverride", {"width": 1264, "height": 900, "deviceScaleFactor": 1, "mobile": False})
        hook = "window.__stWs=null;const _W=window.WebSocket;window.WebSocket=function(...a){const s=new _W(...a);window.__stWs=s;return s;};window.WebSocket.prototype=_W.prototype;"
        recorder.call("Page.addScriptToEvaluateOnNewDocument", {"source": hook})
        page = Page(recorder)
        recorder.call("Page.navigate", {"url": args.url})

        seen = 0
        for index, stage in enumerate(EXECUTION_STAGES):
            if index > 0 and not select_option(page, stage):
                raise RuntimeError(f"mode select failed: {stage}")
            settle(recorder, seen)
            frames = frames_from_events(recorder.take())
            new_frames = frames[seen:]
            seen = len(frames)
            dom = page.evaluate(DOM_EXPRESSION)
            name = f"{index + 1:02d}-{stage}.png"
            if not page.screenshot(out / name, restore=False):
                raise RuntimeError(f"screenshot failed: {stage}")
            observation["stages"].append({
                "name": stage,
                "new_frames": new_frames,
                "dom": dom,
                "screenshot": {"file": name, "sha256": digest(out / name)},
            })
        verdict = execution_result(observation=observation)
        trace = {"schema_version": 1, "journey": "execution-sequence", "contract": "journey-execution-v1",
                 "scope": args.scope, "url": args.url, "observation": observation,
                 "counts": verdict["counts"], "failures": verdict["failures"]}
        (out / "trace-execution.json").write_text(json.dumps(trace, ensure_ascii=False, indent=1), encoding="utf-8")
        manifest["exit_code"] = 0 if verdict["ok"] else 1
        print(json.dumps({"counts": verdict["counts"], "failures": verdict["failures"]}, ensure_ascii=False))
        return 0 if verdict["ok"] else 1
    except Exception as exc:
        (out / "trace-execution.json").write_text(json.dumps({"journey": "execution-sequence", "observation": observation,
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
        (out / "execution-manifest.json").write_text(json.dumps({**manifest, "finished_unix": time.time()}, indent=1), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url")
    parser.add_argument("--label", default="execution")
    parser.add_argument("--out", default="")
    parser.add_argument("--scope", default="PYTHON SIDE ONLY")
    parser.add_argument("--port", type=int, default=60925, help="DevTools port of the owned Chrome")
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
    out = pathlib.Path(args.out or f"target/execution-{args.label}")
    out.mkdir(parents=True, exist_ok=True)
    return capture(args, out)


if __name__ == "__main__":
    raise SystemExit(main())
