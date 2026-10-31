"""Frozen temporal/slider creation-parameter evidence (python + rust)."""
import base64
import json
from pathlib import Path

import pytest

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


IDENTITY_PHASES = ("load", "edit", "policy", "step", "edit-step", "format", "edit-format", "defaults", "bounds", "restore", "observe")
IDENTITY_VALUES = (
    ("12:30", "2024-03-15T12:30", "2024-03-15"),
    ("13:45", "2024-06-01T13:45", "2024-06-01"),
    ("13:45", "2024-06-01T13:45", "2024-06-01"),
    ("12:30", "2024-03-15T12:30", "2024-06-01"),
    ("14:00", "2024-06-01T14:00", "2024-06-01"),
    ("14:00", "2024-03-15T12:30", "2024-03-15"),
    ("15:00", "2024-07-04T15:00", "2024-07-04"),
    ("15:00", "2024-07-04T15:00", "2024-07-04"),
    ("15:00", "2024-07-04T15:00", "2024-07-04"),
    ("12:30", "2024-03-15T12:30", "2024-03-15"),
    ("12:30", "2024-03-15T12:30", "2024-03-15"),
)


def identity_runs(capture):
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
            assert message.delta.WhichOneof("type") == "new_element"
            element = message.delta.new_element
            entry_kind = element.WhichOneof("type")
            assert entry_kind in ("time_input", "date_time_input", "date_input", "json")
            view = getattr(element, entry_kind)
            fields = MessageToDict(view, preserving_proto_field_name=True)
            emitted.append((entry_kind, fields, list(message.metadata.delta_path)))
            runs[-1]["entries"].append((entry_kind, view, element, list(message.metadata.delta_path)))
    return runs, emitted


def check_keyed_temporal_identity(capture):
    assert capture["reference_version"] == "1.66.1" and capture["successful"] and "producer_error" not in capture
    assert len(capture["frames"]) == 98 and capture["finishes"] == [0] * 11
    assert capture["cleanup"]["websocket_closed"]
    if capture["runtime"] == "python":
        assert capture["cleanup"]["server_stopped"]
    runs, emitted = identity_runs(capture)
    assert emitted == [(entry["kind"], entry["fields"], entry["delta_path"]) for entry in capture["elements"]]
    assert len(runs) == 11 and len(emitted) == 44
    groups = ((0, 0, 0, 1, 1, 1, 1, 1, 1, 0, 0), (0, 0, 0, 1, 1, 2, 2, 2, 2, 0, 0), (0, 0, 0, 0, 0, 1, 1, 1, 1, 0, 0))
    ids, sessions, run_ids = ({}, {}, {}), set(), set()
    for index, (run, phase, values) in enumerate(zip(runs, IDENTITY_PHASES, IDENTITY_VALUES, strict=True)):
        request = run["request"]
        assert request.query_string == "probe=identity&phase=" + phase and not request.is_history_navigation
        assert len(run["sessions"]) == 1 and run["finishes"] == [0]
        session = run["sessions"][0]
        assert session.initialize.environment_info.streamlit_version == "1.66.1"
        sessions.add(session.initialize.session_id)
        run_ids.add(session.script_run_id)
        assert [entry[0] for entry in run["entries"]] == ["time_input", "date_time_input", "date_input", "json"]
        for position, (_, _, _, path) in enumerate(run["entries"]):
            assert path == [0, position]
        clock, moment, date = [entry[1] for entry in run["entries"][:3]]
        for position, (key, label) in enumerate((("clock", "Clock"), ("moment", "Moment"), ("date", "Date"))):
            _, widget, element, _ = run["entries"][position]
            assert widget.id.endswith("-" + key) and widget.id == ids[position].setdefault(groups[position][index], widget.id)
            assert widget.label == label and widget.help == phase and not widget.form_id
            assert widget.disabled == (phase == "policy") and widget.label_visibility.value == (1 if phase == "policy" else 0)
            assert MessageToDict(element.width_config, preserving_proto_field_name=True) == ({"pixel_width": 360} if phase == "policy" else {"use_stretch": True})
            assert not widget.set_value and not element.HasField("has_one_shot_effect")
        step = 1800 if 3 <= index <= 8 else 900
        display_format = "DD/MM/YYYY" if 5 <= index <= 8 else "YYYY/MM/DD"
        default_date = "2024-04-20" if phase in ("defaults", "bounds") else "2024-03-15"
        default_time = "10:00" if phase in ("defaults", "bounds") else "12:30"
        assert clock.default == default_time and clock.HasField("default") and not clock.HasField("value")
        assert clock.step == moment.step == step and clock.format == ("12h" if 5 <= index <= 8 else "24h")
        assert list(moment.default) == [default_date + "T" + default_time] and list(date.default) == [default_date]
        assert not moment.value and not date.value and not date.is_range
        assert moment.format == date.format == display_format
        low, high = (("2024-01-01", "2024-12-31") if phase == "bounds" else ("2014" + default_date[4:], "2034" + default_date[4:]))
        assert (date.min, date.max, moment.min, moment.max) == (low, high, low + "T00:00", high + "T23:59")
        assert json.loads(run["entries"][3][1].body) == {"phase": phase, "values": list(values), "native": list(values)}
        incoming = request.widget_states.widgets
        if phase in ("edit", "edit-step", "edit-format"):
            assert len(incoming) == 3
            assert [(widget.id, widget.WhichOneof("value")) for widget in incoming] == [
                (clock.id, "string_value"), (moment.id, "string_array_value"), (date.id, "string_array_value")]
            assert incoming[0].string_value == values[0]
            assert list(incoming[1].string_array_value.data) == [values[1]] and list(incoming[2].string_array_value.data) == [values[2]]
        else:
            assert not incoming
    assert [len(set(group.values())) for group in ids] == [2, 3, 2]
    assert len(sessions) == 1 and len(run_ids) == 11


