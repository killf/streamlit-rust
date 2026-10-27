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

    run.arrow_files = files
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
    args=types.SimpleNamespace(journey="empty",fixture=str(HERE.parent/"fixtures/csv/sales_empty.csv"),files="",scope="REVIEW",binary="not-a-live-capture",url="http://127.0.0.1:8501/")
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
    command=types.SimpleNamespace(journey="recover",files=bad["action"]["file"]+","+good["action"]["file"],fixture="",scope="REVIEW",binary="offline-unit-not-browser-proof",url=obs["url"])
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


def _stage2_state_observation(tmp_path):
    """Offline full contract fixture; PNG tests do not claim visual verification."""
    import base64
    import copy
    import runpy
    source=_journey_contract_fixture(tmp_path,"sessions")["observation"]
    tab=source["tabs"]["a"];old=tab["frames"]
    upload,selector=tab["phases"]
    selected=old[selector["start"]:selector["end"]]
    upload_frames=old[upload["start"]:upload["end"]]
    states=copy.deepcopy(next(f["decoded"]["rerun_script"]["widget_states"] for f in selected if f["decoded"]["type"]=="rerun_script"))
    server=copy.deepcopy([f for f in selected if f["direction"]=="server->client"])
    template=copy.deepcopy(selected[0]);frames=[];phases=[]
    driver=runpy.run_path(str(HERE.parent/"browser/numeric_capture.py"));store=driver["_ArrowFiles"](tmp_path)
    for payload in selector["ipc"].values():
        if payload and payload.get("arrow"):store.by_digest[payload["arrow"]["sha256"]]=payload["arrow"]["file"]
    def add(name,number,pulses,group,data,action,with_file=False,trigger=False):
        start=len(frames);client=copy.deepcopy(template)
        values=copy.deepcopy(states)
        for v in values:
            if v["id"]=="group":v["value"]=group
            if v["id"]=="uploader" and not with_file:v["value"]={};v["value_full"]={}
        if trigger:values.append({"id":"pulse","value_field":"trigger_value","value":True})
        client["decoded"]={"message":"BackMsg","type":"rerun_script","rerun_script":{"widget_states":values}}
        if name=="upload-baseline":
            frames.extend(copy.deepcopy([f for f in upload_frames if f["decoded"]["type"] in ("file_urls_request","file_urls_response")]))
        frames.append(client)
        for f in copy.deepcopy(server):
            d=f["decoded"]
            if d.get("type")=="new_session":d["new_session"]["script_run_id"]="state-run-"+str(number)
            if d.get("delta",{}).get("element") in ("dataframe","vega_lite_chart") and not data:continue
            if d.get("type")=="script_finished":continue
            frames.append(f)
        for element,body in [("button",None),("markdown",f"Script runs: {number}"),("text",f"Pulses: {pulses}")]:
            f=copy.deepcopy(template);f["direction"]="server->client"
            delta={"type":"new_element","element":element,"body":body}
            if element=="button":delta.update(id="pulse",label="Pulse")
            f["decoded"]={"message":"ForwardMsg","type":"delta","delta":delta};frames.append(f)
        done=copy.deepcopy(server[-1]);frames.append(done)
        for i,f in enumerate(frames):f["timestamp"]=100.+i/10
        dom=copy.deepcopy(selector["dom_after"])
        dom.update(script_runs=str(number),pulses=str(pulses),selectbox_value=group)
        if not data:dom.update(table_present=False,table_cells=[],chart_present=False,chart_bars=0,chart_marks="")
        before=copy.deepcopy(phases[-1]["dom_after"]) if phases else None
        phase=driver["_phase"](name,action,frames,start,len(frames),before,dom,store)
        phase["observation_end_timestamp"]=frames[-1]["timestamp"]+.04
        phases.append(phase)
    add("initial",1,0,"category",False,{"action":"initial","ok":True})
    add("selector",2,0,"region",False,{"action":"select-option","option":"region","ok":True})
    fixture=HERE.parent/"fixtures/csv/sales_basic.csv"
    import hashlib
    add("upload-baseline",3,0,"region",True,{"action":"upload","ok":True,"file":str(fixture),"file_bytes":fixture.stat().st_size,"file_sha256":hashlib.sha256(fixture.read_bytes()).hexdigest()},True)
    add("pulse",4,1,"region",True,{"action":"button","label":"Pulse","ok":True},True,True)
    obs={"contract":"journey-stage2-v1","journey":"state","namespace":"tab-a","url":source["url"],"ipc_dir":str(tmp_path),"frames":frames,"phases":phases,"uploads":{"file":True},"http_timeline":copy.deepcopy(tab["http_timeline"]),"screenshots":[]}
    # The unit upload uses this actual fixture's issued URL in its own new action window.
    request=obs["http_timeline"][0];phase=phases[2]
    request["timestamp"]=phase["start_timestamp"]+.11;request["response_timestamp"]=phase["start_timestamp"]+.12
    png=base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+a8m0AAAAASUVORK5CYII=")
    for sid,index in [("J04-S1",0),("J04-S2",1),("J04-S3",3)]:
        file=sid+".png";(tmp_path/file).write_bytes(png);phase=phases[index]
        obs["screenshots"].append({"step_ids":[sid],"phase":phase["name"],"namespace":"tab-a","file":file,"sha256":hashlib.sha256(png).hexdigest(),"timestamp":phase["end_timestamp"]+.02})
    return obs


@pytest.mark.parametrize("value",[None,{},[],{"contract":"journey-stage2-v1","journey":"state"}])
def test_stage2_state_and_png_missing_observations_fail_closed(value):
    import capture_browser_trace as checks
    assert not journey_result(checks.state_checks(observation=value))["ok"]
    assert not journey_result(checks.screenshot_checks(observation=value))["ok"]


def test_stage2_state_and_original_png_contract_have_a_complete_positive(tmp_path):
    import capture_browser_trace as checks
    observation=_stage2_state_observation(tmp_path)
    state=journey_result(checks.state_checks(observation=observation))
    pictures=journey_result(checks.screenshot_checks(observation=observation))
    assert state["ok"],state["failures"]
    assert pictures["ok"],pictures["failures"]


@pytest.mark.parametrize("mutation",["no_picture","wrong_sha","wrong_namespace","wrong_phase","absolute_file","path_escape","before_finish","after_window","next_action","missing_clock"])
def test_stage2_png_proof_rejects_missing_crossed_or_changed_artifacts(tmp_path,mutation):
    import capture_browser_trace as checks
    observation=_stage2_state_observation(tmp_path);record=observation["screenshots"][0]
    if mutation=="no_picture":observation["screenshots"].pop(0)
    elif mutation=="wrong_sha":record["sha256"]="0"*64
    elif mutation=="wrong_namespace":record["namespace"]="tab-b"
    elif mutation=="wrong_phase":record["phase"]="pulse"
    elif mutation=="absolute_file":record["file"]=str((tmp_path/record["file"]).resolve())
    elif mutation=="path_escape":record["file"]="../"+record["file"]
    elif mutation=="before_finish":record["timestamp"]=observation["phases"][0]["end_timestamp"]-.1
    elif mutation=="after_window":record["timestamp"]=observation["phases"][0]["observation_end_timestamp"]+.1
    elif mutation=="next_action":
        record["timestamp"]=observation["phases"][1]["start_timestamp"]+.1
        observation["phases"][0]["observation_end_timestamp"]=record["timestamp"]+.1
    else:record.pop("timestamp")
    assert not journey_result(checks.screenshot_checks(observation=observation))["ok"]


def test_stage2_png_wall_clock_cannot_impersonate_cdp_time_even_in_last_phase(tmp_path):
    import capture_browser_trace as checks
    observation=_stage2_state_observation(tmp_path)
    observation["screenshots"][-1]["timestamp"]=1_800_000_000.
    observation["phases"][-1]["observation_end_timestamp"]=1_800_000_001.
    assert not journey_result(checks.screenshot_checks(observation=observation))["ok"]


@pytest.mark.parametrize("mutation",["wrong_counter","wrong_wire_counter","double_trigger","false_trigger","no_pulse_ipc","pulse_data_changed","missing_run_marker","wrong_connection","old_delta","empty_observation"])
def test_stage2_state_proof_rejects_counter_trigger_and_data_counterexamples(tmp_path,mutation):
    import capture_browser_trace as checks
    observation=_stage2_state_observation(tmp_path)
    if mutation=="empty_observation":observation={}
    else:
        phase=observation["phases"][-1];current=observation["frames"][phase["start"]:phase["end"]]
        if mutation=="wrong_counter":phase["dom_after"]["script_runs"]="5"
        elif mutation=="wrong_wire_counter":
            next(f["decoded"]["delta"] for f in current if f["decoded"].get("delta",{}).get("body")=="Script runs: 4")["body"]="Script runs: 5"
        elif mutation in ("double_trigger","false_trigger"):
            values=next(f["decoded"]["rerun_script"]["widget_states"] for f in current if f["decoded"]["type"]=="rerun_script")
            if mutation=="double_trigger":values.append(dict(values[-1]))
            else:values[-1]["value"]=False
        elif mutation in ("no_pulse_ipc","old_delta"):
            for f in current:
                if f["decoded"].get("delta",{}).get("element")=="dataframe":f["decoded"]={"type":"session_status_changed"}
        elif mutation=="pulse_data_changed":phase["dom_after"]["table_cells"][1]="999"
        elif mutation=="missing_run_marker":next(f["decoded"]["new_session"] for f in current if f["decoded"]["type"]=="new_session").pop("script_run_id")
        else:current[-1]["connection"]=99
    assert not journey_result(checks.state_checks(observation=observation))["ok"]


@pytest.mark.parametrize("control,value",[("slider",[100.0]),("checkbox",False)])
def test_stage2_pulse_client_controls_cannot_reuse_unchanged_dom_and_ipc(tmp_path,control,value):
    import capture_browser_trace as checks
    observation=_stage2_state_observation(tmp_path)
    phase=observation["phases"][-1]
    current=observation["frames"][phase["start"]:phase["end"]]
    element=next(f["decoded"]["delta"] for f in current if f["decoded"].get("delta",{}).get("element")==control)
    states=next(f["decoded"]["rerun_script"]["widget_states"] for f in current if f["decoded"]["type"]=="rerun_script")
    state=next(v for v in states if v["id"]==element["id"])
    if control=="slider":state["value_full"]={"data":value}
    else:state["value"]=value
    assert not journey_result(checks.state_checks(observation=observation))["ok"]


@pytest.mark.parametrize("control",["slider","checkbox"])
@pytest.mark.parametrize("mutation",["missing","wrong_type","duplicate","wrong_id_with_decoy","missing_value","wrong_element_type"])
def test_stage2_controls_require_unique_typed_source_widget_state(tmp_path,control,mutation):
    import copy
    import capture_browser_trace as checks
    observation=_stage2_state_observation(tmp_path)
    phase=observation["phases"][-1]
    current=observation["frames"][phase["start"]:phase["end"]]
    element=next(f["decoded"]["delta"] for f in current if f["decoded"].get("delta",{}).get("element")==control)
    states=next(f["decoded"]["rerun_script"]["widget_states"] for f in current if f["decoded"]["type"]=="rerun_script")
    state=next(v for v in states if v["id"]==element["id"])
    if mutation=="missing":states.remove(state)
    elif mutation=="wrong_type":state["value_field"]="string_value"
    elif mutation=="duplicate":states.append(copy.deepcopy(state))
    elif mutation=="wrong_id_with_decoy":
        state["id"]="unrelated-sender";state["label"]=element["label"]
    elif mutation=="missing_value":
        if control=="slider":state.pop("value_full")
        else:state.pop("value")
    else:element["element"]="text_input"
    result=journey_result(checks.state_checks(observation=observation))
    assert not result["ok"]


def test_stage2_pulse_changed_real_ipc_is_rejected_even_when_dom_and_chart_agree(tmp_path):
    import base64
    import hashlib
    import runpy
    import pyarrow as pa
    import capture_browser_trace as checks
    observation=_stage2_state_observation(tmp_path);phase=observation["phases"][-1]
    current=observation["frames"][phase["start"]:phase["end"]]
    arrow=next(f["decoded"]["delta"]["arrow"] for f in current if f["decoded"].get("delta",{}).get("element")=="dataframe")
    table=pa.ipc.open_stream(base64.b64decode(arrow["base64"])).read_all()
    values=table.column("total_amount").to_pylist();values[0]=999.
    table=table.set_column(2,table.schema.field(2),pa.array(values,type=pa.float64()))
    sink=pa.BufferOutputStream()
    with pa.ipc.new_stream(sink,table.schema) as writer:writer.write_table(table)
    arrow.clear();arrow.update(checks.arrow_summary(sink.getvalue().to_pybytes()))
    phase["dom_after"]["table_cells"][2]="999.0"
    marks=phase["dom_after"]["chart_marks"].split("|")
    marks[0]="M0,1h8v999Z";phase["dom_after"]["chart_marks"]="|".join(marks)
    driver=runpy.run_path(str(HERE.parent/"browser/numeric_capture.py"));store=driver["_ArrowFiles"](tmp_path)
    store.by_digest={hashlib.sha256(p.read_bytes()).hexdigest():p.name for p in tmp_path.glob("arrow-*.bin")}
    end=phase["observation_end_timestamp"]
    new=driver["_phase"](phase["name"],phase["action"],observation["frames"],phase["start"],phase["end"],phase["dom_before"],phase["dom_after"],store)
    new["observation_end_timestamp"]=end;observation["phases"][-1]=new
    assert not journey_result(checks.state_checks(observation=observation))["ok"]


@pytest.mark.parametrize("kind",["soft-invalid","non-utf8","filter-empty"])
def test_stage2_specific_cases_without_required_phases_fail_closed(kind):
    import capture_browser_trace as checks
    function={"soft-invalid":checks.soft_invalid_checks,"non-utf8":checks.non_utf8_checks,"filter-empty":checks.filter_empty_checks}[kind]
    result=journey_result(function(observation={"contract":"journey-stage2-v1","journey":kind}))
    assert not result["ok"]
    assert result["counts"]["expected"]==len(checks.STAGE2_REQUIRED[kind])
    assert result["counts"]["asserted"]==0


@pytest.mark.parametrize("alias,canonical",[("soft-amount","soft-invalid"),("not-utf8","non-utf8"),("filtered-empty","filter-empty"),("session-state","state")])
def test_stage2_case_ids_share_one_explicit_mapping(alias,canonical):
    from capture_browser_trace import canonical_stage2_case,STAGE2_REQUIRED
    assert canonical_stage2_case(alias)==canonical_stage2_case(canonical)==canonical
    assert canonical in STAGE2_REQUIRED


@pytest.mark.parametrize("name",[None,"", "basic", "unknown", "STATE"])
def test_unknown_stage2_cli_case_must_not_fall_back_to_basic(name):
    from capture_browser_trace import canonical_stage2_case
    with pytest.raises(ValueError,match="unknown stage2 journey"):
        canonical_stage2_case(name)


def _stage2_soft_replacement_boundary():
    """Selected real frames from raw SHA88995597325a0e8332bec657ad880812688fec4986053d3ab1f5fc07967158c8.

    Original indices 50/51/63/68/71/73/90/93. The target state arrives
    before the clear run finishes; counter3 belongs to that older run.
    No status2 occurred in this recording; its mutation below is negative only.
    """
    widget="$$ID-19480263d3eb5977e56726a4936e1a89-upload"
    session="f2da5511-ae80-4aa3-a9c1-9a4808190922"
    target_file="13d4eac4-9951-44fe-a89b-b751f10d868f"
    definitions=[
        (50,24362.490081,"client->server",{"type":"rerun_script","rerun_script":{"widget_states":[{"id":widget,"value_field":"file_uploader_state_value","value_full":{}}]}}),
        (51,24362.493692,"server->client",{"type":"new_session","new_session":{"session_id":session,"script_run_id":"8445b1b1-7b95-4253-9b61-6e98d54b254e"}}),
        (63,24362.58155,"client->server",{"type":"rerun_script","rerun_script":{"widget_states":[{"id":widget,"value_field":"file_uploader_state_value","value_full":{"uploadedFileInfo":[{"name":"sales_basic.csv","fileId":target_file,"size":"737"}]}}]}}),
        (68,24362.587679,"server->client",{"type":"delta","delta":{"type":"new_element","element":"text","body":"Script runs: 3"}}),
        (71,24362.587833,"server->client",{"type":"script_finished","script_finished":{"status":0,"status_name":"FINISHED_SUCCESSFULLY"}}),
        (73,24362.598714,"server->client",{"type":"new_session","new_session":{"session_id":session,"script_run_id":"3deb7c75-c9c5-4112-956c-e2b8b8a53539"}}),
        (90,24362.662974,"server->client",{"type":"delta","delta":{"type":"new_element","element":"text","body":"Script runs: 4"}}),
        (93,24362.663069,"server->client",{"type":"script_finished","script_finished":{"status":0,"status_name":"FINISHED_SUCCESSFULLY"}}),
    ]
    frames=[{"original_frame":i,"timestamp":stamp,"direction":direction,"decoded":decoded,
             "connection":0,"request_id":"88144.151","namespace":"reference-soft-invalid","target":"reference-soft-invalid"}
            for i,stamp,direction,decoded in definitions]
    return frames,{"start":0,"end":len(frames),"widget":widget,"target":"reference-soft-invalid"}


def test_stage2_soft_replacement_binds_target63_run73_finish93_not_clear71():
    from capture_browser_trace import _journey_run_verdict
    frames,window=_stage2_soft_replacement_boundary()
    proof=_journey_run_verdict(frames,window,{"action":"upload","ok":True},"sales_basic.csv","category")
    assert proof["ok"],proof["problems"]
    assert [frames[proof[key]]["original_frame"] for key in ("state_frame","run_start_frame","completion_frame")]==[63,73,93]
    counters=[f["decoded"].get("delta",{}).get("body") for f in proof["proof_frames"]]
    assert "Script runs: 4" in counters and "Script runs: 3" not in counters


@pytest.mark.parametrize("mutation",["truncated_at_clear_finish","target_status2","wrong_file","crossed_finish"])
def test_stage2_soft_replacement_rejects_wrong_or_nonterminal_completion(mutation):
    from capture_browser_trace import _journey_run_verdict
    frames,window=_stage2_soft_replacement_boundary()
    if mutation=="truncated_at_clear_finish":window["end"]=5
    elif mutation=="target_status2":frames[-1]["decoded"]["script_finished"]={"status":2,"status_name":"FINISHED_EARLY_FOR_RERUN"}
    elif mutation=="wrong_file":frames[2]["decoded"]["rerun_script"]["widget_states"][0]["value_full"]["uploadedFileInfo"][0]["name"]="unrelated.csv"
    else:frames[-1]["connection"]=1
    with pytest.raises(ValueError):
        _journey_run_verdict(frames,window,{"action":"upload","ok":True},"sales_basic.csv","category")


@pytest.mark.parametrize("end,ready",[(5,False),(6,False),(7,False),(8,True)])
def test_stage2_upload_readiness_waits_for_target_run_completion(end,ready):
    from capture_browser_trace import _stage2_target_upload_run
    frames,window=_stage2_soft_replacement_boundary()
    result=_stage2_target_upload_run(frames,namespace=window["target"],start=0,end=end,
        widget_id=window["widget"],file_id="13d4eac4-9951-44fe-a89b-b751f10d868f",file_name="sales_basic.csv")
    assert result["ok"] is ready
    if ready:
        assert [frames[result[k]]["original_frame"] for k in ("state_frame","run_start_frame","completion_frame")]==[63,73,93]


@pytest.mark.parametrize("mutation",["wrong_id","wrong_namespace","wrong_type","status2","crossed_connection"])
def test_stage2_upload_readiness_rejects_unbound_or_unsuccessful_target(mutation):
    from capture_browser_trace import _stage2_target_upload_run
    frames,window=_stage2_soft_replacement_boundary()
    file_id="13d4eac4-9951-44fe-a89b-b751f10d868f"
    if mutation=="wrong_id":file_id="another-file"
    elif mutation=="wrong_namespace":frames[2]["namespace"]="another-tab"
    elif mutation=="wrong_type":frames[2]["decoded"]["rerun_script"]["widget_states"][0]["value_field"]="string_value"
    elif mutation=="status2":frames[-1]["decoded"]["script_finished"]["status"]=2
    else:frames[-1]["connection"]=1
    result=_stage2_target_upload_run(frames,namespace=window["target"],start=0,end=len(frames),
        widget_id=window["widget"],file_id=file_id,file_name="sales_basic.csv")
    assert not result["ok"] and result["problems"]


_SPECIFIC_RAW_CASES = [
    ("python", "soft-invalid", "soft-amount"), ("python", "non-utf8", "not-utf8"),
    ("python", "filter-empty", "filtered-empty"), ("rust", "soft-invalid", "soft-invalid"),
    ("rust", "non-utf8", "non-utf8"), ("rust", "filter-empty", "filter-empty"),
]


def _stage2_specific_observation(tmp_path, side, directory):
    """Relocate adjacent artifacts, preserving captured action paths as provenance."""
    import shutil
    root = HERE / "reference-browser/journeys" if side == "python" else HERE.parent / "browser/rust-journeys"
    path = root / directory / "trace-data-loop.json"
    observation = json.loads(path.read_text(encoding="utf-8"))["observation"]
    tmp_path.mkdir(parents=True, exist_ok=True)
    # Preserve exact bytes; never write into the published capture directories.
    for artifact in path.parent.iterdir():
        if artifact.is_file() and artifact.suffix in (".bin", ".png"):
            shutil.copyfile(artifact, tmp_path / artifact.name)
    observation["ipc_dir"] = str(tmp_path.resolve())
    return observation


@pytest.mark.parametrize("captured,accepted", [
    (r"D:\dlab\streamlit-rust\tests\fixtures\csv\sales_basic.csv", True),
    ("/srv/old-checkout/tests/fixtures/csv/sales_basic.csv", True),
    ("tests/fixtures/csv/sales_basic.csv", True),
    ("/srv/other-directory/sales_basic.csv", False),
    ("/srv/tests/other/csv/sales_basic.csv", False),
    ("/srv/tests/fixtures/csv/sales_with_missing.csv", False),
    ("/srv/../old-checkout/tests/fixtures/csv/sales_basic.csv", False),
    (r"D:\dlab\tests\fixtures\other\..\csv\sales_basic.csv", False),
    ("D:tests/fixtures/csv/sales_basic.csv", False),
])
def test_stage2_fixture_identity_uses_controlled_relative_path_without_rewriting_capture(captured, accepted):
    import capture_browser_trace as checks
    size, sha = checks.J01_FILE_FINGERPRINTS["sales_basic.csv"]
    phase = {"action": {"action": "upload", "ok": True, "file": captured, "file_bytes": size, "file_sha256": sha}}
    original = dict(phase["action"])
    if accepted:
        checks._stage2_specific_input(phase, "sales_basic.csv")
    else:
        with pytest.raises(ValueError, match="fixture path ownership mismatch"):
            checks._stage2_specific_input(phase, "sales_basic.csv")
    assert phase["action"] == original


