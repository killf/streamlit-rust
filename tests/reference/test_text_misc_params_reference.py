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


NORMALIZATION_INPUTS = [
    "\n    alpha\n      beta\n    gamma\n", "\talpha\n    beta", " \talpha\n \tbeta", "  alpha\n \tbeta",
    "  alpha\n \t \n    beta", "\n  alpha\r\n    beta\r\n", "  alpha\r    beta", "\u2003alpha\n\u2003beta",
    "\u001calpha\u001f", "  alpha\n\u00a0\n    beta", " \t\n\t  ", "\n  中文\n    🧊\n",
]

NORMALIZED_TEXT = [
    "alpha\n  beta\ngamma", "alpha\n    beta", "alpha\nbeta", "alpha\n\tbeta",
    "alpha\n\n  beta", "alpha\r\n  beta", "alpha\r    beta", "alpha\n\u2003beta",
    "alpha", "alpha\n\n  beta", "", "中文\n  🧊",
]


def assert_normalized_payloads(capture):
    assert_capture(capture)
    payloads = full_elements(capture)
    assert len(payloads) == 85
    report = payloads[0][1]
    assert payloads[0][0] == [0, 0] and set(report) == {"json", "width_config"}
    assert report["width_config"] == {"use_stretch": True}
    assert report["json"]["expanded"] is True
    assert json.loads(report["json"]["body"])["normalization_cases"] == NORMALIZATION_INPUTS
    for index, body in enumerate(NORMALIZED_TEXT):
        for offset, kind in enumerate(("markdown", "caption", "text", "title", "header", "subheader", "latex")):
            slot = 1 + index * 7 + offset
            path, observed = payloads[slot]
            fields = {"body": body} if body else {}
            if kind in ("markdown", "caption", "latex"):
                fields["element_type"] = {"markdown": "NATIVE", "caption": "CAPTION", "latex": "LATEX"}[kind]
                if kind == "latex":
                    fields["body"] = "$$\n" + body + "\n$$"
                else:
                    fields["wrap"] = True
                expected = {"markdown": fields}
            elif kind == "text":
                fields["wrap"] = True
                expected = {"text": fields}
            else:
                fields.update(tag={"title": "h1", "header": "h2", "subheader": "h3"}[kind], wrap=True)
                expected = {"heading": fields}
            if kind != "markdown":
                expected["width_config"] = {"use_content" if kind == "text" else "use_stretch": True}
            if kind != "latex":
                expected["text_alignment_config"] = {"alignment": "LEFT"}
            assert path == [0, slot]
            assert observed == expected, (index, kind)


def test_text_normalization_complete_wire_and_retained_failures():
    python = read(PYTHON / "normalization-valid/trace.json")
    rust = read(RUST / "normalization/trace.json")
    before = read(RUST / "normalization-before/trace.json")
    for runtime, capture in (("python", python), ("rust", rust), ("rust", before)):
        assert_capture(capture)
        assert capture["runtime"] == runtime and capture["reference_version"] == "1.66.1"
        assert capture["scenario"] == "normalization" and capture["successful"]
        assert "producer_error" not in capture
    assert python["cleanup"] == {"websocket_closed": True, "server_stopped": True}
    assert_normalized_payloads(python)
    assert_normalized_payloads(rust)
    assert full_elements(rust) == full_elements(python)
    with pytest.raises(AssertionError):
        assert_normalized_payloads(before)
    assert len(full_elements(before)) == 85
    assert sum(a != b for a, b in zip(full_elements(python), full_elements(before))) == 72
    malformed = read(PYTHON / "normalization/trace.json")
    assert_capture(malformed)
    assert len(malformed["elements"]) == 79
    assert malformed["elements"][-1]["kind"] == "exception"
    assert malformed["elements"][-1]["fields"]["type"] == "UnicodeEncodeError"
    assert malformed["cleanup"] == {"websocket_closed": True, "server_stopped": True}


@pytest.mark.parametrize("mutation", ["mixed-indent", "crlf", "unicode", "latex-width", "latex-alignment"])
def test_normalization_gate_rejects_coherent_wrong_wire(mutation):
    capture = read(PYTHON / "normalization-valid/trace.json")
    slot = {"mixed-indent": 8, "crlf": 36, "unicode": 50, "latex-width": 7, "latex-alignment": 7}[mutation]
    frame = next(frame for frame in capture["frames"] if frame["message"].get("metadata", {}).get("delta_path") == [0, slot])
    message = ForwardMsg()
    message.ParseFromString(base64.b64decode(frame["base64"]))
    element = message.delta.new_element
    if mutation == "mixed-indent":
        element.markdown.body = "alpha\n   beta"
    elif mutation == "crlf":
        element.markdown.body = element.markdown.body.replace("\r\n", "\n")
    elif mutation == "unicode":
        element.markdown.body = "alpha\nbeta"
    elif mutation == "latex-width":
        element.ClearField("width_config")
    else:
        element.text_alignment_config.alignment = 1
    data = message.SerializeToString()
    frame.update(base64=base64.b64encode(data).decode(), bytes=len(data), message=MessageToDict(message, preserving_proto_field_name=True))
    capture["elements"][slot]["fields"] = MessageToDict(element.markdown, preserving_proto_field_name=True)
    assert_capture(capture)
    with pytest.raises(AssertionError):
        assert_normalized_payloads(capture)



def assert_divider_payloads(capture):
    assert_capture(capture)
    payloads = full_elements(capture)
    assert len(payloads) == 9 and payloads[0][0] == [0, 0]
    report = payloads[0][1]
    assert set(report) == {"json", "width_config"}
    assert report["width_config"] == {"use_stretch": True}
    assert report["json"]["expanded"] is True
    assert json.loads(report["json"]["body"]) == {"divider_widths": ["default", "stretch", 1, 240, 2147483647]}
    for slot, (path, actual) in enumerate(payloads[1:], 1):
        markdown = {"body": "---", "element_type": "DIVIDER"}
        expected = {"markdown": markdown, "width_config": {"use_stretch": True}}
        if slot in (3, 4, 5):
            expected["width_config"] = {"pixel_width": {3: 1, 4: 240, 5: 2147483647}[slot]}
        elif slot in (6, 7):
            markdown.update(element_type="NATIVE" if slot == 6 else "CAPTION", wrap=True)
            expected["text_alignment_config"] = {"alignment": "LEFT"}
            if slot == 6:
                del expected["width_config"]
        elif slot == 8:
            markdown.update(body="$$\nx\n$$", element_type="LATEX")
        assert path == [0, slot] and actual == expected, slot


