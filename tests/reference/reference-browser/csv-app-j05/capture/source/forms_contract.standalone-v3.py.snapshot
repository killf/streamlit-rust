"""The sole strict contract for the forms/text-input browser observations.

The collector records evidence but never decides success.  This module owns
the fail-closed predicate used by both the Python reference and Rust captures.
It re-decodes every raw protobuf frame with the pinned official definitions;
it never trusts a derived summary by itself.
"""

from __future__ import annotations

import base64
import hashlib
import math
import pathlib
from datetime import datetime
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[2]
NAMESPACE = "forms-text-input-v1"
DOCS_LABEL = "1.66.0"
RUNTIME_VERSION = "1.66.1"
CONTRACT_REVISION = "forms-text-input-monotonic-window-v3"
CORE_CASE_IDS = (
    "form-default-submit",
    "form-text-enter-blur",
    "form-none-vs-empty",
    "form-error-duplicate-key",
    "form-error-nested-form",
)
EXTENDED_CASE_IDS = (
    "form-clear-on-submit-false",
    "form-clear-on-submit-true",
    "form-enter-to-submit-off",
    "form-first-submit-disabled",
    "form-two-submit-buttons",
    "form-two-forms-external-button",
    "form-text-types",
    "form-text-live-validate",
    "form-text-required-disabled",
    "form-max-chars-cjk",
    "form-j05-continuous",
)
LAYOUT_CASE_IDS = ("form-inside-container", "form-inside-column", "container-inside-form", "columns-inside-form", "form-inside-expander")
CALLBACK_CASE_IDS = ("form-submit-callback-args", "form-disabled-text-input")
TEXT_FIELD_CASE_IDS = ("form-text-password", "form-text-remaining-fields")
EXTRA_CASE_IDS = LAYOUT_CASE_IDS + CALLBACK_CASE_IDS + TEXT_FIELD_CASE_IDS
CANONICAL_CASE_IDS = CORE_CASE_IDS + EXTENDED_CASE_IDS + EXTRA_CASE_IDS

# Required observations are independent of the supplied observation. Removing a
# phase must never turn an incomplete capture into a passing one.
REQUIRED_PHASES = dict(zip(CORE_CASE_IDS + EXTENDED_CASE_IDS, (
    ("load", "type", "toggle", "blur", "submit"),
    ("load", "type", "enter", "blur"),
    ("load", "untouched", "typed-none"),
    ("load", "error"), ("load", "error"),
    ("load", "type", "submit-1", "submit-2"),
    ("load", "type", "submit-1", "submit-2"),
    ("load", "type", "enter", "submit"),
    ("load", "type", "enter", "submit"),
    ("load", "type", "save", "save-and-continue"),
    ("load", "type-left", "type-right", "outside"),
    ("load", "observe", "email"),
    ("load", "type-digits", "type-invalid"),
    ("load", "observe", "required"),
    ("load", "type", "enter"),
    ("load", "type", "submit", "pulse-1", "pulse-2", "pulse-3"),
), strict=True))
REQUIRED_PHASES.update({case: ("load", "type", "submit") for case in LAYOUT_CASE_IDS + CALLBACK_CASE_IDS})
REQUIRED_PHASES.update({"form-text-password": ("load", "enter"), "form-text-remaining-fields": ("load", "observe", "narrow")})

# User actions that must not contact the server. This is deliberately an
# explicit set, not a phase-name heuristic: a live ``type-digits`` phase does
# contact the server, while an invalid live edit and staged form edits do not.
QUIET_PHASE_IDS = {
    *(f"{case}:type" for case in LAYOUT_CASE_IDS + CALLBACK_CASE_IDS),
    "form-text-remaining-fields:observe",
    "form-none-vs-empty:untouched",
    "form-error-duplicate-key:error",
    "form-error-nested-form:error",
    "form-default-submit:type",
    "form-default-submit:toggle",
    "form-default-submit:blur",
    "form-text-enter-blur:type",
    "form-clear-on-submit-false:type",
    "form-clear-on-submit-true:type",
    "form-enter-to-submit-off:type",
    "form-enter-to-submit-off:enter",
    "form-first-submit-disabled:type",
    "form-first-submit-disabled:enter",
    "form-two-submit-buttons:type",
    "form-two-forms-external-button:type-left",
    "form-two-forms-external-button:type-right",
    "form-text-types:observe",
    "form-text-live-validate:type-invalid",
    "form-text-required-disabled:observe",
    "form-max-chars-cjk:type",
    "form-j05-continuous:type",
}

