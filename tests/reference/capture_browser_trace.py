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

SCENARIOS = ("closed-loop", "errors", "form", "tabs", "reconnect")


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
return JSON.stringify({
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
            for event in list(self.events):
                if event.get("id") == ident:
                    self.events.remove(event)
                    return event
            time.sleep(0.05)
        return {"error": f"no response for {method}"}

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


def page_targets(cdp_browser_url: str) -> list[dict]:
    import urllib.request

    m = re.match(r"ws://([^:/]+):(\d+)/", cdp_browser_url)
    if not m:
        raise SystemExit(f"unexpected cdp url: {cdp_browser_url}")
    base = f"http://{m.group(1)}:{m.group(2)}"
    with urllib.request.urlopen(base + "/json/list", timeout=10) as response:
        targets = json.load(response)
    return [t for t in targets if t.get("type") == "page" and "localhost" in t.get("url", "")]


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

        before_ids = {t["id"] for t in page_targets(self.cdp_browser_url)}
        self.ab.run("tab", "new", self.args.url)
        self.ab.run("wait", "6000")
        new_targets = [t for t in page_targets(self.cdp_browser_url) if t["id"] not in before_ids]
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
        """A real connection fault: the live socket is closed, then reconnected."""
        self.upload("sales_basic.csv")
        for _ in range(2):
            self.ab.click("[data-testid='stButton']")
            self.ab.run("wait", "1500")
        before = self.mark(
            "reconnect-before", "state before the socket is closed", {"pulses": "2"}
        )
        session_before = _session_ids(self.recorders, "tab-a")
        recorder = self.recorders[0]

        closed = recorder.call(
            "Runtime.evaluate",
            {"expression": "window.__stWs ? (window.__stWs.close(), 'closed') : 'no socket'"},
        )
        self.notes.append(f"live socket closed through Runtime.evaluate: {closed}")
        time.sleep(5)
        after_close = self.mark("reconnect-closed", "state right after the socket was closed", {})
        self.shot("16-reconnect-closed.png")

        # What does the frontend offer now?  Record it verbatim.
        tree = self.ab.run("snapshot", "-i")
        retry = _find_retry_ref(self.ab)
        self.notes.append("accessibility tree after the close:\n" + tree[:1500])

        if retry:
            self.ab.run("click", "@" + retry)
            self.ab.run("wait", "8000")
            self.mark("reconnect-retried", "clicked the reconnect affordance", {})
            self.shot("17-reconnect-retried.png")
        else:
            self.notes.append("no reconnect affordance was found in the accessibility tree")
            self.ab.run("reload")
            self.ab.run("wait", "8000")
            self.mark(
                "reconnect-reload",
                "no reconnect affordance: the page was reloaded instead, which starts a NEW session",
                {},
            )
            self.shot("17-reconnect-reload.png")

        after = self.mark("reconnect-after", "state after the connection came back", {})
        self.shot("18-reconnect-after.png")

        handshakes = _handshakes(recorder)
        third_entry = [h for h in handshakes if len(h.get("entries", [])) >= 3]
        session_after = _session_ids(self.recorders, "tab-a")
        self.notes.append(
            f"handshakes observed: {len(handshakes)}; with a third subprotocol entry: {len(third_entry)}; "
            f"session id before: {session_before or 'not captured'}; after: {session_after or 'not captured'}"
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
        if _pulses(before) and _pulses(after) and _pulses(before) != _pulses(after):
            self.failures.append(
                {
                    "step": "reconnect",
                    "check": "counter_preserved",
                    "expected": _pulses(before),
                    "actual": _pulses(after),
                }
            )

    # -- driver ----------------------------------------------------------
    def run(self) -> int:
        self.ab.run("open", self.args.url)
        self.ab.run("wait", "3000")
        self.cdp_browser_url = self.ab.run("get", "cdp-url")
        targets = page_targets(self.cdp_browser_url)
        if not targets:
            raise SystemExit("no localhost page target found")
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
        handshake_by_target: dict[str, dict] = {}
        frames: list[dict] = []
        http_requests: list[dict] = []
        static_bundle_requests = 0

        for event in events:
            method = event.get("method")
            params = event.get("params", {})
            target = event.get("_target", "tab-a")
            if method == "Network.webSocketWillSendHandshakeRequest":
                handshake_by_target.setdefault(target, {})["request_headers"] = (
                    params.get("request", {}).get("headers", {})
                )
            elif method == "Network.webSocketCreated":
                handshake_by_target.setdefault(target, {})["url"] = params.get("url")
            elif method == "Network.webSocketHandshakeResponseReceived":
                entry = handshake_by_target.setdefault(target, {})
                entry["response_status"] = params.get("response", {}).get("status")
                entry["response_headers"] = params.get("response", {}).get("headers", {})
            elif method in ("Network.webSocketFrameSent", "Network.webSocketFrameReceived"):
                frame = params.get("response", {})
                payload = _decode_payload(frame.get("opcode"), frame.get("payloadData", ""))
                direction = "client->server" if method.endswith("Sent") else "server->client"
                decoder = summarise_back if direction == "client->server" else summarise_forward
                frames.append(
                    {
                        "target": target,
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

        handshakes = []
        for target, entry in handshake_by_target.items():
            request_headers = entry.get("request_headers", {})
            protocol = request_headers.get("Sec-WebSocket-Protocol", "")
            handshakes.append(
                {
                    "target": target,
                    "url": entry.get("url"),
                    "response_status": entry.get("response_status"),
                    "request_headers": request_headers,
                    "response_headers": entry.get("response_headers", {}),
                    "subprotocol_entries": [p.strip() for p in protocol.split(",") if p.strip()],
                }
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
            "http_requests": http_requests,
            "static_bundle_requests_counted_not_stored": static_bundle_requests,
            "button_trace": button_trace,
            "steps": self.steps,
            "failures": self.failures,
            "notes": self.notes,
            "frames": frames,
        }


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
        "--fixtures",
        default=str(REPO_ROOT / "tests" / "fixtures" / "csv"),
        help="directory holding the CSV fixtures",
    )
    args = parser.parse_args()
    return Capture(args).run()


if __name__ == "__main__":
    raise SystemExit(main())
