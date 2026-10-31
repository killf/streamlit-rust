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


PERMISSIVE_NUMBERS = (
    ("Int equal", 2, 2, 2, 1), ("Int zero step", 4, None, None, 0),
    ("Int negative step", 4, None, None, -2),
    ("Float equal", 2.5, 2.5, 2.5, 0.25), ("Float zero step", 1.5, None, None, 0.0),
    ("Float negative step", 1.5, None, None, -0.25),
)
REJECTED_NUMBERS = ("Int inverted", "Int below", "Int above", "Float inverted", "Float below", "Float above")


def check_permissive_numbers(capture):
    runs = number_runs(capture)
    assert len(runs) == 1 and capture["finishes"] == [0]
    run = runs[0]
    assert run["request"].query_string == "probe=number-permissive"
    assert not run["request"].widget_states.widgets and not run["request"].is_history_navigation
    assert len(run["sessions"]) == 1 and run["finishes"] == [0]
    assert run["sessions"][0].initialize.environment_info.streamlit_version == "1.66.1"
    assert run["layouts"] == [{"use_stretch": True}] * 6
    assert len(run["widgets"]) == 6
    assert [element["kind"] for element in capture["elements"]] == ["number_input", "json"] * 6 + ["json"] * 6
    ids = set()
    for index, (widget, (label, value, low, high, step)) in enumerate(zip(run["widgets"], PERMISSIVE_NUMBERS, strict=True)):
        floating = index >= 3
        sentinel = sys.float_info.max if floating else 9007199254740991
        assert widget.label == label and widget.id.endswith("-" + label)
        ids.add(widget.id)
        assert widget.default == value and widget.HasField("default")
        assert (widget.min, widget.max) == (low if low is not None else -sentinel, high if high is not None else sentinel)
        assert (widget.has_min, widget.has_max) == (low is not None, high is not None)
        assert widget.step == step and widget.data_type == int(floating)
        assert widget.format == ("%0.2f" if floating else "%d")
        assert not widget.set_value and not widget.HasField("value") and not widget.disabled
    assert len(ids) == 6
    assert run["reports"] == [
        {"case": label, "accepted": True, "value": value, "state": value}
        for label, value, *_ in PERMISSIVE_NUMBERS
    ] + [{"case": label, "accepted": False} for label in REJECTED_NUMBERS]


@pytest.mark.parametrize("root", (PYTHON, RUST), ids=("python", "rust"))
def test_number_equal_bounds_and_nonpositive_steps(root):
    check_permissive_numbers(read(root / "number-permissive/trace.json"))


def test_pre_fix_rust_rejection_does_not_match_permissive_reference():
    capture = read(RUST / "number-permissive/before/trace.json")
    run = number_runs(capture)[0]
    assert not run["widgets"]
    assert run["reports"] == [{"case": label, "accepted": False} for label, *_ in PERMISSIVE_NUMBERS] + [{"case": label, "accepted": False} for label in REJECTED_NUMBERS]
    with pytest.raises(AssertionError):
        check_permissive_numbers(capture)


@pytest.mark.parametrize("mutation", ("equal-bound", "zero-step", "negative-step", "accepted", "value", "type"))
def test_permissive_number_gate_rejects_coherent_wrong_wire(mutation):
    capture = read(PYTHON / "number-permissive/trace.json")
    for frame in capture["frames"]:
        if frame["direction"] != "server->client":
            continue
        msg = ForwardMsg()
        msg.ParseFromString(base64.b64decode(frame["base64"]))
        if msg.WhichOneof("type") != "delta":
            continue
        element = msg.delta.new_element
        kind = element.WhichOneof("type")
        if kind == "number_input":
            widget = element.number_input
            if mutation == "equal-bound" and widget.label == "Int equal":
                widget.min = 1
            elif mutation == "zero-step" and widget.label == "Float zero step":
                widget.step = 0.01
            elif mutation == "negative-step" and widget.label == "Int negative step":
                widget.step = 2
            elif mutation == "type" and widget.label == "Float equal":
                widget.data_type = 0
            else:
                continue
        elif kind == "json" and mutation in ("accepted", "value"):
            report = json.loads(element.json.body)
            if report["case"] != "Int equal":
                continue
            if mutation == "accepted":
                report = {"case": "Int equal", "accepted": False}
            else:
                report["value"] = report["state"] = 1
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
        check_permissive_numbers(capture)


