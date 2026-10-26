"""Unit tests of the strict button-family contract (journey-buttons-v1)."""
from __future__ import annotations

import copy
import hashlib
import json
import pathlib
import sys

import pytest

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "browser"))

from buttons_contract import (  # noqa: E402
    BUTTONS_DOMS,
    BUTTONS_REQUIRED,
    BUTTONS_SOURCE_PINS,
    BUTTONS_STAGES,
    BUTTONS_TIMELINE,
    buttons_result,
)

PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"not-a-real-image-but-magic-and-hash-are-checked"

WIDGET_KINDS = ("checkbox", "feedback", "button_group", "pagination", "menu_button", "link_button", "page_link", "download_button")


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
        if isinstance(widget.get("url"), str) and "<hash>" in widget["url"]:
            widget["url"] = widget["url"].replace("<hash>", "c" * 32)
        return {"direction": "server->client", "timestamp": 0.5, "summary": {"type": "delta", "delta": {"type": "new_element", "element": kind, "widget": widget, "id": widget["id"], "path": entry["path"]}}}
    return {"direction": "server->client", "timestamp": 0.5, "summary": {"type": "delta", "delta": {"type": "new_element", "element": kind, "body": entry.get("body"), "path": entry.get("path")}}}


def stage_frames(name, *, leading_main_blocks=0, reverse_states=False):
    frames = []
    for _ in range(leading_main_blocks):
        frames.append({"direction": "server->client", "timestamp": 0.2,
                       "summary": {"type": "delta", "delta": {"type": "add_block", "block_id": "main_container", "block_type": "vertical",
                                                              "block": {"vertical": {}, "id": "main_container"}, "path": [0]}}})
    for entry in BUTTONS_TIMELINE[name]:
        frame = build_frame(entry)
        if reverse_states and frame["summary"].get("type") == "rerun_script":
            frame["summary"]["rerun_script"]["widget_states"] = list(reversed(frame["summary"]["rerun_script"]["widget_states"]))
        frames.append(frame)
    return frames


def dom(name):
    return json.loads(json.dumps(copy.deepcopy(BUTTONS_DOMS[name]), ensure_ascii=False))


