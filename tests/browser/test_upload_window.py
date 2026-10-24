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
import json
import base64
import hashlib
import shutil
import subprocess
from types import SimpleNamespace

import pytest

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "reference"))

import numeric_capture  # noqa: E402

_ORIGINAL_ISOLATION_TARGETS = [
    {"id":"preexisting-user-target","type":"page","url":"http://user.invalid/"},
    *[{"id":f"retained-{i}","type":"page" if i < 14 else "browser_ui","url":"about:blank"} for i in range(16)],
]


class _IsolationCDP:
    """Driver-only transport double: ordering/ownership, not a wire oracle."""

    clock = 100.0
    instances = []
    log = []

    def __init__(self, url, label):
        self.label, self.events, self.epoch = label, [], -1
        self.dom = {key: None for key in numeric_capture.J06_OBSERVATION_FIELDS["dom"]}
        self.dom.update(uploaded_files=[], script_runs=1, pulses=0)
        self.instances.append(self)

    @classmethod
    def tick(cls):
        cls.clock += .01
        return cls.clock

    def start(self):
        self.log.append((self.label, "start"))

    def stop(self):
        self.log.append((self.label, "stop"))

    def take(self):
        return list(self.events)

    def call(self, method, params=None):
        params = params or {}
        self.log.append((self.label, method))
        if method == "Performance.getMetrics":
            return {"result": {"metrics": [{"name": "Timestamp", "value": self.tick()}]}}
        if method in ("Page.navigate", "Page.reload"):
            self.epoch += 1
            request = f"{self.label}-socket-{self.epoch}"
            for name, extra in (
                ("requestWillBeSent", {"type": "Document", "request": {"url": "http://test/", "method": "GET"}}),
                ("webSocketCreated", {"url": "ws://test/_stcore/stream"}),
                ("webSocketWillSendHandshakeRequest", {"request": {"headers": {"Sec-WebSocket-Protocol": "streamlit,token"}}}),
                ("webSocketHandshakeResponseReceived", {"response": {"status": 101, "headers": {"Sec-WebSocket-Protocol": "streamlit"}}}),
            ):
                self.events.append({"method": "Network."+name, "params": dict(requestId=request, timestamp=self.tick(), **extra)})
        return {"result": {}}

    def complete(self, mode):
        from streamlit.proto.BackMsg_pb2 import BackMsg
        from streamlit.proto.ForwardMsg_pb2 import ForwardMsg
        if mode in ("initial", "refresh"):
            self.dom.update(script_runs=1, pulses=0, uploaded_files=[])
        else:
            self.dom["script_runs"] += 1
            if mode == "pulse":
                self.dom["pulses"] += 1
            if mode == "upload":
                self.dom["uploaded_files"] = ["sales_basic.csv"]
        back = BackMsg(); back.rerun_script.SetInParent()
        new = ForwardMsg(); new.new_session.script_run_id = f"{self.label}-{self.epoch}-{self.dom['script_runs']}"
        new.new_session.initialize.environment_info.streamlit_version = "1.66.1"
        new.new_session.main_script_path = str(numeric_capture.ROOT / "tests/reference/app.py")
        finish = ForwardMsg(); finish.script_finished = 0
        for direction, msg in (("Sent", back), ("Received", new), ("Received", finish)):
            payload = msg.SerializeToString()
            self.events.append({"method": "Network.webSocketFrame"+direction, "params": {
                "requestId": f"{self.label}-socket-{self.epoch}", "timestamp": self.tick(),
                "response": {"opcode": 2, "payloadData": base64.b64encode(payload).decode()}}})


class _IsolationPage:
    def __init__(self, cdp):
        self.cdp = cdp

    def bring_to_front(self):
        pass

    def state_digest(self):
        result = dict(self.cdp.dom)
        # Actual OBSERVE_JS pick() returns text, as the real own-tab probe
        # observed: {script_runs:"1", pulses:"0"}, not numeric JSON values.
        for key in ("script_runs","pulses"):
            if type(result[key]) is int:
                result[key] = str(result[key])
        return result

    def files_dom(self):
        return {"chips": list(self.cdp.dom["uploaded_files"])}

    def upload(self, path):
        return True

    def click_visible(self, expression):
        return True

    def screenshot(self, path, *, restore):
        assert restore is False
        path.write_bytes(b"\x89PNG\r\n\x1a\nmock only")
        return {"file": str(path)}


