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

COLOR_DEFAULTS = (
    ("short-upper", "#ABC"), ("short-lower", "#abc"), ("long-mixed", "#aBcDeF"), ("black", "#000000"),
    ("missing-hash", "ABCDEF"), ("short-unprefixed", "abc"), ("alpha", "#12345678"), ("bad-digit", "#12G"),
    ("too-short", "#12"), ("leading-space", " #123"), ("trailing-space", "#123 "), ("lf", "#ABC\n"),
    ("crlf", "#ABC\r\n"), ("double-lf", "#ABC\n\n"), ("empty", ""), ("plain-default", None),
)
COLOR_STEPS = (("load", None), ("short", "abc"), ("short-hash", "#AbC"), ("long", "00ffAA"), ("invalid", "#12"), ("empty", ""),
               ("lower", "#abcdef"), ("invalid-after-edit", "oops"), ("default-change", None), ("changed-invalid", "!"), ("width", None),
               ("assign", None), ("native-invalid", None), ("observe", None), ("recover", "123abc"))
COLOR_VALUES = ("#123456", "#abc", "#AbC", "#00ffAA", "#123456", "#123456", "#abcdef", "#123456", "#123456", "#FED", "#FED", "#135", "nothex", "nothex", "#123abc")
COLOR_EVENTS = ("#abc", "#AbC", "#00ffAA", "#123456", "#abcdef", "#123456", "#FED", "#123abc")
COLOR_EVENT_COUNTS = (0, 1, 2, 3, 4, 4, 5, 6, 6, 7, 7, 7, 7, 7, 8)


def color_runs(capture, element_kinds=("color_picker", "json")):
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
            assert entry_kind in element_kinds
            view = getattr(element, entry_kind)
            emitted.append((entry_kind, MessageToDict(view, preserving_proto_field_name=True), list(message.metadata.delta_path)))
            runs[-1]["entries"].append((entry_kind, view, element))
    assert emitted == [(entry["kind"], entry["fields"], entry["delta_path"]) for entry in capture["elements"]]
    return runs


def check_color_capture(capture):
    assert capture["successful"] and "producer_error" not in capture and capture["reference_version"] == "1.66.1"
    if capture["runtime"] == "rust":
        assert capture.get("color_flow_match") is True and capture["semantic_match"] is False
    assert capture["cleanup"]["websocket_closed"] and capture["finishes"] == [0] * 16
    assert capture["cleanup"]["server_stopped" if capture["runtime"] == "python" else "caller_server_stopped"]
    assert len(capture["frames"]) == 122 and len(capture["elements"]) == 43
    kinds = []
    for message in frames(capture):
        kind = message.WhichOneof("type")
        kinds.append((kind, message.session_status_changed.script_is_running) if kind == "session_status_changed" else kind)
    expected_kinds = []
    for index in range(16):
        expected_kinds += ["rerun_script"] + ([("session_status_changed", False)] if index else [])
        expected_kinds += ["new_session", ("session_status_changed", True)] + ["delta"] * (13 if index == 0 else 2) + ["script_finished"]
    assert kinds == expected_kinds
    runs = color_runs(capture)
    assert len(runs) == 16
    assert runs[0]["request"].query_string == "probe=color&phase=defaults" and not runs[0]["request"].widget_states.widgets
    accepted = {"short-upper", "short-lower", "long-mixed", "black", "lf", "plain-default"}
    defaults = json.loads(runs[0]["entries"][-1][1].body)
    assert len(defaults) == 22
    widgets = []
    for report, (name, value) in zip(defaults[:16], COLOR_DEFAULTS, strict=True):
        if name in accepted:
            expected = value if value is not None else "#000000"
            assert report == {"case": name, "accepted": True, "value": expected}
            widgets.append((name, expected, None))
        else:
            error_type, error = "StreamlitAPIException", f"'{value}' is not a valid hex code for colors. Valid ones are like '#00FFAA' or '#000'."
            if capture["runtime"] == "rust":
                error_type, error = "InvalidValue", "invalid widget value: color_picker expects a #RGB or #RRGGBB value"
            assert report == {"case": name, "accepted": False, "error_type": error_type, "error": error}
    for report, width in zip(defaults[16:], (-5, 0, 1, 39, 40, 41), strict=True):
        name = "width-" + str(width)
        assert report == {"case": name, "accepted": True, "value": "#123456"}
        widgets.append((name, "#123456", max(40, width)))
    assert [entry[0] for entry in runs[0]["entries"]] == ["color_picker"] * 12 + ["json"]
    sessions, run_ids, creation_ids = set(), set(), set()
    for run in runs:
        assert len(run["sessions"]) == 1 and run["finishes"] == [0]
        session = run["sessions"][0]
        assert session.initialize.environment_info.streamlit_version == "1.66.1"
        sessions.add(session.initialize.session_id)
        run_ids.add(session.script_run_id)
        assert not run["request"].is_history_navigation
    for (name, default, width), (_, widget, element) in zip(widgets, runs[0]["entries"][:-1], strict=True):
        assert widget.label == name and widget.id.endswith("-" + name) and widget.default == default
        creation_ids.add(widget.id)
        assert not widget.value and not widget.set_value and not element.HasField("has_one_shot_effect")
        assert MessageToDict(element.width_config, preserving_proto_field_name=True) == ({"use_content": True} if width is None else {"pixel_width": width})
    accent_id = runs[1]["entries"][0][1].id
    assert len(creation_ids) == 12 and accent_id not in creation_ids
    for index, (run, (phase, submitted), value, count) in enumerate(zip(runs[1:], COLOR_STEPS, COLOR_VALUES, COLOR_EVENT_COUNTS, strict=True)):
        request = run["request"]
        assert request.query_string == "probe=color&phase=" + phase
        assert [entry[0] for entry in run["entries"]] == ["color_picker", "json"]
        widget, element = run["entries"][0][1:]
        assert widget.id == accent_id and widget.label == "Accent"
        assert widget.default == ("#FED" if index >= 8 else "#123456")
        sync = phase in ("assign", "native-invalid")
        assert widget.set_value == sync and widget.value == (value if sync else "")
        assert element.HasField("has_one_shot_effect") == sync and (not sync or element.has_one_shot_effect)
        assert MessageToDict(element.width_config, preserving_proto_field_name=True) == ({"pixel_width": 40} if phase == "width" else {"use_content": True})
        assert json.loads(run["entries"][1][1].body) == {"phase": phase, "accepted": True, "value": value, "native": value, "events": list(COLOR_EVENTS[:count])}
        incoming = request.widget_states.widgets
        if submitted is None:
            assert not incoming
        else:
            assert len(incoming) == 1 and incoming[0].id == accent_id and incoming[0].WhichOneof("value") == "string_value" and incoming[0].string_value == submitted
    assert len(sessions) == 1 and len(run_ids) == 16
    emitted_index = 0
    for run in runs:
        for index, (kind, widget, element) in enumerate(run["entries"]):
            assert capture["elements"][emitted_index]["delta_path"] == [0, index]
            emitted_index += 1
            if kind == "color_picker":
                assert not widget.disabled and not widget.help and not widget.form_id and not widget.ignore_rerun and widget.label_visibility.value == 0


@pytest.mark.parametrize("root", (PYTHON, RUST), ids=("python", "rust"))
def test_color_defaults_inputs_callbacks_and_code_state(root):
    check_color_capture(read(root / "color/trace.json"))


def test_color_full_widget_elements_match_reference():
    captures = [read(root / "color/trace.json") for root in (PYTHON, RUST)]
    assert captures[0]["producer_sources_sha256"] == captures[1]["producer_sources_sha256"]
    normalized = []
    for capture in captures:
        check_color_capture(capture)
        widgets = []
        for run in color_runs(capture):
            for kind, _, element in run["entries"]:
                if kind == "color_picker":
                    fields = MessageToDict(element, preserving_proto_field_name=True)
                    fields[kind].pop("id")
                    widgets.append(fields)
        normalized.append(widgets)
    assert normalized[0] == normalized[1]


def test_color_before_keeps_wrong_callback_and_default_admission():
    capture = read(RUST / "color/before/trace.json")
    assert capture["successful"] and len(capture["frames"]) == 106 and len(capture["elements"]) == 27 and capture["finishes"] == [0] * 16
    runs = color_runs(capture)
    defaults = json.loads(runs[0]["entries"][-1][1].body)
    assert not defaults[0]["accepted"] and defaults[4]["accepted"] and defaults[4]["value"] == "ABCDEF"
    report = json.loads(runs[2]["entries"][-1][1].body)
    assert report["phase"] == "short" and not report["accepted"] and report["native"] == "abc" and report["events"] == ["abc"]
    with pytest.raises(AssertionError):
        check_color_capture(capture)


@pytest.mark.parametrize("mutation", ("short-normalization", "invalid-fallback", "callback", "width", "code-sync"))
def test_color_gate_rejects_wrong_wire(mutation):
    capture = read(PYTHON / "color/trace.json")
    run = -1
    target = {"short-normalization": 2, "invalid-fallback": 5, "callback": 2, "width": 0, "code-sync": 12}[mutation]
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
        if kind == "json" and mutation in ("short-normalization", "invalid-fallback", "callback"):
            report = json.loads(element.json.body)
            if mutation == "callback":
                report["events"] = []
            else:
                report["value"] = report["native"] = "abc" if mutation == "short-normalization" else "#00ffAA"
                report["events"][-1] = report["value"]
            element.json.body = json.dumps(report)
        elif kind == "color_picker" and mutation == "width" and element.color_picker.label == "width-39":
            element.width_config.pixel_width = 39
        elif kind == "color_picker" and mutation == "code-sync":
            element.color_picker.set_value = False
            element.color_picker.value = ""
            element.ClearField("has_one_shot_effect")
        else:
            continue
        raw = message.SerializeToString()
        frame.update(base64=base64.b64encode(raw).decode(), bytes=len(raw), message=MessageToDict(message, preserving_proto_field_name=True))
    color_runs_raw = []
    # Rebuild only the decoded summary, keeping the mutated original protobufs.
    for message in frames(capture):
        if isinstance(message, ForwardMsg) and message.WhichOneof("type") == "delta":
            element = message.delta.new_element
            kind = element.WhichOneof("type")
            color_runs_raw.append({"kind": kind, "fields": MessageToDict(getattr(element, kind), preserving_proto_field_name=True), "delta_path": list(message.metadata.delta_path)})
    capture["elements"] = color_runs_raw
    with pytest.raises(AssertionError):
        check_color_capture(capture)


def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


COLOR_UI_STAGES = ("load", "short-draft", "short-commit", "invalid-draft", "invalid-close", "recover-draft", "recover-commit", "restore-draft", "restore-commit")
COLOR_UI_VALUES = ("#123456", "#123456", "#aabbcc", "#aabbcc", "#aabbcc", "#aabbcc", "#00ffaa", "#00ffaa", "#123456")
COLOR_UI_COUNTS = (0, 0, 1, 1, 1, 1, 2, 2, 3)
COLOR_UI_DRAFTS = (None, "abc", None, "zzzzzz", None, "00ffAA", None, "123456", None)
COLOR_UI_RGB = ((18, 52, 86), (170, 187, 204), (170, 187, 204), (170, 187, 204), (170, 187, 204), (0, 255, 170), (0, 255, 170), (18, 52, 86), (18, 52, 86))
COLOR_UI_SCREEN_RGB = ((26, 51, 82), (174, 187, 203), (174, 187, 203), (174, 187, 203), (174, 187, 203), (116, 250, 177), (116, 250, 177), (26, 51, 82), (26, 51, 82))


def color_ui_messages(capture):
    events = capture["raw_browser_events"]
    assert len(events) == 36
    created = [event for event in events if event["method"] == "Network.webSocketCreated"]
    assert len(created) == 1
    port = 8624 if capture["runtime"] == "python" else 8599
    assert created[0]["params"]["url"] == f"ws://127.0.0.1:{port}/_stcore/stream"
    ws_id = created[0]["params"]["requestId"]
    output, sequence = [], 0
    for index, event in enumerate(events):
        assert event["sequence"] > sequence
        sequence = event["sequence"]
        assert event["source"]["tabId"] == int(capture["tab_id"])
        if event["method"] == "Network.webSocketCreated":
            continue
        assert event["method"] in ("Network.webSocketFrameSent", "Network.webSocketFrameReceived")
        assert event["params"]["requestId"] == ws_id and event["params"]["response"]["opcode"] == 2
        data = base64.b64decode(event["params"]["response"]["payloadData"], validate=True)
        message = BackMsg() if event["method"].endswith("Sent") else ForwardMsg()
        message.ParseFromString(data)
        output.append((index, message))
    assert len(output) == 35
    return output


def check_color_ui(capture, folder):
    import hashlib
    from PIL import Image

    assert capture["successful"] and capture["collection_complete"] and capture["semantic_match"]
    assert capture["reference_version"] == "1.66.1" and capture["runtime"] in ("python", "rust")
    assert capture["visual_review"]["all_stage_images_inspected"] and capture["visual_review"]["phase_alignment"]
    cleanup = capture["cleanup"]
    assert cleanup["tab_closed"] and cleanup["owned_servers_stopped"] and cleanup["network_disabled_before_tab_close"]
    assert cleanup["ports_without_listeners"] == [8599, 8624] and cleanup["websocket_close_event_observed"] is False
    assert [stage["stage"] for stage in capture["stages"]] == list(COLOR_UI_STAGES)
    messages = color_ui_messages(capture)
    events = ("#aabbcc", "#00ffaa", "#123456")
    sessions, run_ids, widget_ids, normalized = set(), set(), set(), []
    boundary = 0
    port = 8624 if capture["runtime"] == "python" else 8599
    for index, stage in enumerate(capture["stages"]):
        name, value, count, draft = COLOR_UI_STAGES[index], COLOR_UI_VALUES[index], COLOR_UI_COUNTS[index], COLOR_UI_DRAFTS[index]
        assert stage["action_and_capture_calls_separate"] and stage["events_complete"]
        assert stage["event_start"] == boundary
        expected_events = 8 if index == 0 else 7 if draft is None else 0
        assert stage["event_end"] - boundary == expected_events
        boundary = stage["event_end"]
        dom = stage["dom"]
        assert not dom["exceptions"] and dom["url"] == f"http://127.0.0.1:{port}/?probe=color&phase=load"
        assert dom["viewport"] == {"width": 1463, "height": 724, "dpr": 1.75}
        assert dom["color_buttons"] == [{"disabled": False, "expanded": "true" if draft is not None else "false"}]
        assert dom["inputs"] == ([] if draft is None else [{"type": "text", "value": draft, "placeholder": None, "label": None, "disabled": False}])
        rgb = COLOR_UI_RGB[index]
        assert dom["swatch"] == [{"style": None, "background": f"rgb({rgb[0]}, {rgb[1]}, {rgb[2]})"}]
        fields = {"phase": '"load"', "accepted": "true", "value": json.dumps(value), "native": json.dumps(value),
                  "events": "[" + "".join(f"{i}:{json.dumps(event)}" for i, event in enumerate(events[:count])) + "]"}
        order = ("phase", "accepted", "value", "native", "events") if capture["runtime"] == "python" else ("accepted", "value", "phase", "native", "events")
        assert len(dom["reports"]) == 1
        assert re.sub(r"\s+", "", dom["reports"][0]) == "{" + "".join(f'"{key}":{fields[key]}' for key in order) + "}"
        assert stage["screenshot"] == f"{index + 1:02}-{name}.jpg"
        path, integrity = folder / stage["screenshot"], stage["screenshot_integrity"]
        assert path.stat().st_size == integrity["bytes"] and hashlib.sha256(path.read_bytes()).hexdigest() == integrity["sha256"]
        image = Image.open(path)
        assert image.format == "JPEG" and integrity["format"] == "jpeg" and image.size == (1463, 724)
        assert (integrity["width"], integrity["height"]) == image.size
        assert image.convert("RGB").getpixel((400, 144)) == COLOR_UI_SCREEN_RGB[index]
        batch = [message for position, message in messages if stage["event_start"] <= position < stage["event_end"]]
        if draft is not None:
            assert not batch
            continue
        assert [message.WhichOneof("type") for message in batch] == ["rerun_script", "new_session", "session_status_changed", "delta", "delta", "script_finished", "session_status_changed"]
        assert batch[2].session_status_changed.script_is_running and not batch[6].session_status_changed.script_is_running and batch[5].script_finished == 0
        session = batch[1].new_session
        assert session.initialize.environment_info.streamlit_version == "1.66.1"
        sessions.add(session.initialize.session_id)
        run_ids.add(session.script_run_id)
        assert batch[3].delta.WhichOneof("type") == batch[4].delta.WhichOneof("type") == "new_element"
        element = batch[3].delta.new_element
        assert element.WhichOneof("type") == "color_picker"
        widget = element.color_picker
        widget_ids.add(widget.id)
        assert widget.label == "Accent" and widget.id.endswith("-accent") and widget.default == "#123456"
        assert not widget.value and not widget.set_value and not element.HasField("has_one_shot_effect")
        assert not widget.disabled and not widget.form_id and not widget.help and not widget.ignore_rerun and widget.label_visibility.value == 0
        assert MessageToDict(element.width_config, preserving_proto_field_name=True) == {"use_content": True}
        request = batch[0].rerun_script
        assert request.query_string == "probe=color&phase=load" and not request.is_history_navigation
        incoming = request.widget_states.widgets
        assert len(incoming) == (0 if index == 0 else 1)
        if incoming:
            assert incoming[0].id == widget.id and incoming[0].WhichOneof("value") == "string_value" and incoming[0].string_value == value
        report_element = batch[4].delta.new_element
        assert report_element.WhichOneof("type") == "json"
        report = json.loads(report_element.json.body)
        assert report == {"phase": "load", "accepted": True, "value": value, "native": value, "events": list(events[:count])}
        assert list(batch[3].metadata.delta_path) == [0, 0] and list(batch[4].metadata.delta_path) == [0, 1]
        normalized_widget = MessageToDict(element, preserving_proto_field_name=True)
        normalized_widget["color_picker"].pop("id")
        normalized_report = MessageToDict(report_element, preserving_proto_field_name=True)
        normalized_report["json"]["body"] = report
        normalized.append((normalized_widget, normalized_report))
    assert boundary == 36 and len(sessions) == 1 and len(run_ids) == 5 and len(widget_ids) == 1
    return normalized


@pytest.mark.parametrize("root", (PYTHON, RUST), ids=("python", "rust"))
def test_color_ui_popover_commit_rejection_and_restore(root):
    folder = root / "color/ui"
    check_color_ui(read(folder / "trace.json"), folder)


def test_color_ui_full_elements_match_reference():
    captures = [read(root / "color/ui/trace.json") for root in (PYTHON, RUST)]
    assert captures[0]["producer_sources_sha256"] == captures[1]["producer_sources_sha256"]
    assert check_color_ui(captures[0], PYTHON / "color/ui") == check_color_ui(captures[1], RUST / "color/ui")


@pytest.mark.parametrize("mutation", ("draft-send", "invalid-input", "callback", "swatch", "screenshot", "old-image"))
def test_color_ui_gate_rejects_wrong_wire_or_picture(mutation, tmp_path):
    import hashlib

    capture = read(PYTHON / "color/ui/trace.json")
    folder = PYTHON / "color/ui"
    if mutation == "draft-send":
        capture["stages"][1]["event_end"] = 15
        capture["stages"][2]["event_start"] = 15
    elif mutation == "swatch":
        capture["stages"][5]["dom"]["swatch"][0]["background"] = "rgb(18, 52, 86)"
    elif mutation == "screenshot":
        capture["stages"][6]["screenshot_integrity"]["sha256"] = "wrong"
    elif mutation == "old-image":
        for stage in capture["stages"]:
            (tmp_path / stage["screenshot"]).write_bytes((folder / stage["screenshot"]).read_bytes())
        old = (folder / capture["stages"][0]["screenshot"]).read_bytes()
        target = capture["stages"][1]
        (tmp_path / target["screenshot"]).write_bytes(old)
        target["screenshot_integrity"].update(sha256=hashlib.sha256(old).hexdigest(), bytes=len(old))
        folder = tmp_path
    else:
        stage = capture["stages"][4]
        for event in capture["raw_browser_events"][stage["event_start"]:stage["event_end"]]:
            method = event["method"]
            message = BackMsg() if method.endswith("Sent") else ForwardMsg()
            message.ParseFromString(base64.b64decode(event["params"]["response"]["payloadData"]))
            if mutation == "invalid-input" and isinstance(message, BackMsg):
                message.rerun_script.widget_states.widgets[0].string_value = "zzzzzz"
            elif mutation == "callback" and message.WhichOneof("type") == "delta" and message.delta.new_element.WhichOneof("type") == "json":
                report = json.loads(message.delta.new_element.json.body)
                report["events"].append("#aabbcc")
                message.delta.new_element.json.body = json.dumps(report)
                stage["dom"]["reports"][0] = stage["dom"]["reports"][0].replace('0:"#aabbcc"', '0:"#aabbcc"\n1:"#aabbcc"')
            else:
                continue
            event["params"]["response"]["payloadData"] = base64.b64encode(message.SerializeToString()).decode()
    with pytest.raises(AssertionError):
        check_color_ui(capture, folder)


def frames(capture):
    for frame in capture["frames"]:
        data = base64.b64decode(frame["base64"], validate=True)
        assert len(data) == frame["bytes"]
        message = BackMsg() if frame["direction"] == "client->server" else ForwardMsg()
        message.ParseFromString(data)
        assert MessageToDict(message, preserving_proto_field_name=True) == frame["message"]
        yield message


COLOR_UNKEYED_PHASES = ("load", "edit", "explicit", "explicit-edit", "width-zero", "width-edit", "width-neg", "width-one", "width39", "width40", "width41", "width41-edit", "width40-return", "implicit-return", "observe")
COLOR_UNKEYED_GROUPS = (0, 0, 1, 1, 2, 2, 2, 2, 2, 2, 3, 3, 2, 0, 0)
COLOR_UNKEYED_VALUES = ("#000000", "#a1b2c3", "#000000", "#112233", "#000000", "#445566", "#445566", "#445566", "#445566", "#445566", "#000000", "#778899", "#000000", "#000000", "#000000")
COLOR_UNKEYED_WIDTHS = (None, None, None, None, 40, 40, 40, 40, 40, 40, 41, 41, 40, None, None)


