"""Guard tests for the components.v2 contract constants (journey-componentv2-v1)."""
import copy
import importlib.util
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests" / "browser"))
sys.path.insert(0, str(ROOT / "tests" / "reference"))

spec = importlib.util.spec_from_file_location("componentv2_contract", ROOT / "tests/browser/componentv2_contract.py")
contract = importlib.util.module_from_spec(spec)
spec.loader.exec_module(contract)


def frozen():
    observation = {
        "journey": contract.COMPONENTV2_CASE,
        "contract": contract.COMPONENTV2_CONTRACT,
        "scope": "PYTHON SIDE ONLY",
        "url": "http://127.0.0.1:8630/",
        "source": {"file": contract.COMPONENTV2_SOURCE_PINS["python"][0], "sha256": contract.COMPONENTV2_SOURCE_PINS["python"][1]},
        "ipc_dir": str(ROOT / "target/checks/m5-componentv2-pyref"),
        "stages": [],
    }
    raw = json.loads((ROOT / "target/checks/m5-componentv2-pyref/trace-colconfig.json").read_text(encoding="utf-8"))
    for stage in raw["observation"]["stages"]:
        record = copy.deepcopy(stage)
        record["new_frames"] = copy.deepcopy(stage["new_frames"])
        observation["stages"].append(record)
    return observation


def test_frozen_python_observation_passes():
    result = contract.componentv2_result(observation=frozen())
    assert result["failures"] == [] and result["ok"], json.dumps(result["checks"], indent=1)


def test_one_divergence_fails_closed():
    observation = frozen()
    frames = [frame for frame in observation["stages"][0]["new_frames"]
              if (frame.get("summary") or {}).get("type") == "delta"
              and frame["summary"]["delta"].get("element") == "bidi_component"]
    frames[0]["summary"]["delta"]["element_full"]["bidiComponent"]["componentName"] = "tampered"
    result = contract.componentv2_result(observation=observation)
    assert not result["ok"] and any(check["check"] == "timeline" for check in result["failures"])


def test_stage_png_sha_is_guarded():
    observation = frozen()
    observation["stages"][0]["screenshot"]["sha256"] = "0" * 64
    result = contract.componentv2_result(observation=observation)
    assert any(check["check"] == "png_sources" for check in result["failures"])


def test_dom_projection_is_guarded():
    observation = frozen()
    observation["stages"][0]["dom"]["markdowns"] = []
    result = contract.componentv2_result(observation=observation)
    assert any(check["check"] == "dom_projection" for check in result["failures"])


def test_source_pin_is_guarded():
    observation = frozen()
    observation["source"]["sha256"] = "0" * 64
    result = contract.componentv2_result(observation=observation)
    assert any(check["check"] == "source_pin" for check in result["failures"])


def test_degenerate_observation_fails_closed():
    for broken in ({}, {"journey": "other"}, {"stages": []}):
        result = contract.componentv2_result(observation=broken)
        assert not result["ok"]
        assert result["counts"]["asserted"] < result["counts"]["expected"]
