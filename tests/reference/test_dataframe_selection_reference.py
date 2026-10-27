"""Offline checks of frozen Python inputs; never launch or recollect the reference."""

import base64
import hashlib
import json
from pathlib import Path

import pytest
import pyarrow as pa
from google.protobuf.json_format import MessageToDict
from streamlit.proto.BackMsg_pb2 import BackMsg
from streamlit.proto.ForwardMsg_pb2 import ForwardMsg


PUBLISHED = Path(__file__).parent / "reference-browser/dataframe-selection"
STAGES = {
    "ignore": "load selection-attempt probe",
    "multi": "load row-first row-third ordinary-rerun sort-qty sorted-row-first replace hide hidden-probe restore",
    "single-combo": "load user-cell ordinary-rerun program-rows program-columns program-cells callback-cell",
    "multi-combo": "load row-first row-third column-id column-qty rectangle",
    "required": "load row-third clear-attempt probe",
    "multi-shrink": "load row-third replace-shrink probe-after-shrink",
}


@pytest.fixture(scope="module")
def frozen():
    cases = json.loads((PUBLISHED / "selection-input-output.json").read_text(encoding="utf-8"))
    raw = {c["name"]: json.loads((PUBLISHED / c["raw_file"]).read_text(encoding="utf-8")) for c in cases["captures"]}
    stages = {(s["case"], s["name"]): s for s in cases["stages"]}
    return cases, raw, stages


def test_frozen_data_integrity_and_actual_wire(frozen):
    cases, captures, _ = frozen
    manifest = json.loads((PUBLISHED / "manifest.json").read_text(encoding="utf-8"))
    for item in manifest["files"]:
        path = (PUBLISHED / item["file"]).resolve()
        assert path.is_relative_to(PUBLISHED.resolve())
        data = path.read_bytes()
        assert len(data) == item["bytes"] and hashlib.sha256(data).hexdigest() == item["sha256"]
    assert cases["reference_version"] == "1.66.1"
    assert sum(len(c["frames"]) for c in captures.values()) == 512
    for capture in captures.values():
        assert not capture.get("producer_error") and not capture["case_errors"]
        assert capture["cleanup"] == {"chrome_stopped": True, "server_stopped": True}
        assert capture["cleanup_errors"] == []
        binary = [e for e in capture["events"] if e.get("method") in
                  ("Network.webSocketFrameSent", "Network.webSocketFrameReceived") and e["params"]["response"]["opcode"] == 2]
        assert len(binary) == len(capture["frames"])
        versions = set()
        for frame in capture["frames"]:
            data = base64.b64decode(frame["base64"], validate=True)
            assert len(data) == frame["bytes"] and hashlib.sha256(data).hexdigest() == frame["sha256"]
            message = BackMsg() if frame["direction"] == "client->server" else ForwardMsg()
            message.ParseFromString(data)
            assert MessageToDict(message, preserving_proto_field_name=True) == frame["message"]
            event = capture["events"][frame["event_index"]]
            assert event["params"]["response"]["payloadData"] == frame["base64"]
            if isinstance(message, ForwardMsg) and message.WhichOneof("type") == "new_session":
                versions.add(message.new_session.initialize.environment_info.streamlit_version)
        assert versions == {"1.66.1"}


def test_compact_inputs_and_results_match_raw_stages(frozen):
    cases, captures, stages = frozen
    assert len(stages) == len(cases["stages"]) == 34
    for case, names in STAGES.items():
        assert [s["name"] for s in cases["stages"] if s["case"] == case] == names.split()
    for name, capture in captures.items():
        previous_end = 0
        for raw in capture["stages"]:
            compact = stages[raw["case"], raw["name"]]
            assert compact["capture"] == name
            assert raw["frame_start"] == previous_end
            previous_end = raw["frame_end"]
            observed = json.loads(raw["dom"]["code"])
            assert observed == raw["observed"] and not raw["dom"]["exceptions"]
            for key in ("input_rows", "version", "visible", "run", "trigger", "before", "events"):
                assert compact[key] == observed[key]
            for key in ("returned", "returned_type", "keyed", "key_present"):
                assert compact["expected_" + key] == observed[key]
            assert compact["visual_cells"] == raw["dom"]["cells"]
            messages = capture["frames"][raw["frame_start"]:raw["frame_end"]]
            finished = [f["message"]["script_finished"] for f in messages if "script_finished" in f["message"]]
            assert finished == (["FINISHED_SUCCESSFULLY"] if raw["did_run"] else [])
            codes = [f["message"].get("delta", {}).get("new_element", {}).get("code", {}).get("code_text") for f in messages]
            if raw["did_run"]:
                assert json.loads(next(code for code in reversed(codes) if code is not None)) == observed
            else:
                assert not messages
            png = (PUBLISHED / compact["screenshot"]["file"]).read_bytes()
            assert png.startswith(b"\x89PNG\r\n\x1a\n")
            assert hashlib.sha256(png).hexdigest() == compact["screenshot"]["sha256"]
            widgets, dataframes, run_messages = [], [], []
            for index in range(raw["frame_start"], raw["frame_end"]):
                frame = capture["frames"][index]["message"]
                for widget in frame.get("rerun_script", {}).get("widget_states", {}).get("widgets", []):
                    if widget["id"].endswith("-selection-" + raw["case"]):
                        value_key, = set(widget) - {"id"}
                        widgets.append({"frame_index": index, "message_oneof": "rerun_script", "id": widget["id"],
                                        "value_oneof": value_key, "value": widget[value_key]})
                dataframe = frame.get("delta", {}).get("new_element", {}).get("dataframe")
                if dataframe is not None:
                    table = pa.ipc.open_stream(base64.b64decode(dataframe["arrow_data"]["data"])).read_all()
                    assert table.to_pylist() == observed["input_rows"]
                    dataframes.append({"frame_index": index, "message_oneof": "delta", "delta_oneof": "new_element",
                                       "element_oneof": "dataframe", "delta_path": frame.get("metadata", {}).get("delta_path", []),
                                       "fields": {k: v for k, v in dataframe.items() if k != "arrow_data"}})
                if "new_session" in frame:
                    session = frame["new_session"]
                    run_messages.append({"frame_index": index, "message_oneof": "new_session", "script_run_id": session["script_run_id"],
                                         "session_id": session["initialize"]["session_id"],
                                         "wire_version": session["initialize"]["environment_info"]["streamlit_version"]})
                elif "script_finished" in frame:
                    run_messages.append({"frame_index": index, "message_oneof": "script_finished", "status": frame["script_finished"]})
            assert compact["target_widget_states"] == widgets
            assert compact["dataframes"] == dataframes
            assert compact["run_messages"] == run_messages
        assert previous_end == len(capture["frames"])


