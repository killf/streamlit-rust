"""Capture the numeric widgets of a Streamlit server with the official frontend.

This is the committed entry point for the numeric comparison.  It reuses the
recorder, the protobuf decoders, the DOM probe, the case list and the strict
click verification of tests/reference/capture_browser_trace.py -- it only adds
the input: the agent-browser CLI cannot start its daemon in this environment,
so the real Chrome is driven over the DevTools Protocol with real key and
mouse events.  Nothing here fabricates a widget state.

    python tests/browser/numeric_capture.py --url http://127.0.0.1:8501/ \
        --label rust --out target/numeric-rust

The output goes to target by default; only a capture that has been reviewed
belongs under tests/browser/.
"""

from __future__ import annotations

import argparse
import base64
import json
import pathlib
import sys
import time
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests" / "reference"))

from capture_browser_trace import (  # noqa: E402
    OBSERVE_JS,
    SUITES,
    case_verdict,
    data_loop_verdict,
    http_requests_from_events,
    suite_counts,
    suite_failures,
    WIDGET_DOM_JS,
    CDP,
    _decode_payload,
    _safe,
    dom_value_for,
    summarise_back,
    summarise_forward,
    verify_click_windows,
    widget_value_matches,
    wire_value_of,
)

CHROME_PORT = 60667


def http_json(url: str, method: str = "GET"):
    req = urllib.request.Request(url, method=method)
    with urllib.request.urlopen(req, timeout=15) as response:
        return json.loads(response.read().decode("utf-8"))