NUMBER_UI_STAGES = ("load", "int-zero-increment", "int-negative-increment", "float-zero-increment",
                    "float-negative-increment", "equal-invalid", "equal-recover", "float-typed")
NUMBER_UI_VALUES = ((2, 4, 4, 2.5, 1.5, 1.5), (2, 5, 4, 2.5, 1.5, 1.5), (2, 5, 2, 2.5, 1.5, 1.5),
                    (2, 5, 2, 2.5, 1.51, 1.5), (2, 5, 2, 2.5, 1.51, 1.25), (2, 5, 2, 2.5, 1.51, 1.25),
                    (2, 5, 2, 2.5, 1.51, 1.25), (2, 5, 2, 2.5, 1.51, 2.75))


def check_number_ui(capture, folder):
    import hashlib
    from PIL import Image

    assert capture["reference_version"] == "1.66.1" and capture["runtime"] in ("python", "rust")
    assert capture["visual_review"]["accepted"]
    assert capture["visual_review"]["reviewed_stages"] == list(NUMBER_UI_STAGES)
    assert capture["cleanup"]["owned_servers_stopped"] and capture["cleanup"]["owned_tab_closed"]
    assert capture["cleanup"]["ports_without_listeners"] == [8599, 8619]
    assert [stage["stage"] for stage in capture["stages"]] == list(NUMBER_UI_STAGES)
    baseline = number_runs(read(PYTHON / "number-permissive/trace.json"))[0]["widgets"]
    expected_wire = [MessageToDict(widget, preserving_proto_field_name=True) for widget in baseline]
    for fields in expected_wire:
        fields.pop("id")
    created = [event for stage in capture["stages"] for event in stage["events"]["events"] if event["method"] == "Network.webSocketCreated"]
    assert len(created) == 1
    ws_id = created[0]["params"]["requestId"]
    port = 8619 if capture["runtime"] == "python" else 8599
    assert created[0]["params"]["url"] == f"ws://127.0.0.1:{port}/_stcore/stream"
    ids, sessions, run_ids, previous_sequence, frame_count = {}, set(), set(), 0, 0
    for stage, values in zip(capture["stages"], NUMBER_UI_VALUES, strict=True):
        phase = stage["stage"]
        assert stage["action_and_capture_calls_separate"]
        events = stage["events"]
        assert not events["truncated"] and not events["hasMore"]
        messages = []
        for event in events["events"]:
            assert previous_sequence < event["sequence"] <= events["cursor"]
            previous_sequence = event["sequence"]
            if event["method"] not in ("Network.webSocketFrameSent", "Network.webSocketFrameReceived"):
                continue
            assert event["params"]["requestId"] == ws_id
            raw = event["params"]["response"]
            assert raw["opcode"] == 2
            message = BackMsg() if event["method"].endswith("Sent") else ForwardMsg()
            message.ParseFromString(base64.b64decode(raw["payloadData"], validate=True))
            messages.append(message)
        frame_count += len(messages)
        reports = [{"case": row[0], "accepted": True, "value": value, "state": value}
                   for row, value in zip(PERMISSIVE_NUMBERS, values, strict=True)]
        reports += [{"case": label, "accepted": False} for label in REJECTED_NUMBERS]
        dom = stage["dom"]
        assert dom["url"] == f"http://127.0.0.1:{port}/?probe=number-permissive"
        assert dom["viewport"] == {"width": 1463, "height": 724, "dpr": 1.75} and not dom["exceptions"]
        assert dom["reports"] == [json.dumps(report, separators=(",", ":")).replace(",", "") for report in reports]
        assert len(dom["widgets"]) == 6
        for index, (widget, value) in enumerate(zip(dom["widgets"], values, strict=True)):
            assert widget["label"] == PERMISSIVE_NUMBERS[index][0] and not widget["disabled"]
            displayed = "3" if phase == "equal-invalid" and index == 0 else f"{value:.2f}" if index >= 3 else str(value)
            assert widget["value"] == displayed
            assert widget["step"] == ("1", "1", "-2", "0.25", "0.01", "-0.25")[index]
            low, high = PERMISSIVE_NUMBERS[index][2:4]
            sentinel = sys.float_info.max if index >= 3 else 9007199254740991
            assert (widget["min"], widget["max"]) == (str(low if low is not None else -sentinel), str(high if high is not None else sentinel))
            expected_buttons = [True, True] if index in (0, 3) else [False, False]
            if phase == "equal-invalid" and index == 0:
                expected_buttons = [False, True]
                assert "Error: Number is outside the allowed range. Please enter a value between 2 and 2." in widget["text"]
            else:
                assert "Error:" not in widget["text"]
            assert widget["buttons"] == [{"label": name, "disabled": disabled} for name, disabled in zip(("Decrement", "Increment"), expected_buttons, strict=True)]
        path = folder / stage["screenshot"]
        integrity = stage["screenshot_integrity"]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == integrity["sha256"]
        with Image.open(path) as image:
            assert image.format == integrity["format"] == "JPEG"
            assert image.size == (integrity["width"], integrity["height"]) == (1463, 724)
        if phase == "equal-invalid":
            assert not messages
            continue
        assert len(messages) == 23
        assert isinstance(messages[0], BackMsg)
        request = messages[0].rerun_script
        assert request.query_string == "probe=number-permissive" and not request.is_history_navigation
        widgets, output_reports, statuses, finishes, current_sessions, element_kinds = [], [], [], [], [], []
        for message in messages[1:]:
            kind = message.WhichOneof("type")
            if kind == "new_session":
                current_sessions.append(message.new_session)
            elif kind == "script_finished":
                finishes.append(message.script_finished)
            elif kind == "session_status_changed":
                statuses.append(message.session_status_changed.script_is_running)
            else:
                assert kind == "delta" and message.delta.WhichOneof("type") == "new_element"
                element = message.delta.new_element
                element_kinds.append(element.WhichOneof("type"))
                assert list(message.metadata.delta_path) == [0, len(widgets) + len(output_reports)]
                if element.WhichOneof("type") == "number_input":
                    widget = element.number_input
                    fields = MessageToDict(widget, preserving_proto_field_name=True)
                    assert fields.pop("id") == ids.setdefault(widget.label, widget.id)
                    assert fields == expected_wire[len(widgets)]
                    widgets.append(widget)
                else:
                    assert element.WhichOneof("type") == "json"
                    output_reports.append(json.loads(element.json.body))
        assert len(widgets) == 6 and output_reports == reports
        assert element_kinds == ["number_input", "json"] * 6 + ["json"] * 6
        assert finishes == [0] and statuses == [True, False] and len(current_sessions) == 1
        session = current_sessions[0]
        assert session.initialize.environment_info.streamlit_version == "1.66.1"
        sessions.add(session.initialize.session_id)
        run_ids.add(session.script_run_id)
        incoming = request.widget_states.widgets
        if phase == "load":
            assert not incoming
        else:
            assert len(incoming) == 6
            for index, (state, value) in enumerate(zip(incoming, values, strict=True)):
                assert state.id == ids[PERMISSIVE_NUMBERS[index][0]]
                field = "int_value" if index < 3 else "double_value"
                assert state.WhichOneof("value") == field and getattr(state, field) == value
    assert frame_count == 161 and len(sessions) == 1 and len(run_ids) == 7 and len(ids) == 6


