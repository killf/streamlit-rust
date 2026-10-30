"""Frozen json/badge/feedback parameter evidence (python + rust)."""
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

PYTHON = Path(__file__).parent / "reference-browser/json-badge-params"
RUST = Path(__file__).parents[1] / "browser/rust-json-badge-params"


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
        assert message.delta.WhichOneof("type") == "new_element", "unexpected JSON parameter delta"
        element = message.delta.new_element
        element_kind = element.WhichOneof("type")
        assert element_kind is not None
        view = getattr(element, element_kind)
        elements.append({"index": len(elements), "kind": element_kind,
                         "fields": MessageToDict(view, preserving_proto_field_name=True),
                         "url": getattr(view, "url", ""), "delta_path": list(message.metadata.delta_path)})
    assert elements and elements == capture["elements"], "element summaries differ from decoded wire"
    assert finishes == capture["finishes"] == [0]


def comparable(capture):
    return [(element["kind"], {key: value for key, value in element["fields"].items() if key != "id"}) for element in capture["elements"]]


def test_python_reference_rules():
    raw = read(PYTHON / "trace.json")
    assert_capture(raw)
    assert raw["runtime"] == "python" and raw["reference_version"] == "1.66.1"
    assert raw["successful"] and "producer_error" not in raw
    assert raw["server_cleanup"] == "collector-owned" and raw["cleanup"]["server_stopped"] is True
    assert raw["finishes"] == [0]
    kinds = [element["kind"] for element in raw["elements"]]
    assert kinds == ["heading", "json", "json", "markdown", "markdown", "feedback"]
    expanded, collapsed = raw["elements"][1]["fields"], raw["elements"][2]["fields"]
    assert expanded == {"body": '{"outer": {"inner": [1, 2]}}', "expanded": True}
    assert collapsed == {"body": '{"deep": {"a": {"b": {"c": 1}}}}'}, "collapsed omits expanded entirely"
    green, plain = raw["elements"][3]["fields"], raw["elements"][4]["fields"]
    assert green == {"body": ":green-badge[:material/rocket_launch: New]", "element_type": "NATIVE"}, "badge markdown leaves wrap unset"
    assert plain == {"body": ":blue-badge[Plain]", "element_type": "NATIVE"}, "no separator without an icon"
    feedback = raw["elements"][5]["fields"]
    feedback.pop("id", None)
    assert feedback == {"disabled": True}


def test_rust_matches_field_for_field():
    raw = read(RUST / "trace.json")
    assert_capture(raw)
    assert raw["runtime"] == "rust" and raw["server_cleanup"] == "caller-owned"
    assert raw["finishes"] == [0]
    python = read(PYTHON / "trace.json")
    assert_capture(python)
    left, right = comparable(python), comparable(raw)
    assert len(left) == len(right) == 6
    for a, b in zip(left, right):
        assert a == b, (a, b)


def test_json_string_passthrough_and_structured_controls_reference():
    capture = read(PYTHON / "strings/trace.json")
    assert_capture(capture)
    assert capture["runtime"] == "python" and capture["reference_version"] == "1.66.1"
    assert capture["scenario"] == "strings" and capture["successful"] and "producer_error" not in capture
    assert capture["cleanup"] == {"websocket_closed": True, "server_stopped": True}
    requests = [message for message in frames(capture) if isinstance(message, BackMsg)]
    assert len(requests) == 1 and requests[0].rerun_script.query_string == "case=strings"
    elements = capture["elements"]
    assert len(elements) == 36 and all(element["kind"] == "json" for element in elements)
    inputs = json.loads(elements[0]["fields"]["body"])
    strings, controls = inputs["string_cases"], inputs["controls"]
    assert len(strings) == 15 and len(controls) == 5
    assert strings[1].startswith(" \n") and strings[1].endswith("\t")
    assert strings[8:11] == ["", "not json", '{"unfinished":']
    for index, text in enumerate(strings):
        expanded, collapsed = elements[1 + index * 2:3 + index * 2]
        assert expanded["fields"].get("body", "") == collapsed["fields"].get("body", "") == text
        assert expanded["fields"]["expanded"] is True and not collapsed["fields"].get("expanded", False)
    for element, value in zip(elements[31:], controls):
        assert element["fields"]["body"] == json.dumps(value)
        assert element["fields"]["expanded"] is True
    for index, element in enumerate(elements):
        assert element["delta_path"] == [0, index]
    for message in frames(capture):
        if isinstance(message, ForwardMsg) and message.WhichOneof("type") == "delta":
            assert MessageToDict(message.delta.new_element.width_config, preserving_proto_field_name=True) == {"use_stretch": True}