def test_divider_complete_layouts_and_retained_before_difference():
    python = read(PYTHON / "dividers/trace.json")
    rust = read(RUST / "dividers/trace.json")
    before = read(RUST / "dividers-before/trace.json")
    for runtime, capture in (("python", python), ("rust", rust), ("rust", before)):
        assert_capture(capture)
        assert capture["runtime"] == runtime and capture["reference_version"] == "1.66.1"
        assert capture["scenario"] == "dividers" and capture["successful"]
        assert "producer_error" not in capture
    assert python["cleanup"] == {"websocket_closed": True, "server_stopped": True}
    assert_divider_payloads(python)
    assert_divider_payloads(rust)
    assert full_elements(python) == full_elements(rust)
    assert [i for i, (a, b) in enumerate(zip(full_elements(python), full_elements(before))) if a != b] == [1, 2, 3, 4, 5]
    with pytest.raises(AssertionError):
        assert_divider_payloads(before)


@pytest.mark.parametrize("mutation", ["alignment", "wrap", "pixel-width", "markdown-control"])
def test_divider_gate_rejects_coherent_wrong_wire(mutation):
    capture = read(PYTHON / "dividers/trace.json")
    slot = 6 if mutation == "markdown-control" else 4
    frame = next(frame for frame in capture["frames"] if frame["message"].get("metadata", {}).get("delta_path") == [0, slot])
    message = ForwardMsg()
    message.ParseFromString(base64.b64decode(frame["base64"]))
    element = message.delta.new_element
    if mutation == "alignment":
        element.text_alignment_config.alignment = 1
    elif mutation == "wrap":
        element.markdown.wrap = False
    elif mutation == "pixel-width":
        element.width_config.pixel_width = 1
    else:
        element.ClearField("text_alignment_config")
    data = message.SerializeToString()
    frame.update(base64=base64.b64encode(data).decode(), bytes=len(data), message=MessageToDict(message, preserving_proto_field_name=True))
    capture["elements"][slot]["fields"] = MessageToDict(element.markdown, preserving_proto_field_name=True)
    assert_capture(capture)
    with pytest.raises(AssertionError):
        assert_divider_payloads(capture)



def divider_error_rounds(capture):
    assert_capture(capture, expected_finishes=(0, 0, 0, 0))
    requests, sessions, rounds, current = [], [], [], []
    for message in frames(capture):
        if isinstance(message, BackMsg):
            assert message.WhichOneof("type") == "rerun_script"
            requests.append(message.rerun_script.query_string)
        elif message.WhichOneof("type") == "new_session":
            sessions.append(message.new_session.initialize.session_id)
        elif message.WhichOneof("type") == "delta":
            current.append((list(message.metadata.delta_path), MessageToDict(message.delta.new_element, preserving_proto_field_name=True)))
        elif message.WhichOneof("type") == "script_finished":
            rounds.append(current)
            current = []
    assert not current and len(rounds) == len(sessions) == 4
    assert all(sessions) and len(set(sessions)) == 1
    assert requests == ["case=divider-errors&phase=" + phase for phase in ("zero", "negative", "caught", "recovered")]
    for index, (phase, outputs) in enumerate(zip(("zero", "negative", "caught", "recovered"), rounds), 1):
        assert outputs[0][0] == [0, 0]
        assert json.loads(outputs[0][1]["json"]["body"]) == {"phase": phase, "runs": index, "stage": "before"}
        assert [path for path, _ in outputs] == [[0, slot] for slot in range(len(outputs))]
    return rounds


def assert_python_divider_error_flow(capture):
    rounds = divider_error_rounds(capture)
    assert [len(outputs) for outputs in rounds] == [2, 2, 4, 3]
    for width, outputs in zip((0, -1), rounds[:2]):
        assert set(outputs[1][1]) == {"exception"}
        error = outputs[1][1]["exception"]
        assert error["type"] == "streamlit.errors.StreamlitInvalidWidthError"
        assert error["message"] == f"Invalid width value: {width}. Width must be either a positive integer (pixels) or 'stretch'."
        assert error["message_is_markdown"] and error["is_streamlit_exception"]
        assert error["width_config"] == {"use_stretch": True} and error["stack_trace"]
    caught = rounds[2]
    assert caught[1][1] == {"markdown": {"body": "---", "element_type": "DIVIDER"}, "width_config": {"pixel_width": 1}}
    results = json.loads(caught[2][1]["json"]["body"])["caught_results"]
    assert results == [
        {"width": width, "type": "StreamlitInvalidWidthError", "message": f"Invalid width value: {width}. Width must be either a positive integer (pixels) or 'stretch'."}
        for width in (0, -1, -2147483648)
    ] + [{"width": 1, "returned": True}]
    for index, phase in ((2, "caught"), (3, "recovered")):
        assert json.loads(rounds[index][-1][1]["json"]["body"]) == {"phase": phase, "runs": index + 1, "stage": "after"}
    assert rounds[3][1][1] == {"markdown": {"body": "---", "element_type": "DIVIDER"}, "width_config": {"pixel_width": 240}}


