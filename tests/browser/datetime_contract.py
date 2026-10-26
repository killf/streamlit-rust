"""The strict datetime-input contract: journey-datetime-v1.

This criterion judges the observation the committed collector
(datetime_capture.py) writes, against the Python 1.66.1 wire measured on
2026-10-26 with the official frontend and recorded in .codex/compatibility.md
(Picker inputs / datetime): a valued st.datetime_input carries its ISO
"YYYY-MM-DDTHH:MM" default, the ten-year min/max window around the value's
date (min at 00:00, max at 23:59), the 15-minute step and the YYYY/MM/DD
display format; a None-valued picker carries no default and anchors its
window on today. Widget ids are judged modulo the $$ID digest segment. The
run still finishes FINISHED_SUCCESSFULLY and the settled DOM shows both
input values (the None picker renders an empty input). Unbounded leading
main-container add_blocks at [0] are the Rust runtime's documented
divergence.
"""

from __future__ import annotations

import hashlib
import json
import pathlib
import re

DATETIME_CASE = "datetime-page"
DATETIME_CONTRACT = "journey-datetime-v1"

DATETIME_STAGES = [
    '01-load'
]

DATETIME_TIMELINE = {
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
            'kind': 'date_time_input',
            'widget': {
                'id': '$$ID-launch',
                'label': 'Launch window',
                'default': [
                    '2025-03-15T14:30'
                ],
                'min': '2015-03-15T00:00',
                'max': '2035-03-15T23:59',
                'labelVisibility': {},
                'format': 'YYYY/MM/DD',
                'step': '900'
            },
            'path': [
                0,
                0
            ]
        },
        {
            'kind': 'date_time_input',
            'widget': {
                'id': '$$ID-slot',
                'label': 'Optional slot',
                'min': '2016-10-26T00:00',
                'max': '2036-10-26T23:59',
                'labelVisibility': {},
                'format': 'YYYY/MM/DD',
                'step': '900'
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

DATETIME_DOMS = {
    '01-load': {
        'datetimeInputs': [
            '2025-03-15T14:30',
            ''
        ],
        'exceptions': []
    }
}

DATETIME_SOURCE_PINS = {
    "python": [
    'tests/reference/datetime_app.py',
    '584879326bf4881286bf1f416d09eb2a2721d77d125b6a368e7f665a506217e0'
],
    "native": [
    'streamlit/examples/datetime.rs',
    'ac35a299e657b862cd39ec65bacc21e586467b098bf6e7df30565ce4dbfb2e48'
],
}

DATETIME_REQUIRED = (
    "contract", "stage_set", "source_pin", "timeline", "dom_projection",
    "finishes", "png_sources",
)

ID_RE = re.compile(r"\$\$ID-[0-9a-f]{32}-")
NORM_ID = "$$ID-"


def _record(checks, name, ok, expected, actual):
    checks.append({"step": DATETIME_CASE, "check": name, "expected": expected, "actual": actual, "ok": bool(ok)})


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
            if name == "date_time_input":
                widget = dict(delta.get("widget") or {})
                _need(widget.get("id"), "the date_time_input widget lacks its id")
                widget["id"] = ID_RE.sub(NORM_ID, widget["id"])
                out.append({"kind": "date_time_input", "widget": widget, "path": delta.get("path")})
            else:
                _need(False, f"unexpected element {name!r}")
        elif kind == "rerun_script":
            out.append({"kind": "rerun"})
        elif kind in ("new_session", "session_status_changed", "script_finished"):
            out.append({"kind": kind})
        else:
            _need(False, f"unexpected frame kind {kind!r}")
    return out


def datetime_checks(*, observation=None):
    checks = []
    verified = set()

    def mark(name):
        verified.add(name)
        _record(checks, name, True, "the measured 1.66.1 datetime-input wire", "contract verified")

    def fail(name, actual):
        _record(checks, name, False, "the measured 1.66.1 datetime-input wire", str(actual))

    try:
        _need(isinstance(observation, dict), "observation must be a dict")
        _need(observation.get("journey") == DATETIME_CASE and observation.get("contract") == DATETIME_CONTRACT,
              "missing versioned datetime contract identity")
        _need(bool(observation.get("scope")) and bool(observation.get("url")), "missing scope/url")
        mark("contract")

        stages = observation.get("stages")
        _need(isinstance(stages, list) and tuple(s.get("name") for s in stages) == tuple(DATETIME_STAGES),
              f"stages must be exactly the {len(DATETIME_STAGES)} measured stages in order")
        for stage in stages:
            _need(isinstance(stage.get("dom"), dict) and isinstance(stage.get("screenshot"), dict)
                  and isinstance(stage.get("new_frames"), list), f"stage {stage.get('name')} lacks dom/screenshot/new_frames")
        mark("stage_set")

        source = observation.get("source") or {}
        side = "python" if observation.get("scope") == "PYTHON SIDE ONLY" else "native"
        path, pinned = DATETIME_SOURCE_PINS[side]
        _need(source.get("file") == path and source.get("sha256") == pinned,
              f"driven source is not the pinned {path} of this contract")
        mark("source_pin")

        timelines = {stage["name"]: _timeline(stage) for stage in stages}
        for name in DATETIME_STAGES:
            _need(timelines[name] == DATETIME_TIMELINE[name],
                  f"stage {name} frame timeline differs from the measured wire ({len(timelines[name])} frames)")
        mark("timeline")

        for stage in stages:
            name = stage["name"]
            _need({key: (stage["dom"] or {}).get(key) for key in DATETIME_DOMS[name]} == DATETIME_DOMS[name],
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
        for name in DATETIME_REQUIRED:
            if name not in verified:
                fail(name, str(exc))
        return checks
    return checks


def datetime_result(*, observation=None):
    """Aggregate the contract checks the way the shared journey judge does."""
    checks = datetime_checks(observation=observation)
    failures = [check for check in checks if not check["ok"]]
    return {
        "checks": checks,
        "counts": {"expected": len(checks), "executed": len(checks), "asserted": len(checks) - len(failures)},
        "failures": failures,
        "ok": not failures and len(checks) == len(DATETIME_REQUIRED),
    }
