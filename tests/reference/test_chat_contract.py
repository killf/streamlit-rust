"""Unit tests of the strict chat contract (journey-chat-v1)."""
from __future__ import annotations

import copy
import hashlib
import json
import pathlib
import sys

import pytest

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "browser"))

from chat_contract import (  # noqa: E402
    CHAT_DOMS,
    CHAT_INPUTS,
    CHAT_REQUIRED,
    CHAT_SOURCE_FILES,
    CHAT_STAGES,
    CHAT_TIMELINE,
    chat_result,
)

PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"not-a-real-image-but-magic-and-hash-are-checked"

CHAT_ID = "$$ID-9ffa0071d49a881686a4660123e61147-None"
URL = "http://127.0.0.1:8621"


def build_frame(entry):
    entry = copy.deepcopy(entry)
    kind = entry["kind"]
    if kind == "rerun":
        states = []
        for state in entry["states"]:
            real = CHAT_ID if state["id"] == "$$ID-None" else state["id"]
            states.append({**state, "id": real})
        return {"direction": "client->server", "timestamp": 0.0, "summary": {"type": "rerun_script", "rerun_script": {"widget_states": states}}}
    if kind in ("new_session", "session_status_changed"):
        return {"direction": "server->client", "timestamp": 0.1, "summary": {"type": kind, kind: {}}}
    if kind == "script_finished":
        return {"direction": "server->client", "timestamp": 9.0, "summary": {"type": "script_finished", "script_finished": {"status": 0}}}
    if kind == "chat_message":
        block = {kind_entry: copy.deepcopy(entry["chat"]) for kind_entry in ["chatMessage"]}
        block.update(copy.deepcopy(entry["configs"]))
        return {"direction": "server->client", "timestamp": 0.3, "summary": {"type": "delta", "delta": {"type": "add_block", "block": block, "path": entry["path"]}}}
    if kind == "chat_input":
        widget = copy.deepcopy(entry["widget"])
        widget["id"] = CHAT_ID
        return {"direction": "server->client", "timestamp": 0.5, "summary": {"type": "delta", "delta": {"type": "new_element", "element": "chat_input", "widget": widget, "id": CHAT_ID, "path": entry["path"]}}}
    return {"direction": "server->client", "timestamp": 0.5, "summary": {"type": "delta", "delta": {"type": "new_element", "element": kind, "body": entry.get("body"), "path": entry.get("path")}}}


def stage_frames(name, *, leading_main_blocks=0):
    frames = []
    for _ in range(leading_main_blocks):
        frames.append({"direction": "server->client", "timestamp": 0.2,
                       "summary": {"type": "delta", "delta": {"type": "add_block", "block_id": "main_container", "block_type": "vertical",
                                                              "block": {"vertical": {}, "id": "main_container"}, "path": [0]}}})
    frames.extend(build_frame(entry) for entry in CHAT_TIMELINE[name])
    return frames


def dom(name):
    return json.loads(json.dumps(copy.deepcopy(CHAT_DOMS[name]), ensure_ascii=False))


def observation(tmp_path, **faults):
    leading = faults.pop("leading_main_blocks", 0)
    stages = []
    for name in CHAT_STAGES:
        stages.append({"name": name, "new_frames": stage_frames(name, leading_main_blocks=leading), "http": [], "dom": dom(name)})
    observation = {
        "journey": "chat-page",
        "contract": "journey-chat-v1",
        "scope": "PYTHON SIDE ONLY",
        "url": f"{URL}/",
        "source": {"file": CHAT_SOURCE_FILES["python"]},
        "capture_sources": {},
        "stages": stages,
        "ipc_dir": str(tmp_path),
    }
    for stage in stages:
        png = f"{stage['name']}.png"
        (tmp_path / png).write_bytes(PNG_BYTES)
        stage["screenshot"] = {"file": png, "sha256": hashlib.sha256(PNG_BYTES).hexdigest()}
    mutation = faults.pop("mutation", None)
    load, commit = stages

    def chat_frames(stage):
        return [frame for frame in stage["new_frames"] if (frame["summary"].get("delta") or {}).get("block")]

    def chat_input_frame(stage):
        return next(frame for frame in stage["new_frames"] if (frame["summary"].get("delta") or {}).get("element") == "chat_input")

    def rerun_frame(stage):
        return next(frame for frame in stage["new_frames"] if frame["summary"].get("type") == "rerun_script")

    if mutation == "avatar_not_defaulted":
        chat_frames(load)[0]["summary"]["delta"]["block"]["chatMessage"]["avatar"] = ""
    elif mutation == "avatar_type_emoji":
        for stage in stages:
            for frame in chat_frames(stage):
                frame["summary"]["delta"]["block"]["chatMessage"]["avatarType"] = "EMOJI"
    elif mutation == "block_not_allow_empty":
        del chat_frames(load)[0]["summary"]["delta"]["block"]["allowEmpty"]
    elif mutation == "input_main_path":
        chat_input_frame(load)["summary"]["delta"]["path"] = [0, 2]
    elif mutation == "input_cap_changed":
        for stage in stages:
            chat_input_frame(stage)["summary"]["delta"]["widget"]["maxUploadSizeMb"] = 50
    elif mutation == "input_not_bottom_routed":
        for stage in stages:
            chat_input_frame(stage)["summary"]["delta"]["widget"].pop("isAutoPositionedAtBottom")
    elif mutation == "submit_value_lost":
        rerun_frame(commit)["summary"]["rerun_script"]["widget_states"] = []
    elif mutation == "echo_missing":
        doomed = [frame for frame in commit["new_frames"] if (frame["summary"].get("delta") or {}).get("body") == "echo: hi"]
        commit["new_frames"] = [frame for frame in commit["new_frames"] if frame not in doomed]
    elif mutation == "dom_messages_missing":
        load["dom"]["messages"] = []
    elif mutation == "extra_element":
        load["new_frames"].append(build_frame({"kind": "markdown", "body": "extra", "path": [0, 2]}))
    elif mutation == "missing_png":
        (tmp_path / f"{load['name']}.png").unlink()
    elif mutation == "png_sha":
        load["screenshot"]["sha256"] = "0" * 64
    elif mutation == "wrong_contract":
        observation["contract"] = "journey-chat-v0"
    elif mutation == "missing_stage":
        observation["stages"] = []
    assert not faults, faults
    return observation