class Page:
    """The input events and the reads this capture needs."""

    def __init__(self, cdp):
        self.cdp = cdp

    def evaluate(self, expression: str):
        response = self.cdp.call(
            "Runtime.evaluate", {"expression": expression, "returnByValue": True}
        )
        inner = (response or {}).get("result", {})
        inner = inner.get("result", inner) if isinstance(inner, dict) else {}
        raw = inner.get("value") if isinstance(inner, dict) else None
        if isinstance(raw, str):
            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                return raw
        return raw

    def click(self, x: float, y: float):
        for kind in ("mousePressed", "mouseReleased"):
            self.cdp.call(
                "Input.dispatchMouseEvent",
                {"type": kind, "x": x, "y": y, "button": "left", "clickCount": 1},
            )

    def press(self, key: str, code: str, vk: int):
        for kind in ("rawKeyDown", "keyUp"):
            self.cdp.call(
                "Input.dispatchKeyEvent",
                {"type": kind, "key": key, "code": code,
                 "windowsVirtualKeyCode": vk, "nativeVirtualKeyCode": vk},
            )

    def rect(self, expression: str):
        js = (
            "(()=>{const e=" + expression + ";if(!e)return null;"
            "const r=e.getBoundingClientRect();"
            "return {x:r.x+r.width/2,y:r.y+r.height/2};})()"
        )
        value = self.evaluate(js)
        return value if isinstance(value, dict) else None

    def focus(self, expression: str) -> bool:
        js = "(()=>{const e=" + expression + ";if(!e)return false;e.focus();return true;})()"
        return bool(self.evaluate(js))

    def option_rect(self, text: str):
        js = (
            "(()=>{const o=[...document.querySelectorAll('[role=option]')]"
            ".find(x=>x.textContent.trim()===" + json.dumps(text) + ");"
            "if(!o)return null;const r=o.getBoundingClientRect();"
            "return {x:r.x+r.width/2,y:r.y+r.height/2};})()"
        )
        value = self.evaluate(js)
        return value if isinstance(value, dict) else None

    def upload(self, paths) -> bool:
        """Hand files to the file input, the way the browser does it."""
        if isinstance(paths, str):
            paths = [paths]
        document = self.cdp.call("DOM.getDocument", {"depth": 0})
        root = (document.get("result", {}) or {}).get("root", {}) or {}
        node = self.cdp.call(
            "DOM.querySelector",
            {"nodeId": root.get("nodeId"), "selector": "[data-testid='stFileUploaderDropzoneInput']"},
        )
        node_id = (node.get("result", {}) or {}).get("nodeId")
        if not node_id:
            return False
        self.cdp.call("DOM.setFileInputFiles", {"files": list(paths), "nodeId": node_id})
        return True

    def remove_file(self, name: str) -> bool:
        """Click the control that removes an uploaded file."""
        js = (
            "(()=>{const b=[...document.querySelectorAll('[data-testid=stFileChipDeleteBtn] button, "
            "[aria-label^=\"Remove\"]')]"
            ".find(x=>x.getAttribute('aria-label')===" + json.dumps("Remove " + name) + ");"
            "if(!b)return false;const r=b.getBoundingClientRect();"
            "return {x:r.x+r.width/2,y:r.y+r.height/2};})()"
        )
        rect = self.evaluate(js)
        if not isinstance(rect, dict):
            return False
        self.click(rect["x"], rect["y"])
        return True

    def files_dom(self):
        """The files the uploader shows."""
        value = self.evaluate(
            "JSON.stringify({chips:[...document.querySelectorAll('[data-testid=stFileChipName]')]"
            ".map(e=>e.textContent.trim()),"
            "chip_count:document.querySelectorAll('[data-testid=stFileChip]').length})"
        )
        return value if isinstance(value, dict) else None

    def chart_tooltip(self):
        """Hover the first bar and read the tooltip the chart shows.

        The tooltip carries the values the chart drew, so it is the rendered
        counterpart of the Arrow payload.
        """
        rect = self.evaluate(
            "(()=>{const m=document.querySelector(\"[data-testid='stVegaLiteChart'] "
            "g[class*='mark-rect'] path\");"
            "if(!m)return null;const r=m.getBoundingClientRect();"
            "return {x:r.x+r.width/2,y:r.y+r.height/2};})()"
        )
        if not isinstance(rect, dict):
            return None
        self.cdp.call(
            "Input.dispatchMouseEvent",
            {"type": "mouseMoved", "x": rect["x"], "y": rect["y"]},
        )
        time.sleep(1.5)
        value = self.evaluate(
            "(()=>{const t=document.querySelector('[data-testid=stTooltipHoverTarget]');"
            "return t?t.innerText.replace(/\\s+/g,' ').trim():null;})()"
        )
        return value if isinstance(value, str) else None

    def result_digest(self):
        """The rendered result: the table cells and the chart."""
        dom = self.evaluate(OBSERVE_JS)
        if not isinstance(dom, dict):
            return None
        return {
            "table_present": dom.get("table_present"),
            "table_cells": dom.get("table_cells"),
            "chart_present": dom.get("chart_present"),
            "chart_bars": dom.get("chart_bars"),
            "chart_labels": dom.get("chart_labels"),
            "chart_marks": dom.get("chart_marks"),
            "alerts": dom.get("alerts"),
        }

    def slider_inputs(self, label: str):
        js = (
            "(()=>{const g=[...document.querySelectorAll('[data-testid=stSlider] [role=group]')]"
            ".find(x=>x.getAttribute('aria-label')===" + json.dumps(label) + ");"
            "if(!g)return null;return [...g.querySelectorAll('input[type=range]')].length;})()"
        )
        return self.evaluate(js)

    def focus_slider(self, label: str, index: int) -> bool:
        js = (
            "(()=>{const g=[...document.querySelectorAll('[data-testid=stSlider] [role=group]')]"
            ".find(x=>x.getAttribute('aria-label')===" + json.dumps(label) + ");"
            "if(!g)return false;"
            "const inputs=[...g.querySelectorAll('input[type=range]')];"
            "const t=inputs[" + str(index) + "];"
            "if(!t)return false;t.focus();return true;})()"
        )
        return bool(self.evaluate(js))

    def focus_checkbox(self, label: str) -> bool:
        js = (
            "(()=>{const roots=[...document.querySelectorAll('[data-testid=stCheckbox]')];"
            "const e=roots.find(r=>r.textContent.includes(" + json.dumps(label) + "));"
            "if(!e)return false;"
            "const i=e.querySelector('input[type=checkbox]');"
            "if(!i)return false;i.focus();return true;})()"
        )
        return bool(self.evaluate(js))

    def open_selectbox(self, label: str) -> bool:
        js = (
            "(()=>{const roots=[...document.querySelectorAll('[data-testid=stSelectbox]')];"
            "const e=roots.find(r=>r.textContent.includes(" + json.dumps(label) + "));"
            "if(!e)return false;"
            "const b=e.querySelector(\"button[aria-label='Open']\");"
            "if(!b)return false;const r=b.getBoundingClientRect();"
            "return {x:r.x+r.width/2,y:r.y+r.height/2};})()"
        )
        rect = self.evaluate(js)
        if not isinstance(rect, dict):
            return False
        self.click(rect["x"], rect["y"])
        return True


