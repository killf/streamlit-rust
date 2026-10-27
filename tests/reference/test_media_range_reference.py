"""Offline links from public media URLs to original Range HTTP bytes."""

import base64
import hashlib
import json
from pathlib import Path

import pytest
from google.protobuf.json_format import MessageToDict
from streamlit.proto.BackMsg_pb2 import BackMsg
from streamlit.proto.ForwardMsg_pb2 import ForwardMsg


ROOT = Path(__file__).parent / "reference-browser/media-range"
CAPTURES = ("first", "integer-forms")


def read(name):
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


def test_range_data_integrity_and_rust_response_arrays():
    manifest = read("manifest.json")
    assert manifest["reference_version"] == "1.66.1" and len(manifest["files"]) == 13
    for item in manifest["files"]:
        path = (ROOT / item["file"]).resolve()
        assert path.is_relative_to(ROOT.resolve())
        data = path.read_bytes()
        assert len(data) == item["bytes"] and hashlib.sha256(data).hexdigest() == item["sha256"]
    derived = read("range-input-output.json")
    assert derived["reference_version"] == "1.66.1" and len(derived["cases"]) == 27
    expected = {(capture, i) for capture, count in zip(CAPTURES, (23, 4)) for i in range(count)}
    assert {(case["capture"], case["case_index"]) for case in derived["cases"]} == expected
    for case in derived["cases"]:
        original = read(f"{case['capture']}/trace.json")["responses"][case["case_index"]]
        assert {key: case[key] for key in ("label", "asset", "range_header", "url", "status", "headers")} == {key: original[key] for key in ("label", "asset", "range_header", "url", "status", "headers")}
        assert bytes(case["body_bytes"]) == base64.b64decode(original["body_base64"], validate=True)
    assert derived["asset_lengths"] == {key: value["bytes"] for key, value in read("first/inputs.json")["assets"].items()}


@pytest.mark.parametrize("capture", CAPTURES)
def test_frozen_public_media_emissions_and_protocol(capture):
    raw, compact, inputs = (read(f"{capture}/{name}.json") for name in ("trace", "range-cases", "inputs"))
    assert raw["reference_version"] == compact["reference_version"] == "1.66.1"
    assert raw["exceptions"] == [] and raw["finishes"] == [0]
    assert raw["handshake"]["status"] == 101 and raw["handshake"]["subprotocol"] == "streamlit"
    assets, versions, finishes = {}, [], []
    assert len(raw["frames"]) == (9 if capture == "first" else 7)
    for frame in raw["frames"]:
        data = base64.b64decode(frame["base64"], validate=True)
        assert len(data) == frame["bytes"]
        message = BackMsg() if frame["direction"] == "client->server" else ForwardMsg()
        message.ParseFromString(data)
        decoded = MessageToDict(message, preserving_proto_field_name=True)
        assert decoded == frame["message"]
        if "new_session" in decoded:
            versions.append(decoded["new_session"]["initialize"]["environment_info"]["streamlit_version"])
        if "script_finished" in decoded:
            finishes.append(decoded["script_finished"])
        element = decoded.get("delta", {}).get("new_element", {})
        if "download_button" in element or "video" in element:
            fields = element.get("download_button", element.get("video"))
            asset = fields["label"].removeprefix("range-") if "download_button" in element else "video"
            assert asset not in assets
            assets[asset] = {"url": fields["url"], "delta_path": decoded["metadata"]["delta_path"], "fields": fields}
    assert versions == ["1.66.1"] and finishes == ["FINISHED_SUCCESSFULLY"]
    assert assets == raw["emitted_assets"] == compact["emitted_assets"]
    assert raw["public_results"] == compact["public_results"] == [{"asset": key, "accepted": True} for key in inputs["assets"]]
    assert read(f"{capture}/execution.json")["exit_code"] == 0
    cleanup = raw["cleanup"]
    assert cleanup == compact["cleanup"] and raw["cleanup_errors"] == compact["cleanup_errors"] == []
    assert cleanup["websocket_closed"] and cleanup["close_code"] == 1000 and cleanup["server_stopped"]
    assert cleanup["listener_count"] == "0" and cleanup["listener_check_exit_code"] == 0 and not cleanup["browser_started"]


@pytest.mark.parametrize("capture", CAPTURES)
def test_range_http_requests_and_responses_match_original_payloads(capture):
    raw, compact, inputs = (read(f"{capture}/{name}.json") for name in ("trace", "range-cases", "inputs"))
    assert len(raw["responses"]) == len(compact["cases"]) == len(inputs["cases"]) == raw["completed_cases"]
    for original, response, case in zip(inputs["cases"], raw["responses"], compact["cases"]):
        assert all(case[key] == value for key, value in response.items())
        assert all(response[key] == value for key, value in original.items())
        assert response["url"] == raw["emitted_assets"][original["asset"]]["url"]
        request = base64.b64decode(response["request_base64"], validate=True)
        assert request.decode("ascii") == response["request_text"]
        assert request.startswith(f"GET {response['url']} HTTP/1.1\r\n".encode())
        header = original["range_header"]
        if header is None:
            assert b"\r\nRange:" not in request
        else:
            assert b"\r\nRange: " + header.encode("ascii") + b"\r\n" in request
        head, body = base64.b64decode(response["raw_response_base64"], validate=True).split(b"\r\n\r\n", 1)
        lines = head.decode("latin-1").split("\r\n")
        assert int(lines[0].split()[1]) == response["status"]
        assert [list((name, value.lstrip())) for name, value in (line.split(":", 1) for line in lines[1:])] == response["headers"]
        headers = {key.lower(): value for key, value in response["headers"]}
        assert body == base64.b64decode(response["body_base64"], validate=True)
        assert len(body) == response["body_length"] == int(headers["content-length"])
        asset = inputs["assets"][original["asset"]]
        payload = base64.b64decode(asset["payload_base64"], validate=True)
        assert len(payload) == asset["bytes"]
        if original["asset"] == "video":
            assert payload == (Path(__file__).parent / "video_sample.mp4").read_bytes()
        if response["status"] == 206:
            span, total = headers["content-range"].removeprefix("bytes ").split("/")
            start, end = map(int, span.split("-"))
            assert 0 <= start <= end < int(total) == len(payload)
            assert body == payload[start:end + 1] and headers["accept-ranges"] == "bytes"
        elif response["status"] == 416:
            assert body == b"Invalid range" and headers["content-range"] == f"bytes */{len(payload)}"
            assert headers["content-type"] == "text/plain; charset=utf-8"
            assert "accept-ranges" not in headers and "content-disposition" not in headers
        else:
            assert response["status"] == 200 and body == payload and "content-range" not in headers
