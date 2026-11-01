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


PLAYBACK_UI_ROOTS = (
    HERE / "reference-browser/video/playback-ui",
    HERE.parent / "browser/rust-video/playback-ui",
)
PLAYBACK_UI_STAGES = ("loaded", "play-command", "paused", "pause-held", "resumed", "ended", "seek-middle")


def read_playback_ui(root):
    import json

    return json.loads((root / "trace.json").read_text(encoding="utf-8"))


def check_playback_ui(record):
    from datetime import datetime
    from io import BytesIO
    from urllib.parse import urlsplit
    from PIL import Image

    # 1. 核对来源和清理状态；源码指纹不充当功能兼容门。
    assert record["runtime"] in ("python", "rust") and record["reference_version"] == "1.66.1"
    assert record["sdk_distribution"]["streamlit"] == "1.66.1"
    assert record["tab_closed"] and record["server_cleanup"]["stopped"]
    assert record["server_cleanup"]["port_closed_final"]
    assert record["browser"]["name"] == "Chrome" and record["browser"]["viewport_override"] is False
    assert record["source_sha256"]["tests/reference/video_sample.mp4"] == VIDEO_SAMPLE_SHA256
    assert record["source_sha256"]["streamlit/examples/data/video_sample.mp4"] == VIDEO_SAMPLE_SHA256
    assert tuple(stage["name"] for stage in record["stages"]) == PLAYBACK_UI_STAGES
    stages = {stage["name"]: stage for stage in record["stages"]}
    players = {}

    # 2. 逐阶段验证播放器与原图，保留真实时间及常规视口。
    for name, stage in stages.items():
        dom = stage["dom"]
        assert not dom["exceptions"] and len(dom["videos"]) == 1
        player = players[name] = dom["videos"][0]
        assert player["error"] is None and player["readyState"] >= 2
        assert player["duration"] == 1 and (player["videoWidth"], player["videoHeight"]) == (64, 48)
        assert player["controls"] and not any(player[key] for key in ("muted", "loop", "autoplay"))
        source = urlsplit(player["src"])
        assert source.hostname == "127.0.0.1" and source.port == record["server_cleanup"]["port"]
        assert source.path == VIDEO_URL and not source.query and not source.fragment
        assert 0 <= player["currentTime"] <= player["duration"]
        if name in ("loaded", "paused", "ended", "seek-middle"):
            assert "screenshot" in stage
            shot = stage["screenshot"]
            body = (HERE.parents[1] / shot["path"]).read_bytes()
            assert len(body) == shot["bytes"] and hashlib.sha256(body).hexdigest() == shot["sha256"]
            with Image.open(BytesIO(body)) as image:
                assert image.format == "JPEG"
                assert image.size == (dom["viewport"]["width"], dom["viewport"]["height"])
                image.verify()

    # 3. 检查实际播放进展、暂停保持、结束和定位。
    assert players["loaded"]["paused"] and players["loaded"]["currentTime"] == 0 and not players["loaded"]["ended"]
    assert stages["play-command"]["action"] == "focus video and press Space"
    assert not players["play-command"]["paused"] and 0 < players["play-command"]["currentTime"] < 1
    assert players["paused"]["paused"] and 0 < players["paused"]["currentTime"] < 1
    assert players["pause-held"]["paused"] and players["pause-held"]["currentTime"] == players["paused"]["currentTime"]
    assert (datetime.fromisoformat(stages["pause-held"]["at"]) - datetime.fromisoformat(stages["paused"]["at"])).total_seconds() >= 1
    assert not players["resumed"]["paused"] and players["resumed"]["currentTime"] >= players["paused"]["currentTime"]
    assert players["ended"]["paused"] and players["ended"]["ended"] and players["ended"]["currentTime"] == 1
    assert any(start <= 0.001 and end >= 0.999 for start, end in players["ended"]["played"])
    assert players["seek-middle"]["paused"] and not players["seek-middle"]["ended"]
    assert 0.45 <= players["seek-middle"]["currentTime"] <= 0.55
    assert stages["seek-middle"]["coordinate_source"] == stages["ended"]["screenshot"]["path"]
    return players


