"""Unit tests of the strict display2 contract (journey-display2-v1)."""
from __future__ import annotations

import copy
import hashlib
import json
import pathlib
import sys

import pytest

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "browser"))

from display2_contract import (  # noqa: E402
    DISPLAY2_DOMS,
    DISPLAY2_REQUIRED,
    DISPLAY2_SOURCE_FILES,
    DISPLAY2_STAGES,
    DISPLAY2_TIMELINE,
    display2_result,
)

PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"not-a-real-image-but-magic-and-hash-are-checked"

PDF_MESSAGE = "The PDF viewer requires the `streamlit-pdf` component to be installed.\n\nPlease run `pip install streamlit[pdf]` to install it.\n\nFor more information, see the Streamlit PDF documentation at https://docs.streamlit.io/develop/api-reference/media/st.pdf."


def build_frame(entry):
    entry = copy.deepcopy(entry)
    kind = entry["kind"]
    if kind == "logo":
        return {"direction": "server->client", "timestamp": 0.1, "summary": {"type": "logo", "logo": entry["logo"], "metadata_shape": entry.get("metadata_shape")}}
    if kind == "rerun":
        return {"direction": "client->server", "timestamp": 0.0, "summary": {"type": "rerun_script", "rerun_script": {"widget_states": []}}}
    if kind in ("new_session", "session_status_changed"):
        return {"direction": "server->client", "timestamp": 0.1, "summary": {"type": kind, kind: {}}}
    if kind == "script_finished":
        return {"direction": "server->client", "timestamp": 9.0, "summary": {"type": "script_finished", "script_finished": {"status": 0}}}
    if kind in ("help_info", "skeleton"):
        return {"direction": "server->client", "timestamp": 0.5, "summary": {"type": "delta", "delta": {"type": "new_element", "element": kind, "element_full": entry["element_full"], "path": entry["path"]}}}
    if kind == "exception":
        exception = dict(entry["exception"])
        exception["stackTrace"] = ['File "<side-specific>", line 1']
        return {"direction": "server->client", "timestamp": 0.5, "summary": {"type": "delta", "delta": {"type": "new_element", "element": "exception", "exception": exception, "path": entry["path"]}}}
    raise AssertionError(kind)


def stage_frames(name, *, leading_main_blocks=0):
    frames = []
    for _ in range(leading_main_blocks):
        frames.append({"direction": "server->client", "timestamp": 0.2,
                       "summary": {"type": "delta", "delta": {"type": "add_block", "block_id": "main_container", "block_type": "vertical",
                                                              "block": {"vertical": {}, "id": "main_container"}, "path": [0]}}})
    frames.extend(build_frame(entry) for entry in DISPLAY2_TIMELINE[name])
    return frames


def dom(name):
    return json.loads(json.dumps(copy.deepcopy(DISPLAY2_DOMS[name]), ensure_ascii=False))


