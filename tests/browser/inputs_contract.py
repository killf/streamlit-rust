"""The strict input-widget contract: journey-inputs-v1.

This criterion judges the observation the committed collector
(inputs_capture.py) writes, against the Python 1.66.1 wire measured on
2026-10-25 with the official frontend and recorded in .codex/compatibility.md
(Input widget wire). The collector states no verdict; this module owns it:

* four widgets render with the exact measured wire configs: radio defaults to
  an option index with a text-valued state, multiselect defaults to [i32]
  indices with accept_new_options false and select_all 1000 and a
  string-array state, number_input carries format %d, the INT enum, has_min /
  has_max plus the bound doubles and an int-valued state, and text_area
  defaults to the given string with a string-valued state;
* every stage carries exactly one rerun_script whose widget-state snapshot
  equals the accumulated measured values (the page-load run sends no states);
  radio and multiselect commit their picks immediately, while number_input
  and text_area commit on blur — the typed text sits in the DOM projection
  while the widget state keeps the previously committed value until the next
  stage's click blurs the control;
* the DOM echoes the measured Python-repr strings and holds the driven
  control values, no exception renders, and every stage's run finishes
  FINISHED_SUCCESSFULLY.
"""

from __future__ import annotations

import hashlib
import pathlib

INPUTS_CASE = "inputs-sequence"
INPUTS_CONTRACT = "journey-inputs-v1"

INPUTS_STAGES = ["01-load", "02-radio-sms", "03-multiselect-beta", "04-number-42", "05-textarea-append"]

# The exact measured wire config of each widget on first render.
INPUTS_WIRE = {
 "Channel": {
  "label": "Channel",
  "default": 0,
  "options": [
   "email",
   "sms",
   "push"
  ],
  "labelVisibility": {}
 },
 "Tags": {
  "label": "Tags",
  "default": [
   0
  ],
  "options": [
   "alpha",
   "beta",
   "gamma"
  ],
  "labelVisibility": {},
  "acceptNewOptions": False,
  "selectAll": 1000
 },
 "Count": {
  "label": "Count",
  "format": "%d",
  "hasMin": True,
  "hasMax": True,
  "default": 7.0,
  "step": 1.0,
  "max": 100.0,
  "labelVisibility": {}
 },
 "Note": {
  "label": "Note",
  "default": "first line\nsecond line",
  "labelVisibility": {}
 }
}

# The widget-state snapshot each stage's single rerun_script carries. The
# initial page-load run sends one rerun_script with no states at all.
INPUTS_STATES = {
 "01-load": {},
 "02-radio-sms": {
  "Channel": {
   "field": "string_value",
   "data": "sms"
  },
  "Tags": {
   "field": "string_array_value",
   "data": [
    "alpha"
   ]
  },
  "Count": {
   "field": "int_value",
   "data": 7
  },
  "Note": {
   "field": "string_value",
   "data": "first line\nsecond line"
  }
 },
 "03-multiselect-beta": {
  "Channel": {
   "field": "string_value",
   "data": "sms"
  },
  "Tags": {
   "field": "string_array_value",
   "data": [
    "alpha",
    "beta"
   ]
  },
  "Count": {
   "field": "int_value",
   "data": 7
  },
  "Note": {
   "field": "string_value",
   "data": "first line\nsecond line"
  }
 },
 "04-number-42": {
  "Channel": {
   "field": "string_value",
   "data": "sms"
  },
  "Tags": {
   "field": "string_array_value",
   "data": [
    "alpha",
    "beta"
   ]
  },
  "Count": {
   "field": "int_value",
   "data": 7
  },
  "Note": {
   "field": "string_value",
   "data": "first line\nsecond line"
  }
 },
 "05-textarea-append": {
  "Channel": {
   "field": "string_value",
   "data": "sms"
  },
  "Tags": {
   "field": "string_array_value",
   "data": [
    "alpha",
    "beta"
   ]
  },
  "Count": {
   "field": "int_value",
   "data": 42
  },
  "Note": {
   "field": "string_value",
   "data": "first line\nsecond line"
  }
 }
}

# The touched widget of each driven stage and its measured landing value.
INPUTS_TOUCHED = {
 "02-radio-sms": [
  "Channel",
  "sms"
 ],
 "03-multiselect-beta": [
  "Tags",
  [
   "alpha",
   "beta"
  ]
 ],
 "04-number-42": [
  "Count",
  7
 ],
 "05-textarea-append": [
  "Note",
  "first line\nsecond line"
 ]
}

