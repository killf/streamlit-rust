"""Unit tests of the strict navigation contract (journey-navigation-v1)."""
from __future__ import annotations

import copy
import hashlib
import json
import pathlib
import sys

import pytest

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "browser"))

from navigation_contract import (  # noqa: E402
    NAVIGATION_DOMS,
    NAVIGATION_REQUIRED,
    NAVIGATION_SOURCE_FILES,
    NAVIGATION_STAGES,
    NAVIGATION_TIMELINE,
    navigation_result,
)

PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"not-a-real-image-but-magic-and-hash-are-checked"

MAIN_HASH = next(entry["pages"][0]["hash"] for stage in NAVIGATION_TIMELINE.values() for entry in stage if entry["kind"] == "navigation")
TWO_HASH = next(entry["pages"][1]["hash"] for stage in NAVIGATION_TIMELINE.values() for entry in stage if entry["kind"] == "navigation")
URL = "http://127.0.0.1:8618"


def build_frame(entry):
    entry = copy.deepcopy(entry)
    kind = entry["kind"]
    if kind == "rerun":
        states = []
        for state in entry["widget_states"]:
            real = state["id"]
            if real.endswith("-None"):
                real = "$$ID-bf8a25d7cee6b6b11e53de1446109712-None"
            states.append({**state, "id": real})
        page = entry["page_script_hash"]
        return {"direction": "client->server", "timestamp": 0.0, "summary": {"type": "rerun_script", "rerun_script": {"page_script_hash": page if page != "<main>" else "", "widget_states": states}}}
    if kind == "new_session":
        page = entry["page"]
        return {"direction": "server->client", "timestamp": 0.1, "summary": {"type": "new_session", "new_session": {"page_script_hash": page if page != "<main>" else "<main-hash>", "main_script_hash": "<main-hash>"}}}
    if kind == "navigation":
        pages = [{"pageScriptHash": page["hash"], "pageName": page["name"], "icon": page["icon"], "isDefault": page["default"], "urlPathname": page["url_path"]} for page in entry["pages"]]
        return {"direction": "server->client", "timestamp": 0.3, "summary": {"type": "navigation", "navigation": {"appPages": pages, "position": entry["position"], "pageScriptHash": entry["current"], "sections": entry["sections"], "expanded": entry["expanded"]}}}
    if kind == "page_info":
        return {"direction": "server->client", "timestamp": 0.5, "summary": {"type": "page_info_changed", "page_info": {"query_string": entry["query_string"]}}}
    if kind == "finished":
        return {"direction": "server->client", "timestamp": 9.0, "summary": {"type": "script_finished", "script_finished": {"status": entry["status"]}}}
    if kind == "session_status_changed":
        return {"direction": "server->client", "timestamp": 0.2, "summary": {"type": kind, kind: {}}}
    if kind == "button":
        return {"direction": "server->client", "timestamp": 0.5, "summary": {"type": "delta", "delta": {"type": "new_element", "element": "button", "path": entry["path"]}}}
    return {"direction": "server->client", "timestamp": 0.5, "summary": {"type": "delta", "delta": {"type": "new_element", "element": kind, "path": entry.get("path"), "body": entry.get("body")}}}


def stage_frames(name, *, leading_main_blocks=0):
    frames = []
    for _ in range(leading_main_blocks):
        frames.append({"direction": "server->client", "timestamp": 0.25,
                       "summary": {"type": "delta", "delta": {"type": "add_block", "block_id": "main_container", "block_type": "vertical",
                                                              "block": {"vertical": {}, "id": "main_container"}, "path": [0]}}})
    frames.extend(build_frame(entry) for entry in NAVIGATION_TIMELINE[name])
    return frames


def dom(name):
    return json.loads(json.dumps(copy.deepcopy(NAVIGATION_DOMS[name]), ensure_ascii=False))


