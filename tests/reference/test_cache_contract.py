"""Unit tests of the strict cache contract (journey-cache-v1)."""
from __future__ import annotations

import copy
import hashlib
import json
import pathlib
import sys

import pytest

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "browser"))

from cache_contract import (  # noqa: E402
    CACHE_DOMS,
    CACHE_REQUIRED,
    CACHE_SOURCE_PINS,
    CACHE_STAGES,
    CACHE_TIMELINE,
    CACHE_TRANSIENT_PATHS,
    cache_result,
)

PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"not-a-real-image-but-magic-and-hash-are-checked"

URL = "http://127.0.0.1:8617"


def build_frame(entry):
    entry = copy.deepcopy(entry)
    kind = entry["kind"]
    if kind == "rerun":
        states = []
        for state in entry["widget_states"]:
            real = state["id"]
            if real.endswith("-None"):
                real = "$$ID-ca80e2944c65088786bdb4f6a1134a49-None"
            states.append({**state, "id": real})
        return {"direction": "client->server", "timestamp": 0.0, "summary": {"type": "rerun_script", "rerun_script": {"query_string": entry["query_string"], "widget_states": states}}}
    if kind == "transient":
        return {"direction": "server->client", "timestamp": 0.5, "summary": {"type": "delta", "delta": {"type": "new_transient", "transient": entry["transient"], "path": entry["path"]}}}
    if kind in ("new_session", "session_status_changed", "script_finished"):
        if kind == "script_finished":
            return {"direction": "server->client", "timestamp": 9.0, "summary": {"type": "script_finished", "script_finished": {"status": 0}}}
        return {"direction": "server->client", "timestamp": 0.1, "summary": {"type": kind, kind: {}}}
    return {"direction": "server->client", "timestamp": 0.5, "summary": {"type": "delta", "delta": {"type": "new_element", "element": kind, "path": entry.get("path"), "body": entry.get("body")}}}


def stage_frames(name, *, leading_main_blocks=0):
    frames = []
    for _ in range(leading_main_blocks):
        frames.append({"direction": "server->client", "timestamp": 0.2,
                       "summary": {"type": "delta", "delta": {"type": "add_block", "block_id": "main_container", "block_type": "vertical",
                                                              "block": {"vertical": {}, "id": "main_container"}, "path": [0]}}})
    frames.extend(build_frame(entry) for entry in CACHE_TIMELINE[name])
    return frames


def dom(name):
    return json.loads(json.dumps(copy.deepcopy(CACHE_DOMS[name]), ensure_ascii=False))


def observation(tmp_path, **faults):
    leading = faults.pop("leading_main_blocks", 0)
    stages = []
    for name in CACHE_STAGES:
        stages.append({"name": name, "new_frames": stage_frames(name, leading_main_blocks=leading), "http": [], "dom": dom(name)})
    observation = {
        "journey": "cache-page",
        "contract": "journey-cache-v1",
        "scope": "PYTHON SIDE ONLY",
        "url": f"{URL}/",
        "source": {"file": CACHE_SOURCE_PINS["python"][0], "sha256": CACHE_SOURCE_PINS["python"][1]},
        "capture_sources": {},
        "stages": stages,
        "ipc_dir": str(tmp_path),
    }
    for stage in stages:
        png = f"{stage['name']}.png"
        (tmp_path / png).write_bytes(PNG_BYTES)
        stage["screenshot"] = {"file": png, "sha256": hashlib.sha256(PNG_BYTES).hexdigest()}
    mutation = faults.pop("mutation", None)
    miss, hit = stages

    def markdown_frames(stage, body=None):
        out = [frame for frame in stage["new_frames"]
               if (frame["summary"].get("delta") or {}).get("type") == "new_element"
               and (body is None or frame["summary"]["delta"].get("body") == body)]
        return out

    def transient_frames(stage):
        return [frame for frame in stage["new_frames"]
                if (frame["summary"].get("delta") or {}).get("type") == "new_transient"]

    if mutation == "transient_missing":
        first_transient = next(frame for frame in miss["new_frames"]
                               if (frame["summary"].get("delta") or {}).get("type") == "new_transient")
        miss["new_frames"] = [frame for frame in miss["new_frames"] if frame is not first_transient]
    elif mutation == "transient_shifted":
        transient_frames(miss)[2]["summary"]["delta"]["path"] = [0, 4]
    elif mutation == "transient_before_inside":
        frames = miss["new_frames"]
        index = frames.index(transient_frames(miss)[2])
        frames.insert(frames.index(markdown_frames(miss, "inside cached fn")[0]), frames.pop(index))
    elif mutation == "hit_transient_present":
        hit["new_frames"].insert(4, copy.deepcopy(transient_frames(hit)[0]))
    elif mutation == "replay_path_shifted":
        markdown_frames(hit, "inside cached fn")[0]["summary"]["delta"]["path"] = [0, 4]
    elif mutation == "post_replay_unshifted":
        markdown_frames(hit, "side=1")[0]["summary"]["delta"]["path"] = [0, 3]
    elif mutation == "value_unstable":
        markdown_frames(hit, "cached=42")[0]["summary"]["delta"]["body"] = "cached=84"
    elif mutation == "remiss_transient_missing":
        doomed = {id(frame) for frame in transient_frames(hit)}
        hit["new_frames"] = [frame for frame in hit["new_frames"] if id(frame) not in doomed]
    elif mutation == "clear_missing":
        bodies = {"cleared", "cached_after_clear=42"}
        hit["new_frames"] = [frame for frame in hit["new_frames"]
                             if (frame["summary"].get("delta") or {}).get("body") not in bodies
                             and (frame["summary"].get("delta") or {}).get("type") != "new_transient"]
    elif mutation == "dom_markdown_missing":
        hit["dom"]["markdowns"] = [text for text in hit["dom"]["markdowns"] if text != "inside cached fn"]
    elif mutation == "exception_element":
        miss["new_frames"].insert(6, {"direction": "server->client", "timestamp": 2.9,
                                      "summary": {"type": "delta", "delta": {"type": "new_element", "element": "exception", "path": [0, 5]}}})
    elif mutation == "wrong_finish":
        for frame in miss["new_frames"]:
            if frame["summary"]["type"] == "script_finished":
                frame["summary"]["script_finished"]["status"] = 2
    elif mutation == "missing_png":
        (tmp_path / f"{miss['name']}.png").unlink()
    elif mutation == "png_sha":
        miss["screenshot"]["sha256"] = "0" * 64
    elif mutation == "wrong_source":
        observation["source"]["sha256"] = "0" * 64
    elif mutation == "wrong_contract":
        observation["contract"] = "journey-cache-v0"
    elif mutation == "missing_stage":
        observation["stages"] = []
    assert not faults, faults
    return observation


