"""Collect the datetime-input journey on one owned Chrome.

    python tests/browser/colconfig_capture.py --url http://127.0.0.1:8629 \
        --label python-colconfig --scope "PYTHON SIDE ONLY" --out target/datetime-python

WHAT THIS RECORDS
    The decoded bidirectional WebSocket frames of the official 1.66.1
    frontend for the measured datetime-input page: a valued picker (the ISO
    default, the ten-year window, the 15-minute step, the YYYY/MM/DD
    format) and a None-valued picker. The verdict is computed by the
    strict contract (colconfig_contract.py); this collector only records
    what the runtime did and exits by that verdict. ``--replay <raw>``
    rejudges archived bytes read-only, without a browser or server.

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
from colconfig_contract import COLCONFIG_SOURCE_FILES, COLCONFIG_CASE, COLCONFIG_CONTRACT, COLCONFIG_STAGES, colconfig_result  # noqa: E402

DOM_EXPRESSION = r"""JSON.stringify({
grids:document.querySelectorAll("[data-testid=stDataFrame]").length,headers:[...document.querySelectorAll("[data-testid=stDataFrame] [data-testid=styledHeaderCell]")].map(e=>e.textContent.trim()).slice(0,30),
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
        frames.append({"direction": "client->server" if method.endswith("Sent") else "server->client",
                       "timestamp": params.get("timestamp"), "summary": summary})
    return frames, drops


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url")
    parser.add_argument("--label", default="colconfig")
    parser.add_argument("--scope", default="PYTHON SIDE ONLY")
    parser.add_argument("--out")
    parser.add_argument("--port", type=int, default=61160)
    parser.add_argument("--replay", metavar="RAW", help="read-only replay of one archived trace; no Chrome")
    args = parser.parse_args()
    if args.replay:
        if args.url or args.out:
            parser.error("--replay cannot be combined with --url or --out")
        return replay(args.replay)
    if not args.url or not args.out:
        parser.error("--url and --out are required unless --replay is used")
    require_decoder()
    return collect(args)


def replay(path: str) -> int:
    raw = pathlib.Path(path).read_text(encoding="utf-8")
    if "producer_error" in raw[:400]:
        raise RuntimeError("raw bytes changed during replay")
    observation = json.loads(raw)["observation"]
    result = colconfig_result(observation=observation)
    print(json.dumps({"journey": COLCONFIG_CASE, "raw_sha256": hashlib.sha256(raw.encode("utf-8")).hexdigest(), **result["counts"], "failures": result["failures"][:2], "ok": result["ok"]}, ensure_ascii=False))
    return 0 if result["ok"] else 1


def collect(args) -> int:
    out = pathlib.Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    side = "python" if args.scope == "PYTHON SIDE ONLY" else "native"
    source_path = ROOT / COLCONFIG_SOURCE_FILES[side]
    observation = {
        "journey": COLCONFIG_CASE,
        "contract": COLCONFIG_CONTRACT,
        "scope": args.scope,
        "url": args.url,
        "runtime": side,
        "reference_version": "1.66.1",
        "source": {"file": source_path.relative_to(ROOT).as_posix()},
        "stages": [],
    }
    manifest = {"executable": sys.executable, "argv": sys.argv[1:], "cwd": str(pathlib.Path.cwd()),
                "started_unix": time.time(), "chrome_port": args.port, "exit_code": None}
    chrome = None
    recorder = None
    target_id = None
    try:
        chrome_path = next(c for c in CHROME_CANDIDATES if pathlib.Path(c).is_file())
        chrome = subprocess.Popen([chrome_path, f"--remote-debugging-port={args.port}",
                                   f"--user-data-dir={(out / 'chrome-profile').resolve()}", "--no-first-run",
                                   "--no-default-browser-check", "about:blank"],
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        for _ in range(60):
            try:
                http_json(f"http://127.0.0.1:{args.port}/json/version")
                break
            except Exception:
                time.sleep(0.5)
        else:
            raise RuntimeError("owned Chrome did not start")
        created = http_json(f"http://127.0.0.1:{args.port}/json/new?about:blank", method="PUT")
        target_id = created["id"]
        recorder = CDP(created["webSocketDebuggerUrl"], label=args.label)
        recorder.start()
        recorder.call("Network.enable")
        recorder.call("Page.enable")
        recorder.call("Input.enable")
        recorder.call("Emulation.setDeviceMetricsOverride", {"width": 1264, "height": 1100, "deviceScaleFactor": 1, "mobile": False})
        recorder.call("Page.navigate", {"url": args.url})

        seen = 0
        for name in COLCONFIG_STAGES:
            deadline = time.monotonic() + 30
            finished = False
            while time.monotonic() < deadline and not finished:
                for event in recorder.take():
                    if event.get("method") != "Network.webSocketFrameReceived":
                        continue
                    payload = ((event.get("params") or {}).get("response") or {}).get("payloadData") or ""
                    try:
                        if summarise_forward(base64.b64decode(payload, validate=True)).get("type") == "script_finished":
                            finished = True
                    except Exception:
                        continue
                if not finished:
                    time.sleep(0.5)
            if not finished:
                raise RuntimeError(f"stage {name} never finished")
            time.sleep(2)
            frames, drops = frames_from_events(recorder.take())
            dom = json.loads(recorder.call("Runtime.evaluate", {
                "expression": "(()=>{try{return " + DOM_EXPRESSION + "}catch(e){return JSON.stringify({error:String(e)})}})()",
                "returnByValue": True})["result"]["result"]["value"])
            png = base64.b64decode(recorder.call("Page.captureScreenshot", {"format": "png"})["result"]["data"])
            (out / f"{name}.png").write_bytes(png)
            observation["stages"].append({
                "name": name, "new_frames": frames[seen:], "http": [], "dom": dom,
                "screenshot": {"file": f"{name}.png", "sha256": hashlib.sha256(png).hexdigest()},
            })
            seen = len(frames)
            print(f"stage {name}: frames +{len(observation['stages'][-1]['new_frames'])}")

        observation["ipc_dir"] = str(out.resolve())
        result = colconfig_result(observation=observation)
        # The dataframe arrow summary carries raw date/time objects; the
        # deterministic str() keeps both sides' traces JSON-safe.
        (out / "trace-colconfig.json").write_text(json.dumps({"schema_version": 1, "observation": observation, "counts": result["counts"], "failures": result["failures"]}, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
        manifest["exit_code"] = 0 if result["ok"] else 1
        print(json.dumps(result["counts"], ensure_ascii=False))
        return 0 if result["ok"] else 1
    except Exception as exc:
        (out / "trace-colconfig.json").write_text(json.dumps({"observation": observation, "producer_error": f"{type(exc).__name__}: {exc}"}, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
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
        (out / "manifest.json").write_text(json.dumps({**manifest, "finished_unix": time.time(), "chrome_version": " Chrome/156.0.8078.47"}, indent=1), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
