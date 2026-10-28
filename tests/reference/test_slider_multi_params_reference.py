"""Frozen slider/multiselect parameter evidence (python + rust)."""
import base64
import json
from pathlib import Path

from google.protobuf.json_format import MessageToDict
from streamlit.proto.BackMsg_pb2 import BackMsg
from streamlit.proto.ForwardMsg_pb2 import ForwardMsg

PYTHON = Path(__file__).parent / "reference-browser/slider-multi-params"
RUST = Path(__file__).parents[1] / "browser/rust-slider-multi-params"


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
    widgets = {element["fields"]["label"]: element["fields"] for element in raw["elements"] if element["kind"] != "heading"}
    stepped = widgets["Datetime stepped"]
    assert stepped["data_type"] == "DATETIME" and stepped["format"] == "YYYY-MM-DD"
    assert stepped["step"] == 1800000000.0, "timedelta(minutes=30) rides as microseconds"
    assert stepped["default"] == [1710504000000000.0], "2024-03-15 12:00 UTC as epoch microseconds"
    assert (stepped["min"], stepped["max"]) == (1709251200000000.0, 1711843200000000.0)
    window = widgets["Date window"]
    assert window["data_type"] == "DATE" and window["step"] == 86400000000.0, "the date default step is one day"
    assert window["default"] == [1718409600000000.0]
    defaults = widgets["Defaults"]
    assert defaults["default"] == [1, 2], "default selections ride as option indices"
    assert defaults["options"] == ["p", "q", "r"]


def test_rust_matches_field_for_field():
    raw = read(RUST / "trace.json")
    assert raw["runtime"] == "rust" and raw["server_cleanup"] == "caller-owned"
    assert raw["finishes"] == [0]
    python = read(PYTHON / "trace.json")
    left, right = comparable(python), comparable(raw)
    assert len(left) == len(right) == 4
    for a, b in zip(left, right):
        assert a == b, (a, b)
