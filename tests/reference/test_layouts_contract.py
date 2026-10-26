"""Unit tests of the strict layouts contract (journey-layouts-v1)."""
from __future__ import annotations

import copy
import hashlib
import json
import pathlib
import sys

import pytest

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "browser"))

from layouts_contract import (  # noqa: E402
    LAYOUTS_DOM,
    LAYOUTS_REQUIRED,
    LAYOUTS_SOURCE_PINS,
    LAYOUTS_TIMELINE,
    layouts_result,
)

PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"not-a-real-image-but-magic-and-hash-are-checked"

URL = "http://127.0.0.1:8613"


def block_frame(delta):
    return {"direction": "server->client", "timestamp": 1.0, "summary": {"type": "delta", "delta": delta}}


def timeline_frames(timeline=None, *, leading_main_blocks=0):
    frames = []
    for _ in range(leading_main_blocks):
        frames.append(block_frame({"type": "add_block", "block_id": "main_container", "block_type": "vertical",
                                   "block": {"vertical": {}, "id": "main_container"}, "path": [0]}))
    for index, delta in enumerate(timeline if timeline is not None else LAYOUTS_TIMELINE):
        served = copy.deepcopy(delta)
        if served.get("block_id") == "$$ID-<hash>-None":
            served["block_id"] = "$$ID-79b26fd5542f64b238f6f878327b6b00-None"
        if served.get("block") and "dialog" in served["block"]:
            served["block"]["id"] = served["block_id"]
        frames.append({"direction": "server->client", "timestamp": float(index), "summary": {"type": "delta", "delta": served}})
    return frames


def dom():
    return json.loads(json.dumps(copy.deepcopy(LAYOUTS_DOM), ensure_ascii=False))


