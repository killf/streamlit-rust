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

class _ReconnectCDP(_IsolationCDP):
    branch = "ui-probe"

    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.auto_at = None
        self.auto_sent = False

    def call(self,method,params=None):
        params = params or {}
        if method == "Runtime.evaluate" and "__stWs.close" in params.get("expression",""):
            self.log.append((self.label,"close-live-socket"))
            if self.branch == "hook-failed":
                return {"id":24,"result":{"result":{"type":"string","value":"no socket"}}}
            self.events.append({"method":"Network.webSocketClosed","params":{
                "requestId":f"{self.label}-socket-{self.epoch}","timestamp":self.tick()}})
            self.epoch += 1
            for name,extra in (
                ("webSocketCreated",{"url":"ws://test/_stcore/stream"}),
                ("webSocketWillSendHandshakeRequest",{"request":{"headers":{"Sec-WebSocket-Protocol":"streamlit,token,old-session"}}}),
                ("webSocketHandshakeResponseReceived",{"response":{"status":101,"headers":{"Sec-WebSocket-Protocol":"streamlit"}}}),
            ):
                self.events.append({"method":"Network."+name,"params":dict(requestId=f"{self.label}-socket-{self.epoch}",timestamp=self.tick(),**extra)})
            self.auto_at = self.clock+2
            return {"id":24,"result":{"result":{"type":"string","value":"closed"}}}
        if method == "Performance.getMetrics" and self.auto_at is not None and self.clock >= self.auto_at and not self.auto_sent and self.branch in ("natural","pending-natural","late-natural-finish"):
            self.auto_sent = True
            self.complete("natural")
            if self.branch in ("pending-natural","late-natural-finish"):
                self.events.pop()  # Real pending-run model: no success finish.
        return super().call(method,params)


def _reconnect_driver(monkeypatch,tmp_path,branch="ui-probe",fault=None,*,slow=False):
    _ReconnectCDP.instances = [];_ReconnectCDP.log = [];_ReconnectCDP.branch = branch
    created,closed,selected = [],[],[]
    def http(url,method="GET"):
        if "/json/list" in url:
            return _ORIGINAL_ISOLATION_TARGETS+[{"id":i,"type":"page","url":"about:blank","webSocketDebuggerUrl":"ws://"+i} for i in created if i not in closed]
        if "/json/new?" in url:
            if fault=="old-id":return {"id":"preexisting-user-target","webSocketDebuggerUrl":"ws://user"}
            created.append("owned-j09")
            return {"id":"owned-j09","webSocketDebuggerUrl":"ws://owned-j09"}
        raise AssertionError(url)
    class Response:
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def read(self):return b"Target is closing"
    def urlopen(url,**kwargs):
        assert url.endswith("/json/close/owned-j09")
        closed.append("owned-j09");return Response()
    def select(page,option):
        selected.append(option);page.cdp.dom["selectbox_value"]=option
        return fault!="action-failed"
    def wait(state,start,mode,filename=None,timeout=45):
        if fault=="no-response" or (mode=="natural" and branch=="pending-natural"):
            raise RuntimeError("missing target server response")
        if mode=="natural":
            if branch=="late-natural-finish":
                from streamlit.proto.ForwardMsg_pb2 import ForwardMsg
                msg=ForwardMsg();msg.script_finished=0
                state['recorder'].events.append({'method':'Network.webSocketFrameReceived','params':{
                    'requestId':f"{state['namespace']}-socket-1",'timestamp':state['recorder'].tick(),
                    'response':{'opcode':2,'payloadData':base64.b64encode(msg.SerializeToString()).decode()}}})
            return numeric_capture._reconnect_window(numeric_capture.frames_of(state["recorder"]),start,natural=True)
        wiremode="upload" if filename else "pulse" if mode.startswith("pulse-") else "select" if mode.startswith("probe-") else mode
        state["recorder"].complete(wiremode)
        return numeric_capture._run_window(numeric_capture.frames_of(state["recorder"]),start)
    monkeypatch.setattr(numeric_capture,"http_json",http)
    monkeypatch.setattr(numeric_capture.urllib.request,"urlopen",urlopen)
    monkeypatch.setattr(numeric_capture,"CDP",_ReconnectCDP)
    monkeypatch.setattr(numeric_capture,"Page",_IsolationPage)
    monkeypatch.setattr(numeric_capture,"_reconnect_select",lambda page,action:select(page,action['option']))
    monkeypatch.setattr(numeric_capture,"_reconnect_wait",wait)
    # Transport-only models have no Arrow/rendered grid. Their rejecting
    # criterion is unchanged; recorded render snapshots test real readiness.
    monkeypatch.setattr(numeric_capture,"_reconnect_ready",lambda *args:None)
    monkeypatch.setattr(numeric_capture.time,"sleep",lambda _:None)
    # Keep transport models explicitly unverified, independent of concurrent
    # checker implementation. These are not synthetic browser-pass proofs.
    monkeypatch.setattr(numeric_capture,"j09_checks",lambda **kwargs:[
        dict(journey=numeric_capture.J09_CASE,step=numeric_capture.J09_CASE,check=key,
             ok=False,expected='independent full proof',actual='transport model only')
        for key in numeric_capture.J09_REQUIRED])
    # Transport/ordering model only. This explicitly injected reader double
    # sends no ref_hash and is never a production fallback/cache algorithm.
    materialize=lambda page:[dict(f) for f in page['frames']]
    args=SimpleNamespace(label="j09-model",port=60667,url="http://test/",scope="driver model only",binary="",build_base="",journey=numeric_capture.J09_CASE)
    if slow:
        args.journey=numeric_capture.J09_SLOW_CASE;args.port=60923;args.url="http://127.0.0.1:8604/";args.scope="PYTHON SIDE ONLY"
        monkeypatch.setattr(numeric_capture,"_slow_configuration",lambda *a:dict(effective_seconds=120))
        judge=numeric_capture._judge_sequence
        # Transport model has no fixture IPC/rendered chart, so only bypass
        # the separately tested base proof here. Never manufacture S4 PASS.
        monkeypatch.setattr(numeric_capture,"_judge_sequence",lambda name,obs:
            dict(failures=[]) if name==numeric_capture.J09_CASE else judge(name,obs))
        def hold(state,obs,save):
            obs['hold'].update(samples=[dict(cdp_timestamp=1,driver_monotonic=1,utc='model')])
            state['rule_active']=True;save()
            if fault=='hold-failed':raise RuntimeError('model interrupted hold')
        def recover(state,obs):
            state['rule_active']=False
            state['recorder'].call('Runtime.evaluate',{'expression':'window.__stWs.close()'})
            obs['recovery']['requested_session_id']='model-old'
        def read(state,obs):
            start=len(numeric_capture.frames_of(state['recorder']))
            state['recorder'].complete('natural')
            if fault=='rerun-overlap':
                # A spontaneous server-only result, not the model helper's
                # default synthetic client-state + response exchange.
                state['recorder'].events.pop(-3)
            obs['recovery'].update(observed_session_id='model-new',recovery_action='rerun' if fault=='rerun-overlap' else 'observe')
            if fault=='rerun-overlap':state['rerun_input_timestamp']=0.
            return numeric_capture._reconnect_window(numeric_capture.frames_of(state['recorder']),start,natural=True)
        monkeypatch.setattr(numeric_capture,'_slow_hold',hold)
        monkeypatch.setattr(numeric_capture,'_slow_reconnect',recover)
        monkeypatch.setattr(numeric_capture,'_slow_recovery_read',read)
        monkeypatch.setattr(numeric_capture,'_slow_recovery_paint',lambda *a:None)
        def clear(state,obs,*,block):
            assert block is False
            obs['commands'].append({'model_cleanup_only':True});state['rule_active']=False
            return len(obs['commands'])-1
        monkeypatch.setattr(numeric_capture,'_slow_network_command',clear)
    result=numeric_capture.run_reconnect_journey(args,tmp_path,materialize=materialize)
    trace=json.loads((tmp_path/'trace-data-loop.json').read_bytes())
    return result,trace,created,closed,selected


