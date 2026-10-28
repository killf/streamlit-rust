"""Frozen public results and the distinct, visibly imperfect upstream UI."""
import base64
import hashlib
import json
from pathlib import Path

import pyarrow as pa
import pytest
from google.protobuf.json_format import MessageToDict
from streamlit.proto.BackMsg_pb2 import BackMsg
from streamlit.proto.ForwardMsg_pb2 import ForwardMsg

ROOT = Path(__file__).parent / "reference-browser/zero-columns"


def read(path):
    return json.loads((ROOT / path).read_text(encoding="utf-8-sig"))


def decode(frame):
    data = base64.b64decode(frame["base64"], validate=True)
    assert len(data) == frame["bytes"]
    if "sha256" in frame:
        assert hashlib.sha256(data).hexdigest() == frame["sha256"]
    message = BackMsg() if frame["direction"] == "client->server" else ForwardMsg()
    message.ParseFromString(data)
    assert MessageToDict(message, preserving_proto_field_name=True) == frame["message"]
    return message


def test_frozen_zero_column_files_are_data_only_and_complete():
    manifest = read("manifest.json")
    assert manifest["scope"] == "captured data only; no source identity gates"
    paths = []
    for item in manifest["files"]:
        path = (ROOT / item["file"]).resolve()
        assert path.is_relative_to(ROOT.resolve())
        assert path.suffix not in {".py", ".rs"}
        data = path.read_bytes()
        assert len(data) == item["bytes"]
        assert hashlib.sha256(data).hexdigest() == item["sha256"]
        paths.append(item["file"])
    assert len(paths) == len(set(paths))
    assert {"primary/trace.json", "table/trace.json", "ui/trace.json", "ui-first/trace.json"} <= set(paths)
    assert {f"ui/{name}.png" for name in ("zero-initial", "two-rows", "ordinary-rerun", "zero-again")} <= set(paths)
    audit = read("cleanup-verification.json")
    assert all(not item["present"] for item in audit["processes"])
    assert all(item["listeners"] == 0 for item in audit["ports"])
    assert all(not item["exists"] for item in audit["profiles"])


@pytest.mark.parametrize(("group", "count", "frame_count"), [("primary", 9, 32), ("table", 3, 14)])
def test_public_zero_column_calls_keep_rows_without_physical_index_columns(group, count, frame_count):
    raw = read(f"{group}/trace.json")
    compact = read(f"{group}/zero-column-cases.json")
    inputs = read(f"{group}/inputs.json")
    assert raw["reference_version"] == compact["reference_version"] == "1.66.1"
    assert raw["versions"] == {"streamlit": "1.66.1", "pandas": "3.1.0", "pyarrow": "26.0.0"}
    assert len(raw["frames"]) == frame_count
    decoded = [decode(frame) for frame in raw["frames"]]
    forwards = [message for frame, message in zip(raw["frames"], decoded) if frame["direction"] == "server->client"]
    sessions = [message.new_session for message in forwards if message.WhichOneof("type") == "new_session"]
    assert len(sessions) == 1 and sessions[0].initialize.environment_info.streamlit_version == "1.66.1"
    assert raw["finishes"] == [0] and not raw["unhandled_exceptions"]
    assert len(raw["cases"]) == count and compact["cases"] == raw["cases"]
    assert {case["label"] for case in raw["cases"]} == {case["label"] for case in inputs["cases"]}
    code_reports = {}
    for message in forwards:
        if message.WhichOneof("type") == "delta" and message.delta.WhichOneof("type") == "new_element":
            element = message.delta.new_element
            if element.WhichOneof("type") == "code":
                report = json.loads(element.code.code_text)
                assert report["label"] not in code_reports
                code_reports[report["label"]] = report

    for case in compact["cases"]:
        report = case["report"]
        assert report == code_reports[case["label"]]
        assert report["outcome"] == "returned" and report["caller_input_unchanged"]
        assert report["input_before"] == report["input_after"]
        expected_rows = 0 if report["input"] == "arrow-zero0" else 2
        assert (report["input_before"]["num_rows"], report["input_before"]["num_columns"]) == (expected_rows, 0)
        kind = "table" if report["operation"] == "table-index" else "dataframe"
        observations = case["tables" if kind == "table" else "dataframes"]
        assert len(observations) == 1
        observed = observations[0]
        message = decoded[observed["frame_index"]]
        assert message.delta.new_element.WhichOneof("type") == kind
        assert list(message.metadata.delta_path) == observed["delta_path"]
        view = getattr(message.delta.new_element, kind)
        fields = MessageToDict(view, preserving_proto_field_name=True)
        fields.pop("arrow_data")
        assert fields == observed["fields"]
        ipc = view.arrow_data.data
        assert ipc == base64.b64decode(observed["arrow_ipc_base64"], validate=True)
        assert ipc == (ROOT / group / (case["label"].replace("/", "--") + ".arrow")).read_bytes()
        table = pa.ipc.open_stream(ipc).read_all()
        assert (table.num_rows, table.num_columns) == (expected_rows, 0)
        assert table.to_pylist() == observed["rows"]
        assert observed["schema"]["fields"] == []
        metadata = [{"key_base64": base64.b64encode(key).decode(), "value_base64": base64.b64encode(value).decode()}
                    for key, value in (table.schema.metadata or {}).items()]
        assert metadata == observed["schema"]["metadata"]
        if report["operation"].startswith("editor"):
            returned = report["returned"]
            assert returned["type"] == report["input_before"]["type"]
            assert (returned["num_rows"], returned["num_columns"]) == (expected_rows, 0)
            assert view.columns == "{}" and view.editing_mode == 1
            assert view.disabled == inputs["operations"][report["operation"]].get("disabled", False)
            assert view.id.endswith("-" + case["label"])
            pandas = json.loads(table.schema.metadata[b"pandas"])
            assert pandas["index_columns"] == [{"kind": "range", "name": None, "start": 0, "stop": expected_rows, "step": 1}]
        elif report["input"].startswith("arrow"):
            assert table.schema.metadata is None
    assert read(f"{group}/execution.json")["exit_code"] == 0
    assert raw["cleanup_errors"] == []
    assert raw["cleanup"]["websocket_closed"] and raw["cleanup"]["close_code"] == 1000
    assert raw["cleanup"]["server_stopped"] and raw["cleanup"]["listener_count"] == "0"
    assert raw["cleanup"]["listener_check_exit_code"] == 0