@pytest.mark.parametrize("changed", ["local_bytes", "file_bytes", "file_sha256"])
def test_stage2_relocated_fixture_still_requires_frozen_local_and_action_fingerprints(tmp_path, monkeypatch, changed):
    import capture_browser_trace as checks
    size, sha = checks.J01_FILE_FINGERPRINTS["sales_basic.csv"]
    phase = {"action": {"action": "upload", "ok": True, "file": "/old/tests/fixtures/csv/sales_basic.csv",
                        "file_bytes": size, "file_sha256": sha}}
    if changed == "local_bytes":
        local = tmp_path / "tests/fixtures/csv/sales_basic.csv"
        local.parent.mkdir(parents=True)
        local.write_bytes((checks.REPO_ROOT / "tests/fixtures/csv/sales_basic.csv").read_bytes() + b"\n")
        monkeypatch.setattr(checks, "REPO_ROOT", tmp_path)
    else:
        phase["action"][changed] = size + 1 if changed == "file_bytes" else "0" * 64
    with pytest.raises(ValueError, match="fixture/action fingerprint"):
        checks._stage2_specific_input(phase, "sales_basic.csv")


def _stage2_specific_result(kind, observation):
    import capture_browser_trace as checks
    function = {"soft-invalid": checks.soft_invalid_checks, "non-utf8": checks.non_utf8_checks,
                "filter-empty": checks.filter_empty_checks}[kind]
    return journey_result(function(observation=observation))


def _stage2_specific_refresh(observation):
    """Recompute producer summaries after a deliberate unit counterexample."""
    import runpy
    driver = runpy.run_path(str(HERE.parent / "browser/numeric_capture.py"))
    store = driver["_ArrowFiles"](pathlib.Path(observation["ipc_dir"]))
    import hashlib
    store.by_digest = {hashlib.sha256(p.read_bytes()).hexdigest(): p.name for p in pathlib.Path(observation["ipc_dir"]).glob("arrow-*.bin")}
    for index, phase in enumerate(observation["phases"]):
        updated = driver["_phase"](phase["name"], phase["action"], observation["frames"], phase["start"], phase["end"],
                                    phase["dom_before"], phase["dom_after"], store)
        if "observation_end_timestamp" in phase:
            updated["observation_end_timestamp"] = phase["observation_end_timestamp"]
        observation["phases"][index] = updated


@pytest.mark.parametrize("side,kind,directory",_SPECIFIC_RAW_CASES)
def test_stage2_specific_published_cases_recompute_all_required_evidence(tmp_path,side,kind,directory):
    observation = _stage2_specific_observation(tmp_path,side,directory)
    result = _stage2_specific_result(kind,observation)
    assert result["ok"],result["failures"]
    assert result["counts"]["asserted"] == result["counts"]["expected"]


@pytest.mark.parametrize("kind,directory",[("soft-invalid","soft-amount"),("non-utf8","not-utf8"),("filter-empty","filtered-empty")])
@pytest.mark.parametrize("mutation",["missing_contract","wrong_source","wrong_file_sha","wrong_slider","wrong_checkbox", "wrong_control_type",
                                      "no_image","wrong_image_sha","missing_artifact","status2_terminal","missing_finish","restored_wrong_values"])
def test_stage2_specific_proof_rejects_incomplete_or_contradictory_observations(tmp_path,kind,directory,mutation):
    observation = _stage2_specific_observation(tmp_path,"python",directory)
    phase = observation["phases"][-1]
    current = observation["frames"][phase["start"]:phase["end"]]
    states = next(f["decoded"]["rerun_script"]["widget_states"] for f in reversed(current) if f["decoded"].get("type")=="rerun_script")
    if mutation == "missing_contract":observation.pop("contract")
    elif mutation == "wrong_source":current[-1]["namespace"]="another-tab"
    elif mutation == "wrong_file_sha":observation["phases"][0]["action"]["file_sha256"]="0"*64
    elif mutation in ("wrong_slider","wrong_checkbox","wrong_control_type"):
        field = "bool_value" if mutation=="wrong_checkbox" else "double_array_value"
        value = next(v for v in states if v.get("value_field")==field)
        if mutation=="wrong_checkbox":value["value"]=False
        elif mutation=="wrong_slider":value["value_full"]={"data":[100.]}
        else:value["value_field"]="string_value"
        _stage2_specific_refresh(observation)
    elif mutation == "no_image":observation["screenshots"]=[]
    elif mutation == "wrong_image_sha":observation["screenshots"][0]["sha256"]="0"*64
    elif mutation == "missing_artifact":
        next(pathlib.Path(observation["ipc_dir"]).glob("arrow-*.bin")).unlink()
    elif mutation == "status2_terminal":
        current[-1]["decoded"]["script_finished"]={"status":2,"status_name":"FINISHED_EARLY_FOR_RERUN"}
        _stage2_specific_refresh(observation)
    elif mutation == "missing_finish":
        current[-1]["decoded"]={"type":"session_status_changed"}
        _stage2_specific_refresh(observation)
    else:phase["dom_after"]["table_cells"][2]="99999"
    result = _stage2_specific_result(kind,observation)
    assert not result["ok"],mutation


@pytest.mark.parametrize("kind,directory",[("soft-invalid","soft-amount"),("non-utf8","not-utf8")])
@pytest.mark.parametrize("mutation",["old_clear_finish","unrelated_delete","delete_outside_window","delete_status_wrong","wrong_warning_or_error","stale_recovery_alert","changed_recovery_counter","wrong_target_file_id"])
def test_stage2_replacement_proof_rejects_clear_run_and_unbound_recovery(tmp_path,kind,directory,mutation):
    observation = _stage2_specific_observation(tmp_path,"python",directory)
    first,good = observation["phases"]
    if mutation == "old_clear_finish":
        finish=next(i for i in range(good["start"],good["end"]) if observation["frames"][i]["decoded"].get("type")=="script_finished")
        good["end"]=finish+1;_stage2_specific_refresh(observation)
    elif mutation in ("unrelated_delete","delete_outside_window","delete_status_wrong"):
        deletion=next(h for h in observation["http_timeline"] if h["method"]=="DELETE")
        if mutation=="unrelated_delete":deletion["url"]="http://unrelated.invalid/delete"
        elif mutation=="delete_outside_window":deletion["timestamp"]=first["start_timestamp"];deletion["response_timestamp"]=first["start_timestamp"]+.01
        else:deletion["status"]=500
        deletion.update(matches_issued_file=True,in_phase=True)
    elif mutation == "wrong_warning_or_error":
        first["dom_after"]["alerts"][0]="Unrelated warning/error"
        for f in observation["frames"][first["start"]:first["end"]]:
            d=f["decoded"].get("delta",{})
            if d.get("element")=="alert" and d.get("alert",{}).get("format") in ("WARNING","ERROR"):
                d["alert"]["body"]="Unrelated warning/error";d["body"]="Unrelated warning/error"
    elif mutation == "stale_recovery_alert":good["dom_after"]["alerts"]=list(first["dom_after"]["alerts"])
    elif mutation == "changed_recovery_counter":good["dom_after"]["script_runs"]="3"
    else:
        current=observation["frames"][good["start"]:good["end"]]
        state=next(f["decoded"]["rerun_script"]["widget_states"] for f in reversed(current) if f["decoded"].get("type")=="rerun_script")
        up=next(v for v in state if v.get("value_field")=="file_uploader_state_value")
        up["value_full"]["uploadedFileInfo"][0]["fileId"]="not-issued"
        _stage2_specific_refresh(observation)
    assert not _stage2_specific_result(kind,observation)["ok"]


@pytest.mark.parametrize("mutation",["empty_null_group","empty_int_group","empty_wrong_count_type","empty_wrong_order",
                                      "populated_double_group","coherent_wrong_restored_values"])
def test_stage2_filtered_ipc_checks_actual_bounded_types_and_restored_values(tmp_path,mutation):
    import base64
    import pyarrow as pa
    from capture_browser_trace import arrow_summary
    observation = _stage2_specific_observation(tmp_path,"python","filtered-empty")
    phase = observation["phases"][1 if mutation.startswith("empty_") else 2]
    current=observation["frames"][phase["start"]:phase["end"]]
    arrow=next(f["decoded"]["delta"]["arrow"] for f in current if f["decoded"].get("delta",{}).get("element")=="dataframe")
    old_sha=arrow["sha256"]
    table=pa.ipc.open_stream(base64.b64decode(arrow["base64"])).read_all()
    if mutation == "empty_null_group":table=table.set_column(0,"group_key",pa.array([],type=pa.null()))
    elif mutation == "empty_int_group":table=table.set_column(0,"group_key",pa.array([],type=pa.int64()))
    elif mutation == "empty_wrong_count_type":table=table.set_column(1,"row_count",pa.array([],type=pa.float64()))
    elif mutation == "empty_wrong_order":table=table.select(["row_count","group_key","total_amount","avg_amount"])
    elif mutation == "populated_double_group":
        keys=[float(i) for i in range(table.num_rows)]
        table=table.set_column(0,"group_key",pa.array(keys,type=pa.float64()))
        for i,key in enumerate(keys):phase["dom_after"]["table_cells"][i*4]=str(key)
    else:
        values=table.column("total_amount").to_pylist();values[0]=999.
        table=table.set_column(2,"total_amount",pa.array(values,type=pa.float64()))
        phase["dom_after"]["table_cells"][2]="999.0"
        phase["dom_after"]["chart_marks"]="|".join(f"M{i*10},{1000-v}h8v{v}Z" for i,v in enumerate(values))
    sink=pa.BufferOutputStream()
    with pa.ipc.new_stream(sink,table.schema) as writer:writer.write_table(table)
    payload=arrow_summary(sink.getvalue().to_pybytes())
    for f in current:
        delta=f["decoded"].get("delta",{})
        candidates=[delta.get("arrow"),*[v.get("arrow") for v in delta.get("vega_lite_datasets",[])]]
        for value in candidates:
            if value and value.get("sha256")==old_sha:value.clear();value.update(payload)
        if mutation=="populated_double_group" and delta.get("element")=="vega_lite_chart":
            delta["vega_lite_spec"]["encoding"]["x"]["sort"]=keys
    _stage2_specific_refresh(observation)
    assert not _stage2_specific_result("filter-empty",observation)["ok"]


@pytest.mark.parametrize("control",["slider","checkbox"])
@pytest.mark.parametrize("mutation",["missing_value","duplicate_id","decoy_sender"])
def test_stage2_new_cases_do_not_default_missing_or_misattributed_controls(tmp_path,control,mutation):
    import copy
    observation=_stage2_specific_observation(tmp_path,"rust","soft-invalid")
    phase=observation["phases"][-1]
    current=observation["frames"][phase["start"]:phase["end"]]
    element=next(f["decoded"]["delta"] for f in reversed(current) if f["decoded"].get("delta",{}).get("element")==control)
    states=next(f["decoded"]["rerun_script"]["widget_states"] for f in reversed(current) if f["decoded"].get("type")=="rerun_script")
    state=next(v for v in states if v.get("id")==element["id"])
    if mutation=="missing_value":state.pop("value_full" if control=="slider" else "value")
    elif mutation=="duplicate_id":states.append(copy.deepcopy(state))
    else:state["id"]="another-sender";state["label"]=element["label"]
    _stage2_specific_refresh(observation)
    assert not _stage2_specific_result("soft-invalid",observation)["ok"]


def _sequence_unit_observation(tmp_path, kind):
    """Generated offline frames with real IPC; never a browser continuity claim."""
    import base64
    import copy
    import hashlib
    import pyarrow as pa
    import capture_browser_trace as checks
    from unittest.mock import patch
    if kind == checks.J00_CASE:
        phase_names, inputs, png_roles, contract = checks.J00_PHASES, checks.J00_INPUTS, checks.J00_PNG_ROLES, checks.J00_CONTRACT
    elif kind == checks.J01_CASE:
        phase_names, inputs, png_roles, contract = checks.J01_PHASES, checks.J01_INPUTS, checks.J01_PNG_ROLES, checks.J01_CONTRACT
    elif kind == checks.J03_CASE:
        phase_names, inputs, png_roles, contract = checks.J03_PHASES, checks.J03_INPUTS, checks.J03_PNG_ROLES, checks.J03_CONTRACT
    elif kind == checks.J02_CASE:
        phase_names, inputs, png_roles, contract = checks.J02_PHASES, checks.J02_INPUTS, checks.J02_PNG_ROLES, checks.J02_CONTRACT
    else:
        phase_names, inputs, png_roles, contract = checks.SEQUENCE_PHASES[kind], checks.SEQUENCE_INPUTS, checks.SEQUENCE_PNG_ROLES, checks.SEQUENCE_CONTRACT
    with patch.dict(_journey_contract_fixture.__globals__, {"_journey_fixture_parts": lambda *args: args}):
        _, _, run, driver, fixture_root, _ = _journey_contract_fixture(tmp_path, "unit-sequence")
    store = run.arrow_files
    source = "sequence-unit"
    frames, timeline, phases, records, uploads = [], [], [], [], {}
    dom = {"script_runs":"1","pulses":"0","table_present":False,"table_cells":[],"chart_present":False,
           "chart_bars":0,"chart_marks":"","chart_labels":[],"selectbox_value":"category","slider_value":"0",
           "checkbox_checked":True,"alerts":["Upload a CSV to see the aggregated result."],"exceptions":[]}
    def frame(direction, decoded):
        return {"direction":direction,"namespace":source,"target":source,"connection":0,"request_id":"socket-"+source,
                "timestamp":100.+len(frames)/10,"decoded":decoded}
    frames.append(frame("client->server",{"type":"rerun_script","rerun_script":{"widget_states":[]}}))
    frames.append(frame("server->client",{"type":"new_session","new_session":{"session_id":"session-"+source,"script_run_id":"initial-run"}}))
    def output(element, **fields):
        return frame("server->client",{"type":"delta","delta":{"type":"new_element","element":element,**fields}})
    for element,label,identity,default in [("selectbox","Group by","group",0),("slider","Minimum amount","minimum",[0.]),("checkbox","Include unknown region","unknown",True)]:
        widget={"id":identity,"label":label,"default":default}
        if element=="selectbox":widget["options"]=["category","region","channel"]
        frames.append(output(element,id=identity,label=label,widget=widget))
    frames.append(output("alert",body=dom["alerts"][0],alert={"format":"INFO","body":dom["alerts"][0]}))
    frames.append(output("text",body="Script runs: 1"));frames.append(output("text",body="Pulses: 0"))
    frames.append(frame("server->client",{"type":"script_finished","script_finished":{"status":0,"status_name":"FINISHED_SUCCESSFULLY"}}))
    phases.append(driver["_phase"]("initial",{"action":"initial","ok":True},frames,0,len(frames),None,copy.deepcopy(dom),store))
    previous_info = None
    filename, group = "sales_basic.csv", "category"
    for number, name in enumerate(phase_names[1:], 2):
        upload = name in inputs
        if upload:filename = inputs[name]
        if kind == checks.J00_CASE and checks.J00_ACTIONS[name]["action"] == "select-option":
            group = checks.J00_ACTIONS[name]["option"]
        elif kind == checks.J01_CASE and name in ("group-region", "group-channel", "prepare-category"):
            group = checks.J01_ACTIONS[name]["option"]
        elif kind == checks.J03_CASE and name == "group-region":
            group = checks.J03_ACTIONS[name]["option"]
        elif kind == checks.J02_CASE and name in ("group-region", "group-category"):
            group = checks.J02_ACTIONS[name]["option"]
        bad = filename in ("sales_malformed.csv","sales_latin1.csv")
        timeline_start = len(timeline)
        phase, after = run(frames,timeline,source,filename,group,upload=upload,bad=bad,old=copy.deepcopy(dom))
        start = phase["start"]
        if upload:
            old_id, new_id = "file-"+filename, "file-"+filename+"-"+str(number)
            frames[start:] = json.loads(json.dumps(frames[start:]).replace(old_id,new_id))
            timeline[timeline_start:] = json.loads(json.dumps(timeline[timeline_start:]).replace(old_id,new_id))
            if previous_info is not None:
                stamp = frames[start]["timestamp"]+.001
                timeline.append({"request_id":"delete-"+str(number),"method":"DELETE","url":"http://127.0.0.1:8501"+previous_info["fileUrls"]["deleteUrl"],
                                 "timestamp":stamp,"response_timestamp":stamp+.001,"status":204})
        states = next(f["decoded"]["rerun_script"]["widget_states"] for f in frames[start:] if f["decoded"].get("type")=="rerun_script")
        info_state = next(v for v in states if v["id"]=="uploader")
        if upload:previous_info = copy.deepcopy(info_state["value_full"]["uploadedFileInfo"][0])
        else:info_state["value_full"]={"uploadedFileInfo":[copy.deepcopy(previous_info)]}
        expected_alerts = []
        if filename == "sales_malformed.csv":expected_alerts=[("ERROR","Could not parse the uploaded CSV: row 3: expected 8 fields, found 7"),("INFO","Upload a valid CSV to continue.")]
        elif filename == "sales_latin1.csv":expected_alerts=[("ERROR","Could not parse the uploaded CSV: the uploaded file is not valid UTF-8"),("INFO","Upload a valid CSV to continue.")]
        elif filename == "sales_with_missing.csv":expected_alerts=[("WARNING","2 row(s) with an unusable 'amount' were excluded from the aggregation.")]
        elif filename == "sales_empty.csv":expected_alerts=[("INFO","The uploaded CSV contains no data rows.")]
        if (kind == checks.J00_CASE and name in ("slider-100", "exclude-unknown")) or (kind == checks.J03_CASE and name == "slider-100") or (kind == checks.J02_CASE and name in ("exclude-unknown", "slider-100", "group-category")):
            from refcore import aggregate,parse_csv
            minimum = 0 if name == "exclude-unknown" else 100
            include_unknown = kind != checks.J02_CASE and name != "exclude-unknown"
            rows=[{"group_key":v.group_key,"row_count":v.row_count,"total_amount":float(v.total_amount),"avg_amount":float(v.avg_amount)}
                  for v in aggregate(parse_csv((fixture_root/filename).read_bytes()).rows,group,minimum,include_unknown)]
            table=pa.Table.from_pylist(rows,schema=pa.schema([("group_key",pa.large_string()),("row_count",pa.int64()),("total_amount",pa.float64()),("avg_amount",pa.float64())]))
            sink=pa.BufferOutputStream()
            with pa.ipc.new_stream(sink,table.schema) as writer:writer.write_table(table)
            arrow=checks.arrow_summary(sink.getvalue().to_pybytes());dataset="dataset-"+arrow["sha256"][:12]
            for f in frames[start:]:
                delta=f["decoded"].get("delta",{})
                if delta.get("element")=="dataframe":delta["arrow"]=arrow
                elif delta.get("element")=="vega_lite_chart":
                    delta["vega_lite_spec"]["data"]["name"]=dataset
                    delta["vega_lite_spec"]["encoding"]["x"]["sort"]=[r["group_key"] for r in rows]
                    delta["vega_lite_datasets"]=[{"name":dataset,"arrow":arrow}]
            next(v for v in states if v["id"]=="minimum")["value_full"]={"data":[float(minimum)]}
            next(v for v in states if v["id"]=="unknown")["value"]=include_unknown
            after.update(table_cells=[str(r[c]) for r in rows for c in ("group_key","row_count","total_amount","avg_amount")],
                         chart_bars=len(rows),chart_marks="|".join(f"M{i*10},{1000-r['total_amount']}h8v{r['total_amount']}Z" for i,r in enumerate(rows)),slider_value=str(minimum),checkbox_checked=include_unknown)
        if name == "slider-200":
            next(v for v in states if v["id"]=="minimum")["value_full"]={"data":[200.]}
            table = pa.Table.from_pylist([],schema=pa.schema([("group_key",pa.float64()),("row_count",pa.int64()),("total_amount",pa.float64()),("avg_amount",pa.float64())]))
            sink=pa.BufferOutputStream()
            with pa.ipc.new_stream(sink,table.schema) as writer:writer.write_table(table)
            arrow=checks.arrow_summary(sink.getvalue().to_pybytes())
            for f in frames[start:]:
                delta=f["decoded"].get("delta",{})
                if delta.get("element")=="dataframe":delta["arrow"]=arrow
            frames[start:] = [f for f in frames[start:] if f["decoded"].get("delta",{}).get("element")!="vega_lite_chart"]
            after.update(table_cells=["","","",""],chart_present=False,chart_bars=0,chart_marks="",chart_labels=[],slider_value="200")
            expected_alerts=[("INFO","No rows match the current filters.")]
        action = {"action":"upload","file":str(fixture_root/filename),"ok":True,
                  "file_sha256":hashlib.sha256((fixture_root/filename).read_bytes()).hexdigest(),"file_bytes":(fixture_root/filename).stat().st_size} if upload else {"action":"slider","label":"Minimum amount","value":200 if name=="slider-200" else 0,"ok":True}
        if kind == checks.J01_CASE and not upload:
            action = dict(checks.J01_ACTIONS[name],ok=True,changed=True)
        elif kind in (checks.J00_CASE, checks.J03_CASE, checks.J02_CASE) and not upload:
            actions = {checks.J00_CASE:checks.J00_ACTIONS, checks.J03_CASE:checks.J03_ACTIONS, checks.J02_CASE:checks.J02_ACTIONS}[kind]
            action = dict(actions[name],ok=True)
            if action["action"] == "checkbox":
                action["checkbox"]={"ok":True,"before":dom["checkbox_checked"],"after":after["checkbox_checked"],
                                    "requested_value":False,"input_method":"Space"}
            if action["action"] == "slider":
                # Generated unit observations matching the measured probe shape,
                # not a claim that a browser pointer was actually dispatched.
                def slider_snapshot(value):
                    return {"value":str(value),"min":"0","max":"200","step":"10","aria_value_now":None,"aria_value_text":str(value),
                            "track":{"x":50.,"y":100.,"width":1000.,"height":40.,"left":50.,"right":1050.,"top":100.,"bottom":140.},"viewport":[1200,900]}
                value=action["value"]
                action["pointer"]={"ok":True,"requested_value":value,"before":slider_snapshot(int(dom["slider_value"])),"after":slider_snapshot(value),
                                   "pointer":{"method":"single-track-click","x":1049. if value==200 else 50.+value*5,"y":120.}}
        after.update(script_runs=str(number),pulses="0",alerts=[body for _,body in expected_alerts],exceptions=[])
        extra = [output("alert",body=body,alert={"format":style,"body":body}) for style,body in expected_alerts]
        extra += [output("text",body=f"Script runs: {number}"),output("text",body="Pulses: 0")]
        frames[-1:-1]=extra
        for index in range(start,len(frames)):frames[index]["timestamp"]=100.+index/10
        phase=driver["_phase"](name,action,frames,start,len(frames),copy.deepcopy(dom),after,store)
        phases.append(phase);dom=copy.deepcopy(after)
        if upload:uploads[name]=True
    png=base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+a8m0AAAAASUVORK5CYII=")
    for phase in phases:
        phase["observation_end_timestamp"]=phase["end_timestamp"]+.04
        file=phase["name"]+".png";(tmp_path/file).write_bytes(png)
        record={"phase":phase["name"],"namespace":source,"file":file,"sha256":hashlib.sha256(png).hexdigest(),
                "timestamp":phase["end_timestamp"]+.02,"step_ids":list(png_roles[phase["name"]])}
        if not record["step_ids"]:record["role"]="preparation"
        records.append(record)
    observation = {"contract":contract,"journey":kind,"namespace":source,"url":"http://127.0.0.1:8501/","ipc_dir":str(tmp_path),
                   "frames":frames,"http_timeline":timeline,"phases":phases,"screenshots":records,"uploads":uploads}
    if kind == checks.J00_CASE:
        _j00_unit_forms(observation)
    return observation


