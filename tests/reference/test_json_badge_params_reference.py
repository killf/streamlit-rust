"""Frozen json/badge/feedback parameter evidence (python + rust)."""
import base64
import json
from pathlib import Path

from google.protobuf.json_format import MessageToDict
from streamlit.proto.BackMsg_pb2 import BackMsg
from streamlit.proto.ForwardMsg_pb2 import ForwardMsg

PYTHON = Path(__file__).parent / "reference-browser/json-badge-params"
RUST = Path(__file__).parents[1] / "browser/rust-json-badge-params"


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


def test_python_reference_rules():
    raw = read(PYTHON / "trace.json")
    assert raw["runtime"] == "python" and raw["reference_version"] == "1.66.1"
    assert raw["successful"] and "producer_error" not in raw
    assert raw["server_cleanup"] == "collector-owned" and raw["cleanup"]["server_stopped"] is True
    assert raw["finishes"] == [0]
    kinds = [element["kind"] for element in raw["elements"]]
    assert kinds == ["heading", "json", "json", "markdown", "markdown", "feedback"]
    expanded, collapsed = raw["elements"][1]["fields"], raw["elements"][2]["fields"]
    assert expanded == {"body": '{"outer": {"inner": [1, 2]}}', "expanded": True}
    assert collapsed == {"body": '{"deep": {"a": {"b": {"c": 1}}}}'}, "collapsed omits expanded entirely"
    green, plain = raw["elements"][3]["fields"], raw["elements"][4]["fields"]
    assert green == {"body": ":green-badge[:material/rocket_launch: New]", "element_type": "NATIVE"}, "badge markdown leaves wrap unset"
    assert plain == {"body": ":blue-badge[Plain]", "element_type": "NATIVE"}, "no separator without an icon"
    feedback = raw["elements"][5]["fields"]
    feedback.pop("id", None)
    assert feedback == {"disabled": True}


def test_rust_matches_field_for_field():
    raw = read(RUST / "trace.json")
    assert raw["runtime"] == "rust" and raw["server_cleanup"] == "caller-owned"
    assert raw["finishes"] == [0]
    python = read(PYTHON / "trace.json")
    left, right = comparable(python), comparable(raw)
    assert len(left) == len(right) == 6
    for a, b in zip(left, right):
        assert a == b, (a, b)
