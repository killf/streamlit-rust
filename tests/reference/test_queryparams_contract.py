"""Unit tests of the strict query-params contract (journey-queryparams-v1)."""
from __future__ import annotations

import copy
import hashlib
import json
import pathlib
import sys

import pytest

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "browser"))

from queryparams_contract import (  # noqa: E402
    QUERYPARAMS_DOMS,
    QUERYPARAMS_PAGE_INFOS,
    QUERYPARAMS_REQUIRED,
    QUERYPARAMS_RERUNS,
    QUERYPARAMS_SOURCE_FILES,
    QUERYPARAMS_STAGES,
    QUERYPARAMS_TIMELINE,
    queryparams_result,
)

PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"not-a-real-image-but-magic-and-hash-are-checked"


def read_query_param_capture(scenario):
    import base64
    from google.protobuf.json_format import MessageToDict
    from streamlit.proto.BackMsg_pb2 import BackMsg
    from streamlit.proto.ForwardMsg_pb2 import ForwardMsg

    capture = json.loads((HERE / f"reference-browser/queryparams/{scenario}/trace.json").read_text(encoding="utf-8-sig"))
    assert capture["runtime"] == "python" and capture["reference_version"] == "1.66.1"
    assert capture["successful"] and "producer_error" not in capture
    assert capture["cleanup"] == {"websocket_closed": True, "server_stopped": True}
    snapshots, urls, finishes, requests, histories, errors = [], [], [], [], [], []
    for frame in capture["frames"]:
        assert frame["direction"] in ("client->server", "server->client")
        raw = base64.b64decode(frame["base64"], validate=True)
        assert len(raw) == frame["bytes"]
        message = BackMsg() if frame["direction"] == "client->server" else ForwardMsg()
        message.ParseFromString(raw)
        assert MessageToDict(message, preserving_proto_field_name=True) == frame["message"]
        if isinstance(message, BackMsg):
            requests.append(message.rerun_script.query_string)
            histories.append(message.rerun_script.is_history_navigation)
        elif message.WhichOneof("type") == "script_finished":
            finishes.append(message.script_finished)
        elif message.WhichOneof("type") == "page_info_changed":
            urls.append(message.page_info_changed.query_string)
        elif message.WhichOneof("type") == "delta" and message.delta.WhichOneof("type") == "new_element":
            element = message.delta.new_element
            if element.WhichOneof("type") == "exception":
                assert scenario == "disabled", "reference must not contain an unexpected exception"
                errors.append(element.exception)
                assert element.exception.type == "TypeError"
                assert element.exception.message == "'str' object cannot be interpreted as an integer"
                assert not element.exception.message_is_markdown and not element.exception.is_streamlit_exception
                assert len(element.exception.stack_trace) == 2
            if element.WhichOneof("type") == "json":
                snapshots.append(json.loads(element.json.body))
    assert len(errors) == (1 if scenario == "disabled" else 0)
    if scenario == "navigation-rerun":
        assert requests == ["probe=load", "probe=switch"] and histories == [False, False]
        assert finishes == [0, 2, 0]
    elif scenario == "rerun-queue":
        assert requests == ["case=queue&phase=warm", "case=queue&phase=queue"] and histories == [False, False]
        assert finishes == [0, 2, 0]
    elif scenario == "rerun-messages":
        assert requests == [capture["query_string"]] and histories == [False]
        assert finishes == [2, 0]
    elif scenario == "rerun":
        assert len(requests) == 5 and requests[0] == capture["query_string"]
        assert histories == [False] * 4 + [True] and finishes == [2, 0] * 5
        assert [query.split("phase=")[1].split("&")[0] for query in requests] == ["load", "frontend", "early", "assign", "history"]
    elif scenario in ("disabled", "disabled-valid"):
        assert len(requests) == 9 and requests[0] == capture["query_string"]
        assert histories == [False] * 9 and finishes == [0] * 9
        assert [query.split("phase=")[1].split("&")[0] for query in requests] == [
            "load", "forge", "malformed" if scenario == "disabled" else "invalid-url", "code", "hidden", "remount", "enabled", "interactive", "redisable"]
    elif scenario == "binding":
        assert capture["query_string"] == requests[0]
        assert requests == ["case=binding&phase=load", "case=binding&phase=active&bound=y&text=hello",
                            "case=binding&phase=hidden&bound=y&text=hello&BOUND=case-sensitive",
                            "case=binding&phase=released&BOUND=case-sensitive"]
        assert finishes == [0, 0, 0, 0]
    elif scenario == "seed":
        assert len(requests) == 8 and requests[0] == capture["query_string"]
        assert [query.split("phase=")[1].split("&")[0] for query in requests] == ["initial", "frontend", "again", "invalid", "empty", "assign", "history", "history-missing"]
        assert histories == [False] * 6 + [True, True] and finishes == [0] * 8
    elif scenario == "seed-code":
        assert len(requests) == 2 and requests[0] == capture["query_string"]
        assert histories == [False, True] and finishes == [0, 0]
    else:
        assert requests == [capture["query_string"]] and finishes == [0]
    return snapshots, urls