@pytest.mark.parametrize("branch", ["natural","ui-probe","late-natural-finish"])
def test_j09_driver_exact_shared_plan_preserves_unverified_stub(monkeypatch,tmp_path,branch):
    result,trace,created,closed,selected = _reconnect_driver(monkeypatch,tmp_path,branch)
    obs=trace['observation']
    assert trace['summary']['producer_error'] is None
    assert result==1 and trace['counts']=={'expected':20,'executed':20,'asserted':0}
    assert created==closed==['owned-j09']
    plan='natural' if branch=='late-natural-finish' else branch
    assert tuple(p['name'] for p in obs['phases'])==numeric_capture.J09_PHASES[plan]
    assert len(obs['screenshots'])==len(numeric_capture.J09_PHASES[plan])
    assert selected==(['region','category'] if branch=='ui-probe' else [])
    epochs=obs['page']['epochs']
    assert [e['id'] for e in epochs]==['e0','e1','e2']
    assert epochs[0]['document_event']==epochs[1]['document_event']!=epochs[2]['document_event']
    assert epochs[1]['navigation_timestamp'] is epochs[1]['navigation_event'] is None
    reconnect=next(p for p in obs['phases'] if p['name']==numeric_capture.J09_PREFIX[-1])
    auto=reconnect['auto_observation'];assert auto['end_timestamp']-auto['start_timestamp']>=numeric_capture.J09_AUTO_OBSERVE_SECONDS
    closed_event=obs['page']['events'][reconnect['close']['closed_event']]
    assert closed_event['method']=='Network.webSocketClosed'
    assert closed_event['params']['requestId']==reconnect['close']['request_id']
    pulses=[p for p in obs['phases'] if p['action']['action']=='pulse']
    assert [p['dom_after']['pulses'] for p in pulses]==['1','2']
    assert reconnect['dom_after']['pulses']=='2' and obs['phases'][-1]['dom_after']['pulses']=='0'
    if branch=='ui-probe':
        assert reconnect['ipc']=={'table':None,'chart':None}
        assert reconnect['checkpoint']==pulses[-1]['checkpoint']
        probe=next(p for p in obs['phases'] if p['name']=='probe-region')
        assert probe['action_timestamp'] > auto['end_timestamp']
    if branch=='late-natural-finish':
        finish=obs['page']['frames'][reconnect['checkpoint']['finish_frame']]
        assert auto['start_timestamp']+numeric_capture.J09_AUTO_OBSERVE_SECONDS < finish['timestamp'] <= auto['end_timestamp']
    assert reconnect['action_timestamp']==reconnect['close']['command_timestamp']
    log=_ReconnectCDP.log
    assert log.index(('j09-model','start'))<log.index(('j09-model','Page.addScriptToEvaluateOnNewDocument'))<log.index(('j09-model','Page.navigate'))
    assert sum(m=='Page.navigate' for _,m in log)==sum(m=='Page.reload' for _,m in log)==1
    assert not any('emulateNetwork' in m for _,m in log)


@pytest.mark.parametrize("branch,fault", [("pending-natural",None),("hook-failed",None),("ui-probe","old-id"),("ui-probe","action-failed"),("ui-probe","no-response")])
def test_j09_failure_never_conceals_pending_natural_run_or_loses_raw(monkeypatch,tmp_path,branch,fault):
    result,trace,created,closed,selected=_reconnect_driver(monkeypatch,tmp_path,branch,fault)
    assert result==1 and trace['summary']['producer_error']
    assert created==closed
    if branch=='pending-natural':
        assert not selected and trace['observation']['plan'] is None
        assert any(f['decoded'].get('type')=='new_session' and f['connection']==1 for f in trace['observation']['page']['frames'])
    if fault=='old-id':
        assert not _ReconnectCDP.instances
    else:
        assert trace['observation']['page']['events']==_ReconnectCDP.instances[0].take()
        assert trace['observation']['diagnostics']['last_dom_read']['dom']['script_runs'] is not None


def test_j09_missing_canonical_reader_fails_closed(monkeypatch,tmp_path):
    # No production adapter may silently reuse the per-connection J06 cache.
    with pytest.raises(RuntimeError,match='not wired'):
        numeric_capture._reconnect_frames({}, {'frames':[]})


@pytest.mark.parametrize('opening_ok',[True,False])
def test_j09_probe_uses_visible_clicks_for_both_dropdown_and_option(opening_ok):
    class Page:
        def __init__(self):self.clicks=[];self.reads=[]
        def click_visible(self,expression):
            self.clicks.append(expression)
            return opening_ok
        def option_rect(self,option):
            assert len(self.clicks)==1
            self.reads.append(option);return {'x':10,'y':20}
    page=Page();action=numeric_capture.J09_ACTIONS['probe-region']
    assert numeric_capture._reconnect_select(page,action) is opening_ok
    assert len(page.clicks)==(2 if opening_ok else 1)
    assert page.reads==(['region'] if opening_ok else [])


