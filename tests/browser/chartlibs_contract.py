"""The strict chart-library contract: journey-chartlibs-v1.

This criterion judges the observation the committed collector
(chartlibs_capture.py) writes, against the Python 1.66.1 wire measured on
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

CHARTLIBS_CASE = "chartlibs-page"
CHARTLIBS_CONTRACT = "journey-chartlibs-v1"

CHARTLIBS_STAGES = [
    '01-load'
]

CHARTLIBS_TIMELINE = {
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
            'kind': 'vega_lite_chart',
            'element_full': {
                'vegaLiteChart': {
                    'spec': '{"data": {"name": "<digest>"}, "mark": {"type": "bar"}, "encoding": {"x": {"field": "kind", "type": "nominal"}, "y": {"field": "count", "type": "quantitative"}}, "$schema": "https://vega.github.io/schema/vega-lite/v5.20.1.json", "autosize": {"type": "fit", "contains": "padding"}}',
                    'datasets': [
                        {
                            'name': '<digest>',
                            'data': {
                                'data': {
                                    'fields': [
                                        [
                                            'kind',
                                            'large_string',
                                            True
                                        ],
                                        [
                                            'count',
                                            'int64',
                                            True
                                        ]
                                    ],
                                    'metadata': {
                                        'pandas': '{"index_columns": [{"kind": "range", "name": null, "start": 0, "stop": 2, "step": 1}], "column_indexes": [{"name": null, "field_name": null, "pandas_type": "unicode", "numpy_type": "str", "metadata": {"encoding": "UTF-8"}}], "columns": [{"name": "kind", "field_name": "kind", "pandas_type": "object", "numpy_type": "str", "metadata": null}, {"name": "count", "field_name": "count", "pandas_type": "int64", "numpy_type": "int64", "metadata": null}], "attributes": {}, "creator": {"library": "pyarrow", "version": "26.0.0"}, "pandas_version": "3.1.0"}'
                                    },
                                    'rows': [
                                        {
                                            'kind': 'a',
                                            'count': 3
                                        },
                                        {
                                            'kind': 'b',
                                            'count': 7
                                        }
                                    ]
                                }
                            },
                            'hasName': True
                        }
                    ],
                    'theme': 'streamlit'
                },
                'heightConfig': {
                    'useContent': True
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
            'kind': 'vega_lite_chart',
            'element_full': {
                'vegaLiteChart': {
                    'spec': '{"mark": "bar", "encoding": {"x": {"field": "kind", "type": "nominal"}, "y": {"field": "count", "type": "quantitative"}}, "autosize": {"type": "fit", "contains": "padding"}}',
                    'data': {
                        'data': {
                            'fields': [
                                [
                                    'kind',
                                    'large_string',
                                    True
                                ],
                                [
                                    'count',
                                    'int64',
                                    True
                                ]
                            ],
                            'metadata': {
                                'pandas': '{"index_columns": [{"kind": "range", "name": null, "start": 0, "stop": 2, "step": 1}], "column_indexes": [{"name": null, "field_name": null, "pandas_type": "unicode", "numpy_type": "str", "metadata": {"encoding": "UTF-8"}}], "columns": [{"name": "kind", "field_name": "kind", "pandas_type": "object", "numpy_type": "str", "metadata": null}, {"name": "count", "field_name": "count", "pandas_type": "int64", "numpy_type": "int64", "metadata": null}], "attributes": {}, "creator": {"library": "pyarrow", "version": "26.0.0"}, "pandas_version": "3.1.0"}'
                            },
                            'rows': [
                                {
                                    'kind': 'a',
                                    'count': 3
                                },
                                {
                                    'kind': 'b',
                                    'count': 7
                                }
                            ]
                        }
                    },
                    'theme': 'streamlit'
                },
                'heightConfig': {
                    'useContent': True
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
            'kind': 'plotly_chart',
            'element_full': {
                'plotlyChart': {
                    'theme': 'streamlit',
                    'id': '$$ID-None',
                    'spec': '{"data":[{"x":["a","b"],"y":[3,7],"type":"bar"}],"layout":{"template":{"data":{"candlestick":[{"decreasing":{"line":{"color":"#000033"}},"increasing":{"line":{"color":"#000032"}},"type":"candlestick"}],"contourcarpet":[{"colorscale":[[0.0,"#000011"],[0.1111111111111111,"#000012"],[0.2222222222222222,"#000013"],[0.3333333333333333,"#000014"],[0.4444444444444444,"#000015"],[0.5555555555555556,"#000016"],[0.6666666666666666,"#000017"],[0.7777777777777778,"#000018"],[0.8888888888888888,"#000019"],[1.0,"#000020"]],"type":"contourcarpet"}],"contour":[{"colorscale":[[0.0,"#000011"],[0.1111111111111111,"#000012"],[0.2222222222222222,"#000013"],[0.3333333333333333,"#000014"],[0.4444444444444444,"#000015"],[0.5555555555555556,"#000016"],[0.6666666666666666,"#000017"],[0.7777777777777778,"#000018"],[0.8888888888888888,"#000019"],[1.0,"#000020"]],"type":"contour"}],"heatmap":[{"colorscale":[[0.0,"#000011"],[0.1111111111111111,"#000012"],[0.2222222222222222,"#000013"],[0.3333333333333333,"#000014"],[0.4444444444444444,"#000015"],[0.5555555555555556,"#000016"],[0.6666666666666666,"#000017"],[0.7777777777777778,"#000018"],[0.8888888888888888,"#000019"],[1.0,"#000020"]],"type":"heatmap"}],"histogram2d":[{"colorscale":[[0.0,"#000011"],[0.1111111111111111,"#000012"],[0.2222222222222222,"#000013"],[0.3333333333333333,"#000014"],[0.4444444444444444,"#000015"],[0.5555555555555556,"#000016"],[0.6666666666666666,"#000017"],[0.7777777777777778,"#000018"],[0.8888888888888888,"#000019"],[1.0,"#000020"]],"type":"histogram2d"}],"icicle":[{"textfont":{"color":"white"},"type":"icicle"}],"sankey":[{"textfont":{"color":"#000036"},"type":"sankey"}],"scatter":[{"marker":{"line":{"width":0}},"type":"scatter"}],"table":[{"cells":{"fill":{"color":"#000038"},"font":{"color":"#000037"},"line":{"color":"#000039"}},"header":{"fill":{"color":"#000040"},"font":{"color":"#000036"},"line":{"color":"#000039"}},"type":"table"}],"waterfall":[{"connector":{"line":{"color":"#000036","width":2}},"decreasing":{"marker":{"color":"#000033"}},"increasing":{"marker":{"color":"#000032"}},"totals":{"marker":{"color":"#000034"}},"type":"waterfall"}]},"layout":{"coloraxis":{"colorscale":[[0.0,"#000011"],[0.1111111111111111,"#000012"],[0.2222222222222222,"#000013"],[0.3333333333333333,"#000014"],[0.4444444444444444,"#000015"],[0.5555555555555556,"#000016"],[0.6666666666666666,"#000017"],[0.7777777777777778,"#000018"],[0.8888888888888888,"#000019"],[1.0,"#000020"]]},"colorscale":{"diverging":[[0.0,"#000021"],[0.1111111111111111,"#000022"],[0.2222222222222222,"#000023"],[0.3333333333333333,"#000024"],[0.4444444444444444,"#000025"],[0.5555555555555556,"#000026"],[0.6666666666666666,"#000027"],[0.7777777777777778,"#000028"],[0.8888888888888888,"#000029"],[1.0,"#000030"]],"sequential":[[0.0,"#000011"],[0.1111111111111111,"#000012"],[0.2222222222222222,"#000013"],[0.3333333333333333,"#000014"],[0.4444444444444444,"#000015"],[0.5555555555555556,"#000016"],[0.6666666666666666,"#000017"],[0.7777777777777778,"#000018"],[0.8888888888888888,"#000019"],[1.0,"#000020"]],"sequentialminus":[[0.0,"#000011"],[0.1111111111111111,"#000012"],[0.2222222222222222,"#000013"],[0.3333333333333333,"#000014"],[0.4444444444444444,"#000015"],[0.5555555555555556,"#000016"],[0.6666666666666666,"#000017"],[0.7777777777777778,"#000018"],[0.8888888888888888,"#000019"],[1.0,"#000020"]]},"colorway":["#000001","#000002","#000003","#000004","#000005","#000006","#000007","#000008","#000009","#000010"]}}}}',
                    'config': '{}'
                },
                'heightConfig': {
                    'pixelHeight': 450
                },
                'widthConfig': {
                    'useStretch': True
                }
            },
            'path': [
                0,
                2
            ]
        },
        {
            'kind': 'deck_gl_json_chart',
            'element_full': {
                'deckGlJsonChart': {
                    'json': '{\n  "initialViewState": {\n    "latitude": 0.0,\n    "longitude": 0.0,\n    "zoom": 1\n  },\n  "layers": [\n    {\n      "@@type": "ScatterplotLayer",\n      "data": [\n        {\n          "position": [\n            0.0,\n            0.0\n          ],\n          "size": 4\n        }\n      ],\n      "getColor": [\n        255,\n        0,\n        0\n      ],\n      "getRadius": 100,\n      "id": "<uuid>"\n    }\n  ],\n  "mapProvider": "carto",\n  "mapStyle": "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json",\n  "views": [\n    {\n      "@@type": "MapView",\n      "controller": true\n    }\n  ]\n}'
                },
                'heightConfig': {
                    'pixelHeight': 500
                },
                'widthConfig': {
                    'useStretch': True
                }
            },
            'path': [
                0,
                3
            ]
        },
        {
            'kind': 'graphviz_chart',
            'element_full': {
                'graphvizChart': {
                    'spec': 'digraph { a -> b }',
                    'elementId': '342a5ac24f2b29e74222b5f39ab31d99',
                    'engine': 'dot'
                },
                'heightConfig': {
                    'useContent': True
                },
                'widthConfig': {
                    'useContent': True
                }
            },
            'path': [
                0,
                4
            ]
        },
        {
            'kind': 'markdown',
            'element_full': {
                'markdown': {
                    'body': '````mermaid\ngraph LR\n    A[Start] --> B{Decision}\n````',
                    'elementType': 'NATIVE',
                    'wrap': True
                },
                'widthConfig': {
                    'useStretch': True
                },
                'textAlignmentConfig': {
                    'alignment': 'LEFT'
                }
            },
            'path': [
                0,
                5
            ]
        },
        {
            'kind': 'echarts_chart',
            'element_full': {
                'heightConfig': {
                    'pixelHeight': 350
                },
                'widthConfig': {
                    'useStretch': True
                },
                'echartsChart': {
                    'spec': '{"xAxis":{"type":"category","data":["a","b"]},"yAxis":{"type":"value"},"series":[{"type":"bar","data":[3,7]}]}',
                    'theme': 'streamlit'
                }
            },
            'path': [
                0,
                6
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

CHARTLIBS_DOMS = {
    '01-load': {
        'charts': 2,
        'plotly': 1,
        'deck': 0,
        'graphviz': 1,
        'mermaid': 0,
        'echarts': 0,
        'exceptions': []
    }
}

CHARTLIBS_SOURCE_FILES = {
    "python": "tests/reference/chartlibs_app.py",
    "native": "streamlit/examples/chartlibs.rs",
}

CHARTLIBS_REQUIRED = (
    "contract", "stage_set", "timeline", "dom_projection",
    "finishes", "png_sources",
)

ID_RE = re.compile(r"\$\$ID-[0-9a-f]{32}-")
NORM_ID = "$$ID-"
DATASET_NAME_RE = re.compile(r"[0-9a-f]{32}")
# pydeck assigns an unnamed layer a fresh random UUID every run.
UUID_RE = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")


def normalize_chart(full):
    """Mask the side-specific chart details: the $$ID digests, the arrow IPC
    flatbuffer layout (compared logically: fields, metadata, rows), the
    content-addressed dataset names derived from those bytes, and pydeck's
    per-run layer UUIDs."""
    import base64
    import io

    import pyarrow.ipc

    full = json.loads(json.dumps(full))
    vega = full.get("vegaLiteChart")
    if vega is not None:
        if "data" in vega:
            vega["data"]["data"] = _logical_arrow(vega["data"]["data"])
        for dataset in vega.get("datasets", []):
            dataset["name"] = DATASET_NAME_RE.sub("<digest>", dataset["name"])
            dataset["data"]["data"] = _logical_arrow(dataset["data"]["data"])
        vega["spec"] = DATASET_NAME_RE.sub("<digest>", vega["spec"])
    deck = full.get("deckGlJsonChart")
    if deck is not None:
        deck["json"] = UUID_RE.sub("<uuid>", deck["json"])
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
        "rows": batch.to_pylist(),
    }


def _record(checks, name, ok, expected, actual):
    checks.append({"step": CHARTLIBS_CASE, "check": name, "expected": expected, "actual": actual, "ok": bool(ok)})


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
            if name in ("vega_lite_chart", "plotly_chart", "deck_gl_json_chart", "graphviz_chart", "markdown", "echarts_chart"):
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


def chartlibs_checks(*, observation=None):
    checks = []
    verified = set()

    def mark(name):
        verified.add(name)
        _record(checks, name, True, "the measured 1.66.1 chart-library wire", "contract verified")

    def fail(name, actual):
        _record(checks, name, False, "the measured 1.66.1 chart-library wire", str(actual))

    try:
        _need(isinstance(observation, dict), "observation must be a dict")
        _need(observation.get("journey") == CHARTLIBS_CASE and observation.get("contract") == CHARTLIBS_CONTRACT,
              "missing versioned datetime contract identity")
        _need(bool(observation.get("scope")) and bool(observation.get("url")), "missing scope/url")
        mark("contract")

        stages = observation.get("stages")
        _need(isinstance(stages, list) and tuple(s.get("name") for s in stages) == tuple(CHARTLIBS_STAGES),
              f"stages must be exactly the {len(CHARTLIBS_STAGES)} measured stages in order")
        for stage in stages:
            _need(isinstance(stage.get("dom"), dict) and isinstance(stage.get("screenshot"), dict)
                  and isinstance(stage.get("new_frames"), list), f"stage {stage.get('name')} lacks dom/screenshot/new_frames")
        mark("stage_set")

        timelines = {stage["name"]: _timeline(stage) for stage in stages}
        for name in CHARTLIBS_STAGES:
            _need(timelines[name] == CHARTLIBS_TIMELINE[name],
                  f"stage {name} frame timeline differs from the measured wire ({len(timelines[name])} frames)")
        mark("timeline")

        for stage in stages:
            name = stage["name"]
            _need({key: (stage["dom"] or {}).get(key) for key in CHARTLIBS_DOMS[name]} == CHARTLIBS_DOMS[name],
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
        for name in CHARTLIBS_REQUIRED:
            if name not in verified:
                fail(name, str(exc))
        return checks
    return checks


def chartlibs_result(*, observation=None):
    """Aggregate the contract checks the way the shared journey judge does."""
    checks = chartlibs_checks(observation=observation)
    failures = [check for check in checks if not check["ok"]]
    return {
        "checks": checks,
        "counts": {"expected": len(checks), "executed": len(checks), "asserted": len(checks) - len(failures)},
        "failures": failures,
        "ok": not failures and len(checks) == len(CHARTLIBS_REQUIRED),
    }
