"""Frozen chat/metric/progress parameter evidence (python + rust)."""
import base64
import copy
import json
import re
from pathlib import Path

import pytest
from google.protobuf.json_format import MessageToDict
from streamlit.proto.BackMsg_pb2 import BackMsg
from streamlit.proto.ForwardMsg_pb2 import ForwardMsg

PYTHON = Path(__file__).parent / "reference-browser/chat-metric-params"
RUST = Path(__file__).parents[1] / "browser/rust-chat-metric-params"


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
    """Bind the comparison summary to the retained, decoded wire bytes."""
    elements = []
    finishes = []
    for message in frames(capture):
        if not isinstance(message, ForwardMsg):
            continue
        if message.WhichOneof("type") == "script_finished":
            finishes.append(message.script_finished)
        if message.WhichOneof("type") != "delta":
            continue
        delta = message.delta
        if delta.WhichOneof("type") == "add_block":
            parent = delta.add_block
            kind = parent.WhichOneof("type")
            if kind is None:
                continue
            element = {"kind": f"add_block:{kind}", "url": None, "block": {
                field: MessageToDict(getattr(parent, field), preserving_proto_field_name=True)
                for field in ("width_config", "height_config") if parent.HasField(field)
            }}
        elif delta.WhichOneof("type") == "new_element":
            parent = delta.new_element
            kind = parent.WhichOneof("type")
            if kind is None:
                continue
            element = {"kind": kind, "url": getattr(getattr(parent, kind), "url", "")}
        else:
            continue
        element.update(index=len(elements),
                       fields=MessageToDict(getattr(parent, kind), preserving_proto_field_name=True),
                       delta_path=list(message.metadata.delta_path))
        elements.append(element)
    assert elements, "capture contains no element frames"
    assert elements == capture["elements"], "element summary differs from the wire"
    assert finishes == capture["finishes"] == [0], "capture did not finish successfully"


def comparable(capture):
    out = []
    for element in capture["elements"]:
        if element["kind"] == "exception":
            continue  # the python-only float overload error
        fields = dict(element["fields"])
        fields.pop("id", None)
        if element["kind"] == "markdown":
            fields.pop("body", None)
        blob = re.sub(r"[0-9a-f]{32}", "<digest32>", json.dumps(fields, sort_keys=True))
        out.append((element["kind"], json.loads(blob)))
    return out


def test_python_reference_rules():
    raw = read(PYTHON / "trace.json")
    assert_capture(raw)
    assert raw["runtime"] == "python" and raw["reference_version"] == "1.66.1"
    assert raw["successful"] and "producer_error" not in raw
    assert raw["server_cleanup"] == "collector-owned" and raw["cleanup"]["server_stopped"] is True
    assert raw["finishes"] == [0]
    kinds = [element["kind"] for element in raw["elements"]]
    assert kinds == ["heading", "add_block:chat_message", "markdown", "metric", "metric", "metric", "metric", "progress", "exception"]
    chat = raw["elements"][1]["fields"]
    assert chat["avatar_type"] == "EMOJI" and chat["avatar"] == "🛠️"
    metrics = {element["fields"]["label"]: element["fields"] for element in raw["elements"] if element["kind"] == "metric"}
    # No delta and zero delta: NONE + GRAY. Note the proto zero-values —
    # DOWN=0 and RED=0 — are OMITTED by MessageToDict.
    assert metrics["No delta"] == {"body": "42", "color": "GRAY", "direction": "NONE", "label": "No delta", "label_visibility": {}}
    assert metrics["Zero delta"] == {"body": "5", "color": "GRAY", "delta": "0", "direction": "NONE", "label": "Zero delta", "label_visibility": {}}
    assert metrics["Gray"] == {"body": "7", "color": "GRAY", "delta": "3", "direction": "UP", "label": "Gray", "label_visibility": {}}
    assert metrics["Negative"] == {"body": "9", "delta": "-2", "label": "Negative", "label_visibility": {}}, "DOWN+RED are the omitted zero values"
    progress = next(element["fields"] for element in raw["elements"] if element["kind"] == "progress")
    assert progress == {"text": "Halfway there", "value": 50}
    exception = next(element["fields"] for element in raw["elements"] if element["kind"] == "exception")
    assert "outside the required range [0.0, 1.0]" in exception["message"] and exception["is_streamlit_exception"]


def test_rust_matches_field_for_field():
    raw = read(RUST / "trace.json")
    assert_capture(raw)
    assert raw["runtime"] == "rust" and raw["server_cleanup"] == "caller-owned"
    assert raw["finishes"] == [0]
    python = read(PYTHON / "trace.json")
    assert_capture(python)
    left, right = comparable(python), comparable(raw)
    assert len(left) == len(right) == 8
    for a, b in zip(left, right):
        assert a == b, (a, b)


