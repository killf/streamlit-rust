"""Frozen text/latex/help/divider parameter evidence (python + rust)."""
import base64
import json
from pathlib import Path

from google.protobuf.json_format import MessageToDict
from streamlit.proto.BackMsg_pb2 import BackMsg
from streamlit.proto.ForwardMsg_pb2 import ForwardMsg

PYTHON = Path(__file__).parent / "reference-browser/text-misc-params"
RUST = Path(__file__).parents[1] / "browser/rust-text-misc-params"


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
    return [(element["kind"], {key: value for key, value in element["fields"].items() if key != "id"}) for element in capture["elements"]]


def test_python_reference_rules():
    raw = read(PYTHON / "trace.json")
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
    assert raw["runtime"] == "rust" and raw["server_cleanup"] == "caller-owned"
    assert raw["finishes"] == [0]
    python = read(PYTHON / "trace.json")
    left, right = comparable(python), comparable(raw)
    assert len(left) == len(right) == 5
    for a, b in zip(left, right):
        assert a == b, (a, b)