def test_first_ui_flow_preserves_upstream_cell_errors_instead_of_claiming_success():
    raw = read("ui/trace.json")
    assert raw["runtime"] == "python" and raw["successful"]
    assert [stage["name"] for stage in raw["stages"]] == ["zero-initial", "two-rows", "ordinary-rerun", "zero-again"]
    messages = [decode(frame) for frame in raw["frames"]]
    assert len(messages) == 76
    for stage, rows in zip(raw["stages"], [0, 2, 2, 0]):
        frames = raw["frames"][stage["frame_start"]:stage["frame_end"]]
        observed = messages[stage["frame_start"]:stage["frame_end"]]
        assert [message.script_finished for frame, message in zip(frames, observed)
                if frame["direction"] == "server->client" and message.WhichOneof("type") == "script_finished"] == [0]
        views = []
        back_widgets = []
        for frame, message in zip(frames, observed):
            kind = message.WhichOneof("type")
            if frame["direction"] == "client->server" and kind == "rerun_script":
                back_widgets.extend(message.rerun_script.widget_states.widgets)
            elif kind == "new_session":
                assert message.new_session.initialize.environment_info.streamlit_version == "1.66.1"
            elif kind == "delta" and message.delta.WhichOneof("type") == "new_element":
                element = message.delta.new_element
                element_kind = element.WhichOneof("type")
                if element_kind in {"dataframe", "table"}:
                    views.append(pa.ipc.open_stream(getattr(element, element_kind).arrow_data.data).read_all())
        assert len(views) == 4 and all((view.num_rows, view.num_columns) == (rows, 0) for view in views)
        dom = stage["dom"]
        assert dom["checkboxes"] == [{"checked": rows == 2}] and dom["exceptions"] == []
        assert f"zero-input rows={rows} columns=0" in dom["text"]
        for label in ("disabled", "enabled"):
            assert f"zero-return={label} rows={rows} columns=0" in dom["text"]
        assert len(dom["grids"]) == 3
        cells = [[cell["text"] for cell in grid["cells"]] for grid in dom["grids"]]
        if rows:
            assert cells == [["Error during cell creation"] * 2, ["0", "1"], ["0", "1"]]
            assert dom["tables"][-1].strip() == ""
        else:
            assert cells == [[""], [""], [""]]
            assert dom["tables"][-1] == "empty"
        if stage["name"] != "zero-initial":
            assert any(widget.id.endswith("-zero-two") and widget.WhichOneof("value") == "bool_value"
                       and widget.bool_value == (rows == 2) for widget in back_widgets)
        if stage["name"] == "ordinary-rerun":
            assert any(widget.id.endswith("-zero-rerun") and widget.trigger_value for widget in back_widgets)
    assert raw["cleanup"] == {"chrome_stopped": True, "server_stopped": True} and not raw["cleanup_errors"]
    failed = read("ui-first/trace.json")
    assert failed["producer_error"] == "KeyError: 'value'"
    assert not failed.get("successful") and len(failed["stages"]) == 1
    assert failed["cleanup"] == {"chrome_stopped": True, "server_stopped": True} and not failed["cleanup_errors"]