def test_query_param_values_oracle_is_complete_and_backed_by_wire():
    snapshots, urls = read_query_param_capture("values")
    assert [state["stage"] for state in snapshots] == ["load", "replace", "append", "empty-list", "remove-empty", "remove-tag", "clear", "restore"]
    assert snapshots[0]["value"] == "second" and snapshots[0]["all"] == ["first", "second"]
    assert snapshots[3]["empty"] == "" and snapshots[3]["pairs"][-1] == ["empty", ""]
    assert snapshots[4]["empty"] is None and snapshots[5]["value"] is None
    assert snapshots[6]["pairs"] == [] and snapshots[7]["value"] == "last"
    assert len(urls) == 7 and urls[2] == urls[3] == urls[1]
    assert urls[0].startswith("z=last&tag=replacement&tag=tail&a=first&blank=")
    assert urls[1].endswith("&new=%E4%B8%AD%E6%96%87+%2B+text")
    assert urls[-2:] == ["", "tag=again&tag=last"]

def test_query_param_reserved_oracle_is_complete_and_backed_by_wire():
    snapshots, urls = read_query_param_capture("reserved")
    assert len(snapshots) == 9 and len(urls) == 4
    reports = [item for item in snapshots if "stage" in item]
    assert [item["stage"] for item in reports] == ["reserved-load", "after-rejections", "empty-key-set", "empty-key-remove", "reserved-clear", "reserved-restore"]
    assert snapshots[1:4] == [
        {"operation": "set:embed", "rejected": True},
        {"operation": "set:EmBeD_OpTiOnS", "rejected": True},
        {"operation": "remove:embed", "rejected": True},
    ]
    assert reports[1] | {"stage": "reserved-load"} == reports[0]
    assert all(item["embed"] is None and item["options"] == [] for item in reports)
    assert reports[0]["ordinary"] == "ordinary" and reports[0]["empty_key"] == "empty-key-value"
    assert reports[2]["empty_key"] == "updated empty key" and reports[3]["empty_key"] is None
    assert reports[4]["pairs"] == [] and reports[5]["pairs"] == [["restored", "ok"]]
    assert urls[0].endswith("&=updated+empty+key")
    assert urls[-2:] == ["embed=true&EMBED_OPTIONS=light_theme", "embed=true&EMBED_OPTIONS=light_theme&restored=ok"]


