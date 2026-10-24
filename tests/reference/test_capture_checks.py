"""Regression tests for the click verification in the browser capture.

These cover the two misjudgements found in the independent review of C-P0-04:

B2  the smoke scenario used to accept a run in which three clicks produced only
    a single ``trigger_value=False`` and no server frame at all.  The counter
    example below is that run: it must now fail.
B1  a reconnect used to be "proved" by a stale DOM.  A click on the
    reconnected connection must carry a true trigger and a server answer on
    that same, new, connection.
"""

from __future__ import annotations

import pathlib
import sys
import types
import json
import os
import shutil
import subprocess

import pytest

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from capture_browser_trace import (  # noqa: E402
    SUITES,
    Capture,
    case_verdict,
    data_loop_verdict,
    WIDGET_DOM_JS,
    dom_value_for,
    parse_counter_texts,
    suite_counts,
    suite_failures,
    verify_click_windows,
    widget_value_matches,
    wire_value_of,
)


def trigger_frame(connection: int, value: bool = True, widget_id: str = "$$ID-x-pulse") -> dict:
    return {
        "direction": "client->server",
        "connection": connection,
        "decoded": {
            "message": "BackMsg",
            "type": "rerun_script",
            "rerun_script": {
                "widget_states": [
                    {"id": widget_id, "value_field": "trigger_value", "value": value}
                ]
            },
        },
    }


def completion_frame(connection: int, status: int = 0) -> dict:
    """A script_finished frame with the given ScriptFinishedStatus."""
    names = {
        0: "FINISHED_SUCCESSFULLY",
        1: "FINISHED_WITH_COMPILE_ERROR",
        2: "FINISHED_EARLY_FOR_RERUN",
        3: "FINISHED_FRAGMENT_RUN_SUCCESSFULLY",
    }
    return {
        "direction": "server->client",
        "connection": connection,
        "decoded": {
            "message": "ForwardMsg",
            "type": "script_finished",
            "script_finished": {"status": status, "status_name": names[status]},
        },
    }


def running_frame(connection: int) -> dict:
    """A session_status_changed that only says the script is running."""
    return {
        "direction": "server->client",
        "connection": connection,
        "decoded": {
            "message": "ForwardMsg",
            "type": "session_status_changed",
            "session_status_changed": {"script_is_running": True, "run_on_save": False},
        },
    }


def test_the_reviewers_counterexample_now_fails() -> None:
    """clicks=3, one trigger_value=False, zero server frames -> must not pass."""
    frames = [trigger_frame(0, value=False)]
    clicks = [
        {"click": 1, "start": 0, "end": 1},
        {"click": 2, "start": 1, "end": 1},
        {"click": 3, "start": 1, "end": 1},
    ]
    failures = verify_click_windows(frames, clicks)
    assert failures, "a false trigger with no server response must not pass"
    checks = {failure["check"] for failure in failures}
    assert "true_trigger" in checks
    assert "server_response" in checks
    assert {failure["step"] for failure in failures} == {"click-1", "click-2", "click-3"}


def test_a_click_without_a_server_response_fails() -> None:
    frames = [trigger_frame(0), completion_frame(0), trigger_frame(0)]
    clicks = [{"click": 1, "start": 0, "end": 2}, {"click": 2, "start": 2, "end": 3}]
    failures = verify_click_windows(frames, clicks)
    assert [failure["check"] for failure in failures] == ["server_response"]
    assert failures[0]["step"] == "click-2"


def test_a_response_on_another_connection_fails() -> None:
    frames = [trigger_frame(0), completion_frame(1)]
    clicks = [{"click": 1, "start": 0, "end": 2}]
    failures = verify_click_windows(frames, clicks)
    assert "same_connection" in {failure["check"] for failure in failures}


def test_a_reconnect_click_must_use_a_new_connection() -> None:
    stale = [trigger_frame(0), completion_frame(0)]
    window = [
        {
            "click": "post-reconnect",
            "start": 0,
            "end": 2,
            "require_new_connection": True,
            "connection_before": 0,
        }
    ]
    failures = verify_click_windows(stale, window)
    assert "new_connection" in {failure["check"] for failure in failures}

    fresh = [trigger_frame(1), completion_frame(1)]
    assert verify_click_windows(fresh, window) == []


def test_valid_clicks_pass() -> None:
    frames = [
        trigger_frame(0),
        completion_frame(0),
        trigger_frame(0),
        completion_frame(0),
    ]
    clicks = [{"click": 1, "start": 0, "end": 2}, {"click": 2, "start": 2, "end": 4}]
    assert verify_click_windows(frames, clicks) == []


def test_a_running_status_is_not_a_completion() -> None:
    """script_is_running=true says the server started, not that it finished."""
    frames = [trigger_frame(0), running_frame(0)]
    clicks = [{"click": 1, "start": 0, "end": 2}]
    failures = verify_click_windows(frames, clicks)
    assert [failure["check"] for failure in failures] == ["server_response"]


def test_a_completion_before_the_trigger_is_not_a_completion() -> None:
    frames = [completion_frame(0), trigger_frame(0)]
    clicks = [{"click": 1, "start": 0, "end": 2}]
    failures = verify_click_windows(frames, clicks)
    assert [failure["check"] for failure in failures] == ["server_response"]


