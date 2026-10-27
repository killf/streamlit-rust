"""The strict elements contract: journey-elements-v1.

This criterion judges the observation the committed collector
(elements_capture.py) writes, against the Python 1.66.1 reference page
measured on 2026-10-25 with the official frontend. One page exercises the
fifteen promoted APIs (title, header, caption, badge, divider, code,
markdown, write, columns, container, form, text_input, form_submit_button,
table, bar_chart); the collector states no verdict, this module owns it:

* the normalized wire stream of each stage equals the measured reference —
  element kinds and bodies in order, the columns/container/form block
  structure, and the text-input/submit widget fields (the only tolerated
  difference is the Rust side's documented leading main-block add_block);
* the vega-lite shape matches the measured chart (bar mark, ordinal x,
  quantitative y with integer tick axis, v5.20.1 schema, one named arrow
  dataset) without comparing altair decoration or arrow bytes;
* the ordered DOM fingerprint (testids and texts, headings, code blocks,
  table text, chart bar count, the form note value and the echo lines)
  equals the reference on both stages, including the typed-and-applied
  end state; every stage finishes FINISHED_SUCCESSFULLY with no exception.
"""

from __future__ import annotations

import hashlib
import json
import pathlib

ELEMENTS_CASE = "elements-sequence"
ELEMENTS_CONTRACT = "journey-elements-v1"

ELEMENTS_STAGES = ["01-load", "02-apply"]

# The normalized wire stream per stage: deltas only, ids and hashes dropped.
# The table entry pins the arrow payload's presence, not its bytes.
ELEMENTS_WIRE = {
 "01-load": [
  {
   "element": "heading",
   "body": "Elements parity title"
  },
  {
   "element": "heading",
   "body": "Header level"
  },
  {
   "element": "markdown",
   "body": "A caption line"
  },
  {
   "element": "markdown",
   "body": ":blue-badge[BETA]"
  },
  {
   "element": "markdown",
   "body": "---"
  },
  {
   "element": "code"
  },
  {
   "element": "markdown",
   "body": "**bold** and `inline`"
  },
  {
   "element": "markdown",
   "body": "plain write"
  },
  {
   "add_block": "flex_container"
  },
  {
   "add_block": "column"
  },
  {
   "add_block": "column"
  },
  {
   "element": "markdown",
   "body": "left column"
  },
  {
   "element": "markdown",
   "body": "right column"
  },
  {
   "add_block": "flex_container"
  },
  {
   "element": "markdown",
   "body": "inside container"
  },
  {
   "add_block": "form"
  },
  {
   "element": "text_input",
   "widget": {
    "label": "Note",
    "default": "hello",
    "formId": "note_form"
   }
  },
  {
   "element": "button",
   "widget": {
    "label": "Apply",
    "type": "secondary",
    "formId": "note_form",
    "isFormSubmitter": True
   }
  },
  {
   "element": "markdown",
   "body": "form: note='hello' submitted=False"
  },
  {
   "element": "table",
   "table_has_arrow": True
  },
  {
   "element": "vega_lite_chart",
   "chart": {
    "mark": "bar",
    "x": {
     "field": "kind",
     "type": "ordinal"
    },
    "y": {
     "field": "count",
     "type": "quantitative"
    },
    "y_axis": {
     "grid": True,
     "tickMinStep": 1
    },
    "schema": "https://vega.github.io/schema/vega-lite/v5.20.1.json",
    "has_data_name": True,
    "datasets": 1
   }
  },
  {
   "finish": 0
  }
 ],
 "02-apply": [
  {
   "element": "heading",
   "body": "Elements parity title"
  },
  {
   "element": "heading",
   "body": "Header level"
  },
  {
   "element": "markdown",
   "body": "A caption line"
  },
  {
   "element": "markdown",
   "body": ":blue-badge[BETA]"
  },
  {
   "element": "markdown",
   "body": "---"
  },
  {
   "element": "code"
  },
  {
   "element": "markdown",
   "body": "**bold** and `inline`"
  },
  {
   "element": "markdown",
   "body": "plain write"
  },
  {
   "add_block": "flex_container"
  },
  {
   "add_block": "column"
  },
  {
   "add_block": "column"
  },
  {
   "element": "markdown",
   "body": "left column"
  },
  {
   "element": "markdown",
   "body": "right column"
  },
  {
   "add_block": "flex_container"
  },
  {
   "element": "markdown",
   "body": "inside container"
  },
  {
   "add_block": "form"
  },
  {
   "element": "text_input",
   "widget": {
    "label": "Note",
    "default": "hello",
    "formId": "note_form"
   }
  },
  {
   "element": "button",
   "widget": {
    "label": "Apply",
    "type": "secondary",
    "formId": "note_form",
    "isFormSubmitter": True
   }
  },
  {
   "element": "markdown",
   "body": "form: note='hello typed' submitted=True"
  },
  {
   "element": "table",
   "table_has_arrow": True
  },
  {
   "element": "vega_lite_chart",
   "chart": {
    "mark": "bar",
    "x": {
     "field": "kind",
     "type": "ordinal"
    },
    "y": {
     "field": "count",
     "type": "quantitative"
    },
    "y_axis": {
     "grid": True,
     "tickMinStep": 1
    },
    "schema": "https://vega.github.io/schema/vega-lite/v5.20.1.json",
    "has_data_name": True,
    "datasets": 1
   }
  },
  {
   "finish": 0
  }
 ]
}