def _isolation_driver(monkeypatch, tmp_path, *, failed_action=False, predicate_error=False, no_response=False,
                      target_fault=None, corrupt_tab=None, bad_base64=False, close_fault=None):
    _IsolationCDP.instances, _IsolationCDP.log = [], []
    created, closed = [], []

    def http(url, method="GET"):
        if "/json/list" in url:
            return _ORIGINAL_ISOLATION_TARGETS + [
                {"id":ident,"type":"page","url":"about:blank","webSocketDebuggerUrl":"ws://"+ident}
                for ident in created if ident not in closed or close_fault == "retained"]
        if "/json/new?" in url:
            assert url.endswith("about:blank")
            if target_fault == "preexisting":
                return {"id":"preexisting-user-target","webSocketDebuggerUrl":"ws://preexisting-user-target"}
            if target_fault == "duplicate" and created:
                return {"id":created[0],"webSocketDebuggerUrl":"ws://"+created[0]}
            if target_fault == "unverified":
                return {"id":"not-in-inventory","webSocketDebuggerUrl":"ws://not-in-inventory"}
            if target_fault == "missing":
                return {}
            ident = f"owned-{len(created)}"
            created.append(ident)
            return {"id": ident, "webSocketDebuggerUrl": "ws://"+ident}
        raise AssertionError("unexpected mock JSON URL: " + url)

    class CloseResponse:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def read(self):
            return b"No such target id" if close_fault == "rejected" else b"Target is closing"

    def urlopen(url, **kwargs):
        assert "/json/close/owned-" in url
        if close_fault == "transport":
            raise OSError("close transport failed")
        closed.append(url.rsplit("/",1)[1])
        return CloseResponse()

    monkeypatch.setattr(numeric_capture, "http_json", http)
    monkeypatch.setattr(numeric_capture.urllib.request, "urlopen", urlopen)
    real_close = numeric_capture._close_owned_target
    monkeypatch.setattr(numeric_capture,"_close_owned_target",lambda port,ident:real_close(port,ident,timeout=.001))
    monkeypatch.setattr(numeric_capture, "CDP", _IsolationCDP)
    monkeypatch.setattr(numeric_capture, "Page", _IsolationPage)
    monkeypatch.setattr(numeric_capture, "_select_option", lambda *args: True)

    def wait(state, start, mode, filename):
        if no_response:
            raise RuntimeError("no server completion")
        state["recorder"].complete(mode)
        if state["key"] == corrupt_tab:
            state["recorder"].events[-1]["params"]["response"]["payloadData"] = (
                "not-valid-base64!" if bad_base64 else base64.b64encode(b"\xff").decode())

    monkeypatch.setattr(numeric_capture, "_isolation_wait", wait)
    if failed_action:
        monkeypatch.setattr(_IsolationPage, "click_visible", lambda *args: False)

    def judge(**kwargs):
        if predicate_error:
            raise NameError("predicate fault")
        return [{"journey": numeric_capture.J06_CASE, "step": numeric_capture.J06_CASE,
                 "check": key, "ok": True} for key in J06_REQUIRED]

    # Use the shared required set, not a second producer case table.
    from capture_browser_trace import J06_REQUIRED
    monkeypatch.setattr(numeric_capture, "j06_checks", judge)
    args = SimpleNamespace(label="mock", port=60667, url="http://test/", scope="driver unit double",
                           binary="", build_base="", journey=numeric_capture.J06_CASE)
    code = numeric_capture.run_isolation_journey(args, tmp_path)
    return code, json.loads((tmp_path/"trace-data-loop.json").read_text()), created, closed


def test_j06_driver_records_before_navigation_and_owns_cleanup(monkeypatch, tmp_path):
    code, trace, created, closed = _isolation_driver(monkeypatch, tmp_path)
    assert code == 0
    obs = trace["observation"]
    assert tuple(p["name"] for p in obs["phases"]) == numeric_capture.J06_PHASES
    assert len(obs["screenshots"]) == 18
    assert closed == created == ["owned-0", "owned-1"]
    log = _IsolationCDP.log
    assert max(log.index((key, "start")) for key in ("mock-a", "mock-b")) < log.index(("mock-a", "Page.navigate"))
    assert ("mock-b", "Page.reload") not in log
    assert sum(method == "Page.reload" for _, method in log) == 1
    assert [e["id"] for e in obs["tabs"]["a"]["epochs"]] == ["a0", "a1"]
    assert [e["id"] for e in obs["tabs"]["b"]["epochs"]] == ["b0"]
    for tab in obs["tabs"].values():
        assert any(e["method"] == "Network.webSocketCreated" for e in tab["events"])
        for f in tab["frames"]:
            assert hashlib.sha256(base64.b64decode(f["base64"])).hexdigest() == f["sha256"]
    pulses = [p for p in obs["phases"] if p["action"]["action"] == "pulse"]
    assert [p["views"]["a"]["dom_after"]["pulses"] for p in pulses] == ["1", "2", "3"]
    for phase in obs["phases"]:
        for key, view in phase["views"].items():
            frames = obs["tabs"][key]["frames"]
            assert view["start"] == sum(f["timestamp"] <= view["read_start_timestamp"] for f in frames)
            assert view["end"] == sum(f["timestamp"] <= view["read_end_timestamp"] for f in frames)
            if view["mode"] == "readonly":
                assert view["client_states"] == view["completions"] == []
                assert view["ipc"] == {"table": None, "chart": None}