@pytest.mark.parametrize("mutation", ["body", "path", "finish", "message", "length", "direction", "drop"])
def test_json_reference_gate_rejects_summary_or_wire_corruption(mutation):
    capture = copy.deepcopy(read(PYTHON / "trace.json"))
    if mutation == "body":
        capture["elements"][1]["fields"]["body"] = "fabricated"
    elif mutation == "path":
        capture["elements"][1]["delta_path"] = [0, 999]
    elif mutation == "finish":
        capture["finishes"] = []
    elif mutation == "message":
        frame = next(frame for frame in capture["frames"] if "json" in frame["message"].get("delta", {}).get("new_element", {}))
        frame["message"]["delta"]["new_element"]["json"]["body"] = "fabricated"
    elif mutation == "length":
        capture["frames"][0]["bytes"] += 1
    elif mutation == "direction":
        capture["frames"][0]["direction"] = "unknown"
    else:
        capture["elements"].pop()
    with pytest.raises(AssertionError):
        assert_capture(capture)


UI_STAGES = [("matrix", index, False) for index in range(15)] + [
    (stage, sample, True) for sample in (0, 2) for stage in ("initial-collapse", "click-expand", "click-collapse")
] + [("unicode-final", 11, False)]


def assert_ui_capture(capture, folder, runtime):
    assert capture["runtime"] == runtime and capture["reference_version"] == "1.66.1"
    assert capture["capture_method"].startswith("Browser Use Chrome extension")
    assert capture["cleanup"]["browser_tabs_closed"] and capture["cleanup"]["server_stopped"] and capture["cleanup"]["listener_absent"]
    steps = capture["steps"]
    assert [(step["stage"], step["sample"], step["collapsed"]) for step in steps] == UI_STAGES
    port = 18604 if runtime == "python" else 8604
    screenshot_names = set()
    for step in steps:
        sample, collapsed = step["sample"], step["collapsed"]
        assert step["url"] == f"http://127.0.0.1:{port}/?case=strings&sample={sample}" + ("&collapsed=true" if collapsed else "")
        assert step["main_text"].startswith(f"JSON string {sample}\n") and step["dom"]
        if sample in (8, 9, 10, 14):
            assert len(step["alerts"]) == 1 and step["json"] == []
            assert "Json Parse Error:" in step["main_text"] and "- alert:" in step["dom"]
        else:
            assert step["alerts"] == [] and len(step["json"]) == 1
            component = step["json"][0]
            assert step["main_text"] == f"JSON string {sample}\n" + component["text"]
            assert component["html"].count('class="expanded-icon"') == component["icons"].count("expanded-icon")
            assert component["html"].count('class="collapsed-icon"') == component["icons"].count("collapsed-icon")
            assert component["html"].count('class="variable-row"') == component["rows"]
            assert component["html"].count('class="object-key"') == len(component["keys"])
            if sample in (3, 4, 5, 6, 7, 12, 13):
                assert "src property must be a valid json object" in component["text"]
            if step["stage"] in ("initial-collapse", "click-collapse"):
                assert component["icons"] == ["collapsed-icon"] and component["rows"] == 0 and "..." in component["text"]
            elif sample in (0, 1, 2, 11):
                assert component["icons"] == ["expanded-icon"] and component["rows"] > 0
            if sample == 11:
                assert '"emoji":"🤖"' in component["text"] and '"中文":"值"' in component["text"]
        if step.get("screenshot"):
            screenshot_names.add(step["screenshot"])
    assert len(capture["preflight"]) == 1 and capture["preflight"][0]["main_text"] == steps[0]["main_text"]
    screenshot_names.add(capture["preflight"][0]["screenshot"])
    manifest = capture["screenshots"]
    assert len(manifest) == len(screenshot_names) == 9
    assert {entry["file"] for entry in manifest} == screenshot_names
    for entry in manifest:
        name = entry["file"]
        assert Path(name).name == name and name.endswith(".jpg")
        content = (folder / name).read_bytes()
        assert len(content) == entry["bytes"] and hashlib.sha256(content).hexdigest() == entry["sha256"]
        with Image.open(folder / name) as picture:
            assert picture.format == "JPEG" and picture.width > 0 and picture.height > 0
            if name == "unicode-context.jpg":
                assert picture.size == (776, 350)
            picture.verify()


@pytest.mark.parametrize("runtime,folder", [("python", PYTHON / "ui"), ("rust", RUST / "ui")])
def test_json_live_browser_capture_has_complete_observations_and_images(runtime, folder):
    assert_ui_capture(read(folder / "trace.json"), folder, runtime)