def test_divider_error_and_recovery_reference_retains_actual_rust_failure():
    python = read(PYTHON / "divider-errors/trace.json")
    rust = read(RUST / "divider-errors-before/trace.json")
    for runtime, capture in (("python", python), ("rust", rust)):
        assert capture["runtime"] == runtime and capture["reference_version"] == "1.66.1"
        assert capture["scenario"] == "divider-errors" and capture["successful"]
        assert "producer_error" not in capture
    assert python["cleanup"] == {"websocket_closed": True, "server_stopped": True}
    assert_python_divider_error_flow(python)
    rounds = divider_error_rounds(rust)
    assert [len(outputs) for outputs in rounds] == [3, 3, 7, 3]
    assert rounds[0][1][1]["width_config"] == {"pixel_width": 0}
    assert rounds[1][1][1]["width_config"] == {"pixel_width": 4294967295}
    assert [output[1]["width_config"]["pixel_width"] for output in rounds[2][1:5]] == [0, 4294967295, 2147483648, 1]
    assert json.loads(rounds[2][5][1]["json"]["body"])["caught_results"] == [{"width": width, "returned": True} for width in (0, -1, -2147483648, 1)]
    assert rounds[3] == divider_error_rounds(python)[3]
    with pytest.raises(AssertionError):
        assert_python_divider_error_flow(rust)


@pytest.mark.parametrize("mutation", ["error-message", "error-kind", "caught-result", "recovery-counter"])
def test_divider_error_flow_gate_rejects_coherent_wrong_wire(mutation):
    capture = read(PYTHON / "divider-errors/trace.json")
    messages = [frame for frame in capture["frames"] if "delta" in frame["message"]]
    slot = {"error-message": 1, "error-kind": 1, "caught-result": 6, "recovery-counter": 10}[mutation]
    frame = messages[slot]
    message = ForwardMsg()
    message.ParseFromString(base64.b64decode(frame["base64"]))
    element = message.delta.new_element
    kind = element.WhichOneof("type")
    if mutation == "error-message":
        element.exception.message = "invalid"
    elif mutation == "error-kind":
        element.exception.type = "ValueError"
    else:
        report = json.loads(element.json.body)
        if mutation == "caught-result":
            report["caught_results"][0] = {"width": 0, "returned": True}
        else:
            report["runs"] = 1
        element.json.body = json.dumps(report)
    data = message.SerializeToString()
    frame.update(base64=base64.b64encode(data).decode(), bytes=len(data), message=MessageToDict(message, preserving_proto_field_name=True))
    capture["elements"][slot]["fields"] = MessageToDict(getattr(element, kind), preserving_proto_field_name=True)
    assert_capture(capture, expected_finishes=(0, 0, 0, 0))
    with pytest.raises(AssertionError):
        assert_python_divider_error_flow(capture)



def assert_text_layout_browser(capture, folder):
    assert capture["successful"] and capture["reference_version"] == "1.66.1"
    assert capture["capture_method"].startswith("Browser Use Chrome extension")
    assert capture["cleanup"] == {"browser_tabs_closed": True, "server_stopped": True, "listener_absent": True}
    observations = capture["observations"]
    assert [step["scene"] for step in observations] == ["dividers", "normalization", "normalization-bottom", "normalization-restored"]
    port = 18606 if capture["runtime"] == "python" else 8606
    # Raw viewport heights and x origins are retained; content geometry is compared separately.
    for step in observations:
        case = "dividers" if step["scene"] == "dividers" else "normalization"
        assert step["url"] == f"http://127.0.0.1:{port}/?case={case}"
        assert step["page"]["exceptions"] == [] and step["dom"]
        assert step["page"]["viewport"]["width"] == 2560 and step["page"]["viewport"]["dpr"] == 1
    dividers = observations[0]["page"]["elements"]
    assert len(dividers) == 9 and observations[0]["console"] == []
    assert [element["rect"]["width"] for element in dividers] == [704, 704, 704, 16, 240, 704, 704, 704, 704]
    for slot in range(1, 8):
        assert dividers[slot]["text"] == ""
        assert dividers[slot]["separators"] == [{"height": 1, "width": dividers[slot]["rect"]["width"]}]
    assert dividers[8]["text"] == "𝑥\nx"
    assert dividers[8]["separators"] == []
    top = observations[1]["page"]["elements"]
    assert len(top) == 85
    assert [top[3 + index * 7]["text"] for index in range(12)] == NORMALIZED_TEXT
    # 单独 CR 在标题内产生软换行，不能假设所有标题只含正文首行。
    heading_texts = ["alpha"] * 6 + ["alpha\nbeta"] + ["alpha"] * 3 + ["", "中文"]
    for index, heading_text in enumerate(heading_texts):
        assert top[1 + index * 7]["children"] == ["stMarkdown", "stMarkdownContainer"]
        assert top[2 + index * 7]["children"] == ["stMarkdown", "stCaptionContainer"]
        assert top[3 + index * 7]["children"] == ["stText"]
        for offset, tag in ((4, "H1"), (5, "H2"), (6, "H3")):
            heading = top[offset + index * 7]["headings"]
            assert len(heading) == 1 and heading[0]["tag"] == tag
            assert heading[0]["text"] == heading_text
    assert top[84]["text"] == "中文🧊\n中文🧊"
    for step in observations[1:]:
        assert len(step["console"]) == 6 and all(log["level"] == "warn" for log in step["console"])
        assert [log["message"] for log in step["console"]] == [log["message"] for log in observations[1]["console"]]
    assert "unknownSymbol" in observations[1]["console"][0]["message"]
    assert "unicodeTextInMathMode" in observations[1]["console"][2]["message"]
    assert capture["scroll"]["bottom"]["top"] == capture["scroll"]["bottom"]["max"] > 0
    assert capture["scroll"]["restored"]["top"] == capture["scroll"]["restored_layout"]["scrollTop"] == 0
    for stage, scroll in ((2, capture["scroll"]["bottom"]["top"]), (3, 0)):
        assert len(observations[stage]["page"]["elements"]) == 85
        for original, moved in zip(top, observations[stage]["page"]["elements"]):
            assert original["text"] == moved["text"]
            assert original["rect"]["y"] == moved["rect"]["y"] + scroll
            assert original["rect"]["width"] == moved["rect"]["width"]
            assert original["rect"]["height"] == moved["rect"]["height"]
    assert len(capture["screenshots"]) == 4
    assert {item["file"] for item in capture["screenshots"]} == {"dividers.jpg", "dividers-context.jpg", "normalization-top.jpg", "normalization-bottom.jpg"}
    for item in capture["screenshots"]:
        assert Path(item["file"]).name == item["file"]
        data = (folder / item["file"]).read_bytes()
        assert len(data) == item["bytes"] and hashlib.sha256(data).hexdigest() == item["sha256"]
        with Image.open(folder / item["file"]) as image:
            image.load()
            assert image.format == "JPEG"
            size = (item["clip"]["width"], item["clip"]["height"]) if item["clip"] else (2560, observations[0]["page"]["viewport"]["height"])
            assert image.size == size


