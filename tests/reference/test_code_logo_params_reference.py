"""Frozen code/skeleton/logo parameter evidence (python + rust)."""
import base64
import copy
import json
import hashlib
from pathlib import Path

import pytest
from PIL import Image

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
        element_kind = element.WhichOneof("type")
        assert element_kind is not None
        view = getattr(element, element_kind)
        elements.append({"index": len(elements), "kind": element_kind,
                         "fields": MessageToDict(view, preserving_proto_field_name=True),
                         "url": getattr(view, "url", ""), "delta_path": list(message.metadata.delta_path)})
    assert elements and elements == capture["elements"]
    assert finishes == capture["finishes"] == list(expected_finishes)


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


def assert_height_capture(capture, runtime, before=False):
    assert_capture(capture, expected_finishes=(0, 0, 0))
    assert capture["runtime"] == runtime and capture["reference_version"] == "1.66.1"
    assert capture["scenario"] == "code-live" and capture["successful"] and "producer_error" not in capture
    messages = list(frames(capture))
    requests = [message.rerun_script for message in messages if isinstance(message, BackMsg)]
    assert len(requests) == 3 and all(request.query_string == "case=code-live" for request in requests)
    assert not requests[0].widget_states.widgets
    ids = {message.delta.new_element.checkbox.label: message.delta.new_element.checkbox.id for message in messages
           if isinstance(message, ForwardMsg) and message.WhichOneof("type") == "delta"
           and message.delta.new_element.WhichOneof("type") == "checkbox"}
    assert set(ids) == {"Tall code", "Wrap code", "Show line numbers"}
    for index, request in enumerate(requests[1:], 1):
        assert {widget.id: widget.bool_value for widget in request.widget_states.widgets} == {
            widget_id: label == "Tall code" and index == 1 for label, widget_id in ids.items()}
    codes = [message for message in messages if isinstance(message, ForwardMsg) and message.WhichOneof("type") == "delta"
             and message.delta.new_element.WhichOneof("type") == "code"]
    assert len(capture["elements"]) == 18 and len(codes) == 3
    assert [message.delta.new_element.height_config.pixel_height for message in codes] == [120, 240, 120]
    assert all(list(message.metadata.delta_path) == [0, 4] for message in codes)
    hashes = [message.hash for message in codes]
    assert all(hashes) and hashes[0] == hashes[2]
    assert (hashes[0] == hashes[1]) == before
    assert capture["cleanup"]["websocket_closed"] is True
    return codes


def test_height_rerun_wire_changes_hash_with_layout_and_preserves_failure():
    python = read(PYTHON / "height-rerun/trace.json")
    before = read(RUST / "height-rerun-before/trace.json")
    after = read(RUST / "height-rerun/trace.json")
    reference = assert_height_capture(python, "python")
    assert python["server_cleanup"] == "collector-owned" and python["cleanup"]["server_stopped"] is True
    assert_height_capture(before, "rust", before=True)
    actual = assert_height_capture(after, "rust")
    assert comparable(python) == comparable(before) == comparable(after)
    assert [list(element["delta_path"]) for element in python["elements"]] == [list(element["delta_path"]) for element in after["elements"]]
    assert [MessageToDict(message.delta.new_element, preserving_proto_field_name=True) for message in reference] == [
        MessageToDict(message.delta.new_element, preserving_proto_field_name=True) for message in actual]
    assert all(not message.metadata.cacheable for message in actual)


def test_python_url_runtime_metadata_mistake_is_retained_and_rejected():
    capture = read(PYTHON / "height-rerun-metadata-before/trace.json")
    assert_capture(capture, expected_finishes=(0, 0, 0))
    assert capture["url"] == "http://127.0.0.1:18607" and capture["runtime"] == "rust"
    assert capture["server_command"] is None and capture["server_cleanup"] == "caller-owned"
    with pytest.raises(AssertionError):
        assert_height_capture(capture, "python")


