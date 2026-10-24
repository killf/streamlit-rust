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
    empty_checks,
    journey_result,
    recover_checks,
    sessions_checks,
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
        scope = "PYTHON SIDE ONLY"
        label = "test-data-loop"
        kind = "python-reference-widget-trace"
        suite = "python-numeric"
        only = "all"
        case = "data-loop"
        journey = "basic"
        port = 60667
        out = ""
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

# --- bounded journeys; complete offline contract fixtures use real IPC ---

def _journey_contract_fixture(tmp_path, kind):
    """Complete offline driver observations, not a claim of browser recapture."""
    tmp_path.mkdir(parents=True, exist_ok=True)
    import runpy
    import pyarrow as pa
    from capture_browser_trace import arrow_summary
    from refcore import aggregate, parse_csv
    driver = runpy.run_path(str(HERE.parent / "browser/numeric_capture.py"))
    files = driver["_ArrowFiles"](tmp_path)
    fixture_root = HERE.parent / "fixtures/csv"
    columns = ["group_key", "row_count", "total_amount", "avg_amount"]

    def run(frames, timeline, source, filename, group, *, upload=True, bad=False, old=None):
        start = len(frames)
        session, socket = "session-" + source, "socket-" + source
        file_id = "file-" + filename
        path = fixture_root / filename
        upload_url = f"/_stcore/upload_file/{session}/{file_id}"

        def frame(direction, decoded):
            frames.append({"direction": direction, "connection": 0, "request_id": socket,
                           "namespace": source, "timestamp": 100.0 + len(frames) / 10, "decoded": decoded})

        if not frames:
            frame("server->client", {"message":"ForwardMsg", "type":"new_session", "new_session":{"session_id":session,"script_run_id":"initial-run"}})
            start = len(frames)
        if upload:
            frame("client->server", {"message":"BackMsg", "type":"file_urls_request", "file_urls_request":{"request_id":file_id,"file_names":[filename],"session_id":session}})
            frame("server->client", {"message":"ForwardMsg", "type":"file_urls_response", "file_urls_response":{"response_id":file_id,"file_urls":[{"file_id":file_id,"upload_url":upload_url,"delete_url":upload_url}],"error_msg":""}})
            stamp = frames[-1]["timestamp"] + .01
            timeline.append({"request_id":"put-"+file_id,"method":"PUT","request_headers":{"Content-Type":"multipart/form-data; boundary=unit"},"url":"http://127.0.0.1:8501"+upload_url,"timestamp":stamp,"response_timestamp":stamp+.01,"status":204})
        info = {"name":filename,"size":str(path.stat().st_size),"fileId":file_id,"fileUrls":{"fileId":file_id,"uploadUrl":upload_url,"deleteUrl":upload_url}}
        states = [{"id":"uploader","value_field":"file_uploader_state_value","value":{"uploaded_file_info":filename},"value_full":{"uploadedFileInfo":[info]}},
                  {"id":"group","value_field":"string_value","value":group},
                  {"id":"minimum","value_field":"double_array_value","value":{},"value_full":{"data":[0.0]}},
                  {"id":"unknown","value_field":"bool_value","value":True}]
        frame("client->server", {"message":"BackMsg","type":"rerun_script","rerun_script":{"widget_states":states}})
        frame("server->client", {"message":"ForwardMsg","type":"new_session","new_session":{"session_id":session,"script_run_id":"run-"+str(len(frames))}})
        for element, label, widget in [("file_uploader","Upload sales CSV","uploader"),("selectbox","Group by","group"),("slider","Minimum amount","minimum"),("checkbox","Include unknown region","unknown")]:
            frame("server->client", {"message":"ForwardMsg","type":"delta","delta":{"type":"new_element","element":element,"label":label,"id":widget}})
        dom={"table_present":False,"table_cells":[],"chart_present":False,"chart_bars":0,"chart_marks":"","chart_labels":[],"selectbox_value":group,"slider_value":"0","checkbox_checked":True,"alerts":[]}
        if not bad:
            parsed=parse_csv(path.read_bytes())
            rows=[{"group_key":r.group_key,"row_count":r.row_count,"total_amount":float(r.total_amount),"avg_amount":float(r.avg_amount)} for r in aggregate(parsed.rows,group,0,True)]
            table=pa.Table.from_pylist(rows,schema=pa.schema([("group_key",pa.large_string()),("row_count",pa.int64()),("total_amount",pa.float64()),("avg_amount",pa.float64())]))
            sink=pa.BufferOutputStream()
            with pa.ipc.new_stream(sink,table.schema) as writer:
                writer.write_table(table)
            arrow=arrow_summary(sink.getvalue().to_pybytes())
            frame("server->client", {"message":"ForwardMsg","type":"delta","delta":{"type":"new_element","element":"dataframe","arrow":arrow}})
            dom["table_present"]=True
            dom["table_cells"]=[str(row[c]) for row in rows for c in columns] if rows else ["", "", "", ""]
            if rows:
                name="dataset-"+arrow["sha256"][:12]
                spec={"data":{"name":name},"mark":{"type":"bar"},"encoding":{"x":{"field":"group_key","sort":[r["group_key"] for r in rows]},"y":{"field":"total_amount"}}}
                frame("server->client", {"message":"ForwardMsg","type":"delta","delta":{"type":"new_element","element":"vega_lite_chart","vega_lite_spec":spec,"vega_lite_datasets":[{"name":name,"arrow":arrow}]}})
                dom.update(chart_present=True,chart_bars=len(rows),chart_marks="|".join(f"M{i*10},{1000-r['total_amount']}h8v{r['total_amount']}Z" for i,r in enumerate(rows)))
        frame("server->client", {"message":"ForwardMsg","type":"script_finished","script_finished":{"status":0,"status_name":"FINISHED_SUCCESSFULLY"}})
        before=old or {"table_present":False,"table_cells":[],"chart_present":False,"chart_bars":0,"chart_marks":""}
        action={"action":"upload","file":str(path)} if upload else {"action":"select-option","option":group,"changed":True}
        phase=driver["_phase"]("upload" if upload else "change-group",action,frames,start,len(frames),before,dom,files)
        return phase,dom

    return _journey_fixture_parts(tmp_path, kind, run, driver, fixture_root, columns)