@pytest.mark.parametrize("root", PLAYBACK_UI_ROOTS, ids=("python", "rust"))
def test_actual_video_play_pause_end_and_seek_evidence(root):
    check_playback_ui(read_playback_ui(root))


def test_native_and_sdk_playback_evidence_share_sample_and_viewport():
    sdk, native = [read_playback_ui(root) for root in PLAYBACK_UI_ROOTS]
    for record in (sdk, native):
        check_playback_ui(record)
    assert sdk["source_commit"] == native["source_commit"]
    assert sdk["source_sha256"] == native["source_sha256"]
    assert sdk["stages"][0]["dom"]["viewport"] == native["stages"][0]["dom"]["viewport"]


@pytest.mark.parametrize("root", PLAYBACK_UI_ROOTS, ids=("python", "rust"))
@pytest.mark.parametrize("fault", ("loading", "not-playing", "zero-time", "pause-drift", "not-ended", "incomplete-played", "seek-noop", "media-error", "wrong-source", "leaked-server", "missing-shot", "wrong-shot-sha"))
def test_playback_ui_gate_rejects_incomplete_or_damaged_evidence(root, fault):
    record = copy.deepcopy(read_playback_ui(root))
    stages = {stage["name"]: stage for stage in record["stages"]}
    player = lambda name: stages[name]["dom"]["videos"][0]
    if fault == "loading": player("loaded")["readyState"] = 1
    elif fault == "not-playing": player("play-command")["paused"] = True
    elif fault == "zero-time": player("play-command")["currentTime"] = 0
    elif fault == "pause-drift": player("pause-held")["currentTime"] += 0.1
    elif fault == "not-ended": player("ended")["ended"] = False
    elif fault == "incomplete-played": player("ended")["played"] = [[0, 0.2]]
    elif fault == "seek-noop": player("seek-middle")["currentTime"] = 1
    elif fault == "media-error": player("loaded")["error"] = {"code": 3, "message": "decode failed"}
    elif fault == "wrong-source": player("loaded")["src"] = player("loaded")["src"].replace(VIDEO_URL, "/media/" + "0" * 32 + ".mp4")
    elif fault == "leaked-server": record["server_cleanup"]["port_closed_final"] = False
    elif fault == "missing-shot": del stages["paused"]["screenshot"]
    elif fault == "wrong-shot-sha": stages["loaded"]["screenshot"]["sha256"] = "0" * 64
    with pytest.raises(AssertionError):
        check_playback_ui(record)


SUBTITLE_UI_ROOTS = (HERE / "reference-browser/video/subtitle-ui", HERE.parent / "browser/rust-video/subtitle-ui")
SUBTITLE_UI_STAGES = ("english-default", "track-menu", "chinese-selected", "off-menu", "captions-off", "default-restored")