CODE_UI_STATES = [
    ("initial", 120, False, False), ("tall", 240, False, False), ("short", 120, False, False),
    ("wrap", 120, True, False), ("numbered", 120, True, True), ("all-enabled", 240, True, True),
    ("nowrap", 240, False, True), ("unnumbered", 240, False, False), ("wrap-restored", 240, True, False),
    ("renumbered", 240, True, True),
]


def assert_code_ui_controls(capture):
    assert [step["stage"] for step in capture["steps"][:10]] == [state[0] for state in CODE_UI_STATES]
    strings = [f'"line {index:02d} — 🤖 012345678901234567890123456789012345678901234567890123456789"' for index in range(1, 21)]
    for step, (_, height, wrap, lines) in zip(capture["steps"][:10], CODE_UI_STATES):
        assert step["title"] == "Code layout controls" and step["dom"]
        assert step["caption"] == f"height={height}; wrap={str(wrap).lower()}; lines={str(lines).lower()}"
        assert step["checkboxes"] == [{"label": label, "checked": checked} for label, checked in [
            ("Tall code", height == 240), ("Wrap code", wrap), ("Show line numbers", lines)]]
        code = step["code"]
        assert code["height"] == height, "code height did not follow the rendered control state"
        assert code["width"] == 360 and code["whiteSpace"] == ("pre-wrap" if wrap else "pre")
        assert code["keywords"] == ["print"] * 20 and code["strings"] == strings
        assert [number["text"] for number in code["numbers"]] == ([str(index) for index in range(1, 21)] if lines else [])
        assert code["scrollTop"] == 0 and code["scrollHeight"] > code["clientHeight"] > 0
        assert code["overflowY"] == code["overflowX"] == "auto"
        assert code["html"].count('token token keyword') == 20
        assert 'language-python' in code["html"] and 'line 20' in code["text"]


def assert_code_ui_screenshots(capture, folder):
    named = {step["screenshot"]: step for step in capture["steps"] if step.get("screenshot")}
    assert named and len(named) == len(capture["screenshots"])
    assert {item["file"] for item in capture["screenshots"]} == set(named)
    for item in capture["screenshots"]:
        filename = item["file"]
        assert Path(filename).name == filename and Path(filename).suffix in (".jpg", ".png")
        path = folder / filename
        raw = path.read_bytes()
        assert len(raw) == item["bytes"] and hashlib.sha256(raw).hexdigest() == item["sha256"]
        with Image.open(path) as image:
            image.load()
            clip = named[filename]["clip"]
            assert image.size == (clip["width"], clip["height"]) and min(image.size) > 100


def assert_code_ui(capture, folder, runtime):
    assert capture["runtime"] == runtime and capture["reference_version"] == "1.66.1"
    assert capture["successful"] and capture["capture_method"].startswith("Browser Use Chrome extension")
    assert capture["cleanup"] == {"browser_tabs_closed": True, "server_stopped": True, "listener_absent": True}
    assert_code_ui_controls(capture)
    port = 18607 if runtime == "python" else 8607
    assert all(step["url"] == f"http://127.0.0.1:{port}/?case=code-live" for step in capture["steps"])
    tail = [step["stage"] for step in capture["steps"][10:]]
    assert tail == (["scroll-down", "scroll-up", "scroll-up-settled"] if runtime == "python" else [
        "scroll-down", "scroll-down-settled", "scroll-up", "scroll-up-settled"])
    downward = [step["code"]["scrollTop"] for step in capture["steps"][10:] if step["stage"].startswith("scroll-down")]
    assert max(downward) > 0, "the actual inner scroll must move"
    assert capture["steps"][-1]["code"]["scrollTop"] == 0, "upward scrolling must restore the top"
    for step in capture["steps"][10:]:
        code = step["code"]
        assert code["height"] == 240 and code["width"] == 360 and code["whiteSpace"] == "pre-wrap"
        assert 0 <= code["scrollTop"] <= code["scrollHeight"] - code["clientHeight"]
    assert capture["console"] == []  # Only this tab's captured warn/error buffer, not an all-time zero-error claim.
    assert_code_ui_screenshots(capture, folder)


