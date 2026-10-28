"""Frozen st.context reflection from the pinned Python 1.66.1 wire."""
import base64
import hashlib
import json
from pathlib import Path

from google.protobuf.json_format import MessageToDict
from streamlit.proto.BackMsg_pb2 import BackMsg
from streamlit.proto.ForwardMsg_pb2 import ForwardMsg

ROOT = Path(__file__).parent / "reference-browser/context-headers"


def read(path):
    return json.loads((ROOT / path).read_text(encoding="utf-8-sig"))


def test_frozen_context_files_and_frames_are_complete():
    manifest = read("manifest.json")
    assert manifest["scope"] == "captured data only; no source identity gates"
    paths = []
    for item in manifest["files"]:
        path = (ROOT / item["file"]).resolve()
        assert path.is_relative_to(ROOT.resolve())
        data = path.read_bytes()
        assert len(data) == item["bytes"] and hashlib.sha256(data).hexdigest() == item["sha256"]
        paths.append(item["file"])
    assert "trace.json" in paths


def test_context_reflects_handshake_headers_and_empty_frontend_fields():
    raw = read("trace.json")
    assert raw["runtime"] == "python" and raw["reference_version"] == "1.66.1"
    assert "producer_error" not in raw and raw["finishes"] == [0, 0]
    assert raw["cleanup"] == {"websocket_closed": True, "close_code": 1000, "server_stopped": True}
    assert raw["handshake"]["subprotocol"] == "streamlit"
    messages = []
    for frame in raw["frames"]:
        data = base64.b64decode(frame["base64"], validate=True)
        assert len(data) == frame["bytes"]
        message = BackMsg() if frame["direction"] == "client->server" else ForwardMsg()
        message.ParseFromString(data)
        assert MessageToDict(message, preserving_proto_field_name=True) == frame["message"]
        messages.append(message)
    sessions = [message.new_session for message in messages if message.WhichOneof("type") == "new_session"]
    assert len(sessions) == 2 and sessions[0].initialize.environment_info.streamlit_version == "1.66.1"
    reports = [message.delta.new_element.code.code_text
               for message in messages
               if message.WhichOneof("type") == "delta" and message.delta.WhichOneof("type") == "new_element"
               and message.delta.new_element.WhichOneof("type") == "code"]
    assert len(reports) == 2 and reports[0] == reports[1], "the context does not change across ordinary reruns"
    report = raw["report"]
    # The probe headers ride the WS handshake and Python surfaces every one of
    # them without a whitelist — the Rust proposal's default whitelist is a
    # deliberate, documented divergence.
    for header, value in raw["probe_headers"].items():
        assert report["headers"].get(header) == value, f"probe header {header} must be reflected"
    assert "Sec-Websocket-Key" in report["headers"] and "Host" in report["headers"], "transport headers are included"
    # The frontend-session fields stay empty for a native connection: url,
    # timezone, locale and theme come from the browser session, not the
    # handshake; a direct connection without X-Forwarded-For has no address.
    assert report["ip_address"] is None
    assert report["url"] == "" and report["locale"] == "" and report["timezone"] == ""
    assert report["timezone_offset"] == 0 and report["theme"] == {"type": ""} and report["is_embedded"] is False


def test_browser_path_context_rides_the_rerun_context_info():
    # The browser reference: the official frontend reports the page context
    # with every rerun (context_info), and ?embed=true flips is_embedded
    # (?st_embed=true does not — measured).
    raw = json.loads((Path(__file__).parent / "reference-browser/context-browser/trace.json").read_text(encoding="utf-8-sig"))
    assert raw["runtime"] == "python" and raw["reference_version"] == "1.66.1" and "producer_error" not in raw
    assert raw["profile_cleaned"] is True and raw["server_stopped"] is True
    reruns = [frame for frame in raw["frames"] if frame["direction"] == "client->server" and "rerun_script" in frame["message"]]
    assert reruns, "the frontend rerun must be on the wire"
    context = reruns[0]["message"]["rerun_script"]["context_info"]
    assert context["is_embedded"] is True and context["locale"] == "zh-CN"
    assert context["timezone"] == "Asia/Shanghai" and context["timezone_offset"] == -480
    assert context["url"].startswith("http://127.0.0.1:") and context["color_scheme"] == "dark"
    report = raw["report"]
    assert report["is_embedded"] is True and report["locale"] == "zh-CN" and report["timezone"] == "Asia/Shanghai"
    assert report["theme"] == {"type": "dark"} and report["url"] == context["url"].rstrip("/")
    assert report["ip_address"] is None
    assert "Cookie" in report["headers"], "the real frontend connection carries the XSRF cookie"
