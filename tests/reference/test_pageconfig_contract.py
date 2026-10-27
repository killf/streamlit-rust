"""Unit tests of the strict page-config contract (journey-pageconfig-v1)."""
from __future__ import annotations

import copy
import hashlib
import json
import pathlib
import sys

import pytest

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "browser"))

from pageconfig_contract import (  # noqa: E402
    PAGECONFIG_DOM,
    PAGECONFIG_FIELDS,
    PAGECONFIG_REQUIRED,
    PAGECONFIG_SOURCE_FILES,
    pageconfig_result,
)

PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"not-a-real-image-but-magic-and-hash-are-checked"

URL = "http://127.0.0.1:8614"


def stream_frames(config=None, *, leading_main_blocks=0, config_after_delta=False):
    frames = []
    for _ in range(leading_main_blocks):
        frames.append({"direction": "server->client", "timestamp": 0.3,
                       "summary": {"type": "delta", "delta": {"type": "add_block", "block_id": "main_container", "block_type": "vertical",
                                                              "block": {"vertical": {}, "id": "main_container"}, "path": [0]}}})
    config_frame = {"direction": "server->client", "timestamp": 0.4,
                    "summary": {"type": "page_config_changed", "page_config": copy.deepcopy(config if config is not None else PAGECONFIG_FIELDS)}}
    delta_frame = {"direction": "server->client", "timestamp": 0.5,
                   "summary": {"type": "delta", "delta": {"type": "new_element", "path": [0, 0], "element": "markdown", "body": "configured"}}}
    if config_after_delta:
        frames.extend([delta_frame, config_frame])
    else:
        frames.extend([config_frame, delta_frame])
    return frames


def dom():
    return json.loads(json.dumps(copy.deepcopy(PAGECONFIG_DOM), ensure_ascii=False))


