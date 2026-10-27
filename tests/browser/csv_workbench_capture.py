"""Real CSV workbench UI capture; every stage keeps raw CDP/PB and artifacts."""

from __future__ import annotations

import argparse
import base64
import csv
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import io
import json
import pathlib
import subprocess
import sys
import tempfile
import time
import urllib.request

import pyarrow as pa

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests/browser"))

from componentv2_state_capture import Recorder, _cleanup_owned, frames, free_port, write_json  # noqa: E402
from componenttrigger_capture import CHROME_CANDIDATES, click, evaluate, http_json, rect, settle  # noqa: E402
from dataeditor_capture import key  # noqa: E402


def input_files(out):
    inputs = out / "inputs"
    inputs.mkdir()
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerows([["item", "region", "quantity", "note"], ["rC", "north", "30", 'line 1\nline 2,"quoted"'], ["rA", "south", "10", "é游戏"], ["rB", "", "20", ""]])
    payloads = {"workbench-bom.csv": b"\xef\xbb\xbf" + stream.getvalue().encode(),
                "replacement.csv": b"item,region,quantity,note\nother,east,5,replaced\n", "header-only.csv": b"item,region,quantity,note\n",
                "bad-utf8.csv": b"item,region\nx,\xff\n", "empty-header.csv": b"item,,quantity\nx,y,1\n",
                "duplicate-header.csv": b"item,item\nx,y\n", "ragged.csv": b"item,region\nx\n", "bad-quote.csv": b'item,region\n"x"z,y\n'}
    for name, data in payloads.items():
        (inputs / name).write_bytes(data)
    return inputs


