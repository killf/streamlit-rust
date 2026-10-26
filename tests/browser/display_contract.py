"""The strict display contract: journey-display-v1.

This criterion judges the observation the committed collector
(display_capture.py) writes, against the Python 1.66.1 wire measured on
2026-10-26 with the official frontend and recorded in .codex/compatibility.md
(Display containers). The collector states no verdict; this module owns it:

* st.json streams one Json element with the Python json.dumps rendering of
  the value and stretch width;
* st.status is an expandable block (allowEmpty, stretch width) carrying the
  label, the spinner icon and the RUNNING state; status.update re-streams
  the SAME block path with the new label/icon/state/expansion
  (COMPLETE pairs :material/check:);
* st.empty takes a slot and the handle's write replaces that slot without
  advancing the cursor -- the reference's queue composes the placeholder
  into a same-path replacement within one flush batch (both the streamed
  and the coalesced shape are accepted; the replacement always lands);
* st.space is the square spacer with BOTH the width and height configs at
  the pixel value;
* st.bottom streams children at the fixed root [3, i] with no block;
* the settled DOM shows the json viewer, the bottom line and no exception.

At most one leading main-container add_block at [0] is the Rust runtime's
documented divergence.
"""

from __future__ import annotations

import hashlib
import json
import pathlib

DISPLAY_CASE = "display-page"
DISPLAY_CONTRACT = "journey-display-v1"

DISPLAY_STAGES = [
    '01-load'
]

