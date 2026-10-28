"""Capture the zero-column UI with an owned Chrome and real input events."""
import argparse
import base64
from datetime import datetime, timezone
import importlib.metadata
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "tests/browser"), str(ROOT / "tests/reference")]
from componentv2_state_capture import Recorder, _cleanup_owned, finished, frames, free_port, wait_run
from componenttrigger_capture import CHROME_CANDIDATES, click, evaluate, http_json, rect


def collect(args):
    if importlib.metadata.version("streamlit") != "1.66.1":
        raise RuntimeError("requires the pinned Streamlit 1.66.1 decoder environment")
    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=False)
    chrome_port = free_port()
    server_port = free_port() if not args.url else None
    url = args.url or f"http://127.0.0.1:{server_port}/"
    command = [sys.executable, "-B", "-m", "streamlit", "run", str(ROOT / "tests/reference/zero_columns_app.py"),
               "--server.address=127.0.0.1", f"--server.port={server_port}", "--server.headless=true",
               "--server.fileWatcherType=none", "--browser.gatherUsageStats=false", "--", "--ui"]
    capture = {"runtime": "rust" if args.url else "python", "reference_decoder": "1.66.1", "url": url,
               "captured_at_utc": datetime.now(timezone.utc).isoformat(), "server_command": None if args.url else command,
               "server_cleanup": "caller-owned" if args.url else "collector-owned",
               "recorder_label_note": "Recorder inherits python-componentv2-state label independently of runtime", "stages": []}
    server = chrome = recorder = None
    profile = tempfile.TemporaryDirectory(prefix="zero-columns-", dir=out)
    try:
        with (out / "server.log").open("w", encoding="utf-8") as server_log, (out / "chrome.log").open("w", encoding="utf-8") as chrome_log:
            flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            if not args.url:
                server = subprocess.Popen(command, cwd=ROOT, stdout=server_log, stderr=subprocess.STDOUT, creationflags=flags)
                capture["server_pid"] = server.pid
            deadline = time.monotonic() + 30
            while True:
                try:
                    with urllib.request.urlopen(url.rstrip("/") + "/_stcore/health", timeout=1) as response:
                        capture["health"] = {"status": response.status, "body": response.read().decode()}
                    break
                except OSError:
                    if time.monotonic() > deadline or server is not None and server.poll() is not None:
                        raise RuntimeError("server unavailable")
                    time.sleep(0.1)
            chrome_path = next(path for path in CHROME_CANDIDATES if Path(path).is_file())
            chrome_command = [chrome_path, "--headless=new", "--disable-gpu", f"--remote-debugging-port={chrome_port}",
                              f"--user-data-dir={profile.name}", "--no-first-run", "--no-default-browser-check", "about:blank"]
            chrome = subprocess.Popen(chrome_command, stdout=chrome_log, stderr=subprocess.STDOUT, creationflags=flags)
            capture.update(chrome_pid=chrome.pid, chrome_command=chrome_command)
            deadline = time.monotonic() + 30
            while True:
                try:
                    capture["browser"] = http_json(f"http://127.0.0.1:{chrome_port}/json/version")
                    break
                except OSError:
                    if time.monotonic() > deadline or chrome.poll() is not None:
                        raise RuntimeError("owned Chrome unavailable")
                    time.sleep(0.1)
            target = http_json(f"http://127.0.0.1:{chrome_port}/json/new?about:blank", method="PUT")
            recorder = Recorder(target["webSocketDebuggerUrl"])
            recorder.start()
            recorder.call("Network.enable")
            recorder.call("Runtime.enable")
            recorder.call("Log.enable")
            recorder.call("Emulation.setDeviceMetricsOverride", {"width": 1264, "height": 1100, "deviceScaleFactor": 1, "mobile": False})
            actions = [("zero-initial", None), ("two-rows", "checkbox"), ("ordinary-rerun", "button"), ("zero-again", "checkbox")]
            before = seen = 0
            for name, control in actions:
                if control is None:
                    recorder.call("Page.navigate", {"url": url})
                else:
                    expression = ("[...document.querySelectorAll('[data-testid=stCheckbox]')].find(e=>e.textContent.includes('Two rows')).querySelector('label')"
                                  if control == "checkbox" else "[...document.querySelectorAll('button')].find(e=>e.textContent.trim()==='Ordinary rerun')")
                    evaluate(recorder, "(()=>{const e=" + expression + ";if(!e)return false;e.scrollIntoView({block:'center'});return true;})()")
                    point = rect(recorder, expression)
                    if point is None:
                        raise RuntimeError("control missing: " + name)
                    click(recorder, point)
                wait_run(recorder, before)
                before = finished(recorder)
                all_frames = frames(recorder)
                dom = json.loads(evaluate(recorder, "JSON.stringify({text:document.body.innerText,checkboxes:[...document.querySelectorAll('input[type=checkbox]')].map(e=>({checked:e.checked})),grids:[...document.querySelectorAll('[data-testid=stDataFrame]')].map(e=>({text:e.innerText,cells:[...e.querySelectorAll('[data-testid^=glide-cell]')].map(c=>({id:c.getAttribute('data-testid'),text:c.textContent})),canvas:!!e.querySelector('canvas')})),tables:[...document.querySelectorAll('table')].map(e=>e.innerText),exceptions:[...document.querySelectorAll('[data-testid=stException]')].map(e=>e.innerText)})"))
                metrics = recorder.call("Page.getLayoutMetrics")["result"]["cssContentSize"]
                png = recorder.call("Page.captureScreenshot", {"format": "png", "captureBeyondViewport": True,
                                    "clip": {"x": 0, "y": 0, "width": metrics["width"], "height": metrics["height"], "scale": 1}})["result"]["data"]
                (out / f"{name}.png").write_bytes(base64.b64decode(png))
                capture["stages"].append({"name": name, "frame_start": seen, "frame_end": len(all_frames), "dom": dom, "screenshot": name + ".png"})
                seen = len(all_frames)
                print(name, "exceptions", dom["exceptions"], "grids", len(dom["grids"]), flush=True)
            capture["frames"] = frames(recorder)
            capture["console_errors"] = [e for e in recorder.take() if e.get("method") in ("Runtime.exceptionThrown", "Log.entryAdded", "Runtime.consoleAPICalled")]
            capture["successful"] = True
    except Exception as error:
        capture["producer_error"] = f"{type(error).__name__}: {error}"
        raise
    finally:
        _cleanup_owned(capture, recorder, chrome, server, profile, out)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", help="caller-owned Rust server URL; otherwise start Python reference")
    parser.add_argument("--out", required=True)
    collect(parser.parse_args())
