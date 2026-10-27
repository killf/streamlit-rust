"""The strict components.v2 trigger contract: journey-componenttrigger-v1.

This criterion judges the observation the committed collector
(componenttrigger_capture.py) writes, against the Python 1.66.1 wire
measured on 2026-10-27 with the official frontend and recorded in
.codex/compatibility.md (Custom components): one registered inline
component whose JS fires setTriggerValue("ping", {count}) from a real
button click inside the isolated shadow root. Every fire sends exactly one
internal json_trigger_value state on
$$STREAMLIT_INTERNAL_KEY_$$ID-<digest>-triggers__events (the digest is
side-specific and masked), its value the JSON array string of the fired
{"event", "value"} payloads; each run re-emits the bidi_component element
and the surfaced trigger value markdown, and the value is fresh per run
(count=1, then count=2) with null before the first fire. Unbounded leading
main-container add_blocks at [0] are the Rust runtime's documented
divergence.
"""

from __future__ import annotations

import hashlib
import json
import pathlib
import re

COMPONENTTRIGGER_CASE = "componenttrigger-page"
COMPONENTTRIGGER_CONTRACT = "journey-componenttrigger-v1"

COMPONENTTRIGGER_STAGES = [
    '01-load',
    '02-click-fire',
    '03-click-again'
]

