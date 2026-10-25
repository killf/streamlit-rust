"""Unit tests of the strict presentation contract (journey-presentation-v1)."""
from __future__ import annotations

import copy
import hashlib
import pathlib
import sys

import pytest

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "browser"))

from presentation_contract import (  # noqa: E402
    PRESENTATION_DOM,
    PRESENTATION_REQUIRED,
    PRESENTATION_SOURCE_PINS,
    PRESENTATION_STAGES,
    PRESENTATION_TIMELINE,
    presentation_result,
)

PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"not-a-real-image-but-magic-and-hash-are-checked"


def frame(kind, direction="server->client", **extra):
    summary = {"type": kind, **extra}
    return {"direction": direction, "timestamp": 0.0, "summary": summary}


def timeline_frames():
    """The measured deltas with real shapes and paths."""
    frames = []
    for entry in copy.deepcopy(PRESENTATION_TIMELINE):
        if entry["kind"] == "new_transient":
            transient = {"elements": copy.deepcopy(entry["elements"])}
            frames.append(frame("delta", delta={"type": "new_transient", "path": entry["path"], "transient": transient}))
        else:
            delta = {"type": "new_element", "path": entry["path"], "element": entry["element"]}
            if entry.get("full") is not None:
                delta["element_full"] = entry["full"]
            if entry.get("body") is not None:
                delta["body"] = entry["body"]
            frames.append(frame("delta", delta=delta))
    return frames


def dom():
    import json

    text = json.dumps(copy.deepcopy(PRESENTATION_DOM), ensure_ascii=False)
    return json.loads(text.replace("<page>", "http://127.0.0.1:8611"))


def observation(tmp_path, **faults):
    frames = [
        frame("rerun_script", "client->server", rerun_script={"widget_states": []}),
        frame("new_session", new_session={"script_run_id": "run-1", "session_id": "session-a"}),
        frame("session_status_changed", session_status_changed={"script_is_running": True, "run_on_save": False}),
        *timeline_frames(),
        frame("script_finished", script_finished={"status": 0}),
        frame("session_status_changed", session_status_changed={"script_is_running": False, "run_on_save": False}),
    ]
    stages = [{"name": PRESENTATION_STAGES[0], "new_frames": frames, "http": [], "dom": dom()}]
    observation = {
        "journey": "presentation-page",
        "contract": "journey-presentation-v1",
        "scope": "PYTHON SIDE ONLY",
        "url": "http://127.0.0.1:8611/",
        "source": {"file": PRESENTATION_SOURCE_PINS["python"][0], "sha256": PRESENTATION_SOURCE_PINS["python"][1]},
        "capture_sources": {},
        "stages": stages,
        "ipc_dir": str(tmp_path),
    }
    for stage in stages:
        name = f"{stage['name']}.png"
        (tmp_path / name).write_bytes(PNG_BYTES)
        stage["screenshot"] = {"file": name, "sha256": hashlib.sha256(PNG_BYTES).hexdigest()}
    mutation = faults.pop("mutation", None)
    target = stages[0]
    if mutation == "spinner_not_cleared":
        target["new_frames"][4]["summary"]["delta"]["transient"] = {"elements": copy.deepcopy(PRESENTATION_TIMELINE[0]["elements"])}
    elif mutation == "spinner_wrong_text":
        target["new_frames"][3]["summary"]["delta"]["transient"]["elements"][0]["spinner"]["text"] = "Other"
    elif mutation == "transient_extra_element":
        target["new_frames"][3]["summary"]["delta"]["transient"]["elements"].append(
            copy.deepcopy(PRESENTATION_TIMELINE[0]["elements"][0]))
    elif mutation == "unknown_delta_kind":
        target["new_frames"][5]["summary"]["delta"]["type"] = "new_blob"
    elif mutation == "spinner_consumes_path":
        target["new_frames"][5]["summary"]["delta"]["path"] = [0, 1]
    elif mutation == "toast_wrong_path":
        for delta_frame in target["new_frames"]:
            delta = delta_frame["summary"].get("delta") or {}
            if delta.get("element") == "toast":
                delta["path"] = [0, 2]
    elif mutation == "toast_wrong_duration":
        for delta_frame in target["new_frames"]:
            delta = delta_frame["summary"].get("delta") or {}
            if delta.get("element") == "toast":
                delta["element_full"]["toast"]["duration"] = 7
    elif mutation == "toast_not_one_shot":
        for delta_frame in target["new_frames"]:
            delta = delta_frame["summary"].get("delta") or {}
            if delta.get("element") == "toast":
                delta["element_full"].pop("hasOneShotEffect")
    elif mutation == "balloons_hidden":
        for delta_frame in target["new_frames"]:
            delta = delta_frame["summary"].get("delta") or {}
            if delta.get("element") == "balloons":
                delta["element_full"]["balloons"]["show"] = False
    elif mutation == "wrong_dom_toast":
        target["dom"]["toasts"] = []
    elif mutation == "spinner_left_in_dom":
        target["dom"]["spinners"] = ["Loading data"]
    elif mutation == "exception_element":
        target["new_frames"].insert(3, frame("delta", delta={"element": "exception"}))
    elif mutation == "wrong_finish":
        for frame_ in target["new_frames"]:
            if frame_["summary"]["type"] == "script_finished":
                frame_["summary"]["script_finished"]["status"] = 2
    elif mutation == "missing_png":
        (tmp_path / f"{target['name']}.png").unlink()
    elif mutation == "png_sha":
        target["screenshot"]["sha256"] = "0" * 64
    elif mutation == "wrong_source":
        observation["source"]["sha256"] = "0" * 64
    elif mutation == "wrong_contract":
        observation["contract"] = "journey-presentation-v0"
    elif mutation == "missing_stage":
        observation["stages"] = []
    assert not faults, faults
    return observation