@pytest.mark.parametrize("runtime,folder", [("python", PYTHON / "ui"), ("rust", RUST / "ui")])
def test_code_live_browser_controls_scroll_and_images(runtime, folder):
    assert_code_ui(read(folder / "trace.json"), folder, runtime)


def test_code_live_browser_before_fix_is_retained_as_failure():
    capture = read(RUST / "ui-before/trace.json")
    assert capture["successful"] is False and len(capture["steps"]) == 10
    assert capture["failure_observations"] == [{"stage": stage, "expected_height": 240, "observed_height": 120} for stage in ("tall", "all-enabled")]
    assert capture["cleanup"] == {"browser_tabs_closed": True, "server_stopped": True}
    assert_code_ui_screenshots(capture, RUST / "ui-before")
    with pytest.raises(AssertionError, match="height"):
        assert_code_ui_controls(capture)


def test_code_live_browser_semantics_match_across_runtimes():
    python, rust = [read(folder / "trace.json") for folder in (PYTHON / "ui", RUST / "ui")]
    keys = ["width", "height", "clientWidth", "clientHeight", "scrollWidth", "scrollHeight", "whiteSpace", "overflowX", "overflowY", "keywords", "strings", "numbers", "text"]
    for left, right in zip(python["steps"][:10], rust["steps"][:10]):
        assert left["checkboxes"] == right["checkboxes"] and left["caption"] == right["caption"]
        assert {key: left["code"][key] for key in keys} == {key: right["code"][key] for key in keys}


@pytest.mark.parametrize("mutation", ["height", "width", "wrap", "line-numbers", "body", "scroll", "missing", "screenshot", "checkbox"])
def test_code_live_browser_gate_rejects_broken_or_incomplete_observations(mutation):
    capture = read(PYTHON / "ui/trace.json")
    if mutation in ("height", "width"):
        capture["steps"][1]["code"][mutation] = 120 if mutation == "height" else 1200
    elif mutation == "wrap":
        capture["steps"][3]["code"]["whiteSpace"] = "pre"
    elif mutation == "line-numbers":
        capture["steps"][4]["code"]["numbers"] = []
    elif mutation == "body":
        capture["steps"][0]["code"]["strings"][0] = '"fabricated"'
    elif mutation == "scroll":
        capture["steps"][-1]["code"]["scrollTop"] = 10
    elif mutation == "missing":
        capture["steps"].pop()
    elif mutation == "screenshot":
        capture["screenshots"][0]["sha256"] = "0" * 64
    else:
        capture["steps"][1]["checkboxes"][0]["checked"] = False
    with pytest.raises(AssertionError):
        assert_code_ui(capture, PYTHON / "ui", "python")


def test_code_identity_wire_preserves_fields_and_separates_the_hash():
    captures = [read(PYTHON / "identity-rerun/trace.json"), read(RUST / "identity-rerun-before/trace.json"), read(RUST / "identity-rerun/trace.json")]
    expected = [("left_right", "python"), ("left", "right_python"), ("left_right", "python")]
    for index, capture in enumerate(captures):
        assert_capture(capture, expected_finishes=(0, 0, 0))
        assert capture["runtime"] == ("python" if index == 0 else "rust") and capture["scenario"] == "code-identity"
        assert capture["successful"] and "producer_error" not in capture
        messages = list(frames(capture))
        codes = [message for message in messages if isinstance(message, ForwardMsg) and message.WhichOneof("type") == "delta"
                 and message.delta.new_element.WhichOneof("type") == "code"]
        assert len(capture["elements"]) == 12 and len(codes) == 3
        assert [(message.delta.new_element.code.code_text, message.delta.new_element.code.language) for message in codes] == expected
        assert all(list(message.metadata.delta_path) == [0, 2] for message in codes)
        assert all(message.delta.new_element.height_config.pixel_height == 120 and message.delta.new_element.width_config.pixel_width == 360 for message in codes)
        hashes = [message.hash for message in codes]
        assert all(hashes) and hashes[0] == hashes[2]
        assert (hashes[0] == hashes[1]) == (index == 1)
        requests = [message.rerun_script for message in messages if isinstance(message, BackMsg)]
        assert len(requests) == 3 and all(request.query_string == "case=code-identity" for request in requests)
        assert not requests[0].widget_states.widgets
        assert [request.widget_states.widgets[0].bool_value for request in requests[1:]] == [True, False]
        assert all(len(request.widget_states.widgets) == 1 for request in requests[1:])
        assert capture["cleanup"]["websocket_closed"] is True
    assert captures[0]["server_cleanup"] == "collector-owned" and captures[0]["cleanup"]["server_stopped"] is True
    assert comparable(captures[0]) == comparable(captures[1]) == comparable(captures[2])