def test_query_param_binding_lifecycle_oracle():
    reports, urls = read_query_param_capture("binding")
    assert len(reports) == 18 and len(urls) == 5
    assert reports[0] == {"phase": "load", "selected": "x", "text": ""}
    assert reports[6] == {"phase": "active", "selected": "y", "text": "hello"}
    assert reports[4] == {"operation": "clear", "rejected": False}, "absent bound params do not block clear"
    assert all(report["rejected"] for report in reports[7:11])
    assert all(report["rejected"] for report in reports[12:16]), "hidden widgets stay bound until run-end cleanup"
    assert urls[2] == "case=binding&phase=hidden&BOUND=case-sensitive"
    assert urls[-2:] == ["case=binding&phase=released&BOUND=case-sensitive&bound=manual", ""]
    assert reports[-1] == {"phase": "released", "pairs": []}


def test_query_param_url_seed_priority_and_correction_oracle():
    reports, urls = read_query_param_capture("seed")
    assert len(reports) == 8 and len(urls) == 9
    values = {report["phase"]: (report["bound"], report["text"], report["optional"], report["creation"]) for report in reports}
    assert values == {
        "initial": ("y", "hello", "y", "new"),
        "frontend": ("x", "edited", "x", "typed"),
        "again": ("y", "fresh", "y", "another"),
        "invalid": ("y", "fresh", "y", "another"),
        "empty": ("y", "", "y", "another"),
        "assign": ("x", "code", "y", "url"),
        "history": ("y", "url-history", "y", "history"),
        "history-missing": ("x", "base", None, "x"),
    }
    assert "bound" not in dict(reports[1]["pairs"]), "frontend default collapses the stored query without a URL broadcast"
    assert reports[3]["pairs"] == [["case", "seed"], ["phase", "invalid"]]
    assert reports[4]["pairs"] == [["case", "seed"], ["phase", "empty"], ["text", ""]]
    assert urls[3] == "case=seed&phase=invalid"
    assert urls[-1] == "case=seed&phase=assign&text=code&optional=y&creation=url"


def test_query_param_url_overrides_invalid_code_types_oracle():
    reports, urls = read_query_param_capture("seed-code")
    assert urls == [] and len(reports) == 2
    assert (reports[0]["phase"], reports[0]["bound"], reports[0]["text"]) == ("bad-initial", "y", "hello")
    assert (reports[1]["phase"], reports[1]["bound"], reports[1]["text"]) == ("bad-history", "y", "code-history")


@pytest.mark.parametrize("scenario", ["disabled", "disabled-valid"])
def test_disabled_input_callbacks_and_error_recovery_oracle(scenario):
    reports, urls = read_query_param_capture(scenario)
    assert len(reports) == (8 if scenario == "disabled" else 9)
    assert len(urls) == (3 if scenario == "disabled" else 5)
    values = {report["phase"]: tuple(report[key] for key in ("plain", "bound", "text", "check", "live")) for report in reports}
    assert values["load"] == ("safe", "y", "url", False, "ready")
    assert values["forge"] == ("safe", "y", "url", False, "one")
    assert values["code"] == ("code", "x", "code", True, "three")
    assert values["hidden"] == (None, "y", "url", True, "four")
    assert values["remount"] == ("safe", "y", "url", True, "five")
    assert values["enabled"] == ("edited", "x", "edited", False, "six")
    assert values["interactive"] == ("edited2", "y", "edited2", True, "seven")
    assert values["redisable"] == ("edited2", "y", "edited2", True, "eight")
    callbacks = {report["phase"]: report["callbacks"] for report in reports}
    assert callbacks["load"] == [] and callbacks["forge"] == ["live"]
    assert callbacks["code"] == ["live"] * 3, "malformed run already executed the live callback"
    assert callbacks["enabled"] == ["live"] * 6
    assert callbacks["interactive"] == ["live"] * 6 + ["plain", "bound", "text", "check", "live"]
    assert callbacks["redisable"] == ["live"] * 6 + ["plain", "bound", "text", "check", "live"] * 2
    if scenario == "disabled-valid":
        assert values["invalid-url"] == ("safe", "y", "url", False, "two")
        assert callbacks["invalid-url"] == ["live"] * 2