def observation(tmp_path, **faults):
    leading = faults.pop("leading_main_blocks", 0)
    stages = []
    for name in NAVIGATION_STAGES:
        stages.append({"name": name, "new_frames": stage_frames(name, leading_main_blocks=leading), "http": [], "dom": dom(name)})
    observation = {
        "journey": "navigation-page",
        "contract": "journey-navigation-v1",
        "scope": "PYTHON SIDE ONLY",
        "url": f"{URL}/",
        "source": {"file": NAVIGATION_SOURCE_FILES["python"]},
        "capture_sources": {},
        "stages": stages,
        "ipc_dir": str(tmp_path),
    }
    for stage in stages:
        png = f"{stage['name']}.png"
        (tmp_path / png).write_bytes(PNG_BYTES)
        stage["screenshot"] = {"file": png, "sha256": hashlib.sha256(PNG_BYTES).hexdigest()}
    mutation = faults.pop("mutation", None)
    load, click_two, back, switched = stages

    def markdown_frames(stage, body=None):
        return [frame for frame in stage["new_frames"]
                if (frame["summary"].get("delta") or {}).get("type") == "new_element"
                and (frame["summary"]["delta"].get("element") == "markdown")
                and (body is None or frame["summary"]["delta"].get("body") == body)]

    def nav_frames(stage):
        return [frame for frame in stage["new_frames"] if (frame["summary"].get("type")) == "navigation"]

    if mutation == "navigation_missing":
        click_two["new_frames"] = [frame for frame in click_two["new_frames"] if frame["summary"].get("type") != "navigation"]
    elif mutation == "page_hash_wrong":
        nav_frames(click_two)[0]["summary"]["navigation"]["appPages"][1]["pageScriptHash"] = "0" * 32
    elif mutation == "default_marker_missing":
        nav_frames(load)[0]["summary"]["navigation"]["appPages"][0]["isDefault"] = False
    elif mutation == "url_pathname_on_default":
        nav_frames(load)[0]["summary"]["navigation"]["appPages"][0]["urlPathname"] = "render_main"
    elif mutation == "position_top":
        nav_frames(load)[0]["summary"]["navigation"]["position"] = "TOP"
    elif mutation == "current_page_wrong":
        nav_frames(click_two)[0]["summary"]["navigation"]["pageScriptHash"] = MAIN_HASH
    elif mutation == "new_session_hash_mismatch":
        session = next(frame for frame in click_two["new_frames"] if frame["summary"].get("type") == "new_session")
        session["summary"]["new_session"]["page_script_hash"] = TWO_HASH[::-1]
    elif mutation == "hits_reset":
        markdown_frames(back, "page=main hits=2")[0]["summary"]["delta"]["body"] = "page=main hits=1"
    elif mutation == "switch_early_finish_lost":
        finishes = [frame for frame in switched["new_frames"] if frame["summary"].get("type") == "script_finished"]
        finishes[0]["summary"]["script_finished"]["status"] = 0
    elif mutation == "switch_page_info_missing":
        switched["new_frames"] = [frame for frame in switched["new_frames"] if frame["summary"].get("type") != "page_info_changed"]
    elif mutation == "server_run_missing":
        cut = next(index for index, frame in enumerate(switched["new_frames"]) if frame["summary"].get("type") == "new_session" and index > 0)
        del switched["new_frames"][cut:]
    elif mutation == "second_rerun_fabricated":
        switched["new_frames"].append(build_frame({"kind": "rerun", "page_script_hash": TWO_HASH, "widget_states": []}))
    elif mutation == "dom_url_stale":
        click_two["dom"]["url"] = "/"
    elif mutation == "dom_nav_missing":
        load["dom"]["nav"] = ["Main", "Two"]
    elif mutation == "exception_element":
        load["new_frames"].insert(6, {"direction": "server->client", "timestamp": 2.9,
                                      "summary": {"type": "delta", "delta": {"type": "new_element", "element": "exception", "path": [0, 2]}}})
    elif mutation == "wrong_finish":
        for frame in back["new_frames"]:
            if frame["summary"]["type"] == "script_finished":
                frame["summary"]["script_finished"]["status"] = 2
    elif mutation == "missing_png":
        (tmp_path / f"{load['name']}.png").unlink()
    elif mutation == "png_sha":
        load["screenshot"]["sha256"] = "0" * 64
    elif mutation == "wrong_contract":
        observation["contract"] = "journey-navigation-v0"
    elif mutation == "missing_stage":
        observation["stages"] = []
    assert not faults, faults
    return observation


