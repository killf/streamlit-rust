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
import hashlib
import json
import pathlib
import re
import subprocess
import sys
import time
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests" / "reference"))

from capture_browser_trace import (  # noqa: E402
    J01_CASE, J01_CONTRACT, J01_PHASES, J01_INPUTS, J01_ACTIONS, J01_PNG_ROLES, j01_checks,
    J03_CASE, J03_CONTRACT, J03_PHASES, J03_INPUTS, J03_ACTIONS, J03_PNG_ROLES, j03_checks,
    J02_CASE, J02_CONTRACT, J02_PHASES, J02_INPUTS, J02_ACTIONS, J02_PNG_ROLES, j02_checks,
    J00_CASE, J00_CONTRACT, J00_PHASES, J00_INPUTS, J00_ACTIONS, J00_PNG_ROLES, j00_checks,
)

from capture_browser_trace import (  # noqa: E402
    OBSERVE_JS,
    SUITES,
    case_verdict,
    data_loop_verdict,
    empty_checks,
    http_requests_from_events,
    recover_checks,
    canonical_stage2_case,
    filter_empty_checks,
    non_utf8_checks,
    screenshot_checks,
    soft_invalid_checks,
    state_checks,
    STAGE2_SCREENSHOTS,
    require_decoder,
    sessions_checks,
    journey_result,
    suite_counts,
    suite_failures,
    WIDGET_DOM_JS,
    CDP,
    _decode_payload,
    _safe,
    _stage2_target_upload_run,
    dom_value_for,
    summarise_back,
    summarise_forward,
    verify_click_windows,
    widget_value_matches,
    wire_value_of,
)

try:  # the contract of a whole journey, from the shared harness
    from capture_browser_trace import (  # noqa: E402
        SEQUENCE_CONTRACT,
        SEQUENCE_INPUTS,
        SEQUENCE_PNG_ROLES,
        SEQUENCE_PHASES,
        sequence_checks,
    )
except ImportError:  # the closed door: the case fails, it never passes by itself
    SEQUENCE_CONTRACT = "journey-sequence-v1"
    SEQUENCE_INPUTS = {}
    SEQUENCE_PNG_ROLES = {}
    SEQUENCE_PHASES = {}
    sequence_checks = None

CHROME_PORT = 60667

# J00 presence/membership only; form interaction belongs to the forms collector.
J00_FORM_DOM_JS = r"""(()=>{
const qa=(selector,root=document)=>[...root.querySelectorAll(selector)];
const forms=qa("[data-testid='stForm']");
const text=e=>(e?.innerText||e?.textContent||'').replace(/\s+/g,' ').trim();
const membership=(e,selector)=>forms.findIndex(f=>qa(selector,f).includes(e));
const inputs=qa("[data-testid='stTextInput']").map(e=>({
 label:text(e.querySelector('label')),value:e.querySelector('input')?.value??null,
 form_index:membership(e,"[data-testid='stTextInput']")}));
const buttons=[...qa("[data-testid='stButton']"),...qa("[data-testid='stFormSubmitButton']")].map(e=>({
 label:text(e),testid:e.getAttribute('data-testid'),
 form_index:membership(e,"[data-testid='"+e.getAttribute('data-testid')+"']")}));
return JSON.stringify({text_inputs:inputs,buttons:buttons,forms:forms.map((f,index)=>({
 index,text_inputs:inputs.filter(e=>e.form_index===index),
 submit_buttons:buttons.filter(e=>e.form_index===index&&e.testid==='stFormSubmitButton')}))});})()"""


# The names of the journeys.  The command line, the observation and the
# criterion of a journey use exactly these strings: the shared harness has
# one required set of checks per name, and the driver never spells a name
# of its own.
JOURNEYS = (
    "basic",
    "recover",
    "empty",
    "sessions",
    "soft-invalid",
    "non-utf8",
    "filter-empty",
    "state",
    "j07-sequence",
    "j08-sequence",
    J01_CASE,
    J03_CASE,
    J02_CASE,
    J00_CASE,
)



# The phases of a whole journey, their order and their inputs are the shared
# harness's: the driver never spells a phase of its own.  The two files below
# are only how the driver drives the page -- how long it waits for the table
# and which key moves the slider.
SEQUENCE_SLIDER = {
    "slider-200": ("End", 35, 200),
    "slider-0": ("Home", 36, 0),
}
SEQUENCE_WITH_TABLE = {
    "upload-soft", "good-after-soft", "good-after-utf8", "upload-baseline", "slider-0",
}