def test_bound_server_reruns_keep_state_callbacks_and_url_oracle():
    reports, urls = read_query_param_capture("rerun")
    assert len(reports) == 15 and len(urls) == 12
    assert [(report["phase"], report["iteration"], report["stage"]) for report in reports] == [
        (phase, 1, stage) for phase in ("load", "frontend", "early", "assign", "history") for stage in ("before", "values", "complete")]
    complete = {report["phase"]: report for report in reports if report["stage"] == "complete"}
    assert [(report["bound"], report["text"]) for report in complete.values()] == [
        ("y", "url"), ("x", "edited"), ("y", "fresh"), ("x", "code"), ("x", "base")]
    assert complete["load"]["callbacks"] == []
    assert all(report["callbacks"] == ["bound", "text"] for report in reports[3:]), "internal reruns must not replay callbacks"
    assert reports[6]["bound"] == "x" and reports[6]["text"] == "edited", "early rerun keeps unseen widget state"
    assert reports[3]["pairs"] == [["case", "rerun"], ["phase", "frontend"], ["bound", "y"], ["text", "ignored"], ["marker", "frontend-1"]]
    assert complete["frontend"]["pairs"] == [["case", "rerun"], ["phase", "frontend"], ["text", "ignored"], ["marker", "frontend-1"]]
    assert urls[7:10] == ["case=rerun&phase=assign&text=url&marker=assign-0",
                          "case=rerun&phase=assign&text=code&marker=assign-0",
                          "case=rerun&phase=assign&text=code&marker=assign-1"]


def selected_rerun_events(scenario):
    capture = json.loads((HERE / f"reference-browser/queryparams/{scenario}/trace.json").read_text())
    events = []
    for frame in capture["frames"]:
        message = frame["message"]
        element = message.get("delta", {}).get("new_element", {})
        events.extend(element.keys() & {"toast", "markdown", "balloons", "json", "selectbox", "text_input", "button"})
        for kind in ("page_config_changed", "page_info_changed", "navigation", "script_finished"):
            if kind in message:
                events.append(kind + (":" + message[kind] if kind == "script_finished" else ""))
    return events


def test_native_navigation_rerun_discards_queued_navigation_and_deltas():
    reports, urls = read_query_param_capture("navigation-rerun")
    assert reports == [] and urls == [""]
    assert selected_rerun_events("navigation-rerun") == [
        "navigation", "markdown", "button", "script_finished:FINISHED_SUCCESSFULLY",
        "page_info_changed", "script_finished:FINISHED_EARLY_FOR_RERUN",
        "navigation", "markdown", "script_finished:FINISHED_SUCCESSFULLY"]


def test_warm_rerun_keeps_toast_url_and_lifecycle_but_drops_other_queued_messages():
    reports, urls = read_query_param_capture("rerun-queue")
    assert reports == [{"phase": "warm", "iteration": 0}, {"phase": "queue", "iteration": 1}]
    assert urls == ["case=queue&phase=queue&marker=retained"]
    assert selected_rerun_events("rerun-queue") == [
        "page_config_changed", "toast", "markdown", "balloons", "json", "script_finished:FINISHED_SUCCESSFULLY",
        "toast", "page_info_changed", "script_finished:FINISHED_EARLY_FOR_RERUN", "json", "script_finished:FINISHED_SUCCESSFULLY"]


def test_cold_rerun_capture_retains_its_already_sent_prefix():
    reports, urls = read_query_param_capture("rerun-messages")
    assert len(reports) == 4 and len(urls) == 2
    assert [(report["iteration"], report["stage"]) for report in reports] == [(0, "before"), (1, "before"), (1, "values"), (1, "complete")]
    assert selected_rerun_events("rerun-messages")[:7] == ["page_config_changed", "toast", "markdown", "balloons", "page_info_changed", "json", "selectbox"]


URL = "http://127.0.0.1:8616"


