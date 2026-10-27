"""Collect the elements journey on one owned Chrome.

    python tests/browser/elements_capture.py --url http://127.0.0.1:8607 \
        --label python-elements --scope "PYTHON SIDE ONLY" --out target/elements-python

WHAT THIS RECORDS
    The decoded bidirectional WebSocket frames of the official 1.66.1
    frontend across two stages (the initial load of the fifteen-API page,
    then typing into the form's Note input and clicking Apply), the DOM
    fingerprint of each stage (ordered testids/texts, headings, code blocks,
    table text, chart bars, the note value, exceptions), a PNG per stage, the
    driven application source identity, and the loaded capture sources. The
    verdict is computed by the strict contract (elements_contract.py); this
    collector only records what the runtime did and exits by that verdict.
    ``--replay <raw>`` rejudges archived bytes read-only, without a browser
    or server.

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
from elements_contract import ELEMENTS_SOURCE_FILES, ELEMENTS_CASE, ELEMENTS_CONTRACT, ELEMENTS_STAGES, elements_result  # noqa: E402

DOM_EXPRESSION = r"""JSON.stringify({
items:[...document.querySelectorAll("[data-testid]")]
 .filter(e=>["stTitle","stHeader","stSubheader","stCaption","stBadge","stCodeBlock","stMarkdown",
 "stColumn","stVerticalBlock","stForm","stTable","stVegaLiteChart","stTextInput",
 "stFormSubmitButton","stHorizontalBlock"].includes(e.getAttribute("data-testid")))
 .map(e=>({t:e.getAttribute("data-testid"),x:(e.innerText||"").replace(/\s+/g," ").trim().slice(0,160)})),
headings:[...document.querySelectorAll("h1,h2,h3")].map(e=>e.tagName+":"+e.textContent.trim()),
code_blocks:[...document.querySelectorAll("[data-testid=stCodeBlock], [data-testid=stCode], pre")]
 .map(e=>(e.innerText||"").replace(/\s+/g," ").trim().slice(0,120)),
note:document.querySelector("[data-testid=stTextInput] input")?.value??null,
chart_bars:document.querySelectorAll("[data-testid=stVegaLiteChart] g[class*=mark-rect] path").length,
table_cells:[...document.querySelectorAll("[data-testid=stTable] [role=gridcell]")].map(e=>e.textContent.trim()).slice(0,12),
markdowns:[...document.querySelectorAll("[data-testid=stMarkdown]")].map(e=>e.textContent.trim()),
exceptions:[...document.querySelectorAll("[data-testid=stException]")].map(e=>e.innerText.slice(0,200))})"""


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


def type_text(page, text):
    """Type with real key events, one key press per character."""
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


def drive_apply(page):
    """Stage two: type ' typed' after the current note and click Apply."""
    box = rect_of(page, "[...document.querySelectorAll('[data-testid=stTextInput]')].find(e=>e.textContent.includes('Note'))?.querySelector('input')")
    if not box:
        raise RuntimeError("Note input not found")
    page.click(box["x"], box["y"])
    time.sleep(0.3)
    page.press("End", "End", 35)
    type_text(page, " typed")
    apply_rect = rect_of(page, "[...document.querySelectorAll('[data-testid=stFormSubmitButton] button')].find(b=>b.textContent.trim()==='Apply')")
    if not apply_rect:
        raise RuntimeError("Apply button not found")
    page.click(apply_rect["x"], apply_rect["y"])


def replay(path: str) -> int:
    raw = pathlib.Path(path).resolve()
    original = raw.read_bytes()
    trace = json.loads(original)
    observation = trace.get("observation")
    observation["ipc_dir"] = str(raw.parent)
    verdict = elements_result(observation=observation)
    if raw.read_bytes() != original:
        raise RuntimeError("raw bytes changed during replay")
    print(json.dumps({"journey": trace.get("journey"), "raw_sha256": hashlib.sha256(original).hexdigest(),
                      **{key: verdict[key] for key in ("counts", "failures", "ok")}}, ensure_ascii=False))
    return 0 if verdict["ok"] else 1


def capture(args, out: pathlib.Path) -> int:
    side = "python" if args.scope == "PYTHON SIDE ONLY" else "native"
    source_path = ROOT / ELEMENTS_SOURCE_FILES[side]
    observation = {
        "journey": ELEMENTS_CASE,
        "contract": ELEMENTS_CONTRACT,
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
        recorder.call("Emulation.setDeviceMetricsOverride", {"width": 1264, "height": 1200, "deviceScaleFactor": 1, "mobile": False})
        page = Page(recorder)
        recorder.call("Page.navigate", {"url": args.url})

        seen = 0
        for name in ELEMENTS_STAGES:
            if name == "02-apply":
                drive_apply(page)
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
                "action": "load" if name == ELEMENTS_STAGES[0] else "type-and-apply",
                "new_frames": new_frames,
                "dom": dom,
                "screenshot": {"file": png, "sha256": digest(out / png)},
            })
            print(f"stage {name}: frames +{len(new_frames)}")
        verdict = elements_result(observation=observation)
        trace = {"schema_version": 1, "journey": ELEMENTS_CASE, "contract": ELEMENTS_CONTRACT,
                 "scope": args.scope, "url": args.url, "observation": observation,
                 "counts": verdict["counts"], "failures": verdict["failures"]}
        (out / "trace-elements.json").write_text(json.dumps(trace, ensure_ascii=False, indent=1), encoding="utf-8")
        manifest["exit_code"] = 0 if verdict["ok"] else 1
        print(json.dumps({"counts": verdict["counts"], "failures": verdict["failures"]}, ensure_ascii=False))
        return 0 if verdict["ok"] else 1
    except Exception as exc:
        (out / "trace-elements.json").write_text(json.dumps({"journey": ELEMENTS_CASE, "observation": observation,
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


CHROME_CANDIDATES = (
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url")
    parser.add_argument("--label", default="elements")
    parser.add_argument("--out", default="")
    parser.add_argument("--scope", default="PYTHON SIDE ONLY")
    parser.add_argument("--port", type=int, default=60940, help="DevTools port of the owned Chrome")
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
    out = pathlib.Path(args.out or f"target/elements-{args.label}")
    out.mkdir(parents=True, exist_ok=True)
    return capture(args, out)


if __name__ == "__main__":
    raise SystemExit(main())
