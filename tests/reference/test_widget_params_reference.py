"""Frozen widget creation-parameter evidence (python reference + rust browser)."""
import base64
import json
import re
import sys
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


NUMBER_PHASES = ("load", "edit", "zero-min", "narrow-max", "grow", "default", "edit-low", "raise-min", "step", "disabled", "recover", "assign")
NUMBER_VALUES = (4, 7, 7, 4, 4, 4, 1, 4, 4, 4, 4, 8)


def number_runs(capture):
    assert capture["successful"] and "producer_error" not in capture
    assert capture["cleanup"]["websocket_closed"]
    if capture["runtime"] == "python":
        assert capture["cleanup"]["server_stopped"]
    runs, emitted = [], []
    for msg in frames(capture):
        kind = msg.WhichOneof("type")
        if isinstance(msg, BackMsg):
            assert kind == "rerun_script"
            runs.append({"request": msg.rerun_script, "widgets": [], "reports": [], "finishes": [], "sessions": [], "layouts": []})
        elif kind == "new_session":
            runs[-1]["sessions"].append(msg.new_session)
        elif kind == "script_finished":
            runs[-1]["finishes"].append(msg.script_finished)
        elif kind == "delta":
            assert msg.delta.WhichOneof("type") == "new_element"
            element = msg.delta.new_element
            element_kind = element.WhichOneof("type")
            assert element_kind in ("number_input", "json")
            fields = MessageToDict(getattr(element, element_kind), preserving_proto_field_name=True)
            emitted.append((element_kind, fields))
            if element_kind == "number_input":
                runs[-1]["layouts"].append(MessageToDict(element.width_config, preserving_proto_field_name=True))
                runs[-1]["widgets"].append(element.number_input)
            else:
                runs[-1]["reports"].append(json.loads(element.json.body))
    assert emitted == [(e["kind"], e["fields"]) for e in capture["elements"]]
    return runs


def check_number_sequence(capture, *, floating=False):
    runs = number_runs(capture)
    assert len(runs) == 12 and capture["finishes"] == [0] * 12
    ids, sessions, run_ids = set(), set(), set()
    result = []
    values = (4.25, 7.25, 7.25, 4.25, 4.25, 4.25, 1.25, 4.25, 4.25, 4.25, 4.25, 8.25) if floating else NUMBER_VALUES
    for index, (run, phase, value) in enumerate(zip(runs, NUMBER_PHASES, values, strict=True)):
        request = run["request"]
        assert request.query_string == "probe=" + ("number-float" if floating else "number-sequence") + "&phase=" + phase
        assert not request.is_history_navigation
        assert len(run["sessions"]) == 1 and run["finishes"] == [0]
        session = run["sessions"][0]
        assert session.initialize.environment_info.streamlit_version == "1.66.1"
        sessions.add(session.initialize.session_id)
        run_ids.add(session.script_run_id)
        assert len(run["widgets"]) == 1
        assert run["layouts"] == [{"use_stretch": True}]
        widget = run["widgets"][0]
        ids.add(widget.id)
        incoming = request.widget_states.widgets
        if index in (1, 6):
            assert len(incoming) == 1 and incoming[0].id == widget.id
            assert incoming[0].WhichOneof("value") == ("double_value" if floating else "int_value")
            assert getattr(incoming[0], "double_value" if floating else "int_value") == value
        else:
            assert not incoming
        sentinel = sys.float_info.max if floating else 9007199254740991
        low = 3 if phase == "raise-min" else 0 if index >= 2 else -sentinel
        high = 6 if phase == "narrow-max" else 10 if index >= 3 else sentinel
        assert (widget.min, widget.max) == (low, high)
        assert (widget.has_min, widget.has_max) == (index >= 2, index >= 3)
        assert widget.default == ((5.5 if phase == "default" else 4.25) if floating else (5 if phase == "default" else 4))
        assert widget.step == ((0.5 if phase == "step" else 0.25) if floating else (2 if phase == "step" else 1))
        assert widget.data_type == int(floating)
        assert widget.format == ("%0.2f" if floating else "%d")
        assert widget.label == ("Dynamic float" if floating else "Dynamic")
        assert widget.disabled == (phase == "disabled")
        sync = index in (3, 7, 11)
        assert widget.set_value == sync and widget.HasField("value") == sync
        if sync:
            assert widget.value == value
        edits = [7.25, 1.25] if floating else [7, 1]
        calls = [] if index == 0 else edits[:1] if index < 6 else edits
        report = {"phase": phase, "value": value, "state": value, "callbacks": calls}
        assert run["reports"] == [report]
        result.append(report)
    assert len(ids) == len(sessions) == 1 and len(run_ids) == 12
    return result


