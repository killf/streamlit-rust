"""Unit tests of the strict display contract (journey-display-v1)."""
from __future__ import annotations

import copy
import hashlib
import json
import pathlib
import sys

import pytest

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "browser"))

from display_contract import (  # noqa: E402
    DISPLAY_DOMS,
    DISPLAY_REQUIRED,
    DISPLAY_SOURCE_FILES,
    DISPLAY_STAGES,
    DISPLAY_TIMELINE,
    display_result,
)

PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"not-a-real-image-but-magic-and-hash-are-checked"

URL = "http://127.0.0.1:8620"


def build_frame(entry):
    entry = copy.deepcopy(entry)
    kind = entry["kind"]
    if kind == "rerun":
        return {"direction": "client->server", "timestamp": 0.0, "summary": {"type": "rerun_script", "rerun_script": {"widget_states": []}}}
    if kind in ("new_session", "session_status_changed"):
        return {"direction": "server->client", "timestamp": 0.1, "summary": {"type": kind, kind: {}}}
    if kind == "script_finished":
        return {"direction": "server->client", "timestamp": 9.0, "summary": {"type": "script_finished", "script_finished": {"status": 0}}}
    if kind == "block":
        return {"direction": "server->client", "timestamp": 0.3, "summary": {"type": "delta", "delta": {"type": "add_block", "block": entry["block"], "path": entry["path"]}}}
    if kind in ("json", "space"):
        return {"direction": "server->client", "timestamp": 0.5, "summary": {"type": "delta", "delta": {"type": "new_element", "element": kind, "element_full": copy.deepcopy(entry["full"]), "path": entry["path"]}}}
    return {"direction": "server->client", "timestamp": 0.5, "summary": {"type": "delta", "delta": {"type": "new_element", "element": kind, "body": entry.get("body"), "path": entry.get("path")}}}


def stage_frames(name, *, leading_main_blocks=0, keep_placeholder=False):
    frames = []
    for _ in range(leading_main_blocks):
        frames.append({"direction": "server->client", "timestamp": 0.2,
                       "summary": {"type": "delta", "delta": {"type": "add_block", "block_id": "main_container", "block_type": "vertical",
                                                              "block": {"vertical": {}, "id": "main_container"}, "path": [0]}}})
    for entry in DISPLAY_TIMELINE[name]:
        frames.append(build_frame(entry))
        if keep_placeholder and entry["kind"] == "markdown" and entry.get("body") == "replaced":
            frames.insert(len(frames) - 1, build_frame({"kind": "empty", "path": entry["path"]}))
    return frames


def dom(name):
    return json.loads(json.dumps(copy.deepcopy(DISPLAY_DOMS[name]), ensure_ascii=False))


def observation(tmp_path, **faults):
    leading = faults.pop("leading_main_blocks", 0)
    keep_placeholder = faults.pop("keep_placeholder", False)
    stages = []
    for name in DISPLAY_STAGES:
        stages.append({"name": name, "new_frames": stage_frames(name, leading_main_blocks=leading, keep_placeholder=keep_placeholder), "http": [], "dom": dom(name)})
    observation = {
        "journey": "display-page",
        "contract": "journey-display-v1",
        "scope": "PYTHON SIDE ONLY",
        "url": f"{URL}/",
        "source": {"file": DISPLAY_SOURCE_FILES["python"]},
        "capture_sources": {},
        "stages": stages,
        "ipc_dir": str(tmp_path),
    }
    for stage in stages:
        png = f"{stage['name']}.png"
        (tmp_path / png).write_bytes(PNG_BYTES)
        stage["screenshot"] = {"file": png, "sha256": hashlib.sha256(PNG_BYTES).hexdigest()}
    mutation = faults.pop("mutation", None)
    target = stages[0]

    def block_frame(index):
        return [frame for frame in target["new_frames"] if (frame["summary"].get("delta") or {}).get("type") == "add_block"][index]

    def element_frame(kind):
        return next(frame for frame in target["new_frames"] if (frame["summary"].get("delta") or {}).get("element") == kind)

    def markdown_frame(body):
        return next(frame for frame in target["new_frames"]
                    if (frame["summary"].get("delta") or {}).get("element") == "markdown" and frame["summary"]["delta"].get("body") == body)

    if mutation == "json_compact_separators":
        element_frame("json")["summary"]["delta"]["element_full"]["json"]["body"] = "{\"a\":1,\"b\":[true,null]}"
    elif mutation == "json_collapsed":
        element_frame("json")["summary"]["delta"]["element_full"]["json"]["expanded"] = False
    elif mutation == "status_update_path_shifted":
        block_frame(1)["summary"]["delta"]["path"] = [0, 2]
    elif mutation == "status_state_lost":
        block_frame(1)["summary"]["delta"]["block"]["expandable"]["state"] = "RUNNING"
    elif mutation == "status_icon_stale":
        block_frame(1)["summary"]["delta"]["block"]["expandable"]["icon"] = "spinner"
    elif mutation == "status_allow_empty_lost":
        del block_frame(0)["summary"]["delta"]["block"]["allowEmpty"]
    elif mutation == "empty_replacement_wrong_path":
        markdown_frame("replaced")["summary"]["delta"]["path"] = [0, 4]
    elif mutation == "space_height_lost":
        del element_frame("space")["summary"]["delta"]["element_full"]["heightConfig"]
    elif mutation == "space_rect":
        element_frame("space")["summary"]["delta"]["element_full"]["widthConfig"]["pixelWidth"] = 300
    elif mutation == "bottom_root_wrong":
        markdown_frame("bottom line")["summary"]["delta"]["path"] = [0, 4]
    elif mutation == "dom_bottom_missing":
        target["dom"]["bottom"] = []
    elif mutation == "extra_element":
        target["new_frames"].append(build_frame({"kind": "markdown", "body": "extra", "path": [0, 5]}))
    elif mutation == "missing_png":
        (tmp_path / f"{target['name']}.png").unlink()
    elif mutation == "png_sha":
        target["screenshot"]["sha256"] = "0" * 64
    elif mutation == "wrong_contract":
        observation["contract"] = "journey-display-v0"
    elif mutation == "missing_stage":
        observation["stages"] = []
    assert not faults, faults
    return observation


