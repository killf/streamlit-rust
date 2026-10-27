"""The strict presentation-leftover contract: journey-display2-v1.

This criterion judges the observation the committed collector
(display2_capture.py) writes, against the Python 1.66.1 wire measured on
2026-10-26 with the official frontend and recorded in .codex/compatibility.md
(Presentation leftovers). The collector states no verdict; this module
owns it:

* st.logo streams a ForwardMsg-level logo message (no element path): the
  emoji image, its EMOJI type and the size;
* st.help streams a help_info element: the doc string, type, name and
  value with stretch width;
* st.skeleton streams an all-default Skeleton element sized entirely by
  its layout config (pixel height, stretch width);
* st.pdf on the pinned reference (which lacks the optional streamlit-pdf
  component) raises StreamlitAPIException: the exception element carries
  the full error path type, the exact message, the markdown and
  streamlit-error flags, and the stretch width; the trace lines name the
  caller's Python file, so they are judged away as a side-specific
  detail;
* the run still finishes FINISHED_SUCCESSFULLY and the settled DOM shows
  the help text and the exception box.

At most one leading main-container add_block at [0] is the Rust runtime's
documented divergence.
"""

from __future__ import annotations

import hashlib
import json
import pathlib
import re

DISPLAY2_CASE = "display2-page"
DISPLAY2_CONTRACT = "journey-display2-v1"

DISPLAY2_STAGES = [
    '01-load'
]