def result(tmp_path, **faults):
    return cache_result(observation=observation(tmp_path, **faults))


def test_complete_synthetic_model_passes_every_check(tmp_path):
    outcome = result(tmp_path)
    assert outcome["ok"], outcome["failures"]
    assert outcome["counts"] == {"expected": 12, "executed": 12, "asserted": 12}
    assert tuple(check["check"] for check in outcome["checks"]) == CACHE_REQUIRED


def test_the_rust_leading_main_block_is_the_one_allowed_divergence(tmp_path):
    outcome = result(tmp_path, leading_main_blocks=1)
    assert outcome["ok"], outcome["failures"]


@pytest.mark.parametrize("leading", [2, 3])
def test_more_than_one_leading_main_block_fails(tmp_path, leading):
    outcome = result(tmp_path, leading_main_blocks=leading)
    assert not outcome["ok"], (leading, outcome["counts"])


@pytest.mark.parametrize("mutation", [
    "transient_missing", "transient_shifted", "transient_before_inside",
    "hit_transient_present", "replay_path_shifted", "post_replay_unshifted",
    "value_unstable", "remiss_transient_missing", "clear_missing",
    "dom_markdown_missing", "exception_element", "wrong_finish",
    "missing_png", "png_sha", "wrong_source", "wrong_contract",
    "missing_stage",
])
def test_known_mutations_fail(tmp_path, mutation):
    outcome = result(tmp_path, mutation=mutation)
    assert not outcome["ok"], (mutation, outcome["counts"])


def test_degenerate_observations_fail_closed():
    for observation in (None, {}, [], {"journey": "cache-page"}):
        outcome = cache_result(observation=observation)
        assert not outcome["ok"] and outcome["counts"]["expected"] == len(CACHE_REQUIRED)


def test_the_constants_pin_the_measured_semantics():
    assert CACHE_STAGES == ["01-load", "02-again-click"]
    assert CACHE_TRANSIENT_PATHS == {"01-load": [[0, 1], [0, 2], [0, 3]], "02-again-click": [[0, 7]]}
    miss = CACHE_TIMELINE["01-load"]
    hit = CACHE_TIMELINE["02-again-click"]
    assert all(entry["transient"] == {} for entry in miss if entry["kind"] == "transient")
    assert all(entry["transient"] == {} for entry in hit if entry["kind"] == "transient")
    inside_miss = [e for e in miss if e["kind"] == "markdown" and e.get("body") == "inside cached fn"][0]
    inside_hit = [e for e in hit if e["kind"] == "markdown" and e.get("body") == "inside cached fn"][0]
    side_hit = [e for e in hit if e["kind"] == "markdown" and e.get("body") == "side=1"][0]
    assert inside_miss["path"] == inside_hit["path"] == [0, 3]
    assert side_hit["path"] == [0, 4]
    assert CACHE_DOMS["01-load"]["markdowns"] == ["runs=1", "cached=42", "cached_other=14", "inside cached fn", "side=1"]
    assert CACHE_DOMS["02-again-click"]["markdowns"] == ["runs=2", "cached=42", "cached_other=14", "inside cached fn", "side=1", "cleared", "cached_after_clear=42"]
    assert all(not dom["exceptions"] for dom in CACHE_DOMS.values())