def _j09_cache_page(messages):
    page=dict(namespace='cache-model',frames=[],events=[],epochs=[
        dict(connection=0,request_id='r0',document_event=0),
        dict(connection=1,request_id='r1',document_event=0),
        dict(connection=2,request_id='r2',document_event=100)])
    for i,(connection,message) in enumerate(messages):
        data=message.SerializeToString();encoded=base64.b64encode(data).decode()
        page['events'].append({'method':'Network.webSocketFrameReceived','params':{
            'requestId':'r'+str(connection),'timestamp':float(i+1),
            'response':{'opcode':2,'payloadData':encoded}}})
        page['frames'].append(dict(namespace=page['namespace'],direction='server->client',connection=connection,
            request_id='r'+str(connection),timestamp=float(i+1),base64=encoded,bytes=len(data),
            sha256=hashlib.sha256(data).hexdigest(),decoded=numeric_capture.summarise_forward(data)))
    return page


def test_j09_wires_real_canonical_reader_same_document_cache_and_raw_immutable():
    from streamlit.proto.ForwardMsg_pb2 import ForwardMsg
    original=ForwardMsg();original.hash='cached-body';original.metadata.cacheable=True
    original.delta.new_element.text.body='retained body'
    reference=ForwardMsg();reference.ref_hash='cached-body';reference.metadata.delta_path.append(2)
    page=_j09_cache_page([(0,original),(1,reference)])
    before=json.dumps(page,sort_keys=True)
    result=numeric_capture._reconnect_frames({'materialize':numeric_capture._j09_materialize_frames},page)
    assert result[1]['decoded']['delta']['body']=='retained body'
    assert page['frames'][1]['decoded']['type']=='ref_hash'
    assert json.dumps(page,sort_keys=True)==before
    assert numeric_capture.run_reconnect_journey.__kwdefaults__['materialize'] is numeric_capture._j09_materialize_frames


@pytest.mark.parametrize('case',['new-document','missing','expired'])
def test_j09_reader_rejects_foreign_missing_or_stale_ref_without_fallback(case):
    from streamlit.proto.ForwardMsg_pb2 import ForwardMsg
    initial=ForwardMsg();initial.new_session.config.max_cached_message_age=0
    original=ForwardMsg();original.hash='h';original.metadata.cacheable=True;original.delta.new_element.text.body='body'
    reference=ForwardMsg();reference.ref_hash='h';reference.metadata.delta_path.append(0)
    finish=ForwardMsg();finish.script_finished=0
    messages=([(0,original),(2,reference)] if case=='new-document' else
              [(1,reference)] if case=='missing' else [(0,initial),(0,original),(0,finish),(1,reference)])
    page=_j09_cache_page(messages);before=json.dumps(page,sort_keys=True)
    with pytest.raises(ValueError,match='cache reference'):
        numeric_capture._reconnect_frames({'materialize':numeric_capture._j09_materialize_frames},page)
    assert json.dumps(page,sort_keys=True)==before


def test_j09_natural_newsession_without_client_state_is_real_run_not_ui_probe():
    frames=[_frame('server->client',{'type':'new_session','new_session':{'script_run_id':'natural'}},0),
            _frame('server->client',{'type':'script_finished','script_finished':{'status':0}},1)]
    assert numeric_capture._run_window(frames,0) is None
    assert numeric_capture._reconnect_window(frames,0,natural=True)['finish']==1
    for bad in ('failed','cross-connection','pending'):
        variant=json.loads(json.dumps(frames))
        if bad=='failed':variant[1]['decoded']['script_finished']['status']=1
        elif bad=='cross-connection':variant[1]['connection']=2
        else:variant.pop()
        assert numeric_capture._reconnect_window(variant,0,natural=True) is None


@pytest.mark.parametrize('stage',['phase-entry','after-observe','pre-probe-read'])
@pytest.mark.parametrize('outcome',['pending','failed','success'])
def test_j09_exact_late_server_only_race_never_sends_probes_over_natural(monkeypatch,tmp_path,stage,outcome):
    from streamlit.proto.ForwardMsg_pb2 import ForwardMsg
    injected=[];flags={'stored':False}
    def inject(state):
        rec=state['recorder']
        new=ForwardMsg();new.new_session.script_run_id='review-late-pending-server-only'
        status=ForwardMsg();status.session_status_changed.script_is_running=True
        messages=[new,status]
        if outcome!='pending':
            for label,value in (('Script runs',rec.dom['script_runs']+1),('Pulses',2)):
                msg=ForwardMsg();msg.delta.new_element.text.body=f'{label}: {value}';messages.append(msg)
            finish=ForwardMsg();finish.script_finished=0 if outcome=='success' else 1;messages.append(finish)
        for msg in messages:
            event={'method':'Network.webSocketFrameReceived','params':{
                'requestId':f'{rec.label}-socket-{rec.epoch}','timestamp':rec.tick(),
                'response':{'opcode':2,'payloadData':base64.b64encode(msg.SerializeToString()).decode()}}}
            rec.events.append(event);injected.append(event)
        if outcome=='success':rec.dom['script_runs']+=1
    old_phase=numeric_capture._reconnect_phase
    def phase(state,name,*args,**kwargs):
        if stage=='phase-entry' and name==numeric_capture.J09_PREFIX[-1] and not injected:inject(state)
        result=old_phase(state,name,*args,**kwargs)
        if stage=='after-observe' and name==numeric_capture.J09_PREFIX[-1] and not injected:inject(state)
        return result
    monkeypatch.setattr(numeric_capture,'_reconnect_phase',phase)
    old_store=numeric_capture._reconnect_store_phase
    def store(state,observation,out,arrows,index,name,*args,**kwargs):
        result=old_store(state,observation,out,arrows,index,name,*args,**kwargs)
        if name==numeric_capture.J09_PREFIX[-1]:flags['stored']=True
        return result
    monkeypatch.setattr(numeric_capture,'_reconnect_store_phase',store)
    old_read=numeric_capture._isolation_read
    def read(state):
        if stage=='pre-probe-read' and flags['stored'] and not injected:inject(state)
        return old_read(state)
    monkeypatch.setattr(numeric_capture,'_isolation_read',read)
    code,trace,created,closed,selected=_reconnect_driver(monkeypatch,tmp_path,'ui-probe')
    assert code==1 and selected==[] and created==closed==['owned-j09']
    assert all(e['method']=='Network.webSocketFrameReceived' for e in injected)
    events=trace['observation']['page']['events']
    assert all(e in events for e in injected)
    assert events==_ReconnectCDP.instances[0].take()
    refresh=sum(m=='Page.reload' for _,m in _ReconnectCDP.log)
    if outcome=='success':
        assert trace['summary']['producer_error'] is None and refresh==1
        assert trace['observation']['plan']=='natural'
        assert tuple(p['name'] for p in trace['observation']['phases'])==numeric_capture.J09_PHASES['natural']
        observed=trace['observation']['phases'][-2]
        assert observed['dom_after']['script_runs']=='5' and observed['dom_after']['pulses']=='2'
    else:
        assert trace['summary']['producer_error'] and refresh==0
        assert trace['observation']['diagnostics']['last_dom_read']