@pytest.mark.parametrize("root", (PYTHON, RUST), ids=("python", "rust"))
def test_keyed_temporal_constraints_and_retention(root):
    check_keyed_temporal_identity(read(root / "keyed-identity/trace.json"))


def test_pre_fix_temporal_identity_remains_a_known_mismatch():
    capture = read(RUST / "keyed-identity/before/trace.json")
    runs, _ = identity_runs(capture)
    assert json.loads(runs[3]["entries"][3][1].body)["values"][:2] == ["13:45", "2024-06-01T13:45"]
    assert [len({run["entries"][position][1].id for run in runs}) for position in range(3)] == [1, 1, 1]
    with pytest.raises(AssertionError):
        check_keyed_temporal_identity(capture)


@pytest.mark.parametrize("mutation", ("clock-step-id", "moment-format-id", "date-format-id", "retained-value", "policy-width"))
def test_temporal_identity_gate_rejects_coherent_wrong_wire(mutation):
    capture = read(PYTHON / "keyed-identity/trace.json")
    source_runs, _ = identity_runs(capture)
    run = -1
    target = 3 if mutation == "clock-step-id" else 5 if mutation in ("moment-format-id", "date-format-id") else 7 if mutation == "retained-value" else 2
    for frame in capture["frames"]:
        if frame["direction"] == "client->server":
            run += 1
            continue
        if run != target:
            continue
        message = ForwardMsg()
        message.ParseFromString(base64.b64decode(frame["base64"]))
        if message.WhichOneof("type") != "delta" or message.delta.WhichOneof("type") != "new_element":
            continue
        element = message.delta.new_element
        kind = element.WhichOneof("type")
        if mutation in ("clock-step-id", "moment-format-id", "date-format-id"):
            position = {"clock-step-id": 0, "moment-format-id": 1, "date-format-id": 2}[mutation]
            if kind != ("time_input", "date_time_input", "date_input")[position]:
                continue
            getattr(element, kind).id = source_runs[target - 1]["entries"][position][1].id
        elif mutation == "retained-value" and kind == "json":
            report = json.loads(element.json.body)
            report["values"][0] = report["native"][0] = "10:00"
            element.json.body = json.dumps(report)
        elif mutation == "policy-width" and kind == "time_input":
            element.width_config.pixel_width = 361
        else:
            continue
        raw = message.SerializeToString()
        frame.update(base64=base64.b64encode(raw).decode(), bytes=len(raw), message=MessageToDict(message, preserving_proto_field_name=True))
    _, emitted = identity_runs(capture)
    capture["elements"] = [{"kind": kind, "fields": fields, "delta_path": path} for kind, fields, path in emitted]
    with pytest.raises(AssertionError):
        check_keyed_temporal_identity(capture)


