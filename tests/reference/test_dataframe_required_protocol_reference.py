"""Offline replay of required-row protocol observations, without a reference server."""

import base64
import hashlib
import json
from pathlib import Path

import pyarrow as pa
from google.protobuf.json_format import MessageToDict
from streamlit.proto.BackMsg_pb2 import BackMsg
from streamlit.proto.ForwardMsg_pb2 import ForwardMsg


PUBLISHED = Path(__file__).parent / "reference-browser/dataframe-required-protocol"


def load():
    return (json.loads((PUBLISHED / "first-attempt/trace.json").read_text(encoding="utf-8")),
            json.loads((PUBLISHED / "required-protocol-input-output.json").read_text(encoding="utf-8")))


def test_required_protocol_data_and_compact_match_original_wire():
    capture, compact = load()
    manifest = json.loads((PUBLISHED / "manifest.json").read_text(encoding="utf-8"))
    for item in manifest["files"]:
        path = (PUBLISHED / item["file"]).resolve()
        assert path.is_relative_to(PUBLISHED.resolve())
        data = path.read_bytes()
        assert len(data) == item["bytes"] and hashlib.sha256(data).hexdigest() == item["sha256"]
    assert capture["transport"] == "native-websocket-protocol-probe"
    assert capture["successful"] and capture["cleanup_errors"] == []
    assert capture["cleanup"] == {"server_stopped": True, "websocket_closed": True}
    assert len(capture["frames"]) == 176
    versions = set()
    for frame in capture["frames"]:
        assert frame["direction"] in ("client->server", "server->client")
        data = base64.b64decode(frame["base64"], validate=True)
        assert len(data) == frame["bytes"] and hashlib.sha256(data).hexdigest() == frame["sha256"]
        message = BackMsg() if frame["direction"] == "client->server" else ForwardMsg()
        message.ParseFromString(data)
        assert MessageToDict(message, preserving_proto_field_name=True) == frame["message"]
        if isinstance(message, ForwardMsg) and message.WhichOneof("type") == "new_session":
            versions.add(message.new_session.initialize.environment_info.streamlit_version)
    assert versions == {"1.66.1"}

    assert len(capture["stages"]) == len(compact["stages"]) == 8
    previous_end = 0
    for stage, case in zip(capture["stages"], compact["stages"], strict=True):
        assert stage["name"] == case["name"]
        assert stage["frame_start"] == previous_end
        previous_end = stage["frame_end"]
        frames = capture["frames"][stage["frame_start"]:stage["frame_end"]]
        codes = [f["message"].get("delta", {}).get("new_element", {}).get("code", {}).get("code_text") for f in frames]
        observed = json.loads(next(code for code in reversed(codes) if code is not None))
        assert observed == stage["observed"]
        assert [f["message"]["script_finished"] for f in frames if "script_finished" in f["message"]] == ["FINISHED_SUCCESSFULLY"]
        for field in ("input_rows", "version", "visible", "run", "before", "events"):
            assert case[field] == observed[field]
        for field in ("returned", "keyed", "key_present"):
            assert case["expected_" + field] == observed[field]
        inputs, dataframes = [], []
        for index in range(stage["frame_start"], stage["frame_end"]):
            message = capture["frames"][index]["message"]
            for widget in message.get("rerun_script", {}).get("widget_states", {}).get("widgets", []):
                value_key, = set(widget) - {"id"}
                inputs.append({"frame_index": index, "id": widget["id"], "value_oneof": value_key, "value": widget[value_key]})
            dataframe = message.get("delta", {}).get("new_element", {}).get("dataframe")
            if dataframe is not None:
                table = pa.ipc.open_stream(base64.b64decode(dataframe["arrow_data"]["data"])).read_all()
                assert table.to_pylist() == observed["input_rows"]
                dataframes.append({"frame_index": index, "delta_path": message.get("metadata", {}).get("delta_path", []),
                                   "fields": {k: v for k, v in dataframe.items() if k != "arrow_data"},
                                   "schema": [{"name": f.name, "type": str(f.type), "nullable": f.nullable} for f in table.schema],
                                   "rows": table.to_pylist()})
        assert case["all_widget_inputs"] == inputs
        assert case["target_widget_states"] == [w for w in inputs if w["id"].endswith("-selection-required-protocol")]
        assert case["dataframes"] == dataframes
        assert case["server_selection_state"] == dataframes[0]["fields"].get("selection_state")
    assert previous_end == len(capture["frames"])
    # 直接连接两个 raw PB 字段，不能仅用 compact 内部的同名值证明 echo。
    before_echo, echo = capture["stages"][6:8]
    emitted = [f["message"]["delta"]["new_element"]["dataframe"]["selection_state"]
               for f in capture["frames"][before_echo["frame_start"]:before_echo["frame_end"]]
               if "selection_state" in f["message"].get("delta", {}).get("new_element", {}).get("dataframe", {})]
    incoming = [w["string_value"] for f in capture["frames"][echo["frame_start"]:echo["frame_end"]]
                for w in f["message"].get("rerun_script", {}).get("widget_states", {}).get("widgets", [])
                if w["id"].endswith("-selection-required-protocol")]
    assert emitted == incoming and len(emitted) == 1


def test_required_protocol_row_count_lifecycle_and_exact_server_echo():
    _, compact = load()
    stages = compact["stages"]
    expected_rows = [[0], [0], [0], [0], [], [], [0], [0]]
    assert [len(stage["input_rows"]) for stage in stages] == [3, 3, 3, 0, 0, 3, 3, 3]
    assert [stage["expected_returned"]["selection"]["rows"] for stage in stages] == expected_rows
    assert stages[6]["expected_keyed"] == {"selection": {"rows": []}}
    for index, stage in enumerate(stages):
        if index != 6:
            assert stage["expected_keyed"] == stage["expected_returned"]
        callbacks = [event for event in stage["events"] if event["kind"] == "callback"]
        assert len(callbacks) == sum(index >= when for when in (4, 6, 7))
        if index in (4, 6, 7):
            assert stage["events"][-2]["kind"] == "callback"
            assert stage["events"][-2]["run_seen"] == index
            assert stage["events"][-1] == {"kind": "main", "run": index + 1}
    # 回送字节来自上一轮实际输出，不由 Rust 或测试自行生成预期。
    assert stages[7]["target_widget_states"][0]["value"] == stages[6]["server_selection_state"]