def check_color_unkeyed(capture):
    assert capture["successful"] and "producer_error" not in capture and capture["reference_version"] == "1.66.1"
    assert len(capture["frames"]) == 104 and len(capture["elements"]) == 30 and capture["finishes"] == [0] * 15
    assert capture["cleanup"]["websocket_closed"] and capture["cleanup"]["server_stopped" if capture["runtime"] == "python" else "caller_server_stopped"]
    kinds = []
    for message in frames(capture):
        kind = message.WhichOneof("type")
        kinds.append((kind, message.session_status_changed.script_is_running) if kind == "session_status_changed" else kind)
    expected = []
    for index in range(15):
        expected += ["rerun_script"] + ([("session_status_changed", False)] if index else [])
        expected += ["new_session", ("session_status_changed", True), "delta", "delta", "script_finished"]
    assert kinds == expected
    runs = color_runs(capture)
    assert len(runs) == 15
    ids, sessions, run_ids, normalized = [], set(), set(), []
    for index, (run, phase, value, width) in enumerate(zip(runs, COLOR_UNKEYED_PHASES, COLOR_UNKEYED_VALUES, COLOR_UNKEYED_WIDTHS, strict=True)):
        request = run["request"]
        assert request.query_string == "probe=color-unkeyed&phase=" + phase and not request.is_history_navigation
        assert len(run["sessions"]) == 1 and run["finishes"] == [0]
        session = run["sessions"][0]
        assert session.initialize.environment_info.streamlit_version == "1.66.1"
        sessions.add(session.initialize.session_id)
        run_ids.add(session.script_run_id)
        assert [entry[0] for entry in run["entries"]] == ["color_picker", "json"]
        widget, element = run["entries"][0][1:]
        assert widget.id and widget.label == "Unkeyed accent" and widget.default == "#000000"
        assert not widget.value and not widget.set_value and not element.HasField("has_one_shot_effect")
        assert not widget.disabled and not widget.form_id and not widget.help and not widget.ignore_rerun and widget.label_visibility.value == 0
        assert MessageToDict(element.width_config, preserving_proto_field_name=True) == ({"use_content": True} if width is None else {"pixel_width": width})
        for earlier in range(index):
            assert (widget.id == ids[earlier]) == (COLOR_UNKEYED_GROUPS[index] == COLOR_UNKEYED_GROUPS[earlier]), (phase, earlier)
        ids.append(widget.id)
        assert json.loads(run["entries"][1][1].body) == {"phase": phase, "value": value}
        for position in range(2):
            assert capture["elements"][index * 2 + position]["delta_path"] == [0, position]
        incoming = request.widget_states.widgets
        if phase in ("edit", "explicit-edit", "width-edit", "width41-edit"):
            assert len(incoming) == 1 and incoming[0].id == ids[index - 1] and incoming[0].WhichOneof("value") == "string_value" and incoming[0].string_value == value
        else:
            assert not incoming
        normalized_run = []
        for kind, _, element in run["entries"]:
            fields = MessageToDict(element, preserving_proto_field_name=True)
            if kind == "color_picker":
                fields[kind].pop("id")
            else:
                fields[kind]["body"] = json.loads(fields[kind]["body"])
            normalized_run.append(fields)
        normalized.append(normalized_run)
    assert len(set(ids)) == 4 and len(sessions) == 1 and len(run_ids) == 15
    return normalized


@pytest.mark.parametrize("root", (PYTHON, RUST), ids=("python", "rust"))
def test_unkeyed_color_raw_default_width_and_cleanup(root):
    check_color_unkeyed(read(root / "color-unkeyed/trace.json"))


def test_unkeyed_color_complete_elements_match_reference():
    captures = [read(root / "color-unkeyed/trace.json") for root in (PYTHON, RUST)]
    assert captures[0]["producer_sources_sha256"] == captures[1]["producer_sources_sha256"]
    assert check_color_unkeyed(captures[0]) == check_color_unkeyed(captures[1])


def test_unkeyed_color_before_keeps_single_identity_and_old_values():
    capture = read(RUST / "color-unkeyed/before/trace.json")
    assert capture["successful"] and capture["semantic_match"] is False
    runs = color_runs(capture)
    assert len(runs) == 15 and len(capture["frames"]) == 104 and len(capture["elements"]) == 30
    assert len({run["entries"][0][1].id for run in runs}) == 1
    assert json.loads(runs[2]["entries"][1][1].body)["value"] == "#a1b2c3"
    assert json.loads(runs[-1]["entries"][1][1].body)["value"] == "#778899"
    with pytest.raises(AssertionError):
        check_color_unkeyed(capture)


@pytest.mark.parametrize("mutation", ("explicit-id", "raw-width-id", "revived-value", "wire-width", "stale-input"))
def test_unkeyed_color_gate_rejects_wrong_wire(mutation):
    capture = read(PYTHON / "color-unkeyed/trace.json")
    source = color_runs(capture)
    target = {"explicit-id": 2, "raw-width-id": 6, "revived-value": 12, "wire-width": 8, "stale-input": 5}[mutation]
    run = -1
    for frame in capture["frames"]:
        client = frame["direction"] == "client->server"
        if client:
            run += 1
        if run != target:
            continue
        message = BackMsg() if client else ForwardMsg()
        message.ParseFromString(base64.b64decode(frame["base64"]))
        if mutation == "stale-input" and client:
            message.rerun_script.widget_states.widgets[0].id = source[3]["entries"][0][1].id
        elif not client and message.WhichOneof("type") == "delta" and message.delta.WhichOneof("type") == "new_element":
            element = message.delta.new_element
            kind = element.WhichOneof("type")
            if kind == "color_picker" and mutation in ("explicit-id", "raw-width-id"):
                element.color_picker.id = source[0]["entries"][0][1].id if mutation == "explicit-id" else "wrong-raw-width-identity"
            elif kind == "color_picker" and mutation == "wire-width":
                element.width_config.pixel_width = 39
            elif kind == "json" and mutation == "revived-value":
                report = json.loads(element.json.body)
                report["value"] = "#445566"
                element.json.body = json.dumps(report)
            else:
                continue
        else:
            continue
        raw = message.SerializeToString()
        frame.update(base64=base64.b64encode(raw).decode(), bytes=len(raw), message=MessageToDict(message, preserving_proto_field_name=True))
    emitted = []
    for message in frames(capture):
        if isinstance(message, ForwardMsg) and message.WhichOneof("type") == "delta":
            element = message.delta.new_element
            kind = element.WhichOneof("type")
            emitted.append({"kind": kind, "fields": MessageToDict(getattr(element, kind), preserving_proto_field_name=True), "delta_path": list(message.metadata.delta_path)})
    capture["elements"] = emitted
    with pytest.raises(AssertionError):
        check_color_unkeyed(capture)


BOOL_PHASES = ("load", "edit", "width", "width-edit", "restore", "edit-restored", "observe")
BOOL_LABELS = ("Unkeyed check", "Unkeyed toggle", "Keyed check", "Keyed toggle")


def check_bool_width(capture):
    assert capture["successful"] and "producer_error" not in capture and capture["reference_version"] == "1.66.1"
    assert capture["cleanup"]["websocket_closed"] and capture["finishes"] == [0] * 7
    assert capture["cleanup"]["server_stopped" if capture["runtime"] == "python" else "caller_server_stopped"]
    assert len(capture["frames"]) == 69 and len(capture["elements"]) == 35
    runs = color_runs(capture, ("checkbox", "json"))
    assert len(runs) == 7
    groups, history, normalized, sessions, run_ids = (0, 0, 1, 1, 0, 0, 0), [], [], set(), set()
    for index, (phase, run) in enumerate(zip(BOOL_PHASES, runs, strict=True)):
        request = run["request"]
        assert request.query_string == "probe=bool-width&phase=" + phase and not request.is_history_navigation
        assert len(run["sessions"]) == 1 and run["finishes"] == [0]
        session = run["sessions"][0]
        assert session.initialize.environment_info.streamlit_version == "1.66.1"
        sessions.add(session.initialize.session_id)
        run_ids.add(session.script_run_id)
        assert [entry[0] for entry in run["entries"]] == ["checkbox"] * 4 + ["json"]
        ids = []
        for position, (_, widget, element) in enumerate(run["entries"][:4]):
            assert widget.label == BOOL_LABELS[position] and widget.id and widget.type == position % 2
            assert not widget.default and not widget.value and not widget.set_value
            assert not widget.disabled and not widget.form_id and not widget.help and not widget.ignore_rerun
            assert widget.label_visibility.value == 0 and not element.HasField("has_one_shot_effect")
            assert MessageToDict(element.width_config, preserving_proto_field_name=True) == ({"pixel_width": 320} if phase in ("width", "width-edit") else {"use_content": True})
            for earlier in range(index):
                assert (widget.id == history[earlier][position]) == (position >= 2 or groups[index] == groups[earlier]), (phase, position, earlier)
            ids.append(widget.id)
        history.append(ids)
        unkeyed = phase not in ("load", "width", "restore")
        assert json.loads(run["entries"][4][1].body) == {"phase": phase, "values": [unkeyed, unkeyed, index != 0, index != 0]}
        assert run["entries"][4][1].expanded
        assert [capture["elements"][index * 5 + i]["delta_path"] for i in range(5)] == [[0, i] for i in range(5)]
        incoming = request.widget_states.widgets
        if phase in ("edit", "width-edit", "edit-restored"):
            assert len(incoming) == 4
            assert [w.id for w in incoming] == history[index - 1]
            assert all(w.WhichOneof("value") == "bool_value" and w.bool_value for w in incoming)
        else:
            assert not incoming
        normalized_run = []
        for kind, _, element in run["entries"]:
            fields = MessageToDict(element, preserving_proto_field_name=True)
            if kind == "checkbox":
                fields[kind].pop("id")
            else:
                fields[kind]["body"] = json.loads(fields[kind]["body"])
            normalized_run.append(fields)
        normalized.append(normalized_run)
    assert len(sessions) == 1 and len(run_ids) == 7
    assert [len({ids[i] for ids in history}) for i in range(4)] == [2, 2, 1, 1]
    return normalized


@pytest.mark.parametrize("root", (PYTHON, RUST), ids=("python", "rust"))
def test_checkbox_toggle_width_and_cleanup(root):
    check_bool_width(read(root / "bool-width/trace.json"))


def test_bool_width_complete_elements_match_reference():
    captures = [read(root / "bool-width/trace.json") for root in (PYTHON, RUST)]
    assert captures[0]["producer_sources_sha256"] == captures[1]["producer_sources_sha256"]
    assert captures[1]["semantic_match"] is True
    assert check_bool_width(captures[0]) == check_bool_width(captures[1])


def test_bool_width_before_keeps_old_unkeyed_state():
    capture = read(RUST / "bool-width/before/trace.json")
    runs = color_runs(capture, ("checkbox", "json"))
    assert capture["semantic_match"] is False
    assert json.loads(runs[2]["entries"][4][1].body)["values"] == [True] * 4
    assert [len({r["entries"][i][1].id for r in runs}) for i in range(4)] == [1] * 4
    with pytest.raises(AssertionError):
        check_bool_width(capture)


@pytest.mark.parametrize("mutation", ("unkeyed-id", "keyed-id", "revived-value", "wire-width", "stale-input"))
def test_bool_width_gate_rejects_coherent_wrong_wire(mutation):
    capture = read(PYTHON / "bool-width/trace.json")
    source = color_runs(capture, ("checkbox", "json"))
    target = 4 if mutation == "revived-value" else 3 if mutation == "stale-input" else 2
    run = -1
    for frame in capture["frames"]:
        client = frame["direction"] == "client->server"
        if client:
            run += 1
        if run != target:
            continue
        message = BackMsg() if client else ForwardMsg()
        message.ParseFromString(base64.b64decode(frame["base64"]))
        if client and mutation == "stale-input":
            message.rerun_script.widget_states.widgets[0].id = source[0]["entries"][0][1].id
        elif not client and message.WhichOneof("type") == "delta":
            element = message.delta.new_element
            kind = element.WhichOneof("type")
            if kind == "checkbox" and mutation == "unkeyed-id" and element.checkbox.label == BOOL_LABELS[0]:
                element.checkbox.id = source[0]["entries"][0][1].id
            elif kind == "checkbox" and mutation == "keyed-id" and element.checkbox.label == BOOL_LABELS[2]:
                element.checkbox.id = "wrong-keyed-identity"
            elif kind == "checkbox" and mutation == "wire-width":
                element.width_config.pixel_width = 321
            elif kind == "json" and mutation == "revived-value":
                report = json.loads(element.json.body)
                report["values"] = [True] * 4
                element.json.body = json.dumps(report)
            else:
                continue
        else:
            continue
        raw = message.SerializeToString()
        frame.update(base64=base64.b64encode(raw).decode(), bytes=len(raw), message=MessageToDict(message, preserving_proto_field_name=True))
    emitted = []
    for message in frames(capture):
        if isinstance(message, ForwardMsg) and message.WhichOneof("type") == "delta":
            element = message.delta.new_element
            kind = element.WhichOneof("type")
            emitted.append({"kind": kind, "fields": MessageToDict(getattr(element, kind), preserving_proto_field_name=True), "delta_path": list(message.metadata.delta_path)})
    capture["elements"] = emitted
    with pytest.raises(AssertionError):
        check_bool_width(capture)


SELECT_PHASES = ("load", "edit", "mode", "mode-edit", "width", "limit", "limit-edit", "restore", "observe")
SELECT_VALUES = (("Alpha", ["Alpha"]), ("Beta", ["Beta"]), ("Alpha", ["Alpha"]), ("Novel", ["Beta", "Charlie"]),
                 ("Novel", ["Beta", "Charlie"]), ("Novel", ["Alpha"]), ("Beta", ["Charlie"]), ("Alpha", ["Alpha"]), ("Alpha", ["Alpha"]))


SELECT_UNKEYED_PHASES = ("load", "edit", "mode", "mode-edit", "width", "limit", "limit-edit", "placeholder", "placeholder-edit",
                         "filter", "filter-edit", "filter-return", "empty-placeholder", "empty-edit", "space-placeholder", "restore", "observe")
SELECT_UNKEYED_VALUES = (("Alpha", ["Alpha"]), ("Beta", ["Beta"]), ("Alpha", ["Alpha"]), ("Novel", ["Beta", "Charlie"]),
                         ("Alpha", ["Alpha"]), ("Alpha", ["Alpha"]), ("Beta", ["Charlie"]), ("Alpha", ["Charlie"]),
                         ("Beta", ["Charlie"]), ("Alpha", ["Charlie"]), ("Beta", ["Charlie"]), ("Alpha", ["Charlie"]),
                         ("Alpha", ["Charlie"]), ("Beta", ["Charlie"]), ("Beta", ["Charlie"]), ("Alpha", ["Alpha"]), ("Alpha", ["Alpha"]))
SELECT_UNKEYED_GROUPS = ((0, 0, 1, 1, 2, 1, 1, 3, 3, 4, 4, 3, 5, 5, 5, 0, 0), (0, 0, 1, 1, 2, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 0, 0))


def check_select_policy(capture, *, unkeyed=False):
    phases = SELECT_UNKEYED_PHASES if unkeyed else SELECT_PHASES
    expected_values = SELECT_UNKEYED_VALUES if unkeyed else SELECT_VALUES
    groups = SELECT_UNKEYED_GROUPS if unkeyed else ((0, 0, 1, 1, 1, 1, 1, 0, 0), (0, 0, 1, 1, 1, 2, 2, 0, 0))
    assert capture["successful"] and "producer_error" not in capture and capture["reference_version"] == "1.66.1"
    assert capture["cleanup"]["websocket_closed"] and capture["finishes"] == [0] * len(phases)
    assert capture["cleanup"]["server_stopped" if capture["runtime"] == "python" else "caller_server_stopped"]
    assert len(capture["frames"]) == len(phases) * 8 - 1 and len(capture["elements"]) == len(phases) * 3
    runs = color_runs(capture, ("selectbox", "multiselect", "json"))
    history, normalized, sessions, run_ids = [], [], set(), set()
    for index, (phase, run) in enumerate(zip(phases, runs, strict=True)):
        request = run["request"]
        assert request.query_string == "probe=" + ("select-policy-unkeyed" if unkeyed else "select-policy") + "&phase=" + phase and not request.is_history_navigation
        assert len(run["sessions"]) == 1 and run["finishes"] == [0]
        session = run["sessions"][0]
        assert session.initialize.environment_info.streamlit_version == "1.66.1"
        sessions.add(session.initialize.session_id)
        run_ids.add(session.script_run_id)
        assert [entry[0] for entry in run["entries"]] == ["selectbox", "multiselect", "json"]
        creation = phase not in ("load", "edit", "restore", "observe")
        single, multiple = (entry[1] for entry in run["entries"][:2])
        assert single.label == "Choice" and multiple.label == "Choices"
        assert single.accept_new_options == creation and not multiple.accept_new_options
        assert single.default == 0 and list(multiple.default) == [0]
        assert multiple.max_selections == ((2 if phase in ("mode", "mode-edit", "width") else 3) if creation else 0)
        assert single.placeholder == ("Pick one" if phase.startswith(("placeholder", "filter")) else " " if phase.startswith("empty") or phase == "space-placeholder" else "")
        assert single.filter_mode == (2 if phase in ("filter", "filter-edit") else 0)
        ids = []
        for position, (_, widget, element) in enumerate(run["entries"][:2]):
            assert widget.id and list(widget.options) == ["Alpha", "Beta", "Charlie"]
            assert not widget.set_value and not widget.disabled and not widget.form_id and not widget.help and not widget.ignore_rerun
            assert widget.label_visibility.value == 0 and not element.HasField("has_one_shot_effect")
            assert MessageToDict(element.width_config, preserving_proto_field_name=True) == ({"pixel_width": 320} if phase == "width" else {"use_stretch": True})
            for earlier in range(index):
                assert (widget.id == history[earlier][position]) == (groups[position][index] == groups[position][earlier]), (phase, position, earlier)
            ids.append(widget.id)
        history.append(ids)
        assert json.loads(run["entries"][2][1].body) == {"phase": phase, "values": list(expected_values[index])}
        assert [capture["elements"][index * 3 + i]["delta_path"] for i in range(3)] == [[0, i] for i in range(3)]
        incoming = request.widget_states.widgets
        if phase.endswith("edit"):
            assert len(incoming) == 2 and [w.id for w in incoming] == history[index - 1]
            assert incoming[0].WhichOneof("value") == "string_value" and incoming[0].string_value == expected_values[index][0]
            assert incoming[1].WhichOneof("value") == "string_array_value" and list(incoming[1].string_array_value.data) == expected_values[index][1]
        else:
            assert not incoming
        normalized_run = []
        for kind, _, element in run["entries"]:
            fields = MessageToDict(element, preserving_proto_field_name=True)
            if kind != "json":
                fields[kind].pop("id")
            else:
                fields[kind]["body"] = json.loads(fields[kind]["body"])
            normalized_run.append(fields)
        normalized.append(normalized_run)
    assert len(sessions) == 1 and len(run_ids) == len(phases)
    assert [len({ids[i] for ids in history}) for i in range(2)] == ([6, 4] if unkeyed else [2, 3])
    return normalized


@pytest.mark.parametrize("root", (PYTHON, RUST), ids=("python", "rust"))
def test_keyed_selection_creation_and_limit_identity(root):
    check_select_policy(read(root / "select-policy/trace.json"))


def test_select_policy_complete_elements_match_reference():
    captures = [read(root / "select-policy/trace.json") for root in (PYTHON, RUST)]
    assert captures[0]["producer_sources_sha256"] == captures[1]["producer_sources_sha256"]
    assert captures[1]["semantic_match"] is True
    assert check_select_policy(captures[0]) == check_select_policy(captures[1])


def test_select_policy_before_keeps_one_identity_and_old_values():
    capture = read(RUST / "select-policy/before/trace.json")
    assert capture["successful"] and "producer_error" not in capture and capture["finishes"] == [0] * 9
    assert len(capture["frames"]) == 71 and len(capture["elements"]) == 27
    assert capture["cleanup"] == {"websocket_closed": True, "caller_server_stopped": True}
    runs = color_runs(capture, ("selectbox", "multiselect", "json"))
    assert capture["semantic_match"] is False
    assert [len({r["entries"][i][1].id for r in runs}) for i in range(2)] == [1, 1]
    assert json.loads(runs[2]["entries"][2][1].body)["values"] == ["Beta", ["Beta"]]
    with pytest.raises(AssertionError):
        check_select_policy(capture)


@pytest.mark.parametrize("mutation", ("mode-id", "limit-id", "restore-value", "max-count", "stale-input"))
def test_select_policy_gate_rejects_coherent_wrong_wire(mutation):
    capture = read(PYTHON / "select-policy/trace.json")
    source = color_runs(capture, ("selectbox", "multiselect", "json"))
    target = {"mode-id": 2, "limit-id": 5, "restore-value": 7, "max-count": 5, "stale-input": 6}[mutation]
    run = -1
    for frame in capture["frames"]:
        client = frame["direction"] == "client->server"
        if client:
            run += 1
        if run != target:
            continue
        message = BackMsg() if client else ForwardMsg()
        message.ParseFromString(base64.b64decode(frame["base64"]))
        if client and mutation == "stale-input":
            message.rerun_script.widget_states.widgets[1].id = source[0]["entries"][1][1].id
        elif not client and message.WhichOneof("type") == "delta":
            element = message.delta.new_element
            kind = element.WhichOneof("type")
            if kind == "selectbox" and mutation == "mode-id":
                element.selectbox.id = source[0]["entries"][0][1].id
            elif kind == "multiselect" and mutation == "limit-id":
                element.multiselect.id = source[2]["entries"][1][1].id
            elif kind == "multiselect" and mutation == "max-count":
                element.multiselect.max_selections = 2
            elif kind == "json" and mutation == "restore-value":
                report = json.loads(element.json.body)
                report["values"] = ["Beta", ["Charlie"]]
                element.json.body = json.dumps(report)
            else:
                continue
        else:
            continue
        raw = message.SerializeToString()
        frame.update(base64=base64.b64encode(raw).decode(), bytes=len(raw), message=MessageToDict(message, preserving_proto_field_name=True))
    capture["elements"] = [{"kind": m.delta.new_element.WhichOneof("type"), "fields": MessageToDict(getattr(m.delta.new_element, m.delta.new_element.WhichOneof("type")), preserving_proto_field_name=True),
                            "delta_path": list(m.metadata.delta_path)} for m in frames(capture) if isinstance(m, ForwardMsg) and m.WhichOneof("type") == "delta"]
    with pytest.raises(AssertionError):
        check_select_policy(capture)


@pytest.mark.parametrize("root", (PYTHON, RUST), ids=("python", "rust"))
def test_unkeyed_selection_display_and_limit_identity(root):
    check_select_policy(read(root / "select-policy-unkeyed/trace.json"), unkeyed=True)


def test_unkeyed_selection_complete_elements_match_reference():
    captures = [read(root / "select-policy-unkeyed/trace.json") for root in (PYTHON, RUST)]
    assert captures[0]["producer_sources_sha256"] == captures[1]["producer_sources_sha256"]
    assert captures[1]["semantic_match"] is True
    assert check_select_policy(captures[0], unkeyed=True) == check_select_policy(captures[1], unkeyed=True)


def test_unkeyed_selection_before_keeps_values_and_omits_empty_placeholder():
    capture = read(RUST / "select-policy-unkeyed/before/trace.json")
    assert capture["successful"] and capture["finishes"] == [0] * 17 and "producer_error" not in capture
    assert len(capture["frames"]) == 135 and len(capture["elements"]) == 51
    assert capture["semantic_match"] is False and capture["cleanup"] == {"websocket_closed": True, "caller_server_stopped": True}
    runs = color_runs(capture, ("selectbox", "multiselect", "json"))
    assert [len({r["entries"][i][1].id for r in runs}) for i in range(2)] == [2, 3]
    assert json.loads(runs[4]["entries"][2][1].body)["values"] == ["Novel", ["Beta", "Charlie"]]
    assert runs[12]["entries"][0][1].placeholder == ""
    with pytest.raises(AssertionError):
        check_select_policy(capture, unkeyed=True)