def check_subtitle_ui(record):
    import base64
    import re
    from io import BytesIO
    from urllib.parse import urlsplit
    from PIL import Image

    # 1. 绑定原始画面、DOM 轨道和实际清理；不把不可见的 mode/cues 当验证值。
    assert record["reference_version"] == "1.66.1" and record["sdk_distribution"]["streamlit"] == "1.66.1"
    assert record["tab_closed"] and record["server_cleanup"]["stopped"] and record["server_cleanup"]["port_closed_final"]
    assert tuple(s["name"] for s in record["stages"]) == SUBTITLE_UI_STAGES
    stages = {s["name"]: s for s in record["stages"]}
    region_hashes = {}
    tracks = stages["english-default"]["dom"]["videos"][0]["tracks"]
    assert [t["label"] for t in tracks] == ["English", "中文"]
    assert [t["default"] for t in tracks] == [True, False]
    assert all(t["kind"] == "captions" for t in tracks)

    for name, stage in stages.items():
        dom = stage["dom"]
        assert not dom["exceptions"] and len(dom["videos"]) == 1
        video = dom["videos"][0]
        assert video["error"] is None and video["readyState"] >= 2 and video["paused"]
        assert video["currentTime"] == 0 and video["duration"] == 1
        assert (video["videoWidth"], video["videoHeight"]) == (64, 48)
        assert urlsplit(video["src"]).path == VIDEO_URL
        assert video["tracks"] == ([] if name == "default-restored" else tracks)
        assert video["muted"] == (name != "default-restored")
        assert (urlsplit(dom["url"]).query == "subtitles=1") == (name != "default-restored")
        assert "screenshot" in stage
        shot = stage["screenshot"]
        expected_base = "tests/reference/reference-browser/video/subtitle-ui" if record["runtime"] == "python" else "tests/browser/rust-video/subtitle-ui"
        assert shot["path"] == expected_base + "/" + name + ".jpg"
        body = (HERE.parents[1] / shot["path"]).read_bytes()
        assert len(body) == shot["bytes"] and hashlib.sha256(body).hexdigest() == shot["sha256"]
        with Image.open(BytesIO(body)) as image:
            assert image.format == "JPEG" and image.mode == "RGB"
            assert image.size == (dom["viewport"]["width"], dom["viewport"]["height"])
            pixels = image.tobytes()
            width, height = image.size
            left, top, right, bottom = stage["caption_region"]["bounds"]
            assert (left, top, right, bottom) == (650, 510, 805, 556)
            assert right <= width and bottom <= height
            region = b"".join(pixels[(y * width + left) * 3:(y * width + right) * 3] for y in range(top, bottom))
        region_hashes[name] = hashlib.sha256(region).hexdigest()
        assert region_hashes[name] == stage["caption_region"]["rgb_sha256"]

    # 2. 原生菜单值和三种实际像素状态互相约束；像素比较不冒充 OCR。
    assert [int(v) for v in re.findall(r"(?m)^\s+\d+ ([01])$", stages["track-menu"]["ax"])] == [0, 1, 0]
    assert [int(v) for v in re.findall(r"(?m)^\s+\d+ ([01])$", stages["off-menu"]["ax"])] == [0, 0, 1]
    assert stages["chinese-selected"]["coordinate_source"] == stages["track-menu"]["screenshot"]["path"]
    assert stages["captions-off"]["coordinate_source"] == stages["off-menu"]["screenshot"]["path"]
    assert region_hashes["english-default"] == region_hashes["track-menu"]
    assert region_hashes["chinese-selected"] == region_hashes["off-menu"]
    assert region_hashes["captions-off"] == region_hashes["default-restored"]
    assert len({region_hashes[n] for n in ("english-default", "chinese-selected", "captions-off")}) == 3

    # 3. 按真实 DOM 地址核对下载原文、内容摘要和 SDK AppTest 公开地址。
    expected_bodies = [b"WEBVTT\n\n1\n00:00:00.000 --> 00:00:01.000\nHello SRT", "WEBVTT\n\n00:00:00.000 --> 00:00:01.000\n中文字幕".encode()]
    assert len(record["track_http"]) == 2
    for track, response, expected, sdk in zip(tracks, record["track_http"], expected_bodies, record["sdk_apptest"]["subtitles"]["subtitles"]):
        body = base64.b64decode(response["body_base64"], validate=True)
        assert body == bytes(response["body_bytes"]) == expected
        assert hashlib.sha256(body).hexdigest() == response["body_sha256"]
        filename = hashlib.blake2b(track["label"].encode(), digest_size=16).hexdigest() + ".vtt"
        path = "/media/" + hashlib.blake2b(str(len(body)).encode() + b":" + body + b"text/vtt" + filename.encode(), digest_size=16).hexdigest() + ".vtt"
        assert response["url"] == track["src"] and response["label"] == track["label"] == sdk["label"]
        assert urlsplit(response["url"]).path == path and sdk["url"] == "/mock" + path
        assert response["status"] == 200 and response["headers"]["content-type"] == "text/vtt; charset=utf-8"
        assert response["headers"]["content-length"] == str(len(body)) and "content-disposition" not in response["headers"]
    return region_hashes


@pytest.mark.parametrize("root", SUBTITLE_UI_ROOTS, ids=("python", "rust"))
def test_real_subtitle_display_switch_off_and_default_restore(root):
    check_subtitle_ui(read_playback_ui(root))


