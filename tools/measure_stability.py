"""Observe the M5 stability fixtures; no Cargo/compiler memory in the sample."""
import ctypes
from ctypes import wintypes
import json
from pathlib import Path
import platform
import re
import subprocess
import sys
import time

FIXTURES = {
    "large_payloads": "server::tests::stability::large_payloads_render_correctly_and_survive_a_rerun",
    "long_session_churn": "server::tests::stability::a_long_session_survives_rerun_churn_with_exact_state",
    "slow_reader_isolation": "server::tests::stability::a_slow_reader_does_not_block_a_fast_session",
}

if len(sys.argv) != 3:
    raise SystemExit("Usage: python tools/measure_stability.py TEST_BINARY OUTPUT_JSON")
binary = Path(sys.argv[1]).resolve()
out = Path(sys.argv[2]).resolve()
out.parent.mkdir(parents=True, exist_ok=True)


class Counters(ctypes.Structure):
    _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD)] + [
        (name, ctypes.c_size_t) for name in [
            "PeakWorkingSetSize", "WorkingSetSize", "QuotaPeakPagedPoolUsage",
            "QuotaPeakPagedPoolUsage", "QuotaNonPagedPoolUsage", "PagefileUsage",
            "PeakPagefileUsage", "PrivateUsage"]]


query = ctypes.WinDLL("psapi", use_last_error=True).GetProcessMemoryInfo
query.argtypes = [wintypes.HANDLE, ctypes.POINTER(Counters), wintypes.DWORD]
query.restype = wintypes.BOOL

phases = {}
for phase, fixture in FIXTURES.items():
    trials = []
    for trial in range(3):
        log_path = out.parent / f"stability-{phase}-{trial + 1}.log"
        with log_path.open("wb") as log:
            began = time.perf_counter()
            process = subprocess.Popen([str(binary), fixture, "--exact", "--nocapture", "--test-threads=1"],
                                       stdout=log, stderr=subprocess.STDOUT)
            samples = []
            try:
                while process.poll() is None:
                    if time.perf_counter() - began > 120:
                        raise TimeoutError(f"owned measurement process exceeded 120 seconds: {process.pid}")
                    counters = Counters()
                    counters.cb = ctypes.sizeof(counters)
                    if query(wintypes.HANDLE(process._handle), ctypes.byref(counters), counters.cb):
                        samples.append({"private_bytes": counters.PrivateUsage, "working_set_bytes": counters.WorkingSetSize})
                    time.sleep(.005)
                code = process.wait()
            finally:
                if process.poll() is None:
                    process.kill()
                    process.wait()
        raw = log_path.read_text(encoding="utf-8", errors="replace")
        match = re.search(r"stability_measurement=(\{[^\n]+\})", raw)
        if code or not match:
            raise RuntimeError(f"trial failed: {code}, see {log_path}")
        trials.append({"exit_code": code, "wall_seconds": time.perf_counter() - began,
                       "samples": len(samples),
                       "max_observed_private_bytes": max(s["private_bytes"] for s in samples),
                       "max_observed_working_set_bytes": max(s["working_set_bytes"] for s in samples),
                       "measurement": json.loads(match.group(1)), "log": log_path.name})
    phases[phase] = trials

result = {
    "schema_version": 1,
    "measured_at_utc": time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime()),
    "environment": {"os": platform.platform(), "rustc": subprocess.run(["rustc", "--version"], capture_output=True, text=True).stdout.strip()},
    "binary": str(binary),
    "phases": phases,
    "scope": ("Whole isolated test process per fixture: one WS session rendering 100k/50k-row tables plus a "
              "200k-point chart (large_payloads); 300 reruns with 11 widget triggers on one session "
              "(long_session_churn); a parked reader mid-stream while a second session runs 20 full-speed "
              "reruns (slow_reader_isolation). Correctness assertions are in-test; memory/timing here are "
              "observations, not thresholds or SLOs."),
    "memory_scope": ("Whole test binary process sampled every 5ms; includes fixture setup and test harness. "
                     "Observed maxima can miss brief peaks; cross-machine comparison is not claimed."),
}
out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
print(json.dumps({phase: [trial["measurement"] for trial in trials] for phase, trials in phases.items()}, indent=2))
