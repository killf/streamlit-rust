from __future__ import annotations

import copy
import base64
import hashlib
import json
import pathlib
import sys
from datetime import datetime, timezone

import pytest

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "browser"))

from forms_contract import CANONICAL_CASE_IDS, verify_forms_text_input_contract  # noqa: E402


def _mutation_observation():
    # Positive and negative controls share the one formal selected capture.
    # Missing/incomplete selection is a gate failure, never a legacy fallback.
    selected = HERE / "reference-browser" / "forms-final" / "trace-forms.json"
    return json.loads(selected.read_text(encoding="utf-8"))


@pytest.mark.parametrize("mutation,code", [
    ("delete_phases", "required_phases"),
    ("null_clocks", "phase_clock"),
    ("wrong_namespace", "frame_namespace"),
    ("failed_completion", "completion_status"),
])
def test_review_mutations_are_rejected_by_their_specific_guard(mutation, code):
    observed = _mutation_observation()
    baseline = verify_forms_text_input_contract(copy.deepcopy(observed), case_ids=CANONICAL_CASE_IDS)
    assert code not in {failure["code"] for failure in baseline}, baseline
    if mutation == "delete_phases":
        next(case for case in observed["cases"] if case["case_id"] == "form-none-vs-empty")["phases"] = []
    elif mutation == "null_clocks":
        for case in observed["cases"]:
            for phase in case["phases"]:
                phase["clock"] = {key: None for key in phase["clock"]}
                phase["screenshot"]["at_utc"] = "1900-01-01T00:00:00Z"
    elif mutation == "wrong_namespace":
        for frame in observed["frames"]:
            frame["namespace"] = "OTHER-NAMESPACE"
        for case in observed["cases"]:
            for phase in case["phases"]:
                for frame in phase["frames"]:
                    frame["namespace"] = "OTHER-NAMESPACE"
    else:
        from streamlit.proto.ForwardMsg_pb2 import ForwardMsg
        changed = {}
        for frame in observed["frames"]:
            if frame["direction"] != "server->client":
                continue
            message = ForwardMsg()
            message.ParseFromString(base64.b64decode(frame["base64"]))
            if message.WhichOneof("type") == "script_finished":
                message.script_finished = 1
                payload = message.SerializeToString()
                frame.update(base64=base64.b64encode(payload).decode(), bytes=len(payload), sha256=hashlib.sha256(payload).hexdigest())
                changed[frame["index"]] = frame
        assert changed
        for case in observed["cases"]:
            for phase in case["phases"]:
                phase["frames"] = [copy.deepcopy(changed.get(frame["index"], frame)) for frame in phase["frames"]]
    failures = verify_forms_text_input_contract(observed, case_ids=CANONICAL_CASE_IDS)
    assert code in {failure["code"] for failure in failures}


@pytest.mark.parametrize("window", [None, {}, {"frame_count": 0, "window_empty": True}])
def test_missing_or_invalid_submit_window_fails_closed(window):
    observed = _mutation_observation()
    phase = next(p for p in observed["cases"][0]["phases"] if p["phase_id"].endswith(":submit"))
    phase["frames"] = []
    phase["action_window"] = window
    codes = {failure["code"] for failure in verify_forms_text_input_contract(observed)}
    assert "empty_action_window" in codes


@pytest.mark.parametrize("bad", [None, float("nan"), float("inf"), "0", False, -1])
def test_clock_values_are_finite_numbers(bad):
    from forms_contract import _clock_time
    clock = {"driver_utc": "2026-10-24T00:00:00+00:00", "driver_monotonic_s": 100,
             "chrome_wall_ms": 1792800000000, "chrome_performance_now_ms": 0, "chrome_time_origin_ms": 1792800000000}
    assert _clock_time(clock) is not None
    for key in ("driver_monotonic_s", "chrome_wall_ms", "chrome_performance_now_ms", "chrome_time_origin_ms"):
        assert _clock_time({**clock, key: bad}) is None


