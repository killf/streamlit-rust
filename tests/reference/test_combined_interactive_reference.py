"""The second M7 combined differential: the interactive flow, both runtimes."""
import base64
import json
from pathlib import Path

from google.protobuf.json_format import MessageToDict
from streamlit.proto.BackMsg_pb2 import BackMsg
from streamlit.proto.ForwardMsg_pb2 import ForwardMsg

PYTHON = Path(__file__).parent / "reference-browser/combined-interactive"
RUST = Path(__file__).parents[1] / "browser/rust-combined-interactive"
STAGES = ["load", "upload-two", "check", "pick-b", "select-row-2", "apply"]
EXPECTED = [
    {"applied": False, "checked": False, "files": [], "picked": "a", "row": None},
    {"applied": False, "checked": False, "files": ["alpha.txt", "beta.csv"], "picked": "a", "row": None},
    {"applied": False, "checked": True, "files": ["alpha.txt", "beta.csv"], "picked": "a", "row": None},
    {"applied": False, "checked": True, "files": ["alpha.txt", "beta.csv"], "picked": "b", "row": None},
    {"applied": False, "checked": True, "files": ["alpha.txt", "beta.csv"], "picked": "b", "row": 0},
    {"applied": True, "checked": True, "files": ["alpha.txt", "beta.csv"], "picked": "b", "row": 0},
]


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


def flow(capture):
    assert capture["successful"] and "producer_error" not in capture
    assert [stage["name"] for stage in capture["stages"]] == STAGES
    for stage, report in zip(capture["stages"], EXPECTED):
        assert stage["report"] == report, (stage["name"], stage["report"])
        assert stage["dom"]["exceptions"] == []
    uploads = [upload for upload in capture["uploads"] if upload["method"] == "PUT"]
    assert len(uploads) == 2, "both files are PUT once"
    return capture


def test_python_reference_interactive_flow():
    raw = flow(read(PYTHON / "trace.json"))
    assert raw["runtime"] == "python" and raw["reference_version"] == "1.66.1"
    assert raw["server_cleanup"] == "collector-owned" and raw["profile_cleaned"] is True and raw["server_stopped"] is True
    stages = {stage["name"]: stage for stage in raw["stages"]}
    assert stages["upload-two"]["dom"]["chips"] == ["alpha.txt", "beta.csv"]
    assert stages["check"]["dom"]["checkbox"] is True
    assert stages["apply"]["dom"]["toasts"] == ["applied"]
    # The widget states ride every rerun after their first interaction.
    states = []
    for message in frames(raw):
        if message.WhichOneof("type") == "rerun_script":
            states.append(sorted(widget.id.rsplit("-", 1)[-1] for widget in message.rerun_script.widget_states.widgets))
    assert states and states[-1] == ["cb", "df", "go", "k", "sel"], states[-1:]


def test_rust_flow_matches_report_for_report():
    raw = flow(read(RUST / "trace.json"))
    assert raw["runtime"] == "rust" and raw["server_cleanup"] == "caller-owned"
    python = read(PYTHON / "trace.json")
    for rust_stage, python_stage in zip(raw["stages"], python["stages"]):
        assert rust_stage["report"] == python_stage["report"], rust_stage["name"]
    stages = {stage["name"]: stage for stage in raw["stages"]}
    assert stages["upload-two"]["dom"]["chips"] == ["alpha.txt", "beta.csv"]
    assert stages["check"]["dom"]["checkbox"] is True
    assert stages["apply"]["dom"]["toasts"] == ["applied"]
    # The final rerun carries the same widget-state set as the reference.
    states = []
    for message in frames(raw):
        if message.WhichOneof("type") == "rerun_script":
            states.append(sorted(widget.id.rsplit("-", 1)[-1] for widget in message.rerun_script.widget_states.widgets))
    assert states and states[-1] == ["cb", "df", "go", "k", "sel"], states[-1:]
