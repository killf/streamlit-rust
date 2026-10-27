"""Observe one exact test binary; no Cargo/compiler memory in the sample."""
import ctypes
from ctypes import wintypes
import json
from pathlib import Path
import re
import subprocess
import sys
import time

if len(sys.argv) != 4:
    raise SystemExit("Usage: python tools/measure_media_storage.py TEST_BINARY PHASE OUTPUT_DIRECTORY")

binary = Path(sys.argv[1]).resolve()
phase = sys.argv[2]
out = Path(sys.argv[3]).resolve()
out.mkdir(parents=True, exist_ok=True)


class Counters(ctypes.Structure):
    _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD)] + [
        (name, ctypes.c_size_t) for name in [
            "PeakWorkingSetSize", "WorkingSetSize", "QuotaPeakPagedPoolUsage",
            "QuotaPagedPoolUsage", "QuotaPeakNonPagedPoolUsage", "QuotaNonPagedPoolUsage",
            "PagefileUsage", "PeakPagefileUsage", "PrivateUsage"]]


query = ctypes.WinDLL("psapi", use_last_error=True).GetProcessMemoryInfo
query.argtypes = [wintypes.HANDLE, ctypes.POINTER(Counters), wintypes.DWORD]
query.restype = wintypes.BOOL
trials = []
for trial in range(3):
    log_path = out / f"{phase}-{trial + 1}.log"
    with log_path.open("wb") as log:
        began = time.perf_counter()
        process = subprocess.Popen([str(binary),
            "server::tests::media::large_media_responses_keep_full_and_range_bytes_alive_independently",
            "--exact", "--nocapture", "--test-threads=1"], stdout=log, stderr=subprocess.STDOUT)
        samples = []
        try:
            while process.poll() is None:
                if time.perf_counter() - began > 60:
                    raise TimeoutError(f"owned measurement process exceeded 60 seconds: {process.pid}")
                counters = Counters()
                counters.cb = ctypes.sizeof(counters)
                if query(wintypes.HANDLE(process._handle), ctypes.byref(counters), counters.cb):
                    samples.append({"private_bytes": counters.PrivateUsage,
                        "working_set_bytes": counters.WorkingSetSize,
                        "peak_working_set_bytes": counters.PeakWorkingSetSize})
                elif process.poll() is None:
                    raise ctypes.WinError(ctypes.get_last_error())
                time.sleep(.005)
            code = process.wait()
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()
    raw = log_path.read_text(encoding="utf-8")
    match = re.search(r"media_storage_measurement=(\{[^\n]+\})", raw)
    if code or not match or not samples:
        raise RuntimeError(f"trial failed: {code}, see {log_path}")
    trials.append({"exit_code": code, "wall_seconds": time.perf_counter() - began,
        "samples": len(samples), "requested_sample_period_seconds": .005,
        "max_observed_private_bytes": max(s["private_bytes"] for s in samples),
        "max_observed_working_set_bytes": max(s["working_set_bytes"] for s in samples),
        "peak_working_set_bytes": max(s["peak_working_set_bytes"] for s in samples),
        "measurement": json.loads(match[1]), "log": log_path.name,
        "owned_process_exited": process.poll() is not None})
result = {"phase": phase, "binary": str(binary), "trials": trials,
    "scope": "Debug Actix in-process production-route response construction and retention; not sockets, throughput, slow clients, long-term reclamation, or SLO.",
    "memory_scope": "Whole isolated test process. Sampling requests a 5ms sleep between observations; scheduling and query overhead can extend intervals, and observed maxima can miss brief peaks. Peak working set is OS process high-water mark.",
    "measurement_scope": "construction_us includes route setup per response, headers and retaining body handles, excludes fixture setup and byte validation. Buffer count is observation, not an acceptance threshold."}
(out / f"{phase}.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
print(json.dumps(result, indent=2))