def test_sdk_and_native_caption_regions_are_identical_without_editing_images():
    sdk, native = [read_playback_ui(root) for root in SUBTITLE_UI_ROOTS]
    assert check_subtitle_ui(sdk) == check_subtitle_ui(native)
    assert sdk["source_sha256"] == native["source_sha256"]


@pytest.mark.parametrize("mode", ("default", "subtitles"))
def test_video_fixture_query_variant_preserves_default(mode):
    from google.protobuf.json_format import MessageToDict
    from streamlit.testing.v1 import AppTest

    app = AppTest.from_file(str(HERE / "video_app.py"))
    if mode == "subtitles":
        app.query_params["subtitles"] = "1"
    app.run()
    reference = read_playback_ui(SUBTITLE_UI_ROOTS[0])["sdk_apptest"][mode]
    assert not app.exception and len(app.get("video")) == 1
    assert MessageToDict(app.get("video")[0].proto, preserving_proto_field_name=True) == reference


@pytest.mark.parametrize("root", SUBTITLE_UI_ROOTS, ids=("python", "rust"))
@pytest.mark.parametrize("fault", ("missing-track", "wrong-default", "menu-selection", "source", "body", "status", "mime", "default-leak", "region-hash", "missing-shot", "cleanup"))
def test_subtitle_ui_gate_rejects_damaged_evidence(root, fault):
    record = copy.deepcopy(read_playback_ui(root))
    first = record["stages"][0]
    if fault == "missing-track": first["dom"]["videos"][0]["tracks"].pop()
    elif fault == "wrong-default": first["dom"]["videos"][0]["tracks"][0]["default"] = False
    elif fault == "menu-selection": record["stages"][1]["ax"] = record["stages"][3]["ax"]
    elif fault == "source": first["dom"]["videos"][0]["tracks"][0]["src"] += "wrong"
    elif fault == "body": record["track_http"][0]["body_bytes"][0] ^= 1
    elif fault == "status": record["track_http"][0]["status"] = 404
    elif fault == "mime": record["track_http"][0]["headers"]["content-type"] = "text/plain"
    elif fault == "default-leak": record["stages"][-1]["dom"]["videos"][0]["tracks"] = first["dom"]["videos"][0]["tracks"]
    elif fault == "region-hash": first["caption_region"]["rgb_sha256"] = "0" * 64
    elif fault == "missing-shot": del first["screenshot"]
    elif fault == "cleanup": record["server_cleanup"]["port_closed_final"] = False
    with pytest.raises(AssertionError):
        check_subtitle_ui(record)


TIMED_UI_ROOTS = (HERE / "reference-browser/video/timed-ui", HERE.parent / "browser/rust-video/timed-ui")
TIMED_SEEKS = {"first-cue": (0.15, 0.25), "between-cues": (0.45, 0.55), "second-cue": (0.7, 0.8), "after-cues": (0.93, 0.99)}


def timed_loop_stages(record):
    names = ("fresh-play-start", "fresh-loop-observed", "fresh-loop-paused", "fresh-loop-held") if record["runtime"] == "python" else ("play-start", "loop-observed", "loop-paused", "loop-held")
    stages = {s["name"]: s for s in record["stages"]}
    return [stages[n] for n in names]