def result(tmp_path, **faults):
    return presentation_result(observation=observation(tmp_path, **faults))


def test_complete_synthetic_model_passes_every_check(tmp_path):
    outcome = result(tmp_path)
    assert outcome["ok"], outcome["failures"]
    assert outcome["counts"] == {"expected": 11, "executed": 11, "asserted": 11}
    assert tuple(check["check"] for check in outcome["checks"]) == PRESENTATION_REQUIRED


@pytest.mark.parametrize("mutation", [
    "spinner_not_cleared", "spinner_wrong_text", "transient_extra_element",
    "unknown_delta_kind", "spinner_consumes_path",
    "toast_wrong_path", "toast_wrong_duration", "toast_not_one_shot",
    "balloons_hidden", "wrong_dom_toast", "spinner_left_in_dom",
    "exception_element", "wrong_finish", "missing_png", "png_sha",
    "wrong_source", "wrong_contract", "missing_stage",
])
def test_known_mutations_fail(tmp_path, mutation):
    outcome = result(tmp_path, mutation=mutation)
    assert not outcome["ok"], (mutation, outcome["counts"])


def test_degenerate_observations_fail_closed():
    for observation in (None, {}, [], {"journey": "presentation-page"}):
        outcome = presentation_result(observation=observation)
        assert not outcome["ok"] and outcome["counts"]["expected"] == len(PRESENTATION_REQUIRED)


def test_the_timeline_pins_the_measured_semantics():
    kinds = [entry["kind"] for entry in PRESENTATION_TIMELINE]
    assert kinds == ["new_transient", "new_transient", "new_element", "new_element", "new_element"]
    assert [entry["path"] for entry in PRESENTATION_TIMELINE] == [[0, 0], [0, 0], [0, 0], [2, 0], [0, 1]]
    assert PRESENTATION_TIMELINE[1]["elements"] == []
    assert len(PRESENTATION_TIMELINE[0]["elements"]) == 1
    assert PRESENTATION_TIMELINE[0]["elements"][0]["spinner"]["text"] == "Loading data"
    assert PRESENTATION_TIMELINE[2]["element"] == "markdown" and PRESENTATION_TIMELINE[2]["body"] == "loaded"
    assert PRESENTATION_DOM["toasts"] and not PRESENTATION_DOM["spinners"] and not PRESENTATION_DOM["exceptions"]


def test_contract_pins_the_committed_sources():
    for side, (relative, pinned) in PRESENTATION_SOURCE_PINS.items():
        path = HERE.parents[1] / relative
        assert path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest() == pinned, side