@pytest.mark.parametrize("root", (PYTHON, RUST), ids=("python", "rust"))
def test_number_nonpositive_step_browser_evidence(root):
    folder = root / "number-permissive/ui/settled"
    check_number_ui(read(folder / "trace.json"), folder)


@pytest.mark.parametrize("root", (PYTHON, RUST), ids=("python", "rust"))
def test_same_call_number_screenshots_are_not_settled_evidence(root):
    folder = root / "number-permissive/ui"
    capture = read(folder / "trace.json")
    assert not capture["visual_review"]["accepted"]
    with pytest.raises(AssertionError):
        check_number_ui(capture, folder)


@pytest.mark.parametrize("mutation", ("dom-step", "raw-step", "input-type", "screenshot", "coverage", "missing-stage"))
def test_browser_number_evidence_rejects_damage(mutation):
    folder = PYTHON / "number-permissive/ui/settled"
    capture = read(folder / "trace.json")
    if mutation == "dom-step":
        capture["stages"][1]["dom"]["widgets"][1]["step"] = "0"
    elif mutation == "screenshot":
        capture["stages"][1]["screenshot_integrity"]["sha256"] = "wrong"
    elif mutation == "coverage":
        capture["stages"][1]["events"]["truncated"] = True
    elif mutation == "missing-stage":
        capture["stages"].pop(5)
    else:
        for event in capture["stages"][1]["events"]["events"]:
            method = event["method"]
            if mutation == "input-type" and method == "Network.webSocketFrameSent":
                message = BackMsg()
                message.ParseFromString(base64.b64decode(event["params"]["response"]["payloadData"]))
                message.rerun_script.widget_states.widgets[1].double_value = 5.0
            elif mutation == "raw-step" and method == "Network.webSocketFrameReceived":
                message = ForwardMsg()
                message.ParseFromString(base64.b64decode(event["params"]["response"]["payloadData"]))
                if message.WhichOneof("type") != "delta" or message.delta.new_element.WhichOneof("type") != "number_input":
                    continue
                if message.delta.new_element.number_input.label != "Int negative step":
                    continue
                message.delta.new_element.number_input.step = 2
                capture["stages"][1]["dom"]["widgets"][2]["step"] = "2"
            else:
                continue
            event["params"]["response"]["payloadData"] = base64.b64encode(message.SerializeToString()).decode()
            break
    with pytest.raises(AssertionError):
        check_number_ui(capture, folder)


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


