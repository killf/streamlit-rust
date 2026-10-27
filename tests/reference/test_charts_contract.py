"""Unit tests of the strict charts contract (journey-charts-v1)."""
from __future__ import annotations

import base64
import copy
import hashlib
import json
import pathlib
import sys

import pytest

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "browser"))

from charts_contract import (  # noqa: E402
    CHARTS_DATASETS,
    CHARTS_DECK,
    CHARTS_DECK_RAW,
    CHARTS_DOM,
    CHARTS_MARKS,
    CHARTS_REQUIRED,
    CHARTS_SOURCE_FILES,
    CHARTS_SPECS,
    charts_result,
)

PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"not-a-real-image-but-magic-and-hash-are-checked"

URL = "http://127.0.0.1:8612"


def _calc_hash(data: bytes) -> str:
    return hashlib.blake2b(str(data).encode("utf-8"), digest_size=16).hexdigest()


def vega_frame(index: int, mark: str, *, dataset_bytes: bytes | None = None, spec: str | None = None, name: str | None = None,
               dataset: dict | None = None, config: tuple[dict, dict] | None = None) -> dict:
    measured = CHARTS_DATASETS[mark]
    served_name = name if name is not None else measured["name"]
    if dataset_bytes is None:
        dataset_bytes = f"synthetic-{mark}".encode()
        served_name = _calc_hash(dataset_bytes)
    served_spec = spec if spec is not None else CHARTS_SPECS[mark].replace(measured["name"], served_name)
    summary = dataset if dataset is not None else {
        key: copy.deepcopy(measured[key]) for key in ("schema", "columns", "row_count", "rows")
    }
    width, height = config or ({"useStretch": True}, {"useContent": True})
    return {"direction": "server->client", "timestamp": float(index), "summary": {"type": "delta", "delta": {
        "type": "new_element", "path": [0, index], "element": "vega_lite_chart",
        "element_full": {"vegaLiteChart": {"spec": served_spec, "theme": "streamlit"},
                          "widthConfig": width, "heightConfig": height},
        "vega_lite_datasets": [{"name": served_name, "has_name": True,
                                 "arrow": {"base64": base64.b64encode(dataset_bytes).decode(), **summary}}],
    }}}


def deck_frame(*, raw: str | None = None, fields: dict | None = None, config: tuple[dict, dict] | None = None) -> dict:
    width, height = config or ({"useStretch": True}, {"pixelHeight": 500})
    return {"direction": "server->client", "timestamp": 3.0, "summary": {"type": "delta", "delta": {
        "type": "new_element", "path": [0, 3], "element": "deck_gl_json_chart",
        "element_full": {"deckGlJsonChart": {"json": raw if raw is not None else CHARTS_DECK_RAW},
                          "widthConfig": width, "heightConfig": height},
        "deck_gl_json": copy.deepcopy(CHARTS_DECK),
        "deck_gl_fields": fields if fields is not None
        else {"id": "", "tooltip": "", "mapbox_token": "", "selection_mode": [], "form_id": "", "alt": ""},
    }}}


def chart_frames():
    return [vega_frame(index, mark) for index, mark in enumerate(CHARTS_MARKS)] + [deck_frame()]


def dom():
    text = json.dumps(copy.deepcopy(CHARTS_DOM), ensure_ascii=False)
    return json.loads(text.replace("<page>", URL))