def _journey_fixture_parts(tmp_path, kind, run, driver, fixture_root, columns):
    obs={"journey":kind,"url":"http://127.0.0.1:8501/","ipc_dir":str(tmp_path)}
    if kind=="empty":
        frames=[];timeline=[];phase,dom=run(frames,timeline,"empty","sales_empty.csv","category")
        obs.update(uploads={"file":True},phases=[phase],frames=frames,http_timeline=timeline,alerts={"after_upload":{"alerts":["The uploaded CSV contains no data rows."],"exceptions":[]}},dom={"after_upload":dom},table={**phase["ipc"]["table"]["arrow"],"arrow":phase["ipc"]["table"]["arrow"]})
        return {"alerts":obs["alerts"]["after_upload"],"rows":[],"columns":columns,"dom":dom,"upload_ok":True,"observation":obs}
    if kind=="recover":
        frames=[];timeline=[];bad,dom_bad=run(frames,timeline,"recovery","sales_malformed.csv","category",bad=True)
        good,dom_good=run(frames,timeline,"recovery","sales_basic.csv","category",old=dom_bad)
        old_url="http://127.0.0.1:8501/_stcore/upload_file/session-recovery/file-sales_malformed.csv"
        deletion={"request_id":"delete-old","method":"DELETE","url":old_url,"timestamp":good["start_timestamp"]+.02,"response_timestamp":good["start_timestamp"]+.03,"status":204,"matches_issued_file":True,"in_phase":True}
        timeline.append(deletion)
        alerts_bad={"alerts":["Could not parse the uploaded CSV: record 2"],"exceptions":[]};alerts_good={"alerts":[],"exceptions":[]}
        obs.update(uploads={"bad":True,"good":True},phases=[bad,good],frames=frames,http_timeline=timeline,file_urls={"issued":driver["_issued_file_urls"](frames)},delete_requests=[deletion],alerts={"after_bad":alerts_bad,"after_good":alerts_good},dom={"after_bad":dom_bad,"after_good":dom_good},chips={"chips":["sales_basic.csv"]})
        return {"alerts_bad":alerts_bad,"dom_bad":dom_bad,"verdict":{"ok":True},"delete_requests":[deletion],"chips":obs["chips"],"uploads":(True,True),"frames":frames[good["start"]:],"good_name":"sales_basic.csv","observation":obs}
    tabs={}
    for key,filename in [("a","sales_basic.csv"),("b","sales_unicode.csv")]:
        frames=[];timeline=[];source="tab-"+key;phase,dom=run(frames,timeline,source,filename,"category");phases=[phase]
        if key=="a":
            phase,dom=run(frames,timeline,source,filename,"region",upload=False,old=dom);phases.append(phase)
        tabs[key]={"namespace":source,"file":str(fixture_root/filename),"session_ids":["session-"+source],"uploaded":[filename],"group_values_sent":["category","region"] if key=="a" else ["category"],"phases":phases,"dom":{"after_group_change" if key=="a" else "after_upload":dom},"frames":frames,"http_timeline":timeline}
    obs.update(uploads={"a":True,"b":True},tabs=tabs)
    return {"sessions_a":tabs["a"]["session_ids"],"sessions_b":tabs["b"]["session_ids"],"names_a":tabs["a"]["uploaded"],"names_b":tabs["b"]["uploaded"],"groups_a":tabs["a"]["group_values_sent"],"groups_b":tabs["b"]["group_values_sent"],"dom_a":tabs["a"]["phases"][-1]["dom_after"],"dom_b":tabs["b"]["phases"][-1]["dom_after"],"uploads_a":True,"uploads_b":True,"observation":obs}


