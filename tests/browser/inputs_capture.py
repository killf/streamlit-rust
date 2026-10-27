"""Collect the input-widget journey on one owned Chrome.

    python tests/browser/inputs_capture.py --url http://127.0.0.1:8608 \
        --label python-inputs --scope "PYTHON SIDE ONLY" --out target/inputs-python

WHAT THIS RECORDS
    The decoded bidirectional WebSocket frames of the official 1.66.1
    frontend across the five measured stages (the initial load, a radio
    pick, a multiselect pick through its real popover, number_input
    retyping with real key events, and a text_area append), the settled DOM
    end state of each stage (repr echo lines, radio label/checked/options,
    multiselect chips, number input value, textarea value, exceptions), a
    PNG per stage, the driven application source identity, and the loaded
    capture sources. The verdict is computed by the strict contract
    (inputs_contract.py); this collector only records what the runtime did
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
from inputs_contract import INPUTS_SOURCE_FILES, INPUTS_CASE, INPUTS_CONTRACT, INPUTS_STAGES, inputs_result  # noqa: E402

DOM_EXPRESSION = r"""JSON.stringify({
markdowns:[...document.querySelectorAll("[data-testid=stMarkdown]")].map(e=>e.textContent.trim()),
radio:{label:document.querySelector("[data-testid=stRadio] label")?.textContent.trim()??null,
       checked:[...document.querySelectorAll("[data-testid=stRadio] label p")].findIndex(p=>p.closest("label").querySelector("input")?.checked),
       value:[...document.querySelectorAll("[data-testid=stRadio] label p")].map(p=>p.textContent.trim())},
multiselect:{chips:[...document.querySelectorAll("[data-testid=stMultiSelect] [data-testid=stMultiSelectControlItem]")].map(e=>e.textContent.trim().slice(0,-1)),
             options:[...document.querySelectorAll("[data-testid=stMultiSelect] [data-baseweb=popover] [role=option]")].map(e=>e.textContent.trim())},
number:{value:document.querySelector("[data-testid=stNumberInput] input")?.value??null},
textarea:{value:document.querySelector("[data-testid=stTextArea] textarea")?.value??null},
exceptions:[...document.querySelectorAll("[data-testid=stException]")].map(e=>e.innerText.slice(0,200))})"""

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
    drops = 0
    for event in events:
        method = event.get("method")
        if method not in ("Network.webSocketFrameSent", "Network.webSocketFrameReceived"):
            continue
        params = event.get("params") or {}
        payload = (params.get("response") or {}).get("payloadData") or ""
        try:
            data = base64.b64decode(payload, validate=True)
            summary = summarise_back(data) if method.endswith("Sent") else summarise_forward(data)
        except Exception as exc:
            drops += 1
            print(f"dropped frame ({len(payload)} chars): {type(exc).__name__}: {exc}")
            continue
        frames.append({
            "direction": "client->server" if method.endswith("Sent") else "server->client",
            "timestamp": params.get("timestamp"),
            "summary": summary,
        })
    frames.sort(key=lambda frame: (frame["timestamp"] is None, frame["timestamp"]))
    if drops:
        raise RuntimeError(f"{drops} websocket frames failed to decode; the trace would be silently incomplete")
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


def dom_stable(page, timeout=6.0):
    """Read the DOM until two reads agree: the rerun's React commit may lag
    the last WebSocket frame, and reading early freezes stale echoes."""
    deadline = time.monotonic() + timeout
    last = None
    while time.monotonic() < deadline:
        dom = page.evaluate(DOM_EXPRESSION)
        if dom == last:
            return dom
        last = dom
        time.sleep(0.4)
    return last


def type_text(page, text):
    for char in text:
        code = "Key" + char.upper() if char.isalpha() else ""
        vk = ord(char.upper()) if char.isalpha() else 0
        page.cdp.call("Input.dispatchKeyEvent", {
            "type": "keyDown", "text": char, "unmodifiedText": char, "key": char,
            "code": code, "windowsVirtualKeyCode": vk, "nativeVirtualKeyCode": vk,
        })
        page.cdp.call("Input.dispatchKeyEvent", {
            "type": "keyUp", "key": char, "code": code,
            "windowsVirtualKeyCode": vk, "nativeVirtualKeyCode": vk,
        })
        time.sleep(0.05)


def rect_of(page, expression):
    value = page.evaluate(
        "(()=>{const e=" + expression + ";if(!e)return null;const r=e.getBoundingClientRect();"
        "return {x:r.x+r.width/2,y:r.y+r.height/2};})()"
    )
    return value if isinstance(value, dict) else None


def click_option(page, option, timeout=8):
    """Click an already-open role=option by its exact text."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        rect = rect_of(page, f"[...document.querySelectorAll('[role=option]')].find(e=>e.textContent.trim()==={json.dumps(option)})")
        if rect:
            page.click(rect["x"], rect["y"])
            return True
        time.sleep(0.1)
    return False


