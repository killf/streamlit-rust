"""The strict query-params contract: journey-queryparams-v1.

This criterion judges the observation the committed collector
(queryparams_capture.py) writes, against the Python 1.66.1 wire measured on
2026-10-26 with the official frontend and recorded in .codex/compatibility.md
(Query params). The collector states no verdict; this module owns it:

* exactly one page_info_changed{query_string} per run, between the running
  status and the first delta, merged with the browser-reported URL state
  and serialized in key insertion order with repeated values;
* the creation-mode selectbox carries acceptNewOptions true plus the
  measured filter mode and keeps a freshly typed value as its string state;
  the bound selectbox carries queryParamKey with acceptNewOptions false;
* the browser reports ClientState.query_string with every rerun, and the
  bound pick updates the URL (?bound=y&mode=demo);
* the settled DOM shows the URL query string and the markdown echoes, no
  exception, each run finishing FINISHED_SUCCESSFULLY.

Widget ids are judged modulo the $$ID digest segment; at most one leading
main-container add_block at [0] is the Rust runtime's documented divergence.
"""

from __future__ import annotations

import hashlib
import json
import pathlib
import re

QUERYPARAMS_CASE = "queryparams-page"
QUERYPARAMS_CONTRACT = "journey-queryparams-v1"

QUERYPARAMS_STAGES = [
    '01-load',
    '02-new-option',
    '03-bound-pick'
]

