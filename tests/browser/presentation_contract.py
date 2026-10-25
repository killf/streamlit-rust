"""The strict presentation contract: journey-presentation-v1.

This criterion judges the observation the committed collector
(presentation_capture.py) writes, against the Python 1.66.1 wire measured on
2026-10-25 with the official frontend and recorded in .codex/compatibility.md
(Presentation widgets). The collector states no verdict; this module owns it:

* the spinner rides two new_transient deltas at path [0, 0] — one active
  spinner (text plus content width, cache/show_time unset), then an empty
  list at block exit — and consumes no element path: the block's next
  element lands at the same [0, 0];
* the toast is a one-shot element routed to the dedicated root path [2, 0]
  with the measured body/icon and an explicit four-second duration;
* the balloons are a one-shot show element at the container's next slot
  [0, 1];
* the DOM shows the loaded markdown and the visible toast with no spinner
  and no exception, and the run finishes FINISHED_SUCCESSFULLY.
"""

from __future__ import annotations

import hashlib
import pathlib

PRESENTATION_CASE = "presentation-page"
PRESENTATION_CONTRACT = "journey-presentation-v1"

PRESENTATION_STAGES = ["01-load"]

# The measured delta timeline: kind, delta path and element shape in order.
PRESENTATION_TIMELINE = [
 {
  "kind": "new_transient",
  "path": [
   0,
   0
  ],
  "elements": [
   {
    "spinner": {
     "text": "Loading data"
    },
    "widthConfig": {
     "useContent": True
    }
   }
  ]
 },
 {
  "kind": "new_transient",
  "path": [
   0,
   0
  ],
  "elements": []
 },
 {
  "kind": "new_element",
  "path": [
   0,
   0
  ],
  "element": "markdown",
  "full": None,
  "body": "loaded"
 },
 {
  "kind": "new_element",
  "path": [
   2,
   0
  ],
  "element": "toast",
  "full": {
   "toast": {
    "body": "Saved successfully",
    "icon": "✅",
    "duration": 4
   },
   "hasOneShotEffect": True
  },
  "body": "Saved successfully"
 },
 {
  "kind": "new_element",
  "path": [
   0,
   1
  ],
  "element": "balloons",
  "full": {
   "balloons": {
    "show": True
   },
   "hasOneShotEffect": True
  },
  "body": None
 }
]

# The DOM projection the official frontend resolves.
PRESENTATION_DOM = {
 "markdowns": [
  "loaded"
 ],
 "alerts": [],
 "toasts": [
  "✅Saved successfully"
 ],
 "spinners": [],
 "exceptions": []
}

PRESENTATION_SOURCE_PINS = {
    "python": ("tests/reference/presentation_app.py", "386f744f39f90874bab6b31a2c1b1593a3657de6c6eebd83e9b1a40a3994aba1"),
    "native": ("streamlit/examples/presentation.rs", "2f9c2b678e865d2c283c8c2856e80a8d837a9a92647abeca12bb39ba17950f04"),
}

PRESENTATION_REQUIRED = (
    "contract", "stage_set", "source_pin", "timeline", "spinner_lifecycle",
    "toast_wire", "balloons_wire", "dom_projection", "no_exceptions",
    "finishes", "png_sources",
)


def _record(checks, name, ok, expected, actual):
    checks.append({"step": PRESENTATION_CASE, "check": name, "expected": expected, "actual": actual, "ok": bool(ok)})


def _need(condition, message):
    if not condition:
        raise ValueError(message)


def _timeline(stage):
    out = []
    for frame in stage.get("new_frames") or []:
        delta = (frame.get("summary") or {}).get("delta") or {}
        if not delta:
            continue
        kind = delta.get("type")
        _need(kind in ("new_transient", "new_element", "add_block"), f"unexpected delta kind {kind!r}")
        if kind == "new_transient":
            elements = (delta.get("transient") or {}).get("elements") or []
            _need(isinstance(elements, list), "transient elements must be a list")
            out.append({"kind": "new_transient", "path": delta.get("path"),
                        "elements": elements})
        elif kind == "new_element":
            out.append({"kind": "new_element", "path": delta.get("path"), "element": delta.get("element"),
                        "full": delta.get("element_full"), "body": delta.get("body")})
    return out