def check_timed_ui(record):
    import base64
    from datetime import datetime
    from io import BytesIO
    from urllib.parse import urlsplit
    from PIL import Image

    # 1. 核对实际定位和所有原图；视口变化不强改为同一高度。
    assert record["reference_version"] == "1.66.1" and record["sdk_distribution"]["streamlit"] == "1.66.1"
    assert record["tab_closed"] and record["server_cleanup"]["stopped"] and record["server_cleanup"]["port_closed_final"]
    assert record["browser"]["viewport_override"] is False
    stages = {s["name"]: s for s in record["stages"]}
    assert stages["loaded"]["dom"]["videos"][0]["currentTime"] == 0
    regions = {}
    for stage in record["stages"]:
        dom = stage["dom"]
        assert not dom["exceptions"] and len(dom["videos"]) == 1
        video = dom["videos"][0]
        assert video["error"] is None and video["readyState"] >= 2 and video["duration"] == 1
        assert (video["videoWidth"], video["videoHeight"]) == (64, 48)
        assert urlsplit(video["src"]).path == VIDEO_URL
        if stage["name"] in TIMED_SEEKS:
            low, high = TIMED_SEEKS[stage["name"]]
            assert video["paused"] and low <= video["currentTime"] <= high
        if "screenshot" not in stage:
            continue
        shot = stage["screenshot"]
        body = (HERE.parents[1] / shot["path"]).read_bytes()
        assert hashlib.sha256(body).hexdigest() == shot["sha256"] and len(body) == shot["bytes"]
        with Image.open(BytesIO(body)) as image:
            assert image.format == "JPEG" and image.mode == "RGB"
            assert image.size == (dom["viewport"]["width"], dom["viewport"]["height"])
            if "caption_region" in stage:
                pixels = image.tobytes()
                width, height = image.size
                left, top, right, bottom = stage["caption_region"]["bounds"]
                assert (left, top, right, bottom) == (650, 510, 805, 556)
                region = b"".join(pixels[(y * width + left) * 3:(y * width + right) * 3] for y in range(top, bottom))
                regions[stage["name"]] = hashlib.sha256(region).hexdigest()
                assert regions[stage["name"]] == stage["caption_region"]["rgb_sha256"]
    assert all("screenshot" in stages[n] and n in regions for n in TIMED_SEEKS)
    assert len({regions[n] for n in ("first-cue", "between-cues", "second-cue")}) == 3

    # 2. 跨片长后仍播放、已覆盖全片，随后暂停保持且显示对应 cue。
    start, observed, paused, held = timed_loop_stages(record)
    elapsed = (datetime.fromisoformat(observed["at"]) - datetime.fromisoformat(start["at"])).total_seconds()
    assert elapsed >= 3
    for stage in (start, observed):
        video = stage["dom"]["videos"][0]
        assert not video["paused"] and not video["ended"] and 0 <= video["currentTime"] < 1
    for stage in (observed, held):
        assert any(a <= 0.001 and b >= 0.999 for a, b in stage["dom"]["videos"][0]["played"])
    position = paused["dom"]["videos"][0]["currentTime"]
    assert paused["dom"]["videos"][0]["paused"] and held["dom"]["videos"][0]["paused"]
    assert held["dom"]["videos"][0]["currentTime"] == position
    assert (datetime.fromisoformat(held["at"]) - datetime.fromisoformat(paused["at"])).total_seconds() >= 1
    expected_cue = "first-cue" if position < 0.4 else "second-cue" if 0.6 <= position < 0.9 else "between-cues"
    assert regions[held["name"]] == regions[expected_cue]

    # 3. 完整 VTT 原文和 SDK 地址绑定，不能用同名轨道替代定时内容。
    assert len(record["track_http"]) == 2
    tracks = stages["loaded"]["dom"]["videos"][0]["tracks"]
    assert [t["label"] for t in tracks] == ["English", "中文"] and [t["default"] for t in tracks] == [True, False]
    expected = base64.b64decode(record["sdk_apptest"]["timed_vtt_base64"], validate=True)
    assert expected == b"WEBVTT\n\n1\n00:00:00.000 --> 00:00:00.400\nFirst cue\n\n2\n00:00:00.600 --> 00:00:00.900\nSecond cue"
    bodies = [expected, "WEBVTT\n\n00:00:00.000 --> 00:00:01.000\n中文字幕".encode()]
    for track, response, body, sdk in zip(tracks, record["track_http"], bodies, record["sdk_apptest"]["timed"]["subtitles"]):
        assert bytes(response["body_bytes"]) == base64.b64decode(response["body_base64"], validate=True) == body
        assert hashlib.sha256(body).hexdigest() == response["body_sha256"]
        filename = hashlib.blake2b(track["label"].encode(), digest_size=16).hexdigest() + ".vtt"
        path = "/media/" + hashlib.blake2b(str(len(body)).encode() + b":" + body + b"text/vtt" + filename.encode(), digest_size=16).hexdigest() + ".vtt"
        assert response["url"] == track["src"] and urlsplit(response["url"]).path == path and sdk["url"] == "/mock" + path
        assert response["status"] == 200 and response["headers"]["content-type"] == "text/vtt; charset=utf-8"
        assert response["headers"]["content-length"] == str(len(body))
    return {name: regions[name] for name in TIMED_SEEKS}


