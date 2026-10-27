"""Capture one owned Python 1.66.1 component state session; never invent expected values."""

from __future__ import annotations

import argparse
import base64
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import pathlib
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests/reference"))
sys.path.insert(0, str(ROOT / "tests/browser"))

from capture_browser_trace import CDP  # noqa: E402
from componenttrigger_capture import CHROME_CANDIDATES, click, evaluate, http_json, rect, settle  # noqa: E402
from google.protobuf.json_format import MessageToDict  # noqa: E402
from streamlit.proto.BackMsg_pb2 import BackMsg  # noqa: E402
from streamlit.proto.ForwardMsg_pb2 import ForwardMsg  # noqa: E402


class Recorder(CDP):
    def __init__(self, url):
        super().__init__(url, label="python-componentv2-state")
        self.commands = []

    def send(self, method, params=None):
        self.commands.append({"method": method, "params": params or {}, "asynchronous": True})
        return super().send(method, params)

    def call(self, method, params=None, timeout=10.0):
        entry = {"method": method, "params": params or {}, "monotonic": time.monotonic()}
        self.commands.append(entry)
        response = super().call(method, params, timeout)
        entry["response"] = response
        return response


def free_port():
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return listener.getsockname()[1]


def frames(recorder):
    result = []
    for index, event in enumerate(recorder.take()):
        method = event.get("method")
        if method not in ("Network.webSocketFrameSent", "Network.webSocketFrameReceived"):
            continue
        response = event["params"]["response"]
        if response["opcode"] != 2:
            continue
        raw = base64.b64decode(response["payloadData"], validate=True)
        message = BackMsg() if method.endswith("Sent") else ForwardMsg()
        message.ParseFromString(raw)
        result.append({"event_index": index, "direction": "client->server" if method.endswith("Sent") else "server->client",
                       "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest(),
                       "base64": response["payloadData"], "message": MessageToDict(message, preserving_proto_field_name=True)})
    return result


def finished(recorder):
    return sum("script_finished" in frame["message"] for frame in frames(recorder))


def wait_run(recorder, before):
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        if finished(recorder) > before and settle(recorder, quiet=0.8, timeout=10):
            return
        time.sleep(0.1)
    raise RuntimeError("no new completed script run")


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def _cleanup_owned(capture, recorder, chrome, server, profile, out):
    errors = []

    def attempt(step, action):
        try:
            return True, action()
        except Exception as error:
            errors.append({"step": step, "error": f"{type(error).__name__}: {error}"})
            return False, None

    # 1. 分别保留原始记录，单项读取或 stop 失败不阻断其他清理。
    if recorder is not None:
        for field, read in (("events", recorder.take), ("commands", lambda: recorder.commands),
                            ("asynchronous_responses", lambda: recorder._responses)):
            ok, value = attempt("recorder." + field, read)
            if ok:
                capture[field] = value
        attempt("recorder.stop", recorder.stop)

    # 2. 分别回收两个自有进程，等待失败后仍尝试 kill 和再次等待。
    cleanup = {}
    for name, process in (("chrome", chrome), ("server", server)):
        if process is None:
            cleanup[name + "_stopped"] = True
            continue
        ok, status = attempt(name + ".poll", process.poll)
        if not ok or status is None:
            if sys.platform == "win32":
                stopped, _ = attempt(name + ".taskkill", lambda: subprocess.run(
                    ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True,
                    creationflags=subprocess.CREATE_NO_WINDOW))
                if not stopped:
                    attempt(name + ".terminate", process.terminate)
            else:
                attempt(name + ".terminate", process.terminate)
        waited, _ = attempt(name + ".wait", lambda: process.wait(timeout=10))
        if not waited:
            attempt(name + ".kill", process.kill)
            attempt(name + ".wait_after_kill", lambda: process.wait(timeout=10))
        ok, status = attempt(name + ".final_poll", process.poll)
        cleanup[name + "_stopped"] = ok and status is not None
        if ok and status is None:
            errors.append({"step": name + ".final_poll", "error": "owned process is still running"})
    capture["cleanup"] = cleanup

    # 3. profile 清理失败也必须最后尝试写入原始 trace。
    attempt("profile.cleanup", profile.cleanup)
    capture["cleanup_errors"] = errors
    attempt("trace.write", lambda: write_json(out / "trace.json", capture))
    if errors and "producer_error" not in capture:
        raise RuntimeError("owned resource cleanup failed: " + json.dumps(errors))


