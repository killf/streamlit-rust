"""Offline links for editor row bounds; script and protocol evidence stay distinct."""

import base64
import hashlib
import json
from pathlib import Path

import pyarrow as pa
from google.protobuf.json_format import MessageToDict
from streamlit.proto.BackMsg_pb2 import BackMsg
from streamlit.proto.ForwardMsg_pb2 import ForwardMsg


ROOT = Path(__file__).parent / "reference-browser/dataeditor-invalid-rows"


def read(name):
    return json.loads((ROOT / name).read_text(encoding="utf-8-sig"))


def test_frozen_editor_helper_cases_preserve_inputs_and_record_index_differences():
    for item in read("manifest.json")["files"]:
        path = (ROOT / item["file"]).resolve()
        assert path.is_relative_to(ROOT.resolve())
        data = path.read_bytes()
        assert len(data) == item["bytes"] and hashlib.sha256(data).hexdigest() == item["sha256"]
    reference = read("observations.json")
    assert reference["versions"]["streamlit"] == "1.66.1"
    cases = {case["name"]: case for case in reference["cases"]}
    assert len(cases) == 18
    for item in read("inputs.json"):
        case = cases[item["name"]]
        assert item["ui_value"] == case["input_string_value"]
        assert json.loads(item["ui_value"]) == case["deserialized_state"]
        assert case["original_unchanged"] and case["original_before"] == case["original_after"]
    for name in ("delete-equals-len", "delete-far", "delete-valid-then-invalid", "delete-invalid-then-valid", "edit-equals-len", "edit-far"):
        assert cases[name]["outcome"] == "exception" and cases[name]["exception_type"] == "builtins.IndexError"
    assert cases["delete-u64-max"]["exception_type"] == "builtins.OverflowError"
    assert cases["delete-duplicate"]["working_after"]["rows"] == [{"qty": 2, "label": "b"}]
    assert cases["delete-ascending"]["working_after"]["rows"] == cases["delete-descending"]["working_after"]["rows"] == []
    # 这是已观察差异，不把未采纳的负索引策略写成 Rust 验收要求。
    assert cases["delete-negative-one"]["working_after"]["rows"] == [{"qty": 1, "label": "a"}]
    assert cases["delete-negative-beyond"]["exception_type"] == "builtins.IndexError"


def test_frozen_editor_protocol_error_and_same_connection_recovery():
    raw = read("protocol-first/trace.json")
    compact = read("protocol-first/protocol-input-output.json")
    assert raw["reference_version"] == compact["reference_version"] == "1.66.1"
    assert raw["browser"] is None and raw["completed_all_stages"]
    assert len(raw["frames"]) == 30 and len(compact["stages"]) == 4
    sessions, editor_ids, versions = set(), set(), set()
    for frame in raw["frames"]:
        data = base64.b64decode(frame["base64"], validate=True)
        assert len(data) == frame["bytes"]
        message = BackMsg() if frame["direction"] == "client->server" else ForwardMsg()
        message.ParseFromString(data)
        assert MessageToDict(message, preserving_proto_field_name=True) == frame["message"]
        if "new_session" in frame["message"]:
            init = frame["message"]["new_session"]["initialize"]
            sessions.add(init["session_id"])
            versions.add(init["environment_info"]["streamlit_version"])
    for stage in compact["stages"]:
        frames = raw["frames"][stage["frame_start"]:stage["frame_end"]]
        inputs = [widget["string_value"] for frame in frames for widget in frame["message"].get("rerun_script", {}).get("widget_states", {}).get("widgets", [])]
        assert inputs == ([] if stage["input_string_value"] is None else [stage["input_string_value"]])
        assert [f["message"]["script_finished"] for f in frames if "script_finished" in f["message"]] == ["FINISHED_SUCCESSFULLY"]
        dataframes, exceptions, markdowns = [], [], []
        for frame in frames:
            message = frame["message"]
            element = message.get("delta", {}).get("new_element", {})
            path = message.get("metadata", {}).get("delta_path", [])
            if "dataframe" in element:
                dataframe = element["dataframe"]
                table = pa.ipc.open_stream(base64.b64decode(dataframe["arrow_data"]["data"])).read_all()
                dataframes.append({"delta_path": path, "fields": {k: v for k, v in dataframe.items() if k != "arrow_data"},
                                   "rows": table.to_pylist(), "row_count": table.num_rows,
                                   "schema": [{"name": f.name, "type": str(f.type), "nullable": f.nullable} for f in table.schema]})
                if "id" in dataframe:
                    editor_ids.add(dataframe["id"])
            if "exception" in element:
                exceptions.append({"delta_path": path, "fields": element["exception"]})
            if "markdown" in element:
                markdowns.append(element["markdown"]["body"])
        assert (dataframes, exceptions, markdowns) == (stage["dataframes"], stage["exceptions"], stage["markdowns"])
        assert stage["socket_state_after"] == "OPEN"
    assert len(sessions) == len(editor_ids) == 1 and versions == {"1.66.1"}
    stages = compact["stages"]
    assert stages[1]["exceptions"][0]["fields"]["type"] == "IndexError" and stages[1]["dataframes"] == []
    assert stages[2]["dataframes"][1]["rows"] == [{"qty": 2, "label": "b"}]
    assert stages[3]["dataframes"][1]["rows"] == stages[0]["dataframes"][1]["rows"]
    final = read("cleanup-final-verification.json")
    assert final["owned_pid"] == raw["server_pid"] and final["owned_pid_absent"] and final["listener_count"] == 0
    assert raw["cleanup"]["websocket_closed"] and raw["cleanup"]["close_code"] == 1000
    # 首次即时检查失利原样保留，随后独立确认；不能改写成一次无错误退出。
    assert read("protocol-first/cleanup-verification.json")["initial_cleanup"] == raw["cleanup"]