def test_sdk_unkeyed_temporal_display_and_bounds_identity():
    """Live pinned SDK AppTest oracle; not a native WS or browser capture."""
    import datetime
    import importlib.metadata

    from streamlit.testing.v1 import AppTest

    assert importlib.metadata.version("streamlit") == "1.66.1"
    app = AppTest.from_string('''
import datetime
import streamlit as st

phase = st.session_state.get("phase", "load")
width = {"width": 360} if phase == "width" else {}
clock = st.time_input("Clock", datetime.time(12, 30), format="12h" if phase == "format" else "24h", **width)
moment = st.datetime_input("Moment", datetime.datetime(2024, 3, 15, 12, 30),
    min_value=datetime.datetime(2024, 1, 1) if phase == "bounds" else None,
    max_value=datetime.datetime(2024, 12, 31, 23, 59) if phase == "bounds" else None, **width)
date = st.date_input("Date", datetime.date(2024, 3, 15), **width)
st.json([clock.isoformat(), moment.isoformat(), date.isoformat()])
''')
    phases = ("load", "edit", "format", "width", "restore", "edit-bounds", "bounds", "observe")
    groups = ((0, 0, 0, 1, 0, 0, 0, 0), (0, 0, 0, 1, 0, 0, 2, 0), (0, 0, 0, 1, 0, 0, 0, 0))
    expected = (
        ["12:30:00", "2024-03-15T12:30:00", "2024-03-15"],
        ["13:45:00", "2024-06-01T13:45:00", "2024-06-01"],
        ["13:45:00", "2024-06-01T13:45:00", "2024-06-01"],
        ["12:30:00", "2024-03-15T12:30:00", "2024-03-15"],
        ["12:30:00", "2024-03-15T12:30:00", "2024-03-15"],
        ["13:45:00", "2024-06-01T13:45:00", "2024-06-01"],
        ["13:45:00", "2024-03-15T12:30:00", "2024-06-01"],
        ["13:45:00", "2024-03-15T12:30:00", "2024-06-01"],
    )
    ids = [[], [], []]
    for index, phase in enumerate(phases):
        app.session_state["phase"] = phase
        if phase in ("edit", "edit-bounds"):
            app.time_input[0].set_value(datetime.time(13, 45))
            app.get("date_time_input")[0].set_value(datetime.datetime(2024, 6, 1, 13, 45))
            app.date_input[0].set_value(datetime.date(2024, 6, 1))
        app.run()
        assert not app.exception
        assert json.loads(app.json[0].value) == expected[index], phase
        widgets = (app.time_input[0], app.get("date_time_input")[0], app.date_input[0])
        for position, widget in enumerate(widgets):
            for earlier in range(index):
                assert (widget.id == ids[position][earlier]) == (groups[position][index] == groups[position][earlier]), (phase, position, earlier)
            ids[position].append(widget.id)
    assert [len(set(widget_ids)) for widget_ids in ids] == [2, 3, 2]


UNKEYED_PHASES = ("load", "edit", "format", "width", "restore", "edit-bounds", "bounds", "observe")
UNKEYED_VALUES = (
    ("12:30", "2024-03-15T12:30", "2024-03-15"),
    ("13:45", "2024-06-01T13:45", "2024-06-01"),
    ("13:45", "2024-06-01T13:45", "2024-06-01"),
    ("12:30", "2024-03-15T12:30", "2024-03-15"),
    ("12:30", "2024-03-15T12:30", "2024-03-15"),
    ("13:45", "2024-06-01T13:45", "2024-06-01"),
    ("13:45", "2024-03-15T12:30", "2024-06-01"),
    ("13:45", "2024-03-15T12:30", "2024-06-01"),
)


