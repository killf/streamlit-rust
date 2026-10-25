"""The strict charts contract: journey-charts-v1.

This criterion judges the observation the committed collector
(charts_capture.py) writes, against the Python 1.66.1 wire measured on
2026-10-25 with the official frontend and recorded in .codex/compatibility.md
(Charts). The collector states no verdict; this module owns it:

* the page carries exactly three vega charts in order — line, area, circle
  (scatter) — plus one deck.gl map;
* each vega spec string equals the measured wire modulo the dataset name,
  and the dataset name is the reference formula calc_hash(str(arrow_bytes))
  over the bytes actually served in the same delta (the Rust IPC writer
  lays out flatbuffers differently from pyarrow, so the bytes themselves —
  and therefore the name derived from them — legitimately differ; the
  schema, columns, row count, rows and pandas metadata do not);
* the map's deck.gl json string is byte-identical to the measured wire;
* the DOM resolves three rendered charts and the deck canvases with no
  exception, and the run finishes FINISHED_SUCCESSFULLY.
"""

from __future__ import annotations

import base64
import hashlib
import json
import pathlib

CHARTS_CASE = "charts-page"
CHARTS_CONTRACT = "journey-charts-v1"

CHARTS_STAGES = ["01-load"]

CHARTS_MARKS = ["line", "area", "circle"]

# The measured spec strings; a served spec must equal its constant after the
# dataset names are substituted.
CHARTS_SPECS = {'line': '{"layer": [{"mark": {"type": "line"}, "encoding": {"tooltip": [{"field": "index -- streamlit-generated", "title": "index", "type": "quantitative"}, {"field": "value", "type": "quantitative"}], "x": {"axis": {"grid": false, "tickMinStep": 1}, "field": "index -- streamlit-generated", "scale": {}, "title": "", "type": "quantitative"}, "y": {"axis": {"grid": true, "tickMinStep": 1}, "field": "value", "scale": {}, "title": "", "type": "quantitative"}}, "name": "view_1"}, {"mark": {"type": "point", "opacity": 0}, "encoding": {"tooltip": [{"field": "index -- streamlit-generated", "title": "index", "type": "quantitative"}, {"field": "value", "type": "quantitative"}], "x": {"axis": {"grid": false, "tickMinStep": 1}, "field": "index -- streamlit-generated", "scale": {}, "title": "", "type": "quantitative"}, "y": {"axis": {"grid": true, "tickMinStep": 1}, "field": "value", "scale": {}, "title": "", "type": "quantitative"}}, "name": "view_2"}, {"mark": {"type": "point", "filled": true, "size": 65}, "encoding": {"tooltip": [{"field": "index -- streamlit-generated", "title": "index", "type": "quantitative"}, {"field": "value", "type": "quantitative"}], "x": {"axis": {"grid": false, "tickMinStep": 1}, "field": "index -- streamlit-generated", "scale": {}, "title": "", "type": "quantitative"}, "y": {"axis": {"grid": true, "tickMinStep": 1}, "field": "value", "scale": {}, "title": "", "type": "quantitative"}}, "transform": [{"filter": {"param": "param_1", "empty": false}}]}], "config": {"legend": {"symbolType": "stroke"}}, "data": {"name": "078ef25999e136180ee783f5424378b2"}, "height": 0, "params": [{"name": "param_1", "select": {"type": "point", "clear": "mouseleave", "fields": ["index -- streamlit-generated"], "nearest": true, "on": "mousemove"}, "views": ["view_2"]}, {"name": "param_2", "select": {"type": "interval", "encodings": ["x", "y"]}, "bind": "scales", "views": ["view_1"]}], "width": 0, "$schema": "https://vega.github.io/schema/vega-lite/v5.20.1.json", "autosize": {"type": "fit", "contains": "padding"}}', 'area': '{"data": {"name": "3e315e07f62cbdd23e962c76b991da6d"}, "mark": {"type": "area"}, "encoding": {"color": {"field": "color -- streamlit-generated", "legend": {"titlePadding": 5, "offset": 5, "orient": "bottom"}, "title": " ", "type": "nominal"}, "opacity": {"value": 0.7}, "tooltip": [{"field": "index -- streamlit-generated", "title": "index", "type": "quantitative"}, {"field": "value -- streamlit-generated", "title": "value", "type": "quantitative"}, {"field": "color -- streamlit-generated", "title": "color", "type": "nominal"}], "x": {"axis": {"grid": false, "tickMinStep": 1}, "field": "index -- streamlit-generated", "scale": {}, "title": "", "type": "quantitative"}, "y": {"axis": {"grid": true, "tickMinStep": 1}, "field": "value -- streamlit-generated", "scale": {}, "stack": false, "title": "", "type": "quantitative"}}, "height": 0, "params": [{"name": "param_1", "select": {"type": "interval", "encodings": ["x", "y"]}, "bind": "scales"}], "width": 0, "$schema": "https://vega.github.io/schema/vega-lite/v5.20.1.json", "autosize": {"type": "fit", "contains": "padding"}}', 'circle': '{"data": {"name": "bbb5436c72daf7f025b50a08bfaa6151"}, "mark": {"type": "circle"}, "encoding": {"size": {"value": 100}, "tooltip": [{"field": "x", "type": "quantitative"}, {"field": "y", "type": "quantitative"}], "x": {"axis": {"grid": false, "tickMinStep": 1}, "field": "x", "scale": {}, "title": "x", "type": "quantitative"}, "y": {"axis": {"grid": true, "tickMinStep": 1}, "field": "y", "scale": {}, "title": "y", "type": "quantitative"}}, "height": 0, "params": [{"name": "param_1", "select": {"type": "interval", "encodings": ["x", "y"]}, "bind": "scales"}], "width": 0, "$schema": "https://vega.github.io/schema/vega-lite/v5.20.1.json", "autosize": {"type": "fit", "contains": "padding"}}'}

