"""Frozen st.columns parameter evidence (python reference + rust browser)."""
import base64
import json
from pathlib import Path

from google.protobuf.json_format import MessageToDict
from streamlit.proto.BackMsg_pb2 import BackMsg
from streamlit.proto.ForwardMsg_pb2 import ForwardMsg

PYTHON = Path(__file__).parent / "reference-browser/columns-params"
RUST = Path(__file__).parents[1] / "browser/rust-columns-params"


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


def test_python_reference_column_semantics():
    raw = read(PYTHON / "trace.json")
    assert raw["runtime"] == "python" and raw["reference_version"] == "1.66.1"
    assert raw["successful"] and "producer_error" not in raw
    assert raw["server_cleanup"] == "collector-owned" and raw["cleanup"]["server_stopped"] is True
    assert raw["finishes"] == [0]
    wire = blocks(raw)
    assert len(wire) == 22, len(wire)
    containers = [element["fields"] for element in wire if element["kind"] == "add_block:flex_container"]
    columns = [element["fields"] for element in wire if element["kind"] == "add_block:column"]
    assert len(containers) == 7 and len(columns) == 15
    # Every container: the measured flex shape; only the gap varies.
    for index, gap in enumerate(["SMALL", "MEDIUM", "LARGE", "SMALL", "SMALL", "SMALL", "LARGE"]):
        assert containers[index] == {
            "gap_config": {"gap_size": gap},
            "scale": 1.0,
            "direction": "HORIZONTAL",
            "wrap": True,
            "align": "STRETCH",
        }, index
    # Equal columns carry double-precision weights; the gap rides each column.
    assert columns[0] == {"weight": 0.5, "gap_config": {"gap_size": "SMALL"}}
    assert columns[4] == {"weight": 0.3333333333333333, "gap_config": {"gap_size": "LARGE"}}
    assert columns[8] == {"weight": 0.5, "show_border": True, "gap_config": {"gap_size": "SMALL"}}
    assert columns[10] == {"weight": 0.5, "vertical_alignment": "CENTER", "gap_config": {"gap_size": "SMALL"}}
    assert columns[11] == {"weight": 0.5, "vertical_alignment": "BOTTOM", "gap_config": {"gap_size": "SMALL"}}
    assert columns[13] == {"weight": 0.75, "vertical_alignment": "CENTER", "show_border": True, "gap_config": {"gap_size": "LARGE"}}
    assert columns[14] == {"weight": 0.25, "vertical_alignment": "CENTER", "show_border": True, "gap_config": {"gap_size": "LARGE"}}


def test_rust_blocks_are_field_identical_to_the_reference():
    raw = read(RUST / "trace.json")
    assert raw["runtime"] == "rust" and raw["server_cleanup"] == "caller-owned"
    assert raw["finishes"] == [0]
    python = read(PYTHON / "trace.json")
    rust_blocks, python_blocks = blocks(raw), blocks(python)
    assert len(rust_blocks) == len(python_blocks) == 22
    for rust, reference in zip(rust_blocks, python_blocks):
        assert rust["kind"] == reference["kind"]
        assert rust["fields"] == reference["fields"], (rust["kind"], rust["fields"], reference["fields"])