def test_a_failed_script_finished_is_not_a_success() -> None:
    """status 1 is FINISHED_WITH_COMPILE_ERROR, not a successful run."""
    frames = [trigger_frame(0), completion_frame(0, status=1)]
    clicks = [{"click": 1, "start": 0, "end": 2}]
    failures = verify_click_windows(frames, clicks)
    assert [failure["check"] for failure in failures] == ["server_response"]
    assert "status" in failures[0]["actual"] or "FINISHED" in failures[0]["actual"]


def test_a_fragment_run_is_not_a_full_success() -> None:
    """status 3 is a fragment run, not the completion of the clicked run."""
    frames = [trigger_frame(0), completion_frame(0, status=3)]
    clicks = [{"click": 1, "start": 0, "end": 2}]
    failures = verify_click_windows(frames, clicks)
    assert [failure["check"] for failure in failures] == ["server_response"]


def test_counter_values_are_read_from_text_or_markdown() -> None:
    """The Rust counter renders its numbers as markdown, not as st.text."""
    assert parse_counter_texts(["Pulses: 3", "Script runs: 7"]) == {
        "pulses": "3",
        "script_runs": "7",
    }
    assert parse_counter_texts(["Pulses: 0", "Script runs: 1"]) == {
        "pulses": "0",
        "script_runs": "1",
    }


def test_a_missing_counter_is_absent_rather_than_empty() -> None:
    """An absent counter must not read as a valid value."""
    assert parse_counter_texts(["something else"]) == {}
    assert "pulses" not in parse_counter_texts(["Script runs: 4"])


def test_a_valueless_counter_is_ignored() -> None:
    assert parse_counter_texts(["Pulses:", "Script runs:"]) == {}


def test_a_different_label_is_not_read_as_the_counter() -> None:
    assert parse_counter_texts(["Pulse count: 3"]) == {}


class _StubRecorder:
    """A recorder that only counts the frames the stub browser produces."""

    def __init__(self, answer: bool) -> None:
        self.frames: list[dict] = []
        self.answer = answer
        self.label = "tab-a"

    def frame_count(self) -> int:
        return len(self.frames)

    def take(self) -> list[dict]:
        return list(self.frames)


class _StubBrowser:
    """A browser that clicks the button and, optionally, answers the click."""

    def __init__(self, recorder: _StubRecorder) -> None:
        self.recorder = recorder

    def observe(self) -> dict:
        return {"has_button": True}

    def click(self, selector: str) -> None:
        self.recorder.frames.append(trigger_frame(0))

    def run(self, *args) -> str:
        if args and args[0] == "wait" and self.recorder.answer:
            self.recorder.frames.append(completion_frame(0))
        return ""


def _drive_smoke(tmp_path, answer: bool):
    """Drive scenario_smoke itself against a stub browser.

    The capture object is built without its constructor, so the test needs
    neither agent-browser nor a running Chrome.  The windows are translated the
    way trace() translates them: with a single target the offset into the
    merged frame list is zero.
    """
    capture = Capture.__new__(Capture)
    capture.args = types.SimpleNamespace(clicks=1)
    capture.out_dir = tmp_path
    capture.steps = []
    capture.failures = []
    capture.notes = []
    capture.click_windows = []
    recorder = _StubRecorder(answer=answer)
    capture.ab = _StubBrowser(recorder)
    capture.recorders = [recorder]
    capture.scenario_smoke()
    windows = [
        {"click": w["click"], "start": w["start"], "end": w["end"]}
        for w in capture.click_windows
    ]
    return capture, recorder.frames, windows


def test_a_legal_smoke_click_passes_the_scenario_driver(tmp_path) -> None:
    """The smoke scenario must build a window that holds the click and its answer.

    The driver used to leave the window empty -- start and end were both the
    frame count from before the click -- so a click the server did answer was
    rejected by the helper.
    """
    capture, frames, windows = _drive_smoke(tmp_path, answer=True)
    assert capture.failures == []
    assert windows, "the smoke scenario must record a click window"
    assert windows[0]["end"] > windows[0]["start"], "the click window must not be empty"
    assert verify_click_windows(frames, windows) == []


def test_a_smoke_click_without_an_answer_fails_the_scenario_driver(tmp_path) -> None:
    """A click the server never answered must still fail."""
    capture, frames, windows = _drive_smoke(tmp_path, answer=False)
    assert windows, "the smoke scenario must record a click window"
    failures = verify_click_windows(frames, windows)
    assert failures, "a click without a server answer must fail"
    assert [failure["check"] for failure in failures] == ["server_response"]


def value_state_frame(connection: int, widget_id: str, value_field: str, value) -> dict:
    """A rerun_script that carries the new state of a value widget."""
    return {
        "direction": "client->server",
        "connection": connection,
        "decoded": {
            "message": "BackMsg",
            "type": "rerun_script",
            "rerun_script": {
                "widget_states": [
                    {"id": widget_id, "value_field": value_field, "value": value}
                ]
            },
        },
    }


def test_a_value_widget_window_needs_its_state_and_an_answer() -> None:
    """A selectbox, a slider or a checkbox send their value, not a trigger."""
    frames = [
        value_state_frame(0, "$$ID-x-group_by", "string_value", "region"),
        completion_frame(0),
    ]
    window = {"click": "selectbox-select", "start": 0, "end": 2, "widget": "$$ID-x-group_by"}
    assert verify_click_windows(frames, [window]) == []