def test_string_delta_reference_and_fixed_rust_wire():
    reference = read(PYTHON / "string-delta/trace.json")
    before = read(RUST / "string-delta-before/trace.json")
    fixed = read(RUST / "string-delta/trace.json")
    for capture in (reference, before, fixed):
        assert_capture(capture)
        assert capture["successful"] and "producer_error" not in capture
    assert reference["reference_version"] == "1.66.1"
    assert reference["successful"] and reference["cleanup"]["server_stopped"]
    assert before["runtime"] == fixed["runtime"] == "rust"

    def metrics(capture):
        return {element["fields"]["label"]: element["fields"] for element in capture["elements"]
                if element["kind"] == "metric" and ":" in element["fields"]["label"]}

    expected = metrics(reference)
    old = metrics(before)
    assert len(expected) == 36
    assert len([key for key, value in expected.items() if old[key] != value]) == 30
    assert metrics(fixed) == expected
    assert expected["normal:2"]["delta"] == "0.0" and expected["normal:2"]["direction"] == "UP"
    assert expected["normal:4"]["delta"] == "-0" and "direction" not in expected["normal:4"]
    assert expected["normal:10"]["delta"] == "\nup\nnext\n"
    assert expected["normal:11"]["delta"] == "\n" and expected["normal:11"]["direction"] == "UP"


@pytest.mark.parametrize("root", [PYTHON, RUST], ids=["python", "rust"])
@pytest.mark.parametrize("corruption", ["bytes", "message", "fields", "path", "block", "finishes", "missing-frame", "direction"])
def test_capture_rejects_detached_or_corrupted_evidence(root, corruption):
    capture = copy.deepcopy(read(root / "trace.json"))
    if corruption == "bytes":
        capture["frames"][0]["bytes"] += 1
    elif corruption == "message":
        capture["frames"][0]["message"] = {}
    elif corruption == "fields":
        capture["elements"][1]["fields"]["avatar"] = "fabricated"
    elif corruption == "path":
        capture["elements"][1]["delta_path"] = [99]
    elif corruption == "block":
        capture["elements"][1]["block"] = {}
    elif corruption == "finishes":
        capture["finishes"] = [1]
    elif corruption == "missing-frame":
        capture["frames"] = [frame for frame in capture["frames"]
                             if "delta" not in frame["message"]]
    else:
        capture["frames"][0]["direction"] = "unknown"
    with pytest.raises(AssertionError):
        assert_capture(capture)


def test_string_avatar_inputs_and_wire_reference():
    capture = read(PYTHON / "string-avatars/trace.json")
    assert_capture(capture)
    assert capture["runtime"] == "python" and capture["reference_version"] == "1.66.1"
    assert capture["scenario"] == "avatars" and capture["successful"] and "producer_error" not in capture
    assert capture["cleanup"] == {"websocket_closed": True, "server_stopped": True}
    requests = [message for message in frames(capture) if isinstance(message, BackMsg)]
    assert len(requests) == 1 and requests[0].rerun_script.query_string == "case=avatars"
    elements = capture["elements"]
    assert [element["kind"] for element in elements] == ["json"] + [kind for _ in range(28) for kind in ("add_block:chat_message", "markdown")]
    assert elements[0]["fields"]["expanded"] is True, "default JSON display is expanded"
    cases = json.loads(elements[0]["fields"]["body"])["avatar_cases"]
    assert len(cases) == 28
    expected_defaults = [("user", "ICON"), ("user", "ICON"), ("assistant", "ICON"), ("assistant", "ICON"),
                         ("user", "ICON"), ("user", "ICON"), ("assistant", "ICON"), ("assistant", "ICON"),
                         ("", "ICON"), ("", "ICON"), ("🤖", "EMOJI"), ("👩‍💻", "EMOJI"), ("🛠️", "EMOJI"), ("🛠", "EMOJI"), ("", "ICON")]
    for index, case in enumerate(cases):
        block, child = elements[1 + index * 2:3 + index * 2]
        fields = block["fields"]
        assert fields.get("name", "") == case["name"]
        assert block["delta_path"] == [0, index + 1] and child["delta_path"] == [0, index + 1, 0]
        assert block["block"] == {"width_config": {"use_stretch": True}}
        assert child["fields"]["body"] == f"avatar-case:{index}"
        if index < 15:
            assert (fields.get("avatar", ""), fields.get("avatar_type", "IMAGE")) == expected_defaults[index]
        elif index < 19:
            assert fields["avatar_type"] == "ICON" and fields["avatar"] == ("user" if index < 17 else "assistant")
        else:
            assert fields["avatar"] == case["avatar"], "URI/emoji/icon strings must retain their exact spelling"
            assert fields.get("avatar_type", "IMAGE") == ("EMOJI" if index < 21 else "ICON" if index == 21 else "IMAGE")
    assert all(frame["message"]["delta"]["add_block"]["allow_empty"] for frame in capture["frames"] if "add_block" in frame["message"].get("delta", {}))