def test_png_clock_rejects_wrong_epoch_and_outside_window():
    # Synthetic clock records are predicate unit inputs, never browser evidence.
    from forms_contract import _clock_time, _png_clock_matches
    clock = {"driver_utc": "2026-10-24T00:00:00+00:00", "driver_monotonic_s": 100,
             "chrome_wall_ms": 1792800000000, "chrome_performance_now_ms": 0, "chrome_time_origin_ms": 1792800000000}
    at = _clock_time(clock)
    png = {"clock": clock, "at_utc": clock["driver_utc"], "window_empty": False}
    assert _png_clock_matches(png, at + 0.1, at - 0.1, False)
    assert not _png_clock_matches({**png, "at_utc": "1900-01-01T00:00:00Z"}, at, at - 1, False)
    assert not _png_clock_matches(png, at + 3, at - 1, False)
    assert not _png_clock_matches(png, at, at + 1, False)
    assert not _png_clock_matches(png, at, at - 1, True)
    assert not _png_clock_matches({**png, "clock": None}, at, at - 1, False)


def _insert_unreferenced_quiet_rerun(observed):
    case = next(case for case in observed["cases"] if case["case_id"] == "form-default-submit")
    load, quiet = case["phases"][:2]
    start = datetime.fromisoformat(load["clock"]["driver_utc"]).timestamp()
    end = datetime.fromisoformat(quiet["clock"]["driver_utc"]).timestamp()
    assert end > start
    frame = copy.deepcopy(next(frame for frame in load["frames"] if frame["decoded"]["type"] == "rerun_script"))
    wall = (start + end) / 2
    frame.update(index=len(observed["frames"]), timestamp=wall - observed["chrome_clock"]["offset_s"],
                 wall_time_utc=datetime.fromtimestamp(wall, timezone.utc).isoformat(timespec="milliseconds"))
    observed["frames"].append(frame)
    return quiet


def test_authoritative_global_quiet_rerun_cannot_hide_outside_phase_sidecache():
    observed = _mutation_observation()
    baseline = verify_forms_text_input_contract(copy.deepcopy(observed))
    assert "phase_window_coverage" not in {failure["code"] for failure in baseline}
    quiet = _insert_unreferenced_quiet_rerun(observed)
    assert quiet["frames"] == []
    failures = verify_forms_text_input_contract(observed)
    assert "phase_window_coverage" in {failure["code"] for failure in failures}
    assert any(failure["phase_id"] == quiet["phase_id"] and failure["code"] == "unexpected_rerun" for failure in failures)


@pytest.mark.parametrize("missing,code", [("clock", "phase_window_coverage"), ("window", "phase_window"), ("connection", "case_connection")])
def test_quiet_global_derivation_requires_clock_window_and_connection(missing, code):
    observed = _mutation_observation()
    case = next(case for case in observed["cases"] if case["case_id"] == "form-default-submit")
    quiet = case["phases"][1]
    if missing == "clock":
        quiet.pop("clock")
    elif missing == "window":
        quiet.pop("action_window")
    else:
        case.pop("frame_range")
    failures = verify_forms_text_input_contract(observed)
    assert code in {failure["code"] for failure in failures}


def _mutate_quiet_clock_or_lifetime(observed, mutation):
    case = next(case for case in observed["cases"] if case["case_id"] == "form-default-submit")
    load, quiet = case["phases"][:2]
    start = datetime.fromisoformat(load["clock"]["driver_utc"]).timestamp()
    end = datetime.fromisoformat(quiet["clock"]["driver_utc"]).timestamp()
    if mutation in ("zero", "negative", "short"):
        elapsed = {"zero": 0, "negative": -1, "short": 0.001}[mutation]
        clock = copy.deepcopy(load["clock"])
        clock["driver_monotonic_s"] += elapsed
        clock["chrome_performance_now_ms"] += elapsed * 1000
        clock["chrome_wall_ms"] += elapsed * 1000
        clock["driver_utc"] = datetime.fromtimestamp(start + elapsed, timezone.utc).isoformat(timespec="milliseconds")
        quiet["clock"] = clock
        quiet["at_utc"] = clock["driver_utc"]
        quiet["screenshot"]["clock"] = copy.deepcopy(clock)
        quiet["screenshot"]["at_utc"] = clock["driver_utc"]
    elif mutation == "origin_jump":
        quiet["clock"]["chrome_time_origin_ms"] += 1000
        quiet["clock"]["chrome_performance_now_ms"] -= 1000
    elif mutation == "driver_backwards":
        quiet["clock"]["driver_monotonic_s"] = load["clock"]["driver_monotonic_s"] - 1
    elif mutation == "early_close":
        handshake = next(item for item in observed["websocket_handshakes"] if item["request_id"] == load["frames"][0]["request_id"])
        wall = (start + end) / 2
        handshake.update(closed=True, closed_timestamp=wall - observed["chrome_clock"]["offset_s"],
                         closed_wall_time_utc=datetime.fromtimestamp(wall, timezone.utc).isoformat(timespec="milliseconds"))