@pytest.mark.parametrize("failure", ["failed_action", "predicate_error", "no_response"])
def test_j06_driver_nonzero_preserves_raw_and_closes_only_own_tabs(monkeypatch, tmp_path, failure):
    code, trace, created, closed = _isolation_driver(monkeypatch, tmp_path, **{failure: True})
    assert code == 1 and trace["failures"]
    assert closed == created
    assert set(trace["observation"]["tabs"]) == {"a", "b"}
    if failure != "no_response":
        assert trace["observation"]["tabs"]["a"]["frames"]
    if failure == "predicate_error":
        assert len(trace["observation"]["screenshots"]) == 18
        assert "NameError" in trace["failures"][0]["actual"]


def test_j06_dom_never_defaults_missing_files_to_empty():
    page = _IsolationPage(_IsolationCDP("", "missing"))
    page.files_dom = lambda: None
    with pytest.raises(RuntimeError, match="uploader"):
        numeric_capture._isolation_dom(page)


def test_j06_view_keeps_late_business_frames_and_real_read_boundary(tmp_path):
    from streamlit.proto.ForwardMsg_pb2 import ForwardMsg
    recorder = _IsolationCDP("", "late")
    recorder.complete("initial")
    # A business delta after success must remain in raw and in the view's
    # actual read interval.  The driver cannot hide it at the first finish.
    message = ForwardMsg(); message.delta.new_element.markdown.body = "late unwanted output"
    payload = message.SerializeToString()
    recorder.events.append({"method": "Network.webSocketFrameReceived", "params": {
        "requestId": "late-socket--1", "timestamp": recorder.tick(),
        "response": {"opcode": 2, "payloadData": base64.b64encode(payload).decode()}}})
    tab = {"namespace": "late", "events": recorder.take(), "frames": numeric_capture.frames_of(recorder,"late",raw=True)}
    original = json.dumps(tab, sort_keys=True)
    stamps = [f["timestamp"] for f in tab["frames"]]
    view = numeric_capture._isolation_view(tab,"initial","a0",None,{},stamps[0]-.001,stamps[-1]+.001,None,
                                           numeric_capture._ArrowFiles(tmp_path))
    assert view["end"] == 4 and view["checkpoint"]["finish_frame"] == 2
    assert json.dumps(tab, sort_keys=True) == original


def test_j06_wait_without_response_is_not_ready():
    recorder = _IsolationCDP("", "silent")
    state = {"recorder": recorder, "namespace": "silent", "page": _IsolationPage(recorder),
             "started": 1, "target_id": "own", "key": "a", "navigations": []}
    with pytest.raises(RuntimeError, match="completion/DOM paint timeout"):
        numeric_capture._isolation_wait(state,0,"pulse",timeout=.001)


def test_j06_runtime_rejects_nonreference_version():
    from streamlit.proto.ForwardMsg_pb2 import ForwardMsg
    message = ForwardMsg(); message.new_session.initialize.environment_info.streamlit_version = "1.44.0"
    tab = {"frames": [{"direction": "server->client", "base64": base64.b64encode(message.SerializeToString()).decode()}]}
    with pytest.raises(RuntimeError, match="not Streamlit 1.66.1"):
        numeric_capture._isolation_runtime(tab,reference=True)


