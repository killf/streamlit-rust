"""Unit tests of the strict media-route contract (journey-media-v1)."""
from __future__ import annotations

import copy
import hashlib
import pathlib
import sys

import pytest

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "browser"))

from media_contract import (  # noqa: E402
    MEDIA_DOM,
    MEDIA_ELEMENTS,
    MEDIA_HTTP,
    MEDIA_PNG_PIXELS,
    MEDIA_PNG_SIZE,
    MEDIA_REQUIRED,
    MEDIA_SOURCE_FILES,
    MEDIA_STAGES,
    MEDIA_WAV_URL,
    media_result,
)


def png_bytes():
    """A real PNG encoding the measured gradient, decodable by PIL."""
    import io

    from PIL import Image

    image = Image.new("RGBA", tuple(MEDIA_PNG_SIZE))
    for row in range(MEDIA_PNG_SIZE[1]):
        for column in range(MEDIA_PNG_SIZE[0]):
            image.putpixel((column, row), tuple(MEDIA_PNG_PIXELS[row][column]))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


PNG_BYTES = png_bytes()


def frame(kind, direction="server->client", **extra):
    summary = {"type": kind, **extra}
    return {"direction": direction, "timestamp": 0.0, "summary": summary}


def element_frames():
    """The five first-render element deltas, media ids back to real shape."""
    import json
    import re

    frames = []
    for element in MEDIA_ELEMENTS:
        text = json.dumps(element, ensure_ascii=False)
        text = text.replace("<page>", "http://127.0.0.1:8609")
        text = re.sub(r"/media/<id>\.([a-z0-9]+)", r"/media/345574f4dfdd34edf3ba28c9709733d2.\1", text)
        frames.append(frame("delta", delta={"type": "new_element", "element": "media", "element_full": json.loads(text)}))
    return frames


def media_http():
    """The measured /media records with real ids and bodies."""
    records = []
    for entry in MEDIA_HTTP:
        record = {
            "url": "http://127.0.0.1:8609" + entry["path"].replace("<id>", "345574f4dfdd34edf3ba28c9709733d2"),
            "method": "GET",
            "status": entry["status"],
            "mime": entry["mime"],
            "headers": {
                "content-type": entry["content_type"],
                "accept-ranges": entry["accept_ranges"],
                **({"content-range": entry["content_range"]} if entry["content_range"] else {}),
            },
        }
        if "body_sha256" in entry:
            record["body"] = {"base64": True, "sha256": entry["body_sha256"], "length": entry["body_length"]}
        else:
            import base64

            record["body"] = {"base64": True, "sha256": "0" * 64, "length": len(PNG_BYTES), "data_b64": base64.b64encode(PNG_BYTES).decode("ascii")}
        records.append(record)
    return records


def dom():
    import json
    import re

    text = json.dumps(copy.deepcopy(MEDIA_DOM), ensure_ascii=False)
    text = text.replace("<page>", "http://127.0.0.1:8609")
    text = re.sub(r"/media/<id>\.([a-z0-9]+)", r"/media/345574f4dfdd34edf3ba28c9709733d2.\1", text)
    return json.loads(text)