FORM_IDENTITY_PHASES = ("load", "edit", "form-a", "form-b", "form-edit", "root-return", "form-a-return")
FORM_IDENTITY_VALUES = ((4, "base", 4, None), (7, "EDIT", 9, None), (7, "EDIT", 4, False),
                        (7, "EDIT", 4, False), (8, "NEXT", 6, True), (8, "NEXT", 4, None), (8, "NEXT", 4, False))


def form_identity_runs(capture):
    runs, emitted = [], []
    for message in frames(capture):
        kind = message.WhichOneof("type")
        if isinstance(message, BackMsg):
            assert kind == "rerun_script"
            runs.append({"request": message.rerun_script, "sessions": [], "finishes": [], "entries": []})
        elif kind == "new_session":
            runs[-1]["sessions"].append(message.new_session)
        elif kind == "script_finished":
            runs[-1]["finishes"].append(message.script_finished)
        elif kind == "delta":
            delta_kind = message.delta.WhichOneof("type")
            if delta_kind == "add_block":
                block = message.delta.add_block
                assert block.WhichOneof("type") == "form"
                entry_kind, view = "add_block:form", block.form
                assert MessageToDict(block.width_config, preserving_proto_field_name=True) == {"use_stretch": True}
                assert MessageToDict(block.height_config, preserving_proto_field_name=True) == {"use_content": True}
            else:
                assert delta_kind == "new_element"
                element = message.delta.new_element
                entry_kind = element.WhichOneof("type")
                assert entry_kind in ("number_input", "text_input", "button", "json")
                view = getattr(element, entry_kind)
            entry = (entry_kind, MessageToDict(view, preserving_proto_field_name=True), list(message.metadata.delta_path))
            emitted.append(entry)
            runs[-1]["entries"].append((entry_kind, view, entry[2]))
    return runs, emitted


