"""Frozen text/latex/help/divider parameter evidence (python + rust)."""
import base64
import hashlib
import json
from pathlib import Path

import pytest
from PIL import Image

from google.protobuf.json_format import MessageToDict
from streamlit.proto.BackMsg_pb2 import BackMsg
from streamlit.proto.ForwardMsg_pb2 import ForwardMsg

PYTHON = Path(__file__).parent / "reference-browser/text-misc-params"
RUST = Path(__file__).parents[1] / "browser/rust-text-misc-params"


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


def assert_capture(capture, expected_finishes=(0,)):
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
        kind = element.WhichOneof("type")
        assert kind is not None
        view = getattr(element, kind)
        elements.append({"index": len(elements), "kind": kind, "fields": MessageToDict(view, preserving_proto_field_name=True),
                         "url": getattr(view, "url", ""), "delta_path": list(message.metadata.delta_path)})
    assert elements == capture["elements"] and elements
    assert finishes == capture["finishes"] == list(expected_finishes)


def comparable(capture):
    return [(element["kind"], {key: value for key, value in element["fields"].items() if key != "id"}) for element in capture["elements"]]


def full_elements(capture):
    result = []
    for message in frames(capture):
        if not isinstance(message, ForwardMsg) or message.WhichOneof("type") != "delta":
            continue
        element = MessageToDict(message.delta.new_element, preserving_proto_field_name=True)
        for kind in ("button", "checkbox"):
            if kind in element:
                element[kind].pop("id", None)
        result.append((list(message.metadata.delta_path), element))
    return result


def assert_layout_rules(capture):
    assert_capture(capture)
    payloads = full_elements(capture)
    report = payloads[0][1]
    assert set(report) == {"json", "width_config"}
    assert report["width_config"] == {"use_stretch": True}
    assert report["json"]["expanded"] is True
    cases = json.loads(report["json"]["body"])["layout_cases"]
    assert len(payloads) == len(cases) + 1
    for index, (case, (path, actual)) in enumerate(zip(cases, payloads[1:]), 1):
        kind, kwargs = case["kind"], case["kwargs"]
        body = case["body"]
        markdown = {"body": body, "element_type": "CAPTION" if kind == "caption" else "NATIVE"}
        expected = {"markdown": markdown}
        if kind == "badge":
            markdown["body"] = ":blue-badge[" + (kwargs["icon"] + " " if "icon" in kwargs else "") + body + "]"
        else:
            markdown["wrap"] = True
            expected["text_alignment_config"] = {"alignment": kwargs.get("text_alignment", "left").upper()}
        if "help" in kwargs:
            markdown["help"] = kwargs["help"]
        width = kwargs.get("width", {"markdown": "auto", "caption": "stretch", "badge": "content"}[kind])
        if width != "auto":
            expected["width_config"] = {"pixel_width": width} if isinstance(width, int) else {"use_" + width: True}
        assert path == [0, index]
        assert actual == expected, case
    return cases


def test_text_layout_reference_and_complete_supported_width_payloads():
    full = read(PYTHON / "layouts/trace.json")
    subset = read(PYTHON / "layout-widths/trace.json")
    for capture in (full, subset):
        assert capture["runtime"] == "python" and capture["reference_version"] == "1.66.1"
        assert capture["successful"] and "producer_error" not in capture
        assert capture["cleanup"] == {"websocket_closed": True, "server_stopped": True}
    cases = assert_layout_rules(full)
    assert len(cases) == 17
    supported = assert_layout_rules(subset)
    assert len(supported) == 13
    assert supported == [case for case in cases if "text_alignment" not in case["kwargs"]]
    fixed = read(RUST / "layout-widths/trace.json")
    before = read(RUST / "layout-widths-before/trace.json")
    for capture in (before, fixed):
        assert_capture(capture)
        assert capture["runtime"] == "rust" and capture["scenario"] == "layout-widths"
        assert capture["successful"] and "producer_error" not in capture
        assert capture["server_cleanup"] == "caller-owned"
    assert_layout_rules(fixed)
    assert full_elements(fixed) == full_elements(subset)
    assert [i for i, (a, b) in enumerate(zip(full_elements(subset), full_elements(before))) if a != b] == [1, 2, 6, 10, 11, 12, 13]


def test_identity_layout_correction_does_not_claim_identity_repair():
    reference = read(PYTHON / "identity/trace.json")
    fixed = read(RUST / "identity-layouts/trace.json")
    for capture in (reference, fixed):
        assert_capture(capture, expected_finishes=(0, 0, 0))
    assert len(full_elements(fixed)) == 24
    assert full_elements(fixed) == full_elements(reference)
    deltas = [message for message in frames(fixed) if isinstance(message, ForwardMsg) and message.WhichOneof("type") == "delta"]
    for slot in (2, 3, 4, 6):
        outputs = [message for message in deltas if list(message.metadata.delta_path) == [0, slot]]
        assert len(outputs) == 3 and len({message.hash for message in outputs}) == 1
        assert outputs[0].delta.new_element != outputs[1].delta.new_element