# Observation policy, in seconds, for the existing capture actions. Editing
# phases retain their collector's explicit 1.5/2/2.5/3 second settle waits;
# observation-only phases require a full second of continuous observation.
# These are acceptance intervals, not claims about upstream timing guarantees.
QUIET_MIN_SECONDS = {phase: 1.5 for phase in QUIET_PHASE_IDS}
QUIET_MIN_SECONDS.update({phase: 1.0 for phase in QUIET_PHASE_IDS if phase.endswith((":observe", ":untouched", ":error"))})
QUIET_MIN_SECONDS.update({f"{case}:type": 2.0 for case in LAYOUT_CASE_IDS + CALLBACK_CASE_IDS + ("form-j05-continuous", "form-max-chars-cjk")})
QUIET_MIN_SECONDS.update({"form-text-live-validate:type-invalid": 2.5, "form-enter-to-submit-off:enter": 3.0, "form-first-submit-disabled:enter": 3.0})


def _number(value: Any) -> bool:
    return type(value) in (int, float) and math.isfinite(value) and value >= 0


def _utc(value: Any) -> float | None:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed.timestamp() if parsed.utcoffset() is not None else None
    except (ValueError, TypeError, AttributeError, OverflowError, OSError):
        return None


def _clock_time(clock: Any) -> float | None:
    if not isinstance(clock, dict):
        return None
    wall = _utc(clock.get("driver_utc"))
    keys = ("driver_monotonic_s", "chrome_wall_ms", "chrome_performance_now_ms", "chrome_time_origin_ms")
    if wall is None or any(not _number(clock.get(key)) for key in keys):
        return None
    chrome = clock["chrome_wall_ms"] / 1000
    if abs(wall - chrome) > 2 or abs(chrome - (clock["chrome_time_origin_ms"] + clock["chrome_performance_now_ms"]) / 1000) > 2:
        return None
    return wall


def _png_clock_matches(png: dict, phase_time: float | None, last_time: float | None, empty: bool) -> bool:
    png_time = _clock_time(png.get("clock"))
    return (png_time is not None and phase_time is not None and _utc(png.get("at_utc")) == png_time
            and -0.05 <= phase_time - png_time <= 2
            and (last_time is None or png_time >= last_time - 0.05)
            and png.get("window_empty") is empty)


def _clock_progress(before: Any, after: Any) -> tuple[float, float] | None:
    if _clock_time(before) is None or _clock_time(after) is None:
        return None
    if before["chrome_time_origin_ms"] != after["chrome_time_origin_ms"]:
        return None
    driver = after["driver_monotonic_s"] - before["driver_monotonic_s"]
    browser = (after["chrome_performance_now_ms"] - before["chrome_performance_now_ms"]) / 1000
    wall = _utc(after["driver_utc"]) - _utc(before["driver_utc"])
    if driver <= 0 or browser <= 0 or abs(driver - browser) > 0.1 or abs(driver - wall) > 0.1:
        return None
    return driver, browser


def _problem(case: str, phase: str, code: str, detail: str) -> dict[str, str]:
    return {"case_id": case, "phase_id": phase, "code": code, "detail": detail}


def _png_problem(case: str, phase: str, detail: str) -> dict[str, str]:
    return _problem(case, phase, "invalid_png", detail)


def _official_forward(payload: bytes) -> dict[str, Any]:
    from google.protobuf.json_format import MessageToDict
    from streamlit.proto.ForwardMsg_pb2 import ForwardMsg

    message = ForwardMsg()
    message.ParseFromString(payload)
    full = MessageToDict(message, preserving_proto_field_name=True)
    full["type"] = message.WhichOneof("type")
    if full["type"] == "script_finished":
        full["script_finished_status"] = message.script_finished
    return full


def _official_back(payload: bytes) -> dict[str, Any]:
    from google.protobuf.json_format import MessageToDict
    from streamlit.proto.BackMsg_pb2 import BackMsg

    message = BackMsg()
    message.ParseFromString(payload)
    full = MessageToDict(message, preserving_proto_field_name=True)
    full["type"] = message.WhichOneof("type")
    return full


def _form_blocks_from_forward(full: dict[str, Any]) -> list[dict[str, Any]]:
    delta = full.get("delta") or {}
    block = delta.get("add_block")
    if not isinstance(block, dict) or "form" not in block:
        return []
    form = dict(block["form"])
    form.setdefault("clear_on_submit", False)
    return [form]