def frames_of(recorder):
    """The recorded frames, each with the connection it travelled on.

    The connection is the DevTools request id of the socket, mapped to the
    order the sockets were seen.  A frame that carries no request id keeps
    no connection: it may never be counted as the same connection as
    another frame.
    """
    out = []
    connections = {}
    for event in recorder.take():
        method = event.get("method")
        if method not in ("Network.webSocketFrameSent", "Network.webSocketFrameReceived"):
            continue
        payload = event["params"].get("response", {})
        if payload.get("opcode") != 2:
            continue
        request_id = event["params"].get("requestId")
        if request_id is not None and request_id not in connections:
            connections[request_id] = len(connections)
        data = base64.b64decode(payload.get("payloadData", ""))
        decoded = _safe(
            summarise_back if method.endswith("Sent") else summarise_forward, data
        )
        out.append({
            "direction": "client->server" if method.endswith("Sent") else "server->client",
            "connection": connections.get(request_id),
            "request_id": request_id,
            "decoded": decoded,
        })
    return out


def states_for(frames, widget_id):
    """The widget states the client sent, in order."""
    found = []
    for index, frame in enumerate(frames):
        if frame["direction"] != "client->server":
            continue
        decoded = frame["decoded"]
        if decoded.get("type") != "rerun_script":
            continue
        for state in (decoded.get("rerun_script") or {}).get("widget_states", []) or []:
            if state.get("id") == widget_id:
                found.append((index, state))
    return found



# The controls of the data loop: the group, the minimum amount and the
# unknown region, with the values the reference app expects.
DATA_LOOP_CASES = (
    {"kind": "selectbox", "label": "Group by", "option": "region", "other_option": "channel"},
    {"kind": "checkbox", "label": "Include unknown region"},
    {"kind": "slider", "label": "Minimum amount", "key": "ArrowRight", "times": 10, "thumb": 0},
)


def act(page, case) -> dict:
    """Perform one widget change with a real input event."""
    kind = case["kind"]
    label = case["label"]
    if kind == "slider":
        if page.focus_slider(label, case.get("thumb", 0)):
            for _ in range(case.get("times", 1)):
                page.press(case.get("key", "ArrowRight"), case.get("key", "ArrowRight"), 39)
                time.sleep(0.5)
            return {"action": "press", "key": case.get("key", "ArrowRight"),
                    "times": case.get("times", 1)}
        return {"action": "press", "failed": "no range input"}
    if kind == "checkbox":
        if page.focus_checkbox(label):
            page.press(" ", "Space", 32)
            return {"action": "press-Space"}
        return {"action": "press-Space", "failed": "no checkbox input"}
    if kind == "selectbox":
        opened = page.open_selectbox(label)
        rect = None
        for _ in range(6):
            time.sleep(1.0)
            rect = page.option_rect(case.get("option", "region"))
            if rect:
                break
        if rect:
            page.click(rect["x"], rect["y"])
            return {"action": "select-option", "option": case.get("option", "region")}
        return {"action": "select-option", "failed": "no option", "opened": opened}
    return {"action": "unknown", "failed": f"unknown widget kind {kind!r}"}


def stage_elements(frames):
    """The table and the chart the server sent in these frames."""
    table = None
    chart = None
    for frame in frames:
        decoded = frame.get("decoded") or {}
        delta = decoded.get("delta") or {}
        if delta.get("type") != "new_element":
            continue
        if delta.get("element") in ("dataframe", "table") and delta.get("arrow"):
            table = delta
        if delta.get("element") == "vega_lite_chart":
            chart = delta
    return table, chart