@pytest.mark.parametrize("root", (PYTHON, RUST), ids=("python", "rust"))
def test_keyed_number_dynamic_bounds_match_reference(root):
    check_number_sequence(read(root / "number-sequence/trace.json"))


@pytest.mark.parametrize("root", (PYTHON, RUST), ids=("python", "rust"))
def test_float_number_dynamic_bounds_match_reference(root):
    check_number_sequence(read(root / "number-float/trace.json"), floating=True)


@pytest.mark.parametrize("floating", (False, True), ids=("integer", "float"))
@pytest.mark.parametrize("mutation", ("identity", "sync", "callback", "value", "type", "step", "bound"))
def test_dynamic_number_gate_rejects_coherent_wrong_wire(mutation, floating):
    capture = read(PYTHON / ("number-float/trace.json" if floating else "number-sequence/trace.json"))
    run = -1
    for frame in capture["frames"]:
        if frame["direction"] == "client->server":
            run += 1
            continue
        if run != 3:
            continue
        msg = ForwardMsg()
        msg.ParseFromString(base64.b64decode(frame["base64"]))
        element = msg.delta.new_element
        kind = element.WhichOneof("type")
        if kind == "number_input" and mutation in ("identity", "sync", "value", "type", "step", "bound"):
            if mutation == "identity":
                element.number_input.id += "changed"
            elif mutation == "sync":
                element.number_input.set_value = False
            elif mutation == "type":
                element.number_input.data_type = 1 - element.number_input.data_type
            elif mutation == "step":
                element.number_input.step += 1
            elif mutation == "bound":
                element.number_input.min = -1
            else:
                element.number_input.value = 5
        elif kind == "json" and mutation in ("callback", "value"):
            report = json.loads(element.json.body)
            if mutation == "callback":
                report["callbacks"].append(4)
            else:
                report["state"] = report["value"] = 5
            element.json.body = json.dumps(report)
        else:
            continue
        raw = msg.SerializeToString()
        frame.update(base64=base64.b64encode(raw).decode(), bytes=len(raw), message=MessageToDict(msg, preserving_proto_field_name=True))
    capture["elements"] = []
    for msg in frames(capture):
        if msg.WhichOneof("type") == "delta":
            element = msg.delta.new_element
            kind = element.WhichOneof("type")
            capture["elements"].append({"kind": kind, "fields": MessageToDict(getattr(element, kind), preserving_proto_field_name=True)})
    with pytest.raises(AssertionError):
        check_number_sequence(capture, floating=floating)


UNKEYED_PHASES = ("load", "edit", "disabled", "hidden", "ignore", "none", "explicit-step", "explicit-edit", "restore-step",
                  "minzero", "min-edit", "restore-min", "width", "width-edit", "help", "restore", "default", "step2",
                  "maxzero", "negative-edit", "maxnone")
UNKEYED_VALUES = (4, 7, 7, 7, 7, 7, 4, 9, 4, 4, 8, 4, 4, 6, 4, 4, 5, 4, -4, -7, -4)
UNKEYED_IDENTITIES = (0, 0, 0, 0, 0, 0, 1, 1, 0, 2, 2, 0, 3, 3, 4, 0, 5, 6, 7, 7, 8)


