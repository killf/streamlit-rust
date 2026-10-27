"""Guard tests for the components.v2 trigger contract constants (journey-componenttrigger-v1)."""
import copy
import importlib.util
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests" / "browser"))
sys.path.insert(0, str(ROOT / "tests" / "reference"))

spec = importlib.util.spec_from_file_location("componenttrigger_contract", ROOT / "tests/browser/componenttrigger_contract.py")
contract = importlib.util.module_from_spec(spec)
spec.loader.exec_module(contract)

PUBLISHED = ROOT / "tests/reference/reference-browser/componenttrigger"


def frozen():
    observation = {
        "journey": contract.COMPONENTTRIGGER_CASE,
        "contract": contract.COMPONENTTRIGGER_CONTRACT,
        "scope": "PYTHON SIDE ONLY",
        "url": "http://127.0.0.1:8633/",
        "source": {"file": contract.COMPONENTTRIGGER_SOURCE_FILES["python"]},
        "ipc_dir": str(PUBLISHED),
        "stages": [],
    }
    raw = json.loads((PUBLISHED / "trace-componenttrigger.json").read_text(encoding="utf-8"))
    for stage in raw["observation"]["stages"]:
        record = copy.deepcopy(stage)
        record["new_frames"] = copy.deepcopy(stage["new_frames"])
        observation["stages"].append(record)
    return observation


def test_frozen_python_observation_passes():
    result = contract.componenttrigger_result(observation=frozen())
    assert result["failures"] == [] and result["ok"], json.dumps(result["checks"], indent=1)


def test_one_divergence_fails_closed():
    observation = frozen()
    frames = [frame for frame in observation["stages"][1]["new_frames"]
              if (frame.get("summary") or {}).get("message") == "BackMsg"]
    frames[0]["summary"]["rerun_script"]["widget_states"][0]["value"] = "[]"
    result = contract.componenttrigger_result(observation=observation)
    assert not result["ok"] and any(check["check"] == "timeline" for check in result["failures"])


def test_stage_png_sha_is_guarded():
    observation = frozen()
    observation["stages"][0]["screenshot"]["sha256"] = "0" * 64
    result = contract.componenttrigger_result(observation=observation)
    assert any(check["check"] == "png_sources" for check in result["failures"])


def test_dom_projection_is_guarded():
    observation = frozen()
    observation["stages"][1]["dom"]["markdowns"] = []
    result = contract.componenttrigger_result(observation=observation)
    assert any(check["check"] == "dom_projection" for check in result["failures"])


def test_degenerate_observation_fails_closed():
    for broken in ({}, {"journey": "other"}, {"stages": []}):
        result = contract.componenttrigger_result(observation=broken)
        assert not result["ok"]
        assert result["counts"]["asserted"] < result["counts"]["expected"]


def test_source_fingerprints_do_not_gate_functional_evidence():
    for source in ({"file": "historical-app.py", "sha256": "changed"}, {"file": "historical-app.py"}, None):
        observation = frozen()
        observation["source"] = source
        result = contract.componenttrigger_result(observation=observation)
        assert result["ok"], result["failures"]