def result(tmp_path, **faults):
    return navigation_result(observation=observation(tmp_path, **faults))


def test_complete_synthetic_model_passes_every_check(tmp_path):
    outcome = result(tmp_path)
    assert outcome["ok"], outcome["failures"]
    assert outcome["counts"] == {"expected": 11, "executed": 11, "asserted": 11}
    assert tuple(check["check"] for check in outcome["checks"]) == NAVIGATION_REQUIRED


def test_the_rust_leading_main_block_is_the_one_allowed_divergence(tmp_path):
    outcome = result(tmp_path, leading_main_blocks=1)
    assert outcome["ok"], outcome["failures"]


@pytest.mark.parametrize("leading", [2, 3])
def test_more_than_one_leading_main_block_fails(tmp_path, leading):
    outcome = result(tmp_path, leading_main_blocks=leading)
    assert not outcome["ok"], (leading, outcome["counts"])


@pytest.mark.parametrize("mutation", [
    "navigation_missing", "page_hash_wrong", "default_marker_missing",
    "url_pathname_on_default", "position_top", "current_page_wrong",
    "new_session_hash_mismatch", "hits_reset", "switch_early_finish_lost",
    "switch_page_info_missing", "server_run_missing", "second_rerun_fabricated",
    "dom_url_stale", "dom_nav_missing", "exception_element", "wrong_finish",
    "missing_png", "png_sha", "wrong_contract",
    "missing_stage",
])
def test_known_mutations_fail(tmp_path, mutation):
    outcome = result(tmp_path, mutation=mutation)
    assert not outcome["ok"], (mutation, outcome["counts"])


def test_degenerate_observations_fail_closed():
    for observation in (None, {}, [], {"journey": "navigation-page"}):
        outcome = navigation_result(observation=observation)
        assert not outcome["ok"] and outcome["counts"]["expected"] == len(NAVIGATION_REQUIRED)


def test_the_constants_pin_the_measured_semantics():
    assert NAVIGATION_STAGES == ["01-load", "02-click-two", "03-back-main", "04-switch-button"]
    load = NAVIGATION_TIMELINE["01-load"]
    nav = next(entry for entry in load if entry["kind"] == "navigation")
    assert [page["hash"] for page in nav["pages"]] == [MAIN_HASH, TWO_HASH]
    assert nav["pages"][0] == {"hash": MAIN_HASH, "name": "Main", "icon": ":material/home:", "default": True, "url_path": ""}
    assert nav["pages"][1] == {"hash": TWO_HASH, "name": "Two", "icon": "", "default": False, "url_path": "two"}
    assert nav["position"] == "SIDEBAR" and nav["current"] == MAIN_HASH and nav["sections"] == [""]
    assert next(entry for entry in load if entry["kind"] == "new_session")["page"] == "<main>"
    two = NAVIGATION_TIMELINE["02-click-two"]
    assert next(entry for entry in two if entry["kind"] == "new_session")["page"] == TWO_HASH
    switched = NAVIGATION_TIMELINE["04-switch-button"]
    assert [entry["status"] for entry in switched if entry["kind"] == "finished"] == [2, 0]
    assert NAVIGATION_DOMS["02-click-two"]["url"] == "/two"
    assert NAVIGATION_DOMS["03-back-main"]["markdowns"] == ["page=main hits=2"]
    assert all(not dom["exceptions"] for dom in NAVIGATION_DOMS.values())


def test_source_fingerprints_do_not_gate_functional_evidence(tmp_path):
    for source in ({"file": "historical-app.py", "sha256": "changed"}, {"file": "historical-app.py"}, None):
        observed = observation(tmp_path)
        observed["source"] = source
        outcome = navigation_result(observation=observed)
        assert outcome["ok"], outcome["failures"]
