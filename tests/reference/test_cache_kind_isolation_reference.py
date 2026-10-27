"""Reuse public bare-script cache observations; no live Python capture."""

import hashlib
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).parent / "reference-browser/cache-kind-isolation"


def read(name):
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


def test_cache_kind_reference_data_integrity_and_execution():
    manifest = read("manifest.json")
    assert manifest["reference_version"] == "1.66.1"
    for item in manifest["files"]:
        path = (ROOT / item["file"]).resolve()
        assert path.is_relative_to(ROOT.resolve())
        data = path.read_bytes()
        assert len(data) == item["bytes"] and hashlib.sha256(data).hexdigest() == item["sha256"]
    assert read("execution.json")["exit_code"] == 0
    observed = read("observations.json")
    assert observed["reference_version"] == "1.66.1" and observed["observed_independent_kinds"]
    assert observed["cleanup"] == {"owned_wrapper_caches_cleared": True, "errors": [], "AppTest_started": False, "server_started": False, "browser_started": False}
    versions = json.loads((ROOT / "stdout.log").read_text(encoding="utf-8").splitlines()[0].removeprefix("versions "))
    assert versions["streamlit"] == "1.66.1" and versions["python"] == observed["python_version"]
    assert "No runtime found, using MemoryCacheStorageManager" in (ROOT / "stderr.log").read_text(encoding="utf-8")


@pytest.mark.parametrize("index", range(4))
def test_public_cache_kind_call_orders_values_and_independent_clear(index):
    inputs = read("inputs.json")
    assert inputs["same_compute_function_object"] and not inputs["show_spinner"]
    plan, observed = inputs["plans"][index], read("observations.json")["plans"][index]
    assert (plan["name"], plan["arg"]) == (observed["name"], observed["arg"])
    assert [call["action"] for call in observed["calls"]] == plan["order"] + plan["after_initial"]
    lines = (ROOT / "stdout.log").read_text(encoding="utf-8").splitlines()
    logged = [json.loads(line.split(" ", 1)[1]) for line in lines if line.startswith(plan["name"] + " ")]
    assert logged == observed["calls"]
    live, counter = set(), 0
    expected = None if plan["arg"] == "null" else {"value": 42}
    for call in observed["calls"]:
        assert call["counter_before"] == counter
        action = call["action"]
        if action.startswith("clear-"):
            live.discard(action.removeprefix("clear-"))
            assert call["returned"] is None
        else:
            miss = action not in live
            counter += int(miss)
            live.add(action)
            assert call["function_executed"] == miss and call["returned"] == expected
        assert call["counter_after"] == counter
    assert observed["initial_counters"] == [1, 2, 2, 2]
    assert observed["after_clear_data_counters"] == [2, 3, 3]
    assert observed["after_clear_resource_counters"] == [3, 4, 4]
