"""Unit tests of the strict text-elements contract (journey-textelements-v1)."""
from __future__ import annotations

import copy
import hashlib
import json
import pathlib
import sys

import pytest

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "browser"))

from textelements_contract import (  # noqa: E402
    TEXTELEMENTS_DOMS,
    TEXTELEMENTS_REQUIRED,
    TEXTELEMENTS_SOURCE_PINS,
    TEXTELEMENTS_STAGES,
    TEXTELEMENTS_TIMELINE,
    textelements_result,
)

PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"not-a-real-image-but-magic-and-hash-are-checked"

URL = "http://127.0.0.1:8619"


def build_frame(entry):
    entry = copy.deepcopy(entry)
    kind = entry["kind"]
    if kind == "rerun":
        return {"direction": "client->server", "timestamp": 0.0, "summary": {"type": "rerun_script", "rerun_script": {"widget_states": []}}}
    if kind in ("new_session", "session_status_changed"):
        return {"direction": "server->client", "timestamp": 0.1, "summary": {"type": kind, kind: {}}}
    if kind == "script_finished":
        return {"direction": "server->client", "timestamp": 9.0, "summary": {"type": "script_finished", "script_finished": {"status": 0}}}
    if kind == "markdown":
        return {"direction": "server->client", "timestamp": 0.5, "summary": {"type": "delta", "delta": {"type": "new_element", "element": "markdown", "body": entry["body"], "path": entry["path"]}}}
    if kind == "exception":
        return {"direction": "server->client", "timestamp": 0.5, "summary": {"type": "delta", "delta": {"type": "new_element", "element": "exception", "exception": {"type": entry["type"], "message": entry["message"], "stackTrace": ["<line>"] * entry["trace"]}, "path": entry["path"]}}}
    full = {kind: copy.deepcopy(entry["body"]), **copy.deepcopy(entry["configs"])}
    return {"direction": "server->client", "timestamp": 0.5, "summary": {"type": "delta", "delta": {"type": "new_element", "element": kind, "element_full": full, "path": entry["path"]}}}


def stage_frames(name, *, leading_main_blocks=0):
    frames = []
    for _ in range(leading_main_blocks):
        frames.append({"direction": "server->client", "timestamp": 0.2,
                       "summary": {"type": "delta", "delta": {"type": "add_block", "block_id": "main_container", "block_type": "vertical",
                                                              "block": {"vertical": {}, "id": "main_container"}, "path": [0]}}})
    frames.extend(build_frame(entry) for entry in TEXTELEMENTS_TIMELINE[name])
    return frames


def dom(name):
    raw = json.loads(json.dumps(copy.deepcopy(TEXTELEMENTS_DOMS[name]), ensure_ascii=False))
    # Rebuild the raw exception text the projection normalizes.
    raw["exceptions"] = [text + "\nTraceback:\neach apps own trace line" for text in raw["exceptions"]]
    return raw


