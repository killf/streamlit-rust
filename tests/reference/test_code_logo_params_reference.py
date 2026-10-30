"""Frozen code/skeleton/logo parameter evidence (python + rust)."""
import base64
import copy
import json
from pathlib import Path

import pytest

from google.protobuf.json_format import MessageToDict
from streamlit.proto.BackMsg_pb2 import BackMsg
from streamlit.proto.ForwardMsg_pb2 import ForwardMsg

PYTHON = Path(__file__).parent / "reference-browser/code-logo-params"
RUST = Path(__file__).parents[1] / "browser/rust-code-logo-params"


def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def frames(capture):
    for frame in capture["frames"]:
        assert frame["direction"] in ("client->server", "server->client")
        data = base64.b64decode(frame["base64"], validate=True)
        assert len(data) == frame["bytes"]
        message = BackMsg() if frame["direction"] == "client->server" else ForwardMsg()
        message.ParseFromString(data)
        assert MessageToDict(message, preserving_proto_field_name=True) == frame["message"]
        yield message


def assert_capture(capture):
    elements, finishes = [], []
    for message in frames(capture):
        if not isinstance(message, ForwardMsg):
            continue
        kind = message.WhichOneof("type")
        if kind == "script_finished":
            finishes.append(message.script_finished)
        if kind != "delta":
            continue
        assert message.delta.WhichOneof("type") == "new_element"
        element = message.delta.new_element
        element_kind = element.WhichOneof("type")
        assert element_kind is not None
        view = getattr(element, element_kind)
        elements.append({"index": len(elements), "kind": element_kind,
                         "fields": MessageToDict(view, preserving_proto_field_name=True),
                         "url": getattr(view, "url", ""), "delta_path": list(message.metadata.delta_path)})
    assert elements and elements == capture["elements"]
    assert finishes == capture["finishes"] == [0]


def comparable(capture):
    return [(element["kind"], {key: value for key, value in element["fields"].items() if key != "id"}) for element in capture["elements"]]


def logo_frames(capture):
    out = []
    for message in frames(capture):
        if message.WhichOneof("type") == "logo":
            out.append((message.logo.image, message.logo.image_type, message.logo.size, message.logo.link))
    return out


def test_python_reference_rules():
    raw = read(PYTHON / "trace.json")
    assert_capture(raw)
    assert raw["runtime"] == "python" and raw["reference_version"] == "1.66.1"
    assert raw["successful"] and "producer_error" not in raw
    assert raw["server_cleanup"] == "collector-owned" and raw["cleanup"]["server_stopped"] is True
    assert raw["finishes"] == [0]
    kinds = [element["kind"] for element in raw["elements"]]
    assert kinds == ["heading", "code", "skeleton"]
    code = raw["elements"][1]["fields"]
    assert code == {"code_text": "print('hi')", "language": "rust", "show_line_numbers": True}
    skeleton = raw["elements"][2]["fields"]
    assert skeleton == {}, "the default skeleton message carries no fields"
    logos = logo_frames(raw)
    assert logos == [("🧊", 1, "medium", "")], "emoji image, EMOJI type, medium default size, no link"  # EMOJI enum = 1


def test_rust_matches_field_for_field_and_logo_for_logo():
    raw = read(RUST / "trace.json")
    assert_capture(raw)
    assert raw["runtime"] == "rust" and raw["server_cleanup"] == "caller-owned"
    assert raw["finishes"] == [0]
    python = read(PYTHON / "trace.json")
    assert_capture(python)
    left, right = comparable(python), comparable(raw)
    assert len(left) == len(right) == 3
    for a, b in zip(left, right):
        assert a == b, (a, b)
    assert logo_frames(raw) == logo_frames(python)


def test_logo_unicode_sequences_icons_and_uri_reference():
    capture = read(PYTHON / "logo-strings/trace.json")
    assert_capture(capture)
    assert capture["runtime"] == "python" and capture["reference_version"] == "1.66.1" and capture["scenario"] == "logo-strings"
    assert capture["cleanup"] == {"websocket_closed": True, "server_stopped": True}
    assert len(capture["elements"]) == 1 and capture["elements"][0]["kind"] == "json"
    cases = json.loads(capture["elements"][0]["fields"]["body"])["logo_cases"]
    logos = [message for message in frames(capture) if isinstance(message, ForwardMsg) and message.WhichOneof("type") == "logo"]
    assert len(cases) == len(logos) == 18
    values = [case["image"] for case in cases]
    for index, (case, message) in enumerate(zip(cases, logos)):
        logo = message.logo
        assert logo.image == case["image"] and logo.icon_image == case["icon_image"]
        assert logo.image_type == (1 if index < 12 else 2 if index < 14 else 0)
        icon_index = values.index(case["icon_image"])
        assert logo.icon_image_type == (1 if icon_index < 12 else 2 if icon_index < 14 else 0)
        assert logo.size == case["size"] and logo.link == case.get("link", "")
        assert message.metadata.active_script_hash and not message.metadata.delta_path


@pytest.mark.parametrize("mutation", ["summary", "path", "finish", "logo", "length", "direction"])
def test_logo_evidence_gate_rejects_summary_or_wire_corruption(mutation):
    capture = copy.deepcopy(read(PYTHON / "trace.json"))
    if mutation == "summary":
        capture["elements"][1]["fields"]["code_text"] = "fabricated"
    elif mutation == "path":
        capture["elements"][1]["delta_path"] = [0, 999]
    elif mutation == "finish":
        capture["finishes"] = []
    elif mutation == "logo":
        next(frame for frame in capture["frames"] if "logo" in frame["message"])["message"]["logo"]["image_type"] = "IMAGE"
    elif mutation == "length":
        capture["frames"][0]["bytes"] += 1
    else:
        capture["frames"][0]["direction"] = "unknown"
    with pytest.raises(AssertionError):
        assert_capture(capture)
