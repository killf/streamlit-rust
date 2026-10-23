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

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from capture_browser_trace import verify_click_windows  # noqa: E402


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