class WorkbenchCapture:
    def __init__(self, recorder, out, capture, target):
        self.recorder, self.out, self.capture, self.target = recorder, out, capture, target
        self.seen = 0

    def evaluate(self, expression):
        return evaluate(self.recorder, expression)

    def scroll(self, expression):
        self.evaluate("(()=>{const e=" + expression + ";if(!e)return false;e.scrollIntoView({block:'center'});return true;})()")

    def button(self, label):
        expression = "[...document.querySelectorAll('button,a')].find(e=>e.textContent.trim()===" + json.dumps(label) + ")"
        self.scroll(expression)
        point = rect(self.recorder, expression)
        if point is None:
            raise RuntimeError("missing actual control: " + label)
        click(self.recorder, point)

    def upload(self, path):
        document = self.recorder.call("DOM.getDocument", {"depth": 0})["result"]["root"]
        node = self.recorder.call("DOM.querySelector", {"nodeId": document["nodeId"], "selector": "[data-testid=stFileUploaderDropzoneInput]"})["result"]["nodeId"]
        if not node:
            raise RuntimeError("missing actual upload input")
        self.recorder.call("DOM.setFileInputFiles", {"files": [str(path.resolve())], "nodeId": node})

    def clear_upload(self):
        expression = "[...document.querySelectorAll('[data-testid=stFileChipDeleteBtn] button,[aria-label^=Remove]')].find(e=>(e.getAttribute('aria-label')||'').startsWith('Remove '))"
        self.scroll(expression)
        point = rect(self.recorder, expression)
        if point is None:
            raise RuntimeError("missing actual remove-file control")
        click(self.recorder, point)

    def select(self, label, value):
        expression = "[...document.querySelectorAll('[data-testid=stSelectbox]')].find(e=>e.innerText.trim().startsWith(" + json.dumps(label) + ")).querySelector('[role=combobox]')"
        self.scroll(expression)
        click(self.recorder, rect(self.recorder, expression))
        time.sleep(0.2)
        option = "[...document.querySelectorAll('[role=option]')].find(e=>e.textContent.trim()===" + json.dumps(value) + ")"
        point = rect(self.recorder, option)
        if point is None:
            raise RuntimeError("missing actual option " + value)
        click(self.recorder, point)

    def check(self, label):
        expression = "[...document.querySelectorAll('[data-testid=stCheckbox]')].find(e=>e.textContent.trim()===" + json.dumps(label) + ").querySelector('label')"
        self.scroll(expression)
        click(self.recorder, rect(self.recorder, expression))

    def fill(self, label, text):
        expression = "[...document.querySelectorAll('[data-testid=stTextInput]')].find(e=>e.innerText.trim().startsWith(" + json.dumps(label) + ")).querySelector('input')"
        self.scroll(expression)
        click(self.recorder, rect(self.recorder, expression))
        self.recorder.call("Input.dispatchKeyEvent", {"type": "rawKeyDown", "key": "a", "code": "KeyA", "windowsVirtualKeyCode": 65, "modifiers": 2})
        self.recorder.call("Input.dispatchKeyEvent", {"type": "keyUp", "key": "a", "code": "KeyA", "windowsVirtualKeyCode": 65, "modifiers": 2})
        key(self.recorder, "Backspace", "Backspace", 8)
        if text:
            self.recorder.call("Input.insertText", {"text": text})
        key(self.recorder, "Enter", "Enter", 13)

    def grid(self, index):
        expression = "[...document.querySelectorAll('[data-testid=stDataFrame]')].at(" + str(index) + ")"
        self.scroll(expression)
        return expression

    def grid_click(self, index, x, y):
        expression = self.grid(index) + ".querySelector('[data-testid=data-grid-canvas]')"
        bounds = json.loads(self.evaluate("JSON.stringify((()=>{const r=" + expression + ".getBoundingClientRect();return {x:r.x,y:r.y,width:r.width};})())"))
        click(self.recorder, {"x": bounds["x"] + x, "y": bounds["y"] + y})

    def edit(self, index, column, text):
        self.grid_click(index, 32 + (700 - 32) * (column + 0.5) / 4, 52)
        first = text[0]
        key(self.recorder, first, "Key" + first.upper(), ord(first.upper()), text=first)
        time.sleep(0.2)
        if text[1:]:
            self.recorder.call("Input.insertText", {"text": text[1:]})
        key(self.recorder, "Enter", "Enter", 13)

    def add_row(self):
        expression = self.grid(-1)
        point = rect(self.recorder, expression)
        self.recorder.call("Input.dispatchMouseEvent", {"type": "mouseMoved", **point})
        time.sleep(0.4)
        button = expression + ".querySelector('button[aria-label=\"Add row\"]')"
        point = rect(self.recorder, button)
        if point is None:
            raise RuntimeError("missing actual New rows draft Add row control")
        click(self.recorder, point)

    def snapshot(self, name, action, wait=True, file=None):
        recorder = self.recorder
        command_start = len(recorder.commands)
        recorder.call("Page.bringToFront")
        before = sum("script_finished" in f["message"] for f in frames(recorder))
        action()
        if wait:
            deadline = time.monotonic() + 12
            while sum("script_finished" in f["message"] for f in frames(recorder)) <= before and time.monotonic() < deadline:
                time.sleep(0.1)
        else:
            time.sleep(1)
        settle(recorder, quiet=0.8, timeout=10)
        all_frames = frames(recorder)
        state = json.loads(self.evaluate("JSON.stringify({markdowns:[...document.querySelectorAll('[data-testid=stMarkdownContainer]')].map(e=>e.textContent),alerts:[...document.querySelectorAll('[data-testid=stAlert]')].map(e=>e.innerText),subheaders:[...document.querySelectorAll('h3')].map(e=>e.textContent),text_inputs:[...document.querySelectorAll('[data-testid=stTextInput]')].map(e=>({label:e.innerText,value:e.querySelector('input')?.value})),checkboxes:[...document.querySelectorAll('[data-testid=stCheckbox]')].map(e=>({label:e.textContent,value:e.querySelector('input')?.checked})),selectboxes:[...document.querySelectorAll('[data-testid=stSelectbox]')].map(e=>({label:e.innerText})),grids:[...document.querySelectorAll('[data-testid=stDataFrame]')].map(e=>({cells:[...e.querySelectorAll('[data-testid^=glide-cell]')].map(c=>({id:c.getAttribute('data-testid'),text:c.textContent}))})),exceptions:[...document.querySelectorAll('[data-testid=stException]')].map(e=>e.innerText)})"))
        tables = []
        charts = []
        runs = []
        finishes = []
        for index in range(self.seen, len(all_frames)):
            message = all_frames[index]["message"]
            if "new_session" in message:
                runs.append({"frame_index": index, **message["new_session"]})
            if "script_finished" in message:
                finishes.append(message["script_finished"])
            element = message.get("delta", {}).get("new_element", {})
            if "dataframe" in element:
                frame = element["dataframe"]
                decoded = pa.ipc.open_stream(base64.b64decode(frame["arrow_data"]["data"])).read_all()
                tables.append({"frame_index": index, "delta_path": message.get("metadata", {}).get("delta_path", []),
                               "fields": {k: v for k, v in frame.items() if k != "arrow_data"},
                               "schema": [{"name": f.name, "type": str(f.type), "nullable": f.nullable} for f in decoded.schema], "rows": decoded.to_pylist()})
            if "vega_lite_chart" in element:
                chart = element["vega_lite_chart"]
                datasets = []
                if chart.get("data", {}).get("data"):
                    decoded = pa.ipc.open_stream(base64.b64decode(chart["data"]["data"])).read_all()
                    datasets.append({"name": None, "rows": decoded.to_pylist()})
                for dataset in chart.get("datasets", []):
                    if dataset.get("data", {}).get("data"):
                        decoded = pa.ipc.open_stream(base64.b64decode(dataset["data"]["data"])).read_all()
                        datasets.append({"name": dataset.get("name"), "rows": decoded.to_pylist()})
                charts.append({"frame_index": index, "spec": chart.get("spec"), "datasets": datasets})
        prefix = f"{len(self.capture['stages']):02d}-{self.target}-{name}"
        metrics = recorder.call("Page.getLayoutMetrics")["result"]["cssContentSize"]
        screenshot_response = recorder.call("Page.captureScreenshot", {"format": "png", "captureBeyondViewport": True,
                                             "clip": {"x": 0, "y": 0, "width": metrics["width"], "height": metrics["height"], "scale": 1}})
        if "result" not in screenshot_response:
            raise RuntimeError("actual screenshot failed: " + json.dumps(screenshot_response))
        png = base64.b64decode(screenshot_response["result"]["data"])
        (self.out / (prefix + ".png")).write_bytes(png)
        stage = {"target": self.target, "name": name, "frame_start": self.seen, "frame_end": len(all_frames),
                 "command_start": command_start, "command_end": len(recorder.commands), "dom": state, "tables": tables, "charts": charts,
                 "runs": runs, "finishes": finishes, "screenshot": {"file": prefix + ".png", "bytes": len(png), "sha256": hashlib.sha256(png).hexdigest()}}
        if file is not None:
            data = file.read_bytes()
            stage["input"] = {"file": file.relative_to(self.out).as_posix(), "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
        self.capture["stages"].append(stage)
        self.capture["targets"][self.target] = {"frames": all_frames, "events": recorder.take(), "commands": recorder.commands}
        self.seen = len(all_frames)
        write_json(self.out / "progress.json", self.capture)
        print(self.target, name, "finishes", finishes, "tables", [t["rows"] for t in tables[-3:]], "alerts", state["alerts"], flush=True)
        if state["exceptions"]:
            raise RuntimeError("actual application exception: " + str(state["exceptions"]))
        if wait and not finishes:
            raise RuntimeError("no actual completed run after " + name)
        return stage

    def download(self, name):
        directory = self.out / "downloads"
        before = {p: (p.stat().st_mtime_ns, p.stat().st_size) for p in directory.iterdir()}
        stage = self.snapshot(name, lambda: self.button("Download CSV"), wait=False)
        deadline = time.monotonic() + 10
        paths = []
        while time.monotonic() < deadline:
            paths = [p for p in directory.iterdir() if p.suffix == ".csv" and before.get(p) != (p.stat().st_mtime_ns, p.stat().st_size)]
            if paths:
                break
            time.sleep(0.1)
        if len(paths) != 1:
            raise RuntimeError("actual browser download did not complete once")
        data = paths[0].read_bytes()
        artifacts = self.out / "artifacts"
        artifacts.mkdir(exist_ok=True)
        artifact = artifacts / (self.target + "-" + name + ".csv")
        artifact.write_bytes(data)
        parsed = list(csv.reader(io.StringIO(data.decode("utf-8"), newline=""), strict=True))
        stage["download"] = {"file": artifact.relative_to(self.out).as_posix(), "browser_file": paths[0].relative_to(self.out).as_posix(), "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(),
                             "base64": base64.b64encode(data).decode(), "headers": parsed[0], "rows": parsed[1:], "utf8_bom": data.startswith(b"\xef\xbb\xbf")}
        write_json(self.out / "progress.json", self.capture)
        return stage


def collect(args):
    if importlib.metadata.version("streamlit") != "1.66.1":
        raise RuntimeError("requires the pinned reference/decoder environment")
    out = pathlib.Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=False)
    (out / "downloads").mkdir()
    inputs = input_files(out)
    initial_file = inputs / "workbench-bom.csv"
    chrome_port = free_port()
    url = args.url or f"http://127.0.0.1:{free_port()}/"
    command = [sys.executable, "-B", "-m", "streamlit", "run", str(ROOT / "tests/reference/csv_workbench_app.py"), "--server.address=127.0.0.1",
               f"--server.port={url.rstrip('/').rsplit(':', 1)[1]}", "--server.headless=true", "--server.fileWatcherType=none", "--browser.gatherUsageStats=false"]
    capture = {"schema_version": 1, "runtime": args.runtime, "reference_version": "1.66.1", "captured_at_utc": datetime.now(timezone.utc).isoformat(),
               "url": url, "chrome_port": chrome_port, "segment": args.segment, "external_server": bool(args.url),
               "server_cleanup": "caller-owned" if args.url else "collector-owned", "server_command": None if args.url else command, "targets": {}, "stages": []}
    server = chrome = None
    recorders = {}
    profile = tempfile.TemporaryDirectory(prefix="csv-workbench-", dir=out)
    try:
        with (out / "server.log").open("w", encoding="utf-8") as server_log, (out / "chrome.log").open("w", encoding="utf-8") as chrome_log:
            if not args.url:
                server = subprocess.Popen(command, cwd=ROOT, stdout=server_log, stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW)
                capture["server_pid"] = server.pid
            deadline = time.monotonic() + 25
            while True:
                try:
                    with urllib.request.urlopen(url.rstrip("/") + "/_stcore/health", timeout=1) as response:
                        capture["health"] = {"status": response.status, "body": response.read().decode()}
                    break
                except OSError:
                    if time.monotonic() > deadline or server is not None and server.poll() is not None:
                        raise RuntimeError("workbench server unavailable")
                    time.sleep(0.1)
            chrome_path = next(p for p in CHROME_CANDIDATES if pathlib.Path(p).is_file())
            chrome_command = [chrome_path, "--headless=new", "--disable-gpu", f"--remote-debugging-port={chrome_port}", f"--user-data-dir={profile.name}", "--no-first-run", "--no-default-browser-check", "about:blank"]
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

            def target(label):
                page = http_json(f"http://127.0.0.1:{chrome_port}/json/new?about:blank", method="PUT")
                recorder = Recorder(page["webSocketDebuggerUrl"])
                recorder.label = label
                recorders[label] = recorder
                recorder.start()
                recorder.call("Network.enable", {"maxPostDataSize": 1024 * 1024})
                recorder.call("Emulation.setDeviceMetricsOverride", {"width": 1264, "height": 1100, "deviceScaleFactor": 1, "mobile": False})
                recorder.call("Browser.setDownloadBehavior", {"behavior": "allow", "downloadPath": str(out / "downloads"), "eventsEnabled": True})
                return WorkbenchCapture(recorder, out, capture, label)

            a = target("A")
            a.snapshot("load", lambda: a.recorder.call("Page.navigate", {"url": url}))
            a.snapshot("upload-bom", lambda: a.upload(initial_file), file=initial_file)
            if args.segment == "main":
                a.snapshot("empty-append", lambda: a.button("Append"))
                a.snapshot("count-region", lambda: a.select("Count by", "region"))
                a.snapshot("sort-item", lambda: a.grid_click(0, 110, 16), wait=False)
                a.snapshot("select-sorted-first", lambda: a.grid_click(0, 17, 52))
                a.snapshot("edit-detail-unapplied", lambda: a.edit(1, 1, "north"))
                a.download("download-unapplied")
                a.snapshot("apply", lambda: a.button("Apply"))
                a.download("download-applied")
                a.snapshot("new-row", a.add_row)
                a.snapshot("edit-new-row", lambda: a.edit(-1, 0, "new"))
                a.snapshot("append", lambda: a.button("Append"))
                a.download("download-appended")
                a.snapshot("ordinary-rerun", lambda: a.button("Ordinary rerun"))
                b = target("B")
                b.snapshot("isolated-load", lambda: b.recorder.call("Page.navigate", {"url": url}))
                b.snapshot("isolated-upload", lambda: b.upload(inputs / "replacement.csv"), file=inputs / "replacement.csv")
                b.download("isolated-download")
                a.snapshot("A-after-B", lambda: a.button("Ordinary rerun"))
                a.download("A-after-B-download")
            elif args.segment == "filters":
                a.snapshot("new-row", a.add_row)
                a.snapshot("pending-new-row", lambda: a.edit(-1, 0, "pending"))
                a.snapshot("select-first", lambda: a.grid_click(0, 17, 52))
                a.snapshot("detail-draft", lambda: a.edit(1, 0, "scratch"))
                a.snapshot("count-region", lambda: a.select("Count by", "region"))
                a.snapshot("enable-empty-match", lambda: a.check("Filter enabled"))
                a.snapshot("filter-region-empty", lambda: a.select("Filter column", "region"))
                a.snapshot("no-match", lambda: a.fill("Exact value", "missing"))
                a.snapshot("disable-keep-value", lambda: a.check("Filter enabled"))
                a.snapshot("append-preserved-draft", lambda: a.button("Append"))
                a.download("filtered-flow-download")
            else:
                for name in ("bad-utf8.csv", "empty-header.csv", "duplicate-header.csv", "ragged.csv", "bad-quote.csv"):
                    a.snapshot("reject-" + name.removesuffix(".csv"), lambda name=name: a.upload(inputs / name), file=inputs / name)
                a.download("after-errors-download")
                a.snapshot("header-only", lambda: a.upload(inputs / "header-only.csv"), file=inputs / "header-only.csv")
                a.download("header-only-download")
                a.snapshot("replace-valid", lambda: a.upload(inputs / "replacement.csv"), file=inputs / "replacement.csv")
                a.download("replacement-download")
                a.snapshot("clear-upload", a.clear_upload)
                a.snapshot("empty-rerun", lambda: a.button("Ordinary rerun"))
            capture["successful"] = True
    except Exception as error:
        capture["producer_error"] = f"{type(error).__name__}: {error}"
        raise
    finally:
        secondary_errors = []
        for label, recorder in recorders.items():
            try:
                capture["targets"][label] = {"frames": frames(recorder), "events": recorder.take(), "commands": recorder.commands}
            except Exception as error:
                secondary_errors.append({"step": label + ".preserve", "error": str(error)})
            try:
                recorder.stop()
            except Exception as error:
                secondary_errors.append({"step": label + ".stop", "error": str(error)})
        capture["recorder_cleanup_errors"] = secondary_errors
        try:
            _cleanup_owned(capture, None, chrome, server, profile, out)
        finally:
            if args.url:
                capture["cleanup"]["server_stopped"] = None
                capture["cleanup"]["server_cleanup"] = "caller-owned"
                write_json(out / "trace.json", capture)
        if secondary_errors and "producer_error" not in capture:
            raise RuntimeError("recorder cleanup failed: " + json.dumps(secondary_errors))
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime", choices=("python", "rust"), default="python")
    parser.add_argument("--url")
    parser.add_argument("--segment", choices=("main", "filters", "sources"), default="main")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    if args.runtime == "rust" and not args.url:
        parser.error("--runtime rust requires the caller-owned server's --url")
    raise SystemExit(collect(args))
