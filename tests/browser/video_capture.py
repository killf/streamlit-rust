"""Collect the video journey on one owned Chrome.

    python tests/browser/video_capture.py --url http://127.0.0.1:8610 \
        --label python-video --scope "PYTHON SIDE ONLY" --out target/video-python

WHAT THIS RECORDS
    The decoded bidirectional WebSocket frames of the official 1.66.1
    frontend for the measured video page (the committed one-second sample
    under its default st.video call), the real GET /media/{file_id}.mp4
    round trip (status, content type, accept-ranges, content-range, body
    digest), the settled DOM end state (resolved video src, controls,
    muted/loop/autoplay, exceptions), a PNG of the page, the driven
    application source identity, and the loaded capture sources. The verdict
    is computed by the strict contract (video_contract.py); this collector
    only records what the runtime did and exits by that verdict.
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
from video_contract import VIDEO_CASE, VIDEO_CONTRACT, VIDEO_STAGES, video_result  # noqa: E402

DOM_EXPRESSION = r"""JSON.stringify({
markdowns:[...document.querySelectorAll("[data-testid=stMarkdown]")].map(e=>e.textContent.trim()),
videos:[...document.querySelectorAll("video")].map(e=>({src:e.querySelector("source")?.getAttribute("src") ?? e.getAttribute("src"),controls:e.hasAttribute("controls"),muted:e.muted,loop:e.loop,autoplay:e.autoplay,testid:e.closest("[data-testid]")?.getAttribute("data-testid")})),
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


def wait_for_finish(recorder, timeout=30):
    """Wait for the run's script_finished frame, then let the media GET land."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        finished = False
        for event in recorder.take():
            if event.get("method") != "Network.webSocketFrameReceived":
                continue
            payload = ((event.get("params") or {}).get("response") or {}).get("payloadData") or ""
            try:
                data = base64.b64decode(payload, validate=True)
            except Exception:
                continue
            # The decoded kind, never a byte pattern: the reference leaves
            # ForwardMsg.hash empty where the Rust side spells the name out.
            try:
                if summarise_forward(data).get("type") == "script_finished":
                    finished = True
            except Exception:
                continue
        if finished:
            time.sleep(3)
            return
        time.sleep(0.5)
    raise RuntimeError("the run never finished")


def http_media_log(recorder, events):
    """Every /media request the page made, with response metadata and body."""
    requests = {}
    for event in events:
        method = event.get("method")
        params = event.get("params") or {}
        if method == "Network.requestWillBeSent":
            requests[params["requestId"]] = {"url": params["request"]["url"], "method": params["request"]["method"],
                                             "headers": params["request"].get("headers", {})}
        elif method == "Network.responseReceived":
            response = params["response"]
            record = requests.setdefault(params["requestId"], {"url": response["url"], "method": "?"})
            record["status"] = response["status"]
            record["mime"] = response["mimeType"]
            record["headers"] = response.get("headers", {})
    from urllib.parse import urlsplit

    out = []
    for request_id, record in requests.items():
        if not urlsplit(record.get("url", "")).path.startswith("/media/"):
            continue
        try:
            message = recorder.call("Network.getResponseBody", {"requestId": request_id})
            inner = message["result"]
            raw = base64.b64decode(inner["body"]) if inner.get("base64Encoded") else inner["body"].encode("utf-8")
            record["body"] = {"base64": bool(inner.get("base64Encoded")),
                              "sha256": hashlib.sha256(raw).hexdigest(),
                              "length": len(raw)}
        except Exception as exc:
            record["body"] = {"error": f"{type(exc).__name__}: {exc}"}
        out.append(record)
    return out


def dom_stable(recorder, timeout=6.0):
    """Read the DOM until two reads agree: a rerun's React commit may lag
    the last WebSocket frame."""
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


def replay(path: str) -> int:
    raw = pathlib.Path(path).resolve()
    original = raw.read_bytes()
    trace = json.loads(original)
    observation = trace.get("observation")
    observation["ipc_dir"] = str(raw.parent)
    verdict = video_result(observation=observation)
    if raw.read_bytes() != original:
        raise RuntimeError("raw bytes changed during replay")
    print(json.dumps({"journey": trace.get("journey"), "raw_sha256": hashlib.sha256(original).hexdigest(),
                      **{key: verdict[key] for key in ("counts", "failures", "ok")}}, ensure_ascii=False))
    return 0 if verdict["ok"] else 1


def capture(args, out: pathlib.Path) -> int:
    side = "python" if args.scope == "PYTHON SIDE ONLY" else "native"
    source_path = ROOT / ("tests/reference/video_app.py" if side == "python" else "streamlit/examples/video.rs")
    observation = {
        "journey": VIDEO_CASE,
        "contract": VIDEO_CONTRACT,
        "scope": args.scope,
        "url": args.url,
        "binary": args.binary or None,
        "source": {"file": source_path.relative_to(ROOT).as_posix(), "sha256": digest(source_path)},
        "capture_sources": {name: digest(ROOT / "tests/browser" / name) for name in ("video_capture.py", "video_contract.py")},
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
        recorder.call("Network.enable")
        recorder.call("Page.enable")
        recorder.call("Emulation.setDeviceMetricsOverride", {"width": 1264, "height": 1100, "deviceScaleFactor": 1, "mobile": False})
        recorder.call("Page.navigate", {"url": args.url})

        for name in VIDEO_STAGES:
            wait_for_finish(recorder)
            events = recorder.take()
            frames = frames_from_events(events)
            http_log = http_media_log(recorder, events)
            dom = dom_stable(recorder)
            png = f"{name}.png"
            message = recorder.call("Page.captureScreenshot", {"format": "png"})
            (out / png).write_bytes(base64.b64decode(message["result"]["data"]))
            observation["stages"].append({
                "name": name,
                "new_frames": frames,
                "http": http_log,
                "dom": dom,
                "screenshot": {"file": png, "sha256": digest(out / png)},
            })
            print(f"stage {name}: frames {len(frames)}, media GETs {len(http_log)}")
        verdict = video_result(observation=observation)
        trace = {"schema_version": 1, "journey": VIDEO_CASE, "contract": VIDEO_CONTRACT,
                 "scope": args.scope, "url": args.url, "observation": observation,
                 "counts": verdict["counts"], "failures": verdict["failures"]}
        (out / "trace-video.json").write_text(json.dumps(trace, ensure_ascii=False, indent=1), encoding="utf-8")
        manifest["exit_code"] = 0 if verdict["ok"] else 1
        print(json.dumps({"counts": verdict["counts"], "failures": verdict["failures"]}, ensure_ascii=False))
        return 0 if verdict["ok"] else 1
    except Exception as exc:
        (out / "trace-video.json").write_text(json.dumps({"journey": VIDEO_CASE, "observation": observation,
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
    parser.add_argument("--label", default="video")
    parser.add_argument("--out", default="")
    parser.add_argument("--scope", default="PYTHON SIDE ONLY")
    parser.add_argument("--port", type=int, default=60975, help="DevTools port of the owned Chrome")
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
    out = pathlib.Path(args.out or f"target/video-{args.label}")
    out.mkdir(parents=True, exist_ok=True)
    return capture(args, out)


if __name__ == "__main__":
    raise SystemExit(main())