def observation(tmp_path, **faults):
    leading = faults.pop("leading_main_blocks", 0)
    reverse = faults.pop("reverse_states", False)
    stages = []
    for name in BUTTONS_STAGES:
        stages.append({"name": name, "new_frames": stage_frames(name, leading_main_blocks=leading, reverse_states=reverse), "http": [], "dom": dom(name)})
    observation = {
        "journey": "buttons-page",
        "contract": "journey-buttons-v1",
        "scope": "PYTHON SIDE ONLY",
        "url": "http://127.0.0.1:8623/",
        "source": {"file": BUTTONS_SOURCE_PINS["python"][0], "sha256": BUTTONS_SOURCE_PINS["python"][1]},
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

    if mutation == "toggle_style_lost":
        for stage in stages:
            widget_frames(stage, "checkbox")[0]["summary"]["delta"]["widget"].pop("type")
    elif mutation == "feedback_style_changed":
        for stage in stages:
            widget_frames(stage, "feedback")[0]["summary"]["delta"]["widget"]["type"] = "FACES"
    elif mutation == "group_mode_changed":
        for stage in stages:
            widget_frames(stage, "button_group")[1]["summary"]["delta"]["widget"]["clickMode"] = "SINGLE_SELECT"
    elif mutation == "group_default_lost":
        for stage in stages:
            widget_frames(stage, "button_group")[1]["summary"]["delta"]["widget"].pop("default")
    elif mutation == "pagination_value_stray":
        for stage in stages:
            widget_frames(stage, "pagination")[0]["summary"]["delta"]["widget"]["value"] = 1
    elif mutation == "menu_options_changed":
        for stage in stages:
            widget_frames(stage, "menu_button")[0]["summary"]["delta"]["widget"]["options"] = ["CSV"]
    elif mutation == "download_url_empty":
        for stage in stages:
            widget_frames(stage, "download_button")[0]["summary"]["delta"]["widget"]["url"] = ""
    elif mutation == "link_ignore_rerun_lost":
        for stage in stages:
            widget_frames(stage, "link_button")[0]["summary"]["delta"]["widget"].pop("ignoreRerun")
    elif mutation == "page_link_external_lost":
        for stage in stages:
            widget_frames(stage, "page_link")[0]["summary"]["delta"]["widget"].pop("external")
    elif mutation == "menu_trigger_lost":
        menu = stages[-1]
        rerun = next(frame for frame in menu["new_frames"] if frame["summary"].get("type") == "rerun_script")
        rerun["summary"]["rerun_script"]["widget_states"] = [
            state for state in rerun["summary"]["rerun_script"]["widget_states"]
            if state.get("value_field") != "string_trigger_value"]
    elif mutation == "dom_buttons_missing":
        load["dom"]["buttons"] = []
    elif mutation == "extra_element":
        load["new_frames"].append(build_frame({"kind": "markdown", "body": "extra", "path": [0, 12]}))
    elif mutation == "missing_png":
        (tmp_path / f"{load['name']}.png").unlink()
    elif mutation == "png_sha":
        load["screenshot"]["sha256"] = "0" * 64
    elif mutation == "wrong_source":
        observation["source"]["sha256"] = "0" * 64
    elif mutation == "wrong_contract":
        observation["contract"] = "journey-buttons-v0"
    elif mutation == "missing_stage":
        observation["stages"] = []
    assert not faults, faults
    return observation


def result(tmp_path, **faults):
    return buttons_result(observation=observation(tmp_path, **faults))


def test_complete_synthetic_model_passes_every_check(tmp_path):
    outcome = result(tmp_path)
    assert outcome["ok"], outcome["failures"]
    assert outcome["counts"]["expected"] == len(BUTTONS_REQUIRED)
    assert tuple(check["check"] for check in outcome["checks"]) == BUTTONS_REQUIRED


def test_the_rust_leading_main_block_is_the_one_allowed_divergence(tmp_path):
    outcome = result(tmp_path, leading_main_blocks=1)
    assert outcome["ok"], outcome["failures"]


def test_the_browser_state_order_is_normalized(tmp_path):
    outcome = result(tmp_path, reverse_states=True)
    assert outcome["ok"], outcome["failures"]


@pytest.mark.parametrize("leading", [2, 3])
def test_more_than_one_leading_main_block_fails(tmp_path, leading):
    outcome = result(tmp_path, leading_main_blocks=leading)
    assert not outcome["ok"], (leading, outcome["counts"])


@pytest.mark.parametrize("mutation", [
    "toggle_style_lost", "feedback_style_changed", "group_mode_changed",
    "group_default_lost", "pagination_value_stray", "menu_options_changed",
    "download_url_empty", "link_ignore_rerun_lost", "page_link_external_lost",
    "menu_trigger_lost", "dom_buttons_missing", "extra_element",
    "missing_png", "png_sha", "wrong_source", "wrong_contract", "missing_stage",
])
def test_known_mutations_fail(tmp_path, mutation):
    outcome = result(tmp_path, mutation=mutation)
    assert not outcome["ok"], (mutation, outcome["counts"])


def test_degenerate_observations_fail_closed():
    for observation in (None, {}, [], {"journey": "buttons-page"}):
        outcome = buttons_result(observation=observation)
        assert not outcome["ok"] and outcome["counts"]["expected"] == len(BUTTONS_REQUIRED)


def test_the_constants_pin_the_measured_semantics():
    assert BUTTONS_STAGES == ["01-load", "02-toggle", "03-pills", "04-pagination", "05-feedback", "06-menu"]
    load = BUTTONS_TIMELINE["01-load"]
    toggles = [entry for entry in load if entry["kind"] == "checkbox"]
    assert toggles[0]["widget"] == {"label": "Night mode", "labelVisibility": {}, "type": "TOGGLE"}
    assert toggles[1]["widget"]["default"] is True
    groups = [entry for entry in load if entry["kind"] == "button_group"]
    assert groups[0]["widget"]["style"] == "PILLS" and "clickMode" not in groups[0]["widget"]
    assert groups[1]["widget"]["clickMode"] == "MULTI_SELECT" and groups[1]["widget"]["default"] == [0]
    assert "style" not in groups[2]["widget"]
    pagination = [entry for entry in load if entry["kind"] == "pagination"][0]
    assert pagination["widget"] == {"numPages": 10, "default": 1, "maxVisiblePages": 7}
    download = [entry for entry in load if entry["kind"] == "download_button"][0]
    assert download["widget"]["url"] == "/media/<hash>.txt"
    link = [entry for entry in load if entry["kind"] == "link_button"][0]
    assert link["widget"]["ignoreRerun"] is True
    page_link = [entry for entry in load if entry["kind"] == "page_link"][0]
    assert page_link["widget"]["external"] is True
    menu = next(entry for entry in BUTTONS_TIMELINE["06-menu"] if entry["kind"] == "rerun")
    trigger = [state for state in menu["states"] if state.get("value_field") == "string_trigger_value"]
    assert trigger[0]["value"] == {"data": "CSV"}
    assert all(not dom["exceptions"] for dom in BUTTONS_DOMS.values())