@pytest.mark.parametrize("mutation", ("width-id", "placeholder-id", "filter-id", "space-id", "revived-value", "wire-placeholder", "stale-input"))
def test_unkeyed_selection_gate_rejects_coherent_wrong_wire(mutation):
    capture = read(PYTHON / "select-policy-unkeyed/trace.json")
    source = color_runs(capture, ("selectbox", "multiselect", "json"))
    target = {"width-id": 4, "placeholder-id": 7, "filter-id": 9, "space-id": 14, "revived-value": 11, "wire-placeholder": 12, "stale-input": 13}[mutation]
    run = -1
    for frame in capture["frames"]:
        client = frame["direction"] == "client->server"
        if client:
            run += 1
        if run != target:
            continue
        message = BackMsg() if client else ForwardMsg()
        message.ParseFromString(base64.b64decode(frame["base64"]))
        if client and mutation == "stale-input":
            message.rerun_script.widget_states.widgets[0].id = source[9]["entries"][0][1].id
        elif not client and message.WhichOneof("type") == "delta":
            element = message.delta.new_element
            kind = element.WhichOneof("type")
            if kind == "selectbox" and mutation in ("width-id", "placeholder-id", "filter-id", "space-id"):
                earlier = {"width-id": 2, "placeholder-id": 6, "filter-id": 8, "space-id": 11}[mutation]
                element.selectbox.id = source[earlier]["entries"][0][1].id
            elif kind == "selectbox" and mutation == "wire-placeholder":
                element.selectbox.placeholder = ""
            elif kind == "json" and mutation == "revived-value":
                report = json.loads(element.json.body)
                report["values"][0] = "Beta"
                element.json.body = json.dumps(report)
            else:
                continue
        else:
            continue
        raw = message.SerializeToString()
        frame.update(base64=base64.b64encode(raw).decode(), bytes=len(raw), message=MessageToDict(message, preserving_proto_field_name=True))
    capture["elements"] = [{"kind": m.delta.new_element.WhichOneof("type"), "fields": MessageToDict(getattr(m.delta.new_element, m.delta.new_element.WhichOneof("type")), preserving_proto_field_name=True),
                            "delta_path": list(m.metadata.delta_path)} for m in frames(capture) if isinstance(m, ForwardMsg) and m.WhichOneof("type") == "delta"]
    with pytest.raises(AssertionError):
        check_select_policy(capture, unkeyed=True)


SELECT_UI_NAMES = ("01-prefix-load", "02-prefix-ha", "03-prefix-Be", "04-prefix-Beta-commit", "05-prefix-Novel-draft", "06-prefix-Novel-commit",
                   "07-fuzzy-load", "08-fuzzy-ha", "09-fuzzy-Charlie-commit", "10-empty-load", "11-empty-blank-editor", "12-empty-Beta-commit",
                   "13-space-load", "14-space-blank-editor", "15-space-Beta-commit")
SELECT_UI_INPUTS = ("Alpha", "ha", "Be", "Beta", "Novel", "Novel", "Alpha", "ha", "Charlie", "Alpha", "", "Beta", "Alpha", "", "Beta")
SELECT_UI_RETURNED = ("Alpha", "Alpha", "Alpha", "Beta", "Beta", "Novel", "Alpha", "Alpha", "Charlie", "Alpha", "Alpha", "Beta", "Alpha", "Alpha", "Beta")
SELECT_UI_DRAFTS = (1, 2, 4, 7, 10, 13)


def check_selection_ui(capture, folder):
    import hashlib
    from PIL import Image

    assert capture["successful"] and capture["collection_complete"] and capture["semantic_match"] and capture["reference_version"] == "1.66.1"
    assert capture["runtime"] in ("python", "rust")
    assert capture["visual_review"]["all_stage_images_inspected"] and capture["visual_review"]["phase_alignment"]
    cleanup = capture["cleanup"]
    assert cleanup["network_disabled"] and cleanup["tab_closed"] and cleanup["server_stopped"] and not cleanup["close_event_observed"]
    assert cleanup["ports_without_listeners"] == [8599, 8624]
    assert capture["console"] == []
    port, height = (8624, 780) if capture["runtime"] == "python" else (8599, 724)
    assert [s["name"] for s in capture["stages"]] == list(SELECT_UI_NAMES)
    events = capture["events"]
    assert len(events) == 76
    sockets, sequence, current_socket = [], 0, None
    messages = {}
    for index, event in enumerate(events):
        assert event["sequence"] > sequence and event["source"]["tabId"] == int(capture["tab_id"])
        sequence = event["sequence"]
        if event["method"] == "Network.webSocketCreated":
            assert event["params"]["url"] == f"ws://127.0.0.1:{port}/_stcore/stream"
            current_socket = event["params"]["requestId"]
            assert current_socket not in sockets
            sockets.append(current_socket)
            continue
        assert event["method"] in ("Network.webSocketFrameSent", "Network.webSocketFrameReceived")
        assert event["params"]["requestId"] == current_socket and event["params"]["response"]["opcode"] == 2
        message = BackMsg() if event["method"].endswith("Sent") else ForwardMsg()
        message.ParseFromString(base64.b64decode(event["params"]["response"]["payloadData"], validate=True))
        messages[index] = message
    assert len(sockets) == 4 and len(messages) == 72
    boundary, normalized, session_groups, run_ids, widget_ids = 0, [], [], set(), None
    for index, stage in enumerate(capture["stages"]):
        phase = "filter" if index < 6 else "filter-return" if index < 9 else "empty-placeholder" if index < 12 else "space-placeholder"
        case = "prefix" if index < 6 else "fuzzy" if index < 9 else "empty" if index < 12 else "space"
        assert stage["case"] == case and stage["action_and_capture_calls_separate"]
        start, end = stage["event_range"]
        assert start == boundary
        assert end - start == (0 if index in SELECT_UI_DRAFTS else 9 if index in (0, 6, 9, 12) else 8)
        boundary = end
        dom = stage["dom"]
        assert dom["url"] == f"http://127.0.0.1:{port}/?probe=select-policy-unkeyed&phase={phase}"
        assert dom["viewport"] == {"width": 1463, "height": height, "dpr": 1.75}
        assert dom["inputs"] == [{"label": "Choice", "labelledby": None, "value": SELECT_UI_INPUTS[index], "placeholder": "Pick one" if index < 9 else " ", "expanded": "true" if index in SELECT_UI_DRAFTS else "false"},
                                 {"label": "Choices", "labelledby": None, "value": "", "placeholder": "", "expanded": "false"}]
        expected_options = {1: [("Add: ha", False)], 2: [("Add: Be", False), ("Beta", False)], 4: [("Add: Novel", False)],
                            7: [("Add: ha", False), ("Alpha", True), ("Charlie", False)], 10: [("Alpha", True), ("Beta", False), ("Charlie", False)],
                            13: [("Alpha", True), ("Beta", False), ("Charlie", False)]}.get(index, [])
        assert dom["options"] == [{"text": text, "selected": str(selected).lower()} for text, selected in expected_options]
        body = re.sub(r"\s+", "", dom["body"])
        assert f'"phase":"{phase}"' in body and f'"values":[0:"{SELECT_UI_RETURNED[index]}"1:[0:"Alpha"]]' in body
        picture = stage["screenshot"]
        data = (folder / picture["file"]).read_bytes()
        assert picture["file"] == SELECT_UI_NAMES[index] + ".jpg"
        assert len(data) == picture["bytes"] and hashlib.sha256(data).hexdigest() == picture["sha256"]
        with Image.open(folder / picture["file"]) as image:
            assert image.format == picture["format"] == "JPEG" and list(image.size) == picture["dimensions"] == [1463, height]
            rgb = image.convert("RGB")
            bright = sum(min(rgb.getpixel((x, y))) > 110 for y in range(134, 155) for x in range(388, 451))
            assert bright < 30 if index in (10, 13) else bright > 40
        batch = [messages[i] for i in range(start, end) if i in messages]
        if index in SELECT_UI_DRAFTS:
            assert not batch
            continue
        assert [m.WhichOneof("type") for m in batch] == ["rerun_script", "new_session", "session_status_changed", "delta", "delta", "delta", "script_finished", "session_status_changed"]
        request, session = batch[0].rerun_script, batch[1].new_session
        assert request.query_string == f"probe=select-policy-unkeyed&phase={phase}"
        assert session.initialize.environment_info.streamlit_version == "1.66.1"
        run_ids.add(session.script_run_id)
        assert batch[2].session_status_changed.script_is_running and batch[6].script_finished == 0 and not batch[7].session_status_changed.script_is_running
        elements = [m.delta.new_element for m in batch[3:6]]
        assert [m.delta.WhichOneof("type") for m in batch[3:6]] == ["new_element"] * 3
        assert [list(m.metadata.delta_path) for m in batch[3:6]] == [[0, 0], [0, 1], [0, 2]]
        assert [e.WhichOneof("type") for e in elements] == ["selectbox", "multiselect", "json"]
        current_ids = [elements[0].selectbox.id, elements[1].multiselect.id]
        if index in (0, 6, 9, 12):
            assert not request.widget_states.widgets
            session_groups.append([session.initialize.session_id])
        else:
            assert current_ids == widget_ids
            session_groups[-1].append(session.initialize.session_id)
            incoming = request.widget_states.widgets
            assert len(incoming) == 2 and [w.id for w in incoming] == widget_ids
            assert incoming[0].WhichOneof("value") == "string_value" and incoming[0].string_value == SELECT_UI_RETURNED[index]
            assert incoming[1].WhichOneof("value") == "string_array_value" and list(incoming[1].string_array_value.data) == ["Alpha"]
        widget_ids = current_ids
        assert json.loads(elements[2].json.body) == {"phase": phase, "values": [SELECT_UI_RETURNED[index], ["Alpha"]]}
        fields = [MessageToDict(e, preserving_proto_field_name=True) for e in elements]
        fields[0]["selectbox"].pop("id")
        fields[1]["multiselect"].pop("id")
        fields[2]["json"]["body"] = json.loads(fields[2]["json"]["body"])
        normalized.append(fields)
    assert boundary == len(events) and len(run_ids) == 9
    assert [len(g) for g in session_groups] == [3, 2, 2, 2]
    assert all(len(set(g)) == 1 for g in session_groups) and len({g[0] for g in session_groups}) == 4
    return normalized


@pytest.mark.parametrize("root", (PYTHON, RUST), ids=("python", "rust"))
def test_selection_ui_filters_new_values_and_blank_editors(root):
    folder = root / "select-policy-unkeyed/ui"
    check_selection_ui(read(folder / "trace.json"), folder)


def test_selection_ui_complete_elements_match_reference():
    folders = [root / "select-policy-unkeyed/ui" for root in (PYTHON, RUST)]
    captures = [read(folder / "trace.json") for folder in folders]
    assert captures[0]["producer_sources_sha256"] == captures[1]["producer_sources_sha256"]
    assert check_selection_ui(captures[0], folders[0]) == check_selection_ui(captures[1], folders[1])


@pytest.mark.parametrize("mutation", ("draft-send", "filter-options", "placeholder", "input", "returned-value", "screenshot", "old-image"))
def test_selection_ui_gate_rejects_wrong_events_or_picture(mutation, tmp_path):
    import hashlib

    folder = PYTHON / "select-policy-unkeyed/ui"
    capture = read(folder / "trace.json")
    if mutation == "draft-send":
        capture["stages"][1]["event_range"][1] += 1
    elif mutation == "filter-options":
        capture["stages"][7]["dom"]["options"] = [{"text": "Add: ha", "selected": "false"}]
    elif mutation == "placeholder":
        capture["stages"][10]["dom"]["inputs"][0]["placeholder"] = "Pick one"
    elif mutation == "screenshot":
        capture["stages"][10]["screenshot"]["sha256"] = "wrong"
    elif mutation == "old-image":
        for stage in capture["stages"]:
            (tmp_path / stage["screenshot"]["file"]).write_bytes((folder / stage["screenshot"]["file"]).read_bytes())
        data = (folder / capture["stages"][0]["screenshot"]["file"]).read_bytes()
        target = capture["stages"][10]["screenshot"]
        (tmp_path / target["file"]).write_bytes(data)
        target.update(bytes=len(data), sha256=hashlib.sha256(data).hexdigest())
        folder = tmp_path
    else:
        for event in capture["events"][slice(*capture["stages"][3]["event_range"])]:
            message = BackMsg() if event["method"].endswith("Sent") else ForwardMsg()
            message.ParseFromString(base64.b64decode(event["params"]["response"]["payloadData"]))
            if mutation == "input" and isinstance(message, BackMsg):
                message.rerun_script.widget_states.widgets[0].string_value = "wrong"
            elif mutation == "returned-value" and message.WhichOneof("type") == "delta" and message.delta.new_element.WhichOneof("type") == "json":
                report = json.loads(message.delta.new_element.json.body)
                report["values"][0] = "wrong"
                message.delta.new_element.json.body = json.dumps(report)
                capture["stages"][3]["dom"]["body"] = capture["stages"][3]["dom"]["body"].replace('0:"Beta"', '0:"wrong"')
            else:
                continue
            event["params"]["response"]["payloadData"] = base64.b64encode(message.SerializeToString()).decode()
    with pytest.raises(AssertionError):
        check_selection_ui(capture, folder)


RADIO_PHASES = ("load", "edit", "width", "width-edit", "horizontal", "horizontal-edit", "captions", "captions-edit", "empty", "empty-edit", "restore", "observe")
RADIO_GROUPS = (0, 0, 1, 1, 2, 2, 3, 3, 4, 4, 0, 0)


RADIO_EMPTY_PHASES = ("load", "edit", "empty", "empty-observe", "empty-none", "restore", "none", "none-edit", "none-observe", "restore-index", "assign-none", "observe", "assign-missing", "missing-observe")
RADIO_EMPTY_GROUPS = (0, 0, 1, 1, 2, 0, 3, 3, 3, 0, 0, 0, 0, 0)
RADIO_EMPTY_VALUES = (("Alpha", "Alpha"), ("Beta", "Beta"), (None, None), (None, None), (None, None), ("Alpha", None), (None, None),
                      ("Beta", "Beta"), ("Beta", "Beta"), ("Alpha", "Beta"), ("Alpha", None), ("Alpha", None), ("Alpha", "Alpha"), ("Alpha", "Alpha"))


def check_radio_identity(capture, *, empty=False):
    phases = RADIO_EMPTY_PHASES if empty else RADIO_PHASES
    groups = RADIO_EMPTY_GROUPS if empty else RADIO_GROUPS
    assert capture["successful"] and "producer_error" not in capture and capture["reference_version"] == "1.66.1"
    assert capture["runtime"] in ("python", "rust") and capture["finishes"] == [0] * len(phases)
    assert capture["cleanup"]["websocket_closed"] and capture["cleanup"]["server_stopped" if capture["runtime"] == "python" else "caller_server_stopped"]
    assert len(capture["frames"]) == len(phases) * 8 - 1 and len(capture["elements"]) == len(phases) * 3
    runs = color_runs(capture, ("radio", "json"))
    history, normalized, sessions, run_ids = [], [], set(), set()
    for index, (phase, run) in enumerate(zip(phases, runs, strict=True)):
        request = run["request"]
        assert request.query_string == "probe=" + ("radio-empty" if empty else "radio-identity") + "&phase=" + phase and not request.is_history_navigation
        assert len(run["sessions"]) == 1 and run["finishes"] == [0]
        session = run["sessions"][0]
        assert session.initialize.environment_info.streamlit_version == "1.66.1"
        sessions.add(session.initialize.session_id)
        run_ids.add(session.script_run_id)
        assert [e[0] for e in run["entries"]] == ["radio", "radio", "json"]
        ids = []
        for position, (_, widget, element) in enumerate(run["entries"][:2]):
            assert widget.label == ("Choice" if position == 0 else "Keyed choice") and widget.id
            wire_none = empty and (phase in ("none", "none-edit", "none-observe", "empty-none") or position == 1 and phase in ("empty-observe", "restore", "assign-none", "observe"))
            assert widget.HasField("default") == (not wire_none) and widget.default == 0
            assert list(widget.options) == ([] if empty and phase.startswith("empty") else ["Alpha", "Beta", "Charlie"])
            assert widget.horizontal == (phase in ("horizontal", "horizontal-edit"))
            assert list(widget.captions) == (["First", "Second", "Third"] if phase in ("captions", "captions-edit") else [])
            sync = empty and position == 1 and phase in ("empty", "assign-none", "assign-missing")
            assert widget.set_value == sync and not widget.disabled and not widget.form_id and not widget.help and not widget.ignore_rerun
            assert widget.label_visibility.value == 0 and element.HasField("has_one_shot_effect") == sync and element.has_one_shot_effect == sync
            assert widget.HasField("raw_value") == (sync and phase == "assign-missing") and widget.raw_value == ("Alpha" if sync and phase == "assign-missing" else "")
            assert MessageToDict(element.width_config, preserving_proto_field_name=True) == ({"pixel_width": 320} if phase in ("width", "width-edit") else {"use_content": True})
            for earlier in range(index):
                assert (widget.id == history[earlier][position]) == (position == 1 or groups[index] == groups[earlier]), (phase, position, earlier)
            ids.append(widget.id)
        history.append(ids)
        values = list(RADIO_EMPTY_VALUES[index]) if empty else ["Beta" if phase.endswith("edit") else "Alpha", "Beta" if index else "Alpha"]
        assert json.loads(run["entries"][2][1].body) == {"phase": phase, "values": values}
        assert [capture["elements"][index * 3 + i]["delta_path"] for i in range(3)] == [[0, i] for i in range(3)]
        incoming = request.widget_states.widgets
        if phase.endswith("edit"):
            assert len(incoming) == 2 and [w.id for w in incoming] == history[index - 1]
            assert all(w.WhichOneof("value") == "string_value" and w.string_value == "Beta" for w in incoming)
        else:
            assert not incoming
        normalized_run = []
        for kind, _, element in run["entries"]:
            fields = MessageToDict(element, preserving_proto_field_name=True)
            if kind == "radio":
                fields[kind].pop("id")
            else:
                fields[kind]["body"] = json.loads(fields[kind]["body"])
            normalized_run.append(fields)
        normalized.append(normalized_run)
    assert len(sessions) == 1 and len(run_ids) == len(phases)
    assert [len({ids[i] for ids in history}) for i in range(2)] == ([4, 1] if empty else [5, 1])
    return normalized


@pytest.mark.parametrize("root", (PYTHON, RUST), ids=("python", "rust"))
def test_radio_display_identity_and_default_width(root):
    check_radio_identity(read(root / "radio-identity/trace.json"))


def test_radio_complete_elements_match_reference():
    captures = [read(root / "radio-identity/trace.json") for root in (PYTHON, RUST)]
    assert captures[0]["producer_sources_sha256"] == captures[1]["producer_sources_sha256"] and captures[1]["semantic_match"] is True
    assert check_radio_identity(captures[0]) == check_radio_identity(captures[1])


def test_radio_before_keeps_old_values_and_stretch_default():
    capture = read(RUST / "radio-identity/before/trace.json")
    assert capture["successful"] and "producer_error" not in capture and capture["finishes"] == [0] * 12
    assert len(capture["frames"]) == 95 and len(capture["elements"]) == 36 and capture["semantic_match"] is False
    assert capture["cleanup"] == {"websocket_closed": True, "caller_server_stopped": True}
    runs = color_runs(capture, ("radio", "json"))
    assert [len({r["entries"][i][1].id for r in runs}) for i in range(2)] == [1, 1]
    assert runs[0]["entries"][0][2].width_config.use_stretch
    assert json.loads(runs[2]["entries"][2][1].body)["values"] == ["Beta", "Beta"]
    with pytest.raises(AssertionError):
        check_radio_identity(capture)


@pytest.mark.parametrize("mutation", ("default-width", "horizontal-id", "captions-id", "empty-id", "revived-value", "keyed-id", "stale-input"))
def test_radio_gate_rejects_coherent_wrong_wire(mutation):
    capture = read(PYTHON / "radio-identity/trace.json")
    source = color_runs(capture, ("radio", "json"))
    target = {"default-width": 0, "horizontal-id": 4, "captions-id": 6, "empty-id": 8, "revived-value": 10, "keyed-id": 4, "stale-input": 9}[mutation]
    run = -1
    for frame in capture["frames"]:
        client = frame["direction"] == "client->server"
        if client:
            run += 1
        if run != target:
            continue
        message = BackMsg() if client else ForwardMsg()
        message.ParseFromString(base64.b64decode(frame["base64"]))
        if client and mutation == "stale-input":
            message.rerun_script.widget_states.widgets[0].id = source[6]["entries"][0][1].id
        elif not client and message.WhichOneof("type") == "delta":
            element = message.delta.new_element
            kind = element.WhichOneof("type")
            if kind == "radio" and mutation == "default-width":
                element.width_config.use_stretch = True
            elif kind == "radio" and element.radio.label == "Choice" and mutation in ("horizontal-id", "captions-id", "empty-id"):
                element.radio.id = source[0]["entries"][0][1].id
            elif kind == "radio" and element.radio.label == "Keyed choice" and mutation == "keyed-id":
                element.radio.id = "wrong-keyed-identity"
            elif kind == "json" and mutation == "revived-value":
                report = json.loads(element.json.body)
                report["values"][0] = "Beta"
                element.json.body = json.dumps(report)
            else:
                continue
        else:
            continue
        raw = message.SerializeToString()
        frame.update(base64=base64.b64encode(raw).decode(), bytes=len(raw), message=MessageToDict(message, preserving_proto_field_name=True))
    capture["elements"] = [{"kind": m.delta.new_element.WhichOneof("type"), "fields": MessageToDict(getattr(m.delta.new_element, m.delta.new_element.WhichOneof("type")), preserving_proto_field_name=True),
                            "delta_path": list(m.metadata.delta_path)} for m in frames(capture) if isinstance(m, ForwardMsg) and m.WhichOneof("type") == "delta"]
    with pytest.raises(AssertionError):
        check_radio_identity(capture)


@pytest.mark.parametrize("root", (PYTHON, RUST), ids=("python", "rust"))
def test_radio_empty_none_and_native_state(root):
    check_radio_identity(read(root / "radio-empty/trace.json"), empty=True)


def test_radio_empty_complete_elements_match_reference():
    captures = [read(root / "radio-empty/trace.json") for root in (PYTHON, RUST)]
    assert captures[0]["producer_sources_sha256"] == captures[1]["producer_sources_sha256"] and captures[1]["semantic_match"] is True
    assert check_radio_identity(captures[0], empty=True) == check_radio_identity(captures[1], empty=True)


def test_radio_empty_before_errors_and_misses_sync():
    capture = read(RUST / "radio-empty/before/trace.json")
    assert capture["successful"] and "producer_error" not in capture and capture["finishes"] == [0] * 14
    assert len(capture["frames"]) == 106 and len(capture["elements"]) == 37 and capture["semantic_match"] is False
    assert capture["cleanup"] == {"websocket_closed": True, "caller_server_stopped": True}
    runs = color_runs(capture, ("radio", "json", "markdown"))
    assert [e[0] for e in runs[2]["entries"]] == ["markdown"]
    assert "value does not match radio" in runs[2]["entries"][0][1].body
    assert runs[10]["entries"][1][1].HasField("default") and not runs[10]["entries"][1][1].set_value
    with pytest.raises(AssertionError):
        check_radio_identity(capture, empty=True)


