"""The strict column-config contract: journey-colconfig-v1.

This criterion judges the observation the committed collector
(colconfig_capture.py) writes, against the Python 1.66.1 wire measured on
2026-10-26 with the official frontend and recorded in .codex/compatibility.md
(Chart libraries): the seven chart surfaces (altair, vega_lite, plotly,
pydeck, graphviz, mermaid, echarts) with their full element wires — spec
strings, layout configs, themes and heights. The chart-building libraries
are Python-only; the Rust surfaces pass the same final payloads. Two
side-specific normalizations apply, like the $$ID digests: the arrow IPC
flatbuffer layout is compared logically (fields, metadata, rows), and the
content-addressed dataset names inside vega specs are masked. The run still
finishes FINISHED_SUCCESSFULLY and the settled DOM shows the mounted chart
counts. Unbounded leading main-container add_blocks at [0] are the Rust
runtime's documented divergence.
"""

from __future__ import annotations

import hashlib
import json
import pathlib
import re

COLCONFIG_CASE = "colconfig-page"
COLCONFIG_CONTRACT = "journey-colconfig-v1"

COLCONFIG_STAGES = [
    '01-load'
]

COLCONFIG_TIMELINE = {
    '01-load': [
        {
            'kind': 'rerun'
        },
        {
            'kind': 'new_session'
        },
        {
            'kind': 'session_status_changed'
        },
        {
            'kind': 'dataframe',
            'element_full': {
                'dataframe': {
                    'arrowData': {
                        'data': {
                            'fields': [
                                [
                                    'name',
                                    'large_string',
                                    True
                                ],
                                [
                                    'title',
                                    'large_string',
                                    True
                                ],
                                [
                                    'score',
                                    'int64',
                                    True
                                ],
                                [
                                    'done',
                                    'bool',
                                    True
                                ],
                                [
                                    'kind',
                                    'large_string',
                                    True
                                ],
                                [
                                    'tags',
                                    'list<item: string>',
                                    True
                                ],
                                [
                                    'day',
                                    'date32[day]',
                                    True
                                ],
                                [
                                    'moment',
                                    'timestamp[us]',
                                    True
                                ],
                                [
                                    'clock',
                                    'time64[us]',
                                    True
                                ],
                                [
                                    'items',
                                    'list<item: string>',
                                    True
                                ],
                                [
                                    'payload',
                                    'struct<k: int64>',
                                    True
                                ],
                                [
                                    'notes',
                                    'large_string',
                                    True
                                ],
                                [
                                    'site',
                                    'large_string',
                                    True
                                ],
                                [
                                    'pic',
                                    'large_string',
                                    True
                                ],
                                [
                                    'trend',
                                    'int64',
                                    True
                                ],
                                [
                                    'count',
                                    'int64',
                                    True
                                ],
                                [
                                    'signal',
                                    'int64',
                                    True
                                ],
                                [
                                    'fill',
                                    'int64',
                                    True
                                ],
                                [
                                    'clip',
                                    'large_string',
                                    True
                                ],
                                [
                                    'reel',
                                    'large_string',
                                    True
                                ],
                                [
                                    'act',
                                    'large_string',
                                    True
                                ]
                            ],
                            'metadata': {
                                'pandas': '{"index_columns": [{"kind": "range", "name": null, "start": 0, "stop": 2, "step": 1}], "column_indexes": [{"name": null, "field_name": null, "pandas_type": "unicode", "numpy_type": "str", "metadata": {"encoding": "UTF-8"}}], "columns": [{"name": "name", "field_name": "name", "pandas_type": "object", "numpy_type": "str", "metadata": null}, {"name": "title", "field_name": "title", "pandas_type": "object", "numpy_type": "str", "metadata": null}, {"name": "score", "field_name": "score", "pandas_type": "int64", "numpy_type": "int64", "metadata": null}, {"name": "done", "field_name": "done", "pandas_type": "bool", "numpy_type": "bool", "metadata": null}, {"name": "kind", "field_name": "kind", "pandas_type": "object", "numpy_type": "str", "metadata": null}, {"name": "tags", "field_name": "tags", "pandas_type": "list[unicode]", "numpy_type": "object", "metadata": null}, {"name": "day", "field_name": "day", "pandas_type": "date", "numpy_type": "object", "metadata": null}, {"name": "moment", "field_name": "moment", "pandas_type": "datetime", "numpy_type": "datetime64[us]", "metadata": null}, {"name": "clock", "field_name": "clock", "pandas_type": "time", "numpy_type": "object", "metadata": null}, {"name": "items", "field_name": "items", "pandas_type": "list[unicode]", "numpy_type": "object", "metadata": null}, {"name": "payload", "field_name": "payload", "pandas_type": "object", "numpy_type": "object", "metadata": null}, {"name": "notes", "field_name": "notes", "pandas_type": "object", "numpy_type": "str", "metadata": null}, {"name": "site", "field_name": "site", "pandas_type": "object", "numpy_type": "str", "metadata": null}, {"name": "pic", "field_name": "pic", "pandas_type": "object", "numpy_type": "str", "metadata": null}, {"name": "trend", "field_name": "trend", "pandas_type": "int64", "numpy_type": "int64", "metadata": null}, {"name": "count", "field_name": "count", "pandas_type": "int64", "numpy_type": "int64", "metadata": null}, {"name": "signal", "field_name": "signal", "pandas_type": "int64", "numpy_type": "int64", "metadata": null}, {"name": "fill", "field_name": "fill", "pandas_type": "int64", "numpy_type": "int64", "metadata": null}, {"name": "clip", "field_name": "clip", "pandas_type": "object", "numpy_type": "str", "metadata": null}, {"name": "reel", "field_name": "reel", "pandas_type": "object", "numpy_type": "str", "metadata": null}, {"name": "act", "field_name": "act", "pandas_type": "object", "numpy_type": "str", "metadata": null}], "attributes": {}, "creator": {"library": "pyarrow", "version": "26.0.0"}, "pandas_version": "3.1.0"}'
                            },
                            'rows': [
                                [
                                    'alpha',
                                    'Chief',
                                    '1',
                                    'True',
                                    'a',
                                    "['x']",
                                    '2025-01-02',
                                    '2025-01-02 03:04:00',
                                    '03:04:00',
                                    "['a', 'b']",
                                    "{'k': 1}",
                                    '**bold**',
                                    'https://example.com',
                                    'a',
                                    '1',
                                    '3',
                                    '5',
                                    '50',
                                    'c1',
                                    'r1',
                                    'go'
                                ],
                                [
                                    'beta',
                                    'Deputy',
                                    '2',
                                    'False',
                                    'b',
                                    "['y']",
                                    '2025-02-03',
                                    '2025-02-03 04:05:00',
                                    '04:05:00',
                                    "['c']",
                                    "{'k': 2}",
                                    'plain',
                                    'https://example.org',
                                    'b',
                                    '2',
                                    '4',
                                    '6',
                                    '60',
                                    'c2',
                                    'r2',
                                    'stop'
                                ]
                            ]
                        }
                    },
                    'columns': '{"name": {"label": "Name", "width": "medium", "help": "the name", "pinned": true, "alignment": "center"}, "title": {"label": "Title", "default": "hi", "type_config": {"type": "text", "max_chars": 10, "validate": "^h"}}, "score": {"label": "Score", "default": 1, "type_config": {"type": "number", "min_value": 0, "max_value": 10, "format": "%d", "step": 1}}, "done": {"label": "Done", "default": true, "type_config": {"type": "checkbox"}}, "kind": {"label": "Kind", "default": "a", "type_config": {"type": "selectbox", "options": ["a", "b"]}}, "tags": {"label": "Tags", "default": ["x"], "type_config": {"type": "multiselect", "options": [{"value": "x"}, {"value": "y"}], "accept_new_options": true}}, "day": {"label": "Day", "default": "2025-01-02", "type_config": {"type": "date", "format": "YYYY/MM/DD", "min_value": "2024-01-01", "max_value": "2026-01-01", "step": 1}}, "moment": {"label": "Moment", "default": "2025-01-02T03:04:00", "type_config": {"type": "datetime", "format": "YYYY/MM/DD HH:mm", "min_value": "2024-01-01T00:00:00", "max_value": "2026-01-01T00:00:00", "step": 60, "timezone": "UTC"}}, "clock": {"label": "Clock", "default": "03:04:00", "type_config": {"type": "time", "format": "HH:mm", "min_value": "01:00:00", "max_value": "23:00:00", "step": 60}}, "items": {"label": "Items", "default": ["a"], "type_config": {"type": "list"}}, "payload": {"label": "Payload", "type_config": {"type": "json"}}, "notes": {"label": "Notes", "default": "**bold**", "type_config": {"type": "markdown"}}, "site": {"label": "Site", "default": "https://example.com", "type_config": {"type": "link", "max_chars": 40, "validate": "^https", "display_text": "open"}}, "pic": {"label": "Pic", "type_config": {"type": "image"}}, "trend": {"label": "Trend", "type_config": {"type": "area_chart", "y_min": 0, "y_max": 10, "color": "#ff0000"}}, "count": {"label": "Count", "type_config": {"type": "bar_chart", "y_min": 0, "y_max": 10, "color": "#00ff00"}}, "signal": {"label": "Signal", "type_config": {"type": "line_chart", "y_min": 0, "y_max": 10, "color": "#0000ff"}}, "fill": {"label": "Fill", "type_config": {"type": "progress", "format": "%d", "min_value": 0, "max_value": 100, "step": 1, "color": "green"}}, "clip": {"label": "Clip", "type_config": {"type": "audio"}}, "reel": {"label": "Reel", "type_config": {"type": "video"}}, "act": {"label": "Act", "disabled": true, "type_config": {"type": "button", "button_type": "primary"}}}',
                    'buttonClickWidgets': {
                        'act': '$$ID-act'
                    }
                },
                'widthConfig': {
                    'useStretch': True
                }
            },
            'path': [
                0,
                0
            ]
        },
        {
            'kind': 'dataframe',
            'element_full': {
                'dataframe': {
                    'arrowData': {
                        'data': {
                            'fields': [
                                [
                                    'qty',
                                    'int64',
                                    True
                                ]
                            ],
                            'metadata': {
                                'pandas': '{"index_columns": [{"kind": "range", "name": null, "start": 0, "stop": 2, "step": 1}], "column_indexes": [{"name": null, "field_name": null, "pandas_type": "unicode", "numpy_type": "str", "metadata": {"encoding": "UTF-8"}}], "columns": [{"name": "qty", "field_name": "qty", "pandas_type": "int64", "numpy_type": "int64", "metadata": null}], "attributes": {}, "creator": {"library": "pyarrow", "version": "26.0.0"}, "pandas_version": "3.1.0"}'
                            },
                            'rows': [
                                [
                                    '1'
                                ],
                                [
                                    '2'
                                ]
                            ]
                        }
                    },
                    'id': '$$ID-editor',
                    'columns': '{"_index": {"hidden": true}}',
                    'editingMode': 'DYNAMIC'
                },
                'widthConfig': {
                    'useStretch': True
                }
            },
            'path': [
                0,
                1
            ]
        },
        {
            'kind': 'markdown',
            'element_full': {
                'markdown': {
                    'body': 'edits=(2, 1)',
                    'elementType': 'NATIVE',
                    'wrap': True
                },
                'textAlignmentConfig': {
                    'alignment': 'LEFT'
                }
            },
            'path': [
                0,
                2
            ]
        },
        {
            'kind': 'script_finished'
        },
        {
            'kind': 'session_status_changed'
        }
    ]
}

