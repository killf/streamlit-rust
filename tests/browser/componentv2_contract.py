"""The strict components.v2 contract: journey-componentv2-v1.

This criterion judges the observation the committed collector
(componentv2_capture.py) writes, against the Python 1.66.1 wire measured on
2026-10-27 with the official frontend and recorded in .codex/compatibility.md
(Custom components): one registered st.components.v2.component (inline
HTML/CSS/JS, isolated styles) mounted once with a JSON data payload and a
default state. The element carries the instance's widget id
($$ID-<digest>-<key>; the digest is side-specific and masked), the trusted
content strings and the json.dumps-default-separator payload at stretch
width and content height. The run finishes FINISHED_SUCCESSFULLY and the
settled DOM shows the isolated component mount plus the state markdown.
Unbounded leading main-container add_blocks at [0] are the Rust runtime's
documented divergence.
"""

from __future__ import annotations

import hashlib
import json
import pathlib
import re

COMPONENTV2_CASE = "componentv2-page"
COMPONENTV2_CONTRACT = "journey-componentv2-v1"

COMPONENTV2_STAGES = [
    '01-load'
]

COMPONENTV2_TIMELINE = {
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
            'kind': 'bidi_component',
            'element_full': {
                'heightConfig': {
                    'useContent': True
                },
                'widthConfig': {
                    'useStretch': True
                },
                'bidiComponent': {
                    'id': '$$ID-greeter',
                    'componentName': 'greeting',
                    'jsContent': "\n    export default function(component) {\n        const { setStateValue, parentElement } = component;\n        const input = parentElement.querySelector('input');\n        input.onkeydown = (e) => {\n            if (e.key === 'Enter') {\n                setStateValue('value', e.target.value);\n            }\n        };\n    }\n",
                    'jsSourcePath': '',
                    'htmlContent': "\n    <label style='padding-right: 1em;' for='txt'>Enter text</label>\n    <input id='txt' type='text' />\n",
                    'cssContent': 'label { color: red; }',
                    'cssSourcePath': '',
                    'isolateStyles': True,
                    'json': '{"label": "Name", "value": "hi"}'
                }
            },
            'path': [
                0,
                0
            ]
        },
        {
            'kind': 'markdown',
            'element_full': {
                'markdown': {
                    'body': 'value=hi',
                    'elementType': 'NATIVE',
                    'wrap': True
                },
                'textAlignmentConfig': {
                    'alignment': 'LEFT'
                }
            },
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

COMPONENTV2_DOMS = {
    '01-load': {
        'testids': [
            'portal',
            'stApp',
            'stAppDeployButton',
            'stAppIframeResizerAnchor',
            'stAppViewContainer',
            'stBaseButton-header',
            'stBidiComponentIsolated',
            'stElementContainer',
            'stHeader',
            'stMain',
            'stMainBlockContainer',
            'stMainMenu',
            'stMainMenuButton',
            'stMarkdown',
            'stMarkdownContainer',
            'stScreencast',
            'stSkipToContent',
            'stToolbar',
            'stToolbarActions',
            'stVerticalBlock'
        ],
        'exceptions': [],
        'markdowns': [
            'value=hi'
        ]
    }
}

COMPONENTV2_SOURCE_FILES = {
    "python": "tests/reference/componentv2_app.py",
    "native": "streamlit/examples/componentv2.rs",
}

COMPONENTV2_REQUIRED = (
    "contract", "stage_set", "timeline", "dom_projection",
    "finishes", "png_sources",
)

ID_RE = re.compile(r"\$\$ID-[0-9a-f]{32}-")
NORM_ID = "$$ID-"


def normalize_element(full):
    """Mask the side-specific $$ID digests; everything else compares
    verbatim."""
    return json.loads(ID_RE.sub(NORM_ID, json.dumps(full)))


def _record(checks, name, ok, expected, actual):
    checks.append({"step": COMPONENTV2_CASE, "check": name, "expected": expected, "actual": actual, "ok": bool(ok)})


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
            if name in ("bidi_component", "markdown"):
                full = delta.get("element_full")
                _need(isinstance(full, dict), f"the {name} delta lacks its full element")
                out.append({"kind": name, "element_full": normalize_element(full), "path": delta.get("path")})
            else:
                _need(False, f"unexpected element {name!r}")
        elif kind == "rerun_script":
            out.append({"kind": "rerun"})
        elif kind in ("new_session", "session_status_changed", "script_finished"):
            out.append({"kind": kind})
        else:
            _need(False, f"unexpected frame kind {kind!r}")
    return out


def componentv2_checks(*, observation=None):
    checks = []
    verified = set()

    def mark(name):
        verified.add(name)
        _record(checks, name, True, "the measured 1.66.1 components.v2 wire", "contract verified")

    def fail(name, actual):
        _record(checks, name, False, "the measured 1.66.1 components.v2 wire", str(actual))

    try:
        _need(isinstance(observation, dict), "observation must be a dict")
        _need(observation.get("journey") == COMPONENTV2_CASE and observation.get("contract") == COMPONENTV2_CONTRACT,
              "missing versioned componentv2 contract identity")
        _need(bool(observation.get("scope")) and bool(observation.get("url")), "missing scope/url")
        mark("contract")

        stages = observation.get("stages")
        _need(isinstance(stages, list) and tuple(s.get("name") for s in stages) == tuple(COMPONENTV2_STAGES),
              f"stages must be exactly the {len(COMPONENTV2_STAGES)} measured stages in order")
        for stage in stages:
            _need(isinstance(stage.get("dom"), dict) and isinstance(stage.get("screenshot"), dict)
                  and isinstance(stage.get("new_frames"), list), f"stage {stage.get('name')} lacks dom/screenshot/new_frames")
        mark("stage_set")

        timelines = {stage["name"]: _timeline(stage) for stage in stages}
        for name in COMPONENTV2_STAGES:
            _need(timelines[name] == COMPONENTV2_TIMELINE[name],
                  f"stage {name} frame timeline differs from the measured wire ({len(timelines[name])} frames)")
        mark("timeline")

        for stage in stages:
            name = stage["name"]
            _need({key: (stage["dom"] or {}).get(key) for key in COMPONENTV2_DOMS[name]} == COMPONENTV2_DOMS[name],
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
        for name in COMPONENTV2_REQUIRED:
            if name not in verified:
                fail(name, str(exc))
        return checks
    return checks


def componentv2_result(*, observation=None):
    """Aggregate the contract checks the way the shared journey judge does."""
    checks = componentv2_checks(observation=observation)
    failures = [check for check in checks if not check["ok"]]
    return {
        "checks": checks,
        "counts": {"expected": len(checks), "executed": len(checks), "asserted": len(checks) - len(failures)},
        "failures": failures,
        "ok": not failures and len(checks) == len(COMPONENTV2_REQUIRED),
    }
