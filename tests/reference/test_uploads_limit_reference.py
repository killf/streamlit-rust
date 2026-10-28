"""Frozen size-limited upload evidence (python reference + rust browser)."""
import base64
import hashlib
import json
from pathlib import Path

from google.protobuf.json_format import MessageToDict
from streamlit.proto.BackMsg_pb2 import BackMsg
from streamlit.proto.ForwardMsg_pb2 import ForwardMsg

PYTHON = Path(__file__).parent / "reference-browser/uploads-limit"
RUST = Path(__file__).parents[1] / "browser/rust-uploads-limit"


def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def stage_reports(stage):
    """The limit section's JSON report: the last code block on both runtimes."""
    parsed = []
    for text in stage["code_texts"]:
        try:
            parsed.append(json.loads(text))
        except ValueError:
            continue
    assert parsed, "at least one JSON report must render"
    return parsed[-1]


def flow(capture):
    assert capture["successful"] and "producer_error" not in capture
    assert [stage["name"] for stage in capture["stages"]] == ["load", "select-oversize", "select-small"]
    reports = [stage_reports(stage) for stage in capture["stages"]]
    for stage in capture["stages"]:
        assert stage["dom"]["exceptions"] == []
    # The oversized file never reaches the app: no upload request leaves the
    # browser and the report stays at zero.
    assert reports[0] == {"count": 0, "files": []}
    assert reports[1] == {"count": 0, "files": []}
    puts = [upload for upload in capture["uploads"] if upload["method"] == "PUT"]
    assert len(puts) == 1, f"only the small file is uploaded: {capture['uploads']}"
    assert reports[2]["count"] == 1
    assert reports[2]["files"][0]["name"] == "small.txt"
    assert reports[2]["files"][0]["size"] == 14
    # The widget limit rides the wire element.
    limits = []
    for frame in capture["frames"]:
        message = BackMsg() if frame["direction"] == "client->server" else ForwardMsg()
        data = base64.b64decode(frame["base64"], validate=True)
        assert len(data) == frame["bytes"]
        message.ParseFromString(data)
        assert MessageToDict(message, preserving_proto_field_name=True) == frame["message"]
        if message.WhichOneof("type") == "delta" and message.delta.WhichOneof("type") == "new_element":
            element = message.delta.new_element
            if element.WhichOneof("type") == "file_uploader" and element.file_uploader.id.endswith("-limit-upload"):
                limits.append(element.file_uploader.max_upload_size_mb)
    assert limits and all(limit == 1 for limit in limits), f"wire limit: {limits}"
    return reports


def test_python_reference_blocks_oversize_before_upload():
    raw = read(PYTHON / "trace.json")
    assert raw["runtime"] == "python" and raw["reference_version"] == "1.66.1"
    assert raw["profile_cleaned"] is True and raw["server_stopped"] is True
    assert (PYTHON / "inputs/small.txt").read_bytes() == b"small payload\n"
    assert (PYTHON / "inputs/oversize-2m.bin").stat().st_size == 2 * 1024 * 1024
    flow(raw)


def test_rust_capture_matches_the_reference_semantics():
    raw = read(RUST / "trace.json")
    assert raw["runtime"] == "rust" and raw["server_cleanup"] == "caller-owned"
    flow(raw)
