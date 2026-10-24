"""Replay CLI scope/exit unit tests; synthetic inputs are not reference proof."""
import base64
import json
import pathlib
import sys
import tempfile

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import forms_capture as capture
import forms_contract as contract


@pytest.fixture
def replay(monkeypatch, capsys):
    parent = capture.ROOT / "target/forms-capture/replay-cli-unit"
    parent.mkdir(parents=True, exist_ok=True)
    output = pathlib.Path(tempfile.mkdtemp(prefix="unit-", dir=parent))
    calls = []
    def verify(obs, **kwargs):
        calls.append(kwargs)
        return []
    monkeypatch.setattr(capture, "require_decoder", lambda: None)
    monkeypatch.setattr(capture, "pb_trace_report", lambda obs: {"frames": 1, "checks_passed": {}, "failures": [], "ok": True})
    monkeypatch.setattr(contract, "verify_forms_text_input_contract", verify)
    def run(declared=("form-j05-continuous",), selected=None, profile="standalone"):
        trace = {"frames": [{"synthetic_unit_frame": True}], "cases": [{"case_id": case} for case in declared]}
        path = output / "unit-input.json"
        path.write_text(json.dumps(trace), encoding="utf-8")
        code = capture.verify_trace(path, case_ids=selected, j05_profile=profile)
        return code, json.loads(capsys.readouterr().out), calls
    return run


def test_csv_calls_exact_frozen_api_and_reports_one_actual_case(replay):
    code, report, calls = replay(selected=["form-j05-continuous"], profile="csv-data-app")
    assert code == 0 and report["ok"]
    assert report["contract"]["checked_case_ids"] == ["form-j05-continuous"]
    assert report["contract"]["checked_case_count"] == 1
    assert calls == [{"namespace": "forms-text-input-v1", "case_ids": ("form-j05-continuous",), "docs_label": "1.66.0", "runtime_version": "1.66.1", "require_png": True, "j05_profile": "csv-data-app"}]


def test_default_scope_is_all_declared_cases_not_implicit_core5(replay):
    declared = ("form-default-submit", "form-text-enter-blur")
    code, report, calls = replay(declared=declared)
    assert code == 0
    assert calls[0]["case_ids"] == declared and calls[0]["j05_profile"] == "standalone"
    assert report["contract"]["checked_case_count"] == 2


def test_explicit_all_canonical_scope(replay):
    code, report, calls = replay(declared=capture.CASES, selected=["all"])
    assert code == 0 and report["contract"]["case_scope"] == "all-canonical"
    assert report["contract"]["checked_case_count"] == len(capture.CASES) == 25
    assert calls[0]["case_ids"] == tuple(capture.CASES)


@pytest.mark.parametrize("selected,profile", [
    (None, "csv-data-app"), ([], "standalone"), (["unknown"], "standalone"),
    (["form-default-submit"], "standalone"),
    (["form-j05-continuous", "form-j05-continuous"], "standalone"),
    (["all"], "csv-data-app"), (["all", "form-j05-continuous"], "standalone"),
    (["form-j05-continuous"], "unknown"),
])
def test_invalid_or_missing_selection_never_silently_passes(replay, selected, profile):
    code, report, calls = replay(selected=selected, profile=profile)
    assert code == 1 and not report["ok"] and report["contract"]["failures"]
    assert report["contract"]["checked_case_count"] == 0 and calls == []


@pytest.mark.parametrize("declared", [(), (None,), ("unknown",), ("form-j05-continuous", "form-j05-continuous")])
def test_bad_capture_case_declaration_rejected(replay, declared):
    code, report, calls = replay(declared=declared)
    assert code == 1 and not report["ok"] and calls == []


def test_contract_failure_cannot_be_hidden_by_pb_success(replay, monkeypatch):
    monkeypatch.setattr(contract, "verify_forms_text_input_contract", lambda *a, **k: [{"code": "unit-contract-rejection"}])
    code, report, _ = replay(selected=["form-j05-continuous"])
    assert code == 1 and report["pb"]["ok"] and not report["contract"]["ok"]


def test_pb_failure_cannot_be_hidden_by_contract_success(replay, monkeypatch):
    monkeypatch.setattr(capture, "pb_trace_report", lambda obs: {"frames": 1, "checks_passed": {}, "failures": [{"check": "unit-pb-rejection"}], "ok": False})
    code, report, calls = replay()
    assert code == 1 and not report["pb"]["ok"] and report["contract"]["ok"] and calls


def test_contract_exception_is_reported_as_nonzero(replay, monkeypatch):
    def explode(*args, **kwargs): raise RuntimeError("unit predicate exception")
    monkeypatch.setattr(contract, "verify_forms_text_input_contract", explode)
    code, report, _ = replay()
    assert code == 1 and report["contract"]["failures"][0]["code"] == "contract_exception"


@pytest.mark.parametrize("frames", [[], [{"base64": "not-base64"}]])
def test_pb_empty_or_corrupt_payload_is_failure(frames):
    report = capture.pb_trace_report({"frames": frames})
    assert report["ok"] is False and report["failures"]


def test_pb_unknown_direction_is_not_treated_as_backmsg():
    from streamlit.proto.ForwardMsg_pb2 import ForwardMsg
    msg = ForwardMsg();msg.session_status_changed.script_is_running = True
    raw = msg.SerializeToString()
    import hashlib
    report = capture.pb_trace_report({"frames": [{"index": 0, "base64": base64.b64encode(raw).decode(), "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest(), "direction": "unknown", "decoded": {}}]})
    assert report["ok"] is False and report["failures"][0]["check"] == "decode_error"


def test_cli_unknown_profile_and_capture_profile_rejected_before_browser(monkeypatch):
    def forbidden(*a, **k): raise AssertionError("browser must never be accessed")
    monkeypatch.setattr(capture, "start_chrome", forbidden)
    monkeypatch.setattr(capture, "create_owned_target", forbidden)
    for argv in (["--verify", "missing", "--j05-profile", "unknown"], ["--url", "http://unit.invalid", "--j05-profile", "csv-data-app"]):
        monkeypatch.setattr(sys, "argv", ["forms_capture.py", *argv])
        with pytest.raises(SystemExit) as error: capture.main()
        assert error.value.code == 2