# The measured dataset frames, judged semantically.
CHARTS_DATASETS = {'line': {'name': '078ef25999e136180ee783f5424378b2', 'schema': 'index -- streamlit-generated: int64\nvalue: int64\n-- schema metadata --\npandas: \'{"index_columns": [{"kind": "range", "name": null, "start": 0, "\' + 534', 'columns': ['index -- streamlit-generated', 'value'], 'row_count': 3, 'rows': [{'index -- streamlit-generated': 0, 'value': 2}, {'index -- streamlit-generated': 1, 'value': 1}, {'index -- streamlit-generated': 2, 'value': 3}]}, 'area': {'name': '3e315e07f62cbdd23e962c76b991da6d', 'schema': 'index -- streamlit-generated: int64\ncolor -- streamlit-generated: large_string\nvalue -- streamlit-generated: int64\n-- schema metadata --\npandas: \'{"index_columns": [{"kind": "range", "name": null, "start": 0, "\' + 732', 'columns': ['index -- streamlit-generated', 'color -- streamlit-generated', 'value -- streamlit-generated'], 'row_count': 6, 'rows': [{'index -- streamlit-generated': 0, 'color -- streamlit-generated': 'alpha', 'value -- streamlit-generated': 1}, {'index -- streamlit-generated': 1, 'color -- streamlit-generated': 'alpha', 'value -- streamlit-generated': 2}, {'index -- streamlit-generated': 2, 'color -- streamlit-generated': 'alpha', 'value -- streamlit-generated': 3}, {'index -- streamlit-generated': 0, 'color -- streamlit-generated': 'beta', 'value -- streamlit-generated': 3}, {'index -- streamlit-generated': 1, 'color -- streamlit-generated': 'beta', 'value -- streamlit-generated': 2}, {'index -- streamlit-generated': 2, 'color -- streamlit-generated': 'beta', 'value -- streamlit-generated': 1}]}, 'circle': {'name': 'bbb5436c72daf7f025b50a08bfaa6151', 'schema': 'x: int64\ny: int64\n-- schema metadata --\npandas: \'{"index_columns": [{"kind": "range", "name": null, "start": 0, "\' + 472', 'columns': ['x', 'y'], 'row_count': 3, 'rows': [{'x': 1, 'y': 3}, {'x': 2, 'y': 1}, {'x': 3, 'y': 2}]}}

# The measured deck.gl json, parsed and raw.
CHARTS_DECK = {'initialViewState': {'latitude': 40.85, 'longitude': -73.95, 'pitch': 0, 'zoom': 10}, 'layers': [{'@@type': 'ScatterplotLayer', 'getPosition': '@@=[lon, lat]', 'getRadius': 100, 'radiusMinPixels': 3, 'radiusUnits': 'meters', 'getFillColor': [200, 30, 0, 160], 'data': [{'lat': 40.7, 'lon': -74.0}, {'lat': 41.0, 'lon': -73.9}]}]}
CHARTS_DECK_RAW = '{"initialViewState": {"latitude": 40.85, "longitude": -73.95, "pitch": 0, "zoom": 10}, "layers": [{"@@type": "ScatterplotLayer", "getPosition": "@@=[lon, lat]", "getRadius": 100, "radiusMinPixels": 3, "radiusUnits": "meters", "getFillColor": [200, 30, 0, 160], "data": [{"lat": 40.7, "lon": -74.0}, {"lat": 41.0, "lon": -73.9}]}]}'