COLCONFIG_DOMS = {
    '01-load': {
        'grids': 2,
        'headers': [],
        'exceptions': []
    }
}

COLCONFIG_SOURCE_FILES = {
    "python": "tests/reference/colconfig_app.py",
    "native": "streamlit/examples/colconfig.rs",
}

COLCONFIG_REQUIRED = (
    "contract", "stage_set", "timeline", "dom_projection",
    "finishes", "png_sources",
)

ID_RE = re.compile(r"\$\$ID-[0-9a-f]{32}-")
NORM_ID = "$$ID-"


def normalize_chart(full):
    """Mask the side-specific element details: the $$ID digests and the
    arrow IPC flatbuffer layout (compared logically: fields, metadata and
    the string form of every cell, so date/time objects compare across
    sides)."""
    import base64
    import io

    import pyarrow.ipc

    full = json.loads(json.dumps(full))
    frame = full.get("dataframe")
    if frame is not None:
        arrow = (frame.get("data") or {}).get("data") or (frame.get("arrowData") or {}).get("data")
        if arrow:
            logical = _logical_arrow(arrow)
            if "data" in frame:
                frame["data"]["data"] = logical
            else:
                frame["arrowData"]["data"] = logical
    return json.loads(ID_RE.sub("$$ID-", json.dumps(full)))


