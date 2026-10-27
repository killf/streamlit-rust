"""Frozen native release relocation observations, without source identity gates."""

import base64
import hashlib
import json
from pathlib import Path
from urllib.parse import unquote, urlsplit

from streamlit.proto.BackMsg_pb2 import BackMsg
from streamlit.proto.ForwardMsg_pb2 import ForwardMsg


ROOT = Path(__file__).parents[1] / "browser/rust-library-portability"
REPO = Path(__file__).parents[2]


def read(name):
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


def test_portability_data_integrity_and_recorded_build_outcomes():
    manifest = read("manifest.json")
    assert len(manifest["files"]) == 75
    for item in manifest["files"]:
        path = (ROOT / item["file"]).resolve()
        assert path.is_relative_to(ROOT.resolve())
        data = path.read_bytes()
        assert len(data) == item["bytes"] and hashlib.sha256(data).hexdigest() == item["sha256"]
    outcome = read("build-results.json")
    assert outcome["protoc_red_exit_code"] == outcome["consumer_macro_exit_code"] == 101
    assert outcome["renamed_no_frontend_check_exit_code"] == outcome["release_build_exit_code"] == outcome["package_list_exit_code"] == 0
    assert outcome["release_source_directory_has_spaces"] and outcome["release_build_no_external_www"] and outcome["release_copy_byte_equal"]
    assert outcome["package_private_identity_included"] and outcome["no_new_library_dependencies"] is True
    # 只核对历史失败的真实内容，不要求当前 consumer 永远失败。
    assert "protoc failed" in (ROOT / "build-logs/before.log").read_text(encoding="utf-8-sig")
    error = (ROOT / "build-logs/consumer-macro-red.log").read_text(encoding="utf-8-sig")
    assert "tokio" in error and "env_logger" in error and "error[E0433]" in error
    assert "assets/frontend-index.html" in (ROOT / "build-logs/package-files.log").read_text(encoding="utf-8-sig").splitlines()
    assert (REPO / "streamlit/assets/frontend-index.html").read_bytes() == (REPO / "www/index.html").read_bytes()


def test_relocated_frontend_file_set_and_actual_http_bodies():
    trace, frontend = read("trace.json"), read("frontend-files.json")
    assert frontend["reference_version"] == "1.66.1" and len(frontend["files"]) == 347
    lock = json.loads((REPO / "upstream.lock.json").read_text(encoding="utf-8"))
    assert frontend["wheel_sha256"] == lock["artifacts"]["wheel"]["sha256"]
    expected = {item["file"]: item for item in frontend["files"]}
    assert len(expected) == 347
    for item in frontend["files"]:
        data = (REPO / "www" / item["file"]).read_bytes()
        assert len(data) == item["bytes"] and hashlib.sha256(data).hexdigest() == item["sha256"]
    for phase in ("source_bundle", "installed_bundle", "installed_bundle_after"):
        assert trace[phase] == {"wheel_files": 347, "actual_files": 347, "missing": [], "extra": [], "changed": []}
    assert len(trace["http"]) == 60
    observed = set()
    for response in trace["http"]:
        name = unquote(urlsplit(response["url"]).path).lstrip("/") or "index.html"
        assert name in expected and response["status"] == 200
        path = (ROOT / response["body"]).resolve()
        assert path.is_relative_to(ROOT.resolve())
        body = path.read_bytes()
        assert len(body) == response["bytes"] == expected[name]["bytes"]
        assert hashlib.sha256(body).hexdigest() == response["sha256"] == expected[name]["sha256"]
        observed.add(name)
    index = (REPO / "www/index.html").read_text(encoding="utf-8")
    boot = {part.removeprefix("./") for part in index.split('"') if part.startswith("./") and part.endswith((".js", ".css"))}
    assert boot and boot | {"index.html"} <= observed


def test_native_release_ui_same_socket_rerun_and_separate_log_check():
    trace = read("trace.json")
    assert trace["runtime"] == "rust-release" and trace["decoder"] == "streamlit 1.66.1" and trace["successful"]
    assert trace["static_override_removed"] and len(trace["websocket_request_ids"]) == 1 and len(trace["frames"]) == 24
    sessions, finishes, changes, checkbox_ids = [], [], [], set()
    for frame in trace["frames"]:
        data = base64.b64decode(frame["base64"], validate=True)
        assert len(data) == frame["bytes"] and hashlib.sha256(data).hexdigest() == frame["sha256"]
        event = trace["events"][frame["event_index"]]
        assert event["params"]["requestId"] == trace["websocket_request_ids"][0]
        assert event["params"]["response"]["payloadData"] == frame["base64"]
        if frame["direction"] == "client->server":
            message = BackMsg.FromString(data)
            changes.extend((w.id, w.bool_value) for w in message.rerun_script.widget_states.widgets if w.WhichOneof("value") == "bool_value")
        else:
            message = ForwardMsg.FromString(data)
            if message.HasField("new_session"):
                sessions.append(message.new_session.initialize.session_id)
            if message.HasField("script_finished"):
                finishes.append(message.script_finished)
            if message.delta.new_element.HasField("checkbox"):
                checkbox_ids.add(message.delta.new_element.checkbox.id)
    assert len(sessions) == 2 and sessions[0] == sessions[1] and finishes == [0, 0]
    assert len(checkbox_ids) == 1 and len(changes) == 1 and changes[0] == (next(iter(checkbox_ids)), False)
    methods = [item["method"] for item in trace["commands"]]
    assert methods.count("Input.dispatchMouseEvent") >= 2
    screenshots = [item["response"]["result"]["data"] for item in trace["commands"] if item["method"] == "Page.captureScreenshot"]
    dom_values = [item["response"]["result"]["result"]["value"] for item in trace["commands"] if item["method"] == "Runtime.evaluate"]
    dom_reads = [json.loads(value) if isinstance(value, str) else value for value in dom_values]
    assert len(trace["stages"]) == len(screenshots) == 2
    for stage, checked, screenshot in zip(trace["stages"], (True, False), screenshots):
        assert stage["dom"] in dom_reads
        assert stage["dom"]["exceptions"] == [] and stage["dom"]["checkboxes"] == [{"checked": checked}]
        assert f"Include unknown: {str(checked).lower()}" in stage["dom"]["text"]
        assert "Group by: category" in stage["dom"]["text"] and "Minimum amount: 0" in stage["dom"]["text"]
        assert (ROOT / stage["png"]).read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
        assert (ROOT / stage["png"]).read_bytes() == base64.b64decode(screenshot, validate=True)
    assert trace["cleanup"] == {"chrome_stopped": True, "server_stopped": True} and trace["cleanup_errors"] == []
    info = read("server-info-check.json")
    assert info["server_pid"] != trace["server_pid"] and info["health_status"] == 200 and info["server_stopped"]
    assert "executable sidecar" in (ROOT / "server-info.log").read_text(encoding="utf-8-sig")
    assert (ROOT / "server.log").read_bytes() == b""