# The DOM projection the official frontend resolves.
CHARTS_DOM = {'charts': ['0120123', '0120123alphabeta', '0123x0123y'], 'deckish': ['stVegaLiteChart', 'stVegaLiteChart', 'stVegaLiteChart', 'stDeckGlJsonChart', 'stDeckGlJsonChartZoomButton'], 'canvases': 2, 'exceptions': []}

CHARTS_SOURCE_PINS = {
    "python": ("tests/reference/charts_app.py", "bb49103ead1673de17c33c297e44587089f2a1a6903411e38d90b63ce8c5c076"),
    "native": ("streamlit/examples/charts.rs", "11d1267eb2156bea9b32f77d1902d23c792674a9d963a70cfb28753df4e9b9e1"),
}

CHARTS_REQUIRED = (
    "contract", "stage_set", "source_pin", "charts_set", "line_wire",
    "area_wire", "scatter_wire", "map_wire", "dom_projection",
    "no_exceptions", "finishes", "png_sources",
)


def _record(checks, name, ok, expected, actual):
    checks.append({"step": CHARTS_CASE, "check": name, "expected": expected, "actual": actual, "ok": bool(ok)})


def _need(condition, message):
    if not condition:
        raise ValueError(message)


def _calc_hash(data: bytes) -> str:
    """The reference fast hasher pinned in 1.66.1: BLAKE2b/16."""
    return hashlib.blake2b(str(data).encode("utf-8"), digest_size=16).hexdigest()


def _charts(stage):
    out = []
    for frame in stage.get("new_frames") or []:
        delta = (frame.get("summary") or {}).get("delta") or {}
        if not delta:
            continue
        kind = delta.get("type")
        _need(kind in ("new_transient", "new_element", "add_block"), f"unexpected delta kind {kind!r}")
        if kind == "new_element":
            out.append(delta)
    return out