def test_json_live_browser_states_match_the_fixed_python_reference():
    python, rust = read(PYTHON / "ui/trace.json"), read(RUST / "ui/trace.json")
    assert_ui_capture(python, PYTHON / "ui", "python")
    assert_ui_capture(rust, RUST / "ui", "rust")
    def projection(step):
        return (step["stage"], step["sample"], step["collapsed"], step["main_text"], step["alerts"],
                [{key: component[key] for key in ("text", "icons", "keys", "rows")} for component in step["json"]])
    assert [projection(step) for step in python["steps"]] == [projection(step) for step in rust["steps"]]
    python_logs = [(entry["level"], entry["message"]) for entry in python["console_log_buffer_at_final_observation"]]
    rust_logs = [(entry["level"], entry["message"]) for entry in rust["console_log_buffer_at_final_observation"]]
    assert python_logs == rust_logs and len(python_logs) == 8
    assert all(message == "react-json-view error: src property must be a valid json object" for _, message in python_logs)


def test_json_browser_example_full_scene_matches_frozen_native_wire():
    python, rust = read(PYTHON / "strings/trace.json"), read(RUST / "strings/trace.json")
    assert_capture(python)
    assert_capture(rust)
    def payloads(capture):
        return [(tuple(message.metadata.delta_path), MessageToDict(message.delta.new_element, preserving_proto_field_name=True))
                for message in frames(capture) if isinstance(message, ForwardMsg) and message.WhichOneof("type") == "delta"]
    assert payloads(python) == payloads(rust) and len(payloads(python)) == 36


@pytest.mark.parametrize("mutation", ["missing", "url", "visible_text", "icon", "screenshot", "alert", "unicode"])
def test_json_ui_gate_rejects_incomplete_or_corrupt_evidence(mutation):
    capture = copy.deepcopy(read(PYTHON / "ui/trace.json"))
    if mutation == "missing":
        capture["steps"].pop()
    elif mutation == "url":
        capture["steps"][0]["url"] = "https://example.invalid/"
    elif mutation == "visible_text":
        capture["steps"][0]["main_text"] = "JSON string 0\nfabricated"
    elif mutation == "icon":
        capture["steps"][15]["json"][0]["icons"] = ["expanded-icon"]
    elif mutation == "screenshot":
        capture["screenshots"][0]["sha256"] = "0" * 64
    elif mutation == "alert":
        capture["steps"][8]["alerts"] = []
    else:
        capture["steps"][21]["main_text"] = capture["steps"][21]["main_text"].replace("🤖", "corrupt")
    with pytest.raises(AssertionError):
        assert_ui_capture(capture, PYTHON / "ui", "python")


def test_json_integer_depth_width_and_rejection_reference():
    capture = read(PYTHON / "expansion/trace.json")
    assert_capture(capture)
    assert capture["scenario"] == "expansion" and capture["cleanup"] == {"websocket_closed": True, "server_stopped": True}
    elements = capture["elements"]
    assert len(elements) == 28 and all(element["kind"] == "json" for element in elements)
    cases = json.loads(elements[0]["fields"]["body"])["expansion_cases"]
    assert len(cases) == 18
    reports, outputs = [], []
    for element in elements[1:]:
        body = json.loads(element["fields"]["body"])
        if "index" in body:
            reports.append(body)
        else:
            assert body == {"nested": {"items": [1, 2]}}
            outputs.append(element)
    accepted = [0, 1, 2, 3, 4, 5, 6, 7, 16]
    assert [report["index"] for report in reports] == list(range(18))
    assert [report["index"] for report in reports if report["ok"]] == accepted
    assert len(outputs) == len(accepted) == 9
    for index, element in zip(accepted, outputs):
        kwargs, fields = cases[index]["kwargs"], element["fields"]
        expanded = kwargs.get("expanded", True)
        if isinstance(expanded, bool):
            assert fields.get("expanded", False) == expanded and "max_expand_depth" not in fields
        else:
            assert fields["expanded"] is True and fields["max_expand_depth"] == expanded
        frame = next(frame for frame in capture["frames"] if frame["message"].get("metadata", {}).get("delta_path") == element["delta_path"])
        width = frame["message"]["delta"]["new_element"]["width_config"]
        assert width == ({"pixel_width": int(kwargs["width"])} if isinstance(kwargs.get("width"), int) else {"use_stretch": True})
    failures = {report["label"]: report for report in reports if not report["ok"]}
    assert failures["depth-overflow"]["error_type"] == "ValueError" and failures["depth-overflow"]["message"] == "Value out of range: 2147483648"
    assert all(failures[label]["error_type"] == "StreamlitInvalidParameterTypeError" for label in ("depth-float", "depth-text"))
    assert all(report["error_type"] == "StreamlitInvalidWidthError" for label, report in failures.items() if label.startswith("width-"))
