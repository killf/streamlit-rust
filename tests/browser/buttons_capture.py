"""Collect the button-family journey on one owned Chrome.

    python tests/browser/buttons_capture.py --url http://127.0.0.1:8623 \
        --label python-buttons --scope "PYTHON SIDE ONLY" --out target/buttons-python

WHAT THIS RECORDS
    The decoded bidirectional WebSocket frames of the official 1.66.1
    frontend for the measured button-family page (two toggles, two
    feedbacks, three button groups, a pagination, a menu button, a download
    button, a link button and an external page link) across six
    real-interaction stages: the load and one committed interaction each
    for the toggle, the single-select pill, the pagination page, the
    feedback star and the menu pick. Each stage pins every element's full
    wire message, the browser's widget-state report and the settled DOM.
    The verdict is computed by the strict contract (buttons_contract.py);
    this collector only records what the runtime did and exits by that
    verdict. ``--replay <raw>`` rejudges archived bytes read-only, without
    a browser or server.

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
from buttons_contract import BUTTONS_CASE, BUTTONS_CONTRACT, BUTTONS_STAGES, buttons_result  # noqa: E402

DOM_EXPRESSION = r"""JSON.stringify({
buttons:[...document.querySelectorAll("button")].map(e=>e.textContent.trim().slice(0,40)),
checkboxes:[...document.querySelectorAll("[data-testid=stCheckbox]")].map(e=>e.innerText.trim().slice(0,60)),
markdowns:[...document.querySelectorAll("section.main [data-testid=stMarkdown]")].map(e=>e.textContent.trim()),
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


def wait_for_finish(recorder, timeout=30):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        for event in recorder.take():
            if event.get("method") != "Network.webSocketFrameReceived":
                continue
            payload = ((event.get("params") or {}).get("response") or {}).get("payloadData") or ""
            try:
                data = base64.b64decode(payload, validate=True)
            except Exception:
                continue
            try:
                if summarise_forward(data).get("type") == "script_finished":
                    time.sleep(2.5)
                    return True
            except Exception:
                continue
        time.sleep(0.5)
    return False


def dom_stable(recorder, timeout=6.0):
    deadline = time.monotonic() + timeout
    last = None
    while time.monotonic() < deadline:
        message = recorder.call("Runtime.evaluate", {
            "expression": "(()=>{try{return " + DOM_EXPRESSION + "}catch(e){return JSON.stringify({error:String(e)})}})()",
            "returnByValue": True})
        dom = json.loads(message["result"]["result"]["value"])
        if dom == last:
            return dom
        last = dom
        time.sleep(0.4)
    return last


def click(recorder, expression, what):
    found = recorder.call("Runtime.evaluate", {
        "expression": "(()=>{const e=" + expression + ";if(!e)return null;const r=e.getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2};})()",
        "returnByValue": True})
    rect = found["result"]["result"].get("value")
    if not rect:
        raise RuntimeError(f"{what} not found")
    recorder.call("Input.dispatchMouseEvent", {"type": "mousePressed", "x": rect["x"], "y": rect["y"], "button": "left", "buttons": 1, "clickCount": 1})
    recorder.call("Input.dispatchMouseEvent", {"type": "mouseReleased", "x": rect["x"], "y": rect["y"], "button": "left", "buttons": 0, "clickCount": 1})


def replay(path: str) -> int:
    raw = pathlib.Path(path).resolve()
    original = raw.read_bytes()
    trace = json.loads(original)
    observation = trace.get("observation")
    observation["ipc_dir"] = str(raw.parent)
    verdict = buttons_result(observation=observation)
    if raw.read_bytes() != original:
        raise RuntimeError("raw bytes changed during replay")
    print(json.dumps({"journey": trace.get("journey"), "raw_sha256": hashlib.sha256(original).hexdigest(),
                      **{key: verdict[key] for key in ("counts", "failures", "ok")}}, ensure_ascii=False))
    return 0 if verdict["ok"] else 1


def capture(args, out: pathlib.Path) -> int:
    side = "python" if args.scope == "PYTHON SIDE ONLY" else "native"
    source_path = ROOT / ("tests/reference/buttons_app.py" if side == "python" else "streamlit/examples/buttons.rs")
    observation = {
        "journey": BUTTONS_CASE,
        "contract": BUTTONS_CONTRACT,
        "scope": args.scope,
        "url": args.url,
        "binary": args.binary or None,
        "source": {"file": source_path.relative_to(ROOT).as_posix(), "sha256": digest(source_path)},
        "capture_sources": {name: digest(ROOT / "tests/browser" / name) for name in ("buttons_capture.py", "buttons_contract.py")},
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
            raise RuntimeError("owned Chrome did not start")
        manifest["chrome_version"] = version["Browser"]
        before = http_json(f"http://127.0.0.1:{args.port}/json/list")
        created = http_json(f"http://127.0.0.1:{args.port}/json/new?about:blank", method="PUT")
        target_id = created["id"]
        if target_id in {target["id"] for target in before}:
            raise RuntimeError("new tab id is not fresh; refusing attachment")
        recorder = CDP(created["webSocketDebuggerUrl"], label=args.label)
        recorder.start()
        recorder.call("Performance.enable")
        recorder.call("Network.enable")
        recorder.call("Page.enable")
        recorder.call("Input.enable")
        recorder.call("Emulation.setDeviceMetricsOverride", {"width": 1264, "height": 1100, "deviceScaleFactor": 1, "mobile": False})
        recorder.call("Page.navigate", {"url": args.url})
        seen = 0

        def snapshot(name):
            nonlocal seen
            if not wait_for_finish(recorder):
                raise RuntimeError(f"stage {name} never finished")
            frames = frames_from_events(recorder.take())
            observation["stages"].append({"name": name, "new_frames": frames[seen:], "http": [],
                                          "dom": dom_stable(recorder), "screenshot": None})
            seen = len(frames)
            png = f"{name}.png"
            message = recorder.call("Page.captureScreenshot", {"format": "png"})
            (out / png).write_bytes(base64.b64decode(message["result"]["data"]))
            observation["stages"][-1]["screenshot"] = {"file": png, "sha256": digest(out / png)}
            print(f"stage {name}: frames +{len(observation['stages'][-1]['new_frames'])}")

        snapshot("01-load")

        click(recorder,
              "[...document.querySelectorAll('[data-testid=stCheckbox]')].find(e=>e.innerText.includes('Night mode'))",
              "night mode toggle")
        snapshot("02-toggle")

        click(recorder,
              "[...document.querySelectorAll('button')].find(e=>e.textContent.trim()==='high')",
              "priority pill high")
        snapshot("03-pills")

        click(recorder,
              "[...document.querySelectorAll('button')].filter(e=>e.textContent.trim()==='2')[0]",
              "pagination page 2")
        snapshot("04-pagination")

        click(recorder,
              "[...document.querySelectorAll('[data-testid=stFeedback]')][0]?.querySelectorAll('button')[2]",
              "third feedback star")
        snapshot("05-feedback")

        click(recorder,
              "[...document.querySelectorAll('button')].find(e=>e.textContent.trim().startsWith('Export'))",
              "export menu button")
        time.sleep(1.0)
        click(recorder,
              "[...document.querySelectorAll('[data-testid=stPopoverBody] button,[role=menuitem],button')].find(e=>e.textContent.trim()==='CSV')",
              "export CSV option")
        snapshot("06-menu")

        verdict = buttons_result(observation=observation)
        trace = {"schema_version": 1, "journey": BUTTONS_CASE, "contract": BUTTONS_CONTRACT,
                 "scope": args.scope, "url": args.url, "observation": observation,
                 "counts": verdict["counts"], "failures": verdict["failures"]}
        (out / "trace-buttons.json").write_text(json.dumps(trace, ensure_ascii=False, indent=1), encoding="utf-8")
        manifest["exit_code"] = 0 if verdict["ok"] else 1
        print(json.dumps({"counts": verdict["counts"], "failures": verdict["failures"]}, ensure_ascii=False))
        return 0 if verdict["ok"] else 1
    except Exception as exc:
        (out / "trace-buttons.json").write_text(json.dumps({"journey": BUTTONS_CASE, "observation": observation,
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
    parser.add_argument("--label", default="buttons")
    parser.add_argument("--out", default="")
    parser.add_argument("--scope", default="PYTHON SIDE ONLY")
    parser.add_argument("--port", type=int, default=61058, help="DevTools port of the owned Chrome")
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
    out = pathlib.Path(args.out or f"target/buttons-{args.label}")
    out.mkdir(parents=True, exist_ok=True)
    return capture(args, out)


if __name__ == "__main__":
    raise SystemExit(main())
