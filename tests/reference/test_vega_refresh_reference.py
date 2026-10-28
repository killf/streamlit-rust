"""Frozen generic Vega same-shape refresh evidence (accepted A)."""
import base64
import hashlib
import json
from pathlib import Path

from google.protobuf.json_format import MessageToDict
from streamlit.proto.BackMsg_pb2 import BackMsg
from streamlit.proto.ForwardMsg_pb2 import ForwardMsg

AFTER = Path(__file__).parents[1] / "browser/rust-vega-refresh-after"


def read(path):
    return json.loads((AFTER / path).read_text(encoding="utf-8-sig"))


def test_frozen_after_files_are_complete():
    manifest = read("manifest.json")
    assert manifest["scope"] == "frozen rust capture data only; the caller-owned rust server is not archived"
    for item in manifest["files"]:
        data = (AFTER / item["file"]).read_bytes()
        assert len(data) == item["bytes"] and hashlib.sha256(data).hexdigest() == item["sha256"]


def test_visible_aria_follows_same_shape_wire_updates():
    raw = read("trace.json")
    assert raw["runtime"] == "rust" and raw["successful"] and "producer_error" not in raw
    assert raw["cleanup"]["chrome_stopped"] is True and raw["cleanup_errors"] == []
    assert [stage["name"] for stage in raw["stages"]] == ["load", "change-to-8", "ordinary-rerun", "change-back-to-3"]
    for frame in raw["frames"]:
        data = base64.b64decode(frame["base64"], validate=True)
        assert len(data) == frame["bytes"] and hashlib.sha256(data).hexdigest() == frame["sha256"]
        message = BackMsg() if frame["direction"] == "client->server" else ForwardMsg()
        message.ParseFromString(data)
        assert MessageToDict(message, preserving_proto_field_name=True) == frame["message"]
    # The generic chart's dataset name is the md5 of its IPC bytes and rides
    # the spec's data.name; 3 -> 8 changes it, an ordinary rerun keeps it,
    # 3 again restores it. The visible ARIA marks follow the wire at every
    # stage — exactly what the pre-fix baseline missed.
    import re

    names = []
    for stage, count in zip(raw["stages"], [3, 8, 8, 3]):
        charts = [chart for chart in stage["charts"] if len(chart["datasets"]) == 1]
        assert charts, f"{stage['name']}: the generic chart must emit its named dataset"
        dataset = charts[-1]["datasets"][0]
        assert re.fullmatch(r"[0-9a-f]{32}", dataset["name"]) is not None
        spec = json.loads(charts[-1]["spec"])
        assert spec["data"] == {"name": dataset["name"]}
        assert dataset["rows"] == [{"kind": "a", "count": count}, {"kind": "b", "count": 7}]
        names.append(dataset["name"])
        aria = stage["dom"]["charts"][1]["aria"]
        assert f"kind: a; count: {count}" in aria, f"{stage['name']}: the visible mark must show the wire value"
        assert "kind: b; count: 7" in aria
        assert stage["dom"]["exceptions"] == []
    assert names[0] == names[3] and names[1] == names[2] and names[0] != names[1], \
        "the dataset identity must follow the values across the four stages"
