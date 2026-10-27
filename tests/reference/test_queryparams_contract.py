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