def observation(tmp_path, **faults):
    leading = faults.pop("leading_main_blocks", 0)
    stages = [{"name": name, "new_frames": stage_frames(name, leading_main_blocks=leading), "http": [], "dom": dom(name)}
              for name in DISPLAY2_STAGES]
    observation = {
        "journey": "display2-page",
        "contract": "journey-display2-v1",
        "scope": "PYTHON SIDE ONLY",
        "url": "http://127.0.0.1:8625/",
        "source": {"file": DISPLAY2_SOURCE_FILES["python"]},
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

    def delta_of(stage, element):
        return [frame for frame in stage["new_frames"] if (frame["summary"].get("delta") or {}).get("element") == element]

    def logo_frame(stage):
        return next(frame for frame in stage["new_frames"] if frame["summary"].get("type") == "logo")

    def timeline_entry(kind):
        return next(entry for entry in DISPLAY2_TIMELINE["01-load"] if entry["kind"] == kind)

    if mutation == "logo_type_lost":
        logo_frame(load)["summary"]["logo"]["imageType"] = "IMAGE"
    elif mutation == "logo_size_lost":
        logo_frame(load)["summary"]["logo"].pop("size")
    elif mutation == "help_value_lost":
        delta_of(load, "help_info")[0]["summary"]["delta"]["element_full"]["helpInfo"].pop("value")
    elif mutation == "skeleton_height_lost":
        delta_of(load, "skeleton")[0]["summary"]["delta"]["element_full"].pop("heightConfig")
    elif mutation == "pdf_type_shortened":
        delta_of(load, "exception")[0]["summary"]["delta"]["exception"]["type"] = "StreamlitAPIException"
    elif mutation == "pdf_flags_lost":
        for key in ("messageIsMarkdown", "isStreamlitException"):
            delta_of(load, "exception")[0]["summary"]["delta"]["exception"].pop(key)
    elif mutation == "pdf_message_edited":
        delta_of(load, "exception")[0]["summary"]["delta"]["exception"]["message"] = "short"
    elif mutation == "dom_help_missing":
        load["dom"]["help"] = []
    elif mutation == "extra_element":
        load["new_frames"].append(build_frame({"kind": "skeleton", "element_full": timeline_entry("skeleton")["element_full"], "path": [0, 3]}))
    elif mutation == "missing_png":
        (tmp_path / f"{load['name']}.png").unlink()
    elif mutation == "png_sha":
        load["screenshot"]["sha256"] = "0" * 64
    elif mutation == "wrong_contract":
        observation["contract"] = "journey-display2-v0"
    elif mutation == "missing_stage":
        observation["stages"] = []
    assert not faults, faults
    return observation


def result(tmp_path, **faults):
    return display2_result(observation=observation(tmp_path, **faults))


def test_complete_synthetic_model_passes_every_check(tmp_path):
    outcome = result(tmp_path)
    assert outcome["ok"], outcome["failures"]
    assert outcome["counts"]["expected"] == len(DISPLAY2_REQUIRED)
    assert tuple(check["check"] for check in outcome["checks"]) == DISPLAY2_REQUIRED


def test_the_rust_leading_main_block_is_the_one_allowed_divergence(tmp_path):
    outcome = result(tmp_path, leading_main_blocks=1)
    assert outcome["ok"], outcome["failures"]


@pytest.mark.parametrize("leading", [2, 3])
def test_more_than_one_leading_main_block_fails(tmp_path, leading):
    outcome = result(tmp_path, leading_main_blocks=leading)
    assert not outcome["ok"], (leading, outcome["counts"])


@pytest.mark.parametrize("mutation", [
    "logo_type_lost", "logo_size_lost", "help_value_lost",
    "skeleton_height_lost", "pdf_type_shortened", "pdf_flags_lost",
    "pdf_message_edited", "dom_help_missing", "extra_element",
    "missing_png", "png_sha", "wrong_contract", "missing_stage",
])
def test_known_mutations_fail(tmp_path, mutation):
    outcome = result(tmp_path, mutation=mutation)
    assert not outcome["ok"], (mutation, outcome["counts"])


def test_degenerate_observations_fail_closed():
    for observation in (None, {}, [], {"journey": "display2-page"}):
        outcome = display2_result(observation=observation)
        assert not outcome["ok"] and outcome["counts"]["expected"] == len(DISPLAY2_REQUIRED)


def test_the_constants_pin_the_measured_semantics():
    assert DISPLAY2_STAGES == ["01-load"]
    load = DISPLAY2_TIMELINE["01-load"]

    def entry(kind):
        return next(item for item in load if item["kind"] == kind)

    assert entry("logo") == {"kind": "logo", "logo": {"image": "🏠", "size": "small", "imageType": "EMOJI"}}
    assert entry("help_info")["element_full"]["helpInfo"] == {"docString": "Return the number of items in a container.",
                                                               "type": "builtin_function_or_method", "name": "len",
                                                               "value": "builtins.len(obj, /)"}
    assert entry("skeleton")["element_full"] == {"skeleton": {}, "heightConfig": {"pixelHeight": 100}, "widthConfig": {"useStretch": True}}
    assert entry("exception")["exception"]["type"] == "streamlit.errors.StreamlitAPIException"
    assert entry("exception")["exception"]["message"] == PDF_MESSAGE
    assert "stackTrace" not in entry("exception")["exception"]
    assert all(not dom["skeletons"] or dom["skeletons"] for dom in DISPLAY2_DOMS.values())


def test_source_fingerprints_do_not_gate_functional_evidence(tmp_path):
    for source in ({"file": "historical-app.py", "sha256": "changed"}, {"file": "historical-app.py"}, None):
        observed = observation(tmp_path)
        observed["source"] = source
        outcome = display2_result(observation=observed)
        assert outcome["ok"], outcome["failures"]