def check_unkeyed_number(capture, *, stopped=False, resumed=False):
    runs = number_runs(capture)
    assert not resumed or stopped
    phases = UNKEYED_PHASES + (("normal-resume", "explicit-step") if resumed else ())
    values = UNKEYED_VALUES + ((7, 4) if resumed else ())
    identities = UNKEYED_IDENTITIES + ((0, 1) if resumed else ())
    assert len(runs) == len(phases) and capture["finishes"] == [0] * len(phases)
    ids, sessions, run_ids, calls = [], set(), set(), []
    submitted = {1: 7, 7: 9, 10: 8, 13: 6, 19: -7}
    for index, (run, phase, value) in enumerate(zip(runs, phases, values, strict=True)):
        assert run["request"].query_string == "probe=number-unkeyed&phase=" + phase + ("&stop=on" if stopped and index < 21 else "")
        if stopped and index in (8, 11, 15):
            value = 7
        assert not run["request"].is_history_navigation
        assert len(run["sessions"]) == 1 and run["finishes"] == [0]
        session = run["sessions"][0]
        assert session.initialize.environment_info.streamlit_version == "1.66.1"
        sessions.add(session.initialize.session_id)
        run_ids.add(session.script_run_id)
        assert len(run["widgets"]) == 1
        widget = run["widgets"][0]
        ids.append(widget.id)
        incoming = run["request"].widget_states.widgets
        if index in submitted:
            assert len(incoming) == 1 and incoming[0].id == widget.id
            assert incoming[0].WhichOneof("value") == "int_value" and incoming[0].int_value == submitted[index]
            calls.append("changed")
        else:
            assert not incoming
        low, high = phase in ("minzero", "min-edit"), phase in ("maxzero", "negative-edit")
        assert (widget.has_min, widget.has_max) == (low, high)
        assert (widget.min, widget.max) == (0 if low else -9007199254740991, 0 if high else 9007199254740991)
        assert widget.default == (-4 if phase in ("maxzero", "negative-edit", "maxnone") else 5 if phase == "default" else 4)
        assert widget.step == (2 if phase == "step2" else 1)
        assert widget.data_type == 0 and widget.format == "%d" and widget.label == "Unkeyed"
        assert widget.disabled == (phase == "disabled")
        assert widget.label_visibility.value == (1 if phase == "hidden" else 0)
        assert widget.ignore_rerun == (phase == "ignore")
        assert widget.help == ("hint" if phase == "help" else "")
        assert not widget.set_value and not widget.HasField("value")
        assert run["layouts"] == ([{"pixel_width": 360}] if phase in ("width", "width-edit") else [{"use_stretch": True}])
        assert run["reports"] == [{"phase": phase, "value": value, "callbacks": calls.copy()}]
    assert len(sessions) == 1 and len(run_ids) == len(phases)
    for i in range(len(phases)):
        for j in range(len(phases)):
            assert (ids[i] == ids[j]) == (identities[i] == identities[j])


@pytest.mark.parametrize("root", (PYTHON, RUST), ids=("python", "rust"))
def test_unkeyed_number_raw_options_and_normal_cleanup(root):
    check_unkeyed_number(read(root / "number-unkeyed/normal/trace.json"))


def test_unkeyed_stop_attempt_cannot_prove_normal_cleanup():
    with pytest.raises(AssertionError):
        check_unkeyed_number(read(PYTHON / "number-unkeyed/trace.json"))


