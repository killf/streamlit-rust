"""One owned capture of the size-limited uploader flow (python or rust).

Stages over a real Chrome: load, select an oversized file (2 MiB against a
1 MiB widget limit — the official frontend must block it before any upload),
then select a small file which uploads normally. Records WebSocket frames,
upload HTTP requests, the rendered report, alert/toast DOM, and screenshots.
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
from componenttrigger_capture import CHROME_CANDIDATES, evaluate, http_json

INPUTS = {"oversize-2m.bin": b"x" * (2 * 1024 * 1024), "small.txt": b"small payload\n"}


def collect(args):
    if importlib.metadata.version("streamlit") != "1.66.1":
        raise RuntimeError("requires the pinned Streamlit 1.66.1 decoder environment")
    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=False)
    inputs = out / "inputs"
    inputs.mkdir()
    for name, data in INPUTS.items():
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
        command = [sys.executable, "-B", "-m", "streamlit", "run", str(ROOT / "tests/reference/uploads_limit_app.py"),
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
            recorder.call("Emulation.setDeviceMetricsOverride", {"width": 1264, "height": 900, "deviceScaleFactor": 1, "mobile": False})

            def upload(files, last=True):
                document = recorder.call("DOM.getDocument", {"depth": 0})["result"]["root"]
                nodes = recorder.call("DOM.querySelectorAll", {"nodeId": document["nodeId"], "selector": "[data-testid=stFileUploaderDropzoneInput]"})["result"]["nodeIds"]
                # The size-limited uploader is the page's last dropzone on both
                # runtimes (the Rust example adds other uploaders before it).
                node = (nodes[-1] if last else nodes[0]) if nodes else 0
                if not node:
                    raise RuntimeError("missing actual upload input")
                recorder.call("DOM.setFileInputFiles", {"files": [str((inputs / name).resolve()) for name in files], "nodeId": node})

            def stage(name, action, settle=2.5):
                action()
                time.sleep(settle)
                # All rendered JSON code blocks in order; the offline test picks
                # the limit section's report (the last one on both runtimes).
                code = evaluate(recorder, "JSON.stringify([...document.querySelectorAll('[data-testid=stCode]')].map(e=>e.innerText))")
                dom = json.loads(evaluate(recorder, "JSON.stringify({alerts:[...document.querySelectorAll('[data-testid=stAlert], [data-testid=stNotification]')].map(e=>e.innerText),exceptions:[...document.querySelectorAll('[data-testid=stException]')].map(e=>e.innerText)})"))
                metrics = recorder.call("Page.getLayoutMetrics")["result"]["cssContentSize"]
                png = recorder.call("Page.captureScreenshot", {"format": "png", "captureBeyondViewport": True,
                                   "clip": {"x": 0, "y": 0, "width": metrics["width"], "height": metrics["height"], "scale": 1}})["result"]["data"]
                (out / f"{name}.png").write_bytes(base64.b64decode(png))
                capture["stages"].append({"name": name, "code_texts": json.loads(code), "dom": dom, "screenshot": f"{name}.png"})
                print(name, "reports:", [text.replace("\n", " ")[:60] for text in json.loads(code)], "| alerts:", dom["alerts"][:2], flush=True)

            stage("load", lambda: recorder.call("Page.navigate", {"url": url}))
            stage("select-oversize", lambda: upload(["oversize-2m.bin"]))
            stage("select-small", lambda: upload(["small.txt"]))
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