# Per stage: the normalized frame timeline and the DOM projection.
DISPLAY_TIMELINE = {
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
            'kind': 'json',
            'full': {
                'json': {
                    'body': '{"a": 1, "b": [true, null]}',
                    'expanded': True
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
            'kind': 'block',
            'block': {
                'expandable': {
                    'label': 'Working...',
                    'expanded': True,
                    'icon': 'spinner',
                    'state': 'RUNNING'
                },
                'allowEmpty': True,
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
            'body': 'step one',
            'path': [
                0,
                1,
                0
            ]
        },
        {
            'kind': 'markdown',
            'body': 'step two',
            'path': [
                0,
                1,
                1
            ]
        },
        {
            'kind': 'block',
            'block': {
                'expandable': {
                    'label': 'Done',
                    'expanded': False,
                    'icon': ':material/check:',
                    'state': 'COMPLETE'
                },
                'allowEmpty': True,
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
            'body': 'replaced',
            'path': [
                0,
                2
            ]
        },
        {
            'kind': 'space',
            'full': {
                'heightConfig': {
                    'pixelHeight': 3
                },
                'widthConfig': {
                    'pixelWidth': 3
                },
                'space': {}
            },
            'path': [
                0,
                3
            ]
        },
        {
            'kind': 'markdown',
            'body': 'bottom line',
            'path': [
                3,
                0
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

DISPLAY_DOMS = {
    '01-load': {
        'json': [
            '{"a":1"b":[0:true1:NULL]}'
        ],
        'markdowns': [],
        'bottom': [
            'bottom line'
        ],
        'exceptions': []
    }
}

DISPLAY_SOURCE_PINS = {
    "python": [
    'tests/reference/display_app.py',
    '6ff9cca00a26fa36b0e89d45bef7596bf1ec4e47dd6d1de87291fe2d8904fee6'
],
    "native": [
    'streamlit/examples/display.rs',
    '876779e3a6e1d2c3a8ad85d79eb135177ae1f51973ec701d9784c2ecc47d324c'
],
}

DISPLAY_REQUIRED = (
    "contract", "stage_set", "source_pin", "timeline", "json_wire",
    "status_wire", "empty_wire", "space_wire", "bottom_wire",
    "dom_projection", "finishes", "png_sources",
)


def _record(checks, name, ok, expected, actual):
    checks.append({"step": DISPLAY_CASE, "check": name, "expected": expected, "actual": actual, "ok": bool(ok)})


def _need(condition, message):
    if not condition:
        raise ValueError(message)


def _timeline(stage):
    """The stage's normalized frames: the optional leading main container
    peeled off, and an st.empty placeholder composed into a same-path
    replacement (the reference's queue coalesces them within one flush
    batch; both shapes are legitimate)."""
    out = []
    stripped = 0
    for frame in stage.get("new_frames") or []:
        summary = frame.get("summary") or {}
        kind = summary.get("type")
        if kind == "delta":
            delta = summary.get("delta") or {}
            inner = delta.get("type")
            _need(inner in ("new_element", "add_block"), f"unexpected delta kind {inner!r}")
            if inner == "add_block" and (delta.get("path") or None) == [0] and (delta.get("block") or {}).get("id") == "main_container":
                stripped += 1
                _need(stripped <= 1, "more than one leading main-container block")
                continue
            if inner == "add_block":
                out.append({"kind": "block", "block": delta.get("block") or {}, "path": delta.get("path")})
            else:
                name = delta.get("element")
                if name in ("json", "space"):
                    _need(bool(delta.get("element_full")), f"{name} delta lacks its full element")
                    out.append({"kind": name, "full": delta.get("element_full") or {}, "path": delta.get("path")})
                else:
                    out.append({"kind": name, "body": delta.get("body"), "path": delta.get("path")})
        elif kind == "rerun_script":
            out.append({"kind": "rerun"})
        elif kind in ("new_session", "session_status_changed", "script_finished"):
            out.append({"kind": kind})
        else:
            _need(False, f"unexpected frame kind {kind!r}")
    composed = []
    for index, entry in enumerate(out):
        rest = out[index + 1] if index + 1 < len(out) else None
        if entry["kind"] == "empty" and rest is not None and rest.get("path") == entry.get("path"):
            continue
        composed.append(entry)
    return composed


def display_checks(*, observation=None):
    checks = []
    verified = set()

    def mark(name):
        verified.add(name)
        _record(checks, name, True, "the measured 1.66.1 display wire", "contract verified")

    def fail(name, actual):
        _record(checks, name, False, "the measured 1.66.1 display wire", str(actual))

    try:
        _need(isinstance(observation, dict), "observation must be a dict")
        _need(observation.get("journey") == DISPLAY_CASE and observation.get("contract") == DISPLAY_CONTRACT,
              "missing versioned display contract identity")
        _need(bool(observation.get("scope")) and bool(observation.get("url")), "missing scope/url")
        mark("contract")

        stages = observation.get("stages")
        _need(isinstance(stages, list) and tuple(s.get("name") for s in stages) == tuple(DISPLAY_STAGES),
              f"stages must be exactly the {len(DISPLAY_STAGES)} measured stages in order")
        for stage in stages:
            _need(isinstance(stage.get("dom"), dict) and isinstance(stage.get("screenshot"), dict)
                  and isinstance(stage.get("new_frames"), list), f"stage {stage.get('name')} lacks dom/screenshot/new_frames")
        mark("stage_set")

        source = observation.get("source") or {}
        side = "python" if observation.get("scope") == "PYTHON SIDE ONLY" else "native"
        path, pinned = DISPLAY_SOURCE_PINS[side]
        _need(source.get("file") == path and source.get("sha256") == pinned,
              f"driven source is not the pinned {path} of this contract")
        mark("source_pin")

        timelines = {stage["name"]: _timeline(stage) for stage in stages}
        for name in DISPLAY_STAGES:
            _need(timelines[name] == DISPLAY_TIMELINE[name],
                  f"stage {name} frame timeline differs from the measured wire ({len(timelines[name])} frames)")
        mark("timeline")

        load = timelines["01-load"]
        json_entry = next(entry for entry in load if entry["kind"] == "json")
        _need(json_entry["full"] == {"json": {"body": "{\"a\": 1, \"b\": [true, null]}", "expanded": True}, "widthConfig": {"useStretch": True}} and json_entry["path"] == [0, 0],
              "st.json must stream the json.dumps rendering expanded with stretch width")
        mark("json_wire")

        blocks = [entry for entry in load if entry["kind"] == "block"]
        _need(len(blocks) == 2 and blocks[0]["path"] == blocks[1]["path"] == [0, 1],
              "st.status and its update must stream at the same block path")
        _need(blocks[0]["block"] == {"expandable": {"label": "Working...", "expanded": True, "icon": "spinner", "state": "RUNNING"}, "allowEmpty": True, "widthConfig": {"useStretch": True}},
              "the status block opens RUNNING with the spinner icon")
        _need(blocks[1]["block"] == {"expandable": {"label": "Done", "expanded": False, "icon": ":material/check:", "state": "COMPLETE"}, "allowEmpty": True, "widthConfig": {"useStretch": True}},
              "the update re-streams the block COMPLETE with the check icon")
        _need([entry["body"] for entry in load if entry["kind"] == "markdown"][:2] == ["step one", "step two"]
              and [entry["path"] for entry in load if entry["kind"] == "markdown"][:2] == [[0, 1, 0], [0, 1, 1]],
              "the status children stream inside the block")
        mark("status_wire")

        markdowns = [entry for entry in load if entry["kind"] == "markdown"]
        _need(markdowns[2]["body"] == "replaced" and markdowns[2]["path"] == [0, 2],
              "the empty slot's replacement lands at the slot's own path")
        mark("empty_wire")

        space = next(entry for entry in load if entry["kind"] == "space")
        _need(space["full"] == {"heightConfig": {"pixelHeight": 3}, "widthConfig": {"pixelWidth": 3}, "space": {}} and space["path"] == [0, 3],
              "st.space must be the square spacer with both configs at the pixel value")
        mark("space_wire")

        _need(markdowns[3]["body"] == "bottom line" and markdowns[3]["path"] == [3, 0],
              "st.bottom children stream at the fixed root [3, 0]")
        mark("bottom_wire")

        for stage in stages:
            name = stage["name"]
            _need({key: (stage["dom"] or {}).get(key) for key in DISPLAY_DOMS[name]} == DISPLAY_DOMS[name],
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
        for name in DISPLAY_REQUIRED:
            if name not in verified:
                fail(name, str(exc))
        return checks
    return checks


def display_result(*, observation=None):
    """Aggregate the contract checks the way the shared journey judge does."""
    checks = display_checks(observation=observation)
    failures = [check for check in checks if not check["ok"]]
    return {
        "checks": checks,
        "counts": {"expected": len(checks), "executed": len(checks), "asserted": len(checks) - len(failures)},
        "failures": failures,
        "ok": not failures and len(checks) == len(DISPLAY_REQUIRED),
    }
