"""Unit tests of the strict video contract (journey-video-v1)."""
from __future__ import annotations

import copy
import hashlib
import pathlib
import sys

import pytest

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "browser"))

from video_contract import (  # noqa: E402
    VIDEO_DOM,
    VIDEO_ELEMENTS,
    VIDEO_HTTP,
    VIDEO_REQUIRED,
    VIDEO_SOURCE_FILES,
    VIDEO_STAGES,
    VIDEO_URL,
    VIDEO_SAMPLE_SHA256,
    video_result,
)

PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"not-a-real-image-but-magic-and-hash-are-checked"


def frame(kind, direction="server->client", **extra):
    summary = {"type": kind, **extra}
    return {"direction": direction, "timestamp": 0.0, "summary": summary}


def media_http():
    return [{
        "url": "http://127.0.0.1:8610" + VIDEO_URL,
        "method": "GET",
        "status": VIDEO_HTTP["status"],
        "mime": VIDEO_HTTP["mime"],
        "headers": {
            "content-type": VIDEO_HTTP["content_type"],
            "accept-ranges": VIDEO_HTTP["accept_ranges"],
            "content-range": VIDEO_HTTP["content_range"],
        },
        "body": {"base64": True, "sha256": VIDEO_HTTP["body_sha256"], "length": VIDEO_HTTP["body_length"]},
    }]


def dom():
    import json

    text = json.dumps(copy.deepcopy(VIDEO_DOM), ensure_ascii=False)
    return json.loads(text.replace("<page>", "http://127.0.0.1:8610"))


def observation(tmp_path, **faults):
    frames = [
        frame("rerun_script", "client->server", rerun_script={"widget_states": []}),
        frame("new_session", new_session={"script_run_id": "run-1", "session_id": "session-a"}),
        frame("session_status_changed", session_status_changed={"script_is_running": True, "run_on_save": False}),
        frame("delta", delta={"type": "new_element", "element": "video", "element_full": copy.deepcopy(VIDEO_ELEMENTS[0])}),
        frame("script_finished", script_finished={"status": 0}),
        frame("session_status_changed", session_status_changed={"script_is_running": False, "run_on_save": False}),
    ]
    stages = [{"name": VIDEO_STAGES[0], "new_frames": frames, "http": media_http(), "dom": dom()}]
    observation = {
        "journey": "video-page",
        "contract": "journey-video-v1",
        "scope": "PYTHON SIDE ONLY",
        "url": "http://127.0.0.1:8610/",
        "source": {"file": VIDEO_SOURCE_FILES["python"]},
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
    if mutation == "youtube_type":
        target["new_frames"][3]["summary"]["delta"]["element_full"]["video"]["type"] = "YOUTUBE_IFRAME"
    elif mutation == "wrong_element_width":
        target["new_frames"][3]["summary"]["delta"]["element_full"]["element_width_config"] = {"useStretch": True}
    elif mutation == "wrong_url":
        target["new_frames"][3]["summary"]["delta"]["element_full"]["video"]["url"] = "/media/" + "0" * 32 + ".mp4"
        target["http"][0]["url"] = "http://127.0.0.1:8610/media/" + "0" * 32 + ".mp4"
    elif mutation == "wrong_body_sha":
        target["http"][0]["body"]["sha256"] = "0" * 64
    elif mutation == "wrong_status":
        target["http"][0]["status"] = 200
    elif mutation == "wrong_content_range":
        target["http"][0]["headers"]["content-range"] = "bytes 0-1/3605"
    elif mutation == "wrong_dom_video":
        target["dom"]["videos"][0]["muted"] = True
    elif mutation == "missing_http":
        target["http"] = []
    elif mutation == "duplicate_media_request":
        target["http"].append(copy.deepcopy(target["http"][0]))
    elif mutation == "exception_element":
        target["new_frames"].insert(3, frame("delta", delta={"element": "exception"}))
    elif mutation == "exception_dom":
        target["dom"]["exceptions"] = ["StreamlitAPIException"]
    elif mutation == "wrong_finish":
        for frame_ in target["new_frames"]:
            if frame_["summary"]["type"] == "script_finished":
                frame_["summary"]["script_finished"]["status"] = 2
    elif mutation == "missing_png":
        (tmp_path / f"{target['name']}.png").unlink()
    elif mutation == "png_sha":
        target["screenshot"]["sha256"] = "0" * 64
    elif mutation == "wrong_contract":
        observation["contract"] = "journey-video-v0"
    elif mutation == "missing_stage":
        observation["stages"] = []
    assert not faults, faults
    return observation


def result(tmp_path, **faults):
    return video_result(observation=observation(tmp_path, **faults))


def test_complete_synthetic_model_passes_every_check(tmp_path):
    outcome = result(tmp_path)
    assert outcome["ok"], outcome["failures"]
    assert outcome["counts"] == {"expected": 9, "executed": 9, "asserted": 9}
    assert tuple(check["check"] for check in outcome["checks"]) == VIDEO_REQUIRED


@pytest.mark.parametrize("mutation", [
    "youtube_type", "wrong_element_width", "wrong_url", "wrong_body_sha",
    "wrong_status", "wrong_content_range", "wrong_dom_video", "missing_http",
    "duplicate_media_request",
    "exception_element", "exception_dom", "wrong_finish", "missing_png",
    "png_sha", "wrong_contract", "missing_stage",
])
def test_known_mutations_fail(tmp_path, mutation):
    outcome = result(tmp_path, mutation=mutation)
    assert not outcome["ok"], (mutation, outcome["counts"])


def test_degenerate_observations_fail_closed():
    for observation in (None, {}, [], {"journey": "video-page"}):
        outcome = video_result(observation=observation)
        assert not outcome["ok"] and outcome["counts"]["expected"] == len(VIDEO_REQUIRED)


def test_the_sample_bytes_pin_the_measured_address():
    sample = HERE.parents[1] / "tests/reference/video_sample.mp4"
    assert hashlib.sha256(sample.read_bytes()).hexdigest() == VIDEO_SAMPLE_SHA256
    assert VIDEO_HTTP["body_sha256"] == VIDEO_SAMPLE_SHA256
    assert VIDEO_HTTP["content_range"] == f"bytes 0-{VIDEO_HTTP['body_length'] - 1}/{VIDEO_HTTP['body_length']}"
    assert VIDEO_ELEMENTS[0]["video"]["url"] == VIDEO_URL


def test_the_dom_is_the_measured_player():
    assert len(VIDEO_DOM["videos"]) == 1
    video = VIDEO_DOM["videos"][0]
    assert video["controls"] is True and video["muted"] is False and video["loop"] is False and video["autoplay"] is False
    assert video["testid"] == "stVideo" and VIDEO_DOM["exceptions"] == []


def test_source_fingerprints_do_not_gate_functional_evidence(tmp_path):
    for source in ({"file": "historical-app.py", "sha256": "changed"}, {"file": "historical-app.py"}, None):
        observed = observation(tmp_path)
        observed["source"] = source
        outcome = video_result(observation=observed)
        assert outcome["ok"], outcome["failures"]