def _run_journey_contract(kind, args):
    return journey_result({"empty":empty_checks,"recover":recover_checks,"sessions":sessions_checks}[kind](**args))


@pytest.mark.parametrize("kind", ["empty","recover","sessions"])
def test_complete_journey_contract_with_real_ipc_and_fixture_values(tmp_path, kind):
    result=_run_journey_contract(kind,_journey_contract_fixture(tmp_path,kind))
    assert result["ok"],result["failures"]
    assert result["counts"]["expected"]==result["counts"]["executed"]==result["counts"]["asserted"]


# Independent review J1/J2/J3 reproductions: these must fail closed.
def _recovery_with_overlapping_clear_run(tmp_path):
    """Model the observed Python ordering: new state before the old run finishes."""
    import copy
    args=_journey_contract_fixture(tmp_path,"recover");obs=args["observation"]
    phase=obs["phases"][-1];frames=obs["frames"]
    state_index=next(i for i in range(phase["start"],phase["end"]) if frames[i]["decoded"].get("type")=="rerun_script")
    clear=copy.deepcopy(frames[state_index])
    uploader=next(s for s in clear["decoded"]["rerun_script"]["widget_states"] if s["value_field"]=="file_uploader_state_value")
    uploader["value"]={};uploader["value_full"]={}
    start=copy.deepcopy(frames[state_index+1]);start["decoded"]["new_session"]["script_run_id"]="clear-run"
    widget=copy.deepcopy(frames[state_index+2])
    finished=copy.deepcopy(frames[-1])
    obs["frames"]=frames[:state_index]+[clear,start,widget,frames[state_index],finished]+frames[state_index+1:]
    for i,f in enumerate(obs["frames"]):f["timestamp"]=100.+i/10
    phase["end"]=len(obs["frames"])
    args["frames"]=obs["frames"][phase["start"]:]
    _resummarize_unit_phases(args)
    return args


def test_recovery_binds_good_file_to_its_new_run_not_previous_clear_completion(tmp_path):
    args=_recovery_with_overlapping_clear_run(tmp_path)
    result=_run_journey_contract("recover",args)
    assert result["ok"],result["failures"]


@pytest.mark.parametrize("mutation",["no_marker","reused_run_id","failed_target_finish","no_target_finish","result_after_finish","another_run_owns_result"])
def test_previous_success_cannot_complete_or_supply_data_for_the_target_run(tmp_path,mutation):
    import copy
    args=_recovery_with_overlapping_clear_run(tmp_path);obs=args["observation"]
    phase=obs["phases"][-1];frames=obs["frames"]
    run_starts=[i for i in range(phase["start"],phase["end"]) if frames[i]["decoded"].get("type")=="new_session"]
    target_start=run_starts[-1];target_finish=phase["end"]-1
    if mutation=="no_marker":frames[target_start]["decoded"]["new_session"].pop("script_run_id")
    elif mutation=="reused_run_id":frames[target_start]["decoded"]["new_session"]["script_run_id"]="clear-run"
    elif mutation=="failed_target_finish":frames[target_finish]["decoded"]["script_finished"]["status"]=1
    elif mutation=="no_target_finish":frames[target_finish]["decoded"]={"message":"ForwardMsg","type":"session_status_changed"}
    elif mutation=="result_after_finish":
        marker=frames.pop(target_finish);frames.insert(target_start+1,marker)
    else:
        marker=copy.deepcopy(frames[target_finish]);next_run=copy.deepcopy(frames[target_start])
        next_run["decoded"]["new_session"]["script_run_id"]="unrelated-later-run"
        frames[target_start+1:target_start+1]=[marker,next_run]
        phase["end"]=len(frames)
    for i,f in enumerate(frames):f["timestamp"]=100.+i/10
    args["frames"]=frames[phase["start"]:]
    _resummarize_unit_phases(args)
    result=_run_journey_contract("recover",args)
    assert not result["ok"],result


def _resummarize_unit_phases(args):
    """Keep changed unit raw/phase metadata coherent so negatives test content."""
    import runpy
    from copy import deepcopy
    driver=runpy.run_path(str(HERE.parent / "browser/numeric_capture.py"))
    obs=args["observation"]
    stores=driver["_ArrowFiles"](pathlib.Path(obs["ipc_dir"]))
    scopes=list(obs["tabs"].values()) if "tabs" in obs else [obs]
    for scope in scopes:
        for phase in scope["phases"]:
            for payload in phase["ipc"].values():
                arrow=(payload or {}).get("arrow")
                if arrow and arrow.get("file"):
                    stores.by_digest[arrow["sha256"]]=arrow["file"]
    for scope in scopes:
        for index,phase in enumerate(scope["phases"]):
            new=driver["_phase"](phase["name"],phase["action"],scope["frames"][:phase["end"]],phase["start"],phase["end"],phase["dom_before"],phase["dom_after"],stores)
            scope["phases"][index]=new


