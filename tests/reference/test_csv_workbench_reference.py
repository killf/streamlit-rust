"""Frozen text-CSV observations; never starts Python, Chrome, or a server."""

import base64
import csv
import hashlib
import io
import json
from pathlib import Path

import pyarrow as pa
from google.protobuf.json_format import MessageToDict
from streamlit.proto.BackMsg_pb2 import BackMsg
from streamlit.proto.ForwardMsg_pb2 import ForwardMsg


PUBLISHED = Path(__file__).parent / "reference-browser/csv-workbench"


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_csv_compact_matches_original_protocol_arrow_and_downloads():
    manifest = read_json(PUBLISHED / "manifest.json")
    for item in manifest["files"]:
        path = (PUBLISHED / item["file"]).resolve()
        assert path.is_relative_to(PUBLISHED.resolve())
        data = path.read_bytes()
        assert len(data) == item["bytes"]
        assert hashlib.sha256(data).hexdigest() == item["sha256"]
    compact = read_json(PUBLISHED / "csv-input-output.json")
    assert compact["reference_version"] == "1.66.1" and len(compact["stages"]) == 33
    captures = {}
    for item in compact["captures"]:
        raw = (PUBLISHED / item["raw_file"]).read_bytes()
        assert len(raw) == item["bytes"] and hashlib.sha256(raw).hexdigest() == item["sha256"]
        capture = json.loads(raw)
        assert capture["runtime"] == "python" and capture["successful"]
        assert capture["cleanup"] == {"chrome_stopped": True, "server_stopped": True}
        assert not capture.get("cleanup_errors") and not capture.get("recorder_cleanup_errors")
        versions = set()
        for target in capture["targets"].values():
            for frame in target["frames"]:
                data = base64.b64decode(frame["base64"], validate=True)
                assert len(data) == frame["bytes"]
                message = BackMsg() if frame["direction"] == "client->server" else ForwardMsg()
                message.ParseFromString(data)
                assert MessageToDict(message, preserving_proto_field_name=True) == frame["message"]
                if "new_session" in frame["message"]:
                    versions.add(frame["message"]["new_session"]["initialize"]["environment_info"]["streamlit_version"])
        assert versions == {"1.66.1"}
        captures[item["name"]] = capture

    for stage in compact["stages"]:
        capture = captures[stage["capture"]]
        frames = capture["targets"][stage["target"]]["frames"]
        window = frames[stage["frame_start"]:stage["frame_end"]]
        assert [f["message"]["script_finished"] for f in window if "script_finished" in f["message"]] == stage["finishes"]
        inputs = []
        for index in range(stage["frame_start"], stage["frame_end"]):
            for widget in frames[index]["message"].get("rerun_script", {}).get("widget_states", {}).get("widgets", []):
                value_key, = set(widget) - {"id"}
                inputs.append({"frame_index": index, "id": widget["id"], "value_oneof": value_key, "value": widget[value_key]})
        assert inputs == stage["widget_inputs"]
        for key in ("visible_table", "detail_source_table", "new_editor_input_table"):
            table = stage[key]
            if table is None:
                continue
            assert stage["state_source_run_start"] <= table["frame_index"] < stage["frame_end"]
            message = frames[table["frame_index"]]["message"]
            dataframe = message["delta"]["new_element"]["dataframe"]
            actual = pa.ipc.open_stream(base64.b64decode(dataframe["arrow_data"]["data"])).read_all()
            assert actual.to_pylist() == table["rows"]
            assert [{"name": f.name, "type": str(f.type), "nullable": f.nullable} for f in actual.schema] == table["schema"]
            assert {k: v for k, v in dataframe.items() if k != "arrow_data"} == table["fields"]
            assert message.get("metadata", {}).get("delta_path", []) == table["delta_path"]
        assert stage["visible_rows"] == (stage["visible_table"]["rows"] if stage["visible_table"] else None)
        if stage["chart_present"]:
            charts = [f["message"].get("delta", {}).get("new_element", {}).get("vega_lite_chart")
                      for f in frames[stage["state_source_run_start"]:stage["frame_end"]]]
            chart = next(chart for chart in reversed(charts) if chart is not None)
            counts = pa.ipc.open_stream(base64.b64decode(chart["data"]["data"])).read_all().to_pylist()
            assert counts == stage["counts"]
        else:
            assert stage["counts"] is None
        if "download" in stage:
            download = stage["download"]
            data = (PUBLISHED / download["file"]).read_bytes()
            assert data == base64.b64decode(download["base64"], validate=True)
            assert len(data) == download["bytes"] and hashlib.sha256(data).hexdigest() == download["sha256"]
            parsed = list(csv.reader(io.StringIO(data.decode("utf-8"), newline=""), strict=True))
            assert parsed == [download["headers"], *download["rows"]]
            assert not data.startswith(b"\xef\xbb\xbf") and b"\r\n" not in data


def test_csv_frozen_working_copy_and_session_boundaries():
    compact = read_json(PUBLISHED / "csv-input-output.json")
    main = {s["name"]: s for s in compact["stages"] if s["capture"] == "main-complete"}
    before = main["download-unapplied"]["download"]["rows"]
    applied = main["download-applied"]["download"]["rows"]
    appended = main["download-appended"]["download"]["rows"]
    assert before[1][0:2] == ["rA", "south"] and applied[1][0:2] == ["rA", "north"]
    assert applied[0] == before[0] and applied[2] == before[2]
    assert appended[:-1] == applied and appended[-1] == ["new", "", "", ""]
    assert main["A-after-B-download"]["download"]["rows"] == appended
    assert main["isolated-download"]["download"]["rows"] == [["other", "east", "5", "replaced"]]
    source = read_json(PUBLISHED / "main-complete/trace.json")
    sessions = [{f["message"]["new_session"]["initialize"]["session_id"] for f in target["frames"] if "new_session" in f["message"]}
                for target in source["targets"].values()]
    assert len(sessions) == 2 and all(len(ids) == 1 for ids in sessions) and sessions[0].isdisjoint(sessions[1])
    filters = {s["name"]: s for s in compact["stages"] if s["capture"] == "filters-first"}
    assert filters["enable-empty-match"]["visible_rows"] == []
    assert [row["item"] for row in filters["filter-region-empty"]["visible_rows"]] == ["rB"]
    assert filters["no-match"]["visible_rows"] == []
    assert len(filters["disable-keep-value"]["visible_rows"]) == 3
    assert filters["filtered-flow-download"]["download"]["rows"][-1] == ["pending", "", "", ""]