@pytest.mark.parametrize("mutation", ("disabled-empty", "wire-default", "sync-flag", "raw-value", "restored-value", "stale-input", "unkeyed-id"))
def test_radio_empty_gate_rejects_coherent_wrong_wire(mutation):
    capture = read(PYTHON / "radio-empty/trace.json")
    source = color_runs(capture, ("radio", "json"))
    target = {"disabled-empty": 2, "wire-default": 3, "sync-flag": 2, "raw-value": 12, "restored-value": 5, "stale-input": 7, "unkeyed-id": 4}[mutation]
    run = -1
    for frame in capture["frames"]:
        client = frame["direction"] == "client->server"
        if client:
            run += 1
        if run != target:
            continue
        message = BackMsg() if client else ForwardMsg()
        message.ParseFromString(base64.b64decode(frame["base64"]))
        if client and mutation == "stale-input":
            message.rerun_script.widget_states.widgets[0].id = source[0]["entries"][0][1].id
        elif not client and message.WhichOneof("type") == "delta":
            element = message.delta.new_element
            kind = element.WhichOneof("type")
            if kind == "radio" and mutation == "disabled-empty":
                element.radio.disabled = True
            elif kind == "radio" and element.radio.label == "Keyed choice" and mutation == "wire-default":
                element.radio.default = 0
            elif kind == "radio" and element.radio.label == "Keyed choice" and mutation == "sync-flag":
                element.radio.set_value = False
                element.ClearField("has_one_shot_effect")
            elif kind == "radio" and element.radio.label == "Keyed choice" and mutation == "raw-value":
                element.radio.raw_value = "Missing"
            elif kind == "radio" and element.radio.label == "Choice" and mutation == "unkeyed-id":
                element.radio.id = source[2]["entries"][0][1].id
            elif kind == "json" and mutation == "restored-value":
                report = json.loads(element.json.body)
                report["values"][1] = "Alpha"
                element.json.body = json.dumps(report)
            else:
                continue
        else:
            continue
        raw = message.SerializeToString()
        frame.update(base64=base64.b64encode(raw).decode(), bytes=len(raw), message=MessageToDict(message, preserving_proto_field_name=True))
    capture["elements"] = [{"kind": m.delta.new_element.WhichOneof("type"), "fields": MessageToDict(getattr(m.delta.new_element, m.delta.new_element.WhichOneof("type")), preserving_proto_field_name=True),
                            "delta_path": list(m.metadata.delta_path)} for m in frames(capture) if isinstance(m, ForwardMsg) and m.WhichOneof("type") == "delta"]
    with pytest.raises(AssertionError):
        check_radio_identity(capture, empty=True)


def test_sdk_empty_selectbox_constructor_defaults():
    import importlib.metadata
    from streamlit.testing.v1 import AppTest

    assert importlib.metadata.version("streamlit") == "1.66.1"
    app = AppTest.from_string('''
import streamlit as st
a = st.selectbox("Normal", [])
b = st.selectbox("Creation", [], accept_new_options=True)
st.json([a, b])
''').run()
    assert not app.exception and json.loads(app.json[0].value) == [None, None]
    for creation, widget in zip((False, True), app.selectbox, strict=True):
        assert widget.proto.HasField("default") and widget.proto.default == 0
        assert widget.proto.accept_new_options == creation and not widget.proto.disabled


def test_sdk_integer_options_can_temporarily_return_label_strings():
    """SDK-only boundary: no Rust/native-WS parity claim for dynamic return types."""
    import importlib.metadata
    from streamlit.testing.v1 import AppTest

    assert importlib.metadata.version("streamlit") == "1.66.1"
    app = AppTest.from_string('''
import streamlit as st
if st.session_state.get("assign", False):
    st.session_state["number"] = "2"
value = st.selectbox("Number", [1, 2, 3], key="number")
st.json([value])
''').run()
    assert not app.exception and type(json.loads(app.json[0].value)[0]) is int
    app.session_state["assign"] = True
    app.run()
    assert not app.exception and json.loads(app.json[0].value) == ["2"]
    assert app.selectbox[0].proto.set_value and app.selectbox[0].proto.raw_value == "2"
    app.session_state["assign"] = False
    app.run()
    assert not app.exception and json.loads(app.json[0].value) == [2] and type(json.loads(app.json[0].value)[0]) is int


def check_select_empty(capture):
    assert capture["successful"] and "producer_error" not in capture and capture["reference_version"] == "1.66.1"
    assert capture["runtime"] in ("python", "rust") and capture["finishes"] == [0] * 14
    assert capture["cleanup"]["websocket_closed"] and capture["cleanup"]["server_stopped" if capture["runtime"] == "python" else "caller_server_stopped"]
    assert len(capture["frames"]) == 125 and len(capture["elements"]) == 56
    runs = color_runs(capture, ("selectbox", "json"))
    history, normalized, sessions, run_ids = [], [], set(), set()
    for index, (phase, run) in enumerate(zip(RADIO_EMPTY_PHASES, runs, strict=True)):
        request = run["request"]
        assert request.query_string == "probe=select-empty&phase=" + phase and not request.is_history_navigation
        assert len(run["sessions"]) == 1 and run["finishes"] == [0]
        session = run["sessions"][0]
        assert session.initialize.environment_info.streamlit_version == "1.66.1"
        sessions.add(session.initialize.session_id)
        run_ids.add(session.script_run_id)
        assert [e[0] for e in run["entries"]] == ["selectbox"] * 3 + ["json"]
        ids = []
        for position, (_, widget, element) in enumerate(run["entries"][:3]):
            assert widget.label == ("Choice", "Keyed choice", "Number")[position] and widget.id
            wire_none = phase in ("none", "none-edit", "none-observe", "empty-none") or position > 0 and phase in ("empty-observe", "restore", "assign-none", "observe")
            assert widget.HasField("default") == (not wire_none) and widget.default == 0
            assert list(widget.options) == ([] if phase.startswith("empty") else ["1", "2", "3"] if position == 2 else ["Alpha", "Beta", "Charlie"])
            sync = position > 0 and phase in ("empty", "assign-none", "assign-missing")
            assert widget.set_value == sync and not widget.disabled and not widget.form_id and not widget.help and not widget.ignore_rerun
            assert not widget.accept_new_options and widget.filter_mode == 0 and not widget.query_param_key
            assert widget.label_visibility.value == 0 and element.HasField("has_one_shot_effect") == sync and element.has_one_shot_effect == sync
            raw = ("1" if position == 2 else "Alpha") if sync and phase == "assign-missing" else None
            assert widget.HasField("raw_value") == (raw is not None) and widget.raw_value == (raw or "")
            assert element.width_config.use_stretch
            for earlier in range(index):
                assert (widget.id == history[earlier][position]) == (position > 0 or RADIO_EMPTY_GROUPS[index] == RADIO_EMPTY_GROUPS[earlier]), (phase, position, earlier)
            ids.append(widget.id)
        history.append(ids)
        plain, keyed = RADIO_EMPTY_VALUES[index]
        report = json.loads(run["entries"][3][1].body)
        assert report == {"phase": phase, "values": [plain, keyed, {"Alpha": 1, "Beta": 2, None: None}[keyed]]}
        assert type(report["values"][2]) in (int, type(None)), "integer selections must not become bool, float or string"
        assert [capture["elements"][index * 4 + i]["delta_path"] for i in range(4)] == [[0, i] for i in range(4)]
        incoming = request.widget_states.widgets
        if phase in ("edit", "none-edit"):
            assert len(incoming) == 3 and [w.id for w in incoming] == history[index - 1]
            assert all(w.WhichOneof("value") == "string_value" for w in incoming)
            assert [w.string_value for w in incoming] == ["Beta", "Beta", "2"]
        else:
            assert not incoming
        normalized_run = []
        for kind, _, element in run["entries"]:
            fields = MessageToDict(element, preserving_proto_field_name=True)
            if kind == "selectbox":
                fields[kind].pop("id")
            else:
                fields[kind]["body"] = json.loads(fields[kind]["body"])
            normalized_run.append(fields)
        normalized.append(normalized_run)
    assert len(sessions) == 1 and len(run_ids) == 14
    assert [len({ids[i] for ids in history}) for i in range(3)] == [4, 1, 1]
    return normalized


@pytest.mark.parametrize("root", (PYTHON, RUST), ids=("python", "rust"))
def test_selectbox_empty_and_native_none(root):
    check_select_empty(read(root / "select-empty/trace.json"))


def test_selectbox_empty_complete_elements_match_reference():
    captures = [read(root / "select-empty/trace.json") for root in (PYTHON, RUST)]
    assert captures[0]["producer_sources_sha256"] == captures[1]["producer_sources_sha256"] and captures[1]["semantic_match"] is True
    assert check_select_empty(captures[0]) == check_select_empty(captures[1])


def test_selectbox_empty_before_errors_and_forces_empty_disabled():
    capture = read(RUST / "select-empty/before/trace.json")
    assert capture["successful"] and "producer_error" not in capture and capture["finishes"] == [0] * 14
    assert len(capture["frames"]) == 121 and len(capture["elements"]) == 52 and capture["semantic_match"] is False
    assert capture["cleanup"] == {"websocket_closed": True, "caller_server_stopped": True}
    runs = color_runs(capture, ("selectbox", "json", "markdown"))
    assert [e[0] for e in runs[2]["entries"]] == ["selectbox", "markdown"]
    assert runs[2]["entries"][0][1].disabled and not runs[2]["entries"][0][1].HasField("default")
    assert "session value is absent from selectbox options" in runs[2]["entries"][1][1].body
    with pytest.raises(AssertionError):
        check_select_empty(capture)


@pytest.mark.parametrize("mutation", ("disabled-empty", "wire-default", "sync-flag", "raw-value", "restored-value", "stale-input", "unkeyed-id", "numeric-type"))
def test_selectbox_empty_gate_rejects_coherent_wrong_wire(mutation):
    capture = read(PYTHON / "select-empty/trace.json")
    source = color_runs(capture, ("selectbox", "json"))
    target = {"disabled-empty": 2, "wire-default": 3, "sync-flag": 2, "raw-value": 12, "restored-value": 5, "stale-input": 7, "unkeyed-id": 4, "numeric-type": 0}[mutation]
    run = -1
    for frame in capture["frames"]:
        client = frame["direction"] == "client->server"
        if client:
            run += 1
        if run != target:
            continue
        message = BackMsg() if client else ForwardMsg()
        message.ParseFromString(base64.b64decode(frame["base64"]))
        if client and mutation == "stale-input":
            message.rerun_script.widget_states.widgets[0].id = source[0]["entries"][0][1].id
        elif not client and message.WhichOneof("type") == "delta":
            element = message.delta.new_element
            kind = element.WhichOneof("type")
            if kind == "selectbox" and mutation == "disabled-empty":
                element.selectbox.disabled = True
            elif kind == "selectbox" and element.selectbox.label == "Keyed choice" and mutation == "wire-default":
                element.selectbox.default = 0
            elif kind == "selectbox" and element.selectbox.label == "Keyed choice" and mutation == "sync-flag":
                element.selectbox.set_value = False
                element.ClearField("has_one_shot_effect")
            elif kind == "selectbox" and element.selectbox.label == "Number" and mutation == "raw-value":
                element.selectbox.raw_value = "99"
            elif kind == "selectbox" and element.selectbox.label == "Choice" and mutation == "unkeyed-id":
                element.selectbox.id = source[2]["entries"][0][1].id
            elif kind == "json" and mutation in ("restored-value", "numeric-type"):
                report = json.loads(element.json.body)
                report["values"][2] = 1 if mutation == "restored-value" else 1.0
                element.json.body = json.dumps(report)
            else:
                continue
        else:
            continue
        raw = message.SerializeToString()
        frame.update(base64=base64.b64encode(raw).decode(), bytes=len(raw), message=MessageToDict(message, preserving_proto_field_name=True))
    capture["elements"] = [{"kind": m.delta.new_element.WhichOneof("type"), "fields": MessageToDict(getattr(m.delta.new_element, m.delta.new_element.WhichOneof("type")), preserving_proto_field_name=True),
                            "delta_path": list(m.metadata.delta_path)} for m in frames(capture) if isinstance(m, ForwardMsg) and m.WhichOneof("type") == "delta"]
    with pytest.raises(AssertionError):
        check_select_empty(capture)


def test_sdk_multiselect_can_temporarily_return_mixed_native_label_types():
    """SDK-only dynamic return boundary; typed Rust Vec<T> remains unresolved."""
    import importlib.metadata
    from streamlit.testing.v1 import AppTest

    assert importlib.metadata.version("streamlit") == "1.66.1"
    app = AppTest.from_string('''
import streamlit as st
if st.session_state.get("assign", False):
    st.session_state["number"] = ["2", 2, 99]
value = st.multiselect("Number", [1, 2, 3], key="number")
st.json([value])
''').run()
    app.session_state["assign"] = True
    app.run()
    assert not app.exception and json.loads(app.json[0].value) == [["2", 2]]
    assert app.multiselect[0].proto.set_value and list(app.multiselect[0].proto.raw_values) == ["2", "2"]
    app.session_state["assign"] = False
    app.run()
    assert not app.exception and json.loads(app.json[0].value) == [[2, 2]]
    assert all(type(n) is int for n in json.loads(app.json[0].value)[0])


def test_sdk_multiselect_none_assignment_errors_until_repaired():
    """SDK-only public error observation, not a Rust error-rendering parity gate."""
    import importlib.metadata
    from streamlit.testing.v1 import AppTest

    assert importlib.metadata.version("streamlit") == "1.66.1"
    app = AppTest.from_string('''
import streamlit as st
phase = st.session_state.get("phase", "load")
if phase == "assign-none":
    st.session_state["choice"] = None
elif phase == "repair":
    st.session_state["choice"] = []
value = st.multiselect("Choice", ["Alpha", "Beta"], key="choice")
st.json([value])
''').run()
    assert not app.exception and json.loads(app.json[0].value) == [[]]
    for phase in ("assign-none", "observe"):
        app.session_state["phase"] = phase
        app.run()
        assert len(app.exception) == 1 and app.exception[0].message == "'NoneType' object is not iterable"
        assert not app.json and not app.multiselect
    app.session_state["phase"] = "repair"
    app.run()
    assert not app.exception and json.loads(app.json[0].value) == [[]]


MULTI_EMPTY_PHASES = ("load", "edit", "subset", "reorder", "restore", "assign-partial", "observe", "assign-repeat", "repeat-observe", "empty", "empty-observe", "restore-final")
MULTI_EMPTY_GROUPS = (0, 0, 1, 2, 0, 0, 0, 0, 0, 3, 3, 0)
MULTI_EMPTY_NUMBERS = ([], [1, 2], [2], [2], [2], [2, 3], [2, 3], [2, 2], [2, 2], [], [], [])


def check_multi_empty(capture):
    assert capture["successful"] and "producer_error" not in capture and capture["reference_version"] == "1.66.1"
    assert capture["runtime"] in ("python", "rust") and capture["finishes"] == [0] * 12
    assert capture["cleanup"]["websocket_closed"] and capture["cleanup"]["server_stopped" if capture["runtime"] == "python" else "caller_server_stopped"]
    assert len(capture["frames"]) == 107 and len(capture["elements"]) == 48
    runs = color_runs(capture, ("multiselect", "json"))
    history, normalized, sessions, run_ids = [], [], set(), set()
    names = {1: "Alpha", 2: "Beta", 3: "Charlie"}
    for index, (phase, run) in enumerate(zip(MULTI_EMPTY_PHASES, runs, strict=True)):
        request = run["request"]
        assert request.query_string == "probe=multi-empty&phase=" + phase and not request.is_history_navigation
        assert len(run["sessions"]) == 1 and run["finishes"] == [0]
        session = run["sessions"][0]
        assert session.initialize.environment_info.streamlit_version == "1.66.1"
        sessions.add(session.initialize.session_id)
        run_ids.add(session.script_run_id)
        assert [e[0] for e in run["entries"]] == ["multiselect"] * 3 + ["json"]
        numbers = {"subset": [2, 3], "reorder": [3, 2, 1], "empty": [], "empty-observe": []}.get(phase, [1, 2, 3])
        expected = MULTI_EMPTY_NUMBERS[index]
        ids = []
        for position, (_, widget, element) in enumerate(run["entries"][:3]):
            assert widget.label == ("Choice", "Keyed choice", "Number")[position] and widget.id
            assert list(widget.options) == [str(n) if position == 2 else names[n] for n in numbers]
            sync = position > 0 and phase in ("subset", "assign-partial", "assign-repeat", "empty")
            assert widget.set_value == sync and not widget.disabled and not widget.default
            assert not widget.form_id and not widget.help and not widget.ignore_rerun and not widget.max_selections
            assert not widget.accept_new_options and widget.filter_mode == 0 and not widget.query_param_key and not widget.placeholder
            assert widget.select_all == 1000 and not widget.HasField("wrap")
            assert widget.label_visibility.value == 0 and element.HasField("has_one_shot_effect") == sync and element.has_one_shot_effect == sync
            assert list(widget.raw_values) == ([str(n) if position == 2 else names[n] for n in expected] if sync else [])
            assert element.width_config.use_stretch
            for earlier in range(index):
                assert (widget.id == history[earlier][position]) == (position > 0 or MULTI_EMPTY_GROUPS[index] == MULTI_EMPTY_GROUPS[earlier]), (phase, position, earlier)
            ids.append(widget.id)
        history.append(ids)
        plain = ["Alpha", "Beta"] if phase == "edit" else []
        report = json.loads(run["entries"][3][1].body)
        assert report == {"phase": phase, "values": [plain, [names[n] for n in expected], expected]}
        assert all(type(n) is int for n in report["values"][2]), "integer selections must retain their native type"
        assert [capture["elements"][index * 4 + i]["delta_path"] for i in range(4)] == [[0, i] for i in range(4)]
        incoming = request.widget_states.widgets
        if phase == "edit":
            assert len(incoming) == 3 and [w.id for w in incoming] == history[index - 1]
            assert all(w.WhichOneof("value") == "string_array_value" for w in incoming)
            assert [list(w.string_array_value.data) for w in incoming] == [["Alpha", "Beta"], ["Alpha", "Beta"], ["1", "2"]]
        else:
            assert not incoming
        normalized_run = []
        for kind, _, element in run["entries"]:
            fields = MessageToDict(element, preserving_proto_field_name=True)
            if kind == "multiselect":
                fields[kind].pop("id")
            else:
                fields[kind]["body"] = json.loads(fields[kind]["body"])
            normalized_run.append(fields)
        normalized.append(normalized_run)
    assert len(sessions) == 1 and len(run_ids) == 12
    assert [len({ids[i] for ids in history}) for i in range(3)] == [4, 1, 1]
    return normalized


@pytest.mark.parametrize("root", (PYTHON, RUST), ids=("python", "rust"))
def test_multiselect_empty_and_filtered_native_state(root):
    check_multi_empty(read(root / "multi-empty/trace.json"))


def test_multiselect_empty_complete_elements_match_reference():
    captures = [read(root / "multi-empty/trace.json") for root in (PYTHON, RUST)]
    assert captures[0]["producer_sources_sha256"] == captures[1]["producer_sources_sha256"] and captures[1]["semantic_match"] is True
    assert check_multi_empty(captures[0]) == check_multi_empty(captures[1])


def test_multiselect_empty_before_errors_and_forces_disabled():
    capture = read(RUST / "multi-empty/before/trace.json")
    assert capture["successful"] and capture["finishes"] == [0] * 12 and capture["semantic_match"] is False
    assert len(capture["frames"]) == 101 and len(capture["elements"]) == 42
    assert capture["cleanup"] == {"websocket_closed": True, "caller_server_stopped": True}
    runs = color_runs(capture, ("multiselect", "json", "markdown"))
    assert [e[0] for e in runs[2]["entries"]] == ["multiselect", "markdown"]
    assert "session value is absent from multiselect options" in runs[2]["entries"][1][1].body
    assert runs[9]["entries"][0][1].disabled
    with pytest.raises(AssertionError):
        check_multi_empty(capture)


@pytest.mark.parametrize("mutation", ("disabled-empty", "sync-flag", "raw-order", "raw-repeat", "returned-repeat", "stale-input", "unkeyed-id", "numeric-type"))
def test_multiselect_empty_gate_rejects_coherent_wrong_wire(mutation):
    capture = read(PYTHON / "multi-empty/trace.json")
    source = color_runs(capture, ("multiselect", "json"))
    target = {"disabled-empty": 9, "sync-flag": 2, "raw-order": 5, "raw-repeat": 7, "returned-repeat": 8, "stale-input": 1, "unkeyed-id": 3, "numeric-type": 1}[mutation]
    run = -1
    for frame in capture["frames"]:
        client = frame["direction"] == "client->server"
        if client:
            run += 1
        if run != target:
            continue
        message = BackMsg() if client else ForwardMsg()
        message.ParseFromString(base64.b64decode(frame["base64"]))
        if client and mutation == "stale-input":
            message.rerun_script.widget_states.widgets[0].id = "$$ID-stale-None"
        elif not client and message.WhichOneof("type") == "delta":
            element = message.delta.new_element
            kind = element.WhichOneof("type")
            if kind == "multiselect" and mutation == "disabled-empty":
                element.multiselect.disabled = True
            elif kind == "multiselect" and element.multiselect.label == "Keyed choice" and mutation == "sync-flag":
                element.multiselect.set_value = False
                element.ClearField("has_one_shot_effect")
            elif kind == "multiselect" and element.multiselect.label == "Keyed choice" and mutation in ("raw-order", "raw-repeat"):
                element.multiselect.raw_values[:] = ["Charlie", "Beta"] if mutation == "raw-order" else ["Beta"]
            elif kind == "multiselect" and element.multiselect.label == "Choice" and mutation == "unkeyed-id":
                element.multiselect.id = source[2]["entries"][0][1].id
            elif kind == "json" and mutation in ("returned-repeat", "numeric-type"):
                report = json.loads(element.json.body)
                report["values"][2] = [2] if mutation == "returned-repeat" else [1.0, 2]
                element.json.body = json.dumps(report)
            else:
                continue
        else:
            continue
        raw = message.SerializeToString()
        frame.update(base64=base64.b64encode(raw).decode(), bytes=len(raw), message=MessageToDict(message, preserving_proto_field_name=True))
    capture["elements"] = [{"kind": m.delta.new_element.WhichOneof("type"), "fields": MessageToDict(getattr(m.delta.new_element, m.delta.new_element.WhichOneof("type")), preserving_proto_field_name=True),
                            "delta_path": list(m.metadata.delta_path)} for m in frames(capture) if isinstance(m, ForwardMsg) and m.WhichOneof("type") == "delta"]
    with pytest.raises(AssertionError):
        check_multi_empty(capture)


MULTI_LIMIT_PHASES = ("load", "over", "observe", "repair", "repair-observe", "edit-limit", "partial", "repair-final")


def multi_limit_count_message(count, limit):
    return (f"Multiselect has {count} options selected but `max_selections` is set to {limit}. "
            "This happened because you either gave too many options to `default` or you manipulated the widget's state through `st.session_state`. "
            "Note that the latter can happen before the line indicated in the traceback. "
            f"Please select at most {limit} option{'s' if limit != 1 else ''}.")


def multi_limit_reports(capture):
    runs = color_runs(capture, ("multiselect", "json"))
    reports = []
    for phase, run in zip(MULTI_LIMIT_PHASES, runs, strict=True):
        assert run["request"].query_string == "probe=multi-limits&phase=" + phase
        assert not run["request"].is_history_navigation and run["finishes"] == [0]
        reports.append({json.loads(widget.body)["case"]: json.loads(widget.body) for kind, widget, _ in run["entries"] if kind == "json"})
        for report in reports[-1].values():
            if report["accepted"]:
                assert all(type(value) is int for value in report["value"])
    return runs, reports


