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
    """Replay published immutable events with adjacent artifacts in a test sandbox."""
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
    if kind == checks.J01_CASE:
        phase_names, inputs, png_roles, contract = checks.J01_PHASES, checks.J01_INPUTS, checks.J01_PNG_ROLES, checks.J01_CONTRACT
    elif kind == checks.J03_CASE:
        phase_names, inputs, png_roles, contract = checks.J03_PHASES, checks.J03_INPUTS, checks.J03_PNG_ROLES, checks.J03_CONTRACT
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
        if kind == checks.J01_CASE and name in ("group-region", "group-channel", "prepare-category"):
            group = checks.J01_ACTIONS[name]["option"]
        elif kind == checks.J03_CASE and name == "group-region":
            group = checks.J03_ACTIONS[name]["option"]
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
        if kind == checks.J03_CASE and name == "slider-100":
            from refcore import aggregate,parse_csv
            rows=[{"group_key":v.group_key,"row_count":v.row_count,"total_amount":float(v.total_amount),"avg_amount":float(v.avg_amount)}
                  for v in aggregate(parse_csv((fixture_root/filename).read_bytes()).rows,group,100,True)]
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
            next(v for v in states if v["id"]=="minimum")["value_full"]={"data":[100.]}
            after.update(table_cells=[str(r[c]) for r in rows for c in ("group_key","row_count","total_amount","avg_amount")],
                         chart_bars=len(rows),chart_marks="|".join(f"M{i*10},{1000-r['total_amount']}h8v{r['total_amount']}Z" for i,r in enumerate(rows)),slider_value="100")
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
        elif kind == checks.J03_CASE and not upload:
            action = dict(checks.J03_ACTIONS[name],ok=True)
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
    return {"contract":contract,"journey":kind,"namespace":source,"url":"http://127.0.0.1:8501/","ipc_dir":str(tmp_path),
            "frames":frames,"http_timeline":timeline,"phases":phases,"screenshots":records,"uploads":uploads}


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