def _logical_arrow(b64):
    import base64
    import io

    import pyarrow.ipc

    batch = pyarrow.ipc.open_stream(io.BytesIO(base64.b64decode(b64))).read_next_batch()
    schema = batch.schema
    return {
        "fields": [[f.name, str(f.type), f.nullable] for f in schema],
        "metadata": {k.decode(): v.decode() for k, v in (schema.metadata or {}).items()},
        "rows": [[str(cell) for cell in row.values()] for row in batch.to_pylist()],
    }


def _record(checks, name, ok, expected, actual):
    checks.append({"step": COLCONFIG_CASE, "check": name, "expected": expected, "actual": actual, "ok": bool(ok)})


def _need(condition, message):
    if not condition:
        raise ValueError(message)


def _timeline(stage):
    """The stage's normalized frames; the Rust runtime re-announces the
    main container at [0] at the head of every element batch."""
    out = []
    for frame in stage.get("new_frames") or []:
        summary = frame.get("summary") or {}
        kind = summary.get("type")
        if kind == "delta":
            delta = summary.get("delta") or {}
            inner = delta.get("type")
            _need(inner in ("new_element", "add_block"), f"unexpected delta kind {inner!r}")
            if inner == "add_block" and (delta.get("path") or None) == [0] and (delta.get("block") or {}).get("id") == "main_container":
                continue
            if inner == "add_block":
                _need(False, f"unexpected block {sorted(delta.get('block') or {})}")
            name = delta.get("element")
            if name in ("dataframe", "markdown"):
                full = delta.get("element_full")
                _need(isinstance(full, dict), f"the {name} delta lacks its full element")
                out.append({"kind": name, "element_full": normalize_chart(full), "path": delta.get("path")})
            else:
                _need(False, f"unexpected element {name!r}")
        elif kind == "rerun_script":
            out.append({"kind": "rerun"})
        elif kind in ("new_session", "session_status_changed", "script_finished"):
            out.append({"kind": kind})
        else:
            _need(False, f"unexpected frame kind {kind!r}")
    return out


