"""The strict execution-semantics contract: journey-execution-v1.

This is the criterion of journey step J04-S4. It judges the observation the
committed collector (execution_capture.py) writes, against the Python 1.66.1
wire measured on 2026-10-25 and recorded in .codex/compatibility.md
(Execution semantics). The collector states no verdict; this module owns it:

* every run opens with new_session (fresh script_run_id, same session_id),
  then session_status_changed(running), streamed deltas, script_finished and
  session_status_changed(idle);
* a run that calls st.rerun() finishes FINISHED_EARLY_FOR_RERUN (status 2)
  and the server starts the next run with NO further client BackMsg;
* st.rerun()/st.stop() suppress every later element of their run, so the
  epilogue after either call never emits and never appears in the DOM;
* a stopped run still finishes FINISHED_SUCCESSFULLY (status 0).
"""

from __future__ import annotations

import hashlib
import pathlib

EXECUTION_CASE = "execution-sequence"
EXECUTION_CONTRACT = "journey-execution-v1"
EXECUTION_STAGES = ("plain", "rerun", "stop")
FINISHED_SUCCESSFULLY = 0
FINISHED_EARLY_FOR_RERUN = 2

# The exact rendered markdowns of each stage end state, identical on both
# runtimes because the driven applications are mirrors.
EXECUTION_DOM = {
    "plain": ["mode=plain runs=1 reruns=0", "epilogue"],
    "rerun": ["mode=rerun runs=3 reruns=1", "epilogue"],
    "stop": ["mode=stop runs=4 reruns=1", "before-stop"],
}

# Application paths label the captured roles; source content is not a gate.
EXECUTION_SOURCE_FILES = {
    "python": "tests/reference/execution_app.py",
    "native": "streamlit/examples/execution.rs",
}

EXECUTION_REQUIRED = (
    "contract", "stage_set", "plain_lifecycle",
    "rerun_aborts_early", "same_session_fresh_runs", "stop_suppresses", "png_sources",
)


def _record(checks, name, ok, expected, actual):
    checks.append({"step": EXECUTION_CASE, "check": name, "expected": expected, "actual": actual, "ok": bool(ok)})


def _need(condition, message):
    if not condition:
        raise ValueError(message)


def runs_of(frames):
    """Group decoded frames into runs at new_session boundaries.

    A client rerun_script counts toward the run it precedes, so a run started
    by the server (an in-run st.rerun) is the only kind with no BackMsg.
    """
    runs = []
    pending_backmsgs = 0
    for frame in frames:
        summary = frame.get("summary") or {}
        kind = summary.get("type")
        if kind == "rerun_script":
            pending_backmsgs += 1
        elif kind == "new_session":
            session = summary.get("new_session") or {}
            runs.append({
                "run_id": session.get("script_run_id"),
                "session_id": session.get("session_id"),
                "backmsgs": pending_backmsgs,
                "markdowns": [],
                "finish": [],
            })
            pending_backmsgs = 0
        elif runs:
            if kind == "delta":
                delta = summary.get("delta") or {}
                if delta.get("element") == "markdown" and delta.get("body") is not None:
                    runs[-1]["markdowns"].append(delta["body"])
            elif kind == "script_finished":
                runs[-1]["finish"].append((summary.get("script_finished") or {}).get("status"))
    return runs


def _stage_runs(stage):
    frames = stage.get("new_frames") or []
    backmsgs = sum(1 for frame in frames if (frame.get("summary") or {}).get("type") == "rerun_script")
    return runs_of(frames), backmsgs


