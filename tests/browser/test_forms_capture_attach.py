"""Mock-only leased-browser cleanup tests. No Chrome or network is accessed."""
from __future__ import annotations

import base64
import copy
import hashlib
import json
import pathlib
import sys
import tempfile
from urllib.error import URLError

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import forms_capture as capture


class Response:
    def __init__(self, payload):
        self.payload = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
    def __enter__(self): return self
    def __exit__(self, *args): pass
    def read(self): return self.payload


class LeasedBrowser:
    def __init__(self, fault=None):
        self.original = {
            "user-a": {"id": "user-a", "type": "page", "url": "https://user.invalid/a"},
            "user-b": {"id": "user-b", "type": "page", "url": "http://127.0.0.1:8501/"},
        }
        self.tabs = copy.deepcopy(self.original)
        self.fault = fault
        self.closed = []
        self.requests = []
    def open(self, request, **kwargs):
        url = request.full_url if isinstance(request, capture.urllib.request.Request) else request
        method = request.get_method() if isinstance(request, capture.urllib.request.Request) else "GET"
        self.requests.append((method, url))
        if url == "http://127.0.0.1:60667/json/list":
            return Response(list(self.tabs.values()))
        if url == "http://127.0.0.1:60667/json/new?about:blank":
            assert method == "PUT"
            if self.fault == "creation":
                raise URLError("unit creation failure")
            if self.fault == "existing_id":
                return Response(self.tabs["user-a"])
            tab = {"id": "owned-unit", "type": "page", "url": "about:blank"}
            if self.fault != "missing_debugger":
                tab["webSocketDebuggerUrl"] = "ws://127.0.0.1:60667/devtools/page/owned-unit"
            self.tabs["owned-unit"] = tab
            return Response(tab)
        if url == "http://127.0.0.1:60667/json/close/owned-unit":
            self.closed.append("owned-unit")
            if self.fault == "cleanup":
                raise URLError("unit cleanup failure")
            del self.tabs["owned-unit"]
            return Response(b"Target is closing")
        raise AssertionError(f"Unexpected/mock-external browser request: {method} {url}")
    def assert_originals_unchanged(self):
        assert {key: self.tabs[key] for key in self.original} == self.original


def unit_output():
    parent = capture.ROOT / "target/forms-capture/attach-unit"
    parent.mkdir(parents=True, exist_ok=True)
    return pathlib.Path(tempfile.mkdtemp(prefix="unit-", dir=parent))


def forbid(*args, **kwargs):
    raise AssertionError("Shared-browser launch/kill/CLI action was attempted")


def run_attach(monkeypatch, fault=None):
    browser = LeasedBrowser(fault)
    out = unit_output()
    from streamlit.proto.ForwardMsg_pb2 import ForwardMsg
    msg = ForwardMsg()
    msg.session_status_changed.script_is_running = True
    payload = msg.SerializeToString()
    events = [{"method": "Network.webSocketFrameReceived", "params": {
        "requestId": "unit-ws", "timestamp": 1.0,
        "response": {"opcode": 2, "payloadData": base64.b64encode(payload).decode()}}}]
    recorders = []
    class Recorder:
        def __init__(self, url, **kwargs):
            assert url == "ws://127.0.0.1:60667/devtools/page/owned-unit"
            self.stopped = False
            recorders.append(self)
        def start(self):
            if fault == "recorder_start": raise RuntimeError("unit recorder start failure")
        def stop(self): self.stopped = True
        def take(self): return list(events)
    def make_page(recorder):
        if fault == "page_constructor": raise RuntimeError("unit page constructor failure")
        return object()
    def collect(page, recorder, case, args, output, *, progress):
        progress["phases"].append({"synthetic_unit_phase": "retained"})
        if fault == "capture": raise RuntimeError("unit predicate failure")
        return dict(progress)
    monkeypatch.setattr(capture.urllib.request, "urlopen", browser.open)
    for name in ("start_chrome", "chrome_binary", "agent_browser", "_kill_tree"):
        monkeypatch.setattr(capture, name, forbid)
    monkeypatch.setattr(capture.subprocess, "Popen", forbid)
    monkeypatch.setattr(capture, "CDP", Recorder)
    monkeypatch.setattr(capture, "FormsPage", make_page)
    monkeypatch.setattr(capture, "collect_case", collect)
    monkeypatch.setattr(capture, "host_config", lambda *args: {"synthetic_unit": True})
    monkeypatch.setattr(capture, "frontend_record", lambda *args: {"synthetic_unit": True})
    monkeypatch.setattr(sys, "argv", ["forms_capture.py", "--browser-mode", "attach", "--cdp-port", "60667", "--url", "http://unit.invalid", "--out", str(out), "--cases", "form-j05-continuous"])
    code = capture.main()
    state = json.loads((out / "capture-state.json").read_text(encoding="utf-8"))
    raw = (out / "trace-forms.json").read_bytes()
    trace = json.loads(raw)
    assert state["trace_sha256"] == hashlib.sha256(raw).hexdigest()
    browser.assert_originals_unchanged()
    assert all(recorder.stopped for recorder in recorders)
    return code, state, trace, browser, payload


def test_attach_success_creates_and_closes_only_own_tab(monkeypatch):
    code, state, trace, browser, payload = run_attach(monkeypatch)
    assert code == 0 and state["complete"] is True
    assert browser.tabs == browser.original
    assert browser.closed == ["owned-unit"]
    assert trace["browser"] == {"mode": "attach", "cdp_port": 60667, "session_label": "forms-capture", "owned_target_id": "owned-unit"}


