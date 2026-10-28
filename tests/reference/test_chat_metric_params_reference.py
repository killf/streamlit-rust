"""Frozen chat/metric/progress parameter evidence (python + rust)."""
import base64
import json
import re
from pathlib import Path

from google.protobuf.json_format import MessageToDict
from streamlit.proto.BackMsg_pb2 import BackMsg
from streamlit.proto.ForwardMsg_pb2 import ForwardMsg

PYTHON = Path(__file__).parent / "reference-browser/chat-metric-params"
RUST = Path(__file__).parents[1] / "browser/rust-chat-metric-params"


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
    out = []
    for element in capture["elements"]:
        if element["kind"] == "exception":
            continue  # the python-only float overload error
        fields = dict(element["fields"])
        fields.pop("id", None)
        if element["kind"] == "markdown":
            fields.pop("body", None)
        blob = re.sub(r"[0-9a-f]{32}", "<digest32>", json.dumps(fields, sort_keys=True))
        out.append((element["kind"], json.loads(blob)))
    return out


def test_python_reference_rules():
    raw = read(PYTHON / "trace.json")
    assert raw["runtime"] == "python" and raw["reference_version"] == "1.66.1"
    assert raw["successful"] and "producer_error" not in raw
    assert raw["server_cleanup"] == "collector-owned" and raw["cleanup"]["server_stopped"] is True
    assert raw["finishes"] == [0]
    kinds = [element["kind"] for element in raw["elements"]]
    assert kinds == ["heading", "add_block:chat_message", "markdown", "metric", "metric", "metric", "metric", "progress", "exception"]
    chat = raw["elements"][1]["fields"]
    assert chat["avatar_type"] == "EMOJI" and chat["avatar"] == "🛠️"
    metrics = {element["fields"]["label"]: element["fields"] for element in raw["elements"] if element["kind"] == "metric"}
    # No delta and zero delta: NONE + GRAY. Note the proto zero-values —
    # DOWN=0 and RED=0 — are OMITTED by MessageToDict.
    assert metrics["No delta"] == {"body": "42", "color": "GRAY", "direction": "NONE", "label": "No delta", "label_visibility": {}}
    assert metrics["Zero delta"] == {"body": "5", "color": "GRAY", "delta": "0", "direction": "NONE", "label": "Zero delta", "label_visibility": {}}
    assert metrics["Gray"] == {"body": "7", "color": "GRAY", "delta": "3", "direction": "UP", "label": "Gray", "label_visibility": {}}
    assert metrics["Negative"] == {"body": "9", "delta": "-2", "label": "Negative", "label_visibility": {}}, "DOWN+RED are the omitted zero values"
    progress = next(element["fields"] for element in raw["elements"] if element["kind"] == "progress")
    assert progress == {"text": "Halfway there", "value": 50}
    exception = next(element["fields"] for element in raw["elements"] if element["kind"] == "exception")
    assert "outside the required range [0.0, 1.0]" in exception["message"] and exception["is_streamlit_exception"]


def test_rust_matches_field_for_field():
    raw = read(RUST / "trace.json")
    assert raw["runtime"] == "rust" and raw["server_cleanup"] == "caller-owned"
    assert raw["finishes"] == [0]
    python = read(PYTHON / "trace.json")
    left, right = comparable(python), comparable(raw)
    assert len(left) == len(right) == 8
    for a, b in zip(left, right):
        assert a == b, (a, b)
