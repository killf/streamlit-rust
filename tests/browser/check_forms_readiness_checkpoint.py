"""Synthetic producer control-flow regressions; never reference/product proof."""
import json
import base64
import hashlib
import pathlib
import sys
import tempfile
from unittest.mock import patch
import forms_capture as capture


def main():
    assert capture.case_dom_ready("form-error-duplicate-key", {"texts": [], "exceptions": ["observed error"]})
    assert capture.case_dom_ready("form-error-nested-form", {"texts": [], "exceptions": ["observed error"]})
    assert not capture.case_dom_ready("form-error-duplicate-key", {"texts": ["unrelated text"], "exceptions": []})
    assert not capture.case_dom_ready("form-error-nested-form", {"texts": [], "exceptions": []})
    assert not capture.case_dom_ready("form-default-submit", {"texts": [], "exceptions": []})
    assert not capture.case_dom_ready("form-j05-continuous", {"texts": ["unrelated text"], "exceptions": []})
    for case in ("form-default-submit", "form-j05-continuous"):
        try:
            capture.case_dom_ready(case, {"texts": ["Script runs: 1"], "exceptions": ["unexpected error"]})
        except RuntimeError:
            pass
        else:
            raise AssertionError("normal/J05 actual exception was accepted")
    parent = capture.ROOT / "target/forms-capture/checkpoint-regressions"
    parent.mkdir(parents=True, exist_ok=True)
    out = pathlib.Path(tempfile.mkdtemp(prefix="unit-", dir=parent))
    atomic = out / "atomic-unit.json"
    capture.atomic_json(atomic, {"unit_data": 1})
    with patch.object(capture.os, "replace", side_effect=OSError("simulated atomic replace failure")):
        try:
            capture.atomic_json(atomic, {"unit_data": 2})
        except OSError:
            pass
        else:
            raise AssertionError("replacement failure was swallowed")
    assert json.loads(atomic.read_text()) == {"unit_data": 1}
    # Synthetic CDP envelope and ForwardMsg for persistence testing only.
    # It is never used as a reference/app observation or accepted product proof.
    from streamlit.proto.ForwardMsg_pb2 import ForwardMsg
    message = ForwardMsg()
    message.session_status_changed.script_is_running = True
    payload = message.SerializeToString()
    unit_events = [
        {"method": "Network.requestWillBeSent", "params": {
            "requestId": "unit-http", "timestamp": 10.0, "wallTime": 1700000000.0,
            "type": "Document", "request": {"url": "http://unit.invalid/retained", "method": "GET"}}},
        {"method": "Network.webSocketFrameReceived", "params": {
            "requestId": "unit-websocket", "timestamp": 10.5,
            "response": {"opcode": 2, "payloadData": base64.b64encode(payload).decode("ascii")}}},
    ]
    original_png = capture.ROOT / "tests/browser/rust-forms-j05/png/form-j05-continuous-01-load.png"
    png_bytes = original_png.read_bytes()
    (out / "png").mkdir()
    (out / "png/retained-original.png").write_bytes(png_bytes)
    class Recorder:
        def __init__(self, *a, **k): pass
        def start(self): pass
        def stop(self): pass
        def take(self): return list(unit_events)
    class Chrome:
        def terminate(self): pass
    completed = []
    def collect(page, recorder, case, args, output, *, progress):
        if completed:
            previous = json.loads((out / "capture-state.json").read_text())
            assert previous["completed_case_ids"] == completed
            assert previous["complete"] is False
            progress["phases"].append({"synthetic_unit_phase": "active-phase-retained"})
            raise RuntimeError("synthetic predicate exploded")
        progress["phases"].append({"synthetic_unit_phase": "completed-phase-retained"})
        result = dict(progress)
        completed.append(case)
        return result
    argv = ["forms_capture.py", "--url", "http://unit.invalid", "--out", str(out),
            "--cases", "form-default-submit", "form-error-duplicate-key"]
    with patch.object(sys, "argv", argv), patch.object(capture, "start_chrome", return_value=Chrome()), patch.object(capture, "chrome_binary", return_value="unit-only"), patch.object(capture, "page_targets", return_value=[{"type": "page", "webSocketDebuggerUrl": "ws://unit.invalid"}]), patch.object(capture, "CDP", Recorder), patch.object(capture, "FormsPage", return_value=object()), patch.object(capture, "collect_case", side_effect=collect), patch.object(capture, "host_config", return_value={"unit_control_flow_only": True}), patch.object(capture, "frontend_record", return_value={"unit_control_flow_only": True}):
        code = capture.main()
    state = json.loads((out / "capture-state.json").read_text())
    trace = json.loads((out / "trace-forms.json").read_text())
    assert code == state["process_exit_code"] == 1
    assert state["complete"] is False
    assert state["completed_case_ids"] == ["form-default-submit"]
    assert state["active_case_id"] == "form-error-duplicate-key"
    assert state["failure"]["message"] == "synthetic predicate exploded"
    assert len(trace["frames"]) == 1 and len(trace["cases"]) == 2
    frame = trace["frames"][0]
    assert base64.b64decode(frame["base64"]) == payload
    assert frame["bytes"] == len(payload)
    assert frame["sha256"] == hashlib.sha256(payload).hexdigest()
    assert trace["http_requests"][0]["url"] == "http://unit.invalid/retained"
    assert trace["cases"][0]["phases"] == [{"synthetic_unit_phase": "completed-phase-retained"}]
    assert trace["cases"][1]["phases"] == [{"synthetic_unit_phase": "active-phase-retained"}]
    assert state["observed_png_files"][0]["sha256"] == hashlib.sha256(png_bytes).hexdigest()
    assert hashlib.sha256((out / "trace-forms.json").read_bytes()).hexdigest() == state["trace_sha256"]
    report = {"scope": "Synthetic producer readiness/atomic checkpoint tests, not product observations", "readiness_paths": "two real-exception cases ready; missing/normal/J05 exception paths rejected", "atomic_replace": "previous complete JSON retained on replacement error", "predicate_exception": "per-case checkpoint exists before next case; finally retained partial trace and failure, exit 1", "unit_output": str(out)}
    (out / "regression-result.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report))


if __name__ == "__main__":
    main()
