"""The strict data_editor contract: journey-dataeditor-v1.

This criterion judges the observation the committed collector
(dataeditor_capture.py) writes, against the Python 1.66.1 wire measured on
2026-10-26 with the official frontend and recorded in .codex/compatibility.md
(Data editor): one dynamic-rows st.data_editor driven with real mouse and
keyboard input through four stages — load, a committed cell edit, one added
row, and an edit inside the added row. Every rerun sends exactly one
string_value edit state (row keys as strings, column-NAME keys, typed
cells; an untouched added row reports {}); each run re-emits the editor
element with the ORIGINAL table while the written table carries the applied
edits, an int64 column that gains a null upcasting to float64 like pandas
and back once the cell is filled, and an untouched text cell staying None.
Dataframe payloads compare by decoded content (schema types and column
values), not IPC bytes. The delete-row surface has no keyboard affordance
in the pinned frontend and stays unobserved. Unbounded leading
main-container add_blocks at [0] are the Rust runtime's documented
divergence.
"""

from __future__ import annotations

import base64
import hashlib
import io
import json
import pathlib
import re

DATAEDITOR_CASE = "dataeditor-grid"
DATAEDITOR_CONTRACT = "journey-dataeditor-v1"

DATAEDITOR_STAGES = [
    '01-load',
    '02-edit-cell',
    '03-add-row',
    '04-edit-added-row'
]

