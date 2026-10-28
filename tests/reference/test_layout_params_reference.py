"""Frozen layout/streaming parameter evidence (python reference + rust browser)."""
import base64
import json
from pathlib import Path

from google.protobuf.json_format import MessageToDict
from streamlit.proto.BackMsg_pb2 import BackMsg
from streamlit.proto.ForwardMsg_pb2 import ForwardMsg

PYTHON = Path(__file__).parent / "reference-browser/layout-params"
RUST = Path(__file__).parents[1] / "browser/rust-layout-params"


def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def frames(capture):
    for frame in capture["frames"]:
        data = base64.b64decode(frame["base64"], validate=True)
        assert len(data) == frame["bytes"]
        message = BackMsg() if frame["direction"] == "client->server" else ForwardMsg()
        message.ParseFromString(data)
        assert MessageToDict(message, preserving_proto_field_name=True) == frame["message"]
        yield message


def blocks(capture):
    return [element for element in capture["elements"] if element["kind"].startswith("add_block:")]


def test_python_reference_parameter_semantics():
    raw = read(PYTHON / "trace.json")
    assert raw["runtime"] == "python" and raw["reference_version"] == "1.66.1"
    assert raw["successful"] and "producer_error" not in raw
    assert raw["server_cleanup"] == "collector-owned" and raw["cleanup"]["server_stopped"] is True
    assert raw["finishes"] == [0]
    by_kind = {}
    for element in blocks(raw):
        by_kind.setdefault(element["kind"], []).append(element["fields"])
    expanders, popovers = by_kind["add_block:expandable"], by_kind["add_block:popover"]
    assert expanders[0] == {"label": "Compact collapsed", "expanded": False, "icon": ":material/add:", "type": "COMPACT"}
    assert expanders[1] == {"label": "Plain expanded", "expanded": True}
    assert popovers[0] == {"label": "Primary", "help": " popover help", "disabled": True, "type": "primary", "open": False}
    assert by_kind["add_block:tab_container"] == [{"default_tab_index": 1}]
    dialog = by_kind["add_block:dialog"]
    assert dialog[0] == {"title": "Wide", "dismissible": True, "width": "LARGE"}
    assert dialog[1] == {"title": "Wide", "dismissible": True, "width": "LARGE", "is_open": True}
    # status: RUNNING -> COMPLETE keeps the explicit expanded, ERROR update
    # without expanded re-streams WITHOUT the field (None clears).
    assert expanders[2] == {"label": "Working", "expanded": False, "icon": "spinner", "state": "RUNNING"}
    assert expanders[3] == {"label": "Done", "expanded": False, "icon": ":material/check:", "state": "COMPLETE"}
    assert expanders[4] == {"label": "Broken", "expanded": False, "icon": "spinner", "state": "RUNNING"}
    assert expanders[5] == {"label": "Broken", "icon": ":material/error:", "state": "ERROR"}
    toasts = [element["fields"] for element in raw["elements"] if element["kind"] == "toast"]
    assert toasts == [{"body": "short default", "duration": 4}, {"body": "long", "duration": 10}, {"body": "ms", "duration": 1500}]


def test_rust_blocks_are_field_identical_to_the_reference():
    raw = read(RUST / "trace.json")
    assert raw["runtime"] == "rust" and raw["server_cleanup"] == "caller-owned"
    assert raw["finishes"] == [0]
    python = read(PYTHON / "trace.json")
    rust_blocks, python_blocks = blocks(raw), blocks(python)
    assert len(rust_blocks) == len(python_blocks) == 14
    for rust, reference in zip(rust_blocks, python_blocks):
        assert rust["kind"] == reference["kind"], (rust["kind"], reference["kind"])
        assert rust["fields"] == reference["fields"], (rust["kind"], rust["fields"], reference["fields"])