@pytest.mark.parametrize('bad',[False,0,{}, {'error':{'message':'failed'}},
    {'id':24,'result':{'result':{'type':'string','value':'closed'}},'error':{}},
    {'id':24,'result':{'result':{'type':'string','value':'closed'},'exceptionDetails':{}}}])
def test_j09_full_cdp_hook_failure_cannot_be_truthy_success(monkeypatch,tmp_path,bad):
    old=_ReconnectCDP.call
    def call(self,method,params=None):
        result=old(self,method,params)
        return bad if method=='Runtime.evaluate' and '__stWs.close' in (params or {}).get('expression','') else result
    monkeypatch.setattr(_ReconnectCDP,'call',call)
    code,trace,_,_,selected=_reconnect_driver(monkeypatch,tmp_path)
    assert code==1 and trace['summary']['producer_error'] and selected==[]
    assert not any(m=='Page.reload' for _,m in _ReconnectCDP.log)
    assert trace['observation']['diagnostics']['close']['evaluation_result']==bad


def test_j09_full_cdp_hook_success_retains_real_preflight_shape(monkeypatch,tmp_path):
    _,trace,_,_,_=_reconnect_driver(monkeypatch,tmp_path)
    phase=next(p for p in trace['observation']['phases'] if p['name']==numeric_capture.J09_PREFIX[-1])
    assert phase['close']['evaluation_result']=={'id':24,'result':{'result':{'type':'string','value':'closed'}}}
    assert trace['observation']['page']['events'][phase['close']['closed_event']]['method']=='Network.webSocketClosed'


def _recorded_j09_ready_case(name,tmp_path):
    fixture=json.loads((HERE/'j09-readiness-snapshots.json').read_bytes())
    assert fixture['source_raw_sha256']=='e711edc1817af52ceb010528146f3ae6c769df2315b7e769d926a26131f55648'
    case=next(c for c in fixture['cases'] if c['name']==name)
    frames=case['selected_decoded_frames'];window=numeric_capture._run_window(frames,0)
    assert window
    if name=='refresh':
        good=json.loads(json.dumps(case['dom_after']))
    else:
        published=json.loads((HERE/'rust-journeys/j06-sequence/trace-data-loop.json').read_bytes())['observation']['phases']
        phase,tab=('b-group-region','b') if name=='probe-region' else ('a-pulse-3','a')
        good=json.loads(json.dumps(next(p for p in published if p['name']==phase)['views'][tab]['dom_after']))
        # Model a fully painted target using actual recorded J06 table/chart
        # geometry and this J09 target's measured counters. This is a unit
        # positive control, never a fabricated actual J09 browser result.
        for key in ('script_runs','pulses'):good[key]=case['dom_after'][key]
    state={'arrows':numeric_capture._ArrowFiles(tmp_path),'ipc_dir':str(tmp_path)}
    return state,frames,window,case['dom_after'],good


@pytest.mark.parametrize('name',['probe-region','probe-category'])
def test_j09_recorded_wrong_phase_table_is_not_ready_even_with_new_counters(tmp_path,name):
    state,frames,window,stale,good=_recorded_j09_ready_case(name,tmp_path)
    with pytest.raises(ValueError,match='DOM cells differ'):
        numeric_capture._reconnect_ready(state,frames,window,stale,name)
    numeric_capture._reconnect_ready(state,frames,window,good,name)


@pytest.mark.parametrize('fault',['wrong-same-count-value','wrong-controls','zero-height-bars','wrong-schema'])
def test_j09_full_paint_readiness_rejects_partial_or_inconsistent_result(tmp_path,fault):
    state,frames,window,_,good=_recorded_j09_ready_case('probe-region',tmp_path)
    if fault=='wrong-same-count-value':good['table_cells'][2]='999999'
    elif fault=='wrong-controls':good['checkbox_checked']=False
    elif fault=='zero-height-bars':good['chart_marks']='|'.join('M0,0h10v0Z' for _ in range(6))
    else:
        delta=next(f['decoded']['delta'] for f in frames if f['decoded'].get('delta',{}).get('element')=='dataframe')
        delta['arrow']['schema']=delta['arrow']['schema'].replace('int64','double')
    with pytest.raises(ValueError):numeric_capture._reconnect_ready(state,frames,window,good,'probe-region')


def test_j09_refresh_requires_defaults_info_and_actual_old_result_disappearance(tmp_path):
    state,frames,window,_,good=_recorded_j09_ready_case('refresh',tmp_path)
    numeric_capture._reconnect_ready(state,frames,window,good,'refresh')
    for key,value in (('table_present',True),('table_cells',['Books']),('chart_marks','M0,0h10v10Z'),
                      ('alerts',[]),('uploaded_files',['sales_basic.csv']),('selectbox_value','region')):
        dom=dict(good,**{key:value})
        with pytest.raises(ValueError):numeric_capture._reconnect_ready(state,frames,window,dom,'refresh')


@pytest.mark.parametrize('never_paints',[False,True])
def test_j09_real_wait_polls_full_recorded_result_and_keeps_last_dom(monkeypatch,tmp_path,never_paints):
    state,frames,window,stale,good=_recorded_j09_ready_case('probe-region',tmp_path)
    class Paint:
        reads=0
        current=None
        def bring_to_front(self):pass
        def state_digest(self):
            self.current=stale if never_paints or self.reads==0 else good
            self.reads+=1
            return dict(self.current)
        def files_dom(self):return {'chips':self.current['uploaded_files']}
    page=Paint();recorder=_IsolationCDP('','paint-model')
    _IsolationCDP.clock=frames[-1]['timestamp']+1
    state.update(page=page,recorder=recorder,namespace=frames[0]['namespace'],materialize=lambda p:p['frames'])
    monkeypatch.setattr(numeric_capture,'_reconnect_tab',lambda state:{'frames':frames})
    monkeypatch.setattr(numeric_capture.time,'sleep',lambda _:None)
    if never_paints:
        with pytest.raises(RuntimeError,match='DOM timeout'):
            numeric_capture._reconnect_wait(state,0,'probe-region',timeout=.01)
        assert state['last_dom_read']['dom']['table_cells']==stale['table_cells']
    else:
        assert numeric_capture._reconnect_wait(state,0,'probe-region',timeout=2)==window
        assert page.reads>=2 and state['last_dom_read']['dom']['table_cells']==good['table_cells']