@pytest.mark.parametrize("mutation", ("identity", "restored_value", "width", "step"))
def test_unkeyed_number_gate_rejects_coherent_wrong_wire(mutation):
    capture = read(PYTHON / "number-unkeyed/normal/trace.json")
    initial_id = next(e["fields"]["id"] for e in capture["elements"] if e["kind"] == "number_input")
    run = -1
    for frame in capture["frames"]:
        if frame["direction"] == "client->server":
            run += 1
            continue
        if run != {"identity": 6, "restored_value": 8, "width": 12, "step": 6}[mutation]:
            continue
        msg = ForwardMsg()
        msg.ParseFromString(base64.b64decode(frame["base64"]))
        element = msg.delta.new_element
        kind = element.WhichOneof("type")
        if kind == "number_input" and mutation in ("identity", "width", "step"):
            if mutation == "identity":
                element.number_input.id = initial_id
            elif mutation == "width":
                element.width_config.pixel_width = 361
            else:
                element.number_input.step = 2
        elif kind == "json" and mutation == "restored_value":
            report = json.loads(element.json.body)
            report["value"] = 7
            element.json.body = json.dumps(report)
        else:
            continue
        raw = msg.SerializeToString()
        frame.update(base64=base64.b64encode(raw).decode(), bytes=len(raw), message=MessageToDict(msg, preserving_proto_field_name=True))
    capture["elements"] = []
    for msg in frames(capture):
        if msg.WhichOneof("type") == "delta":
            element = msg.delta.new_element
            kind = element.WhichOneof("type")
            capture["elements"].append({"kind": kind, "fields": MessageToDict(getattr(element, kind), preserving_proto_field_name=True)})
    with pytest.raises(AssertionError):
        check_unkeyed_number(capture)


@pytest.mark.parametrize("root", (PYTHON, RUST), ids=("python", "rust"))
def test_keyed_number_natural_completion_preserves_existing_results(root):
    assert check_number_sequence(read(root / "number-sequence/normal/trace.json")) == check_number_sequence(read(PYTHON / "number-sequence/trace.json"))


@pytest.mark.parametrize("root", (PYTHON, RUST), ids=("python", "rust"))
def test_explicit_stop_preserves_unseen_number_identities(root):
    check_unkeyed_number(read(root / "number-unkeyed/stopped/trace.json"), stopped=True)


@pytest.mark.parametrize("mutation", ("lost-value", "callback", "after-normal"))
def test_stopped_number_gate_rejects_wrong_restoration(mutation):
    resumed = mutation == "after-normal"
    capture = read(PYTHON / ("number-unkeyed/stopped-resume/trace.json" if resumed else "number-unkeyed/stopped/trace.json"))
    run = -1
    for frame in capture["frames"]:
        if frame["direction"] == "client->server":
            run += 1
            continue
        if run != (22 if resumed else 8):
            continue
        msg = ForwardMsg()
        msg.ParseFromString(base64.b64decode(frame["base64"]))
        if msg.delta.new_element.WhichOneof("type") != "json":
            continue
        report = json.loads(msg.delta.new_element.json.body)
        if mutation == "after-normal":
            report["value"] = 9
        elif mutation == "lost-value":
            report["value"] = 4
        else:
            report["callbacks"].append("changed")
        msg.delta.new_element.json.body = json.dumps(report)
        raw = msg.SerializeToString()
        frame.update(base64=base64.b64encode(raw).decode(), bytes=len(raw), message=MessageToDict(msg, preserving_proto_field_name=True))
    capture["elements"] = []
    for msg in frames(capture):
        if msg.WhichOneof("type") == "delta":
            element = msg.delta.new_element
            kind = element.WhichOneof("type")
            capture["elements"].append({"kind": kind, "fields": MessageToDict(getattr(element, kind), preserving_proto_field_name=True)})
    with pytest.raises(AssertionError):
        check_unkeyed_number(capture, stopped=True, resumed=resumed)


@pytest.mark.parametrize("root", (PYTHON, RUST), ids=("python", "rust"))
def test_normal_completion_after_stop_cleans_old_identities(root):
    check_unkeyed_number(read(root / "number-unkeyed/stopped-resume/trace.json"), stopped=True, resumed=True)