@pytest.mark.parametrize("kind",["j07-sequence","j08-sequence"])
def test_sequence_checks_validate_full_generated_chain_without_resetting_counts(tmp_path,kind):
    from capture_browser_trace import sequence_checks,SEQUENCE_REQUIRED
    observation=_sequence_unit_observation(tmp_path,kind)
    result=journey_result(sequence_checks(observation=observation))
    assert result["ok"],result["failures"]
    assert result["counts"]["asserted"]==len(SEQUENCE_REQUIRED[kind])
    assert observation["phases"][-1]["dom_after"]["script_runs"]==str(len(observation["phases"]))


@pytest.mark.parametrize("kind",["j07-sequence","j08-sequence"])
@pytest.mark.parametrize("mutation",["missing_phase","wrong_order","duplicate_phase","foreign_namespace","foreign_socket","foreign_session",
                                      "reused_run_id","reset_absolute_counter","wrong_before_counter","terminal2","old_finish_window",
                                      "gap_hidden_rerun","missing_image","wrong_image_phase","wrong_sha","image_after_next_action"])
def test_sequence_checks_reject_incomplete_spliced_or_reset_chains(tmp_path,kind,mutation):
    import copy
    from capture_browser_trace import sequence_checks
    observation=_sequence_unit_observation(tmp_path,kind)
    phases=observation["phases"];phase=phases[-1]
    current=observation["frames"][phase["start"]:phase["end"]]
    if mutation=="missing_phase":phases.pop(2)
    elif mutation=="wrong_order":phases[1],phases[2]=phases[2],phases[1]
    elif mutation=="duplicate_phase":phases[2]=copy.deepcopy(phases[1])
    elif mutation=="foreign_namespace":current[-1]["namespace"]="another-browser"
    elif mutation=="foreign_socket":current[-1]["request_id"]="other-real-trace"
    elif mutation=="foreign_session":next(f["decoded"]["new_session"] for f in current if f["decoded"].get("type")=="new_session")["session_id"]="other-session"
    elif mutation=="reused_run_id":next(f["decoded"]["new_session"] for f in current if f["decoded"].get("type")=="new_session")["script_run_id"]="initial-run"
    elif mutation=="reset_absolute_counter":
        phase["dom_after"]["script_runs"]="2"
        next(f["decoded"]["delta"] for f in current if f["decoded"].get("delta",{}).get("body")==f"Script runs: {len(phases)}")["body"]="Script runs: 2"
    elif mutation=="wrong_before_counter":phase["dom_before"]["script_runs"]="1"
    elif mutation=="terminal2":current[-1]["decoded"]["script_finished"]["status"]=2;_stage2_specific_refresh(observation)
    elif mutation=="old_finish_window":phase["end"]=phase["start"]+1
    elif mutation=="gap_hidden_rerun":phases[-2]["end"]-=2
    elif mutation=="missing_image":observation["screenshots"].pop(2)
    elif mutation=="wrong_image_phase":observation["screenshots"][-1]["phase"]=phases[1]["name"]
    elif mutation=="wrong_sha":observation["screenshots"][-1]["sha256"]="0"*64
    else:observation["screenshots"][0]["timestamp"]=phases[1]["start_timestamp"]+.1
    assert not journey_result(sequence_checks(observation=observation))["ok"]


@pytest.mark.parametrize("observation",[None,{},[],{"journey":"j07-sequence"},{"contract":"journey-sequence-v1","journey":"unknown"}, {"journey":[]},{"journey":{}}])
def test_sequence_empty_or_unknown_contract_never_passes(observation):
    from capture_browser_trace import sequence_checks
    assert not journey_result(sequence_checks(observation=observation))["ok"]


def _sequence_unit_clear_run(observation, status, *, phase_index=2):
    """Insert one explicitly empty old-file run into a generated atomic upload."""
    import copy
    phase=observation["phases"][phase_index];frames=observation["frames"]
    client=next(i for i in range(phase["start"],phase["end"]) if frames[i]["decoded"].get("type")=="rerun_script")
    marker=next(f for f in frames[client:] if f["decoded"].get("type")=="new_session")
    old_client=copy.deepcopy(frames[client]);old_marker=copy.deepcopy(marker)
    old_marker["decoded"]["new_session"]["script_run_id"]="explicit-clear-run"
    values=old_client["decoded"]["rerun_script"]["widget_states"]
    uploader=next(v for v in values if v["id"]=="uploader");uploader["value"]={};uploader["value_full"]={}
    templates=[copy.deepcopy(f) for f in frames[client:] if f["decoded"].get("delta",{}).get("element") in ("file_uploader","selectbox","slider","checkbox")][:4]
    def output(element,**fields):
        f=copy.deepcopy(marker);f["decoded"]={"type":"delta","delta":{"type":"new_element","element":element,**fields}};return f
    clear_count=int(phase["dom_before"]["script_runs"])+1
    inserted=[old_client,old_marker,*templates,output("alert",body="Upload a CSV to see the aggregated result.",alert={"format":"INFO","body":"Upload a CSV to see the aggregated result."}),
              output("text",body=f"Script runs: {clear_count}"),output("text",body="Pulses: 0")]
    finish=copy.deepcopy(marker);finish["decoded"]={"type":"script_finished","script_finished":{"status":status,"status_name":"FINISHED_SUCCESSFULLY" if status==0 else "FINISHED_EARLY_FOR_RERUN"}}
    if status==0:inserted.append(finish)
    original_later=frames[client:]
    base=frames[client-1]["timestamp"]
    for index,f in enumerate(inserted):f["timestamp"]=base+.005*(index+1)
    frames[client:client]=inserted
    if status==2:
        finish["timestamp"]=frames[client+len(inserted)]["timestamp"]+.01
        frames.insert(client+len(inserted)+1,finish)
    added=len(inserted)+(status==2)
    for index,p in enumerate(observation["phases"]):
        if index>=phase_index:
            p["end"]+=added;p["dom_after"]["script_runs"]=str(int(p["dom_after"]["script_runs"])+1)
        if index>phase_index:
            p["start"]+=added;p["dom_before"]["script_runs"]=str(int(p["dom_before"]["script_runs"])+1)
    for f in original_later:
        delta=f["decoded"].get("delta",{});body=delta.get("body","")
        if body.startswith("Script runs: "):delta["body"]="Script runs: "+str(int(body.split(": ")[1])+1)
    _stage2_specific_refresh(observation)


@pytest.mark.parametrize("kind",["j07-sequence","j08-sequence"])
@pytest.mark.parametrize("clear_status",[0,2])
def test_sequence_counts_follow_real_clear_and_target_entries_not_fixed_upload_totals(tmp_path,kind,clear_status):
    from capture_browser_trace import sequence_checks
    observation=_sequence_unit_observation(tmp_path,kind)
    _sequence_unit_clear_run(observation,clear_status)
    result=journey_result(sequence_checks(observation=observation))
    assert result["ok"],result["failures"]
    assert observation["phases"][-1]["dom_after"]["script_runs"]==str(len(observation["phases"])+1)


def test_sequence_j08_two_actual_slider_runs_cannot_count_as_one_operation(tmp_path):
    import copy
    from capture_browser_trace import sequence_checks
    observation=_sequence_unit_observation(tmp_path,"j08-sequence")
    phase=observation["phases"][-1];frames=observation["frames"]
    extra=copy.deepcopy(frames[phase["start"]:phase["end"]])
    for index,f in enumerate(extra):
        f["timestamp"]=frames[-1]["timestamp"]+.1*(index+1)
        if f["decoded"].get("type")=="new_session":f["decoded"]["new_session"]["script_run_id"]="extra-slider-run"
        delta=f["decoded"].get("delta",{})
        if delta.get("body")=="Script runs: 5":delta["body"]="Script runs: 6"
    frames.extend(extra);phase["end"]=len(frames);phase["dom_after"]["script_runs"]="6"
    phase["observation_end_timestamp"]=frames[-1]["timestamp"]+.04
    observation["screenshots"][-1]["timestamp"]=frames[-1]["timestamp"]+.02
    _stage2_specific_refresh(observation)
    assert not journey_result(sequence_checks(observation=observation))["ok"]


@pytest.mark.parametrize("mutation",["wrong_initial_controls","missing_preparation_image","preparation_as_manifest_step",
                                      "wrong_input","delete_other_old_file","stale_warning_on_good","late_utf8_error","wrong_terminal_values"])
def test_sequence_j07_requires_each_specific_stage_proof_in_its_original_role(tmp_path,mutation):
    from capture_browser_trace import sequence_checks
    observation=_sequence_unit_observation(tmp_path,"j07-sequence")
    if mutation=="wrong_initial_controls":observation["phases"][0]["dom_after"]["checkbox_checked"]=False
    elif mutation=="missing_preparation_image":observation["screenshots"].pop(0)
    elif mutation=="preparation_as_manifest_step":observation["screenshots"][0]["step_ids"]=["J07-S1"]
    elif mutation=="wrong_input":observation["phases"][2]["action"]["file_sha256"]="0"*64
    elif mutation=="delete_other_old_file":
        deletion=[h for h in observation["http_timeline"] if h.get("method")=="DELETE"][-1]
        deletion["url"]=[h for h in observation["http_timeline"] if h.get("method")=="PUT"][0]["url"]
        deletion.update(matches_issued_file=True,in_phase=True)
    elif mutation=="stale_warning_on_good":observation["phases"][3]["dom_after"]["alerts"]=["2 row(s) with an unusable 'amount' were excluded from the aggregation."]
    elif mutation=="late_utf8_error":observation["phases"][-1]["dom_after"]["alerts"]=["Could not parse the uploaded CSV: the uploaded file is not valid UTF-8"]
    else:observation["phases"][-1]["dom_after"]["table_cells"][2]="9999"
    assert not journey_result(sequence_checks(observation=observation))["ok"]


@pytest.mark.parametrize("control,wrong",[("slider",[100.]),("checkbox",False),("selectbox",1)])
def test_sequence_initial_dom_cannot_hide_contradictory_actual_widget_defaults(tmp_path,control,wrong):
    from capture_browser_trace import sequence_checks
    observation=_sequence_unit_observation(tmp_path,"j07-sequence")
    phase=observation["phases"][0]
    element=next(f["decoded"]["delta"] for f in observation["frames"][phase["start"]:phase["end"]] if f["decoded"].get("delta",{}).get("element")==control)
    element["widget"]["default"]=wrong
    assert not journey_result(sequence_checks(observation=observation))["ok"]


@pytest.mark.parametrize("side",["python","rust"])
def test_j07_published_whole_trace_has_exact_malformed_fixture_error(tmp_path,side):
    from capture_browser_trace import sequence_checks
    observation=_stage2_specific_observation(tmp_path,side,"j07-sequence")
    assert observation["phases"][1]["dom_after"]["alerts"][0]=="Could not parse the uploaded CSV: row 3: expected 8 fields, found 7"
    result=journey_result(sequence_checks(observation=observation))
    assert result["ok"],result["failures"]


@pytest.mark.parametrize("side",["python","rust"])
@pytest.mark.parametrize("message",[
    "Could not parse the uploaded CSV: row 999 unrelated",
    "Could not parse the uploaded CSV: row 999: expected 8 fields, found 7",
    "Could not parse the uploaded CSV: row 3: expected 9 fields, found 7",
    "Could not parse the uploaded CSV: row 3: expected 8 fields, found 6",
    "CSV error: record 999 unrelated",
])
def test_j07_rejects_same_wrong_malformed_error_in_actual_wire_and_dom(tmp_path,side,message):
    from capture_browser_trace import sequence_checks
    observation=_stage2_specific_observation(tmp_path,side,"j07-sequence")
    phase=observation["phases"][1]
    phase["dom_after"]["alerts"][0]=message
    # Preserve continuity so this is rejected for S1's error, not the next DOM snapshot.
    observation["phases"][2]["dom_before"]["alerts"][0]=message
    errors=[]
    for f in observation["frames"][phase["start"]:phase["end"]]:
        delta=f.get("decoded",{}).get("delta",{})
        if delta.get("element")=="alert" and delta.get("alert",{}).get("format")=="ERROR":
            delta["body"]=message;delta["alert"]["body"]=message
            if "alert" in delta.get("element_full",{}):delta["element_full"]["alert"]["body"]=message
            errors.append(delta)
    assert len(errors)==1
    result=journey_result(sequence_checks(observation=observation))
    assert not result["ok"],(side,message)


def test_j01_offline_model_preserves_exact_rows_and_equivalent_new_bom_upload(tmp_path):
    """Test construction only: generated frames/PNG are never reference evidence."""
    import capture_browser_trace as checks
    observation=_sequence_unit_observation(tmp_path,checks.J01_CASE)
    assert tuple(p["name"] for p in observation["phases"])==checks.J01_PHASES
    files={}
    for p in observation["phases"][1:]:
        arrow=p["ipc"]["table"]["arrow"];files[arrow["sha256"]]=arrow["file"]
    for phase in observation["phases"][1:]:
        current=observation["frames"][phase["start"]:phase["end"]]
        wire=next(f["decoded"]["delta"]["arrow"] for f in current if f["decoded"].get("delta",{}).get("element")=="dataframe")
        table=checks._journey_ipc(wire,{"ipc_dir":observation["ipc_dir"],"ipc_files":files})
        expected=[{"group_key":key,"row_count":count,"total_amount":float(total),"avg_amount":float(mean)}
                  for key,count,total,mean in checks.J01_EXPECTED_ROWS[phase["name"]]]
        assert table["rows"]==expected
    unicode,bom=observation["phases"][-2:]
    assert unicode["ipc"]["table"]["arrow"]["sha256"]==bom["ipc"]["table"]["arrow"]["sha256"]
    identities=[]
    for p in (unicode,bom):
        current=observation["frames"][p["start"]:p["end"]]
        states=next(f["decoded"]["rerun_script"]["widget_states"] for f in current if f["decoded"].get("type")=="rerun_script")
        info=next(v for v in states if v["id"]=="uploader")["value_full"]["uploadedFileInfo"][0]
        run=next(f["decoded"]["new_session"]["script_run_id"] for f in current if f["decoded"].get("type")=="new_session")
        identities.append((info["fileId"],run))
        assert any(f["decoded"].get("delta",{}).get("element")=="dataframe" for f in current)
        assert any(f["decoded"].get("delta",{}).get("element")=="vega_lite_chart" for f in current)
    assert identities[0][0]!=identities[1][0] and identities[0][1]!=identities[1][1]
    # This is a unit model only; the real reference is independently replayed.
    result=journey_result(checks.j01_checks(observation=observation))
    assert result["ok"],result["failures"]
    assert result["counts"]["asserted"]==len(checks.J01_REQUIRED)


@pytest.mark.parametrize("mutation",[
    "no_prepare","wrong_order","channel_still_region","wrong_input_sha","reuse_old_upload_id",
    "missing_new_bom_run","terminal2","no_fresh_bom_table","bom_values_changed","unicode_key_changed",
    "bom_leaks_into_key","slider100","checkbox_false","reset_counter","other_session",
    "missing_png","wrong_png_sha","wall_clock_png","unrelated_delete",
])
def test_j01_negative_specifications_never_pass(tmp_path,mutation):
    """Offline mutations; never a replacement for reference/browser evidence."""
    import capture_browser_trace as checks
    observation=_sequence_unit_observation(tmp_path,checks.J01_CASE)
    phases=observation["phases"];phase=phases[-1]
    current=observation["frames"][phase["start"]:phase["end"]]
    states=next(f["decoded"]["rerun_script"]["widget_states"] for f in current if f["decoded"].get("type")=="rerun_script")
    if mutation=="no_prepare":phases.pop(4)
    elif mutation=="wrong_order":phases[2],phases[3]=phases[3],phases[2]
    elif mutation=="channel_still_region":
        channel=phases[3];window=observation["frames"][channel["start"]:channel["end"]]
        values=next(f["decoded"]["rerun_script"]["widget_states"] for f in window if f["decoded"].get("type")=="rerun_script")
        next(v for v in values if v["id"]=="group")["value"]="region"
    elif mutation=="wrong_input_sha":phase["action"]["file_sha256"]="0"*64
    elif mutation=="reuse_old_upload_id":
        next(v for v in states if v["id"]=="uploader")["value_full"]["uploadedFileInfo"][0]["fileId"]="file-sales_unicode.csv-6"
    elif mutation=="missing_new_bom_run":next(f for f in current if f["decoded"].get("type")=="new_session")["decoded"]={"type":"session_status_changed"}
    elif mutation=="terminal2":current[-1]["decoded"]["script_finished"]["status"]=2
    elif mutation=="no_fresh_bom_table":next(f for f in current if f["decoded"].get("delta",{}).get("element")=="dataframe")["decoded"]={"type":"session_status_changed"}
    elif mutation=="bom_values_changed":phase["dom_after"]["table_cells"][2]="999.0"
    elif mutation=="unicode_key_changed":phases[-2]["dom_after"]["table_cells"][0]="Bucher"
    elif mutation=="bom_leaks_into_key":phase["dom_after"]["table_cells"][0]="\ufeffBücher"
    elif mutation=="slider100":next(v for v in states if v["id"]=="minimum")["value_full"]={"data":[100.]}
    elif mutation=="checkbox_false":next(v for v in states if v["id"]=="unknown")["value"]=False
    elif mutation=="reset_counter":phase["dom_after"]["script_runs"]="2"
    elif mutation=="other_session":next(f["decoded"]["new_session"] for f in current if f["decoded"].get("type")=="new_session")["session_id"]="another-session"
    elif mutation=="missing_png":observation["screenshots"].pop()
    elif mutation=="wrong_png_sha":observation["screenshots"][-1]["sha256"]="0"*64
    elif mutation=="wall_clock_png":observation["screenshots"][-1]["timestamp"]=1_800_000_000.
    else:next(h for h in observation["http_timeline"] if h["method"]=="DELETE")["url"]="http://unrelated.invalid/delete"
    _stage2_specific_refresh(observation)
    assert not journey_result(checks.j01_checks(observation=observation))["ok"]


@pytest.mark.parametrize("mutation",["unicode_run_id_on_bom","only_clear_run_has_data","missing_chart","wrong_named_dataset",
                                      "issued_reply_before_request","wrong_put_url","wrong_delete_file","overlapping_window"])
def test_j01_bom_freshness_and_transport_counterexamples(tmp_path,mutation):
    import copy
    import capture_browser_trace as checks
    observation=_sequence_unit_observation(tmp_path,checks.J01_CASE)
    phase=observation["phases"][-1];frames=observation["frames"]
    current=frames[phase["start"]:phase["end"]]
    if mutation=="unicode_run_id_on_bom":
        before=observation["phases"][-2]
        previous=next(f["decoded"]["new_session"]["script_run_id"] for f in frames[before["start"]:before["end"]] if f["decoded"].get("type")=="new_session")
        next(f["decoded"]["new_session"] for f in current if f["decoded"].get("type")=="new_session")["script_run_id"]=previous
    elif mutation=="only_clear_run_has_data":
        _sequence_unit_clear_run(observation,2,phase_index=6)
        phase=observation["phases"][-1];current=frames[phase["start"]:phase["end"]]
        markers=[i for i,f in enumerate(current) if f["decoded"].get("type")=="new_session"]
        old_captions=[f for f in current[markers[0]+1:markers[1]] if f["decoded"].get("delta",{}).get("element")=="text"]
        new_data=[f for f in current[markers[1]+1:] if f["decoded"].get("delta",{}).get("element") in ("dataframe","vega_lite_chart")]
        assert len(old_captions)==len(new_data)==2
        for old,new in zip(old_captions,new_data):
            old["decoded"]=copy.deepcopy(new["decoded"]);new["decoded"]={"type":"session_status_changed"}
    elif mutation=="missing_chart":next(f for f in current if f["decoded"].get("delta",{}).get("element")=="vega_lite_chart")["decoded"]={"type":"session_status_changed"}
    elif mutation=="wrong_named_dataset":next(f["decoded"]["delta"]["vega_lite_spec"] for f in current if f["decoded"].get("delta",{}).get("element")=="vega_lite_chart")["data"]["name"]="not-the-emitted-dataset"
    elif mutation=="issued_reply_before_request":
        request=next(f for f in current if f["decoded"].get("type")=="file_urls_request")
        response=next(f for f in current if f["decoded"].get("type")=="file_urls_response")
        request["decoded"],response["decoded"]=response["decoded"],request["decoded"]
    elif mutation=="wrong_put_url":next(h for h in reversed(observation["http_timeline"]) if h["method"]=="PUT")["url"]="http://unrelated.invalid/upload"
    elif mutation=="wrong_delete_file":next(h for h in reversed(observation["http_timeline"]) if h["method"]=="DELETE")["url"]="http://unrelated.invalid/delete"
    else:phase["start"]=observation["phases"][-2]["start"]
    _stage2_specific_refresh(observation)
    assert not journey_result(checks.j01_checks(observation=observation))["ok"]


@pytest.mark.parametrize("status",[0,2])
def test_j01_same_ipc_with_actual_clear_then_new_bom_target_is_valid(tmp_path,status):
    import capture_browser_trace as checks
    observation=_sequence_unit_observation(tmp_path,checks.J01_CASE)
    _sequence_unit_clear_run(observation,status,phase_index=6)
    result=journey_result(checks.j01_checks(observation=observation))
    assert result["ok"],result["failures"]


@pytest.mark.parametrize("mutation",["wrong_count_type","bom_column_name","bom_key","wrong_mean","wrong_total"])
def test_j01_coherent_bom_ipc_and_dom_corruption_is_rejected(tmp_path,mutation):
    import base64
    import pyarrow as pa
    import capture_browser_trace as checks
    observation=_sequence_unit_observation(tmp_path,checks.J01_CASE)
    phase=observation["phases"][-1];current=observation["frames"][phase["start"]:phase["end"]]
    arrow=next(f["decoded"]["delta"]["arrow"] for f in current if f["decoded"].get("delta",{}).get("element")=="dataframe")
    old_sha=arrow["sha256"];table=pa.ipc.open_stream(base64.b64decode(arrow["base64"])).read_all()
    if mutation=="wrong_count_type":table=table.set_column(1,"row_count",table.column(1).cast(pa.float64()))
    elif mutation=="bom_column_name":table=table.rename_columns(["\ufeffgroup_key","row_count","total_amount","avg_amount"])
    elif mutation=="bom_key":
        keys=table.column(0).to_pylist();keys[0]="\ufeff"+keys[0];table=table.set_column(0,"group_key",pa.array(keys,type=pa.large_string()))
        phase["dom_after"]["table_cells"][0]=keys[0]
    else:
        index=3 if mutation=="wrong_mean" else 2;values=table.column(index).to_pylist();values[0]=999.
        table=table.set_column(index,table.schema.field(index),pa.array(values,type=pa.float64()))
        phase["dom_after"]["table_cells"][index]="999.0"
        if mutation=="wrong_total":
            phase["dom_after"]["chart_marks"]="|".join(f"M{i*10},{1000-v}h8v{v}Z" for i,v in enumerate(values))
    sink=pa.BufferOutputStream()
    with pa.ipc.new_stream(sink,table.schema) as writer:writer.write_table(table)
    payload=checks.arrow_summary(sink.getvalue().to_pybytes())
    for f in current:
        delta=f["decoded"].get("delta",{})
        for item in [delta.get("arrow"),*[v.get("arrow") for v in delta.get("vega_lite_datasets",[])]]:
            if item and item.get("sha256")==old_sha:item.clear();item.update(payload)
        if mutation=="bom_key" and delta.get("element")=="vega_lite_chart":delta["vega_lite_spec"]["encoding"]["x"]["sort"]=keys
    _stage2_specific_refresh(observation)
    assert not journey_result(checks.j01_checks(observation=observation))["ok"]


