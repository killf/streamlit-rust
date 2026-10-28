"""Frozen media/layout edge evidence (python reference + rust browser)."""
import base64
import json
import re
from pathlib import Path

from google.protobuf.json_format import MessageToDict
from streamlit.proto.BackMsg_pb2 import BackMsg
from streamlit.proto.ForwardMsg_pb2 import ForwardMsg

PYTHON = Path(__file__).parent / "reference-browser/media-more"
RUST = Path(__file__).parents[1] / "browser/rust-media-more"


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


def normalized(capture):
    out = []
    for element in capture["elements"]:
        fields = dict(element["fields"])
        blob = json.dumps(fields, sort_keys=True)
        blob = re.sub(r"[0-9a-f]{32}", "<digest32>", blob)
        out.append((element["kind"], json.loads(blob), element.get("url") or None, element.get("block", {})))
    return out


def test_python_reference_edges():
    raw = read(PYTHON / "trace.json")
    assert raw["runtime"] == "python" and raw["reference_version"] == "1.66.1"
    assert raw["successful"] and "producer_error" not in raw
    assert raw["server_cleanup"] == "collector-owned" and raw["cleanup"]["server_stopped"] is True
    assert raw["finishes"] == [0]
    elements = raw["elements"]
    assert [element["kind"] for element in elements] == ["video", "video", "add_block:popover", "add_block:tab_container", "add_block:tab", "add_block:tab"]
    # URL input rides the wire unchanged with the playback knobs.
    url_video = elements[0]["fields"]
    assert url_video["url"] == "https://example.com/clip.mp4"
    assert url_video["type"] == "NATIVE" and url_video["start_time"] == 1 and url_video["end_time"] == 5
    assert not url_video["url"].startswith("/media/")
    # The SRT subtitle became a .vtt media track on the byte-upload video.
    srt_video = elements[1]["fields"]
    assert srt_video["url"].startswith("/media/") and srt_video["url"].endswith(".mp4")
    track = srt_video["subtitles"][0]
    assert track["label"] == "en" and track["url"].endswith(".vtt")
    # popover wrap rides the message; tabs width/height ride the BLOCK.
    assert elements[2]["fields"] == {"label": "Wrapped", "type": "secondary", "open": False, "wrap": True}
    assert elements[2]["block"] == {"width_config": {"use_content": True}}
    assert elements[3]["fields"] == {"default_tab_index": 1}
    assert elements[3]["block"] == {"width_config": {"pixel_width": 500}, "height_config": {"pixel_height": 200}}


def test_rust_edges_match_field_for_field():
    raw = read(RUST / "trace.json")
    assert raw["runtime"] == "rust" and raw["server_cleanup"] == "caller-owned"
    assert raw["finishes"] == [0]
    python = read(PYTHON / "trace.json")
    left, right = normalized(python), normalized(raw)
    assert len(left) == len(right) == 6
    for a, b in zip(left, right):
        assert a == b, (a, b)