def test_j09_final_fresh_phase_read_cannot_commit_stale_table(monkeypatch,tmp_path):
    state,frames,_,stale,_=_recorded_j09_ready_case('probe-region',tmp_path)
    recorder=_IsolationCDP('','fresh-read');recorder.dom=stale
    _IsolationCDP.clock=frames[-1]['timestamp']+1
    state.update(page=_IsolationPage(recorder),recorder=recorder,materialize=lambda p:p['frames'])
    monkeypatch.setattr(numeric_capture,'_reconnect_tab',lambda state:{'frames':frames,'epochs':[{'id':'e1'}]})
    with pytest.raises(ValueError,match='DOM cells differ'):
        numeric_capture._reconnect_phase(state,'probe-region',{},None,frames[0]['timestamp']-.001,None,state['arrows'])
    assert state['last_dom_read']['dom']['table_cells']==stale['table_cells']


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


@pytest.mark.parametrize('branch',['ui-probe','natural'])
def test_slow_transport_appends_shared_suffix_to_one_original_stream(monkeypatch,tmp_path,branch):
    result,trace,created,closed,selected=_reconnect_driver(monkeypatch,tmp_path,branch,slow=True)
    n=numeric_capture;obs=trace['observation']
    assert trace['summary']['producer_error'] is None
    assert result==1  # Mechanical transport mocks are not an expiry oracle.
    assert tuple(p['name'] for p in obs['phases'])==n.J09_PHASES[branch]+n.J09_SLOW_SUFFIX
    assert len(obs['screenshots'])==len(obs['phases'])
    assert created==closed==['owned-j09']
    assert len([p for p in obs['phases'] if p['action']['action']=='upload'])==2
    assert len([p for p in obs['phases'] if p['action']['action']=='pulse'])==3
    assert len([p for p in obs['phases'] if p['action']['action']=='refresh'])==1
    assert obs['recovery']['oracle_status']=='unverified'
    base=n._j09_slow_base_view(obs)
    assert tuple(p['name'] for p in base['phases'])==n.J09_PHASES[branch]
    assert len(base['page']['frames'])<len(obs['page']['frames'])
    assert [e['id'] for e in obs['page']['epochs']]==['e0','e1','e2','e3']
    assert obs['page']['epochs'][2]['document_event']==obs['page']['epochs'][3]['document_event']


def test_slow_failed_hold_saves_original_stream_and_cleans_owned_target(monkeypatch,tmp_path):
    result,trace,created,closed,_=_reconnect_driver(monkeypatch,tmp_path,fault='hold-failed',slow=True)
    assert result==1 and 'model interrupted hold' in trace['summary']['producer_error']
    assert trace['observation']['page']['frames']
    assert trace['observation']['hold']['samples']
    assert trace['observation']['screenshots']
    assert trace['observation']['commands']==[{'model_cleanup_only':True}]
    assert created==closed==['owned-j09']


def test_slow_driver_final_overlap_is_nonzero_with_full_original_raw(monkeypatch,tmp_path):
    result,trace,created,closed,_=_reconnect_driver(monkeypatch,tmp_path,fault='rerun-overlap',slow=True)
    assert result==1 and 'final Rerun attribution' in trace['summary']['producer_error']
    assert 'overlaps Rerun' in trace['summary']['producer_error']
    assert len(trace['observation']['phases'])==len(numeric_capture.J09_PHASES['ui-probe'])+len(numeric_capture.J09_SLOW_SUFFIX)
    recorder=_ReconnectCDP.instances[-1]
    page=trace['observation']['page']
    assert page['events']==recorder.take()
    assert page['frames'][-1]['base64']==recorder.take()[-1]['params']['response']['payloadData']
    assert created==closed==['owned-j09']