def _mutate_journey(args, kind, mutation):
    import pyarrow as pa
    from capture_browser_trace import arrow_summary
    obs=args["observation"];scope=obs["tabs"]["a"] if kind=="sessions" else obs
    phase=scope["phases"][-1];frames=scope["frames"]
    current=frames[phase["start"]:phase["end"]]
    if mutation=="missing_observation":args["observation"]=None;return
    if mutation=="wrong_shape":args["observation"]=[];return
    if mutation=="no_frames":scope["frames"]=[];return
    if mutation=="no_phase":scope["phases"]=[];return
    if mutation=="no_clientstate":
        for f in current:
            if f["decoded"]["type"]=="rerun_script":f["decoded"]["type"]="session_status_changed"
    elif mutation=="no_finish":
        for f in current:
            if f["decoded"]["type"]=="script_finished":f["decoded"]["type"]="session_status_changed"
    elif mutation=="wrong_finish_connection":
        next(f for f in current if f["decoded"]["type"]=="script_finished")["connection"]=99
    elif mutation=="wrong_finish_request":
        next(f for f in current if f["decoded"]["type"]=="script_finished")["request_id"]="another-socket"
    elif mutation=="wrong_namespace":current[-1]["namespace"]="opposite-tab"
    elif mutation=="missing_request_id":current[-1].pop("request_id")
    elif mutation=="missing_timestamp":current[-1].pop("timestamp")
    elif mutation=="failed_action":
        if kind=="sessions":phase["action"]["changed"]=False
        else:obs["uploads"]["file" if kind=="empty" else "good"]=False
    elif mutation in ("wrong_dom","opposite_control","stale_bar"):
        dom=phase["dom_after"]
        if mutation=="wrong_dom":dom["table_cells"]=["WRONG_DATA"]
        elif mutation=="opposite_control":dom["selectbox_value"]="category" if kind=="sessions" else "region"
        else:dom["chart_bars"]=1
    elif mutation in ("no_ipc","wrong_schema","wrong_data","old_delta"):
        table=next(f["decoded"]["delta"] for f in current if f["decoded"].get("delta",{}).get("element")=="dataframe")
        arrow=table["arrow"]
        if mutation=="no_ipc":arrow.pop("base64")
        elif mutation=="old_delta":
            frames[0]["decoded"]={"message":"ForwardMsg","type":"delta","delta":table.copy()}
            next(f for f in current if f["decoded"].get("delta") is table)["decoded"]["type"]="session_status_changed"
        else:
            rows=arrow["rows"]
            if mutation=="wrong_data":
                rows=[dict(row,total_amount=999.0) for row in rows] or [{"group_key":"OLD","row_count":1,"total_amount":999.,"avg_amount":999.}]
            schema=pa.schema([("group_key",pa.large_string()),("row_count",pa.int32() if mutation=="wrong_schema" else pa.int64()),("total_amount",pa.float64()),("avg_amount",pa.float64())])
            t=pa.Table.from_pylist(rows,schema=schema);sink=pa.BufferOutputStream()
            with pa.ipc.new_stream(sink,t.schema) as writer:writer.write_table(t)
            arrow.clear();arrow.update(arrow_summary(sink.getvalue().to_pybytes()))
    elif mutation in ("no_put","put_outside_window","put_wrong_url"):
        request=next(r for r in scope["http_timeline"] if r["method"]=="PUT")
        if mutation=="no_put":scope["http_timeline"].remove(request)
        elif mutation=="put_outside_window":request["timestamp"]=1.;request["response_timestamp"]=2.
        else:request["url"]="http://unrelated.invalid/not-the-file"
    elif mutation=="missing_ipc_file":
        arrow=phase["ipc"]["table"]["arrow"];(pathlib.Path(obs["ipc_dir"])/arrow["file"]).unlink()
    elif mutation=="wrong_fixture_path":
        upload=scope["phases"][0];upload["action"]["file"]=str(HERE.parent/"fixtures/csv/sales_unicode.csv")
    else:raise AssertionError(mutation)
    _resummarize_unit_phases(args)


@pytest.mark.parametrize("kind", ["empty","recover","sessions"])
@pytest.mark.parametrize("mutation", ["missing_observation","wrong_shape","no_frames","no_phase","no_clientstate","no_finish","wrong_finish_connection","wrong_finish_request","wrong_namespace","missing_request_id","missing_timestamp","failed_action","wrong_dom","opposite_control","no_ipc","wrong_schema","wrong_data","old_delta","no_put","put_outside_window","put_wrong_url","wrong_fixture_path","missing_ipc_file"])
def test_journey_contract_rejects_missing_crossed_stale_or_wrong_evidence(tmp_path,kind,mutation):
    args=_journey_contract_fixture(tmp_path,kind)
    _mutate_journey(args,kind,mutation)
    result=_run_journey_contract(kind,args)
    assert not result["ok"],(kind,mutation,result)