@pytest.mark.parametrize("side", ["a", "b"])
@pytest.mark.parametrize("invalid_base64", [False, True])
def test_j06_decode_fault_retains_both_raw_streams(monkeypatch, tmp_path, side, invalid_base64):
    code, trace, created, closed = _isolation_driver(monkeypatch,tmp_path,corrupt_tab=side,bad_base64=invalid_base64)
    assert code == 1 and trace["failures"] and created == closed
    tabs = trace["observation"]["tabs"]
    assert set(tabs) == {"a", "b"}
    for key, recorder in zip(("a", "b"), _IsolationCDP.instances):
        # Compare all original lifecycle/frame events, not just summary counts.
        assert tabs[key]["events"] == recorder.take()
        assert len(tabs[key]["frames"]) == 3
        for frame,event in zip(tabs[key]["frames"], recorder.take()[-3:]):
            assert frame["base64"] == event["params"]["response"]["payloadData"]
    bad = tabs[side]["frames"][-1]
    if invalid_base64:
        assert bad["decode_error"] and bad["decoded"] is None
    else:
        assert bad["decoded"]["message"] == "undecoded" and bad["decoded"]["error"]
    assert bad["base64"] == ("not-valid-base64!" if invalid_base64 else "/w==")
    if not invalid_base64:
        assert bad["bytes"] == 1 and bad["sha256"] == hashlib.sha256(b"\xff").hexdigest()
    assert not any(f.get("decode_error") or (f.get("decoded") or {}).get("message") == "undecoded"
                   for f in tabs["b" if side == "a" else "a"]["frames"])


@pytest.mark.parametrize("fault", ["preexisting", "duplicate", "unverified", "missing"])
def test_j06_rejects_unowned_target_without_navigation_or_close(monkeypatch, tmp_path, fault):
    code, trace, created, closed = _isolation_driver(monkeypatch,tmp_path,target_fault=fault)
    assert code == 1 and trace["failures"]
    assert closed == created == (["owned-0"] if fault == "duplicate" else [])
    assert not any(method in ("Page.navigate", "Page.reload") for _,method in _IsolationCDP.log)
    assert "preexisting-user-target" not in closed
    assert len(_IsolationCDP.instances) == (1 if fault == "duplicate" else 0)


def test_j06_plain_text_close_confirms_actual_disappearance(monkeypatch, tmp_path):
    code,trace,created,closed = _isolation_driver(monkeypatch,tmp_path)
    assert code == 0 and created == closed
    for result in trace["observation"]["target_cleanup"].values():
        assert result["acknowledgement"] == "Target is closing"
    assert trace["observation"]["target_cleanup"]["b"]["remaining_targets"] == _ORIGINAL_ISOLATION_TARGETS


@pytest.mark.parametrize("fault", ["rejected", "retained", "transport"])
def test_j06_close_failure_cannot_turn_into_pass(monkeypatch, tmp_path, fault):
    code,trace,_,_ = _isolation_driver(monkeypatch,tmp_path,close_fault=fault)
    assert code == 1 and "own target cleanup" in trace["summary"]["producer_error"]
    assert len(trace["observation"]["screenshots"]) == 18
    assert set(trace["observation"]["tabs"]) == {"a","b"}


@pytest.mark.parametrize("value,want", [("0",0),("1",1),("120",120),(0,0),(12,12)])
def test_j06_readiness_counter_parses_only_exact_nonnegative_counts(value, want):
    assert numeric_capture._isolation_counter(value) == want


@pytest.mark.parametrize("value", [None,False,True,0.0,1.0,-1,""," "," 1","1 ","01","-1","1.0","1x","runs: 1","１"])
def test_j06_readiness_counter_missing_or_malformed_never_defaults(value):
    with pytest.raises(ValueError):
        numeric_capture._isolation_counter(value)


def _isolation_counter_state():
    from streamlit.proto.ForwardMsg_pb2 import ForwardMsg
    recorder = _IsolationCDP("", "counter-shape")
    recorder.complete("initial")
    finish = recorder.events.pop()
    for label,value in (("Script runs",1),("Pulses",0)):
        message = ForwardMsg(); message.delta.new_element.text.body = f"{label}: {value}"
        recorder.events.append({"method":"Network.webSocketFrameReceived","params":{
            "requestId":"counter-shape-socket--1","timestamp":recorder.tick(),
            "response":{"opcode":2,"payloadData":base64.b64encode(message.SerializeToString()).decode()}}})
    finish["params"]["timestamp"] = recorder.tick()
    recorder.events.append(finish)
    recorder.dom.update(table_present=False,table_cells=[],chart_present=False,chart_marks="",chart_bars=0)
    return dict(recorder=recorder,namespace=recorder.label,page=_IsolationPage(recorder),
                started=1,target_id="own",key="a",navigations=[])


def test_j06_real_dom_string_shape_reaches_ready_without_rewriting_dom():
    state = _isolation_counter_state()
    numeric_capture._isolation_wait(state,0,"initial",timeout=1)
    assert state["last_dom_read"]["dom"]["script_runs"] == "1"
    assert state["last_dom_read"]["dom"]["pulses"] == "0"


