"""Capture two real official frontend runs of the pinned nested-cache fixture."""

from __future__ import annotations

import argparse
import base64
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import pathlib
import subprocess
import sys
import tempfile
import time
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests/browser"))

from componentv2_state_capture import Recorder, _cleanup_owned, frames, free_port, write_json  # noqa: E402
from componenttrigger_capture import CHROME_CANDIDATES, click, evaluate, http_json, rect, settle  # noqa: E402


def wait_run(recorder, before):
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        completed = sum("script_finished" in frame["message"] for frame in frames(recorder))
        if completed > before and settle(recorder, quiet=0.8, timeout=10):
            return completed
        time.sleep(0.1)
    raise RuntimeError("no new completed nested-cache script run")


def collect(out):
    if importlib.metadata.version("streamlit") != "1.66.1":
        raise RuntimeError("Run with target/pyref-venv/Scripts/python.exe (Streamlit 1.66.1)")
    out.mkdir(parents=True, exist_ok=False)
    server_port, chrome_port = free_port(), free_port()
    url = f"http://127.0.0.1:{server_port}"
    app = ROOT / "tests/reference/cache_nested_app.py"
    server_command = [sys.executable, "-B", "-m", "streamlit", "run", str(app),
                      "--server.address=127.0.0.1", f"--server.port={server_port}",
                      "--server.headless=true", "--server.fileWatcherType=none", "--browser.gatherUsageStats=false"]
    capture = {"schema_version": 1, "runtime": "python", "reference_version": "1.66.1",
               "captured_at_utc": datetime.now(timezone.utc).isoformat(), "app": app.relative_to(ROOT).as_posix(),
               "git_revision": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
               "server_command": server_command, "url": url, "chrome_port": chrome_port,
               "configuration": {"server.address": "127.0.0.1", "server.port": server_port, "server.headless": True,
                                 "server.fileWatcherType": "none", "browser.gatherUsageStats": False}, "stages": []}
    server = chrome = recorder = None
    profile = tempfile.TemporaryDirectory(prefix="cache-nested-", dir=ROOT / "target")
    try:
        if not pathlib.Path(profile.name).resolve().is_relative_to((ROOT / "target").resolve()):
            raise RuntimeError("owned browser profile is outside target")
        # 1. 仅启动本次自有 server、headless Chrome 和隔离 profile。
        with (out / "server.log").open("w", encoding="utf-8") as server_log, (out / "chrome.log").open("w", encoding="utf-8") as chrome_log:
            flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            server = subprocess.Popen(server_command, cwd=ROOT, stdout=server_log, stderr=subprocess.STDOUT, creationflags=flags)
            capture["server_pid"] = server.pid
            deadline = time.monotonic() + 30
            while True:
                try:
                    with urllib.request.urlopen(url + "/_stcore/health", timeout=1) as response:
                        capture["health"] = {"status": response.status, "body": response.read().decode()}
                    break
                except OSError:
                    if time.monotonic() > deadline or server.poll() is not None:
                        raise RuntimeError("owned reference server did not start")
                    time.sleep(0.1)
            chrome_path = next(path for path in CHROME_CANDIDATES if pathlib.Path(path).is_file())
            chrome_command = [chrome_path, "--headless=new", "--disable-gpu", f"--remote-debugging-port={chrome_port}",
                              f"--user-data-dir={profile.name}", "--no-first-run", "--no-default-browser-check", "about:blank"]
            chrome = subprocess.Popen(chrome_command, stdout=chrome_log, stderr=subprocess.STDOUT, creationflags=flags)
            capture.update(chrome_pid=chrome.pid, chrome_command=chrome_command)
            deadline = time.monotonic() + 30
            while True:
                try:
                    capture["browser"] = http_json(f"http://127.0.0.1:{chrome_port}/json/version")
                    break
                except OSError:
                    if time.monotonic() > deadline or chrome.poll() is not None:
                        raise RuntimeError("owned Chrome did not start")
                    time.sleep(0.1)
            target = http_json(f"http://127.0.0.1:{chrome_port}/json/new?about:blank", method="PUT")
            recorder = Recorder(target["webSocketDebuggerUrl"])
            recorder.label = "python-cache-nested"
            recorder.start()
            recorder.call("Emulation.setDeviceMetricsOverride", {"width": 1000, "height": 1800, "deviceScaleFactor": 1, "mobile": False})

            # 2. 一次初始加载及一次真实 Again 点击，保留所有 PB delta 与路径。
            before = seen = 0
            for name in ("load", "again"):
                operation = {"action": name, "command_start": len(recorder.commands)}
                if name == "load":
                    recorder.call("Page.navigate", {"url": url})
                else:
                    point = rect(recorder, "[...document.querySelectorAll('button')].find(b=>b.textContent.trim()==='Again')")
                    if point is None:
                        raise RuntimeError("missing actual Again button")
                    click(recorder, point)
                before = wait_run(recorder, before)
                all_frames = frames(recorder)
                dom = json.loads(evaluate(recorder, "JSON.stringify({code:document.querySelector('pre code')?.textContent,markdowns:[...document.querySelectorAll('[data-testid=stMarkdownContainer] p')].map(e=>e.textContent),buttons:[...document.querySelectorAll('button')].map(e=>e.textContent.trim()),exceptions:[...document.querySelectorAll('[data-testid=stException]')].map(e=>e.innerText)})"))
                if dom["exceptions"]:
                    raise RuntimeError("reference raised: " + str(dom["exceptions"]))
                observed = json.loads(dom["code"])
                png = base64.b64decode(recorder.call("Page.captureScreenshot", {"format": "png"})["result"]["data"])
                (out / (name + ".png")).write_bytes(png)
                operation["command_end"] = len(recorder.commands)
                capture["stages"].append({"name": name, "operation": operation, "frame_start": seen, "frame_end": len(all_frames),
                                          "observed": observed, "dom": dom, "screenshot": {"file": name + ".png", "sha256": hashlib.sha256(png).hexdigest()}})
                seen = len(all_frames)
                print(name, json.dumps(observed), flush=True)
            capture["frames"] = frames(recorder)
            versions = {frame["message"]["new_session"]["initialize"]["environment_info"]["streamlit_version"]
                        for frame in capture["frames"] if "new_session" in frame["message"]}
            if versions != {"1.66.1"}:
                raise RuntimeError("actual wire runtime version differs: " + str(versions))

            # 3. 紧凑 oracle 仅从本次真实 wire 和页面 JSON 提取，不预设 transient 数量。
            compact = {"schema_version": 1, "reference_version": "1.66.1", "stages": []}
            for stage in capture["stages"]:
                timeline = []
                for index in range(stage["frame_start"], stage["frame_end"]):
                    message = capture["frames"][index]["message"]
                    if "delta" in message:
                        timeline.append({"frame_index": index, "delta_path": message.get("metadata", {}).get("delta_path", []),
                                         "delta": message["delta"]})
                compact["stages"].append({"name": stage["name"], "round": stage["observed"]["round"],
                                          "timeline": timeline, "returned": stage["observed"]["returned"],
                                          "counters": stage["observed"]["counters"]})
            write_json(out / "cache-cases.json", compact)
    except Exception as error:
        capture["producer_error"] = f"{type(error).__name__}: {error}"
        raise
    finally:
        _cleanup_owned(capture, recorder, chrome, server, profile, out)
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True)
    raise SystemExit(collect(pathlib.Path(parser.parse_args().out)))
