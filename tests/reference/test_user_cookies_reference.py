"""Frozen st.user (anonymous) and st.context.cookies evidence, both runtimes."""
import base64
import hashlib
import json
from pathlib import Path

from google.protobuf.json_format import MessageToDict
from streamlit.proto.BackMsg_pb2 import BackMsg
from streamlit.proto.ForwardMsg_pb2 import ForwardMsg

PYTHON = Path(__file__).parent / "reference-browser/user-cookies"
RUST = Path(__file__).parents[1] / "browser/rust-user-cookies"


def frames(capture):
    for frame in capture["frames"]:
        data = base64.b64decode(frame["base64"], validate=True)
        assert len(data) == frame["bytes"]
        message = BackMsg() if frame["direction"] == "client->server" else ForwardMsg()
        message.ParseFromString(data)
        assert MessageToDict(message, preserving_proto_field_name=True) == frame["message"]
        yield message


def test_python_reference_anonymous_user_and_cookie_parsing():
    raw = json.loads((PYTHON / "trace.json").read_text(encoding="utf-8-sig"))
    assert raw["runtime"] == "python" and raw["reference_version"] == "1.66.1"
    assert raw["successful"] and "producer_error" not in raw
    assert raw["server_cleanup"] == "collector-owned" and raw["cleanup"]["server_stopped"] is True
    report = raw["report"]
    # The anonymous baseline: an empty mapping with no attribute access, and
    # cookies parsed verbatim from the handshake Cookie header.
    assert report["user"] == {} and report["user_keys"] == []
    assert report["cookies"] == {"probe-flavor": "oat", "probe-session": "42"}
    assert report["cookie_missing"] is None
    sessions = [message for message in frames(raw) if message.WhichOneof("type") == "new_session"]
    assert len(sessions) == 1 and sessions[0].new_session.initialize.environment_info.streamlit_version == "1.66.1"


def test_rust_capture_matches_the_anonymous_baseline_and_parsing():
    raw = json.loads((RUST / "trace.json").read_text(encoding="utf-8-sig"))
    assert raw["runtime"] == "rust" and "producer_error" not in raw
    assert raw["server_cleanup"] == "caller-owned"
    assert raw["url"].startswith("http://127.0.0.1:8592")
    report = raw["report"]
    assert report["user"] == {}
    assert report["cookies"] == {"probe-flavor": "oat", "probe-session": "42"}