def test_j03_generated_unit_model_has_full_original_values_but_no_reference_claim(tmp_path):
    """Only a unit model; generated pointer fields are not reference evidence."""
    import capture_browser_trace as checks
    observation=_sequence_unit_observation(tmp_path,checks.J03_CASE)
    assert tuple(p["name"] for p in observation["phases"])==checks.J03_PHASES
    expected={
        "upload-baseline":checks.J01_EXPECTED_ROWS["upload-baseline"],
        "slider-100":(("Books",1,"120.50","120.50"),("Games",2,"349.49","174.75")),
        "prepare-slider-zero":checks.J01_EXPECTED_ROWS["upload-baseline"],
        "group-region":checks.J01_EXPECTED_ROWS["group-region"],
        "slider-200":(),
    }
    files={p["ipc"]["table"]["arrow"]["sha256"]:p["ipc"]["table"]["arrow"]["file"] for p in observation["phases"][1:]}
    for phase in observation["phases"][1:]:
        current=observation["frames"][phase["start"]:phase["end"]]
        wire=next(f["decoded"]["delta"]["arrow"] for f in current if f["decoded"].get("delta",{}).get("element")=="dataframe")
        actual=checks._journey_ipc(wire,{"ipc_dir":observation["ipc_dir"],"ipc_files":files})
        rows=[{"group_key":key,"row_count":count,"total_amount":float(total),"avg_amount":float(mean)} for key,count,total,mean in expected[phase["name"]]]
        assert actual["rows"]==rows
        assert phase["dom_after"]["checkbox_checked"] is True
    empty=observation["phases"][-1]
    assert empty["dom_after"]["chart_present"] is False and empty["ipc"]["chart"] is None
    result=journey_result(checks.j03_checks(observation=observation))
    assert result["ok"],result["failures"]
    assert result["counts"]["asserted"]==len(checks.J03_REQUIRED)


@pytest.mark.parametrize("mutation",[
    "missing_prepare","prepare_did_not_reset","region_still_category","checkbox_false","wrong_slider_type",
    "wrong_full_values","stale_four_bars_at_100","stale_chart_at_empty","empty_table_missing",
    "counter_reset","foreign_namespace","reused_run_id","terminal2","missing_image","wrong_png_clock",
])
def test_j03_negative_specs_reject_incomplete_or_wrong_values(tmp_path,mutation):
    """Generated mutations remain separate from reference/raw evidence."""
    import capture_browser_trace as checks
    observation=_sequence_unit_observation(tmp_path,checks.J03_CASE)
    phases=observation["phases"];phase=phases[2]
    current=observation["frames"][phase["start"]:phase["end"]]
    states=next(f["decoded"]["rerun_script"]["widget_states"] for f in current if f["decoded"].get("type")=="rerun_script")
    if mutation=="missing_prepare":phases.pop(3)
    elif mutation=="prepare_did_not_reset":phases[3]["dom_after"]["slider_value"]="100"
    elif mutation=="region_still_category":phases[4]["dom_after"]["selectbox_value"]="category"
    elif mutation=="checkbox_false":next(v for v in states if v["id"]=="unknown")["value"]=False
    elif mutation=="wrong_slider_type":next(v for v in states if v["id"]=="minimum")["value_field"]="string_value"
    elif mutation=="wrong_full_values":phase["dom_after"]["table_cells"][2]="999.0"
    elif mutation=="stale_four_bars_at_100":phase["dom_after"]["chart_bars"]=4
    elif mutation=="stale_chart_at_empty":phases[-1]["dom_after"]["chart_present"]=True
    elif mutation=="empty_table_missing":phases[-1]["dom_after"]["table_present"]=False
    elif mutation=="counter_reset":phases[-1]["dom_after"]["script_runs"]="1"
    elif mutation=="foreign_namespace":current[-1]["namespace"]="other-context"
    elif mutation=="reused_run_id":next(f["decoded"]["new_session"] for f in current if f["decoded"].get("type")=="new_session")["script_run_id"]="initial-run"
    elif mutation=="terminal2":current[-1]["decoded"]["script_finished"]["status"]=2
    elif mutation=="missing_image":observation["screenshots"].pop(3)
    else:observation["screenshots"][-1]["timestamp"]=1_800_000_000.
    _stage2_specific_refresh(observation)
    assert not journey_result(checks.j03_checks(observation=observation))["ok"]


@pytest.mark.parametrize("mutation",["missing","only_ok","not_ok","wrong_method","wrong_requested","right_edge","outside_viewport",
                                      "wrong_x_for_value","nan_x","wrong_aria","wrong_now","missing_aria","wrong_before","wrong_step"])
def test_j03_pointer_requires_observed_geometry_aria_and_real_value_change(tmp_path,mutation):
    import capture_browser_trace as checks
    observation=_sequence_unit_observation(tmp_path,checks.J03_CASE)
    phase=observation["phases"][2];record=phase["action"]["pointer"]
    if mutation=="missing":phase["action"].pop("pointer")
    elif mutation=="only_ok":phase["action"]["pointer"]={"ok":True}
    elif mutation=="not_ok":record["ok"]=False
    elif mutation=="wrong_method":record["pointer"]["method"]="injected-clientstate"
    elif mutation=="wrong_requested":record["requested_value"]=200
    elif mutation=="right_edge":record["pointer"]["x"]=record["before"]["track"]["right"]
    elif mutation=="outside_viewport":record["pointer"]["y"]=record["before"]["viewport"][1]+1
    elif mutation=="wrong_x_for_value":record["pointer"]["x"]=record["before"]["track"]["left"]
    elif mutation=="nan_x":record["pointer"]["x"]=float("nan")
    elif mutation=="wrong_aria":record["after"]["aria_value_text"]="0"
    elif mutation=="wrong_now":record["after"]["aria_value_now"]="200"
    elif mutation=="missing_aria":record["after"].pop("aria_value_text")
    elif mutation=="wrong_before":record["before"]["value"]="100"
    else:record["before"]["step"]="20"
    assert not journey_result(checks.j03_checks(observation=observation))["ok"]


@pytest.mark.parametrize("mutation",["empty_null_key","empty_wrong_count","empty_wrong_order","empty_large_string_valid","populated_double_key"])
def test_j03_actual_ipc_keeps_bounded_empty_schema_and_strict_populated_schema(tmp_path,mutation):
    import base64
    import pyarrow as pa
    import capture_browser_trace as checks
    observation=_sequence_unit_observation(tmp_path,checks.J03_CASE)
    phase=observation["phases"][2 if mutation=="populated_double_key" else -1]
    current=observation["frames"][phase["start"]:phase["end"]]
    arrow=next(f["decoded"]["delta"]["arrow"] for f in current if f["decoded"].get("delta",{}).get("element")=="dataframe")
    old_sha=arrow["sha256"];table=pa.ipc.open_stream(base64.b64decode(arrow["base64"])).read_all()
    if mutation=="empty_null_key":table=table.set_column(0,"group_key",pa.array([],type=pa.null()))
    elif mutation=="empty_wrong_count":table=table.set_column(1,"row_count",pa.array([],type=pa.float64()))
    elif mutation=="empty_wrong_order":table=table.select(["row_count","group_key","total_amount","avg_amount"])
    elif mutation=="empty_large_string_valid":table=table.set_column(0,"group_key",pa.array([],type=pa.large_string()))
    else:
        keys=[float(i) for i in range(table.num_rows)];table=table.set_column(0,"group_key",pa.array(keys,type=pa.float64()))
        for index,key in enumerate(keys):phase["dom_after"]["table_cells"][index*4]=str(key)
    sink=pa.BufferOutputStream()
    with pa.ipc.new_stream(sink,table.schema) as writer:writer.write_table(table)
    payload=checks.arrow_summary(sink.getvalue().to_pybytes())
    for f in current:
        delta=f["decoded"].get("delta",{})
        for value in [delta.get("arrow"),*[d.get("arrow") for d in delta.get("vega_lite_datasets",[])]]:
            if value and value.get("sha256")==old_sha:value.clear();value.update(payload)
        if mutation=="populated_double_key" and delta.get("element")=="vega_lite_chart":delta["vega_lite_spec"]["encoding"]["x"]["sort"]=keys
    _stage2_specific_refresh(observation)
    result=journey_result(checks.j03_checks(observation=observation))
    assert result["ok"] is (mutation=="empty_large_string_valid"),result["failures"]


def test_j03_empty_dom_cannot_hide_a_stale_wire_chart(tmp_path):
    import copy
    import capture_browser_trace as checks
    observation=_sequence_unit_observation(tmp_path,checks.J03_CASE)
    region,empty=observation["phases"][-2:];frames=observation["frames"]
    chart=next(f["decoded"] for f in frames[region["start"]:region["end"]] if f["decoded"].get("delta",{}).get("element")=="vega_lite_chart")
    target=next(f for f in frames[empty["start"]:empty["end"]] if f["decoded"].get("delta",{}).get("element")=="alert")
    target["decoded"]=copy.deepcopy(chart)
    _stage2_specific_refresh(observation)
    assert not journey_result(checks.j03_checks(observation=observation))["ok"]


def test_j03_single_pointer_cannot_mask_two_actual_slider_runs(tmp_path):
    import copy
    import capture_browser_trace as checks
    observation=_sequence_unit_observation(tmp_path,checks.J03_CASE)
    phase=observation["phases"][-1];frames=observation["frames"]
    extra=copy.deepcopy(frames[phase["start"]:phase["end"]]);end=frames[-1]["timestamp"]
    for index,f in enumerate(extra):
        f["timestamp"]=end+.1*(index+1)
        if f["decoded"].get("type")=="new_session":f["decoded"]["new_session"]["script_run_id"]="extra-pointer-run"
        if f["decoded"].get("delta",{}).get("body")=="Script runs: 6":f["decoded"]["delta"]["body"]="Script runs: 7"
    frames.extend(extra);phase["end"]=len(frames);phase["dom_after"]["script_runs"]="7"
    phase["observation_end_timestamp"]=frames[-1]["timestamp"]+.04
    observation["screenshots"][-1]["timestamp"]=frames[-1]["timestamp"]+.02
    _stage2_specific_refresh(observation)
    assert not journey_result(checks.j03_checks(observation=observation))["ok"]


def test_j02_generated_model_keeps_false_oneof_and_shared_final_png_without_extra_run(tmp_path):
    """Generated unit model, not evidence of reference execution."""
    import capture_browser_trace as checks
    observation=_sequence_unit_observation(tmp_path,checks.J02_CASE)
    assert tuple(p["name"] for p in observation["phases"])==checks.J02_PHASES
    assert len(observation["phases"])==6 and len(observation["screenshots"])==6
    assert observation["screenshots"][-1]["step_ids"]==["J02-S4","J02-S5"]
    files={p["ipc"]["table"]["arrow"]["sha256"]:p["ipc"]["table"]["arrow"]["file"] for p in observation["phases"][1:]}
    for index,phase in enumerate(observation["phases"][1:],1):
        current=observation["frames"][phase["start"]:phase["end"]]
        arrow=next(f["decoded"]["delta"]["arrow"] for f in current if f["decoded"].get("delta",{}).get("element")=="dataframe")
        table=checks._journey_ipc(arrow,{"ipc_dir":observation["ipc_dir"],"ipc_files":files})
        expected=[{"group_key":key,"row_count":count,"total_amount":float(total),"avg_amount":float(mean)}
                  for key,count,total,mean in checks.J02_EXPECTED_ROWS[phase["name"]]]
        assert table["rows"]==expected
        states=next(f["decoded"]["rerun_script"]["widget_states"] for f in current if f["decoded"].get("type")=="rerun_script")
        checkbox=next(v for v in states if v["id"]=="unknown")
        assert checkbox["value_field"]=="bool_value" and checkbox["value"] is (index<3)
        assert phase["dom_after"]["script_runs"]==str(index+1)
    result=journey_result(checks.j02_checks(observation=observation))
    assert result["ok"],result["failures"]
    assert result["counts"]["asserted"]==len(checks.J02_REQUIRED)


@pytest.mark.parametrize("mutation",["false_oneof_absent","false_value_absent","wrong_false_type","checkbox_back_on","slider_reset_at_category",
                                      "wrong_three_region_values","zero_music_group","missing_region_phase","wrong_namespace","reused_run",
                                      "counter_reset","terminal2","s5_as_extra_phase","missing_s5_png_role","wrong_final_sha"])
def test_j02_negative_specs_reject_missing_false_or_inconsistent_filtering(tmp_path,mutation):
    """Negative unit specifications, separate from real protocol evidence."""
    import copy
    import capture_browser_trace as checks
    observation=_sequence_unit_observation(tmp_path,checks.J02_CASE)
    phases=observation["phases"];phase=phases[-1]
    current=observation["frames"][phase["start"]:phase["end"]]
    states=next(f["decoded"]["rerun_script"]["widget_states"] for f in current if f["decoded"].get("type")=="rerun_script")
    checkbox=next(v for v in states if v["id"]=="unknown")
    if mutation=="false_oneof_absent":states.remove(checkbox)
    elif mutation=="false_value_absent":checkbox.pop("value")
    elif mutation=="wrong_false_type":checkbox["value_field"]="string_value"
    elif mutation=="checkbox_back_on":checkbox["value"]=True
    elif mutation=="slider_reset_at_category":next(v for v in states if v["id"]=="minimum")["value_full"]={"data":[0.]}
    elif mutation=="wrong_three_region_values":phases[4]["dom_after"]["table_cells"][2]="999.0"
    elif mutation=="zero_music_group":phase["dom_after"]["table_cells"] += ["Music","0","0","0"]
    elif mutation=="missing_region_phase":phases.pop(2)
    elif mutation=="wrong_namespace":current[-1]["namespace"]="another-tab"
    elif mutation=="reused_run":next(f["decoded"]["new_session"] for f in current if f["decoded"].get("type")=="new_session")["script_run_id"]="initial-run"
    elif mutation=="counter_reset":phase["dom_after"]["script_runs"]="1"
    elif mutation=="terminal2":current[-1]["decoded"]["script_finished"]["status"]=2
    elif mutation=="s5_as_extra_phase":
        duplicate=copy.deepcopy(phase);duplicate["name"]="observe-ledger";phases.append(duplicate)
    elif mutation=="missing_s5_png_role":observation["screenshots"][-1]["step_ids"]=["J02-S4"]
    else:observation["screenshots"][-1]["sha256"]="0"*64
    _stage2_specific_refresh(observation)
    assert not journey_result(checks.j02_checks(observation=observation))["ok"]


@pytest.mark.parametrize("mutation",["missing_observation","only_ok","wrong_before","wrong_after","wrong_requested","injected_method","action_numeric_zero","wire_numeric_zero","wrong_id"])
def test_j02_false_requires_real_typed_widget_and_consistent_ui_observation(tmp_path,mutation):
    import capture_browser_trace as checks
    observation=_sequence_unit_observation(tmp_path,checks.J02_CASE)
    phase=observation["phases"][3];action=phase["action"];record=action["checkbox"]
    current=observation["frames"][phase["start"]:phase["end"]]
    states=next(f["decoded"]["rerun_script"]["widget_states"] for f in current if f["decoded"].get("type")=="rerun_script")
    value=next(v for v in states if v["id"]=="unknown")
    if mutation=="missing_observation":action.pop("checkbox")
    elif mutation=="only_ok":action["checkbox"]={"ok":True}
    elif mutation=="wrong_before":record["before"]=False
    elif mutation=="wrong_after":record["after"]=True
    elif mutation=="wrong_requested":record["requested_value"]=True
    elif mutation=="injected_method":record["input_method"]="injected-clientstate"
    elif mutation=="action_numeric_zero":action["value"]=0
    elif mutation=="wire_numeric_zero":value["value"]=0
    else:value["id"]="unrelated-checkbox-with-false"
    _stage2_specific_refresh(observation)
    assert not journey_result(checks.j02_checks(observation=observation))["ok"]


@pytest.mark.parametrize("mutation",["count_double","group_double","wrong_order","coherent_wrong_total","coherent_zero_music"])
def test_j02_full_ipc_schema_and_values_cannot_borrow_empty_tolerance(tmp_path,mutation):
    import base64
    import pyarrow as pa
    import capture_browser_trace as checks
    observation=_sequence_unit_observation(tmp_path,checks.J02_CASE)
    phase=observation["phases"][-1];current=observation["frames"][phase["start"]:phase["end"]]
    arrow=next(f["decoded"]["delta"]["arrow"] for f in current if f["decoded"].get("delta",{}).get("element")=="dataframe")
    old_sha=arrow["sha256"];table=pa.ipc.open_stream(base64.b64decode(arrow["base64"])).read_all()
    if mutation=="count_double":table=table.set_column(1,"row_count",table.column(1).cast(pa.float64()))
    elif mutation=="group_double":
        keys=[float(i) for i in range(table.num_rows)];table=table.set_column(0,"group_key",pa.array(keys,type=pa.float64()))
    elif mutation=="wrong_order":table=table.select(["row_count","group_key","total_amount","avg_amount"])
    elif mutation=="coherent_wrong_total":
        values=table.column(2).to_pylist();values[0]=999.;table=table.set_column(2,table.schema.field(2),pa.array(values,type=pa.float64()))
    else:
        rows=table.to_pylist()+[{"group_key":"Music","row_count":0,"total_amount":0.,"avg_amount":0.}]
        table=pa.Table.from_pylist(rows,schema=table.schema)
    columns=table.column_names;rows=table.to_pylist()
    phase["dom_after"]["table_cells"]=[str(row[c]) for row in rows for c in columns]
    totals=table.column("total_amount").to_pylist();keys=table.column("group_key").to_pylist()
    phase["dom_after"]["chart_bars"]=len(rows)
    phase["dom_after"]["chart_marks"]="|".join(f"M{i*10},{1000-v}h8v{v}Z" for i,v in enumerate(totals))
    sink=pa.BufferOutputStream()
    with pa.ipc.new_stream(sink,table.schema) as writer:writer.write_table(table)
    payload=checks.arrow_summary(sink.getvalue().to_pybytes())
    for f in current:
        d=f["decoded"].get("delta",{})
        for item in [d.get("arrow"),*[v.get("arrow") for v in d.get("vega_lite_datasets",[])]]:
            if item and item.get("sha256")==old_sha:item.clear();item.update(payload)
        if d.get("element")=="vega_lite_chart":d["vega_lite_spec"]["encoding"]["x"]["sort"]=keys
    _stage2_specific_refresh(observation)
    assert not journey_result(checks.j02_checks(observation=observation))["ok"]


@pytest.mark.parametrize("server_only",[False,True])
def test_j02_readonly_s5_cannot_conceal_an_extra_actual_run(tmp_path,server_only):
    import copy
    import capture_browser_trace as checks
    observation=_sequence_unit_observation(tmp_path,checks.J02_CASE)
    phase=observation["phases"][-1];frames=observation["frames"]
    extra=copy.deepcopy(frames[phase["start"]:phase["end"]]);end=frames[-1]["timestamp"]
    if server_only:extra=[f for f in extra if f.get("direction")=="server->client"]
    for index,f in enumerate(extra):
        f["timestamp"]=end+.1*(index+1)
        if f["decoded"].get("type")=="new_session":f["decoded"]["new_session"]["script_run_id"]="fake-s5-rerun"
        if f["decoded"].get("delta",{}).get("body")=="Script runs: 6":f["decoded"]["delta"]["body"]="Script runs: 7"
    frames.extend(extra);phase["end"]=len(frames);phase["dom_after"]["script_runs"]="7"
    phase["observation_end_timestamp"]=frames[-1]["timestamp"]+.04
    observation["screenshots"][-1]["timestamp"]=frames[-1]["timestamp"]+.02
    _stage2_specific_refresh(observation)
    assert not journey_result(checks.j02_checks(observation=observation))["ok"]


def _j00_retain_message(frame, message):
    """Serialize a generated/mutated test protobuf, using the shared decoders."""
    import base64
    import hashlib
    import runpy
    import capture_browser_trace as checks
    canonical = runpy.run_path(str(HERE.parent / "browser/forms_contract.py"))
    payload = message.SerializeToString()
    frame.update(base64=base64.b64encode(payload).decode(), bytes=len(payload), sha256=hashlib.sha256(payload).hexdigest())
    if frame["direction"] == "client->server":
        frame["decoded"] = checks.summarise_back(payload)
    else:
        full = canonical["_official_forward"](payload)
        frame.update(decoded=checks.summarise_forward(payload), official_forward=full,
                     form_blocks=canonical["_form_blocks_from_forward"](full))


def _j00_unit_forms(observation):
    """Offline protobuf unit model only; never a reference/browser oracle."""
    import copy
    from google.protobuf.json_format import ParseDict
    from streamlit.proto.BackMsg_pb2 import BackMsg
    from streamlit.proto.ForwardMsg_pb2 import ForwardMsg
    dom = {"text_inputs":[{"label":"Note","value":"","form_index":0}],
           "buttons":[{"label":"Pulse","testid":"stButton","form_index":-1},
                      {"label":"Apply note","testid":"stFormSubmitButton","form_index":0}],
           "forms":[{"index":0,"text_inputs":[{"label":"Note","value":"","form_index":0}],
                     "submit_buttons":[{"label":"Apply note","testid":"stFormSubmitButton","form_index":0}]}]}
    original, frames = observation["frames"], []
    for number, phase in enumerate(observation["phases"]):
        selected = copy.deepcopy(original[phase["start"]:phase["end"]])
        state_frame = next(f for f in selected if f["decoded"].get("type") == "rerun_script")
        states = state_frame["decoded"]["rerun_script"]["widget_states"]
        if number:
            states.append({"id":"note","value_field":"string_value","value":""})
        widgets = [{"id":v["id"], v["value_field"]:v.get("value_full",v.get("value"))} for v in states]
        _j00_retain_message(state_frame, ParseDict({"rerun_script":{"widget_states":{"widgets":widgets}}}, BackMsg()))
        elements = [({"new_element":{"button":{"id":"pulse","label":"Pulse"}}}, [0,9]),
                    ({"add_block":{"form":{"form_id":"apply_form","border":True,"enter_to_submit":True}}}, [0,10]),
                    ({"new_element":{"text_input":{"id":"note","label":"Note","default":"","form_id":"apply_form"}}}, [0,10,0]),
                    ({"new_element":{"button":{"id":"apply","label":"Apply note","form_id":"apply_form","is_form_submitter":True}}}, [0,10,1])]
        if not number:
            elements.insert(0, ({"new_element":{"file_uploader":{"id":"uploader","label":"Upload sales CSV"}}}, [0,0]))
        extra = []
        for index, (delta,path) in enumerate(elements):
            frame = dict(selected[-1], timestamp=selected[-1]["timestamp"]-.001*(len(elements)-index))
            _j00_retain_message(frame, ParseDict({"metadata":{"delta_path":path},"delta":delta}, ForwardMsg()))
            extra.append(frame)
        selected[-1:-1] = extra
        for value in ([phase["dom_before"],phase["dom_after"]] if number else [phase["dom_after"]]):
            value.update(form_membership=copy.deepcopy(dom),applied_note="",has_uploader=True,has_button=True,button_labels=["Pulse"])
        phase["start"] = len(frames)
        frames.extend(selected)
        phase["end"] = len(frames)
    observation["frames"] = frames
    _stage2_specific_refresh(observation)