def _sequence_plan(kind):
    """The steps of a whole journey, read from the shared contract."""
    if kind in (J00_CASE, J01_CASE, J02_CASE, J03_CASE):
        phases, inputs, actions = {
            J00_CASE: (J00_PHASES, J00_INPUTS, J00_ACTIONS),
            J01_CASE: (J01_PHASES, J01_INPUTS, J01_ACTIONS),
            J02_CASE: (J02_PHASES, J02_INPUTS, J02_ACTIONS),
            J03_CASE: (J03_PHASES, J03_INPUTS, J03_ACTIONS),
        }[kind]
        return [
            (name, dict(actions[name], **({"file": inputs[name]} if name in inputs else {})),
             name != "initial" and not (actions[name].get("action") == "slider" and actions[name].get("value") == 200),
             "%02d-%s.png" % (index + 1, name))
            for index, name in enumerate(phases)
        ]
    plan = []
    for index, name in enumerate(SEQUENCE_PHASES[kind]):
        if name == "initial":
            action = {"action": "initial"}
        elif name in SEQUENCE_INPUTS:
            action = {"action": "upload", "file": SEQUENCE_INPUTS[name]}
        else:
            key, code, value = SEQUENCE_SLIDER[name]
            action = {"action": "slider", "label": "Minimum amount", "key": key,
                      "code": code, "value": value}
        plan.append((name, action, name in SEQUENCE_WITH_TABLE,
                     "%02d-%s.png" % (index + 1, name)))
    return plan


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

    def click_visible(self, expression: str) -> bool:
        """Scroll an element into view and click it with a real mouse event.

        The rectangle is read after the scroll: a rectangle from before it
        points outside the viewport, so the click would land on nothing
        while looking like a click.  Nothing is clicked from the script --
        the page only gets a real mouse event at a place the user can see.
        """
        self.evaluate(
            "(()=>{const e=" + expression + ";if(!e)return false;"
            "e.scrollIntoView({block:'center'});return true;})()"
        )
        time.sleep(0.5)
        rect = self.rect(expression)
        if not rect:
            return False
        self.click(rect["x"], rect["y"])
        return True

    def screenshot(self, path, width: int = 1264, height: int = 1800):
        """Save a picture of the page and say how big it was.

        The viewport is made tall enough to hold the whole result -- the
        app scrolls inside its own container, so the document never grows --
        and the picture is taken from the real page.  Nothing in the page is
        changed for the picture.
        """
        self.cdp.call(
            "Emulation.setDeviceMetricsOverride",
            {"width": width, "height": height, "deviceScaleFactor": 1, "mobile": False},
        )
        try:
            time.sleep(1.0)
            data = self.cdp.call(
                "Page.captureScreenshot",
                {
                    "format": "png",
                    "captureBeyondViewport": True,
                    "clip": {"x": 0, "y": 0, "width": width, "height": height, "scale": 1},
                },
            )
            png = (data.get("result", {}) or {}).get("data")
            if not png:
                return None
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(base64.b64decode(png))
            return {
                "file": str(path),
                "bytes": path.stat().st_size,
                "viewport": [width, height],
            }
        finally:
            self.cdp.call("Emulation.clearDeviceMetricsOverride", {})

    def wait_for_render(self, timeout: float = 30.0, want_cells: bool = True):
        """Wait until the page has drawn its result and its counters.

        A field the page never showed stays missing; it is not filled in.
        """
        deadline = time.time() + timeout
        digest = None
        while time.time() < deadline:
            digest = self.state_digest()
            if digest and digest.get("script_runs") is not None:
                if not want_cells or digest.get("table_cells"):
                    return digest
            time.sleep(0.5)
        return digest

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

    def slider_pointer(self, label: str, value: float, timeout: float = 5.0):
        """One visible track click; read the actual native value and ARIA back."""
        group = ("[...document.querySelectorAll('[data-testid=stSlider] [role=group]')]"
                 ".find(e=>e.getAttribute('aria-label')===" + json.dumps(label) + ")")
        self.evaluate("(()=>{const g=" + group + ";g?.scrollIntoView({block:'center'});})()")
        read = ("(()=>{const g=" + group + ";const i=g?.querySelector('input[type=range]');"
                "const t=g?.firstElementChild;if(!i||!t)return null;"
                "return {value:i.value,min:i.min,max:i.max,step:i.step,"
                "aria_value_now:i.getAttribute('aria-valuenow'),"
                "aria_value_text:i.getAttribute('aria-valuetext'),"
                "track:t.getBoundingClientRect().toJSON(),viewport:[innerWidth,innerHeight]};})()")
        before = self.evaluate(read)
        result = {"ok": False, "requested_value": value, "before": before, "after": None}
        if not isinstance(before, dict):
            return dict(result, error="no visible slider track/input")
        minimum, maximum = float(before["min"]), float(before["max"])
        track = before["track"]
        if not minimum <= value <= maximum or maximum <= minimum or track["width"] <= 0:
            return dict(result, error="invalid slider range/track")
        # The right boundary belongs to the adjacent box in browser hit testing.
        # Click inside the track; the native step rounding still selects max.
        x = min(track["x"] + track["width"] * (value - minimum) / (maximum - minimum),
                track["x"] + track["width"] - min(1.0, track["width"] / 2))
        y = track["y"] + track["height"] / 2
        result["pointer"] = {"x": x, "y": y, "method": "single-track-click"}
        if not 0 <= x < before["viewport"][0] or not 0 <= y < before["viewport"][1]:
            return dict(result, error="target outside visible viewport")
        for kind, buttons in (("mouseMoved", 0), ("mousePressed", 1), ("mouseReleased", 0)):
            response = self.cdp.call("Input.dispatchMouseEvent", {
                "type": kind, "x": x, "y": y, "button": "left", "buttons": buttons, "clickCount": 1,
            })
            if "error" in response:
                return dict(result, error=response["error"])
        deadline = time.monotonic() + timeout
        while True:
            after = self.evaluate(read)
            result["after"] = after
            if isinstance(after, dict) and float(after["value"]) == value:
                return dict(result, ok=True)
            if time.monotonic() >= deadline:
                return dict(result, error="native slider value did not reach requested value")
            time.sleep(0.05)

    def focus_checkbox(self, label: str) -> bool:
        js = (
            "(()=>{const roots=[...document.querySelectorAll('[data-testid=stCheckbox]')];"
            "const e=roots.find(r=>r.textContent.includes(" + json.dumps(label) + "));"
            "if(!e)return false;"
            "const i=e.querySelector('input[type=checkbox]');"
            "if(!i)return false;i.focus();return true;})()"
        )
        return bool(self.evaluate(js))

    def checkbox_toggle(self, label: str, value: bool, timeout: float = 5.0):
        """Read native checked state, press Space once and read it back."""
        read = ("(()=>{const r=[...document.querySelectorAll('[data-testid=stCheckbox]')]"
                ".find(e=>e.textContent.includes(" + json.dumps(label) + "));"
                "return r?.querySelector('input[type=checkbox]')?.checked;})()")
        before = self.evaluate(read)
        result = {"ok": False, "before": before, "after": None,
                  "requested_value": value, "input_method": "Space"}
        if type(before) is not bool or type(value) is not bool:
            return dict(result, error="missing native checkbox state")
        if before == value:
            return dict(result, error="checkbox already at requested value; no input sent")
        if not self.focus_checkbox(label):
            return dict(result, error="checkbox could not be focused")
        self.press(" ", "Space", 32)
        deadline = time.monotonic() + timeout
        while True:
            after = self.evaluate(read)
            result["after"] = after
            if type(after) is bool and after == value:
                return dict(result, ok=True)
            if time.monotonic() >= deadline:
                return dict(result, error="native checkbox state did not change to target")
            time.sleep(0.05)

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
        frame = {
            "direction": "client->server" if method.endswith("Sent") else "server->client",
            "connection": connections.get(request_id),
            "request_id": request_id,
            "timestamp": event["params"].get("timestamp"),
            "namespace": namespace,
            "decoded": decoded,
        }
        if getattr(recorder, "capture_form_membership", False):
            delta = decoded.get("delta") or {}
            form_message = (delta.get("block_type") == "form" or
                            delta.get("element") in ("text_input", "button"))
            if method.endswith("Sent") or form_message:
                frame.update(base64=base64.b64encode(data).decode("ascii"),
                             bytes=len(data), sha256=hashlib.sha256(data).hexdigest())
            if form_message and method.endswith("Received"):
                from forms_contract import _official_forward, _form_blocks_from_forward
                full = _official_forward(data)
                frame["official_forward"] = full
                frame["form_blocks"] = _form_blocks_from_forward(full)
        out.append(frame)
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



