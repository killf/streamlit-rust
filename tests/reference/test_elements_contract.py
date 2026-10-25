"""Unit tests of the strict elements contract (journey-elements-v1)."""
from __future__ import annotations

import copy
import hashlib
import json
import pathlib
import sys

import pytest

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "browser"))

from elements_contract import (  # noqa: E402
    ELEMENTS_DOM,
    ELEMENTS_REQUIRED,
    ELEMENTS_SOURCE_PINS,
    ELEMENTS_STAGES,
    ELEMENTS_WIRE,
    elements_result,
)

PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"not-a-real-image-but-magic-and-hash-are-checked"


def frame(kind, direction="server->client", **extra):
    summary = {"type": kind, **extra}
    return {"direction": direction, "timestamp": 0.0, "summary": summary}


def delta_frame(delta):
    return frame("delta", delta=delta)


def frames_of_stream(stream, with_main_block=False):
    """Rebuild a frame list whose normalized stream equals the given one."""
    frames = [frame("rerun_script", "client->server", rerun_script={"widget_states": []})]
    frames.append(frame("new_session", new_session={"script_run_id": "r", "session_id": "s"}))
    frames.append(frame("session_status_changed", session_status_changed={"script_is_running": True}))
    if with_main_block:
        frames.append(delta_frame({"type": "add_block", "block_type": "vertical"}))
    for entry in stream:
        if "add_block" in entry:
            frames.append(delta_frame({"type": "add_block", "block_type": entry["add_block"]}))
            continue
        if "finish" in entry:
            frames.append(frame("script_finished", script_finished={"status": entry["finish"]}))
            continue
        delta = {"type": "new_element", "element": entry["element"]}
        if "body" in entry:
            delta["body"] = entry["body"]
        if "widget" in entry:
            delta["widget"] = {"id": "$$ID-synthetic", **entry["widget"]}
        if "chart" in entry:
            shape = entry["chart"]
            spec = {
                "mark": {"type": shape["mark"]},
                "encoding": {"x": dict(shape["x"]), "y": {**shape["y"], "axis": shape["y_axis"]}},
                "data": {"name": "synthetic"} if shape["has_data_name"] else {},
                "$schema": shape["schema"],
            }
            delta["element_full"] = {"vegaLiteChart": {"spec": json.dumps(spec), "datasets": [{}] * shape["datasets"]}}
        if "table_has_arrow" in entry:
            delta["element_full"] = {"table": {"arrowData": {"data": "bytes"} if entry["table_has_arrow"] else {}}}
        frames.append(delta_frame(delta))
    frames.append(frame("session_status_changed", session_status_changed={"script_is_running": False}))
    return frames


