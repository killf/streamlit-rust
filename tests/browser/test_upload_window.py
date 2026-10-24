"""The upload window has to end in the run that carried the new file.

Replacing a file sends the state twice: first with the file cleared, then
with the new file.  The clear run finishes before the run that answers the
new file, so a window that stops at the first successful completion ends
before the result and hides it.  These tests drive the driver's own window
reader against the frames of such a replacement: the window it returns has
to reach the run of the new file, and it is not returned at all while that
run has not finished.
"""

from __future__ import annotations

import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "reference"))

import numeric_capture  # noqa: E402

NAMESPACE = "tab"
WIDGET = "$$ID-upload"
FILE_NAME = "sales.csv"
FILE_ID = "file-1"


def _frame(direction, decoded, index):
    return {
        "direction": direction,
        "connection": 1,
        "request_id": "REQ",
        "timestamp": float(index),
        "namespace": NAMESPACE,
        "decoded": decoded,
    }


def _uploader_state(file_id=None):
    infos = [] if file_id is None else [{"name": FILE_NAME, "fileId": file_id, "size": 10}]
    return {
        "id": WIDGET,
        "value_field": "file_uploader_state_value",
        "value_full": {"uploadedFileInfo": infos},
    }


def _replacement_frames():
    """The frames of a replacement: the clear run, then the run of the file."""
    return [
        _frame("client->server", {"type": "file_urls_request", "file_urls_request": {
            "request_id": "REQ-1", "file_names": [FILE_NAME], "session_id": "S"}}, 0),
        _frame("server->client", {"type": "file_urls_response", "file_urls_response": {
            "response_id": "REQ-1",
            "file_urls": [{"file_id": FILE_ID, "upload_url": "http://host/upload",
                           "delete_url": "http://host/delete"}],
            "error_msg": ""}}, 1),
        _frame("server->client", {"type": "delta", "delta": {
            "type": "new_element", "element": "file_uploader", "id": WIDGET,
            "label": "Upload sales CSV"}}, 2),
        # the client clears the uploader first
        _frame("client->server", {"type": "rerun_script", "rerun_script": {
            "widget_states": [_uploader_state()]}}, 3),
        _frame("server->client", {"type": "new_session", "new_session": {
            "script_run_id": "run-clear", "session_id": "S"}}, 4),
        _frame("server->client", {"type": "script_finished", "script_finished": {
            "status": 0, "status_name": "FINISHED_SUCCESSFULLY"}}, 5),
        # and then names the new file
        _frame("client->server", {"type": "rerun_script", "rerun_script": {
            "widget_states": [_uploader_state(FILE_ID)]}}, 6),
        _frame("server->client", {"type": "new_session", "new_session": {
            "script_run_id": "run-target", "session_id": "S"}}, 7),
        _frame("server->client", {"type": "script_finished", "script_finished": {
            "status": 0, "status_name": "FINISHED_SUCCESSFULLY"}}, 8),
    ]


def _old_window(frames):
    """The rule the driver used: the first completion after the first state."""
    for index, frame in enumerate(frames):
        if (frame.get("decoded") or {}).get("type") != "rerun_script":
            continue
        for later in range(index + 1, len(frames)):
            decoded = frames[later].get("decoded") or {}
            if decoded.get("type") != "script_finished":
                continue
            if (decoded.get("script_finished") or {}).get("status") == 0:
                return later
    return None


def test_the_old_rule_stops_at_the_clear_run_and_the_new_one_at_the_target_run():
    frames = _replacement_frames()
    assert _old_window(frames) == 5
    window = numeric_capture._upload_window(frames, 0, FILE_NAME, NAMESPACE)
    assert window is not None
    assert window["target"] == 6
    assert window["run"] == 7
    assert window["finish"] == 8
    assert window["script_run_id"] == "run-target"
    assert window["start"] == 0
    assert window["end"] == 9
    assert 5 in range(window["start"], window["end"])


def test_no_window_while_the_run_of_the_new_file_has_not_finished():
    frames = [frame for index, frame in enumerate(_replacement_frames()) if index != 8]
    assert _old_window(frames) == 5
    assert numeric_capture._upload_window(frames, 0, FILE_NAME, NAMESPACE) is None


def test_a_failed_run_of_the_new_file_gives_no_window():
    frames = _replacement_frames()
    frames[8]["decoded"]["script_finished"]["status"] = 2
    assert numeric_capture._upload_window(frames, 0, FILE_NAME, NAMESPACE) is None


def test_a_completion_on_another_connection_gives_no_window():
    frames = _replacement_frames()
    frames[8]["connection"] = 2
    assert numeric_capture._upload_window(frames, 0, FILE_NAME, NAMESPACE) is None


def test_a_frame_of_another_tab_gives_no_window():
    frames = _replacement_frames()
    frames[6]["namespace"] = "other-tab"
    assert numeric_capture._upload_window(frames, 0, FILE_NAME, NAMESPACE) is None


def test_the_window_belongs_to_the_file_that_was_asked_for():
    frames = _replacement_frames()
    assert numeric_capture._upload_window(frames, 0, "other.csv", NAMESPACE) is None


def test_the_driver_follows_the_phase_ids_of_the_shared_contract():
    """One list of phases: the shared one, never a second one in the driver."""
    for kind, phases in numeric_capture.SEQUENCE_PHASES.items():
        plan = numeric_capture._sequence_plan(kind)
        assert [step[0] for step in plan] == list(phases), kind
        pictures = [step[3] for step in plan]
        assert len(pictures) == len(set(pictures)), kind
    parse = list(numeric_capture.SEQUENCE_PHASES["j07-sequence"])
    assert parse.count("good-after-soft") == 1 and parse.count("good-after-utf8") == 1
    assert "good-after-soft" != "good-after-utf8"


def test_a_whole_journey_never_passes_without_the_shared_criterion():
    """An empty observation cannot pass, with or without the shared criterion."""
    verdict = numeric_capture._judge_sequence("j07-sequence", {"phases": []})
    assert verdict["failures"]
    assert verdict["counts"]["asserted"] == 0