def check_multi_limits_sdk(capture):
    assert capture["runtime"] == "python" and capture["reference_version"] == "1.66.1" and capture["successful"]
    assert "producer_error" not in capture and capture["finishes"] == [0] * 8
    assert capture["cleanup"] == {"websocket_closed": True, "server_stopped": True}
    assert len(capture["frames"]) == 61 and len(capture["elements"]) == 22
    runs, reports = multi_limit_reports(capture)
    load = reports[0]
    assert list(load) == ["Repeat", "Repeat long", "Repeat capped", "Default over", "Zero", "Outside", "State"]
    for label, values in (("Repeat", [2, 2]), ("Repeat long", [2, 2, 2, 2]), ("Repeat capped", [2, 2]), ("State", [2])):
        assert load[label] == {"case": label, "phase": "load", "accepted": True, "value": values}
    errors = {
        "Default over": ("StreamlitSelectionCountExceedsMaxError", multi_limit_count_message(2, 1)),
        "Zero": ("StreamlitValueError", "Invalid `max_selections` value. Supported values: a positive integer. To disable `st.multiselect`, use `disabled=True`."),
        "Outside": ("StreamlitDefaultNotInOptionsError", "The default value '4' is not part of the options. Please make sure that every default value also exists in the options."),
    }
    for label, (kind, message) in errors.items():
        assert load[label] == {"case": label, "phase": "load", "accepted": False, "error_type": kind, "error": message}
    widgets = [w for kind, w, _ in runs[0]["entries"] if kind == "multiselect"]
    assert [w.label for w in widgets] == ["Repeat", "Repeat long", "Repeat capped", "State"]
    assert [list(w.default) for w in widgets] == [[1, 1], [1, 1, 1, 1], [1, 1], [1]]
    assert [w.max_selections for w in widgets] == [0, 0, 2, 2]
    state_id = widgets[-1].id
    sessions, run_ids = set(), set()
    for index, (phase, run) in enumerate(zip(MULTI_LIMIT_PHASES, runs, strict=True)):
        assert len(run["sessions"]) == 1
        session = run["sessions"][0]
        assert session.initialize.environment_info.streamlit_version == "1.66.1"
        sessions.add(session.initialize.session_id)
        run_ids.add(session.script_run_id)
        incoming = run["request"].widget_states.widgets
        if phase in ("over", "edit-limit"):
            assert len(incoming) == 1 and incoming[0].id == state_id and incoming[0].WhichOneof("value") == "string_array_value"
            assert list(incoming[0].string_array_value.data) == (["1", "2", "3"] if phase == "over" else ["1", "3"])
        else:
            assert not incoming
        failed = phase in ("over", "observe", "partial")
        if index:
            assert list(reports[index]) == ["State"]
            assert [kind for kind, _, _ in run["entries"]] == (["json"] if failed else ["multiselect", "json"])
            if failed:
                assert reports[index]["State"] == {"case": "State", "phase": phase, "accepted": False,
                    "error_type": "StreamlitSelectionCountExceedsMaxError", "error": multi_limit_count_message(3, 2)}
            else:
                assert reports[index]["State"] == {"case": "State", "phase": phase, "accepted": True, "value": [1, 3] if phase == "edit-limit" else [2]}
        for kind, widget, element in run["entries"]:
            if kind != "multiselect":
                continue
            assert list(widget.options) == ["1", "2", "3"] and not widget.disabled
            assert widget.select_all == 1000 and widget.HasField("accept_new_options") and not widget.accept_new_options
            assert widget.label_visibility.value == 0 and element.width_config.use_stretch
            sync = phase in ("repair", "repair-final")
            assert widget.set_value == sync and list(widget.raw_values) == (["2"] if sync else [])
            assert element.HasField("has_one_shot_effect") == sync and element.has_one_shot_effect == sync
            if widget.label == "State":
                assert widget.id == state_id and list(widget.default) == [1] and widget.max_selections == 2
    offset = 0
    for run in runs:
        count = len(run["entries"])
        assert [e["delta_path"] for e in capture["elements"][offset:offset + count]] == [[0, i] for i in range(count)]
        offset += count
    assert len(sessions) == 1 and len(run_ids) == 8


def test_multiselect_limit_sdk_errors_and_recovery():
    check_multi_limits_sdk(read(PYTHON / "multi-limits/trace.json"))


def test_multiselect_duplicate_defaults_and_zero_limit_fixed_subset():
    sdk, rust = [read(root / "multi-limits/trace.json") for root in (PYTHON, RUST)]
    check_multi_limits_sdk(sdk)
    assert rust["successful"] and rust["cleanup"] == {"websocket_closed": True, "caller_server_stopped": True}
    assert rust["producer_sources_sha256"] == sdk["producer_sources_sha256"]
    runs, reports = multi_limit_reports(rust)
    assert len(rust["frames"]) == 65 and len(rust["elements"]) == 26
    assert rust["semantic_match"] is False, "count-error flow is still pending"
    sdk_runs, sdk_reports = multi_limit_reports(sdk)
    for label in ("Repeat", "Repeat long", "Repeat capped"):
        assert reports[0][label] == sdk_reports[0][label]
        fields = []
        for current in (sdk_runs, runs):
            element = next(e for kind, w, e in current[0]["entries"] if kind == "multiselect" and w.label == label)
            view = MessageToDict(element, preserving_proto_field_name=True)
            view["multiselect"].pop("id")
            fields.append(view)
        assert fields[0] == fields[1]
    for label, message in (("Zero", "multiselect max_selections must be positive"), ("Outside", "multiselect defaults must be indices inside options")):
        assert reports[0][label] == {"case": label, "phase": "load", "accepted": False, "error_type": "InvalidValue", "error": "invalid widget value: " + message}
        assert not any(kind == "multiselect" and w.label == label for kind, w, _ in runs[0]["entries"])
    # Preserve the actual remaining discrepancy, rather than relabeling this as full parity.
    assert reports[0]["Default over"]["accepted"] is True
    assert all(reports[i]["State"]["accepted"] is True for i in (1, 2, 6))
    with pytest.raises(AssertionError):
        check_multi_limits_sdk(rust)


def test_multiselect_limit_before_rejects_duplicates_and_accepts_zero():
    capture = read(RUST / "multi-limits/before/trace.json")
    assert capture["successful"] and capture["finishes"] == [0] * 8 and capture["semantic_match"] is False
    assert len(capture["frames"]) == 63 and len(capture["elements"]) == 24
    runs, reports = multi_limit_reports(capture)
    assert all(reports[0][label]["accepted"] is False for label in ("Repeat", "Repeat long", "Repeat capped"))
    assert reports[0]["Zero"]["accepted"] is True
    assert any(kind == "multiselect" and w.label == "Zero" for kind, w, _ in runs[0]["entries"])


@pytest.mark.parametrize("mutation", ("default-repeat", "returned-repeat", "zero-accepted", "input-id", "repair-sync", "count-after-filter", "persistent-error"))
def test_multiselect_limit_reference_rejects_coherent_wrong_evidence(mutation):
    capture = read(PYTHON / "multi-limits/trace.json")
    target = {"default-repeat": 0, "returned-repeat": 0, "zero-accepted": 0, "input-id": 1, "repair-sync": 3, "count-after-filter": 6, "persistent-error": 2}[mutation]
    run = -1
    for frame in capture["frames"]:
        client = frame["direction"] == "client->server"
        if client:
            run += 1
        if run != target:
            continue
        message = BackMsg() if client else ForwardMsg()
        message.ParseFromString(base64.b64decode(frame["base64"]))
        if client and mutation == "input-id":
            message.rerun_script.widget_states.widgets[0].id = "$$ID-stale-limited"
        elif not client and message.WhichOneof("type") == "delta":
            element = message.delta.new_element
            kind = element.WhichOneof("type")
            if kind == "multiselect" and mutation == "default-repeat" and element.multiselect.label == "Repeat":
                element.multiselect.default[:] = [1]
            elif kind == "multiselect" and mutation == "repair-sync":
                element.multiselect.set_value = False
                element.ClearField("has_one_shot_effect")
            elif kind == "json":
                report = json.loads(element.json.body)
                if mutation == "returned-repeat" and report["case"] == "Repeat":
                    report["value"] = [2]
                elif mutation == "zero-accepted" and report["case"] == "Zero":
                    report = {"case": "Zero", "phase": "load", "accepted": True, "value": []}
                elif mutation in ("count-after-filter", "persistent-error") and report["case"] == "State":
                    report = {"case": "State", "phase": MULTI_LIMIT_PHASES[target], "accepted": True, "value": [2]}
                else:
                    continue
                element.json.body = json.dumps(report)
            else:
                continue
        else:
            continue
        raw = message.SerializeToString()
        frame.update(base64=base64.b64encode(raw).decode(), bytes=len(raw), message=MessageToDict(message, preserving_proto_field_name=True))
    capture["elements"] = [{"kind": m.delta.new_element.WhichOneof("type"), "fields": MessageToDict(getattr(m.delta.new_element, m.delta.new_element.WhichOneof("type")), preserving_proto_field_name=True),
                            "delta_path": list(m.metadata.delta_path)} for m in frames(capture) if isinstance(m, ForwardMsg) and m.WhichOneof("type") == "delta"]
    with pytest.raises(AssertionError):
        check_multi_limits_sdk(capture)


EMPTY_SELECT_UI_NAMES = ("01-none-load", "02-keyed-options", "03-keyed-Beta", "04-number-options", "05-number-2", "06-plain-options", "07-plain-Alpha", "08-plain-clear", "09-keyed-clear", "10-number-clear")
EMPTY_SELECT_UI_VALUES = ((None, None, None), (None, "Beta", None), (None, "Beta", 2), ("Alpha", "Beta", 2), (None, "Beta", 2), (None, None, 2), (None, None, None))
EMPTY_SELECT_UI_STAGE_RUN = (0, 0, 1, 1, 2, 2, 3, 4, 5, 6)


def check_empty_select_ui(capture, folder, *, before=False):
    import hashlib
    from PIL import Image

    assert capture["runtime"] in ("python", "rust") and capture["reference_version"] == "1.66.1"
    assert capture["successful"] and capture["complete"] and capture["semantic_match"] == (not before)
    assert capture["cleanup"] == {"tab_closed": True, "network_capture_disabled": True, "server_stopped": True}
    assert capture["console"] == [] and capture["visual_review"]["original_jpegs_inspected"] == 10
    assert len(capture["producer_sources_sha256"]) == 2 and all(re.fullmatch(r"[0-9a-f]{64}", h) for h in capture["producer_sources_sha256"].values())
    events = capture["events"]
    assert len(events) == 64 and events[0]["method"] == "Network.webSocketCreated"
    assert events[0]["params"]["url"] == capture["url"].split("/?")[0].replace("http:", "ws:") + "/_stcore/stream"
    ws_id = events[0]["params"]["requestId"]
    messages, sequence = {}, -1
    for index, event in enumerate(events):
        assert event["sequence"] > sequence and event["source"]["tabId"] == int(capture["tab_id"])
        sequence = event["sequence"]
        if index == 0:
            continue
        assert event["method"] in ("Network.webSocketFrameSent", "Network.webSocketFrameReceived")
        assert event["params"]["requestId"] == ws_id and event["params"]["response"]["opcode"] == 2
        message = BackMsg() if event["method"].endswith("Sent") else ForwardMsg()
        message.ParseFromString(base64.b64decode(event["params"]["response"]["payloadData"], validate=True))
        messages[index] = message
    assert len(messages) == 63
    stages = capture["snapshots"]
    assert [s["name"] for s in stages] == list(EMPTY_SELECT_UI_NAMES)
    normalized, sessions, run_ids, widget_ids, boundary = [], set(), set(), None, 0
    for index, stage in enumerate(stages):
        start, end = stage["event_range"]
        assert start == boundary and end - start == (10 if index == 0 else 0 if index in (1, 3, 5) else 9)
        boundary = end
        run = EMPTY_SELECT_UI_STAGE_RUN[index]
        expected = EMPTY_SELECT_UI_VALUES[run]
        returned = ((None, None, None) if run < 3 else ("Alpha", "Beta", 2)) if before else expected
        dom = stage["dom"]
        height = 724 if before else 780
        assert dom["viewport"] == {"width": 1463, "height": height, "dpr": 1.75}
        assert dom["inputs"] == [{"label": label, "value": "" if value is None else str(value), "disabled": False, "placeholder": "Choose an option"}
                                   for label, value in zip(("Choice", "Keyed choice", "Number"), expected, strict=True)]
        assert dom["options"] == (["1", "2", "3"] if index == 3 else ["Alpha", "Beta", "Charlie"] if index in (1, 5) else [])
        assert sum(button["label"] == "Clear value" for button in dom["buttons"]) == sum(value is not None for value in expected)
        compact = re.sub(r"\s+", "", dom["body"])
        result_text = "".join(f"{i}:" + ("NULL" if value is None else json.dumps(value)) for i, value in enumerate(returned))
        assert '"phase":"none"' in compact and '"values":[' + result_text + ']' in compact
        assert stage["action_and_capture_calls_separate"] and stage["screenshot"] == stage["name"] + ".jpg"
        data = (folder / stage["screenshot"]).read_bytes()
        assert len(data) == stage["screenshot_bytes"] and hashlib.sha256(data).hexdigest() == stage["screenshot_sha256"]
        with Image.open(folder / stage["screenshot"]) as image:
            assert image.format == stage["screenshot_format"] == "JPEG" and list(image.size) == stage["screenshot_dimensions"] == [1463, height]
            if index not in (1, 3, 5):
                rgb = image.convert("RGB")
                bright = sum(min(rgb.getpixel((x, y))) > 110 for x in range(388, 551) for y in range(302, 322))
                assert bright > 200 if expected[2] is None else bright < 80
        batch = [messages[i] for i in range(start, end) if i in messages]
        if index in (1, 3, 5):
            assert not batch
            continue
        assert [m.WhichOneof("type") for m in batch] == ["rerun_script", "new_session", "session_status_changed"] + ["delta"] * 4 + ["script_finished", "session_status_changed"]
        request, session = batch[0].rerun_script, batch[1].new_session
        assert request.query_string == "probe=select-empty&phase=none" and not request.is_history_navigation
        assert session.initialize.environment_info.streamlit_version == "1.66.1"
        sessions.add(session.initialize.session_id)
        run_ids.add(session.script_run_id)
        assert batch[2].session_status_changed.script_is_running and batch[7].script_finished == 0 and not batch[8].session_status_changed.script_is_running
        elements = [m.delta.new_element for m in batch[3:7]]
        assert [m.delta.WhichOneof("type") for m in batch[3:7]] == ["new_element"] * 4
        assert [list(m.metadata.delta_path) for m in batch[3:7]] == [[0, i] for i in range(4)]
        assert [e.WhichOneof("type") for e in elements] == ["selectbox"] * 3 + ["json"]
        ids = [e.selectbox.id for e in elements[:3]]
        if run == 0:
            assert not request.widget_states.widgets and len(set(ids)) == 3
            widget_ids = ids
        else:
            incoming = request.widget_states.widgets
            assert ids == widget_ids and len(incoming) == 3 and [w.id for w in incoming] == ids
            for widget, value in zip(incoming, expected, strict=True):
                assert widget.WhichOneof("value") == (None if value is None else "string_value")
                if value is not None:
                    assert widget.string_value == str(value)
        for position, element in enumerate(elements[:3]):
            widget = element.selectbox
            assert widget.label == ("Choice", "Keyed choice", "Number")[position]
            assert list(widget.options) == (["1", "2", "3"] if position == 2 else ["Alpha", "Beta", "Charlie"])
            assert not widget.HasField("default") and not widget.disabled and not widget.set_value and not widget.HasField("raw_value")
            assert not element.HasField("has_one_shot_effect") and element.width_config.use_stretch
        report = json.loads(elements[-1].json.body)
        assert report == {"phase": "none", "values": list(returned)}
        assert type(report["values"][2]) in (int, type(None))
        fields = [MessageToDict(element, preserving_proto_field_name=True) for element in elements]
        for field in fields[:3]:
            field["selectbox"].pop("id")
        fields[-1]["json"]["body"] = report
        normalized.append(fields)
    assert boundary == len(events) and len(normalized) == 7 and len(sessions) == 1 and len(run_ids) == 7
    return normalized


@pytest.mark.parametrize("root", (PYTHON, RUST), ids=("python", "rust"))
def test_selectbox_empty_ui_real_selection_and_clear(root):
    folder = root / "select-empty/ui"
    check_empty_select_ui(read(folder / "trace.json"), folder)


def test_selectbox_empty_ui_complete_elements_match_reference():
    folders = [root / "select-empty/ui" for root in (PYTHON, RUST)]
    captures = [read(folder / "trace.json") for folder in folders]
    assert captures[0]["producer_sources_sha256"] == captures[1]["producer_sources_sha256"]
    assert check_empty_select_ui(captures[0], folders[0]) == check_empty_select_ui(captures[1], folders[1])


def test_selectbox_empty_ui_before_loses_input_and_keeps_stale_backend_values():
    folder = RUST / "select-empty/ui/before"
    capture = read(folder / "trace.json")
    before = check_empty_select_ui(capture, folder, before=True)
    sdk_folder = PYTHON / "select-empty/ui"
    assert before != check_empty_select_ui(read(sdk_folder / "trace.json"), sdk_folder)
    with pytest.raises(AssertionError):
        check_empty_select_ui(capture, folder)


@pytest.mark.parametrize("creation", (False, True))
@pytest.mark.parametrize("default", (None, 0))
def test_sdk_selectbox_id_only_payload_uses_registered_default(creation, default):
    import importlib.metadata
    from streamlit.testing.v1 import AppTest

    assert importlib.metadata.version("streamlit") == "1.66.1"
    app = AppTest.from_string('import streamlit as st\nv=st.selectbox("Choice",["Alpha","Beta"],key="choice",index=' + repr(default) + ',accept_new_options=' + repr(creation) + ')\nst.json([v])').run()
    app.selectbox[0].set_value("Beta")
    app.run()
    assert not app.exception and json.loads(app.json[0].value) == ["Beta"]
    app.selectbox[0].set_value(None)
    app.run()
    assert not app.exception and json.loads(app.json[0].value) == ([None] if default is None else ["Alpha"])


@pytest.mark.parametrize("mutation", ("menu-send", "empty-oneof", "return-type", "clear-revert", "wire-default", "screenshot", "old-image", "options"))
def test_selectbox_empty_ui_gate_rejects_wrong_wire_or_picture(mutation, tmp_path):
    import hashlib

    folder = PYTHON / "select-empty/ui"
    capture = read(folder / "trace.json")
    if mutation == "menu-send":
        capture["snapshots"][1]["event_range"][1] += 1
    elif mutation == "options":
        capture["snapshots"][1]["dom"]["options"] = ["Beta"]
    elif mutation == "screenshot":
        capture["snapshots"][-1]["screenshot_sha256"] = "wrong"
    elif mutation == "old-image":
        for stage in capture["snapshots"]:
            (tmp_path / stage["screenshot"]).write_bytes((folder / stage["screenshot"]).read_bytes())
        data = (folder / capture["snapshots"][4]["screenshot"]).read_bytes()
        stage = capture["snapshots"][-1]
        (tmp_path / stage["screenshot"]).write_bytes(data)
        stage.update(screenshot_bytes=len(data), screenshot_sha256=hashlib.sha256(data).hexdigest())
        folder = tmp_path
    else:
        stage = capture["snapshots"][4 if mutation == "return-type" else 9 if mutation == "clear-revert" else 2]
        for event in capture["events"][slice(*stage["event_range"])]:
            if event["method"] not in ("Network.webSocketFrameSent", "Network.webSocketFrameReceived"):
                continue
            message = BackMsg() if event["method"].endswith("Sent") else ForwardMsg()
            message.ParseFromString(base64.b64decode(event["params"]["response"]["payloadData"]))
            if mutation == "empty-oneof" and isinstance(message, BackMsg):
                message.rerun_script.widget_states.widgets[0].bool_value = False
            elif message.WhichOneof("type") == "delta":
                element = message.delta.new_element
                if mutation == "wire-default" and element.WhichOneof("type") == "selectbox":
                    element.selectbox.default = 0
                elif mutation in ("return-type", "clear-revert") and element.WhichOneof("type") == "json":
                    report = json.loads(element.json.body)
                    report["values"][2] = 2.0 if mutation == "return-type" else 2
                    element.json.body = json.dumps(report)
                    if mutation == "clear-revert":
                        stage["dom"]["body"] = stage["dom"]["body"].replace("2:NULL", "2:2")
                else:
                    continue
            else:
                continue
            event["params"]["response"]["payloadData"] = base64.b64encode(message.SerializeToString()).decode()
    with pytest.raises(AssertionError):
        check_empty_select_ui(capture, folder)


RADIO_NONE_UI_NAMES = ("01-none-load", "02-keyed-Alpha", "03-keyed-Beta", "04-plain-Alpha", "05-keyed-Alpha")
RADIO_NONE_UI_VALUES = ((None, None), (None, "Alpha"), (None, "Beta"), ("Alpha", "Beta"), ("Alpha", "Alpha"))