@pytest.mark.parametrize("bad", [None,"junk","2"])
def test_j06_actual_wait_rejects_missing_invalid_or_stale_dom_counter(bad):
    state = _isolation_counter_state()
    state["recorder"].dom["script_runs"] = bad
    with pytest.raises(RuntimeError,match="timeout"):
        numeric_capture._isolation_wait(state,0,"initial",timeout=.001)
    assert state["last_dom_read"]["dom"]["script_runs"] == bad


@pytest.mark.parametrize("fault", ["failed_action","no_response"])
def test_j06_failed_capture_keeps_actual_last_dom(monkeypatch,tmp_path,fault):
    code,trace,_,_ = _isolation_driver(monkeypatch,tmp_path,**{fault:True})
    assert code == 1 and trace["summary"]["failed_phase"]
    for key,recorder in zip(("a","b"),_IsolationCDP.instances):
        saved = trace["observation"]["diagnostics"][key]["last_dom_read"]
        assert saved["timestamp"] > 0
        assert saved["dom"] == dict(_IsolationPage(recorder).state_digest(),uploaded_files=recorder.dom["uploaded_files"])


def test_j06_producer_manifest_counts_actual_inventory_and_exit(monkeypatch,tmp_path):
    code,_,_,_ = _isolation_driver(monkeypatch,tmp_path)
    manifest = json.loads((tmp_path/"execution-manifest.json").read_text())
    assert manifest["targets_before_count"] == manifest["targets_after_count"] == 17
    assert manifest["original_targets_unchanged"] is True
    assert manifest["exit_code"] == code == 0
    assert manifest["executable"] == sys.executable
    assert manifest["argv"] == sys.argv[1:]


def test_j06_failed_manifest_records_nonzero_without_fake_inventory_success(monkeypatch,tmp_path):
    code,_,_,_ = _isolation_driver(monkeypatch,tmp_path,close_fault="retained")
    manifest = json.loads((tmp_path/"execution-manifest.json").read_text())
    assert code == manifest["exit_code"] == 1
    assert manifest["targets_before_count"] == 17 and manifest["targets_after_count"] == 19
    assert manifest["original_targets_unchanged"] is False

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


def test_j01_plan_uses_shared_actions_inputs_and_png_roles():
    plan = numeric_capture._sequence_plan(numeric_capture.J01_CASE)
    assert tuple(step[0] for step in plan) == numeric_capture.J01_PHASES
    for name, action, want_cells, _ in plan:
        for key, value in numeric_capture.J01_ACTIONS[name].items():
            assert action[key] == value
        if name in numeric_capture.J01_INPUTS:
            assert action["file"] == numeric_capture.J01_INPUTS[name]
        assert want_cells == (name != "initial")


def test_j01_unverified_criterion_cannot_pass():
    verdict = numeric_capture._judge_sequence(numeric_capture.J01_CASE, {})
    assert verdict["failures"]
    assert verdict["counts"]["asserted"] == 0


def test_j03_plan_uses_only_shared_phases_actions_and_inputs():
    n = numeric_capture
    plan = n._sequence_plan(n.J03_CASE)
    assert tuple(p[0] for p in plan) == n.J03_PHASES
    for name, action, want_cells, _ in plan:
        assert all(action[k] == v for k, v in n.J03_ACTIONS[name].items())
        if name in n.J03_INPUTS:
            assert action["file"] == n.J03_INPUTS[name]
        assert want_cells == (name not in ("initial", "slider-200"))
    verdict = n._judge_sequence(n.J03_CASE, {})
    assert verdict["failures"] and verdict["counts"]["asserted"] == 0


def test_j02_plan_uses_shared_actions_and_one_final_picture_for_two_steps():
    n = numeric_capture
    plan = n._sequence_plan(n.J02_CASE)
    assert tuple(p[0] for p in plan) == n.J02_PHASES
    for name, action, want_cells, _ in plan:
        assert all(action[k] == v for k, v in n.J02_ACTIONS[name].items())
        assert want_cells == (name != "initial")
    assert n.J02_PNG_ROLES[n.J02_PHASES[-1]] == ("J02-S4", "J02-S5")
    verdict = n._judge_sequence(n.J02_CASE, {})
    assert verdict["failures"] and verdict["counts"]["asserted"] == 0


