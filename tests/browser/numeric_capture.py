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
import re
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
    empty_checks,
    http_requests_from_events,
    recover_checks,
    require_decoder,
    sessions_checks,
    journey_result,
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

    def bring_to_front(self) -> None:
        """Make this tab the visible one.

        A hidden tab renders its table grid late or not at all, so a capture
        that reads a second tab has to show it first.
        """
        self.cdp.call("Page.bringToFront", {})

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
        """Hand files to the file input, the way the browser does it.

        The paths are resolved first: Chrome resolves them against its own
        working directory, so a relative path hands the uploader nothing.
        The page then never reruns, the frame window stays empty and the DOM
        read times out -- a broken capture that looks like an empty page.
        """
        if isinstance(paths, str):
            paths = [paths]
        resolved = []
        for path in paths:
            full = pathlib.Path(path).resolve()
            if not full.is_file():
                raise SystemExit(f"the file to upload does not exist: {path}")
            resolved.append(str(full))
        document = self.cdp.call("DOM.getDocument", {"depth": 0})
        root = (document.get("result", {}) or {}).get("root", {}) or {}
        node = self.cdp.call(
            "DOM.querySelector",
            {"nodeId": root.get("nodeId"), "selector": "[data-testid='stFileUploaderDropzoneInput']"},
        )
        node_id = (node.get("result", {}) or {}).get("nodeId")
        if not node_id:
            return False
        self.cdp.call("DOM.setFileInputFiles", {"files": resolved, "nodeId": node_id})
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

    def page_alerts(self):
        """The alerts and the exceptions the page shows."""
        value = self.evaluate(
            "JSON.stringify({alerts:[...document.querySelectorAll('[data-testid^=stAlertContent]')]"
            ".map(e=>e.innerText.replace(/\\s+/g,' ').trim()),"
            "exceptions:[...document.querySelectorAll('[data-testid=stException]')]"
            ".map(e=>e.innerText.replace(/\\s+/g,' ').trim().slice(0,300))})"
        )
        return value if isinstance(value, dict) else {"alerts": [], "exceptions": []}

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

    def state_digest(self):
        """The rendered page: the result and the controls, in one digest.

        The result comes from the result probe and the controls from the
        widget probe; the criterion compares both against the wire.
        """
        result = self.evaluate(OBSERVE_JS)
        controls = self.evaluate(WIDGET_DOM_JS)
        if not isinstance(result, dict) or not isinstance(controls, dict):
            return None
        merged = dict(result)
        merged.update(controls)
        return merged

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


