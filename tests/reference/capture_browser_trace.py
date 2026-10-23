"""Capture a real-browser reference trace of the Streamlit 1.66.1 reference app.

    python tests/reference/capture_browser_trace.py --scenario closed-loop \\
        --url http://localhost:8601 --out tests/reference/reference-browser/closed-loop
    python tests/reference/capture_browser_trace.py --scenario errors   ...
    python tests/reference/capture_browser_trace.py --scenario form     ...
    python tests/reference/capture_browser_trace.py --scenario tabs     ...
    python tests/reference/capture_browser_trace.py --scenario reconnect ...

WHAT THIS RECORDS
    * the HTTP requests the official 1.66.1 frontend makes.  The static bundle
      is counted but not stored, so the artefact stays small.  The upload
      request is recorded in full detail -- method, path, content-type, the
      multipart field names, the part's filename and size, and the 204
      response -- so that a Rust server can replay it.
    * the WebSocket handshake, including the ``Sec-WebSocket-Protocol`` request
      header that carries the XSRF token and, on a reconnect, the session id.
    * every bidirectional binary frame, decoded with the official 1.66.1
      protobuf definitions that ship with the pinned interpreter.
    * the rendered DOM state after every interaction, plus the expected value,
      so a step that silently did nothing is recorded as failed.

WHAT THIS IS NOT
    A PYTHON-SIDE OBSERVATION.  It records what Streamlit 1.66.1 does over the
    wire.  It says nothing about the Rust implementation, which is still
    entirely unverified.  The Rust side is expected to reproduce this trace,
    not to be excused by it.

BROWSER
    The browser is driven with the ``agent-browser`` CLI.  That CLI records HTTP
    requests but has no WebSocket frame capture, so the frames are read from
    the Chrome DevTools Protocol endpoint of the very same browser instance
    (``Network.webSocketFrameSent`` / ``Network.webSocketFrameReceived``).  No
    second browser is involved.

END CONDITION
    The capture ends on the last observed ``script_finished`` frame plus the
    final DOM observation -- not on socket EOF.  Streamlit keeps a long-lived
    WebSocket with a heartbeat, so waiting for the socket to close would hang
    forever.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import pathlib
import re
import shutil
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone

HERE = pathlib.Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]

AB_EXE_CANDIDATES = [
    r"C:\nvm4w\nodejs\node_modules\agent-browser\bin\agent-browser-win32-x64.exe",
]

SCENARIOS = ("closed-loop", "errors", "form", "tabs", "reconnect", "refresh", "smoke")


def find_agent_browser() -> str:
    for candidate in AB_EXE_CANDIDATES:
        if pathlib.Path(candidate).exists():
            return candidate
    found = shutil.which("agent-browser")
    if found:
        return found
    raise SystemExit("agent-browser not found; install it with `npm i -g agent-browser`")


class AB:
    """Thin, timeout-guarded wrapper around the agent-browser CLI."""

    def __init__(self, exe: str, timeout: int = 40) -> None:
        self.exe = exe
        self.timeout = timeout
        self.commands: list[dict] = []

    def run(self, *args: str, timeout: int | None = None) -> str:
        argv = [self.exe, *args]
        label = " ".join(args)
        try:
            done = subprocess.run(
                argv,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout or self.timeout,
            )
        except subprocess.TimeoutExpired:
            self.commands.append({"command": label, "exit_code": None, "note": "timeout"})
            raise SystemExit(f"agent-browser timed out: {label}")
        out = (done.stdout or "") + (done.stderr or "")
        self.commands.append({"command": label, "exit_code": done.returncode})
        if done.returncode != 0:
            raise SystemExit(f"agent-browser failed ({done.returncode}): {label}\n{out}")
        return out.strip()

    def click(self, selector: str) -> None:
        """Scroll the target into the viewport, then click it.

        The Streamlit button is built on a Radix primitive that reacts to
        pointer events, and the page is taller than the browser viewport, so a
        click without scrolling lands on nothing.
        """
        self.run("scrollintoview", selector)
        time.sleep(0.4)
        self.run("click", selector)

    def snapshot_refs(self) -> list[dict]:
        text = self.run("snapshot", "-i")
        entries = []
        pattern = re.compile(
            r'^\s*-\s+(?P<role>[\w ]+?)\s+"(?P<name>[^"]*)"(?P<rest>.*?)\bref=(?P<ref>e\d+)'
        )
        for line in text.splitlines():
            m = pattern.match(line)
            if not m:
                continue
            rest = m.group("rest")
            state = ""
            for key in ("checked", "expanded", "value"):
                sm = re.search(rf"{key}=(\S+?)[,\]]", rest)
                if sm:
                    state = sm.group(1)
                    break
            entries.append(
                {
                    "ref": m.group("ref"),
                    "role": m.group("role").strip(),
                    "name": m.group("name"),
                    "state": state,
                }
            )
        return entries

    def find_ref(self, role: str, name_contains: str) -> str:
        for entry in self.snapshot_refs():
            if entry["role"] == role and name_contains.lower() in entry["name"].lower():
                return entry["ref"]
        raise SystemExit(f"no {role!r} matching {name_contains!r} in the accessibility tree")

    def observe(self) -> dict:
        """Read the rendered state back from the DOM.

        The table renders into a canvas, so its content is read from the ARIA
        grid cells rather than from innerText.
        """
        js = r"""(()=>{const q=s=>document.querySelector(s);
const df=q("[data-testid='stDataFrame']");
const cells=[...document.querySelectorAll("[data-testid='stDataFrame'] [role='gridcell']")].map(e=>e.textContent);
const chart=q("[data-testid='stVegaLiteChart']");
const bars=chart?chart.querySelectorAll("g[class*='mark-rect'] path").length:0;
const labels=chart?[...chart.querySelectorAll("g[class*='mark-text'] text")].map(e=>e.textContent):[];
const thumb=q("[data-testid='stSliderThumbValue']");
const cb=q("[data-testid='stCheckbox'] input");
const sb=q("[data-testid='stSelectbox'] input");
const alerts=[...document.querySelectorAll("[data-testid^='stAlertContent']")].map(e=>e.textContent);
const texts=[...document.querySelectorAll("[data-testid='stText']")].map(e=>e.textContent);
const pick=(p)=>{const t=texts.find(x=>x.startsWith(p));return t?t.slice(p.length).trim():null;};
const buttons=[...document.querySelectorAll("[data-testid='stButton']")].map(e=>e.innerText.trim());
return JSON.stringify({
 document_title: document.title,
 headings: [...document.querySelectorAll("h1,h2,h3")].map(e=>e.innerText.trim()).slice(0,4),
 button_labels: buttons,
 has_button: buttons.length>0,
 script_runs: pick("Script runs:"),
 pulses: pick("Pulses:"),
 applied_note: pick("Applied note:"),
 table_cells:cells, table_present:!!df,
 chart_present:!!chart, chart_bars:bars, chart_labels:labels,
 slider_value: thumb?thumb.textContent:null,
 checkbox_checked: cb?cb.checked:null,
 selectbox_value: sb?sb.value:null,
 texts:texts,
 alerts:alerts});})()"""
        raw = self.run("eval", js)
        try:
            value = json.loads(raw)
        except json.JSONDecodeError:
            return {"raw": raw[:400]}
        if isinstance(value, str):
            try:
                value = json.loads(value)
            except json.JSONDecodeError:
                return {"raw": value[:400]}
        return value if isinstance(value, dict) else {"value": value}


class CDP:
    """Records HTTP traffic and WebSocket frames from one page target."""

    def __init__(self, page_ws_url: str, label: str = "tab-a") -> None:
        self.page_ws_url = page_ws_url
        self.label = label
        self.events: list[dict] = []
        self._ws = None
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._next_id = 0
        self._responses: dict[int, dict] = {}
        self._lock = threading.Lock()

    def start(self) -> None:
        from websockets.sync.client import connect

        self._ws = connect(self.page_ws_url, max_size=None, open_timeout=20)
        self._thread = threading.Thread(target=self._pump, daemon=True)
        self._thread.start()
        self.send("Network.enable")
        self.send("Page.enable")

    def send(self, method: str, params: dict | None = None) -> None:
        with self._lock:
            self._next_id += 1
            message = {"id": self._next_id, "method": method, "params": params or {}}
        self._ws.send(json.dumps(message))

    def call(self, method: str, params: dict | None = None, timeout: float = 10.0) -> dict:
        """Send a command and wait for its response."""
        with self._lock:
            self._next_id += 1
            ident = self._next_id
            message = {"id": ident, "method": method, "params": params or {}}
        self._ws.send(json.dumps(message))
        deadline = time.time() + timeout
        while time.time() < deadline:
            with self._lock:
                response = self._responses.pop(ident, None)
            if response is not None:
                return response
            time.sleep(0.02)
        return {"error": f"timeout waiting for the response to {method}"}

    def _pump(self) -> None:
        from websockets.exceptions import ConnectionClosed

        while not self._stop.is_set():
            try:
                raw = self._ws.recv(timeout=0.25)
            except TimeoutError:
                continue
            except (ConnectionClosed, OSError):
                break
            except Exception:
                break
            try:
                message = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if "method" in message:
                message["_target"] = self.label
                self.events.append(message)
            elif "id" in message:
                # Command responses must be kept, otherwise every call() would
                # time out and a failed command would look like a silent pass.
                with self._lock:
                    self._responses[message["id"]] = message

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=3)
        try:
            self._ws.close()
        except Exception:
            pass

    def take(self) -> list[dict]:
        with self._lock:
            return list(self.events)

    def frame_count(self) -> int:
        """How many WebSocket frame events have been observed so far.

        The index of a frame in the finished trace is the same number, because
        the trace lists the frame events in arrival order.
        """
        with self._lock:
            return sum(
                1
                for event in self.events
                if event.get("method")
                in ("Network.webSocketFrameSent", "Network.webSocketFrameReceived")
            )


def _scalar(value):
    if isinstance(value, (bool, int, float, str)) or value is None:
        return value
    if isinstance(value, bytes):
        return f"<{len(value)} bytes>"
    if isinstance(value, str) and len(value) > 300:
        return value[:300] + "...<truncated>"
    if hasattr(value, "ListFields"):
        return {f.name: _scalar(getattr(value, f.name)) for f, _ in value.ListFields()}
    if isinstance(value, (list, tuple)) or (
        hasattr(value, "__iter__") and not isinstance(value, (str, bytes, dict))
    ):
        try:
            return [_scalar(v) for v in value]
        except TypeError:
            return str(value)
    return str(value)


def _safe(fn, payload: bytes) -> dict:
    try:
        return fn(payload)
    except Exception as exc:
        return {"message": "undecoded", "error": f"{type(exc).__name__}: {exc}"}


def summarise_forward(payload: bytes) -> dict:
    from streamlit.proto.ForwardMsg_pb2 import ForwardMsg

    msg = ForwardMsg()
    msg.ParseFromString(payload)
    kind = msg.WhichOneof("type")
    out: dict = {"message": "ForwardMsg", "type": kind}
    if kind == "new_session":
        out["new_session"] = {
            "script_run_id": msg.new_session.script_run_id,
            "name": msg.new_session.name,
            "main_script_path": msg.new_session.main_script_path,
            "page_script_hash": msg.new_session.page_script_hash,
            "main_script_hash": msg.new_session.main_script_hash,
            "session_id": msg.new_session.initialize.session_id,
        }
    elif kind == "delta":
        delta = msg.delta
        dkind = delta.WhichOneof("type")
        entry: dict = {"type": dkind}
        if dkind == "new_element":
            element = delta.new_element
            name = element.WhichOneof("type")
            entry["element"] = name
            widget = getattr(element, name, None)
            if widget is not None:
                if hasattr(widget, "id"):
                    entry["id"] = widget.id
                if hasattr(widget, "label"):
                    entry["label"] = widget.label
                if hasattr(widget, "body"):
                    entry["body"] = widget.body[:120]
                if hasattr(widget, "type"):
                    accepted = widget.type
                    if isinstance(accepted, (str, bytes)) or not hasattr(accepted, "__iter__"):
                        accepted = [accepted]
                    entry["accepted_types"] = [str(a) for a in accepted]
                if hasattr(widget, "form_id"):
                    entry["form_id"] = widget.form_id
        elif dkind == "add_block":
            entry["block_id"] = delta.add_block.id
            entry["block_type"] = delta.add_block.WhichOneof("type")
        out["delta"] = entry
    elif kind == "script_finished":
        out["script_finished"] = {
            "status": int(msg.script_finished),
            "status_name": ForwardMsg.ScriptFinishedStatus.Name(msg.script_finished),
        }
    elif kind == "session_status_changed":
        out["session_status_changed"] = {
            "script_is_running": msg.session_status_changed.script_is_running,
            "run_on_save": msg.session_status_changed.run_on_save,
        }
    return out


def summarise_back(payload: bytes) -> dict:
    from streamlit.proto.BackMsg_pb2 import BackMsg

    msg = BackMsg()
    msg.ParseFromString(payload)
    kind = msg.WhichOneof("type")
    out: dict = {"message": "BackMsg", "type": kind}
    if kind == "rerun_script":
        states = []
        for widget in msg.rerun_script.widget_states.widgets:
            value_field = widget.WhichOneof("value")
            value = getattr(widget, value_field) if value_field else None
            states.append({"id": widget.id, "value_field": value_field, "value": _scalar(value)})
        out["rerun_script"] = {"widget_states": states}
    return out


def _ab_version(exe: str) -> str:
    try:
        done = subprocess.run(
            [exe, "--version"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=20,
        )
        return (done.stdout or "").strip() or "unknown"
    except Exception:
        return "unknown"


def browser_version(cdp_browser_url: str) -> str:
    import urllib.request

    m = re.match(r"ws://([^:/]+):(\d+)/", cdp_browser_url)
    if not m:
        return "unknown"
    try:
        with urllib.request.urlopen(f"http://{m.group(1)}:{m.group(2)}/json/version", timeout=10) as r:
            return json.load(r).get("Browser", "unknown")
    except Exception:
        return "unknown"


def page_targets(cdp_browser_url: str, host: str | None = None) -> list[dict]:
    """The page targets of the browser.

    ``host`` is the host of the application under test.  It must be honoured
    rather than assuming "localhost": the Rust server is reached through
    127.0.0.1 while the reference server uses localhost.
    """
    import urllib.request

    m = re.match(r"ws://([^:/]+):(\d+)/", cdp_browser_url)
    if not m:
        raise SystemExit(f"unexpected cdp url: {cdp_browser_url}")
    base = f"http://{m.group(1)}:{m.group(2)}"
    with urllib.request.urlopen(base + "/json/list", timeout=10) as response:
        targets = json.load(response)
    wanted = host or "localhost"
    return [t for t in targets if t.get("type") == "page" and wanted in t.get("url", "")]


def _matches(want, got) -> bool:
    if isinstance(want, list):
        if not isinstance(got, list):
            return False
        return got[: len(want)] == want
    return got == want


def _find_option_ref(ab: AB, text: str) -> str | None:
    for role in ("option", "menuitem", "text", "listitem"):
        for entry in ab.snapshot_refs():
            if entry["role"] == role and entry["name"].strip().lower() == text.lower():
                return entry["ref"]
    return None


def _decode_payload(opcode, payload_data: str) -> bytes:
    if opcode == 2:
        return base64.b64decode(payload_data)
    return payload_data.encode("utf-8")


def _runs(observation: dict) -> str:
    for text in observation.get("texts") or []:
        if text.startswith("Script runs:"):
            return text.split(":", 1)[1].strip()
    return ""


def _pulses(observation: dict) -> str:
    for text in observation.get("texts") or []:
        if text.startswith("Pulses:"):
            return text.split(":", 1)[1].strip()
    return ""


class Capture:
    def __init__(self, args) -> None:
        self.args = args
        self.out_dir = pathlib.Path(args.out)
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self.ab = AB(find_agent_browser())
        self.steps: list[dict] = []
        self.failures: list[dict] = []
        self.recorders: list[CDP] = []
        self.notes: list[str] = []
        self.click_windows: list[dict] = []
        self.page_title = ""
        self.chrome = "unknown"
        self.cdp_browser_url = ""
        # A real connection fault needs a real close of the established socket.
        # Chrome's Network.emulateNetworkConditions only blocks NEW requests, so
        # the hook below captures the live WebSocket and closes it for real.
        self.hook_source = (
            "window.__stWs=null;"
            "const _W=window.WebSocket;"
            "window.WebSocket=function(...a){const s=new _W(...a);window.__stWs=s;return s;};"
            "window.WebSocket.prototype=_W.prototype;"
        ) if args.scenario == "reconnect" else None

    def mark(self, name: str, note: str, expected: dict | None = None) -> dict:
        try:
            observation = self.ab.observe()
        except SystemExit as exc:
            observation = {"error": str(exc)[:200]}
        checked = {}
        for key, want in (expected or {}).items():
            got = observation.get(key)
            ok = _matches(want, got)
            checked[key] = {"expected": want, "actual": got, "ok": ok}
            if not ok:
                self.failures.append({"step": name, "check": key, "expected": want, "actual": got})
        self.steps.append(
            {
                "step": name,
                "note": note,
                "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "observed": observation,
                "checked": checked,
                "status": "failed" if any(not c["ok"] for c in checked.values()) else "ok",
            }
        )
        return observation

    def upload(self, filename: str) -> None:
        path = pathlib.Path(self.args.fixtures) / filename
        self.ab.run("upload", "[data-testid='stFileUploaderDropzoneInput']", str(path))
        self.ab.run("wait", "4000")

    def set_group(self, option: str) -> None:
        ref = self.ab.find_ref("combobox", "Group by")
        self.ab.run("click", "@" + ref)
        self.ab.run("wait", "1200")
        option_ref = _find_option_ref(self.ab, option)
        if option_ref:
            self.ab.run("click", "@" + option_ref)
        else:
            self.ab.run("find", "text", option, "click")
        self.ab.run("wait", "4000")

    def set_slider(self, presses: int) -> None:
        ref = self.ab.find_ref("slider", "Minimum amount")
        self.ab.run("focus", "@" + ref)
        for _ in range(presses):
            self.ab.run("press", "ArrowRight")
        self.ab.run("wait", "4000")

    def set_checkbox(self, checked: bool) -> None:
        ref = self.ab.find_ref("checkbox", "Include unknown region")
        self.ab.run("scrollintoview", "@" + ref)
        time.sleep(0.4)
        self.ab.run("check" if checked else "uncheck", "@" + ref)
        self.ab.run("wait", "4000")

    def shot(self, name: str) -> None:
        self.ab.run("screenshot", str(self.out_dir / name))

    def current_tab_index(self) -> int:
        """Index of the focused tab, as agent-browser reports it."""
        out = self.ab.run("tab")
        m = re.search(r"->\s*\[(\d+)\]", out.replace("\u2192", "->"))
        return int(m.group(1)) if m else 0

    # -- scenarios -------------------------------------------------------
    def scenario_closed_loop(self) -> None:
        self.mark(
            "startup",
            "a fresh page load starts a new session and renders the empty state",
            {"table_present": False, "chart_present": False},
        )
        self.shot("01-startup.png")
        self.upload("sales_basic.csv")
        self.mark(
            "upload",
            "uploaded sales_basic.csv",
            {
                "table_present": True,
                "chart_present": True,
                "chart_bars": 4,
                "table_cells": ["Books", "3", "245.75", "81.92", "Games", "3", "409.48", "136.49"],
            },
        )
        self.shot("02-upload.png")
        self.set_group("region")
        self.mark(
            "selector",
            "set 'Group by' to region",
            {
                "selectbox_value": "region",
                "chart_bars": 6,
                "table_cells": ["(missing)", "1", "88", "88", "East", "2", "209.49", "104.75"],
            },
        )
        self.shot("03-selector-region.png")
        self.set_slider(10)
        self.mark(
            "slider",
            "moved 'Minimum amount' to 100",
            {
                "slider_value": "100",
                "chart_bars": 3,
                "table_cells": ["East", "1", "149.5", "149.5", "North", "1", "120.5", "120.5"],
            },
        )
        self.shot("04-slider-100.png")
        self.set_checkbox(False)
        self.mark(
            "checkbox",
            "unchecked 'Include unknown region'",
            {
                "checkbox_checked": False,
                "chart_bars": 3,
                "table_cells": ["East", "1", "149.5", "149.5", "North", "1", "120.5", "120.5"],
            },
        )
        self.shot("05-checkbox-off.png")
        self.ab.click("[data-testid='stButton']")
        self.ab.run("wait", "4000")
        self.mark(
            "pulse",
            "clicked Pulse",
            {"texts": ["Script runs: 15", "Pulses: 1", "Applied note:"]},
        )
        self.shot("06-pulse.png")

    def scenario_errors(self) -> None:
        """Empty and malformed CSV, and a filter that matches nothing."""
        self.upload("sales_malformed.csv")
        self.mark(
            "malformed",
            "uploaded sales_malformed.csv: a hard structural failure",
            {
                "table_present": False,
                "chart_present": False,
                "alerts": ["Could not parse the uploaded CSV: row 3: expected 8 fields, found 7"],
            },
        )
        self.shot("07-malformed.png")
        self.upload("sales_with_missing.csv")
        self.mark(
            "soft-failure",
            "uploaded sales_with_missing.csv: a soft failure, two rows excluded",
            {
                "table_present": True,
                "chart_bars": 4,
                "table_cells": ["Books", "2", "200.5", "100.25", "Games", "3", "409.48", "136.49"],
                "alerts": ["2 row(s) with an unusable 'amount' were excluded from the aggregation."],
            },
        )
        self.shot("08-soft-failure.png")
        self.upload("sales_empty.csv")
        self.mark(
            "empty",
            "uploaded sales_empty.csv: a header with no rows",
            {"table_present": True, "chart_present": False, "table_cells": []},
        )
        self.shot("09-empty.png")
        self.upload("sales_basic.csv")
        self.ab.run("wait", "2000")
        self.set_slider(20)
        self.mark(
            "filter-matches-nothing",
            "moved 'Minimum amount' to 200 so that no row matches",
            {
                "table_present": True,
                "chart_present": False,
                "alerts": ["No rows match the current filters."],
            },
        )
        self.shot("10-filter-no-match.png")

    def scenario_form(self) -> None:
        """Form-gated input: typing must not rerun, submit must."""
        self.upload("sales_basic.csv")
        before = self.mark("form-before", "state before typing into the form", {})
        runs_before = _runs(before)

        note_ref = self.ab.find_ref("textbox", "Note")
        self.ab.run("scrollintoview", "@" + note_ref)
        time.sleep(0.4)
        self.ab.run("fill", "@" + note_ref, "hello")
        self.ab.run("wait", "3000")
        typed = self.mark(
            "form-typed",
            "typed 'hello' into the form WITHOUT submitting: the server must not be contacted",
            {"applied_note": ""},
        )
        runs_after_typing = _runs(typed)
        if runs_after_typing != runs_before:
            self.failures.append(
                {
                    "step": "form-typed",
                    "check": "run_count",
                    "expected": runs_before,
                    "actual": runs_after_typing,
                }
            )
        self.shot("11-form-typed.png")

        note_ref = self.ab.find_ref("textbox", "Note")
        self.ab.run("fill", "@" + note_ref, "hello")
        submit_ref = self.ab.find_ref("button", "Apply note")
        self.ab.run("click", "@" + submit_ref)
        self.ab.run("wait", "4000")
        self.mark(
            "form-submitted",
            "submitted the form: exactly one rerun and the note is applied",
            {"applied_note": "hello"},
        )
        self.shot("12-form-submitted.png")

    def scenario_tabs(self) -> None:
        """Two real tabs: two sessions that cannot observe each other."""
        tab_a_index = self.current_tab_index()
        self.upload("sales_basic.csv")
        for _ in range(3):
            self.ab.click("[data-testid='stButton']")
            self.ab.run("wait", "1500")
        self.mark(
            "tab-a",
            "tab A after the upload and three Pulse clicks",
            {"pulses": "3", "table_present": True},
        )

        before_ids = {t["id"] for t in page_targets(self.cdp_browser_url, self.host)}
        self.ab.run("tab", "new", self.args.url)
        self.ab.run("wait", "6000")
        new_targets = [
            t for t in page_targets(self.cdp_browser_url, self.host) if t["id"] not in before_ids
        ]
        if new_targets:
            self.recorders.append(CDP(new_targets[0]["webSocketDebuggerUrl"], label="tab-b"))
            self.recorders[-1].start()
            time.sleep(1.0)
        self.mark(
            "tab-b",
            "tab B, freshly opened: its own session, its own counters, no uploaded file",
            {"pulses": "0", "script_runs": "1", "table_present": False},
        )
        self.shot("13-tab-b.png")

        self.upload("sales_basic.csv")
        self.mark(
            "tab-b-uploaded",
            "tab B uploaded the fixture: its own data, independent of tab A",
            {"table_present": True, "chart_bars": 4},
        )
        self.set_group("region")
        self.mark(
            "tab-b-filtered",
            "tab B after changing its own filter",
            {"selectbox_value": "region", "chart_bars": 6},
        )
        self.shot("14-tab-b-filtered.png")

        self.ab.run("tab", str(tab_a_index))
        self.ab.run("wait", "2500")
        self.mark(
            "tab-a-unchanged",
            "tab A after tab B changed its filter: tab A must be unaffected",
            {
                "pulses": "3",
                "selectbox_value": "category",
                "table_cells": ["Books", "3", "245.75", "81.92"],
            },
        )
        self.shot("15-tab-a-unchanged.png")

        session_a = _session_ids(self.recorders, "tab-a")
        session_b = _session_ids(self.recorders, "tab-b")
        if session_a and session_b and set(session_a) & set(session_b):
            self.failures.append(
                {
                    "step": "tabs",
                    "check": "session_ids",
                    "expected": "disjoint session ids",
                    "actual": f"shared: {sorted(set(session_a) & set(session_b))}",
                }
            )
        self.notes.append(
            f"tab A session id(s): {session_a or 'not captured'}; "
            f"tab B session id(s): {session_b or 'not captured'}"
        )

    def scenario_reconnect(self) -> None:
        """A real connection fault: the live socket is closed, then reconnected.

        The socket is closed for real from the page side, so the server sees a
        genuine disconnect and the frontend runs its own reconnect path.  The
        page is NEVER reloaded here: a reload would start a new session and
        would destroy the very thing this scenario measures.
        """
        self.upload("sales_basic.csv")
        for _ in range(2):
            self.ab.click("[data-testid='stButton']")
            self.ab.run("wait", "1500")
        before = self.mark(
            "reconnect-before",
            "state before the socket is closed",
            {"pulses": "2", "table_present": True},
        )
        session_before = _session_ids(self.recorders, "tab-a")
        recorder = self.recorders[0]
        connection_before_fault = self.connection_index_before()

        closed = recorder.call(
            "Runtime.evaluate",
            {"expression": "window.__stWs ? (window.__stWs.close(), 'closed') : 'no socket'"},
            timeout=5.0,
        )
        self.notes.append(f"live socket closed through Runtime.evaluate: {closed}")
        close_value = _evaluate_value(closed)
        if not close_value or "closed" not in str(close_value):
            self.failures.append(
                {
                    "step": "reconnect",
                    "check": "socket_closed",
                    "expected": "the live socket to be closed",
                    "actual": str(closed)[:200],
                }
            )
        time.sleep(3)
        self.mark("reconnect-closed", "state right after the socket was closed", {})
        self.shot("16-reconnect-closed.png")

        # Wait for the frontend's own reconnect.  Bounded: no reload, ever.
        deadline = time.time() + 40
        reconnect_handshake = None
        while time.time() < deadline:
            for handshake in _handshakes(recorder):
                if len(handshake.get("entries", [])) >= 3:
                    reconnect_handshake = handshake
                    break
            if reconnect_handshake:
                break
            time.sleep(1.0)

        time.sleep(4)
        after = self.mark(
            "reconnect-after",
            "state after the frontend reconnected: the same session must still be there",
            {"pulses": "2", "table_present": True},
        )
        self.shot("17-reconnect-after.png")

        # A reconnect is only proved by using the reconnected connection: click
        # the button and require a true trigger and a server answer on the NEW
        # connection.  The DOM alone proves nothing, because a stale DOM looks
        # exactly like a live session.
        start = self.recorders[0].frame_count()
        self.ab.click("[data-testid='stButton']")
        self.ab.run("wait", "3000")
        end = self.recorders[0].frame_count()
        self.click_windows.append(
            {
                "click": "post-reconnect",
                "start": start,
                "end": end,
                "require_new_connection": True,
                "connection_before": connection_before_fault,
            }
        )
        self.mark(
            "reconnect-click",
            "clicked the button on the reconnected session: the counter must advance",
            {"pulses": "3"},
        )
        self.shot("18-reconnect-click.png")

        handshakes = _handshakes(recorder)
        third_entry = [h for h in handshakes if len(h.get("entries", [])) >= 3]
        session_after = _session_ids(self.recorders, "tab-a")
        self.notes.append(
            f"handshakes observed: {len(handshakes)}; with a third subprotocol entry: {len(third_entry)}; "
            f"session id before: {session_before or 'not captured'}; after: {session_after or 'not captured'}"
        )
        if reconnect_handshake:
            self.notes.append(
                "reconnect handshake Sec-WebSocket-Protocol: "
                + str(reconnect_handshake["headers"].get("Sec-WebSocket-Protocol"))
            )
        if not third_entry:
            self.failures.append(
                {
                    "step": "reconnect",
                    "check": "third_subprotocol_entry",
                    "expected": "a handshake with three subprotocol entries",
                    "actual": f"handshakes: {[h.get('entries') for h in handshakes]}",
                }
            )
        # The recorder keeps every session id it ever saw, so compare the
        # newest one: after a reconnect it must be the same session.
        if session_before and session_after and session_before[-1] != session_after[-1]:
            self.failures.append(
                {
                    "step": "reconnect",
                    "check": "same_session",
                    "expected": f"the session {session_before[-1]} to be reused",
                    "actual": f"a different session {session_after[-1]}",
                }
            )
        if _pulses(before) and _pulses(after) and _pulses(before) != _pulses(after):
            self.failures.append(
                {
                    "step": "reconnect",
                    "check": "counter_preserved",
                    "expected": _pulses(before),
                    "actual": _pulses(after),
                }
            )

    def scenario_refresh(self) -> None:
        """A page reload: the browser drops its in-memory session id, so the
        server issues a NEW session and the state is gone."""
        self.upload("sales_basic.csv")
        for _ in range(2):
            self.ab.click("[data-testid='stButton']")
            self.ab.run("wait", "1500")
        before = self.mark(
            "refresh-before",
            "state before the reload",
            {"pulses": "2", "table_present": True},
        )
        session_before = _session_ids(self.recorders, "tab-a")

        self.ab.run("reload")
        self.ab.run("wait", "8000")
        after = self.mark(
            "refresh-after",
            "state after the reload: a new session, so the state is gone",
            {"pulses": "0", "script_runs": "1", "table_present": False},
        )
        self.shot("18-refresh-after.png")

        handshakes = _handshakes(self.recorders[0])
        session_after = _session_ids(self.recorders, "tab-a")
        self.notes.append(
            f"handshakes observed: {len(handshakes)}; "
            f"subprotocol entry counts: {[len(h.get('entries', [])) for h in handshakes]}; "
            f"session id before: {session_before or 'not captured'}; after: {session_after or 'not captured'}"
        )
        if session_before and session_after and session_before[-1] == session_after[-1]:
            self.failures.append(
                {
                    "step": "refresh",
                    "check": "new_session",
                    "expected": f"a session id other than {session_before[-1]}",
                    "actual": f"the same session {session_after[-1]}",
                }
            )
        if _pulses(before) and _pulses(after) and _pulses(before) == _pulses(after):
            self.failures.append(
                {
                    "step": "refresh",
                    "check": "counter_reset",
                    "expected": "a reset counter",
                    "actual": _pulses(after),
                }
            )

    def scenario_smoke(self) -> None:
        """A minimal liveness check for any Streamlit-compatible server.

        It checks that the page renders, that the button can be clicked, that
        the click reaches the server as a widget trigger, and that the
        connection keeps working afterwards.  It deliberately claims nothing
        beyond that: it is not a data-loop journey.
        """
        self.mark(
            "smoke-open",
            "the page rendered",
            {"has_button": True},
        )
        self.shot("19-smoke-open.png")

        for index in range(self.args.clicks):
            start = self.recorders[0].frame_count()
            self.ab.click("[data-testid='stButton']")
            self.ab.run("wait", "2500")
            end = self.recorders[0].frame_count()
            self.click_windows.append({"click": index + 1, "start": start, "end": end})
            self.mark(
                f"smoke-click-{index + 1}",
                f"clicked the button ({index + 1}/{self.args.clicks})",
                {},
            )
        self.mark(
            "smoke-still-operable",
            "after every click the page must still be operable",
            {"has_button": True},
        )
        self.shot("20-smoke-after-clicks.png")

        triggers = [
            frame
            for frame in self.recorders[0].take()
            if frame.get("method") == "Network.webSocketFrameSent"
        ]
        self.notes.append(
            f"client->server frames observed during the smoke clicks: {len(triggers)}"
        )
        self.notes.append(f"button traces: {len(self.button_traces())}")

    def connection_index_before(self) -> int:
        """The index of the connection that was alive before the fault."""
        ids: list[str] = []
        for event in self.recorders[0].take():
            if event.get("method") in (
                "Network.webSocketCreated",
                "Network.webSocketWillSendHandshakeRequest",
            ):
                request_id = event.get("params", {}).get("requestId")
                if request_id and request_id not in ids:
                    ids.append(request_id)
        return max(len(ids) - 1, 0)

    def button_traces(self) -> list[dict]:
        found = []
        for recorder in self.recorders:
            for event in recorder.take():
                if event.get("method") != "Network.webSocketFrameSent":
                    continue
                payload = _decode_payload(
                    event["params"].get("response", {}).get("opcode"),
                    event["params"].get("response", {}).get("payloadData", ""),
                )
                decoded = _safe(summarise_back, payload)
                if decoded.get("type") != "rerun_script":
                    continue
                for widget in decoded["rerun_script"]["widget_states"]:
                    if widget.get("value_field") == "trigger_value":
                        found.append({"widget_id": widget["id"], "value": widget["value"]})
        return found

    # -- driver ----------------------------------------------------------
    def run(self) -> int:
        self.ab.run("open", self.args.url)
        self.ab.run("wait", "3000")
        self.cdp_browser_url = self.ab.run("get", "cdp-url")
        import urllib.parse

        self.host = urllib.parse.urlparse(self.args.url).hostname or "localhost"
        targets = page_targets(self.cdp_browser_url, self.host)
        if not targets:
            raise SystemExit(f"no page target for host {self.host!r}")
        self.page_title = targets[0].get("title", "")
        self.chrome = browser_version(self.cdp_browser_url)
        self.recorders.append(CDP(targets[0]["webSocketDebuggerUrl"], label="tab-a"))
        self.recorders[0].start()
        time.sleep(1.0)
        if self.hook_source:
            self.recorders[0].call(
                "Page.addScriptToEvaluateOnNewDocument", {"source": self.hook_source}
            )
        self.ab.run("reload")
        self.ab.run("wait", "5000")

        getattr(self, f"scenario_{self.args.scenario.replace('-', '_')}")()

        deadline = time.time() + 20
        while time.time() < deadline:
            if any(
                e.get("method") == "Network.webSocketFrameReceived"
                and e.get("params", {}).get("response", {}).get("opcode") == 2
                for r in self.recorders
                for e in r.take()
            ):
                time.sleep(1.5)
                break
            time.sleep(0.5)
        for recorder in self.recorders:
            recorder.stop()

        events = [e for recorder in self.recorders for e in recorder.take()]
        trace = self.build_trace(events)
        name = "trace.json" if self.args.scenario == "closed-loop" else f"trace-{self.args.scenario}.json"
        out = self.out_dir / name
        out.write_text(
            json.dumps(trace, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n"
        )
        print(f"wrote {out}")
        print(f"  scenario: {self.args.scenario}  frames: {len(trace['frames'])}")
        print(f"  http requests (excluding the static bundle): {len(trace['http_requests'])}")
        print(f"  step failures: {len(self.failures)}")
        for failure in self.failures:
            print(f"    FAIL {failure['step']}.{failure['check']}: "
                  f"expected {failure['expected']!r}, got {failure['actual']!r}")
        for note in self.notes:
            print(f"  note: {note}")
        return 1 if self.failures else 0

    def build_trace(self, events: list[dict]) -> dict:
        # Every WebSocket connection is kept separately, keyed by its CDP
        # requestId.  Merging them per tab would lose the first handshake and
        # would make it impossible to tell which connection a frame belongs
        # to -- which is exactly what a reconnect claim depends on.
        connections: dict[str, dict] = {}
        connection_order: list[str] = []

        def connection(request_id: str) -> dict:
            record = connections.get(request_id)
            if record is None:
                record = {
                    "index": len(connection_order),
                    "request_id": request_id,
                    "target": "tab-a",
                    "url": None,
                    "request_headers": {},
                    "response_status": None,
                    "response_headers": {},
                    "subprotocol_entries": [],
                    "closed": False,
                    "frames_sent": 0,
                    "frames_received": 0,
                }
                connections[request_id] = record
                connection_order.append(request_id)
            return record

        frames: list[dict] = []
        http_requests: list[dict] = []
        static_bundle_requests = 0

        for event in events:
            method = event.get("method")
            params = event.get("params", {})
            target = event.get("_target", "tab-a")
            if method == "Network.webSocketWillSendHandshakeRequest":
                record = connection(params.get("requestId", ""))
                record["target"] = target
                record["request_headers"] = params.get("request", {}).get("headers", {})
                protocol = record["request_headers"].get("Sec-WebSocket-Protocol", "")
                record["subprotocol_entries"] = [
                    entry.strip() for entry in protocol.split(",") if entry.strip()
                ]
            elif method == "Network.webSocketCreated":
                record = connection(params.get("requestId", ""))
                record["target"] = target
                record["url"] = params.get("url")
            elif method == "Network.webSocketHandshakeResponseReceived":
                record = connection(params.get("requestId", ""))
                record["response_status"] = params.get("response", {}).get("status")
                record["response_headers"] = params.get("response", {}).get("headers", {})
            elif method == "Network.webSocketClosed":
                connection(params.get("requestId", ""))["closed"] = True
            elif method in ("Network.webSocketFrameSent", "Network.webSocketFrameReceived"):
                frame = params.get("response", {})
                payload = _decode_payload(frame.get("opcode"), frame.get("payloadData", ""))
                direction = "client->server" if method.endswith("Sent") else "server->client"
                decoder = summarise_back if direction == "client->server" else summarise_forward
                record = connection(params.get("requestId", ""))
                if direction == "client->server":
                    record["frames_sent"] += 1
                else:
                    record["frames_received"] += 1
                frames.append(
                    {
                        "target": target,
                        "connection": record["index"],
                        "direction": direction,
                        "bytes": len(payload),
                        "sha256": hashlib.sha256(payload).hexdigest(),
                        "decoded": _safe(decoder, payload),
                    }
                )
            elif method == "Network.requestWillBeSent":
                request = params.get("request", {})
                url = request.get("url", "")
                if "/static/" in url:
                    static_bundle_requests += 1
                    continue
                entry = {
                    "target": target,
                    "method": request.get("method"),
                    "url": url,
                    "resource_type": params.get("type"),
                    "request_headers": {
                        k: v for k, v in request.get("headers", {}).items()
                        if k.lower() in ("content-type", "content-length", "origin")
                    },
                }
                post = request.get("postData")
                if post:
                    entry["multipart_preamble"] = post[:400]
                    entry["post_data_bytes"] = len(post)
                http_requests.append(entry)
            elif method == "Network.responseReceived":
                url = params.get("response", {}).get("url", "")
                if "/static/" in url:
                    continue
                for entry in http_requests:
                    if entry["url"] == url and "status" not in entry:
                        entry["status"] = params.get("response", {}).get("status")
                        entry["mime_type"] = params.get("response", {}).get("mimeType")

        handshakes = [connections[request_id] for request_id in connection_order]

        self.failures.extend(verify_click_windows(frames, self.click_windows))
        for window in self.click_windows:
            self.notes.append(
                f"click window {window.get('click')}: frames {window['start']}..{window['end']}"
            )

        button_trace = []
        for index, frame in enumerate(frames):
            decoded = frame["decoded"]
            if decoded.get("message") != "BackMsg" or decoded.get("type") != "rerun_script":
                continue
            for widget in decoded["rerun_script"]["widget_states"]:
                if widget.get("value_field") == "trigger_value":
                    button_trace.append(
                        {
                            "frame_index": index,
                            "target": frame["target"],
                            "direction": frame["direction"],
                            "widget_id": widget["id"],
                            "value_field": widget["value_field"],
                            "value": widget["value"],
                        }
                    )

        return {
            "schema_version": 2,
            "contract_id": "C-P0-04",
            "kind": "python-reference-browser-trace",
            "scenario": self.args.scenario,
            "scope": (
                "PYTHON SIDE ONLY. The Rust implementation is not exercised and is not "
                "verified by this trace. This is black-box evidence over the real HTTP, "
                "WebSocket and protobuf surface of the reference application."
            ),
            "generated_by": "tests/reference/capture_browser_trace.py",
            "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "app_url": self.args.url,
            "page_title": self.page_title,
            "capture": {
                "browser": self.chrome,
                "agent_browser": _ab_version(self.ab.exe),
                "method": (
                    "agent-browser drives the UI; HTTP requests and WebSocket frames are read "
                    "from the Chrome DevTools Protocol endpoint of the same browser instance"
                ),
                "frame_decode": "official streamlit 1.66.1 protobuf (streamlit.proto.*)",
                "end_condition": (
                    "the last script_finished frame plus the final DOM observation; the "
                    "long-lived Streamlit WebSocket is never waited on for EOF"
                ),
                "commands": self.ab.commands,
                "capture_exit_code": 0 if not self.failures else 1,
            },
            "versions": {
                "streamlit": __import__("streamlit").__version__,
                "python": sys.version.split()[0],
                "chrome": self.chrome,
                "agent_browser": _ab_version(self.ab.exe),
            },
            "websocket_handshakes": handshakes,
            "websocket_handshake": handshakes[0] if handshakes else None,
            "http_requests": http_requests,
            "static_bundle_requests_counted_not_stored": static_bundle_requests,
            "button_trace": button_trace,
            "steps": self.steps,
            "failures": self.failures,
            "notes": self.notes,
            "frames": frames,
        }


def _evaluate_value(response: dict):
    """Pull the value out of a CDP Runtime.evaluate response.

    The payload is nested: {"result": {"result": {"type": ..., "value": ...}}}.
    """
    if not isinstance(response, dict):
        return None
    outer = response.get("result")
    if not isinstance(outer, dict):
        return None
    inner = outer.get("result")
    if isinstance(inner, dict):
        return inner.get("value")
    return outer.get("value")


#: ForwardMsg.ScriptFinishedStatus.FINISHED_SUCCESSFULLY.  The other values
#: are NOT a successful completion of the script run a click triggered:
#: 1 = FINISHED_WITH_COMPILE_ERROR, 2 = FINISHED_EARLY_FOR_RERUN and
#: 3 = FINISHED_FRAGMENT_RUN_SUCCESSFULLY (a partial run, not this run).
SCRIPT_FINISHED_SUCCESS = 0


def _is_successful_completion(frame: dict) -> bool:
    """True only for a script_finished that reports a real, successful run."""
    decoded = frame.get("decoded") or {}
    if decoded.get("type") != "script_finished":
        return False
    finished = decoded.get("script_finished") or {}
    return finished.get("status") == SCRIPT_FINISHED_SUCCESS


def verify_click_windows(frames, clicks):
    """Check that every click really reached the server and was answered.

    ``frames`` is the finished trace's frame list; ``clicks`` is a list of
    ``{"click": label, "start": i, "end": j}`` windows into it.  For each click
    the window must contain

    * a client->server frame whose widget state carries ``trigger_value`` with
      the value ``True`` -- a ``False`` trigger proves nothing;
    * AFTER that trigger, on the SAME connection, a ``script_finished`` whose
      status is ``FINISHED_SUCCESSFULLY``.  A ``session_status_changed`` with
      ``running=true`` is not a completion, a ``script_finished`` that arrives
      before the trigger is not a completion, and a ``script_finished`` that
      reports a compile error, an early rerun or a fragment run is not a
      success;
    * and, when the window asks for it, on a connection other than the one
      that was alive before -- that is what a reconnect claim rests on.

    Returns the list of failures; an empty list means every click passed.
    """
    failures: list[dict] = []
    for window in clicks:
        label = window.get("click")
        segment = frames[window["start"] : window["end"]]

        trigger_position = None
        trigger_connection = None
        false_triggers = []
        for offset, frame in enumerate(segment):
            if frame.get("direction") != "client->server":
                continue
            decoded = frame.get("decoded") or {}
            if decoded.get("type") != "rerun_script":
                continue
            for widget in decoded.get("rerun_script", {}).get("widget_states", []):
                if widget.get("value_field") != "trigger_value":
                    continue
                item = {"widget_id": widget.get("id"), "connection": frame.get("connection")}
                if widget.get("value") is True:
                    trigger_position = offset
                    trigger_connection = frame.get("connection")
                else:
                    false_triggers.append(item)

        if trigger_position is None:
            failures.append(
                {
                    "step": f"click-{label}",
                    "check": "true_trigger",
                    "expected": "a trigger_value=true for the button inside the click window",
                    "actual": (
                        f"no true trigger; false triggers: {false_triggers or 'none'}; "
                        f"frames in window: {len(segment)}"
                    ),
                }
            )

        if trigger_position is None:
            # Without a trigger there is nothing the server could have
            # completed, so both requirements are unmet.
            failures.append(
                {
                    "step": f"click-{label}",
                    "check": "server_response",
                    "expected": (
                        "a script_finished with status "
                        f"{SCRIPT_FINISHED_SUCCESS} (FINISHED_SUCCESSFULLY) after the "
                        "trigger, on the same connection"
                    ),
                    "actual": (
                        "the click produced no true trigger, so no successful completion "
                        f"could follow; frames in window: {len(segment)}"
                    ),
                }
            )

        # Only frames AFTER the trigger can complete it.
        successful_after = []
        unsuccessful = []
        for offset in range((trigger_position or -1) + 1, len(segment)):
            frame = segment[offset]
            if frame.get("direction") != "server->client":
                continue
            if _is_successful_completion(frame):
                successful_after.append(frame)
            elif (frame.get("decoded") or {}).get("type") == "script_finished":
                unsuccessful.append((frame.get("decoded") or {}).get("script_finished") or {})

        same_connection = [
            frame for frame in successful_after if frame.get("connection") == trigger_connection
        ]
        if trigger_position is not None and not same_connection:
            if successful_after:
                failures.append(
                    {
                        "step": f"click-{label}",
                        "check": "same_connection",
                        "expected": (
                            f"the successful completion on connection {trigger_connection}"
                        ),
                        "actual": (
                            "the successful completion came on connection "
                            f"{sorted({str(f.get('connection')) for f in successful_after})}"
                        ),
                    }
                )
            else:
                failures.append(
                    {
                        "step": f"click-{label}",
                        "check": "server_response",
                        "expected": (
                            "a script_finished with status "
                            f"{SCRIPT_FINISHED_SUCCESS} (FINISHED_SUCCESSFULLY) after the "
                            "trigger, on the same connection"
                        ),
                        "actual": (
                            "no successful completion after the trigger; "
                            f"non-successful script_finished frames: {unsuccessful or 'none'}; "
                            f"frames in window: {len(segment)}"
                        ),
                    }
                )

        if window.get("require_new_connection"):
            before = window.get("connection_before")
            if before is not None and trigger_connection == before:
                failures.append(
                    {
                        "step": f"click-{label}",
                        "check": "new_connection",
                        "expected": f"a connection other than {before}",
                        "actual": f"the click travelled on connection {trigger_connection}",
                    }
                )
    return failures


def _find_retry_ref(ab: AB) -> str | None:
    """Look for the reconnect affordance the frontend shows after a close."""
    for entry in ab.snapshot_refs():
        name = entry["name"].lower()
        if entry["role"] in ("button", "link") and any(
            word in name for word in ("retry", "reconnect", "try again", "rerun")
        ):
            return entry["ref"]
    return None


def _session_ids(recorders, label: str) -> list[str]:
    found = []
    for recorder in recorders:
        if recorder.label != label:
            continue
        for event in recorder.take():
            if event.get("method") != "Network.webSocketFrameReceived":
                continue
            payload = _decode_payload(
                event["params"].get("response", {}).get("opcode"),
                event["params"].get("response", {}).get("payloadData", ""),
            )
            decoded = _safe(summarise_forward, payload)
            if decoded.get("type") == "new_session":
                sid = decoded["new_session"].get("session_id")
                if sid and sid not in found:
                    found.append(sid)
    return found


def _handshakes(recorder) -> list[dict]:
    out = []
    for event in recorder.take():
        if event.get("method") != "Network.webSocketWillSendHandshakeRequest":
            continue
        headers = event.get("params", {}).get("request", {}).get("headers", {})
        protocol = headers.get("Sec-WebSocket-Protocol", "")
        out.append(
            {"headers": headers, "entries": [p.strip() for p in protocol.split(",") if p.strip()]}
        )
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True, help="URL of the running reference app")
    parser.add_argument("--out", required=True, help="output directory for the trace")
    parser.add_argument("--scenario", default="closed-loop", choices=SCENARIOS)
    parser.add_argument(
        "--clicks", type=int, default=3, help="how many times the smoke scenario clicks the button"
    )
    parser.add_argument(
        "--fixtures",
        default=str(REPO_ROOT / "tests" / "fixtures" / "csv"),
        help="directory holding the CSV fixtures",
    )
    args = parser.parse_args()
    return Capture(args).run()


if __name__ == "__main__":
    raise SystemExit(main())