def presentation_checks(*, observation=None):
    import json as _json

    checks = []
    verified = set()

    def mark(name):
        verified.add(name)
        _record(checks, name, True, "the measured 1.66.1 presentation wire", "contract verified")

    def fail(name, actual):
        _record(checks, name, False, "the measured 1.66.1 presentation wire", str(actual))

    try:
        _need(isinstance(observation, dict), "observation must be a dict")
        _need(observation.get("journey") == PRESENTATION_CASE and observation.get("contract") == PRESENTATION_CONTRACT,
              "missing versioned presentation contract identity")
        _need(bool(observation.get("scope")) and bool(observation.get("url")), "missing scope/url")
        mark("contract")

        stages = observation.get("stages")
        _need(isinstance(stages, list) and tuple(s.get("name") for s in stages) == tuple(PRESENTATION_STAGES),
              f"stages must be exactly the {len(PRESENTATION_STAGES)} measured stages in order")
        for stage in stages:
            _need(isinstance(stage.get("dom"), dict) and isinstance(stage.get("screenshot"), dict)
                  and isinstance(stage.get("new_frames"), list), f"stage {stage.get('name')} lacks dom/screenshot/new_frames")
        mark("stage_set")

        source = observation.get("source") or {}
        side = "python" if observation.get("scope") == "PYTHON SIDE ONLY" else "native"
        path, pinned = PRESENTATION_SOURCE_PINS[side]
        _need(source.get("file") == path and source.get("sha256") == pinned,
              f"driven source is not the pinned {path} of this contract")
        mark("source_pin")

        timeline = _timeline(stages[0])
        _need(timeline == PRESENTATION_TIMELINE, "the delta timeline (kinds, paths, shapes) differs from the measured page")
        mark("timeline")

        transients = [entry for entry in timeline if entry["kind"] == "new_transient"]
        _need(len(transients) == 2 and transients[0]["path"] == [0, 0] and transients[1]["path"] == [0, 0],
              "the spinner must ride two transient deltas at path [0, 0]")
        _need(transients[1]["elements"] == [], "the second transient must clear the spinner")
        _need(len(transients[0]["elements"]) == 1, "the active transient must carry exactly one element")
        spinner = (transients[0]["elements"][0] or {}).get("spinner") or {}
        _need(spinner.get("text") == "Loading data" and spinner.get("cache") is None and spinner.get("showTime") is None,
              "the active spinner shape differs from the measured wire")
        mark("spinner_lifecycle")

        toasts = [entry for entry in timeline if entry.get("kind") == "new_element" and entry.get("element") == "toast"]
        _need(len(toasts) == 1 and toasts[0]["path"] == [2, 0], "exactly one toast at the dedicated root path [2, 0]")
        toast = ((toasts[0].get("full") or {}).get("toast")) or {}
        _need(toast == {"body": "Saved successfully", "icon": "\u2705", "duration": 4}, f"the toast fields differ: {toast}")
        _need((toasts[0].get("full") or {}).get("hasOneShotEffect") is True, "the toast is one-shot")
        mark("toast_wire")

        balloons = [entry for entry in timeline if entry.get("kind") == "new_element" and entry.get("element") == "balloons"]
        _need(len(balloons) == 1 and balloons[0]["path"] == [0, 1], "exactly one balloons element at the next container slot")
        _need((balloons[0].get("full") or {}).get("balloons") == {"show": True}, "the balloons fields differ")
        _need((balloons[0].get("full") or {}).get("hasOneShotEffect") is True, "the balloons element is one-shot")
        mark("balloons_wire")

        page = (observation.get("url") or "").rstrip("/")
        dom_text = _json.dumps({key: (stages[0]["dom"] or {}).get(key) for key in ("markdowns", "alerts", "toasts", "spinners", "exceptions")}, ensure_ascii=False)
        dom_text = dom_text.replace(page, "<page>")
        _need(_json.loads(dom_text) == PRESENTATION_DOM, "the resolved DOM projection differs from the measured page")
        mark("dom_projection")

        _need(not ((stages[0]["dom"] or {}).get("exceptions") or []), "the page renders an exception")
        for frame in stages[0]["new_frames"]:
            delta = (frame.get("summary") or {}).get("delta") or {}
            _need(delta.get("element") != "exception", "the stream carries an exception element")
        mark("no_exceptions")

        finishes = [((frame.get("summary") or {}).get("script_finished") or {}).get("status")
                    for frame in stages[0]["new_frames"]
                    if (frame.get("summary") or {}).get("type") == "script_finished"]
        _need(finishes == [0], "the run must finish exactly once with FINISHED_SUCCESSFULLY")
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
        for name in PRESENTATION_REQUIRED:
            if name not in verified:
                fail(name, str(exc))
        return checks
    return checks


def presentation_result(*, observation=None):
    """Aggregate the contract checks the way the shared journey judge does."""
    checks = presentation_checks(observation=observation)
    failures = [check for check in checks if not check["ok"]]
    return {
        "checks": checks,
        "counts": {"expected": len(checks), "executed": len(checks), "asserted": len(checks) - len(failures)},
        "failures": failures,
        "ok": not failures and len(checks) == len(PRESENTATION_REQUIRED),
    }