def observation(tmp_path, **faults):
    leading = faults.pop("leading_main_blocks", 0)
    frames = [
        {"direction": "client->server", "timestamp": 0.0, "summary": {"type": "rerun_script", "rerun_script": {"widget_states": []}}},
        {"direction": "server->client", "timestamp": 0.1, "summary": {"type": "new_session", "new_session": {"script_run_id": "run-1", "session_id": "session-a"}}},
        {"direction": "server->client", "timestamp": 0.2, "summary": {"type": "session_status_changed", "session_status_changed": {"script_is_running": True, "run_on_save": False}}},
        *timeline_frames(leading_main_blocks=leading),
        {"direction": "server->client", "timestamp": 4.0, "summary": {"type": "script_finished", "script_finished": {"status": 0}}},
        {"direction": "server->client", "timestamp": 4.1, "summary": {"type": "session_status_changed", "session_status_changed": {"script_is_running": False, "run_on_save": False}}},
    ]
    stages = [{"name": "01-load", "new_frames": frames, "http": [], "dom": dom()}]
    observation = {
        "journey": "layouts-page",
        "contract": "journey-layouts-v1",
        "scope": "PYTHON SIDE ONLY",
        "url": f"{URL}/",
        "source": {"file": LAYOUTS_SOURCE_PINS["python"][0], "sha256": LAYOUTS_SOURCE_PINS["python"][1]},
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
    deltas = [frame["summary"]["delta"] for frame in target["new_frames"] if (frame["summary"].get("delta") or {}).get("type") in ("new_element", "add_block")]

    def at(path, block_type=None, occurrence=0):
        hits = [delta for delta in deltas if delta.get("path") == path and (block_type is None or delta.get("block_type") == block_type)]
        return hits[occurrence]

    if mutation == "expander_child_depth":
        at([0, 0, 0])["path"] = [0, 0, 0, 0]
    elif mutation == "popover_child_depth":
        at([0, 2, 0])["path"] = [0, 2, 0, 0]
    elif mutation == "sidebar_child_path":
        at([1, 0])["path"] = [1, 1]
    elif mutation == "tab_child_path":
        at([0, 1, 0, 0])["path"] = [0, 1, 0]
    elif mutation == "tab_labels_swapped":
        at([0, 1, 0], "tab")["block"]["tab"]["label"] = "Two"
    elif mutation == "tabs_block_missing":
        target["new_frames"] = [frame for frame in target["new_frames"] if (frame["summary"].get("delta") or {}).get("block_type") != "tab_container"]
    elif mutation == "expander_collapsed":
        at([0, 0], "expandable")["block"]["expandable"]["expanded"] = False
    elif mutation == "popover_open_true":
        at([0, 2], "popover")["block"]["popover"]["open"] = True
    elif mutation == "popover_width_stretch":
        at([0, 2], "popover")["block"]["widthConfig"] = {"useStretch": True}
    elif mutation == "tabs_height_absent":
        del at([0, 1], "tab_container")["block"]["heightConfig"]
    elif mutation == "dialog_reopen_missing":
        second = at([2, 0], "dialog", occurrence=1)
        target["new_frames"] = [frame for frame in target["new_frames"] if frame["summary"].get("delta") is not second]
    elif mutation == "dialog_is_open_false":
        at([2, 0], "dialog", occurrence=1)["block"]["dialog"]["isOpen"] = False
    elif mutation == "dialog_id_malformed":
        for occurrence in (0, 1):
            delta = at([2, 0], "dialog", occurrence=occurrence)
            delta["block_id"] = "dialog-1"
            delta["block"]["id"] = "dialog-1"
    elif mutation == "dialog_ids_differ":
        delta = at([2, 0], "dialog", occurrence=1)
        delta["block_id"] = "$$ID-00000000000000000000000000000000-None"
        delta["block"]["id"] = delta["block_id"]
    elif mutation == "dialog_content_gap":
        at([2, 0, 0], "flex_container")["block"]["flexContainer"]["gapConfig"]["gapSize"] = "MEDIUM"
    elif mutation == "dialog_content_justify":
        at([2, 0, 0], "flex_container")["block"]["flexContainer"]["justify"] = "JUSTIFY_CENTER"
    elif mutation == "dialog_child_missing":
        target["new_frames"] = [frame for frame in target["new_frames"] if (frame["summary"].get("delta") or {}).get("path") != [2, 0, 0, 0]]
    elif mutation == "popover_block_missing":
        target["new_frames"] = [frame for frame in target["new_frames"] if (frame["summary"].get("delta") or {}).get("block_type") != "popover"]
    elif mutation == "unexpected_delta_kind":
        deltas[0]["type"] = "delta_kind_that_does_not_exist"
    elif mutation == "exception_element":
        target["new_frames"].insert(6, {"direction": "server->client", "timestamp": 2.9,
                                        "summary": {"type": "delta", "delta": {"type": "new_element", "element": "exception", "path": [0, 3]}}})
    elif mutation == "dom_blocks_empty":
        target["dom"]["blocks"] = []
    elif mutation == "dom_markdown_missing":
        target["dom"]["markdowns"].remove("inside dialog")
    elif mutation == "dom_expander_open":
        target["dom"]["expanderOpen"] = 1
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
        observation["contract"] = "journey-layouts-v0"
    elif mutation == "missing_stage":
        observation["stages"] = []
    assert not faults, faults
    return observation


def result(tmp_path, **faults):
    return layouts_result(observation=observation(tmp_path, **faults))


def test_complete_synthetic_model_passes_every_check(tmp_path):
    outcome = result(tmp_path)
    assert outcome["ok"], outcome["failures"]
    assert outcome["counts"] == {"expected": 9, "executed": 9, "asserted": 9}
    assert tuple(check["check"] for check in outcome["checks"]) == LAYOUTS_REQUIRED


def test_the_rust_leading_main_block_is_the_one_allowed_divergence(tmp_path):
    outcome = result(tmp_path, leading_main_blocks=1)
    assert outcome["ok"], outcome["failures"]


@pytest.mark.parametrize("leading", [2, 3])
def test_more_than_one_leading_main_block_fails(tmp_path, leading):
    outcome = result(tmp_path, leading_main_blocks=leading)
    assert not outcome["ok"], (leading, outcome["counts"])


@pytest.mark.parametrize("mutation", [
    "expander_child_depth", "popover_child_depth", "sidebar_child_path",
    "tab_child_path", "tab_labels_swapped", "tabs_block_missing",
    "expander_collapsed", "popover_open_true", "popover_width_stretch",
    "tabs_height_absent", "dialog_reopen_missing", "dialog_is_open_false",
    "dialog_id_malformed", "dialog_ids_differ", "dialog_content_gap",
    "dialog_content_justify", "dialog_child_missing", "popover_block_missing",
    "unexpected_delta_kind", "exception_element", "dom_blocks_empty",
    "dom_markdown_missing", "dom_expander_open", "wrong_finish",
    "missing_png", "png_sha", "wrong_source", "wrong_contract",
    "missing_stage",
])
def test_known_mutations_fail(tmp_path, mutation):
    outcome = result(tmp_path, mutation=mutation)
    assert not outcome["ok"], (mutation, outcome["counts"])


def test_degenerate_observations_fail_closed():
    for observation in (None, {}, [], {"journey": "layouts-page"}):
        outcome = layouts_result(observation=observation)
        assert not outcome["ok"] and outcome["counts"]["expected"] == len(LAYOUTS_REQUIRED)


def test_the_constants_pin_the_measured_semantics():
    assert len(LAYOUTS_TIMELINE) == 14
    kinds = [(delta["type"], tuple(delta["path"] or [])) for delta in LAYOUTS_TIMELINE]
    assert kinds == [
        ("new_element", (1, 0)),
        ("add_block", (0, 0)),
        ("new_element", (0, 0, 0)),
        ("add_block", (0, 1)),
        ("add_block", (0, 1, 0)),
        ("add_block", (0, 1, 1)),
        ("new_element", (0, 1, 0, 0)),
        ("new_element", (0, 1, 1, 0)),
        ("add_block", (0, 2)),
        ("new_element", (0, 2, 0)),
        ("add_block", (2, 0)),
        ("add_block", (2, 0)),
        ("add_block", (2, 0, 0)),
        ("new_element", (2, 0, 0, 0)),
    ]
    expander = LAYOUTS_TIMELINE[1]["block"]
    assert expander["expandable"] == {"label": "Details", "expanded": True}
    assert expander["allowEmpty"] is True and expander["widthConfig"] == {"useStretch": True}
    assert LAYOUTS_TIMELINE[3]["block"]["tabContainer"] == {}
    assert [delta["block"]["tab"]["label"] for delta in LAYOUTS_TIMELINE[4:6]] == ["One", "Two"]
    popover = LAYOUTS_TIMELINE[8]["block"]["popover"]
    assert popover == {"label": "Open settings", "type": "secondary", "open": False}
    first_dialog = LAYOUTS_TIMELINE[10]["block"]["dialog"]
    second_dialog = LAYOUTS_TIMELINE[11]["block"]["dialog"]
    assert "isOpen" not in first_dialog and second_dialog["isOpen"] is True
    assert LAYOUTS_TIMELINE[10]["block_id"] == LAYOUTS_TIMELINE[11]["block_id"] == "$$ID-<hash>-None"
    assert LAYOUTS_TIMELINE[12]["block"]["flexContainer"] == {
        "gapConfig": {"gapSize": "SMALL"}, "direction": "VERTICAL", "justify": "JUSTIFY_START", "align": "ALIGN_START"}
    assert LAYOUTS_DOM["markdowns"] == ["side note", "inside expander", "first tab", "second tab", "inside dialog"]
    assert LAYOUTS_DOM["exceptions"] == []