def _validate_frame(frame: dict[str, Any], case: str, phase: str) -> tuple[list[dict[str, str]], dict[str, Any] | None]:
    try:
        payload = base64.b64decode(frame["base64"], validate=True)
    except Exception as exc:
        return [_problem(case, phase, "invalid_raw", f"base64 decode failed: {exc}")], None
    if len(payload) != frame.get("bytes"):
        return [_problem(case, phase, "invalid_raw", "bytes length differs from payload")], None
    digest = hashlib.sha256(payload).hexdigest()
    if digest != frame.get("sha256"):
        return [_problem(case, phase, "invalid_raw", "sha256 differs from payload")], None
    direction = frame.get("direction")
    if direction not in ("server->client", "client->server"):
        return [_problem(case, phase, "direction", "unknown frame direction")], None
    try:
        full = _official_forward(payload) if direction == "server->client" else _official_back(payload)
    except Exception as exc:
        return [_problem(case, phase, "official_decode", f"{type(exc).__name__}: {exc}")], None
    if full.get("type") != (frame.get("decoded") or {}).get("type"):
        return [_problem(case, phase, "official_decode", "decoded message type differs from official protobuf")], None
    if direction == "server->client":
        derived = _form_blocks_from_forward(full)
        if derived and frame.get("form_blocks") != derived:
            return [_problem(case, phase, "form_sidecache", "form_blocks differs from official Block decode")], None
        if not derived and "form_blocks" in frame:
            return [_problem(case, phase, "form_sidecache", "form_blocks is present for a non-form Block")], None
    if frame.get("request_id") is None or frame.get("connection") is None:
        return [_problem(case, phase, "missing_connection", "frame lacks request_id or connection ordinal")], None
    return [], full


def _frame_by_index(frames: list[dict[str, Any]], index: int) -> dict[str, Any] | None:
    return next((frame for frame in frames if frame.get("index") == index), None)


def _run_binding(frames: list[dict[str, Any]]) -> list[dict[str, str]]:
    problems: list[dict[str, str]] = []
    seen_runs: set[str] = set()
    for index, frame in enumerate(frames):
        full = frame.get("_official_full") or {}
        if full.get("type") != "new_session":
            continue
        run_id = full.get("new_session", {}).get("script_run_id")
        if not run_id:
            problems.append({"case_id": "*", "phase_id": "*", "code": "missing_run_id", "detail": f"frame {index}"})
            continue
        if run_id in seen_runs:
            problems.append({"case_id": "*", "phase_id": "*", "code": "duplicate_run_id", "detail": run_id})
        seen_runs.add(run_id)
    return problems


def _marker(dom: dict[str, Any], prefix: str) -> str | None:
    for text in dom.get("texts") or []:
        if str(text).startswith(prefix):
            return str(text)[len(prefix) :].strip()
    return None


def _client_states(phase: dict[str, Any]) -> list[dict[str, Any]]:
    states: list[dict[str, Any]] = []
    for frame in phase.get("frames") or []:
        full = frame.get("_official_full") or {}
        if full.get("type") == "rerun_script":
            states.extend((full.get("rerun_script") or {}).get("widget_states", {}).get("widgets", []))
    return states