def observation(tmp_path, **faults):
    leading = faults.pop("leading_main_blocks", 0)
    config = faults.pop("config", None)
    config_after_delta = faults.pop("config_after_delta", False)
    frames = [
        {"direction": "client->server", "timestamp": 0.0, "summary": {"type": "rerun_script", "rerun_script": {"widget_states": []}}},
        {"direction": "server->client", "timestamp": 0.1, "summary": {"type": "new_session", "new_session": {"script_run_id": "run-1", "session_id": "session-a"}}},
        {"direction": "server->client", "timestamp": 0.2, "summary": {"type": "session_status_changed", "session_status_changed": {"script_is_running": True, "run_on_save": False}}},
        *stream_frames(config, leading_main_blocks=leading, config_after_delta=config_after_delta),
        {"direction": "server->client", "timestamp": 4.0, "summary": {"type": "script_finished", "script_finished": {"status": 0}}},
        {"direction": "server->client", "timestamp": 4.1, "summary": {"type": "session_status_changed", "session_status_changed": {"script_is_running": False, "run_on_save": False}}},
    ]
    stages = [{"name": "01-load", "new_frames": frames, "http": [], "dom": dom()}]
    observation = {
        "journey": "pageconfig-page",
        "contract": "journey-pageconfig-v1",
        "scope": "PYTHON SIDE ONLY",
        "url": f"{URL}/",
        "source": {"file": PAGECONFIG_SOURCE_FILES["python"]},
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

    def find_config_frame():
        return next(frame for frame in target["new_frames"] if frame["summary"].get("type") == "page_config_changed")

    if mutation == "title_changed":
        find_config_frame()["summary"]["page_config"]["title"] = "Other"
    elif mutation == "icon_changed":
        find_config_frame()["summary"]["page_config"]["favicon"] = ":material/cancel:"
    elif mutation == "layout_centered":
        find_config_frame()["summary"]["page_config"]["layout"] = "CENTERED"
    elif mutation == "sidebar_auto":
        find_config_frame()["summary"]["page_config"]["initialSidebarState"] = "AUTO"
    elif mutation == "menu_url_changed":
        find_config_frame()["summary"]["page_config"]["menuItems"]["getHelpUrl"] = "https://example.com/"
    elif mutation == "about_md_changed":
        find_config_frame()["summary"]["page_config"]["menuItems"]["aboutSectionMd"] = "different"
    elif mutation == "menu_removed":
        del find_config_frame()["summary"]["page_config"]["menuItems"]
    elif mutation == "missing_config":
        target["new_frames"] = [frame for frame in target["new_frames"] if frame["summary"].get("type") != "page_config_changed"]
    elif mutation == "second_config_appended":
        target["new_frames"].insert(4, copy.deepcopy(find_config_frame()))
    elif mutation == "config_after_delta":
        return observation_from(tmp_path, config_after_delta=True)
    elif mutation == "delta_path_shift":
        for frame in target["new_frames"]:
            delta = frame["summary"].get("delta") or {}
            if delta.get("type") == "new_element":
                delta["path"] = [0, 1]
    elif mutation == "write_missing":
        target["new_frames"] = [frame for frame in target["new_frames"] if (frame["summary"].get("delta") or {}).get("type") != "new_element"]
    elif mutation == "dom_title_default":
        target["dom"]["title"] = "streamlit"
    elif mutation == "dom_no_wide":
        target["dom"]["wideClasses"] = []
    elif mutation == "dom_favicon_missing":
        target["dom"]["favicons"] = []
    elif mutation == "dom_markdown_missing":
        target["dom"]["markdowns"] = []
    elif mutation == "exception_element":
        target["new_frames"].insert(5, {"direction": "server->client", "timestamp": 2.9,
                                        "summary": {"type": "delta", "delta": {"type": "new_element", "element": "exception", "path": [0, 1]}}})
    elif mutation == "wrong_finish":
        for frame_ in target["new_frames"]:
            if frame_["summary"]["type"] == "script_finished":
                frame_["summary"]["script_finished"]["status"] = 2
    elif mutation == "missing_png":
        (tmp_path / f"{target['name']}.png").unlink()
    elif mutation == "png_sha":
        target["screenshot"]["sha256"] = "0" * 64
    elif mutation == "wrong_contract":
        observation["contract"] = "journey-pageconfig-v0"
    elif mutation == "missing_stage":
        observation["stages"] = []
    assert not faults, faults
    return observation


def observation_from(tmp_path, **faults):
    return observation(tmp_path, **faults)


def result(tmp_path, **faults):
    return pageconfig_result(observation=observation(tmp_path, **faults))


def test_complete_synthetic_model_passes_every_check(tmp_path):
    outcome = result(tmp_path)
    assert outcome["ok"], outcome["failures"]
    assert outcome["counts"] == {"expected": 8, "executed": 8, "asserted": 8}
    assert tuple(check["check"] for check in outcome["checks"]) == PAGECONFIG_REQUIRED


def test_the_rust_leading_main_block_is_the_one_allowed_divergence(tmp_path):
    outcome = result(tmp_path, leading_main_blocks=1)
    assert outcome["ok"], outcome["failures"]


@pytest.mark.parametrize("leading", [2, 3])
def test_more_than_one_leading_main_block_fails(tmp_path, leading):
    outcome = result(tmp_path, leading_main_blocks=leading)
    assert not outcome["ok"], (leading, outcome["counts"])


@pytest.mark.parametrize("mutation", [
    "title_changed", "icon_changed", "layout_centered", "sidebar_auto",
    "menu_url_changed", "about_md_changed", "menu_removed", "missing_config",
    "second_config_appended", "config_after_delta", "delta_path_shift",
    "write_missing", "dom_title_default", "dom_no_wide",
    "dom_favicon_missing", "dom_markdown_missing", "exception_element",
    "wrong_finish", "missing_png", "png_sha",
    "wrong_contract", "missing_stage",
])
def test_known_mutations_fail(tmp_path, mutation):
    outcome = result(tmp_path, mutation=mutation)
    assert not outcome["ok"], (mutation, outcome["counts"])


def test_degenerate_observations_fail_closed():
    for observation in (None, {}, [], {"journey": "pageconfig-page"}):
        outcome = pageconfig_result(observation=observation)
        assert not outcome["ok"] and outcome["counts"]["expected"] == len(PAGECONFIG_REQUIRED)


def test_the_constants_pin_the_measured_semantics():
    assert PAGECONFIG_FIELDS == {
        "title": "Wide demo",
        "favicon": ":material/check_circle:",
        "layout": "WIDE",
        "initialSidebarState": "EXPANDED",
        "menuItems": {
            "getHelpUrl": "https://docs.streamlit.io/",
            "reportABugUrl": "https://github.com/streamlit/streamlit/issues",
            "aboutSectionMd": "### About text\nCreated with the reference fixture.",
        },
    }
    assert PAGECONFIG_DOM["title"] == "Wide demo"
    assert any("streamlit-wide" in entry for entry in PAGECONFIG_DOM["wideClasses"])
    assert PAGECONFIG_DOM["favicons"] == ["shortcut icon https://fonts.gstatic.com/s/i/short-term/release/materialsymbolsrounded/check_circle/default/24px.svg"]
    assert PAGECONFIG_DOM["markdowns"] == ["configured"]
    assert PAGECONFIG_DOM["exceptions"] == []


def test_source_fingerprints_do_not_gate_functional_evidence(tmp_path):
    for source in ({"file": "historical-app.py", "sha256": "changed"}, {"file": "historical-app.py"}, None):
        observed = observation(tmp_path)
        observed["source"] = source
        outcome = pageconfig_result(observation=observed)
        assert outcome["ok"], outcome["failures"]
