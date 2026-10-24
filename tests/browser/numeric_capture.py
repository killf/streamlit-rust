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
    SUITES,
    case_verdict,
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