def comparable_layout_browser_elements(capture, stage):
    elements = capture["observations"][stage]["page"]["elements"]
    origin = elements[0]["rect"]["x"]
    scroll = capture["scroll"]["bottom"]["top"] if stage == 2 else 0
    return [dict(element, rect=dict(element["rect"], x=element["rect"]["x"] - origin, y=element["rect"]["y"] + scroll)) for element in elements]


def test_actual_browser_text_layout_and_scroll_match_reference():
    folders = (PYTHON / "layout-ui", RUST / "layout-ui")
    python, rust = [read(folder / "trace.json") for folder in folders]
    for capture, folder in zip((python, rust), folders):
        assert_text_layout_browser(capture, folder)
    assert python["runtime"] == "python" and rust["runtime"] == "rust"
    for stage in range(4):
        assert comparable_layout_browser_elements(python, stage) == comparable_layout_browser_elements(rust, stage)
    assert [log["message"] for log in python["observations"][1]["console"]] == [log["message"] for log in rust["observations"][1]["console"]]


@pytest.mark.parametrize("mutation", ["width", "text", "heading", "scroll", "console", "image"])
def test_layout_browser_gate_rejects_wrong_observations(mutation):
    capture = read(PYTHON / "layout-ui/trace.json")
    if mutation == "width":
        capture["observations"][0]["page"]["elements"][4]["rect"]["width"] = 241
    elif mutation == "text":
        capture["observations"][1]["page"]["elements"][3]["text"] = "alpha beta gamma"
    elif mutation == "heading":
        capture["observations"][1]["page"]["elements"][4]["headings"][0]["tag"] = "H2"
    elif mutation == "scroll":
        capture["scroll"]["bottom"]["top"] -= 1
    elif mutation == "console":
        capture["observations"][1]["console"].pop()
    else:
        capture["screenshots"][0]["sha256"] = "0" * 64
    with pytest.raises(AssertionError):
        assert_text_layout_browser(capture, PYTHON / "layout-ui")



BADGE_RAW_LABELS = ["plain", "[ready]", "x] :red-badge[other", r"\[ready\]", "nested [[x]]", "**bold**", "`code`", "", "  padded  ", "\n  first\n    second\n", "中文 [🧊]", "line1\r\n[line2]"]
BADGE_ESCAPED_LABELS = ["plain", r"\[ready\]", r"x\] :red-badge\[other", r"\\[ready\\]", r"nested \[\[x\]\]", "**bold**", "`code`", "", "  padded  ", "\n  first\n    second\n", r"中文 \[🧊\]", "line1\r\n\\[line2\\]"]


def assert_badge_content_payloads(capture):
    assert_capture(capture)
    outputs = full_elements(capture)
    assert len(outputs) == 18
    report = outputs[0][1]
    assert outputs[0][0] == [0, 0] and set(report) == {"json", "width_config"}
    assert report["json"]["expanded"] and report["width_config"] == {"use_stretch": True}
    inputs = json.loads(report["json"]["body"])
    assert [case["label"] for case in inputs["badge_cases"]] == BADGE_RAW_LABELS
    assert inputs["common_help"] == "\n    Common **help**\n      detail\n"
    icons = (None, " 🧊 ", "\t \n", " :material/check: ", "\u001c🧊\u001f")
    normalized_icons = ("", "🧊", "", ":material/check:", "🧊")
    for index, label in enumerate(BADGE_ESCAPED_LABELS):
        kwargs = {"help": f"\n    Tip [{index}]\n      detail\n", "color": ("blue", "green", "orange")[index % 3]}
        if icons[index % 5] is not None:
            kwargs["icon"] = icons[index % 5]
        if index % 3:
            kwargs["width"] = "stretch" if index % 3 == 1 else 240
        assert inputs["badge_cases"][index]["kwargs"] == kwargs
        icon = normalized_icons[index % 5]
        expected = {
            "markdown": {"body": f":{kwargs['color']}-badge[" + (icon + " " if icon else "") + label + "]", "element_type": "NATIVE", "help": f"\nTip [{index}]\n  detail\n"},
            "width_config": ({"use_content": True}, {"use_stretch": True}, {"pixel_width": 240})[index % 3],
        }
        assert outputs[index + 1] == ([0, index + 1], expected), index
    for slot, kind in enumerate(("markdown", "caption", "h1", "h2", "h3"), 13):
        fields = {"body": "Help control", "help": "\nCommon **help**\n  detail\n", "wrap": True}
        if kind in ("markdown", "caption"):
            fields["element_type"] = "NATIVE" if kind == "markdown" else "CAPTION"
            expected = {"markdown": fields}
        else:
            fields["tag"] = kind
            expected = {"heading": fields}
        if kind != "markdown":
            expected["width_config"] = {"use_stretch": True}
        expected["text_alignment_config"] = {"alignment": "LEFT"}
        assert outputs[slot] == ([0, slot], expected)