def test_a_value_widget_without_an_answer_fails() -> None:
    """The same click, with no successful completion after it, must fail."""
    frames = [value_state_frame(0, "$$ID-x-group_by", "string_value", "region")]
    window = {"click": "selectbox-select", "start": 0, "end": 1, "widget": "$$ID-x-group_by"}
    failures = verify_click_windows(frames, [window])
    assert [failure["check"] for failure in failures] == ["server_response"]


def test_a_value_widget_window_rejects_a_button_trigger() -> None:
    """A trigger of another widget does not answer a value widget's window."""
    frames = [trigger_frame(0), completion_frame(0)]
    window = {"click": "selectbox-select", "start": 0, "end": 2, "widget": "$$ID-x-group_by"}
    failures = verify_click_windows(frames, [window])
    assert [failure["check"] for failure in failures] == ["true_trigger", "server_response"]
FAKE_DOM_JS = r"""function makeEl(tag, attrs, props, children) {
  const node = {
    tagName: String(tag).toUpperCase(),
    attrs: attrs || {},
    children: children || [],
    value: props && "value" in props ? props.value : undefined,
    checked: props && "checked" in props ? props.checked : undefined,
    disabled: props && "disabled" in props ? props.disabled : undefined,
    textContent: props && props.text ? props.text : "",
    innerText: props && props.text ? props.text : "",
  };
  node.getAttribute = (name) => (name in node.attrs ? node.attrs[name] : null);
  node.matches = (selector) => {
    const m = /^\[data-testid='(.*)'\]$/.exec(selector);
    if (m) return node.attrs["data-testid"] === m[1];
    return node.tagName === selector.toUpperCase();
  };
  node.querySelectorAll = (selector) => {
    const out = [];
    const walk = (parent) => {
      for (const child of parent.children) {
        if (child.matches(selector)) out.push(child);
        walk(child);
      }
    };
    walk(node);
    return out;
  };
  node.querySelector = (selector) => {
    const all = node.querySelectorAll(selector);
    return all.length ? all[0] : null;
  };
  return node;
}
function build(spec) {
  const nodes = (spec || []).map((w) => {
    if (w.kind === "selectbox")
      return makeEl("div", {"data-testid": "stSelectbox"}, {}, [makeEl("input", {}, {value: w.value})]);
    if (w.kind === "slider")
      return makeEl("div", {"data-testid": "stSlider"}, {}, [
        makeEl("div", {"data-testid": "stSliderThumbValue"}, {text: w.thumb || String(w.value)}),
        makeEl("input", {}, {value: String(w.value)}),
      ]);
    if (w.kind === "checkbox")
      return makeEl("div", {"data-testid": "stCheckbox"}, {}, [makeEl("input", {}, {checked: w.checked})]);
    if (w.kind === "text")
      return makeEl("div", {"data-testid": "stTextInput"}, {}, [makeEl("input", {}, {value: w.value})]);
    if (w.kind === "markdown")
      return makeEl("div", {"data-testid": "stMarkdown"}, {text: w.text});
    return makeEl("div", {}, {}, []);
  });
  const body = makeEl("body", {}, {}, nodes);
  return {
    querySelector: (s) => body.querySelector(s),
    querySelectorAll: (s) => body.querySelectorAll(s),
  };
}
const document = build(JSON.parse(process.env.FAKE_PAGE || "[]"));"""

HARNESS_SOURCE = HERE / "capture_browser_trace.py"


def _probe_source() -> str:
    """The probe the capture really runs.

    It is the constant the harness evaluates, so this test exercises the
    shipped probe and not a copy of it.
    """
    return WIDGET_DOM_JS


def _run_probe(tmp_path, probe: str, name: str, page: list) -> dict:
    """Run the probe against a fake DOM with Node."""
    node = shutil.which("node")
    if not node:
        pytest.skip("node is required for this regression (dev dependency: Node.js)")
    script = tmp_path / f"{name}.js"
    script.write_text(
        FAKE_DOM_JS + "\nconst __result = " + probe + ";\nconsole.log(__result);\n",
        encoding="utf-8",
    )
    done = subprocess.run(
        [node, str(script)], capture_output=True, text=True, timeout=60,
        env={**os.environ, "FAKE_PAGE": json.dumps(page)},
    )
    assert done.returncode == 0, done.stderr
    value = json.loads(done.stdout.strip())
    # The probe returns a JSON string; node prints it as it is.
    return json.loads(value) if isinstance(value, str) else value


THREE_WIDGETS = [
    {"kind": "selectbox", "value": "category"},
    {"kind": "slider", "value": 100, "thumb": "100"},
    {"kind": "checkbox", "checked": True},
]


def test_the_widget_probe_reads_each_widget_from_its_own_container(tmp_path) -> None:
    """Three widgets, three inputs: the probe must not read the first one for all."""
    result = _run_probe(tmp_path, _probe_source(), "current", THREE_WIDGETS)
    assert result["selectbox_value"] == "category"
    assert result["slider_value"] == "100"
    assert result["slider_thumb"] == "100"
    assert result["checkbox_checked"] is True


def test_the_widget_probe_ignores_an_input_that_belongs_to_another_widget(tmp_path) -> None:
    """Another input earlier on the page must not be read for the three widgets."""
    page = [{"kind": "text", "value": "a note"}] + THREE_WIDGETS
    result = _run_probe(tmp_path, _probe_source(), "page-with-text", page)
    assert result["selectbox_value"] == "category"
    assert result["slider_value"] == "100"
    assert result["checkbox_checked"] is True