# The ordered DOM fingerprint per stage.
ELEMENTS_DOM = {
 "01-load": {
  "items": [
   {
    "t": "stHeader",
    "x": "Deploy"
   },
   {
    "t": "stVerticalBlock",
    "x": "Elements parity title Header level A caption line BETA print('hello') bold and inline plain write left column right column inside container Note Apply form: not"
   },
   {
    "t": "stMarkdown",
    "x": "A caption line"
   },
   {
    "t": "stMarkdown",
    "x": "BETA"
   },
   {
    "t": "stMarkdown",
    "x": ""
   },
   {
    "t": "stMarkdown",
    "x": "bold and inline"
   },
   {
    "t": "stMarkdown",
    "x": "plain write"
   },
   {
    "t": "stHorizontalBlock",
    "x": "left column right column"
   },
   {
    "t": "stColumn",
    "x": "left column"
   },
   {
    "t": "stVerticalBlock",
    "x": "left column"
   },
   {
    "t": "stMarkdown",
    "x": "left column"
   },
   {
    "t": "stColumn",
    "x": "right column"
   },
   {
    "t": "stVerticalBlock",
    "x": "right column"
   },
   {
    "t": "stMarkdown",
    "x": "right column"
   },
   {
    "t": "stVerticalBlock",
    "x": "inside container"
   },
   {
    "t": "stMarkdown",
    "x": "inside container"
   },
   {
    "t": "stForm",
    "x": "Note Apply"
   },
   {
    "t": "stVerticalBlock",
    "x": "Note Apply"
   },
   {
    "t": "stTextInput",
    "x": "Note"
   },
   {
    "t": "stFormSubmitButton",
    "x": "Apply"
   },
   {
    "t": "stMarkdown",
    "x": "form: note='hello' submitted=False"
   },
   {
    "t": "stTable",
    "x": "kind count a 1 b 2"
   },
   {
    "t": "stVegaLiteChart",
    "x": "a b kind 0 1 2 count"
   }
  ],
  "headings": [
   "H1:Elements parity title",
   "H2:Header level"
  ],
  "code_blocks": [
   "print('hello')",
   "print('hello')"
  ],
  "note": "hello",
  "chart_bars": 2,
  "markdowns": [
   "A caption line",
   "BETA",
   "",
   "bold and inline",
   "plain write",
   "left column",
   "right column",
   "inside container",
   "form: note='hello' submitted=False"
  ],
  "exceptions": []
 },
 "02-apply": {
  "items": [
   {
    "t": "stHeader",
    "x": "Deploy"
   },
   {
    "t": "stVerticalBlock",
    "x": "Elements parity title Header level A caption line BETA print('hello') bold and inline plain write left column right column inside container Note Apply form: not"
   },
   {
    "t": "stMarkdown",
    "x": "A caption line"
   },
   {
    "t": "stMarkdown",
    "x": "BETA"
   },
   {
    "t": "stMarkdown",
    "x": ""
   },
   {
    "t": "stMarkdown",
    "x": "bold and inline"
   },
   {
    "t": "stMarkdown",
    "x": "plain write"
   },
   {
    "t": "stHorizontalBlock",
    "x": "left column right column"
   },
   {
    "t": "stColumn",
    "x": "left column"
   },
   {
    "t": "stVerticalBlock",
    "x": "left column"
   },
   {
    "t": "stMarkdown",
    "x": "left column"
   },
   {
    "t": "stColumn",
    "x": "right column"
   },
   {
    "t": "stVerticalBlock",
    "x": "right column"
   },
   {
    "t": "stMarkdown",
    "x": "right column"
   },
   {
    "t": "stVerticalBlock",
    "x": "inside container"
   },
   {
    "t": "stMarkdown",
    "x": "inside container"
   },
   {
    "t": "stForm",
    "x": "Note Apply"
   },
   {
    "t": "stVerticalBlock",
    "x": "Note Apply"
   },
   {
    "t": "stTextInput",
    "x": "Note"
   },
   {
    "t": "stFormSubmitButton",
    "x": "Apply"
   },
   {
    "t": "stMarkdown",
    "x": "form: note='hello typed' submitted=True"
   },
   {
    "t": "stTable",
    "x": "kind count a 1 b 2"
   },
   {
    "t": "stVegaLiteChart",
    "x": "a b kind 0 1 2 count"
   }
  ],
  "headings": [
   "H1:Elements parity title",
   "H2:Header level"
  ],
  "code_blocks": [
   "print('hello')",
   "print('hello')"
  ],
  "note": "hello typed",
  "chart_bars": 2,
  "markdowns": [
   "A caption line",
   "BETA",
   "",
   "bold and inline",
   "plain write",
   "left column",
   "right column",
   "inside container",
   "form: note='hello typed' submitted=True"
  ],
  "exceptions": []
 }
}

