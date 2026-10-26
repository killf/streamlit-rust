"""Unit tests of the strict picker contract (journey-pickers-v1)."""
from __future__ import annotations

import copy
import hashlib
import json
import pathlib
import sys

import pytest

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "browser"))

from pickers_contract import (  # noqa: E402
    PICKERS_DOMS,
    PICKERS_REQUIRED,
    PICKERS_SOURCE_PINS,
    PICKERS_STAGES,
    PICKERS_TIMELINE,
    pickers_result,
)

PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"not-a-real-image-but-magic-and-hash-are-checked"

WIDGET_KINDS = ("date_input", "time_input", "color_picker", "slider", "audio_input", "camera_input")


def build_frame(entry):
    entry = copy.deepcopy(entry)
    kind = entry["kind"]
    if kind == "rerun":
        states = []
        for state in entry["states"]:
            real = "$$ID-" + "a" * 32 + "-" + state["id"].split("-", 2)[-1]
            states.append({**state, "id": real})
        return {"direction": "client->server", "timestamp": 0.0, "summary": {"type": "rerun_script", "rerun_script": {"widget_states": states}}}
    if kind in ("new_session", "session_status_changed"):
        return {"direction": "server->client", "timestamp": 0.1, "summary": {"type": kind, kind: {}}}
    if kind == "script_finished":
        return {"direction": "server->client", "timestamp": 9.0, "summary": {"type": "script_finished", "script_finished": {"status": 0}}}
    if kind in WIDGET_KINDS:
        widget = copy.deepcopy(entry["widget"])
        widget["id"] = "$$ID-" + "b" * 32 + "-key"
        return {"direction": "server->client", "timestamp": 0.5, "summary": {"type": "delta", "delta": {"type": "new_element", "element": kind, "widget": widget, "id": widget["id"], "path": entry["path"]}}}
    return {"direction": "server->client", "timestamp": 0.5, "summary": {"type": "delta", "delta": {"type": "new_element", "element": kind, "body": entry.get("body"), "path": entry.get("path")}}}


def stage_frames(name, *, leading_main_blocks=0, reverse_states=False):
    frames = []
    for _ in range(leading_main_blocks):
        frames.append({"direction": "server->client", "timestamp": 0.2,
                       "summary": {"type": "delta", "delta": {"type": "add_block", "block_id": "main_container", "block_type": "vertical",
                                                              "block": {"vertical": {}, "id": "main_container"}, "path": [0]}}})
    for entry in PICKERS_TIMELINE[name]:
        frame = build_frame(entry)
        if reverse_states and frame["summary"].get("type") == "rerun_script":
            frame["summary"]["rerun_script"]["widget_states"] = list(reversed(frame["summary"]["rerun_script"]["widget_states"]))
        frames.append(frame)
    return frames


def dom(name):
    return json.loads(json.dumps(copy.deepcopy(PICKERS_DOMS[name]), ensure_ascii=False))


def observation(tmp_path, **faults):
    leading = faults.pop("leading_main_blocks", 0)
    reverse = faults.pop("reverse_states", False)
    stages = []
    for name in PICKERS_STAGES:
        stages.append({"name": name, "new_frames": stage_frames(name, leading_main_blocks=leading, reverse_states=reverse), "http": [], "dom": dom(name)})
    observation = {
        "journey": "pickers-page",
        "contract": "journey-pickers-v1",
        "scope": "PYTHON SIDE ONLY",
        "url": "http://127.0.0.1:8624/",
        "source": {"file": PICKERS_SOURCE_PINS["python"][0], "sha256": PICKERS_SOURCE_PINS["python"][1]},
        "capture_sources": {},
        "stages": stages,
        "ipc_dir": str(tmp_path),
    }
    for stage in stages:
        png = f"{stage['name']}.png"
        (tmp_path / png).write_bytes(PNG_BYTES)
        stage["screenshot"] = {"file": png, "sha256": hashlib.sha256(PNG_BYTES).hexdigest()}
    mutation = faults.pop("mutation", None)
    load = stages[0]

    def widget_frames(stage, kind):
        return [frame for frame in stage["new_frames"] if (frame["summary"].get("delta") or {}).get("element") == kind]

    if mutation == "date_window_lost":
        for stage in stages:
            for frame in widget_frames(stage, "date_input"):
                frame["summary"]["delta"]["widget"]["min"] = ""
    elif mutation == "date_range_flag_lost":
        for stage in stages:
            widget_frames(stage, "date_input")[1]["summary"]["delta"]["widget"].pop("isRange")
    elif mutation == "time_default_lost":
        for stage in stages:
            widget_frames(stage, "time_input")[0]["summary"]["delta"]["widget"].pop("default")
    elif mutation == "color_default_lost":
        for stage in stages:
            widget_frames(stage, "color_picker")[0]["summary"]["delta"]["widget"].pop("default")
    elif mutation == "slider_type_lost":
        for stage in stages:
            for frame in widget_frames(stage, "slider"):
                frame["summary"]["delta"]["widget"].pop("type")
    elif mutation == "slider_first_default_lost":
        for stage in stages:
            widget_frames(stage, "slider")[0]["summary"]["delta"]["widget"]["default"] = []
    elif mutation == "audio_rate_lost":
        for stage in stages:
            widget_frames(stage, "audio_input")[0]["summary"]["delta"]["widget"].pop("sampleRate")
    elif mutation == "slider_step_states_lost":
        slider = stages[-1]
        for frame in slider["new_frames"]:
            states = (frame["summary"].get("rerun_script") or {}).get("widget_states")
            if states is not None:
                frame["summary"]["rerun_script"]["widget_states"] = [
                    state for state in states
                    if not (state.get("id", "").endswith("-one") and state.get("value_field") == "string_array_value")]
    elif mutation == "dom_thumbs_stale":
        stages[-1]["dom"]["sliderThumbs"] = ["low", "b", "d"]
    elif mutation == "extra_element":
        load["new_frames"].append(build_frame({"kind": "markdown", "body": "extra", "path": [0, 8]}))
    elif mutation == "missing_png":
        (tmp_path / f"{load['name']}.png").unlink()
    elif mutation == "png_sha":
        load["screenshot"]["sha256"] = "0" * 64
    elif mutation == "wrong_source":
        observation["source"]["sha256"] = "0" * 64
    elif mutation == "wrong_contract":
        observation["contract"] = "journey-pickers-v0"
    elif mutation == "missing_stage":
        observation["stages"] = []
    assert not faults, faults
    return observation