@pytest.mark.parametrize("field", ["default-width", "explicit-width", "badge-alignment", "caption-width"])
def test_layout_gate_rejects_coherent_wrong_wire(field):
    capture = read(PYTHON / "layout-widths/trace.json")
    target = {"default-width": 1, "explicit-width": 3, "badge-alignment": 10, "caption-width": 7}[field]
    frame = next(frame for frame in capture["frames"] if frame["message"].get("metadata", {}).get("delta_path") == [0, target])
    message = ForwardMsg()
    message.ParseFromString(base64.b64decode(frame["base64"]))
    element = message.delta.new_element
    if field == "default-width":
        element.width_config.use_stretch = True
    elif field in ("explicit-width", "caption-width"):
        element.ClearField("width_config")
    else:
        element.text_alignment_config.alignment = 1
    data = message.SerializeToString()
    frame.update(base64=base64.b64encode(data).decode(), bytes=len(data), message=MessageToDict(message, preserving_proto_field_name=True))
    # Outer layout fields do not appear in the collector's inner summary.
    assert_capture(capture)
    with pytest.raises(AssertionError):
        assert_layout_rules(capture)


def test_python_reference_rules():
    raw = read(PYTHON / "trace.json")
    assert_capture(raw)
    assert raw["runtime"] == "python" and raw["reference_version"] == "1.66.1"
    assert raw["successful"] and "producer_error" not in raw
    assert raw["server_cleanup"] == "collector-owned" and raw["cleanup"]["server_stopped"] is True
    assert raw["finishes"] == [0]
    kinds = [element["kind"] for element in raw["elements"]]
    assert kinds == ["heading", "text", "markdown", "help_info", "markdown"]
    text = raw["elements"][1]["fields"]
    assert text == {"body": "plain body", "wrap": True}, "st.text wraps explicitly"
    latex = raw["elements"][2]["fields"]
    assert latex == {"body": "$$\n\\int_0^1 x^2 dx\n$$", "element_type": "LATEX"}, "latex is LATEX-typed with wrap unset"
    help_fields = raw["elements"][3]["fields"]
    assert help_fields["name"] == "st.dataframe"
    assert help_fields["type"] == "method"
    assert help_fields["value"].startswith("streamlit.delta_generator.ArrowMixin.dataframe(")
    assert "Display a dataframe as an interactive table." in help_fields["doc_string"]
    divider = raw["elements"][4]["fields"]
    assert divider == {"body": "---", "element_type": "DIVIDER"}, "the divider leaves wrap unset"


def test_rust_matches_field_for_field():
    raw = read(RUST / "trace.json")
    assert_capture(raw)
    assert raw["runtime"] == "rust" and raw["server_cleanup"] == "caller-owned"
    assert raw["finishes"] == [0]
    python = read(PYTHON / "trace.json")
    assert_capture(python)
    left, right = comparable(python), comparable(raw)
    assert len(left) == len(right) == 5
    for a, b in zip(left, right):
        assert a == b, (a, b)


@pytest.mark.parametrize("mutation", ["summary", "message", "length", "direction", "finish", "drop"])
def test_text_misc_gate_rejects_summary_or_wire_corruption(mutation):
    capture = read(PYTHON / "trace.json")
    if mutation == "summary":
        capture["elements"][1]["fields"]["body"] = "fabricated"
    elif mutation == "message":
        next(frame for frame in capture["frames"] if "delta" in frame["message"])["message"]["delta"]["new_element"]["text"] = {"body": "fabricated"}
    elif mutation == "length":
        capture["frames"][0]["bytes"] += 1
    elif mutation == "direction":
        capture["frames"][0]["direction"] = "unknown"
    elif mutation == "finish":
        capture["finishes"] = []
    else:
        capture["elements"].pop()
    with pytest.raises(AssertionError):
        assert_capture(capture)


