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
    INPUTS_SOURCE_PINS,
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
        "source": {"file": INPUTS_SOURCE_PINS["python"][0], "sha256": INPUTS_SOURCE_PINS["python"][1]},
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
    elif mutation == "wrong_source":
        observation["source"]["sha256"] = "0" * 64
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
    assert outcome["counts"] == {"expected": 11, "executed": 11, "asserted": 11}
    assert tuple(check["check"] for check in outcome["checks"]) == INPUTS_REQUIRED


@pytest.mark.parametrize("mutation", [
    "wrong_wire_default", "wrong_wire_options", "wrong_state", "wrong_state_field",
    "wrong_repr", "wrong_dom", "wrong_finish", "exception_element", "exception_dom",
    "missing_rerun", "extra_rerun", "missing_png", "png_sha", "wrong_source",
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


def test_contract_pins_the_committed_sources():
    for side, (relative, pinned) in INPUTS_SOURCE_PINS.items():
        path = HERE.parents[1] / relative
        assert path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest() == pinned, side


def test_states_dom_and_reprs_cover_every_stage():
    for name in INPUTS_STAGES:
        assert set(INPUTS_STATES[name]) <= set(INPUTS_WIRE)
        assert set(INPUTS_DOM[name]) == {"radio", "multiselect", "number", "textarea"}
        assert len(INPUTS_REPRS[name]) == len(INPUTS_WIRE)