def test_the_widget_probe_tolerates_a_page_without_those_widgets(tmp_path) -> None:
    """A status or counter page has no input widgets: the probe must not throw."""
    result = _run_probe(tmp_path, _probe_source(), "no-widgets", [{"kind": "markdown", "text": "hello"}])
    assert result["selectbox_value"] is None
    assert result["slider_value"] is None
    assert result["slider_thumb"] is None
    assert result["checkbox_checked"] is None
    assert result["markdown"] == ["hello"]


def test_the_same_probe_with_one_document_wide_input_query_is_wrong(tmp_path) -> None:
    """The control: with a document-wide query every widget reads the first input."""
    old = _probe_source()
    old = old.replace('sb?sb.querySelector("input"):null', 'sb?q("input"):null')
    old = old.replace('sl?sl.querySelector("input"):null', 'sl?q("input"):null')
    old = old.replace(
        'sl?sl.querySelector("[data-testid=\'stSliderThumbValue\']"):null',
        'q("[data-testid=\'stSliderThumbValue\']")',
    )
    old = old.replace('cbBox?cbBox.querySelector("input"):null', 'cbBox?q("input"):null')
    result = _run_probe(tmp_path, old, "document-wide", THREE_WIDGETS)
    # The slider reads the selectbox's input, and the checkbox input is never
    # reached at all, so the probe has no checkbox value to report.
    assert result["slider_value"] == "category"
    assert result.get("checkbox_checked") is not True


def test_the_value_on_the_page_must_match_the_value_that_was_sent() -> None:
    """The page shows the value the client sent -- not merely that it changed."""
    assert widget_value_matches("60", [60]) is True
    assert widget_value_matches("60", [61]) is False
    assert widget_value_matches("0.55", [0.55]) is True
    assert widget_value_matches("0.5", [0.55]) is False
    assert widget_value_matches("false", False) is True
    assert widget_value_matches("true", False) is False
    assert widget_value_matches("region", "region") is True
    assert widget_value_matches("channel", "region") is False
    assert widget_value_matches(None, [60]) is False
    assert widget_value_matches("60", None) is False


def test_a_range_must_match_element_by_element_and_in_length() -> None:
    """Python writes a range "(40, 80)" and Rust writes "40..80"."""
    assert widget_value_matches("(40, 80)", [40, 80]) is True
    assert widget_value_matches("80..80", [80, 80]) is True
    assert widget_value_matches("(40, 80)", [40]) is False
    assert widget_value_matches("(40, 90)", [40, 80]) is False


def test_the_returned_value_is_read_from_the_line_of_the_page() -> None:
    """The page renders one line per widget."""
    lines = ["Group by: region", "Minimum amount: 60", "Changes: 3"]
    assert dom_value_for(lines, "Group by") == "region"
    assert dom_value_for(lines, "Minimum amount") == "60"
    assert dom_value_for(lines, "Ratio") is None
    assert dom_value_for(None, "Group by") is None


def test_the_wire_value_comes_from_the_proto_content() -> None:
    """A slider sends a DoubleArray; the list inside it is the value."""
    assert wire_value_of({"value": {"data": "[20.0]"}, "value_full": {"data": [20]}}) == [20]
    assert wire_value_of({"value": "region"}) == "region"
    assert wire_value_of({"value": True}) is True
    assert wire_value_of(None) is None


def _passed(label, wire, shown):
    return {
        "label": label,
        "wire_value": wire,
        "page_shows": shown,
        "ok": True,
        "value_matches_the_page": True,
    }


def test_a_suite_that_delivers_every_case_passes() -> None:
    """The four numeric representatives, all asserted."""
    required = SUITES["python-numeric"]["required"]
    results = [
        _passed("Minimum amount", [10], "10"),
        _passed("Ratio", [0.3], "0.3"),
        _passed("Amount range", [30, 80], "(30, 80)"),
        _passed("Ratio range", [0.3, 0.8], "(0.3, 0.8)"),
    ]
    assert suite_failures(required, results) == []
    assert suite_counts(required, results) == {"expected": 4, "executed": 4, "asserted": 4}


def test_a_page_without_the_required_widgets_fails_the_suite() -> None:
    """A status or counter page must not pass by doing nothing."""
    required = SUITES["python-numeric"]["required"]
    failures = suite_failures(required, [])
    assert len(failures) == 4
    assert {failure["check"] for failure in failures} == {"case_executed"}
    assert suite_counts(required, []) == {"expected": 4, "executed": 0, "asserted": 0}


def test_a_skipped_required_case_is_a_failure_and_not_a_skip() -> None:
    """A widget the page does not carry is a failure of the suite."""
    required = SUITES["python-numeric"]["required"]
    results = [
        {"label": label, "skipped": True, "ok": False,
         "reason": "no such widget on this page"}
        for label in required
    ]
    failures = suite_failures(required, results)
    assert len(failures) == 4
    assert {failure["check"] for failure in failures} == {"case_executed"}
    assert suite_counts(required, results) == {"expected": 4, "executed": 0, "asserted": 0}


