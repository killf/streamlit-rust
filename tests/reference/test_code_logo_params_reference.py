"""Frozen code/skeleton/logo parameter evidence (python + rust)."""
import base64
import json
from pathlib import Path

from google.protobuf.json_format import MessageToDict
from streamlit.proto.BackMsg_pb2 import BackMsg
from streamlit.proto.ForwardMsg_pb2 import ForwardMsg

PYTHON = Path(__file__).parent / "reference-browser/code-logo-params"
RUST = Path(__file__).parents[1] / "browser/rust-code-logo-params"


def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def frames(capture):
    for frame in capture["frames"]:
        data = base64.b64decode(frame["base64"], validate=True)
        assert len(data) == frame["bytes"]
        message = BackMsg() if frame["direction"] == "client->server" else ForwardMsg()
        message.ParseFromString(data)
        assert MessageToDict(message, preserving_proto_field_name=True) == frame["message"]
        yield message


def comparable(capture):
    return [(element["kind"], {key: value for key, value in element["fields"].items() if key != "id"}) for element in capture["elements"]]


def logo_frames(capture):
    out = []
    for message in frames(capture):
        if message.WhichOneof("type") == "logo":
            out.append((message.logo.image, message.logo.image_type, message.logo.size, message.logo.link))
    return out


def test_python_reference_rules():
    raw = read(PYTHON / "trace.json")
    assert raw["runtime"] == "python" and raw["reference_version"] == "1.66.1"
    assert raw["successful"] and "producer_error" not in raw
    assert raw["server_cleanup"] == "collector-owned" and raw["cleanup"]["server_stopped"] is True
    assert raw["finishes"] == [0]
    kinds = [element["kind"] for element in raw["elements"]]
    assert kinds == ["heading", "code", "skeleton"]
    code = raw["elements"][1]["fields"]
    assert code == {"code_text": "print('hi')", "language": "rust", "show_line_numbers": True}
    skeleton = raw["elements"][2]["fields"]
    assert skeleton == {}, "the default skeleton message carries no fields"
    logos = logo_frames(raw)
    assert logos == [("🧊", 1, "medium", "")], "emoji image, EMOJI type, medium default size, no link"  # EMOJI enum = 1


def test_rust_matches_field_for_field_and_logo_for_logo():
    raw = read(RUST / "trace.json")
    assert raw["runtime"] == "rust" and raw["server_cleanup"] == "caller-owned"
    assert raw["finishes"] == [0]
    python = read(PYTHON / "trace.json")
    left, right = comparable(python), comparable(raw)
    assert len(left) == len(right) == 3
    for a, b in zip(left, right):
        assert a == b, (a, b)
    assert logo_frames(raw) == logo_frames(python)