@pytest.mark.parametrize("mutation", ["unrelated_delete","wrong_file_delete","wrong_session_delete","old_delete","late_response","missing_issued","stale_error","stale_warning","dom_stale_error"])
def test_recovery_contract_binds_delete_window_and_requires_error_to_clear(tmp_path,mutation):
    args=_journey_contract_fixture(tmp_path,"recover");obs=args["observation"]
    deletion=obs["delete_requests"][0]
    if mutation=="unrelated_delete":deletion["url"]="http://unrelated.invalid/not-the-upload"
    elif mutation=="wrong_file_delete":deletion["url"]=deletion["url"].replace("sales_malformed","sales_basic")
    elif mutation=="wrong_session_delete":deletion["url"]=deletion["url"].replace("session-recovery","another-session")
    elif mutation=="old_delete":deletion["timestamp"]=10.;deletion["response_timestamp"]=11.
    elif mutation=="late_response":deletion["response_timestamp"]=999999.
    elif mutation=="missing_issued":obs["file_urls"]["issued"]=[]
    elif mutation=="dom_stale_error":obs["dom"]["after_good"]["alerts"]=["Could not parse the uploaded CSV"]
    else:obs["alerts"]["after_good"]["alerts"]=["Could not parse the uploaded CSV" if mutation=="stale_error" else "rows excluded from aggregation"]
    result=_run_journey_contract("recover",args)
    assert not result["ok"],result


def test_sessions_contract_rejects_swapped_actual_data_and_opposite_controls(tmp_path):
    args=_journey_contract_fixture(tmp_path,"sessions")
    args["dom_a"]["table_cells"],args["dom_b"]["table_cells"]=args["dom_b"]["table_cells"],args["dom_a"]["table_cells"]
    args["dom_a"]["selectbox_value"]="category";args["dom_b"]["selectbox_value"]="region"
    assert not _run_journey_contract("sessions",args)["ok"]


@pytest.mark.parametrize("mutation", ["missing","duplicate","mixed","unknown"])
def test_journey_required_checks_are_not_defined_by_observed_count(tmp_path,mutation):
    checks=empty_checks(**_journey_contract_fixture(tmp_path,"empty"))
    if mutation=="missing":checks.pop()
    elif mutation=="duplicate":checks.append(checks[0])
    elif mutation=="mixed":checks[0]["journey"]="recover"
    else:checks[0]=dict(checks[0],check="unknown-check")
    assert not journey_result(checks)["ok"]


@pytest.mark.parametrize("kind",["empty","recover","sessions"])
@pytest.mark.parametrize("observation",[None,[],{}, {"journey":"recover","dom":[],"alerts":[]}, {"journey":"sessions","tabs":[]}])
def test_malformed_observation_fails_without_crashing_or_default_success(tmp_path,kind,observation):
    args=_journey_contract_fixture(tmp_path,kind);args["observation"]=observation
    assert not _run_journey_contract(kind,args)["ok"]


def test_empty_accepts_actual_python_null_group_type_only_with_zero_rows(tmp_path):
    import pyarrow as pa
    from capture_browser_trace import arrow_summary
    args=_journey_contract_fixture(tmp_path,"empty");obs=args["observation"]
    arrow=next(f["decoded"]["delta"]["arrow"] for f in obs["frames"] if f["decoded"].get("delta",{}).get("element")=="dataframe")
    table=pa.Table.from_pylist([],schema=pa.schema([("group_key",pa.null()),("row_count",pa.int64()),("total_amount",pa.float64()),("avg_amount",pa.float64())]))
    sink=pa.BufferOutputStream()
    with pa.ipc.new_stream(sink,table.schema) as writer:writer.write_table(table)
    arrow.clear();arrow.update(arrow_summary(sink.getvalue().to_pybytes()))
    _resummarize_unit_phases(args)
    obs["table"]={**obs["phases"][0]["ipc"]["table"]["arrow"],"arrow":obs["phases"][0]["ipc"]["table"]["arrow"]}
    result=_run_journey_contract("empty",args)
    assert result["ok"],result["failures"]


def test_missing_real_arrow_decoder_is_a_failure(tmp_path,monkeypatch):
    import builtins
    args=_journey_contract_fixture(tmp_path,"empty")
    original=builtins.__import__
    def missing(name,*a,**kw):
        if name.startswith("pyarrow"):raise ModuleNotFoundError("injected missing PyArrow")
        return original(name,*a,**kw)
    monkeypatch.setattr(builtins,"__import__",missing)
    result=_run_journey_contract("empty",args)
    assert not result["ok"]
    assert any("IPC reader failed" in str(f) for f in result["failures"])


