"""One owned capture of the multiple-file uploader flow (python or rust).

Stages over a real Chrome: load, upload two files at once via CDP
setFileInputFiles, remove one file chip, remove the other. Records every
WebSocket frame (CDP network events, decoded), every upload HTTP request,
the rendered report, chip DOM, and screenshots.
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

UPLOADS = {
    "alpha.txt": b"alpha-payload-01\n",
    "beta.csv": b"key,value\na,1\nb,2\n",
}


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
        url = args.url
    else:
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            port = listener.getsockname()[1]
        url = f"http://127.0.0.1:{port}/"
        command = [sys.executable, "-B", "-m", "streamlit", "run", str(ROOT / "tests/reference/uploads_multi_app.py"),
                   "--server.address=127.0.0.1", f"--server.port={port}", "--server.headless=true",
                   "--server.fileWatcherType=none", "--browser.gatherUsageStats=false"]
    capture = {"runtime": "rust" if args.url else "python", "reference_version": "1.66.1", "reference_decoder": "1.66.1", "url": url,
               "captured_at_utc": datetime.now(timezone.utc).isoformat(),
               "server_command": None if args.url else command,
               "server_cleanup": "caller-owned" if args.url else "collector-owned",
               "inputs": {name: len(data) for name, data in UPLOADS.items()},
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
            recorder.call("Emulation.setDeviceMetricsOverride", {"width": 1264, "height": 900, "deviceScaleFactor": 1, "mobile": False})

            def wait_report_settled():
                deadline = time.monotonic() + 15
                while True:
                    code = evaluate(recorder, "document.querySelector('[data-testid=stCode]')?.innerText || ''")
                    if code.strip().startswith("{") and time.monotonic() > deadline - 13:
                        return code
                    if time.monotonic() > deadline:
                        raise RuntimeError("report never rendered")
                    time.sleep(0.3)

            def upload(files):
                document = recorder.call("DOM.getDocument", {"depth": 0})["result"]["root"]
                nodes = recorder.call("DOM.querySelectorAll", {"nodeId": document["nodeId"], "selector": "[data-testid=stFileUploaderDropzoneInput]"})["result"]["nodeIds"]
                # The multiple-mode uploader is the page's last dropzone (the
                # Python reference app has exactly one; the Rust example adds
                # a single-file uploader before it).
                node = nodes[-1] if nodes else 0
                if not node:
                    raise RuntimeError("missing actual upload input")
                recorder.call("DOM.setFileInputFiles", {"files": [str((inputs / name).resolve()) for name in files], "nodeId": node})

            def remove_chip(name):
                expression = f"[...document.querySelectorAll('button')].find(e=>(e.getAttribute('aria-label')||'')==={json.dumps('Remove ' + name)})"
                evaluate(recorder, "(()=>{const e=" + expression + ";if(!e)return false;e.scrollIntoView({block:'center'});return true;})()")
                point = rect(recorder, expression)
                if point is None:
                    raise RuntimeError("missing remove control: " + name)
                click(recorder, point)

            def stage(name, action):
                before = len(capture["frames"])
                action()
                code = wait_report_settled()
                time.sleep(1.0)
                dom = json.loads(evaluate(recorder, "JSON.stringify({chips:[...document.querySelectorAll('[data-testid=stFileChipDeleteBtn]')].map(e=>e.parentElement?.innerText || ''),exceptions:[...document.querySelectorAll('[data-testid=stException]')].map(e=>e.innerText)})"))
                metrics = recorder.call("Page.getLayoutMetrics")["result"]["cssContentSize"]
                png = recorder.call("Page.captureScreenshot", {"format": "png", "captureBeyondViewport": True,
                                   "clip": {"x": 0, "y": 0, "width": metrics["width"], "height": metrics["height"], "scale": 1}})["result"]["data"]
                (out / f"{name}.png").write_bytes(base64.b64decode(png))
                capture["stages"].append({"name": name, "code_text": code, "dom": dom, "screenshot": f"{name}.png"})
                print(name, "report:", code.replace("\n", " ")[:150], "| chips:", len(dom["chips"]), flush=True)

            stage("load", lambda: recorder.call("Page.navigate", {"url": url}))
            stage("upload-two", lambda: upload(["alpha.txt", "beta.csv"]))
            stage("remove-alpha", lambda: remove_chip("alpha.txt"))
            stage("remove-beta", lambda: remove_chip("beta.csv"))
            capture["frames"] = []
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
                    capture["uploads"].append({"url": params["request"]["url"], "method": params["request"]["method"]})
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