def check_form_identity(capture):
    assert capture["successful"] and "producer_error" not in capture
    assert capture["reference_version"] == "1.66.1" and len(capture["frames"]) == 70
    assert capture["cleanup"]["websocket_closed"] and capture["finishes"] == [0] * 7
    if capture["runtime"] == "python":
        assert capture["cleanup"]["server_stopped"]
    runs, emitted = form_identity_runs(capture)
    assert emitted == [(entry["kind"], entry["fields"], entry["delta_path"]) for entry in capture["elements"]]
    assert len(runs) == 7 and len(emitted) == 36
    keyed_ids, unkeyed_ids, sessions, run_ids = {}, {}, set(), set()
    for run, phase, values in zip(runs, FORM_IDENTITY_PHASES, FORM_IDENTITY_VALUES, strict=True):
        request = run["request"]
        assert request.query_string == "probe=form-identity&phase=" + phase and not request.is_history_navigation
        assert run["finishes"] == [0] and len(run["sessions"]) == 1
        session = run["sessions"][0]
        assert session.initialize.environment_info.streamlit_version == "1.66.1"
        sessions.add(session.initialize.session_id)
        run_ids.add(session.script_run_id)
        form_id = "alpha" if phase in ("form-a", "form-a-return") else "beta" if phase.startswith("form-") else ""
        entries = list(run["entries"])
        if form_id:
            kind, form, path = entries.pop(0)
            assert kind == "add_block:form" and path == [0, 0]
            assert (form.form_id, form.clear_on_submit, form.border, form.enter_to_submit) == (form_id, False, True, True)
        assert [entry[0] for entry in entries] == ["number_input", "text_input", "number_input"] + (["button"] if form_id else []) + ["json"]
        for index, (_, widget, path) in enumerate(entries[:-1]):
            assert path == ([0, 0, index] if form_id else [0, index]) and widget.form_id == form_id
        assert entries[-1][2] == ([0, 1] if form_id else [0, 3])
        number, note, unkeyed = [entry[1] for entry in entries[:3]]
        assert number.label == "Number " + phase and note.label == "Note " + phase and unkeyed.label == "Unkeyed"
        assert number.help == note.help == phase and not unkeyed.help
        for widget in (number, unkeyed):
            assert (widget.default, widget.step, widget.data_type, widget.format) == (4, 1, 0, "%d")
            assert (widget.min, widget.max, widget.has_min, widget.has_max) == (-9007199254740991, 9007199254740991, False, False)
            assert not widget.set_value and not widget.HasField("value") and not widget.disabled
        assert note.default == "base" and note.max_chars == 5 and not note.set_value and not note.disabled
        for key, widget in (("number", number), ("note", note)):
            assert widget.id.endswith("-" + key)
            assert widget.id == keyed_ids.setdefault(key, widget.id)
        assert unkeyed.id == unkeyed_ids.setdefault(form_id, unkeyed.id)
        if form_id:
            button = entries[3][1]
            assert button.label == "Apply" and button.is_form_submitter and button.type == "secondary" and not button.disabled
            assert button.id.endswith("-apply") and button.id == keyed_ids.setdefault("apply", button.id)
        expected = {"phase": phase, "number": values[0], "note": values[1], "unkeyed": values[2],
                    "submitted": values[3], "native": [values[0], values[1]]}
        assert json.loads(entries[-1][1].body) == expected
        incoming = request.widget_states.widgets
        if phase in ("edit", "form-edit"):
            assert len(incoming) == (3 if phase == "edit" else 4)
            assert [(widget.id, widget.WhichOneof("value")) for widget in incoming[:3]] == [
                (number.id, "int_value"), (note.id, "string_value"), (unkeyed.id, "int_value")]
            assert (incoming[0].int_value, incoming[1].string_value, incoming[2].int_value) == values[:3]
            if phase == "form-edit":
                assert incoming[3].id == keyed_ids["apply"] and incoming[3].WhichOneof("value") == "trigger_value" and incoming[3].trigger_value
        else:
            assert not incoming
    assert len(keyed_ids) == 3 and len(set(unkeyed_ids.values())) == 3 and len(sessions) == 1 and len(run_ids) == 7