# The observation of a journey, the shape the shared criterion reads.
#
# One probe, one shape, for every case:
#
#   observation = {
#       "journey": str,                 # which journey this is
#       "namespace": str,               # the tab the frames belong to
#       "url": str,                     # the application under test
#       "ipc_dir": str,                 # where the retained IPC files are
#       "uploads": {name: bool},        # what the browser accepted
#       "frames": [frame],              # every frame of the tab
#       "phases": [phase],              # the actions, in order
#       "states": [state],              # the pages observed before an action
#       "http_timeline": [request],     # the HTTP requests with their moment
#   }
#
#   frame  = {"direction", "connection", "request_id", "timestamp",
#             "namespace", "decoded"}
#   phase  = {"name", "action", "start", "end", "start_timestamp",
#             "end_timestamp", "dom_before", "dom_after", "client_states",
#             "completions", "ipc", "screenshot"}
#   state  = {"name", "dom", "screenshot"}
#   request = {"method", "url", "request_id", "timestamp", "status",
#              "response_timestamp", "request_headers"}
#
# "action" says what was attempted, never what happened:
#
#   {"action": "upload", "file": str, "attempted": true}
#   {"action": "select-option", "option": str, "attempted": true}
#   {"action": "click", "target": str, "attempted": true}
#   {"action": "slider", "label": str, "value": int, "attempted": true}
#
# That a click was attempted is not that it worked: the proof is in the
# window -- the trigger the client sent, the run that answered it on its own
# connection, the IPC of that run and the DOM after it.  The counters and
# every other value the page shows come from the same probe (the merged
# Page.state_digest), so a field the page never showed stays missing and
# the criterion can reject it; nothing is filled in with a default.
#
# "screenshot" says where the picture of that state is and how big it was:
#
#   {"file": str, "bytes": int, "viewport": [width, height]}
#
# The picture is taken from the real page after the result has drawn, with a
# viewport tall enough to hold it.  Nothing in the page is changed for it.


# The contract of a stage2 observation.  The shared harness owns the names and
# the required sets; the driver only fills this shape in.
OBSERVATION_CONTRACT = "journey-stage2-v1"


def _run_window(frames, start, previous_run=None):
    """The window of the run that an action caused.

    The window holds the state the client sent, the run the server started
    for it -- a run id that is not the previous one -- and the completion
    that ended it.  The first completion is not enough: an interrupted run
    ends before the run that carries the result.
    """
    clients = [
        i for i in range(start, len(frames))
        if frames[i].get("direction") == "client->server"
        and (frames[i].get("decoded") or {}).get("type") == "rerun_script"
    ]
    if not clients:
        return None
    client = clients[0]
    runs = [
        i for i in range(client + 1, len(frames))
        if frames[i].get("direction") == "server->client"
        and (frames[i].get("decoded") or {}).get("type") == "new_session"
        and (frames[i].get("decoded", {}).get("new_session", {}) or {}).get("script_run_id") != previous_run
    ]
    if not runs:
        return None
    run = runs[0]
    identity = (frames[client].get("connection"), frames[client].get("request_id"))
    for index in range(run + 1, len(frames)):
        frame = frames[index]
        decoded = frame.get("decoded") or {}
        if decoded.get("type") == "new_session":
            # Another run started before this one finished, so the completion
            # that follows belongs to that run and not to this one.
            break
        if decoded.get("type") != "script_finished":
            continue
        if (decoded.get("script_finished") or {}).get("status") != 0:
            continue
        if (frame.get("connection"), frame.get("request_id")) != identity:
            continue
        return {"start": client, "end": index + 1, "state": client, "run": run, "finish": index}
    return None


def _upload_request(frames, start, file_name):
    """The frame where the browser asked the server for the URLs of a file."""
    for index in range(start, len(frames)):
        decoded = frames[index].get("decoded") or {}
        if decoded.get("type") != "file_urls_request":
            continue
        if (decoded.get("file_urls_request") or {}).get("file_names") == [file_name]:
            return index
    return None


def _issued_file_id(frames, request_index):
    """The id the server signed out for the file of this request."""
    request = (frames[request_index].get("decoded") or {}).get("file_urls_request") or {}
    request_id = request.get("request_id")
    for index in range(request_index + 1, len(frames)):
        decoded = frames[index].get("decoded") or {}
        if decoded.get("type") != "file_urls_response":
            continue
        response = decoded.get("file_urls_response") or {}
        if request_id and response.get("response_id") != request_id:
            continue
        urls = [item for item in (response.get("file_urls") or []) if item.get("file_id")]
        if len(urls) == 1:
            return urls[0]["file_id"]
    return None


def _uploader_widget_id(frames):
    """The id of the uploader the window is bound to.

    The server publishes the uploader as an element and the client echoes that
    id in its widget state.  When both are there they have to agree; when only
    one is there it names the uploader.
    """
    published = None
    sent = None
    for frame in frames:
        decoded = frame.get("decoded") or {}
        delta = decoded.get("delta") or {}
        if delta.get("element") == "file_uploader" and delta.get("id"):
            published = delta["id"]
        if decoded.get("type") == "rerun_script":
            for state in (decoded.get("rerun_script") or {}).get("widget_states", []) or []:
                if state.get("value_field") == "file_uploader_state_value" and state.get("id"):
                    sent = state["id"]
    if published and sent and published != sent:
        return None
    return published or sent