def assert_identity_ui_steps(capture):
    assert [step["stage"] for step in capture["steps"]] == ["initial", "alternate", "restored"]
    for step, (body, language, checked) in zip(capture["steps"], [("left_right", "python", False), ("left", "right_python", True), ("left_right", "python", False)]):
        assert step["title"] == "Code identity controls" and step["dom"]
        assert step["caption"] == f"body={body}; language={language}" and step["checked"] == checked
        assert step["text"] == body, "code body must follow the selected fields"
        assert step["language_class"] == "language-" + language
        assert step["width"] == 360 and step["height"] == 120
        assert body in step["html"] and step["language_class"] in step["html"]


def assert_identity_ui(capture, folder, runtime):
    assert capture["runtime"] == runtime and capture["reference_version"] == "1.66.1"
    assert capture["successful"] and capture["capture_method"].startswith("Browser Use Chrome extension")
    assert capture["cleanup"] == {"browser_tabs_closed": True, "server_stopped": True, "listener_absent": True}
    port = 18607 if runtime == "python" else 8607
    assert all(step["url"] == f"http://127.0.0.1:{port}/?case=code-identity" for step in capture["steps"])
    assert_identity_ui_steps(capture)
    assert capture["console"] == []
    assert_code_ui_screenshots(capture, folder)


@pytest.mark.parametrize("runtime,folder", [("python", PYTHON / "identity-ui"), ("rust", RUST / "identity-ui")])
def test_code_identity_browser_switches_both_text_and_language(runtime, folder):
    assert_identity_ui(read(folder / "trace.json"), folder, runtime)


def test_code_identity_browser_failure_and_fixed_semantics_are_preserved():
    before = read(RUST / "identity-ui-before/trace.json")
    assert before["successful"] is False
    assert before["failure_observation"] == {"stage": "alternate", "expected_text": "left", "actual_text": "left_right",
                                            "expected_language": "language-right_python", "actual_language": "language-python"}
    assert_code_ui_screenshots(before, RUST / "identity-ui-before")
    with pytest.raises(AssertionError, match="body"):
        assert_identity_ui_steps(before)
    python, rust = [read(folder / "trace.json") for folder in (PYTHON / "identity-ui", RUST / "identity-ui")]
    keys = ["title", "caption", "checked", "text", "language_class", "width", "height"]
    assert [{key: step[key] for key in keys} for step in python["steps"]] == [{key: step[key] for key in keys} for step in rust["steps"]]


@pytest.mark.parametrize("mutation", ["body", "language", "caption", "checkbox", "dimension", "missing", "screenshot"])
def test_code_identity_ui_gate_rejects_stale_or_corrupt_evidence(mutation):
    capture = read(PYTHON / "identity-ui/trace.json")
    step = capture["steps"][1]
    if mutation == "body":
        step["text"] = "left_right"
    elif mutation == "language":
        step["language_class"] = "language-python"
    elif mutation == "caption":
        step["caption"] = "fabricated"
    elif mutation == "checkbox":
        step["checked"] = False
    elif mutation == "dimension":
        step["width"] = 1
    elif mutation == "missing":
        capture["steps"].pop()
    else:
        capture["screenshots"][0]["sha256"] = "0" * 64
    with pytest.raises(AssertionError):
        assert_identity_ui(capture, PYTHON / "identity-ui", "python")
