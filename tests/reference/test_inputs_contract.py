"""Unit tests of the strict input-widget contract (journey-inputs-v1)."""
from __future__ import annotations

import copy
import hashlib
import pathlib
import sys

import pytest

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "browser"))

from inputs_contract import (  # noqa: E402
    INPUTS_DOM,
    INPUTS_REPRS,
    INPUTS_REQUIRED,
    INPUTS_SOURCE_FILES,
    INPUTS_STAGES,
    INPUTS_STATES,
    INPUTS_WIRE,
    inputs_result,
)

PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"not-a-real-image-but-magic-and-hash-are-checked"
ARRAY_FIELDS = ("string_array_value", "double_array_value")


def frame(kind, direction="server->client", **extra):
    summary = {"type": kind, **extra}
    return {"direction": direction, "timestamp": 0.0, "summary": summary}


def widget_frames():
    """The four first-render widget deltas, straight from the measured table."""
    frames = []
    for label, config in INPUTS_WIRE.items():
        widget = {"id": f"$$ID-{label}", **config}
        frames.append(frame("delta", delta={"element": "widget", "widget": widget}))
    return frames


def stage_frames(name):
    states = INPUTS_STATES[name]
    entries = []
    for label, state in states.items():
        entry = {"id": f"$$ID-{label}", "value_field": state["field"]}
        if state["field"] in ARRAY_FIELDS:
            entry["value_full"] = {"data": state["data"]}
        else:
            entry["value"] = state["data"]
        entries.append(entry)
    frames = [frame("rerun_script", "client->server", rerun_script={"widget_states": entries})]
    frames.append(frame("new_session", new_session={"script_run_id": f"run-{name}", "session_id": "session-a"}))
    frames.append(frame("session_status_changed", session_status_changed={"script_is_running": True, "run_on_save": False}))
    frames.append(frame("delta", delta={"element": "markdown", "body": "scaffold"}))
    frames.append(frame("script_finished", script_finished={"status": 0}))
    frames.append(frame("session_status_changed", session_status_changed={"script_is_running": False, "run_on_save": False}))
    return frames


def observation(tmp_path, **faults):
    stages = []
    for name in INPUTS_STAGES:
        frames = widget_frames() + stage_frames(name) if name == INPUTS_STAGES[0] else stage_frames(name)
        dom = {
            "markdowns": list(INPUTS_REPRS[name]),
            "exceptions": [],
            **{key: copy.deepcopy(INPUTS_DOM[name][key]) for key in ("radio", "multiselect", "number", "textarea")},
        }
        stages.append({"name": name, "new_frames": frames, "dom": dom})
    observation = {
        "journey": "inputs-sequence",
        "contract": "journey-inputs-v1",
        "scope": "PYTHON SIDE ONLY",
        "url": "http://127.0.0.1:8608/",
        "source": {"file": INPUTS_SOURCE_FILES["python"]},
        "capture_sources": {},
        "stages": stages,
        "ipc_dir": str(tmp_path),
    }
    for index, stage in enumerate(stages):
        name = f"{stage['name']}.png"
        (tmp_path / name).write_bytes(PNG_BYTES)
        stage["screenshot"] = {"file": name, "sha256": hashlib.sha256(PNG_BYTES).hexdigest()}
    mutation = faults.pop("mutation", None)
    target = stages[-1]
    if mutation == "wrong_wire_default":
        stages[0]["new_frames"][0]["summary"]["delta"]["widget"]["default"] = 9
    elif mutation == "wrong_wire_options":
        stages[0]["new_frames"][0]["summary"]["delta"]["widget"]["options"] = ["email", "sms"]
    elif mutation == "wrong_state":
        for state in target["new_frames"][0]["summary"]["rerun_script"]["widget_states"]:
            if state["id"] == "$$ID-Channel":
                state["value"] = "push"
    elif mutation == "wrong_state_field":
        for state in target["new_frames"][0]["summary"]["rerun_script"]["widget_states"]:
            if state["id"] == "$$ID-Count":
                state["value_field"] = "double_value"
    elif mutation == "wrong_repr":
        target["dom"]["markdowns"] = [*INPUTS_REPRS[target["name"]][:-1], "count=42 type=float"]
    elif mutation == "wrong_dom":
        target["dom"]["number"]["value"] = "7"
    elif mutation == "wrong_finish":
        for frame_ in target["new_frames"]:
            if frame_["summary"]["type"] == "script_finished":
                frame_["summary"]["script_finished"]["status"] = 2
    elif mutation == "exception_element":
        target["new_frames"].insert(2, frame("delta", delta={"element": "exception"}))
    elif mutation == "exception_dom":
        target["dom"]["exceptions"] = ["StreamlitDuplicateElementKey"]
    elif mutation == "missing_rerun":
        target["new_frames"] = [f for f in target["new_frames"] if f["summary"]["type"] != "rerun_script"]
    elif mutation == "extra_rerun":
        target["new_frames"].insert(0, frame("rerun_script", "client->server", rerun_script={"widget_states": []}))
    elif mutation == "missing_png":
        (tmp_path / f"{target['name']}.png").unlink()
    elif mutation == "png_sha":
        target["screenshot"]["sha256"] = "0" * 64
    elif mutation == "wrong_contract":
        observation["contract"] = "journey-inputs-v0"
    elif mutation == "missing_stage":
        observation["stages"] = observation["stages"][:4]
    elif mutation == "reordered_stages":
        observation["stages"][1], observation["stages"][2] = observation["stages"][2], observation["stages"][1]
    assert not faults, faults
    return observation