def _upload_window(frames, start, file_name, namespace):
    """The window of an upload, as the shared binder sees it.

    The shared reader decides when the window is complete: the state that
    names the newly issued file, the server run that answered that state and
    that run's successful completion.  Replacing a file sends the state
    twice -- first with the file cleared -- so the clear run is inside the
    window and never its end.
    """
    request = _upload_request(frames, start, file_name)
    if request is None:
        return None
    file_id = _issued_file_id(frames, request)
    if not file_id:
        return None
    widget_id = _uploader_widget_id(frames)
    if not widget_id:
        return None
    ready = _stage2_target_upload_run(
        frames,
        namespace=namespace,
        start=request,
        end=len(frames),
        widget_id=widget_id,
        file_id=file_id,
        file_name=file_name,
    )
    if not ready.get("ok"):
        return None
    return {
        "start": request,
        "end": ready["completion_frame"] + 1,
        "target": ready["state_frame"],
        "run": ready["run_start_frame"],
        "finish": ready["completion_frame"],
        "script_run_id": ready.get("script_run_id"),
        "widget": widget_id,
        "file_id": file_id,
    }


def _roles_for(journey, phase_index, tab=None):
    """The steps a picture of this phase may attest.

    The shared harness holds the fixed coverage: which step a picture shows
    and which phase it belongs to.  The driver only records the pictures the
    coverage asks for, so the records never carry a step that the coverage
    does not name.
    """
    out = []
    for step_id, role_tab, index in STAGE2_SCREENSHOTS.get(journey, ()):
        if index != phase_index or (role_tab or None) != (tab or None):
            continue
        out.append(step_id)
    return out

def _wait_for_window(pick, timeout: float = 30.0):
    """Wait until the window of an action is complete.

    The frames arrive while the server works, so the window of an action is
    only there once the run that carries the result has finished.
    """
    deadline = time.time() + timeout
    window = None
    while time.time() < deadline:
        window = pick()
        if window:
            return window
        time.sleep(0.5)
    return window


def _phase_window(recorder, namespace, start, file_name=None, previous_run=None):
    """The window of one action, once the server has answered it.

    An upload waits for the request of its URLs, the state that names the
    file and the run that carries the result -- replacing a file sends the
    state twice, and the window is the whole of it.  Every other action
    waits for its state, its run and its completion.
    """

    def pick():
        frames = frames_of(recorder, namespace=namespace)
        if file_name:
            return _upload_window(frames, start, file_name, namespace)
        return _run_window(frames, start, previous_run)

    return _wait_for_window(pick)


def _run_id(frames, window):
    """The marker of the run inside a window."""
    if not window:
        return None
    decoded = frames[window["run"]].get("decoded") or {}
    return (decoded.get("new_session") or {}).get("script_run_id")

def _shot(page, frames, out, name, read_at):
    """Take the picture of a phase and say when it was taken.

    The picture is taken between two browser events, so its moment is the
    newest event plus the time that has passed since the frames were read.
    """
    stamps = [
        f.get("timestamp") for f in frames
        if isinstance(f.get("timestamp"), (int, float))
    ]
    stamp = (max(stamps) + (time.time() - read_at)) if stamps else None
    info = page.screenshot(out / name)
    if info is None:
        return None
    info["timestamp"] = stamp
    info["file"] = name
    return info


def _record(step_ids, phase_name, namespace, shot, out):
    """The record of one picture: the steps it shows, where it is, when.

    The file is named relative to the directory of the capture, so a replay
    finds it next to the raw.
    """
    if not shot or not step_ids:
        # A picture that no step names is not a record: the coverage names the
        # steps a picture may attest, and a record without a step is malformed.
        return None
    path = out / shot["file"]
    return {
        "step_ids": list(step_ids),
        "phase": phase_name,
        "namespace": namespace,
        "file": shot["file"],
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "timestamp": shot.get("timestamp"),
    }


def _sequence_record(name, namespace, shot, out, *, roles=None):
    """The record of one picture of a whole journey.

    Every phase of a journey has a picture.  The record says which step of
    the manifest the picture shows; a phase that shows only the preparation
    says so, and a phase that shows a step names it.
    """
    if not shot:
        return None
    path = out / shot["file"]
    roles = list((SEQUENCE_PNG_ROLES if roles is None else roles).get(name, ()))
    return {
        "step_ids": roles,
        "phase": name,
        "namespace": namespace,
        "file": shot["file"],
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "timestamp": shot.get("timestamp"),
        "role": "step" if roles else "preparation",
    }


def _session_of(frames, window):
    """The session the run of this window belongs to."""
    decoded = (frames[window["run"]].get("decoded") or {}).get("new_session") or {}
    return decoded.get("session_id")


def _uploader_of(frames, window):
    """The file the uploader carried in this window, in the order it sent it."""
    found = []
    for index in range(window["start"], window["end"]):
        decoded = frames[index].get("decoded") or {}
        if decoded.get("type") != "rerun_script":
            continue
        for state in (decoded.get("rerun_script") or {}).get("widget_states", []) or []:
            if state.get("value_field") != "file_uploader_state_value":
                continue
            infos = (state.get("value_full") or {}).get("uploadedFileInfo") or []
            found.append([(info.get("name"), info.get("fileId")) for info in infos])
    return found


def _file_fingerprint(path):
    """The fingerprint of the file an action uploaded."""
    raw = pathlib.Path(path).read_bytes()
    return {
        "file": str(pathlib.Path(path).resolve()),
        "file_sha256": hashlib.sha256(raw).hexdigest(),
        "file_bytes": len(raw),
    }

