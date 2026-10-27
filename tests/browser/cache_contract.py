"""The strict cache contract: journey-cache-v1.

This criterion judges the observation the committed collector
(cache_capture.py) writes, against the Python 1.66.1 wire measured on
2026-10-26 with the official frontend and recorded in .codex/compatibility.md
(Caching). The collector states no verdict; this module owns it:

* every st.cache_data miss streams exactly one empty-element transient (the
  cleared-spinner shape) at the call site's entry path -- for an
  element-free function after the return and before the following outside
  write at the same path, for a function with st-side effects after its
  elements at the entry index;
* a hit replays the recorded function-internal elements at the call site
  with no transient, and the replayed element consumes its path slot like a
  live render, so following writes land after it;
* values are stable across the rerun (cached=42, cached_other=14,
  inside cached fn, side=1);
* st.cache_clear() drops the store: the next call remisses with a fresh
  transient and recomputes;
* the settled DOM shows the markdown echoes including the replayed element,
  no exception, each run finishing FINISHED_SUCCESSFULLY.

Widget ids are judged modulo the $$ID digest segment; at most one leading
main-container add_block at [0] is the Rust runtime's documented divergence.
"""

from __future__ import annotations

import hashlib
import json
import pathlib
import re

CACHE_CASE = "cache-page"
CACHE_CONTRACT = "journey-cache-v1"

CACHE_STAGES = [
    '01-load',
    '02-again-click'
]