def check_radio_none_ui(capture, folder, *, before=False):
    import hashlib
    from PIL import Image

    assert capture["reference_version"] == "1.66.1" and capture["runtime"] in ("python", "rust")
    assert capture["successful"] and capture["complete"] and capture["semantic_match"] == (not before)
    assert capture["cleanup"] == {"tab_closed": True, "network_capture_disabled": True, "server_stopped": True}
    assert capture["console"] == [] and capture["visual_review"]["original_jpegs_inspected"] == 5
    assert len(capture["producer_sources_sha256"]) == 2 and all(re.fullmatch(r"[0-9a-f]{64}", h) for h in capture["producer_sources_sha256"].values())
    events = capture["events"]
    assert len(events) == 41 and events[0]["method"] == "Network.webSocketCreated"
    assert events[0]["params"]["url"] == capture["url"].split("/?")[0].replace("http:", "ws:") + "/_stcore/stream"
    ws_id = events[0]["params"]["requestId"]
    messages, sequence = {}, -1
    for index, event in enumerate(events):
        assert event["sequence"] > sequence and event["source"]["tabId"] == int(capture["tab_id"])
        sequence = event["sequence"]
        if index == 0:
            continue
        assert event["method"] in ("Network.webSocketFrameSent", "Network.webSocketFrameReceived")
        assert event["params"]["requestId"] == ws_id and event["params"]["response"]["opcode"] == 2
        message = BackMsg() if event["method"].endswith("Sent") else ForwardMsg()
        message.ParseFromString(base64.b64decode(event["params"]["response"]["payloadData"], validate=True))
        messages[index] = message
    assert len(messages) == 40
    stages = capture["snapshots"]
    assert [stage["name"] for stage in stages] == list(RADIO_NONE_UI_NAMES)
    height = stages[0]["dom"]["viewport"]["height"]
    assert height in (724, 780)
    normalized, sessions, run_ids, widget_ids, boundary = [], set(), set(), None, 0
    for index, (stage, expected) in enumerate(zip(stages, RADIO_NONE_UI_VALUES, strict=True)):
        start, end = stage["event_range"]
        assert start == boundary and end - start == (9 if index == 0 else 8)
        boundary = end
        returned = (None, None) if before and index < 3 else expected
        dom = stage["dom"]
        assert dom["viewport"] == {"width": 1463, "height": height, "dpr": 1.75}
        assert dom["groups"] == [{"label": label, "radios": [{"label": option, "value": str(position), "checked": option == selected, "disabled": False}
            for position, option in enumerate(("Alpha", "Beta", "Charlie"))]} for label, selected in zip(("Choice", "Keyed choice"), expected, strict=True)]
        compact = re.sub(r"\s+", "", dom["body"])
        result_text = "".join(f"{i}:" + ("NULL" if value is None else json.dumps(value)) for i, value in enumerate(returned))
        assert '"phase":"none"' in compact and '"values":[' + result_text + ']' in compact
        assert stage["action_and_capture_calls_separate"] and stage["screenshot"] == stage["name"] + ".jpg"
        data = (folder / stage["screenshot"]).read_bytes()
        assert len(data) == stage["screenshot_bytes"] and hashlib.sha256(data).hexdigest() == stage["screenshot_sha256"]
        with Image.open(folder / stage["screenshot"]) as image:
            assert image.format == stage["screenshot_format"] == "JPEG" and list(image.size) == stage["screenshot_dimensions"] == [1463, height]
            rgb = image.convert("RGB")
            checked = [option == selected for selected in expected for option in ("Alpha", "Beta", "Charlie")]
            for selected, center in zip(checked, (135, 157, 180, 246, 268, 291), strict=True):
                red = sum((lambda c: c[0] > 160 and c[0] > c[1] * 1.3 and c[0] > c[2] * 1.3)(rgb.getpixel((x, y)))
                          for x in range(380, 397) for y in range(center - 8, center + 9))
                assert red > 100 if selected else red < 20
        batch = [messages[i] for i in range(start, end) if i in messages]
        assert [m.WhichOneof("type") for m in batch] == ["rerun_script", "new_session", "session_status_changed"] + ["delta"] * 3 + ["script_finished", "session_status_changed"]
        request, session = batch[0].rerun_script, batch[1].new_session
        assert request.query_string == "probe=radio-empty&phase=none" and not request.is_history_navigation
        assert session.initialize.environment_info.streamlit_version == "1.66.1"
        sessions.add(session.initialize.session_id)
        run_ids.add(session.script_run_id)
        assert batch[2].session_status_changed.script_is_running and batch[6].script_finished == 0 and not batch[7].session_status_changed.script_is_running
        elements = [m.delta.new_element for m in batch[3:6]]
        assert [m.delta.WhichOneof("type") for m in batch[3:6]] == ["new_element"] * 3
        assert [list(m.metadata.delta_path) for m in batch[3:6]] == [[0, i] for i in range(3)]
        assert [e.WhichOneof("type") for e in elements] == ["radio", "radio", "json"]
        ids = [e.radio.id for e in elements[:2]]
        if index == 0:
            assert not request.widget_states.widgets and len(set(ids)) == 2
            widget_ids = ids
        else:
            incoming = request.widget_states.widgets
            assert ids == widget_ids and len(incoming) == 2 and [w.id for w in incoming] == ids
            for widget, value in zip(incoming, expected, strict=True):
                assert widget.WhichOneof("value") == (None if value is None else "string_value")
                if value is not None:
                    assert widget.string_value == value
        for position, element in enumerate(elements[:2]):
            widget = element.radio
            assert widget.label == ("Choice", "Keyed choice")[position] and list(widget.options) == ["Alpha", "Beta", "Charlie"]
            assert not widget.HasField("default") and not widget.disabled and not widget.set_value and not widget.HasField("raw_value")
            assert not widget.horizontal and not widget.captions and not widget.ignore_rerun and not widget.form_id
            assert not element.HasField("has_one_shot_effect") and element.width_config.use_content
        report = json.loads(elements[-1].json.body)
        assert report == {"phase": "none", "values": list(returned)}
        fields = [MessageToDict(element, preserving_proto_field_name=True) for element in elements]
        for field in fields[:2]:
            field["radio"].pop("id")
        fields[-1]["json"]["body"] = report
        normalized.append(fields)
    assert boundary == len(events) and len(sessions) == 1 and len(run_ids) == 5
    return normalized


@pytest.mark.parametrize("root", (PYTHON, RUST), ids=("python", "rust"))
def test_radio_none_ui_selects_with_an_empty_peer(root):
    folder = root / "radio-empty/ui"
    check_radio_none_ui(read(folder / "trace.json"), folder)


def test_radio_none_ui_complete_elements_match_reference():
    folders = [root / "radio-empty/ui" for root in (PYTHON, RUST)]
    captures = [read(folder / "trace.json") for folder in folders]
    assert captures[0]["producer_sources_sha256"] == captures[1]["producer_sources_sha256"]
    assert check_radio_none_ui(captures[0], folders[0]) == check_radio_none_ui(captures[1], folders[1])


def test_radio_none_ui_before_discards_aggregate_input_until_both_are_selected():
    folder = RUST / "radio-empty/ui/before"
    capture = read(folder / "trace.json")
    before = check_radio_none_ui(capture, folder, before=True)
    sdk_folder = PYTHON / "radio-empty/ui"
    assert before != check_radio_none_ui(read(sdk_folder / "trace.json"), sdk_folder)
    with pytest.raises(AssertionError):
        check_radio_none_ui(capture, folder)


@pytest.mark.parametrize("default", (None, 0))
def test_sdk_radio_empty_payload_uses_registered_default_before_callback(default):
    import importlib.metadata
    from streamlit.testing.v1 import AppTest

    assert importlib.metadata.version("streamlit") == "1.66.1"
    script = ('import streamlit as st\n'
              'if "events" not in st.session_state: st.session_state.events=[]\n'
              'def changed(): st.session_state.events.append(st.session_state.choice)\n'
              'v=st.radio("Choice",["Alpha","Beta"],key="choice",index=' + repr(default) + ',on_change=changed)\n'
              'st.json([v,st.session_state.events])')
    app = AppTest.from_string(script).run()
    app.radio[0].set_value("Beta")
    app.run()
    assert not app.exception and json.loads(app.json[0].value) == ["Beta", ["Beta"]]
    app.radio[0].set_value(None)
    app.run()
    fallback = None if default is None else "Alpha"
    assert not app.exception and json.loads(app.json[0].value) == [fallback, ["Beta", fallback]]


@pytest.mark.parametrize("mutation", ("empty-oneof", "returned-value", "checked-state", "stale-id", "wire-default", "spurious-sync", "screenshot", "old-image"))
def test_radio_none_ui_gate_rejects_wrong_input_return_or_picture(mutation, tmp_path):
    import hashlib

    folder = PYTHON / "radio-empty/ui"
    capture = read(folder / "trace.json")
    if mutation == "checked-state":
        capture["snapshots"][2]["dom"]["groups"][1]["radios"][1]["checked"] = False
    elif mutation == "screenshot":
        capture["snapshots"][2]["screenshot_sha256"] = "wrong"
    elif mutation == "old-image":
        for stage in capture["snapshots"]:
            (tmp_path / stage["screenshot"]).write_bytes((folder / stage["screenshot"]).read_bytes())
        data = (folder / capture["snapshots"][1]["screenshot"]).read_bytes()
        stage = capture["snapshots"][2]
        (tmp_path / stage["screenshot"]).write_bytes(data)
        stage.update(screenshot_bytes=len(data), screenshot_sha256=hashlib.sha256(data).hexdigest())
        folder = tmp_path
    else:
        stage = capture["snapshots"][2]
        for event in capture["events"][slice(*stage["event_range"])]:
            if event["method"] not in ("Network.webSocketFrameSent", "Network.webSocketFrameReceived"):
                continue
            message = BackMsg() if event["method"].endswith("Sent") else ForwardMsg()
            message.ParseFromString(base64.b64decode(event["params"]["response"]["payloadData"]))
            if isinstance(message, BackMsg) and mutation in ("empty-oneof", "stale-id"):
                if mutation == "empty-oneof":
                    message.rerun_script.widget_states.widgets[0].int_value = 0
                else:
                    message.rerun_script.widget_states.widgets[0].id = "$$ID-stale-radio"
            elif message.WhichOneof("type") == "delta":
                element = message.delta.new_element
                if mutation in ("wire-default", "spurious-sync") and element.WhichOneof("type") == "radio":
                    if mutation == "wire-default":
                        element.radio.default = 0
                    else:
                        element.radio.set_value = True
                        element.has_one_shot_effect = True
                elif mutation == "returned-value" and element.WhichOneof("type") == "json":
                    report = json.loads(element.json.body)
                    report["values"][1] = None
                    element.json.body = json.dumps(report)
                    stage["dom"]["body"] = stage["dom"]["body"].replace('1:"Beta"', '1:NULL')
                else:
                    continue
            else:
                continue
            event["params"]["response"]["payloadData"] = base64.b64encode(message.SerializeToString()).decode()
    with pytest.raises(AssertionError):
        check_radio_none_ui(capture, folder)


FORMAT_COLLISION_PHASES = ("load", "edit", "other", "repeat", "reorder", "reorder-edit", "assign", "observe", "restore", "restore-edit")
FORMAT_COLLISION_VALUES = ((1, 1, [2]), (2, 2, [1]), (3, 3, [3]), (2, 2, [1, 1]), (2, 2, [1, 1]), (1, 1, [2, 2]), (1, 2, [2]), (1, 2, [2]), (1, 2, [2]), (2, 2, [1]))


def check_format_collisions(capture):
    assert capture["successful"] and "producer_error" not in capture and capture["reference_version"] == "1.66.1"
    assert capture["runtime"] in ("python", "rust") and capture["finishes"] == [0] * 10
    assert capture["cleanup"]["websocket_closed"] and capture["cleanup"]["server_stopped" if capture["runtime"] == "python" else "caller_server_stopped"]
    assert len(capture["frames"]) == 89 and len(capture["elements"]) == 40
    runs = color_runs(capture, ("selectbox", "multiselect", "json"))
    normalized, sessions, run_ids, ids = [], set(), set(), None
    for index, (phase, run) in enumerate(zip(FORMAT_COLLISION_PHASES, runs, strict=True)):
        request = run["request"]
        assert request.query_string == "probe=format-collisions&phase=" + phase and not request.is_history_navigation
        assert len(run["sessions"]) == 1 and run["finishes"] == [0]
        session = run["sessions"][0]
        assert session.initialize.environment_info.streamlit_version == "1.66.1"
        sessions.add(session.initialize.session_id)
        run_ids.add(session.script_run_id)
        assert [e[0] for e in run["entries"]] == ["selectbox", "selectbox", "multiselect", "json"]
        current = []
        for position, (kind, widget, element) in enumerate(run["entries"][:3]):
            assert widget.label == ("Choice", "Keyed choice", "Choices")[position]
            assert list(widget.options) == ["Same", "Same", "Other"] and not widget.disabled
            assert not widget.form_id and not widget.help and not widget.ignore_rerun
            assert widget.label_visibility.value == 0 and element.width_config.use_stretch
            assert widget.HasField("accept_new_options") and not widget.accept_new_options and widget.filter_mode == 0
            sync = phase == "assign" and position > 0
            assert widget.set_value == sync and element.HasField("has_one_shot_effect") == sync and element.has_one_shot_effect == sync
            if kind == "selectbox":
                assert widget.HasField("default") and widget.default == 0
                assert widget.HasField("raw_value") == sync and widget.raw_value == ("Same" if sync else "")
            else:
                assert list(widget.default) == [1] and widget.max_selections == 0 and widget.select_all == 1000
                assert list(widget.raw_values) == (["Same"] if sync else [])
            current.append(widget.id)
        if ids is None:
            ids = current
            assert len(set(ids)) == 3
        else:
            assert current == ids
        submitted = phase in ("edit", "other", "repeat", "reorder-edit", "restore-edit")
        incoming = request.widget_states.widgets
        if submitted:
            assert len(incoming) == 3 and [w.id for w in incoming] == ids
            text = "Other" if phase == "other" else "Same"
            assert [w.WhichOneof("value") for w in incoming] == ["string_value", "string_value", "string_array_value"]
            assert [w.string_value for w in incoming[:2]] == [text, text]
            assert list(incoming[2].string_array_value.data) == [text] * (2 if phase in ("repeat", "reorder-edit") else 1)
        else:
            assert not incoming
        plain, keyed, multiple = FORMAT_COLLISION_VALUES[index]
        report = json.loads(run["entries"][-1][1].body)
        assert report == {"phase": phase, "values": [plain, keyed, multiple]}
        assert all(type(value) is int for value in report["values"][:2] + report["values"][2])
        assert [e["delta_path"] for e in capture["elements"][index * 4:index * 4 + 4]] == [[0, i] for i in range(4)]
        fields = []
        for kind, _, element in run["entries"]:
            view = MessageToDict(element, preserving_proto_field_name=True)
            if kind == "json":
                view[kind]["body"] = json.loads(view[kind]["body"])
            else:
                view[kind].pop("id")
            fields.append(view)
        normalized.append(fields)
    assert len(sessions) == 1 and len(run_ids) == 10
    return normalized


@pytest.mark.parametrize("root", (PYTHON, RUST), ids=("python", "rust"))
def test_formatted_collision_native_state_and_remapping(root):
    check_format_collisions(read(root / "format-collisions/trace.json"))


def test_formatted_collision_complete_elements_match_reference():
    captures = [read(root / "format-collisions/trace.json") for root in (PYTHON, RUST)]
    assert captures[0]["producer_sources_sha256"] == captures[1]["producer_sources_sha256"] and captures[1]["semantic_match"] is True
    assert check_format_collisions(captures[0]) == check_format_collisions(captures[1])


def test_formatted_collision_before_selects_first_instead_of_last():
    capture = read(RUST / "format-collisions/before/trace.json")
    assert capture["successful"] and capture["finishes"] == [0] * 10 and capture["semantic_match"] is False
    assert len(capture["frames"]) == 89 and len(capture["elements"]) == 40
    runs = color_runs(capture, ("selectbox", "multiselect", "json"))
    assert json.loads(runs[1]["entries"][-1][1].body) == {"phase": "edit", "values": [1, 1, [1]]}
    with pytest.raises(AssertionError):
        check_format_collisions(capture)


def test_sdk_formatted_collisions_keep_different_single_and_multi_rules():
    import importlib.metadata
    from streamlit.testing.v1 import AppTest

    assert importlib.metadata.version("streamlit") == "1.66.1"
    app = AppTest.from_string('''
import streamlit as st
if 'calls' not in st.session_state: st.session_state.calls=[]
def changed(): st.session_state.calls.append(st.session_state.single)
formatter=lambda value:'Other' if value==3 else 'Same'
s=st.selectbox('S',[1,2,3],key='single',format_func=formatter,on_change=changed)
m=st.multiselect('M',[1,2,3],default=[2],key='multiple',format_func=formatter)
st.json([s,m,st.session_state.calls])
''').run()
    assert not app.exception and json.loads(app.json[0].value) == [1, [2], []]
    app.selectbox[0].set_value(1)
    app.multiselect[0].set_value([2])
    app.run()
    assert not app.exception and json.loads(app.json[0].value) == [2, [1], [2]]
    app.selectbox[0].set_value(2)
    app.multiselect[0].set_value([2, 2])
    app.run()
    assert not app.exception and json.loads(app.json[0].value) == [2, [1, 1], [2]]


def test_sdk_duplicate_native_options_do_not_create_spurious_callbacks():
    import importlib.metadata
    from streamlit.testing.v1 import AppTest

    assert importlib.metadata.version("streamlit") == "1.66.1"
    app = AppTest.from_string('''
import streamlit as st
if 'calls' not in st.session_state:st.session_state.calls=[]
def changed():st.session_state.calls.append([st.session_state.s,st.session_state.m])
f=lambda value:'Other' if value==3 else 'Same'
s=st.selectbox('S',[1,1,3],key='s',format_func=f,on_change=changed)
m=st.multiselect('M',[1,1,3],default=[1],key='m',format_func=f,on_change=changed)
st.json([s,m,st.session_state.calls])
''').run()
    expected = []
    for value in (1, 3, 1):
        app.selectbox[0].set_value(value)
        app.multiselect[0].set_value([value])
        app.run()
        if value == 3 or expected:
            expected.extend([[value, [value]], [value, [value]]])
        assert not app.exception and json.loads(app.json[0].value) == [value, [value], expected]


@pytest.mark.parametrize("keyed", (False, True))
def test_sdk_unchanged_labels_can_retain_native_values_outside_new_options(keyed):
    """SDK-only typed-state retention boundary; no Rust/native-WS parity claim."""
    import importlib.metadata
    from streamlit.testing.v1 import AppTest

    assert importlib.metadata.version("streamlit") == "1.66.1"
    script = ('import streamlit as st\n'
              'options=[4,5,3] if st.session_state.get("change",False) else [1,2,3]\n'
              'v=st.selectbox("S",options,key=' + repr("s" if keyed else None) + ',format_func=lambda value:"Other" if value==3 else "Same")\n'
              'st.json([v,options])')
    app = AppTest.from_string(script).run()
    assert not app.exception and json.loads(app.json[0].value) == [1, [1, 2, 3]]
    app.session_state["change"] = True
    app.run()
    assert not app.exception and json.loads(app.json[0].value) == [2, [4, 5, 3]]


@pytest.mark.parametrize("mutation", ("single-return", "multi-return", "unkeyed-reorder", "raw-value", "sync-flag", "stale-input", "identity", "numeric-type"))
def test_formatted_collision_gate_rejects_coherent_wrong_wire(mutation):
    capture = read(PYTHON / "format-collisions/trace.json")
    target = {"single-return": 1, "multi-return": 1, "unkeyed-reorder": 4, "raw-value": 6, "sync-flag": 6, "stale-input": 5, "identity": 4, "numeric-type": 0}[mutation]
    run = -1
    for frame in capture["frames"]:
        client = frame["direction"] == "client->server"
        if client:
            run += 1
        if run != target:
            continue
        message = BackMsg() if client else ForwardMsg()
        message.ParseFromString(base64.b64decode(frame["base64"]))
        if client and mutation == "stale-input":
            message.rerun_script.widget_states.widgets[0].id = "$$ID-stale-formatted"
        elif not client and message.WhichOneof("type") == "delta":
            element = message.delta.new_element
            kind = element.WhichOneof("type")
            if kind == "selectbox" and element.selectbox.label == "Keyed choice" and mutation == "raw-value":
                element.selectbox.raw_value = "Other"
            elif kind == "selectbox" and element.selectbox.label == "Keyed choice" and mutation == "sync-flag":
                element.selectbox.set_value = False
                element.ClearField("has_one_shot_effect")
            elif kind == "selectbox" and element.selectbox.label == "Choice" and mutation == "identity":
                element.selectbox.id = "$$ID-wrong-formatted-None"
            elif kind == "json" and mutation in ("single-return", "multi-return", "unkeyed-reorder", "numeric-type"):
                report = json.loads(element.json.body)
                if mutation == "single-return": report["values"][1] = 1
                elif mutation == "multi-return": report["values"][2] = [2]
                elif mutation == "unkeyed-reorder": report["values"][0] = 1
                else: report["values"][0] = 1.0
                element.json.body = json.dumps(report)
            else:
                continue
        else:
            continue
        raw = message.SerializeToString()
        frame.update(base64=base64.b64encode(raw).decode(), bytes=len(raw), message=MessageToDict(message, preserving_proto_field_name=True))
    capture["elements"] = [{"kind": m.delta.new_element.WhichOneof("type"), "fields": MessageToDict(getattr(m.delta.new_element, m.delta.new_element.WhichOneof("type")), preserving_proto_field_name=True),
                            "delta_path": list(m.metadata.delta_path)} for m in frames(capture) if isinstance(m, ForwardMsg) and m.WhichOneof("type") == "delta"]
    with pytest.raises(AssertionError):
        check_format_collisions(capture)


RADIO_DUPLICATE_PHASES = ("load", "same", "other", "back", "peer", "both", "observe")
RADIO_DUPLICATE_VALUES = (("Same", "Idle"), ("Same", "Idle"), ("Other", "Idle"), ("Same", "Idle"), ("Same", "Ready"), ("Other", "Idle"), ("Other", "Idle"))
RADIO_DUPLICATE_COUNTS = (0, 0, 1, 2, 3, 5, 5)
RADIO_DUPLICATE_CALLS = [["choice", "Other", "Idle"], ["choice", "Same", "Idle"], ["peer", "Same", "Ready"], ["choice", "Other", "Idle"], ["peer", "Other", "Idle"]]


def check_radio_duplicates(capture):
    assert capture["successful"] and "producer_error" not in capture and capture["reference_version"] == "1.66.1"
    assert capture["runtime"] in ("python", "rust") and capture["finishes"] == [0] * 7
    assert capture["cleanup"]["websocket_closed"] and capture["cleanup"]["server_stopped" if capture["runtime"] == "python" else "caller_server_stopped"]
    assert len(capture["frames"]) == 55 and len(capture["elements"]) == 21
    runs = color_runs(capture, ("radio", "json"))
    normalized, sessions, run_ids, ids = [], set(), set(), None
    for index, (phase, run) in enumerate(zip(RADIO_DUPLICATE_PHASES, runs, strict=True)):
        request = run["request"]
        assert request.query_string == "probe=radio-duplicates&phase=" + phase and not request.is_history_navigation
        assert len(run["sessions"]) == 1 and run["finishes"] == [0]
        session = run["sessions"][0]
        assert session.initialize.environment_info.streamlit_version == "1.66.1"
        sessions.add(session.initialize.session_id)
        run_ids.add(session.script_run_id)
        assert [entry[0] for entry in run["entries"]] == ["radio", "radio", "json"]
        current = []
        for position, (_, widget, element) in enumerate(run["entries"][:2]):
            assert widget.label == ("Choice", "Peer")[position]
            assert list(widget.options) == (["Same", "Same", "Other"], ["Idle", "Ready"])[position]
            assert widget.HasField("default") and widget.default == (1, 0)[position]
            assert not widget.disabled and not widget.horizontal and not widget.captions
            assert not widget.form_id and not widget.help and not widget.ignore_rerun
            assert widget.label_visibility.value == 0 and element.width_config.use_content
            assert not widget.set_value and not widget.HasField("raw_value") and not element.HasField("has_one_shot_effect")
            current.append(widget.id)
        if ids is None:
            ids = current
            assert len(set(ids)) == 2
        else:
            assert current == ids
        incoming = request.widget_states.widgets
        if phase not in ("load", "observe"):
            assert len(incoming) == 2 and [widget.id for widget in incoming] == ids
            assert all(widget.WhichOneof("value") == "string_value" for widget in incoming)
            assert [widget.string_value for widget in incoming] == list(RADIO_DUPLICATE_VALUES[index])
        else:
            assert not incoming
        assert json.loads(run["entries"][-1][1].body) == {"phase": phase, "values": list(RADIO_DUPLICATE_VALUES[index]), "calls": RADIO_DUPLICATE_CALLS[:RADIO_DUPLICATE_COUNTS[index]]}
        assert [entry["delta_path"] for entry in capture["elements"][index * 3:index * 3 + 3]] == [[0, i] for i in range(3)]
        fields = []
        for kind, _, element in run["entries"]:
            view = MessageToDict(element, preserving_proto_field_name=True)
            if kind == "json":
                view[kind]["body"] = json.loads(view[kind]["body"])
            else:
                view[kind].pop("id")
            fields.append(view)
        normalized.append(fields)
    assert len(sessions) == 1 and len(run_ids) == 7
    return normalized


@pytest.mark.parametrize("root", (PYTHON, RUST), ids=("python", "rust"))
def test_radio_duplicate_native_callback_sequence(root):
    check_radio_duplicates(read(root / "radio-duplicates/trace.json"))