def result(tmp_path, **faults):
    return chat_result(observation=observation(tmp_path, **faults))


def test_complete_synthetic_model_passes_every_check(tmp_path):
    outcome = result(tmp_path)
    assert outcome["ok"], outcome["failures"]
    assert outcome["counts"] == {"expected": 10, "executed": 10, "asserted": 10}
    assert tuple(check["check"] for check in outcome["checks"]) == CHAT_REQUIRED


def test_the_rust_leading_main_block_is_the_one_allowed_divergence(tmp_path):
    outcome = result(tmp_path, leading_main_blocks=1)
    assert outcome["ok"], outcome["failures"]


@pytest.mark.parametrize("leading", [2, 3])
def test_more_than_one_leading_main_block_fails(tmp_path, leading):
    outcome = result(tmp_path, leading_main_blocks=leading)
    assert not outcome["ok"], (leading, outcome["counts"])


@pytest.mark.parametrize("mutation", [
    "avatar_not_defaulted", "avatar_type_emoji", "block_not_allow_empty",
    "input_main_path", "input_cap_changed", "input_not_bottom_routed",
    "submit_value_lost", "echo_missing", "dom_messages_missing",
    "extra_element", "missing_png", "png_sha",
    "wrong_contract", "missing_stage",
])
def test_known_mutations_fail(tmp_path, mutation):
    outcome = result(tmp_path, mutation=mutation)
    assert not outcome["ok"], (mutation, outcome["counts"])


def test_degenerate_observations_fail_closed():
    for observation in (None, {}, [], {"journey": "chat-page"}):
        outcome = chat_result(observation=observation)
        assert not outcome["ok"] and outcome["counts"]["expected"] == len(CHAT_REQUIRED)


def test_the_constants_pin_the_measured_semantics():
    assert CHAT_STAGES == ["01-load", "02-enter-commit"]
    load = CHAT_TIMELINE["01-load"]
    blocks = [entry for entry in load if entry["kind"] == "chat_message"]
    assert blocks[0]["chat"] == {"name": "user", "avatar": "user", "avatarType": "ICON"}
    assert blocks[1]["chat"] == {"name": "assistant", "avatar": ":material/robot:", "avatarType": "ICON"}
    widget = CHAT_INPUTS["01-load"]["widget"]
    assert widget == {"placeholder": "Say something", "maxUploadSizeMb": 200, "audioSampleRate": 16000, "isAutoPositionedAtBottom": True}
    assert CHAT_INPUTS["01-load"]["path"] == [3, 0]
    states = next(entry for entry in CHAT_TIMELINE["02-enter-commit"] if entry["kind"] == "rerun")["states"]
    assert states[0]["id"] == "$$ID-None"
    assert states[0]["value"] == {"data": "hi", "file_uploader_state": {}}
    assert all(not dom["exceptions"] for dom in CHAT_DOMS.values())


def test_source_fingerprints_do_not_gate_functional_evidence(tmp_path):
    for source in ({"file": "historical-app.py", "sha256": "changed"}, {"file": "historical-app.py"}, None):
        observed = observation(tmp_path)
        observed["source"] = source
        outcome = chat_result(observation=observed)
        assert outcome["ok"], outcome["failures"]