def result(tmp_path, **faults):
    return pickers_result(observation=observation(tmp_path, **faults))


def test_complete_synthetic_model_passes_every_check(tmp_path):
    outcome = result(tmp_path)
    assert outcome["ok"], outcome["failures"]
    assert outcome["counts"]["expected"] == len(PICKERS_REQUIRED)
    assert tuple(check["check"] for check in outcome["checks"]) == PICKERS_REQUIRED


def test_the_rust_leading_main_block_is_the_one_allowed_divergence(tmp_path):
    outcome = result(tmp_path, leading_main_blocks=1)
    assert outcome["ok"], outcome["failures"]


def test_the_browser_state_order_is_normalized(tmp_path):
    outcome = result(tmp_path, reverse_states=True)
    assert outcome["ok"], outcome["failures"]


@pytest.mark.parametrize("leading", [2, 3])
def test_every_batch_may_reannounce_the_main_container(tmp_path, leading):
    outcome = result(tmp_path, leading_main_blocks=leading)
    assert outcome["ok"], (leading, outcome["failures"])


def test_a_nested_main_container_block_fails(tmp_path):
    model = observation(tmp_path)
    model["stages"][0]["new_frames"].append({"direction": "server->client", "timestamp": 0.2,
                                             "summary": {"type": "delta", "delta": {"type": "add_block", "block_id": "main_container", "block_type": "vertical",
                                                                                    "block": {"vertical": {}, "id": "main_container"}, "path": [0, 0]}}})
    outcome = pickers_result(observation=model)
    assert not outcome["ok"], outcome["failures"]


@pytest.mark.parametrize("mutation", [
    "date_window_lost", "date_range_flag_lost", "time_default_lost",
    "color_default_lost", "slider_type_lost", "slider_first_default_lost",
    "audio_rate_lost", "slider_step_states_lost", "dom_thumbs_stale",
    "extra_element", "missing_png", "png_sha", "wrong_source",
    "wrong_contract", "missing_stage",
])
def test_known_mutations_fail(tmp_path, mutation):
    outcome = result(tmp_path, mutation=mutation)
    assert not outcome["ok"], (mutation, outcome["counts"])


def test_degenerate_observations_fail_closed():
    for observation in (None, {}, [], {"journey": "pickers-page"}):
        outcome = pickers_result(observation=observation)
        assert not outcome["ok"] and outcome["counts"]["expected"] == len(PICKERS_REQUIRED)


def test_the_constants_pin_the_measured_semantics():
    assert PICKERS_STAGES == ["01-load", "02-slider"]
    load = PICKERS_TIMELINE["01-load"]
    dates = [entry for entry in load if entry["kind"] == "date_input"]
    assert dates[0]["widget"]["min"] == "2015-01-15" and dates[0]["widget"]["max"] == "2035-01-15"
    assert dates[1]["widget"]["isRange"] is True and dates[1]["widget"]["max"] == "2035-02-15"
    times = [entry for entry in load if entry["kind"] == "time_input"][0]
    assert times["widget"]["default"] == "14:30" and times["widget"]["step"] == "900"
    colors = [entry for entry in load if entry["kind"] == "color_picker"][0]
    assert colors["widget"]["default"] == "#FF5733"
    sliders = [entry for entry in load if entry["kind"] == "slider"]
    assert sliders[0]["widget"]["default"] == [0.0] and sliders[0]["widget"]["type"] == "SELECT_SLIDER"
    assert sliders[1]["widget"]["default"] == [1.0, 3.0]
    audios = [entry for entry in load if entry["kind"] == "audio_input"][0]
    assert audios["widget"]["sampleRate"] == 16000
    step_states = [(state.get("value")) for entry in PICKERS_TIMELINE["02-slider"] if entry["kind"] == "rerun"
                   for state in entry["states"] if state.get("id", "").endswith("-one")]
    assert step_states[0] == {"data": "['medium']"} and step_states[-1] == {"data": "['high']"}
    assert all(not dom["exceptions"] for dom in PICKERS_DOMS.values())
