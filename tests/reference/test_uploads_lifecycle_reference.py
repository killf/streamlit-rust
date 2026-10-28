"""Frozen upload concurrency and session-expiry reference (python 1.66.1)."""
import base64
import hashlib
import json
from pathlib import Path

from google.protobuf.json_format import MessageToDict
from streamlit.proto.BackMsg_pb2 import BackMsg
from streamlit.proto.ForwardMsg_pb2 import ForwardMsg

ROOT = Path(__file__).parent / "reference-browser/uploads-lifecycle"


def test_frozen_files_and_frames():
    raw = json.loads((ROOT / "trace.json").read_text(encoding="utf-8-sig"))
    assert raw["runtime"] == "python" and raw["reference_version"] == "1.66.1"
    assert raw["successful"] and "producer_error" not in raw
    assert raw["ttl_seconds"] == 3 and raw["cleanup"]["server_stopped"] is True
    for frame in raw["frames"]:
        data = base64.b64decode(frame["base64"], validate=True)
        assert len(data) == frame["bytes"]
        message = BackMsg() if frame["direction"] == "client->server" else ForwardMsg()
        message.ParseFromString(data)
        assert MessageToDict(message, preserving_proto_field_name=True) == frame["message"]


def test_measured_concurrency_and_expiry_semantics():
    raw = json.loads((ROOT / "trace.json").read_text(encoding="utf-8-sig"))
    stages = raw["stages"]
    # Concurrent PUTs to distinct URLs never disturb each other.
    assert stages["concurrent_distinct"] == {"alpha": 204, "beta": 204}
    # A same-URL race answers 204 to both writers and leaves exactly one
    # complete write (the frozen run kept version B, size 22, no mixture).
    assert stages["concurrent_same_url"] == {"A": 204, "B": 204}
    survivor = stages["surviving_content"]
    assert survivor["count"] == 1 and survivor["files"][0]["name"] == "gamma.bin"
    assert survivor["files"][0]["size"] in (len(b"gamma-version-A"), len(b"gamma-version-B-longer"))
    head = survivor["files"][0]["bytes_head"]
    assert bytes(head) in (b"gamma-version-A"[:8], b"gamma-version-B-longer"[:8])
    # After the socket drops past server.disconnectedSessionTTL the upload
    # endpoint rejects the PUT (unknown session) while DELETE stays idempotent.
    assert stages["after_expiry_put"] == 400
    assert stages["after_expiry_delete"] == 204
    assert stages["unknown_session_put"] == 400