def test_badge_label_icon_help_complete_reference_and_before_capture():
    python = read(PYTHON / "badge-content/trace.json")
    rust = read(RUST / "badge-content/trace.json")
    before = read(RUST / "badge-content-before/trace.json")
    for runtime, capture in (("python", python), ("rust", rust), ("rust", before)):
        assert_capture(capture)
        assert capture["runtime"] == runtime and capture["reference_version"] == "1.66.1"
        assert capture["scenario"] == "badge-content" and capture["successful"]
        assert "producer_error" not in capture
    assert python["cleanup"] == {"websocket_closed": True, "server_stopped": True}
    assert_badge_content_payloads(python)
    assert_badge_content_payloads(rust)
    assert full_elements(python) == full_elements(rust)
    assert [i for i, (a, b) in enumerate(zip(full_elements(python), full_elements(before))) if a != b] == list(range(1, 18))
    with pytest.raises(AssertionError):
        assert_badge_content_payloads(before)


@pytest.mark.parametrize("mutation", ["bracket", "backslash", "raw-label", "icon", "help-indent", "help-strip", "heading-help"])
def test_badge_content_gate_rejects_coherent_wrong_wire(mutation):
    capture = read(PYTHON / "badge-content/trace.json")
    slot = {"bracket": 2, "backslash": 4, "raw-label": 10, "icon": 5, "help-indent": 1, "help-strip": 1, "heading-help": 15}[mutation]
    frame = next(frame for frame in capture["frames"] if frame["message"].get("metadata", {}).get("delta_path") == [0, slot])
    message = ForwardMsg()
    message.ParseFromString(base64.b64decode(frame["base64"]))
    element = message.delta.new_element
    kind = element.WhichOneof("type")
    if mutation == "bracket":
        element.markdown.body = ":green-badge[🧊 [ready]]"
    elif mutation == "backslash":
        element.markdown.body = r":blue-badge[:material/check: \[ready\]]"
    elif mutation == "raw-label":
        element.markdown.body = ":blue-badge[🧊 first\n  second]"
    elif mutation == "icon":
        element.markdown.body = ":green-badge[\u001c🧊\u001f nested \\[\\[x\\]\\]]"
    elif mutation == "help-indent":
        element.markdown.help = "\n    Tip [0]\n      detail\n"
    elif mutation == "help-strip":
        element.markdown.help = element.markdown.help.strip()
    else:
        element.heading.help = "\n    Common **help**\n      detail\n"
    data = message.SerializeToString()
    frame.update(base64=base64.b64encode(data).decode(), bytes=len(data), message=MessageToDict(message, preserving_proto_field_name=True))
    capture["elements"][slot]["fields"] = MessageToDict(getattr(element, kind), preserving_proto_field_name=True)
    assert_capture(capture)
    with pytest.raises(AssertionError):
        assert_badge_content_payloads(capture)



def assert_badge_content_browser(capture, folder):
    assert capture["successful"] and capture["reference_version"] == "1.66.1"
    assert capture["capture_method"].startswith("Browser Use Chrome extension")
    assert capture["cleanup"] == {"browser_tabs_closed": True, "server_stopped": True, "listener_absent": True}
    steps = capture["observations"]
    stages = ["initial", "badge-help", "material-label-help", "markdown-help", "caption-help", "title-help", "header-help", "subheader-help"]
    assert [step["stage"] for step in steps] == stages
    expected_texts = ["plain", "🧊 [ready]", "x] [other", r"check \[ready\]", "🧊 nested [[x]]", "bold", "🧊 code", "", "check padded", "🧊 first second", "中文 [🧊]", "🧊 line1 [line2]"]
    colors = [("rgb(61, 157, 243)", "rgba(61, 157, 243, 0.2)"), ("rgb(92, 228, 136)", "rgba(61, 213, 109, 0.2)"), ("rgb(255, 189, 69)", "rgba(255, 135, 0, 0.2)")]
    port = 18606 if capture["runtime"] == "python" else 8606
    targets = [1, 4, 13, 14, 15, 16, 17]
    for index, step in enumerate(steps):
        assert step["url"] == f"http://127.0.0.1:{port}/?case=badge-content"
        assert step["dom"] and step["console"] == []
        page = step["page"]
        assert page["exceptions"] == [] and page["main_scroll"] == 0
        assert page["viewport"]["width"] == 2560 and page["viewport"]["dpr"] == 1
        elements, badges = page["elements"], page["visible_badges"]
        assert len(elements) == len(badges) == 18 and elements[0]["text"] == "{...}"
        assert badges[0] == []
        for slot, text in enumerate(expected_texts, 1):
            assert [badge["text"] for badge in badges[slot]] == ([text] if text else [])
            for badge in badges[slot]:
                assert (badge["color"], badge["background"]) == colors[(slot - 1) % 3]
        assert elements[8]["text"] == "", "empty label is not a visible badge"
        assert badges[6][0]["strong"] == ["bold"] and badges[7][0]["code"] == ["code"]
        assert any(image["label"] == "check icon" for image in elements[4]["images"])
        for slot in range(13, 18):
            assert badges[slot] == [] and elements[slot]["help_buttons"] == 1
        for slot, tag in ((15, "H1"), (16, "H2"), (17, "H3")):
            assert elements[slot]["headings"] == [{"id": "help-control", "tag": tag, "text": "Help control"}]
        if index == 0:
            assert page["tooltips"] == page["tooltip_details"] == []
        else:
            expected = "Tip [0] detail" if index == 1 else "Tip [3] detail" if index == 2 else "Common help detail"
            paragraph = "Tip [0]\ndetail" if index == 1 else "Tip [3]\ndetail" if index == 2 else "Common help\ndetail"
            assert page["tooltips"] == [expected]
            assert page["tooltip_details"] == [{"text": expected, "paragraphs": [paragraph], "strong": [] if index < 3 else ["help"]}]
            assert '- tooltip "' + expected + '"' in step["dom"]
            action = step["action"]
            assert action["kind"] == "CDP Input.dispatchMouseEvent mouseMoved" and action["element_index"] == targets[index - 1]
            target = elements[action["element_index"]]["rect"]
            assert target["x"] <= action["x"] <= target["x"] + target["width"]
            assert target["y"] <= action["y"] <= target["y"] + target["height"]
    assert len(capture["screenshots"]) == 4
    assert {item["file"] for item in capture["screenshots"]} == {"initial.jpg", "badge-help.jpg", "markdown-help.jpg", "subheader-help.jpg"}
    for item in capture["screenshots"]:
        assert Path(item["file"]).name == item["file"]
        data = (folder / item["file"]).read_bytes()
        assert len(data) == item["bytes"] and hashlib.sha256(data).hexdigest() == item["sha256"]
        with Image.open(folder / item["file"]) as image:
            image.load()
            assert image.format == "JPEG" and image.size == (item["clip"]["width"], item["clip"]["height"]) == (800, 1000)