def result(tmp_path, **faults):
    return inputs_result(observation=observation(tmp_path, **faults))


def test_complete_synthetic_model_passes_every_check(tmp_path):
    outcome = result(tmp_path)
    assert outcome["ok"], outcome["failures"]
    assert outcome["counts"] == {"expected": 10, "executed": 10, "asserted": 10}
    assert tuple(check["check"] for check in outcome["checks"]) == INPUTS_REQUIRED


@pytest.mark.parametrize("mutation", [
    "wrong_wire_default", "wrong_wire_options", "wrong_state", "wrong_state_field",
    "wrong_repr", "wrong_dom", "wrong_finish", "exception_element", "exception_dom",
    "missing_rerun", "extra_rerun", "missing_png", "png_sha",
    "wrong_contract", "missing_stage", "reordered_stages",
])
def test_known_mutations_fail(tmp_path, mutation):
    outcome = result(tmp_path, mutation=mutation)
    assert not outcome["ok"], (mutation, outcome["counts"])


def test_degenerate_observations_fail_closed():
    for observation in (None, {}, [], {"journey": "inputs-sequence"}):
        outcome = inputs_result(observation=observation)
        assert not outcome["ok"] and outcome["counts"]["expected"] == len(INPUTS_REQUIRED)


def test_first_stage_snapshots_pin_the_load_run_without_states():
    assert INPUTS_STATES[INPUTS_STAGES[0]] == {}
    assert all(INPUTS_STATES[name] for name in INPUTS_STAGES[1:])


def test_commit_on_blur_semantics_is_frozen_in_the_tables():
    """number_input and text_area commit on blur: stage 04 carries the old
    count while its DOM shows the typed 42, and stage 05 commits the 42."""
    assert INPUTS_STATES["04-number-42"]["Count"]["data"] == 7
    assert INPUTS_DOM["04-number-42"]["number"]["value"] == "42"
    assert INPUTS_STATES["05-textarea-append"]["Count"]["data"] == 42
    assert INPUTS_DOM["05-textarea-append"]["textarea"]["value"].endswith("third")


def test_states_dom_and_reprs_cover_every_stage():
    for name in INPUTS_STAGES:
        assert set(INPUTS_STATES[name]) <= set(INPUTS_WIRE)
        assert set(INPUTS_DOM[name]) == {"radio", "multiselect", "number", "textarea"}
        assert len(INPUTS_REPRS[name]) == len(INPUTS_WIRE)


def test_source_fingerprints_do_not_gate_functional_evidence(tmp_path):
    for source in ({"file": "historical-app.py", "sha256": "changed"}, {"file": "historical-app.py"}, None):
        observed = observation(tmp_path)
        observed["source"] = source
        outcome = inputs_result(observation=observed)
        assert outcome["ok"], outcome["failures"]


TEXT_UI_STAGES = ("01-load", "02-edit", "03-peer-rerun", "04-empty", "05-restore")
TEXT_UI_VALUES = ("first line\nsecond line", "lineA\nlineB🧊", "lineA\nlineB🧊", "", "first line\nsecond line")
TEXT_UI_ROOTS = (
    HERE / "reference-browser/inputs/text-area-ui/settled",
    HERE.parent / "browser/rust-inputs/text-area-ui/settled",
)


