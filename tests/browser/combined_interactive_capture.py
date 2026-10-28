"""The second M7 combined differential: an interactive flow in the real UI.

One owned Chrome drives the same click/upload flow against the pinned Python
1.66.1 app or a caller-owned Rust server: load, upload two files, check the
checkbox, pick option b, click dataframe row 2, click Apply (toast). Each
stage records the wire frames, the report block's JSON, and the DOM state.
"""
import argparse
import base64
from datetime import datetime, timezone
import importlib.metadata
import json
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import time
import urllib.request

from google.protobuf.json_format import MessageToDict
from streamlit.proto.BackMsg_pb2 import BackMsg
from streamlit.proto.ForwardMsg_pb2 import ForwardMsg

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "tests/browser"), str(ROOT / "tests/reference")]
from componentv2_state_capture import Recorder, free_port
from componenttrigger_capture import CHROME_CANDIDATES, click, evaluate, http_json, rect

UPLOADS = {"alpha.txt": b"alpha-payload-01\n", "beta.csv": b"key,value\na,1\n"}
STAGES = ["load", "upload-two", "check", "pick-b", "select-row-2", "apply"]


def collect(args):
    if importlib.metadata.version("streamlit") != "1.66.1":
        raise RuntimeError("requires the pinned Streamlit 1.66.1 decoder environment")
    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=False)
    inputs = out / "inputs"
    inputs.mkdir()
    for name, data in UPLOADS.items():
        (inputs / name).write_bytes(data)
    chrome_port = free_port()
    server = None
    if args.url:
        url = args.url.rstrip("/")
    else:
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            port = listener.getsockname()[1]
        url = f"http://127.0.0.1:{port}/"
        command = [sys.executable, "-B", "-m", "streamlit", "run", str(ROOT / "tests/reference/combined_interactive_app.py"),
                   "--server.address=127.0.0.1", f"--server.port={port}", "--server.headless=true",
                   "--server.fileWatcherType=none", "--browser.gatherUsageStats=false"]
    capture = {"runtime": "rust" if args.url else "python", "reference_version": "1.66.1", "url": url,
               "captured_at_utc": datetime.now(timezone.utc).isoformat(),
               "server_command": None if args.url else command,
               "server_cleanup": "caller-owned" if args.url else "collector-owned",
               "stages": [], "frames": [], "uploads": []}
    chrome = recorder = None
    profile = (out / "chrome-profile").resolve()
    profile.mkdir()
    try:
        with (out / "server.log").open("w", encoding="utf-8") as server_log:
            flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            if not args.url:
                server = subprocess.Popen(command, cwd=ROOT, stdout=server_log, stderr=subprocess.STDOUT, creationflags=flags)
                capture["server_pid"] = server.pid
            base = url.split("?")[0].rstrip("/")
            deadline = time.monotonic() + 30
            while True:
                try:
                    with urllib.request.urlopen(base + "/_stcore/health", timeout=1) as response:
                        capture["health"] = {"status": response.status, "body": response.read().decode()}
                    break
                except OSError:
                    if time.monotonic() > deadline or server is not None and server.poll() is not None:
                        raise RuntimeError("server unavailable")
                    time.sleep(0.1)
            chrome_path = next(path for path in CHROME_CANDIDATES if Path(path).is_file())
            chrome = subprocess.Popen([chrome_path, "--headless=new", "--disable-gpu", f"--remote-debugging-port={chrome_port}",
                                       f"--user-data-dir={profile}", "--no-first-run", "--no-default-browser-check", "about:blank"],
                                      stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=flags)
            deadline = time.monotonic() + 25
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
            recorder.call("Emulation.setDeviceMetricsOverride", {"width": 1264, "height": 1000, "deviceScaleFactor": 1, "mobile": False})

            def report_block():
                code = evaluate(recorder, "document.querySelector('[data-testid=stCode]')?.innerText || ''")
                return json.loads(code) if code.strip().startswith("{") else None

            def stage(name, action):
                # The block renders the PREVIOUS run until this action's
                # rerun finishes; poll until the report changes from the
                # pre-action baseline (or the load's first render appears).
                baseline = report_block()
                action()
                deadline = time.monotonic() + 15
                report = None
                while time.monotonic() < deadline:
                    report = report_block()
                    if report is not None and report != baseline:
                        break
                    time.sleep(0.3)
                time.sleep(0.7)
                dom = json.loads(evaluate(recorder, "JSON.stringify({checkbox:document.querySelector('[data-testid=stCheckbox] input')?.checked,chips:[...document.querySelectorAll('[data-testid=stFileChipDeleteBtn]')].map(e=>e.parentElement?.innerText.split('\\n')[0]),toasts:[...document.querySelectorAll('[data-testid=stToast]')].map(e=>e.innerText.split('\\n')[0]),exceptions:[...document.querySelectorAll('[data-testid=stException]')].map(e=>e.innerText)})"))
                metrics = recorder.call("Page.getLayoutMetrics")["result"]["cssContentSize"]
                png = recorder.call("Page.captureScreenshot", {"format": "png", "captureBeyondViewport": True,
                                   "clip": {"x": 0, "y": 0, "width": metrics["width"], "height": metrics["height"], "scale": 1}})["result"]["data"]
                (out / f"{name}.png").write_bytes(base64.b64decode(png))
                capture["stages"].append({"name": name, "report": report, "dom": dom, "screenshot": f"{name}.png"})
                print(name, "->", json.dumps(report, sort_keys=True), "| dom:", json.dumps(dom, ensure_ascii=False)[:110], flush=True)

            def upload():
                document = recorder.call("DOM.getDocument", {"depth": 0})["result"]["root"]
                node = recorder.call("DOM.querySelector", {"nodeId": document["nodeId"], "selector": "[data-testid=stFileUploaderDropzoneInput]"})["result"]["nodeId"]
                if not node:
                    raise RuntimeError("missing actual upload input")
                recorder.call("DOM.setFileInputFiles", {"files": [str((inputs / name).resolve()) for name in sorted(UPLOADS)], "nodeId": node})

            def check():
                expression = "[...document.querySelectorAll('[data-testid=stCheckbox]')].find(e=>e.textContent.includes('Check')).querySelector('label')"
                evaluate(recorder, "(()=>{const e=" + expression + ";if(!e)return false;e.scrollIntoView({block:'center'});return true;})()")
                click(recorder, rect(recorder, expression))

            def pick():
                expression = "[...document.querySelectorAll('[data-testid=stSelectbox]')].find(e=>e.innerText.trim().startsWith('Pick')).querySelector('[role=combobox]')"
                click(recorder, rect(recorder, expression))
                time.sleep(0.3)
                option = "[...document.querySelectorAll('[role=option]')].find(e=>e.textContent.trim()==='b')"
                click(recorder, rect(recorder, option))

            def row():
                grid = "[...document.querySelectorAll('[data-testid=stDataFrame]')][0].querySelector('[data-testid=data-grid-canvas]')"
                evaluate(recorder, "(()=>{const e=" + grid + ";if(!e)return false;e.scrollIntoView({block:'center'});return true;})()")
                bounds = json.loads(evaluate(recorder, "JSON.stringify((()=>{const r=" + grid + ".getBoundingClientRect();return {x:r.x,y:r.y,width:r.width};})())"))
                click(recorder, {"x": bounds["x"] + 17, "y": bounds["y"] + 52})

            def apply():
                button = "[...document.querySelectorAll('button')].find(e=>e.textContent.trim()==='Apply')"
                evaluate(recorder, "(()=>{const e=" + button + ";if(!e)return false;e.scrollIntoView({block:'center'});return true;})()")
                click(recorder, rect(recorder, button))

            stage("load", lambda: recorder.call("Page.navigate", {"url": url}))
            stage("upload-two", upload)
            stage("check", check)
            stage("pick-b", pick)
            stage("select-row-2", row)
            stage("apply", apply)
            for event in recorder.take():
                method = event.get("method")
                params = event.get("params", {})
                if method == "Network.webSocketFrameSent":
                    try:
                        raw = base64.b64decode(params["response"]["payloadData"])
                    except Exception:
                        continue
                    message = BackMsg()
                    if message.ParseFromString(raw) and message.WhichOneof("type"):
                        capture["frames"].append({"direction": "client->server", "bytes": len(raw),
                                                  "base64": base64.b64encode(raw).decode(),
                                                  "message": MessageToDict(message, preserving_proto_field_name=True)})
                elif method == "Network.webSocketFrameReceived":
                    try:
                        raw = base64.b64decode(params["response"]["payloadData"])
                    except Exception:
                        continue
                    message = ForwardMsg()
                    if message.ParseFromString(raw) and message.WhichOneof("type"):
                        capture["frames"].append({"direction": "server->client", "bytes": len(raw),
                                                  "base64": base64.b64encode(raw).decode(),
                                                  "message": MessageToDict(message, preserving_proto_field_name=True)})
                elif method == "Network.requestWillBeSent" and "/_stcore/upload_file/" in params.get("request", {}).get("url", ""):
                    capture["uploads"].append({"method": params["request"]["method"]})
            capture["successful"] = True
    except Exception as error:
        capture["producer_error"] = f"{type(error).__name__}: {error}"
        raise
    finally:
        if recorder is not None:
            try:
                recorder.stop()
            except Exception:
                pass
        if chrome is not None:
            chrome.terminate()
            chrome.wait()
        shutil.rmtree(profile, ignore_errors=True)
        capture["profile_cleaned"] = not profile.exists()
        if server is not None:
            server.terminate()
            server.wait(timeout=10)
            capture["server_stopped"] = True
        (out / "trace.json").write_text(json.dumps(capture, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", help="caller-owned Rust server URL; otherwise start the Python reference")
    parser.add_argument("--out", required=True)
    collect(parser.parse_args())