def _slow_config_input(tmp_path):
    rows=[]
    for kind in ('process','config','effective-config','app-source'):
        path=tmp_path/(kind+'.txt');path.write_bytes((kind+'\r\n').encode())
        rows.append(dict(kind=kind,file=path.name,sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
    data=dict(runtime='unit-transport-only',effective_seconds=120,process_id=123,
              process_command_line='unit transport fixture; not actual runtime provenance',evidence=rows)
    path=tmp_path/'configuration.json';path.write_text(json.dumps(data),encoding='utf-8')
    return path,data


@pytest.mark.parametrize('fault',['short-ttl','missing-kind','duplicate-kind','wrong-hash','no-process'])
def test_slow_configuration_rejects_unproven_or_short_ttl(tmp_path,fault):
    path,data=_slow_config_input(tmp_path)
    if fault=='short-ttl':data['effective_seconds']=1
    elif fault=='missing-kind':data['evidence'].pop()
    elif fault=='duplicate-kind':data['evidence'][-1]['kind']='process'
    elif fault=='wrong-hash':data['evidence'][0]['sha256']='0'*64
    else:data['process_command_line']=''
    path.write_text(json.dumps(data),encoding='utf-8');out=tmp_path/'out';out.mkdir()
    with pytest.raises(ValueError):numeric_capture._slow_configuration(SimpleNamespace(ttl_configuration=str(path),scope='PYTHON SIDE ONLY'),out)


def test_slow_configuration_preserves_evidence_bytes_and_portable_paths(tmp_path):
    path,data=_slow_config_input(tmp_path);out=tmp_path/'out';out.mkdir()
    saved=numeric_capture._slow_configuration(SimpleNamespace(ttl_configuration=str(path),scope='PYTHON SIDE ONLY'),out)
    assert (out/'ttl-evidence/input.json').read_bytes()==path.read_bytes()
    for original,record in zip(data['evidence'],saved['evidence']):
        assert not pathlib.Path(record['file']).is_absolute()
        assert (out/record['file']).read_bytes()==(tmp_path/original['file']).read_bytes()


def test_slow_no101_uses_real_interval_not_misleading_summary():
    event=lambda stamp,status:dict(method='Network.webSocketHandshakeResponseReceived',params=dict(timestamp=stamp,response=dict(status=status)))
    tab=dict(events=[event(1,101),event(20,503),event(30,400)])
    numeric_capture._slow_no_101(tab,10,145)  # Initial101 is not a retry.
    tab['events'].append(event(40,101))
    with pytest.raises(RuntimeError,match='HTTP101'):numeric_capture._slow_no_101(tab,10,145)


@pytest.mark.parametrize('active,window',[(True,None),(True,{'run':0,'end':1})])
def test_slow_recovery_never_reruns_an_active_natural_run(monkeypatch,active,window):
    n=numeric_capture;calls=[]
    monkeypatch.setattr(n,'_slow_recovery_status',lambda s:(active,window,[]))
    monkeypatch.setattr(n,'_slow_rerun',lambda s:calls.append('forbidden'))
    monkeypatch.setattr(n,'_isolation_read',lambda s:{})
    obs=dict(recovery={})
    with pytest.raises(RuntimeError,match='no complete'):n._slow_recovery_read({},obs,timeout=0)
    assert calls==[] and obs['recovery']['recovery_action']=='observe'


def _s4_real_menu_model(monkeypatch,*,inject=None,natural='pending'):
    """Real Page scroll/rect/input + real full-ledger reader, mock CDP only."""
    n=numeric_capture;frames=[];clicks=[]
    class Transport:
        def __init__(self):self.clock=10.;self.item=False;self.rect_read=False;self.metrics_after_rect=0;self.ident=0
        def add(self,decoded,direction='server->client'):
            frames.append(dict(connection=3,request_id='e3',timestamp=self.clock+.001,
                               direction=direction,decoded=decoded))
        def natural(self,completion):
            self.add(dict(type='new_session',new_session=dict(script_run_id='natural',session_id='observed')))
            self.add(dict(type='session_status_changed',session_status_changed=dict(script_is_running=True)))
            self.add(dict(type='delta',delta=dict(element='markdown',body='Script runs: 1')))
            self.add(dict(type='delta',delta=dict(element='markdown',body='Pulses: 0')))
            if completion!='pending':self.add(dict(type='script_finished',script_finished=dict(status=0 if completion=='complete' else 1)))
        def call(self,method,params=None):
            params=params or {};self.ident+=1
            if method=='Performance.getMetrics':
                self.clock+=.01
                if self.rect_read:
                    self.metrics_after_rect+=1
                    # After the outer post-geometry guard, inside the final
                    # Input boundary's actual clock/pump operation.
                    if inject=='input-clock' and self.metrics_after_rect==2 and not frames:self.natural(natural)
                return dict(id=self.ident,result=dict(metrics=[dict(name='Timestamp',value=self.clock)]))
            if method=='Runtime.evaluate':
                expression=params['expression'];self.item='stMainMenuItem-rerun' in expression
                if 'getBoundingClientRect' in expression:
                    if self.item:
                        self.rect_read=True
                        if inject=='rect' and not frames:self.natural(natural)
                    value=dict(x=10,y=10)
                else:value=True
                return dict(id=self.ident,result=dict(result=dict(type='object' if isinstance(value,dict) else 'boolean',value=value)))
            assert method=='Input.dispatchMouseEvent'
            clicks.append(('rerun-item' if self.item else 'open-menu',params['type']))
            if self.item and inject=='pressed-response' and params['type']=='mousePressed' and not frames:self.natural(natural)
            if self.item and params['type']=='mouseReleased':
                if inject=='release-response':self.natural('complete')
                self.add(dict(type='rerun_script',rerun_script=dict(widget_states=[])),'client->server')
                if inject!='release-response':self.natural('complete')
            return dict(id=self.ident,result={})
    recorder=Transport();page=n.Page(recorder)
    state=dict(page=page,recorder=recorder,target_id='owned-s4',commands=[])
    def sleep(seconds):
        if inject=='scroll' and recorder.item and not frames:recorder.natural(natural)
    monkeypatch.setattr(n.time,'sleep',sleep)
    monkeypatch.setattr(n,'_reconnect_tab',lambda s:dict(epochs=[dict(request_id='e3')]))
    monkeypatch.setattr(n,'_reconnect_frames',lambda s,t:frames)
    return state,frames,clicks


@pytest.mark.parametrize('injection',['scroll','rect','input-clock'])
@pytest.mark.parametrize('completion',['pending','failed','complete'])
def test_slow_real_helper_suppresses_rerun_at_final_dispatch_race(monkeypatch,injection,completion):
    n=numeric_capture;state,frames,clicks=_s4_real_menu_model(monkeypatch,inject=injection,natural=completion)
    assert n._slow_rerun(state) is False
    assert clicks==[('open-menu','mousePressed'),('open-menu','mouseReleased')]
    active,window,same=n._slow_recovery_status(state)
    assert active and same is frames
    assert (window is not None)==(completion=='complete')
    assert not any(c['method']=='Input.dispatchMouseEvent' and 'rerun_input_timestamp' in state for c in state['commands'])
    assert state['page'].cdp is state['recorder'] and 'click' not in state['page'].__dict__


def test_slow_real_helper_menu_commands_and_input_responses_are_preserved(monkeypatch):
    n=numeric_capture;state,frames,clicks=_s4_real_menu_model(monkeypatch)
    assert n._slow_rerun(state) is True
    assert clicks==[('open-menu','mousePressed'),('open-menu','mouseReleased'),('rerun-item','mousePressed'),('rerun-item','mouseReleased')]
    commands=state['commands']
    assert len(commands)==8  # scroll + rect + press/release for each menu button
    assert sum(c['method']=='Runtime.evaluate' for c in commands)==4
    for command in commands:
        assert command['target_id']=='owned-s4' and command['response']['id']>0
        assert command['started_monotonic']<=command['finished_monotonic']
        assert command['cdp_before']<=command['cdp_after']
    active,window,_=n._slow_recovery_status(state)
    assert active and window
    n._slow_rerun_binding(state,frames,window)


def test_slow_natural_start_after_press_aborts_without_release(monkeypatch):
    state,frames,clicks=_s4_real_menu_model(monkeypatch,inject='pressed-response')
    with pytest.raises(RuntimeError,match='partially dispatched'):numeric_capture._slow_rerun(state)
    assert clicks[-1]==('rerun-item','mousePressed')
    assert ('rerun-item','mouseReleased') not in clicks
    assert frames and state['commands'][-1]['response']


def test_slow_full_ledger_rejects_natural_result_overlapping_released_input(monkeypatch):
    n=numeric_capture;state,frames,_=_s4_real_menu_model(monkeypatch,inject='release-response')
    assert n._slow_rerun(state) is True
    active,window,_=n._slow_recovery_status(state)
    assert active and window
    with pytest.raises(RuntimeError,match='overlaps Rerun'):n._slow_rerun_binding(state,frames,window)


def test_slow_full_ledger_rejects_extra_delta_after_finished_ui_run(monkeypatch):
    n=numeric_capture;state,frames,_=_s4_real_menu_model(monkeypatch)
    assert n._slow_rerun(state) is True
    _,window,_=n._slow_recovery_status(state)
    state['recorder'].add(dict(type='delta',delta=dict(element='markdown',body='late unrelated output')))
    with pytest.raises(RuntimeError,match='overlaps Rerun'):n._slow_rerun_binding(state,frames,window)


@pytest.mark.parametrize('response',[{}, {'id':3,'error':{'message':'input rejected'}},
                                    {'id':3,'result':{'exceptionDetails':{'text':'query threw'}}}])
def test_slow_menu_retains_failed_raw_command_response(monkeypatch,response):
    n=numeric_capture
    state=dict(target_id='owned',commands=[],recorder=SimpleNamespace(call=lambda *a:response))
    monkeypatch.setattr(n,'_isolation_clock',lambda r:12.)
    with pytest.raises(RuntimeError,match='menu command failed'):
        n._S4MenuRecorder(state).call('Runtime.evaluate',{'expression':'actual menu query'})
    assert state['commands'][0]['response'] is response
    assert state['commands'][0]['params']=={'expression':'actual menu query'}


def test_slow_network_command_exact_rule_bracket_and_cleanup(monkeypatch):
    n=numeric_capture;calls=[];clock=iter([5.,6.,7.,8.])
    recorder=SimpleNamespace(call=lambda m,p:calls.append((m,p)) or {'id':3,'result':{'ruleIds':['opaque']}})
    tab=dict(epochs=[dict(request_id='actual')],events=[dict(method='Network.webSocketCreated',params=dict(requestId='actual',url='ws://127.0.0.1:8604/_stcore/stream'))])
    monkeypatch.setattr(n,'_reconnect_tab',lambda s:tab)
    monkeypatch.setattr(n,'_isolation_clock',lambda r:next(clock))
    state=dict(target_id='owned',recorder=recorder);obs=dict(commands=[])
    assert n._slow_network_command(state,obs,block=True)==0
    assert state['rule_active'] is True
    assert n._slow_network_command(state,obs,block=False)==1
    assert state['rule_active'] is False
    assert obs['commands'][0]['cdp_before']==5 and obs['commands'][0]['cdp_after']==6
    assert calls[0]==('Network.emulateNetworkConditionsByRule',{'matchedNetworkConditions':[dict(urlPattern='ws://127.0.0.1:8604/_stcore/stream',offline=True,latency=0,downloadThroughput=-1,uploadThroughput=-1)]})
    assert calls[1][1]=={'matchedNetworkConditions':[]}


@pytest.mark.parametrize('cdp_rate',[.5,1.,2.])
def test_slow_hold_waits_both_real_clocks_and_checkpoints_original_events(monkeypatch,cdp_rate):
    """Synthetic clock only tests scheduling, never supplies browser proof."""
    n=numeric_capture;clock={'value':10.};saved=[]
    events=[dict(method='Network.webSocketHandshakeResponseReceived',params=dict(timestamp=1,response=dict(status=101))),
            dict(method='Network.webSocketClosed',params=dict(requestId='old',timestamp=10.))]
    tab=dict(epochs=[dict(request_id='old')],events=events)
    recorder=SimpleNamespace(call=lambda *a:{'id':24,'result':{'result':{'type':'string','value':'closed'}}})
    state=dict(recorder=recorder);obs=dict(hold=dict(samples=[]))
    monkeypatch.setattr(n,'_slow_network_command',lambda *a,**k:0)
    monkeypatch.setattr(n,'_reconnect_tab',lambda s:tab)
    monkeypatch.setattr(n,'_isolation_clock',lambda r:10+(clock['value']-10)*cdp_rate)
    monkeypatch.setattr(n.time,'monotonic',lambda:clock['value'])
    monkeypatch.setattr(n.time,'sleep',lambda seconds:clock.update(value=clock['value']+seconds))
    n._slow_hold(state,obs,lambda:saved.append(list(events)))
    assert obs['hold']['samples'][-1]['driver_monotonic']>=145
    assert obs['hold']['samples'][-1]['cdp_timestamp']>=145
    assert len(saved)>=135 and saved[-1]==events
    assert obs['hold']['close']['evaluation_result']['id']==24


def test_slow_profile_refuses_original_chrome_before_any_browser_access(monkeypatch,tmp_path):
    n=numeric_capture
    monkeypatch.setattr(n,'http_json',lambda *a,**k:pytest.fail('must not access original Chrome'))
    args=SimpleNamespace(journey=n.J09_SLOW_CASE,port=60667,url='http://127.0.0.1:8604/',scope='PYTHON SIDE ONLY',binary='',build_base='')
    assert n.run_reconnect_journey(args,tmp_path)==1
    trace=json.loads((tmp_path/'trace-data-loop.json').read_bytes())
    assert 'separately owned Chrome60923' in trace['summary']['producer_error']


def _slow_paint_model(tmp_path):
    frames=[dict(decoded=dict(type='new_session',new_session=dict(session_id='actually-observed-model')))]
    frames.extend(dict(decoded=dict(type='delta',delta=dict(element='markdown',body=body)))
                  for body in ('Script runs: 1','Pulses: 0'))
    frames.append(dict(decoded=dict(type='script_finished',status=0)))
    window=dict(start=0,run=0,end=4,finish=3)
    dom=dict(script_runs='1',pulses='0',table_present=False,chart_present=False,table_cells=[],chart_marks=[],
             alerts=[],exceptions=[],uploaded_files=['actual-unknown-recovery-file.csv'])
    state=dict(arrows=numeric_capture._ArrowFiles(tmp_path),ipc_dir=str(tmp_path))
    return state,frames,window,dom


def test_slow_completed_natural_run_is_readonly_without_guessing_file_state(monkeypatch,tmp_path):
    n=numeric_capture;state,frames,window,dom=_slow_paint_model(tmp_path)
    monkeypatch.setattr(n,'_slow_recovery_status',lambda s:(True,window,frames))
    monkeypatch.setattr(n,'_slow_rerun',lambda s:pytest.fail('completed natural run must remain readonly'))
    monkeypatch.setattr(n,'_isolation_read',lambda s:dom)
    obs=dict(recovery=dict(oracle_status='unverified'))
    assert n._slow_recovery_read(state,obs)==window
    assert obs['recovery']==dict(oracle_status='unverified',observed_session_id='actually-observed-model',recovery_action='observe')
    assert dom['uploaded_files']==['actual-unknown-recovery-file.csv']


@pytest.mark.parametrize('fault',['old-counter','stale-table','stale-chart','stale-alert'])
def test_slow_recovery_paint_rejects_stale_render_without_oracle_defaults(tmp_path,fault):
    state,frames,window,dom=_slow_paint_model(tmp_path)
    if fault=='old-counter':dom['script_runs']='99'
    elif fault=='stale-table':dom['table_present']=True
    elif fault=='stale-chart':dom['chart_marks']=[dict(path='old')]
    else:dom['alerts']=['old error']
    with pytest.raises(ValueError):numeric_capture._slow_recovery_paint(state,frames,window,dom)


def test_slow_recovery_no_natural_run_uses_one_real_menu_action(monkeypatch,tmp_path):
    n=numeric_capture;state,frames,clicks=_s4_real_menu_model(monkeypatch)
    _,_,_,dom=_slow_paint_model(tmp_path)
    state.update(arrows=n._ArrowFiles(tmp_path),ipc_dir=str(tmp_path))
    monkeypatch.setattr(n,'_isolation_read',lambda s:dom)
    obs=dict(recovery=dict(oracle_status='unverified'))
    result=n._slow_recovery_read(state,obs)
    assert result['finish']==len(frames)-1 and obs['recovery']['recovery_action']=='rerun'
    assert clicks.count(('rerun-item','mouseReleased'))==1


def test_slow_epoch_ignores_failed_attempt_but_preserves_its_raw_lifecycle(monkeypatch):
    n=numeric_capture
    doc=dict(method='Network.requestWillBeSent',params=dict(type='Document',timestamp=1))
    events=[doc]
    for request,status in [('old',101),('failed-retry',503),('new',101)]:
        events.extend([dict(method='Network.webSocketWillSendHandshakeRequest',params=dict(requestId=request)),
                       dict(method='Network.webSocketHandshakeResponseReceived',params=dict(requestId=request,response=dict(status=status)))])
    tab=dict(events=events,frames=[dict(request_id='old',connection=0),dict(request_id='new',connection=1)])
    monkeypatch.setattr(n,'_isolation_tab',lambda s:dict(tab))
    result=n._reconnect_tab(dict(slow=True,navigations=[1]))
    assert [e['request_id'] for e in result['epochs']]==['old','new']
    assert [e['connection'] for e in result['epochs']]==[0,1]
    assert result['events']==events and len(result['events'])==7


def test_slow_native_configuration_requires_native_kinds_and_preserves_process_hash(tmp_path):
    path,data=_slow_config_input(tmp_path)
    rows=[]
    for kind in ('process','build','config','server-source','entry-source'):
        file=tmp_path/(kind+'.json')
        file.write_text(json.dumps({'kind':kind,'binary_sha256':'unit-model-only'}),encoding='utf-8')
        rows.append(dict(kind=kind,file=file.name,sha256=hashlib.sha256(file.read_bytes()).hexdigest()))
    data['evidence']=rows;path.write_text(json.dumps(data),encoding='utf-8')
    out=tmp_path/'native';out.mkdir()
    saved=numeric_capture._slow_configuration(SimpleNamespace(ttl_configuration=str(path),scope='RUST'),out)
    process=next(item for item in saved['evidence'] if item['kind']=='process')
    assert json.loads((out/process['file']).read_bytes())['binary_sha256']=='unit-model-only'
    bad=tmp_path/'wrong-runtime';bad.mkdir()
    with pytest.raises(ValueError):
        numeric_capture._slow_configuration(SimpleNamespace(ttl_configuration=str(path),scope='PYTHON SIDE ONLY'),bad)


def test_slow_cli_dispatches_existing_recorder_with_explicit_profile(monkeypatch,tmp_path):
    n=numeric_capture;called=[]
    def runner(args,out):
        called.append((args.journey,args.port,args.ttl_configuration,out));return 1
    monkeypatch.setattr(n,'require_decoder',lambda:None)
    monkeypatch.setitem(n.JOURNEY_RUNNERS,n.J09_SLOW_CASE,runner)
    monkeypatch.setattr(sys,'argv',['numeric_capture.py','--journey',n.J09_SLOW_CASE,'--case','data-loop',
        '--port','60923','--url','http://127.0.0.1:8604/','--ttl-configuration','actual-provenance.json','--out',str(tmp_path)])
    assert n.main()==1
    assert called==[(n.J09_SLOW_CASE,60923,'actual-provenance.json',tmp_path)]


def test_slow_replay_remains_readonly_and_uses_full_single_capture(monkeypatch,tmp_path,capsys):
    n=numeric_capture
    raw=tmp_path/'raw.json'
    obs=dict(journey=n.J09_SLOW_CASE,contract=n.J09_SLOW_CONTRACT,page={'events':['full-original-tail']})
    raw.write_text(json.dumps(dict(journey=n.J09_SLOW_CASE,case=n.J09_SLOW_CASE,observation=obs)),encoding='utf-8')
    original=raw.read_bytes();seen=[]
    def criterion(*,observation):
        seen.append(observation)
        return [dict(journey=n.J09_SLOW_CASE,step=n.J09_SLOW_CASE,check=key,ok=False,actual='unverified',expected='actual slow proof') for key in n.J09_SLOW_REQUIRED]
    monkeypatch.setattr(n,'j09_slow_checks',criterion)
    monkeypatch.setattr(n,'http_json',lambda *a,**k:pytest.fail('no browser/network in replay'))
    monkeypatch.setattr(n,'require_decoder',lambda:None)
    assert n.replay_sequence(raw)==1
    assert seen[0]['page']['events']==['full-original-tail']
    assert json.loads(capsys.readouterr().out)['counts']==dict(expected=20,executed=20,asserted=0)
    assert raw.read_bytes()==original