COMPONENTTRIGGER_TIMELINE = {
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
            'kind': 'bidi_component',
            'element_full': {
                'heightConfig': {
                    'useContent': True
                },
                'widthConfig': {
                    'useStretch': True
                },
                'bidiComponent': {
                    'id': '$$ID-triggers',
                    'componentName': 'trigger_demo',
                    'jsContent': "\n    export default function(component) {\n        const { parentElement, setTriggerValue } = component;\n        const button = parentElement.querySelector('button');\n        let count = 0;\n        button.onclick = () => {\n            count += 1;\n            setTriggerValue('ping', { count });\n        };\n    }\n",
                    'jsSourcePath': '',
                    'htmlContent': "<button id='fire' type='button'>Fire</button>",
                    'cssContent': 'button { color: red; }',
                    'cssSourcePath': '',
                    'isolateStyles': True
                }
            },
            'path': [
                0,
                0
            ]
        },
        {
            'kind': 'markdown',
            'body': 'ping=null',
            'path': [
                0,
                1
            ]
        },
        {
            'kind': 'script_finished'
        },
        {
            'kind': 'session_status_changed'
        }
    ],
    '02-click-fire': [
        {
            'kind': 'rerun',
            'states': [
                {
                    'id': '$$STREAMLIT_INTERNAL_KEY_$$ID-triggers__events',
                    'value_field': 'json_trigger_value',
                    'value': '[{"event":"ping","value":{"count":1}}]'
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
            'kind': 'bidi_component',
            'element_full': {
                'heightConfig': {
                    'useContent': True
                },
                'widthConfig': {
                    'useStretch': True
                },
                'bidiComponent': {
                    'id': '$$ID-triggers',
                    'componentName': 'trigger_demo',
                    'jsContent': "\n    export default function(component) {\n        const { parentElement, setTriggerValue } = component;\n        const button = parentElement.querySelector('button');\n        let count = 0;\n        button.onclick = () => {\n            count += 1;\n            setTriggerValue('ping', { count });\n        };\n    }\n",
                    'jsSourcePath': '',
                    'htmlContent': "<button id='fire' type='button'>Fire</button>",
                    'cssContent': 'button { color: red; }',
                    'cssSourcePath': '',
                    'isolateStyles': True
                }
            },
            'path': [
                0,
                0
            ]
        },
        {
            'kind': 'markdown',
            'body': 'ping={"count": 1}',
            'path': [
                0,
                1
            ]
        },
        {
            'kind': 'script_finished'
        },
        {
            'kind': 'session_status_changed'
        }
    ],
    '03-click-again': [
        {
            'kind': 'rerun',
            'states': [
                {
                    'id': '$$STREAMLIT_INTERNAL_KEY_$$ID-triggers__events',
                    'value_field': 'json_trigger_value',
                    'value': '[{"event":"ping","value":{"count":2}}]'
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
            'kind': 'bidi_component',
            'element_full': {
                'heightConfig': {
                    'useContent': True
                },
                'widthConfig': {
                    'useStretch': True
                },
                'bidiComponent': {
                    'id': '$$ID-triggers',
                    'componentName': 'trigger_demo',
                    'jsContent': "\n    export default function(component) {\n        const { parentElement, setTriggerValue } = component;\n        const button = parentElement.querySelector('button');\n        let count = 0;\n        button.onclick = () => {\n            count += 1;\n            setTriggerValue('ping', { count });\n        };\n    }\n",
                    'jsSourcePath': '',
                    'htmlContent': "<button id='fire' type='button'>Fire</button>",
                    'cssContent': 'button { color: red; }',
                    'cssSourcePath': '',
                    'isolateStyles': True
                }
            },
            'path': [
                0,
                0
            ]
        },
        {
            'kind': 'markdown',
            'body': 'ping={"count": 2}',
            'path': [
                0,
                1
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

COMPONENTTRIGGER_DOMS = {
    '01-load': {
        'markdowns': [
            'ping=null'
        ],
        'buttons': [
            'Deploy',
            ''
        ],
        'exceptions': []
    },
    '02-click-fire': {
        'markdowns': [
            'ping={"count": 1}'
        ],
        'buttons': [
            'Deploy',
            ''
        ],
        'exceptions': []
    },
    '03-click-again': {
        'markdowns': [
            'ping={"count": 2}'
        ],
        'buttons': [
            'Deploy',
            ''
        ],
        'exceptions': []
    }
}

COMPONENTTRIGGER_SOURCE_FILES = {
    "python": "tests/reference/componenttrigger_app.py",
    "native": "streamlit/examples/componenttrigger.rs",
}

COMPONENTTRIGGER_REQUIRED = (
    "contract", "stage_set", "timeline", "dom_projection",
    "finishes", "png_sources",
)

ID_RE = re.compile(r"\$\$ID-[0-9a-f]{32}-")
NORM_ID = "$$ID-"


def masked(payload):
    return json.loads(ID_RE.sub(NORM_ID, json.dumps(payload)))


def _record(checks, name, ok, expected, actual):
    checks.append({"step": COMPONENTTRIGGER_CASE, "check": name, "expected": expected, "actual": actual, "ok": bool(ok)})


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
            if name in ("bidi_component", "markdown"):
                full = delta.get("element_full")
                _need(isinstance(full, dict), f"the {name} delta lacks its full element")
                if name == "markdown":
                    body = (full.get("markdown") or {}).get("body")
                    _need(body is not None, "the markdown delta lacks its body")
                    out.append({"kind": "markdown", "body": body, "path": delta.get("path")})
                else:
                    out.append({"kind": name, "element_full": masked(full), "path": delta.get("path")})
            else:
                _need(False, f"unexpected element {name!r}")
        elif kind == "rerun_script":
            states = (summary.get("rerun_script") or {}).get("widget_states") or []
            out.append({"kind": "rerun", "states": masked(states)})
        elif kind in ("new_session", "session_status_changed", "script_finished"):
            out.append({"kind": kind})
        else:
            _need(False, f"unexpected frame kind {kind!r}")
    return out


def componenttrigger_checks(*, observation=None):
    checks = []
    verified = set()

    def mark(name):
        verified.add(name)
        _record(checks, name, True, "the measured 1.66.1 components.v2 trigger wire", "contract verified")

    def fail(name, actual):
        _record(checks, name, False, "the measured 1.66.1 components.v2 trigger wire", str(actual))

    try:
        _need(isinstance(observation, dict), "observation must be a dict")
        _need(observation.get("journey") == COMPONENTTRIGGER_CASE and observation.get("contract") == COMPONENTTRIGGER_CONTRACT,
              "missing versioned componenttrigger contract identity")
        _need(bool(observation.get("scope")) and bool(observation.get("url")), "missing scope/url")
        mark("contract")

        stages = observation.get("stages")
        _need(isinstance(stages, list) and tuple(s.get("name") for s in stages) == tuple(COMPONENTTRIGGER_STAGES),
              f"stages must be exactly the {len(COMPONENTTRIGGER_STAGES)} measured stages in order")
        for stage in stages:
            _need(isinstance(stage.get("dom"), dict) and isinstance(stage.get("screenshot"), dict)
                  and isinstance(stage.get("new_frames"), list), f"stage {stage.get('name')} lacks dom/screenshot/new_frames")
        mark("stage_set")

        timelines = {stage["name"]: _timeline(stage) for stage in stages}
        for name in COMPONENTTRIGGER_STAGES:
            _need(timelines[name] == COMPONENTTRIGGER_TIMELINE[name],
                  f"stage {name} frame timeline differs from the measured wire ({len(timelines[name])} frames)")
        mark("timeline")

        for stage in stages:
            name = stage["name"]
            _need({key: (stage["dom"] or {}).get(key) for key in COMPONENTTRIGGER_DOMS[name]} == COMPONENTTRIGGER_DOMS[name],
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
        for name in COMPONENTTRIGGER_REQUIRED:
            if name not in verified:
                fail(name, str(exc))
        return checks
    return checks


def componenttrigger_result(*, observation=None):
    """Aggregate the contract checks the way the shared journey judge does."""
    checks = componenttrigger_checks(observation=observation)
    failures = [check for check in checks if not check["ok"]]
    return {
        "checks": checks,
        "counts": {"expected": len(checks), "executed": len(checks), "asserted": len(checks) - len(failures)},
        "failures": failures,
        "ok": not failures and len(checks) == len(COMPONENTTRIGGER_REQUIRED),
    }
