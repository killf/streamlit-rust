"""Frozen temporal/slider creation-parameter evidence (python + rust)."""
import base64
import json
from pathlib import Path

from google.protobuf.json_format import MessageToDict
from streamlit.proto.BackMsg_pb2 import BackMsg
from streamlit.proto.ForwardMsg_pb2 import ForwardMsg

PYTHON = Path(__file__).parent / "reference-browser/temporal-params"
RUST = Path(__file__).parents[1] / "browser/rust-temporal-params"


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
        fields = dict(element["fields"])
        fields.pop("id", None)
        out.append((element["kind"], fields))
    return out


def test_python_reference_temporal_edges():
    raw = read(PYTHON / "trace.json")
    assert raw["runtime"] == "python" and raw["reference_version"] == "1.66.1"
    assert raw["successful"] and "producer_error" not in raw
    assert raw["server_cleanup"] == "collector-owned" and raw["cleanup"]["server_stopped"] is True
    assert raw["finishes"] == [0]
    widgets = {element["fields"]["label"]: element["fields"] for element in raw["elements"] if element["kind"] != "heading"}
    bounded = widgets["Bounded"]
    assert bounded["default"] == ["2024-03-15"] and bounded["min"] == "2024-01-01" and bounded["max"] == "2024-12-31"
    assert bounded["format"] == "YYYY/MM/DD"
    formatted = widgets["Formatted"]
    assert formatted["format"] == "DD/MM/YYYY"
    assert (formatted["min"], formatted["max"]) == ("2014-06-01", "2034-06-01"), "the unbounded window is value ± 10 years"
    slider = widgets["Range"]
    assert slider["type"] == "SELECT_SLIDER" and slider["default"] == [0.0, 2.0] and slider["options"] == ["low", "mid", "high"]
    assert (slider["max"], slider["step"], slider["format"]) == (2.0, 1.0, "%s")
    assert "min" not in slider, "the select slider omits min at index 0 (proto default)"
    stepped = widgets["Stepped"]
    assert stepped["step"] == "900" and stepped["format"] == "24h" and stepped["default"] == "12:30"


def test_rust_temporal_matches_field_for_field():
    raw = read(RUST / "trace.json")
    assert raw["runtime"] == "rust" and raw["server_cleanup"] == "caller-owned"
    assert raw["finishes"] == [0]
    python = read(PYTHON / "trace.json")
    left, right = comparable(python), comparable(raw)
    assert len(left) == len(right) == 5
    for a, b in zip(left, right):
        assert a == b, (a, b)