# Per stage: the normalized frame timeline (kind/path/body, the transient
# payload, the browser's rerun report), the transient paths, the DOM
# projection.
CACHE_TIMELINE = {
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
            'kind': 'markdown',
            'path': [
                0,
                0
            ],
            'body': 'runs=1'
        },
        {
            'kind': 'transient',
            'path': [
                0,
                1
            ],
            'transient': {}
        },
        {
            'kind': 'markdown',
            'path': [
                0,
                1
            ],
            'body': 'cached=42'
        },
        {
            'kind': 'transient',
            'path': [
                0,
                2
            ],
            'transient': {}
        },
        {
            'kind': 'markdown',
            'path': [
                0,
                2
            ],
            'body': 'cached_other=14'
        },
        {
            'kind': 'markdown',
            'path': [
                0,
                3
            ],
            'body': 'inside cached fn'
        },
        {
            'kind': 'transient',
            'path': [
                0,
                3
            ],
            'transient': {}
        },
        {
            'kind': 'markdown',
            'path': [
                0,
                4
            ],
            'body': 'side=1'
        },
        {
            'kind': 'button',
            'path': [
                0,
                5
            ],
            'body': None
        },
        {
            'kind': 'script_finished'
        },
        {
            'kind': 'session_status_changed'
        }
    ],
    '02-again-click': [
        {
            'kind': 'rerun',
            'query_string': None,
            'widget_states': [
                {
                    'id': '$$ID-None',
                    'value_field': 'trigger_value',
                    'value': True
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
            'kind': 'markdown',
            'path': [
                0,
                0
            ],
            'body': 'runs=2'
        },
        {
            'kind': 'markdown',
            'path': [
                0,
                1
            ],
            'body': 'cached=42'
        },
        {
            'kind': 'markdown',
            'path': [
                0,
                2
            ],
            'body': 'cached_other=14'
        },
        {
            'kind': 'markdown',
            'path': [
                0,
                3
            ],
            'body': 'inside cached fn'
        },
        {
            'kind': 'markdown',
            'path': [
                0,
                4
            ],
            'body': 'side=1'
        },
        {
            'kind': 'button',
            'path': [
                0,
                5
            ],
            'body': None
        },
        {
            'kind': 'markdown',
            'path': [
                0,
                6
            ],
            'body': 'cleared'
        },
        {
            'kind': 'transient',
            'path': [
                0,
                7
            ],
            'transient': {}
        },
        {
            'kind': 'markdown',
            'path': [
                0,
                7
            ],
            'body': 'cached_after_clear=42'
        },
        {
            'kind': 'script_finished'
        },
        {
            'kind': 'session_status_changed'
        }
    ]
}

CACHE_TRANSIENT_PATHS = {
    '01-load': [
        [
            0,
            1
        ],
        [
            0,
            2
        ],
        [
            0,
            3
        ]
    ],
    '02-again-click': [
        [
            0,
            7
        ]
    ]
}

CACHE_DOMS = {
    '01-load': {
        'markdowns': [
            'runs=1',
            'cached=42',
            'cached_other=14',
            'inside cached fn',
            'side=1'
        ],
        'exceptions': []
    },
    '02-again-click': {
        'markdowns': [
            'runs=2',
            'cached=42',
            'cached_other=14',
            'inside cached fn',
            'side=1',
            'cleared',
            'cached_after_clear=42'
        ],
        'exceptions': []
    }
}

CACHE_SOURCE_FILES = {
    "python": "tests/reference/cache_app.py",
    "native": "streamlit/examples/cache.rs",
}

CACHE_REQUIRED = (
    "contract", "stage_set", "timeline", "miss_wire",
    "hit_wire", "value_stability", "clear_wire", "dom_projection",
    "no_exceptions", "finishes", "png_sources",
)

_ID_SUB = re.compile(r"\$\$ID-[0-9a-f]{32}-")


def _record(checks, name, ok, expected, actual):
    checks.append({"step": CACHE_CASE, "check": name, "expected": expected, "actual": actual, "ok": bool(ok)})


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
            _need(inner in ("new_element", "add_block", "new_transient"), f"unexpected delta kind {inner!r}")
            if inner == "add_block" and (delta.get("path") or None) == [0] and (delta.get("block") or {}).get("id") == "main_container":
                stripped += 1
                _need(stripped <= 1, "more than one leading main-container block")
                continue
            if inner == "new_transient":
                out.append({"kind": "transient", "path": delta.get("path"), "transient": delta.get("transient")})
            else:
                out.append({"kind": delta.get("element"), "path": delta.get("path"), "body": delta.get("body")})
        elif kind == "rerun_script":
            rerun = summary.get("rerun_script") or {}
            states = [{**state, "id": _ID_SUB.sub("$$ID-", state.get("id") or "")} for state in rerun.get("widget_states") or []]
            out.append({"kind": "rerun", "query_string": rerun.get("query_string"), "widget_states": states})
        elif kind in ("new_session", "session_status_changed", "script_finished"):
            out.append({"kind": kind})
        else:
            _need(False, f"unexpected frame kind {kind!r}")
    return out


def _entries(frames, kind):
    return [(index, entry) for index, entry in enumerate(frames) if entry["kind"] == kind]


def _markdown_at(frames, body):
    hits = [entry for _, entry in _entries(frames, "markdown") if entry.get("body") == body]
    _need(len(hits) == 1, f"expected exactly one markdown {body!r}, got {len(hits)}")
    return hits[0]


def cache_checks(*, observation=None):
    checks = []
    verified = set()

    def mark(name):
        verified.add(name)
        _record(checks, name, True, "the measured 1.66.1 cache wire", "contract verified")

    def fail(name, actual):
        _record(checks, name, False, "the measured 1.66.1 cache wire", str(actual))

    try:
        _need(isinstance(observation, dict), "observation must be a dict")
        _need(observation.get("journey") == CACHE_CASE and observation.get("contract") == CACHE_CONTRACT,
              "missing versioned cache contract identity")
        _need(bool(observation.get("scope")) and bool(observation.get("url")), "missing scope/url")
        mark("contract")

        stages = observation.get("stages")
        _need(isinstance(stages, list) and tuple(s.get("name") for s in stages) == tuple(CACHE_STAGES),
              f"stages must be exactly the {len(CACHE_STAGES)} measured stages in order")
        for stage in stages:
            _need(isinstance(stage.get("dom"), dict) and isinstance(stage.get("screenshot"), dict)
                  and isinstance(stage.get("new_frames"), list), f"stage {stage.get('name')} lacks dom/screenshot/new_frames")
        mark("stage_set")

        timelines = {stage["name"]: _timeline(stage) for stage in stages}
        for name in CACHE_STAGES:
            _need(timelines[name] == CACHE_TIMELINE[name],
                  f"stage {name} frame timeline differs from the measured wire ({len(timelines[name])} frames)")
        mark("timeline")

        # Miss run: three empty transients, the element-free ones before
        # their following outside write at the same path, the side-effecting
        # one after its element at the entry index.
        miss = timelines["01-load"]
        transient_entries = _entries(miss, "transient")
        _need([entry["path"] for _, entry in transient_entries] == CACHE_TRANSIENT_PATHS["01-load"],
              "the miss run must stream exactly the three measured transients at their entry paths")
        for _, entry in transient_entries:
            _need(entry.get("transient") == {}, "every miss transient must be the empty cleared-spinner shape")
        inside = _markdown_at(miss, "inside cached fn")
        cached = _markdown_at(miss, "cached=42")
        other = _markdown_at(miss, "cached_other=14")
        _need(transient_entries[0][1]["path"] == cached["path"] and transient_entries[0][0] < next(i for i, e in _entries(miss, "markdown") if e is cached),
              "the element-free miss transient must precede its outside write at the same path")
        _need(transient_entries[1][1]["path"] == other["path"] and transient_entries[1][0] < next(i for i, e in _entries(miss, "markdown") if e is other),
              "the second element-free miss transient must precede its outside write at the same path")
        _need(transient_entries[2][1]["path"] == inside["path"] and transient_entries[2][0] > next(i for i, e in _entries(miss, "markdown") if e is inside),
              "the side-effecting miss transient must follow its element at the entry index")
        mark("miss_wire")

        # Hit run: no transient for the three hits, the replayed element
        # consumes its slot so the following write lands after it.
        hit = timelines["02-again-click"]
        hit_transients = _entries(hit, "transient")
        _need([entry["path"] for _, entry in hit_transients] == CACHE_TRANSIENT_PATHS["02-again-click"],
              "the hit run must stream no transient before the post-clear remiss")
        replayed = _markdown_at(hit, "inside cached fn")
        side_write = _markdown_at(hit, "side=1")
        _need(replayed["path"] == [0, 3], f"the replayed element must keep its recorded path [0, 3], got {replayed['path']}")
        _need(side_write["path"] == [0, 4] and side_write["path"] != replayed["path"],
              "the write after the replay must land on the next slot, not overwrite the replayed element")
        button_entries = _entries(hit, "button")
        _need(len(button_entries) == 1, "the hit run must carry exactly one button element")
        _need(all(index > button_entries[0][0] for index, _ in hit_transients),
              "the only hit-run transient must follow the button, i.e., belong to the post-clear remiss")
        mark("hit_wire")

        # Values are stable across the rerun: the four bodies appear at the
        # same paths in both runs.
        for body in ("cached=42", "cached_other=14", "inside cached fn", "side=1"):
            _need(_markdown_at(miss, body)["path"] == _markdown_at(hit, body)["path"],
                  f"markdown {body!r} must sit at the same path in both runs")
        mark("value_stability")

        # clear() drops the store: the remiss follows the cleared marker and
        # recomputes at the same path, and the miss run has no clear trio.
        cleared = _markdown_at(hit, "cleared")
        after = _markdown_at(hit, "cached_after_clear=42")
        _need(cleared["path"] == [0, 6] and after["path"] == [0, 7], "the clear branch must land at the measured paths")
        cleared_at = next(i for i, e in _entries(hit, "markdown") if e is cleared)
        after_at = next(i for i, e in _entries(hit, "markdown") if e is after)
        _need(len(hit_transients) == 1 and cleared_at < hit_transients[0][0] < after_at,
              "exactly one post-clear transient must sit between cleared and the recomputed write")
        _need(hit_transients[0][1]["path"] == after["path"], "the remiss transient must take the recomputed call site's path")
        for body in ("cleared", "cached_after_clear=42"):
            _need(not [entry for _, entry in _entries(miss, "markdown") if entry.get("body") == body],
                  f"the miss run must not carry {body!r}")
        mark("clear_wire")

        for stage in stages:
            name = stage["name"]
            _need({key: (stage["dom"] or {}).get(key) for key in CACHE_DOMS[name]} == CACHE_DOMS[name],
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
        for name in CACHE_REQUIRED:
            if name not in verified:
                fail(name, str(exc))
        return checks
    return checks


def cache_result(*, observation=None):
    """Aggregate the contract checks the way the shared journey judge does."""
    checks = cache_checks(observation=observation)
    failures = [check for check in checks if not check["ok"]]
    return {
        "checks": checks,
        "counts": {"expected": len(checks), "executed": len(checks), "asserted": len(checks) - len(failures)},
        "failures": failures,
        "ok": not failures and len(checks) == len(CACHE_REQUIRED),
    }