def test_j00_generated_model_checks_eight_runs_and_shared_s5_s6_picture(tmp_path):
    import capture_browser_trace as checks
    observation = _sequence_unit_observation(tmp_path, checks.J00_CASE)
    result = journey_result(checks.j00_checks(observation=observation))
    assert result["ok"], result["failures"]
    assert len(observation["phases"]) == 8
    assert [p["dom_after"]["script_runs"] for p in observation["phases"]] == list("12345678")
    assert observation["screenshots"][-1]["step_ids"] == ["J00-S5","J00-S6"]
    assert result["counts"]["asserted"] == len(checks.J00_REQUIRED)


@pytest.mark.parametrize("phase_index", [0,7])
@pytest.mark.parametrize("mutation", ["missing_dom_form", "wrong_dom_membership", "note_edited_dom", "pulse_in_dom_form",
                                      "missing_raw", "bad_raw_sha", "missing_block", "wrong_block_id", "wrong_note_form",
                                      "wrong_apply_form", "note_default_missing", "note_default_nonempty", "apply_not_submitter",
                                      "note_wrong_path", "apply_wrong_path", "pulse_inside_block", "missing_official_cache", "forged_sidecache"])
def test_j00_form_membership_requires_actual_raw_paths_and_empty_note(tmp_path, phase_index, mutation):
    import base64
    from streamlit.proto.ForwardMsg_pb2 import ForwardMsg
    import capture_browser_trace as checks
    observation = _sequence_unit_observation(tmp_path, checks.J00_CASE)
    phase = observation["phases"][phase_index]
    current = observation["frames"][phase["start"]:phase["end"]]
    form = next(f for f in current if f.get("form_blocks"))
    note = next(f for f in current if f["decoded"].get("delta",{}).get("element") == "text_input")
    apply = next(f for f in current if f["decoded"].get("delta",{}).get("label") == "Apply note")
    pulse = next(f for f in current if f["decoded"].get("delta",{}).get("label") == "Pulse")
    membership = phase["dom_after"]["form_membership"]
    if mutation == "missing_dom_form": membership["forms"] = []
    elif mutation == "wrong_dom_membership": membership["buttons"][1]["form_index"] = -1
    elif mutation == "note_edited_dom": membership["text_inputs"][0]["value"] = "typed but never applied"
    elif mutation == "pulse_in_dom_form": membership["buttons"][0]["form_index"] = 0
    elif mutation == "missing_raw": note.pop("base64")
    elif mutation == "bad_raw_sha": form["sha256"] = "0"*64
    elif mutation == "missing_official_cache": note.pop("official_forward")
    elif mutation == "forged_sidecache": form["form_blocks"][0]["form_id"] = "another"
    else:
        frame = form if mutation in ("missing_block","wrong_block_id") else apply if mutation in ("wrong_apply_form","apply_not_submitter","apply_wrong_path") else pulse if mutation == "pulse_inside_block" else note
        message = ForwardMsg(); message.ParseFromString(base64.b64decode(frame["base64"]))
        if mutation == "missing_block": message.delta.add_block.ClearField("form")
        elif mutation == "wrong_block_id": message.delta.add_block.form.form_id = "another"
        elif mutation == "wrong_note_form": message.delta.new_element.text_input.form_id = "another"
        elif mutation == "wrong_apply_form": message.delta.new_element.button.form_id = "another"
        elif mutation == "note_default_missing": message.delta.new_element.text_input.ClearField("default")
        elif mutation == "note_default_nonempty": message.delta.new_element.text_input.default = "not untouched"
        elif mutation == "apply_not_submitter": message.delta.new_element.button.is_form_submitter = False
        elif mutation == "pulse_inside_block": message.metadata.delta_path[:] = form["official_forward"]["metadata"]["delta_path"]+[3]
        else: message.metadata.delta_path[-1] += 7
        _j00_retain_message(frame, message)
    _stage2_specific_refresh(observation)
    result = journey_result(checks.j00_checks(observation=observation))
    assert not result["ok"], mutation
    assert "J00" in result["failures"][0]["actual"], result["failures"]


@pytest.mark.parametrize("mutation", ["note_entered", "note_wrong_type", "note_missing", "apply_triggered", "pulse_triggered",
                                      "decoded_note_empty_raw_not", "decoded_false_raw_true", "false_oneof_absent"])
def test_j00_all_csv_states_prove_unentered_note_and_no_submit_not_just_applied_empty(tmp_path, mutation):
    import base64
    from streamlit.proto.BackMsg_pb2 import BackMsg
    import capture_browser_trace as checks
    observation = _sequence_unit_observation(tmp_path, checks.J00_CASE)
    phase = observation["phases"][-1]
    current = observation["frames"][phase["start"]:phase["end"]]
    frame = next(f for f in current if f["decoded"].get("type") == "rerun_script")
    ids = {f["decoded"]["delta"]["label"]:f["decoded"]["delta"]["id"] for f in current
           if f["decoded"].get("delta",{}).get("label") in ("Note","Apply note","Pulse","Include unknown region")}
    message = BackMsg(); message.ParseFromString(base64.b64decode(frame["base64"]))
    widgets = message.rerun_script.widget_states.widgets
    note = next(v for v in widgets if v.id == ids["Note"])
    if mutation == "note_entered": note.string_value = "unapplied entry"
    elif mutation == "note_wrong_type": note.bool_value = False
    elif mutation == "note_missing": widgets.remove(note)
    elif mutation in ("apply_triggered","pulse_triggered"):
        value = widgets.add(); value.id = ids["Apply note"] if mutation == "apply_triggered" else ids["Pulse"]; value.trigger_value = True
    elif mutation == "decoded_note_empty_raw_not": note.string_value = "wire-only entry"
    else:
        value = next(v for v in widgets if v.id == ids["Include unknown region"])
        if mutation == "false_oneof_absent": value.ClearField("bool_value")
        else: value.bool_value = True
    original = frame["decoded"]
    _j00_retain_message(frame, message)
    if mutation in ("decoded_note_empty_raw_not","decoded_false_raw_true"): frame["decoded"] = original
    _stage2_specific_refresh(observation)
    assert phase["dom_after"]["applied_note"] == ""
    assert not journey_result(checks.j00_checks(observation=observation))["ok"]


@pytest.mark.parametrize("observation", [None, {}, [], {"journey":"j02-sequence"}, {"journey":"j00-sequence"}])
def test_j00_missing_incomplete_or_other_contract_fails_closed(observation):
    from capture_browser_trace import j00_checks
    assert not journey_result(j00_checks(observation=observation))["ok"]


@pytest.mark.parametrize("mutation", ["missing_prep", "wrong_order", "foreign_socket", "reset_session", "reused_run", "counter_reset",
                                      "terminal2", "wrong_values", "stale_chart", "wrong_pointer_zero", "false_state_missing",
                                      "missing_png", "wrong_png_sha", "png_after_next_action", "s6_extra_event"])
def test_j00_preparations_full_values_typed_controls_and_png_ledger_are_mandatory(tmp_path, mutation):
    import copy
    import capture_browser_trace as checks
    observation = _sequence_unit_observation(tmp_path, checks.J00_CASE)
    phases, frames = observation["phases"], observation["frames"]
    phase = phases[-1]; current = frames[phase["start"]:phase["end"]]
    if mutation == "missing_prep": phases.pop(3)
    elif mutation == "wrong_order": phases[3],phases[4] = phases[4],phases[3]
    elif mutation == "foreign_socket": current[-1]["request_id"] = "foreign"
    elif mutation in ("reset_session","reused_run"):
        marker = next(f["decoded"]["new_session"] for f in current if f["decoded"].get("type") == "new_session")
        marker["session_id" if mutation == "reset_session" else "script_run_id"] = "foreign" if mutation == "reset_session" else "initial-run"
    elif mutation == "counter_reset": phase["dom_after"]["script_runs"] = "1"
    elif mutation == "terminal2": current[-1]["decoded"]["script_finished"]["status"] = 2
    elif mutation == "wrong_values": phase["dom_after"]["table_cells"][2] = "999"
    elif mutation == "stale_chart":
        chart = next(f["decoded"]["delta"] for f in current if f["decoded"].get("delta",{}).get("element") == "vega_lite_chart")
        chart["vega_lite_spec"]["data"]["name"] = "unrelated-old-dataset"
    elif mutation == "wrong_pointer_zero": phases[5]["action"]["pointer"]["after"]["aria_value_text"] = "100"
    elif mutation == "false_state_missing":
        state = next(f["decoded"]["rerun_script"]["widget_states"] for f in current if f["decoded"].get("type") == "rerun_script")
        state[:] = [v for v in state if v["id"] != "unknown"]
    elif mutation == "missing_png": observation["screenshots"].pop(5)
    elif mutation == "wrong_png_sha": observation["screenshots"][-1]["sha256"] = "0"*64
    elif mutation == "png_after_next_action": observation["screenshots"][0]["timestamp"] = phases[1]["start_timestamp"]+.1
    else:
        extra = copy.deepcopy(phase); extra["name"] = "s6-observe"; phases.append(extra)
    _stage2_specific_refresh(observation)
    assert not journey_result(checks.j00_checks(observation=observation))["ok"]


def _j06_unit_observation(tmp_path):
    """Generated protobuf/IPC unit contract, explicitly not a browser oracle."""
    import base64
    import copy
    import hashlib
    from google.protobuf.json_format import ParseDict
    from streamlit.proto.BackMsg_pb2 import BackMsg
    from streamlit.proto.ForwardMsg_pb2 import ForwardMsg
    import capture_browser_trace as c
    from unittest.mock import patch
    with patch.dict(_journey_contract_fixture.__globals__, {"_journey_fixture_parts":lambda *args:args}):
        _,_,generate,driver,_,_ = _journey_contract_fixture(tmp_path,"j06-unit")
    tabs = {key:{"namespace":"unit-"+key,"target_id":"target-"+key,"recorder_started_timestamp":1.,
                 "frames":[],"events":[],"http_timeline":[],"epochs":[]} for key in ("a","b")}
    phases, pictures, current, checkpoints, counters = [],[],{}, {}, {"a":[0,0],"b":[0,0]}
    png=base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+a8m0AAAAASUVORK5CYII=")
    def emit(tab, msg, direction, stamp, connection, request):
        data=msg.SerializeToString();encoded=base64.b64encode(data).decode()
        tab["frames"].append({"namespace":tab["namespace"],"connection":connection,"request_id":request,"direction":direction,
                              "timestamp":stamp,"base64":encoded,"bytes":len(data),"sha256":hashlib.sha256(data).hexdigest(),
                              "decoded":c.summarise_back(data) if direction=="client->server" else c.summarise_forward(data)})
        tab["events"].append({"method":"Network.webSocketFrameSent" if direction=="client->server" else "Network.webSocketFrameReceived",
                              "params":{"timestamp":stamp,"requestId":request,"response":{"opcode":2,"payloadData":encoded}}})
    for index,name in enumerate(c.J06_PHASES):
        clock=10.+index*20; action=dict(c.J06_ACTIONS[name],ok=True)
        views={}
        for key in ("a","b"):
            tab=tabs[key];mode=c.J06_MODES[name][key];connection=1 if key=="a" and name=="a-refresh" else 0
            epoch=key+str(connection);request=key+"-socket-"+str(connection)
            start=len(tab["frames"]);before=copy.deepcopy(current.get(key));active=mode!="readonly"
            if active:
                if mode in ("initial","refresh"):
                    ev=tab["events"];nav=len(ev);ev.append({"method":"Network.requestWillBeSent","params":{"timestamp":clock+1.2,"type":"Document","request":{"url":"http://127.0.0.1:8501/"}}})
                    hs=len(ev);ev.append({"method":"Network.webSocketWillSendHandshakeRequest","params":{"timestamp":clock+1.3,"requestId":request,"request":{"headers":{"Sec-WebSocket-Protocol":"streamlit, actual-token"}}}})
                    response=len(ev);ev.append({"method":"Network.webSocketHandshakeResponseReceived","params":{"timestamp":clock+1.4,"requestId":request,"response":{"status":101,"headers":{"Sec-WebSocket-Protocol":"streamlit"}}}})
                    tab["epochs"].append({"id":epoch,"connection":connection,"request_id":request,"navigation_timestamp":clock+1.1,
                                          "navigation_event":nav,"handshake_event":hs,"response_event":response})
                    counters[key]=[1,0]
                    generated=[{"direction":"client->server","decoded":{"type":"rerun_script","rerun_script":{"widget_states":[]}}},
                               {"direction":"server->client","decoded":{"type":"new_session"}}]
                    for kind,label,identity in (("file_uploader","Upload sales CSV","uploader"),("selectbox","Group by","group"),
                                                ("slider","Minimum amount","minimum"),("checkbox","Include unknown region","unknown")):
                        generated.append({"direction":"server->client","decoded":{"type":"delta","delta":{"element":kind,"label":label,"id":identity}}})
                    after={"table_present":False,"table_cells":[],"chart_present":False,"chart_bars":0,"chart_marks":"","chart_labels":[],
                           "selectbox_value":"category","slider_value":"0","checkbox_checked":True,"alerts":["Upload a CSV to see the aggregated result."]}
                    generated.append({"direction":"server->client","decoded":{"type":"delta","delta":{"element":"alert","alert":{"format":"INFO","body":after["alerts"][0]}}}})
                else:
                    counters[key][0]+=1
                    if mode=="pulse":counters[key][1]+=1
                    group="region" if mode=="select" else "category"
                    model, timeline = [],[]
                    _,after=generate(model,timeline,tab["namespace"],"sales_basic.csv",group,upload=mode=="upload",old=before)
                    generated=model[1:-1] # omit fixture's initial marker and final finish
                    if mode=="upload":
                        action.update(action="upload",file=str((HERE.parent/'fixtures/csv/sales_basic.csv').resolve()),
                                      file_bytes=737,file_sha256=c.J01_FILE_FINGERPRINTS['sales_basic.csv'][1])
                    for f in generated:
                        if f['decoded'].get('type')=='rerun_script' and mode=='pulse':
                            f['decoded']['rerun_script']['widget_states'].append({'id':'pulse','value_field':'trigger_value','value':True})
                after.update(script_runs=str(counters[key][0]),pulses=str(counters[key][1]),exceptions=[],
                             uploaded_files=[] if mode in ('initial','refresh') else ['sales_basic.csv'])
                generated += [{"direction":"server->client","decoded":{"type":"delta","delta":{"element":"button","label":"Pulse","id":"pulse"}}}]
                for label,value in (("Script runs",counters[key][0]),("Pulses",counters[key][1])):
                    generated.append({"direction":"server->client","decoded":{"type":"delta","delta":{"element":"markdown","body":f"{label}: {value}"}}})
                generated.append({"direction":"server->client","decoded":{"type":"script_finished"}})
                for number,f in enumerate(generated):
                    d=f['decoded'];msg=BackMsg() if f['direction']=='client->server' else ForwardMsg();kind=d['type']
                    if kind=='rerun_script':
                        ws=d['rerun_script']['widget_states'];ParseDict({'rerun_script':{'widget_states':{'widgets':[{'id':s['id'],s['value_field']:s.get('value_full',s.get('value'))} for s in ws]}}},msg)
                    elif kind=='file_urls_request':ParseDict({kind:d[kind]},msg)
                    elif kind=='file_urls_response':ParseDict({kind:d[kind]},msg)
                    elif kind=='new_session':
                        msg.new_session.initialize.session_id='session-'+tab['namespace']+('-refreshed' if connection else '')
                        msg.new_session.script_run_id=key+'-run-'+str(index);msg.new_session.config.max_cached_message_age=2
                    elif kind=='script_finished':msg.script_finished=0
                    else:
                        delta=d['delta'];el=delta['element'];element=msg.delta.new_element
                        if el=='dataframe':element.dataframe.arrow_data.data=base64.b64decode(delta['arrow']['base64'])
                        elif el=='vega_lite_chart':
                            element.vega_lite_chart.spec=json.dumps(delta['vega_lite_spec'])
                            for ds in delta['vega_lite_datasets']:
                                entry=element.vega_lite_chart.datasets.add();entry.name=ds['name'];entry.has_name=True;entry.data.data=base64.b64decode(ds['arrow']['base64'])
                        elif el in ('markdown','text'):element.markdown.body=delta['body']
                        elif el=='alert':ParseDict(delta['alert'],element.alert)
                        else:
                            value={'id':delta['id'],'label':delta['label']}
                            if el=='selectbox':value.update(default=0,options=['category','region','channel'])
                            elif el=='slider':value.update(default=[0.],min=0,max=200,step=10)
                            elif el=='checkbox':value['default']=True
                            ParseDict(value,getattr(element,el))
                    emit(tab,msg,f['direction'],clock+2+number*.01,connection,request)
                if mode=='upload':
                    reqframe=next(f for f in tab['frames'][start:] if f['decoded']['type']=='file_urls_response')
                    info=reqframe['decoded']['file_urls_response']['file_urls'][0]
                    stamp=reqframe['timestamp']+.001;url='http://127.0.0.1:8501'+info['upload_url'];rid='put-'+key
                    http={'request_id':rid,'method':'PUT','url':url,'timestamp':stamp,'response_timestamp':stamp+.001,'status':204,
                          'request_headers':{'Content-Type':'multipart/form-data; boundary=unit'}};tab['http_timeline'].append(http)
                    tab['events'] += [{'method':'Network.requestWillBeSent','params':{'timestamp':stamp,'requestId':rid,'request':{'method':'PUT','url':url}}},
                                      {'method':'Network.responseReceived','params':{'timestamp':stamp+.001,'requestId':rid,'response':{'status':204}}}]
                current[key]=after
                marker=next(f for f in tab['frames'][start:] if f['decoded']['type']=='new_session')['decoded']['new_session']['script_run_id']
                checkpoints[key]={'epoch':epoch,'script_run_id':marker,'finish_frame':len(tab['frames'])-1}
            view=driver['_phase'](name,action,tab['frames'],start,len(tab['frames']),before,copy.deepcopy(current[key]),generate.arrow_files)
            view.update(mode=mode,epoch=epoch,read_start_timestamp=clock,read_end_timestamp=clock+4,checkpoint=copy.deepcopy(checkpoints[key]))
            views[key]=view
            file=f'{index}-{key}.png';(tmp_path/file).write_bytes(png)
            pictures.append({'phase':name,'tab':key,'namespace':tab['namespace'],'epoch':epoch,'file':file,
                             'sha256':hashlib.sha256(png).hexdigest(),'timestamp':clock+5,'step_ids':list(c.J06_PNG_ROLES[name]),'role':'preparation'})
        phases.append({'name':name,'action':action,'action_timestamp':clock+1,'observation_end_timestamp':clock+6,'views':views})
    return {'journey':c.J06_CASE,'contract':c.J06_CONTRACT,'url':'http://127.0.0.1:8501/','ipc_dir':str(tmp_path),'tabs':tabs,'phases':phases,'screenshots':pictures}


def test_j06_generated_two_tab_contract(tmp_path):
    import capture_browser_trace as c
    result=journey_result(c.j06_checks(observation=_j06_unit_observation(tmp_path)))
    assert result['ok'],result['failures']


def _j06_replace_proto(tab, index, message):
    import base64
    import hashlib
    import capture_browser_trace as c
    frame=tab['frames'][index];data=message.SerializeToString();encoded=base64.b64encode(data).decode()
    event=next(e for e in tab['events'] if e.get('method') in ('Network.webSocketFrameSent','Network.webSocketFrameReceived')
               and e['params']['timestamp']==frame['timestamp'] and e['params']['requestId']==frame['request_id'])
    event['params']['response']['payloadData']=encoded
    frame.update(base64=encoded,bytes=len(data),sha256=hashlib.sha256(data).hexdigest(),
                 decoded=c.summarise_back(data) if frame['direction']=='client->server' else c.summarise_forward(data))


@pytest.mark.parametrize('mutation', ['missing_phase','reordered','missing_peer','late_recorder','missing_navigation','three_entry_initial',
                                     'wrong_handshake_request','bad_raw_sha','wrong_cursor','stale_read_clock','stale_checkpoint',
                                     'readonly_fake_ipc','peer_wrong_cells','b_early_file','b_counter_leak','missing_file_dom',
                                     'refreshed_old_id','b_session_borrowed','double_pulse','wrong_pulse_sender','contradictory_slider',
                                     'lost_file','foreign_upload_url','extra_http_delete','wrong_http_event','missing_png','wrong_png_sha','late_png'])
def test_j06_rejects_incomplete_crossed_or_invented_proof(tmp_path,mutation):
    import base64
    from streamlit.proto.ForwardMsg_pb2 import ForwardMsg
    from streamlit.proto.BackMsg_pb2 import BackMsg
    import capture_browser_trace as c
    o=_j06_unit_observation(tmp_path);a=o['tabs']['a'];b=o['tabs']['b'];ps=o['phases'];peer=ps[5]['views']['b']
    if mutation=='missing_phase':ps.pop(5)
    elif mutation=='reordered':ps[3],ps[4]=ps[4],ps[3]
    elif mutation=='missing_peer':ps[2]['views'].pop('b')
    elif mutation=='late_recorder':a['recorder_started_timestamp']=12.
    elif mutation=='missing_navigation':a['epochs'][0]['navigation_event']=a['epochs'][0]['handshake_event']
    elif mutation=='three_entry_initial':a['events'][a['epochs'][0]['handshake_event']]['params']['request']['headers']['Sec-WebSocket-Protocol']+=', forged-session'
    elif mutation=='wrong_handshake_request':a['epochs'][1]['request_id']='old-socket'
    elif mutation=='bad_raw_sha':a['frames'][0]['sha256']='0'*64
    elif mutation=='wrong_cursor':peer['start']=1;peer['end']=1
    elif mutation=='stale_read_clock':peer['read_end_timestamp']=peer['read_start_timestamp']
    elif mutation=='stale_checkpoint':ps[4]['views']['a']['checkpoint']=ps[1]['views']['a']['checkpoint']
    elif mutation=='readonly_fake_ipc':peer['ipc']['table']={'arrow':{'sha256':'claimed'}}
    elif mutation=='peer_wrong_cells':ps[6]['views']['a']['dom_after']['table_cells'][2]='999'
    elif mutation=='b_early_file':peer['dom_after']['uploaded_files']=['sales_basic.csv']
    elif mutation=='b_counter_leak':peer['dom_after']['pulses']='3'
    elif mutation=='missing_file_dom':ps[0]['views']['b']['dom_after'].pop('uploaded_files')
    elif mutation in ('refreshed_old_id','b_session_borrowed'):
        tab=a if mutation=='refreshed_old_id' else b
        i=next(i for i,f in enumerate(tab['frames']) if f['decoded']['type']=='new_session' and (mutation!='refreshed_old_id' or f['connection']==1))
        msg=ForwardMsg();msg.ParseFromString(base64.b64decode(tab['frames'][i]['base64']));msg.new_session.initialize.session_id='session-unit-a';_j06_replace_proto(tab,i,msg)
    elif mutation in ('double_pulse','wrong_pulse_sender','contradictory_slider','lost_file'):
        phase=ps[2];i=next(i for i in range(phase['views']['a']['start'],phase['views']['a']['end']) if a['frames'][i]['decoded']['type']=='rerun_script')
        msg=BackMsg();msg.ParseFromString(base64.b64decode(a['frames'][i]['base64']));ws=msg.rerun_script.widget_states.widgets
        if mutation=='double_pulse':ws.add().CopyFrom(next(v for v in ws if v.id=='pulse'))
        elif mutation=='wrong_pulse_sender':next(v for v in ws if v.id=='pulse').id='unrelated-button'
        elif mutation=='contradictory_slider':next(v for v in ws if v.id=='minimum').double_array_value.data[:]=[100.]
        else:next(v for v in ws if v.id=='uploader').file_uploader_state_value.Clear()
        _j06_replace_proto(a,i,msg)
    elif mutation=='foreign_upload_url':a['http_timeline'][0]['url']=b['http_timeline'][0]['url']
    elif mutation=='extra_http_delete':
        import copy
        h=copy.deepcopy(a['http_timeline'][0]);h['method']='DELETE';a['http_timeline'].append(h)
    elif mutation=='wrong_http_event':next(e for e in a['events'] if e.get('method')=='Network.responseReceived')['params']['response']['status']=500
    elif mutation=='missing_png':o['screenshots'].pop()
    elif mutation=='wrong_png_sha':o['screenshots'][0]['sha256']='0'*64
    else:o['screenshots'][0]['timestamp']=o['phases'][1]['action_timestamp']
    result=journey_result(c.j06_checks(observation=o));assert not result['ok'],mutation


