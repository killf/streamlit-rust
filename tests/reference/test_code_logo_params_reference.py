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


CODE_BODIES = ["", "\n", "\n\n", "\n\n\n", "\nprint('hi')\n", "\n\n  indented\n\n", "  leading\n    nested  \n", "\r\nwindows\r\n", "\rreturn\r", "\n spaced \r\n", "\talpha\n\t\tbeta\n", "\u0085line\u2028end\u2029", "Unicode 🤖 中文\n"]


def assert_code_text_reference(capture):
    assert_capture(capture)
    assert capture["runtime"] == "python" and capture["reference_version"] == "1.66.1"
    assert capture["scenario"] == "code-text" and capture["successful"] and "producer_error" not in capture
    assert capture["server_cleanup"] == "collector-owned" and capture["cleanup"] == {"websocket_closed": True, "server_stopped": True}
    cases = json.loads(capture["elements"][0]["fields"]["body"])["code_cases"]
    expected_cases = [{"body": CODE_BODIES[index // 2], "language": ["python", "", "RuSt", "made-up", " "][index % 5],
                       "line_numbers": index % 2 == 1, "wrap_lines": index % 3 == 0,
                       "width": ["stretch", "content", 240][index % 3], "height": ["content", "stretch", 120][index // 3 % 3]}
                      for index in range(26)]
    expected_cases.append({"body": "\nplain None language\n", "language": None, "line_numbers": True,
                           "wrap_lines": True, "width": "content", "height": 120})
    assert cases == expected_cases
    elements = [message.delta.new_element for message in frames(capture)
                if isinstance(message, ForwardMsg) and message.WhichOneof("type") == "delta"]
    assert len(elements) == len(capture["elements"]) == 28
    assert [element["delta_path"] for element in capture["elements"]] == [[0, index] for index in range(28)]
    assert MessageToDict(elements[0], preserving_proto_field_name=True) == {
        "json": {"body": json.dumps({"code_cases": cases}), "expanded": True}, "width_config": {"use_stretch": True}}
    for case, element in zip(cases, elements[1:]):
        body = case["body"].removeprefix("\n").removesuffix("\n")
        fields = {"language": case["language"] or "plaintext"}
        if body:
            fields["code_text"] = body
        if case["line_numbers"]:
            fields["show_line_numbers"] = True
        if case["wrap_lines"]:
            fields["wrap_lines"] = True
        width = {"pixel_width": case["width"]} if isinstance(case["width"], int) else {"use_" + case["width"]: True}
        height = {"pixel_height": case["height"]} if isinstance(case["height"], int) else {"use_" + case["height"]: True}
        assert MessageToDict(element, preserving_proto_field_name=True) == {"code": fields, "width_config": width, "height_config": height}


def test_code_text_language_and_layout_reference():
    assert_code_text_reference(read(PYTHON / "code-text/trace.json"))


@pytest.mark.parametrize("mutation,index", [("newline", 7), ("cr", 15), ("empty-language", 2), ("space-language", 5),
                                          ("width", 1), ("height", 2), ("wrap", 1), ("line-numbers", 2)])
def test_code_text_gate_rejects_coherent_wrong_payloads(mutation, index):
    capture = read(PYTHON / "code-text/trace.json")
    frame = next(frame for frame in capture["frames"] if frame["message"].get("metadata", {}).get("delta_path") == [0, index])
    message = ForwardMsg()
    message.ParseFromString(base64.b64decode(frame["base64"], validate=True))
    element = message.delta.new_element
    if mutation == "newline":
        element.code.code_text = ""
    elif mutation == "cr":
        element.code.code_text = element.code.code_text.replace("\r", "")
    elif mutation == "empty-language":
        element.code.language = ""
    elif mutation == "space-language":
        element.code.language = "plaintext"
    elif mutation == "width":
        element.width_config.pixel_width = 1
    elif mutation == "height":
        element.height_config.pixel_height = 999
    elif mutation == "wrap":
        element.code.wrap_lines = False
    else:
        element.code.show_line_numbers = False
    raw = message.SerializeToString()
    frame.update(base64=base64.b64encode(raw).decode(), bytes=len(raw), message=MessageToDict(message, preserving_proto_field_name=True))
    capture["elements"][index]["fields"] = MessageToDict(element.code, preserving_proto_field_name=True)
    assert_capture(capture)
    with pytest.raises(AssertionError):
        assert_code_text_reference(capture)


def test_code_text_rust_before_and_fixed_wire():
    python = read(PYTHON / "code-text/trace.json")
    assert_code_text_reference(python)
    before = read(RUST / "code-text-before/trace.json")
    after = read(RUST / "code-text/trace.json")
    for capture in (before, after):
        assert_capture(capture)
        assert capture["runtime"] == "rust" and capture["scenario"] == "code-text"
        assert capture["successful"] and "producer_error" not in capture
        assert capture["server_cleanup"] == "caller-owned" and capture["cleanup"]["websocket_closed"] is True
        assert len(capture["elements"]) == 28
    assert [index for index, (left, right) in enumerate(zip(python["elements"], before["elements"])) if left != right] == [
        2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 19, 20, 21, 22, 25, 26, 27]
    views = [[(list(message.metadata.delta_path), MessageToDict(message.delta.new_element, preserving_proto_field_name=True))
              for message in frames(capture) if isinstance(message, ForwardMsg) and message.WhichOneof("type") == "delta"]
             for capture in (python, before, after)]
    for (path, expected), (old_path, old) in zip(views[0], views[1]):
        assert path == old_path
        assert {key: value for key, value in expected.items() if key != "code"} == {key: value for key, value in old.items() if key != "code"}
        if "code" in expected:
            assert {key: value for key, value in expected["code"].items() if key not in ("code_text", "language")} == {
                key: value for key, value in old["code"].items() if key not in ("code_text", "language")}
    assert after["elements"] == python["elements"]
    assert views[0] == views[2], "complete payloads including width and height must match"
