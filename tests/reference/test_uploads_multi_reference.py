"""Frozen multiple-file upload evidence from the pinned Python 1.66.1 wire."""
import base64
import hashlib
import json
from pathlib import Path

from google.protobuf.json_format import MessageToDict
from streamlit.proto.BackMsg_pb2 import BackMsg
from streamlit.proto.ForwardMsg_pb2 import ForwardMsg

PUBLISHED = Path(__file__).parent / "reference-browser/uploads-multi"
RUST = Path(__file__).parents[1] / "browser/rust-uploads-multi"


def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def decoded_frames(capture):
    for frame in capture["frames"]:
        data = base64.b64decode(frame["base64"], validate=True)
        assert len(data) == frame["bytes"]
        message = BackMsg() if frame["direction"] == "client->server" else ForwardMsg()
        message.ParseFromString(data)
        assert MessageToDict(message, preserving_proto_field_name=True) == frame["message"]
        yield message


def semantic_stages(capture):
    assert capture["successful"] and "producer_error" not in capture
    assert [stage["name"] for stage in capture["stages"]] == ["load", "upload-two", "remove-alpha", "remove-beta"]
    for stage, expected in zip(capture["stages"], [0, 2, 1, 0]):
        report = json.loads(stage["code_text"])
        assert report["count"] == expected, f"{stage['name']}: {report}"
        assert len(stage["dom"]["chips"]) == expected, f"{stage['name']} chips: {stage['dom']['chips']}"
        assert stage["dom"]["exceptions"] == []
        yield stage, report


def test_frozen_python_reference_multi_upload_flow():
    raw = read(PUBLISHED / "trace.json")
    assert raw["runtime"] == "python" and raw["reference_version"] == "1.66.1"
    assert raw["profile_cleaned"] is True and raw["server_stopped"] is True
    for name, size in raw["inputs"].items():
        assert (PUBLISHED / "inputs" / name).stat().st_size == size
    reports = {stage["name"]: json.loads(stage["code_text"]) for stage, _ in semantic_stages(raw)}
    both = reports["upload-two"]["files"]
    assert [file["name"] for file in both] == ["alpha.txt", "beta.csv"]
    assert both[0]["size"] == 17 and both[0]["type"] == "text/plain" and both[0]["bytes_head"][:5] == [97, 108, 112, 104, 97]
    assert both[1]["size"] == 18 and both[1]["type"] == "text/csv" and both[1]["bytes_head"][:3] == [107, 101, 121]
    assert [file["name"] for file in reports["remove-alpha"]["files"]] == ["beta.csv"]
    # One batched URL request for both files, then per-file PUTs and a DELETE
    # when one file is removed.
    url_requests = [frame for frame in decoded_frames(raw) if frame.WhichOneof("type") == "file_urls_request"]
    assert len(url_requests) == 1, "both files ride one batched URL request"
    states = []
    for frame in decoded_frames(raw):
        if frame.WhichOneof("type") == "rerun_script":
            for widget in frame.rerun_script.widget_states.widgets:
                if widget.WhichOneof("value") == "file_uploader_state_value":
                    states.append([info.name for info in widget.file_uploader_state_value.uploaded_file_info])
    assert states == [["alpha.txt", "beta.csv"], ["beta.csv"], []], f"widget states: {states}"
    puts = [upload for upload in raw["uploads"] if upload["method"] == "PUT"]
    deletes = [upload for upload in raw["uploads"] if upload["method"] == "DELETE"]
    # Both files are PUT; removing a file issues a DELETE for it. The final
    # clear's trailing DELETE races with the recorder teardown (observed once
    # in, once out of the event window), so only the first is guaranteed.
    assert len(puts) == 2 and 1 <= len(deletes) <= 2, raw["uploads"]


def test_rust_capture_matches_the_reference_semantics():
    raw = read(RUST / "trace.json")
    assert raw["runtime"] == "rust" and "producer_error" not in raw
    assert raw["server_cleanup"] == "caller-owned"
    reports = {}
    for stage, expected in semantic_stages(raw):
        reports[stage["name"]] = json.loads(stage["code_text"])
        # The rust example renders the same JSON report shape as the python app
        # (name/size/bytes_head); the type field is python-only and absent.
        for file in json.loads(stage["code_text"])["files"]:
            assert set(file) == {"name", "size", "bytes_head"}
    assert [file["name"] for file in reports["upload-two"]["files"]] == ["alpha.txt", "beta.csv"]
    assert reports["upload-two"]["files"][0]["bytes_head"][:5] == [97, 108, 112, 104, 97]
    assert [file["name"] for file in reports["remove-alpha"]["files"]] == ["beta.csv"]
    url_requests = [frame for frame in decoded_frames(raw) if frame.WhichOneof("type") == "file_urls_request"]
    assert len(url_requests) == 1 and len(url_requests[0].file_urls_request.file_names) == 2
    states = []
    for frame in decoded_frames(raw):
        if frame.WhichOneof("type") == "rerun_script":
            for widget in frame.rerun_script.widget_states.widgets:
                if widget.WhichOneof("value") == "file_uploader_state_value" and widget.id.endswith("-multi-upload"):
                    states.append([info.name for info in widget.file_uploader_state_value.uploaded_file_info])
    # The rust example adds a single-file uploader whose (empty) state rides
    # every rerun too; only the multi-upload widget's states are compared.
    assert states == [["alpha.txt", "beta.csv"], ["beta.csv"], []], f"rust widget states: {states}"
    puts = [upload for upload in raw["uploads"] if upload["method"] == "PUT"]
    deletes = [upload for upload in raw["uploads"] if upload["method"] == "DELETE"]
    assert len(puts) == 2 and 1 <= len(deletes) <= 2, raw["uploads"]