def test_review_empty_driver_entry_rejects_only_an_old_delta(tmp_path,monkeypatch):
    """J1's actual entry, not just a direct call to the helper."""
    import runpy
    driver=runpy.run_path(str(HERE.parent/"browser/numeric_capture.py"))
    stale={"direction":"server->client","connection":0,"request_id":"old","namespace":"review-empty","timestamp":1.,
           "decoded":{"message":"ForwardMsg","type":"delta","delta":{"type":"new_element","element":"dataframe","arrow":{"rows":[],"columns":["wrong_column"],"schema":"wrong_column: int64"}}}}
    class Recorder:
        label="review-empty"
        def take(self):return []
    class Page:
        def upload(self,path):return True
        def state_digest(self):return {"table_present":True,"table_cells":["","","",""],"chart_present":False,"chart_bars":0,"chart_marks":"","selectbox_value":"category","slider_value":"0","checkbox_checked":True}
        def page_alerts(self):return {"alerts":["The uploaded CSV contains no data rows."],"exceptions":[]}
    entry=driver["run_empty_journey"]
    monkeypatch.setitem(entry.__globals__,"frames_of",lambda *a,**kw:[stale])
    monkeypatch.setattr(entry.__globals__["time"],"sleep",lambda _:None)
    args=types.SimpleNamespace(fixture=str(HERE.parent/"fixtures/csv/sales_empty.csv"),files="",scope="REVIEW",binary="not-a-live-capture",url="http://127.0.0.1:8501/")
    assert entry(Page(),Recorder(),args,tmp_path)==1


@pytest.mark.parametrize("mutation",[None,"unrelated_delete","stale_error"])
def test_recovery_driver_entry_requires_bound_delete_and_cleared_error(tmp_path,monkeypatch,mutation):
    import runpy
    args=_journey_contract_fixture(tmp_path,"recover");obs=args["observation"]
    if mutation=="unrelated_delete":obs["delete_requests"][0]["url"]="http://unrelated.invalid/not-the-upload"
    if mutation=="stale_error":obs["alerts"]["after_good"]["alerts"]=["Could not parse the uploaded CSV"]
    driver=runpy.run_path(str(HERE.parent/"browser/numeric_capture.py"));entry=driver["run_recover_journey"]
    bad,good=obs["phases"];all_frames=obs["frames"]
    frames=iter([all_frames[:bad["start"]],all_frames[:good["start"]],all_frames])
    digests=iter([bad["dom_before"],bad["dom_after"],bad["dom_after"],good["dom_after"]])
    alerts=iter([obs["alerts"]["after_bad"],obs["alerts"]["after_good"]])
    class Recorder:
        label="recovery"
        def take(self):return []
    class Page:
        def upload(self,path):return True
        def state_digest(self):return next(digests)
        def page_alerts(self):return next(alerts)
        def files_dom(self):return args["chips"]
    monkeypatch.setitem(entry.__globals__,"frames_of",lambda *a,**kw:next(frames))
    monkeypatch.setitem(entry.__globals__,"_http_timeline",lambda _:obs["http_timeline"])
    monkeypatch.setattr(entry.__globals__["time"],"sleep",lambda _:None)
    command=types.SimpleNamespace(files=bad["action"]["file"]+","+good["action"]["file"],fixture="",scope="REVIEW",binary="offline-unit-not-browser-proof",url=obs["url"])
    assert entry(Page(),Recorder(),command,tmp_path)==(0 if mutation is None else 1)


@pytest.mark.parametrize("kind",["recover","sessions"])
@pytest.mark.parametrize("mutation",[None,"missing_named","missing_dataset_bytes","fake_inline","wrong_referenced_payload"])
def test_named_chart_payload_is_resolved_by_actual_spec_reference(tmp_path,kind,mutation):
    import copy
    args=_journey_contract_fixture(tmp_path,kind);obs=args["observation"]
    scope=obs["tabs"]["a"] if kind=="sessions" else obs
    phase=scope["phases"][-1]
    chart=next(f["decoded"]["delta"] for f in scope["frames"][phase["start"]:phase["end"]] if f["decoded"].get("delta",{}).get("element")=="vega_lite_chart")
    assert not chart.get("arrow"),"The fixture must exercise the real empty-inline shape"
    if mutation=="missing_named":chart["vega_lite_spec"]["data"]["name"]="not-issued"
    elif mutation=="missing_dataset_bytes":chart["vega_lite_datasets"][0]["arrow"].pop("base64")
    elif mutation=="fake_inline":
        phase["ipc"]["chart"]["arrow"]=copy.deepcopy(phase["ipc"]["table"]["arrow"])
    elif mutation=="wrong_referenced_payload":
        wrong=_journey_contract_fixture(tmp_path/"other","empty")
        other=next(f["decoded"]["delta"]["arrow"] for f in wrong["observation"]["frames"] if f["decoded"].get("delta",{}).get("element")=="dataframe")
        chart["vega_lite_datasets"].append(copy.deepcopy(chart["vega_lite_datasets"][0]))
        chart["vega_lite_datasets"][-1]["name"]="unused-correct-data"
        chart["vega_lite_datasets"][0]["arrow"]=other
    if mutation not in (None,"fake_inline"):_resummarize_unit_phases(args)
    result=_run_journey_contract(kind,args)
    assert result["ok"]==(mutation is None),result


