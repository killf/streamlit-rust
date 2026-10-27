"""Frozen public byte-download inputs, protobuf outputs and real HTTP responses."""

import base64
import hashlib
import json
from pathlib import Path

from google.protobuf.json_format import MessageToDict
from streamlit.proto.BackMsg_pb2 import BackMsg
from streamlit.proto.ForwardMsg_pb2 import ForwardMsg


ROOT = Path(__file__).parent / "reference-browser/download-boundaries"


def read(name):
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


def test_download_reference_data_integrity():
    manifest = read("manifest.json")
    assert manifest["reference_version"] == "1.66.1"
    for item in manifest["files"]:
        path = (ROOT / item["file"]).resolve()
        assert path.is_relative_to(ROOT.resolve())
        data = path.read_bytes()
        assert len(data) == item["bytes"]
        assert hashlib.sha256(data).hexdigest() == item["sha256"]


def test_public_download_inputs_link_to_frozen_wire_http_and_original_bytes():
    raw, compact = read("trace.json"), read("download-cases.json")
    inputs = read("cases-input.json")
    assert raw["reference_version"] == compact["reference_version"] == "1.66.1"
    assert raw["inputs"] == inputs and len(inputs) == 10
    assert raw["browser"] is None and raw["completed_all_cases"]
    assert raw["exceptions"] == [] and raw["handshake"]["status"] == 101
    assert raw["handshake"]["subprotocol"] == "streamlit"
    downloads, versions, finishes = [], [], []
    assert len(raw["frames"]) == 16
    for frame in raw["frames"]:
        data = base64.b64decode(frame["base64"], validate=True)
        assert len(data) == frame["bytes"]
        message = BackMsg() if frame["direction"] == "client->server" else ForwardMsg()
        message.ParseFromString(data)
        decoded = MessageToDict(message, preserving_proto_field_name=True)
        assert decoded == frame["message"]
        if "new_session" in decoded:
            versions.append(decoded["new_session"]["initialize"]["environment_info"]["streamlit_version"])
        if "script_finished" in decoded:
            finishes.append(decoded["script_finished"])
        element = decoded.get("delta", {}).get("new_element", {})
        if "download_button" in element:
            downloads.append({"delta_path": decoded["metadata"]["delta_path"], "fields": element["download_button"]})
    assert versions == ["1.66.1"] and finishes == ["FINISHED_SUCCESSFULLY"]
    assert downloads == raw["downloads"] and len(downloads) == 10
    responses = [item for item in raw["http"] if item["path"].startswith("/media/")]
    assert len(responses) == len(compact["cases"]) == 10
    assert raw["public_parameter_results"] == [{"label": item["label"], "accepted": True} for item in inputs]
    for original, wire, response, case in zip(inputs, downloads, responses, compact["cases"]):
        assert {key: case[key] for key in original} == original
        assert case["accepted"] and case["download_fields"] == wire["fields"]
        assert case["delta_path"] == wire["delta_path"]
        assert original["label"] == wire["fields"]["label"] == response["label"]
        assert case["url"] == wire["fields"]["url"] == response["path"]
        assert response["method"] == "GET" and response["status"] == case["status"] == 200
        assert response["headers"] == case["headers"]
        payload = base64.b64decode(original["payload_base64"], validate=True)
        assert payload == bytes(original["payload_bytes"]) == bytes(case["body_bytes"]) == bytes(response["body_bytes"])
        assert payload == base64.b64decode(response["body_base64"], validate=True) == base64.b64decode(case["body_base64"], validate=True)
        assert payload == (ROOT / f"{original['label']}.bin").read_bytes()
        assert len(payload) == response["body_length"] == case["body_length"]
        # 独立核对实际 URL 的数据地址；响应 charset 不能改变注册时的 MIME。
        mime = original["mime_option"] or "application/octet-stream"
        name = original["file_name_option"] or ""
        identity = hashlib.blake2b(f"{len(payload)}:".encode() + payload + mime.encode() + name.encode(), digest_size=16).hexdigest()
        assert case["url"].removeprefix("/media/").split(".", 1)[0] == identity
    cleanup = raw["cleanup"]
    assert cleanup == compact["cleanup"] and raw["cleanup_errors"] == compact["cleanup_errors"] == []
    assert cleanup["websocket_closed"] and cleanup["close_code"] == 1000 and cleanup["server_stopped"]
    assert cleanup["listener_count"] == "0" and cleanup["listener_check_exit_code"] == 0
    assert not cleanup["browser_started"]


def test_native_download_clicks_save_the_reference_names_and_bytes():
    native = Path(__file__).parents[1] / "browser/rust-download-boundaries"
    for item in json.loads((native / "manifest.json").read_text(encoding="utf-8"))["files"]:
        path = (native / item["file"]).resolve()
        assert path.is_relative_to(native.resolve())
        data = path.read_bytes()
        assert len(data) == item["bytes"] and hashlib.sha256(data).hexdigest() == item["sha256"]
    trace = json.loads((native / "trace.json").read_text(encoding="utf-8"))
    assert trace["runtime"] == "rust" and trace["reference_decoder"] == "1.66.1" and trace["successful"]
    cases = read("download-cases.json")["cases"]
    events = trace["events"]
    urls = {}
    for frame in trace["frames"]:
        data = base64.b64decode(frame["base64"], validate=True)
        assert len(data) == frame["bytes"]
        if frame["direction"] == "server->client":
            message = ForwardMsg.FromString(data)
            if message.delta.new_element.HasField("download_button"):
                button = message.delta.new_element.download_button
                urls[button.label] = button.url
    assert len(trace["stages"]) == 2
    for stage, expected, filename in zip(trace["stages"], (cases[0], cases[2]), ("streamlit_download.bin", "数据 é.csv")):
        window = events[stage["event_start"]:stage["event_end"]]
        begin = [e["params"] for e in window if e["method"] == "Browser.downloadWillBegin"]
        assert len(begin) == 1 and begin[0]["suggestedFilename"] == filename
        assert urls[stage["label"]] == expected["url"]
        assert begin[0]["url"] == trace["url"].rstrip("/") + expected["url"]
        complete = [e["params"] for e in window if e["method"] == "Browser.downloadProgress" and e["params"]["state"] == "completed"]
        assert len(complete) == 1 and complete[0]["guid"] == begin[0]["guid"]
        assert complete[0]["receivedBytes"] == complete[0]["totalBytes"] == stage["bytes"] == 18
        relative = Path(stage["browser_file"].replace("\\", "/"))
        assert relative == Path("downloads") / filename
        assert (native / relative).read_bytes() == bytes(expected["body_bytes"]) == base64.b64decode(stage["content_base64"], validate=True)
        assert stage["label"] in stage["dom"]["buttons"] and stage["dom"]["exceptions"] == []
        assert (native / stage["png"]).read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
        responses = [e["params"]["response"] for e in events if e["method"] == "Network.responseReceived" and e["params"]["response"]["url"] == begin[0]["url"]]
        assert len(responses) == 1 and responses[0]["status"] == 200
        headers = {key.lower(): value for key, value in responses[0]["headers"].items()}
        for name, value in expected["headers"]:
            if name.lower() in ("content-disposition", "content-type", "content-length", "accept-ranges"):
                assert headers[name.lower()] == value
    assert trace["cleanup"] == {"chrome_stopped": True, "server_stopped": True} and trace["cleanup_errors"] == []