def _write_trace(path, trace) -> None:
    """Write the trace of a journey.

    The evidence is written before the criteria run, so a criterion that
    raises still leaves the capture it judged on the disk.
    """
    pending = path.with_name(path.name + ".pending")
    pending.write_text(json.dumps(trace, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    pending.replace(path)


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


PULSE_JS = (
    "([...document.querySelectorAll('[data-testid=\"stButton\"] button')]"
    ".find(x=>x.textContent.trim()==='Pulse'))"
)

def _observe(source, recorder, args, out, uploads, phases, states, arrow_files, screenshots=(),
             contract=OBSERVATION_CONTRACT, phase_ids=None):
    """The observation of a journey: one probe, one shape."""
    observation = {
        "namespace": source,
        "url": args.url,
        "ipc_dir": str(out),
        "uploads": uploads,
        "frames": frames_of(recorder, namespace=source),
        "phases": phases,
        "states": states,
        "http_timeline": _http_timeline(recorder),
        "contract": contract,
        "screenshots": screenshots,
    }
    if phase_ids is not None:
        observation["phase_ids"] = list(phase_ids)
    return observation


def _judge(name, criterion, observation):
    """The shared criterion of a case and the coverage of its pictures.

    The two sets are judged apart -- the case and the pictures are two
    journeys of their own -- and their failures are reported together.
    """
    checks = list(criterion(observation=observation))
    result = journey_result(checks)
    pictures = list(screenshot_checks(observation=observation))
    shot_result = journey_result(pictures)
    counts = {
        "expected": result["counts"]["expected"] + shot_result["counts"]["expected"],
        "executed": result["counts"]["executed"] + shot_result["counts"]["executed"],
        "asserted": result["counts"]["asserted"] + shot_result["counts"]["asserted"],
    }
    return {
        "checks": checks + pictures,
        "counts": counts,
        "failures": result["failures"] + shot_result["failures"],
    }

def _git_head() -> str:
    """The commit the capture ran against, when the tree is a git tree."""
    try:
        done = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(ROOT),
                              capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return ""
    return done.stdout.strip() if done.returncode == 0 else ""


def _write_case(out, args, observation, name, summary, verdict=None):
    """Write the trace of a case and the verdict of the shared criterion.

    The evidence goes to the disk before anything is judged, so a criterion
    that raises still leaves the capture it judged.
    """
    if callable(verdict):
        _write_case(out, args, observation, name, summary)
        try:
            judged = verdict()
        except Exception as exc:
            failure = {"step": name, "check": "predicate_exception", "ok": False,
                       "expected": "criterion completes without exception",
                       "actual": f"{type(exc).__name__}: {exc}"}
            judged = {"checks": [failure], "failures": [failure],
                      "counts": {"expected": 1, "executed": 1, "asserted": 0}}
        return _write_case(out, args, observation, name, summary, judged)
    failure = {
        "step": "criteria",
        "check": "contract",
        "expected": "the shared criterion for the " + name + " journey",
        "actual": "not written yet; the capture records the evidence only",
        "ok": False,
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
            "capture_head": _git_head(),
            "build_base": getattr(args, "build_base", "") or "",
        },
        "url": args.url,
        "case": name,
        "journey": name,
        "observation": observation,
        "summary": summary,
        "checks": (verdict or {}).get("checks", []),
        "counts": (verdict or {}).get("counts", {"expected": 0, "executed": 0, "asserted": 0}),
        "failures": (verdict or {}).get("failures", [failure]),
    }
    trace_path = out / "trace-data-loop.json"
    _write_trace(trace_path, trace)
    print("wrote", trace_path)
    print("failures:", json.dumps(trace["failures"]))
    counts = trace.get("counts") or {}
    # The exit code follows the verdict: a case whose checks all passed is a
    # pass, a case with a failed or missing check is not.
    passed = not trace["failures"] and (counts.get("asserted") or 0) > 0
    return 0 if passed else 1

def run_soft_invalid_journey(page, recorder, args, out):
    """The file with two unusable amounts, and the good file that replaces it."""
    paths = [path for path in (args.files.split(",") if args.files else []) if path]
    soft, good = (paths + [None, None])[:2]
    if not (soft and good):
        raise SystemExit("the soft invalid journey needs two files")
    arrow_files = _ArrowFiles(out)
    source = recorder.label
    phases, screenshots = [], []
    previous_run = None

    dom_before = page.state_digest()
    start = len(frames_of(recorder, namespace=source))
    uploaded = page.upload(soft)
    time.sleep(8)
    window = _phase_window(recorder, source, start, pathlib.Path(soft).name, previous_run)
    frames = frames_of(recorder, namespace=source)
    read_at = time.time()
    dom = page.wait_for_render()
    if window is None:
        raise SystemExit("the soft upload produced no run")
    phase = _phase("upload-soft",
                   {"action": "upload", "ok": bool(uploaded), **_file_fingerprint(soft)},
                   frames, window["start"], window["end"], dom_before, dom, arrow_files)
    shot = _shot(page, frames, out, "01-soft-warning.png", read_at)
    phase["screenshot"] = shot
    phase["observation_end_timestamp"] = shot and shot.get("timestamp")
    record = _record(_roles_for("soft-invalid", 0), "upload-soft", source, shot, out)
    if record:
        screenshots.append(record)
    previous_run = _run_id(frames, window)
    phases.append(phase)

    dom_before = dom
    start = len(frames)
    uploaded_good = page.upload(good)
    time.sleep(8)
    window = _phase_window(recorder, source, start, pathlib.Path(good).name, previous_run)
    frames = frames_of(recorder, namespace=source)
    read_at = time.time()
    dom = page.wait_for_render()
    if window is None:
        raise SystemExit("the replacement produced no run")
    phase = _phase("replace-baseline",
                   {"action": "upload", "ok": bool(uploaded_good), **_file_fingerprint(good)},
                   frames, window["start"], window["end"], dom_before, dom, arrow_files)
    shot = _shot(page, frames, out, "02-replaced.png", read_at)
    phase["screenshot"] = shot
    phase["observation_end_timestamp"] = shot and shot.get("timestamp")
    record = _record(_roles_for("soft-invalid", 1), "replace-baseline", source, shot, out)
    if record:
        screenshots.append(record)
    previous_run = _run_id(frames, window)
    phases.append(phase)

    observation = _observe(source, recorder, args, out,
                          {"soft": bool(uploaded), "good": bool(uploaded_good)},
                          phases, [], arrow_files, screenshots)
    observation["journey"] = "soft-invalid"
    verdict = lambda: _judge("soft-invalid", soft_invalid_checks, observation)
    return _write_case(out, args, observation, "soft-invalid", {
        "alerts": (page.page_alerts() or {}).get("alerts"),
        "dom": dom,
    }, verdict)


def run_non_utf8_journey(page, recorder, args, out):
    """The file that is not UTF-8, and the good file that replaces it."""
    paths = [path for path in (args.files.split(",") if args.files else []) if path]
    bad, good = (paths + [None, None])[:2]
    if not (bad and good):
        raise SystemExit("the non utf8 journey needs two files")
    arrow_files = _ArrowFiles(out)
    source = recorder.label
    phases, screenshots = [], []
    previous_run = None

    dom_before = page.state_digest()
    start = len(frames_of(recorder, namespace=source))
    uploaded = page.upload(bad)
    time.sleep(8)
    window = _phase_window(recorder, source, start, pathlib.Path(bad).name, previous_run)
    frames = frames_of(recorder, namespace=source)
    read_at = time.time()
    dom = page.wait_for_render(want_cells=False)
    if window is None:
        raise SystemExit("the utf8 upload produced no run")
    phase = _phase("upload-utf8",
                   {"action": "upload", "ok": bool(uploaded), **_file_fingerprint(bad)},
                   frames, window["start"], window["end"], dom_before, dom, arrow_files)
    shot = _shot(page, frames, out, "01-not-utf8-error.png", read_at)
    phase["screenshot"] = shot
    phase["observation_end_timestamp"] = shot and shot.get("timestamp")
    record = _record(_roles_for("non-utf8", 0), "upload-utf8", source, shot, out)
    if record:
        screenshots.append(record)
    previous_run = _run_id(frames, window)
    phases.append(phase)

    dom_before = dom
    start = len(frames)
    uploaded_good = page.upload(good)
    time.sleep(8)
    window = _phase_window(recorder, source, start, pathlib.Path(good).name, previous_run)
    frames = frames_of(recorder, namespace=source)
    read_at = time.time()
    dom = page.wait_for_render()
    if window is None:
        raise SystemExit("the replacement produced no run")
    phase = _phase("replace-baseline",
                   {"action": "upload", "ok": bool(uploaded_good), **_file_fingerprint(good)},
                   frames, window["start"], window["end"], dom_before, dom, arrow_files)
    shot = _shot(page, frames, out, "02-replaced.png", read_at)
    phase["screenshot"] = shot
    phase["observation_end_timestamp"] = shot and shot.get("timestamp")
    record = _record(_roles_for("non-utf8", 1), "replace-baseline", source, shot, out)
    if record:
        screenshots.append(record)
    previous_run = _run_id(frames, window)
    phases.append(phase)

    observation = _observe(source, recorder, args, out,
                          {"bad": bool(uploaded), "good": bool(uploaded_good)},
                          phases, [], arrow_files, screenshots)
    observation["journey"] = "non-utf8"
    verdict = lambda: _judge("non-utf8", non_utf8_checks, observation)
    return _write_case(out, args, observation, "non-utf8", {
        "alerts": (page.page_alerts() or {}).get("alerts"),
        "dom": dom,
    }, verdict)


def run_filter_empty_journey(page, recorder, args, out):
    """The filters that leave no row, and the way back."""
    path = args.fixture or (args.files.split(",")[0] if args.files else "")
    if not path:
        raise SystemExit("the filter empty journey needs a file")
    arrow_files = _ArrowFiles(out)
    source = recorder.label
    phases, screenshots = [], []
    previous_run = None

    dom_before = page.state_digest()
    start = len(frames_of(recorder, namespace=source))
    uploaded = page.upload(path)
    time.sleep(8)
    window = _phase_window(recorder, source, start, pathlib.Path(path).name, previous_run)
    frames = frames_of(recorder, namespace=source)
    read_at = time.time()
    dom = page.wait_for_render()
    if window is None:
        raise SystemExit("the upload produced no run")
    phase = _phase("upload-baseline",
                   {"action": "upload", "ok": bool(uploaded), **_file_fingerprint(path)},
                   frames, window["start"], window["end"], dom_before, dom, arrow_files)
    previous_run = _run_id(frames, window)
    phases.append(phase)

    dom_before = dom
    start = len(frames)
    page.focus_slider("Minimum amount", 0)
    page.press("End", "End", 35)
    time.sleep(6)
    window = _phase_window(recorder, source, start, None, previous_run)
    frames = frames_of(recorder, namespace=source)
    read_at = time.time()
    dom = page.wait_for_render(want_cells=False)
    if window is None:
        raise SystemExit("the slider produced no run")
    phase = _phase("slider-200",
                   {"action": "slider", "label": "Minimum amount", "value": 200, "ok": True},
                   frames, window["start"], window["end"], dom_before, dom, arrow_files)
    shot = _shot(page, frames, out, "01-no-rows-match.png", read_at)
    phase["screenshot"] = shot
    phase["observation_end_timestamp"] = shot and shot.get("timestamp")
    record = _record(_roles_for("filter-empty", 1), "slider-200", source, shot, out)
    if record:
        screenshots.append(record)
    previous_run = _run_id(frames, window)
    phases.append(phase)

    dom_before = dom
    start = len(frames)
    page.focus_slider("Minimum amount", 0)
    page.press("Home", "Home", 36)
    time.sleep(6)
    window = _phase_window(recorder, source, start, None, previous_run)
    frames = frames_of(recorder, namespace=source)
    read_at = time.time()
    dom = page.wait_for_render()
    if window is None:
        raise SystemExit("the slider produced no run")
    phase = _phase("slider-0",
                   {"action": "slider", "label": "Minimum amount", "value": 0, "ok": True},
                   frames, window["start"], window["end"], dom_before, dom, arrow_files)
    shot = _shot(page, frames, out, "02-recovered.png", read_at)
    phase["screenshot"] = shot
    phase["observation_end_timestamp"] = shot and shot.get("timestamp")
    record = _record(_roles_for("filter-empty", 2), "slider-0", source, shot, out)
    if record:
        screenshots.append(record)
    previous_run = _run_id(frames, window)
    phases.append(phase)

    observation = _observe(source, recorder, args, out, {"file": bool(uploaded)},
                          phases, [], arrow_files, screenshots)
    observation["journey"] = "filter-empty"
    verdict = lambda: _judge("filter-empty", filter_empty_checks, observation)
    return _write_case(out, args, observation, "filter-empty", {
        "alerts": (page.page_alerts() or {}).get("alerts"),
        "dom": dom,
    }, verdict)

def run_state_journey(page, recorder, args, out):
    """The session state: the first load, a control, an upload, the Pulse button."""
    path = args.fixture or (args.files.split(",")[0] if args.files else "")
    if not path:
        raise SystemExit("the state journey needs a file")
    arrow_files = _ArrowFiles(out)
    source = recorder.label
    phases, screenshots = [], []
    previous_run = None

    def phase_of(name, action, frames, window, dom_before, dom, read_at, shot_name, index):
        phase = _phase(name, action, frames, window["start"], window["end"],
                       dom_before, dom, arrow_files)
        shot = _shot(page, frames, out, shot_name, read_at)
        phase["screenshot"] = shot
        phase["observation_end_timestamp"] = shot and shot.get("timestamp")
        record = _record(_roles_for("state", index), name, source, shot, out)
        if record:
            screenshots.append(record)
        phases.append(phase)
        return phase

    # the first load: the page before any action
    frames = frames_of(recorder, namespace=source)
    read_at = time.time()
    dom = page.wait_for_render(want_cells=False)
    window = _run_window(frames, 0)
    if window is None:
        raise SystemExit("the first load produced no run")
    phase_of("initial", {"action": "initial", "ok": True}, frames, window, dom, dom,
             read_at, "01-initial.png", 0)
    previous_run = _run_id(frames, window)

    # the control: one change, one run
    start = len(frames)
    dom_before = dom
    if not _select_option(page, "region"):
        raise SystemExit("the group of the selector could not be changed")
    time.sleep(6)
    window = _phase_window(recorder, source, start, None, previous_run)
    frames = frames_of(recorder, namespace=source)
    read_at = time.time()
    dom = page.wait_for_render(want_cells=False)
    if window is None:
        raise SystemExit("the selector produced no run")
    phase_of("selector", {"action": "select-option", "option": "region", "ok": True},
             frames, window, dom_before, dom, read_at, "02-after-selector.png", 1)
    previous_run = _run_id(frames, window)

    # the upload: the baseline file, on its own run
    start = len(frames)
    dom_before = dom
    uploaded = page.upload(path)
    time.sleep(8)
    window = _phase_window(recorder, source, start, pathlib.Path(path).name, previous_run)
    frames = frames_of(recorder, namespace=source)
    read_at = time.time()
    dom = page.wait_for_render()
    if window is None:
        raise SystemExit("the upload produced no run")
    phase_of("upload-baseline",
             {"action": "upload", "ok": bool(uploaded), **_file_fingerprint(path)},
             frames, window, dom_before, dom, read_at, "03-after-upload.png", 2)
    previous_run = _run_id(frames, window)

    # the button: a real mouse event on the visible button
    start = len(frames)
    dom_before = dom
    clicked = page.click_visible(PULSE_JS)
    if not clicked:
        raise SystemExit("the Pulse button was not found")
    time.sleep(8)
    window = _phase_window(recorder, source, start, None, previous_run)
    frames = frames_of(recorder, namespace=source)
    read_at = time.time()
    dom = page.wait_for_render()
    if window is None:
        raise SystemExit("the Pulse click produced no run")
    phase_of("pulse", {"action": "button", "label": "Pulse", "ok": True},
             frames, window, dom_before, dom, read_at, "04-after-pulse.png", 3)

    observation = _observe(source, recorder, args, out, {"file": bool(uploaded)},
                          phases, [], arrow_files, screenshots)
    observation["journey"] = "state"
    verdict = lambda: _judge("state", state_checks, observation)
    return _write_case(out, args, observation, "state", {
        "alerts": (page.page_alerts() or {}).get("alerts"),
        "dom": dom,
    }, verdict)

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
        "journey": args.journey,
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
            "capture_head": _git_head(),
            "build_base": getattr(args, "build_base", "") or "",
        },
        "url": args.url,
        "case": args.journey,
        "journey": args.journey,
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
        "journey": args.journey,
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
            "capture_head": _git_head(),
            "build_base": getattr(args, "build_base", "") or "",
        },
        "url": args.url,
        "case": args.journey,
        "journey": args.journey,
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
        "journey": args.journey,
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
            "capture_head": _git_head(),
            "build_base": getattr(args, "build_base", "") or "",
        },
        "url": args.url,
        "case": args.journey,
        "journey": args.journey,
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



