"""Frozen button/image creation-parameter evidence (python + rust)."""
import base64
import json
import re
from pathlib import Path

from google.protobuf.json_format import MessageToDict
from streamlit.proto.BackMsg_pb2 import BackMsg
from streamlit.proto.ForwardMsg_pb2 import ForwardMsg

PYTHON = Path(__file__).parent / "reference-browser/button-image-params"
RUST = Path(__file__).parents[1] / "browser/rust-button-image-params"


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


def comparable(capture):
    out = []
    for element in capture["elements"]:
        fields = dict(element["fields"])
        fields.pop("id", None)
        blob = json.dumps(fields, sort_keys=True)
        blob = re.sub(r"[0-9a-f]{32}", "<digest32>", blob)
        out.append((element["kind"], json.loads(blob)))
    return out


def test_python_reference_button_image_edges():
    raw = read(PYTHON / "trace.json")
    assert raw["runtime"] == "python" and raw["reference_version"] == "1.66.1"
    assert raw["successful"] and "producer_error" not in raw
    assert raw["server_cleanup"] == "collector-owned" and raw["cleanup"]["server_stopped"] is True
    assert raw["finishes"] == [0]
    widgets = [element["fields"] for element in raw["elements"] if element["kind"] != "heading"]
    primary, disabled, named, default, imgs = widgets
    assert primary["type"] == "primary" and primary["icon"] == ":material/star:"
    assert disabled["disabled"] is True and disabled["type"] == "secondary"
    # The download URL extension follows the explicit file name; with neither
    # name nor mime, raw bytes address as .bin. Only the url rides the message.
    assert named["url"].endswith(".txt") and "file_name" not in named and "mime" not in named
    assert default["url"].endswith(".bin")
    entries = imgs["imgs"]
    assert [entry["caption"] for entry in entries] == ["first", "second"]
    assert entries[0]["url"] == entries[1]["url"], "identical pixels share one content address"
    assert entries[0]["url"].endswith(".png")


def test_rust_matches_field_for_field():
    raw = read(RUST / "trace.json")
    assert raw["runtime"] == "rust" and raw["server_cleanup"] == "caller-owned"
    assert raw["finishes"] == [0]
    python = read(PYTHON / "trace.json")
    left, right = comparable(python), comparable(raw)
    assert len(left) == len(right) == 6
    for a, b in zip(left, right):
        assert a == b, (a, b)