def test_actual_browser_badges_and_all_measured_help_entrypoints_match():
    folders = (PYTHON / "badge-content-ui", RUST / "badge-content-ui")
    python, rust = [read(folder / "trace.json") for folder in folders]
    assert python["runtime"] == "python" and rust["runtime"] == "rust"
    for capture, folder in zip((python, rust), folders):
        assert_badge_content_browser(capture, folder)
    for left, right in zip(python["observations"], rust["observations"]):
        def relative_elements(step):
            origin = step["page"]["elements"][0]["rect"]["x"]
            return [dict(element, rect=dict(element["rect"], x=element["rect"]["x"] - origin)) for element in step["page"]["elements"]]
        assert relative_elements(left) == relative_elements(right)
        assert left["page"]["visible_badges"] == right["page"]["visible_badges"]
        assert left["page"]["tooltip_details"] == right["page"]["tooltip_details"]

    # DOM 可见不保证后取的截图仍含 tooltip：保留原图并独立补证。
    original_images = {item["file"]: item for item in python["screenshots"]}
    assert original_images["markdown-help.jpg"]["sha256"] == original_images["initial.jpg"]["sha256"]
    confirmation = read(folders[0] / "markdown-help-confirmation.json")
    assert confirmation["successful"] and confirmation["runtime"] == "python"
    assert confirmation["cleanup"] == {"browser_tabs_closed": True, "server_stopped": True, "listener_absent": True}
    assert confirmation["original_screenshot_review"] == {"file": "markdown-help.jpg", "identical_to": "initial.jpg", "used_for_tooltip_evidence": False}
    assert confirmation["tooltip_css"] == {"opacity": "1", "text": "Common help detail"}
    assert confirmation["observation"]["page"]["tooltip_details"] == rust["observations"][3]["page"]["tooltip_details"]
    assert confirmation["observation"]["action"]["element_index"] == 13
    assert len(confirmation["attempt_observations"]) == 2
    assert len(confirmation["screenshots"]) == 3
    used = [item for item in confirmation["screenshots"] if item["used_for_tooltip_evidence"]]
    assert len(used) == 1 and used[0]["file"] == "markdown-help-cdp.jpg"
    assert used[0]["method"] == "CDP Page.captureScreenshot"
    assert used[0]["sha256"] != original_images["initial.jpg"]["sha256"]
    for item in confirmation["screenshots"]:
        assert Path(item["file"]).name == item["file"]
        data = (folders[0] / item["file"]).read_bytes()
        assert len(data) == item["bytes"] and hashlib.sha256(data).hexdigest() == item["sha256"]
        with Image.open(folders[0] / item["file"]) as image:
            image.load()
            assert image.format == "JPEG" and image.size == (800, 1000)


@pytest.mark.parametrize("mutation", ["label", "color", "bold", "code", "empty", "tooltip", "help-format", "action", "image"])
def test_badge_browser_gate_rejects_wrong_observations(mutation):
    capture = read(PYTHON / "badge-content-ui/trace.json")
    page = capture["observations"][0]["page"]
    if mutation == "label":
        page["visible_badges"][2][0]["text"] = "[ready"
    elif mutation == "color":
        page["visible_badges"][1][0]["color"] = "red"
    elif mutation == "bold":
        page["visible_badges"][6][0]["strong"] = []
    elif mutation == "code":
        page["visible_badges"][7][0]["code"] = []
    elif mutation == "empty":
        page["visible_badges"][8] = [dict(page["visible_badges"][1][0])]
    elif mutation == "tooltip":
        capture["observations"][1]["page"]["tooltips"] = ["stale"]
    elif mutation == "help-format":
        capture["observations"][3]["page"]["tooltip_details"][0]["strong"] = []
    elif mutation == "action":
        capture["observations"][1]["action"]["element_index"] = 2
    else:
        capture["screenshots"][0]["sha256"] = "0" * 64
    with pytest.raises(AssertionError):
        assert_badge_content_browser(capture, PYTHON / "badge-content-ui")



STATUS_PYTHON = PYTHON.parent / "status"
STATUS_RUST = RUST.parent / "rust-status"
ALERT_INPUTS = [
    {"body": "\n    alpha\n      beta\n", "kwargs": {"title": "\n  Title\n    detail\n"}},
    {"body": "\n    💡 alpha\n      beta\n", "kwargs": {"width": 240}},
    {"body": "\n    :material/thumb_up: alpha\n      beta\n", "kwargs": {"title": "\tTitle\n    detail"}},
    {"body": " \t💡 keep \n", "kwargs": {"icon": "", "width": 240}},
    {"body": " \t💡 keep \n", "kwargs": {"icon": " \t\n"}},
    {"body": "  body\r\n    next  ", "kwargs": {"icon": " 🧊 ", "width": 240}},
    {"body": " \u001cbody\u001f ", "kwargs": {"icon": "\u001c👩‍💻\u001f", "title": "\u001cTitle\u001f"}},
    {"body": "\u2003alpha\n\u2003beta", "kwargs": {"width": 240}},
    {"body": "💡\u001cafter", "kwargs": {}},
    {"body": " \t\n ", "kwargs": {"title": " \t\n ", "width": 240}},
    {"body": "plain [x] **bold**", "kwargs": {"icon": " :material/warning: "}},
    {"body": "\tfirst\n    second", "kwargs": {"title": "\n    **Title**\n", "width": 240}},
]


