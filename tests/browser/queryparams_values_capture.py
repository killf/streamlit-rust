"""Capture query parameter values/mutations once over a real native WS.

Uses only synthetic URL values. Retains raw protobuf and never overwrites an
existing capture; no DOM or browser-interaction claim.
"""
import argparse
import base64
from contextlib import ExitStack
from datetime import datetime, timezone
import importlib.metadata
import json
from pathlib import Path
import socket
import subprocess
import sys
import time
import urllib.request

from google.protobuf.json_format import MessageToDict
from streamlit.proto.BackMsg_pb2 import BackMsg
from streamlit.proto.ForwardMsg_pb2 import ForwardMsg
from websockets.sync.client import connect

ROOT = Path(__file__).resolve().parents[2]
QUERY = "z=last&tag=first&tag=second&a=first&blank=&encoded=%E4%B8%AD%E6%96%87+text"
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--out", type=Path, required=True)
parser.add_argument("--scenario", choices=("values", "encoding", "text-length", "text-reset", "reserved", "binding", "seed", "seed-code", "disabled", "disabled-valid", "disabled-types", "disabled-json", "rerun", "navigation-rerun", "rerun-messages", "rerun-queue"), default="values")
args = parser.parse_args()
if args.scenario == "reserved":
    QUERY = "case=reserved&embed=true&EMBED_OPTIONS=light_theme&st_embed=ordinary&=empty-key-value"
elif args.scenario == "binding":
    QUERY = "case=binding&phase=load"
elif args.scenario == "seed":
    QUERY = "case=seed&phase=initial&bound=y&text=hello&optional=y&creation=new"
elif args.scenario == "seed-code":
    QUERY = "case=seed&phase=bad-initial&bound=y&text=hello&optional=y&creation=new"
if args.scenario in ("disabled", "disabled-valid", "disabled-types", "disabled-json"):
    QUERY = "case=disabled&phase=load&bound=y&text=url"
if args.scenario == "rerun":
    QUERY = "case=rerun&phase=load&bound=y&text=url"
if args.scenario == "rerun-queue":
    QUERY = "case=queue&phase=warm"
if args.scenario == "rerun-messages":
    QUERY = "case=rerun&phase=messages&bound=y&text=url"
if args.scenario == "navigation-rerun":
    QUERY = "probe=load"
assert importlib.metadata.version("streamlit") == "1.66.1"
args.out.mkdir(parents=True, exist_ok=True)
trace_path = args.out / "trace.json"
assert not trace_path.exists(), "retain the original capture"
with socket.socket() as listener:
    listener.bind(("127.0.0.1", 0))
    port = listener.getsockname()[1]
url = f"http://127.0.0.1:{port}"
fixture = "navigation_app.py" if args.scenario == "navigation-rerun" else "queryparams_values_app.py"
if args.scenario in ("text-length", "text-reset"):
    fixture = "forms_app.py"
command = [sys.executable, "-B", "-m", "streamlit", "run", str(ROOT / "tests/reference" / fixture),
           "--server.address=127.0.0.1", f"--server.port={port}", "--server.headless=true",
           "--server.fileWatcherType=none", "--browser.gatherUsageStats=false"]
trace = {"schema_version": 1, "runtime": "python", "reference_version": "1.66.1",
         "captured_at_utc": datetime.now(timezone.utc).isoformat(), "query_string": QUERY,
         "scenario": args.scenario,
         "server_command": command, "scope": "Native WS query multimap and mutation behavior; no browser claim.",
         "frames": [], "cleanup": {}}
server = None


def record(direction, raw, message):
    trace["frames"].append({"direction": direction, "bytes": len(raw),
                            "base64": base64.b64encode(raw).decode(),
                            "message": MessageToDict(message, preserving_proto_field_name=True)})