@pytest.mark.parametrize("root", TIMED_UI_ROOTS, ids=("python", "rust"))
def test_real_timed_cues_gaps_and_looped_playback(root):
    check_timed_ui(read_playback_ui(root))


def test_native_and_sdk_timed_caption_pixels_match_with_actual_viewports_retained():
    sdk, native = [read_playback_ui(root) for root in TIMED_UI_ROOTS]
    assert check_timed_ui(sdk) == check_timed_ui(native)
    assert sdk["source_sha256"] == native["source_sha256"]


def test_timed_video_fixture_replays_pinned_sdk():
    from google.protobuf.json_format import MessageToDict
    from streamlit.testing.v1 import AppTest

    app = AppTest.from_file(str(HERE / "video_app.py"))
    app.query_params["subtitles"] = "timed"
    app.run()
    assert not app.exception and len(app.get("video")) == 1
    assert MessageToDict(app.get("video")[0].proto, preserving_proto_field_name=True) == read_playback_ui(TIMED_UI_ROOTS[0])["sdk_apptest"]["timed"]


def test_sdk_transients_and_lost_tab_are_preserved_instead_of_rewritten():
    sdk = read_playback_ui(TIMED_UI_ROOTS[0])
    stages = {s["name"]: s for s in sdk["stages"]}
    assert sdk["original_tab_missing"] and sdk["recovery_tab_closed"] and sdk["recovery_tab_id"] != sdk["tab_id"]
    assert stages["play-start"]["dom"]["videos"][0]["ended"]
    assert stages["play-start"]["dom"]["videos"][0]["paused"]
    assert "image_alignment" in stages["fresh-loop-paused"] and "caption_region" not in stages["fresh-loop-paused"]
    assert stages["tail-play-observed"]["dom"]["viewport"]["height"] != stages["loaded"]["dom"]["viewport"]["height"]


@pytest.mark.parametrize("root", TIMED_UI_ROOTS, ids=("python", "rust"))
@pytest.mark.parametrize("fault", ("first-time", "gap-time", "second-time", "tail-time", "region-hash", "loop-stopped", "loop-ended", "short-observation", "played-incomplete", "pause-drift", "vtt-body", "cleanup"))
def test_timed_ui_gate_rejects_incomplete_or_damaged_evidence(root, fault):
    record = copy.deepcopy(read_playback_ui(root))
    stages = {s["name"]: s for s in record["stages"]}
    player = lambda name: stages[name]["dom"]["videos"][0]
    start, observed, paused, held = timed_loop_stages(record)
    if fault == "first-time": player("first-cue")["currentTime"] = 0.5
    elif fault == "gap-time": player("between-cues")["currentTime"] = 0.2
    elif fault == "second-time": player("second-cue")["currentTime"] = 0.5
    elif fault == "tail-time": player("after-cues")["currentTime"] = 0.75
    elif fault == "region-hash": stages["first-cue"]["caption_region"]["rgb_sha256"] = "0" * 64
    elif fault == "loop-stopped": observed["dom"]["videos"][0]["paused"] = True
    elif fault == "loop-ended": observed["dom"]["videos"][0]["ended"] = True
    elif fault == "short-observation": observed["at"] = start["at"]
    elif fault == "played-incomplete": observed["dom"]["videos"][0]["played"] = [[0, 0.3]]
    elif fault == "pause-drift": held["dom"]["videos"][0]["currentTime"] += 0.1
    elif fault == "vtt-body": record["track_http"][0]["body_bytes"][0] ^= 1
    elif fault == "cleanup": record["server_cleanup"]["port_closed_final"] = False
    with pytest.raises(AssertionError):
        check_timed_ui(record)
