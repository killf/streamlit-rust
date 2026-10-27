"""Unit tests of the strict execution-semantics contract (journey-execution-v1)."""
from __future__ import annotations

import hashlib
import json
import pathlib
import sys

import pytest

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "browser"))

from execution_contract import (  # noqa: E402
    EXECUTION_DOM,
    EXECUTION_REQUIRED,
    EXECUTION_SOURCE_FILES,
    execution_checks,
    execution_result,
    runs_of,
)

PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"not-a-real-image-but-magic-and-hash-are-checked"


def frame(kind, direction="server->client", **extra):
    summary = {"type": kind, **extra}
    return {"direction": direction, "timestamp": 0.0, "summary": summary}


def run_frames(session, run_id, markdowns, finish, backmsg=None):
    frames = []
    if backmsg is not None:
        frames.append(frame("rerun_script", "client->server"))
    frames.append(frame("new_session", new_session={"script_run_id": run_id, "session_id": session}))
    frames.append(frame("session_status_changed", session_status_changed={"script_is_running": True, "run_on_save": False}))
    frames.append(frame("delta", delta={"element": "selectbox"}))
    for body in markdowns:
        frames.append(frame("delta", delta={"element": "markdown", "body": body}))
    frames.append(frame("script_finished", script_finished={"status": finish}))
    frames.append(frame("session_status_changed", session_status_changed={"script_is_running": False, "run_on_save": False}))
    return frames


def observation(tmp_path, **faults):
    session = faults.get("session", "session-a")
    doms = {stage: list(EXECUTION_DOM[stage]) for stage in EXECUTION_DOM}
    faults.pop("session", None)
    stages = []
    stage_runs = {
        "plain": [run_frames(session, "run-1", doms["plain"], 0, backmsg="initial")],
        "rerun": [
            run_frames(session, "run-2", ["mode=rerun runs=2 reruns=0"], 2, backmsg="select"),
            run_frames(session, "run-3", doms["rerun"], 0),
        ],
        "stop": [run_frames(session, "run-4", doms["stop"], 0, backmsg="select")],
    }
    for name, runs in stage_runs.items():
        stages.append({"name": name, "new_frames": [frame for run in runs for frame in run], "dom": {"mode": name, "markdowns": doms[name]}})
    observation = {
        "journey": "execution-sequence",
        "contract": "journey-execution-v1",
        "scope": "PYTHON SIDE ONLY",
        "url": "http://127.0.0.1:8605/",
        "source": {"file": EXECUTION_SOURCE_FILES["python"]},
        "capture_sources": {},
        "stages": stages,
        "ipc_dir": str(tmp_path),
    }
    for index, stage in enumerate(stages):
        name = f"{index + 1:02d}-{stage['name']}.png"
        (tmp_path / name).write_bytes(PNG_BYTES)
        stage["screenshot"] = {"file": name, "sha256": hashlib.sha256(PNG_BYTES).hexdigest()}
    mutation = faults.pop("mutation", None)
    if mutation == "abort_finish":
        stages[1]["new_frames"] = [f for f in stages[1]["new_frames"] if f["summary"]["type"] != "script_finished"][:0] or stages[1]["new_frames"]
        # replace the aborted run's finish 2 with 0
        for f in stages[1]["new_frames"]:
            if f["summary"]["type"] == "script_finished" and f["summary"]["script_finished"]["status"] == 2:
                f["summary"]["script_finished"]["status"] = 0
    elif mutation == "extra_backmsg":
        insert_at = next(i for i, f in enumerate(stages[1]["new_frames"]) if f["summary"]["type"] == "script_finished" and f["summary"]["script_finished"]["status"] == 2) + 2
        stages[1]["new_frames"].insert(insert_at, frame("rerun_script", "client->server"))
    elif mutation == "epilogue_in_aborted":
        for f in stages[1]["new_frames"]:
            if f["summary"].get("delta", {}).get("body") == "mode=rerun runs=2 reruns=0":
                stages[1]["new_frames"].insert(stages[1]["new_frames"].index(f) + 1, frame("delta", delta={"element": "markdown", "body": "epilogue"}))
                break
    elif mutation == "stale_session":
        for f in stages[2]["new_frames"]:
            if f["summary"]["type"] == "new_session":
                f["summary"]["new_session"]["session_id"] = "session-b"
    elif mutation == "reused_run_id":
        for f in stages[2]["new_frames"]:
            if f["summary"]["type"] == "new_session":
                f["summary"]["new_session"]["script_run_id"] = "run-1"
    elif mutation == "stop_keeps_epilogue":
        stages[2]["new_frames"].insert(-2, frame("delta", delta={"element": "markdown", "body": "epilogue"}))
        stages[2]["dom"]["markdowns"] = [*EXECUTION_DOM["stop"], "epilogue"]
    elif mutation == "missing_png":
        (tmp_path / "03-stop.png").unlink()
    elif mutation == "png_sha":
        stages[2]["screenshot"]["sha256"] = "0" * 64
    elif mutation == "wrong_dom":
        stages[0]["dom"]["markdowns"] = ["mode=plain runs=2 reruns=0", "epilogue"]
    elif mutation == "wrong_contract":
        observation["contract"] = "journey-execution-v0"
    elif mutation == "missing_stage":
        observation["stages"] = observation["stages"][:2]
    assert not faults, faults
    return observation


def result(tmp_path, **faults):
    return execution_result(observation=observation(tmp_path, **faults))


def test_complete_synthetic_model_passes_every_check(tmp_path):
    outcome = result(tmp_path)
    assert outcome["ok"], outcome["failures"]
    assert outcome["counts"] == {"expected": 7, "executed": 7, "asserted": 7}
    assert tuple(check["check"] for check in outcome["checks"]) == EXECUTION_REQUIRED


@pytest.mark.parametrize("mutation", [
    "abort_finish", "extra_backmsg", "epilogue_in_aborted", "stale_session", "reused_run_id",
    "stop_keeps_epilogue", "missing_png", "png_sha", "wrong_dom",
    "wrong_contract", "missing_stage",
])
def test_known_mutations_fail(tmp_path, mutation):
    outcome = result(tmp_path, mutation=mutation)
    assert not outcome["ok"], (mutation, outcome["counts"])


def test_degenerate_observations_fail_closed():
    for observation in (None, {}, [], {"journey": "execution-sequence"}):
        outcome = execution_result(observation=observation)
        assert not outcome["ok"] and outcome["counts"]["expected"] == len(EXECUTION_REQUIRED)


def test_runs_of_attributes_backmsgs_to_the_run_they_precede():
    frames = [*run_frames("s", "r1", [], 0, backmsg="yes"), *run_frames("s", "r2", [], 0)]
    runs = runs_of(frames)
    assert [run["backmsgs"] for run in runs] == [1, 0]
    assert [run["run_id"] for run in runs] == ["r1", "r2"]


def test_source_fingerprints_do_not_gate_functional_evidence(tmp_path):
    for source in ({"file": "historical-app.py", "sha256": "changed"}, {"file": "historical-app.py"}, None):
        observed = observation(tmp_path)
        observed["source"] = source
        outcome = execution_result(observation=observed)
        assert outcome["ok"], outcome["failures"]