def frames_of(recorder, namespace: str = ""):
    """The recorded frames, each with the connection it travelled on.

    The connection is the DevTools request id of the socket, mapped to the
    order the sockets were seen.  A frame that carries no request id keeps
    no connection: it may never be counted as the same connection as
    another frame.  The namespace names the tab a frame belongs to, so the
    frames of two tabs never look like the frames of one.
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
            "timestamp": event["params"].get("timestamp"),
            "namespace": namespace,
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

    seen = frames_of(recorder, namespace=recorder.label)
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
        seen = frames_of(recorder, namespace=recorder.label)
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
        "kind": trace_kind(args.scope),
        "scope": args.scope,
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



def _wait_for(predicate, timeout: float = 60.0, step: float = 1.0):
    """Wait until the predicate holds, and return the last value it saw."""
    import time as _time

    deadline = _time.time() + timeout
    value = None
    while _time.time() < deadline:
        value = predicate()
        if value:
            return value
        _time.sleep(step)
    return value


def _frames_since(recorder, start: int):
    frames = frames_of(recorder, namespace=recorder.label)
    return frames[start:]



def trace_kind(scope: str) -> str:
    """The kind of the trace, from the side that was captured."""
    return ("rust-browser-data-loop-trace" if "RUST" in scope.upper()
            else "python-reference-browser-trace")



class _ArrowFiles:
    """The IPC payloads of a capture: one file per digest.

    The bytes are kept as they came off the wire, so a reviewer can read the
    Arrow stream itself and not only the summary of it.
    """

    def __init__(self, out: pathlib.Path):
        self.out = out
        self.by_digest: dict[str, str] = {}

    def keep(self, arrow) -> dict | None:
        """The summary of one payload, with its bytes in a file."""
        if not arrow:
            return None
        digest = arrow.get("sha256")
        if arrow.get("base64") and digest not in self.by_digest:
            raw = base64.b64decode(arrow["base64"])
            name = f"arrow-{len(self.by_digest) + 1}.bin"
            (self.out / name).write_bytes(raw)
            self.by_digest[digest] = name
        info = {"sha256": digest, "bytes": arrow.get("bytes")}
        if digest in self.by_digest:
            info["file"] = self.by_digest[digest]
        for key in ("schema", "columns", "row_count", "rows"):
            if arrow.get(key) is not None:
                info[key] = arrow[key]
        return info


def _completions(frames) -> list[dict]:
    """The script completions inside these frames, with their connection."""
    out = []
    for index, frame in enumerate(frames):
        decoded = frame.get("decoded") or {}
        if decoded.get("type") != "script_finished":
            continue
        finished = decoded.get("script_finished") or {}
        out.append({
            "frame": index,
            "connection": frame.get("connection"),
            "request_id": frame.get("request_id"),
            "status": finished.get("status"),
            "status_name": finished.get("status_name"),
        })
    return out


def _client_states(frames) -> list[dict]:
    """The widget states the client sent inside these frames."""
    states = []
    for frame in frames:
        decoded = frame.get("decoded") or {}
        if decoded.get("type") != "rerun_script":
            continue
        for state in (decoded.get("rerun_script") or {}).get("widget_states", []) or []:
            states.append({
                "id": state.get("id"),
                "value_field": state.get("value_field"),
                "value": state.get("value"),
            })
    return states


def _issued_file_urls(frames) -> list[dict]:
    """The upload and delete URLs the server signed out."""
    issued = []
    for frame in frames:
        decoded = frame.get("decoded") or {}
        if decoded.get("type") != "file_urls_response":
            continue
        response = decoded.get("file_urls_response") or {}
        for item in response.get("file_urls") or []:
            issued.append({
                "response_id": response.get("response_id"),
                "file_id": item.get("file_id"),
                "upload_url": item.get("upload_url"),
                "delete_url": item.get("delete_url"),
                "error_msg": response.get("error_msg"),
            })
    return issued


def _http_timeline(recorder) -> list[dict]:
    """The HTTP requests of a recorder: method, URL, status and moment.

    The moment is what binds a request to the window of frames that the
    action caused; the request id pairs the request with its answer.
    """
    requests: list[dict] = []
    by_id: dict[str, dict] = {}
    for event in recorder.take():
        params = event.get("params", {})
        if event.get("method") == "Network.requestWillBeSent":
            request = params.get("request", {})
            url = request.get("url", "")
            if "/static/" in url:
                continue
            entry = {
                "method": request.get("method"),
                "url": url,
                "request_id": params.get("requestId"),
                "timestamp": params.get("timestamp"),
                "status": None,
                "response_timestamp": None,
                "request_headers": {
                    key: value
                    for key, value in (request.get("headers") or {}).items()
                    if key.lower() in ("content-type", "content-length", "origin")
                },
            }
            requests.append(entry)
            if entry["request_id"]:
                by_id[entry["request_id"]] = entry
        elif event.get("method") == "Network.responseReceived":
            response = params.get("response", {}) or {}
            entry = by_id.get(params.get("requestId"))
            if entry is not None and entry.get("status") is None:
                entry["status"] = response.get("status")
                entry["response_timestamp"] = params.get("timestamp")
    return requests


def _url_path(url: str) -> str:
    """The path of a URL, without the scheme and the host."""
    without_scheme = str(url).split("://", 1)[-1]
    if "/" not in without_scheme:
        return "/"
    return "/" + without_scheme.split("/", 1)[1]


def _matches_issued(request, issued) -> bool:
    """Does this request answer a delete URL the server signed out?

    The URL of the server carries the session and the file, so a delete of
    something else cannot pass for it.
    """
    path = _url_path(request.get("url", ""))
    for item in issued or []:
        delete_url = item.get("delete_url") or ""
        if delete_url and _url_path(delete_url) == path:
            return True
    return False


def _in_window(request, phase) -> bool:
    """Did this request happen while the action was running?"""
    start = phase.get("start_timestamp")
    end = phase.get("end_timestamp")
    stamp = request.get("timestamp")
    if stamp is None or start is None or end is None:
        return False
    return start <= stamp <= end


def _phase(name, action, frames, start, end, dom_before, dom_after, arrow_files) -> dict:
    """One action of a journey and what it caused.

    The phase names the range of frames the action produced; the raw keeps
    the frames once.  It carries the states the client sent, the completion
    that answered the action and the IPC the server sent, so a criterion can
    bind the result to the action that produced it.
    """
    window = frames[start:end]
    table, chart = stage_elements(window)
    return {
        "name": name,
        "action": action,
        "start": start,
        "end": end,
        "start_timestamp": window[0].get("timestamp") if window else None,
        "end_timestamp": window[-1].get("timestamp") if window else None,
        "dom_before": dom_before,
        "dom_after": dom_after,
        "client_states": _client_states(window),
        "completions": _completions(window),
        "ipc": {
            "table": {
                "arrow": arrow_files.keep(table.get("arrow")),
                "arrow_fields": table.get("arrow_fields"),
            } if table else None,
            "chart": {
                "vega_lite_spec": chart.get("vega_lite_spec"),
                "arrow": arrow_files.keep(chart.get("arrow")),
                # The chart carries its data in the named datasets; the
                # element itself has none.
                "datasets": [
                    {
                        "name": dataset.get("name"),
                        "has_name": dataset.get("has_name"),
                        "arrow": arrow_files.keep(dataset.get("arrow")),
                    }
                    for dataset in (chart.get("vega_lite_datasets") or [])
                ],
            } if chart else None,
        },
    }


def _write_trace(path, trace) -> None:
    """Write the trace of a journey.

    The evidence is written before the criteria run, so a criterion that
    raises still leaves the capture it judged on the disk.
    """
    path.write_text(json.dumps(trace, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _event_window(events, window_frames):
    """The events of the recorder that the action caused.

    The frames of the action carry the request id and the moment; the HTTP
    events of the same action sit between them in the event list.
    """
    if not window_frames:
        return 0, len(events)

    def matches(event, frame):
        params = event.get("params", {})
        return (
            str(event.get("method", "")).startswith("Network.webSocketFrame")
            and params.get("requestId") == frame.get("request_id")
            and params.get("timestamp") == frame.get("timestamp")
        )

    start, end = 0, len(events)
    for index, event in enumerate(events):
        if matches(event, window_frames[0]):
            start = index
            break
    for index, event in enumerate(events):
        if matches(event, window_frames[-1]):
            end = index + 1
            break
    return start, end


def _state_id(frames, start, end, value_field):
    """The id of the widget whose state the client sent in this window."""
    for index in range(start, end):
        frame = frames[index]
        decoded = frame.get("decoded") or {}
        if decoded.get("type") != "rerun_script":
            continue
        for state in (decoded.get("rerun_script") or {}).get("widget_states", []) or []:
            if state.get("value_field") == value_field:
                return state.get("id")
    return None


def _bundle(source, frames, events, url, fixture, upload_window, upload_action,
            window, action, dom_before, ipc_files, ipc_dir):
    """The evidence of one operation, as the shared criterion reads it.

    It holds the frames of the tab, the window the action happened in, the
    events of the same moment and the IPC that was kept.  Every value comes
    from the capture; nothing here is filled in by hand.
    """
    return {
        "source": source,
        "url": url,
        "fixture": str(pathlib.Path(fixture).resolve()),
        "frames": frames,
        "events": events,
        "window": window,
        "upload_window": upload_window,
        "action": action,
        "upload_action": upload_action,
        "dom_before": dom_before,
        "ipc_files": ipc_files,
        "ipc_dir": str(ipc_dir),
    }


def run_recover_journey(page, recorder, args, out):
    """Upload a file the app cannot read, then replace it with a good one."""
    paths = [path for path in (args.files.split(",") if args.files else [args.fixture]) if path]
    out.mkdir(parents=True, exist_ok=True)

    bad, good = (paths + [None, None])[:2]
    if not (bad and good):
        raise SystemExit("the recover journey needs two files")

    arrow_files = _ArrowFiles(out)
    namespace = recorder.label

    dom_before_bad = page.state_digest()
    start_bad = len(frames_of(recorder, namespace=recorder.label))
    uploaded_bad = page.upload(bad)
    time.sleep(8)
    frames = frames_of(recorder, namespace=recorder.label)
    dom_bad = page.state_digest()
    alerts_bad = page.page_alerts()

    start_good = len(frames)
    dom_before_good = page.state_digest()
    uploaded_good = page.upload(good)
    time.sleep(8)
    frames = frames_of(recorder, namespace=recorder.label)
    dom_good = page.state_digest()
    alerts_good = page.page_alerts()
    chips = page.files_dom()

    phase_bad = _phase(
        "upload-the-file-the-app-cannot-read",
        {"action": "upload", "ok": bool(uploaded_bad), "file": str(pathlib.Path(bad).resolve())},
        frames, start_bad, start_good, dom_before_bad, dom_bad, arrow_files,
    )
    phase_good = _phase(
        "replace-it-with-a-good-file",
        {"action": "upload", "ok": bool(uploaded_good), "file": str(pathlib.Path(good).resolve())},
        frames, start_good, len(frames), dom_before_good, dom_good, arrow_files,
    )

    window = {"start": start_good, "end": len(frames)}
    verdict = data_loop_verdict(
        {"kind": "file_uploader", "label": "Upload sales CSV"},
        frames, window, {"action": "upload"}, dom_before_good, dom_good,
    )

    http_requests = http_requests_from_events(recorder.take())[0]
    timeline = _http_timeline(recorder)
    issued = _issued_file_urls(frames)
    delete_requests = [
        {
            **request,
            "matches_issued_file": _matches_issued(request, issued),
        }
        for request in timeline
        if request.get("method") == "DELETE"
    ]
    observation = {
        "journey": "recover",
        "namespace": namespace,
        "url": args.url,
        "ipc_dir": str(out),
        "uploads": {"bad": bool(uploaded_bad), "good": bool(uploaded_good)},
        "frames": frames,
        "phases": [phase_bad, phase_good],
        "http_timeline": timeline,
        "alerts": {"after_bad": alerts_bad, "after_good": alerts_good},
        "dom": {"after_bad": dom_bad, "after_good": dom_good},
        "chips": chips,
        "verdict": verdict,
        "file_urls": {"issued": issued},
        "delete_requests": delete_requests,
    }

    trace = {
        "schema_version": 1,
        "contract_id": "C-P0-04",
        "kind": trace_kind(args.scope),
        "scope": args.scope,
                "capture": {
            "tool": "DevTools Protocol against the same real Chrome",
            "tool_limitation": "the agent-browser CLI could not start its daemon in this "
                               "environment (connection timeout), so the input is sent over CDP",
            "driver": "tests/browser/numeric_capture.py",
            "binary": args.binary,
            "python": sys.executable,
        },
        "url": args.url,
        "case": "recover",
        "journey": "recover",
        "bad_file": bad,
        "good_file": good,
        "observation": observation,
        "checks": [],
        "counts": {"expected": 0, "executed": 0, "asserted": 0},
        "failures": [],
    }
    trace_path = out / "trace-data-loop.json"
    _write_trace(trace_path, trace)
    checks = recover_checks(
        alerts_bad, dom_bad, verdict, delete_requests, chips,
        (uploaded_bad, uploaded_good), frames[start_good:], pathlib.Path(good).name,
        observation=observation,
    )
    result = journey_result(checks)
    trace["checks"] = checks
    trace["counts"] = result["counts"]
    trace["failures"] = result["failures"]
    _write_trace(trace_path, trace)
    print("wrote", trace_path)
    print("counts:", json.dumps(result["counts"]))
    print("alerts after the bad file:", json.dumps(alerts_bad.get("alerts")))
    print("alerts after the good file:", json.dumps(alerts_good.get("alerts")))
    print("delete requests:", json.dumps([
        {"status": r.get("status"), "matches_issued_file": r.get("matches_issued_file")}
        for r in delete_requests
    ]))
    print("failures:", json.dumps(result["failures"]))
    return 1 if result["failures"] else 0


def _http_json(url: str, method: str = "GET"):
    import urllib.request

    req = urllib.request.Request(url, method=method)
    with urllib.request.urlopen(req, timeout=15) as response:
        return json.loads(response.read().decode("utf-8"))


def run_empty_journey(page, recorder, args, out):
    """Upload a file without data rows: the result is empty and nothing is stale."""
    out.mkdir(parents=True, exist_ok=True)
    path = args.fixture or (args.files.split(",")[0] if args.files else "")
    if not path:
        raise SystemExit("the empty journey needs a file")

    arrow_files = _ArrowFiles(out)
    namespace = recorder.label

    dom_before = page.state_digest()
    start = len(frames_of(recorder, namespace=recorder.label))
    uploaded = page.upload(path)
    time.sleep(8)
    frames = frames_of(recorder, namespace=recorder.label)
    dom = page.state_digest()
    alerts = page.page_alerts()

    phase = _phase(
        "upload-a-file-without-data-rows",
        {"action": "upload", "ok": bool(uploaded), "file": str(pathlib.Path(path).resolve())},
        frames, start, len(frames), dom_before, dom, arrow_files,
    )
    table, chart = stage_elements(frames[start:])
    rows = (table or {}).get("arrow", {}).get("rows")
    schema = (table or {}).get("arrow", {}).get("schema") or ""
    columns = (table or {}).get("arrow", {}).get("columns") or []
    observation = {
        "journey": "empty",
        "namespace": namespace,
        "url": args.url,
        "ipc_dir": str(out),
        "uploads": {"file": bool(uploaded)},
        "frames": frames,
        "phases": [phase],
        "http_timeline": _http_timeline(recorder),
        "alerts": {"after_upload": alerts},
        "dom": {"after_upload": dom},
        "table": {
            "rows": rows,
            "columns": columns,
            "schema": schema,
            "arrow": arrow_files.keep((table or {}).get("arrow")),
            "arrow_fields": (table or {}).get("arrow_fields"),
        },
        "chart": {
            "vega_lite_spec": (chart or {}).get("vega_lite_spec"),
        } if chart else None,
    }

    trace = {
        "schema_version": 1,
        "contract_id": "C-P0-04",
        "kind": trace_kind(args.scope),
        "scope": args.scope,
                "capture": {
            "tool": "DevTools Protocol against the same real Chrome",
            "tool_limitation": "the agent-browser CLI could not start its daemon in this "
                               "environment (connection timeout), so the input is sent over CDP",
            "driver": "tests/browser/numeric_capture.py",
            "binary": args.binary,
            "python": sys.executable,
        },
        "url": args.url,
        "case": "empty",
        "journey": "empty",
        "file": path,
        "observation": observation,
        "checks": [],
        "counts": {"expected": 0, "executed": 0, "asserted": 0},
        "failures": [],
    }
    trace_path = out / "trace-data-loop.json"
    _write_trace(trace_path, trace)
    checks = empty_checks(alerts, rows, columns, dom, uploaded, observation=observation)
    result = journey_result(checks)
    trace["checks"] = checks
    trace["counts"] = result["counts"]
    trace["failures"] = result["failures"]
    _write_trace(trace_path, trace)
    print("wrote", trace_path)
    print("counts:", json.dumps(result["counts"]))
    print("alerts:", json.dumps(alerts.get("alerts")))
    print("rows:", json.dumps(rows), "| columns:", json.dumps(columns))
    print("schema:", schema)
    print("chart bars:", (dom or {}).get("chart_bars"), "| cells:", json.dumps((dom or {}).get("table_cells")))
    print("failures:", json.dumps(result["failures"]))
    return 1 if result["failures"] else 0


def _session_ids(recorder):
    """The session ids the server sent to this tab."""
    found = set()
    for event in recorder.take():
        if event.get("method") != "Network.webSocketFrameReceived":
            continue
        payload = event["params"].get("response", {})
        if payload.get("opcode") != 2:
            continue
        decoded = _safe(summarise_forward, base64.b64decode(payload.get("payloadData", "")))
        if decoded.get("type") == "new_session":
            session = (decoded.get("new_session") or {}).get("session_id")
            if session:
                found.add(session)
    return sorted(found)


def _uploaded_names(recorder):
    """The files the client told the server about."""
    names = []
    for event in recorder.take():
        if event.get("method") != "Network.webSocketFrameSent":
            continue
        payload = event["params"].get("response", {})
        if payload.get("opcode") != 2:
            continue
        decoded = _safe(summarise_back, base64.b64decode(payload.get("payloadData", "")))
        for state in (decoded.get("rerun_script") or {}).get("widget_states", []) or []:
            if "file_uploader" not in (state.get("value_field") or ""):
                continue
            text = str(state.get("value"))
            if 'name: "' in text:
                names.append(text.split('name: "', 1)[1].split('"', 1)[0])
    return names


def _control_values(recorder, label_fragment: str = "group_by"):
    """The values the client sent for one control."""
    values = []
    for event in recorder.take():
        if event.get("method") != "Network.webSocketFrameSent":
            continue
        payload = event["params"].get("response", {})
        if payload.get("opcode") != 2:
            continue
        decoded = _safe(summarise_back, base64.b64decode(payload.get("payloadData", "")))
        for state in (decoded.get("rerun_script") or {}).get("widget_states", []) or []:
            if label_fragment in (state.get("id") or "") and state.get("value_field") == "string_value":
                values.append(state.get("value"))
    return values


def _select_option(page, option: str) -> bool:
    """Choose an option in the selectbox, with a real click."""
    rect = page.evaluate(
        "(()=>{const b=document.querySelector(\"[data-testid='stSelectbox'] button[aria-label='Open']\");"
        "if(!b)return null;const r=b.getBoundingClientRect();"
        "return {x:r.x+r.width/2,y:r.y+r.height/2};})()"
    )
    if not isinstance(rect, dict):
        return False
    page.click(rect["x"], rect["y"])
    time.sleep(2)
    option_rect = page.evaluate(
        "(()=>{const o=[...document.querySelectorAll('[role=option]')]"
        ".find(x=>x.textContent.trim()===" + json.dumps(option) + ");"
        "if(!o)return null;const r=o.getBoundingClientRect();"
        "return {x:r.x+r.width/2,y:r.y+r.height/2};})()"
    )
    if not isinstance(option_rect, dict):
        return False
    page.click(option_rect["x"], option_rect["y"])
    time.sleep(6)
    return True


def _wait_for_cells(page, timeout: float = 25.0):
    """The rendered result, once the table has drawn its cells.

    The grid of a table is drawn by the frontend; a tab that was hidden
    while the app answered draws it late.  The wait is bounded, so a page
    that really has no table ends the wait with the empty digest.
    """
    deadline = time.time() + timeout
    digest = None
    while time.time() < deadline:
        digest = page.result_digest()
        if digest and digest.get("table_cells"):
            return digest
        time.sleep(1)
    return digest


def run_sessions_journey(page, recorder, args, out):
    """Two tabs, two sessions: each keeps its own file and its own controls."""
    out.mkdir(parents=True, exist_ok=True)
    paths = [path for path in (args.files.split(",") if args.files else [args.fixture]) if path]
    if len(paths) < 2:
        raise SystemExit("the sessions journey needs two files")

    created = _http_json(f"http://127.0.0.1:{args.port}/json/new?{args.url}", method="PUT")
    recorder_b = CDP(created["webSocketDebuggerUrl"], label="tab-b")
    recorder_b.start()
    page_b = Page(recorder_b)
    time.sleep(7)

    arrow_files = _ArrowFiles(out)

    # The first tab: its own file.
    page.bring_to_front()
    dom_a_before = page.state_digest()
    start_a = len(frames_of(recorder, namespace=recorder.label))
    uploaded_a = page.upload(paths[0])
    time.sleep(7)
    page.bring_to_front()
    dom_a_after_upload = page.state_digest()

    # The second tab: its own file, its own session.
    page_b.bring_to_front()
    dom_b_before = page_b.state_digest()
    start_b = len(frames_of(recorder_b))
    uploaded_b = page_b.upload(paths[1])
    time.sleep(7)
    page_b.bring_to_front()
    dom_b_after = page_b.state_digest()

    # The first tab: its own control, its own result.
    page.bring_to_front()
    dom_a_before_change = page.state_digest()
    start_a_change = len(frames_of(recorder, namespace=recorder.label))
    changed = _select_option(page, "region")
    time.sleep(4)
    page.bring_to_front()
    dom_a_after = page.state_digest()

    frames_a = frames_of(recorder, namespace=recorder.label)
    frames_b = frames_of(recorder_b, namespace=recorder_b.label)

    phase_a_upload = _phase(
        "upload-its-own-file",
        {"action": "upload", "ok": bool(uploaded_a), "file": str(pathlib.Path(paths[0]).resolve())},
        frames_a, start_a, start_a_change, dom_a_before, dom_a_after_upload, arrow_files,
    )
    phase_a_change = _phase(
        "change-the-group",
        {"action": "select-option", "ok": bool(changed), "changed": bool(changed), "option": "region"},
        frames_a, start_a_change, len(frames_a), dom_a_before_change, dom_a_after, arrow_files,
    )
    phase_b_upload = _phase(
        "upload-its-own-file",
        {"action": "upload", "ok": bool(uploaded_b), "file": str(pathlib.Path(paths[1]).resolve())},
        frames_b, start_b, len(frames_b), dom_b_before, dom_b_after, arrow_files,
    )

    sessions_a = _session_ids(recorder)
    sessions_b = _session_ids(recorder_b)
    names_a = _uploaded_names(recorder)
    names_b = _uploaded_names(recorder_b)
    groups_a = _control_values(recorder)
    groups_b = _control_values(recorder_b)

    observation = {
        "journey": "sessions",
        "url": args.url,
        "ipc_dir": str(out),
        "uploads": {"a": bool(uploaded_a), "b": bool(uploaded_b)},
        "tabs": {
            "a": {
                "namespace": recorder.label,
                "file": str(pathlib.Path(paths[0]).resolve()),
                "session_ids": sessions_a,
                "uploaded": names_a,
                "group_values_sent": groups_a,
                "frames": frames_a,
                "phases": [phase_a_upload, phase_a_change],
                "http_timeline": _http_timeline(recorder),
                "dom": {
                    "before_upload": dom_a_before,
                    "after_upload": dom_a_after_upload,
                    "before_group_change": dom_a_before_change,
                    "after_group_change": dom_a_after,
                },
            },
            "b": {
                "namespace": recorder_b.label,
                "file": str(pathlib.Path(paths[1]).resolve()),
                "session_ids": sessions_b,
                "uploaded": names_b,
                "group_values_sent": groups_b,
                "frames": frames_b,
                "phases": [phase_b_upload],
                "http_timeline": _http_timeline(recorder_b),
                "dom": {"before_upload": dom_b_before, "after_upload": dom_b_after},
            },
        },
    }

    trace = {
        "schema_version": 1,
        "contract_id": "C-P0-04",
        "kind": trace_kind(args.scope),
        "scope": args.scope,
                "capture": {
            "tool": "DevTools Protocol against the same real Chrome",
            "tool_limitation": "the agent-browser CLI could not start its daemon in this "
                               "environment (connection timeout), so the input is sent over CDP",
            "driver": "tests/browser/numeric_capture.py",
            "binary": args.binary,
            "python": sys.executable,
        },
        "url": args.url,
        "case": "sessions",
        "journey": "sessions",
        "observation": observation,
        "checks": [],
        "counts": {"expected": 0, "executed": 0, "asserted": 0},
        "failures": [],
    }
    trace_path = out / "trace-data-loop.json"
    _write_trace(trace_path, trace)
    checks = sessions_checks(
        sessions_a, sessions_b, names_a, names_b, groups_a, groups_b,
        dom_a_after, dom_b_after, uploaded_a, uploaded_b,
        observation=observation,
    )
    result = journey_result(checks)
    trace["checks"] = checks
    trace["counts"] = result["counts"]
    trace["failures"] = result["failures"]
    _write_trace(trace_path, trace)
    recorder_b.stop()
    print("wrote", trace_path)
    print("counts:", json.dumps(result["counts"]))
    print("tab a session:", json.dumps(sessions_a), "| tab b session:", json.dumps(sessions_b))
    print("failures:", json.dumps(result["failures"]))
    return 1 if result["failures"] else 0


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
        "--journey",
        choices=("basic", "recover", "empty", "sessions"),
        default="basic",
        help="which journey of the data app to capture",
    )
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
    require_decoder()

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
        if args.journey == "recover":
            return run_recover_journey(page, recorder, args, out)
        if args.journey == "empty":
            return run_empty_journey(page, recorder, args, out)
        if args.journey == "sessions":
            return run_sessions_journey(page, recorder, args, out)
        return run_data_loop(page, recorder, args, out)

    suite = SUITES[args.suite]
    cases = list(suite["cases"])
    required = list(suite["required"])

    seen = frames_of(recorder, namespace=recorder.label)
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
        after = frames_of(recorder, namespace=recorder.label)
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