def test_pre_fix_stop_capture_reproduces_lost_values():
    capture = read(RUST / "number-unkeyed/stopped-before/trace.json")
    reports = [json.loads(e["fields"]["body"]) for e in capture["elements"] if e["kind"] == "json"]
    assert [reports[i]["value"] for i in (8, 11, 15)] == [4, 4, 4]
    with pytest.raises(AssertionError):
        check_unkeyed_number(capture, stopped=True)


LIFECYCLE_PHASES = ("load", "submit", "peek", "resume", "hide", "after-hide", "restore", "after-restore")
LIFECYCLE_CALLS = [{"key": "fire", "value": True}, {"key": "plain", "value": "edited"}, {"key": "bound", "value": "changed"}]


def check_stop_lifecycle(capture):
    assert capture["successful"] and "producer_error" not in capture
    assert capture["cleanup"]["websocket_closed"]
    if capture["runtime"] == "python":
        assert capture["cleanup"]["server_stopped"]
    runs, emitted, finishes = [], [], []
    ids = {}
    for msg in frames(capture):
        kind = msg.WhichOneof("type")
        if isinstance(msg, BackMsg):
            assert kind == "rerun_script"
            runs.append({"request": msg.rerun_script, "events": [], "sessions": []})
        elif kind == "new_session":
            runs[-1]["sessions"].append(msg.new_session)
        elif kind == "script_finished":
            finishes.append(msg.script_finished)
        elif kind == "page_info_changed":
            runs[-1]["events"].append(("url", msg.page_info_changed.query_string))
        elif kind == "delta":
            assert msg.delta.WhichOneof("type") == "new_element"
            element = msg.delta.new_element
            element_kind = element.WhichOneof("type")
            assert element_kind in ("button", "text_input", "json")
            widget = getattr(element, element_kind)
            fields = MessageToDict(widget, preserving_proto_field_name=True)
            emitted.append((element_kind, dict(fields)))
            if element_kind == "json":
                report = json.loads(widget.body)
                if report["fire"] is not None:
                    assert type(report["fire"]) is bool
                if report["callbacks"]:
                    assert report["callbacks"][0]["value"] is True
                runs[-1]["events"].append(("report", report))
            else:
                key = widget.id.rsplit("-", 1)[-1]
                assert key in ("fire", "plain", "bound")
                if key in ids:
                    assert widget.id == ids[key]
                ids[key] = widget.id
                fields.pop("id")
                expected = {"label": "Fire", "type": "secondary"} if key == "fire" else {"label": key.title(), "default": "base", "label_visibility": {}}
                if key == "bound":
                    expected.update(value="url", set_value=True, query_param_key="bound")
                assert fields == expected
                assert element.has_one_shot_effect == (key == "bound")
                assert MessageToDict(element.width_config, preserving_proto_field_name=True) == ({"use_content": True} if key == "fire" else {"use_stretch": True})
                runs[-1]["events"].append(("widget", key))
    assert emitted == [(e["kind"], e["fields"]) for e in capture["elements"]]
    assert len(runs) == 8 and finishes == capture["finishes"] == [0] * 8
    assert set(ids) == {"fire", "plain", "bound"} and len(set(ids.values())) == 3
    sessions, run_ids = set(), set()
    for index, (run, phase) in enumerate(zip(runs, LIFECYCLE_PHASES, strict=True)):
        request = run["request"]
        prefix = "probe=stop-lifecycle&phase=" + phase
        present = index not in (5, 6)
        assert request.query_string == prefix + ("&bound=url" if present else "")
        assert not request.is_history_navigation
        incoming = request.widget_states.widgets
        if index == 1:
            assert [w.id for w in incoming] == [ids[key] for key in ("fire", "plain", "bound")]
            assert [w.WhichOneof("value") for w in incoming] == ["trigger_value", "string_value", "string_value"]
            assert incoming[0].trigger_value and incoming[1].string_value == "edited" and incoming[2].string_value == "changed"
        else:
            assert not incoming
        assert len(run["sessions"]) == 1
        session = run["sessions"][0]
        assert session.initialize.environment_info.streamlit_version == "1.66.1"
        sessions.add(session.initialize.session_id)
        run_ids.add(session.script_run_id)
        pairs = [["probe", "stop-lifecycle"], ["phase", phase]] + ([["bound", "url"]] if present else [])
        report = {"phase": phase, "stage": "before", "fire": (None, True, False, False, False, None, None, False)[index],
                  "plain": (None, "edited", "edited", "edited", "edited", None, None, "base")[index],
                  "bound": (None, "changed", "changed", "changed", "url", "url", "url", "url")[index],
                  "callbacks": [] if index == 0 else LIFECYCLE_CALLS, "pairs": pairs, "returns": None}
        expected = [("report", report)]
        if index in (0, 3, 6):
            expected += [("widget", "fire"), ("widget", "plain")]
            if index == 6:
                expected.append(("url", prefix + "&bound=url"))
            expected.append(("widget", "bound"))
            returns = {"fire": False, "plain": "edited" if index == 3 else "base", "bound": "url"}
            expected.append(("report", {**report, **returns, "stage": "values", "pairs": [["probe", "stop-lifecycle"], ["phase", phase], ["bound", "url"]], "returns": returns}))
        elif index in (4, 7):
            expected.append(("url", prefix))
        assert run["events"] == expected
    assert len(sessions) == 1 and len(run_ids) == 8