def collect(out):
    if importlib.metadata.version("streamlit") != "1.66.1":
        raise RuntimeError("Run with target/pyref-venv/Scripts/python.exe (Streamlit 1.66.1)")
    out.mkdir(parents=True, exist_ok=False)
    server_port, chrome_port = free_port(), free_port()
    url = f"http://127.0.0.1:{server_port}"
    app = ROOT / "tests/reference/componentv2_state_app.py"
    server_command = [sys.executable, "-B", "-m", "streamlit", "run", str(app),
                      "--server.address=127.0.0.1", f"--server.port={server_port}",
                      "--server.headless=true", "--server.fileWatcherType=none", "--browser.gatherUsageStats=false"]
    capture = {"schema_version": 1, "runtime": "python", "reference_version": "1.66.1",
               "captured_at_utc": datetime.now(timezone.utc).isoformat(), "app": app.relative_to(ROOT).as_posix(),
               "git_revision": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
               "server_command": server_command, "url": url, "chrome_port": chrome_port,
               "configuration": {"server.address": "127.0.0.1", "server.port": server_port, "server.headless": True,
                                 "server.fileWatcherType": "none", "browser.gatherUsageStats": False}, "stages": []}
    server = chrome = recorder = None
    profile = tempfile.TemporaryDirectory(prefix="componentv2-state-", dir=ROOT / "target")
    try:
        if not pathlib.Path(profile.name).resolve().is_relative_to((ROOT / "target").resolve()):
            raise RuntimeError("owned browser profile is outside target")
        with (out / "server.log").open("w", encoding="utf-8") as server_log, (out / "chrome.log").open("w", encoding="utf-8") as chrome_log:
            flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            server = subprocess.Popen(server_command, cwd=ROOT, stdout=server_log, stderr=subprocess.STDOUT, creationflags=flags)
            capture["server_pid"] = server.pid
            deadline = time.monotonic() + 30
            while True:
                try:
                    with urllib.request.urlopen(url + "/_stcore/health", timeout=1) as response:
                        capture["health"] = {"status": response.status, "body": response.read().decode()}
                    break
                except OSError:
                    if time.monotonic() > deadline or server.poll() is not None:
                        raise RuntimeError("owned reference server did not start")
                    time.sleep(0.1)
            chrome_path = next(path for path in CHROME_CANDIDATES if pathlib.Path(path).is_file())
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
                        raise RuntimeError("owned Chrome did not start")
                    time.sleep(0.1)
            target = http_json(f"http://127.0.0.1:{chrome_port}/json/new?about:blank", method="PUT")
            recorder = Recorder(target["webSocketDebuggerUrl"])
            recorder.start()
            recorder.call("Emulation.setDeviceMetricsOverride", {"width": 1000, "height": 700, "deviceScaleFactor": 1, "mobile": False})
            before, seen = 0, 0
            actions = [("load", None), ("set-bye", "#bye"), ("ordinary-rerun", "ordinary"), ("set-null", "#null")]
            for name, selector in actions:
                operation = {"action": name, "command_start": len(recorder.commands)}
                if selector is None:
                    recorder.call("Page.navigate", {"url": url})
                else:
                    element = ("[...document.querySelectorAll('button')].find(b=>b.textContent.trim()==='Ordinary rerun')"
                               if selector == "ordinary" else
                               "[...document.querySelectorAll('[data-testid=stBidiComponentIsolated]')].map(h=>h.shadowRoot?.querySelector(" + json.dumps(selector) + ")).find(Boolean)")
                    point = rect(recorder, element)
                    if point is None:
                        raise RuntimeError("missing actual button: " + name)
                    click(recorder, point)
                wait_run(recorder, before)
                before = finished(recorder)
                all_frames = frames(recorder)
                dom = json.loads(evaluate(recorder, "JSON.stringify({code:document.querySelector('pre code')?.textContent,exceptions:[...document.querySelectorAll('[data-testid=stException]')].map(e=>e.innerText)})"))
                if dom["exceptions"]:
                    raise RuntimeError("reference raised: " + str(dom["exceptions"]))
                observed = json.loads(dom["code"])
                png = base64.b64decode(recorder.call("Page.captureScreenshot", {"format": "png"})["result"]["data"])
                (out / (name + ".png")).write_bytes(png)
                operation["command_end"] = len(recorder.commands)
                capture["stages"].append({"name": name, "operation": operation, "frame_start": seen, "frame_end": len(all_frames),
                                          "observed": observed, "dom": dom, "screenshot": {"file": name + ".png", "sha256": hashlib.sha256(png).hexdigest()}})
                seen = len(all_frames)
                print(name, json.dumps(observed), flush=True)
            capture["frames"] = frames(recorder)
            versions = {frame["message"]["new_session"]["initialize"]["environment_info"]["streamlit_version"]
                        for frame in capture["frames"] if "new_session" in frame["message"]}
            if versions != {"1.66.1"}:
                raise RuntimeError("actual wire runtime version differs: " + str(versions))
            compact = {"schema_version": 1, "reference_version": "1.66.1", "default_state": {"value": "hi", "untouched": 7}, "stages": []}
            for stage in capture["stages"]:
                states = [widget for frame in capture["frames"][stage["frame_start"]:stage["frame_end"]]
                          for widget in frame["message"].get("rerun_script", {}).get("widget_states", {}).get("widgets", [])
                          if widget.get("id", "").endswith("-greeter")]
                compact["stages"].append({"name": stage["name"], "browser_widget_states": states,
                                          "expected_result": stage["observed"]["result"], "expected_keyed_state": stage["observed"]["session_state"]})
            write_json(out / "state-cases.json", compact)
    except Exception as error:
        capture["producer_error"] = f"{type(error).__name__}: {error}"
        raise
    finally:
        _cleanup_owned(capture, recorder, chrome, server, profile, out)
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True)
    raise SystemExit(collect(pathlib.Path(parser.parse_args().out)))