def build_frame(entry):
    entry = copy.deepcopy(entry)
    kind = entry["kind"]
    if kind == "page_info":
        return {"direction": "server->client", "timestamp": 0.3, "summary": {"type": "page_info_changed", "page_info": {"query_string": entry["query_string"]}}}
    if kind == "rerun":
        states = []
        for state in entry["widget_states"]:
            real = state["id"]
            if real.endswith("-None"):
                real = "$$ID-79b26fd5542f64b238f6f878327b6b00-None"
            elif real.endswith("-bound"):
                real = "$$ID-85e592e7f7a3c4baeb8416bed8b755e6-bound"
            states.append({**state, "id": real})
        return {"direction": "client->server", "timestamp": 0.0, "summary": {"type": "rerun_script", "rerun_script": {"query_string": entry["query_string"], "widget_states": states}}}
    if kind == "selectbox":
        select = copy.deepcopy(entry["selectbox"])
        digest = "79b26fd5542f64b238f6f878327b6b00" if select["id"] == "$$ID-None" else "85e592e7f7a3c4baeb8416bed8b755e6"
        select["id"] = select["id"].replace("$$ID-", f"$$ID-{digest}-")
        return {"direction": "server->client", "timestamp": 0.4, "summary": {"type": "delta", "delta": {"type": "new_element", "element": "selectbox", "path": [0, 0], "element_full": {"selectbox": select}}}}
    if kind in ("new_session", "session_status_changed", "script_finished"):
        if kind == "script_finished":
            return {"direction": "server->client", "timestamp": 9.0, "summary": {"type": "script_finished", "script_finished": {"status": 0}}}
        return {"direction": "server->client", "timestamp": 0.1, "summary": {"type": kind, kind: {}}}
    return {"direction": "server->client", "timestamp": 0.5, "summary": {"type": "delta", "delta": {"type": "new_element", "element": kind, "path": entry.get("path"), "body": entry.get("body")}}}


def stage_frames(name, *, leading_main_blocks=0):
    frames = []
    for _ in range(leading_main_blocks):
        frames.append({"direction": "server->client", "timestamp": 0.2,
                       "summary": {"type": "delta", "delta": {"type": "add_block", "block_id": "main_container", "block_type": "vertical",
                                                              "block": {"vertical": {}, "id": "main_container"}, "path": [0]}}})
    frames.extend(build_frame(entry) for entry in QUERYPARAMS_TIMELINE[name])
    return frames


def dom(name):
    return json.loads(json.dumps(copy.deepcopy(QUERYPARAMS_DOMS[name]), ensure_ascii=False))