def charts_checks(*, observation=None):
    checks = []
    verified = set()

    def mark(name):
        verified.add(name)
        _record(checks, name, True, "the measured 1.66.1 charts wire", "contract verified")

    def fail(name, actual):
        _record(checks, name, False, "the measured 1.66.1 charts wire", str(actual))

    try:
        _need(isinstance(observation, dict), "observation must be a dict")
        _need(observation.get("journey") == CHARTS_CASE and observation.get("contract") == CHARTS_CONTRACT,
              "missing versioned charts contract identity")
        _need(bool(observation.get("scope")) and bool(observation.get("url")), "missing scope/url")
        mark("contract")

        stages = observation.get("stages")
        _need(isinstance(stages, list) and tuple(s.get("name") for s in stages) == tuple(CHARTS_STAGES),
              f"stages must be exactly the {len(CHARTS_STAGES)} measured stages in order")
        for stage in stages:
            _need(isinstance(stage.get("dom"), dict) and isinstance(stage.get("screenshot"), dict)
                  and isinstance(stage.get("new_frames"), list), f"stage {stage.get('name')} lacks dom/screenshot/new_frames")
        mark("stage_set")

        source = observation.get("source") or {}
        side = "python" if observation.get("scope") == "PYTHON SIDE ONLY" else "native"
        path, pinned = CHARTS_SOURCE_PINS[side]
        _need(source.get("file") == path and source.get("sha256") == pinned,
              f"driven source is not the pinned {path} of this contract")
        mark("source_pin")

        charts = _charts(stages[0])
        kinds = [delta.get("element") for delta in charts]
        _need(kinds == ["vega_lite_chart", "vega_lite_chart", "vega_lite_chart", "deck_gl_json_chart"],
              f"the page must carry three vega charts then the map, got {kinds}")
        marks = []
        for delta in charts[:3]:
            full = (delta.get("element_full") or {}).get("vegaLiteChart") or {}
            spec = json.loads(full.get("spec") or "null") or {}
            marks.append((spec.get("mark") or {}).get("type") or ((spec.get("layer") or [{}])[0].get("mark") or {}).get("type"))
        _need(marks == CHARTS_MARKS, f"the vega marks must be {CHARTS_MARKS} in order, got {marks}")
        mark("charts_set")

        for index, name in enumerate(("line_wire", "area_wire", "scatter_wire")):
            delta = charts[index]
            full = (delta.get("element_full") or {}).get("vegaLiteChart") or {}
            served_spec = full.get("spec") or ""
            dataset_list = delta.get("vega_lite_datasets") or []
            _need(len(dataset_list) == 1, f"the {name} chart must carry exactly one dataset, got {len(dataset_list)}")
            summary = dataset_list[0]
            served_name = summary.get("name") or ""
            arrow = summary.get("arrow") or {}
            _need(isinstance(served_name, str) and len(served_name) == 32
                  and all(character in "0123456789abcdef" for character in served_name),
                  f"the {name} dataset name must be a 32-hex digest")
            raw = base64.b64decode(arrow.get("base64") or "", validate=True) if arrow.get("base64") else b""
            _need(bool(raw) and _calc_hash(raw) == served_name,
                  f"the {name} dataset name is not calc_hash(str(arrow_bytes)) over the served bytes")
            expected_spec = CHARTS_SPECS[CHARTS_MARKS[index]]
            expected_name = CHARTS_DATASETS[CHARTS_MARKS[index]]["name"]
            _need(served_spec.replace(served_name, "<name>") == expected_spec.replace(expected_name, "<name>"),
                  f"the {name} spec differs from the measured wire beyond the dataset name")
            _need({key: arrow.get(key) for key in ("schema", "columns", "row_count", "rows")}
                  == {key: CHARTS_DATASETS[CHARTS_MARKS[index]].get(key) for key in ("schema", "columns", "row_count", "rows")},
                  f"the {name} dataset frame differs from the measured frame")
            _need(summary.get("has_name") is True and full.get("theme") == "streamlit",
                  f"the {name} element fields differ from the measured wire")
            element = delta.get("element_full") or {}
            _need(element.get("widthConfig") == {"useStretch": True} and element.get("heightConfig") == {"useContent": True},
                  f"the {name} element sizing differs from the measured wire")
            mark(name)

        deck_delta = charts[3]
        deck_full = deck_delta.get("element_full") or {}
        served_deck_raw = (deck_full.get("deckGlJsonChart") or {}).get("json") or ""
        _need(served_deck_raw == CHARTS_DECK_RAW, "the deck.gl json string differs from the measured wire")
        _need(json.loads(served_deck_raw or "null") == CHARTS_DECK, "the deck.gl json does not reparse to the measured map")
        _need(deck_full.get("widthConfig") == {"useStretch": True} and deck_full.get("heightConfig") == {"pixelHeight": 500},
              "the map element sizing differs from the measured wire")
        _need((deck_delta.get("deck_gl_fields") or {}).get("mapbox_token") in (None, ""),
              "the map must not leak a mapbox token")
        mark("map_wire")

        page = (observation.get("url") or "").rstrip("/")
        dom_text = json.dumps({key: (stages[0]["dom"] or {}).get(key) for key in ("charts", "deckish", "canvases", "exceptions")}, ensure_ascii=False)
        dom_text = dom_text.replace(page, "<page>")
        _need(json.loads(dom_text) == CHARTS_DOM, "the resolved DOM projection differs from the measured page")
        mark("dom_projection")

        _need(not ((stages[0]["dom"] or {}).get("exceptions") or []), "the page renders an exception")
        for frame in stages[0]["new_frames"]:
            delta = (frame.get("summary") or {}).get("delta") or {}
            _need(delta.get("element") != "exception", "the stream carries an exception element")
        mark("no_exceptions")

        finishes = [((frame.get("summary") or {}).get("script_finished") or {}).get("status")
                    for frame in stages[0]["new_frames"]
                    if (frame.get("summary") or {}).get("type") == "script_finished"]
        _need(finishes == [0], "the run must finish exactly once with FINISHED_SUCCESSFULLY")
        mark("finishes")

        root = pathlib.Path(observation.get("ipc_dir", ".")).resolve()
        for stage in stages:
            record = stage.get("screenshot") or {}
            _need(not pathlib.Path(record.get("file", "")).is_absolute(), "screenshot path must be relative")
            png = (root / record.get("file", "")).resolve()
            _need(png.is_relative_to(root) and png.is_file(), f"missing stage PNG {record.get('file')}")
            data = png.read_bytes()
            _need(data.startswith(b"\x89PNG\r\n\x1a\n") and hashlib.sha256(data).hexdigest() == record.get("sha256"),
                  f"stage PNG sha/magic mismatch for {record.get('file')}")
        mark("png_sources")
    except (ValueError, TypeError, KeyError, IndexError, OSError, AttributeError, StopIteration) as exc:
        for name in CHARTS_REQUIRED:
            if name not in verified:
                fail(name, str(exc))
        return checks
    return checks


def charts_result(*, observation=None):
    """Aggregate the contract checks the way the shared journey judge does."""
    checks = charts_checks(observation=observation)
    failures = [check for check in checks if not check["ok"]]
    return {
        "checks": checks,
        "counts": {"expected": len(checks), "executed": len(checks), "asserted": len(checks) - len(failures)},
        "failures": failures,
        "ok": not failures and len(checks) == len(CHARTS_REQUIRED),
    }