def test_a_wrong_value_on_the_page_fails_the_suite() -> None:
    """The page showing another value than the one that was sent is a failure."""
    required = SUITES["rust-widgets"]["required"]
    results = [
        {"label": label, "wire_value": [1], "page_shows": "1", "ok": True,
         "value_matches_the_page": True}
        for label in required
    ]
    results[0] = {
        "label": "Group by",
        "wire_value": "region",
        "page_shows": "channel",
        "ok": False,
        "problems": ["the page shows 'channel', the client sent 'region'"],
        "value_matches_the_page": False,
    }
    failures = suite_failures(required, results)
    assert [failure["check"] for failure in failures] == ["case_verdict"]
    assert "region" in failures[0]["actual"] and "channel" in failures[0]["actual"]
    assert suite_counts(required, results)["asserted"] == len(required) - 1


def _state_frame(connection, widget_id, value_field, value):
    """A client frame that carries the state of one widget."""
    item = {"id": widget_id, "value_field": value_field, "value": {"data": str(value)}}
    if isinstance(value, list):
        item["value_full"] = {"data": value}
    frame = {
        "direction": "client->server",
        "decoded": {
            "message": "BackMsg",
            "type": "rerun_script",
            "rerun_script": {"widget_states": [item]},
        },
    }
    if connection is not None:
        frame["connection"] = connection
    return frame


SLIDER_CASE = {"kind": "slider", "label": "Minimum amount"}
WIDGET_ID = "$$ID-a-min_amount"


def test_a_case_answered_on_the_same_connection_passes() -> None:
    """The state and the successful completion on one connection: the case passes."""
    frames = [
        _state_frame(0, WIDGET_ID, "double_array_value", [10]),
        completion_frame(0, 0),
    ]
    window = {"start": 0, "end": 2, "widget": WIDGET_ID}
    verdict = case_verdict(SLIDER_CASE, frames, window, {"action": "press"}, None, "10")
    assert verdict["ok"], verdict["problems"]
    assert verdict["connection"] == 0
    assert verdict["completion_frame"] == 1


def test_a_case_without_a_connection_is_rejected() -> None:
    """Two frames without a connection may not be read as one connection."""
    frames = [
        _state_frame(None, WIDGET_ID, "double_array_value", [10]),
        completion_frame(None, 0),
    ]
    window = {"start": 0, "end": 2, "widget": WIDGET_ID}
    verdict = case_verdict(SLIDER_CASE, frames, window, {"action": "press"}, None, "10")
    assert not verdict["ok"]
    assert any("connection" in problem for problem in verdict["problems"])


def test_a_case_answered_on_another_connection_is_rejected() -> None:
    """The state on one socket and the completion on another prove nothing."""
    frames = [
        _state_frame(0, WIDGET_ID, "double_array_value", [10]),
        completion_frame(1, 0),
    ]
    window = {"start": 0, "end": 2, "widget": WIDGET_ID}
    verdict = case_verdict(SLIDER_CASE, frames, window, {"action": "press"}, None, "10")
    assert not verdict["ok"]
    assert any("same connection" in problem for problem in verdict["problems"])


def test_a_failed_action_is_rejected() -> None:
    """An action that did not run cannot assert anything."""
    frames = [
        _state_frame(0, WIDGET_ID, "double_array_value", [10]),
        completion_frame(0, 0),
    ]
    window = {"start": 0, "end": 2, "widget": WIDGET_ID}
    action = {"action": "press", "failed": "no range input"}
    verdict = case_verdict(SLIDER_CASE, frames, window, action, None, "10")
    assert not verdict["ok"]
    assert any("action failed" in problem for problem in verdict["problems"])


def test_an_unchanged_value_with_an_unrelated_rerun_is_rejected() -> None:
    """A state that repeats the old value, with a successful completion and
    the old page, asserts nothing -- even though the script finished."""
    frames = [
        _state_frame(0, WIDGET_ID, "double_array_value", [10]),
        _state_frame(0, WIDGET_ID, "double_array_value", [10]),
        completion_frame(0, 0),
    ]
    window = {"start": 1, "end": 3, "widget": WIDGET_ID}
    verdict = case_verdict(SLIDER_CASE, frames, window, {"action": "press"}, "10", "10")
    assert not verdict["ok"]
    assert any("unchanged" in problem for problem in verdict["problems"])
    assert any("old value" in problem for problem in verdict["problems"])


def test_the_page_showing_another_value_is_rejected() -> None:
    """The value the client sent has to be the value the page shows."""
    frames = [
        _state_frame(0, WIDGET_ID, "double_array_value", [10]),
        completion_frame(0, 0),
    ]
    window = {"start": 0, "end": 2, "widget": WIDGET_ID}
    verdict = case_verdict(SLIDER_CASE, frames, window, {"action": "press"}, "0", "0")
    assert not verdict["ok"]
    assert any("the page shows" in problem for problem in verdict["problems"])


def test_a_case_that_did_not_assert_is_a_suite_failure() -> None:
    """A verdict that is not ok fails the suite."""
    required = SUITES["rust-widgets"]["required"]
    results = [
        {"label": label, "ok": True, "value_matches_the_page": True}
        for label in required
    ]
    results[2] = {"label": required[2], "ok": False, "problems": ["the value was sent unchanged"]}
    failures = suite_failures(required, results)
    assert [failure["check"] for failure in failures] == ["case_verdict"]
    assert suite_counts(required, results) == {
        "expected": len(required),
        "executed": len(required),
        "asserted": len(required) - 1,
    }