# The DOM projection of the four controls after each stage: the radio label,
# checked index and option texts, the multiselect chips, the number input
# value and the text area value.
INPUTS_DOM = {
 "01-load": {
  "radio": {
   "label": "Channel",
   "checked": 1,
   "value": [
    "Channel",
    "email",
    "sms",
    "push"
   ]
  },
  "multiselect": {
   "chips": [],
   "options": []
  },
  "number": {
   "value": "7"
  },
  "textarea": {
   "value": "first line\nsecond line"
  }
 },
 "02-radio-sms": {
  "radio": {
   "label": "Channel",
   "checked": 2,
   "value": [
    "Channel",
    "email",
    "sms",
    "push"
   ]
  },
  "multiselect": {
   "chips": [],
   "options": []
  },
  "number": {
   "value": "7"
  },
  "textarea": {
   "value": "first line\nsecond line"
  }
 },
 "03-multiselect-beta": {
  "radio": {
   "label": "Channel",
   "checked": 2,
   "value": [
    "Channel",
    "email",
    "sms",
    "push"
   ]
  },
  "multiselect": {
   "chips": [],
   "options": []
  },
  "number": {
   "value": "7"
  },
  "textarea": {
   "value": "first line\nsecond line"
  }
 },
 "04-number-42": {
  "radio": {
   "label": "Channel",
   "checked": 2,
   "value": [
    "Channel",
    "email",
    "sms",
    "push"
   ]
  },
  "multiselect": {
   "chips": [],
   "options": []
  },
  "number": {
   "value": "42"
  },
  "textarea": {
   "value": "first line\nsecond line"
  }
 },
 "05-textarea-append": {
  "radio": {
   "label": "Channel",
   "checked": 2,
   "value": [
    "Channel",
    "email",
    "sms",
    "push"
   ]
  },
  "multiselect": {
   "chips": [],
   "options": []
  },
  "number": {
   "value": "42"
  },
  "textarea": {
   "value": "first line\nsecond line third"
  }
 }
}

# The measured Python-repr echo lines of each stage end state, identical on
# both runtimes because the driven applications are mirrors.
INPUTS_REPRS = {
 "01-load": [
  "channel='email'",
  "tags=['alpha']",
  "count=7 type=int",
  "note='first line\\nsecond line'"
 ],
 "02-radio-sms": [
  "channel='sms'",
  "tags=['alpha']",
  "count=7 type=int",
  "note='first line\\nsecond line'"
 ],
 "03-multiselect-beta": [
  "channel='sms'",
  "tags=['alpha', 'beta']",
  "count=7 type=int",
  "note='first line\\nsecond line'"
 ],
 "04-number-42": [
  "channel='sms'",
  "tags=['alpha', 'beta']",
  "count=7 type=int",
  "note='first line\\nsecond line'"
 ],
 "05-textarea-append": [
  "channel='sms'",
  "tags=['alpha', 'beta']",
  "count=42 type=int",
  "note='first line\\nsecond line'"
 ]
}

# The driven application source is pinned per side; a capture of another
# source is not this contract's evidence.
INPUTS_SOURCE_PINS = {
    "python": ("tests/reference/inputs_app.py", "cb884ee2a6487585d63d9254cc353e42704cbd9b9f832732cd0e0a35d27da5bf"),
    "native": ("streamlit/examples/inputs.rs", "1052058ec8ed7d354853e611ecbf8e0986a369093794e80467e5d6448acfc309"),
}

INPUTS_REQUIRED = (
    "contract", "stage_set", "source_pin", "wire_configs", "state_snapshots",
    "driven_landings", "returned_reprs", "dom_values", "no_exceptions",
    "finishes", "png_sources",
)


def _record(checks, name, ok, expected, actual):
    checks.append({"step": INPUTS_CASE, "check": name, "expected": expected, "actual": actual, "ok": bool(ok)})


def _need(condition, message):
    if not condition:
        raise ValueError(message)


def _widget_wires(frames):
    wires = {}
    for frame in frames:
        delta = (frame.get("summary") or {}).get("delta") or {}
        widget = delta.get("widget") or {}
        if widget:
            entry = dict(widget)
            entry.pop("id", None)
            wires[widget.get("label")] = entry
    return wires


def _state_snapshot(frames):
    snapshot = {}
    reruns = 0
    for frame in frames:
        summary = frame.get("summary") or {}
        reruns += summary.get("type") == "rerun_script"
        for state in (summary.get("rerun_script") or {}).get("widget_states") or []:
            data = (state.get("value_full") or {}).get("data")
            if data is None:
                data = state.get("value")
            snapshot[state.get("id")] = {"field": state.get("value_field"), "data": data}
    return snapshot, reruns