def data_loop_result(stages, upload, file_action, required):
    """The result of a data loop capture: the failures and the counts.

    A stage that did not run, a stage whose verdict is not ok, a failed
    upload and a failed file action all fail the capture.
    """
    failures = []
    if upload.get("failed"):
        failures.append(
            {
                "step": "upload",
                "check": "file_action",
                "expected": "the file to be uploaded",
                "actual": upload["failed"],
            }
        )
    if file_action.get("failed"):
        failures.append(
            {
                "step": "file-action",
                "check": "file_action",
                "expected": "the file action to run",
                "actual": file_action["failed"],
            }
        )
    executed = []
    asserted = []
    by_stage = {}
    for stage in stages:
        verdict = stage.get("verdict")
        if verdict is None:
            continue
        by_stage[stage["stage"]] = stage
        executed.append(stage["stage"])
        if verdict.get("ok"):
            asserted.append(stage["stage"])
        else:
            failures.append(
                {
                    "step": f'stage-{stage["stage"]}',
                    "check": "case_verdict",
                    "expected": "the step to change the result and to be answered on the "
                                 "same connection",
                    "actual": "; ".join(verdict.get("problems") or ["no verdict"]),
                }
            )
    for label in required:
        if label not in by_stage:
            failures.append(
                {
                    "step": f"stage-{label}",
                    "check": "case_executed",
                    "expected": "the step to run against this page",
                    "actual": "not executed",
                }
            )
    counts = {"expected": len(required), "executed": len(executed), "asserted": len(asserted)}
    return {"failures": failures, "counts": counts, "ok": not failures}