def test_j00_plan_preserves_shared_preparations_without_form_actions():
    n = numeric_capture
    plan = n._sequence_plan(n.J00_CASE)
    assert tuple(p[0] for p in plan) == n.J00_PHASES
    for name, action, want_cells, _ in plan:
        assert all(action[k] == v for k, v in n.J00_ACTIONS[name].items())
        assert want_cells == (name != "initial")
        assert action["action"] in ("initial", "upload", "slider", "select-option", "checkbox")
    assert n.J00_PNG_ROLES[n.J00_PHASES[-1]] == ("J00-S5", "J00-S6")
    verdict = n._judge_sequence(n.J00_CASE, {})
    assert verdict["failures"] and verdict["counts"]["asserted"] == 0


@pytest.mark.parametrize("split,empty", [(False, False), (True, False), (False, True)])
def test_j00_form_dom_executes_for_same_split_and_missing_forms(split, empty, tmp_path):
    # Reuse the existing H1 DOM test double and its already declared Node dev dependency.
    from test_capture_checks import FAKE_DOM_JS
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js is required for the existing DOM execution regression")
    setup = FAKE_DOM_JS.split("const document = build(")[0]
    setup += """
const note=makeEl('div',{'data-testid':'stTextInput'},{},[
 makeEl('label',{}, {text:'Note'}),makeEl('input',{}, {value:''})]);
const apply=makeEl('div',{'data-testid':'stFormSubmitButton'},{text:'Apply note'});
const pulse=makeEl('div',{'data-testid':'stButton'},{text:'Pulse'});
const first=makeEl('div',{'data-testid':'stForm'},{},[note]);
const second=makeEl('div',{'data-testid':'stForm'},{},[apply]);
"""
    if empty:
        setup += "const document=makeEl('body',{}, {}, []);\n"
    elif split:
        setup += "const document=makeEl('body',{}, {}, [first,second,pulse]);\n"
    else:
        setup += "const document=makeEl('body',{}, {}, [makeEl('div',{'data-testid':'stForm'},{},[note,apply]),pulse]);\n"
    script = tmp_path / "j00-probe.js"
    script.write_text(setup + "console.log(" + numeric_capture.J00_FORM_DOM_JS + ");", encoding="utf-8")
    done = subprocess.run([node, str(script)], capture_output=True, text=True, timeout=10)
    assert done.returncode == 0, done.stderr
    observed = json.loads(done.stdout)
    if empty:
        assert observed == {"text_inputs": [], "buttons": [], "forms": []}
    else:
        assert observed["text_inputs"] == [{"label": "Note", "value": "", "form_index": 0}]
        by_label = {b["label"]: b for b in observed["buttons"]}
        assert by_label["Pulse"]["form_index"] == -1
        assert by_label["Apply note"]["form_index"] == (1 if split else 0)
        assert bool(observed["forms"][0]["submit_buttons"]) is not split


def test_j00_preserves_actual_form_proto_using_canonical_helper():
    from streamlit.proto.ForwardMsg_pb2 import ForwardMsg
    from streamlit.proto.BackMsg_pb2 import BackMsg
    from forms_contract import _official_forward, _form_blocks_from_forward
    block = ForwardMsg(); block.delta.add_block.form.form_id = "actual-form-id"
    note = ForwardMsg(); note.delta.new_element.text_input.id = "actual-note-id"
    note.delta.new_element.text_input.label = "Note"; note.delta.new_element.text_input.form_id = "actual-form-id"
    submit = ForwardMsg(); submit.delta.new_element.button.id = "actual-submit-id"
    submit.delta.new_element.button.label = "Apply note"; submit.delta.new_element.button.form_id = "actual-form-id"
    submit.delta.new_element.button.is_form_submitter = True
    client = BackMsg(); client.rerun_script.widget_states.widgets.add(id="actual-note-id", string_value="")
    payloads = [m.SerializeToString() for m in (block, note, submit, client)]
    events = [{"method": "Network.webSocketFrameSent" if i == 3 else "Network.webSocketFrameReceived",
               "params": {"requestId": "real-connection", "timestamp": i,
                          "response": {"opcode": 2, "payloadData": base64.b64encode(b).decode()}}}
              for i, b in enumerate(payloads)]
    recorder = SimpleNamespace(take=lambda: events, capture_form_membership=True)
    frames = numeric_capture.frames_of(recorder, namespace="one-tab")
    for i, (frame, payload) in enumerate(zip(frames, payloads)):
        assert base64.b64decode(frame["base64"]) == payload
        assert frame["bytes"] == len(payload) and frame["sha256"] == hashlib.sha256(payload).hexdigest()
        assert frame["connection"] == 0 and frame["request_id"] == "real-connection"
        if i < 3:
            assert frame["official_forward"] == _official_forward(payload)
            assert frame["form_blocks"] == _form_blocks_from_forward(_official_forward(payload))
    assert frames[0]["form_blocks"][0]["form_id"] == "actual-form-id"
    assert frames[1]["official_forward"]["delta"]["new_element"]["text_input"]["form_id"] == "actual-form-id"
    assert frames[2]["official_forward"]["delta"]["new_element"]["button"]["is_form_submitter"] is True
    recorder.capture_form_membership = False
    ordinary = numeric_capture.frames_of(recorder, namespace="one-tab")
    assert [{k: v for k, v in f.items() if k not in ("base64", "bytes", "sha256", "official_forward", "form_blocks")}
            for f in frames] == ordinary