def _dom_values(dom):
    return {key: dom.get(key) for key in ("radio", "multiselect", "number", "textarea")}


def inputs_checks(*, observation=None):
    checks = []
    verified = set()

    def mark(name):
        verified.add(name)
        _record(checks, name, True, "the measured 1.66.1 input widget wire", "contract verified")

    def fail(name, actual):
        _record(checks, name, False, "the measured 1.66.1 input widget wire", str(actual))

    try:
        _need(isinstance(observation, dict), "observation must be a dict")
        _need(observation.get("journey") == INPUTS_CASE and observation.get("contract") == INPUTS_CONTRACT,
              "missing versioned inputs contract identity")
        _need(bool(observation.get("scope")) and bool(observation.get("url")), "missing scope/url")
        mark("contract")

        stages = observation.get("stages")
        _need(isinstance(stages, list) and tuple(s.get("name") for s in stages) == tuple(INPUTS_STAGES),
              f"stages must be exactly the {len(INPUTS_STAGES)} measured stages in order")
        for stage in stages:
            _need(isinstance(stage.get("dom"), dict) and isinstance(stage.get("screenshot"), dict)
                  and isinstance(stage.get("new_frames"), list), f"stage {stage.get('name')} lacks dom/screenshot/new_frames")
        mark("stage_set")

        source = observation.get("source") or {}
        side = "python" if observation.get("scope") == "PYTHON SIDE ONLY" else "native"
        path, pinned = INPUTS_SOURCE_PINS[side]
        _need(source.get("file") == path and source.get("sha256") == pinned,
              f"driven source is not the pinned {path} of this contract")
        mark("source_pin")

        _need(_widget_wires(stages[0]["new_frames"]) == INPUTS_WIRE,
              "the four first-render widget wire configs differ from the measured table")
        mark("wire_configs")

        label_by_id = {}
        for frame in stages[0]["new_frames"]:
            delta = (frame.get("summary") or {}).get("delta") or {}
            widget = delta.get("widget") or {}
            if widget:
                label_by_id[widget.get("id")] = widget.get("label")
        for stage in stages:
            snapshot, reruns = _state_snapshot(stage["new_frames"])
            _need(reruns == 1, f"stage {stage['name']} must carry exactly one rerun_script")
            _need({label_by_id.get(i): v for i, v in snapshot.items()} == INPUTS_STATES[stage["name"]],
                  f"stage {stage['name']} widget-state snapshot differs from the measured accumulation")
        mark("state_snapshots")

        for name, (label, landing) in INPUTS_TOUCHED.items():
            stage = next(s for s in stages if s["name"] == name)
            snapshot, _ = _state_snapshot(stage["new_frames"])
            _need(next(v["data"] for i, v in snapshot.items() if label_by_id.get(i) == label) == landing,
                  f"stage {name}: {label} must land on the measured {landing!r}")
        mark("driven_landings")

        for stage in stages:
            echo = [line for line in (stage["dom"].get("markdowns") or []) if "=" in line]
            _need(echo == INPUTS_REPRS[stage["name"]], f"stage {stage['name']} echo reprs differ")
        mark("returned_reprs")

        for stage in stages:
            _need(_dom_values(stage["dom"]) == INPUTS_DOM[stage["name"]],
                  f"stage {stage['name']} control DOM projection differs from the measured table")
        mark("dom_values")

        for stage in stages:
            _need(not (stage["dom"].get("exceptions") or []),
                  f"stage {stage['name']} renders an exception")
            for frame in stage["new_frames"]:
                delta = (frame.get("summary") or {}).get("delta") or {}
                _need(delta.get("element") != "exception", f"stage {stage['name']} streams an exception element")
        mark("no_exceptions")

        for stage in stages:
            finishes = [((frame.get("summary") or {}).get("script_finished") or {}).get("status")
                        for frame in stage["new_frames"]
                        if (frame.get("summary") or {}).get("type") == "script_finished"]
            _need(finishes == [0], f"stage {stage['name']} must finish exactly once with FINISHED_SUCCESSFULLY")
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
        for name in INPUTS_REQUIRED:
            if name not in verified:
                fail(name, str(exc))
        return checks
    return checks


def inputs_result(*, observation=None):
    """Aggregate the contract checks the way the shared journey judge does."""
    checks = inputs_checks(observation=observation)
    failures = [check for check in checks if not check["ok"]]
    return {
        "checks": checks,
        "counts": {"expected": len(checks), "executed": len(checks), "asserted": len(checks) - len(failures)},
        "failures": failures,
        "ok": not failures and len(checks) == len(INPUTS_REQUIRED),
    }