def observation(tmp_path, **faults):
    stages = []
    for name in ELEMENTS_STAGES:
        stages.append({
            "name": name,
            "new_frames": frames_of_stream([dict(entry) for entry in ELEMENTS_WIRE[name]]),
            "dom": copy.deepcopy(ELEMENTS_DOM[name]),
        })
    observation = {
        "journey": "elements-sequence",
        "contract": "journey-elements-v1",
        "scope": "PYTHON SIDE ONLY",
        "url": "http://127.0.0.1:8607/",
        "source": {"file": ELEMENTS_SOURCE_PINS["python"][0], "sha256": ELEMENTS_SOURCE_PINS["python"][1]},
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
    first = stages[0]
    if mutation == "leading_main_block":
        # The documented Rust difference must be tolerated on both stages.
        for stage in stages:
            stage["new_frames"] = frames_of_stream([dict(entry) for entry in ELEMENTS_WIRE[stage["name"]]], with_main_block=True)
    elif mutation == "wrong_heading_body":
        first["new_frames"][3]["summary"]["delta"]["body"] = "A different title"
    elif mutation == "wrong_badge_body":
        for frame_ in first["new_frames"]:
            if (frame_["summary"].get("delta") or {}).get("body") == ":blue-badge[BETA]":
                frame_["summary"]["delta"]["body"] = ":blue-badge[ BETA]"
    elif mutation == "wrong_widget_default":
        for frame_ in first["new_frames"]:
            widget = (frame_["summary"].get("delta") or {}).get("widget") or {}
            if widget.get("label") == "Note":
                widget["default"] = "goodbye"
    elif mutation == "wrong_chart_mark":
        for frame_ in first["new_frames"]:
            delta = frame_["summary"].get("delta") or {}
            if delta.get("element") == "vega_lite_chart":
                spec = json.loads(delta["element_full"]["vegaLiteChart"]["spec"])
                spec["mark"]["type"] = "line"
                delta["element_full"]["vegaLiteChart"]["spec"] = json.dumps(spec)
    elif mutation == "drop_chart_dataset":
        for frame_ in first["new_frames"]:
            delta = frame_["summary"].get("delta") or {}
            if delta.get("element") == "vega_lite_chart":
                delta["element_full"]["vegaLiteChart"]["datasets"] = []
    elif mutation == "drop_table_arrow":
        for frame_ in first["new_frames"]:
            delta = frame_["summary"].get("delta") or {}
            if delta.get("element") == "table":
                delta["element_full"]["table"]["arrowData"] = {}
    elif mutation == "wrong_echo":
        target["dom"]["markdowns"] = [
            line.replace("form: note='hello typed' submitted=True", "form: note='hello typed' submitted=False")
            for line in target["dom"]["markdowns"]
        ]
    elif mutation == "wrong_note":
        target["dom"]["note"] = "hello"
    elif mutation == "wrong_chart_bars":
        target["dom"]["chart_bars"] = 3
    elif mutation == "wrong_finish":
        for frame_ in target["new_frames"]:
            if frame_["summary"]["type"] == "script_finished":
                frame_["summary"]["script_finished"]["status"] = 2
    elif mutation == "exception_dom":
        target["dom"]["exceptions"] = ["boom"]
    elif mutation == "missing_stage":
        observation["stages"] = observation["stages"][:1]
    elif mutation == "wrong_source":
        observation["source"]["sha256"] = "0" * 64
    elif mutation == "wrong_contract":
        observation["contract"] = "journey-elements-v0"
    elif mutation == "png_sha":
        target["screenshot"]["sha256"] = "0" * 64
    assert not faults, faults
    return observation


def result(tmp_path, **faults):
    return elements_result(observation=observation(tmp_path, **faults))


def test_complete_synthetic_model_passes_every_check(tmp_path):
    outcome = result(tmp_path)
    assert outcome["ok"], outcome["failures"]
    assert outcome["counts"] == {"expected": 11, "executed": 11, "asserted": 11}
    assert tuple(check["check"] for check in outcome["checks"]) == ELEMENTS_REQUIRED


def test_the_documented_leading_main_block_is_tolerated(tmp_path):
    outcome = result(tmp_path, mutation="leading_main_block")
    assert outcome["ok"], outcome["failures"]


@pytest.mark.parametrize("mutation", [
    "wrong_heading_body", "wrong_badge_body", "wrong_widget_default", "wrong_chart_mark",
    "drop_chart_dataset", "drop_table_arrow", "wrong_echo", "wrong_note", "wrong_chart_bars",
    "wrong_finish", "exception_dom", "missing_stage", "wrong_source", "wrong_contract", "png_sha",
])
def test_known_mutations_fail(tmp_path, mutation):
    outcome = result(tmp_path, mutation=mutation)
    assert not outcome["ok"], (mutation, outcome["counts"])


def test_degenerate_observations_fail_closed():
    for observation in (None, {}, [], {"journey": "elements-sequence"}):
        outcome = elements_result(observation=observation)
        assert not outcome["ok"] and outcome["counts"]["expected"] == len(ELEMENTS_REQUIRED)


def test_contract_pins_the_committed_sources():
    for side, (relative, pinned) in ELEMENTS_SOURCE_PINS.items():
        path = HERE.parents[1] / relative
        assert path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest() == pinned, side


def test_pinned_dom_covers_both_form_states():
    load = [line for line in ELEMENTS_DOM["01-load"]["markdowns"] if line.startswith("form: note=")]
    apply = [line for line in ELEMENTS_DOM["02-apply"]["markdowns"] if line.startswith("form: note=")]
    assert load == ["form: note='hello' submitted=False"]
    assert apply == ["form: note='hello typed' submitted=True"]
    assert (ELEMENTS_DOM["01-load"]["note"], ELEMENTS_DOM["02-apply"]["note"]) == ("hello", "hello typed")
