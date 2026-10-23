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

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from capture_browser_trace import Capture, parse_counter_texts, verify_click_windows  # noqa: E402


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