def observation(tmp_path, **faults):
    leading = faults.pop("leading_main_blocks", 0)
    stages = []
    for name in QUERYPARAMS_STAGES:
        stages.append({"name": name, "new_frames": stage_frames(name, leading_main_blocks=leading), "http": [], "dom": dom(name)})
    observation = {
        "journey": "queryparams-page",
        "contract": "journey-queryparams-v1",
        "scope": "PYTHON SIDE ONLY",
        "url": f"{URL}/",
        "source": {"file": QUERYPARAMS_SOURCE_FILES["python"]},
        "capture_sources": {},
        "stages": stages,
        "ipc_dir": str(tmp_path),
    }
    for stage in stages:
        png = f"{stage['name']}.png"
        (tmp_path / png).write_bytes(PNG_BYTES)
        stage["screenshot"] = {"file": png, "sha256": hashlib.sha256(PNG_BYTES).hexdigest()}
    mutation = faults.pop("mutation", None)
    target = stages[0]

    def find(kind):
        return next(frame for frame in target["new_frames"] if (frame["summary"].get(kind) if kind != "page_info_changed" else None) or frame["summary"].get("type") == kind)

    def page_info_frame(stage):
        return next(frame for frame in stage["new_frames"] if frame["summary"].get("type") == "page_info_changed")

    if mutation == "query_string_changed":
        page_info_frame(stages[0])["summary"]["page_info"]["query_string"] = "mode=other"
    elif mutation == "page_info_missing":
        target["new_frames"] = [frame for frame in target["new_frames"] if frame["summary"].get("type") != "page_info_changed"]
    elif mutation == "page_info_duplicated":
        target["new_frames"].insert(4, copy.deepcopy(page_info_frame(target)))
    elif mutation == "accept_new_options_off":
        for stage in stages:
            select = next(frame for frame in stage["new_frames"] if (frame["summary"].get("delta") or {}).get("element") == "selectbox")
            box = select["summary"]["delta"]["element_full"]["selectbox"]
            if box.get("acceptNewOptions") is True:
                box["acceptNewOptions"] = False
                break
    elif mutation == "filter_mode_changed":
        for stage in stages:
            select = next(frame for frame in stage["new_frames"] if (frame["summary"].get("delta") or {}).get("element") == "selectbox")
            box = select["summary"]["delta"]["element_full"]["selectbox"]
            if box.get("filterMode") == "FILTER_MODE_CONTAINS":
                box["filterMode"] = "FILTER_MODE_FUZZY"
                break
    elif mutation == "query_param_key_missing":
        for stage in stages:
            select = [frame for frame in stage["new_frames"] if (frame["summary"].get("delta") or {}).get("element") == "selectbox"]
            box = select[1]["summary"]["delta"]["element_full"]["selectbox"]
            if "queryParamKey" in box:
                del box["queryParamKey"]
                break
    elif mutation == "bound_label_changed":
        for stage in stages:
            select = [frame for frame in stage["new_frames"] if (frame["summary"].get("delta") or {}).get("element") == "selectbox"]
            box = select[1]["summary"]["delta"]["element_full"]["selectbox"]
            if box.get("queryParamKey") == "bound":
                box["label"] = "Other"
                break
    elif mutation == "typed_value_lost":
        rerun = next(frame for frame in stages[1]["new_frames"] if frame["summary"].get("type") == "rerun_script")
        rerun["summary"]["rerun_script"]["widget_states"] = []
    elif mutation == "browser_query_string_changed":
        rerun = next(frame for frame in stages[2]["new_frames"] if frame["summary"].get("type") == "rerun_script")
        rerun["summary"]["rerun_script"]["query_string"] = "mode=demo"
    elif mutation == "markdown_changed":
        for frame in stages[2]["new_frames"]:
            delta = frame["summary"].get("delta") or {}
            if delta.get("element") == "markdown" and delta.get("body") == "bound=y":
                delta["body"] = "bound=x"
    elif mutation == "dom_url_missing_sync":
        stages[2]["dom"]["url"] = "?mode=demo"
    elif mutation == "dom_markdown_missing":
        stages[1]["dom"]["markdowns"] = ["pick=a", "bound=x"]
    elif mutation == "exception_element":
        target["new_frames"].insert(6, {"direction": "server->client", "timestamp": 2.9,
                                        "summary": {"type": "delta", "delta": {"type": "new_element", "element": "exception", "path": [0, 4]}}})
    elif mutation == "wrong_finish":
        for frame in stages[0]["new_frames"]:
            if frame["summary"]["type"] == "script_finished":
                frame["summary"]["script_finished"]["status"] = 2
    elif mutation == "missing_png":
        (tmp_path / f"{target['name']}.png").unlink()
    elif mutation == "png_sha":
        target["screenshot"]["sha256"] = "0" * 64
    elif mutation == "wrong_contract":
        observation["contract"] = "journey-queryparams-v0"
    elif mutation == "missing_stage":
        observation["stages"] = []
    assert not faults, faults
    return observation


def result(tmp_path, **faults):
    return queryparams_result(observation=observation(tmp_path, **faults))


def test_complete_synthetic_model_passes_every_check(tmp_path):
    outcome = result(tmp_path)
    assert outcome["ok"], outcome["failures"]
    assert outcome["counts"] == {"expected": 10, "executed": 10, "asserted": 10}
    assert tuple(check["check"] for check in outcome["checks"]) == QUERYPARAMS_REQUIRED


