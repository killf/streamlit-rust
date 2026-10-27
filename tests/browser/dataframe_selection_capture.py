"""Capture independent real frontend selection cases without injecting BackMsg."""

from __future__ import annotations

import argparse
import base64
from datetime import datetime, timezone
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

CASES = ("ignore", "multi", "single-combo", "multi-combo", "required")


def completed(recorder):
    return sum("script_finished" in f["message"] for f in frames(recorder))


def dom(recorder):
    return json.loads(evaluate(recorder, "JSON.stringify({code:document.querySelector('pre code')?.textContent,cells:[...document.querySelectorAll('[data-testid^=glide-cell]')].map(e=>({id:e.getAttribute('data-testid'),text:e.textContent})),exceptions:[...document.querySelectorAll('[data-testid=stException]')].map(e=>e.innerText),buttons:[...document.querySelectorAll('button')].map(e=>({text:e.textContent.trim(),label:e.getAttribute('aria-label')}))})"))


def collect(out, cases):
    if importlib.metadata.version("streamlit") != "1.66.1":
        raise RuntimeError("requires pinned Streamlit 1.66.1 reference environment")
    out.mkdir(parents=True, exist_ok=False)
    server_port, chrome_port = free_port(), free_port()
    url = f"http://127.0.0.1:{server_port}/"
    command = [sys.executable, "-B", "-m", "streamlit", "run", str(ROOT / "tests/reference/dataframe_selection_app.py"),
               "--server.address=127.0.0.1", f"--server.port={server_port}", "--server.headless=true",
               "--server.fileWatcherType=none", "--browser.gatherUsageStats=false"]
    capture = {"schema_version": 1, "runtime": "python", "reference_version": "1.66.1",
               "captured_at_utc": datetime.now(timezone.utc).isoformat(), "url": url, "chrome_port": chrome_port,
               "git_revision": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
               "server_command": command, "cases": cases, "stages": [], "case_errors": []}
    server = chrome = recorder = None
    profile = tempfile.TemporaryDirectory(prefix="selection-", dir=ROOT / "target/checks/m2-dataframe-selection")
    seen = 0
    try:
        # 1. 仅启动自有 server、headless Chrome、profile，并记录真实 CDP 输入。
        with (out / "server.log").open("w", encoding="utf-8") as server_log, (out / "chrome.log").open("w", encoding="utf-8") as chrome_log:
            server = subprocess.Popen(command, cwd=ROOT, stdout=server_log, stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW)
            capture["server_pid"] = server.pid
            deadline = time.monotonic() + 25
            while True:
                try:
                    with urllib.request.urlopen(url + "_stcore/health", timeout=1) as response:
                        capture["health"] = {"status": response.status, "body": response.read().decode()}
                    break
                except OSError:
                    if time.monotonic() > deadline or server.poll() is not None:
                        raise RuntimeError("owned reference server did not start")
                    time.sleep(0.1)
            chrome_path = next(p for p in CHROME_CANDIDATES if pathlib.Path(p).is_file())
            chrome_command = [chrome_path, "--headless=new", "--disable-gpu", f"--remote-debugging-port={chrome_port}",
                              f"--user-data-dir={profile.name}", "--no-first-run", "--no-default-browser-check", "about:blank"]
            chrome = subprocess.Popen(chrome_command, stdout=chrome_log, stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW)
            capture.update(chrome_pid=chrome.pid, chrome_command=chrome_command)
            deadline = time.monotonic() + 25
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
            recorder.label = "python-dataframe-selection"
            recorder.start()
            recorder.call("Emulation.setDeviceMetricsOverride", {"width": 1264, "height": 1100, "deviceScaleFactor": 1, "mobile": False})

            def step(case, name, action, wait="run"):
                nonlocal seen
                before = completed(recorder)
                start = len(recorder.commands)
                action()
                if wait == "run":
                    deadline = time.monotonic() + 8
                    while completed(recorder) <= before and time.monotonic() < deadline:
                        time.sleep(0.1)
                    did_run = completed(recorder) > before
                    settle(recorder, quiet=0.6, timeout=6)
                else:
                    time.sleep(1.6)
                    settle(recorder, quiet=0.4, timeout=4)
                    did_run = completed(recorder) > before
                state = dom(recorder)
                all_frames = frames(recorder)
                stage = {"case": case, "name": name, "wait": wait, "did_run": did_run,
                         "frame_start": seen, "frame_end": len(all_frames), "command_start": start,
                         "command_end": len(recorder.commands), "dom": state}
                if state.get("code"):
                    stage["observed"] = json.loads(state["code"])
                screenshot = f"{len(capture['stages']):02d}-{case}-{name}.png"
                (out / screenshot).write_bytes(base64.b64decode(recorder.call("Page.captureScreenshot", {"format": "png"})["result"]["data"]))
                stage["screenshot"] = screenshot
                capture["stages"].append(stage)
                capture["frames"] = all_frames
                seen = len(all_frames)
                write_json(out / "progress.json", capture)
                print(case, name, "run" if did_run else "NO-RERUN", json.dumps(stage.get("observed", {})), flush=True)
                if state["exceptions"]:
                    raise RuntimeError("reference application exception: " + str(state["exceptions"]))
                if wait == "run" and not did_run:
                    raise RuntimeError("no rerun after expected action " + name)
                return stage

            def button(label):
                point = rect(recorder, "[...document.querySelectorAll('button')].find(b=>b.textContent.trim()===" + json.dumps(label) + ")")
                if point is None:
                    raise RuntimeError("missing button " + label)
                click(recorder, point)

            def point(x, y, modifiers=0):
                origin = json.loads(evaluate(recorder, "JSON.stringify((()=>{const r=document.querySelector('[data-testid=data-grid-canvas]').getBoundingClientRect();return {x:r.x,y:r.y};})())"))
                for kind in ("mousePressed", "mouseReleased"):
                    recorder.call("Input.dispatchMouseEvent", {"type": kind, "x": origin["x"] + x, "y": origin["y"] + y,
                                                               "button": "left", "clickCount": 1, "modifiers": modifiers})

            def rectangle():
                origin = json.loads(evaluate(recorder, "JSON.stringify((()=>{const r=document.querySelector('[data-testid=data-grid-canvas]').getBoundingClientRect();return {x:r.x,y:r.y};})())"))
                for kind, x, y in (("mousePressed", 100, 52), ("mouseMoved", 180, 84), ("mouseMoved", 270, 116), ("mouseReleased", 270, 116)):
                    recorder.call("Input.dispatchMouseEvent", {"type": kind, "x": origin["x"] + x, "y": origin["y"] + y,
                                                               "button": "left", "buttons": 0 if kind == "mouseReleased" else 1, "clickCount": 1})

            # 2. 每个独立配置只采一次，失败保留当前数据，再继续其他配置。
            for case in cases:
                try:
                    step(case, "load", lambda: recorder.call("Page.navigate", {"url": url + "?case=" + case}))
                    if case == "ignore":
                        step(case, "selection-attempt", lambda: point(100, 52), wait="bounded")
                        step(case, "probe", lambda: button("Probe"))
                    elif case == "multi-shrink":
                        step(case, "row-third", lambda: point(17, 116))
                        step(case, "replace-shrink", lambda: button("Replace data"))
                        step(case, "probe-after-shrink", lambda: button("Probe"))
                    elif case == "multi":
                        step(case, "row-first", lambda: point(17, 52))
                        selected = step(case, "row-third", lambda: point(17, 116, 2))
                        if len(selected["observed"]["returned"]["selection"]["rows"]) < 2:
                            raise RuntimeError("real row clicks did not produce multiple rows")
                        step(case, "ordinary-rerun", lambda: button("Probe"))
                        step(case, "sort-qty", lambda: point(274, 16), wait="bounded")
                        step(case, "sorted-row-first", lambda: point(17, 52))
                        step(case, "replace", lambda: button("Replace data"))
                        step(case, "hide", lambda: button("Toggle visible"))
                        step(case, "hidden-probe", lambda: button("Probe"))
                        step(case, "restore", lambda: button("Toggle visible"))
                    elif case == "single-combo":
                        step(case, "user-cell", lambda: point(274, 116))
                        step(case, "ordinary-rerun", lambda: button("Probe"))
                        for label in ("Program rows", "Program columns", "Program cells"):
                            step(case, label.lower().replace(" ", "-"), lambda label=label: button(label))
                        step(case, "callback-cell", lambda: point(434, 84))
                    elif case == "multi-combo":
                        step(case, "row-first", lambda: point(17, 52))
                        step(case, "row-third", lambda: point(17, 116, 2))
                        step(case, "column-id", lambda: point(114, 16))
                        step(case, "column-qty", lambda: point(274, 16, 2))
                        step(case, "rectangle", rectangle)
                    else:
                        step(case, "row-third", lambda: point(17, 116))
                        step(case, "clear-attempt", lambda: point(17, 116, 2), wait="bounded")
                        step(case, "probe", lambda: button("Probe"))
                except Exception as error:
                    capture["case_errors"].append({"case": case, "error": f"{type(error).__name__}: {error}"})
                    write_json(out / "progress.json", capture)
                    print("CASE ERROR", case, str(error), flush=True)
            capture["frames"] = frames(recorder)
            write_json(out / "selection-cases.json", {"schema_version": 1, "reference_version": "1.66.1", "stages": capture["stages"], "case_errors": capture["case_errors"]})
    except Exception as error:
        capture["producer_error"] = f"{type(error).__name__}: {error}"
        raise
    finally:
        _cleanup_owned(capture, recorder, chrome, server, profile, out)
    return 1 if capture["case_errors"] else 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    parser.add_argument("--cases", nargs="+", choices=CASES + ("multi-shrink",), default=list(CASES))
    args = parser.parse_args()
    raise SystemExit(collect(pathlib.Path(args.out), args.cases))