def observation(tmp_path, **faults):
    frames = element_frames()
    frames = [
        frame("rerun_script", "client->server", rerun_script={"widget_states": []}),
        frame("new_session", new_session={"script_run_id": "run-1", "session_id": "session-a"}),
        frame("session_status_changed", session_status_changed={"script_is_running": True, "run_on_save": False}),
        *frames,
        frame("script_finished", script_finished={"status": 0}),
        frame("session_status_changed", session_status_changed={"script_is_running": False, "run_on_save": False}),
    ]
    stages = [{"name": MEDIA_STAGES[0], "new_frames": frames, "http": media_http(), "dom": dom()}]
    observation = {
        "journey": "media-page",
        "contract": "journey-media-v1",
        "scope": "PYTHON SIDE ONLY",
        "url": "http://127.0.0.1:8609/",
        "source": {"file": MEDIA_SOURCE_FILES["python"]},
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
    if mutation == "wrong_caption":
        target["new_frames"][3]["summary"]["delta"]["element_full"]["imgs"]["imgs"][0]["caption"] = "other"
    elif mutation == "wrong_metric_direction":
        for delta in target["new_frames"]:
            metric = (delta["summary"].get("delta") or {}).get("element_full", {}).get("metric")
            if metric and metric["label"] == "Temperature":
                metric["direction"] = "DOWN"
    elif mutation == "wrong_progress_value":
        for delta in target["new_frames"]:
            if "progress" in ((delta["summary"].get("delta") or {}).get("element_full") or {}):
                delta["summary"]["delta"]["element_full"]["progress"]["value"] = 50
    elif mutation == "wrong_wav_id":
        for record in target["http"]:
            if record["url"].endswith(".wav"):
                record["url"] = record["url"].replace(MEDIA_WAV_URL.lstrip("/media/").split(".")[0], "0" * 32)
    elif mutation == "wrong_status":
        for record in target["http"]:
            if record["url"].endswith(".wav"):
                record["status"] = 200
    elif mutation == "wrong_content_range":
        for record in target["http"]:
            if record["url"].endswith(".wav"):
                record["headers"]["content-range"] = "bytes 0-1/22094"
    elif mutation == "wrong_body_sha":
        for record in target["http"]:
            if record["url"].endswith(".wav"):
                record["body"]["sha256"] = "0" * 64
    elif mutation == "undecodable_png":
        for record in target["http"]:
            if record["url"].endswith(".png"):
                import base64

                broken = bytearray(PNG_BYTES)
                broken[40] ^= 0xFF
                record["body"]["data_b64"] = base64.b64encode(bytes(broken)).decode("ascii")
    elif mutation == "wrong_png_pixels":
        for record in target["http"]:
            if record["url"].endswith(".png"):
                import base64
                import io

                from PIL import Image

                image = Image.open(io.BytesIO(PNG_BYTES)).convert("RGBA")
                image.putpixel((0, 0), (1, 2, 3, 255))
                buffer = io.BytesIO()
                image.save(buffer, format="PNG")
                record["body"]["data_b64"] = base64.b64encode(buffer.getvalue()).decode("ascii")
    elif mutation == "wrong_dom_metric":
        target["dom"]["metrics"][0]["value"] = "99 °F"
    elif mutation == "wrong_dom_progress":
        target["dom"]["progress"][1]["value"] = "50"
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
        observation["contract"] = "journey-media-v0"
    elif mutation == "missing_http":
        target["http"] = []
    assert not faults, faults
    return observation


def result(tmp_path, **faults):
    return media_result(observation=observation(tmp_path, **faults))


def test_complete_synthetic_model_passes_every_check(tmp_path):
    outcome = result(tmp_path)
    assert outcome["ok"], outcome["failures"]
    assert outcome["counts"] == {"expected": 10, "executed": 10, "asserted": 10}
    assert tuple(check["check"] for check in outcome["checks"]) == MEDIA_REQUIRED


@pytest.mark.parametrize("mutation", [
    "wrong_caption", "wrong_metric_direction", "wrong_progress_value",
    "wrong_wav_id", "wrong_status", "wrong_content_range", "wrong_body_sha",
    "undecodable_png", "wrong_png_pixels",
    "wrong_dom_metric", "wrong_dom_progress", "exception_element",
    "exception_dom", "wrong_finish", "missing_png", "png_sha",
    "wrong_contract", "missing_http",
])
def test_known_mutations_fail(tmp_path, mutation):
    outcome = result(tmp_path, mutation=mutation)
    assert not outcome["ok"], (mutation, outcome["counts"])


def test_degenerate_observations_fail_closed():
    for observation in (None, {}, [], {"journey": "media-page"}):
        outcome = media_result(observation=observation)
        assert not outcome["ok"] and outcome["counts"]["expected"] == len(MEDIA_REQUIRED)


def test_the_wav_address_is_the_measured_one():
    assert MEDIA_WAV_URL == "/media/431dec53348c010fe7c4e0be3ac78ede.wav"
    wav = [entry for entry in MEDIA_HTTP if entry["path"].endswith(".wav")]
    assert len(wav) == 1 and wav[0]["body_length"] == 22094 and wav[0]["status"] == 206


def test_the_png_shape_is_per_side_only():
    png = [entry for entry in MEDIA_HTTP if not entry["path"].endswith(".wav")]
    assert len(png) == 1 and png[0]["body_png"] is True
    assert "<id>" in png[0]["path"]


def test_the_png_pixels_pin_the_measured_gradient():
    assert MEDIA_PNG_SIZE == [8, 8]
    assert len(MEDIA_PNG_PIXELS) == 8 and all(len(row) == 8 for row in MEDIA_PNG_PIXELS)
    # The fixture's flat channel j carries (4*j) % 256 and the alpha plane is
    # forced to 255; pixel p = 8r+c takes channels 4p..4p+2.
    for row in range(8):
        for column in range(8):
            pixel = 8 * row + column
            assert MEDIA_PNG_PIXELS[row][column] == [
                (4 * (4 * pixel)) % 256,
                (4 * (4 * pixel + 1)) % 256,
                (4 * (4 * pixel + 2)) % 256,
                255,
            ], (row, column)


def test_elements_dom_and_http_cover_the_measured_page():
    assert len(MEDIA_ELEMENTS) == 5
    assert [key for key in MEDIA_ELEMENTS[0]] == ["imgs", "widthConfig"]
    assert len(MEDIA_DOM["metrics"]) == 2 and MEDIA_DOM["progress"][1]["value"] == "75"
    assert MEDIA_DOM["exceptions"] == []


def test_source_fingerprints_do_not_gate_functional_evidence(tmp_path):
    for source in ({"file": "historical-app.py", "sha256": "changed"}, {"file": "historical-app.py"}, None):
        observed = observation(tmp_path)
        observed["source"] = source
        outcome = media_result(observation=observed)
        assert outcome["ok"], outcome["failures"]