def test_the_rust_leading_main_block_is_the_one_allowed_divergence(tmp_path):
    outcome = result(tmp_path, leading_main_blocks=1)
    assert outcome["ok"], outcome["failures"]


@pytest.mark.parametrize("leading", [2, 3])
def test_more_than_one_leading_main_block_fails(tmp_path, leading):
    outcome = result(tmp_path, leading_main_blocks=leading)
    assert not outcome["ok"], (leading, outcome["counts"])


@pytest.mark.parametrize("mutation", [
    "query_string_changed", "page_info_missing", "page_info_duplicated",
    "accept_new_options_off", "filter_mode_changed", "query_param_key_missing",
    "bound_label_changed", "typed_value_lost", "browser_query_string_changed",
    "markdown_changed", "dom_url_missing_sync", "dom_markdown_missing",
    "exception_element", "wrong_finish", "missing_png", "png_sha",
    "wrong_contract", "missing_stage",
])
def test_known_mutations_fail(tmp_path, mutation):
    outcome = result(tmp_path, mutation=mutation)
    assert not outcome["ok"], (mutation, outcome["counts"])


def test_degenerate_observations_fail_closed():
    for observation in (None, {}, [], {"journey": "queryparams-page"}):
        outcome = queryparams_result(observation=observation)
        assert not outcome["ok"] and outcome["counts"]["expected"] == len(QUERYPARAMS_REQUIRED)


def test_the_constants_pin_the_measured_semantics():
    assert QUERYPARAMS_STAGES == ["01-load", "02-new-option", "03-bound-pick"]
    assert QUERYPARAMS_PAGE_INFOS["01-load"]["query_string"] == "mode=demo"
    assert QUERYPARAMS_PAGE_INFOS["03-bound-pick"]["query_string"] == "bound=y&mode=demo"
    creation = QUERYPARAMS_SELECTBOXES_FIRST()
    assert creation["acceptNewOptions"] is True
    assert creation["filterMode"] == "FILTER_MODE_CONTAINS"
    assert "queryParamKey" not in creation
    bound = QUERYPARAMS_SELECTBOXES_SECOND()
    assert bound["queryParamKey"] == "bound"
    assert bound["acceptNewOptions"] is False
    # The measured wire omits the default filterMode (proto3 FUZZY = 0).
    assert "filterMode" not in bound
    assert QUERYPARAMS_RERUNS["01-load"]["query_string"] is None
    assert QUERYPARAMS_RERUNS["03-bound-pick"]["query_string"] == "bound=y&mode=demo"
    assert QUERYPARAMS_DOMS["01-load"]["url"] == "?mode=demo"
    assert QUERYPARAMS_DOMS["03-bound-pick"]["url"] == "?bound=y&mode=demo"
    assert QUERYPARAMS_DOMS["03-bound-pick"]["markdowns"] == ["pick=c", "bound=y"]
    assert all(not dom["exceptions"] for dom in QUERYPARAMS_DOMS.values())


def QUERYPARAMS_SELECTBOXES_FIRST():
    from queryparams_contract import QUERYPARAMS_SELECTBOXES
    return QUERYPARAMS_SELECTBOXES["01-load"][0]


def QUERYPARAMS_SELECTBOXES_SECOND():
    from queryparams_contract import QUERYPARAMS_SELECTBOXES
    return QUERYPARAMS_SELECTBOXES["01-load"][1]


def test_source_fingerprints_do_not_gate_functional_evidence(tmp_path):
    for source in ({"file": "historical-app.py", "sha256": "changed"}, {"file": "historical-app.py"}, None):
        observed = observation(tmp_path)
        observed["source"] = source
        outcome = queryparams_result(observation=observed)
        assert outcome["ok"], outcome["failures"]
