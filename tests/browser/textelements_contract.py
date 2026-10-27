"""The strict text-elements contract: journey-textelements-v1.

This criterion judges the observation the committed collector
(textelements_capture.py) writes, against the Python 1.66.1 wire measured on
2026-10-26 with the official frontend and recorded in .codex/compatibility.md
(Text elements). The collector states no verdict; this module owns it:

* st.text is a wrapped Text element with content width and left alignment;
* st.subheader is the h3 heading with wrap true and stretch width;
* st.latex is one markdown element with the formula wrapped in $$ display
  math blocks;
* st.html embeds the document with stretch width; st.iframe points at the
  URL with scrolling on, a 400 px height and stretch width;
* st.snow is the one-shot snowfall;
* st.echo takes an empty placeholder slot, the body's output streams after
  it, and the block exit replaces the placeholder with the code (python,
  content height, stretch width) at the placeholder's own path;
* st.exception renders the bare type, the message and the caller's trace
  lines with stretch width; the trace lines are each app's own source and
  are judged by count;
* the settled DOM shows each element (the exception box normalized to its
  type, message and Traceback marker).

At most one leading main-container add_block at [0] is the Rust runtime's
documented divergence.
"""

from __future__ import annotations

import hashlib
import json
import pathlib

TEXTELEMENTS_CASE = "textelements-page"
TEXTELEMENTS_CONTRACT = "journey-textelements-v1"

TEXTELEMENTS_STAGES = [
    '01-load'
]