@pytest.mark.parametrize("kind",["empty","recover","sessions"])
def test_replay_uses_actual_raw_parent_after_original_capture_directory_is_gone(tmp_path,kind):
    import copy
    old=tmp_path/"original";old.mkdir()
    args=_journey_contract_fixture(old,kind)
    raw=json.dumps(args["observation"],ensure_ascii=False)
    relocated=tmp_path/"archive";relocated.mkdir()
    (relocated/"trace.json").write_text(raw,encoding="utf8")
    for file in old.glob("arrow-*.bin"):
        shutil.copyfile(file,relocated/file.name)
        file.unlink()
    # Loader context only. The archived trace bytes, events and file references stay intact.
    loaded=json.loads((relocated/"trace.json").read_text(encoding="utf8"))
    loaded["ipc_dir"]=str(relocated)
    args["observation"]=loaded
    result=_run_journey_contract(kind,args)
    assert result["ok"],result["failures"]
    assert (relocated/"trace.json").read_text(encoding="utf8")==raw


def test_journey_review_empty_old_delta_wrong_schema_without_state_or_finish():
    checks = empty_checks({"alerts":["The uploaded CSV contains no data rows."]}, [], ["wrong_column"], {"table_cells":[],"chart_bars":0}, True)
    assert not journey_result(checks)["ok"]


def test_journey_review_sessions_opposite_controls_and_wrong_data_without_frames():
    checks = sessions_checks(["a"],["b"],["a.csv"],["b.csv"],["region"],["category"],
        {"table_cells":["WRONG_B_DATA"],"selectbox_value":"category"},
        {"table_cells":["WRONG_A_DATA"],"selectbox_value":"region"},True,True)
    assert not journey_result(checks)["ok"]


def test_journey_review_unrelated_delete_and_no_recovery_frames():
    checks = recover_checks({"alerts":["Could not parse the uploaded CSV"]},
        {"table_cells":[],"chart_bars":0},{"ok":True,"problems":[]},
        [{"method":"DELETE","status":204,"url":"http://unrelated.invalid/not-the-upload"}],
        {"chips":["good.csv"]},(True,True),[],"good.csv")
    assert not journey_result(checks)["ok"]


def test_journey_review_missing_required_checks_is_not_zero_of_zero_success():
    assert not journey_result([])["ok"]