# Per stage: the normalized frame timeline, the two selectbox elements, the
# page_info payload, the rerun report and the DOM projection.
QUERYPARAMS_TIMELINE = {
    '01-load': [
        {
            'kind': 'rerun',
            'query_string': None,
            'widget_states': []
        },
        {
            'kind': 'new_session'
        },
        {
            'kind': 'session_status_changed'
        },
        {
            'kind': 'page_info',
            'query_string': 'mode=demo'
        },
        {
            'kind': 'selectbox',
            'selectbox': {
                'id': '$$ID-None',
                'label': 'Pick',
                'default': 0,
                'options': [
                    'a',
                    'b'
                ],
                'labelVisibility': {},
                'acceptNewOptions': True,
                'filterMode': 'FILTER_MODE_CONTAINS'
            }
        },
        {
            'kind': 'markdown',
            'path': [
                0,
                1
            ],
            'body': 'pick=a'
        },
        {
            'kind': 'selectbox',
            'selectbox': {
                'id': '$$ID-bound',
                'label': 'Bound',
                'default': 0,
                'options': [
                    'x',
                    'y'
                ],
                'labelVisibility': {},
                'acceptNewOptions': False,
                'queryParamKey': 'bound'
            }
        },
        {
            'kind': 'markdown',
            'path': [
                0,
                3
            ],
            'body': 'bound=x'
        },
        {
            'kind': 'script_finished'
        },
        {
            'kind': 'session_status_changed'
        }
    ],
    '02-new-option': [
        {
            'kind': 'rerun',
            'query_string': 'mode=demo',
            'widget_states': [
                {
                    'id': '$$ID-None',
                    'value_field': 'string_value',
                    'value': 'c'
                },
                {
                    'id': '$$ID-bound',
                    'value_field': 'string_value',
                    'value': 'x'
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
            'kind': 'page_info',
            'query_string': 'mode=demo'
        },
        {
            'kind': 'selectbox',
            'selectbox': {
                'id': '$$ID-None',
                'label': 'Pick',
                'default': 0,
                'options': [
                    'a',
                    'b'
                ],
                'labelVisibility': {},
                'acceptNewOptions': True,
                'filterMode': 'FILTER_MODE_CONTAINS'
            }
        },
        {
            'kind': 'markdown',
            'path': [
                0,
                1
            ],
            'body': 'pick=c'
        },
        {
            'kind': 'selectbox',
            'selectbox': {
                'id': '$$ID-bound',
                'label': 'Bound',
                'default': 0,
                'options': [
                    'x',
                    'y'
                ],
                'labelVisibility': {},
                'acceptNewOptions': False,
                'queryParamKey': 'bound'
            }
        },
        {
            'kind': 'markdown',
            'path': [
                0,
                3
            ],
            'body': 'bound=x'
        },
        {
            'kind': 'script_finished'
        },
        {
            'kind': 'session_status_changed'
        }
    ],
    '03-bound-pick': [
        {
            'kind': 'rerun',
            'query_string': 'bound=y&mode=demo',
            'widget_states': [
                {
                    'id': '$$ID-None',
                    'value_field': 'string_value',
                    'value': 'c'
                },
                {
                    'id': '$$ID-bound',
                    'value_field': 'string_value',
                    'value': 'y'
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
            'kind': 'page_info',
            'query_string': 'bound=y&mode=demo'
        },
        {
            'kind': 'selectbox',
            'selectbox': {
                'id': '$$ID-None',
                'label': 'Pick',
                'default': 0,
                'options': [
                    'a',
                    'b'
                ],
                'labelVisibility': {},
                'acceptNewOptions': True,
                'filterMode': 'FILTER_MODE_CONTAINS'
            }
        },
        {
            'kind': 'markdown',
            'path': [
                0,
                1
            ],
            'body': 'pick=c'
        },
        {
            'kind': 'selectbox',
            'selectbox': {
                'id': '$$ID-bound',
                'label': 'Bound',
                'default': 0,
                'options': [
                    'x',
                    'y'
                ],
                'labelVisibility': {},
                'acceptNewOptions': False,
                'queryParamKey': 'bound'
            }
        },
        {
            'kind': 'markdown',
            'path': [
                0,
                3
            ],
            'body': 'bound=y'
        },
        {
            'kind': 'script_finished'
        },
        {
            'kind': 'session_status_changed'
        }
    ]
}

QUERYPARAMS_SELECTBOXES = {
    '01-load': [
        {
            'id': '$$ID-None',
            'label': 'Pick',
            'default': 0,
            'options': [
                'a',
                'b'
            ],
            'labelVisibility': {},
            'acceptNewOptions': True,
            'filterMode': 'FILTER_MODE_CONTAINS'
        },
        {
            'id': '$$ID-bound',
            'label': 'Bound',
            'default': 0,
            'options': [
                'x',
                'y'
            ],
            'labelVisibility': {},
            'acceptNewOptions': False,
            'queryParamKey': 'bound'
        }
    ],
    '02-new-option': [
        {
            'id': '$$ID-None',
            'label': 'Pick',
            'default': 0,
            'options': [
                'a',
                'b'
            ],
            'labelVisibility': {},
            'acceptNewOptions': True,
            'filterMode': 'FILTER_MODE_CONTAINS'
        },
        {
            'id': '$$ID-bound',
            'label': 'Bound',
            'default': 0,
            'options': [
                'x',
                'y'
            ],
            'labelVisibility': {},
            'acceptNewOptions': False,
            'queryParamKey': 'bound'
        }
    ],
    '03-bound-pick': [
        {
            'id': '$$ID-None',
            'label': 'Pick',
            'default': 0,
            'options': [
                'a',
                'b'
            ],
            'labelVisibility': {},
            'acceptNewOptions': True,
            'filterMode': 'FILTER_MODE_CONTAINS'
        },
        {
            'id': '$$ID-bound',
            'label': 'Bound',
            'default': 0,
            'options': [
                'x',
                'y'
            ],
            'labelVisibility': {},
            'acceptNewOptions': False,
            'queryParamKey': 'bound'
        }
    ]
}

QUERYPARAMS_PAGE_INFOS = {
    '01-load': {
        'kind': 'page_info',
        'query_string': 'mode=demo'
    },
    '02-new-option': {
        'kind': 'page_info',
        'query_string': 'mode=demo'
    },
    '03-bound-pick': {
        'kind': 'page_info',
        'query_string': 'bound=y&mode=demo'
    }
}

QUERYPARAMS_RERUNS = {
    '01-load': {
        'kind': 'rerun',
        'query_string': None,
        'widget_states': []
    },
    '02-new-option': {
        'kind': 'rerun',
        'query_string': 'mode=demo',
        'widget_states': [
            {
                'id': '$$ID-None',
                'value_field': 'string_value',
                'value': 'c'
            },
            {
                'id': '$$ID-bound',
                'value_field': 'string_value',
                'value': 'x'
            }
        ]
    },
    '03-bound-pick': {
        'kind': 'rerun',
        'query_string': 'bound=y&mode=demo',
        'widget_states': [
            {
                'id': '$$ID-None',
                'value_field': 'string_value',
                'value': 'c'
            },
            {
                'id': '$$ID-bound',
                'value_field': 'string_value',
                'value': 'y'
            }
        ]
    }
}

QUERYPARAMS_DOMS = {
    '01-load': {
        'url': '?mode=demo',
        'markdowns': [
            'pick=a',
            'bound=x'
        ],
        'exceptions': []
    },
    '02-new-option': {
        'url': '?mode=demo',
        'markdowns': [
            'pick=c',
            'bound=x'
        ],
        'exceptions': []
    },
    '03-bound-pick': {
        'url': '?bound=y&mode=demo',
        'markdowns': [
            'pick=c',
            'bound=y'
        ],
        'exceptions': []
    }
}

QUERYPARAMS_SOURCE_FILES = {
    "python": "tests/reference/queryparams_app.py",
    "native": "streamlit/examples/queryparams.rs",
}

QUERYPARAMS_REQUIRED = (
    "contract", "stage_set", "timeline", "query_wire",
    "selectbox_wire", "state_wire", "dom_projection", "no_exceptions",
    "finishes", "png_sources",
)

_ID_SUB = re.compile(r"\$\$ID-[0-9a-f]{32}-")


def _record(checks, name, ok, expected, actual):
    checks.append({"step": QUERYPARAMS_CASE, "check": name, "expected": expected, "actual": actual, "ok": bool(ok)})


def _need(condition, message):
    if not condition:
        raise ValueError(message)


def _normalize_selectbox(select):
    return json.loads(_ID_SUB.sub("$$ID-", json.dumps(select, ensure_ascii=False)))


def _timeline(stage):
    """The stage's normalized frames, the optional leading main container
    peeled off (the Rust side emits exactly one, the reference none)."""
    out = []
    stripped = 0
    for frame in stage.get("new_frames") or []:
        summary = frame.get("summary") or {}
        kind = summary.get("type")
        if kind == "delta":
            delta = summary.get("delta") or {}
            inner = delta.get("type")
            _need(inner in ("new_element", "add_block", "new_transient"), f"unexpected delta kind {inner!r}")
            if inner == "add_block" and (delta.get("path") or None) == [0] and (delta.get("block") or {}).get("id") == "main_container":
                stripped += 1
                _need(stripped <= 1, "more than one leading main-container block")
                continue
            if delta.get("element") == "selectbox":
                select = (delta.get("element_full") or {}).get("selectbox")
                _need(select is not None, "selectbox delta lacks its full element")
                out.append({"kind": "selectbox", "selectbox": _normalize_selectbox(select)})
            elif inner == "new_element":
                out.append({"kind": delta.get("element"), "path": delta.get("path"), "body": delta.get("body")})
            else:
                out.append({"kind": inner})
        elif kind == "page_info_changed":
            out.append({"kind": "page_info", "query_string": (summary.get("page_info") or {}).get("query_string")})
        elif kind == "rerun_script":
            rerun = summary.get("rerun_script") or {}
            states = [{**state, "id": _ID_SUB.sub("$$ID-", state.get("id") or "")} for state in rerun.get("widget_states") or []]
            out.append({"kind": "rerun", "query_string": rerun.get("query_string"), "widget_states": states})
        elif kind in ("new_session", "session_status_changed", "script_finished"):
            out.append({"kind": kind})
        else:
            _need(False, f"unexpected frame kind {kind!r}")
    return out


def queryparams_checks(*, observation=None):
    checks = []
    verified = set()

    def mark(name):
        verified.add(name)
        _record(checks, name, True, "the measured 1.66.1 query-params wire", "contract verified")

    def fail(name, actual):
        _record(checks, name, False, "the measured 1.66.1 query-params wire", str(actual))

    try:
        _need(isinstance(observation, dict), "observation must be a dict")
        _need(observation.get("journey") == QUERYPARAMS_CASE and observation.get("contract") == QUERYPARAMS_CONTRACT,
              "missing versioned query-params contract identity")
        _need(bool(observation.get("scope")) and bool(observation.get("url")), "missing scope/url")
        mark("contract")

        stages = observation.get("stages")
        _need(isinstance(stages, list) and tuple(s.get("name") for s in stages) == tuple(QUERYPARAMS_STAGES),
              f"stages must be exactly the {len(QUERYPARAMS_STAGES)} measured stages in order")
        for stage in stages:
            _need(isinstance(stage.get("dom"), dict) and isinstance(stage.get("screenshot"), dict)
                  and isinstance(stage.get("new_frames"), list), f"stage {stage.get('name')} lacks dom/screenshot/new_frames")
        mark("stage_set")

        timelines = {stage["name"]: _timeline(stage) for stage in stages}
        for name in QUERYPARAMS_STAGES:
            _need(timelines[name] == QUERYPARAMS_TIMELINE[name],
                  f"stage {name} frame timeline differs from the measured wire ({len(timelines[name])} frames)")
        mark("timeline")

        for name in QUERYPARAMS_STAGES:
            frames = timelines[name]
            infos = [frame for frame in frames if frame["kind"] == "page_info"]
            _need(len(infos) == 1, f"stage {name} must stream exactly one page_info_changed, got {len(infos)}")
            _need(infos[0] == QUERYPARAMS_PAGE_INFOS[name], f"stage {name} page_info payload differs from the measured wire")
            first_element = next(index for index, frame in enumerate(frames) if frame["kind"] in ("selectbox", "markdown"))
            info_at = next(index for index, frame in enumerate(frames) if frame["kind"] == "page_info")
            running = [index for index, frame in enumerate(frames) if frame["kind"] == "session_status_changed"]
            _need(info_at < first_element, f"stage {name} page_info must stream before the first element")
            _need(any(index < info_at for index in running), f"stage {name} page_info must follow the running status")
        mark("query_wire")

        for name in QUERYPARAMS_STAGES:
            boxes = [frame["selectbox"] for frame in timelines[name] if frame["kind"] == "selectbox"]
            _need(len(boxes) == 2, f"stage {name} must carry exactly two selectbox elements, got {len(boxes)}")
            _need(boxes == QUERYPARAMS_SELECTBOXES[name],
                  f"stage {name} selectbox elements differ from the measured wire")
        mark("selectbox_wire")

        for name in QUERYPARAMS_STAGES:
            reruns = [frame for frame in timelines[name] if frame["kind"] == "rerun"]
            _need(len(reruns) == 1, f"stage {name} must carry exactly one rerun report, got {len(reruns)}")
            expected = {"kind": "rerun", **QUERYPARAMS_RERUNS[name]}
            _need(reruns[0] == expected, f"stage {name} rerun query_string/widget_states differ from the measured wire")
        mark("state_wire")

        for stage in stages:
            name = stage["name"]
            _need({key: (stage["dom"] or {}).get(key) for key in QUERYPARAMS_DOMS[name]} == QUERYPARAMS_DOMS[name],
                  f"stage {name} resolved DOM projection differs from the measured page")
        mark("dom_projection")

        for stage in stages:
            _need(not ((stage["dom"] or {}).get("exceptions") or []), f"stage {stage['name']} renders an exception")
            for frame in stage["new_frames"]:
                delta = (frame.get("summary") or {}).get("delta") or {}
                _need(delta.get("element") != "exception", "the stream carries an exception element")
        mark("no_exceptions")

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
        for name in QUERYPARAMS_REQUIRED:
            if name not in verified:
                fail(name, str(exc))
        return checks
    return checks


def queryparams_result(*, observation=None):
    """Aggregate the contract checks the way the shared journey judge does."""
    checks = queryparams_checks(observation=observation)
    failures = [check for check in checks if not check["ok"]]
    return {
        "checks": checks,
        "counts": {"expected": len(checks), "executed": len(checks), "asserted": len(checks) - len(failures)},
        "failures": failures,
        "ok": not failures and len(checks) == len(QUERYPARAMS_REQUIRED),
    }