def drive(page, name):
    if name == "02-radio-sms":
        rect = rect_of(page, "[...document.querySelectorAll('[data-testid=stRadio] label p')].find(p=>p.textContent.trim()==='sms')")
        if not rect:
            raise RuntimeError("radio option not found")
        page.click(rect["x"], rect["y"])
    elif name == "03-multiselect-beta":
        rect = rect_of(page, "document.querySelector('[data-testid=stMultiSelect] input')")
        if not rect:
            raise RuntimeError("multiselect input not found")
        page.click(rect["x"], rect["y"])
        time.sleep(0.4)
        if not click_option(page, "beta"):
            raise RuntimeError("multiselect option not found")
    elif name == "04-number-42":
        rect = rect_of(page, "document.querySelector('[data-testid=stNumberInput] input')")
        if not rect:
            raise RuntimeError("number input not found")
        page.click(rect["x"], rect["y"])
        time.sleep(0.2)
        page.press("End", "End", 35)
        page.press("Backspace", "Backspace", 8)
        type_text(page, "42")
    elif name == "05-textarea-append":
        rect = rect_of(page, "document.querySelector('[data-testid=stTextArea] textarea')")
        if not rect:
            raise RuntimeError("text area not found")
        page.click(rect["x"], rect["y"])
        time.sleep(0.2)
        page.press("End", "End", 35)
        type_text(page, " third")


def replay(path: str) -> int:
    raw = pathlib.Path(path).resolve()
    original = raw.read_bytes()
    trace = json.loads(original)
    observation = trace.get("observation")
    observation["ipc_dir"] = str(raw.parent)
    verdict = inputs_result(observation=observation)
    if raw.read_bytes() != original:
        raise RuntimeError("raw bytes changed during replay")
    print(json.dumps({"journey": trace.get("journey"), "raw_sha256": hashlib.sha256(original).hexdigest(),
                      **{key: verdict[key] for key in ("counts", "failures", "ok")}}, ensure_ascii=False))
    return 0 if verdict["ok"] else 1


def capture(args, out: pathlib.Path) -> int:
    side = "python" if args.scope == "PYTHON SIDE ONLY" else "native"
    source_path = ROOT / INPUTS_SOURCE_FILES[side]
    observation = {
        "journey": INPUTS_CASE,
        "contract": INPUTS_CONTRACT,
        "scope": args.scope,
        "url": args.url,
        "binary": args.binary or None,
        "runtime": side,
        "reference_version": "1.66.1",
        "source": {"file": source_path.relative_to(ROOT).as_posix()},
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
        recorder.call("Emulation.setDeviceMetricsOverride", {"width": 1264, "height": 1100, "deviceScaleFactor": 1, "mobile": False})
        page = Page(recorder)
        recorder.call("Page.navigate", {"url": args.url})

        seen = 0
        for name in INPUTS_STAGES:
            if name != "01-load":
                drive(page, name)
            settle(recorder, seen)
            frames = frames_from_events(recorder.take())
            new_frames = frames[seen:]
            seen = len(frames)
            dom = dom_stable(page)
            png = f"{name}.png"
            if not page.screenshot(out / png, restore=False):
                raise RuntimeError(f"screenshot failed: {name}")
            observation["stages"].append({
                "name": name,
                "new_frames": new_frames,
                "dom": dom,
                "screenshot": {"file": png, "sha256": digest(out / png)},
            })
            print(f"stage {name}: frames +{len(new_frames)}")
        verdict = inputs_result(observation=observation)
        trace = {"schema_version": 1, "journey": INPUTS_CASE, "contract": INPUTS_CONTRACT,
                 "scope": args.scope, "url": args.url, "observation": observation,
                 "counts": verdict["counts"], "failures": verdict["failures"]}
        (out / "trace-inputs.json").write_text(json.dumps(trace, ensure_ascii=False, indent=1), encoding="utf-8")
        manifest["exit_code"] = 0 if verdict["ok"] else 1
        print(json.dumps({"counts": verdict["counts"], "failures": verdict["failures"]}, ensure_ascii=False))
        return 0 if verdict["ok"] else 1
    except Exception as exc:
        (out / "trace-inputs.json").write_text(json.dumps({"journey": INPUTS_CASE, "observation": observation,
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
    parser.add_argument("--label", default="inputs")
    parser.add_argument("--out", default="")
    parser.add_argument("--scope", default="PYTHON SIDE ONLY")
    parser.add_argument("--port", type=int, default=60950, help="DevTools port of the owned Chrome")
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
    out = pathlib.Path(args.out or f"target/inputs-{args.label}")
    out.mkdir(parents=True, exist_ok=True)
    return capture(args, out)


if __name__ == "__main__":
    raise SystemExit(main())