def test_multi_element_identity_reference_and_retained_rust_failures():
    python = read(PYTHON / "identity/trace.json")
    rust = read(RUST / "identity-before/trace.json")
    for runtime, capture in [("python", python), ("rust", rust)]:
        assert_capture(capture, expected_finishes=(0, 0, 0))
        assert capture["runtime"] == runtime and capture["scenario"] == "identity" and capture["successful"]
        assert "producer_error" not in capture and len(capture["elements"]) == 24
        messages = [message for message in frames(capture) if isinstance(message, ForwardMsg) and message.WhichOneof("type") == "delta"]
        for slot in [2, 3, 4, 5, 6]:
            outputs = [message for message in messages if list(message.metadata.delta_path) == [0, slot]]
            assert len(outputs) == 3
            hashes = [message.hash for message in outputs]
            assert all(hashes) and hashes[0] == hashes[2]
            assert (hashes[0] != hashes[1]) == (runtime == "python")
            assert outputs[0].delta.new_element == outputs[2].delta.new_element
            assert outputs[0].delta.new_element != outputs[1].delta.new_element
        headings = [message.delta.new_element.heading for message in messages if message.delta.new_element.WhichOneof("type") == "heading" and message.delta.new_element.heading.tag == "h2"]
        assert [(heading.anchor, heading.help, heading.divider) for heading in headings] == [
            ("anchor-a", "help A", "blue"), ("anchor-b", "help B", "red"), ("anchor-a", "help A", "blue")]
        buttons = [message.delta.new_element.button for message in messages if message.delta.new_element.WhichOneof("type") == "button"]
        assert [button.disabled for button in buttons] == [False, True, False]
        assert [button.icon for button in buttons] == ["🧊", "✅", "🧊"]
        assert len({button.id for button in buttons}) == 1
    assert comparable(python) == comparable(rust)
    assert python["cleanup"] == {"websocket_closed": True, "server_stopped": True}
    # Full Elements still have separate layout-presence differences; inner projections are not full wire parity.
    payloads = []
    for capture in (python, rust):
        current = []
        for message in frames(capture):
            if not isinstance(message, ForwardMsg) or message.WhichOneof("type") != "delta":
                continue
            element = MessageToDict(message.delta.new_element, preserving_proto_field_name=True)
            for kind in ("button", "checkbox"):
                if kind in element:
                    element[kind].pop("id", None)
            current.append(element)
        payloads.append(current)
    assert [index for index, (expected, observed) in enumerate(zip(*payloads)) if expected != observed] == [3, 4, 5, 11, 12, 19, 20, 21]


def assert_identity_ui_steps(capture):
    assert [step["stage"] for step in capture["steps"]] == ["initial", "alternate", "restored"]
    for index, step in enumerate(capture["steps"]):
        alternate = index == 1
        assert step["checked"] == alternate and step["status"] == f"alternate={str(alternate).lower()}"
        assert step["anchor"] == ("anchor-b" if alternate else "anchor-a"), "heading anchor is stale"
        assert step["anchor_href"] == "#" + step["anchor"]
        assert step["divider"] == ("#ff2b2b" if alternate else "#0068c9")
        assert step["style_is_caption"] == alternate
        assert step["button_enabled"] == (not alternate), "button disabled state is stale"
        assert step["title"] == "Element identity controls" and step["dom"]


def assert_identity_images(capture, folder):
    assert len(capture["screenshots"]) == len(capture["steps"]) == 3
    for image, step in zip(capture["screenshots"], capture["steps"]):
        assert image["file"] == step["stage"] + ".jpg" and Path(image["file"]).name == image["file"]
        data = (folder / image["file"]).read_bytes()
        assert len(data) == image["bytes"] and hashlib.sha256(data).hexdigest() == image["sha256"]
        with Image.open(folder / image["file"]) as loaded:
            loaded.load()
            assert loaded.size == (step["clip"]["width"], step["clip"]["height"])


def test_identity_browser_reference_and_actual_visible_rust_failures():
    python, rust = [read(folder / "trace.json") for folder in (PYTHON / "identity-ui", RUST / "identity-ui-before")]
    for runtime, capture, folder in [("python", python, PYTHON / "identity-ui"), ("rust", rust, RUST / "identity-ui-before")]:
        assert capture["runtime"] == runtime and capture["reference_version"] == "1.66.1"
        assert capture["capture_method"].startswith("Browser Use Chrome extension")
        port = 18606 if runtime == "python" else 8606
        assert all(step["url"] == f"http://127.0.0.1:{port}/?case=identity" for step in capture["steps"])
        assert capture["cleanup"] == {"browser_tabs_closed": True, "server_stopped": True, "listener_absent": True}
        assert capture["console"] == []
        assert_identity_images(capture, folder)
    assert python["successful"] and rust["successful"] is False
    assert_identity_ui_steps(python)
    with pytest.raises(AssertionError, match="stale"):
        assert_identity_ui_steps(rust)
    assert rust["failure_observation"]["stale_fields"] == ["anchor", "anchor_href", "divider", "style_is_caption", "button_enabled"]
    assert rust["steps"][1]["checked"] is True and rust["steps"][1]["button_enabled"] is True


@pytest.mark.parametrize("mutation", ["anchor", "divider", "style", "disabled", "image"])
def test_identity_ui_gate_rejects_wrong_observations(mutation):
    capture = read(PYTHON / "identity-ui/trace.json")
    if mutation == "anchor":
        capture["steps"][1]["anchor"] = "anchor-a"
    elif mutation == "divider":
        capture["steps"][1]["divider"] = "#0068c9"
    elif mutation == "style":
        capture["steps"][1]["style_is_caption"] = False
    elif mutation == "disabled":
        capture["steps"][1]["button_enabled"] = True
    else:
        capture["screenshots"][0]["sha256"] = "0" * 64
    with pytest.raises(AssertionError):
        assert_identity_ui_steps(capture)
        assert_identity_images(capture, PYTHON / "identity-ui")