# The runner of each journey, by its name.
def run_sequence_journey(page, recorder, args, out):
    """One page, one session: the whole journey, step by step.

    The tab is never reloaded and the page is never closed, so the journey
    starts at the first load and ends at the last step of the same session.
    Every step is recorded with the window the shared reader accepts, so the
    result of a step is bound to the run that answered it.
    """
    steps = _sequence_plan(args.journey)
    contract = {J00_CASE: J00_CONTRACT, J01_CASE: J01_CONTRACT, J02_CASE: J02_CONTRACT, J03_CASE: J03_CONTRACT}.get(args.journey, SEQUENCE_CONTRACT)
    if args.journey == J00_CASE:
        recorder.capture_form_membership = True
    arrow_files = _ArrowFiles(out)
    source = recorder.label
    phases, screenshots, uploads = [], [], {}
    previous_run = None
    dom = page.state_digest()

    for name, action, want_cells, shot_name in steps:
        dom_before = dom
        start = len(frames_of(recorder, namespace=source))
        fingerprint = {}
        if action["action"] == "initial":
            window = _run_window(frames_of(recorder, namespace=source), 0)
            ok = True
        elif action["action"] == "upload":
            path = str(ROOT / "tests" / "fixtures" / "csv" / action["file"])
            ok = page.upload(path)
            time.sleep(8)
            window = _phase_window(recorder, source, start, action["file"], previous_run)
            fingerprint = _file_fingerprint(path)
            uploads[name] = bool(ok)
        elif action["action"] == "select-option":
            ok = _select_option(page, action["option"])
            window = _phase_window(recorder, source, start, None, previous_run)
        elif args.journey in (J00_CASE, J02_CASE, J03_CASE) and action["action"] == "slider":
            pointer = page.slider_pointer(action["label"], action["value"])
            action = dict(action, pointer=pointer)
            ok = pointer["ok"]
            window = _phase_window(recorder, source, start, None, previous_run)
        elif action["action"] == "checkbox":
            checkbox = page.checkbox_toggle(action["label"], action["value"])
            action = dict(action, checkbox=checkbox)
            ok = checkbox["ok"]
            window = _phase_window(recorder, source, start, None, previous_run)
        else:
            page.focus_slider(action["label"], 0)
            page.press(action["key"], action["key"], action["code"])
            time.sleep(6)
            window = _phase_window(recorder, source, start, None, previous_run)
            ok = True
        frames = frames_of(recorder, namespace=source)
        read_at = time.time()
        dom = page.wait_for_render(want_cells=want_cells) or {}
        alerts = page.page_alerts() or {}
        if window is None:
            observation = _observe(source, recorder, args, out, uploads, phases, [], arrow_files, screenshots,
                                   contract=contract, phase_ids=[p["name"] for p in phases])
            observation["journey"] = args.journey
            return _write_case(out, args, observation, args.journey,
                               {"incomplete_phase": name, "action": dict(action, ok=bool(ok)),
                                "dom_before": dom_before, "dom_after": dom})
        phase = _phase(name, dict(action, ok=bool(ok), **fingerprint),
                       frames, window["start"], window["end"], dom_before, dom, arrow_files)
        shot = _shot(page, frames, out, shot_name, read_at)
        phase["screenshot"] = shot
        phase["observation_end_timestamp"] = shot and shot.get("timestamp")
        # The picture paints the page; the grid of the data frame draws its
        # cells lazily, so the values are read again after it.
        dom = page.state_digest() or dom
        alerts = page.page_alerts() or alerts
        record = _sequence_record(name, source, shot, out,
                                  roles={J00_CASE: J00_PNG_ROLES, J01_CASE: J01_PNG_ROLES, J02_CASE: J02_PNG_ROLES, J03_CASE: J03_PNG_ROLES}.get(args.journey))
        if record:
            screenshots.append(record)
        phase["alerts"] = alerts.get("alerts")
        if args.journey == J00_CASE:
            dom["form_membership"] = page.evaluate(J00_FORM_DOM_JS)
        if args.journey in (J00_CASE, J01_CASE, J02_CASE, J03_CASE):
            phase["dom_after"] = dom
        phase["exceptions"] = alerts.get("exceptions")
        phase["counters"] = {"script_runs": dom.get("script_runs"), "pulses": dom.get("pulses")}
        phase["session_id"] = _session_of(frames, window)
        phase["script_run_id"] = _run_id(frames, window)
        phase["connection"] = frames[window["start"]].get("connection")
        phase["uploader_state"] = _uploader_of(frames, window)
        phases.append(phase)
        previous_run = _run_id(frames, window)

    observation = _observe(source, recorder, args, out, uploads, phases, [], arrow_files, screenshots,
                           contract=contract,
                           phase_ids=[name for name, _, _, _ in steps])
    observation["journey"] = args.journey
    summary = {
        "phases": [
            {
                "name": phase["name"],
                "counters": phase["counters"],
                "alerts": phase["alerts"],
                "session_id": phase["session_id"],
                "script_run_id": phase["script_run_id"],
                "connection": phase["connection"],
                "uploader_state": phase["uploader_state"],
                "table_cells": (phase["dom_after"] or {}).get("table_cells"),
                "chart_present": (phase["dom_after"] or {}).get("chart_present"),
                "screenshot": phase["screenshot"],
            }
            for phase in phases
        ],
    }
    # Preserve the real observation before executing a separately owned
    # criterion: a predicate exception must not discard an entire capture.
    return _write_case(out, args, observation, args.journey, summary,
                       lambda: _judge_sequence(args.journey, observation))