try:
    with (args.out / "server.log").open("w", encoding="utf-8") as log:
        server = subprocess.Popen(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT,
                                  creationflags=subprocess.CREATE_NO_WINDOW)
    deadline = time.monotonic() + 25
    while True:
        try:
            with urllib.request.urlopen(url + "/_stcore/health", timeout=1) as response:
                assert response.status == 200
            break
        except OSError:
            if time.monotonic() >= deadline or server.poll() is not None:
                raise RuntimeError("reference server unavailable")
            time.sleep(0.1)
    with ExitStack() as sockets, connect(url.replace("http", "ws") + "/_stcore/stream", origin=url, subprotocols=["streamlit"],
                 proxy=None, open_timeout=10, close_timeout=5, max_size=None, legacy=True) as ws:
        queries = [QUERY]
        if args.scenario == "text-length":
            trace["connection_policy"] = "Fresh WS per widget kind/limit/default; nine requests share each WS."
            phases = ("load", "ascii", "unicode", "same-prefix", "joiner", "empty", "assign", "retain", "recover")
            text_inputs = {"ascii": "abcdef🧊", "unicode": "中文🧊e\u0301TAIL", "same-prefix": "中文🧊e\u0301OTHER",
                           "joiner": "👨\u200d👩\u200d👧\u200d👦!", "empty": "", "recover": "line1\nline2🧊"}
            queries = [f"case=form-max-chars-cjk&probe=length&kind={kind}&limit={limit}&default={default}&phase={phase}"
                       for kind in ("input", "area") for limit, default in (("5", "long"), ("0", "long"), ("none", "long"), ("5", "none")) for phase in phases]
            trace["query_string"] = queries[0]
        if args.scenario == "text-reset":
            trace["connection_policy"] = "Fresh WS per widget kind; twelve limit/default transitions share each WS."
            steps = (("5", "long", "load"), ("5", "long", "edit"), ("3", "long", "shrink"), ("3", "long", "edit-short"),
                     ("5", "long", "grow"), ("0", "long", "zero"), ("none", "long", "unlimited"), ("none", "long", "same-none"),
                     ("none", "long", "retain"), ("none", "none", "same-default"), ("5", "long", "return-five"), ("5", "long", "edit-five"))
            text_inputs = {"edit": "é🧊zUPPER", "edit-short": "XYZtail", "same-none": "retained🧊text", "edit-five": "END🧊ok"}
            queries = [f"case=form-max-chars-cjk&probe=length&kind={kind}&limit={limit}&default={default}&phase={phase}"
                       for kind in ("input", "area") for limit, default, phase in steps]
            trace["query_string"] = queries[0]
        if args.scenario == "encoding":
            queries = [
                "tag=%+1&%+f=key&keep=ok",
                "tag=%+0&tag=%+9&tag=%+A&tag=%+F&tag=%+a&tag=%+f",
                "tag=%1&tag=%&tag=%%&tag=%GG&tag=%1G&tag=%G1&tag=%-1&tag=%+G",
                "tag=%20&tag=+&tag=%2B&tag=%2520&tag=a%26b%3Dc",
                "tag=%00&tag=%0A&tag=%0D&tag=%09&tag=%7F",
                "tag=%E4%B8%AD%E6%96%87&tag=%e4%b8%ad&tag=%F0%9F%A7%8A",
                "tag=%FF&tag=%C0%AF&tag=%ED%A0%80&tag=%F4%90%80%80",
                "tag=%E2%82&tag=%E2%28%A1&tag=%F0%9F%28%8A&tag=%C3%A9%FF",
                "=empty&bare&blank=&tag=first&tag=last&&",
                "tag=a;b&tag=a=b&tag=%23part&tag=%3Fquestion&tag=%2Fpath",
                "tag=literal中文+🧊&tag=literal%中文",
                "tag=%2b&tag=%2B&tag=%2f&tag=%2F&tag=%7e&tag=~",
                "tag=%+1&tag=%2B1&%+1=invalid-key&%2B1=valid-key",
                "%E4%B8%AD=x&中=y&tag=a&%74ag=b&tag=c",
                "tag=&tag&=one&=two",
                "tag=%+A%+f%2B+%25",
            ]
            trace["query_string"] = queries[0]
        if args.scenario == "binding":
            queries = ["case=binding&phase=load", "case=binding&phase=active&bound=y&text=hello",
                       "case=binding&phase=hidden&bound=y&text=hello&BOUND=case-sensitive",
                       "case=binding&phase=released&BOUND=case-sensitive"]
        if args.scenario == "seed":
            queries = [QUERY,
                       "case=seed&phase=frontend&bound=y&text=ignored&optional=y&creation=url",
                       "case=seed&phase=again&bound=y&text=fresh&optional=y&creation=another",
                       "case=seed&phase=invalid&bound=unknown&text=base&optional=unknown&creation=x",
                       "case=seed&phase=empty&bound=&text=&optional=&creation=",
                       "case=seed&phase=assign&bound=y&text=url&optional=y&creation=url",
                       "case=seed&phase=history&bound=y&text=url-history&optional=y&creation=history",
                       "case=seed&phase=history-missing"]
        if args.scenario == "seed-code":
            queries = [QUERY, "case=seed&phase=bad-history&bound=y&text=code-history&optional=y&creation=new-history"]
        if args.scenario in ("disabled", "disabled-valid"):
            queries = [f"case=disabled&phase={phase}" + suffix for phase, suffix in [
                ("load", "&bound=y&text=url"), ("forge", "&bound=y&text=url"),
                ("invalid-url" if args.scenario == "disabled-valid" else "malformed", "&bound=unknown&text=base"), ("code", ""),
                ("hidden", "&bound=y&text=url"), ("remount", "&bound=y&text=url"),
                ("enabled", "&bound=y&text=url"), ("interactive", "&bound=y&text=url"),
                ("redisable", "&bound=unknown&text=base")]]
        if args.scenario == "disabled-types":
            malformed = [
                ("bound", "bool_value", True), ("bound", "int_value", 1),
                ("bound", "double_value", 1.5), ("bound", "string_array_value", ["x"]),
                ("bound", "json_value", "true"), ("plain", "bool_value", True),
                ("text", "bool_value", True), ("check", "string_value", "invalid"),
                ("bound", "json_value", '["x"]'), ("bound", "json_value", '{"x": 1}'),
                ("bound", "json_value", 'null'), ("bound", "json_value", '"x"'),
                ("bound", "int_array_value", [1]), ("bound", "double_array_value", [1.5]),
                ("bound", "bytes_value", b""), ("bound", "trigger_value", True),
                ("bound", "bytes_value", b"x"), ("bound", "bytes_value", b"'\0\\\r\n"),
                ("bound", "bytes_value", bytes(range(256))),
            ]
        elif args.scenario == "disabled-json":
            malformed = [("bound", "json_value", value) for value in (
                "", "{", "[", '{"x":}', '{"x":1,}', "[1,]", '{"x" 1}',
                r'["\q"]', '"a\nb"', '{"x":1} tail', "中文", '{"🧊":\n }',
                r'["\uZZZZ"]', "true false", "01", "-", "1.",
                "NaN", "Infinity", "-Infinity", r'"\ud800"', "1e9999",
                "[NaN]", '{"x":Infinity}',
            )]
        if args.scenario in ("disabled-types", "disabled-json"):
            trace["connection_policy"] = "Fresh WS per malformed input; recovery uses the same WS."
            queries = []
            for number in range(len(malformed)):
                queries.extend((QUERY, f"case=disabled&phase=malformed-{number}&bound=unknown&text=base",
                                f"case=disabled&phase=recovery-{number}&bound=y&text=url"))
        if args.scenario == "rerun":
            queries = [QUERY, "case=rerun&phase=frontend&bound=y&text=ignored",
                       "case=rerun&phase=early&bound=y&text=fresh",
                       "case=rerun&phase=assign&bound=y&text=url", "case=rerun&phase=history"]
        if args.scenario == "navigation-rerun":
            queries = [QUERY, "probe=switch"]
        if args.scenario == "rerun-queue":
            queries = [QUERY, "case=queue&phase=queue"]
        widget_ids = {}
        main_page_hash = None
        for index, query in enumerate(queries):
            if index > 0 and ((args.scenario in ("disabled-types", "disabled-json") and index % 3 == 0) or (args.scenario == "text-length" and index % 9 == 0)
                              or (args.scenario == "text-reset" and index % 12 == 0)):
                ws.close()
                ws = sockets.enter_context(connect(url.replace("http", "ws") + "/_stcore/stream", origin=url, subprotocols=["streamlit"],
                                                   proxy=None, open_timeout=10, close_timeout=5, max_size=None, legacy=True))
                widget_ids.clear()
            request = BackMsg()
            request.rerun_script.query_string = query
            phase = query.rsplit("phase=", 1)[-1]
            if args.scenario in ("text-length", "text-reset") and phase in text_inputs:
                widget = request.rerun_script.widget_states.widgets.add()
                widget.id = widget_ids["cjk_note"]
                widget.string_value = text_inputs[phase]
            if args.scenario == "binding" and index == 1:
                for key, value in (("bound", "y"), ("text", "hello")):
                    widget = request.rerun_script.widget_states.widgets.add()
                    widget.id = widget_ids[key]
                    widget.string_value = value
            if args.scenario == "seed":
                request.rerun_script.is_history_navigation = index >= 6
                if index in (1, 6):
                    for key, value in (("bound", "x"), ("text", "edited"), ("optional", "x"), ("creation", "typed")):
                        widget = request.rerun_script.widget_states.widgets.add()
                        widget.id = widget_ids[key]
                        widget.string_value = value
            if args.scenario == "seed-code":
                request.rerun_script.is_history_navigation = index == 1
            if args.scenario in ("disabled", "disabled-valid") and index > 0:
                phase = query.split("phase=")[1].split("&")[0]
                updates = {"plain": "forged", "bound": "x", "text": "forged", "check": True, "live": ["ready", "one", "two", "three", "four", "five", "six", "seven", "eight"][index]}
                if phase == "malformed":
                    updates.update(plain=True, bound=True, text=True, check="invalid")
                if phase in ("hidden", "remount"):
                    updates = {"plain": "forged-remount", "live": updates["live"]}
                if phase in ("enabled", "interactive"):
                    updates.update(plain="edited" if index == 6 else "edited2", bound="x" if index == 6 else "y", text="edited" if index == 6 else "edited2", check=index == 7)
                if phase in ("code", "redisable"):
                    updates["check"] = False
                for key, value in updates.items():
                    widget = request.rerun_script.widget_states.widgets.add()
                    widget.id = widget_ids[key]
                    if isinstance(value, bool):
                        widget.bool_value = value
                    else:
                        widget.string_value = value
            if args.scenario in ("disabled-types", "disabled-json") and index % 3:
                if index % 3 == 1:
                    key, field, value = malformed[index // 3]
                    widget = request.rerun_script.widget_states.widgets.add()
                    widget.id = widget_ids[key]
                    if field.endswith("_array_value"):
                        getattr(widget, field).data.extend(value)
                    else:
                        setattr(widget, field, value)
                live = request.rerun_script.widget_states.widgets.add()
                live.id = widget_ids["live"]
                live.string_value = f"step-{index}"
            if args.scenario == "rerun":
                request.rerun_script.is_history_navigation = index == 4
                if index == 1:
                    for key, value in (("bound", "x"), ("text", "edited")):
                        widget = request.rerun_script.widget_states.widgets.add()
                        widget.id = widget_ids[key]
                        widget.string_value = value
            if args.scenario == "navigation-rerun" and index == 1:
                assert main_page_hash
                request.rerun_script.page_script_hash = main_page_hash
                widget = request.rerun_script.widget_states.widgets.add()
                widget.id = widget_ids["None"]
                widget.trigger_value = True
            raw = request.SerializeToString()
            record("client->server", raw, request)
            ws.send(raw)
            while True:
                raw = ws.recv(timeout=20)
                message = ForwardMsg()
                message.ParseFromString(raw)
                record("server->client", raw, message)
                if message.WhichOneof("type") == "navigation" and main_page_hash is None:
                    main_page_hash = message.navigation.page_script_hash
                if message.WhichOneof("type") == "delta" and message.delta.WhichOneof("type") == "new_element":
                    element = message.delta.new_element
                    if element.WhichOneof("type") in ("selectbox", "text_input", "text_area", "checkbox", "button"):
                        widget = getattr(element, element.WhichOneof("type"))
                        key = getattr(widget, "query_param_key", "") or widget.id.rsplit("-", 1)[-1]
                        widget_ids[key] = widget.id
                if message.WhichOneof("type") == "script_finished":
                    if args.scenario in ("rerun", "navigation-rerun", "rerun-messages", "rerun-queue") and message.script_finished == 2:
                        continue
                    assert message.script_finished == 0
                    break
        ws.close()
    trace["cleanup"]["websocket_closed"] = True
    trace["successful"] = True
except Exception as error:
    trace["producer_error"] = f"{type(error).__name__}: {error}"
    raise
finally:
    if server is not None:
        server.terminate()
        server.wait(timeout=10)
        trace["cleanup"]["server_stopped"] = server.poll() is not None
    trace_path.write_text(json.dumps(trace, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