def test_radio_duplicate_complete_elements_match_reference():
    captures = [read(root / "radio-duplicates/trace.json") for root in (PYTHON, RUST)]
    assert captures[0]["producer_sources_sha256"] == captures[1]["producer_sources_sha256"] and captures[1]["semantic_match"] is True
    assert check_radio_duplicates(captures[0]) == check_radio_duplicates(captures[1])


def test_radio_duplicate_before_fires_on_equal_native_value():
    capture = read(RUST / "radio-duplicates/before/trace.json")
    assert capture["successful"] and capture["semantic_match"] is False
    runs = color_runs(capture, ("radio", "json"))
    assert json.loads(runs[1]["entries"][-1][1].body)["calls"] == [["choice", "Same", "Idle"]]
    with pytest.raises(AssertionError):
        check_radio_duplicates(capture)


@pytest.mark.parametrize("mutation", ("spurious-same", "callback-value", "batch-peer", "order", "replayed", "input-id", "wire-default", "sync-flag"))
def test_radio_duplicate_gate_rejects_coherent_wrong_wire(mutation):
    capture = read(PYTHON / "radio-duplicates/trace.json")
    target = {"spurious-same": 1, "callback-value": 2, "batch-peer": 5, "order": 5, "replayed": 6, "input-id": 2, "wire-default": 1, "sync-flag": 3}[mutation]
    run = -1
    for frame in capture["frames"]:
        client = frame["direction"] == "client->server"
        if client:
            run += 1
        if run != target:
            continue
        message = BackMsg() if client else ForwardMsg()
        message.ParseFromString(base64.b64decode(frame["base64"]))
        if client and mutation == "input-id":
            message.rerun_script.widget_states.widgets[0].id = "$$ID-stale-radio"
        elif not client and message.WhichOneof("type") == "delta":
            element = message.delta.new_element
            kind = element.WhichOneof("type")
            if kind == "radio" and element.radio.label == "Choice" and mutation == "wire-default":
                element.radio.default = 0
            elif kind == "radio" and element.radio.label == "Choice" and mutation == "sync-flag":
                element.radio.set_value = True
                element.radio.raw_value = "Same"
                element.has_one_shot_effect = True
            elif kind == "json" and mutation in ("spurious-same", "callback-value", "batch-peer", "order", "replayed"):
                report = json.loads(element.json.body)
                if mutation == "spurious-same": report["calls"].append(["choice", "Same", "Idle"])
                elif mutation == "callback-value": report["calls"][0][1] = "Same"
                elif mutation == "batch-peer": report["calls"][-1][2] = "Ready"
                elif mutation == "order": report["calls"][-2:] = report["calls"][-2:][::-1]
                else: report["calls"].append(report["calls"][-1])
                element.json.body = json.dumps(report)
            else:
                continue
        else:
            continue
        raw = message.SerializeToString()
        frame.update(base64=base64.b64encode(raw).decode(), bytes=len(raw), message=MessageToDict(message, preserving_proto_field_name=True))
    capture["elements"] = [{"kind": m.delta.new_element.WhichOneof("type"), "fields": MessageToDict(getattr(m.delta.new_element, m.delta.new_element.WhichOneof("type")), preserving_proto_field_name=True),
                            "delta_path": list(m.metadata.delta_path)} for m in frames(capture) if isinstance(m, ForwardMsg) and m.WhichOneof("type") == "delta"]
    with pytest.raises(AssertionError):
        check_radio_duplicates(capture)


GROUP_WIDTH_PHASES = ("load", "edit", "width", "width-edit", "restore", "restore-edit", "observe")
GROUP_WIDTH_LABELS = ("Plain pills", "Keyed pills", "Plain segments", "Keyed segments")


def check_group_width(capture):
    assert capture["successful"] and "producer_error" not in capture and capture["reference_version"] == "1.66.1"
    assert capture["runtime"] in ("python", "rust") and capture["finishes"] == [0] * 7
    assert capture["cleanup"]["websocket_closed"] and capture["cleanup"]["server_stopped" if capture["runtime"] == "python" else "caller_server_stopped"]
    assert len(capture["frames"]) == 69 and len(capture["elements"]) == 35
    runs = color_runs(capture, ("button_group", "json"))
    normalized, sessions, run_ids, identities, previous = [], set(), set(), [{}, {}, {}, {}], None
    for index, (phase, run) in enumerate(zip(GROUP_WIDTH_PHASES, runs, strict=True)):
        request = run["request"]
        assert request.query_string == "probe=group-width&phase=" + phase and not request.is_history_navigation
        assert len(run["sessions"]) == 1 and run["finishes"] == [0]
        session = run["sessions"][0]
        assert session.initialize.environment_info.streamlit_version == "1.66.1"
        sessions.add(session.initialize.session_id)
        run_ids.add(session.script_run_id)
        assert [entry[0] for entry in run["entries"]] == ["button_group"] * 4 + ["json"]
        wide = phase in ("width", "width-edit")
        current = []
        for position, (_, widget, element) in enumerate(run["entries"][:4]):
            assert widget.label == GROUP_WIDTH_LABELS[position]
            assert [option.content for option in widget.options] == ["Alpha", "Beta"]
            assert widget.style == (1 if position < 2 else 0) and widget.click_mode == (0 if position < 2 else 1)
            assert not widget.default and not widget.disabled and not widget.required and not widget.ignore_rerun
            assert not widget.form_id and not widget.HasField("help") and widget.label_visibility.value == 0
            assert not widget.set_value and not widget.raw_values and not element.HasField("has_one_shot_effect")
            assert element.width_config.WhichOneof("width_spec") == ("pixel_width" if wide else "use_content")
            assert element.width_config.pixel_width == 300 if wide else element.width_config.use_content
            identity_class = wide if position % 2 == 0 else False
            assert widget.id == identities[position].setdefault(identity_class, widget.id)
            current.append(widget.id)
        assert len(set(current)) == 4
        incoming = request.widget_states.widgets
        if phase in ("edit", "width-edit", "restore-edit"):
            assert len(incoming) == 4 and [widget.id for widget in incoming] == previous
            assert all(widget.WhichOneof("value") == "string_array_value" and list(widget.string_array_value.data) == ["Beta"] for widget in incoming)
        else:
            assert not incoming
        values = [None, None, [], []] if index == 0 else [None, "Beta", [], ["Beta"]] if phase in ("width", "restore") else ["Beta", "Beta", ["Beta"], ["Beta"]]
        assert json.loads(run["entries"][-1][1].body) == {"phase": phase, "values": values}
        assert [entry["delta_path"] for entry in capture["elements"][index * 5:index * 5 + 5]] == [[0, i] for i in range(5)]
        fields = []
        for kind, _, element in run["entries"]:
            view = MessageToDict(element, preserving_proto_field_name=True)
            if kind == "json":
                view[kind]["body"] = json.loads(view[kind]["body"])
            else:
                view[kind].pop("id")
            fields.append(view)
        normalized.append(fields)
        previous = current
    assert [len(set(identity.values())) for identity in identities] == [2, 1, 2, 1]
    assert len(sessions) == 1 and len(run_ids) == 7
    return normalized


@pytest.mark.parametrize("root", (PYTHON, RUST), ids=("python", "rust"))
def test_button_group_width_identity_and_state_cleanup(root):
    check_group_width(read(root / "group-width/trace.json"))


def test_button_group_width_complete_elements_match_reference():
    captures = [read(root / "group-width/trace.json") for root in (PYTHON, RUST)]
    assert captures[0]["producer_sources_sha256"] == captures[1]["producer_sources_sha256"] and captures[1]["semantic_match"] is True
    assert check_group_width(captures[0]) == check_group_width(captures[1])


def test_button_group_width_before_incorrectly_keeps_unkeyed_values():
    capture = read(RUST / "group-width/before/trace.json")
    assert capture["successful"] and capture["semantic_match"] is False
    runs = color_runs(capture, ("button_group", "json"))
    assert json.loads(runs[2]["entries"][-1][1].body)["values"] == ["Beta", "Beta", ["Beta"], ["Beta"]]
    with pytest.raises(AssertionError):
        check_group_width(capture)


@pytest.mark.parametrize("mutation", ("unkeyed-id", "keyed-id", "retained", "revived", "width", "input-id", "input-type", "sync"))
def test_button_group_width_gate_rejects_coherent_wrong_wire(mutation):
    capture = read(PYTHON / "group-width/trace.json")
    initial_id = capture["elements"][0]["fields"]["id"]
    target = {"unkeyed-id": 2, "keyed-id": 2, "retained": 2, "revived": 4, "width": 2, "input-id": 3, "input-type": 1, "sync": 3}[mutation]
    run = -1
    for frame in capture["frames"]:
        client = frame["direction"] == "client->server"
        if client:
            run += 1
        if run != target:
            continue
        message = BackMsg() if client else ForwardMsg()
        message.ParseFromString(base64.b64decode(frame["base64"]))
        if client and mutation == "input-id":
            message.rerun_script.widget_states.widgets[0].id = initial_id
        elif client and mutation == "input-type":
            message.rerun_script.widget_states.widgets[0].string_value = "Beta"
        elif not client and message.WhichOneof("type") == "delta":
            element = message.delta.new_element
            kind = element.WhichOneof("type")
            if kind == "button_group" and element.button_group.label == "Plain pills" and mutation == "unkeyed-id":
                element.button_group.id = initial_id
            elif kind == "button_group" and element.button_group.label == "Keyed pills" and mutation == "keyed-id":
                element.button_group.id = "$$ID-wrong-keyed-group"
            elif kind == "button_group" and element.button_group.label == "Plain pills" and mutation == "width":
                element.width_config.pixel_width = 301
            elif kind == "button_group" and element.button_group.label == "Plain pills" and mutation == "sync":
                element.button_group.set_value = True
                element.button_group.raw_values.append("Beta")
                element.has_one_shot_effect = True
            elif kind == "json" and mutation in ("retained", "revived"):
                report = json.loads(element.json.body)
                report["values"][0] = "Beta"
                element.json.body = json.dumps(report)
            else:
                continue
        else:
            continue
        raw = message.SerializeToString()
        frame.update(base64=base64.b64encode(raw).decode(), bytes=len(raw), message=MessageToDict(message, preserving_proto_field_name=True))
    capture["elements"] = [{"kind": m.delta.new_element.WhichOneof("type"), "fields": MessageToDict(getattr(m.delta.new_element, m.delta.new_element.WhichOneof("type")), preserving_proto_field_name=True),
                            "delta_path": list(m.metadata.delta_path)} for m in frames(capture) if isinstance(m, ForwardMsg) and m.WhichOneof("type") == "delta"]
    with pytest.raises(AssertionError):
        check_group_width(capture)


GROUP_POLICY_PHASES = ("load", "edit", "required", "required-edit", "optional", "multi", "multi-edit", "restore", "restore-edit", "observe")


def check_group_policy(capture):
    assert capture["successful"] and "producer_error" not in capture and capture["reference_version"] == "1.66.1"
    assert capture["runtime"] in ("python", "rust") and capture["finishes"] == [0] * 10
    assert capture["cleanup"]["websocket_closed"] and capture["cleanup"]["server_stopped" if capture["runtime"] == "python" else "caller_server_stopped"]
    assert len(capture["frames"]) == 99 and len(capture["elements"]) == 50
    runs = color_runs(capture, ("button_group", "json"))
    normalized, sessions, run_ids, identities, previous = [], set(), set(), [{}, {}, {}, {}], None
    for index, (phase, run) in enumerate(zip(GROUP_POLICY_PHASES, runs, strict=True)):
        request = run["request"]
        assert request.query_string == "probe=group-policy&phase=" + phase and not request.is_history_navigation
        assert len(run["sessions"]) == 1 and run["finishes"] == [0]
        session = run["sessions"][0]
        assert session.initialize.environment_info.streamlit_version == "1.66.1"
        sessions.add(session.initialize.session_id)
        run_ids.add(session.script_run_id)
        assert [entry[0] for entry in run["entries"]] == ["button_group"] * 4 + ["json"]
        multi = phase in ("multi", "multi-edit")
        required = phase in ("required", "required-edit")
        current = []
        for position, (_, widget, element) in enumerate(run["entries"][:4]):
            assert widget.label == GROUP_WIDTH_LABELS[position]
            assert [option.content for option in widget.options] == ["Alpha", "Beta"]
            assert widget.style == (1 if position < 2 else 0) and widget.click_mode == int(multi)
            assert not widget.default and not widget.disabled and widget.required == required and not widget.ignore_rerun
            assert not widget.form_id and not widget.HasField("help") and widget.label_visibility.value == 0
            assert not widget.set_value and not widget.raw_values and not element.HasField("has_one_shot_effect")
            assert element.width_config.use_content
            identity_class = multi
            assert widget.id == identities[position].setdefault(identity_class, widget.id)
            current.append(widget.id)
        assert len(set(current)) == 4
        incoming = request.widget_states.widgets
        if phase in ("edit", "required-edit", "multi-edit", "restore-edit"):
            assert len(incoming) == 4 and [widget.id for widget in incoming] == previous
            assert all(widget.WhichOneof("value") == "string_array_value" and list(widget.string_array_value.data) == (["Beta", "Alpha"] if multi else ["Alpha"] if phase == "required-edit" else ["Beta"]) for widget in incoming)
        else:
            assert not incoming
        value = None if phase in ("load", "restore") else [] if phase == "multi" else ["Beta", "Alpha"] if multi else "Alpha" if phase in ("required-edit", "optional") else "Beta"
        values = [value] * 4
        assert json.loads(run["entries"][-1][1].body) == {"phase": phase, "values": values}
        assert [entry["delta_path"] for entry in capture["elements"][index * 5:index * 5 + 5]] == [[0, i] for i in range(5)]
        fields = []
        for kind, _, element in run["entries"]:
            view = MessageToDict(element, preserving_proto_field_name=True)
            if kind == "json":
                view[kind]["body"] = json.loads(view[kind]["body"])
            else:
                view[kind].pop("id")
            fields.append(view)
        normalized.append(fields)
        previous = current
    assert [len(set(identity.values())) for identity in identities] == [2, 2, 2, 2]
    assert len(sessions) == 1 and len(run_ids) == 10
    return normalized



@pytest.mark.parametrize("root", (PYTHON, RUST), ids=("python", "rust"))
def test_button_group_required_policy_and_mode_identity(root):
    check_group_policy(read(root / "group-policy/trace.json"))


def test_button_group_policy_complete_elements_match_reference():
    captures = [read(root / "group-policy/trace.json") for root in (PYTHON, RUST)]
    assert captures[0]["producer_sources_sha256"] == captures[1]["producer_sources_sha256"] and captures[1]["semantic_match"] is True
    assert check_group_policy(captures[0]) == check_group_policy(captures[1])


def test_button_group_policy_before_loses_values_and_raises_mode_errors():
    capture = read(RUST / "group-policy/before/trace.json")
    assert capture["successful"] and capture["semantic_match"] is False and capture["finishes"] == [0] * 10
    assert len(capture["frames"]) == 93 and len(capture["elements"]) == 44
    runs = color_runs(capture, ("button_group", "json", "markdown"))
    assert json.loads(runs[2]["entries"][-1][1].body)["values"] == [None, "Beta", None, "Beta"]
    assert runs[5]["entries"][-1][0] == "markdown" and "multi-select session value must be an array" in runs[5]["entries"][-1][1].body
    assert runs[7]["entries"][-1][0] == "markdown" and "session value is absent from options" in runs[7]["entries"][-1][1].body
    with pytest.raises(AssertionError):
        check_group_policy(capture)


@pytest.mark.parametrize("mutation", ("required-id", "keyed-mode-id", "reset-required", "retained-mode", "revived", "mode-wire", "input-order", "sync"))
def test_button_group_policy_gate_rejects_coherent_wrong_wire(mutation):
    capture = read(PYTHON / "group-policy/trace.json")
    keyed_id = capture["elements"][1]["fields"]["id"]
    target = {"required-id": 2, "keyed-mode-id": 5, "reset-required": 2, "retained-mode": 5, "revived": 7, "mode-wire": 5, "input-order": 6, "sync": 3}[mutation]
    run = -1
    for frame in capture["frames"]:
        client = frame["direction"] == "client->server"
        if client:
            run += 1
        if run != target:
            continue
        message = BackMsg() if client else ForwardMsg()
        message.ParseFromString(base64.b64decode(frame["base64"]))
        if client and mutation == "input-order":
            message.rerun_script.widget_states.widgets[0].string_array_value.data[:] = ["Alpha", "Beta"]
        elif not client and message.WhichOneof("type") == "delta":
            element = message.delta.new_element
            kind = element.WhichOneof("type")
            if kind == "button_group" and element.button_group.label == "Plain pills" and mutation == "required-id":
                element.button_group.id = "$$ID-wrong-required-identity"
            elif kind == "button_group" and element.button_group.label == "Keyed pills" and mutation == "keyed-mode-id":
                element.button_group.id = keyed_id
            elif kind == "button_group" and element.button_group.label == "Plain pills" and mutation == "mode-wire":
                element.button_group.click_mode = 0
            elif kind == "button_group" and element.button_group.label == "Plain pills" and mutation == "sync":
                element.button_group.set_value = True
                element.button_group.raw_values.append("Alpha")
                element.has_one_shot_effect = True
            elif kind == "json" and mutation in ("reset-required", "retained-mode", "revived"):
                report = json.loads(element.json.body)
                report["values"][0] = None if mutation == "reset-required" else "Alpha" if mutation == "retained-mode" else "Beta"
                element.json.body = json.dumps(report)
            else:
                continue
        else:
            continue
        raw = message.SerializeToString()
        frame.update(base64=base64.b64encode(raw).decode(), bytes=len(raw), message=MessageToDict(message, preserving_proto_field_name=True))
    capture["elements"] = [{"kind": m.delta.new_element.WhichOneof("type"), "fields": MessageToDict(getattr(m.delta.new_element, m.delta.new_element.WhichOneof("type")), preserving_proto_field_name=True),
                            "delta_path": list(m.metadata.delta_path)} for m in frames(capture) if isinstance(m, ForwardMsg) and m.WhichOneof("type") == "delta"]
    with pytest.raises(AssertionError):
        check_group_policy(capture)


GROUP_STATE_PHASES = ("load", "edit", "subset", "empty", "return", "assign", "observe", "clear", "recover", "observe-final")
GROUP_STATE_LABELS = ("Single pills", "Multi pills", "Single segments", "Multi segments")
GROUP_STATE_VALUES = [
    [single, multiple, single, multiple] for single, multiple in (
        ("Beta", ["Beta"]), ("Alpha", ["Beta", "Alpha", "Beta"]), ("Beta", ["Beta", "Beta"]),
        (None, []), (None, []), ("Beta", ["Beta", "Beta", "Alpha"]), ("Beta", ["Beta", "Beta", "Alpha"]),
        (None, []), ("Alpha", ["Alpha", "Beta"]), ("Alpha", ["Alpha", "Beta"]))
]


def check_group_state(capture):
    assert capture["successful"] and "producer_error" not in capture and capture["reference_version"] == "1.66.1"
    assert capture["runtime"] in ("python", "rust") and capture["finishes"] == [0] * 10
    assert capture["cleanup"]["websocket_closed"] and capture["cleanup"]["server_stopped" if capture["runtime"] == "python" else "caller_server_stopped"]
    assert len(capture["frames"]) == 99 and len(capture["elements"]) == 50
    runs = color_runs(capture, ("button_group", "json"))
    normalized, sessions, run_ids, identities, previous = [], set(), set(), [{}, {}, {}, {}], None
    for index, (phase, run) in enumerate(zip(GROUP_STATE_PHASES, runs, strict=True)):
        request = run["request"]
        assert request.query_string == "probe=group-state&phase=" + phase and not request.is_history_navigation
        assert len(run["sessions"]) == 1 and run["finishes"] == [0]
        session = run["sessions"][0]
        assert session.initialize.environment_info.streamlit_version == "1.66.1"
        sessions.add(session.initialize.session_id)
        run_ids.add(session.script_run_id)
        assert [entry[0] for entry in run["entries"]] == ["button_group"] * 4 + ["json"]
        choices = [] if phase == "empty" else ["Beta"] if phase == "subset" else ["Alpha", "Beta"]
        sync = phase in ("subset", "empty", "assign", "clear")
        current = []
        for position, (_, widget, element) in enumerate(run["entries"][:4]):
            assert widget.label == GROUP_STATE_LABELS[position]
            multi = position % 2 == 1
            assert [option.content for option in widget.options] == choices
            assert widget.style == (1 if position < 2 else 0) and widget.click_mode == int(multi)
            assert list(widget.default) == ([] if not choices else [0] if phase == "subset" else [1])
            assert not widget.disabled and not widget.required and not widget.ignore_rerun
            assert not widget.form_id and not widget.HasField("help") and widget.label_visibility.value == 0
            assert widget.set_value == sync and element.HasField("has_one_shot_effect") == sync and element.has_one_shot_effect == sync
            value = GROUP_STATE_VALUES[index][position]
            assert list(widget.raw_values) == ([] if not sync or value is None else value if multi else [value])
            assert element.width_config.use_content
            identity_class = False
            assert widget.id == identities[position].setdefault(identity_class, widget.id)
            current.append(widget.id)
        assert len(set(current)) == 4
        incoming = request.widget_states.widgets
        if phase in ("edit", "recover"):
            assert len(incoming) == 4 and [widget.id for widget in incoming] == previous
            for position, widget in enumerate(incoming):
                assert widget.WhichOneof("value") == "string_array_value"
                assert list(widget.string_array_value.data) == (["Alpha"] if position % 2 == 0 else ["Beta", "Alpha", "Beta"] if phase == "edit" else ["Alpha", "Beta"])
        else:
            assert not incoming
        values = GROUP_STATE_VALUES[index]
        assert json.loads(run["entries"][-1][1].body) == {"phase": phase, "values": values, "native": values}
        assert [entry["delta_path"] for entry in capture["elements"][index * 5:index * 5 + 5]] == [[0, i] for i in range(5)]
        fields = []
        for kind, _, element in run["entries"]:
            view = MessageToDict(element, preserving_proto_field_name=True)
            if kind == "json":
                view[kind]["body"] = json.loads(view[kind]["body"])
            else:
                view[kind].pop("id")
            fields.append(view)
        normalized.append(fields)
        previous = current
    assert [len(set(identity.values())) for identity in identities] == [1, 1, 1, 1]
    assert len(sessions) == 1 and len(run_ids) == 10
    return normalized



@pytest.mark.parametrize("root", (PYTHON, RUST), ids=("python", "rust"))
def test_button_group_native_filter_reset_and_sync(root):
    check_group_state(read(root / "group-state/trace.json"))


def test_button_group_state_complete_elements_match_reference():
    captures = [read(root / "group-state/trace.json") for root in (PYTHON, RUST)]
    assert captures[0]["producer_sources_sha256"] == captures[1]["producer_sources_sha256"] and captures[1]["semantic_match"] is True
    assert check_group_state(captures[0]) == check_group_state(captures[1])


def test_button_group_state_before_raises_and_loses_duplicate_values():
    capture = read(RUST / "group-state/before/trace.json")
    assert capture["successful"] and capture["semantic_match"] is False and capture["finishes"] == [0] * 10
    assert len(capture["frames"]) == 91 and len(capture["elements"]) == 42
    runs = color_runs(capture, ("button_group", "json", "markdown"))
    for index in (2, 5):
        assert runs[index]["entries"][-1][0] == "markdown" and "session value is absent from options" in runs[index]["entries"][-1][1].body
    assert json.loads(runs[6]["entries"][-1][1].body)["values"] == ["Beta", ["Beta"], "Beta", ["Beta"]]
    with pytest.raises(AssertionError):
        check_group_state(capture)