def check_unkeyed_temporal_wire(capture):
    assert capture["reference_version"] == "1.66.1" and capture["successful"] and "producer_error" not in capture
    assert len(capture["frames"]) == 71 and capture["finishes"] == [0] * 8
    assert capture["cleanup"]["websocket_closed"]
    assert capture["cleanup"]["server_stopped" if capture["runtime"] == "python" else "caller_server_stopped"]
    kinds = []
    for message in frames(capture):
        kind = message.WhichOneof("type")
        kinds.append((kind, message.session_status_changed.script_is_running) if kind == "session_status_changed" else kind)
    expected_kinds = []
    for index in range(8):
        expected_kinds += ["rerun_script"] + ([("session_status_changed", False)] if index else [])
        expected_kinds += ["new_session", ("session_status_changed", True)] + ["delta"] * 4 + ["script_finished"]
    assert kinds == expected_kinds
    runs, emitted = identity_runs(capture)
    assert len(runs) == 8 and len(emitted) == 32
    assert emitted == [(entry["kind"], entry["fields"], entry["delta_path"]) for entry in capture["elements"]]
    groups = ((0, 0, 0, 1, 0, 0, 0, 0), (0, 0, 0, 1, 0, 0, 2, 0), (0, 0, 0, 1, 0, 0, 0, 0))
    ids, sessions, run_ids = ([], [], []), set(), set()
    for index, (run, phase, values) in enumerate(zip(runs, UNKEYED_PHASES, UNKEYED_VALUES, strict=True)):
        request = run["request"]
        assert request.query_string == "probe=unkeyed&phase=" + phase and not request.is_history_navigation
        assert len(run["sessions"]) == 1 and run["finishes"] == [0]
        session = run["sessions"][0]
        assert session.initialize.environment_info.streamlit_version == "1.66.1"
        sessions.add(session.initialize.session_id)
        run_ids.add(session.script_run_id)
        assert [entry[0] for entry in run["entries"]] == ["time_input", "date_time_input", "date_input", "json"]
        assert [entry[3] for entry in run["entries"]] == [[0, position] for position in range(4)]
        for position, label in enumerate(("Clock", "Moment", "Date")):
            _, widget, element, _ = run["entries"][position]
            assert widget.id and widget.label == label and not widget.help and not widget.form_id
            assert not widget.disabled and widget.label_visibility.value == 0 and not widget.ignore_rerun
            assert not widget.set_value and not element.HasField("has_one_shot_effect")
            assert MessageToDict(element.width_config, preserving_proto_field_name=True) == ({"pixel_width": 360} if phase == "width" else {"use_stretch": True})
            for earlier in range(index):
                assert (widget.id == ids[position][earlier]) == (groups[position][index] == groups[position][earlier]), (phase, position, earlier)
            ids[position].append(widget.id)
        clock, moment, date = [entry[1] for entry in run["entries"][:3]]
        assert len({clock.id, moment.id, date.id}) == 3
        assert clock.HasField("default") and clock.default == "12:30" and not clock.HasField("value")
        assert clock.format == ("12h" if phase == "format" else "24h") and clock.step == moment.step == 900
        assert list(moment.default) == ["2024-03-15T12:30"] and list(date.default) == ["2024-03-15"]
        assert not moment.value and not date.value and not date.is_range and not moment.is_range
        assert moment.format == date.format == "YYYY/MM/DD"
        assert (date.min, date.max) == ("2014-03-15", "2034-03-15")
        assert (moment.min, moment.max) == (("2024-01-01T00:00", "2024-12-31T23:59") if phase == "bounds" else ("2014-03-15T00:00", "2034-03-15T23:59"))
        assert json.loads(run["entries"][3][1].body) == {"phase": phase, "values": list(values), "native": []}
        incoming = request.widget_states.widgets
        if phase in ("edit", "edit-bounds"):
            assert len(incoming) == 3
            assert [(widget.id, widget.WhichOneof("value")) for widget in incoming] == [
                (ids[0][index - 1], "string_value"), (ids[1][index - 1], "string_array_value"), (ids[2][index - 1], "string_array_value")]
            assert incoming[0].string_value == values[0]
            assert list(incoming[1].string_array_value.data) == [values[1]] and list(incoming[2].string_array_value.data) == [values[2]]
        else:
            assert not incoming
    assert len(sessions) == 1 and len(run_ids) == 8
    assert [len(set(widget_ids)) for widget_ids in ids] == [2, 3, 2]