def execution_checks(*, observation=None):
    checks = []
    verified = set()

    def mark(name):
        verified.add(name)
        _record(checks, name, True, "the measured 1.66.1 execution wire", "contract verified")

    def fail(name, actual):
        _record(checks, name, False, "the measured 1.66.1 execution wire", str(actual))

    try:
        _need(isinstance(observation, dict), "observation must be a dict")
        _need(observation.get("journey") == EXECUTION_CASE and observation.get("contract") == EXECUTION_CONTRACT,
              "missing versioned execution contract identity")
        _need(bool(observation.get("scope")) and bool(observation.get("url")), "missing scope/url")
        mark("contract")

        stages = observation.get("stages")
        _need(isinstance(stages, list) and tuple(s.get("name") for s in stages) == EXECUTION_STAGES,
              "stages must be exactly plain, rerun, stop in order")
        for stage in stages:
            _need(isinstance(stage.get("dom"), dict) and isinstance(stage.get("screenshot"), dict)
                  and isinstance(stage.get("new_frames"), list), f"stage {stage.get('name')} lacks dom/screenshot/new_frames")
        mark("stage_set")

        plain_runs, plain_backmsgs = _stage_runs(stages[0])
        _need(plain_backmsgs == 1 and len(plain_runs) == 1, "plain stage must be one browser-triggered run")
        _need(plain_runs[0]["finish"] == [FINISHED_SUCCESSFULLY], "plain run must finish FINISHED_SUCCESSFULLY")
        _need(stages[0]["dom"].get("markdowns") == EXECUTION_DOM["plain"], "plain DOM end state differs")
        mark("plain_lifecycle")

        rerun_runs, rerun_backmsgs = _stage_runs(stages[1])
        _need(rerun_backmsgs == 1, "the rerun stage must carry exactly one client rerun_script")
        _need(len(rerun_runs) == 2, "an in-run st.rerun must start exactly one further run")
        _need(rerun_runs[0]["backmsgs"] == 1 and rerun_runs[1]["backmsgs"] == 0,
              "the second cascade run must start without any client BackMsg")
        _need(rerun_runs[0]["finish"] == [FINISHED_EARLY_FOR_RERUN],
              "the aborted run must finish FINISHED_EARLY_FOR_RERUN")
        _need(rerun_runs[1]["finish"] == [FINISHED_SUCCESSFULLY], "the rerun cascade must end FINISHED_SUCCESSFULLY")
        _need("epilogue" not in rerun_runs[0]["markdowns"], "the aborted run must not emit the epilogue")
        _need(rerun_runs[1]["markdowns"] == EXECUTION_DOM["rerun"], "the cascade end state differs")
        _need(stages[1]["dom"].get("markdowns") == EXECUTION_DOM["rerun"], "rerun DOM end state differs")
        mark("rerun_aborts_early")

        all_runs = [run for stage in stages for run in _stage_runs(stage)[0]]
        session_ids = {run["session_id"] for run in all_runs}
        run_ids = [run["run_id"] for run in all_runs]
        _need(all(run_ids) and len(set(run_ids)) == len(run_ids), "every run needs a fresh non-empty script_run_id")
        _need(len(session_ids) == 1, "all runs of the journey must share one session_id")
        mark("same_session_fresh_runs")

        stop_runs, stop_backmsgs = _stage_runs(stages[2])
        _need(stop_backmsgs == 1 and len(stop_runs) == 1, "the stop stage must be one browser-triggered run")
        _need(stop_runs[0]["finish"] == [FINISHED_SUCCESSFULLY], "a stopped run must still finish FINISHED_SUCCESSFULLY")
        _need(stop_runs[0]["markdowns"] == EXECUTION_DOM["stop"], "the stopped run keeps its prefix and drops the epilogue")
        _need("epilogue" not in stop_runs[0]["markdowns"], "the epilogue must never emit after st.stop()")
        _need(stages[2]["dom"].get("markdowns") == EXECUTION_DOM["stop"], "stop DOM end state differs")
        mark("stop_suppresses")

        root = pathlib.Path(observation.get("ipc_dir", ".")).resolve()
        for stage in stages:
            record = stage.get("screenshot") or {}
            _need(not pathlib.Path(record.get("file", "")).is_absolute(), "screenshot path must be relative")
            png = (root / record.get("file", "")).resolve()
            _need(png.is_relative_to(root) and png.is_file(), f"missing stage PNG {record.get('file')}")
            data = png.read_bytes()
            _need(data.startswith(b"\x89PNG\r\n\x1a\n") and hashlib.sha256(data).hexdigest() == record.get("sha256"),
                  f"stage PNG sha/magic mismatch for {record.get('file')}")
        mark("png_sources")
    except (ValueError, TypeError, KeyError, IndexError, OSError, AttributeError) as exc:
        for name in EXECUTION_REQUIRED:
            if name not in verified:
                fail(name, str(exc))
        return checks
    return checks


def execution_result(*, observation=None):
    """Aggregate the contract checks the way the shared journey judge does."""
    checks = execution_checks(observation=observation)
    failures = [check for check in checks if not check["ok"]]
    return {
        "checks": checks,
        "counts": {"expected": len(checks), "executed": len(checks), "asserted": len(checks) - len(failures)},
        "failures": failures,
        "ok": not failures and len(checks) == len(EXECUTION_REQUIRED),
    }