@pytest.mark.parametrize("fault", ["capture", "recorder_start", "page_constructor", "missing_debugger"])
def test_attach_exception_closes_owned_tab_preserves_partial_and_others(monkeypatch, fault):
    code, state, trace, browser, payload = run_attach(monkeypatch, fault)
    assert code == 1 and state["complete"] is False and state["failure"]
    assert browser.tabs == browser.original and browser.closed == ["owned-unit"]
    if fault != "missing_debugger":
        assert base64.b64decode(trace["frames"][0]["base64"]) == payload
        assert trace["frames"][0]["sha256"] == hashlib.sha256(payload).hexdigest()
    if fault == "capture":
        assert trace["cases"][0]["phases"] == [{"synthetic_unit_phase": "retained"}]
        assert state["active_case_id"] == "form-j05-continuous"


@pytest.mark.parametrize("fault", ["creation", "existing_id"])
def test_attach_without_proven_new_id_never_closes_an_existing_tab(monkeypatch, fault):
    code, state, trace, browser, payload = run_attach(monkeypatch, fault)
    assert code == 1 and state["complete"] is False
    assert browser.tabs == browser.original and browser.closed == []
    assert trace["browser"]["owned_target_id"] is None


def test_attach_cleanup_failure_is_nonzero_without_broader_cleanup(monkeypatch):
    code, state, trace, browser, payload = run_attach(monkeypatch, "cleanup")
    assert code == 1 and state["complete"] is False
    assert "cleanup failure" in state["failure"]["message"]
    assert browser.closed == ["owned-unit"]
    browser.assert_originals_unchanged()


@pytest.mark.parametrize("extra", [[], ["--cdp-port", "60667", "--transport-disconnect"]])
def test_attach_requires_explicit_port_and_rejects_transport_experiment(monkeypatch, extra):
    monkeypatch.setattr(capture.urllib.request, "urlopen", forbid)
    monkeypatch.setattr(capture, "start_chrome", forbid)
    monkeypatch.setattr(sys, "argv", ["forms_capture.py", "--browser-mode", "attach", "--url", "http://unit.invalid", *extra])
    with pytest.raises(SystemExit) as error:
        capture.main()
    assert error.value.code == 2


def test_collect_attach_navigates_explicit_owned_target_without_cli(monkeypatch):
    from types import SimpleNamespace
    out = unit_output()
    calls = []
    url = "http://unit.invalid/?case=unit-only"
    class Control:
        def call(self, method, params):
            calls.append((method, params))
            return {"result": {}}
    class Page:
        cdp = Control()
        def evaluate(self, expression): return url
        def dom(self): return {"texts": ["synthetic unit"], "exceptions": []}
        def clock(self): return {"wall_ms": 1, "perf_ms": 1, "origin_ms": 0}
        def screenshot(self, path):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"synthetic-unit-file-not-product-PNG")
            return {"viewport": [1, 1]}
    recorder = type("Recorder", (), {"take": lambda self: []})()
    args = SimpleNamespace(url="http://unit.invalid", browser_mode="attach", owned_target_id="owned-unit")
    monkeypatch.setattr(capture, "agent_browser", forbid)
    monkeypatch.setattr(capture.time, "sleep", lambda *a: None)
    observed = capture.collect_case(Page(), recorder, "unit-only", args, out)
    assert calls == [("Page.navigate", {"url": url})]
    assert observed["navigation"]["target_id"] == "owned-unit"


def test_managed_default_keeps_owned_process_lifecycle_and_port(monkeypatch):
    out = unit_output()
    calls = []
    class Chrome:
        def terminate(self): calls.append("terminate-managed")
    class Recorder:
        def __init__(self, *a, **k): pass
        def start(self): pass
        def stop(self): calls.append("stop-recorder")
        def take(self): return []
        def call(self, *a, **k): return {"result": {}}
    def start(binary, port, profile):
        assert port == 60917 and profile.name == "chrome-profile"
        calls.append("start-managed")
        return Chrome()
    monkeypatch.setattr(capture, "chrome_binary", lambda: "unit-only")
    monkeypatch.setattr(capture, "start_chrome", start)
    monkeypatch.setattr(capture, "create_owned_target", forbid)
    monkeypatch.setattr(capture, "close_owned_target", forbid)
    monkeypatch.setattr(capture, "page_targets", lambda port: [{"type": "page", "webSocketDebuggerUrl": "ws://unit.invalid"}])
    monkeypatch.setattr(capture, "CDP", Recorder)
    monkeypatch.setattr(capture, "FormsPage", lambda recorder: object())
    monkeypatch.setattr(capture, "collect_case", lambda *a, progress, **k: dict(progress))
    monkeypatch.setattr(capture, "host_config", lambda *a: {"synthetic_unit": True})
    monkeypatch.setattr(capture, "frontend_record", lambda *a: {"synthetic_unit": True})
    ticks = iter([0.0, 6.0])
    monkeypatch.setattr(capture.time, "monotonic", lambda: next(ticks))
    monkeypatch.setattr(sys, "argv", ["forms_capture.py", "--url", "http://unit.invalid", "--out", str(out), "--cases", "form-j05-continuous"])
    assert capture.main() == 0
    assert calls == ["start-managed", "stop-recorder", "terminate-managed"]