def result(tmp_path, **faults):
    return display_result(observation=observation(tmp_path, **faults))


def test_complete_synthetic_model_passes_every_check(tmp_path):
    outcome = result(tmp_path)
    assert outcome["ok"], outcome["failures"]
    assert outcome["counts"] == {"expected": 11, "executed": 11, "asserted": 11}
    assert tuple(check["check"] for check in outcome["checks"]) == DISPLAY_REQUIRED


def test_the_streamed_placeholder_is_the_coalesced_shape(tmp_path):
    outcome = result(tmp_path, keep_placeholder=True)
    assert outcome["ok"], outcome["failures"]


def test_the_rust_leading_main_block_is_the_one_allowed_divergence(tmp_path):
    outcome = result(tmp_path, leading_main_blocks=1)
    assert outcome["ok"], outcome["failures"]


@pytest.mark.parametrize("leading", [2, 3])
def test_more_than_one_leading_main_block_fails(tmp_path, leading):
    outcome = result(tmp_path, leading_main_blocks=leading)
    assert not outcome["ok"], (leading, outcome["counts"])


@pytest.mark.parametrize("mutation", [
    "json_compact_separators", "json_collapsed", "status_update_path_shifted",
    "status_state_lost", "status_icon_stale", "status_allow_empty_lost",
    "empty_replacement_wrong_path", "space_height_lost", "space_rect",
    "bottom_root_wrong", "dom_bottom_missing", "extra_element",
    "missing_png", "png_sha", "wrong_contract",
    "missing_stage",
])
def test_known_mutations_fail(tmp_path, mutation):
    outcome = result(tmp_path, mutation=mutation)
    assert not outcome["ok"], (mutation, outcome["counts"])


def test_degenerate_observations_fail_closed():
    for observation in (None, {}, [], {"journey": "display-page"}):
        outcome = display_result(observation=observation)
        assert not outcome["ok"] and outcome["counts"]["expected"] == len(DISPLAY_REQUIRED)


def test_the_constants_pin_the_measured_semantics():
    assert DISPLAY_STAGES == ["01-load"]
    load = DISPLAY_TIMELINE["01-load"]
    kinds = [entry["kind"] for entry in load if entry["kind"] not in ("rerun", "new_session", "session_status_changed", "script_finished")]
    assert kinds == ["json", "block", "markdown", "markdown", "block", "markdown", "space", "markdown"]
    blocks = [entry for entry in load if entry["kind"] == "block"]
    assert blocks[0]["block"]["expandable"]["state"] == "RUNNING"
    assert blocks[1]["block"]["expandable"]["state"] == "COMPLETE"
    assert blocks[1]["block"]["expandable"]["icon"] == ":material/check:"
    space = next(entry for entry in load if entry["kind"] == "space")
    assert space["full"] == {"heightConfig": {"pixelHeight": 3}, "widthConfig": {"pixelWidth": 3}, "space": {}}
    bottom = [entry for entry in load if entry["kind"] == "markdown"][3]
    assert bottom["path"] == [3, 0]
    assert DISPLAY_DOMS["01-load"]["bottom"] == ["bottom line"]
    assert all(not dom["exceptions"] for dom in DISPLAY_DOMS.values())


def test_source_fingerprints_do_not_gate_functional_evidence(tmp_path):
    for source in ({"file": "historical-app.py", "sha256": "changed"}, {"file": "historical-app.py"}, None):
        observed = observation(tmp_path)
        observed["source"] = source
        outcome = display_result(observation=observed)
        assert outcome["ok"], outcome["failures"]
