"""Frozen widget creation-parameter evidence (python reference + rust browser)."""
import base64
import json
import re
from pathlib import Path

import pytest

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


INTEGER_BOUND_CASES = (
    ("Int free", 4, None, None),
    ("Int min only", 4, 2, None),
    ("Int max only", 4, None, 8),
    ("Int zero min", 4, 0, None),
    ("Int zero max", -4, None, 0),
    ("Int safe high", 9007199254740991, None, None),
    ("Int safe low", -9007199254740991, None, None),
)


def check_integer_bound_capture(capture):
    assert capture["successful"] and "producer_error" not in capture
    assert capture["cleanup"]["websocket_closed"]
    if capture["runtime"] == "python":
        assert capture["cleanup"]["server_stopped"]
    messages = list(frames(capture))
    assert [m.WhichOneof("type") for m in messages].count("rerun_script") == 1
    request = next(m.rerun_script for m in messages if isinstance(m, BackMsg))
    assert request.query_string == "probe=integer-bounds" and not request.widget_states.widgets
    finishes = [m.script_finished for m in messages if m.WhichOneof("type") == "script_finished"]
    assert finishes == capture["finishes"] == [0]
    sessions = [m.new_session for m in messages if m.WhichOneof("type") == "new_session"]
    assert len(sessions) == 1 and sessions[0].initialize.environment_info.streamlit_version == "1.66.1"
    emitted = []
    for msg in messages:
        if msg.WhichOneof("type") != "delta" or msg.delta.WhichOneof("type") != "new_element":
            continue
        element = msg.delta.new_element
        kind = element.WhichOneof("type")
        assert kind != "exception"
        emitted.append((kind, MessageToDict(getattr(element, kind), preserving_proto_field_name=True)))
    assert emitted == [(e["kind"], e["fields"]) for e in capture["elements"]]
    assert len(emitted) == 15
    # The opt-in tail adds seven integers; original eight elements are preserved.
    baseline = read(PYTHON / "trace.json")
    assert comparable({"elements": capture["elements"][:8]}) == comparable(baseline)
    for (kind, number), (label, value, low, high) in zip(emitted[8:], INTEGER_BOUND_CASES, strict=True):
        assert kind == "number_input" and number["label"] == label
        assert number["default"] == value and number["step"] == 1 and number["format"] == "%d"
        assert number.get("data_type", "INT") == "INT"
        assert number.get("has_min", False) == (low is not None)
        assert number.get("has_max", False) == (high is not None)
        assert number.get("min", 0) == (-9007199254740991 if low is None else low)
        assert number.get("max", 0) == (9007199254740991 if high is None else high)


@pytest.mark.parametrize("root", (PYTHON, RUST), ids=("python", "rust"))
def test_integer_unset_bounds_use_safe_sentinels(root):
    capture = read(root / "integer-bounds/trace.json")
    check_integer_bound_capture(capture)


@pytest.mark.parametrize("mutation", ("zero_min", "huge_max", "explicit_flag"))
def test_integer_bounds_reject_coherent_wrong_wire(mutation):
    capture = read(PYTHON / "integer-bounds/trace.json")
    for frame in capture["frames"]:
        if frame["direction"] != "server->client":
            continue
        msg = ForwardMsg()
        msg.ParseFromString(base64.b64decode(frame["base64"]))
        if msg.delta.new_element.number_input.label != "Int free":
            continue
        number = msg.delta.new_element.number_input
        if mutation == "zero_min":
            number.min = 0
        elif mutation == "huge_max":
            number.max = 1.7976931348623157e308
        else:
            number.has_min = True
        raw = msg.SerializeToString()
        frame.update(base64=base64.b64encode(raw).decode(), bytes=len(raw), message=MessageToDict(msg, preserving_proto_field_name=True))
        for element in capture["elements"]:
            if element["fields"].get("label") == "Int free":
                element["fields"] = MessageToDict(number, preserving_proto_field_name=True)
        break
    else:
        raise AssertionError("missing mutation target")
    with pytest.raises(AssertionError):
        check_integer_bound_capture(capture)