def assert_alert_normalization(capture):
    assert_capture(capture)
    outputs = full_elements(capture)
    assert len(outputs) == 50
    for slot in (0, 49):
        assert outputs[slot][0] == [0, slot]
        report = outputs[slot][1]
        assert set(report) == {"json", "width_config"}
        assert report["json"]["expanded"] and report["width_config"] == {"use_stretch": True}
    assert json.loads(outputs[0][1]["json"]["body"]) == {"alert_cases": ALERT_INPUTS}
    bodies = ["alpha\n  beta", "alpha\n  beta", "alpha\n  beta", "💡 keep", "💡 keep", "body\r\n  next", "body", "alpha\n\u2003beta", "\u001cafter", "", "plain [x] **bold**", "first\n    second"]
    icons = ["", "💡", ":material/thumb_up:", "", "", "🧊", "👩‍💻", "", "💡", "", ":material/warning:", ""]
    titles = ["Title\n  detail", "", "Title\n    detail", "", "", "", "Title", "", "", "", "", "**Title**"]
    kinds = ("info", "success", "warning", "error")
    results = []
    for index in range(12):
        for offset, kind in enumerate(kinds):
            fields = {"format": kind.upper(), "width_config": {"pixel_width": 240} if index % 2 else {"use_stretch": True}}
            for field, value in (("body", bodies[index]), ("icon", icons[index]), ("title", titles[index])):
                if value:
                    fields[field] = value
            slot = 1 + index * 4 + offset
            assert outputs[slot] == ([0, slot], {"alert": fields}), (index, kind)
            results.append({"index": index, "kind": kind, "returned": True})
    assert json.loads(outputs[49][1]["json"]["body"]) == {"results": results}


def test_alert_normalization_reference_and_two_retained_rust_failures():
    python = read(STATUS_PYTHON / "normalization/trace.json")
    rust = read(STATUS_RUST / "normalization/trace.json")
    before = read(STATUS_RUST / "normalization-before/trace.json")
    attempt = read(STATUS_RUST / "normalization-attempt/trace.json")
    for runtime, capture in (("python", python), ("rust", rust), ("rust", before), ("rust", attempt)):
        assert_capture(capture)
        assert capture["runtime"] == runtime and capture["reference_version"] == "1.66.1"
        assert capture["scenario"] == "alert-normalization" and capture["successful"]
        assert "producer_error" not in capture
    assert python["cleanup"] == {"websocket_closed": True, "server_stopped": True}
    assert_alert_normalization(python)
    assert_alert_normalization(rust)
    assert full_elements(python) == full_elements(rust)
    assert len(before["elements"]) == 34
    results = json.loads(before["elements"][-1]["fields"]["body"])["results"]
    assert len(results) == 48 and sum(item.get("returned", False) for item in results) == 32
    assert {(item["index"], item["kind"]) for item in results if "error" in item} == {(index, kind) for index in (4, 5, 6, 10) for kind in ("info", "success", "warning", "error")}
    assert [i for i, (a, b) in enumerate(zip(full_elements(python), full_elements(attempt))) if a != b] == [33, 34, 35, 36]
    for failed in (before, attempt):
        with pytest.raises(AssertionError):
            assert_alert_normalization(failed)


def test_direct_python_alert_separator_oracle_is_distinct_from_ws_evidence():
    oracle = read(STATUS_PYTHON / "normalization/icon-separators.json")
    assert oracle["reference_version"] == "1.66.1" and oracle["python_version"].startswith("3.14.7")
    assert "not a public WS or browser capture" in oracle["scope"]
    expected = []
    for prefix in ("💡", ":material/thumb_up:"):
        for separator in (" ", "_ -__ ", "\t", "\n", "\r", "\u00a0", "\u2003", "\u001c"):
            remainder = separator if (prefix == "💡" and separator not in (" ", "_ -__ ")) or (prefix != "💡" and separator == "_ -__ ") else ""
            expected.append({"input": prefix + separator + "after", "body": remainder + "after", "icon": prefix})
    assert oracle["cases"] == expected


@pytest.mark.parametrize("mutation", ["body", "icon", "title", "empty-icon", "separator", "width-placement", "result"])
def test_alert_normalization_gate_rejects_coherent_wrong_wire(mutation):
    capture = read(STATUS_PYTHON / "normalization/trace.json")
    slot = {"body": 1, "icon": 21, "title": 1, "empty-icon": 17, "separator": 33, "width-placement": 1, "result": 49}[mutation]
    frame = next(frame for frame in capture["frames"] if frame["message"].get("metadata", {}).get("delta_path") == [0, slot])
    message = ForwardMsg()
    message.ParseFromString(base64.b64decode(frame["base64"]))
    element = message.delta.new_element
    kind = element.WhichOneof("type")
    if mutation == "body":
        element.alert.body = "\n    alpha\n      beta\n"
    elif mutation == "icon":
        element.alert.icon = " 🧊 "
    elif mutation == "title":
        element.alert.title = "\n  Title\n    detail\n"
    elif mutation == "empty-icon":
        element.alert.icon, element.alert.body = "💡", "keep"
    elif mutation == "separator":
        element.alert.body = "after"
    elif mutation == "width-placement":
        element.width_config.CopyFrom(element.alert.width_config)
        element.alert.ClearField("width_config")
    else:
        report = json.loads(element.json.body)
        report["results"][0]["returned"] = False
        element.json.body = json.dumps(report)
    data = message.SerializeToString()
    frame.update(base64=base64.b64encode(data).decode(), bytes=len(data), message=MessageToDict(message, preserving_proto_field_name=True))
    capture["elements"][slot]["fields"] = MessageToDict(getattr(element, kind), preserving_proto_field_name=True)
    assert_capture(capture)
    with pytest.raises(AssertionError):
        assert_alert_normalization(capture)