DATAEDITOR_TIMELINE = {
    '01-load': [
        {
            'kind': 'rerun',
            'states': []
        },
        {
            'kind': 'new_session'
        },
        {
            'kind': 'session_status_changed'
        },
        {
            'kind': 'dataframe',
            'editing': 'DYNAMIC',
            'id': '$$ID-editor',
            'path': [
                0,
                0
            ],
            'table': {
                'rows': 2,
                'types': [
                    'int64',
                    'large_string'
                ],
                'columns': {
                    'qty': [
                        1,
                        2
                    ],
                    'label': [
                        'a',
                        'b'
                    ]
                }
            }
        },
        {
            'kind': 'dataframe',
            'editing': 0,
            'id': '',
            'path': [
                0,
                1
            ],
            'table': {
                'rows': 2,
                'types': [
                    'int64',
                    'large_string'
                ],
                'columns': {
                    'qty': [
                        1,
                        2
                    ],
                    'label': [
                        'a',
                        'b'
                    ]
                }
            }
        },
        {
            'kind': 'markdown',
            'body': 'rows=2',
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
    ],
    '02-edit-cell': [
        {
            'kind': 'rerun',
            'states': [
                {
                    'id': '$$ID-editor',
                    'value_field': 'string_value',
                    'value': '{"edited_rows":{"0":{"qty":7}},"added_rows":[],"deleted_rows":[]}'
                }
            ]
        },
        {
            'kind': 'new_session'
        },
        {
            'kind': 'session_status_changed'
        },
        {
            'kind': 'dataframe',
            'editing': 'DYNAMIC',
            'id': '$$ID-editor',
            'path': [
                0,
                0
            ],
            'table': {
                'rows': 2,
                'types': [
                    'int64',
                    'large_string'
                ],
                'columns': {
                    'qty': [
                        1,
                        2
                    ],
                    'label': [
                        'a',
                        'b'
                    ]
                }
            }
        },
        {
            'kind': 'dataframe',
            'editing': 0,
            'id': '',
            'path': [
                0,
                1
            ],
            'table': {
                'rows': 2,
                'types': [
                    'int64',
                    'large_string'
                ],
                'columns': {
                    'qty': [
                        7,
                        2
                    ],
                    'label': [
                        'a',
                        'b'
                    ]
                }
            }
        },
        {
            'kind': 'markdown',
            'body': 'rows=2',
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
    ],
    '03-add-row': [
        {
            'kind': 'rerun',
            'states': [
                {
                    'id': '$$ID-editor',
                    'value_field': 'string_value',
                    'value': '{"edited_rows":{"0":{"qty":7}},"added_rows":[{}],"deleted_rows":[]}'
                }
            ]
        },
        {
            'kind': 'new_session'
        },
        {
            'kind': 'session_status_changed'
        },
        {
            'kind': 'dataframe',
            'editing': 'DYNAMIC',
            'id': '$$ID-editor',
            'path': [
                0,
                0
            ],
            'table': {
                'rows': 2,
                'types': [
                    'int64',
                    'large_string'
                ],
                'columns': {
                    'qty': [
                        1,
                        2
                    ],
                    'label': [
                        'a',
                        'b'
                    ]
                }
            }
        },
        {
            'kind': 'dataframe',
            'editing': 0,
            'id': '',
            'path': [
                0,
                1
            ],
            'table': {
                'rows': 3,
                'types': [
                    'double',
                    'large_string'
                ],
                'columns': {
                    'qty': [
                        7.0,
                        2.0,
                        None
                    ],
                    'label': [
                        'a',
                        'b',
                        None
                    ]
                }
            }
        },
        {
            'kind': 'markdown',
            'body': 'rows=3',
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
    ],
    '04-edit-added-row': [
        {
            'kind': 'rerun',
            'states': [
                {
                    'id': '$$ID-editor',
                    'value_field': 'string_value',
                    'value': '{"edited_rows":{"0":{"qty":7}},"added_rows":[{"qty":9}],"deleted_rows":[]}'
                }
            ]
        },
        {
            'kind': 'new_session'
        },
        {
            'kind': 'session_status_changed'
        },
        {
            'kind': 'dataframe',
            'editing': 'DYNAMIC',
            'id': '$$ID-editor',
            'path': [
                0,
                0
            ],
            'table': {
                'rows': 2,
                'types': [
                    'int64',
                    'large_string'
                ],
                'columns': {
                    'qty': [
                        1,
                        2
                    ],
                    'label': [
                        'a',
                        'b'
                    ]
                }
            }
        },
        {
            'kind': 'dataframe',
            'editing': 0,
            'id': '',
            'path': [
                0,
                1
            ],
            'table': {
                'rows': 3,
                'types': [
                    'int64',
                    'large_string'
                ],
                'columns': {
                    'qty': [
                        7,
                        2,
                        9
                    ],
                    'label': [
                        'a',
                        'b',
                        None
                    ]
                }
            }
        },
        {
            'kind': 'markdown',
            'body': 'rows=3',
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

DATAEDITOR_DOMS = {
    '01-load': {
        'cells': [
            '1',
            'a',
            '2',
            'b',
            '0',
            '1',
            'a',
            '1',
            '2',
            'b'
        ],
        'markdowns': [
            'rows=2'
        ],
        'exceptions': []
    },
    '02-edit-cell': {
        'cells': [
            '7',
            'a',
            '2',
            'b',
            '0',
            '7',
            'a',
            '1',
            '2',
            'b'
        ],
        'markdowns': [
            'rows=2'
        ],
        'exceptions': []
    },
    '03-add-row': {
        'cells': [
            '7',
            'a',
            '2',
            'b',
            '',
            '',
            '0',
            '7',
            'a',
            '1',
            '2',
            'b',
            '2',
            '',
            ''
        ],
        'markdowns': [
            'rows=3'
        ],
        'exceptions': []
    },
    '04-edit-added-row': {
        'cells': [
            '7',
            'a',
            '2',
            'b',
            '9',
            '',
            '0',
            '7',
            'a',
            '1',
            '2',
            'b',
            '2',
            '9',
            ''
        ],
        'markdowns': [
            'rows=3'
        ],
        'exceptions': []
    }
}

DATAEDITOR_SOURCE_FILES = {
    "python": "tests/reference/dataeditor_app.py",
    "native": "streamlit/examples/dataeditor.rs",
}

DATAEDITOR_REQUIRED = (
    "contract", "stage_set", "timeline", "dom_projection",
    "finishes", "png_sources",
)

ID_RE = re.compile(r"\$\$ID-[0-9a-f]{32}-")
NORM_ID = "$$ID-"


def masked(text):
    return ID_RE.sub(NORM_ID, text)


def table_of(delta):
    """The logical table: schema type strings plus column values, so the
    two sides compare by content while their IPC byte padding may differ."""
    import pyarrow.ipc

    dataframe = (delta.get("element_full") or {}).get("dataframe") or {}
    arrow = dataframe.get("arrowData") or {}
    raw = base64.b64decode(arrow.get("data") or "")
    table = pyarrow.ipc.open_stream(io.BytesIO(raw)).read_all()
    return {
        "rows": table.num_rows,
        "types": [str(kind) for kind in table.schema.types],
        "columns": {name: table.column(name).to_pylist() for name in table.column_names},
    }


def _record(checks, name, ok, expected, actual):
    checks.append({"step": DATAEDITOR_CASE, "check": name, "expected": expected, "actual": actual, "ok": bool(ok)})


def _need(condition, message):
    if not condition:
        raise ValueError(message)


def _timeline(stage):
    """The stage's normalized frames; the Rust runtime used to re-announce
    the main container at [0] and old evidence may still carry it."""
    out = []
    for frame in stage.get("new_frames") or []:
        summary = frame.get("summary") or {}
        kind = summary.get("type")
        if kind == "delta":
            delta = summary.get("delta") or {}
            inner = delta.get("type")
            _need(inner in ("new_element", "add_block"), f"unexpected delta kind {inner!r}")
            if inner == "add_block":
                if (delta.get("path") or None) == [0] and (delta.get("block") or {}).get("id") == "main_container":
                    continue
                _need(False, f"unexpected block {sorted(delta.get('block') or {})}")
            name = delta.get("element")
            if name == "dataframe":
                full = delta.get("element_full")
                _need(isinstance(full, dict), "the dataframe delta lacks its full element")
                dataframe = full.get("dataframe") or {}
                out.append({
                    "kind": "dataframe",
                    "editing": dataframe.get("editingMode", 0),
                    "id": masked(dataframe.get("id") or ""),
                    "path": delta.get("path"),
                    "table": table_of(delta),
                })
            elif name == "markdown":
                full = delta.get("element_full") or {}
                body = (full.get("markdown") or {}).get("body")
                _need(body is not None, "the markdown delta lacks its body")
                out.append({"kind": "markdown", "body": body, "path": delta.get("path")})
            else:
                _need(False, f"unexpected element {name!r}")
        elif kind == "rerun_script":
            states = (summary.get("rerun_script") or {}).get("widget_states") or []
            out.append({
                "kind": "rerun",
                "states": [{"id": masked(state.get("id") or ""), "value_field": state.get("value_field"), "value": state.get("value")} for state in states],
            })
        elif kind in ("new_session", "session_status_changed", "script_finished"):
            out.append({"kind": kind})
        else:
            _need(False, f"unexpected frame kind {kind!r}")
    return out


def dataeditor_checks(*, observation=None):
    checks = []
    verified = set()

    def mark(name):
        verified.add(name)
        _record(checks, name, True, "the measured 1.66.1 data_editor wire", "contract verified")

    def fail(name, actual):
        _record(checks, name, False, "the measured 1.66.1 data_editor wire", str(actual))

    try:
        _need(isinstance(observation, dict), "observation must be a dict")
        _need(observation.get("journey") == DATAEDITOR_CASE and observation.get("contract") == DATAEDITOR_CONTRACT,
              "missing versioned dataeditor contract identity")
        _need(bool(observation.get("scope")) and bool(observation.get("url")), "missing scope/url")
        mark("contract")

        stages = observation.get("stages")
        _need(isinstance(stages, list) and tuple(s.get("name") for s in stages) == tuple(DATAEDITOR_STAGES),
              f"stages must be exactly the {len(DATAEDITOR_STAGES)} measured stages in order")
        for stage in stages:
            _need(isinstance(stage.get("dom"), dict) and isinstance(stage.get("screenshot"), dict)
                  and isinstance(stage.get("new_frames"), list), f"stage {stage.get('name')} lacks dom/screenshot/new_frames")
        mark("stage_set")

        timelines = {stage["name"]: _timeline(stage) for stage in stages}
        for name in DATAEDITOR_STAGES:
            _need(timelines[name] == DATAEDITOR_TIMELINE[name],
                  f"stage {name} frame timeline differs from the measured wire ({len(timelines[name])} frames)")
        mark("timeline")

        for stage in stages:
            name = stage["name"]
            _need({key: (stage["dom"] or {}).get(key) for key in DATAEDITOR_DOMS[name]} == DATAEDITOR_DOMS[name],
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
        for name in DATAEDITOR_REQUIRED:
            if name not in verified:
                fail(name, str(exc))
        return checks
    return checks


def dataeditor_result(*, observation=None):
    """Aggregate the contract checks the way the shared journey judge does."""
    checks = dataeditor_checks(observation=observation)
    failures = [check for check in checks if not check["ok"]]
    return {
        "checks": checks,
        "counts": {"expected": len(checks), "executed": len(checks), "asserted": len(checks) - len(failures)},
        "failures": failures,
        "ok": not failures and len(checks) == len(DATAEDITOR_REQUIRED),
    }