# Application paths label the captured roles; source content is not a gate.
ELEMENTS_SOURCE_FILES = {
    "python": "tests/reference/elements_app.py",
    "native": "streamlit/examples/elements.rs",
}

ELEMENTS_FORM_WIDGETS = {
 "01-load": {
  "Note": {
   "label": "Note",
   "default": "hello",
   "formId": "note_form"
  },
  "Apply": {
   "label": "Apply",
   "type": "secondary",
   "formId": "note_form",
   "isFormSubmitter": True
  }
 },
 "02-apply": {
  "Note": {
   "label": "Note",
   "default": "hello",
   "formId": "note_form"
  },
  "Apply": {
   "label": "Apply",
   "type": "secondary",
   "formId": "note_form",
   "isFormSubmitter": True
  }
 }
}

# The measured normalized chart shape.
ELEMENTS_CHART = {
 "mark": "bar",
 "x": {
  "field": "kind",
  "type": "ordinal"
 },
 "y": {
  "field": "count",
  "type": "quantitative"
 },
 "y_axis": {
  "grid": True,
  "tickMinStep": 1
 },
 "schema": "https://vega.github.io/schema/vega-lite/v5.20.1.json",
 "has_data_name": True,
 "datasets": 1
}

ELEMENTS_REQUIRED = (
    "contract", "stage_set", "wire_stream", "dom_fingerprint",
    "form_widgets", "chart_shape", "echo_and_note", "finishes",
    "no_exceptions", "png_sources",
)


def _record(checks, name, ok, expected, actual):
    checks.append({"step": ELEMENTS_CASE, "check": name, "expected": expected, "actual": actual, "ok": bool(ok)})


def _need(condition, message):
    if not condition:
        raise ValueError(message)


def _normalize_delta(delta):
    kind = delta.get("type")
    if kind == "add_block":
        return {"add_block": delta.get("block_type")}
    if kind == "new_element":
        element = delta.get("element")
        entry = {"element": element}
        if delta.get("body") is not None:
            entry["body"] = delta["body"]
        widget = delta.get("widget") or {}
        if widget:
            entry["widget"] = {key: widget[key] for key in ("label", "default", "type", "formId", "isFormSubmitter") if key in widget}
        if element == "vega_lite_chart":
            chart = ((delta.get("element_full") or {}).get("vegaLiteChart")) or {}
            try:
                spec = json.loads(chart.get("spec") or "{}")
            except (TypeError, ValueError):
                raise ValueError("vega spec is not valid JSON")
            entry["chart"] = {
                "mark": (spec.get("mark") or {}).get("type"),
                "x": {k: (spec.get("encoding", {}).get("x") or {}).get(k) for k in ("field", "type")},
                "y": {k: (spec.get("encoding", {}).get("y") or {}).get(k) for k in ("field", "type")},
                "y_axis": (spec.get("encoding", {}).get("y") or {}).get("axis"),
                "schema": spec.get("$schema"),
                "has_data_name": bool((spec.get("data") or {}).get("name")),
                "datasets": len(chart.get("datasets") or []),
            }
        if element == "table":
            table = ((delta.get("element_full") or {}).get("table")) or {}
            entry["table_has_arrow"] = bool(((table.get("arrowData") or {}).get("data")))
        return entry
    return {"other": kind}


def _wire_stream(stage):
    out = []
    for frame in stage.get("new_frames") or []:
        summary = frame.get("summary") or {}
        delta = summary.get("delta")
        if delta:
            out.append(_normalize_delta(delta))
        elif summary.get("type") == "script_finished":
            out.append({"finish": (summary.get("script_finished") or {}).get("status")})
    # The documented Rust main-block difference: strip a leading
    # add_block(vertical) that appears before any element delta.
    first_delta = next((index for index, entry in enumerate(out) if "element" in entry or "add_block" in entry), None)
    if first_delta is not None and out[first_delta].get("add_block") == "vertical":
        out = out[:first_delta] + out[first_delta + 1:]
    return out