def assert_alert_normalization_browser(capture, folder):
    assert capture["successful"] and capture["reference_version"] == "1.66.1"
    assert capture["capture_method"].startswith("Browser Use Chrome extension")
    assert capture["cleanup"] == {"browser_tabs_closed": True, "server_stopped": True, "listener_absent": True}
    steps = capture["observations"]
    assert [step["stage"] for step in steps] == ["initial", "middle", "bottom", "restored"]
    port = 18502 if capture["runtime"] == "python" else 8502
    bodies = ["alpha beta", "alpha beta", "alpha beta", "💡 keep", "💡 keep", "body next", "body", "alpha \u2003beta", "\u001cafter", "", "plain [x] bold", "first second"]
    paragraphs = [["alpha\nbeta"], ["alpha\nbeta"], ["alpha\nbeta"], ["💡 keep"], ["💡 keep"], ["body\r\nnext"], ["body"], ["alpha\n\u2003beta"], ["\u001cafter"], [], ["plain [x] bold"], ["first\nsecond"]]
    icons = [None, "💡", "thumb_up", None, None, "🧊", "👩‍💻", None, "💡", None, "warning", None]
    titles = ["Title detail", None, "Title detail", None, None, None, "Title", None, None, None, None, "Title"]
    formats = ("Info", "Success", "Warning", "Error")
    colors = [("rgb(61, 157, 243)", "rgba(61, 157, 243, 0.2)"), ("rgb(92, 228, 136)", "rgba(61, 213, 109, 0.2)"), ("rgb(255, 255, 194)", "rgba(255, 255, 18, 0.2)"), ("rgb(255, 108, 108)", "rgba(255, 108, 108, 0.2)")]
    for step in steps:
        assert step["url"] == f"http://127.0.0.1:{port}/?case=normalization"
        assert step["dom"] and step["console"] == []
        page = step["page"]
        assert page["exceptions"] == [] and page["reports"] == ["{...}", "{...}"]
        assert page["viewport"]["width"] == 2560 and page["viewport"]["dpr"] == 1
        assert len(page["alerts"]) == 48
        for index, alert in enumerate(page["alerts"]):
            case, kind = divmod(index, 4)
            assert alert["index"] == index and alert["format"] == "stAlertContent" + formats[kind]
            assert alert["role"] == ("status" if kind < 2 else "alert")
            assert (alert["color"], alert["background"]) == colors[kind]
            assert alert["rect"]["width"] == (240 if case % 2 else 704)
            assert alert["body"] == [{"text": bodies[case], "paragraphs": paragraphs[case], "strong": ["bold"] if case == 10 else [], "code": []}]
            assert alert["title"] == (None if titles[case] is None else {"text": titles[case], "strong": ["Title"] if case == 11 else []})
            if icons[case] is None:
                assert alert["icon"] is None
            else:
                assert alert["icon"]["text"] == icons[case] and alert["icon"]["label"] is None
                assert ("Material Symbols Rounded" in alert["icon"]["font"]) == (case in (2, 10))
    assert steps[0]["page"]["scroll"]["top"] == steps[3]["page"]["scroll"]["top"] == 0
    assert 0 < steps[1]["page"]["scroll"]["top"] < steps[1]["page"]["scroll"]["max"]
    assert steps[2]["page"]["scroll"]["top"] == steps[2]["page"]["scroll"]["max"] > 0
    for step in steps[1:]:
        for original, moved in zip(steps[0]["page"]["alerts"], step["page"]["alerts"]):
            assert original["rect"]["y"] == moved["rect"]["y"] + step["page"]["scroll"]["top"]
            assert original["rect"]["height"] == moved["rect"]["height"]
    assert len(capture["screenshots"]) == 3
    assert {item["file"] for item in capture["screenshots"]} == {"top.jpg", "middle.jpg", "bottom.jpg"}
    for item in capture["screenshots"]:
        assert Path(item["file"]).name == item["file"]
        data = (folder / item["file"]).read_bytes()
        assert len(data) == item["bytes"] and hashlib.sha256(data).hexdigest() == item["sha256"]
        with Image.open(folder / item["file"]) as image:
            image.load()
            assert image.format == "JPEG" and image.size == (item["clip"]["width"], item["clip"]["height"]) == (800, 1000)


def test_actual_browser_alert_formats_content_and_scrolling_match_reference():
    folders = (STATUS_PYTHON / "normalization/ui", STATUS_RUST / "normalization/ui")
    python, rust = [read(folder / "trace.json") for folder in folders]
    assert python["runtime"] == "python" and rust["runtime"] == "rust"
    for capture, folder in zip((python, rust), folders):
        assert_alert_normalization_browser(capture, folder)
    for left, right in zip(python["observations"], rust["observations"]):
        def comparable(step):
            origin = step["page"]["alerts"][0]["rect"]["x"]
            scroll = step["page"]["scroll"]["top"]
            return [dict(alert, rect=dict(alert["rect"], x=alert["rect"]["x"] - origin, y=alert["rect"]["y"] + scroll)) for alert in step["page"]["alerts"]]
        assert comparable(left) == comparable(right)


@pytest.mark.parametrize("mutation", ["body", "title", "icon", "role", "color", "width", "empty", "scroll", "image"])
def test_alert_browser_gate_rejects_wrong_observations(mutation):
    capture = read(STATUS_PYTHON / "normalization/ui/trace.json")
    alerts = capture["observations"][0]["page"]["alerts"]
    if mutation == "body":
        alerts[32]["body"][0]["text"] = "after"
    elif mutation == "title":
        alerts[44]["title"]["strong"] = []
    elif mutation == "icon":
        alerts[16]["icon"] = dict(alerts[4]["icon"])
    elif mutation == "role":
        alerts[0]["role"] = "alert"
    elif mutation == "color":
        alerts[2]["color"] = "red"
    elif mutation == "width":
        alerts[4]["rect"]["width"] = 704
    elif mutation == "empty":
        alerts[36]["title"] = {"text": " ", "strong": []}
    elif mutation == "scroll":
        capture["observations"][2]["page"]["scroll"]["top"] -= 1
    else:
        capture["screenshots"][0]["sha256"] = "0" * 64
    with pytest.raises(AssertionError):
        assert_alert_normalization_browser(capture, STATUS_PYTHON / "normalization/ui")