@pytest.mark.parametrize("before,after,ok,events", [
    (True, False, True, 2), (True, True, False, 2),
    (True, None, False, 2), (None, None, False, 0), (False, False, False, 0),
])
def test_checkbox_false_requires_a_real_native_state_change(before, after, ok, events):
    calls = []
    page = numeric_capture.Page(SimpleNamespace(call=lambda method, params: calls.append((method, params)) or {}))
    readings = iter([before, after])
    page.evaluate = lambda _: next(readings)
    page.focus_checkbox = lambda _: True
    result = page.checkbox_toggle("Include unknown region", False, timeout=0)
    assert result["ok"] is ok
    assert len(calls) == events
    if events:
        assert [p["type"] for _, p in calls] == ["rawKeyDown", "keyUp"]
        assert all(m == "Input.dispatchKeyEvent" and p["code"] == "Space" for m, p in calls)
    if ok:
        assert result["before"] is True and result["after"] is False


def _pointer_page(before_value, after_value):
    calls = []
    cdp = SimpleNamespace(call=lambda method, params: calls.append((method, params)) or {})
    page = numeric_capture.Page(cdp)
    def state(value):
        return {"min": "0", "max": "200", "step": "10", "value": str(value),
                "aria_value_now": None, "aria_value_text": str(value),
                "track": {"x": 100, "y": 200, "width": 400, "height": 40}, "viewport": [600, 500]}
    answers = iter([None, state(before_value), state(after_value)])
    page.evaluate = lambda _: next(answers)
    return page, calls


@pytest.mark.parametrize("target,x", [(0, 100), (100, 300), (200, 499)])
def test_slider_pointer_one_mouse_gesture_and_actual_value(target, x):
    page, calls = _pointer_page(100 if target == 0 else 0, target)
    result = page.slider_pointer("Minimum amount", target, timeout=0)
    assert result["ok"] and result["after"]["value"] == str(target)
    assert result["after"]["aria_value_text"] == str(target)
    assert [params["type"] for _, params in calls] == ["mouseMoved", "mousePressed", "mouseReleased"]
    assert all(method == "Input.dispatchMouseEvent" and params["x"] == x and params["y"] == 220
               for method, params in calls)
    assert all(params["x"] < 500 for _, params in calls)


def test_slider_pointer_unchanged_native_value_is_failure_without_retry():
    page, calls = _pointer_page(0, 0)
    result = page.slider_pointer("Minimum amount", 100, timeout=0)
    assert not result["ok"] and result["after"]["value"] == "0"
    assert len(calls) == 3


def test_slider_pointer_missing_track_never_sends_mouse_events():
    page, calls = _pointer_page(0, 100)
    page.evaluate = lambda _: None
    assert not page.slider_pointer("Minimum amount", 100, timeout=0)["ok"]
    assert not calls