def _j06_unit_wire(messages, connections=None):
    import base64
    import hashlib
    import capture_browser_trace as c
    tab={'namespace':'cache-unit','frames':[],'events':[]}
    for index,msg in enumerate(messages):
        data=msg.SerializeToString();encoded=base64.b64encode(data).decode();conn=connections[index] if connections else 0;request='socket-'+str(conn)
        tab['frames'].append({'namespace':tab['namespace'],'connection':conn,'request_id':request,'direction':'server->client',
                              'timestamp':float(index),'base64':encoded,'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest(),'decoded':c.summarise_forward(data)})
        tab['events'].append({'method':'Network.webSocketFrameReceived','params':{'timestamp':float(index),'requestId':request,'response':{'opcode':2,'payloadData':encoded}}})
    return tab


def test_j06_cache_reference_uses_current_metadata_without_repeated_entity():
    from streamlit.proto.ForwardMsg_pb2 import ForwardMsg
    from unittest.mock import patch
    import capture_browser_trace as c
    full=ForwardMsg(hash='shared');full.metadata.cacheable=True;full.metadata.delta_path[:]=[0,1];full.delta.new_element.markdown.body='cached entity'
    ref=ForwardMsg(ref_hash='shared');ref.metadata.delta_path[:]=[0,7]
    tab=_j06_unit_wire([full,ref]);seen=[];decode=c.summarise_forward
    def observe(data):
        msg=ForwardMsg();msg.ParseFromString(data);seen.append(msg);return decode(data)
    with patch.object(c,'summarise_forward',observe):resolved=c._j06_materialize_frames(tab)
    # The summary now exposes the delta path, so the ref resolution differs
    # from the original full only by carrying the CURRENT metadata's path;
    # the inner delta dict is copied, not mutated, by the strip helper.
    def strip_path(summary):
        copy=dict(summary);delta=dict(summary.get('delta') or {});delta.pop('path',None);copy['delta']=delta;return copy
    assert strip_path(resolved[1]['decoded'])==strip_path(resolved[0]['decoded'])
    assert resolved[0]['decoded']['delta']['path']==[0,1]
    assert resolved[1]['decoded']['delta']['path']==[0,7]
    assert seen[-1].metadata.delta_path==[0,7] and seen[-1].delta.new_element.markdown.body=='cached entity'
    assert tab['frames'][1]['decoded']['type']=='ref_hash' # immutable raw


@pytest.mark.parametrize('mutation',['uncacheable','missing_hash','cache_miss','missing_metadata','expired','new_epoch','foreign_tab'])
def test_j06_cache_missing_foreign_or_expired_reference_is_rejected(mutation):
    from streamlit.proto.ForwardMsg_pb2 import ForwardMsg
    import capture_browser_trace as c
    full=ForwardMsg(hash='shared');full.metadata.cacheable=True;full.delta.new_element.markdown.body='cached'
    ref=ForwardMsg(ref_hash='shared');ref.metadata.delta_path[:]=[0,1]
    messages=[full,ref];connections=None
    if mutation=='uncacheable':full.metadata.cacheable=False
    elif mutation=='missing_hash':full.hash=''
    elif mutation=='cache_miss':ref.ref_hash='missing'
    elif mutation=='missing_metadata':ref.ClearField('metadata')
    elif mutation=='expired':
        initial=ForwardMsg();initial.new_session.config.max_cached_message_age=0;finish=ForwardMsg(script_finished=0);messages=[initial,full,finish,ref]
    elif mutation=='new_epoch':connections=[0,1]
    else:
        c._j06_materialize_frames(_j06_unit_wire([full]));messages=[ref]
    with pytest.raises(ValueError):c._j06_materialize_frames(_j06_unit_wire(messages,connections))


@pytest.mark.parametrize('observation',[None,{},[],{'journey':'sessions'},{'journey':'j06-sequence'}])
def test_j06_missing_contract_fails_closed(observation):
    from capture_browser_trace import j06_checks
    assert not journey_result(j06_checks(observation=observation))['ok']


def _j06_unit_readonly_message(o, message, *, outside=False):
    """Insert actual encoded test bytes and the corresponding CDP event/cursors."""
    import copy
    wire=_j06_unit_wire([message]);phase=o['phases'][5];tab=o['tabs']['a'];view=phase['views']['a'];cursor=view['start']
    frame=wire['frames'][0];frame.update(namespace=tab['namespace'],connection=0,request_id=tab['epochs'][0]['request_id'],
                                      timestamp=phase['action_timestamp']+.5 if not outside else view['read_start_timestamp']-1)
    event=wire['events'][0];event['params'].update(timestamp=frame['timestamp'],requestId=frame['request_id'])
    next_stamp=tab['frames'][cursor]['timestamp'];event_index=next(i for i,e in enumerate(tab['events'])
        if e.get('method') in ('Network.webSocketFrameSent','Network.webSocketFrameReceived') and e['params']['timestamp']==next_stamp)
    tab['events'].insert(event_index,event);tab['frames'].insert(cursor,frame)
    for epoch in tab['epochs']:
        for field in ('navigation_event','handshake_event','response_event'):
            if epoch[field]>=event_index:epoch[field]+=1
    for p in o['phases'][5:]:
        v=p['views']['a']
        if p is not phase or outside:v['start']+=1
        v['end']+=1
        if v['checkpoint']['finish_frame']>=cursor:v['checkpoint']['finish_frame']+=1
        if p is phase and not outside:v['start_timestamp']=v['end_timestamp']=frame['timestamp']


@pytest.mark.parametrize('kind',['heartbeat','new_session','delta','finish','running_status','outside_hidden_run'])
def test_j06_readonly_allows_real_heartbeat_but_no_hidden_business_run(tmp_path,kind):
    from streamlit.proto.ForwardMsg_pb2 import ForwardMsg
    import capture_browser_trace as c
    o=_j06_unit_observation(tmp_path);msg=ForwardMsg()
    if kind=='heartbeat':msg.heartbeat_ack=True
    elif kind in ('new_session','outside_hidden_run'):msg.new_session.script_run_id='hidden-run';msg.new_session.initialize.session_id='session-unit-a'
    elif kind=='delta':msg.delta.new_element.markdown.body='hidden business output'
    elif kind=='finish':msg.script_finished=0
    else:msg.session_status_changed.script_is_running=True
    _j06_unit_readonly_message(o,msg,outside=kind=='outside_hidden_run')
    result=journey_result(c.j06_checks(observation=o))
    assert result['ok'] is (kind=='heartbeat'),result['failures']


@pytest.mark.parametrize('tab_key,epoch_index',[('a',0),('b',0),('a',1)])
@pytest.mark.parametrize('late',['handshake_and_response','response_only'])
def test_j06_c1_handshake_response_cannot_follow_its_epoch_frames(tmp_path,tab_key,epoch_index,late):
    import capture_browser_trace as c
    o=_j06_unit_observation(tmp_path);tab=o['tabs'][tab_key];epoch=tab['epochs'][epoch_index]
    first=next(f['timestamp'] for f in tab['frames'] if f['request_id']==epoch['request_id'])
    if late=='handshake_and_response':tab['events'][epoch['handshake_event']]['params']['timestamp']=first+.9
    tab['events'][epoch['response_event']]['params']['timestamp']=first+1.
    result=journey_result(c.j06_checks(observation=o))
    assert not result['ok'],result


def _j06_insert_active_message(o,message,*,phase_index=2,position='after_finish',tab_key='a'):
    wire=_j06_unit_wire([message]);tab=o['tabs'][tab_key];view=o['phases'][phase_index]['views'][tab_key];frames=tab['frames']
    marker=next(i for i in range(view['start'],view['end']) if frames[i]['decoded']['type']=='new_session')
    cursor=view['checkpoint']['finish_frame']+1 if position=='after_finish' else marker
    stamp=frames[cursor-1]['timestamp']+.005
    frame=wire['frames'][0];frame.update(namespace=tab['namespace'],connection=frames[marker]['connection'],request_id=frames[marker]['request_id'],timestamp=stamp)
    event=wire['events'][0];event['params'].update(timestamp=stamp,requestId=frame['request_id'])
    event_index=next((i for i,e in enumerate(tab['events']) if e.get('method') in ('Network.webSocketFrameSent','Network.webSocketFrameReceived')
                      and e['params']['timestamp']>stamp),len(tab['events']))
    tab['events'].insert(event_index,event);frames.insert(cursor,frame)
    for epoch in tab['epochs']:
        for field in ('navigation_event','handshake_event','response_event'):
            if epoch[field]>=event_index:epoch[field]+=1
    for p in o['phases'][phase_index:]:
        v=p['views'][tab_key];target=p is o['phases'][phase_index]
        if not target:v['start']+=1
        v['end']+=1
        if v['checkpoint']['finish_frame']>=cursor:v['checkpoint']['finish_frame']+=1
        if target:
            v['start_timestamp']=frames[v['start']]['timestamp'];v['end_timestamp']=frames[v['end']-1]['timestamp']
            for completion in v['completions']:
                if completion['frame']>=cursor-v['start']:completion['frame']+=1


@pytest.mark.parametrize('position',['before_run','after_finish'])
@pytest.mark.parametrize('phase_index,tab_key',[(0,'a'),(1,'a'),(2,'a'),(6,'b'),(7,'b'),(8,'a')])
def test_j06_c2_business_delta_outside_target_run_is_not_covered_success(tmp_path,position,phase_index,tab_key):
    from streamlit.proto.ForwardMsg_pb2 import ForwardMsg
    import capture_browser_trace as c
    o=_j06_unit_observation(tmp_path);message=ForwardMsg()
    message.delta.new_element.markdown.body='UNRECORDED POST-FINISH OUTPUT' if position=='after_finish' else 'UNRECORDED PRE-RUN OUTPUT'
    _j06_insert_active_message(o,message,position=position,phase_index=phase_index,tab_key=tab_key)
    result=journey_result(c.j06_checks(observation=o))
    assert not result['ok'],result


@pytest.mark.parametrize('position',['before_run','after_finish'])
@pytest.mark.parametrize('phase_index,tab_key',[(0,'a'),(1,'a'),(2,'a'),(6,'b'),(7,'b'),(8,'a')])
def test_j06_active_boundary_allows_heartbeat_without_inventing_a_run(tmp_path,position,phase_index,tab_key):
    from streamlit.proto.ForwardMsg_pb2 import ForwardMsg
    import capture_browser_trace as c
    o=_j06_unit_observation(tmp_path);message=ForwardMsg(heartbeat_ack=True)
    _j06_insert_active_message(o,message,position=position,phase_index=phase_index,tab_key=tab_key)
    result=journey_result(c.j06_checks(observation=o))
    assert result['ok'],result['failures']


@pytest.mark.parametrize('close_position',['after_last_frame','before_last_frame'])
def test_j06_epoch_frames_obey_actual_close_event_without_extra_interface_fields(tmp_path,close_position):
    import capture_browser_trace as c
    o=_j06_unit_observation(tmp_path);tab=o['tabs']['a'];epoch=tab['epochs'][0]
    last=max(f['timestamp'] for f in tab['frames'] if f['request_id']==epoch['request_id'])
    tab['events'].append({'method':'Network.webSocketClosed','params':{'requestId':epoch['request_id'],
                        'timestamp':last+.001 if close_position=='after_last_frame' else last-.001}})
    result=journey_result(c.j06_checks(observation=o))
    assert result['ok'] is (close_position=='after_last_frame'),result['failures']


def test_j06_http101_at_first_frame_time_is_legal_and_upload_exchange_remains_valid(tmp_path):
    import capture_browser_trace as c
    o=_j06_unit_observation(tmp_path)
    for tab in o['tabs'].values():
        for epoch in tab['epochs']:
            first=next(f['timestamp'] for f in tab['frames'] if f['request_id']==epoch['request_id'])
            tab['events'][epoch['response_event']]['params']['timestamp']=first
    result=journey_result(c.j06_checks(observation=o))
    assert result['ok'],result['failures']


def _j09_unit_observation(tmp_path,plan='ui-probe',*,natural_client_state=True):
    """Compose generated unit protobufs; this is not reference evidence."""
    import base64
    import copy
    import hashlib
    import runpy
    from google.protobuf.json_format import MessageToDict,ParseDict
    from streamlit.proto.ForwardMsg_pb2 import ForwardMsg
    from streamlit.proto.BackMsg_pb2 import BackMsg
    import capture_browser_trace as c
    base=_j06_unit_observation(tmp_path);a,b=base['tabs']['a'],base['tabs']['b']
    driver=runpy.run_path(str(HERE.parent/'browser/numeric_capture.py'));store=driver['_ArrowFiles'](tmp_path)
    store.by_digest={hashlib.sha256(p.read_bytes()).hexdigest():p.name for p in tmp_path.glob('arrow-*.bin')}
    page={'namespace':a['namespace'],'target_id':a['target_id'],'recorder_started_timestamp':1.,'frames':[],'events':[],'http_timeline':[],'epochs':[]}
    phases,pictures,previous,checkpoint=[],[],None,None
    png=(tmp_path/'0-a.png').read_bytes();s0='session-unit-a'
    def epoch(index,clock):
        ev=page['events'];document=page['epochs'][0]['document_event'] if index==1 else len(ev)
        if index!=1:ev.append({'method':'Network.requestWillBeSent','params':{'type':'Document','timestamp':clock+1.1,'request':{'url':base['url']}}})
        hs=len(ev);ev.append({'method':'Network.webSocketWillSendHandshakeRequest','params':{'timestamp':clock+1.2,'requestId':'j09-'+str(index),'request':{'headers':{'Sec-WebSocket-Protocol':'streamlit, token'+(', '+s0 if index==1 else '')}}}})
        response=len(ev);ev.append({'method':'Network.webSocketHandshakeResponseReceived','params':{'timestamp':clock+1.3,'requestId':'j09-'+str(index),'response':{'status':101,'headers':{'Sec-WebSocket-Protocol':'streamlit'}}}})
        page['epochs'].append({'id':'e'+str(index),'connection':index,'request_id':'j09-'+str(index),'document_event':document,
                               'navigation_event':None if index==1 else document,'navigation_timestamp':None if index==1 else clock+1,
                               'handshake_event':hs,'response_event':response})
    for number,name in enumerate(c.J09_PHASES[plan]):
        clock=10.+number*20;conn=2 if name=='refresh' else 1 if name.startswith('probe-') or name=='reconnect-observe' else 0
        start=len(page['frames']);before=copy.deepcopy(previous);action=dict(c.J09_ACTIONS[name],ok=True)
        if name in ('initial','refresh'):epoch(conn,clock)
        extra={};template=None
        if name=='reconnect-observe':
            closed=len(page['events']);page['events'].append({'method':'Network.webSocketClosed','params':{'requestId':'j09-0','timestamp':clock+1.05}});epoch(1,clock)
            # Actual CDP hook success shape, recorded in owned J09 preflight;
            # the surrounding lifecycle here remains generated unit evidence.
            extra={'close':{'request_id':'j09-0','command_timestamp':clock+1,'completed_timestamp':clock+1.1,
                            'evaluation_result':{'id':24,'result':{'result':{'type':'string','value':'closed'}}},'closed_event':closed},
                   'auto_observation':{'start_timestamp':clock+1.3,'end_timestamp':clock+7}}
            if plan=='natural':template=(a,base['phases'][2]['views']['a'],5,2)
        else:
            choices={'initial':(a,base['phases'][0]['views']['a'],1,0),'upload-baseline':(a,base['phases'][1]['views']['a'],2,0),
                     'pulse-1':(a,base['phases'][2]['views']['a'],3,1),'pulse-2':(a,base['phases'][3]['views']['a'],4,2),
                     'probe-region':(b,base['phases'][7]['views']['b'],5,2),'probe-category':(a,base['phases'][3]['views']['a'],6,2),
                     'refresh':(a,base['phases'][8]['views']['a'],1,0)}
            template=choices[name]
        if template:
            tab,view,runs,pulses=template
            for offset,frame in enumerate(tab['frames'][view['start']:view['end']]):
                if name=='reconnect-observe' and frame['direction']=='client->server' and not natural_client_state:
                    continue
                message=BackMsg() if frame['direction']=='client->server' else ForwardMsg();message.ParseFromString(base64.b64decode(frame['base64']))
                if frame['direction']=='client->server':
                    # Unit fixture B's file owner becomes the same retained A owner.
                    doc=json.loads(json.dumps(MessageToDict(message)).replace('session-unit-b',s0));message=ParseDict(doc,BackMsg())
                    if message.WhichOneof('type')=='rerun_script' and name not in ('pulse-1','pulse-2'):
                        widgets=message.rerun_script.widget_states.widgets
                        for item in list(widgets):
                            if item.WhichOneof('value')=='trigger_value':widgets.remove(item)
                elif message.WhichOneof('type')=='new_session':
                    message.new_session.initialize.session_id=s0+'-refreshed' if conn==2 else s0;message.new_session.script_run_id='j09-'+name
                elif message.WhichOneof('type')=='delta' and message.delta.WhichOneof('type')=='new_element':
                    element=message.delta.new_element
                    if element.WhichOneof('type')=='markdown':
                        if element.markdown.body.startswith('Script runs:'):element.markdown.body=f'Script runs: {runs}'
                        elif element.markdown.body.startswith('Pulses:'):element.markdown.body=f'Pulses: {pulses}'
                data=message.SerializeToString();encoded=base64.b64encode(data).decode();stamp=clock+2+offset*.01
                raw={'namespace':page['namespace'],'connection':conn,'request_id':'j09-'+str(conn),'direction':frame['direction'],
                     'timestamp':stamp,'base64':encoded,'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest(),
                     'decoded':c.summarise_back(data) if frame['direction']=='client->server' else c.summarise_forward(data)}
                page['frames'].append(raw);page['events'].append({'method':'Network.webSocketFrameSent' if frame['direction']=='client->server' else 'Network.webSocketFrameReceived',
                    'params':{'timestamp':stamp,'requestId':raw['request_id'],'response':{'opcode':2,'payloadData':encoded}}})
            after=copy.deepcopy(view['dom_after']);after.update(script_runs=str(runs),pulses=str(pulses))
            checkpoint={'epoch':'e'+str(conn),'script_run_id':'j09-'+name,'finish_frame':len(page['frames'])-1}
        else:after=copy.deepcopy(previous)
        if name=='upload-baseline':
            action.update(file=str((HERE.parent/'fixtures/csv/sales_basic.csv').resolve()),file_bytes=737,file_sha256=c.J01_FILE_FINGERPRINTS['sales_basic.csv'][1])
            response=next(f for f in page['frames'][start:] if f['decoded']['type']=='file_urls_response')
            h=copy.deepcopy(a['http_timeline'][0]);h.update(timestamp=response['timestamp']+.001,response_timestamp=response['timestamp']+.002)
            page['http_timeline'].append(h);page['events'] += [
                {'method':'Network.requestWillBeSent','params':{'timestamp':h['timestamp'],'requestId':h['request_id'],'request':{'method':'PUT','url':h['url']}}},
                {'method':'Network.responseReceived','params':{'timestamp':h['response_timestamp'],'requestId':h['request_id'],'response':{'status':204}}}]
        phase=driver['_phase'](name,action,page['frames'],start,len(page['frames']),before,after,store)
        phase.update(epoch='e'+str(conn),action_timestamp=clock+1,observation_end_timestamp=clock+10,
                     read_start_timestamp=clock,read_end_timestamp=clock+8,checkpoint=copy.deepcopy(checkpoint),**extra)
        phases.append(phase);previous=copy.deepcopy(after)
        file='j09-'+name+'.png';(tmp_path/file).write_bytes(png)
        pictures.append({'phase':name,'namespace':page['namespace'],'epoch':phase['epoch'],'file':file,'sha256':hashlib.sha256(png).hexdigest(),
                         'timestamp':clock+9,'step_ids':list(c.J09_PNG_ROLES[name]),'role':'preparation'})
    return {'journey':c.J09_CASE,'contract':c.J09_CONTRACT,'plan':plan,'url':base['url'],'ipc_dir':str(tmp_path),
            'page':page,'phases':phases,'screenshots':pictures}


@pytest.mark.parametrize('plan',['natural','ui-probe'])
def test_j09_generated_closed_plan_has_real_run_and_wire_contract(tmp_path,plan):
    import capture_browser_trace as c
    o=_j09_unit_observation(tmp_path,plan);result=journey_result(c.j09_checks(observation=o))
    assert result['ok'],result['failures']
    assert len(o['screenshots'])==(6 if plan=='natural' else 8)


def _j09_refresh_unit_summaries(o):
    """Derive only phase summaries from effective test frames; retain raw bytes."""
    import hashlib
    import runpy
    import capture_browser_trace as c
    driver=runpy.run_path(str(HERE.parent/'browser/numeric_capture.py'));root=pathlib.Path(o['ipc_dir']);store=driver['_ArrowFiles'](root)
    store.by_digest={hashlib.sha256(p.read_bytes()).hexdigest():p.name for p in root.glob('arrow-*.bin')}
    frames=c._j09_materialize_frames(o['page'])
    for phase in o['phases']:
        phase.update(driver['_phase'](phase['name'],phase['action'],frames,phase['start'],phase['end'],phase['dom_before'],phase['dom_after'],store))


@pytest.mark.parametrize('plan',['natural','ui-probe'])
@pytest.mark.parametrize('mutation',['missing_phase','wrong_plan','late_recorder','handshake_after_frames','fresh_third_entry',
                                     'reconnect_missing_id','foreign_third_id','reconnect_new_document','f5_old_document','implicit_navigation',
                                     'missing_closed','foreign_closed','closed_before_command','short_observation','fake_observation_clock',
                                     'wrong_cursor','wrong_checkpoint','extra_put','hidden_delete','wrong_file_dom','wrong_counts',
                                     'wrong_golden_cells','missing_png','wrong_png_sha','missing_s4_not_a_pass'])
def test_j09_closed_plan_rejects_lifecycle_state_or_evidence_mutations(tmp_path,plan,mutation):
    import copy
    import capture_browser_trace as c
    o=_j09_unit_observation(tmp_path,plan);page=o['page'];events=page['events'];epochs=page['epochs'];phase=o['phases'][4]
    if mutation=='missing_phase':o['phases'].pop(2)
    elif mutation=='wrong_plan':o['plan']='ui-probe' if plan=='natural' else 'natural'
    elif mutation=='late_recorder':page['recorder_started_timestamp']=20.
    elif mutation=='handshake_after_frames':events[epochs[1]['response_event']]['params']['timestamp']=10000.
    elif mutation=='fresh_third_entry':events[epochs[0]['handshake_event']]['params']['request']['headers']['Sec-WebSocket-Protocol']+=', forged'
    elif mutation in ('reconnect_missing_id','foreign_third_id'):
        events[epochs[1]['handshake_event']]['params']['request']['headers']['Sec-WebSocket-Protocol']='streamlit, token'+('' if mutation=='reconnect_missing_id' else ', foreign')
    elif mutation=='reconnect_new_document':epochs[1]['document_event']=epochs[2]['document_event']
    elif mutation=='f5_old_document':epochs[2]['document_event']=epochs[0]['document_event']
    elif mutation=='implicit_navigation':epochs[1]['navigation_timestamp']=91.;epochs[1]['navigation_event']=epochs[0]['document_event']
    elif mutation=='missing_closed':phase['close']['closed_event']=epochs[1]['handshake_event']
    elif mutation=='foreign_closed':events[phase['close']['closed_event']]['params']['requestId']='another-socket'
    elif mutation=='closed_before_command':events[phase['close']['closed_event']]['params']['timestamp']=80.
    elif mutation=='short_observation':phase['auto_observation']['end_timestamp']=phase['auto_observation']['start_timestamp']+4.9
    elif mutation=='fake_observation_clock':phase['auto_observation']['end_timestamp']=10**12
    elif mutation=='wrong_cursor':phase['start']+=1
    elif mutation=='wrong_checkpoint':o['phases'][-1]['checkpoint']=copy.deepcopy(o['phases'][3]['checkpoint'])
    elif mutation=='extra_put':page['http_timeline'].append(copy.deepcopy(page['http_timeline'][0]))
    elif mutation=='hidden_delete':
        h=copy.deepcopy(page['http_timeline'][0]);h['method']='DELETE';page['http_timeline'].append(h)
    elif mutation=='wrong_file_dom':phase['dom_after']['uploaded_files']=[]
    elif mutation=='wrong_counts':o['phases'][-1]['dom_after']['pulses']='2'
    elif mutation=='wrong_golden_cells':o['phases'][1]['dom_after']['table_cells'][2]='999'
    elif mutation=='missing_png':o['screenshots'].pop()
    elif mutation=='wrong_png_sha':o['screenshots'][0]['sha256']='0'*64
    else:
        extra=copy.deepcopy(o['phases'][-1]);extra['name']='expiry-s4';o['phases'].append(extra)
    assert not journey_result(c.j09_checks(observation=o))['ok'],mutation


@pytest.mark.parametrize('plan',['natural','ui-probe'])
@pytest.mark.parametrize('mutation',['wrong_session','failed_finish','missing_run_id','extra_pulse','slider_contradiction','foreign_file_state'])
def test_j09_new_connection_proof_requires_actual_s0_typed_state_and_success(tmp_path,plan,mutation):
    import base64
    from streamlit.proto.ForwardMsg_pb2 import ForwardMsg
    from streamlit.proto.BackMsg_pb2 import BackMsg
    import capture_browser_trace as c
    o=_j09_unit_observation(tmp_path,plan);page=o['page'];phase=o['phases'][4 if plan=='natural' else 5]
    wanted='new_session' if mutation in ('wrong_session','missing_run_id') else 'script_finished' if mutation=='failed_finish' else 'rerun_script'
    index=next(i for i in range(phase['start'],phase['end']) if page['frames'][i]['decoded']['type']==wanted)
    msg=BackMsg() if wanted=='rerun_script' else ForwardMsg();msg.ParseFromString(base64.b64decode(page['frames'][index]['base64']))
    if mutation=='wrong_session':msg.new_session.initialize.session_id='fresh-not-recovered'
    elif mutation=='missing_run_id':msg.new_session.script_run_id=''
    elif mutation=='failed_finish':msg.script_finished=2
    else:
        states=msg.rerun_script.widget_states.widgets
        if mutation=='extra_pulse':state=states.add();state.id='pulse';state.trigger_value=True
        elif mutation=='slider_contradiction':next(v for v in states if v.id=='minimum').double_array_value.data[:]=[100.]
        else:next(v for v in states if v.id=='uploader').file_uploader_state_value.uploaded_file_info[0].file_id='another-file'
    _j06_replace_proto(page,index,msg);_j09_refresh_unit_summaries(o)
    assert not journey_result(c.j09_checks(observation=o))['ok'],mutation


@pytest.mark.parametrize('plan',['natural','ui-probe'])
def test_j09_result_cache_reference_survives_same_document_reconnect(tmp_path,plan):
    import base64
    from streamlit.proto.ForwardMsg_pb2 import ForwardMsg
    import capture_browser_trace as c
    o=_j09_unit_observation(tmp_path,plan);page=o['page'];before=o['phases'][3];after=o['phases'][4 if plan=='natural' else 6]
    first=next(i for i in range(before['start'],before['end']) if page['frames'][i]['decoded'].get('delta',{}).get('element')=='dataframe')
    msg=ForwardMsg();msg.ParseFromString(base64.b64decode(page['frames'][first]['base64']));msg.hash='cached-baseline';msg.metadata.cacheable=True
    _j06_replace_proto(page,first,msg)
    reference=next(i for i in range(after['start'],after['end']) if page['frames'][i]['decoded'].get('delta',{}).get('element')=='dataframe')
    ref=ForwardMsg(ref_hash='cached-baseline');ref.metadata.delta_path[:]=[0,99];_j06_replace_proto(page,reference,ref)
    _j09_refresh_unit_summaries(o)
    result=journey_result(c.j09_checks(observation=o));assert result['ok'],result['failures']
    assert page['frames'][reference]['decoded']['type']=='ref_hash'


@pytest.mark.parametrize('fresh_document',[False,True])
def test_j09_reader_preserves_reconnect_cache_and_clears_it_only_for_f5(fresh_document):
    from streamlit.proto.ForwardMsg_pb2 import ForwardMsg
    import capture_browser_trace as c
    full=ForwardMsg(hash='cached');full.metadata.cacheable=True;full.delta.new_element.markdown.body='cached payload'
    ref=ForwardMsg(ref_hash='cached');ref.metadata.delta_path[:]=[0,4]
    page=_j06_unit_wire([full,ref],connections=[0,1]);page['epochs']=[{'connection':0,'request_id':'socket-0','document_event':10},
        {'connection':1,'request_id':'socket-1','document_event':11 if fresh_document else 10}]
    if fresh_document:
        with pytest.raises(ValueError,match='cache reference'):c._j09_materialize_frames(page)
    else:
        resolved=c._j09_materialize_frames(page)
        # Path-stripped equality: the ref resolution carries the CURRENT
        # metadata's path where the original full carried none. The inner
        # delta dict is copied, not mutated, so later asserts still see it.
        def strip_path(summary):
            copy=dict(summary);delta=dict(summary.get('delta') or {});delta.pop('path',None);copy['delta']=delta;return copy
        assert strip_path(resolved[1]['decoded'])==strip_path(resolved[0]['decoded'])
        assert resolved[0]['decoded']['delta']['path']==[]
        assert resolved[1]['decoded']['delta']['path']==[0,4]


@pytest.mark.parametrize('observation',[None,{},[],{'journey':'j09-sequence'},{'journey':'j06-sequence'}])
def test_j09_missing_observation_is_not_zero_of_zero_success(observation):
    from capture_browser_trace import j09_checks
    result=journey_result(j09_checks(observation=observation));assert not result['ok'] and result['counts']['expected']==20


def _j09_insert_unit_message(o,phase_index,message,*,position='after_finish'):
    import base64
    import hashlib
    import capture_browser_trace as c
    page=o['page'];phase=o['phases'][phase_index];frames=page['frames']
    if position=='observe':cursor=phase['start'];stamp=phase['read_start_timestamp']+2.5
    elif position=='late_heartbeat':cursor=phase['end'];stamp=phase['auto_observation']['end_timestamp']+.1
    else:
        marker=next(i for i in range(phase['start'],phase['end']) if frames[i]['decoded']['type']=='new_session')
        cursor=phase['checkpoint']['finish_frame']+1 if position=='after_finish' else marker;stamp=frames[cursor-1]['timestamp']+.005
    data=message.SerializeToString();encoded=base64.b64encode(data).decode();direction='client->server' if message.DESCRIPTOR.name=='BackMsg' else 'server->client'
    frame={'namespace':page['namespace'],'connection':1,'request_id':page['epochs'][1]['request_id'],'direction':direction,
           'timestamp':stamp,'base64':encoded,'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest(),
           'decoded':c.summarise_back(data) if direction=='client->server' else c.summarise_forward(data)}
    event={'method':'Network.webSocketFrameSent' if direction=='client->server' else 'Network.webSocketFrameReceived',
           'params':{'timestamp':stamp,'requestId':frame['request_id'],'response':{'opcode':2,'payloadData':encoded}}}
    event_index=next((i for i,e in enumerate(page['events']) if e.get('method') in ('Network.webSocketFrameSent','Network.webSocketFrameReceived') and e['params']['timestamp']>stamp),len(page['events']))
    page['events'].insert(event_index,event);frames.insert(cursor,frame)
    for epoch in page['epochs']:
        for field in ('document_event','navigation_event','handshake_event','response_event'):
            if epoch[field] is not None and epoch[field]>=event_index:epoch[field]+=1
    for i,p in enumerate(o['phases']):
        if 'close' in p and p['close']['closed_event']>=event_index:p['close']['closed_event']+=1
        if i<phase_index:continue
        if i>phase_index:p['start']+=1
        p['end']+=1
        if p['checkpoint']['finish_frame']>=cursor:p['checkpoint']['finish_frame']+=1
    _j09_refresh_unit_summaries(o)


@pytest.mark.parametrize('kind',['new_session','running_status','rerun_script','early_finish'])
def test_j09_started_natural_activity_cannot_be_hidden_by_ui_probe_plan(tmp_path,kind):
    from streamlit.proto.ForwardMsg_pb2 import ForwardMsg
    from streamlit.proto.BackMsg_pb2 import BackMsg
    import capture_browser_trace as c
    o=_j09_unit_observation(tmp_path)
    if kind=='rerun_script':msg=BackMsg();msg.rerun_script.widget_states.SetInParent()
    else:
        msg=ForwardMsg()
        if kind=='new_session':msg.new_session.script_run_id='partial-natural';msg.new_session.initialize.session_id='session-unit-a'
        elif kind=='running_status':msg.session_status_changed.script_is_running=True
        else:msg.script_finished=2
    _j09_insert_unit_message(o,4,msg,position='observe')
    result=journey_result(c.j09_checks(observation=o));assert not result['ok']
    assert 'natural activity' in result['failures'][0]['actual']


@pytest.mark.parametrize('plan',['natural','ui-probe'])
def test_j09_exact_five_second_budget_and_late_heartbeat_are_legal(tmp_path,plan):
    from streamlit.proto.ForwardMsg_pb2 import ForwardMsg
    import capture_browser_trace as c
    o=_j09_unit_observation(tmp_path,plan);phase=o['phases'][4]
    phase['auto_observation']['end_timestamp']=phase['auto_observation']['start_timestamp']+5
    _j09_insert_unit_message(o,4,ForwardMsg(heartbeat_ack=True),position='late_heartbeat')
    result=journey_result(c.j09_checks(observation=o));assert result['ok'],result['failures']


@pytest.mark.parametrize('plan,phase_index',[('natural',4),('ui-probe',5),('ui-probe',6)])
@pytest.mark.parametrize('position',['before_run','after_finish'])
def test_j09_recovery_or_probe_run_cannot_hide_outside_business_output(tmp_path,plan,phase_index,position):
    from streamlit.proto.ForwardMsg_pb2 import ForwardMsg
    import capture_browser_trace as c
    o=_j09_unit_observation(tmp_path,plan);msg=ForwardMsg();msg.delta.new_element.markdown.body='OUTSIDE TARGET RUN'
    _j09_insert_unit_message(o,phase_index,msg,position=position)
    result=journey_result(c.j09_checks(observation=o));assert not result['ok']
    assert 'outside the target' in result['failures'][0]['actual']


@pytest.mark.parametrize('plan',['natural','ui-probe'])
def test_j09_f5_must_issue_new_session_not_just_empty_dom(tmp_path,plan):
    import base64
    from streamlit.proto.ForwardMsg_pb2 import ForwardMsg
    import capture_browser_trace as c
    o=_j09_unit_observation(tmp_path,plan);page=o['page'];phase=o['phases'][-1]
    i=next(i for i in range(phase['start'],phase['end']) if page['frames'][i]['decoded']['type']=='new_session')
    msg=ForwardMsg();msg.ParseFromString(base64.b64decode(page['frames'][i]['base64']));msg.new_session.initialize.session_id='session-unit-a'
    _j06_replace_proto(page,i,msg);_j09_refresh_unit_summaries(o)
    assert not journey_result(c.j09_checks(observation=o))['ok']


def test_j09_same_document_reference_cannot_resurrect_an_expired_cache_entry():
    from streamlit.proto.ForwardMsg_pb2 import ForwardMsg
    import capture_browser_trace as c
    initial=ForwardMsg();initial.new_session.config.max_cached_message_age=0
    full=ForwardMsg(hash='old');full.metadata.cacheable=True;full.delta.new_element.markdown.body='old'
    ref=ForwardMsg(ref_hash='old');ref.metadata.delta_path[:]=[0,1]
    page=_j06_unit_wire([initial,full,ForwardMsg(script_finished=0),ref],connections=[0,0,0,1])
    page['epochs']=[{'connection':0,'request_id':'socket-0','document_event':10},{'connection':1,'request_id':'socket-1','document_event':10}]
    with pytest.raises(ValueError,match='cache reference'):c._j09_materialize_frames(page)


@pytest.mark.parametrize('plan',['natural','ui-probe'])
@pytest.mark.parametrize('result',[False,0,{}, {'ok':False,'error':'no live socket'}])
def test_j09_c1_hook_failure_is_rejected_even_with_closed_event_and_reconnect(tmp_path,plan,result):
    import capture_browser_trace as c
    o=_j09_unit_observation(tmp_path,plan)
    o['phases'][4]['close']['evaluation_result']=result
    verdict=journey_result(c.j09_checks(observation=o))
    assert not verdict['ok'] and verdict['counts']['asserted']==0
    assert 'no genuine old-socket close' in verdict['failures'][0]['actual']


@pytest.mark.parametrize('result',[
    'closed',True,None,
    {'id':24,'result':{'result':{'type':'string','value':'closed'}},'error':{'message':'failed'}},
    {'id':24,'result':{'result':{'type':'string','value':'closed'},'exceptionDetails':{'text':'failed'}}},
    {'id':24,'result':{'result':{'type':'string','value':'no socket'}}},
    {'id':24,'result':{'result':{'type':'boolean','value':True}}},
    {'id':True,'result':{'result':{'type':'string','value':'closed'}}},
])
def test_j09_hook_success_shape_does_not_accept_shorthand_or_contradictory_cdp_result(result):
    from capture_browser_trace import _j09_close_success
    assert not _j09_close_success(result)


def test_j09_recorded_hook_success_shape_matches_existing_producer_contract():
    from capture_browser_trace import _j09_close_success
    # Verbatim close_command from observation.json in owned preflight
    # j09-owned-preflight-20261025T052956054; id is a CDP command counter.
    assert _j09_close_success({'id':24,'result':{'result':{'type':'string','value':'closed'}}})


def test_j09_actual_hook_success_keeps_natural_run_without_client_state_legal(tmp_path):
    import capture_browser_trace as c
    o=_j09_unit_observation(tmp_path,'natural',natural_client_state=False)
    assert o['phases'][4]['client_states']==[]
    result=journey_result(c.j09_checks(observation=o))
    assert result['ok'],result['failures']


def _j09_slow_unit_prefix(tmp_path,plan):
    """Capture-in-progress unit model only; no S4 elapsed time or oracle."""
    import capture_browser_trace as c
    o=_j09_unit_observation(tmp_path,plan);page=o['page'];count=len(o['phases'])
    o.update(journey=c.J09_SLOW_CASE,contract=c.J09_SLOW_CONTRACT,base_range={
        'phase_count':count,'frame_end':len(page['frames']),'event_end':len(page['events']),
        'http_end':len(page['http_timeline']),'screenshot_count':len(o['screenshots']),
        'cutoff_timestamp':o['phases'][-1]['observation_end_timestamp']})
    return o


@pytest.mark.parametrize('plan',['natural','ui-probe'])
def test_j09_slow_exports_and_explicit_prefix_do_not_claim_s4_pass(tmp_path,plan):
    import capture_browser_trace as c
    o=_j09_slow_unit_prefix(tmp_path,plan)
    assert c.J09_SLOW_PHASES[plan]==c.J09_PHASES[plan]+c.J09_SLOW_SUFFIX
    assert c.J09_SLOW_TTL_SECONDS==120 and c.J09_SLOW_HOLD_SECONDS==135
    assert c.J09_SLOW_ACTIONS['s4-recovery-read']=={'action':'read-recovery'}
    assert c.J09_SLOW_RECOVERY_ACTIONS==('observe','rerun')
    base=c._j09_slow_base_view(o);assert journey_result(c.j09_checks(observation=base))['ok']
    base['phases'][0]['action']['ok']=False
    assert o['phases'][0]['action']['ok'] is True # independent derived view
    result=journey_result(c.j09_slow_checks(observation=o))
    assert not result['ok'] and result['counts']=={'expected':20,'executed':20,'asserted':1}


@pytest.mark.parametrize('mutation',['phase_count','frame_end','event_end','http_end','screenshot_count','cutoff_timestamp','phase_order'])
def test_j09_slow_prefix_cursor_tampering_is_not_silent_truncation(tmp_path,mutation):
    import capture_browser_trace as c
    o=_j09_slow_unit_prefix(tmp_path,'ui-probe')
    if mutation=='phase_order':o['phases'][2],o['phases'][3]=o['phases'][3],o['phases'][2]
    else:o['base_range'][mutation]-=1
    with pytest.raises(ValueError):c._j09_slow_base_view(o)


def test_j09_slow_prefix_view_preserves_complete_tail_in_original_observation(tmp_path):
    import copy
    import capture_browser_trace as c
    from streamlit.proto.ForwardMsg_pb2 import ForwardMsg
    o=_j09_slow_unit_prefix(tmp_path,'ui-probe');page=o['page'];r=o['base_range']
    tail=_j06_unit_wire([ForwardMsg(heartbeat_ack=True)])
    frame=tail['frames'][0];stamp=r['cutoff_timestamp']+1
    frame.update(namespace=page['namespace'],connection=2,request_id=page['epochs'][2]['request_id'],timestamp=stamp)
    event=tail['events'][0];event['params'].update(timestamp=stamp,requestId=frame['request_id'])
    page['frames'].append(frame);page['events'].append(event);before=copy.deepcopy(o)
    projected=c._j09_slow_base_view(o)
    assert len(projected['page']['frames'])+1==len(page['frames'])
    assert o==before and journey_result(c.j09_checks(observation=projected))['ok']
    assert not journey_result(c.j09_slow_checks(observation=o))['ok']


@pytest.mark.parametrize('observation',[None,{},[],{'oracle_status':'verified','elapsed':135,'passed':True}])
def test_j09_slow_degenerate_input_stays_fail_closed_on_every_check(observation):
    from capture_browser_trace import j09_slow_checks,J09_SLOW_REQUIRED
    result=journey_result(j09_slow_checks(observation=observation))
    assert not result['ok'] and result['counts']['expected']==len(J09_SLOW_REQUIRED)==20
    assert any(f['check']=='recovery_oracle_verified' for f in result['failures'])


def _j09_slow_unit_complete(tmp_path,natural=False):
    """Synthetic clock/protobuf model, NOT real elapsed time or expiry oracle.

    Recovery deliberately retains data/counts in a new session. Common guards
    validate that actual outcome; the unknown oracle must prevent whole PASS.
    """
    import copy,base64,hashlib,runpy
    from datetime import datetime,timezone
    from google.protobuf.json_format import MessageToDict,ParseDict
    from streamlit.proto.ForwardMsg_pb2 import ForwardMsg
    from streamlit.proto.BackMsg_pb2 import BackMsg
    import capture_browser_trace as c
    o=_j09_slow_unit_prefix(tmp_path,'ui-probe');page=o['page'];n=len(o['phases']);cut=o['base_range']['cutoff_timestamp']
    app=HERE/'app.py';app_path=str(app.resolve());command=f'python -m streamlit run {app_path} --server.port 8501 --server.disconnectedSessionTTL 120'
    for i,f in enumerate(page['frames']):
        if f['decoded']['type']=='new_session':
            msg=ForwardMsg();msg.ParseFromString(base64.b64decode(f['base64']));msg.new_session.initialize.environment_info.streamlit_version='1.66.1';msg.new_session.main_script_path=app_path;_j06_replace_proto(page,i,msg)
    _j09_refresh_unit_summaries(o)
    evidence=[]
    for kind,data,extension in [('process',json.dumps([{'pid':777,'port':8501,'command_line':command}]).encode(),'.json'),
                                ('config',b'[server]\ndisconnectedSessionTTL = 120\n','.toml'),
                                ('effective-config',b'disconnectedSessionTTL = 120\n','.txt'),('app-source',app.read_bytes(),'.py')]:
        file='slow-'+kind+extension;(tmp_path/file).write_bytes(data);evidence.append({'kind':kind,'file':file,'sha256':hashlib.sha256(data).hexdigest()})
    o['ttl_configuration']={'runtime':'python','effective_seconds':120,'process_id':777,'process_command_line':command,'evidence':evidence}
    driver=runpy.run_path(str(HERE.parent/'browser/numeric_capture.py'));store=driver['_ArrowFiles'](tmp_path)
    store.by_digest={hashlib.sha256(p.read_bytes()).hexdigest():p.name for p in tmp_path.glob('arrow-*.bin')}
    templates={key:copy.deepcopy(page['frames'][o['phases'][i]['start']:o['phases'][i]['end']]) for key,i in [('upload',1),('pulse',2)]}
    doms={key:copy.deepcopy(o['phases'][i]['dom_after']) for key,i in [('upload',1),('pulse',2)]}
    s0='session-unit-a';aged=s0+'-refreshed';fresh='expired-new-session';doc=page['epochs'][2]['document_event'];ws='ws://127.0.0.1:8501/_stcore/stream'
    png=(tmp_path/'j09-refresh.png').read_bytes();previous=copy.deepcopy(o['phases'][-1]['dom_after']);checkpoint=copy.deepcopy(o['phases'][-1]['checkpoint'])
    def record(method,params,before,after):return {'target_id':page['target_id'],'method':method,'params':params,'cdp_before':before,'cdp_after':after,'started_monotonic':before+500,'finished_monotonic':after+500,'response':{'id':40,'result':{}}}
    hold_clock=cut+50;clear_clock=hold_clock+150
    block=record('Network.emulateNetworkConditionsByRule',{'matchedNetworkConditions':[{'urlPattern':ws,'offline':True,'latency':0,'downloadThroughput':-1,'uploadThroughput':-1}]},hold_clock+1,hold_clock+1.01)
    block['response']['result']={'ruleIds':['actual-unit-rule']}
    clear=record('Network.emulateNetworkConditionsByRule',{'matchedNetworkConditions':[]},clear_clock+1,clear_clock+1.01);clear['response']['result']={'ruleIds':[]}
    o['commands']=[block,clear]
    o['hold']={'block_command':0,'unblock_command':1,'samples':[{'cdp_timestamp':x,'driver_monotonic':x+500,'utc':datetime.fromtimestamp(1700000000+x,timezone.utc).isoformat()} for x in (hold_clock+2,hold_clock+70,hold_clock+137)]}
    o['recovery']={'requested_session_id':aged,'observed_session_id':fresh,'recovery_action':'observe' if natural else 'rerun','oracle_status':'unverified'}
    for index,name in enumerate(c.J09_SLOW_SUFFIX):
        clock=cut+10+index*20 if index<3 else clear_clock+(0 if index==3 else 20)
        start=len(page['frames']);before=copy.deepcopy(previous);action=dict(c.J09_SLOW_ACTIONS[name],ok=True);extra={};template=None
        if index<2:template=templates['upload' if index==0 else 'pulse'];counts=(2+index,index);conn=2
        elif index==2:
            conn=2;closed_index=len(page['events']);closed=hold_clock+1.05
            page['events'].append({'method':'Network.webSocketClosed','params':{'requestId':page['epochs'][2]['request_id'],'timestamp':closed}})
            o['hold']['close']={'request_id':page['epochs'][2]['request_id'],'command_timestamp':hold_clock+1.02,'completed_timestamp':hold_clock+1.06,'evaluation_result':{'id':41,'result':{'result':{'type':'string','value':'closed'}}},'closed_event':closed_index}
            page['events'] += [{'method':'Network.webSocketCreated','params':{'requestId':'blocked-retry','url':ws}},
                              {'method':'Network.webSocketFrameError','params':{'requestId':'blocked-retry','timestamp':hold_clock+5,'errorMessage':'net::ERR_INTERNET_DISCONNECTED'}},
                              {'method':'Network.webSocketClosed','params':{'requestId':'blocked-retry','timestamp':hold_clock+5.01}}]
        else:
            conn=3
            if index==3:
                hs=len(page['events']);page['events'].append({'method':'Network.webSocketWillSendHandshakeRequest','params':{'requestId':'slow-restored','timestamp':clock+1.2,'request':{'headers':{'Sec-WebSocket-Protocol':'streamlit, token, '+aged}}}})
                response=len(page['events']);page['events'].append({'method':'Network.webSocketHandshakeResponseReceived','params':{'requestId':'slow-restored','timestamp':clock+1.3,'response':{'status':101,'headers':{'Sec-WebSocket-Protocol':'streamlit'}}}})
                page['epochs'].append({'id':'e3','connection':3,'request_id':'slow-restored','document_event':doc,'navigation_event':None,'navigation_timestamp':None,'handshake_event':hs,'response_event':response})
            if (index==3 and natural) or (index==4 and not natural):template=templates['pulse'];counts=(7,1)
            if index==4 and not natural:
                for kind,delta in [('rawKeyDown',.05),('keyUp',.1)]:o['commands'].append(record('Input.dispatchKeyEvent',{'type':kind,'key':'r','code':'KeyR'},clock+1+delta,clock+1+delta+.01))
        after=copy.deepcopy(previous)
        if template:
            for offset,f in enumerate(template):
                if index>=3 and natural and f['direction']=='client->server':continue
                cls=BackMsg if f['direction']=='client->server' else ForwardMsg;msg=cls();msg.ParseFromString(base64.b64decode(f['base64']))
                obj=json.loads(json.dumps(MessageToDict(msg)).replace(s0,aged).replace('file-sales_basic.csv','s4-file'))
                msg=ParseDict(obj,cls())
                if f['direction']=='client->server' and msg.WhichOneof('type')=='rerun_script' and index>=3:
                    widgets=msg.rerun_script.widget_states.widgets
                    for item in list(widgets):
                        if item.WhichOneof('value')=='trigger_value':widgets.remove(item)
                if f['direction']=='server->client':
                    if msg.WhichOneof('type')=='new_session':msg.new_session.initialize.session_id=aged if index<2 else fresh;msg.new_session.script_run_id='slow-'+name
                    if msg.WhichOneof('type')=='delta' and msg.delta.WhichOneof('type')=='new_element' and msg.delta.new_element.WhichOneof('type')=='markdown':
                        body=msg.delta.new_element.markdown.body
                        if body.startswith('Script runs:'):msg.delta.new_element.markdown.body=f'Script runs: {counts[0]}'
                        if body.startswith('Pulses:'):msg.delta.new_element.markdown.body=f'Pulses: {counts[1]}'
                data=msg.SerializeToString();encoded=base64.b64encode(data).decode();stamp=clock+2+offset*.01;request=page['epochs'][conn]['request_id']
                page['frames'].append({'namespace':page['namespace'],'connection':conn,'request_id':request,'timestamp':stamp,'direction':f['direction'],'base64':encoded,'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest(),'decoded':c.summarise_back(data) if f['direction']=='client->server' else c.summarise_forward(data)})
                page['events'].append({'method':'Network.webSocketFrameSent' if f['direction']=='client->server' else 'Network.webSocketFrameReceived','params':{'requestId':request,'timestamp':stamp,'response':{'opcode':2,'payloadData':encoded}}})
            after=copy.deepcopy(doms['upload' if index==0 else 'pulse']);after.update(script_runs=str(counts[0]),pulses=str(counts[1]))
            checkpoint={'epoch':'e2' if index<2 else 'e3','script_run_id':'slow-'+name,'finish_frame':len(page['frames'])-1}
        if index==0:
            action.update(file=str((HERE.parent/'fixtures/csv/sales_basic.csv').resolve()),file_bytes=737,file_sha256=c.J01_FILE_FINGERPRINTS['sales_basic.csv'][1])
            f=next(f for f in page['frames'][start:] if f['decoded']['type']=='file_urls_response');url='http://127.0.0.1:8501'+f['decoded']['file_urls_response']['file_urls'][0]['upload_url'];stamp=f['timestamp']+.001
            h={'request_id':'put-s4','method':'PUT','url':url,'timestamp':stamp,'response_timestamp':stamp+.001,'status':204,'request_headers':{'Content-Type':'multipart/form-data; boundary=unit'}};page['http_timeline'].append(h)
            page['events'] += [{'method':'Network.requestWillBeSent','params':{'requestId':h['request_id'],'timestamp':stamp,'request':{'method':'PUT','url':url}}},
                              {'method':'Network.responseReceived','params':{'requestId':h['request_id'],'timestamp':stamp+.001,'response':{'status':204}}}]
        phase=driver['_phase'](name,action,page['frames'],start,len(page['frames']),before,after,store)
        read_end=hold_clock+138 if index==2 else clock+8
        phase.update(epoch='e2' if index<3 else 'e3',action_timestamp=clock+1,read_start_timestamp=clock,read_end_timestamp=read_end,observation_end_timestamp=read_end+2,checkpoint=copy.deepcopy(checkpoint));o['phases'].append(phase)
        file='slow-'+name+'.png';(tmp_path/file).write_bytes(png);o['screenshots'].append({'phase':name,'namespace':page['namespace'],'epoch':phase['epoch'],'file':file,'sha256':hashlib.sha256(png).hexdigest(),'timestamp':read_end+1,'step_ids':list(c.J09_SLOW_PNG_ROLES[name]),'role':'preparation'})
        previous=after
    return o


@pytest.mark.parametrize('natural',[False,True])
def test_j09_slow_synthetic_model_cannot_satisfy_the_reviewed_recovery_oracle(tmp_path,natural):
    import capture_browser_trace as c
    o=_j09_slow_unit_complete(tmp_path,natural);result=journey_result(c.j09_slow_checks(observation=o))
    assert result['counts']=={'expected':20,'executed':20,'asserted':19},result['failures']
    assert [f['check'] for f in result['failures']]==['recovery_oracle_verified']


def _j09_slow_unit_menu(o):
    """Actual CDP menu locator and mouse input shape; synthetic timing only."""
    import copy
    clock=o['phases'][-1]['action_timestamp'];template=o['commands'][2]
    commands=[]
    for offset,method,params in [(.05,'Runtime.evaluate',{'expression':"document.querySelector('[data-testid=stMainMenuItem-rerun]')"}),
                                  (.10,'Input.dispatchMouseEvent',{'type':'mousePressed','x':123,'y':234,'button':'left'}),
                                  (.15,'Input.dispatchMouseEvent',{'type':'mouseReleased','x':123,'y':234,'button':'left'})]:
        cmd=copy.deepcopy(template);at=clock+offset
        cmd.update(method=method,params=params,cdp_before=at,cdp_after=at+.01,started_monotonic=at+500,finished_monotonic=at+500+.01)
        cmd['response']={'id':50+len(commands),'result':{'result':{'type':'object','value':{'x':123,'y':234}}} if method=='Runtime.evaluate' else {}}
        commands.append(cmd)
    o['commands'][2:]=commands


def test_j09_slow_actual_menu_dispatch_is_accepted_without_keyr_or_extra_wait(tmp_path):
    import capture_browser_trace as c
    o=_j09_slow_unit_complete(tmp_path);_j09_slow_unit_menu(o)
    assert journey_result(c.j09_slow_checks(observation=o))['counts']['asserted']==19


def test_j09_slow_actual_click_visible_scroll_then_rectangle_contract(tmp_path):
    import copy
    import capture_browser_trace as c
    o=_j09_slow_unit_complete(tmp_path);_j09_slow_unit_menu(o)
    scroll=copy.deepcopy(o['commands'][2]);scroll['params']['expression']="(()=>{const e=document.querySelector('[data-testid=stMainMenuItem-rerun]');e.scrollIntoView();return true;})()"
    scroll['response']['result']['result']={'type':'boolean','value':True}
    for key in ('cdp_before','cdp_after','started_monotonic','finished_monotonic'):scroll[key]-=.02
    o['commands'].insert(2,scroll)
    assert journey_result(c.j09_slow_checks(observation=o))['counts']['asserted']==19


@pytest.mark.parametrize('late_at',['before_press','between_press_release'])
def test_j09_slow_late_natural_run_cannot_be_credited_to_menu_rerun(tmp_path,late_at):
    import capture_browser_trace as c
    o=_j09_slow_unit_complete(tmp_path);_j09_slow_unit_menu(o)
    state=next(f['timestamp'] for f in o['page']['frames'][o['phases'][-1]['start']:] if f['decoded']['type']=='rerun_script')
    # Keep metadata saying Rerun and retain all valid IPC/DOM. Only actual
    # command dispatch proves this run was already active before the click.
    for cmd,at in zip(o['commands'][2:],[state-.1,state+.01 if late_at=='before_press' else state-.02,state+.05]):
        cmd.update(cdp_before=at,cdp_after=at+.005,started_monotonic=at+500,finished_monotonic=at+500+.005)
    result=journey_result(c.j09_slow_checks(observation=o))
    assert result['counts']['asserted']<19
    assert any('natural activity preceded actual Rerun dispatch' in f['actual'] for f in result['failures'])


def test_j09_slow_late_natural_completion_needs_no_invented_ui_input(tmp_path):
    import capture_browser_trace as c
    o=_j09_slow_unit_complete(tmp_path);o['commands']=o['commands'][:2];o['recovery']['recovery_action']='observe'
    assert journey_result(c.j09_slow_checks(observation=o))['counts']['asserted']==19


@pytest.mark.parametrize('mutation',[
    'base_cursor','prefix_action','ttl','pid','artifact_sha','config_bytes','argv','app_source',
    'global_network','foreign_target','foreign_url','clear_error','close_false','close_socket',
    'short_cdp','short_driver','fake_utc','early_clear','hold101','missing_retry_error',
    'old_requested_id','extra_delete','extra_document','missing_png','png_sha',
    'missing_input','input_failed','input_wrong_point','natural_forced_rerun',
])
def test_j09_slow_known_guard_mutations_fail_independently_of_unknown_oracle(tmp_path,mutation):
    import copy,hashlib
    import capture_browser_trace as c
    o=_j09_slow_unit_complete(tmp_path,natural=mutation=='natural_forced_rerun');page=o['page']
    _j09_slow_unit_menu(o) if mutation in ('input_failed','input_wrong_point') else None
    def artifact(kind,data):
        r=next(r for r in o['ttl_configuration']['evidence'] if r['kind']==kind)
        (tmp_path/r['file']).write_bytes(data);r['sha256']=hashlib.sha256(data).hexdigest()
    if mutation=='base_cursor':o['base_range']['frame_end']-=1
    elif mutation=='prefix_action':o['phases'][1]['action']['ok']=False
    elif mutation=='ttl':o['ttl_configuration']['effective_seconds']=119
    elif mutation=='pid':o['ttl_configuration']['process_id']=778
    elif mutation=='artifact_sha':o['ttl_configuration']['evidence'][0]['sha256']='0'*64
    elif mutation=='config_bytes':artifact('config',b'[server]\ndisconnectedSessionTTL = 10\n')
    elif mutation=='argv':o['ttl_configuration']['process_command_line']=o['ttl_configuration']['process_command_line'].replace('TTL 120','TTL 10')
    elif mutation=='app_source':artifact('app-source',b'# unrelated application\n')
    elif mutation=='global_network':o['commands'][0]['method']='Network.emulateNetworkConditions'
    elif mutation=='foreign_target':o['commands'][0]['target_id']='peer-target'
    elif mutation=='foreign_url':o['commands'][0]['params']['matchedNetworkConditions'][0]['urlPattern']='ws://127.0.0.1:9999/_stcore/stream'
    elif mutation=='clear_error':o['commands'][1]['response']={'id':40,'error':{'message':'failed'}}
    elif mutation=='close_false':o['hold']['close']['evaluation_result']=False
    elif mutation=='close_socket':o['hold']['close']['request_id']='different-socket'
    elif mutation=='short_cdp':o['hold']['samples'][-1]['cdp_timestamp']-=1
    elif mutation=='short_driver':o['hold']['samples'][-1]['driver_monotonic']-=1
    elif mutation=='fake_utc':o['hold']['samples'][-1]['utc']=o['hold']['samples'][0]['utc']
    elif mutation=='early_clear':o['commands'][1]['cdp_before']=o['hold']['samples'][0]['cdp_timestamp']+120
    elif mutation=='hold101':
        e=copy.deepcopy(page['events'][page['epochs'][3]['response_event']]);e['params']['timestamp']=o['hold']['samples'][1]['cdp_timestamp'];page['events'].append(e)
    elif mutation=='missing_retry_error':
        next(e for e in page['events'] if e['method']=='Network.webSocketFrameError')['params']['errorMessage']='unrelated failure'
    elif mutation=='old_requested_id':
        page['events'][page['epochs'][3]['handshake_event']]['params']['request']['headers']['Sec-WebSocket-Protocol']='streamlit, token, session-unit-a'
    elif mutation=='extra_delete':page['http_timeline'].append(dict(page['http_timeline'][-1],method='DELETE'))
    elif mutation=='extra_document':page['events'].append({'method':'Network.requestWillBeSent','params':{'type':'Document','requestId':'reload','timestamp':o['phases'][-1]['action_timestamp']}})
    elif mutation=='missing_png':(tmp_path/o['screenshots'][-1]['file']).unlink()
    elif mutation=='png_sha':o['screenshots'][-1]['sha256']='0'*64
    elif mutation=='missing_input':o['commands']=o['commands'][:2]
    elif mutation=='input_failed':o['commands'][-1]['response']={'id':52,'error':{'message':'failed'}}
    elif mutation=='input_wrong_point':o['commands'][-1]['params']['x']+=1
    elif mutation=='natural_forced_rerun':o['recovery']['recovery_action']='rerun'
    result=journey_result(c.j09_slow_checks(observation=o))
    assert not result['ok'] and result['counts']['asserted']<19,(mutation,result)


def test_j09_slow_reviewed_oracle_and_misleading_initial101_summary_are_not_truth(tmp_path):
    import capture_browser_trace as c
    o=_j09_slow_unit_complete(tmp_path);o['recovery']['oracle_status']='verified'
    o['a_responses_while_rule_active']=[{'status':101,'timestamp':0}]
    result=journey_result(c.j09_slow_checks(observation=o))
    assert result['counts']['asserted']==19
    assert [f['check'] for f in result['failures']]==['recovery_oracle_verified']


def _j09_oracle_clone(runtime):
    """Minimal projection carrying the reviewed identity and semantics."""
    import copy
    import capture_browser_trace as c
    golden=c.J09_SLOW_ORACLE_REVIEW[runtime];semantics=c.J09_SLOW_ORACLE_SEMANTICS
    samples=[{'utc':golden['hold_first_utc']}]*(golden['hold_samples']-1)+[{'utc':golden['hold_last_utc']}]
    return dict(
        phases=[{'name':'s4-pulse','dom_after':copy.deepcopy(semantics['aged'])},
                {'name':'s4-recovery-read','dom_after':copy.deepcopy(semantics['recovered']),
                 'ipc':copy.deepcopy(semantics['recovered_ipc'])}],
        recovery={'recovery_action':semantics['recovery_action'],
                  'requested_session_id':golden['aged_session_id'],
                  'observed_session_id':golden['recovered_session_id']},
        hold={'samples':samples},
        screenshots=[{'sha256':value} for value in golden['screenshots']],
        ttl_configuration={'evidence':[{'sha256':value} for value in golden['ttl_evidence']]})


@pytest.mark.parametrize('runtime',['python','native'])
def test_j09_slow_recovery_oracle_accepts_the_reviewed_identities(runtime):
    import capture_browser_trace as c
    c._j09_slow_recovery_oracle(_j09_oracle_clone(runtime))


@pytest.mark.parametrize('mutation',[
    'aged_runs','aged_files','recovered_runs','recovered_files','recovered_table','recovered_alert',
    'recovered_ipc','recovery_action','requested_id','observed_id','hold_first_utc','hold_last_utc',
    'hold_samples','screenshot_sha','ttl_sha',
])
def test_j09_slow_recovery_oracle_rejects_golden_mutations(mutation):
    import capture_browser_trace as c
    o=_j09_oracle_clone('python')
    aged,recovered=o['phases']
    if mutation=='aged_runs':aged['dom_after']['script_runs']='9'
    elif mutation=='aged_files':aged['dom_after']['uploaded_files']=[]
    elif mutation=='recovered_runs':recovered['dom_after']['script_runs']='2'
    elif mutation=='recovered_files':recovered['dom_after']['uploaded_files']=[]
    elif mutation=='recovered_table':recovered['dom_after']['table_present']=True
    elif mutation=='recovered_alert':recovered['dom_after']['alerts']=[]
    elif mutation=='recovered_ipc':recovered['ipc']={'table':'kept','chart':None}
    elif mutation=='recovery_action':o['recovery']['recovery_action']='observe'
    elif mutation=='requested_id':o['recovery']['requested_session_id']='forged-aged-id'
    elif mutation=='observed_id':o['recovery']['observed_session_id']='forged-new-id'
    elif mutation=='hold_first_utc':o['hold']['samples'][0]['utc']='2026-10-25T05:00:00Z'
    elif mutation=='hold_last_utc':o['hold']['samples'][-1]['utc']='2026-10-25T06:00:00Z'
    elif mutation=='hold_samples':o['hold']['samples']=o['hold']['samples'][:-1]
    elif mutation=='screenshot_sha':o['screenshots'][0]['sha256']='0'*64
    elif mutation=='ttl_sha':o['ttl_configuration']['evidence'][0]['sha256']='0'*64
    with pytest.raises(ValueError):c._j09_slow_recovery_oracle(o)


def _j09_slow_hidden_input(o,kind,phase_index):
    import copy
    scratch=copy.deepcopy(o)
    scratch['commands']=scratch['commands'][:2]+[copy.deepcopy(scratch['commands'][0])]
    _j09_slow_unit_menu(scratch)
    commands=scratch['commands'][2:]
    clock=o['phases'][phase_index]['action_timestamp']+.4
    if kind=='key':
        commands=commands[1:]
        for cmd,event in zip(commands,('rawKeyDown','keyUp')):
            cmd.update(method='Input.dispatchKeyEvent',params={'type':event,'key':'r','code':'KeyR'})
    for i,cmd in enumerate(commands):
        at=clock+i*.02
        cmd.update(cdp_before=at,cdp_after=at+.005,started_monotonic=at+500,finished_monotonic=at+500+.005)
    o['commands'].extend(commands)


@pytest.mark.parametrize('kind',['key','menu'])
@pytest.mark.parametrize('phase_index',[-3,-2,-1])
def test_j09_slow_c1_hidden_rerun_anywhere_after_close_is_not_natural(tmp_path,kind,phase_index):
    import capture_browser_trace as c
    o=_j09_slow_unit_complete(tmp_path,natural=True);_j09_slow_hidden_input(o,kind,phase_index)
    # Hold action precedes close by .05s; move this mutation after actual close.
    if phase_index==-3:
        for cmd in o['commands'][2:]:
            for field in ('cdp_before','cdp_after','started_monotonic','finished_monotonic'):cmd[field]+=1
    result=journey_result(c.j09_slow_checks(observation=o))
    assert result['counts']['asserted']<19,result


@pytest.mark.parametrize('kind',['key','menu'])
@pytest.mark.parametrize('phase_index',[-3,-2])
def test_j09_slow_c1_valid_final_input_cannot_cover_an_earlier_extra_rerun(tmp_path,kind,phase_index):
    import capture_browser_trace as c
    o=_j09_slow_unit_complete(tmp_path);old=len(o['commands']);_j09_slow_hidden_input(o,kind,phase_index)
    if phase_index==-3:
        for cmd in o['commands'][old:]:
            for field in ('cdp_before','cdp_after','started_monotonic','finished_monotonic'):cmd[field]+=1
    result=journey_result(c.j09_slow_checks(observation=o))
    assert result['counts']['asserted']<19
    assert any('outside its single authorized recovery window' in f['actual'] for f in result['failures'])


def test_j09_slow_c1_opening_main_menu_without_rerun_does_not_invalidate_natural(tmp_path):
    import capture_browser_trace as c
    o=_j09_slow_unit_complete(tmp_path,natural=True);_j09_slow_hidden_input(o,'menu',-1)
    o['commands'][2]['params']['expression']="document.querySelector('[data-testid=stMainMenu]')?.querySelector('button')"
    result=journey_result(c.j09_slow_checks(observation=o))
    assert result['counts']['asserted']==19,result['failures']


@pytest.mark.parametrize('inside',[True,False])
@pytest.mark.parametrize('kind',['pending_run','pending_state','heartbeat'])
def test_j09_slow_c1_natural_completion_cannot_hide_pending_business_tail(tmp_path,inside,kind):
    from streamlit.proto.ForwardMsg_pb2 import ForwardMsg
    from streamlit.proto.BackMsg_pb2 import BackMsg
    import capture_browser_trace as c
    o=_j09_slow_unit_complete(tmp_path,natural=True);page=o['page'];phase=o['phases'][-1]
    if kind=='pending_state':msg=BackMsg();msg.rerun_script.page_script_hash='pending'
    elif kind=='pending_run':msg=ForwardMsg();msg.new_session.initialize.session_id='expired-new-session';msg.new_session.script_run_id='uncompleted-tail'
    else:msg=ForwardMsg(heartbeat_ack=True)
    wire=_j06_unit_wire([msg]);frame,event=wire['frames'][0],wire['events'][0]
    if kind=='pending_state':
        frame.update(direction='client->server',decoded=c.summarise_back(msg.SerializeToString()))
        event['method']='Network.webSocketFrameSent'
    stamp=phase['action_timestamp']+.5 if inside else phase['observation_end_timestamp']+.1
    frame.update(namespace=page['namespace'],connection=3,request_id=page['epochs'][3]['request_id'],timestamp=stamp)
    event['params'].update(requestId=frame['request_id'],timestamp=stamp)
    page['frames'].append(frame);page['events'].append(event)
    if inside:
        phase.update(end=len(page['frames']),start_timestamp=stamp,end_timestamp=stamp)
        _j09_refresh_unit_summaries(o)
    result=journey_result(c.j09_slow_checks(observation=o))
    assert (result['counts']['asserted']==19) is (kind=='heartbeat'),result['failures']