def _j05_failures(case: dict[str, Any]) -> list[dict[str, str]]:
    case_id = "form-j05-continuous"
    phases = {str(phase.get("phase_id")).split(":", 1)[-1]: phase for phase in case.get("phases") or []}
    failures: list[dict[str, str]] = []
    expected = {
        "load": (1, 0, ""),
        "type": (1, 0, ""),
        "submit": (2, 0, "hello"),
        "pulse-1": (3, 1, "hello"),
        "pulse-2": (4, 2, "hello"),
        "pulse-3": (5, 3, "hello"),
    }
    note_id = apply_id = pulse_id = None
    for frame in phases.get("load", {}).get("frames") or []:
        full = frame.get("_official_full") or {}
        element = ((full.get("delta") or {}).get("new_element") or {})
        if "text_input" in element and element["text_input"].get("label") == "Note":
            note_id = element["text_input"]["id"]
        button = element.get("button")
        if button and button.get("is_form_submitter"):
            apply_id = button["id"]
        elif button and button.get("label") == "Pulse":
            pulse_id = button["id"]
    if not all((note_id, apply_id, pulse_id)):
        failures.append(_problem(case_id, "load", "j05_widgets", "Note, form submit, and Pulse IDs were not all observed"))
        return failures

    for name, (runs, pulses, applied) in expected.items():
        phase = phases.get(name)
        if phase is None:
            failures.append(_problem(case_id, name, "missing_phase", "J05 phase was not captured"))
            continue
        dom = phase.get("dom_after") or {}
        actual = (_marker(dom, "Script runs:"), _marker(dom, "Pulses:"), _marker(dom, "Applied note:"))
        wanted = (str(runs), str(pulses), applied)
        if actual != wanted:
            failures.append(_problem(case_id, name, "j05_dom", f"markers {actual} != {wanted}"))
        values = [value for value in (phase.get("dom_after") or {}).get("text_inputs") or [] if value.get("label") == "Note"]
        expected_note = "" if name == "load" else "hello"
        if not values or values[0].get("value") != expected_note:
            failures.append(_problem(case_id, name, "j05_dom", "the Note field did not retain its stage value"))

        if name == "type":
            if _client_states(phase):
                failures.append(_problem(case_id, name, "j05_wire", "typing before submit contacted the server"))
            continue
        if name == "load":
            continue
        states = _client_states(phase)
        by_id = {str(state.get("id")): state for state in states}
        if by_id.get(note_id, {}).get("string_value") != "hello":
            failures.append(_problem(case_id, name, "j05_wire", "the batch did not carry note string_value hello"))
        trigger_id = apply_id if name == "submit" else pulse_id
        if by_id.get(trigger_id, {}).get("trigger_value") is not True:
            failures.append(_problem(case_id, name, "j05_wire", f"the expected {name} trigger is absent"))
        wrong = [state.get("id") for state in states if state.get("id") not in {note_id, trigger_id}]
        if wrong:
            failures.append(_problem(case_id, name, "j05_wire", f"unexpected widget states: {wrong}"))
    return failures