@pytest.mark.parametrize("root", (PYTHON, RUST), ids=("python", "rust"))
def test_keyed_widgets_keep_state_across_form_context(root):
    check_form_identity(read(root / "form-identity/trace.json"))


def test_pre_fix_form_migration_remains_a_known_mismatch():
    capture = read(RUST / "form-identity/before/trace.json")
    reports, errors = [], []
    assert len(capture["frames"]) == 65 and len(capture["elements"]) == 31
    for message in frames(capture):
        if message.WhichOneof("type") != "delta" or message.delta.WhichOneof("type") != "new_element":
            continue
        element = message.delta.new_element
        if element.WhichOneof("type") == "json":
            reports.append(json.loads(element.json.body))
        elif element.WhichOneof("type") == "markdown":
            errors.append(element.markdown.body)
    assert reports[2] == {"phase": "form-a", "number": 4, "note": "base", "unkeyed": 4,
                          "submitted": False, "native": [4, "base"]}
    assert errors == ["Widget params error: invalid widget value: button, chat input, menu button and uploader state cannot be preseeded"]
    with pytest.raises(AssertionError):
        check_form_identity(capture)


@pytest.mark.parametrize("mutation", ("keyed-id", "form-id", "state", "unkeyed-revival", "submit-id"))
def test_form_identity_gate_rejects_coherent_wrong_wire(mutation):
    capture = read(PYTHON / "form-identity/trace.json")
    run = -1
    for frame in capture["frames"]:
        if frame["direction"] == "client->server":
            run += 1
            continue
        if run != (3 if mutation == "submit-id" else 2):
            continue
        message = ForwardMsg()
        message.ParseFromString(base64.b64decode(frame["base64"]))
        if message.WhichOneof("type") != "delta" or message.delta.WhichOneof("type") != "new_element":
            continue
        element = message.delta.new_element
        kind = element.WhichOneof("type")
        if kind == "number_input" and element.number_input.id.endswith("-number") and mutation in ("keyed-id", "form-id"):
            if mutation == "keyed-id":
                element.number_input.id = element.number_input.id.replace("$$ID-", "$$ID-changed-")
            else:
                element.number_input.form_id = "beta"
        elif kind == "button" and mutation == "submit-id":
            element.button.id = element.button.id.replace("$$ID-", "$$ID-changed-")
        elif kind == "json" and mutation in ("state", "unkeyed-revival"):
            report = json.loads(element.json.body)
            if mutation == "state":
                report["number"] = report["native"][0] = 4
                report["note"] = report["native"][1] = "base"
            else:
                report["unkeyed"] = 9
            element.json.body = json.dumps(report)
        else:
            continue
        raw = message.SerializeToString()
        frame.update(base64=base64.b64encode(raw).decode(), bytes=len(raw), message=MessageToDict(message, preserving_proto_field_name=True))
    _, emitted = form_identity_runs(capture)
    capture["elements"] = [{"kind": kind, "fields": fields, "delta_path": path} for kind, fields, path in emitted]
    with pytest.raises(AssertionError):
        check_form_identity(capture)