def run_data_loop(page, recorder, args, out):
    """Upload a CSV and record the first table and chart.

    The Arrow payload is written as a binary file next to the trace and
    referenced by its digest, so the trace stays readable.
    """
    paths = [path for path in (args.files.split(",") if args.files else [args.fixture]) if path]
    # A replacement uploads the first file and then the second one; every
    # other case uploads what it was given.
    initial = paths if args.file_action == "none" else paths[:1]
    upload = {"action": "upload", "files": initial}
    if initial and page.upload(initial):
        upload["uploaded"] = True
    else:
        upload["failed"] = "the file input was not found"
    deadline = time.time() + 60
    digest = None
    while time.time() < deadline:
        digest = page.result_digest()
        # The table renders its grid after the container, so the cells are
        # what says that the result is there.
        if digest and digest.get("table_cells") and digest.get("chart_labels"):
            break
        time.sleep(1)
    time.sleep(4)

    file_action = {"action": args.file_action, "files_before": page.files_dom()}
    if args.file_action in ("delete", "replace"):
        name = pathlib.Path(paths[0]).name
        if args.file_action == "delete":
            if page.remove_file(name):
                file_action["removed"] = name
                time.sleep(5)
            else:
                file_action["failed"] = "no remove control for " + name
        else:
            second = args.files.split(",")[1] if len(args.files.split(",")) > 1 else ""
            if second and page.upload(second):
                file_action["uploaded"] = second
                time.sleep(6)
            else:
                file_action["failed"] = "no second file"
        digest = page.result_digest()
        file_action["files_after"] = page.files_dom()
        file_action["digest_after"] = digest

    seen = frames_of(recorder)
    events = recorder.take()
    http_requests, static_count = http_requests_from_events(events)

    # The Arrow payload is written once per digest: the table and the chart
    # carry the same bytes.
    arrow_files: dict = {}

    def keep_arrow(arrow):
        if not arrow:
            return None
        digest = arrow.get("sha256")
        if arrow.get("base64") and digest not in arrow_files:
            raw = base64.b64decode(arrow["base64"])
            name = f"arrow-{len(arrow_files) + 1}.bin"
            (out / name).write_bytes(raw)
            arrow_files[digest] = name
        if digest in arrow_files:
            arrow["base64"] = None
            arrow["file"] = arrow_files[digest]
        return arrow

    def describe(frames):
        table, chart = stage_elements(frames)
        described = {}
        if table:
            arrow = keep_arrow(table.get("arrow"))
            described["table"] = {
                "rows": arrow.get("rows") if arrow else None,
                "schema": arrow.get("schema") if arrow else None,
                "columns": arrow.get("columns") if arrow else None,
                "row_count": arrow.get("row_count") if arrow else None,
                "arrow": {"file": arrow.get("file"), "sha256": arrow.get("sha256"),
                          "bytes": arrow.get("bytes")} if arrow else None,
                "arrow_fields": table.get("arrow_fields"),
            }
        if chart:
            described["chart"] = {
                "spec": chart.get("vega_lite_spec"),
                "datasets": [
                    {
                        "name": dataset.get("name"),
                        "has_name": dataset.get("has_name"),
                        "arrow": (
                            {
                                "file": (keep_arrow(dataset.get("arrow")) or {}).get("file"),
                                "sha256": (dataset.get("arrow") or {}).get("sha256"),
                                "bytes": (dataset.get("arrow") or {}).get("bytes"),
                            }
                            if dataset.get("arrow")
                            else None
                        ),
                    }
                    for dataset in chart.get("vega_lite_datasets") or []
                ],
                "fields": chart.get("vega_lite_fields"),
            }
        return described

    stages = [{"stage": "after-upload", "dom": digest, **describe(seen)}]

    for case in DATA_LOOP_CASES if args.file_action == "none" else ():
        before_frames = len(seen)
        dom_before = page.result_digest()
        action = act(page, case)
        time.sleep(4)
        seen = frames_of(recorder)
        window = {
            "click": f'{case["kind"]}-{case["label"]}',
            "target": recorder.label,
            "start": before_frames,
            "end": len(seen),
            "widget": None,
        }
        # The widget id belongs to the control that was changed; the table
        # carries no id of its own.
        for frame in seen[before_frames:]:
            delta = (frame.get("decoded") or {}).get("delta") or {}
            if delta.get("type") != "new_element":
                continue
            payload = delta.get("element_full") or {}
            inner = payload.get(delta.get("element")) or {}
            if isinstance(inner, dict) and inner.get("label") == case["label"]:
                window["widget"] = inner.get("id")
                break
        dom_after = page.result_digest()
        tooltip = page.chart_tooltip()
        if dom_after is not None and tooltip:
            dom_after["chart_tooltip"] = tooltip
        verdict = data_loop_verdict(case, seen, window, action, dom_before, dom_after)
        stages.append({
            "stage": case["label"],
            "action": action,
            "window": window,
            "verdict": verdict,
            "dom": dom_after,
            **describe(seen[before_frames:]),
        })

    frames = seen
    arrow_file_list = [
        {"file": name, "sha256": digest} for digest, name in arrow_files.items()
    ]

    file_state = None
    for frame in frames:
        decoded = frame.get("decoded") or {}
        if decoded.get("type") != "rerun_script":
            continue
        for state in decoded.get("rerun_script", {}).get("widget_states", []) or []:
            if "file_uploader" in (state.get("value_field") or ""):
                file_state = state
    file_urls_request = [
        (frame.get("decoded") or {}).get("file_urls_request")
        for frame in frames
        if (frame.get("decoded") or {}).get("file_urls_request")
    ]
    file_urls_response = [
        (frame.get("decoded") or {}).get("file_urls_response")
        for frame in frames
        if (frame.get("decoded") or {}).get("file_urls_response")
    ]
    uploads = [
        request
        for request in http_requests
        if "upload_file" in (request.get("url") or "")
    ]

    required = [case["label"] for case in DATA_LOOP_CASES] if args.file_action == "none" else []
    result = data_loop_result(stages, upload, file_action, required)

    trace = {
        "schema_version": 1,
        "contract_id": "C-P0-04",
        "kind": "python-reference-data-loop-trace",
        "scope": "PYTHON SIDE ONLY. The Rust implementation is not exercised by this file.",
        "capture": {
            "tool": "DevTools Protocol against the same real Chrome",
            "tool_limitation": "the agent-browser CLI could not start its daemon in this "
                               "environment (connection timeout), so the input is sent over CDP",
            "input_events": "DOM.setFileInputFiles (the browser uploads the file itself)",
            "driver": "tests/browser/numeric_capture.py",
            "binary": args.binary,
        },
        "url": args.url,
        "case": "data-loop",
        "upload": upload,
        "file_action": file_action,
        "result": digest,
        "stages": stages,
        "arrow_files": arrow_file_list,
        "file_uploader_state": file_state,
        "file_urls_request": file_urls_request,
        "file_urls_response": file_urls_response,
        "http_requests": http_requests,
        "upload_requests": uploads,
        "static_bundle_requests_counted_not_stored": static_count,
        "frames": frames,
        "counts": result["counts"],
        "failures": result["failures"],
    }
    (out / "trace-data-loop.json").write_text(
        json.dumps(trace, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print("wrote", out / "trace-data-loop.json")
    print("upload:", json.dumps(upload))
    print("file action:", json.dumps(file_action))
    print("file uploader state:", json.dumps(file_state))
    print("delete requests:", json.dumps([
        {"method": r.get("method"), "url": (r.get("url") or "").split("/")[-1], "status": r.get("status")}
        for r in http_requests if r.get("method") == "DELETE"
    ]))
    print("table cells:", json.dumps((digest or {}).get("table_cells")))
    print("chart labels:", json.dumps((digest or {}).get("chart_labels")))
    print("file_urls_request:", json.dumps(file_urls_request))
    print("file_urls_response:", json.dumps(file_urls_response))
    print("upload requests:", json.dumps([{k: r.get(k) for k in ("method", "url", "status")} for r in uploads]))
    print("arrow files:", json.dumps(arrow_file_list))
    print("counts:", json.dumps(result["counts"]))
    print("failures:", json.dumps(result["failures"]))
    for stage in stages:
        print("  stage", stage["stage"], "->", json.dumps(stage.get("verdict", {}).get("ok")),
              json.dumps(stage.get("verdict", {}).get("problems", []))[:160])
    return 0 if result["ok"] else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    parser.add_argument("--label", default="numeric")
    parser.add_argument("--out", default="")
    parser.add_argument("--port", type=int, default=CHROME_PORT)
    parser.add_argument("--binary", default="")
    parser.add_argument("--scope", default="PYTHON SIDE ONLY")
    parser.add_argument("--kind", default="python-reference-widget-trace")
    parser.add_argument("--suite", choices=sorted(SUITES), default="python-numeric")
    parser.add_argument("--only", choices=("core", "numeric", "all"), default="all")
    parser.add_argument("--case", choices=("numeric", "data-loop"), default="numeric")
    parser.add_argument("--files", default="", help="comma separated files to upload")
    parser.add_argument(
        "--file-action",
        choices=("none", "delete", "replace"),
        default="none",
        help="what to do with the uploaded file: nothing, remove it, or upload another one",
    )
    parser.add_argument("--fixture", default="", help="the CSV to upload in the data loop case")
    parser.add_argument("--keep-changes", action="store_true",
                        help="keep the control changes in the data loop case")
    args = parser.parse_args()

    out = pathlib.Path(args.out or f"target/numeric-{args.label}")
    out.mkdir(parents=True, exist_ok=True)

    version = http_json(f"http://127.0.0.1:{args.port}/json/version")
    # The tab is opened for this capture and the recorder is bound to that
    # tab, so a session that still carries values from an earlier run is
    # never driven again.
    created = http_json(f"http://127.0.0.1:{args.port}/json/new?{args.url}", method="PUT")
    created_id = created.get("id")
    deadline = time.time() + 45
    tab = None
    while time.time() < deadline and tab is None:
        listing = http_json(f"http://127.0.0.1:{args.port}/json/list")
        for candidate in listing:
            if candidate.get("id") != created_id:
                continue
            if (candidate.get("title") or "").strip() not in ("", "New Tab"):
                tab = candidate
                break
        time.sleep(2)
    if tab is None:
        raise SystemExit("the new tab for " + args.url + " never settled")

    recorder = CDP(tab["webSocketDebuggerUrl"], label=args.label)
    recorder.start()
    page = Page(recorder)
    time.sleep(3)

    if args.case == "data-loop":
        return run_data_loop(page, recorder, args, out)

    suite = SUITES[args.suite]
    cases = list(suite["cases"])
    required = list(suite["required"])

    seen = frames_of(recorder)
    widgets = {}
    windows = []
    interactions = []
    for case in cases:
        label = case["label"]
        widget_id = None
        for frame in seen:
            decoded = frame["decoded"]
            if decoded.get("type") != "delta":
                continue
            delta = decoded.get("delta", {})
            if delta.get("type") != "new_element":
                continue
            payload = delta.get("element_full") or delta.get("widget") or {}
            inner = payload.get(delta["element"]) or payload
            if isinstance(inner, dict) and inner.get("label") == label:
                widget_id = inner.get("id")
                widgets[f'{delta["element"]}|{label}'] = payload
        before_frames = len(seen)
        kind = case["kind"]
        shown_before = dom_value_for(
            page.evaluate(WIDGET_DOM_JS).get("markdown"), label
        )
        if kind == "slider":
            if page.focus_slider(label, case.get("thumb", 0)):
                for _ in range(case.get("times", 1)):
                    page.press(case.get("key", "ArrowRight"), case.get("key", "ArrowRight"), 39)
                    time.sleep(0.5)
                action = {"action": "press", "key": case.get("key", "ArrowRight")}
            else:
                action = {"action": "press", "failed": "no range input"}
        elif kind == "checkbox":
            if page.focus_checkbox(label):
                page.press(" ", "Space", 32)
                action = {"action": "press-Space"}
            else:
                action = {"action": "press-Space", "failed": "no checkbox input"}
        else:
            opened = page.open_selectbox(label)
            rect = None
            for _ in range(6):
                time.sleep(1.0)
                rect = page.option_rect(case.get("option", "region"))
                if rect:
                    break
            if rect:
                page.click(rect["x"], rect["y"])
                action = {"action": "select-option", "option": case.get("option", "region")}
            else:
                action = {"action": "select-option", "failed": "no option", "opened": opened}
        time.sleep(4)
        after = frames_of(recorder)
        new_frames = after[before_frames:]
        seen = after
        if widget_id is None:
            for frame in new_frames:
                decoded = frame["decoded"]
                if decoded.get("type") != "delta":
                    continue
                delta = decoded.get("delta", {})
                if delta.get("type") != "new_element":
                    continue
                payload = delta.get("element_full") or delta.get("widget") or {}
                inner = payload.get(delta["element"]) or payload
                if isinstance(inner, dict) and inner.get("label") == label:
                    widget_id = inner.get("id")
                    widgets[f'{delta["element"]}|{label}'] = payload
        if widget_id is None:
            # The page does not carry this widget: that is not a failure, it
            # is a case the page does not have.
            interactions.append({
                "widget": kind,
                "label": label,
                "widget_id": None,
                "action": action,
                "skipped": True,
                "ok": False,
                "reason": "no such widget on this page",
            })
            continue
        dom_after = page.evaluate(WIDGET_DOM_JS)
        shown_after = dom_value_for(dom_after.get("markdown"), label)
        window = {
            "click": f"{kind}-{label}",
            "target": recorder.label,
            "start": before_frames,
            "end": len(seen),
            "widget": widget_id,
        }
        windows.append(window)
        verdict = case_verdict(
            case, seen, window, action, shown_before, shown_after
        )
        interactions.append({
            "widget": kind,
            "label": label,
            "widget_id": widget_id,
            "action": action,
            "wire_value": verdict["wire_value"],
            "value_before": verdict["before_value"],
            "page_shows": shown_after,
            "page_shows_before": shown_before,
            "connection": verdict["connection"],
            "state_frame": verdict["state_frame"],
            "completion_frame": verdict["completion_frame"],
            "ok": verdict["ok"],
            "problems": verdict["problems"],
            "value_matches_the_page": verdict["ok"],
        })

    all_frames = seen
    dom_after = page.evaluate(WIDGET_DOM_JS)
    recorder.stop()

    failures = verify_click_windows(all_frames, windows)
    failures.extend(suite_failures(required, interactions))
    counts = suite_counts(required, interactions)

    trace = {
        "schema_version": 1,
        "contract_id": "C-P0-04",
        "kind": args.kind,
        "scope": args.scope,
        "capture": {
            "tool": "DevTools Protocol against the same real Chrome",
            "tool_limitation": "the agent-browser CLI could not start its daemon in this "
                               "environment (connection timeout), so the input is sent over CDP",
            "chrome": version.get("Browser"),
            "chrome_cdp_port": args.port,
            "input_events": "Input.dispatchMouseEvent / Input.dispatchKeyEvent (real UI events)",
            "driver": "tests/browser/numeric_capture.py",
            "binary": args.binary,
        },
        "url": args.url,
        "wire_widgets": widgets,
        "suite": args.suite,
        "required_cases": required,
        "counts": counts,
        "interactions": interactions,
        "dom_after": dom_after,
        "frames": all_frames,
        "failures": failures,
    }
    (out / "trace-widgets.json").write_text(
        json.dumps(trace, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print("wrote", out / "trace-widgets.json")
    for item in interactions:
        if item.get("skipped"):
            print(f"  {item['label']}: skipped ({item.get('reason')})")
            continue
        print(f"  {item['label']}: wire={json.dumps(item.get('wire_value'))} "
              f"page={json.dumps(item.get('page_shows'))} match={item.get('value_matches_the_page')}")
    print("suite", args.suite, "counts:", json.dumps(counts))
    print("failures:", json.dumps(failures))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