@pytest.mark.parametrize("mutation", ("return", "duplicates", "native", "raw-values", "missing-sync", "empty-sync", "stale-input", "wire-default"))
def test_button_group_state_gate_rejects_coherent_wrong_wire(mutation):
    capture = read(PYTHON / "group-state/trace.json")
    target = {"return": 2, "duplicates": 6, "native": 5, "raw-values": 5, "missing-sync": 2, "empty-sync": 3, "stale-input": 8, "wire-default": 2}[mutation]
    run = -1
    for frame in capture["frames"]:
        client = frame["direction"] == "client->server"
        if client:
            run += 1
        if run != target:
            continue
        message = BackMsg() if client else ForwardMsg()
        message.ParseFromString(base64.b64decode(frame["base64"]))
        if client and mutation == "stale-input":
            message.rerun_script.widget_states.widgets[0].id = "$$ID-stale-group-state"
        elif not client and message.WhichOneof("type") == "delta":
            element = message.delta.new_element
            kind = element.WhichOneof("type")
            if kind == "button_group" and element.button_group.label == "Multi pills" and mutation == "raw-values":
                element.button_group.raw_values[:] = ["Alpha", "Beta", "Beta"]
            elif kind == "button_group" and element.button_group.label == "Single pills" and mutation in ("missing-sync", "empty-sync"):
                element.button_group.set_value = False
                element.ClearField("has_one_shot_effect")
            elif kind == "button_group" and element.button_group.label == "Single pills" and mutation == "wire-default":
                element.button_group.default[:] = [1]
            elif kind == "json" and mutation in ("return", "duplicates", "native"):
                report = json.loads(element.json.body)
                if mutation == "return": report["values"][0] = "Alpha"
                elif mutation == "duplicates": report["values"][1] = ["Beta", "Alpha"]
                else: report["native"][1] = ["Gone", "Beta", "Beta", "Alpha"]
                element.json.body = json.dumps(report)
            else:
                continue
        else:
            continue
        raw = message.SerializeToString()
        frame.update(base64=base64.b64encode(raw).decode(), bytes=len(raw), message=MessageToDict(message, preserving_proto_field_name=True))
    capture["elements"] = [{"kind": m.delta.new_element.WhichOneof("type"), "fields": MessageToDict(getattr(m.delta.new_element, m.delta.new_element.WhichOneof("type")), preserving_proto_field_name=True),
                            "delta_path": list(m.metadata.delta_path)} for m in frames(capture) if isinstance(m, ForwardMsg) and m.WhichOneof("type") == "delta"]
    with pytest.raises(AssertionError):
        check_group_state(capture)


GROUP_DEFAULT_PHASES = ("load", "edit", "default", "default-edit", "empty", "return", "return-edit", "observe")
GROUP_DEFAULT_VALUES = [
    [["Beta", "Beta", "Alpha", "Beta"]] * 4,
    [["Alpha", "Beta", "Alpha"]] * 4,
    [["Alpha", "Alpha", "Alpha"], ["Alpha", "Beta", "Alpha"]] * 2,
    [["Beta", "Beta"]] * 4,
    [[]] * 4,
    [["Beta", "Beta", "Alpha", "Beta"], []] * 2,
    [["Alpha"]] * 4,
    [["Alpha"]] * 4,
]


def check_group_defaults(capture):
    assert capture["successful"] and "producer_error" not in capture and capture["reference_version"] == "1.66.1"
    assert capture["runtime"] in ("python", "rust") and capture["finishes"] == [0] * 8
    assert capture["cleanup"]["websocket_closed"] and capture["cleanup"]["server_stopped" if capture["runtime"] == "python" else "caller_server_stopped"]
    assert len(capture["frames"]) == 79 and len(capture["elements"]) == 40
    runs = color_runs(capture, ("button_group", "json"))
    normalized, sessions, run_ids, identities, previous = [], set(), set(), [{}, {}, {}, {}], None
    for index, (phase, run) in enumerate(zip(GROUP_DEFAULT_PHASES, runs, strict=True)):
        request = run["request"]
        assert request.query_string == "probe=group-defaults&phase=" + phase and not request.is_history_navigation
        assert len(run["sessions"]) == 1 and run["finishes"] == [0]
        session = run["sessions"][0]
        assert session.initialize.environment_info.streamlit_version == "1.66.1"
        sessions.add(session.initialize.session_id)
        run_ids.add(session.script_run_id)
        assert [entry[0] for entry in run["entries"]] == ["button_group"] * 4 + ["json"]
        empty = phase == "empty"
        alternate = phase in ("default", "default-edit")
        current = []
        for position, (_, widget, element) in enumerate(run["entries"][:4]):
            assert widget.label == GROUP_WIDTH_LABELS[position]
            assert [option.content for option in widget.options] == ([] if empty else ["Alpha", "Beta"])
            assert widget.style == (1 if position < 2 else 0) and widget.click_mode == 1
            assert list(widget.default) == ([] if empty else [0, 0, 0] if alternate else [1, 1, 0, 1])
            assert not widget.disabled and not widget.required and not widget.ignore_rerun
            assert not widget.form_id and not widget.HasField("help") and widget.label_visibility.value == 0
            sync = empty and position % 2 == 1
            assert widget.set_value == sync and not widget.raw_values
            assert element.HasField("has_one_shot_effect") == sync and element.has_one_shot_effect == sync
            assert element.width_config.use_content
            identity_class = (2 if empty else 1 if alternate else 0) if position % 2 == 0 else 0
            assert widget.id == identities[position].setdefault(identity_class, widget.id)
            current.append(widget.id)
        assert len(set(current)) == 4
        incoming = request.widget_states.widgets
        if phase in ("edit", "default-edit", "return-edit"):
            assert len(incoming) == 4 and [widget.id for widget in incoming] == previous
            assert all(widget.WhichOneof("value") == "string_array_value" and list(widget.string_array_value.data) == (["Alpha", "Beta", "Alpha"] if phase == "edit" else ["Beta", "Beta"] if phase == "default-edit" else ["Alpha"]) for widget in incoming)
        else:
            assert not incoming
        values = GROUP_DEFAULT_VALUES[index]
        assert json.loads(run["entries"][-1][1].body) == {"phase": phase, "values": values}
        assert [entry["delta_path"] for entry in capture["elements"][index * 5:index * 5 + 5]] == [[0, i] for i in range(5)]
        fields = []
        for kind, _, element in run["entries"]:
            view = MessageToDict(element, preserving_proto_field_name=True)
            if kind == "json":
                view[kind]["body"] = json.loads(view[kind]["body"])
            else:
                view[kind].pop("id")
            fields.append(view)
        normalized.append(fields)
        previous = current
    assert [len(set(identity.values())) for identity in identities] == [3, 1, 3, 1]
    assert len(sessions) == 1 and len(run_ids) == 8
    return normalized



@pytest.mark.parametrize("root", (PYTHON, RUST), ids=("python", "rust"))
def test_button_group_duplicate_defaults_and_dynamic_state(root):
    check_group_defaults(read(root / "group-defaults/trace.json"))


def test_button_group_defaults_complete_elements_match_reference():
    captures = [read(root / "group-defaults/trace.json") for root in (PYTHON, RUST)]
    assert captures[0]["producer_sources_sha256"] == captures[1]["producer_sources_sha256"] and captures[1]["semantic_match"] is True
    assert check_group_defaults(captures[0]) == check_group_defaults(captures[1])


def test_button_group_defaults_before_rejects_first_call_and_capture_retains_prefix():
    capture = read(RUST / "group-defaults/before/trace.json")
    assert not capture.get("successful", False) and capture["semantic_match"] is False
    assert capture["producer_error"] == "KeyError: 'Plain pills'" and capture["finishes"] == [0]
    assert capture["cleanup"]["caller_server_stopped"]
    assert len(capture["frames"]) == 5 and len(capture["elements"]) == 1
    runs = color_runs(capture, ("markdown",))
    assert len(runs) == 1 and "button-group defaults must fit the selection mode" in runs[0]["entries"][0][1].body
    with pytest.raises((AssertionError, KeyError)):
        check_group_defaults(capture)


@pytest.mark.parametrize("mutation", ("default-order", "default-count", "keyed-id", "unkeyed-id", "keyed-reset", "revived", "empty-sync", "input-order"))
def test_button_group_defaults_gate_rejects_coherent_wrong_wire(mutation):
    capture = read(PYTHON / "group-defaults/trace.json")
    initial_id = capture["elements"][0]["fields"]["id"]
    target = {"default-order": 0, "default-count": 2, "keyed-id": 2, "unkeyed-id": 2, "keyed-reset": 2, "revived": 5, "empty-sync": 4, "input-order": 1}[mutation]
    run = -1
    for frame in capture["frames"]:
        client = frame["direction"] == "client->server"
        if client:
            run += 1
        if run != target:
            continue
        message = BackMsg() if client else ForwardMsg()
        message.ParseFromString(base64.b64decode(frame["base64"]))
        if client and mutation == "input-order":
            message.rerun_script.widget_states.widgets[0].string_array_value.data[:] = ["Alpha", "Alpha", "Beta"]
        elif not client and message.WhichOneof("type") == "delta":
            element = message.delta.new_element
            kind = element.WhichOneof("type")
            if kind == "button_group" and element.button_group.label == "Plain pills" and mutation in ("default-order", "default-count"):
                element.button_group.default[:] = [0, 1, 1, 1] if mutation == "default-order" else [0]
            elif kind == "button_group" and element.button_group.label == "Keyed pills" and mutation == "keyed-id":
                element.button_group.id = "$$ID-wrong-default-keyed"
            elif kind == "button_group" and element.button_group.label == "Plain pills" and mutation == "unkeyed-id":
                element.button_group.id = initial_id
            elif kind == "button_group" and element.button_group.label == "Keyed pills" and mutation == "empty-sync":
                element.button_group.set_value = False
                element.ClearField("has_one_shot_effect")
            elif kind == "json" and mutation in ("keyed-reset", "revived"):
                report = json.loads(element.json.body)
                report["values"][1] = ["Alpha", "Alpha", "Alpha"] if mutation == "keyed-reset" else ["Beta", "Beta"]
                element.json.body = json.dumps(report)
            else:
                continue
        else:
            continue
        raw = message.SerializeToString()
        frame.update(base64=base64.b64encode(raw).decode(), bytes=len(raw), message=MessageToDict(message, preserving_proto_field_name=True))
    capture["elements"] = [{"kind": m.delta.new_element.WhichOneof("type"), "fields": MessageToDict(getattr(m.delta.new_element, m.delta.new_element.WhichOneof("type")), preserving_proto_field_name=True),
                            "delta_path": list(m.metadata.delta_path)} for m in frames(capture) if isinstance(m, ForwardMsg) and m.WhichOneof("type") == "delta"]
    with pytest.raises(AssertionError):
        check_group_defaults(capture)


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


def form_identity_runs(capture, *, allow_selectbox=False):
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
                assert entry_kind in ("number_input", "text_input", "button", "json") or (allow_selectbox and entry_kind == "selectbox")
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


FORM_MOVE_STAGES = ("load", "root-edit", "alpha", "beta", "beta-draft", "beta-submit", "root-return", "alpha-return")
FORM_MOVE_PHASES = ("root", "root", "form-a", "form-b", "form-b", "form-b", "root", "form-a")
FORM_MOVE_VALUES = ((4, "base", 4, None), (7, "EDIT", 9, None), (7, "EDIT", 4, False), (7, "EDIT", 4, False),
                    (7, "EDIT", 4, False), (8, "NEXT", 6, True), (8, "NEXT", 4, None), (8, "NEXT", 4, False))


def form_move_messages(capture):
    created = [event for stage in capture["stages"] for event in stage["events"]["events"] if event["method"] == "Network.webSocketCreated"]
    assert len(created) == 1
    ws_id = created[0]["params"]["requestId"]
    port = 8619 if capture["runtime"] == "python" else 8599
    assert created[0]["params"]["url"] == f"ws://127.0.0.1:{port}/_stcore/stream"
    previous_sequence, output = 0, []
    for stage in capture["stages"]:
        events = stage["events"]
        assert not events["hasMore"] and not events["truncated"]
        for event in events["events"]:
            assert previous_sequence < event["sequence"] <= events["cursor"]
            previous_sequence = event["sequence"]
            if event["method"] not in ("Network.webSocketFrameSent", "Network.webSocketFrameReceived"):
                continue
            assert event["params"]["requestId"] == ws_id
            response = event["params"]["response"]
            assert response["opcode"] == 2
            raw = base64.b64decode(response["payloadData"], validate=True)
            message = BackMsg() if event["method"].endswith("Sent") else ForwardMsg()
            message.ParseFromString(raw)
            output.append(message)
    assert len(output) == 98
    return output


def check_form_move_ui(capture, folder):
    import hashlib
    from PIL import Image

    assert capture["collection_complete"] and capture["reference_version"] == "1.66.1"
    assert capture["runtime"] in ("python", "rust")
    assert capture["visual_review"]["all_stage_images_inspected"] and capture["visual_review"]["phase_alignment"]
    assert capture["cleanup"]["owned_servers_stopped"] and capture["cleanup"]["owned_tab_closed"]
    assert capture["cleanup"]["ports_without_listeners"] == [8599, 8619]
    assert [stage["stage"] for stage in capture["stages"]] == list(FORM_MOVE_STAGES)
    messages = form_move_messages(capture)
    for stage, phase, values in zip(capture["stages"], FORM_MOVE_PHASES, FORM_MOVE_VALUES, strict=True):
        assert stage["action_and_capture_calls_separate"]
        dom = stage["dom"]
        assert dom["viewport"] == {"width": 1463, "height": 780, "dpr": 1.75} and not dom["exceptions"]
        assert dom["location"] == [{"label": "Location", "value": phase}]
        expected_inputs = (8, "NEXT", 6) if stage["stage"] == "beta-draft" else values[:3]
        labels = ["Number " + phase, "Note " + phase, "Unkeyed"]
        assert dom["widgets"] == [{"label": label, "value": str(value), "type": kind, "disabled": False, "in_form": phase != "root"}
                                  for label, value, kind in zip(labels, expected_inputs, ("number", "text", "number"), strict=True)]
        assert len(dom["forms"]) == (0 if phase == "root" else 1)
        if dom["forms"]:
            assert dom["forms"][0]["labels"] == labels
            assert dom["forms"][0]["buttons"][-1] == {"text": "Apply", "disabled": False}
        submitted = "NULL" if values[3] is None else str(values[3]).lower()
        assert dom["reports"] == ['{"phase":"' + phase + '""number":' + str(values[0]) + '"note":"' + values[1]
                                  + '""unkeyed":' + str(values[2]) + '"submitted":' + submitted + '"native":[0:' + str(values[0]) + '1:"' + values[1] + '"]}']
        if stage["stage"] == "beta-draft":
            assert not stage["events"]["events"]
        path = folder / stage["screenshot"]
        integrity = stage["screenshot_integrity"]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == integrity["sha256"]
        with Image.open(path) as image:
            assert image.format == integrity["format"] == "JPEG"
            assert image.size == (integrity["width"], integrity["height"]) == (1463, 780)
    derived = {"frames": [{"direction": "client->server" if isinstance(message, BackMsg) else "server->client",
                            "bytes": len(message.SerializeToString()), "base64": base64.b64encode(message.SerializeToString()).decode(),
                            "message": MessageToDict(message, preserving_proto_field_name=True)} for message in messages]}
    runs, _ = form_identity_runs(derived, allow_selectbox=True)
    phases = ("root", "root", "root", "root", "form-a", "form-b", "form-b", "root", "form-a")
    values = ((4, "base", 4, None), (7, "base", 4, None), (7, "EDIT", 4, None), FORM_MOVE_VALUES[1],
              FORM_MOVE_VALUES[2], FORM_MOVE_VALUES[3], FORM_MOVE_VALUES[5], FORM_MOVE_VALUES[6], FORM_MOVE_VALUES[7])
    input_values = ((7, "base", 4), (7, "EDIT", 4), (7, "EDIT", 9), (7, "EDIT", 9),
                    (7, "EDIT", 4), (8, "NEXT", 6), (8, "NEXT", 6), (8, "NEXT", 4))
    assert len(runs) == 9
    ids, contexts, sessions, run_ids, previous_unkeyed = {}, {}, set(), set(), None
    for index, (run, phase, expected) in enumerate(zip(runs, phases, values, strict=True)):
        assert run["finishes"] == [0] and len(run["sessions"]) == 1
        session = run["sessions"][0]
        assert session.initialize.environment_info.streamlit_version == "1.66.1"
        sessions.add(session.initialize.session_id)
        run_ids.add(session.script_run_id)
        entries = list(run["entries"])
        selector_kind, selector, selector_path = entries.pop(0)
        assert selector_kind == "selectbox" and selector_path == [0, 0]
        assert selector.label == "Location" and list(selector.options) == ["root", "form-a", "form-b"] and not selector.form_id
        assert selector.id == ids.setdefault("identity_location", selector.id)
        form_id = "alpha" if phase == "form-a" else "beta" if phase == "form-b" else ""
        if form_id:
            kind, form, path = entries.pop(0)
            assert kind == "add_block:form" and path == [0, 1] and form.form_id == form_id
        assert [entry[0] for entry in entries] == ["number_input", "text_input", "number_input"] + (["button"] if form_id else []) + ["json"]
        for offset, (_, widget, path) in enumerate(entries[:-1]):
            assert path == ([0, 1, offset] if form_id else [0, offset + 1]) and widget.form_id == form_id
        assert entries[-1][2] == ([0, 2] if form_id else [0, 4])
        number, note, unkeyed = [entry[1] for entry in entries[:3]]
        assert (number.label, note.label, unkeyed.label) == ("Number " + phase, "Note " + phase, "Unkeyed")
        assert number.help == note.help == phase
        assert number.default == unkeyed.default == 4 and note.default == "base" and note.max_chars == 5
        for key, widget in (("number", number), ("note", note)):
            assert widget.id == ids.setdefault(key, widget.id)
        assert unkeyed.id == contexts.setdefault(form_id, unkeyed.id)
        if form_id:
            button = entries[3][1]
            assert button.is_form_submitter and button.label == "Apply"
            assert button.id == ids.setdefault("apply", button.id)
        assert json.loads(entries[-1][1].body) == {"phase": phase, "number": expected[0], "note": expected[1],
                                                 "unkeyed": expected[2], "submitted": expected[3], "native": list(expected[:2])}
        request = run["request"]
        assert request.query_string == "probe=form-identity&ui=on" and not request.is_history_navigation
        incoming = request.widget_states.widgets
        if index == 0:
            assert not incoming
        else:
            assert len(incoming) == (5 if index == 6 else 4)
            assert [(widget.id, widget.WhichOneof("value")) for widget in incoming[:4]] == [
                (ids["identity_location"], "string_value"), (ids["number"], "int_value"),
                (ids["note"], "string_value"), (previous_unkeyed, "int_value")]
            assert incoming[0].string_value == phase
            assert (incoming[1].int_value, incoming[2].string_value, incoming[3].int_value) == input_values[index - 1]
            if index == 6:
                assert incoming[4].id == ids["apply"] and incoming[4].WhichOneof("value") == "trigger_value" and incoming[4].trigger_value
        previous_unkeyed = unkeyed.id
    assert len(sessions) == 1 and len(run_ids) == 9 and len(set(contexts.values())) == 3
    hashes = [message.hash for message in messages if isinstance(message, ForwardMsg) and message.WhichOneof("type") == "delta"
              and message.delta.new_element.WhichOneof("type") == "button"]
    assert len(hashes) == 4 and hashes[0] != hashes[1] and hashes[1] == hashes[2] and hashes[0] == hashes[3]


def test_python_browser_form_migration_reference():
    folder = PYTHON / "form-identity/ui"
    capture = read(folder / "trace.json")
    assert capture["successful"] and capture["semantic_match"]
    check_form_move_ui(capture, folder)


def test_native_browser_form_migration_remains_a_known_hash_failure():
    folder = RUST / "form-identity/ui"
    capture = read(folder / "trace.json")
    assert not capture["successful"] and not capture["semantic_match"] and capture["collection_complete"]
    assert [widget["value"] for widget in capture["stages"][4]["dom"]["widgets"]] == ["8", "NEXT", "6"]
    messages = form_move_messages(capture)
    requests = [message.rerun_script for message in messages if isinstance(message, BackMsg)]
    submit = requests[6].widget_states.widgets
    assert (submit[1].int_value, submit[2].string_value, submit[3].int_value, submit[4].trigger_value) == (7, "EDIT", 4, True)
    buttons = [message for message in messages if isinstance(message, ForwardMsg) and message.WhichOneof("type") == "delta"
               and message.delta.new_element.WhichOneof("type") == "button"]
    assert [message.delta.new_element.button.form_id for message in buttons] == ["alpha", "beta", "beta", "alpha"]
    assert len({message.hash for message in buttons}) == 1
    assert len({message.delta.new_element.button.id for message in buttons}) == 1
    reports = [json.loads(message.delta.new_element.json.body) for message in messages if isinstance(message, ForwardMsg)
               and message.WhichOneof("type") == "delta" and message.delta.new_element.WhichOneof("type") == "json"]
    assert len(reports) == 9
    assert reports[6] == {"phase": "form-b", "number": 7, "note": "EDIT", "unkeyed": 4,
                          "submitted": True, "native": [7, "EDIT"]}
    assert [(report["number"], report["note"], report["unkeyed"]) for report in reports[7:]] == [(7, "EDIT", 4)] * 2
    with pytest.raises(AssertionError):
        check_form_move_ui(capture, folder)


@pytest.mark.parametrize("mutation", ("button-hash", "submit-values", "draft-dom", "screenshot"))
def test_browser_form_migration_gate_rejects_damage(mutation):
    folder = PYTHON / "form-identity/ui"
    capture = read(folder / "trace.json")
    if mutation == "draft-dom":
        capture["stages"][4]["dom"]["widgets"][0]["value"] = "7"
    elif mutation == "screenshot":
        capture["stages"][2]["screenshot_integrity"]["sha256"] = "wrong"
    else:
        messages = form_move_messages(capture)
        first_button_hash = next(message.hash for message in messages if isinstance(message, ForwardMsg) and message.WhichOneof("type") == "delta"
                                 and message.delta.new_element.WhichOneof("type") == "button")
        stage = capture["stages"][3 if mutation == "button-hash" else 5]
        for event in stage["events"]["events"]:
            method = event["method"]
            if mutation == "button-hash" and method == "Network.webSocketFrameReceived":
                message = ForwardMsg()
                message.ParseFromString(base64.b64decode(event["params"]["response"]["payloadData"]))
                if message.WhichOneof("type") != "delta" or message.delta.new_element.WhichOneof("type") != "button":
                    continue
                message.hash = first_button_hash
            elif mutation == "submit-values" and method == "Network.webSocketFrameSent":
                message = BackMsg()
                message.ParseFromString(base64.b64decode(event["params"]["response"]["payloadData"]))
                widgets = message.rerun_script.widget_states.widgets
                widgets[1].int_value, widgets[2].string_value, widgets[3].int_value = 7, "EDIT", 4
            else:
                continue
            event["params"]["response"]["payloadData"] = base64.b64encode(message.SerializeToString()).decode()
            break
    with pytest.raises(AssertionError):
        check_form_move_ui(capture, folder)
