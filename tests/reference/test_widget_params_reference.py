"""Frozen widget creation-parameter evidence (python reference + rust browser)."""
import base64
import json
import re
from pathlib import Path

from google.protobuf.json_format import MessageToDict
from streamlit.proto.BackMsg_pb2 import BackMsg
from streamlit.proto.ForwardMsg_pb2 import ForwardMsg

PYTHON = Path(__file__).parent / "reference-browser/widget-params"
RUST = Path(__file__).parents[1] / "browser/rust-widget-params"


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
        fields.pop("id", None)  # widget ids are per-runtime identity
        blob = json.dumps(fields, sort_keys=True)
        blob = re.sub(r"[0-9a-f]{32}", "<digest32>", blob)
        out.append((element["kind"], json.loads(blob)))
    return out


def test_python_reference_widget_parameter_edges():
    raw = read(PYTHON / "trace.json")
    assert raw["runtime"] == "python" and raw["reference_version"] == "1.66.1"
    assert raw["successful"] and "producer_error" not in raw
    assert raw["server_cleanup"] == "collector-owned" and raw["cleanup"]["server_stopped"] is True
    assert raw["finishes"] == [0]
    widgets = {element["fields"]["label"]: element["fields"] for element in raw["elements"] if element["kind"] != "heading"}
    free, bounded, int_bounded = widgets["Float free"], widgets["Float bounded"], widgets["Int bounded"]
    assert free["format"] == "%0.2f" and free["data_type"] == "FLOAT"
    assert free["step"] == 0.01
    assert free["min"] == -1.7976931348623157e308 and free["max"] == 1.7976931348623157e308
    assert "has_min" not in free and "has_max" not in free
    assert bounded["format"] == "%0.2f" and bounded["has_min"] and bounded["has_max"]
    assert (bounded["min"], bounded["max"], bounded["step"]) == (0.25, 9.75, 0.25)
    assert int_bounded["format"] == "%d" and int_bounded["has_min"] and int_bounded["has_max"]
    assert (int_bounded["default"], int_bounded["step"], int_bounded["min"], int_bounded["max"]) == (4.0, 2.0, 2.0, 8.0)
    plain, horizontal = widgets["Plain"], widgets["Horizontal"]
    assert "default" not in plain, "index=None emits no default"
    assert horizontal["horizontal"] is True and horizontal["captions"] == ["first", "second"] and horizontal["default"] == 0
    area = widgets["Bounded"]
    assert area["default"] == "hello" and area["max_chars"] == 10 and area["placeholder"] == "type here"
    capped = widgets["Capped"]
    assert capped["max_selections"] == 2 and capped["options"] == ["p", "q", "r"]


def test_rust_widgets_match_field_for_field():
    raw = read(RUST / "trace.json")
    assert raw["runtime"] == "rust" and raw["server_cleanup"] == "caller-owned"
    assert raw["finishes"] == [0]
    python = read(PYTHON / "trace.json")
    left, right = comparable(python), comparable(raw)
    assert len(left) == len(right) == 8
    for a, b in zip(left, right):
        assert a == b, (a, b)