def observation(tmp_path, **faults):
    frames = [
        {"direction": "client->server", "timestamp": 0.0, "summary": {"type": "rerun_script", "rerun_script": {"widget_states": []}}},
        {"direction": "server->client", "timestamp": 0.1, "summary": {"type": "new_session", "new_session": {"script_run_id": "run-1", "session_id": "session-a"}}},
        {"direction": "server->client", "timestamp": 0.2, "summary": {"type": "session_status_changed", "session_status_changed": {"script_is_running": True, "run_on_save": False}}},
        *chart_frames(),
        {"direction": "server->client", "timestamp": 4.0, "summary": {"type": "script_finished", "script_finished": {"status": 0}}},
        {"direction": "server->client", "timestamp": 4.1, "summary": {"type": "session_status_changed", "session_status_changed": {"script_is_running": False, "run_on_save": False}}},
    ]
    stages = [{"name": "01-load", "new_frames": frames, "http": [], "dom": dom()}]
    observation = {
        "journey": "charts-page",
        "contract": "journey-charts-v1",
        "scope": "PYTHON SIDE ONLY",
        "url": f"{URL}/",
        "source": {"file": CHARTS_SOURCE_FILES["python"]},
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
    deltas = [frame for frame in target["new_frames"] if (frame["summary"].get("delta") or {}).get("type") == "new_element"]

    def patch_vega(mark: str):
        return deltas[CHARTS_MARKS.index(mark)]["summary"]["delta"]

    if mutation == "spec_tampered":
        patch_vega("line")["element_full"]["vegaLiteChart"]["spec"] = patch_vega("line")["element_full"]["vegaLiteChart"]["spec"].replace('"line"', '"lines"')
    elif mutation == "stale_name_in_spec":
        line = patch_vega("line")
        line["element_full"]["vegaLiteChart"]["spec"] = CHARTS_SPECS["line"]
        line["vega_lite_datasets"][0]["arrow"]["base64"] = base64.b64encode(b"other-bytes").decode()
        line["vega_lite_datasets"][0]["name"] = _calc_hash(b"other-bytes")
    elif mutation == "wrong_name_formula":
        patch_vega("area")["vega_lite_datasets"][0]["name"] = "0" * 32
    elif mutation == "extra_dataset_appended":
        patch_vega("line")["vega_lite_datasets"].append(copy.deepcopy(patch_vega("line")["vega_lite_datasets"][0]))
    elif mutation == "frame_rows_differ":
        rows = patch_vega("area")["vega_lite_datasets"][0]["arrow"]["rows"]
        rows[0]["value -- streamlit-generated"] = 99
    elif mutation == "frame_schema_differs":
        patch_vega("circle")["vega_lite_datasets"][0]["arrow"]["schema"] = "x: int32"
    elif mutation == "deck_zoom_changed":
        deck = deltas[3]["summary"]["delta"]
        deck["element_full"]["deckGlJsonChart"]["json"] = CHARTS_DECK_RAW.replace('"zoom": 10', '"zoom": 11')
        deck["deck_gl_json"]["initialViewState"]["zoom"] = 11
    elif mutation == "deck_color_changed":
        deck = deltas[3]["summary"]["delta"]
        deck["element_full"]["deckGlJsonChart"]["json"] = CHARTS_DECK_RAW.replace("[200, 30, 0, 160]", "[0, 30, 200, 160]")
        deck["deck_gl_json"]["layers"][0]["getFillColor"] = [0, 30, 200, 160]
    elif mutation == "deck_pixel_height":
        deltas[3]["summary"]["delta"]["element_full"]["heightConfig"] = {"pixelHeight": 400}
    elif mutation == "mapbox_token_leak":
        deltas[3]["summary"]["delta"]["deck_gl_fields"]["mapbox_token"] = "pk.leaked"
    elif mutation == "missing_chart":
        target["new_frames"] = [frame for frame in target["new_frames"] if frame is not deltas[2]]
    elif mutation == "wrong_mark_order":
        frames = target["new_frames"]
        first = next(index for index, frame in enumerate(frames) if (frame["summary"].get("delta") or {}).get("element") == "vega_lite_chart")
        frames[first], frames[first + 1] = frames[first + 1], frames[first]
    elif mutation == "exception_element":
        target["new_frames"].insert(3, {"direction": "server->client", "timestamp": 2.9,
                                         "summary": {"type": "delta", "delta": {"type": "new_element", "element": "exception"}}})
    elif mutation == "dom_charts_missing":
        target["dom"]["charts"] = []
    elif mutation == "wrong_finish":
        for frame_ in target["new_frames"]:
            if frame_["summary"]["type"] == "script_finished":
                frame_["summary"]["script_finished"]["status"] = 2
    elif mutation == "missing_png":
        (tmp_path / f"{target['name']}.png").unlink()
    elif mutation == "png_sha":
        target["screenshot"]["sha256"] = "0" * 64
    elif mutation == "wrong_contract":
        observation["contract"] = "journey-charts-v0"
    elif mutation == "missing_stage":
        observation["stages"] = []
    assert not faults, faults
    return observation


def result(tmp_path, **faults):
    return charts_result(observation=observation(tmp_path, **faults))


def test_complete_synthetic_model_passes_every_check(tmp_path):
    outcome = result(tmp_path)
    assert outcome["ok"], outcome["failures"]
    assert outcome["counts"] == {"expected": 11, "executed": 11, "asserted": 11}
    assert tuple(check["check"] for check in outcome["checks"]) == CHARTS_REQUIRED


@pytest.mark.parametrize("mutation", [
    "spec_tampered", "stale_name_in_spec", "wrong_name_formula",
    "extra_dataset_appended", "frame_rows_differ", "frame_schema_differs",
    "deck_zoom_changed", "deck_color_changed", "deck_pixel_height",
    "mapbox_token_leak", "missing_chart", "wrong_mark_order",
    "exception_element", "dom_charts_missing", "wrong_finish", "missing_png",
    "png_sha", "wrong_contract", "missing_stage",
])
def test_known_mutations_fail(tmp_path, mutation):
    outcome = result(tmp_path, mutation=mutation)
    assert not outcome["ok"], (mutation, outcome["counts"])


def test_degenerate_observations_fail_closed():
    for observation in (None, {}, [], {"journey": "charts-page"}):
        outcome = charts_result(observation=observation)
        assert not outcome["ok"] and outcome["counts"]["expected"] == len(CHARTS_REQUIRED)


def test_the_constants_pin_the_measured_semantics():
    assert CHARTS_MARKS == ["line", "area", "circle"]
    line = json.loads(CHARTS_SPECS["line"])
    assert [layer["mark"]["type"] for layer in line["layer"]] == ["line", "point", "point"]
    assert line["layer"][2]["mark"] == {"type": "point", "filled": True, "size": 65}
    assert [param["name"] for param in line["params"]] == ["param_1", "param_2"]
    assert line["params"][0]["select"]["on"] == "mousemove"
    area = json.loads(CHARTS_SPECS["area"])
    assert area["encoding"]["y"]["stack"] is False and area["encoding"]["opacity"]["value"] == 0.7
    assert CHARTS_DATASETS["area"]["row_count"] == 6
    circle = json.loads(CHARTS_SPECS["circle"])
    assert circle["mark"] == {"type": "circle"} and circle["encoding"]["size"] == {"value": 100}
    deck = json.loads(CHARTS_DECK_RAW)
    assert deck["initialViewState"] == {"latitude": 40.85, "longitude": -73.95, "pitch": 0, "zoom": 10}
    assert deck["layers"][0]["getPosition"] == "@@=[lon, lat]"
    assert deck["layers"][0]["getFillColor"] == [200, 30, 0, 160]
    for mark in CHARTS_MARKS:
        spec = json.loads(CHARTS_SPECS[mark])
        assert spec["width"] == 0 and spec["height"] == 0
        assert spec["$schema"].endswith("v5.20.1.json")
        assert CHARTS_DATASETS[mark]["name"] in CHARTS_SPECS[mark]


def test_source_fingerprints_do_not_gate_functional_evidence(tmp_path):
    for source in ({"file": "historical-app.py", "sha256": "changed"}, {"file": "historical-app.py"}, None):
        observed = observation(tmp_path)
        observed["source"] = source
        outcome = charts_result(observation=observed)
        assert outcome["ok"], outcome["failures"]