def check_text_area_ui(root, stages):
    """Check raw browser input, full completions, rendered state and screenshot binding."""
    import base64
    import io
    from PIL import Image
    from streamlit.proto.BackMsg_pb2 import BackMsg
    from streamlit.proto.ForwardMsg_pb2 import ForwardMsg

    sessions, runs, identities, requests = set(), set(), [], set()
    previous_cursor = None
    for index, (name, stage, value) in enumerate(zip(TEXT_UI_STAGES, stages, TEXT_UI_VALUES, strict=True)):
        assert stage["name"] == name and stage["truncated"] is False
        if previous_cursor is not None:
            assert stage["cursor_before"] == previous_cursor
        previous_cursor = stage["cursor_after"]
        events = stage["events"]
        assert len(events) == 13
        sequences = [e["sequence"] for e in events]
        assert stage["cursor_before"] < sequences[0] <= sequences[-1] <= previous_cursor
        assert sequences == sorted(set(sequences))
        messages = []
        for i, event in enumerate(events):
            assert event["method"] == ("Network.webSocketFrameSent" if i == 0 else "Network.webSocketFrameReceived")
            requests.add(event["params"]["requestId"])
            response = event["params"]["response"]
            assert response["opcode"] == 2
            msg = BackMsg() if i == 0 else ForwardMsg()
            msg.ParseFromString(base64.b64decode(response["payloadData"], validate=True))
            messages.append(msg)
        assert [m.WhichOneof("type") for m in messages] == [
            "rerun_script", "new_session", "session_status_changed", *(["delta"] * 8),
            "script_finished", "session_status_changed",
        ]
        session = messages[1].new_session
        assert session.initialize.environment_info.streamlit_version == "1.66.1"
        sessions.add(session.initialize.session_id)
        runs.add(session.script_run_id)
        assert messages[2].session_status_changed.script_is_running
        assert messages[-2].script_finished == 0
        assert not messages[-1].session_status_changed.script_is_running
        elements = [m.delta.new_element for m in messages[3:11]]
        assert [e.WhichOneof("type") for e in elements] == ["radio", "multiselect", "number_input", "text_area", *(["markdown"] * 4)]
        ids = [getattr(e, kind).id for e, kind in zip(elements, ("radio", "multiselect", "number_input", "text_area"))]
        identities.append(ids)
        assert len(set(ids)) == 4
        area = elements[3]
        assert area.text_area.label == "Note" and area.text_area.default == TEXT_UI_VALUES[0]
        assert not area.text_area.set_value
        assert area.height_config.pixel_height == 122 and area.width_config.use_stretch
        channel = "email" if index < 2 else "sms"
        echo = [f"channel='{channel}'", "tags=['alpha']", "count=7 type=int", "note=" + repr(value)]
        assert [e.markdown.body for e in elements[4:]] == echo
        states = messages[0].rerun_script.widget_states.widgets
        if index == 0:
            assert not states
        else:
            assert [w.id for w in states] == ids
            assert [w.WhichOneof("value") for w in states] == ["string_value", "string_array_value", "int_value", "string_value"]
            assert (states[0].string_value, list(states[1].string_array_value.data), states[2].int_value, states[3].string_value) == (channel, ["alpha"], 7, value)
        dom, after = stage["dom"], stage["dom_after"]
        assert dom["textarea"]["value"] == after["value"] == value
        assert dom["markdowns"] == after["markdowns"] == echo
        assert dom["exceptions"] == []
        assert [r["checked"] for r in dom["radio"]] == [index < 2, index >= 2, False]
        assert dom["viewport"] == after["viewport"] == {"width": 1463, "height": 724, "dpr": 1.75}
        assert dom["textarea"]["height"] == pytest.approx(92, abs=0.01)
        assert dom["textarea"]["width"] == pytest.approx(702.85718, abs=0.01)
        outer = next(a for a in dom["textarea"]["ancestors"] if a["testId"] == "stTextArea")
        assert outer["height"] == pytest.approx(121.14286, abs=0.01)
        image_bytes = (root / stage["screenshot"]["file"]).read_bytes()
        assert hashlib.sha256(image_bytes).hexdigest() == stage["screenshot"]["sha256"]
        with Image.open(io.BytesIO(image_bytes)) as image:
            assert image.format == "JPEG" and image.size == (1463, 724)
            image.load()
    assert len(sessions) == len(requests) == 1 and len(runs) == 5
    assert all(ids == identities[0] for ids in identities)


@pytest.mark.parametrize("root", TEXT_UI_ROOTS, ids=("python", "rust"))
def test_frozen_real_text_area_ui(root):
    import json
    stages = [json.loads((root / (name + ".json")).read_text(encoding="utf-8")) for name in TEXT_UI_STAGES]
    browser = json.loads((root / "browser.json").read_text(encoding="utf-8"))
    assert browser["stages"] == list(TEXT_UI_STAGES) and browser["events"] == 65
    assert browser["viewport_override"] is False and browser["browser_logs"] == []
    check_text_area_ui(root, stages)


@pytest.mark.parametrize("fault", ("input", "dom", "echo", "height", "truncated", "missing_frame", "png"))
def test_real_text_area_ui_rejects_evidence_damage(fault):
    import json
    root = TEXT_UI_ROOTS[1]
    stages = [json.loads((root / (name + ".json")).read_text(encoding="utf-8")) for name in TEXT_UI_STAGES]
    stage = stages[2]
    if fault == "input":
        stage["events"][0]["params"]["response"]["payloadData"] = stages[1]["events"][0]["params"]["response"]["payloadData"]
    elif fault == "dom":
        stage["dom"]["textarea"]["value"] = "lost"
    elif fault == "echo":
        stage["dom_after"]["markdowns"] = []
    elif fault == "height":
        stage["dom"]["textarea"]["height"] = 101
    elif fault == "truncated":
        stage["truncated"] = True
    elif fault == "missing_frame":
        stage["events"].pop()
    else:
        stage["screenshot"]["sha256"] = "0" * 64
    with pytest.raises(AssertionError):
        check_text_area_ui(root, stages)