@pytest.mark.parametrize("mutation,code", [("zero", "quiet_duration"), ("negative", "quiet_duration"), ("short", "quiet_duration"),
                                         ("origin_jump", "clock_continuity"), ("driver_backwards", "clock_continuity"), ("early_close", "connection_lifetime")])
def test_quiet_duration_clock_continuity_and_known_close_are_enforced(mutation, code):
    observed = _mutation_observation()
    # Isolate the clock/lifetime guard from historical PNG records that predate
    # screenshot.clock. Full PNG-bound acceptance uses the selected final trace.
    baseline = verify_forms_text_input_contract(copy.deepcopy(observed), require_png=False)
    assert code not in {failure["code"] for failure in baseline}
    _mutate_quiet_clock_or_lifetime(observed, mutation)
    failures = verify_forms_text_input_contract(observed, require_png=False)
    assert code in {failure["code"] for failure in failures}


def test_the_pinned_forms_reference_satisfies_the_strict_contract() -> None:
    # Only the final source-matched bundle is a positive acceptance input.
    # Older traces stay as historical provenance and negative-test inputs.
    path = HERE / "reference-browser" / "forms-final" / "trace-forms.json"
    observed = json.loads(path.read_text(encoding="utf-8"))
    assert observed["fixture"]["sha256"] == "d177df7d7ef72414faffce8984d1b88547f401beff560eb103ae0bd945eda352"
    assert observed["fixture"]["bytes"] == 21696
    failures = verify_forms_text_input_contract(
        observed,
        namespace="forms-text-input-v1",
        case_ids=CANONICAL_CASE_IDS,
        docs_label="1.66.0",
        runtime_version="1.66.1",
        require_png=True,
    )
    assert failures == []


def test_empty_windows_fail_closed_for_submit_and_quiet_counterfeit() -> None:
    path = HERE / "reference-browser" / "forms-final" / "trace-forms.json"
    observed = json.loads(path.read_text(encoding="utf-8"))
    cases = {case["case_id"]: case for case in observed["cases"]}

    submit = next(phase for phase in cases["form-default-submit"]["phases"] if phase["phase_id"].endswith(":submit"))
    empty_window = {
        "first_frame_index": None,
        "last_frame_index": None,
        "frame_count": 0,
        "window_empty": True,
        "chrome_monotonic_first": None,
        "chrome_monotonic_last": None,
        "wall_time_utc_first": None,
        "wall_time_utc_last": None,
    }
    submit["frames"] = []
    submit["action_window"] = empty_window
    submit["screenshot"]["frame_first"] = None
    submit["screenshot"]["frame_last"] = None

    quiet = next(phase for phase in cases["form-default-submit"]["phases"] if phase["phase_id"].endswith(":type"))
    counterfeit = copy.deepcopy(quiet)
    counterfeit["dom_after"] = copy.deepcopy(counterfeit["dom_before"])
    counterfeit["dom_after"]["texts"] = ["Script runs: 2", *counterfeit["dom_after"]["texts"][1:]]
    cases["form-default-submit"]["phases"].append(counterfeit)

    failures = verify_forms_text_input_contract(
        observed,
        case_ids=("form-default-submit",),
        require_png=True,
    )
    codes = {failure["code"] for failure in failures}
    assert "empty_action_window" in codes
    assert "quiet_dom" in codes
