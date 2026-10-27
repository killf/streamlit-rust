"""Unit tests of the strict temporal-slider contract (journey-temporal-v1)."""
from __future__ import annotations

import hashlib
import pathlib
import sys

import pytest

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "browser"))

from temporal_contract import (  # noqa: E402
    TEMPORAL_INPUTS,
    TEMPORAL_REPRS,
    TEMPORAL_REQUIRED,
    TEMPORAL_SOURCE_FILES,
    TEMPORAL_STAGES,
    TEMPORAL_STATES,
    TEMPORAL_WIRE,
    temporal_result,
)

PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"not-a-real-image-but-magic-and-hash-are-checked"


def frame(kind, direction="server->client", **extra):
    summary = {"type": kind, **extra}
    return {"direction": direction, "timestamp": 0.0, "summary": summary}


def slider_frames():
    """The six first-render slider deltas, straight from the measured table."""
    frames = []
    for label, config in TEMPORAL_WIRE.items():
        widget = {"id": f"$$ID-{label}", "label": label, **config}
        frames.append(frame("delta", delta={"element": "slider", "widget": widget}))
    return frames


def stage_frames(name):
    states = TEMPORAL_STATES[name]
    frames = [frame("rerun_script", "client->server",
                    rerun_script={"widget_states": [{"id": f"$$ID-{label}", "value_field": "double_array_value",
                                                     "value_full": {"data": data}} for label, data in states.items()]})]
    frames.append(frame("new_session", new_session={"script_run_id": f"run-{name}", "session_id": "session-a"}))
    frames.append(frame("session_status_changed", session_status_changed={"script_is_running": True, "run_on_save": False}))
    frames.append(frame("delta", delta={"element": "markdown", "body": "scaffold"}))
    frames.append(frame("script_finished", script_finished={"status": 0}))
    frames.append(frame("session_status_changed", session_status_changed={"script_is_running": False, "run_on_save": False}))
    return frames


def observation(tmp_path, **faults):
    stages = []
    for name in TEMPORAL_STAGES:
        frames = slider_frames() + stage_frames(name) if name == TEMPORAL_STAGES[0] else stage_frames(name)
        dom = {
            "markdowns": list(TEMPORAL_REPRS[name]),
            "sliders": [{"label": label, "inputs": [{"value": value} for value in values]} for label, values in TEMPORAL_INPUTS[name].items()],
            "exceptions": [],
        }
        stages.append({"name": name, "new_frames": frames, "dom": dom})
    observation = {
        "journey": "temporal-sequence",
        "contract": "journey-temporal-v1",
        "scope": "PYTHON SIDE ONLY",
        "url": "http://127.0.0.1:8606/",
        "source": {"file": TEMPORAL_SOURCE_FILES["python"]},
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
    if mutation == "wrong_wire_step":
        stages[0]["new_frames"][1]["summary"]["delta"]["widget"]["step"] = 1.0
    elif mutation == "wrong_state":
        for state in target["new_frames"][0]["summary"]["rerun_script"]["widget_states"]:
            if state["id"] == "$$ID-date":
                state["value_full"]["data"] = [42.0]
    elif mutation == "wrong_repr":
        target["dom"]["markdowns"] = [*TEMPORAL_REPRS[target["name"]][:-1], "time=datetime.time(9, 99)|time"]
    elif mutation == "wrong_input":
        target["dom"]["sliders"][0]["inputs"][0]["value"] = "1"
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
        observation["contract"] = "journey-temporal-v0"
    elif mutation == "missing_stage":
        observation["stages"] = observation["stages"][:12]
    elif mutation == "reordered_stages":
        observation["stages"][1], observation["stages"][2] = observation["stages"][2], observation["stages"][1]
    assert not faults, faults
    return observation


def result(tmp_path, **faults):
    return temporal_result(observation=observation(tmp_path, **faults))


def test_complete_synthetic_model_passes_every_check(tmp_path):
    outcome = result(tmp_path)
    assert outcome["ok"], outcome["failures"]
    assert outcome["counts"] == {"expected": 10, "executed": 10, "asserted": 10}
    assert tuple(check["check"] for check in outcome["checks"]) == TEMPORAL_REQUIRED


@pytest.mark.parametrize("mutation", [
    "wrong_wire_step", "wrong_state", "wrong_repr", "wrong_input", "wrong_finish",
    "exception_element", "exception_dom", "missing_rerun", "extra_rerun",
    "missing_png", "png_sha", "wrong_contract", "missing_stage",
    "reordered_stages",
])
def test_known_mutations_fail(tmp_path, mutation):
    outcome = result(tmp_path, mutation=mutation)
    assert not outcome["ok"], (mutation, outcome["counts"])


def test_degenerate_observations_fail_closed():
    for observation in (None, {}, [], {"journey": "temporal-sequence"}):
        outcome = temporal_result(observation=observation)
        assert not outcome["ok"] and outcome["counts"]["expected"] == len(TEMPORAL_REQUIRED)


def test_first_stage_snapshots_pin_the_load_run_without_states():
    assert TEMPORAL_STATES[TEMPORAL_STAGES[0]] == {}
    assert all(TEMPORAL_STATES[name] for name in TEMPORAL_STAGES[1:])


def test_states_inputs_and_reprs_cover_every_stage():
    for name in TEMPORAL_STAGES:
        assert set(TEMPORAL_STATES[name]) <= set(TEMPORAL_WIRE)
        assert set(TEMPORAL_INPUTS[name]) == set(TEMPORAL_WIRE)
        assert len(TEMPORAL_REPRS[name]) == len(TEMPORAL_WIRE)


def test_source_fingerprints_do_not_gate_functional_evidence(tmp_path):
    for source in ({"file": "historical-app.py", "sha256": "changed"}, {"file": "historical-app.py"}, None):
        observed = observation(tmp_path)
        observed["source"] = source
        outcome = temporal_result(observation=observed)
        assert outcome["ok"], outcome["failures"]