def _judge_sequence(name, observation):
    """The shared criterion of the whole journey, or the closed door.

    While the shared criterion is not written the case fails: the raw is
    written first, so the evidence is on the disk, and the verdict says that
    nothing was judged.
    """
    criterion = {J00_CASE: j00_checks, J01_CASE: j01_checks, J02_CASE: j02_checks, J03_CASE: j03_checks}.get(name, sequence_checks)
    if criterion is None:
        checks = [
            {
                "journey": name,
                "step": name,
                "check": "contract",
                "expected": "the shared criterion of the whole journey",
                "actual": "the shared criterion is not written yet",
                "ok": False,
            }
        ]
    else:
        checks = list(criterion(observation=observation))
    result = journey_result(checks)
    return {"checks": checks, "counts": result["counts"], "failures": result["failures"]}


JOURNEY_RUNNERS = {
    "recover": run_recover_journey,
    "empty": run_empty_journey,
    "sessions": run_sessions_journey,
    "soft-invalid": run_soft_invalid_journey,
    "non-utf8": run_non_utf8_journey,
    "filter-empty": run_filter_empty_journey,
    "state": run_state_journey,
    "j07-sequence": run_sequence_journey,
    "j08-sequence": run_sequence_journey,
    J01_CASE: run_sequence_journey,
    J03_CASE: run_sequence_journey,
    J02_CASE: run_sequence_journey,
    J00_CASE: run_sequence_journey,
}


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
        choices=JOURNEYS,
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
    parser.add_argument("--build-base", default="",
                        help="the commit the binary under test was built from")
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
    # The tab opens blank and the recorder is attached before the
    # application is loaded, so the first run of the app is recorded too --
    # the initial state of a session is part of the evidence.
    created = http_json(f"http://127.0.0.1:{args.port}/json/new?about:blank", method="PUT")
    created_id = created.get("id")
    deadline = time.time() + 45
    tab = None
    while time.time() < deadline and tab is None:
        listing = http_json(f"http://127.0.0.1:{args.port}/json/list")
        for candidate in listing:
            if candidate.get("id") == created_id:
                tab = candidate
                break
        time.sleep(1)
    if tab is None:
        raise SystemExit("the new tab never appeared")

    recorder = CDP(tab["webSocketDebuggerUrl"], label=args.label)
    recorder.start()
    recorder.call("Page.navigate", {"url": args.url})
    deadline = time.time() + 45
    while time.time() < deadline:
        listing = http_json(f"http://127.0.0.1:{args.port}/json/list")
        for candidate in listing:
            if candidate.get("id") != created_id:
                continue
            if (candidate.get("title") or "").strip() not in ("", "New Tab", "about:blank"):
                break
        else:
            time.sleep(2)
            continue
        break
    page = Page(recorder)
    time.sleep(3)

    if args.case == "data-loop":
        runner = JOURNEY_RUNNERS.get(args.journey)
        if runner is not None:
            return runner(page, recorder, args, out)
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
