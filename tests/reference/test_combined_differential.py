"""The M7 cross-capability combined differential: python 1.66.1 vs rust.

The combined page interleaves every capability that already carries its own
frozen parity evidence. This differential asserts the full element sequence
and per-element equality, with exactly the two established normalizations:
Arrow payloads compare logically (rows/columns/types — the producer pandas
metadata blob differs by design), and the generic vega chart compares under
the accepted-A carriage (python top-level data == rust content-named dataset,
same logical rows, identical spec modulo the data key).
"""
import base64
import hashlib
import json
import re
from pathlib import Path

import pyarrow as pa
from google.protobuf.json_format import MessageToDict
from streamlit.proto.BackMsg_pb2 import BackMsg
from streamlit.proto.ForwardMsg_pb2 import ForwardMsg

PYTHON = Path(__file__).parent / "reference-browser/combined"
RUST = Path(__file__).parents[1] / "browser/rust-combined"


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


def logical_arrow(b64):
    table = pa.ipc.open_stream(base64.b64decode(b64, validate=True)).read_all()
    return {
        "num_rows": table.num_rows,
        "columns": [[field.name, str(field.type)] for field in table.schema],
        "rows": table.to_pylist(),
    }


def vega_payload(fields):
    """(logical rows, spec-without-data) under the accepted-A carriage."""
    if "data" in fields:
        arrow = fields["data"]["data"]
    else:
        dataset = fields["datasets"][0]
        arrow = dataset["data"]["data"]
    spec = json.loads(fields["spec"])
    rows = logical_arrow(arrow)
    if "datasets" in fields:
        # The rust carriage names the dataset and the spec references it.
        assert re.fullmatch(r"[0-9a-f]{32}", fields["datasets"][0]["name"])
        assert spec["data"] == {"name": fields["datasets"][0]["name"]}
    spec.pop("data", None)
    return rows, spec


def comparable(element):
    kind = element["kind"]
    fields = dict(element["fields"])
    if kind == "markdown":
        return kind, {"body_sha16": fields.pop("body_sha16")}
    if kind == "dataframe":
        arrow = fields.pop("arrow_data")["data"]
        return kind, {"logical": logical_arrow(arrow), **fields}
    if kind == "vega_lite_chart":
        rows, spec = vega_payload(fields)
        return kind, {"logical_rows": rows, "spec_without_data": spec}
    blob = json.dumps(fields, sort_keys=True)
    blob = re.sub(r"[0-9a-f]{32}", "<digest32>", blob)
    return kind, json.loads(blob)


def normalized(capture):
    return [comparable(element) for element in capture["elements"]]


def test_combined_page_sequences_and_fields_match():
    python = read(PYTHON / "trace.json")
    rust = read(RUST / "trace.json")
    for capture, runtime in ((python, "python"), (rust, "rust")):
        assert capture["successful"] and "producer_error" not in capture, runtime
        assert capture["finishes"] == [0], runtime
    assert python["runtime"] == "python" and python["reference_version"] == "1.66.1"
    assert rust["runtime"] == "rust" and rust["server_cleanup"] == "caller-owned"
    left, right = normalized(python), normalized(rust)
    assert [kind for kind, _ in left] == [kind for kind, _ in right], "the element sequence must match"
    for index, ((left_kind, left_fields), (right_kind, right_fields)) in enumerate(zip(left, right)):
        assert left_fields == right_fields, (index, left_kind, left_fields, right_fields)


def test_combined_page_covers_the_crossed_capabilities():
    python = read(PYTHON / "trace.json")
    kinds = {element["kind"] for element in python["elements"]}
    assert {"heading", "markdown", "code", "metric", "dataframe", "vega_lite_chart", "audio", "video", "toast"} <= kinds
    assert {"add_block:expandable", "add_block:popover", "add_block:tab_container", "add_block:tab", "add_block:flex_container", "add_block:column"} <= kinds
    assert "exception" not in kinds, "the combined page must run clean on the reference"
