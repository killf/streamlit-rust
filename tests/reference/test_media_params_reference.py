"""Frozen media playback-parameter evidence (python reference + rust browser)."""
import base64
import hashlib
import json
from pathlib import Path

from google.protobuf.json_format import MessageToDict
from streamlit.proto.BackMsg_pb2 import BackMsg
from streamlit.proto.ForwardMsg_pb2 import ForwardMsg

PYTHON = Path(__file__).parent / "reference-browser/media-params"
RUST = Path(__file__).parents[1] / "browser/rust-media-params"


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


def exceptions_of(capture):
    out = []
    for message in frames(capture):
        if message.WhichOneof("type") == "delta" and message.delta.WhichOneof("type") == "new_element":
            element = message.delta.new_element
            if element.WhichOneof("type") == "exception":
                out.append(element.exception)
    return out


def test_python_reference_playback_parameters():
    raw = read(PYTHON / "trace.json")
    assert raw["runtime"] == "python" and raw["reference_version"] == "1.66.1"
    assert raw["successful"] and "producer_error" not in raw
    assert raw["server_cleanup"] == "collector-owned" and raw["cleanup"]["server_stopped"] is True
    elements = raw["elements"]
    assert [element["kind"] for element in elements] == ["audio", "audio", "audio", "video", "video", "video"]
    audio_default, audio_params, audio_xwav, video_default, video_params, video_subtitles = (element["fields"] for element in elements)
    # The measured defaults carry only the stretch width.
    assert audio_default == {"width_config": {"use_stretch": True}}
    assert video_default == {"type": "NATIVE", "width_config": {"use_stretch": True}}
    # Times truncate to whole seconds; loop/autoplay ride along; the id is the
    # $$ID-<32hex>-None shape on autoplay only.
    assert audio_params["start_time"] == 1 and audio_params["end_time"] == 3
    assert audio_params["loop"] is True and audio_params["autoplay"] is True
    assert audio_params["id"].startswith("$")
    assert audio_params["id"].startswith("$" * 2 + "ID-") and audio_params["id"].endswith("-None") and len(audio_params["id"]) == 42
    assert video_params["muted"] is True and video_params["start_time"] == 2 and video_params["end_time"] == 4
    assert video_params["id"].startswith("$$ID-")
    # The format decides the address suffix: audio/wav -> .wav, audio/x-wav -> bare.
    assert elements[0]["url"].endswith(".wav") and elements[2]["url"].count(".") == 0
    # Subtitles ride one track with a .vtt media URL.
    track = video_subtitles["subtitles"][0]
    assert track["label"] == "en" and track["url"].endswith(".vtt")
    # Content addressing: identical bytes share one URL.
    assert elements[0]["url"] == elements[1]["url"] and elements[3]["url"] == elements[5]["url"]
    # The invalid subtitle renders the framework's API exception.
    exceptions = exceptions_of(raw)
    assert len(exceptions) == 1
    assert exceptions[0].type == "streamlit.errors.StreamlitAPIException"
    assert exceptions[0].message.startswith("Failed to process the provided subtitle 'en'")
    assert exceptions[0].message_is_markdown and exceptions[0].is_streamlit_exception
    assert raw["finishes"] == [0]


def test_rust_capture_matches_field_for_field_and_url_for_url():
    raw = read(RUST / "trace.json")
    assert raw["runtime"] == "rust" and raw["server_cleanup"] == "caller-owned"
    python = read(PYTHON / "trace.json")
    for rust_element, python_element in zip(raw["elements"], python["elements"]):
        assert rust_element["kind"] == python_element["kind"]
        fields = dict(rust_element["fields"])
        reference = dict(python_element["fields"])
        # The autoplay id hash and the subtitle-coordinate hash are per-runtime
        # identity (the dialog precedent); everything else must be equal.
        fields.pop("id", None), reference.pop("id", None)
        if "subtitles" in fields:
            for track in fields["subtitles"]:
                track["url"] = track["url"].rsplit(".", 1)[-1]
            for track in reference["subtitles"]:
                track["url"] = track["url"].rsplit(".", 1)[-1]
        assert fields == reference, f"{rust_element['index']}: {fields} vs {reference}"
        # Content addressing makes the payload URLs identical cross-runtime.
        assert rust_element["url"] == python_element["url"], rust_element["index"]
        assert rust_element["url"].endswith(".wav") if rust_element["index"] in (0, 1) else True
    assert raw["finishes"] == [0]
    exceptions = exceptions_of(raw)
    assert len(exceptions) == 1
    assert exceptions[0].type == "streamlit.errors.StreamlitAPIException"
    assert exceptions[0].message == exceptions_of(python)[0].message
    assert exceptions[0].message_is_markdown and exceptions[0].is_streamlit_exception