def colconfig_checks(*, observation=None):
    checks = []
    verified = set()

    def mark(name):
        verified.add(name)
        _record(checks, name, True, "the measured 1.66.1 column-config wire", "contract verified")

    def fail(name, actual):
        _record(checks, name, False, "the measured 1.66.1 column-config wire", str(actual))

    try:
        _need(isinstance(observation, dict), "observation must be a dict")
        _need(observation.get("journey") == COLCONFIG_CASE and observation.get("contract") == COLCONFIG_CONTRACT,
              "missing versioned datetime contract identity")
        _need(bool(observation.get("scope")) and bool(observation.get("url")), "missing scope/url")
        mark("contract")

        stages = observation.get("stages")
        _need(isinstance(stages, list) and tuple(s.get("name") for s in stages) == tuple(COLCONFIG_STAGES),
              f"stages must be exactly the {len(COLCONFIG_STAGES)} measured stages in order")
        for stage in stages:
            _need(isinstance(stage.get("dom"), dict) and isinstance(stage.get("screenshot"), dict)
                  and isinstance(stage.get("new_frames"), list), f"stage {stage.get('name')} lacks dom/screenshot/new_frames")
        mark("stage_set")

        timelines = {stage["name"]: _timeline(stage) for stage in stages}
        for name in COLCONFIG_STAGES:
            _need(timelines[name] == COLCONFIG_TIMELINE[name],
                  f"stage {name} frame timeline differs from the measured wire ({len(timelines[name])} frames)")
        mark("timeline")

        for stage in stages:
            name = stage["name"]
            _need({key: (stage["dom"] or {}).get(key) for key in COLCONFIG_DOMS[name]} == COLCONFIG_DOMS[name],
                  f"stage {name} resolved DOM projection differs from the measured page")
        mark("dom_projection")

        for stage in stages:
            finishes = [((frame.get("summary") or {}).get("script_finished") or {}).get("status")
                        for frame in stage["new_frames"]
                        if (frame.get("summary") or {}).get("type") == "script_finished"]
            _need(finishes == [0], f"stage {stage['name']} must finish exactly once FINISHED_SUCCESSFULLY")
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
        for name in COLCONFIG_REQUIRED:
            if name not in verified:
                fail(name, str(exc))
        return checks
    return checks


def colconfig_result(*, observation=None):
    """Aggregate the contract checks the way the shared journey judge does."""
    checks = colconfig_checks(observation=observation)
    failures = [check for check in checks if not check["ok"]]
    return {
        "checks": checks,
        "counts": {"expected": len(checks), "executed": len(checks), "asserted": len(checks) - len(failures)},
        "failures": failures,
        "ok": not failures and len(checks) == len(COLCONFIG_REQUIRED),
    }