def test_the_driver_keeps_the_connection_of_every_frame() -> None:
    """The driver maps the DevTools request id of a socket to its connection."""
    import importlib.util

    path = pathlib.Path(__file__).resolve().parents[2] / "tests" / "browser" / "numeric_capture.py"
    spec = importlib.util.spec_from_file_location("numeric_capture", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    events = [
        {
            "method": "Network.webSocketFrameSent",
            "params": {"requestId": "1001.7", "response": {"opcode": 2, "payloadData": ""}},
        },
        {
            "method": "Network.webSocketFrameReceived",
            "params": {"requestId": "1001.7", "response": {"opcode": 2, "payloadData": ""}},
        },
        {
            "method": "Network.webSocketFrameReceived",
            "params": {"requestId": "1002.9", "response": {"opcode": 2, "payloadData": ""}},
        },
        {
            "method": "Network.webSocketFrameReceived",
            "params": {"response": {"opcode": 2, "payloadData": ""}},
        },
    ]

    class Recorder:
        def take(self):
            return events

    frames = module.frames_of(Recorder())
    assert [frame["connection"] for frame in frames] == [0, 0, 1, None]
    assert [frame["request_id"] for frame in frames] == ["1001.7", "1001.7", "1002.9", None]


def _data_loop_rows():
    """One row, as the server sends it."""
    return [{"group_key": "East", "row_count": 1, "total_amount": 100, "avg_amount": 100}]


def _data_loop_frames(connection=0):
    """The state, the result the server sent, the chart and the completion."""
    rows = _data_loop_rows()
    digest = "1" * 64
    return [
        _state_frame(connection, WIDGET_ID, "double_array_value", [100]),
        {
            "direction": "server->client",
            "connection": connection,
            "decoded": {
                "message": "ForwardMsg",
                "type": "delta",
                "delta": {
                    "type": "new_element",
                    "element": "dataframe",
                    "arrow": {
                        "rows": rows,
                        "columns": ["group_key", "row_count", "total_amount", "avg_amount"],
                        "sha256": digest,
                    },
                },
            },
        },
        {
            "direction": "server->client",
            "connection": connection,
            "decoded": {
                "message": "ForwardMsg",
                "type": "delta",
                "delta": {
                    "type": "new_element",
                    "element": "vega_lite_chart",
                    "vega_lite_spec": {
                        "data": {"name": "ds"},
                        "encoding": {"x": {"field": "group_key", "sort": ["East"]}},
                    },
                    "vega_lite_datasets": [{"name": "ds", "arrow": {"sha256": digest}}],
                },
            },
        },
        completion_frame(connection, 0),
    ]


def _digest(cells, bars, marks="M0,0h10v50Z"):
    return {
        "table_cells": cells,
        "chart_bars": bars,
        "chart_labels": ["a", "b"],
        "chart_marks": marks,
    }


def test_a_data_loop_step_that_changed_the_result_passes() -> None:
    """The value changed, the answer came on the same connection and the
    rendered result changed: the step passes."""
    frames = _data_loop_frames()
    window = {"start": 0, "end": 4, "widget": WIDGET_ID}
    verdict = data_loop_verdict(
        SLIDER_CASE, frames, window, {"action": "press"},
        _digest(["West", "2", "10", "10"], 1, marks="M0,0h10v5Z"),
        _digest(["East", "1", "100", "100"], 1),
    )
    assert verdict["ok"], verdict["problems"]


def test_a_data_loop_step_without_rendered_cells_is_rejected() -> None:
    """A container without cells proves nothing."""
    frames = _data_loop_frames()
    window = {"start": 0, "end": 4, "widget": WIDGET_ID}
    verdict = data_loop_verdict(
        SLIDER_CASE, frames, window, {"action": "press"},
        _digest([], 0), _digest([], 0),
    )
    assert not verdict["ok"]
    assert any("no cells" in problem for problem in verdict["problems"])


def test_a_data_loop_step_without_bars_is_rejected() -> None:
    """The chart has to show bars."""
    frames = _data_loop_frames()
    window = {"start": 0, "end": 4, "widget": WIDGET_ID}
    verdict = data_loop_verdict(
        SLIDER_CASE, frames, window, {"action": "press"},
        _digest(["East", "1", "100", "100"], 1), _digest(["East", "1", "100", "100"], 0),
    )
    assert not verdict["ok"]
    assert any("no bars" in problem for problem in verdict["problems"])


def test_a_data_loop_step_that_changed_nothing_is_rejected() -> None:
    """The same rows before and after: the data did not update."""
    frames = _data_loop_frames()
    window = {"start": 0, "end": 4, "widget": WIDGET_ID}
    digest = _digest(["East", "1", "100", "100"], 1)
    verdict = data_loop_verdict(
        SLIDER_CASE, frames, window, {"action": "press"}, digest, digest,
    )
    assert not verdict["ok"]
    assert any("did not change" in problem for problem in verdict["problems"])


def test_a_data_loop_step_with_a_failed_action_is_rejected() -> None:
    """An action that did not run cannot assert anything."""
    frames = _data_loop_frames()
    window = {"start": 0, "end": 4, "widget": WIDGET_ID}
    verdict = data_loop_verdict(
        SLIDER_CASE, frames, window, {"action": "press", "failed": "no range input"},
        _digest(["East", "1", "100", "100"], 1), _digest(["East", "1", "100", "100"], 1),
    )
    assert not verdict["ok"]
    assert any("action failed" in problem for problem in verdict["problems"])


def test_a_data_loop_step_answered_on_another_connection_is_rejected() -> None:
    """The state on one socket and the completion on another prove nothing."""
    frames = [
        _state_frame(0, WIDGET_ID, "double_array_value", [100]),
        completion_frame(1, 0),
    ]
    window = {"start": 0, "end": 2, "widget": WIDGET_ID}
    verdict = data_loop_verdict(
        SLIDER_CASE, frames, window, {"action": "press"},
        _digest(["East", "1", "100", "100"], 1), _digest(["East", "1", "100", "100"], 1),
    )
    assert not verdict["ok"]
    assert any("same connection" in problem for problem in verdict["problems"])


def test_a_data_loop_step_without_a_completion_is_rejected() -> None:
    """A state without an answer is not a finished step."""
    frames = [_state_frame(0, WIDGET_ID, "double_array_value", [100])]
    window = {"start": 0, "end": 1, "widget": WIDGET_ID}
    verdict = data_loop_verdict(
        SLIDER_CASE, frames, window, {"action": "press"},
        _digest(["East", "1", "100", "100"], 1), _digest(["East", "1", "100", "100"], 1),
    )
    assert not verdict["ok"]
    assert any("same connection" in problem for problem in verdict["problems"])


def test_a_data_loop_step_that_repeated_the_value_is_rejected() -> None:
    """The same value sent again is not a change."""
    frames = [
        _state_frame(0, WIDGET_ID, "double_array_value", [100]),
        _state_frame(0, WIDGET_ID, "double_array_value", [100]),
        completion_frame(0, 0),
    ]
    window = {"start": 1, "end": 3, "widget": WIDGET_ID}
    verdict = data_loop_verdict(
        SLIDER_CASE, frames, window, {"action": "press"},
        _digest(["East", "1", "100", "100"], 1), _digest(["East", "1", "100", "100"], 1),
    )
    assert not verdict["ok"]
    assert any("unchanged" in problem for problem in verdict["problems"])


DATA_LOOP_TRACE = (
    HERE / "reference-browser" / "data-loop" / "updates-strict" / "trace-data-loop.json"
)


def _load_data_loop_trace() -> dict:
    import json

    return json.loads(DATA_LOOP_TRACE.read_text(encoding="utf-8"))


def _first_filter_stage(trace: dict):
    for stage in trace["stages"]:
        if stage.get("verdict") is not None:
            return stage
    raise AssertionError("no filter stage in the trace")


def test_the_data_loop_stage_of_the_trace_passes_the_strict_verdict() -> None:
    """The published capture satisfies the strict verdict."""
    trace = _load_data_loop_trace()
    stage = _first_filter_stage(trace)
    before = trace["stages"][0]["dom"]
    verdict = data_loop_verdict(
        {"kind": "selectbox", "label": "Group by"},
        trace["frames"],
        stage["window"],
        stage["action"],
        before,
        stage["dom"],
    )
    assert verdict["ok"], verdict["problems"]
    assert verdict.get("result_digest")


def test_a_stale_table_with_only_the_bar_count_changed_is_rejected() -> None:
    """The counter-example of the review: the old table, the old chart labels
    and only the number of bars changed."""
    trace = _load_data_loop_trace()
    stage = _first_filter_stage(trace)
    before = trace["stages"][0]["dom"]
    stale = dict(before)
    stale["chart_bars"] = 6
    verdict = data_loop_verdict(
        {"kind": "selectbox", "label": "Group by"},
        trace["frames"],
        stage["window"],
        stage["action"],
        before,
        stale,
    )
    assert not verdict["ok"]
    assert any(
        "table values did not change" in problem or "does not show" in problem
        for problem in verdict["problems"]
    )


def test_a_stage_without_a_result_delta_is_rejected() -> None:
    """The counter-example of the review: every delta frame is emptied."""
    trace = _load_data_loop_trace()
    stage = _first_filter_stage(trace)
    before = trace["stages"][0]["dom"]
    frames = [
        dict(frame, decoded={})
        if (frame.get("decoded") or {}).get("delta")
        else frame
        for frame in trace["frames"]
    ]
    verdict = data_loop_verdict(
        {"kind": "selectbox", "label": "Group by"},
        frames,
        stage["window"],
        stage["action"],
        before,
        stage["dom"],
    )
    assert not verdict["ok"]
    assert any("no result data in the window" in problem for problem in verdict["problems"])


def test_the_entry_fails_when_the_upload_and_every_step_fail() -> None:
    """The entry must not report success when nothing worked."""
    import importlib.util

    path = pathlib.Path(__file__).resolve().parents[2] / "tests" / "browser" / "numeric_capture.py"
    spec = importlib.util.spec_from_file_location("numeric_capture", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    class Page:
        def upload(self, *args):
            return False

        def result_digest(self):
            return {"table_cells": ["stale"], "chart_labels": ["stale"], "chart_bars": 1,
                    "chart_marks": "stale"}

        def files_dom(self):
            return {"chips": [], "chip_count": 0}

        def open_selectbox(self, label):
            return False

        def option_rect(self, text):
            return None

        def focus_slider(self, label, index):
            return False

        def focus_checkbox(self, label):
            return False

        def click(self, x, y):
            return None

        def chart_tooltip(self):
            return None

    class Recorder:
        label = "test"

        def take(self):
            return []

    class Out:
        def __init__(self):
            self.trace = ""

        def __truediv__(self, other):
            return self

        def write_text(self, text, **kwargs):
            self.trace = text

    class Args:
        files = ""
        fixture = "missing.csv"
        file_action = "none"
        binary = ""
        url = ""
        keep_changes = False

    out = Out()
    original_sleep = module.time.sleep
    module.time.sleep = lambda _seconds: None
    try:
        code = module.run_data_loop(Page(), Recorder(), Args(), out)
    finally:
        module.time.sleep = original_sleep
    assert code != 0, "a capture where everything failed must not report success"
    assert '"failures": []' not in out.trace
    assert "expected" in out.trace


def _verdict_for(trace, stage_index=1, frames=None, dom=None):
    """The verdict of one stage of the published capture."""
    stage = trace["stages"][stage_index]
    before = trace["stages"][stage_index - 1]["dom"]
    return data_loop_verdict(
        {"kind": "selectbox", "label": "Group by"},
        frames if frames is not None else trace["frames"],
        stage["window"],
        stage["action"],
        before,
        dom if dom is not None else stage["dom"],
    )


def test_the_table_numbers_must_be_the_numbers_of_the_data() -> None:
    """The counter-example of the review: every number of the table is 999999."""
    trace = _load_data_loop_trace()
    stage = trace["stages"][1]
    dom = dict(stage["dom"])
    dom["table_cells"] = [
        value if index % 4 == 0 else "999999"
        for index, value in enumerate(dom["table_cells"])
    ]
    verdict = _verdict_for(trace, dom=dom)
    assert not verdict["ok"]
    assert any("cell " in problem for problem in verdict["problems"]), verdict["problems"]


def test_an_arbitrary_chart_path_is_rejected() -> None:
    """The counter-example of the review: the chart is redrawn with any path."""
    trace = _load_data_loop_trace()
    stage = trace["stages"][1]
    dom = dict(stage["dom"])
    dom["chart_marks"] = "M0,0h1v1h-1Z|" * (dom.get("chart_bars") or 0)
    verdict = _verdict_for(trace, dom=dom)
    assert not verdict["ok"]
    assert any(
        "bar heights" in problem or "baseline" in problem for problem in verdict["problems"]
    ), verdict["problems"]


def test_a_stage_without_a_chart_delta_is_rejected() -> None:
    """The counter-example of the review: the chart delta is emptied."""
    import copy

    trace = _load_data_loop_trace()
    frames = copy.deepcopy(trace["frames"])
    for frame in frames:
        delta = (frame.get("decoded") or {}).get("delta") or {}
        if delta.get("element") == "vega_lite_chart":
            frame["decoded"] = {}
    verdict = _verdict_for(trace, frames=frames)
    assert not verdict["ok"]
    assert any("no chart in the window" in problem for problem in verdict["problems"])


def test_the_same_groups_with_wrong_numbers_are_rejected() -> None:
    """The same rows and the same count, but the amounts are wrong."""
    trace = _load_data_loop_trace()
    stage = trace["stages"][1]
    dom = dict(stage["dom"])
    cells = list(dom["table_cells"])
    for index in range(2, len(cells), 4):
        cells[index] = "1"
    dom["table_cells"] = cells
    verdict = _verdict_for(trace, dom=dom)
    assert not verdict["ok"]
    assert any("cell " in problem for problem in verdict["problems"]), verdict["problems"]


def test_the_published_capture_passes_the_strict_verdict() -> None:
    """Every stage of the published capture satisfies the strict verdict."""
    trace = _load_data_loop_trace()
    for index in range(1, len(trace["stages"])):
        stage = trace["stages"][index]
        if stage.get("verdict") is None:
            continue
        kinds = {
            "Group by": "selectbox",
            "Include unknown region": "checkbox",
            "Minimum amount": "slider",
        }
        verdict = data_loop_verdict(
            {"kind": kinds.get(stage["stage"], "selectbox"), "label": stage["stage"]},
            trace["frames"],
            stage["window"],
            stage["action"],
            trace["stages"][index - 1]["dom"],
            stage["dom"],
        )
        assert verdict["ok"], (stage["stage"], verdict["problems"])


def test_flat_bars_are_rejected() -> None:
    """The counter-example of the review: every bar has a height of zero.

    The values are positive, so a flat chart stands for nothing even though
    the ratios of zero heights are all the same.
    """
    trace = _load_data_loop_trace()
    stage = trace["stages"][1]
    dom = dict(stage["dom"])
    bars = dom.get("chart_bars") or 0
    dom["chart_marks"] = "|".join("M0,0h10v0Z" for _ in range(bars))
    verdict = _verdict_for(trace, dom=dom)
    assert not verdict["ok"]
    assert any(
        "no height" in problem or "positive scale" in problem
        for problem in verdict["problems"]
    ), verdict["problems"]


def test_a_chart_that_draws_another_column_is_rejected() -> None:
    """The counter-example of the review: the spec names another column while
    the bars keep the old heights."""
    import copy

    trace = _load_data_loop_trace()
    stage = trace["stages"][1]
    frames = copy.deepcopy(trace["frames"])
    for frame in frames:
        delta = (frame.get("decoded") or {}).get("delta") or {}
        if delta.get("element") == "vega_lite_chart":
            spec = delta.get("vega_lite_spec") or {}
            encoding = spec.setdefault("encoding", {})
            encoding.setdefault("y", {})["field"] = "row_count"
    verdict = _verdict_for(trace, frames=frames)
    assert not verdict["ok"]
    assert any(
        "bar heights" in problem or "no height" in problem or "positive scale" in problem
        for problem in verdict["problems"]
    ), verdict["problems"]
