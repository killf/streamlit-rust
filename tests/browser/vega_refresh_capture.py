"""Capture the generic Vega same-shape refresh flow against a Rust server.

Four stages over the official frontend: load (a=3), Change Vega data (a=8),
Ordinary rerun (a=8), Change Vega data again (a=3). Each stage records the
generic chart's wire (content-named dataset + decoded rows), the visible
ARIA mark labels of every vega chart, and a full-page screenshot — the same
observation that froze the pre-fix miss in rust-vega-refresh-before.
"""
import argparse
import base64
from datetime import datetime, timezone
import importlib.metadata
import json
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "tests/browser"), str(ROOT / "tests/reference")]
import pyarrow as pa
from componentv2_state_capture import Recorder, _cleanup_owned, finished, frames, free_port, wait_run
from componenttrigger_capture import CHROME_CANDIDATES, click, evaluate, http_json, rect


def collect(args):
    if importlib.metadata.version("streamlit") != "1.66.1":
        raise RuntimeError("requires the pinned Streamlit 1.66.1 decoder environment")
    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=False)
    chrome_port = free_port()
    capture = {"runtime": "rust", "reference_decoder": "1.66.1", "url": args.url,
               "captured_at_utc": datetime.now(timezone.utc).isoformat(),
               "server_cleanup": "caller-owned", "stages": []}
    chrome = recorder = None
    profile = tempfile.TemporaryDirectory(prefix="vega-refresh-", dir=out)
    try:
        with (out / "chrome.log").open("w", encoding="utf-8") as chrome_log:
            import subprocess
            flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            chrome_path = next(path for path in CHROME_CANDIDATES if Path(path).is_file())
            chrome_command = [chrome_path, "--headless=new", "--disable-gpu", f"--remote-debugging-port={chrome_port}",
                              f"--user-data-dir={profile.name}", "--no-first-run", "--no-default-browser-check", "about:blank"]
            chrome = subprocess.Popen(chrome_command, stdout=chrome_log, stderr=subprocess.STDOUT, creationflags=flags)
            capture.update(chrome_pid=chrome.pid, chrome_command=chrome_command)
            deadline = __import__("time").monotonic() + 30
            while True:
                try:
                    capture["browser"] = http_json(f"http://127.0.0.1:{chrome_port}/json/version")
                    break
                except OSError:
                    if __import__("time").monotonic() > deadline or chrome.poll() is not None:
                        raise RuntimeError("owned Chrome unavailable")
                    __import__("time").sleep(0.1)
            target = http_json(f"http://127.0.0.1:{chrome_port}/json/new?about:blank", method="PUT")
            recorder = Recorder(target["webSocketDebuggerUrl"])
            recorder.start()
            recorder.call("Network.enable")
            recorder.call("Runtime.enable")
            recorder.call("Emulation.setDeviceMetricsOverride", {"width": 1264, "height": 1100, "deviceScaleFactor": 1, "mobile": False})
            actions = [("load", None), ("change-to-8", "Change Vega data"), ("ordinary-rerun", "Ordinary rerun"), ("change-back-to-3", "Change Vega data")]
            before = seen = 0
            for name, control in actions:
                if control is None:
                    recorder.call("Page.navigate", {"url": args.url})
                else:
                    expression = f"[...document.querySelectorAll('button')].find(e=>e.textContent.trim()==={json.dumps(control)})"
                    evaluate(recorder, "(()=>{const e=" + expression + ";if(!e)return false;e.scrollIntoView({block:'center'});return true;})()")
                    point = rect(recorder, expression)
                    if point is None:
                        raise RuntimeError("control missing: " + name)
                    click(recorder, point)
                wait_run(recorder, before)
                before = finished(recorder)
                all_frames = frames(recorder)
                response = recorder.call("Runtime.evaluate", {"expression": "JSON.stringify({charts:[...document.querySelectorAll('[data-testid=stVegaLiteChart]')].map(e=>({aria:[...e.querySelectorAll('[role=graphics-symbol]')].map(n=>n.getAttribute('aria-label'))})),exceptions:[...document.querySelectorAll('[data-testid=stException]')].map(e=>e.innerText)})", "returnByValue": True})
                value = response.get("result", {}).get("result", {}).get("value")
                if value is None:
                    raise RuntimeError("dom evaluate returned no value: " + json.dumps(response, ensure_ascii=False)[:500])
                dom = json.loads(value)
                charts = []
                for index in range(seen, len(all_frames)):
                    element = all_frames[index]["message"].get("delta", {}).get("new_element", {})
                    if "vega_lite_chart" in element:
                        chart = element["vega_lite_chart"]
                        datasets = []
                        for dataset in chart.get("datasets", []):
                            if dataset.get("data", {}).get("data"):
                                decoded = pa.ipc.open_stream(base64.b64decode(dataset["data"]["data"])).read_all()
                                datasets.append({"name": dataset.get("name"), "rows": decoded.to_pylist()})
                        charts.append({"frame_index": index, "spec": chart.get("spec"), "datasets": datasets})
                metrics = recorder.call("Page.getLayoutMetrics")["result"]["cssContentSize"]
                png = recorder.call("Page.captureScreenshot", {"format": "png", "captureBeyondViewport": True,
                                    "clip": {"x": 0, "y": 0, "width": metrics["width"], "height": metrics["height"], "scale": 1}})["result"]["data"]
                (out / f"{name}.png").write_bytes(base64.b64decode(png))
                capture["stages"].append({"name": name, "frame_start": seen, "frame_end": len(all_frames), "dom": dom, "charts": charts, "screenshot": name + ".png"})
                seen = len(all_frames)
                print(name, "charts", len(charts), "aria", [a for a in dom["charts"][1]["aria"] if a and "kind:" in a] if len(dom["charts"]) > 1 else [], flush=True)
            capture["frames"] = frames(recorder)
            capture["console_errors"] = [e for e in recorder.take() if e.get("method") in ("Runtime.exceptionThrown", "Log.entryAdded", "Runtime.consoleAPICalled")]
            capture["successful"] = True
    except Exception as error:
        capture["producer_error"] = f"{type(error).__name__}: {error}"
        raise
    finally:
        _cleanup_owned(capture, recorder, chrome, None, profile, out)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True, help="caller-owned Rust chartlibs server URL")
    parser.add_argument("--out", required=True)
    collect(parser.parse_args())