def test_sort_keeps_original_input_positions_and_multiselections(frozen):
    _, _, stages = frozen
    before = stages["multi", "row-third"]
    sorted_view = stages["multi", "sort-qty"]
    selected = stages["multi", "sorted-row-first"]
    assert before["expected_returned"]["selection"]["rows"] == [0, 2]
    assert not sorted_view["did_run"]
    assert [c["text"] for c in sorted_view["visual_cells"]] == ["rA", "10", "A", "rB", "20", "B", "rC", "30", "C"]
    assert selected["expected_returned"]["selection"]["rows"] == [0, 1, 2]
    rectangle = stages["multi-combo", "rectangle"]["expected_returned"]["selection"]
    assert rectangle == {"rows": [0, 2], "columns": ["id", "qty"],
                         "cells": [[r, c] for r in range(3) for c in ("id", "qty")]}


def test_partial_program_state_and_callback_order(frozen):
    _, _, stages = frozen
    for field, value in (("rows", [0]), ("columns", ["id"]), ("cells", [[0, "qty"]])):
        stage = stages["single-combo", "program-" + field]
        assert stage["expected_keyed"] == {"selection": {field: value}}
        expected = {"rows": [], "columns": [], "cells": []}
        expected[field] = value
        assert stage["expected_returned"] == {"selection": expected}
    # 程序设置后回调可来自下一次浏览器回送，不能当作赋值当轮触发。
    rows_events = stages["single-combo", "program-rows"]["events"]
    assert [e["kind"] for e in rows_events[-2:]] == ["main", "main"]
    columns_events = stages["single-combo", "program-columns"]["events"]
    assert columns_events[-2] == {"kind": "callback", "run_seen": 4,
                                   "state": {"selection": {"rows": [0], "columns": [], "cells": []}}}
    assert columns_events[-1] == {"kind": "main", "run": 5}
    callback = stages["single-combo", "callback-cell"]["events"][-2:]
    assert callback[0]["kind"] == "callback" and callback[0]["run_seen"] == 6
    assert callback[1] == {"kind": "main", "run": 7}


def test_hidden_cleanup_and_required_selection(frozen):
    _, _, stages = frozen
    assert stages["multi", "hide"]["expected_key_present"]
    assert not stages["multi", "hidden-probe"]["expected_key_present"]
    assert stages["multi", "restore"]["expected_returned"]["selection"] == {"rows": [], "columns": [], "cells": []}
    assert stages["required", "load"]["expected_returned"]["selection"]["rows"] == [0]
    assert not stages["required", "clear-attempt"]["did_run"]
    assert stages["required", "probe"]["expected_returned"]["selection"]["rows"] == [2]
    assert not stages["ignore", "selection-attempt"]["did_run"]
    assert stages["ignore", "probe"]["expected_returned_type"] == "DeltaGenerator"
    assert not stages["ignore", "probe"]["expected_key_present"]


def test_shrinking_data_does_not_invent_selection_cleanup(frozen):
    _, _, stages = frozen
    assert len(stages["multi-shrink", "row-third"]["input_rows"]) == 3
    for name in ("replace-shrink", "probe-after-shrink"):
        stage = stages["multi-shrink", name]
        assert len(stage["input_rows"]) == 1
        assert stage["expected_returned"]["selection"]["rows"] == [2]
        assert stage["expected_keyed"] == stage["expected_returned"]