# Actual state/run/finish fields transcribed from Python recover raw SHA
# 8fc2e3d6e039033da7b4df448cad03e6f2948beda6c92cd6e149485f984fee07.
# Only the uploader state and run-boundary fields are retained for this unit
# regression; real IPC/DOM replay is checked separately, not fabricated here.
_PYTHON_RECOVERY_RUN_BOUNDARY = [{'original_frame': 27,
  'frame': {'direction': 'client->server',
            'connection': 0,
            'request_id': '78980.151',
            'namespace': 'python-final-recover',
            'timestamp': 19135.01091,
            'decoded': {'message': 'BackMsg',
                        'type': 'rerun_script',
                        'rerun_script': {'widget_states': [{'id': '$$ID-19480263d3eb5977e56726a4936e1a89-upload',
                                                            'value_field': 'file_uploader_state_value',
                                                            'value': {},
                                                            'value_full': {}}]}}}},
 {'original_frame': 28,
  'frame': {'direction': 'server->client',
            'connection': 0,
            'request_id': '78980.151',
            'namespace': 'python-final-recover',
            'timestamp': 19135.01431,
            'decoded': {'message': 'ForwardMsg',
                        'type': 'new_session',
                        'new_session': {'script_run_id': '6d615358-e64e-4a79-8487-db9ae095e383',
                                        'session_id': 'bdec8992-f74d-4dc6-bd34-82c1d298a72d'}}}},
 {'original_frame': 44,
  'frame': {'direction': 'client->server',
            'connection': 0,
            'request_id': '78980.151',
            'namespace': 'python-final-recover',
            'timestamp': 19135.104398,
            'decoded': {'message': 'BackMsg',
                        'type': 'rerun_script',
                        'rerun_script': {'widget_states': [{'id': '$$ID-19480263d3eb5977e56726a4936e1a89-upload',
                                                            'value_field': 'file_uploader_state_value',
                                                            'value': {'uploaded_file_info': '[name: '
                                                                                            '"sales_basic.csv"\n'
                                                                                            'size: '
                                                                                            '737\n'
                                                                                            'file_id: '
                                                                                            '"2259d81b-24d1-4252-9d8f-d4b246152168"\n'
                                                                                            'file_urls '
                                                                                            '{\n'
                                                                                            '  '
                                                                                            'file_id: '
                                                                                            '"2259d81b-24d1-4252-9d8f-d4b246152168"\n'
                                                                                            '  '
                                                                                            'upload_url: '
                                                                                            '"/_stcore/upload_file/bdec8992-f74d-4dc6-bd34-82c1d298a72d/2259d81b-24d1-4252-9d8f-d4b246152168"\n'
                                                                                            '  '
                                                                                            'delete_url: '
                                                                                            '"/_stcore/upload_file/bdec8992-f74d-4dc6-bd34-82c1d298a72d/2259d81b-24d1-4252-9d8f-d4b246152168"\n'
                                                                                            '}\n'
                                                                                            ']'},
                                                            'value_full': {'uploadedFileInfo': [{'name': 'sales_basic.csv',
                                                                                                 'size': '737',
                                                                                                 'fileId': '2259d81b-24d1-4252-9d8f-d4b246152168',
                                                                                                 'fileUrls': {'fileId': '2259d81b-24d1-4252-9d8f-d4b246152168',
                                                                                                              'uploadUrl': '/_stcore/upload_file/bdec8992-f74d-4dc6-bd34-82c1d298a72d/2259d81b-24d1-4252-9d8f-d4b246152168',
                                                                                                              'deleteUrl': '/_stcore/upload_file/bdec8992-f74d-4dc6-bd34-82c1d298a72d/2259d81b-24d1-4252-9d8f-d4b246152168'}}]}}]}}}},
 {'original_frame': 48,
  'frame': {'direction': 'server->client',
            'connection': 0,
            'request_id': '78980.151',
            'namespace': 'python-final-recover',
            'timestamp': 19135.114871,
            'decoded': {'message': 'ForwardMsg',
                        'type': 'script_finished',
                        'script_finished': {'status': 0, 'status_name': 'FINISHED_SUCCESSFULLY'}}}},
 {'original_frame': 50,
  'frame': {'direction': 'server->client',
            'connection': 0,
            'request_id': '78980.151',
            'namespace': 'python-final-recover',
            'timestamp': 19135.122935,
            'decoded': {'message': 'ForwardMsg',
                        'type': 'new_session',
                        'new_session': {'script_run_id': 'c1f44342-7a2f-4a9f-ad21-8aeb2dc1ab6a',
                                        'session_id': 'bdec8992-f74d-4dc6-bd34-82c1d298a72d'}}}},
 {'original_frame': 60,
  'frame': {'direction': 'server->client',
            'connection': 0,
            'request_id': '78980.151',
            'namespace': 'python-final-recover',
            'timestamp': 19135.130288,
            'decoded': {'message': 'ForwardMsg',
                        'type': 'delta',
                        'delta': {'type': 'new_element',
                                  'element': 'dataframe',
                                  'arrow': {'sha256': '2ef28720376df68c13fe7cd9a63bac0e8c56e74716fc19ed6bd17df21b89a5c2'}}}}},
 {'original_frame': 70,
  'frame': {'direction': 'server->client',
            'connection': 0,
            'request_id': '78980.151',
            'namespace': 'python-final-recover',
            'timestamp': 19135.247648,
            'decoded': {'message': 'ForwardMsg',
                        'type': 'script_finished',
                        'script_finished': {'status': 0, 'status_name': 'FINISHED_SUCCESSFULLY'}}}}]


def test_reviewed_python_boundary_binds_44_to_run50_finish70_not_clear_finish48():
    from capture_browser_trace import _journey_run_verdict
    frames=[dict(item["frame"],target=item["frame"]["namespace"]) for item in _PYTHON_RECOVERY_RUN_BOUNDARY]
    widget=frames[2]["decoded"]["rerun_script"]["widget_states"][0]["id"]
    verdict=_journey_run_verdict(frames,{"start":0,"end":len(frames),"widget":widget,"target":frames[0]["target"]},
                                 {"action":"upload","ok":True},"sales_basic.csv","category")
    assert verdict["ok"],verdict["problems"]
    assert _PYTHON_RECOVERY_RUN_BOUNDARY[verdict["state_frame"]]["original_frame"]==44
    assert _PYTHON_RECOVERY_RUN_BOUNDARY[verdict["run_start_frame"]]["original_frame"]==50
    assert _PYTHON_RECOVERY_RUN_BOUNDARY[verdict["completion_frame"]]["original_frame"]==70