@pytest.mark.parametrize("root", (PYTHON, RUST), ids=("python", "rust"))
def test_bound_values_and_button_lifecycle_across_stop_and_normal_cleanup(root):
    check_stop_lifecycle(read(root / "stop-lifecycle/trace.json"))


def test_pre_fix_binding_cleanup_capture_reproduces_lost_native_value():
    capture = read(RUST / "stop-lifecycle-before/trace.json")
    reports = [json.loads(e["fields"]["body"]) for e in capture["elements"] if e["kind"] == "json"]
    assert next(r for r in reports if r["phase"] == "after-hide")["bound"] is None
    with pytest.raises(AssertionError):
        check_stop_lifecycle(capture)


@pytest.mark.parametrize("mutation", ("native", "trigger", "callback", "url", "late-url"))
def test_stop_lifecycle_gate_rejects_coherent_wrong_wire(mutation):
    capture = read(PYTHON / "stop-lifecycle/trace.json")
    run, changed = -1, False
    for i, frame in enumerate(capture["frames"]):
        if frame["direction"] == "client->server":
            run += 1
            continue
        if run != {"native": 5, "trigger": 2, "callback": 2, "url": 6, "late-url": 6}[mutation]:
            continue
        msg = ForwardMsg()
        msg.ParseFromString(base64.b64decode(frame["base64"]))
        if mutation in ("url", "late-url") and msg.WhichOneof("type") == "page_info_changed":
            if mutation == "late-url":
                capture["frames"][i], capture["frames"][i + 1] = capture["frames"][i + 1], frame
                changed = True
                break
            msg.page_info_changed.query_string += "&ignored=1"
        elif mutation in ("native", "trigger", "callback") and msg.delta.new_element.WhichOneof("type") == "json":
            report = json.loads(msg.delta.new_element.json.body)
            if mutation == "native":
                report["bound"] = None
            elif mutation == "trigger":
                report["fire"] = True
            else:
                report["callbacks"].pop()
            msg.delta.new_element.json.body = json.dumps(report)
        else:
            continue
        raw = msg.SerializeToString()
        frame.update(base64=base64.b64encode(raw).decode(), bytes=len(raw), message=MessageToDict(msg, preserving_proto_field_name=True))
        changed = True
    assert changed
    capture["elements"] = []
    for msg in frames(capture):
        if msg.WhichOneof("type") == "delta":
            element = msg.delta.new_element
            kind = element.WhichOneof("type")
            capture["elements"].append({"kind": kind, "fields": MessageToDict(getattr(element, kind), preserving_proto_field_name=True)})
    with pytest.raises(AssertionError):
        check_stop_lifecycle(capture)