@pytest.mark.parametrize("error_type", [NameError, RuntimeError])
@pytest.mark.parametrize("case", [numeric_capture.J01_CASE, "j07-sequence"])
def test_sequence_preserves_observation_when_criterion_raises(monkeypatch, tmp_path, error_type, case):
    n = numeric_capture
    monkeypatch.setattr(n, "_sequence_plan", lambda _: [("initial", {"action": "initial"}, False, "initial.png")])
    frames = [{"connection": 0}]
    monkeypatch.setattr(n, "frames_of", lambda *a, **k: frames)
    monkeypatch.setattr(n, "_run_window", lambda *a: {"start": 0, "end": 1})
    monkeypatch.setattr(n, "_phase", lambda *a: {"name": "initial", "dom_after": a[-2]})
    png = tmp_path / "initial.png"
    png.write_bytes(b"test-reference-only")
    monkeypatch.setattr(n, "_shot", lambda *a: {"file": png.name, "timestamp": 2.0})
    monkeypatch.setattr(n, "_session_of", lambda *a: "test-session")
    monkeypatch.setattr(n, "_run_id", lambda *a: "test-run")
    monkeypatch.setattr(n, "_uploader_of", lambda *a: [])
    http = [{"method": "PUT", "status": 204, "url": "http://127.0.0.1:8601/test-upload"}]
    monkeypatch.setattr(n, "_http_timeline", lambda *a: http)
    def broken(*a):
        checkpoint = json.loads((tmp_path / "trace-data-loop.json").read_bytes())
        assert checkpoint["observation"]["frames"] == frames
        assert checkpoint["observation"]["http_timeline"] == http
        assert checkpoint["observation"]["screenshots"][0]["file"] == png.name
        raise error_type("unfinished predicate")
    monkeypatch.setattr(n, "_judge_sequence", broken)
    dom = {"script_runs": "1", "pulses": "0", "table_cells": []}
    page = SimpleNamespace(state_digest=lambda: dict(dom), wait_for_render=lambda **k: dict(dom),
                           page_alerts=lambda: {"alerts": [], "exceptions": []})
    args = SimpleNamespace(journey=case, url="http://127.0.0.1:8601/",
                           scope="PYTHON SIDE ONLY", binary="", build_base="")
    assert n.run_sequence_journey(page, SimpleNamespace(label="test-tab"), args, tmp_path) == 1
    saved = json.loads((tmp_path / "trace-data-loop.json").read_bytes())
    assert saved["observation"]["frames"] == frames
    assert saved["observation"]["phases"][0]["counters"] == {"script_runs": "1", "pulses": "0"}
    assert saved["failures"]
    assert saved["failures"][0]["actual"] == f"{error_type.__name__}: unfinished predicate"
    assert saved["observation"]["http_timeline"] == http
    assert saved["observation"]["screenshots"][0]["file"] == png.name
    assert saved["counts"]["asserted"] == 0
    assert not (tmp_path / "trace-data-loop.json.pending").exists()


def _published_sequence_copy(tmp_path):
    source = HERE / "rust-journeys" / "j01-sequence"
    dest = tmp_path / "archive"
    shutil.copytree(source, dest)
    return dest / "trace-data-loop.json"


def _replay_main(monkeypatch, raw):
    def no_browser(*a, **k):
        raise AssertionError("replay must never access the browser")
    monkeypatch.setattr(numeric_capture, "http_json", no_browser)
    monkeypatch.setattr(sys, "argv", ["numeric_capture.py", "--replay", str(raw)])
    return numeric_capture.main()


def test_replay_entry_uses_adjacent_artifacts_without_browser_or_writes(monkeypatch, tmp_path, capsys):
    raw = _published_sequence_copy(tmp_path)
    before = {p.relative_to(raw.parent): p.read_bytes() for p in raw.parent.rglob("*") if p.is_file()}
    assert _replay_main(monkeypatch, raw) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["counts"] == {"expected": 15, "executed": 15, "asserted": 15}
    assert report["raw_sha256"] == hashlib.sha256(before[pathlib.Path(raw.name)]).hexdigest()
    assert before == {p.relative_to(raw.parent): p.read_bytes() for p in raw.parent.rglob("*") if p.is_file()}


@pytest.mark.parametrize("mutation", ["no_frames", "wrong_case", "wrong_observation", "unsupported"])
def test_replay_entry_does_not_trust_cached_pass(monkeypatch, tmp_path, capsys, mutation):
    raw = _published_sequence_copy(tmp_path)
    trace = json.loads(raw.read_bytes())
    assert trace["failures"] == [] and trace["counts"]["asserted"] == 15
    if mutation == "no_frames":
        trace["observation"]["frames"] = []
    elif mutation == "wrong_case":
        trace["case"] = numeric_capture.J00_CASE
    elif mutation == "wrong_observation":
        trace["observation"]["journey"] = numeric_capture.J00_CASE
    else:
        trace["case"] = trace["journey"] = trace["observation"]["journey"] = "unknown-sequence"
    raw.write_text(json.dumps(trace), encoding="utf-8")
    before = raw.read_bytes()
    assert _replay_main(monkeypatch, raw) == 1
    assert json.loads(capsys.readouterr().out)["failures"]
    assert raw.read_bytes() == before


def test_replay_entry_reports_predicate_exception_nonzero(monkeypatch, tmp_path, capsys):
    raw = _published_sequence_copy(tmp_path)
    def broken(*a):
        raise NameError("predicate failed")
    monkeypatch.setattr(numeric_capture, "_judge_sequence", broken)
    before = raw.read_bytes()
    assert _replay_main(monkeypatch, raw) == 1
    assert json.loads(capsys.readouterr().out)["failures"][0]["actual"] == "NameError: predicate failed"
    assert raw.read_bytes() == before