def _form_widgets(stage):
    found = {}
    for frame in stage.get("new_frames") or []:
        widget = ((frame.get("summary") or {}).get("delta") or {}).get("widget") or {}
        if widget.get("label") in ("Note", "Apply"):
            found[widget["label"]] = {key: widget.get(key) for key in ("label", "default", "type", "formId", "isFormSubmitter") if key in widget}
    return found


def elements_checks(*, observation=None):
    checks = []
    verified = set()

    def mark(name):
        verified.add(name)
        _record(checks, name, True, "the measured 1.66.1 elements page", "contract verified")

    def fail(name, actual):
        _record(checks, name, False, "the measured 1.66.1 elements page", str(actual))

    try:
        _need(isinstance(observation, dict), "observation must be a dict")
        _need(observation.get("journey") == ELEMENTS_CASE and observation.get("contract") == ELEMENTS_CONTRACT,
              "missing versioned elements contract identity")
        _need(bool(observation.get("scope")) and bool(observation.get("url")), "missing scope/url")
        mark("contract")

        stages = observation.get("stages")
        _need(isinstance(stages, list) and tuple(s.get("name") for s in stages) == tuple(ELEMENTS_STAGES),
              f"stages must be exactly the {len(ELEMENTS_STAGES)} measured stages in order")
        for stage in stages:
            _need(isinstance(stage.get("dom"), dict) and isinstance(stage.get("screenshot"), dict)
                  and isinstance(stage.get("new_frames"), list), f"stage {stage.get('name')} lacks dom/screenshot/new_frames")
        mark("stage_set")

        for stage in stages:
            stream = _wire_stream(stage)
            _need(stream == ELEMENTS_WIRE[stage["name"]],
                  f"stage {stage['name']} normalized wire stream differs from the measured reference")
        mark("wire_stream")

        for stage in stages:
            dom = {key: (stage["dom"] or {}).get(key) for key in ("items", "headings", "code_blocks", "note", "chart_bars", "markdowns", "exceptions")}
            _need(dom == ELEMENTS_DOM[stage["name"]], f"stage {stage['name']} DOM fingerprint differs")
        mark("dom_fingerprint")

        for stage in stages:
            _need(_form_widgets(stage) == ELEMENTS_FORM_WIDGETS[stage["name"]],
                  f"stage {stage['name']} form widget fields differ")
        mark("form_widgets")

        for stage in stages:
            charts = [entry for entry in _wire_stream(stage) if entry.get("element") == "vega_lite_chart"]
            _need(len(charts) == 1 and charts[0].get("chart") == ELEMENTS_CHART,
                  f"stage {stage['name']} chart shape differs")
            _need((stage["dom"] or {}).get("chart_bars") == 2, f"stage {stage['name']} must render two bars")
        mark("chart_shape")

        for stage in stages:
            dom = stage["dom"] or {}
            expected = ELEMENTS_DOM[stage["name"]]
            echo = [line for line in dom.get("markdowns") or [] if line.startswith("form: note=")]
            _need(echo == [line for line in expected["markdowns"] if line.startswith("form: note=")],
                  f"stage {stage['name']} form echo differs")
            _need(dom.get("note") == expected["note"], f"stage {stage['name']} note value differs")
        mark("echo_and_note")

        for stage in stages:
            finishes = [((frame.get("summary") or {}).get("script_finished") or {}).get("status")
                        for frame in stage.get("new_frames") or []
                        if (frame.get("summary") or {}).get("type") == "script_finished"]
            _need(finishes == [0], f"stage {stage['name']} must finish exactly once with FINISHED_SUCCESSFULLY")
        mark("finishes")

        for stage in stages:
            _need(not ((stage["dom"] or {}).get("exceptions") or []),
                  f"stage {stage['name']} renders an exception")
            for frame in stage.get("new_frames") or []:
                delta = (frame.get("summary") or {}).get("delta") or {}
                _need(delta.get("element") != "exception", f"stage {stage['name']} streams an exception element")
        mark("no_exceptions")

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
    except (ValueError, TypeError, KeyError, IndexError, OSError, AttributeError) as exc:
        for name in ELEMENTS_REQUIRED:
            if name not in verified:
                fail(name, str(exc))
        return checks
    return checks


def elements_result(*, observation=None):
    """Aggregate the contract checks the way the shared journey judge does."""
    checks = elements_checks(observation=observation)
    failures = [check for check in checks if not check["ok"]]
    return {
        "checks": checks,
        "counts": {"expected": len(checks), "executed": len(checks), "asserted": len(checks) - len(failures)},
        "failures": failures,
        "ok": not failures and len(checks) == len(ELEMENTS_REQUIRED),
    }