DISPLAY2_TIMELINE = {
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
            'kind': 'logo',
            'logo': {
                'image': '🏠',
                'size': 'small',
                'imageType': 'EMOJI'
            }
        },
        {
            'kind': 'help_info',
            'element_full': {
                'helpInfo': {
                    'docString': 'Return the number of items in a container.',
                    'type': 'builtin_function_or_method',
                    'name': 'len',
                    'value': 'builtins.len(obj, /)'
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
            'kind': 'skeleton',
            'element_full': {
                'skeleton': {},
                'heightConfig': {
                    'pixelHeight': 100
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
            'kind': 'exception',
            'exception': {
                'type': 'streamlit.errors.StreamlitAPIException',
                'message': 'The PDF viewer requires the `streamlit-pdf` component to be installed.\n\nPlease run `pip install streamlit[pdf]` to install it.\n\nFor more information, see the Streamlit PDF documentation at https://docs.streamlit.io/develop/api-reference/media/st.pdf.',
                'messageIsMarkdown': True,
                'widthConfig': {
                    'useStretch': True
                },
                'isStreamlitException': True
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

DISPLAY2_DOMS = {
    '01-load': {
        'logo': None,
        'help': [
            'lenbuiltin_function_or_methodbuiltins.len(obj, /)Return the number of items in a container.'
        ],
        'skeletons': 0,
        'exceptions': [
            'streamlit.errors.StreamlitAPIException: The PDF viewer requires the streamlit-pdf component to be installed.\n\nPlease run pip install streamlit[pdf] to install it.\n\nFor more information, see the Stream'
        ]
    }
}

DISPLAY2_SOURCE_FILES = {
    "python": "tests/reference/display2_app.py",
    "native": "streamlit/examples/display2.rs",
}

DISPLAY2_REQUIRED = (
    "contract", "stage_set", "timeline", "logo_wire",
    "help_wire", "skeleton_wire", "pdf_wire", "dom_projection", "finishes",
    "png_sources",
)


def _record(checks, name, ok, expected, actual):
    checks.append({"step": DISPLAY2_CASE, "check": name, "expected": expected, "actual": actual, "ok": bool(ok)})


def _need(condition, message):
    if not condition:
        raise ValueError(message)


def _timeline(stage):
    """The stage's normalized frames, the optional leading main container
    peeled off (the Rust side emits exactly one, the reference none)."""
    out = []
    stripped = 0
    for frame in stage.get("new_frames") or []:
        summary = frame.get("summary") or {}
        kind = summary.get("type")
        if kind == "logo":
            out.append({"kind": "logo", "logo": summary.get("logo")})
        elif kind == "delta":
            delta = summary.get("delta") or {}
            inner = delta.get("type")
            _need(inner in ("new_element", "add_block"), f"unexpected delta kind {inner!r}")
            if inner == "add_block" and (delta.get("path") or None) == [0] and (delta.get("block") or {}).get("id") == "main_container":
                stripped += 1
                _need(stripped <= 1, "more than one leading main-container block")
                continue
            if inner == "add_block":
                _need(False, f"unexpected block {sorted(delta.get('block') or {})}")
            name = delta.get("element")
            if name in ("help_info", "skeleton"):
                _need(delta.get("element_full") is not None, f"{name} delta lacks its full element")
                out.append({"kind": name, "element_full": delta.get("element_full"), "path": delta.get("path")})
            elif name == "exception":
                exception = dict(delta.get("exception") or {})
                exception.pop("stackTrace", None)
                _need(exception.get("message"), "the exception delta lacks its payload")
                out.append({"kind": "exception", "exception": exception, "path": delta.get("path")})
            else:
                _need(False, f"unexpected element {name!r}")
        elif kind == "rerun_script":
            out.append({"kind": "rerun"})
        elif kind in ("new_session", "session_status_changed", "script_finished"):
            out.append({"kind": kind})
        else:
            _need(False, f"unexpected frame kind {kind!r}")
    return out


def _entries(stage_timeline, kind):
    return [entry for entry in stage_timeline if entry["kind"] == kind]


def display2_checks(*, observation=None):
    checks = []
    verified = set()

    def mark(name):
        verified.add(name)
        _record(checks, name, True, "the measured 1.66.1 presentation-leftover wire", "contract verified")

    def fail(name, actual):
        _record(checks, name, False, "the measured 1.66.1 presentation-leftover wire", str(actual))

    try:
        _need(isinstance(observation, dict), "observation must be a dict")
        _need(observation.get("journey") == DISPLAY2_CASE and observation.get("contract") == DISPLAY2_CONTRACT,
              "missing versioned display2 contract identity")
        _need(bool(observation.get("scope")) and bool(observation.get("url")), "missing scope/url")
        mark("contract")

        stages = observation.get("stages")
        _need(isinstance(stages, list) and tuple(s.get("name") for s in stages) == tuple(DISPLAY2_STAGES),
              f"stages must be exactly the {len(DISPLAY2_STAGES)} measured stages in order")
        for stage in stages:
            _need(isinstance(stage.get("dom"), dict) and isinstance(stage.get("screenshot"), dict)
                  and isinstance(stage.get("new_frames"), list), f"stage {stage.get('name')} lacks dom/screenshot/new_frames")
        mark("stage_set")

        timelines = {stage["name"]: _timeline(stage) for stage in stages}
        for name in DISPLAY2_STAGES:
            _need(timelines[name] == DISPLAY2_TIMELINE[name],
                  f"stage {name} frame timeline differs from the measured wire ({len(timelines[name])} frames)")
        mark("timeline")

        load = timelines["01-load"]
        logos = _entries(load, "logo")
        _need(len(logos) == 1 and logos[0]["logo"] == {"image": "🏠", "size": "small", "imageType": "EMOJI"},
              "the logo message carries the emoji image, its type and the size")
        mark("logo_wire")

        helps = _entries(load, "help_info")
        _need(len(helps) == 1 and helps[0]["element_full"] == {
            "helpInfo": {"docString": "Return the number of items in a container.", "type": "builtin_function_or_method",
                          "name": "len", "value": "builtins.len(obj, /)"},
            "widthConfig": {"useStretch": True}}, "the help element carries the doc string, type, name and value")
        _need(helps[0]["path"] == [0, 0], "the help element takes the first main slot")
        mark("help_wire")

        skeletons = _entries(load, "skeleton")
        _need(len(skeletons) == 1 and skeletons[0]["element_full"] == {
            "skeleton": {}, "heightConfig": {"pixelHeight": 100}, "widthConfig": {"useStretch": True}},
              "the skeleton is all-default with its pixel height and stretch width")
        _need(skeletons[0]["path"] == [0, 1], "the skeleton takes the second main slot")
        mark("skeleton_wire")

        exceptions = _entries(load, "exception")
        _need(len(exceptions) == 1 and exceptions[0]["exception"] == {
            "type": "streamlit.errors.StreamlitAPIException",
            "message": "The PDF viewer requires the `streamlit-pdf` component to be installed.\n\nPlease run `pip install streamlit[pdf]` to install it.\n\nFor more information, see the Streamlit PDF documentation at https://docs.streamlit.io/develop/api-reference/media/st.pdf.",
            "messageIsMarkdown": True, "isStreamlitException": True, "widthConfig": {"useStretch": True}},
              "the pdf exception carries the full error path type, exact message and flags")
        _need(exceptions[0]["path"] == [0, 2], "the exception takes the third main slot")
        mark("pdf_wire")

        for stage in stages:
            name = stage["name"]
            _need({key: (stage["dom"] or {}).get(key) for key in DISPLAY2_DOMS[name]} == DISPLAY2_DOMS[name],
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
        for name in DISPLAY2_REQUIRED:
            if name not in verified:
                fail(name, str(exc))
        return checks
    return checks


def display2_result(*, observation=None):
    """Aggregate the contract checks the way the shared journey judge does."""
    checks = display2_checks(observation=observation)
    failures = [check for check in checks if not check["ok"]]
    return {
        "checks": checks,
        "counts": {"expected": len(checks), "executed": len(checks), "asserted": len(checks) - len(failures)},
        "failures": failures,
        "ok": not failures and len(checks) == len(DISPLAY2_REQUIRED),
    }
