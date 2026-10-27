"""Explicit native-WS protocol probe, not evidence of browser-reachable clearing."""

from __future__ import annotations

import argparse
import base64
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import pathlib
import subprocess
import sys
import time
import urllib.request

import pyarrow as pa
from google.protobuf.json_format import MessageToDict
from streamlit.proto.BackMsg_pb2 import BackMsg
from streamlit.proto.ForwardMsg_pb2 import ForwardMsg
from websockets.sync.client import connect

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests/browser"))

from componentv2_state_capture import free_port, write_json  # noqa: E402

EMPTY_SELECTION = '{"selection":{"rows":[],"columns":[],"cells":[]}}'


def collect(out):
    version = importlib.metadata.version("streamlit")
    if version != "1.66.1":
        raise RuntimeError("requires pinned Python Streamlit 1.66.1")
    out.mkdir(parents=True, exist_ok=False)
    port = free_port()
    url = f"http://127.0.0.1:{port}/"
    command = [sys.executable, "-B", "-m", "streamlit", "run", str(ROOT / "tests/reference/dataframe_selection_app.py"),
               "--server.address=127.0.0.1", f"--server.port={port}", "--server.headless=true",
               "--server.fileWatcherType=none", "--browser.gatherUsageStats=false"]
    capture = {"schema_version": 1, "runtime": "python", "reference_version": version,
               "captured_at_utc": datetime.now(timezone.utc).isoformat(), "transport": "native-websocket-protocol-probe",
               "scope": "Explicit StringValue and button-trigger protocol inputs; no browser, UI clear, CDP, DOM, or screenshot claim.",
               "git_revision": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
               "configuration": {"server.address": "127.0.0.1", "server.port": port, "server.headless": True,
                                 "server.fileWatcherType": "none", "browser.gatherUsageStats": False,
                                 "security_cli_overrides": [], "browser": None, "profile": None},
               "server_command": command, "url": url, "commands": [], "frames": [], "stages": []}
    server = websocket = None
    selection_id = script_hash = ""
    button_ids = {}
    last_selection_state = None
    try:
        # 1. 仅启动自有本机 Python server，保留默认安全配置和真实 HTTP/WS 握手。
        with (out / "server.log").open("w", encoding="utf-8") as server_log:
            server = subprocess.Popen(command, cwd=ROOT, stdout=server_log, stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW)
            capture["server_pid"] = server.pid
            deadline = time.monotonic() + 25
            while True:
                try:
                    with urllib.request.urlopen(url + "_stcore/health", timeout=1) as response:
                        capture["health"] = {"status": response.status, "body": response.read().decode()}
                    break
                except OSError:
                    if time.monotonic() > deadline or server.poll() is not None:
                        raise RuntimeError("owned Python reference server did not start")
                    time.sleep(0.1)
            websocket = connect(f"ws://127.0.0.1:{port}/_stcore/stream", origin=url.rstrip("/"), subprotocols=["streamlit"], proxy=None,
                                open_timeout=10, close_timeout=5, max_size=None, legacy=True)
            capture["handshake"] = {"status": websocket.response.status_code, "origin": url.rstrip("/"), "subprotocol": websocket.subprotocol,
                                    "headers": {key: websocket.response.headers.get(key) for key in ("Upgrade", "Connection", "Sec-WebSocket-Protocol")}}

            def record(direction, raw, message):
                item = {"direction": direction, "monotonic": time.monotonic(), "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest(),
                        "base64": base64.b64encode(raw).decode(), "message_oneof": message.WhichOneof("type"),
                        "message": MessageToDict(message, preserving_proto_field_name=True)}
                capture["frames"].append(item)
                return item

            # 2. 一次新会话只探测缺失边界；输入来源和原字符串明确记录。
            plan = [("01-load", None, None), ("02-empty-nonempty", None, "manual-empty"),
                    ("03-probe-nonempty", "Probe", "manual-empty"), ("04-switch-empty", "Empty table", "manual-empty"),
                    ("05-empty-empty", None, "manual-empty"), ("06-restore", "Restore table", "manual-empty"),
                    ("07-program-partial-empty", "Program empty rows", "manual-empty"), ("08-probe-server-echo", "Probe", "server-echo")]
            for name, button, source in plan:
                start = len(capture["frames"])
                request = BackMsg()
                request.rerun_script.query_string = "case=required-protocol"
                request.rerun_script.page_script_hash = script_hash
                payload = EMPTY_SELECTION if source == "manual-empty" else last_selection_state if source == "server-echo" else None
                if payload is not None:
                    if not selection_id:
                        raise RuntimeError("selection widget id must come from a prior real server output")
                    widget = request.rerun_script.widget_states.widgets.add()
                    widget.id = selection_id
                    widget.string_value = payload
                if button is not None:
                    widget = request.rerun_script.widget_states.widgets.add()
                    widget.id = button_ids[button]
                    widget.trigger_value = True
                raw = request.SerializeToString()
                operation = {"name": name, "kind": "explicit-protocol-injection" if source else "initial-protocol-load",
                             "selection_input_source": source, "selection_input": payload, "button_trigger_label": button,
                             "frame_start": start, "command_index": len(capture["commands"])}
                capture["commands"].append({"method": "websocket.send", "stage": name, "frame_index": start, "monotonic": time.monotonic()})
                record("client->server", raw, request)
                websocket.send(raw)
                finished = False
                observed = None
                dataframes = []
                runs = []
                while True:
                    raw = websocket.recv(timeout=20)
                    if not isinstance(raw, bytes):
                        raise RuntimeError("Python server sent a non-binary protocol message")
                    message = ForwardMsg()
                    message.ParseFromString(raw)
                    item = record("server->client", raw, message)
                    kind = message.WhichOneof("type")
                    if kind == "new_session":
                        script_hash = message.new_session.page_script_hash
                        runs.append(item["message"]["new_session"])
                    if kind == "delta" and message.delta.WhichOneof("type") == "new_element":
                        element = message.delta.new_element
                        element_kind = element.WhichOneof("type")
                        if element_kind == "button":
                            button_ids[element.button.label] = element.button.id
                        elif element_kind == "dataframe":
                            frame = element.dataframe
                            if frame.id.endswith("-selection-required-protocol"):
                                selection_id = frame.id
                                last_selection_state = frame.selection_state if frame.HasField("selection_state") else None
                            table = pa.ipc.open_stream(frame.arrow_data.data).read_all()
                            fields = MessageToDict(frame, preserving_proto_field_name=True)
                            fields.pop("arrow_data", None)
                            dataframes.append({"frame_index": len(capture["frames"]) - 1, "delta_path": list(message.metadata.delta_path), "fields": fields,
                                               "schema": [{"name": field.name, "type": str(field.type), "nullable": field.nullable} for field in table.schema], "rows": table.to_pylist()})
                        elif element_kind == "code":
                            observed = json.loads(element.code.code_text)
                    if kind == "script_finished":
                        finished = True
                    if kind == "session_status_changed" and finished and not message.session_status_changed.script_is_running:
                        break
                operation.update(frame_end=len(capture["frames"]), observed=observed, dataframes=dataframes, runs=runs,
                                 server_selection_state=last_selection_state)
                capture["stages"].append(operation)
                write_json(out / "progress.json", capture)
                print(name, json.dumps(observed), flush=True)
                if observed is None:
                    raise RuntimeError("probe run did not emit its actual application JSON")
            capture["successful"] = True
    except Exception as error:
        capture["producer_error"] = f"{type(error).__name__}: {error}"
        raise
    finally:
        # 3. 没有 browser/profile；关闭 WS 失败也继续回收唯一自有进程并落 raw。
        errors = []

        def attempt(step, action):
            try:
                return True, action()
            except Exception as error:
                errors.append({"step": step, "error": f"{type(error).__name__}: {error}"})
                return False, None

        if websocket is not None:
            attempt("websocket.close", websocket.close)
        server_stopped = server is None
        if server is not None:
            polled, status = attempt("server.poll", server.poll)
            if not polled or status is None:
                attempt("server.taskkill", lambda: subprocess.run(["taskkill", "/PID", str(server.pid), "/T", "/F"], stdout=subprocess.DEVNULL,
                                                                  stderr=subprocess.DEVNULL, check=True, creationflags=subprocess.CREATE_NO_WINDOW))
            waited, _ = attempt("server.wait", lambda: server.wait(timeout=10))
            if not waited:
                attempt("server.kill", server.kill)
                attempt("server.wait_after_kill", lambda: server.wait(timeout=10))
            polled, status = attempt("server.final_poll", server.poll)
            server_stopped = polled and status is not None
        closed, status = attempt("websocket.state", lambda: "CLOSED" if websocket is None else websocket.state.name)
        capture["cleanup"] = {"server_stopped": server_stopped, "websocket_closed": closed and status == "CLOSED"}
        if not all(capture["cleanup"].values()):
            errors.append({"step": "cleanup.final_state", "error": "owned server or websocket did not close"})
        capture["cleanup_errors"] = errors
        attempt("trace.write", lambda: write_json(out / "trace.json", capture))
        if errors and "producer_error" not in capture:
            raise RuntimeError("owned protocol probe cleanup failed: " + json.dumps(errors))
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    raise SystemExit(collect(pathlib.Path(parser.parse_args().out)))