@pytest.mark.parametrize("root", (PYTHON, RUST), ids=("python", "rust"))
def test_unkeyed_temporal_native_sequence(root):
    check_unkeyed_temporal_wire(read(root / "unkeyed-identity/trace.json"))


def test_unkeyed_temporal_elements_match_field_for_field():
    left = read(PYTHON / "unkeyed-identity/trace.json")
    right = read(RUST / "unkeyed-identity/trace.json")
    assert left["producer_sources_sha256"] == right["producer_sources_sha256"]
    for capture in (left, right):
        check_unkeyed_temporal_wire(capture)
    sdk_runs, _ = identity_runs(left)
    rust_runs, _ = identity_runs(right)
    for sdk, rust in zip(sdk_runs, rust_runs, strict=True):
        for sdk_entry, rust_entry in zip(sdk["entries"], rust["entries"], strict=True):
            elements = []
            for kind, _, element, _ in (sdk_entry, rust_entry):
                fields = MessageToDict(element, preserving_proto_field_name=True)
                if kind == "json":
                    fields[kind]["body"] = json.loads(fields[kind]["body"])
                else:
                    fields[kind].pop("id")
                elements.append(fields)
            assert elements[0] == elements[1]


@pytest.mark.parametrize("mutation", ("time-format-id", "date-width-id", "datetime-bounds-id", "retained-value", "stale-input-id", "width"))
def test_unkeyed_temporal_gate_rejects_wrong_wire(mutation):
    capture = read(PYTHON / "unkeyed-identity/trace.json")
    source_runs, _ = identity_runs(capture)
    target = {"time-format-id": 2, "date-width-id": 3, "datetime-bounds-id": 6, "retained-value": 2, "stale-input-id": 5, "width": 3}[mutation]
    run = -1
    for frame in capture["frames"]:
        client = frame["direction"] == "client->server"
        if client:
            run += 1
        if run != target:
            continue
        message = BackMsg() if client else ForwardMsg()
        message.ParseFromString(base64.b64decode(frame["base64"]))
        if mutation == "stale-input-id" and client:
            message.rerun_script.widget_states.widgets[0].id = source_runs[3]["entries"][0][1].id
        elif not client and message.WhichOneof("type") == "delta" and message.delta.WhichOneof("type") == "new_element":
            element = message.delta.new_element
            kind = element.WhichOneof("type")
            position = {"time-format-id": 0, "date-width-id": 2, "datetime-bounds-id": 1}.get(mutation)
            if position is not None and kind == ("time_input", "date_time_input", "date_input")[position]:
                getattr(element, kind).id = "wrong-format-identity" if mutation == "time-format-id" else source_runs[0]["entries"][position][1].id
            elif mutation == "retained-value" and kind == "json":
                report = json.loads(element.json.body)
                report["values"][0] = "12:30"
                element.json.body = json.dumps(report)
            elif mutation == "width" and kind == "date_input":
                element.width_config.pixel_width = 361
            else:
                continue
        else:
            continue
        raw = message.SerializeToString()
        frame.update(base64=base64.b64encode(raw).decode(), bytes=len(raw), message=MessageToDict(message, preserving_proto_field_name=True))
    _, emitted = identity_runs(capture)
    capture["elements"] = [{"kind": kind, "fields": fields, "delta_path": path} for kind, fields, path in emitted]
    with pytest.raises(AssertionError):
        check_unkeyed_temporal_wire(capture)