def verify_forms_text_input_contract(
    obs: dict[str, Any],
    *,
    namespace: str = NAMESPACE,
    case_ids: tuple[str, ...] = CORE_CASE_IDS,
    docs_label: str = DOCS_LABEL,
    runtime_version: str = RUNTIME_VERSION,
    require_png: bool = True,
) -> list[dict[str, str]]:
    """Return failures only; an empty list is the sole PASS representation."""
    failures: list[dict[str, str]] = []
    if namespace != NAMESPACE:
        failures.append({"case_id": "*", "phase_id": "*", "code": "namespace", "detail": namespace})
    if docs_label != DOCS_LABEL or runtime_version != RUNTIME_VERSION:
        failures.append({"case_id": "*", "phase_id": "*", "code": "version", "detail": f"{docs_label}/{runtime_version}"})
    if not isinstance(obs.get("chrome_clock"), dict) or not (obs.get("chrome_clock") or {}).get("samples"):
        failures.append({"case_id": "*", "phase_id": "*", "code": "missing_clock", "detail": "Chrome monotonic/wall-clock calibration is missing"})
    runtime = obs.get("reference_runtime") or {}
    if runtime.get("streamlit") != runtime_version:
        failures.append({"case_id": "*", "phase_id": "*", "code": "runtime_version", "detail": "reference runtime differs"})
    for key in ("python", "protobuf", "pyarrow"):
        if not runtime.get(key):
            failures.append({"case_id": "*", "phase_id": "*", "code": "runtime_version", "detail": f"missing {key}"})
    frontend = obs.get("frontend") or {}
    for key in ("index_bytes", "index_sha256", "main_bundle", "main_bundle_bytes", "main_bundle_sha256"):
        if key not in frontend or frontend.get(key) in (None, "", 0):
            failures.append({"case_id": "*", "phase_id": "*", "code": "frontend_provenance", "detail": f"missing {key}"})
    host_config = obs.get("host_config")
    if not isinstance(host_config, dict) or "error" in host_config:
        failures.append({"case_id": "*", "phase_id": "*", "code": "host_config", "detail": "host-config observation is missing or failed"})
    for key in ("fixture", "frontend", "websocket_handshakes", "cases", "frames"):
        if obs.get(key) in (None, [], {}):
            failures.append({"case_id": "*", "phase_id": "*", "code": "missing_field", "detail": key})

    fixture = obs.get("fixture") or {}
    app_path = ROOT / str(fixture.get("app", ""))
    if not app_path.is_file() or not app_path.resolve().is_relative_to(ROOT.resolve()):
        failures.append({"case_id": "*", "phase_id": "*", "code": "fixture", "detail": "fixture path is missing or outside the worktree"})
    else:
        data = app_path.read_bytes()
        if len(data) != fixture.get("bytes") or hashlib.sha256(data).hexdigest() != fixture.get("sha256"):
            failures.append({"case_id": "*", "phase_id": "*", "code": "fixture", "detail": "fixture digest differs"})

    frames = obs.get("frames") or []
    handshake_ids = {str(item.get("request_id")) for item in obs.get("websocket_handshakes") or []}
    closed_times: dict[str, tuple[float, float]] = {}
    offset = (obs.get("chrome_clock") or {}).get("offset_s")
    for handshake in obs.get("websocket_handshakes") or []:
        if handshake.get("closed") is True or "closed_timestamp" in handshake or "closed_wall_time_utc" in handshake:
            stamp = handshake.get("closed_timestamp")
            wall = _utc(handshake.get("closed_wall_time_utc"))
            if not _number(stamp) or wall is None or not _number(offset) or abs(wall - stamp - offset) > 0.01:
                failures.append(_problem("*", "*", "connection_lifetime", "an observed close lacks a coherent native clock"))
            else:
                closed_times[str(handshake.get("request_id"))] = (stamp, wall)
    official_frames: list[dict[str, Any]] = []
    connections: dict[str, int] = {}
    for index, frame in enumerate(frames):
        frame.pop("_official_full", None)
        if frame.get("namespace") != namespace:
            failures.append(_problem("*", "*", "frame_namespace", f"frame {index}"))
        if frame.get("index") != index:
            failures.append({"case_id": "*", "phase_id": "*", "code": "frame_index", "detail": str(index)})
        problems, full = _validate_frame(frame, "*", "*")
        failures.extend(problems)
        if not frame.get("wall_time_utc"):
            failures.append({"case_id": "*", "phase_id": "*", "code": "missing_clock", "detail": f"frame {index} lacks wall_time_utc"})
        if str(frame.get("request_id")) not in handshake_ids:
            failures.append({"case_id": "*", "phase_id": "*", "code": "unknown_connection", "detail": str(frame.get("request_id"))})
        request_id, connection = frame.get("request_id"), frame.get("connection")
        handshake = next((item for item in obs.get("websocket_handshakes") or [] if item.get("request_id") == request_id), {})
        if (not isinstance(request_id, str) or not request_id or type(connection) is not int or connection < 0
                or handshake.get("response_status") != 101
                or (request_id in connections and connections[request_id] != connection)
                or any(other != request_id and ordinal == connection for other, ordinal in connections.items())):
            failures.append(_problem("*", "*", "connection", f"frame {index} has an invalid connection binding"))
        else:
            connections[request_id] = connection
        if full is not None:
            if full.get("type") == "script_finished" and full.get("script_finished_status") != 0:
                failures.append(_problem("*", "*", "completion_status", f"frame {index} did not finish successfully"))
            frame["_official_full"] = full
            official_frames.append(frame)
        offset = (obs.get("chrome_clock") or {}).get("offset_s")
        wall = _utc(frame.get("wall_time_utc"))
        if not _number(offset) or not _number(frame.get("timestamp")) or wall is None or abs(wall - frame["timestamp"] - offset) > 0.01:
            failures.append(_problem("*", "*", "frame_clock", f"frame {index} is not on the calibrated Chrome clock"))
        close = closed_times.get(str(frame.get("request_id")))
        if close and _number(frame.get("timestamp")) and frame["timestamp"] > close[0]:
            failures.append(_problem("*", "*", "connection_lifetime", f"frame {index} occurs after this connection's recorded close"))
    failures.extend(_run_binding(official_frames))

    cases = {str(case.get("case_id")): case for case in obs.get("cases") or []}
    canonical_cases: dict[str, dict[str, Any]] = {}
    for case_id in case_ids:
        case = cases.get(case_id)
        if case is None:
            failures.append({"case_id": case_id, "phase_id": "*", "code": "missing_case", "detail": "not captured"})
            continue
        case_range = case.get("frame_range") or {}
        case_first, case_last = case_range.get("first_frame_index"), case_range.get("last_frame_index")
        range_valid = (type(case_first) is int and type(case_last) is int and 0 <= case_first <= case_last < len(frames)
                       and case_range.get("frame_count") == case_last - case_first + 1)
        case_frames = frames[case_first:case_last + 1] if range_valid else []
        case_connections = {(frame.get("request_id"), frame.get("connection")) for frame in case_frames}
        if not range_valid or len(case_connections) != 1:
            failures.append(_problem(case_id, "*", "case_connection", "case lacks a complete global range on one connection"))
        case_connection = next(iter(case_connections)) if len(case_connections) == 1 else None
        case_phases = case.get("phases") or []
        canonical_cases[case_id] = {**case, "phases": []}
        required = REQUIRED_PHASES.get(case_id)
        if required is None:
            failures.append(_problem(case_id, "*", "unknown_case", "no phase contract is defined"))
        else:
            actual_ids = [phase.get("phase_id") for phase in case_phases]
            wanted_ids = [f"{case_id}:{name}" for name in required]
            if actual_ids != wanted_ids:
                failures.append(_problem(case_id, "*", "required_phases", f"expected ordered phases {wanted_ids}"))
        for phase_index, phase in enumerate(case_phases):
            phase_id = str(phase.get("phase_id"))
            if not phase_id.startswith(f"{case_id}:") or phase.get("case_id") != case_id:
                failures.append(_problem(case_id, phase_id, "phase_case_id", "phase_id uses another case namespace"))
            window = phase.get("action_window")
            if not isinstance(window, dict):
                failures.append(_problem(case_id, phase_id, "phase_window", "missing or invalid action_window"))
                window = {}
            supplied = phase.get("frames") or []
            phase_time = _clock_time(phase.get("clock"))
            previous_time = _clock_time(case_phases[phase_index - 1].get("clock")) if phase_index else None
            previous_clock = case_phases[phase_index - 1].get("clock") if phase_index else None
            progress = _clock_progress(previous_clock, phase.get("clock")) if phase_index else None
            if phase_index and progress is None:
                failures.append(_problem(case_id, phase_id, "clock_continuity", "driver/browser clocks must advance coherently on the same page origin"))
            close = closed_times.get(str(case_connection[0])) if case_connection else None
            if close and phase_time is not None and phase_time > close[1]:
                failures.append(_problem(case_id, phase_id, "connection_lifetime", "phase endpoint exceeds this connection's recorded close"))
            # The phase is an observation interval, not a trusted list of
            # events. Derive ALL matching raw frames globally, including frames
            # whose indices were omitted from the declared case/phase range.
            start_time = previous_time if phase_index else (_utc(case_frames[0].get("wall_time_utc")) if case_frames else None)
            expected = []
            if phase_time is None or start_time is None or case_connection is None:
                failures.append(_problem(case_id, phase_id, "phase_window_coverage", "missing finite clock/connection evidence for the global observation interval"))
            else:
                for raw in frames:
                    wall = _utc(raw.get("wall_time_utc"))
                    after_start = wall is not None and (wall > start_time if phase_index else wall >= start_time)
                    if (raw.get("namespace") == namespace and (raw.get("request_id"), raw.get("connection")) == case_connection
                            and after_start and wall <= phase_time):
                        expected.append(raw)
                if [frame.get("index") for frame in supplied] != [frame.get("index") for frame in expected]:
                    failures.append(_problem(case_id, phase_id, "phase_window_coverage", "phase references do not exactly cover the authoritative global time/connection window"))
            canonical_cases[case_id]["phases"].append({**phase, "frames": expected})
            first, last = window.get("first_frame_index"), window.get("last_frame_index")
            if window.get("frame_count") != len(expected):
                failures.append(_problem(case_id, phase_id, "phase_window", "frame_count differs from embedded frames"))
            if "window_empty" not in window or window.get("window_empty") != bool(not expected):
                failures.append(_problem(case_id, phase_id, "phase_window", "window_empty differs from the frame window"))
            clock_keys = ("chrome_monotonic_first", "chrome_monotonic_last", "wall_time_utc_first", "wall_time_utc_last")
            if expected:
                if any(window.get(key) is None for key in clock_keys):
                    failures.append(_problem(case_id, phase_id, "phase_clock", "non-empty window lacks Chrome clock bounds"))
                if expected[0].get("timestamp") != window.get("chrome_monotonic_first") or expected[-1].get("timestamp") != window.get("chrome_monotonic_last"):
                    failures.append(_problem(case_id, phase_id, "phase_clock", "Chrome monotonic bounds do not match frames"))
            elif any(window.get(key) is not None for key in clock_keys):
                failures.append(_problem(case_id, phase_id, "phase_clock", "empty window must have null clock bounds"))
            if expected:
                if first != expected[0].get("index") or last != expected[-1].get("index"):
                    failures.append(_problem(case_id, phase_id, "phase_window", "global frame bounds differ"))
                for embedded in supplied:
                    actual = _frame_by_index(frames, int(embedded.get("index", -1)))
                    if actual is None or {k: v for k, v in actual.items() if k != "_official_full"} != {k: v for k, v in embedded.items() if k != "_official_full"}:
                        failures.append(_problem(case_id, phase_id, "phase_window", "embedded frame does not match global trace"))
            elif first is not None or last is not None:
                failures.append(_problem(case_id, phase_id, "phase_window", "empty window must have null frame bounds"))
            png = phase.get("screenshot")
            phase_clock = phase.get("clock")
            if phase_time is None or _utc(phase.get("at_utc")) is None or abs(_utc(phase.get("at_utc")) - phase_time) > 0.05:
                failures.append(_problem(case_id, phase_id, "phase_clock", "phase lacks a valid coherent five-field driver/Chrome clock"))
            if previous_time is not None and phase_time is not None and phase_time < previous_time:
                failures.append(_problem(case_id, phase_id, "phase_clock", "phase clock goes backwards"))
            if expected:
                if window.get("wall_time_utc_first") != expected[0].get("wall_time_utc") or window.get("wall_time_utc_last") != expected[-1].get("wall_time_utc"):
                    failures.append(_problem(case_id, phase_id, "phase_clock", "wall clock window differs from frames"))
                times = [_utc(frame.get("wall_time_utc")) for frame in expected]
                if any(value is None for value in times) or times != sorted(times):
                    failures.append(_problem(case_id, phase_id, "phase_clock", "invalid or unordered frame times"))
                elif phase_time is not None and (times[-1] > phase_time + 0.05 or (previous_time is not None and times[0] < previous_time - 0.05)):
                    failures.append(_problem(case_id, phase_id, "phase_clock", "frames fall outside the action observation interval"))
            if require_png:
                if not isinstance(png, dict):
                    failures.append(_png_problem(case_id, phase_id, "required PNG record is missing"))
                else:
                    for key in ("namespace", "case_id", "phase_id", "at_utc", "frame_first", "frame_last", "sha256", "bytes", "file"):
                        if key not in png:
                            failures.append(_png_problem(case_id, phase_id, f"missing {key}"))
                    if png.get("namespace") != namespace or png.get("case_id") != case_id or png.get("phase_id") != phase_id:
                        failures.append(_png_problem(case_id, phase_id, "PNG identifiers differ from phase"))
                    if png.get("frame_first") != first or png.get("frame_last") != last:
                        failures.append(_png_problem(case_id, phase_id, "PNG is not bound to the action frame window"))
                    last_time = _utc(expected[-1].get("wall_time_utc")) if expected else previous_time
                    if not _png_clock_matches(png, phase_time, last_time, bool(not expected)):
                        failures.append(_problem(case_id, phase_id, "png_clock", "PNG clock/time does not bind the real screenshot to this action window"))
                    path = ROOT / str(png.get("file", ""))
                    if not path.is_file() or not path.resolve().is_relative_to(ROOT.resolve()):
                        failures.append(_png_problem(case_id, phase_id, "PNG path is missing or outside evidence root"))
                    else:
                        data = path.read_bytes()
                        if len(data) != png.get("bytes") or hashlib.sha256(data).hexdigest() != png.get("sha256"):
                            failures.append(_png_problem(case_id, phase_id, "PNG bytes/hash differ"))

            quiet = phase_id in QUIET_PHASE_IDS
            if quiet:
                minimum = QUIET_MIN_SECONDS[phase_id]
                picture_progress = _clock_progress(previous_clock, (png or {}).get("clock")) if isinstance(png, dict) else None
                if progress is None or min(progress) < minimum or (require_png and (picture_progress is None or min(picture_progress) < minimum)):
                    failures.append(_problem(case_id, phase_id, "quiet_duration", f"both monotonic clocks must cover the {minimum:g}s observation policy before the PNG and endpoint"))
            if quiet and expected:
                failures.append(_problem(case_id, phase_id, "unexpected_rerun", "an edit-only phase contacted the server"))
            elif quiet:
                before_dom = phase.get("dom_before")
                after_dom = phase.get("dom_after")
                if not isinstance(before_dom, dict) or not isinstance(after_dom, dict):
                    failures.append(_problem(case_id, phase_id, "quiet_dom", "both DOM observations are required"))
                else:
                    if before_dom.get("texts") != after_dom.get("texts"):
                        failures.append(_problem(case_id, phase_id, "quiet_dom", "server-rendered counters/markers changed without a frame"))
                    action = (phase.get("action") or {}).get("action")
                    if action == "type":
                        field = str((phase.get("action") or {}).get("field", ""))
                        before_values = [item for item in before_dom.get("text_inputs") or [] if item.get("label") == field]
                        after_values = [item for item in after_dom.get("text_inputs") or [] if item.get("label") == field]
                        if not before_values or not after_values or before_values[0].get("value") == after_values[0].get("value"):
                            failures.append(_problem(case_id, phase_id, "quiet_dom", f"the staged text value of {field!r} did not change"))
                    if action == "click":
                        field = str((phase.get("action") or {}).get("field", ""))
                        before_values = [item for item in before_dom.get("checkboxes") or [] if field in str(item.get("label", ""))]
                        after_values = [item for item in after_dom.get("checkboxes") or [] if field in str(item.get("label", ""))]
                        if not before_values or not after_values or before_values[0].get("checked") == after_values[0].get("checked"):
                            failures.append(_problem(case_id, phase_id, "quiet_dom", f"the staged checkbox {field!r} did not change"))

                previous = next(
                    (item.get("frames") or [] for item in reversed(case_phases[:phase_index]) if item.get("frames")),
                    None,
                )
                following = next(
                    (item.get("frames") or [] for item in case_phases[phase_index + 1 :] if item.get("frames")),
                    None,
                )
                if not previous:
                    failures.append(_problem(case_id, phase_id, "quiet_connection", "a quiet window has no preceding live frame"))
                elif following:
                    left, right = previous[-1], following[0]
                    if left.get("connection") != right.get("connection") or left.get("request_id") != right.get("request_id"):
                        failures.append(_problem(case_id, phase_id, "quiet_connection", "the surrounding live frames are not on one connection"))
                else:
                    request_id = str(previous[-1].get("request_id"))
                    handshake = next((item for item in obs.get("websocket_handshakes") or [] if str(item.get("request_id")) == request_id), None)
                    close_time = _utc((handshake or {}).get("closed_wall_time_utc"))
                    close_stamp = (handshake or {}).get("closed_timestamp")
                    offset = (obs.get("chrome_clock") or {}).get("offset_s")
                    closed_later = (phase_time is not None and close_time is not None and _number(close_stamp) and _number(offset)
                                    and abs(close_time - close_stamp - offset) <= 0.01 and close_time >= phase_time)
                    if not handshake or not (handshake.get("closed") is False or (handshake.get("closed") is True and closed_later)):
                        failures.append(_problem(case_id, phase_id, "quiet_connection", "the terminal quiet window's connection is not demonstrably live"))
            if not quiet:
                if not supplied:
                    failures.append(_problem(case_id, phase_id, "empty_action_window", "a required action has no phase frame references"))
                if not expected:
                    failures.append(_problem(case_id, phase_id, "empty_action_window", "a non-quiet action produced no frames"))
                    continue
                reruns = [frame for frame in expected if (frame.get("_official_full") or {}).get("type") == "rerun_script"]
                completions = [frame for frame in expected if (frame.get("_official_full") or {}).get("type") == "script_finished"]
                sessions = [frame for frame in expected if (frame.get("_official_full") or {}).get("type") == "new_session"]
                if len(reruns) != 1:
                    failures.append(_problem(case_id, phase_id, "rerun_count", str(len(reruns))))
                if len(completions) != 1:
                    failures.append(_problem(case_id, phase_id, "missing_completion", "expected one script_finished in action window"))
                if len(sessions) != 1:
                    failures.append(_problem(case_id, phase_id, "missing_run_id", "expected one distinct new_session in action window"))
                if reruns and completions and sessions:
                    run_frames = [reruns[0], sessions[0], completions[0]]
                    if len({(frame.get("connection"), frame.get("request_id")) for frame in run_frames}) != 1:
                        failures.append(_problem(case_id, phase_id, "connection", "trigger and completion use different sockets"))
                    if not reruns[0]["index"] < sessions[0]["index"] < completions[0]["index"]:
                        failures.append(_problem(case_id, phase_id, "run_order", "expected trigger, new_session, successful completion in order"))

    if canonical_cases.get("form-j05-continuous"):
        failures.extend(_j05_failures(canonical_cases["form-j05-continuous"]))
    if canonical_cases.get("form-default-submit"):
        texts = [phase.get("dom_after", {}).get("texts", []) for phase in cases["form-default-submit"].get("phases", [])]
        flat = [text for batch in texts for text in batch]
        if not any("Order this run: callback,main" in text for text in flat):
            failures.append({"case_id": "form-default-submit", "phase_id": "*", "code": "callback_order", "detail": "callback-before-main marker missing"})
    for frame in frames:
        frame.pop("_official_full", None)
    for case in obs.get("cases") or []:
        for phase in case.get("phases") or []:
            for frame in phase.get("frames") or []:
                frame.pop("_official_full", None)
    return failures