def observation(tmp_path, **faults):
    leading = faults.pop("leading_main_blocks", 0)
    stages = []
    for name in TEXTELEMENTS_STAGES:
        stages.append({"name": name, "new_frames": stage_frames(name, leading_main_blocks=leading), "http": [], "dom": dom(name)})
    observation = {
        "journey": "textelements-page",
        "contract": "journey-textelements-v1",
        "scope": "PYTHON SIDE ONLY",
        "url": f"{URL}/",
        "source": {"file": TEXTELEMENTS_SOURCE_PINS["python"][0], "sha256": TEXTELEMENTS_SOURCE_PINS["python"][1]},
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

    def element_frame(kind):
        return next(frame for frame in target["new_frames"]
                    if (frame["summary"].get("delta") or {}).get("element") == kind)

    if mutation == "text_unwrapped":
        element_frame("text")["summary"]["delta"]["element_full"]["text"]["wrap"] = False
    elif mutation == "heading_no_wrap":
        del element_frame("heading")["summary"]["delta"]["element_full"]["heading"]["wrap"]
    elif mutation == "latex_inline":
        frame = next(frame for frame in target["new_frames"] if (frame["summary"].get("delta") or {}).get("element") == "markdown" and frame["summary"]["delta"].get("body", "").startswith("$$"))
        frame["summary"]["delta"]["body"] = "$a^2$"
    elif mutation == "iframe_no_scroll":
        element_frame("iframe")["summary"]["delta"]["element_full"]["iframe"]["scrolling"] = False
    elif mutation == "iframe_height_changed":
        element_frame("iframe")["summary"]["delta"]["element_full"]["heightConfig"]["pixelHeight"] = 300
    elif mutation == "snow_not_one_shot":
        del element_frame("snow")["summary"]["delta"]["element_full"]["hasOneShotEffect"]
    elif mutation == "echo_code_wrong_path":
        element_frame("code")["summary"]["delta"]["path"] = [0, 7]
    elif mutation == "echo_placeholder_missing":
        frames = target["new_frames"]
        empty = element_frame("empty")
        target["new_frames"] = [frame for frame in frames if frame is not empty]
    elif mutation == "exception_trace_fabricated":
        element_frame("exception")["summary"]["delta"]["exception"]["stackTrace"] = ["<line>", "<line>"]
    elif mutation == "dom_text_missing":
        target["dom"]["texts"] = []
    elif mutation == "dom_snow_missing":
        target["dom"]["snow"] = 0
    elif mutation == "extra_element":
        target["new_frames"].append(build_frame({"kind": "markdown", "body": "extra", "path": [0, 9]}))
    elif mutation == "missing_png":
        (tmp_path / f"{target['name']}.png").unlink()
    elif mutation == "png_sha":
        target["screenshot"]["sha256"] = "0" * 64
    elif mutation == "wrong_source":
        observation["source"]["sha256"] = "0" * 64
    elif mutation == "wrong_contract":
        observation["contract"] = "journey-textelements-v0"
    elif mutation == "missing_stage":
        observation["stages"] = []
    assert not faults, faults
    return observation


def result(tmp_path, **faults):
    return textelements_result(observation=observation(tmp_path, **faults))


def test_complete_synthetic_model_passes_every_check(tmp_path):
    outcome = result(tmp_path)
    assert outcome["ok"], outcome["failures"]
    assert outcome["counts"] == {"expected": 12, "executed": 12, "asserted": 12}
    assert tuple(check["check"] for check in outcome["checks"]) == TEXTELEMENTS_REQUIRED


def test_the_rust_leading_main_block_is_the_one_allowed_divergence(tmp_path):
    outcome = result(tmp_path, leading_main_blocks=1)
    assert outcome["ok"], outcome["failures"]


@pytest.mark.parametrize("leading", [2, 3])
def test_more_than_one_leading_main_block_fails(tmp_path, leading):
    outcome = result(tmp_path, leading_main_blocks=leading)
    assert not outcome["ok"], (leading, outcome["counts"])


@pytest.mark.parametrize("mutation", [
    "text_unwrapped", "heading_no_wrap", "latex_inline", "iframe_no_scroll",
    "iframe_height_changed", "snow_not_one_shot", "echo_code_wrong_path",
    "echo_placeholder_missing", "exception_trace_fabricated",
    "dom_text_missing", "dom_snow_missing", "extra_element",
    "missing_png", "png_sha", "wrong_source", "wrong_contract",
    "missing_stage",
])
def test_known_mutations_fail(tmp_path, mutation):
    outcome = result(tmp_path, mutation=mutation)
    assert not outcome["ok"], (mutation, outcome["counts"])


def test_degenerate_observations_fail_closed():
    for observation in (None, {}, [], {"journey": "textelements-page"}):
        outcome = textelements_result(observation=observation)
        assert not outcome["ok"] and outcome["counts"]["expected"] == len(TEXTELEMENTS_REQUIRED)


def test_the_constants_pin_the_measured_semantics():
    assert TEXTELEMENTS_STAGES == ["01-load"]
    load = TEXTELEMENTS_TIMELINE["01-load"]
    kinds = [entry["kind"] for entry in load if entry["kind"] not in ("rerun", "new_session", "session_status_changed", "script_finished")]
    assert kinds == ["text", "heading", "markdown", "html", "iframe", "snow", "empty", "markdown", "code", "exception"]
    paths = {entry["kind"]: entry["path"] for entry in load if entry["kind"] in ("empty", "code")}
    assert paths["empty"] == paths["code"] == [0, 6], "the echo code retro-fills the placeholder slot"
    exception = next(entry for entry in load if entry["kind"] == "exception")
    assert (exception["type"], exception["message"], exception["trace"]) == ("ValueError", "boom", 1)
    assert TEXTELEMENTS_DOMS["01-load"]["snow"] == 1
    assert TEXTELEMENTS_DOMS["01-load"]["iframes"] == ["https://example.com/"]
    assert TEXTELEMENTS_DOMS["01-load"]["exceptions"] == ["ValueError: boom\nTraceback:"]