# Per stage: the normalized frame timeline (element kinds with their full
# bodies and configs, paths, the markdown bodies, the exception shape with
# the trace judged by count) and the DOM projection.
TEXTELEMENTS_TIMELINE = {
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
            'kind': 'text',
            'body': {
                'body': 'plain text',
                'wrap': True
            },
            'configs': {
                'widthConfig': {
                    'useContent': True
                },
                'textAlignmentConfig': {
                    'alignment': 'LEFT'
                }
            },
            'path': [
                0,
                0
            ]
        },
        {
            'kind': 'heading',
            'body': {
                'tag': 'h3',
                'body': 'Sub header',
                'wrap': True
            },
            'configs': {
                'widthConfig': {
                    'useStretch': True
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
            'kind': 'markdown',
            'body': '$$\na^2 + b^2 = c^2\n$$',
            'path': [
                0,
                2
            ]
        },
        {
            'kind': 'html',
            'body': {
                'body': '<p><b>bold</b> html</p>'
            },
            'configs': {
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
            'kind': 'iframe',
            'body': {
                'src': 'https://example.com',
                'scrolling': True
            },
            'configs': {
                'heightConfig': {
                    'pixelHeight': 400
                },
                'widthConfig': {
                    'useStretch': True
                }
            },
            'path': [
                0,
                4
            ]
        },
        {
            'kind': 'snow',
            'body': {
                'show': True
            },
            'configs': {
                'hasOneShotEffect': True
            },
            'path': [
                0,
                5
            ]
        },
        {
            'kind': 'empty',
            'body': {},
            'configs': {},
            'path': [
                0,
                6
            ]
        },
        {
            'kind': 'markdown',
            'body': 'echoed inside',
            'path': [
                0,
                7
            ]
        },
        {
            'kind': 'code',
            'body': {
                'codeText': 'st.write("echoed inside")',
                'language': 'python'
            },
            'configs': {
                'heightConfig': {
                    'useContent': True
                },
                'widthConfig': {
                    'useStretch': True
                }
            },
            'path': [
                0,
                6
            ]
        },
        {
            'kind': 'exception',
            'type': 'ValueError',
            'message': 'boom',
            'trace': 1,
            'path': [
                0,
                8
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

TEXTELEMENTS_DOMS = {
    '01-load': {
        'texts': [
            'plain text'
        ],
        'markdowns': [
            'a2+b2=c2a^2 + b^2 = c^2a2+b2=c2',
            'echoed inside'
        ],
        'htmls': [
            'bold html'
        ],
        'iframes': [
            'https://example.com/'
        ],
        'snow': 1,
        'exceptions': [
            'ValueError: boom\nTraceback:'
        ]
    }
}

TEXTELEMENTS_SOURCE_FILES = {
    "python": "tests/reference/textelements_app.py",
    "native": "streamlit/examples/textelements.rs",
}

TEXTELEMENTS_REQUIRED = (
    "contract", "stage_set", "timeline", "text_wire",
    "embed_wire", "oneshot_wire", "echo_wire", "exception_wire",
    "dom_projection", "finishes", "png_sources",
)


def _record(checks, name, ok, expected, actual):
    checks.append({"step": TEXTELEMENTS_CASE, "check": name, "expected": expected, "actual": actual, "ok": bool(ok)})


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
        if kind == "delta":
            delta = summary.get("delta") or {}
            inner = delta.get("type")
            _need(inner in ("new_element", "add_block"), f"unexpected delta kind {inner!r}")
            if inner == "add_block" and (delta.get("path") or None) == [0] and (delta.get("block") or {}).get("id") == "main_container":
                stripped += 1
                _need(stripped <= 1, "more than one leading main-container block")
                continue
            name = delta.get("element")
            full = delta.get("element_full") or {}
            body = full.get(name) or {}
            configs = {key: value for key, value in full.items() if key != name}
            if name == "exception":
                exception = delta.get("exception") or {}
                out.append({
                    "kind": "exception",
                    "type": exception.get("type"),
                    "message": exception.get("message"),
                    "trace": len(exception.get("stackTrace") or []),
                    "path": delta.get("path"),
                })
            elif name == "markdown":
                out.append({"kind": "markdown", "body": delta.get("body"), "path": delta.get("path")})
            else:
                _need(bool(delta.get("element_full")), f"{name} delta lacks its full element")
                out.append({"kind": name, "body": body, "configs": configs, "path": delta.get("path")})
        elif kind == "rerun_script":
            out.append({"kind": "rerun"})
        elif kind in ("new_session", "session_status_changed", "script_finished"):
            out.append({"kind": kind})
        else:
            _need(False, f"unexpected frame kind {kind!r}")
    return out


def textelements_checks(*, observation=None):
    checks = []
    verified = set()

    def mark(name):
        verified.add(name)
        _record(checks, name, True, "the measured 1.66.1 text-elements wire", "contract verified")

    def fail(name, actual):
        _record(checks, name, False, "the measured 1.66.1 text-elements wire", str(actual))

    try:
        _need(isinstance(observation, dict), "observation must be a dict")
        _need(observation.get("journey") == TEXTELEMENTS_CASE and observation.get("contract") == TEXTELEMENTS_CONTRACT,
              "missing versioned text-elements contract identity")
        _need(bool(observation.get("scope")) and bool(observation.get("url")), "missing scope/url")
        mark("contract")

        stages = observation.get("stages")
        _need(isinstance(stages, list) and tuple(s.get("name") for s in stages) == tuple(TEXTELEMENTS_STAGES),
              f"stages must be exactly the {len(TEXTELEMENTS_STAGES)} measured stages in order")
        for stage in stages:
            _need(isinstance(stage.get("dom"), dict) and isinstance(stage.get("screenshot"), dict)
                  and isinstance(stage.get("new_frames"), list), f"stage {stage.get('name')} lacks dom/screenshot/new_frames")
        mark("stage_set")

        timelines = {stage["name"]: _timeline(stage) for stage in stages}
        for name in TEXTELEMENTS_STAGES:
            _need(timelines[name] == TEXTELEMENTS_TIMELINE[name],
                  f"stage {name} frame timeline differs from the measured wire ({len(timelines[name])} frames)")
        mark("timeline")

        load = timelines["01-load"]
        text = next(entry for entry in load if entry["kind"] == "text")
        _need(text["body"] == {"body": "plain text", "wrap": True} and text["configs"] == {"widthConfig": {"useContent": True}, "textAlignmentConfig": {"alignment": "LEFT"}},
              "st.text must be wrapped with content width and left alignment")
        heading = next(entry for entry in load if entry["kind"] == "heading")
        _need(heading["body"] == {"tag": "h3", "body": "Sub header", "wrap": True} and heading["configs"] == {"widthConfig": {"useStretch": True}, "textAlignmentConfig": {"alignment": "LEFT"}},
              "st.subheader must be the wrapped h3 heading with stretch width")
        markdowns = [entry for entry in load if entry["kind"] == "markdown"]
        _need(markdowns[0]["body"] == "$$\na^2 + b^2 = c^2\n$$", "st.latex must wrap the formula in display math")
        mark("text_wire")

        html = next(entry for entry in load if entry["kind"] == "html")
        _need(html["body"] == {"body": "<p><b>bold</b> html</p>"} and html["configs"] == {"widthConfig": {"useStretch": True}},
              "st.html must embed the document with stretch width")
        iframe = next(entry for entry in load if entry["kind"] == "iframe")
        _need(iframe["body"] == {"src": "https://example.com", "scrolling": True}
              and iframe["configs"] == {"heightConfig": {"pixelHeight": 400}, "widthConfig": {"useStretch": True}},
              "st.iframe must scroll with the 400 px default height and stretch width")
        mark("embed_wire")

        snow = next(entry for entry in load if entry["kind"] == "snow")
        _need(snow["body"] == {"show": True} and snow["configs"] == {"hasOneShotEffect": True},
              "st.snow must be the one-shot snowfall")
        mark("oneshot_wire")

        empty = next(entry for entry in load if entry["kind"] == "empty")
        _need(empty["body"] == {} and empty["configs"] == {} and empty["path"] == [0, 6],
              "st.echo's placeholder must be the bare empty at the call slot")
        _need(markdowns[1]["body"] == "echoed inside" and markdowns[1]["path"] == [0, 7],
              "the echoed body streams after the placeholder")
        code = next(entry for entry in load if entry["kind"] == "code")
        _need(code["body"] == {"codeText": "st.write(\"echoed inside\")", "language": "python"}
              and code["configs"] == {"heightConfig": {"useContent": True}, "widthConfig": {"useStretch": True}}
              and code["path"] == empty["path"],
              "the block exit must replace the placeholder with the code at its own path")
        mark("echo_wire")

        exception = next(entry for entry in load if entry["kind"] == "exception")
        _need(exception["type"] == "ValueError" and exception["message"] == "boom" and exception["trace"] == 1
              and exception["path"] == [0, 8],
              "st.exception must render the type, the message and one trace line at the next slot")
        mark("exception_wire")

        for stage in stages:
            name = stage["name"]
            projection = {
                "texts": (stage["dom"] or {}).get("texts"),
                "markdowns": (stage["dom"] or {}).get("markdowns"),
                "htmls": (stage["dom"] or {}).get("htmls"),
                "iframes": (stage["dom"] or {}).get("iframes"),
                "snow": (stage["dom"] or {}).get("snow"),
                "exceptions": ["\n".join(text.split("\n")[:2]) for text in (stage["dom"] or {}).get("exceptions") or []],
            }
            _need(projection == TEXTELEMENTS_DOMS[name], f"stage {name} resolved DOM projection differs from the measured page")
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
        for name in TEXTELEMENTS_REQUIRED:
            if name not in verified:
                fail(name, str(exc))
        return checks
    return checks


def textelements_result(*, observation=None):
    """Aggregate the contract checks the way the shared journey judge does."""
    checks = textelements_checks(observation=observation)
    failures = [check for check in checks if not check["ok"]]
    return {
        "checks": checks,
        "counts": {"expected": len(checks), "executed": len(checks), "asserted": len(checks) - len(failures)},
        "failures": failures,
        "ok": not failures and len(checks) == len(TEXTELEMENTS_REQUIRED),
    }
