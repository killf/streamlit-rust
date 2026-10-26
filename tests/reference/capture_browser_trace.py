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
import math
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

SCENARIOS = (
    "closed-loop",
    "errors",
    "form",
    "tabs",
    "reconnect",
    "refresh",
    "smoke",
    "counter",
    "status",
    "widgets",
)


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
        raw = self.ab.run("eval", OBSERVE_JS)
        try:
            value = json.loads(raw)
        except json.JSONDecodeError:
            return {"raw": raw[:400]}
        if isinstance(value, str):
            try:
                value = json.loads(value)
            except json.JSONDecodeError:
                return {"raw": raw[:400]}
        return value if isinstance(value, dict) else {"value": value}
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


def require_decoder() -> None:
    """Refuse to capture when the protobuf decoder is not importable.

    The decoder needs the pinned reference interpreter (streamlit 1.66.1 with
    its protobuf definitions).  Without it every frame is recorded as
    "undecoded", which still looks like a trace: the capture then reports an
    empty window instead of the missing dependency.  Failing here keeps a
    tool failure from turning into a product claim.
    """
    try:
        from streamlit.proto import ForwardMsg_pb2  # noqa: F401
        import google.protobuf  # noqa: F401
    except Exception as exc:
        raise SystemExit(
            f"the protobuf decoder is missing ({type(exc).__name__}: {exc}).  Run the "
            "capture with target\\pyref-venv\\Scripts\\python.exe, the interpreter "
            "that carries streamlit 1.66.1 and its protobuf definitions."
        )


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
    elif kind == "page_config_changed":
        from google.protobuf.json_format import MessageToDict

        out["page_config"] = MessageToDict(msg.page_config_changed)
    elif kind == "page_info_changed":
        out["page_info"] = {"query_string": msg.page_info_changed.query_string}
    elif kind == "navigation":
        # The whole NavigationCommand message: the pages (label, icon, url
        # path, script hash), the position and the expanded flag.
        from google.protobuf.json_format import MessageToDict

        out["navigation"] = MessageToDict(msg.navigation)
    elif kind == "logo":
        # The whole Logo message: the image (emoji, icon or URL), the size,
        # the optional link and the collapsed-sidebar icon.  The logo handler
        # in the frontend dereferences metadata.activeScriptHash, so a logo
        # frame without metadata blanks the page: record its presence (the
        # hash value itself is side-specific and stays out of the summary).
        from google.protobuf.json_format import MessageToDict

        out["logo"] = MessageToDict(msg.logo)
        out["metadata_shape"] = {
            "present": msg.HasField("metadata"),
            "cacheable": msg.metadata.cacheable,
            "delta_path_len": len(msg.metadata.delta_path),
            "has_active_script_hash": bool(msg.metadata.active_script_hash),
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
            if name == "exception":
                # The full Exception element is the field oracle for an
                # invalid-argument failure.
                from google.protobuf.json_format import MessageToDict

                entry["exception"] = MessageToDict(element.exception)
            if name == "alert":
                # The full Alert message is the field oracle for a status
                # element: body, format (the style), icon, title and its own
                # width config, plus the element level layout values.
                from google.protobuf.json_format import MessageToDict

                entry["alert"] = MessageToDict(element.alert)
                entry["element_width_config"] = (
                    MessageToDict(element.width_config) if element.HasField("width_config") else None
                )
                entry["element_height_config"] = (
                    MessageToDict(element.height_config) if element.HasField("height_config") else None
                )
            if widget is not None:
                if name in DATA_ELEMENT_TYPES or name in FULL_ELEMENT_PRESENTATION:
                    # The whole element: the table, the chart, the uploader or
                    # the presentation element's full parameter set.
                    try:
                        from google.protobuf.json_format import MessageToDict

                        entry["element_full"] = MessageToDict(element)
                    except Exception as exc:  # pragma: no cover - defensive
                        entry["element_full"] = {"error": f"{type(exc).__name__}: {exc}"}
                if name in ("dataframe", "table"):
                    message = getattr(element, name, None)
                    if message is not None:
                        if message.arrow_data.data:
                            entry["arrow"] = arrow_summary(message.arrow_data.data)
                        # The pinned 1.66.1 Table message carries only a
                        # subset of these fields; every access stays optional
                        # so one missing field cannot drop the whole frame.
                        entry["arrow_fields"] = {
                            field: value
                            for field in ("id", "columns", "editing_mode", "disabled", "form_id",
                                          "column_order", "selection_mode", "row_height", "placeholder",
                                          "border_mode", "hide_index", "hide_header", "alt")
                            if (value := getattr(message, field, None)) not in (None, "", [], ())
                        }
                if name == "vega_lite_chart":
                    chart = element.vega_lite_chart
                    entry["vega_lite_spec_raw"] = chart.spec
                    entry["vega_lite_spec"] = json.loads(chart.spec) if chart.spec else None
                    entry["vega_lite_datasets"] = [
                        {
                            "name": dataset.name,
                            "has_name": dataset.has_name,
                            "arrow": (
                                arrow_summary(dataset.data.data)
                                if dataset.data.data
                                else None
                            ),
                        }
                        for dataset in chart.datasets
                    ]
                    entry["vega_lite_fields"] = {
                        "use_container_width": chart.use_container_width,
                        "theme": chart.theme,
                        "id": chart.id,
                        "form_id": chart.form_id,
                    }
                    if chart.data and chart.data.data:
                        entry["arrow"] = arrow_summary(chart.data.data)
                if name == "deck_gl_json_chart":
                    deck = element.deck_gl_json_chart
                    entry["deck_gl_json"] = json.loads(deck.json) if deck.json else None
                    entry["deck_gl_fields"] = {
                        "id": deck.id,
                        "tooltip": deck.tooltip,
                        "mapbox_token": deck.mapbox_token,
                        "selection_mode": list(deck.selection_mode),
                        "form_id": deck.form_id,
                        "alt": deck.alt,
                    }
                if name in ("arrow_data_frame", "arrow_vega_lite_chart"):
                    arrow = getattr(element, name, None)
                    if arrow is not None:
                        entry["arrow"] = arrow_summary(arrow.data)
                        if name == "arrow_vega_lite_chart":
                            entry["vega_lite_spec"] = json.loads(arrow.spec) if arrow.spec else None
                            entry["vega_lite_datasets"] = [
                                MessageToDict(dataset) for dataset in arrow.datasets
                            ]
                        else:
                            entry["arrow_fields"] = {
                                field: value
                                for field, value in (
                                    ("id", arrow.id),
                                    ("columns", arrow.columns),
                                    ("editing_mode", arrow.editing_mode),
                                    ("disabled", arrow.disabled),
                                    ("form_id", arrow.form_id),
                                    ("column_order", list(arrow.column_order)),
                                    ("selection_mode", list(arrow.selection_mode)),
                                    ("row_height", arrow.row_height),
                                    ("border_mode", arrow.border_mode),
                                    ("placeholder", arrow.placeholder),
                                )
                                if value not in (None, "", [], ())
                            }
                if name in FULL_ELEMENT_WIDGETS:
                    # The whole Element message: every public parameter of the
                    # widget plus the element level width and height config.
                    try:
                        from google.protobuf.json_format import MessageToDict

                        entry["element_full"] = MessageToDict(element)
                    except Exception as exc:  # pragma: no cover - defensive
                        entry["element_full"] = {"error": f"{type(exc).__name__}: {exc}"}
                if name in MEDIA_ELEMENT_TYPES:
                    # The whole Element message for the media and presentation
                    # elements: the URLs, captions, metric fields and the
                    # progress value.
                    try:
                        from google.protobuf.json_format import MessageToDict

                        entry["element_full"] = MessageToDict(element)
                    except Exception as exc:  # pragma: no cover - defensive
                        entry["element_full"] = {"error": f"{type(exc).__name__}: {exc}"}
                if name in WIDGET_ELEMENTS:
                    # The whole widget message is the field oracle for the
                    # public parameters: options, index, default, min, max,
                    # step, format, key, disabled and on_change.
                    try:
                        from google.protobuf.json_format import MessageToDict

                        entry["widget"] = MessageToDict(widget)
                    except Exception as exc:  # pragma: no cover - defensive
                        entry["widget"] = {"error": f"{type(exc).__name__}: {exc}"}
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
            # The whole Block message: expander/popover/dialog metadata and
            # allowed widget state ride here.
            try:
                from google.protobuf.json_format import MessageToDict

                entry["block"] = MessageToDict(delta.add_block)
            except Exception as exc:  # pragma: no cover - defensive
                entry["block"] = {"error": f"{type(exc).__name__}: {exc}"}
        elif dkind == "new_transient":
            # The whole transient delta: the spinner lifecycle rides the
            # element list (one spinner active, then none at block exit).
            try:
                from google.protobuf.json_format import MessageToDict

                entry["transient"] = MessageToDict(delta.new_transient)
            except Exception as exc:  # pragma: no cover - defensive
                entry["transient"] = {"error": f"{type(exc).__name__}: {exc}"}
        if msg.metadata:
            entry["path"] = list(msg.metadata.delta_path)
        out["delta"] = entry
    elif kind == "file_urls_response":
        out["file_urls_response"] = {
            "response_id": msg.file_urls_response.response_id,
            "file_urls": [
                {
                    "file_id": item.file_id,
                    "upload_url": item.upload_url,
                    "delete_url": item.delete_url,
                }
                for item in msg.file_urls_response.file_urls
            ],
            "error_msg": msg.file_urls_response.error_msg,
        }
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
    if kind == "file_urls_request":
        out["file_urls_request"] = {
            "request_id": msg.file_urls_request.request_id,
            "file_names": list(msg.file_urls_request.file_names),
            "session_id": msg.file_urls_request.session_id,
        }
    elif kind == "rerun_script":
        states = []
        for widget in msg.rerun_script.widget_states.widgets:
            value_field = widget.WhichOneof("value")
            value = getattr(widget, value_field) if value_field else None
            item = {"id": widget.id, "value_field": value_field, "value": _scalar(value)}
            if value_field and hasattr(value, "ListFields"):
                # The exact proto content of the value, not a lossy summary.
                try:
                    from google.protobuf.json_format import MessageToDict

                    item["value_full"] = MessageToDict(value)
                except Exception as exc:  # pragma: no cover - defensive
                    item["value_full"] = {"error": f"{type(exc).__name__}: {exc}"}
            states.append(item)
        # The URL state the browser reports with every rerun: query params,
        # page identity.
        out["rerun_script"] = {"widget_states": states}
        if msg.rerun_script.cached_message_hashes:
            out["rerun_script"]["cached_message_hashes"] = sorted(msg.rerun_script.cached_message_hashes)
        if msg.rerun_script.query_string:
            out["rerun_script"]["query_string"] = msg.rerun_script.query_string
        if msg.rerun_script.page_script_hash:
            out["rerun_script"]["page_script_hash"] = msg.rerun_script.page_script_hash
        if msg.rerun_script.page_name:
            out["rerun_script"]["page_name"] = msg.rerun_script.page_name
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

# The Python 1.66.1 oracle for the status page, read off the real browser
# capture in tests/reference/reference-browser/status/.  The Rust status
# example renders the same page, so the wire fields can be compared directly:
# same body, format, icon, title and width.
FULL_ELEMENT_WIDGETS = ("selectbox", "slider", "checkbox")

# The whole Element message for the text family and one-shot presentation
# elements: the heading level, the iframe src/scrolling, the html scrolling,
# the code body/language of st.echo, the snow/empty flags, the json
# expansion default and the space height.
FULL_ELEMENT_PRESENTATION = ("text", "heading", "html", "iframe", "snow", "empty", "code", "json", "space", "help_info", "skeleton", "markdown", "plotly_chart", "graphviz_chart", "echarts_chart", "bidi_component")

WIDGET_ELEMENTS = (
    "selectbox",
    "slider",
    "checkbox",
    "text_input",
    "text_area",
    "number_input",
    "radio",
    "multiselect",
    "toggle_button",
    "button",
    "file_uploader",
    "date_input",
    "time_input",
    "date_time_input",
    "chat_input",
    "button_group",
    "feedback",
    "pagination",
    "menu_button",
    "link_button",
    "page_link",
    "download_button",
    "color_picker",
    "audio_input",
    "camera_input",
    "help_info",
    "skeleton",
)


# The numeric representatives: the four shapes the widgets example renders --
# one int value, one float value, a range of two int values and a range of two
# float values.  The case list is shared by every driver, so the CLI path and
# the DevTools Protocol path assert exactly the same thing.
NUMERIC_CASES = (
    {"kind": "slider", "label": "Minimum amount", "key": "ArrowRight", "times": 1, "thumb": 0},
    {"kind": "slider", "label": "Ratio", "key": "ArrowRight", "times": 1, "thumb": 0},
    {"kind": "slider", "label": "Amount range", "key": "ArrowRight", "times": 1, "thumb": 0},
    {"kind": "slider", "label": "Ratio range", "key": "ArrowRight", "times": 1, "thumb": 0},
)

# The core controls: a string valued selectbox and a boolean checkbox.
CORE_WIDGET_CASES = (
    {"kind": "selectbox", "label": "Group by", "option": "region", "other_option": "channel"},
    {"kind": "checkbox", "label": "Include unknown region"},
)


# The page probe: the table, the chart and the texts of the page.
OBSERVE_JS = r"""(()=>{const q=s=>document.querySelector(s);
const df=q("[data-testid='stDataFrame']");
const cells=[...document.querySelectorAll("[data-testid='stDataFrame'] [role='gridcell']")].map(e=>e.textContent);
const chart=q("[data-testid='stVegaLiteChart']");
const bars=chart?chart.querySelectorAll("g[class*='mark-rect'] path").length:0;
const chartMarks=chart?[...chart.querySelectorAll("g[class*='mark-rect'] path, g[class*='mark-bar'] path")].map(p=>p.getAttribute("d")||"").join("|"):"";
const labels=chart?[...chart.querySelectorAll("g[class*='mark-text'] text")].map(e=>e.textContent):[];
const thumb=q("[data-testid='stSliderThumbValue']");
const cb=q("[data-testid='stCheckbox'] input");
const sb=q("[data-testid='stSelectbox'] input");
const alerts=[...document.querySelectorAll("[data-testid^='stAlertContent']")].map(e=>e.textContent);
const markdown=[...document.querySelectorAll("[data-testid='stMarkdown']")].map(e=>e.innerText.trim());
const markdownLines=markdown.flatMap(m=>m.split("\n").map(s=>s.trim())).filter(s=>s);
const texts=[...document.querySelectorAll("[data-testid='stText']")].map(e=>e.textContent);
const all=texts.concat(markdownLines);
const pick=(p)=>{const t=all.find(x=>x.startsWith(p));return t?t.slice(p.length).trim():null;};
const buttons=[...document.querySelectorAll("[data-testid='stButton']")].map(e=>e.innerText.trim());
return JSON.stringify({
 document_title: document.title,
 markdown: markdown,
 has_uploader: !!document.querySelector("[data-testid='stFileUploader']"),
 headings: [...document.querySelectorAll("h1,h2,h3")].map(e=>e.innerText.trim()).slice(0,4),
 button_labels: buttons,
 has_button: buttons.length>0,
 script_runs: pick("Script runs:"),
 pulses: pick("Pulses:"),
 applied_note: pick("Applied note:"),
 table_cells:cells, table_present:!!df,
 chart_present:!!chart, chart_bars:bars, chart_labels:labels, chart_marks:chartMarks,
 slider_value: thumb?thumb.textContent:null,
 checkbox_checked: cb?cb.checked:null,
 selectbox_value: sb?sb.value:null,
 texts:texts,
 alerts:alerts});})()"""

# The element types whose full message is the field oracle for the data
# loop: the table, the chart and the file uploader.
DATA_ELEMENT_TYPES = (
    "dataframe",
    "table",
    "vega_lite_chart",
    "deck_gl_json_chart",
    "file_uploader",
)

# The media and presentation elements whose full message is the field
# oracle: URLs and captions for the media elements, the metric fields and
# the progress value.
MEDIA_ELEMENT_TYPES = (
    "imgs",
    "video",
    "audio",
    "metric",
    "progress",
    "toast",
    "balloons",
    "spinner",
)


def arrow_summary(data: bytes) -> dict:
    """The Arrow IPC payload: its schema, its rows and the bytes themselves."""
    import base64 as _base64
    import hashlib as _hashlib

    info = {"bytes": len(data), "sha256": _hashlib.sha256(data).hexdigest()}
    if len(data) <= 256 * 1024:
        info["base64"] = _base64.b64encode(data).decode("ascii")
    try:
        import pyarrow as pa
        import pyarrow.ipc as ipc

        try:
            table = ipc.open_stream(pa.BufferReader(data)).read_all()
        except Exception:
            table = ipc.open_file(pa.BufferReader(data)).read_all()
        info["schema"] = str(table.schema)
        info["columns"] = table.schema.names
        info["row_count"] = table.num_rows
        info["rows"] = table.to_pylist()[:25]
    except Exception as exc:
        info["arrow_error"] = f"{type(exc).__name__}: {exc}"
    return info


def http_requests_from_events(events, target: str = "") -> tuple[list[dict], int]:
    """The HTTP requests of a capture, with the body of an upload.

    A file upload posts a multipart body: the entries carry the bytes, so
    the size, the digest and the first bytes of the body are kept next to
    the method, the URL and the headers.
    """
    requests: list[dict] = []
    static_bundle_requests = 0
    for event in events:
        if event.get("method") != "Network.requestWillBeSent":
            continue
        params = event.get("params", {})
        request = params.get("request", {})
        url = request.get("url", "")
        if "/static/" in url:
            static_bundle_requests += 1
            continue
        entry = {
            "target": event.get("_target", target),
            "method": request.get("method"),
            "url": url,
            "resource_type": params.get("type"),
            "request_headers": {
                key: value
                for key, value in (request.get("headers") or {}).items()
                if key.lower() in ("content-type", "content-length", "origin")
            },
        }
        post = request.get("postData")
        if post:
            entry["multipart_preamble"] = post[:400]
            entry["post_data_bytes"] = len(post)
        for item in request.get("postDataEntries") or []:
            raw = base64.b64decode(item.get("bytes", "") or "")
            entry["post_data_entries"] = [
                {
                    "bytes": len(raw),
                    "sha256": hashlib.sha256(raw).hexdigest(),
                    "head": raw[:160].decode("utf-8", "replace"),
                    "base64": base64.b64encode(raw).decode("ascii") if len(raw) <= 256 * 1024 else None,
                }
            ]
            break
        requests.append(entry)
    for event in events:
        if event.get("method") != "Network.responseReceived":
            continue
        params = event.get("params", {})
        url = params.get("response", {}).get("url", "")
        if "/static/" in url:
            continue
        for entry in requests:
            if entry.get("url") == url and "status" not in entry:
                entry["status"] = params.get("response", {}).get("status")
                entry["mime_type"] = params.get("response", {}).get("mimeType")
                break
    return requests, static_bundle_requests


# The DOM probe: one query per widget, each inside its own container, so a
# page with several inputs cannot make one widget read another's value.
WIDGET_DOM_JS = r"""(()=>{const q=s=>document.querySelector(s);
const sb=q("[data-testid='stSelectbox']");const sbInput=sb?sb.querySelector("input"):null;
const sl=q("[data-testid='stSlider']");const slInput=sl?sl.querySelector("input"):null;
const thumb=sl?sl.querySelector("[data-testid='stSliderThumbValue']"):null;
const cbBox=q("[data-testid='stCheckbox']");const cb=cbBox?cbBox.querySelector("input"):null;
const dis=e=>!!(e&&(e.getAttribute("aria-disabled")==="true"||e.disabled));
const markdown=[...document.querySelectorAll("[data-testid='stMarkdown']")].map(e=>e.innerText.replace(/\s+/g," ").trim());
return JSON.stringify({
 selectbox_value:sbInput?sbInput.value:null,
 selectbox_disabled:dis(sb)||dis(sbInput),
 slider_value:slInput?slInput.value:(thumb?thumb.textContent:null),
 slider_thumb:thumb?thumb.textContent:null,
 slider_disabled:dis(sl)||dis(slInput),
 checkbox_checked:cb?cb.checked:null,
 checkbox_disabled:dis(cbBox)||dis(cb),
 markdown:markdown,
 exceptions:[...document.querySelectorAll("[data-testid='stException']")].map(e=>e.innerText.replace(/\s+/g," ").trim().slice(0,400))
});})()"""

# The suites: the cases a page has to deliver.  A suite names its cases
# explicitly, so a page that does not carry them fails instead of quietly
# skipping them.
SUITES = {
    "python-numeric": {
        "cases": NUMERIC_CASES,
        "required": [case["label"] for case in NUMERIC_CASES],
    },
    "rust-widgets": {
        "cases": CORE_WIDGET_CASES + NUMERIC_CASES,
        "required": [case["label"] for case in CORE_WIDGET_CASES]
        + [case["label"] for case in NUMERIC_CASES],
    },
}


# The value field each kind of widget sends.
EXPECTED_VALUE_FIELDS = {
    "slider": "double_array_value",
    "selectbox": "string_value",
    "checkbox": "bool_value",
}


def case_verdict(case, frames, window, action, dom_before_value, dom_after_value, check_page: bool = True) -> dict:
    """Decide one widget case from what actually happened.

    The case passes only when the action ran, the widget's own state inside
    the window carries a changed value in the field that kind of widget
    sends, a successful script_finished follows it on the same connection,
    and the page shows that value.  A frame without a connection, a state
    that was sent unchanged and a page that still shows the old value all
    fail the case.
    """
    problems = []
    label = case.get("label", "")
    if action.get("failed"):
        problems.append(f"the action failed: {action['failed']}")
    widget_id = window.get("widget")

    state = None
    for index in range(window["start"], window["end"]):
        frame = frames[index]
        if frame.get("direction") != "client->server":
            continue
        decoded = frame.get("decoded") or {}
        if decoded.get("type") != "rerun_script":
            continue
        for item in decoded.get("rerun_script", {}).get("widget_states", []) or []:
            if item.get("id") == widget_id:
                state = (index, item)
    if state is None:
        problems.append("the window carries no state for this widget")
        return {
            "ok": False,
            "problems": problems,
            "wire_value": None,
            "before_value": None,
            "connection": None,
            "state_frame": None,
            "completion_frame": None,
        }

    connection = frames[state[0]].get("connection")
    if connection is None:
        problems.append("the state frame carries no connection")

    before_value = None
    for index in range(0, window["start"]):
        frame = frames[index]
        if frame.get("direction") != "client->server":
            continue
        decoded = frame.get("decoded") or {}
        if decoded.get("type") != "rerun_script":
            continue
        for item in decoded.get("rerun_script", {}).get("widget_states", []) or []:
            if item.get("id") == widget_id:
                before_value = wire_value_of(item)
    after_value = wire_value_of(state[1])

    expected_field = EXPECTED_VALUE_FIELDS.get(case.get("kind"))
    if expected_field and state[1].get("value_field") != expected_field:
        problems.append(
            f"the state was sent in {state[1].get('value_field')!r}, "
            f"not in {expected_field!r}"
        )
    if before_value is not None and before_value == after_value:
        problems.append(f"the value was sent unchanged: {before_value!r}")

    completion = None
    for index in range(state[0] + 1, window["end"]):
        frame = frames[index]
        decoded = frame.get("decoded") or {}
        if decoded.get("type") != "script_finished":
            continue
        if frame.get("connection") is None or frame.get("connection") != connection:
            continue
        if (decoded.get("script_finished") or {}).get("status") != 0:
            continue
        completion = index
        break
    if completion is None:
        problems.append("no successful script_finished on the same connection after the state")

    if check_page:
        if dom_after_value is None:
            problems.append("the page shows no value for this widget")
        elif not widget_value_matches(dom_after_value, after_value):
            problems.append(
                f"the page shows {dom_after_value!r}, the client sent {after_value!r}"
            )
        if dom_before_value is not None and dom_before_value == dom_after_value:
            problems.append(f"the page still shows the old value {dom_before_value!r}")

    return {
        "ok": not problems,
        "problems": problems,
        "wire_value": after_value,
        "before_value": before_value,
        "connection": connection,
        "state_frame": state[0],
        "completion_frame": completion,
        "value_matches_the_page": not problems,
    }



def _same_cell_value(want, got) -> bool:
    """Is the rendered cell the value of the data?

    A number is compared with a tolerance, because the page may show fewer
    digits than the data carries; a string is compared as it is.
    """
    if want is None:
        return got in ("", "None", None)
    if isinstance(want, bool):
        return str(want) == str(got)
    if isinstance(want, (int, float)):
        try:
            return abs(float(got) - float(want)) <= max(1e-9, abs(float(want)) * 1e-9)
        except (TypeError, ValueError):
            return False
    return str(want).strip() == str(got).strip()


def _bar_geometry(chart_marks: str) -> list[dict]:
    """The bars of a Vega bar chart: their left edge, their top and their height.

    Vega draws a bar as "M<x>,<top>h<width>v<height>...", so the height is
    the vertical command and the baseline is the bottom of that path.
    """
    bars = []
    for path in (chart_marks or "").split("|"):
        numbers = re.findall(r"-?\d+(?:\.\d+)?", path)
        if len(numbers) < 4:
            continue
        try:
            x, top, width, height = (float(number) for number in numbers[:4])
        except ValueError:
            continue
        bars.append({"x": x, "top": top, "width": width, "height": height})
    bars.sort(key=lambda bar: bar["x"])
    return bars


def data_loop_verdict(case, frames, window, action, dom_before, dom_after) -> dict:
    """The verdict for one step of the data loop.

    The wire part is the one of a widget case -- the action ran, the
    widget's own state in the window carries a changed value and a
    successful script_finished follows it on the same connection.  On top of
    that the rendered result has to change, because the page must show the
    effect of the new filter and not only of the rerun.
    """
    verdict = case_verdict(case, frames, window, action, None, None, check_page=False)
    problems = list(verdict["problems"])

    # The result this action caused: the Arrow the server sent inside the
    # window.  Without it nothing was rendered for this step.
    rows = None
    table_arrow = {}
    chart_delta = None
    for index in range(window["start"], window["end"]):
        delta = (frames[index].get("decoded") or {}).get("delta") or {}
        if delta.get("type") != "new_element":
            continue
        if delta.get("element") in ("dataframe", "table"):
            table_arrow = delta.get("arrow") or {}
            rows = table_arrow.get("rows")
            verdict["result_digest"] = table_arrow.get("sha256")
        if delta.get("element") == "vega_lite_chart":
            chart_delta = delta
    if rows is None:
        problems.append("no result data in the window")
        rows = []

    before = dom_before or {}
    after = dom_after or {}

    # Every cell of the page has to be the value of the data, in the order of
    # the columns of the Arrow.
    columns = table_arrow.get("columns") or []
    expected_cells = [
        row.get(column) for row in rows for column in columns
    ]
    actual_cells = after.get("table_cells") or []
    if len(actual_cells) != len(expected_cells):
        problems.append(
            f"the table shows {len(actual_cells)} cells, the data has {len(expected_cells)}"
        )
    else:
        for index, (want, got) in enumerate(zip(expected_cells, actual_cells)):
            if not _same_cell_value(want, got):
                problems.append(
                    f"cell {index} shows {got!r}, the data says {want!r}"
                )
                break
    if not actual_cells:
        problems.append("the table rendered no cells")
    if not after.get("chart_bars"):
        problems.append("the chart rendered no bars")

    # The chart of this step has to be the same data, and it has to be here.
    if chart_delta is None:
        problems.append("no chart in the window")
    else:
        spec = chart_delta.get("vega_lite_spec") or {}
        datasets = chart_delta.get("vega_lite_datasets") or []
        name = (spec.get("data") or {}).get("name")
        # The chart either carries the data itself or names a data set
        # that carries it; either way it has to be the data of the table.
        chart_arrow = chart_delta.get("arrow") or {}
        dataset_arrow = None
        for dataset in datasets:
            if dataset.get("name") == name:
                dataset_arrow = dataset.get("arrow") or {}
        if dataset_arrow is None and not chart_arrow:
            problems.append("the chart names a data set it does not send")
        else:
            sent = dataset_arrow or chart_arrow
            if table_arrow.get("sha256") and sent.get("sha256") != table_arrow.get("sha256"):
                problems.append("the chart carries other data than the table")

        # The bars have to stand for the values of the rows.  Which
        # column the chart draws is read from the spec itself.
        encoding = spec.get("encoding") or {}
        x_field = (encoding.get("x") or {}).get("field") or "group_key"
        y_field = (encoding.get("y") or {}).get("field") or "total_amount"
        order = (encoding.get("x") or {}).get("sort")
        if not order:
            order = [row.get(x_field) for row in rows]
        values = []
        for key in order:
            row = next((row for row in rows if row.get(x_field) == key), None)
            values.append(row.get(y_field) if row else None)
        bars = _bar_geometry(after.get("chart_marks"))
        if len(bars) != len(values):
            problems.append(
                f"the chart draws {len(bars)} bars, the table has {len(values)} rows"
            )
        else:
            ratios = []
            baselines = []
            for bar, value in zip(bars, values):
                if not isinstance(value, (int, float)):
                    problems.append("a row of the chart has no value")
                    break
                if value > 0:
                    # A positive value has to be drawn with a positive height:
                    # a chart whose bars are all flat stands for nothing.
                    if bar["height"] <= 0:
                        problems.append(
                            f"the bar of {value} has no height"
                        )
                        break
                    ratio = bar["height"] / float(value)
                    if not math.isfinite(ratio) or ratio <= 0:
                        problems.append(
                            "the bars do not stand for the values with a positive scale"
                        )
                        break
                    ratios.append(ratio)
                baselines.append(bar["top"] + bar["height"])
            if ratios and len(ratios) > 1:
                spread = max(ratios) - min(ratios)
                if spread > max(1e-6, abs(max(ratios)) * 1e-6):
                    problems.append("the bar heights do not stand for the values")
            if baselines and len(baselines) > 1:
                if max(baselines) - min(baselines) > 1e-6:
                    problems.append("the bars do not share one baseline")

    if before.get("table_cells") == after.get("table_cells"):
        problems.append("the table values did not change")
    if before.get("chart_marks") == after.get("chart_marks"):
        problems.append("the chart did not re-render")
    verdict["problems"] = problems
    verdict["ok"] = not problems
    return verdict


def _check(step: str, check: str, expected: str, actual, ok: bool) -> dict:
    """One check of a journey: what was expected, what was seen and the verdict."""
    return {
        "step": step,
        "check": check,
        "expected": expected,
        "actual": actual if isinstance(actual, str) else json.dumps(actual, default=str),
        "ok": bool(ok),
    }


JOURNEY_REQUIRED = {
    "recover": {(s, c) for s, c in (
        ("bad-csv", "file_uploaded"), ("bad-csv", "error_visible"), ("bad-csv", "no_result"),
        ("recover", "file_uploaded"), ("recover", "case_verdict"), ("recover", "frames_decoded"),
        ("replace", "delete_status"), ("replace", "old_file_gone"),
        ("bad-csv", "upload_proof"), ("recover", "upload_proof"),
        ("recover", "no_stale_error"), ("replace", "delete_bound"))},
    "empty": {("empty-csv", c) for c in (
        "file_uploaded", "info_visible", "result_present", "no_rows", "schema_kept", "no_stale_view", "operation_proof")},
    "sessions": {("sessions", c) for c in (
        "file_uploaded_a", "file_uploaded_b", "session_ids", "session_isolation", "upload_isolation",
        "control_isolation", "group_isolation", "results_present", "result_isolation", "proof_a", "proof_b")},
}


def journey_result(checks: list[dict]) -> dict:
    """Require the fixed, finite contract of one journey, not an arbitrary count."""
    if not isinstance(checks, list) or any(not isinstance(c, dict) or not isinstance(c.get("journey"), str) for c in checks):
        return {"failures": [_check("journey", "required_checks", "well-formed journey checks", "missing or malformed checks", False)],
                "counts": {"expected": 1, "executed": 0, "asserted": 0}, "ok": False}
    kinds = {c.get("journey") for c in checks if isinstance(c, dict)}
    kind = next(iter(kinds)) if len(kinds) == 1 else None
    required = JOURNEY_REQUIRED.get(kind)
    if not required:
        failure = _check("journey", "required_checks", "one complete known journey contract", "missing or mixed journey checks", False)
        return {"failures": [failure], "counts": {"expected": 1, "executed": 0, "asserted": 0}, "ok": False}
    keyed = {(c.get("step"), c.get("check")): c for c in checks}
    failures = [{k: c.get(k) for k in ("step", "check", "expected", "actual")} for c in checks if c.get("ok") is not True]
    for key in sorted(required - keyed.keys()):
        failures.append(_check(*key, "required journey check", "not executed", False))
    if len(keyed) != len(checks) or keyed.keys() - required:
        failures.append(_check("journey", "required_checks", "exactly one of every required check", "duplicate or unknown checks", False))
    return {"failures": failures, "counts": {"expected": len(required), "executed": len(required & keyed.keys()),
            "asserted": sum(key in keyed and keyed[key].get("ok") is True for key in required)}, "ok": not failures}


# A parse error reads differently in the reference app and in the Rust one
# ("row 3: expected 8 fields, found 7" against "CSV error: record 2 ..."), so
# the check looks for the shape of a parse failure and not for one wording.
PARSE_ERROR = re.compile(r"(?i)could not parse|csv error|record \d+|row \d+")


def _filled_cells(cells) -> list[str]:
    """The cells that carry text.

    A table of an empty result still renders one cell per column, with
    empty text.  Those cells are not stale data, so the stale check looks
    at the text and not at the number of cells.
    """
    return [str(cell) for cell in (cells or []) if str(cell).strip()]


def _journey_need(ok, message):
    if not ok:
        raise ValueError(message)


def _journey_http(bundle, phase):
    """Use actual request/response timestamps, never driver in_phase booleans."""
    timeline = bundle.get("http_timeline")
    start, end = phase.get("start_timestamp"), phase.get("end_timestamp")
    _journey_need(isinstance(timeline, list) and timeline and all(type(t) in (int, float) and math.isfinite(t) for t in (start, end)) and start < end, "missing HTTP timeline/action timestamps")
    requests = []
    for request in timeline:
        sent, received = request.get("timestamp"), request.get("response_timestamp")
        if not all(type(t) in (int, float) and math.isfinite(t) for t in (sent, received)):
            continue
        if start <= sent <= received <= end:
            _journey_need(request.get("request_id"), "HTTP request lacks real requestId")
            requests.append(request)
    return requests


def _journey_url(base, value, session, file_id):
    from urllib.parse import urljoin, urlsplit, unquote
    _journey_need(isinstance(value, str) and bool(value), "missing issued file URL")
    absolute = urljoin(base, value)
    parsed, origin = urlsplit(absolute), urlsplit(base)
    _journey_need(parsed.scheme in ("http", "https") and (parsed.scheme, parsed.netloc) == (origin.scheme, origin.netloc), "file URL origin mismatch")
    _journey_need([unquote(v) for v in parsed.path.rstrip("/").split("/")[-2:]] == [session, file_id], "file URL session/file id mismatch")
    return absolute


def _journey_ipc(arrow, bundle):
    """Re-read wire and retained IPC bytes, not just a claimed digest."""
    _journey_need(isinstance(arrow, dict) and isinstance(arrow.get("base64"), str), "missing IPC bytes in wire")
    data = base64.b64decode(arrow["base64"], validate=True)
    actual = arrow_summary(data)
    _journey_need("arrow_error" not in actual, "IPC reader failed: " + str(actual.get("arrow_error")))
    for key in ("bytes", "sha256", "schema", "columns", "rows", "row_count"):
        _journey_need(key in arrow and actual.get(key) == arrow[key], "wire IPC summary mismatch: " + key)
    _journey_need(actual["row_count"] == len(actual["rows"]), "IPC row preview is incomplete")
    files = bundle.get("ipc_files")
    _journey_need(isinstance(files, dict) and isinstance(bundle.get("ipc_dir"), (str, pathlib.Path)), "missing retained IPC mapping")
    name = files.get(actual["sha256"])
    _journey_need(isinstance(name, str) and pathlib.Path(name).name == name, "missing or unsafe retained IPC filename")
    folder = pathlib.Path(bundle["ipc_dir"]).resolve()
    path = (folder / name).resolve()
    _journey_need(path.parent == folder and path.is_file() and path.read_bytes() == data, "retained IPC differs from operation wire bytes")
    return actual


def _journey_bundle(observation, *, tab=None, phase_index=-1):
    """Read the published shape. A replay loader binds ipc_dir in memory to
    the actual raw parent (or resolved archive location); historical events
    and stored IPC filenames are never rewritten to repair missing evidence.
    """
    _journey_need(isinstance(observation, dict), "missing observation")
    raw = observation.get("tabs", {}).get(tab) if tab else observation
    _journey_need(isinstance(raw, dict), "missing tab observation")
    frames, phases = raw.get("frames"), raw.get("phases")
    _journey_need(isinstance(frames, list) and frames and isinstance(phases, list) and phases, "missing raw frames/phases")
    namespaces = {f.get("namespace") for f in frames}
    source = raw.get("namespace") if tab else next(iter(namespaces)) if len(namespaces) == 1 else None
    _journey_need(isinstance(source, str) and source and namespaces == {source}, "missing or mixed frame namespaces")
    _journey_need(isinstance(observation.get("ipc_dir"), str) and isinstance(observation.get("url"), str), "missing IPC directory/application URL")
    files = {}
    normalized = [dict(f, target=f["namespace"]) for f in frames]
    for phase in phases:
        start, end = phase.get("start"), phase.get("end")
        _journey_need(type(start) is int and type(end) is int and 0 <= start < end <= len(frames), "invalid phase frame window")
        selected = frames[start:end]
        stamps = [f.get("timestamp") for f in selected]
        _journey_need(all(type(t) in (int, float) and math.isfinite(t) for t in stamps)
                      and stamps == sorted(stamps) and phase.get("start_timestamp") == stamps[0]
                      and phase.get("end_timestamp") == stamps[-1], "phase timestamps are not bound to raw frames")
        client_states = [{k: state.get(k) for k in ("id", "value_field", "value")}
                         for f in selected if (f.get("decoded") or {}).get("type") == "rerun_script"
                         for state in f["decoded"].get("rerun_script", {}).get("widget_states", [])]
        completions = [{"frame": i, "connection": f.get("connection"), "request_id": f.get("request_id"),
                        "status": f["decoded"]["script_finished"].get("status"), "status_name": f["decoded"]["script_finished"].get("status_name")}
                       for i, f in enumerate(selected) if (f.get("decoded") or {}).get("type") == "script_finished"]
        _journey_need(client_states and client_states == phase.get("client_states") and completions and completions == phase.get("completions"), "phase ClientState/completion summaries differ from raw frames")
        _journey_need(isinstance(phase.get("ipc"), dict), "missing phase IPC evidence")
        for payload in phase["ipc"].values():
            if not payload:
                continue
            payloads = [payload.get("arrow"), *[d.get("arrow") for d in payload.get("datasets", [])]]
            for arrow in (value for value in payloads if value):
                _journey_need(isinstance(arrow.get("file"), str) and arrow.get("sha256"), "missing retained phase IPC file")
                previous = files.get(arrow["sha256"])
                _journey_need(previous is None or previous == arrow["file"], "conflicting retained IPC mapping")
                files[arrow["sha256"]] = arrow["file"]
        deltas = [f.get("decoded", {}).get("delta", {}) for f in selected if f.get("direction") == "server->client" and f.get("decoded", {}).get("type") == "delta"]
        for name, kinds in (("table", ("dataframe", "table")), ("chart", ("vega_lite_chart",))):
            wire = [d for d in deltas if d.get("type") == "new_element" and d.get("element") in kinds]
            retained = phase["ipc"].get(name)
            _journey_need(bool(wire) == bool(retained), "phase IPC does not correspond to its frame window")
            if wire:
                pairs = [(wire[-1].get("arrow"), retained.get("arrow"))]
                if name == "chart":
                    _journey_need(retained.get("vega_lite_spec") == wire[-1].get("vega_lite_spec"), "phase chart spec differs from wire")
                    datasets = wire[-1].get("vega_lite_datasets") or []
                    kept_datasets = retained.get("datasets")
                    _journey_need(isinstance(kept_datasets, list) and len(kept_datasets) == len(datasets), "missing retained chart datasets")
                    for dataset, kept in zip(datasets, kept_datasets):
                        _journey_need(dataset.get("name") == kept.get("name") and dataset.get("has_name") == kept.get("has_name"), "retained chart dataset identity differs from wire")
                        pairs.append((dataset.get("arrow"), kept.get("arrow")))
                for wire_arrow, arrow in pairs:
                    _journey_need(bool(wire_arrow) == bool(arrow), "retained IPC invents or omits a wire payload")
                    if wire_arrow:
                        _journey_need(isinstance(arrow, dict) and all(key in arrow and arrow[key] == wire_arrow.get(key)
                                      for key in ("sha256", "bytes", "columns", "rows", "row_count", "schema")), "phase IPC summary differs from window wire")
    phase = phases[phase_index]
    upload_phase = next((p for p in phases[:phases.index(phase)+1] if p.get("action", {}).get("action") == "upload" and p.get("action", {}).get("file")), None)
    # Recovery selects its own upload phase; a tab's later group phase uses its first upload.
    if phase.get("action", {}).get("action") == "upload":
        upload_phase = phase
    _journey_need(upload_phase is not None, "missing upload phase")
    if tab:
        _journey_need(isinstance(raw.get("file"), str) and pathlib.Path(raw["file"]).resolve() == pathlib.Path(upload_phase["action"]["file"]).resolve(), "tab file path differs from its upload action")
    def window(p):
        select = p.get("action", {}).get("action") == "select-option"
        label = "Group by" if select else "Upload sales CSV"
        ids = {f["decoded"].get("delta", {}).get("id") for f in frames[p["start"]:p["end"]]
               if f.get("decoded", {}).get("delta", {}).get("label") == label}
        _journey_need(len(ids) == 1 and None not in ids, "missing unique server widget id for phase")
        return {"start": p["start"], "end": p["end"], "widget": next(iter(ids)), "target": source,
                "start_timestamp": p["start_timestamp"], "end_timestamp": p["end_timestamp"]}
    uploads = observation.get("uploads", {})
    if tab:
        upload_ok = uploads.get(tab)
    elif observation.get("journey") == "empty":
        upload_ok = uploads.get("file")
    else:
        upload_ok = uploads.get("bad" if phase_index == 0 else "good")
    action = phase.get("action")
    _journey_need(isinstance(action, dict) and action.get("action") in ("upload", "select-option"), "missing observed action")
    ok = action.get("changed") if action["action"] == "select-option" else upload_ok
    _journey_need(not action.get("failed") and action.get("ok") is not False
                  and upload_phase.get("action", {}).get("ok") is not False, "action failed")
    return {"frames": normalized, "source": source, "url": observation["url"],
            "fixture": upload_phase["action"]["file"], "window": window(phase), "upload_window": window(upload_phase),
            "action": {"action": "select" if action["action"] == "select-option" else "upload", "ok": ok},
            "upload_action": {"action": "upload", "ok": upload_ok}, "http_timeline": raw.get("http_timeline"),
            "ipc_dir": observation["ipc_dir"], "ipc_files": files, "dom_before": phase.get("dom_before")}


def _journey_run_verdict(frames, window, operation, fixture_name, group):
    """Bind a target state to its *new* server run, not an older run's finish.

    Python can send the replacement state while the clear-state run is still
    finishing. NewSession/script_run_id separates those responses. The proof
    view contains unchanged recorded frame objects, projected by run boundary;
    numeric/data_loop's existing state/completion/value checks remain intact.
    """
    kind = "selectbox" if operation["action"] == "select" else "file_uploader"
    candidates = []
    for index in range(window["start"], window["end"]):
        frame = frames[index]
        if frame.get("direction") != "client->server" or frame.get("decoded", {}).get("type") != "rerun_script":
            continue
        for state in frame["decoded"]["rerun_script"].get("widget_states", []):
            if state.get("id") != window["widget"]:
                continue
            if kind == "selectbox":
                matches = state.get("value_field") == "string_value" and state.get("value") == group
            else:
                infos = state.get("value_full", {}).get("uploadedFileInfo")
                matches = (state.get("value_field") == "file_uploader_state_value" and isinstance(infos, list)
                           and len(infos) == 1 and infos[0].get("name") == fixture_name and bool(infos[0].get("fileId")))
            if matches:
                candidates.append(index)
    _journey_need(len(candidates) == 1, "missing or ambiguous target file/control ClientState in this operation")
    state_index = candidates[0]
    state = frames[state_index]
    identity = (state.get("target"), state.get("request_id"), state.get("connection"))

    def same(frame):
        return (frame.get("target"), frame.get("request_id"), frame.get("connection")) == identity

    run_start = next((i for i in range(state_index + 1, window["end"])
                      if same(frames[i]) and frames[i].get("direction") == "server->client"
                      and frames[i].get("decoded", {}).get("type") == "new_session"), None)
    _journey_need(run_start is not None, "no new server run marker after the target ClientState")
    run_id = frames[run_start]["decoded"]["new_session"].get("script_run_id")
    _journey_need(isinstance(run_id, str) and run_id, "target server run has no script_run_id")
    earlier_ids = {f["decoded"]["new_session"].get("script_run_id") for f in frames[:run_start]
                   if same(f) and f.get("decoded", {}).get("type") == "new_session"}
    _journey_need(run_id not in earlier_ids, "target run reuses an earlier script_run_id")
    _journey_need(not any(f.get("direction") == "client->server" and f.get("decoded", {}).get("type") == "rerun_script"
                          for f in frames[state_index + 1:run_start]), "another ClientState superseded the target before its run")
    finish = None
    for index in range(run_start + 1, window["end"]):
        frame = frames[index]
        if not same(frame) or frame.get("direction") != "server->client":
            continue
        decoded = frame.get("decoded", {})
        _journey_need(decoded.get("type") != "new_session", "target run has no completion before another run starts")
        if decoded.get("type") == "script_finished":
            _journey_need(decoded.get("script_finished", {}).get("status") == 0, "target run did not finish successfully")
            finish = index
            break
    _journey_need(finish is not None, "target run has no successful completion")
    _journey_need(not any(f.get("direction") == "client->server" and f.get("decoded", {}).get("type") == "rerun_script"
                          for f in frames[run_start + 1:finish]), "another ClientState arrived during the target run")
    prefix = frames[:window["start"]]
    proof_frames = prefix + [state] + frames[run_start:finish + 1]
    proof_window = dict(window, start=len(prefix), end=len(proof_frames))
    verdict = case_verdict({"kind": kind, "label": "Group by" if kind == "selectbox" else "Upload sales CSV"},
                           proof_frames, proof_window, operation, None, None, check_page=False)
    verdict.update(state_frame=state_index, completion_frame=finish, run_start_frame=run_start,
                   script_run_id=run_id, proof_frames=proof_frames, proof_window=proof_window)
    return verdict


def _journey_context(bundle, fixture_name, group, dom, *, no_result=False, empty=False):
    """Bounded upload/result proof for these three journeys, not a new runner."""
    try:
        _journey_need(isinstance(bundle, dict), "missing operation evidence")
        frames, source = bundle.get("frames"), bundle.get("source")
        _journey_need(isinstance(frames, list) and frames and isinstance(source, str) and source, "missing frames/source namespace")
        base = bundle.get("url")
        _journey_need(isinstance(base, str) and base.startswith(("http://", "https://")), "missing application URL")
        fixture = (REPO_ROOT / "tests/fixtures/csv" / fixture_name).resolve()
        _journey_need(isinstance(bundle.get("fixture"), str) and pathlib.Path(bundle["fixture"]).resolve() == fixture and fixture.is_file(), "fixture path ownership mismatch")
        window, upload_window = bundle.get("window"), bundle.get("upload_window")
        for candidate in (window, upload_window):
            _journey_need(isinstance(candidate, dict) and type(candidate.get("start")) is int and type(candidate.get("end")) is int
                          and 0 <= candidate["start"] < candidate["end"] <= len(frames)
                          and candidate.get("target") == source and candidate.get("widget"), "missing or invalid action frame window")
        action, upload_action = bundle.get("action"), bundle.get("upload_action")
        _journey_need(isinstance(action, dict) and action.get("ok") is True and action.get("action") in ("upload", "select")
                      and isinstance(upload_action, dict) and upload_action.get("action") == "upload" and upload_action.get("ok") is True, "action failed or was not observed")
        identity = None
        verdicts = []
        for current, operation in ((upload_window, upload_action), (window, action)):
            selected = frames[current["start"]:current["end"]]
            _journey_need(all(f.get("target") == source for f in selected), "frame source namespace mismatch")
            verdict = _journey_run_verdict(frames, current, operation, fixture.name, group)
            _journey_need(verdict["ok"], "; ".join(verdict["problems"]))
            state = frames[verdict["state_frame"]]
            done = frames[verdict["completion_frame"]]
            pair = (source, state.get("request_id"), state.get("connection"))
            _journey_need(pair[1] and pair[2] is not None and done.get("direction") == "server->client"
                          and (done.get("target"), done.get("request_id"), done.get("connection")) == pair, "completion is on another source/connection/requestId")
            _journey_need(all((f.get("target"), f.get("request_id"), f.get("connection")) == pair for f in selected), "operation contains frames from another connection/requestId")
            _journey_need(identity is None or identity == pair, "upload/control changed connection")
            identity = pair
            _journey_need(not any((f.get("decoded") or {}).get("message") == "undecoded" for f in selected), "undecoded operation frame")
            verdicts.append(verdict)
        upload_proof, result_proof = verdicts
        _journey_need(upload_proof["state_frame"] <= result_proof["state_frame"], "result comes from before this upload")

        def same(frame):
            return (frame.get("target"), frame.get("request_id"), frame.get("connection")) == identity

        def states_at(index):
            return (frames[index].get("decoded") or {}).get("rerun_script", {}).get("widget_states", [])

        def uploaded(index):
            states = [v for v in states_at(index) if v.get("id") == upload_window["widget"] and v.get("value_field") == "file_uploader_state_value"]
            _journey_need(len(states) == 1, "missing uploader ClientState")
            infos = (states[0].get("value_full") or {}).get("uploadedFileInfo")
            _journey_need(isinstance(infos, list) and len(infos) == 1, "uploader state does not name exactly one file")
            return infos[0]

        info = uploaded(upload_proof["state_frame"])
        final_info = uploaded(result_proof["state_frame"])
        _journey_need(info == final_info and info.get("name") == fixture.name and int(info.get("size", -1)) == fixture.stat().st_size, "ClientState file is not this fixture")
        file_id = info.get("fileId")
        _journey_need(isinstance(file_id, str) and file_id, "missing uploaded file id")
        before_state = range(upload_window["start"], upload_proof["state_frame"])
        requests = [(i, frames[i]["decoded"]["file_urls_request"]) for i in before_state if same(frames[i]) and frames[i].get("direction") == "client->server" and (frames[i].get("decoded") or {}).get("type") == "file_urls_request"]
        _journey_need(requests, "no issued URL request in this upload window")
        request_index, request = requests[-1]
        session = request.get("session_id")
        _journey_need(isinstance(session, str) and session and request.get("file_names") == [fixture.name] and request.get("request_id"), "URL request file/session mismatch")
        responses = [frames[i]["decoded"]["file_urls_response"] for i in range(request_index + 1, upload_proof["state_frame"]) if same(frames[i]) and frames[i].get("direction") == "server->client" and (frames[i].get("decoded") or {}).get("type") == "file_urls_response"]
        issued = [u for r in responses if r.get("response_id") == request["request_id"] and not r.get("error_msg") for u in r.get("file_urls", []) if u.get("file_id") == file_id]
        _journey_need(len(issued) == 1, "no matching issued URL response")
        urls = info.get("fileUrls") or {}
        _journey_need(urls.get("fileId") == file_id and urls.get("uploadUrl") == issued[0].get("upload_url") and urls.get("deleteUrl") == issued[0].get("delete_url"), "uploaded state URLs differ from issued URLs")
        upload_url = _journey_url(base, issued[0].get("upload_url"), session, file_id)
        delete_url = _journey_url(base, issued[0].get("delete_url"), session, file_id)
        http = _journey_http(bundle, upload_window)
        _journey_need(any(r.get("method") == "PUT" and r.get("url") == upload_url and r.get("status") == 204
                          and "multipart/form-data" in str(r.get("request_headers", {})).lower()
                          for r in http), "no matching multipart PUT204 in upload action window")
        sessions = {((f.get("decoded") or {}).get("new_session") or {}).get("session_id") for f in frames[:result_proof["completion_frame"]+1] if same(f) and (f.get("decoded") or {}).get("type") == "new_session"}
        _journey_need(sessions == {session}, "NewSession does not bind this upload connection/session")
        result_frames = [frames[i] for i in range(result_proof["run_start_frame"]+1, result_proof["completion_frame"]) if same(frames[i]) and frames[i].get("direction") == "server->client"]
        deltas = [(f.get("decoded") or {}).get("delta", {}) for f in result_frames if f.get("decoded", {}).get("type") == "delta"]
        widgets = {d.get("label"): d.get("id") for d in deltas if d.get("element") in ("selectbox", "slider", "checkbox", "file_uploader")}
        _journey_need(widgets.get("Upload sales CSV") == upload_window["widget"], "uploader widget not bound to server")
        states = {v.get("id"): v for v in states_at(result_proof["state_frame"])}
        for label, want in (("Group by", group), ("Minimum amount", [0.0]), ("Include unknown region", True)):
            _journey_need(widgets.get(label) in states and wire_value_of(states[widgets[label]]) == want, "wrong or missing ClientState control: " + label)
        _journey_need(isinstance(dom, dict) and dom.get("selectbox_value") == group and _same_cell_value(0, dom.get("slider_value")) and dom.get("checkbox_checked") is True, "DOM controls differ from this tab ClientState")
        tables = [d for d in deltas if d.get("type") == "new_element" and d.get("element") in ("dataframe", "table")]
        charts = [d for d in deltas if d.get("element") == "vega_lite_chart"]
        context = {"ok": True, "problems": [], "identity": identity, "session": session, "file_id": file_id, "delete_url": delete_url, "info": info}
        if no_result:
            _journey_need(not tables and not charts and dom.get("table_present") is False and dom.get("chart_present") is False
                          and isinstance(dom.get("table_cells"), list) and not _filled_cells(dom["table_cells"]) and dom.get("chart_bars") == 0, "bad file still has a result or missing DOM")
            return context
        return _journey_result_data(context, bundle, frames, window, action, dom, deltas, tables, charts, fixture, group, empty, result_proof)
    except (ValueError, TypeError, KeyError, IndexError, OSError) as exc:
        return {"ok": False, "problems": [str(exc)]}


def _journey_result_data(context, bundle, frames, window, action, dom, deltas, tables, charts, fixture, group, empty, proof):
    _journey_need(len(tables) == 1, "no unique result table after this ClientState on this connection")
    table = _journey_ipc(tables[0].get("arrow"), bundle)
    columns = ["group_key", "row_count", "total_amount", "avg_amount"]
    _journey_need(table["columns"] == columns, "result schema columns/order mismatch")
    types = [line.split(": ", 1)[1].removesuffix(" not null") for line in table["schema"].splitlines()[:4]]
    allowed_group = ("large_string", "null") if empty else ("large_string",)
    _journey_need(types[0] in allowed_group and types[1:] == ["int64", "double", "double"], "result schema field types mismatch")
    from refcore import parse_csv, aggregate
    parsed = parse_csv(fixture.read_bytes())
    expected = [{"group_key": r.group_key, "row_count": r.row_count, "total_amount": float(r.total_amount), "avg_amount": float(r.avg_amount)} for r in aggregate(parsed.rows, group, 0, True)]
    _journey_need(table["rows"] == expected and table["row_count"] == len(expected), "IPC values do not belong to this fixture/controls")
    _journey_need(dom.get("table_present") is True and isinstance(dom.get("table_cells"), list), "missing rendered table DOM")
    if empty:
        _journey_need(not expected and not charts and dom.get("chart_present") is False and dom.get("chart_bars") == 0
                      and len(dom["table_cells"]) in (0, 4) and not _filled_cells(dom["table_cells"]), "empty result contains stale DOM/chart")
    else:
        _journey_need(isinstance(bundle.get("dom_before"), dict), "missing before-action DOM")
        verdict = data_loop_verdict({"kind": "selectbox" if action["action"] == "select" else "file_uploader", "label": "Group by"}, proof["proof_frames"], proof["proof_window"], action, bundle["dom_before"], dom)
        _journey_need(verdict["ok"], "; ".join(verdict["problems"]))
        for chart in charts:
            spec = chart.get("vega_lite_spec") or {}
            _journey_need(spec.get("mark", {}).get("type") == "bar" and spec.get("encoding", {}).get("x", {}).get("field") == "group_key"
                          and spec.get("encoding", {}).get("y", {}).get("field") == "total_amount"
                          and spec["encoding"]["x"].get("sort") == [row["group_key"] for row in expected], "chart does not encode this fixture's grouped totals")
            named = [d for d in chart.get("vega_lite_datasets", []) if d.get("name") == spec.get("data", {}).get("name")]
            _journey_need(len(named) == 1, "chart dataset missing")
            _journey_need(_journey_ipc(named[0].get("arrow"), bundle)["sha256"] == table["sha256"], "chart/table actual IPC differ")
    context["table"] = table
    return context


def _journey_observed(observation, journey, fixture, group, dom, *, tab=None, phase_index=-1, **options):
    try:
        _journey_need(isinstance(observation, dict) and observation.get("journey") == journey, "missing or wrong journey observation")
        raw = observation["tabs"][tab] if tab else observation
        count = 2 if journey == "recover" or tab == "a" else 1
        _journey_need(isinstance(raw.get("phases"), list) and len(raw["phases"]) == count, "missing required journey phases")
        bundle = _journey_bundle(observation, tab=tab, phase_index=phase_index)
        phase = raw["phases"][phase_index]
        _journey_need(isinstance(phase.get("dom_after"), dict) and dom == phase["dom_after"], "DOM is not this phase's observation")
        context = _journey_context(bundle, fixture, group, dom, **options)
        if context["ok"] and journey == "empty":
            table = observation.get("table")
            _journey_need(isinstance(table, dict) and all(table.get(key) == context["table"][key] for key in ("schema", "columns", "rows")), "empty table summary differs from decoded operation IPC")
        dom_key = "after_group_change" if tab == "a" else "after_upload" if tab or journey == "empty" else "after_bad" if phase_index == 0 else "after_good"
        _journey_need(raw.get("dom", {}).get(dom_key) == dom, "published DOM is not the phase observation")
        if context["ok"] and tab:
            _journey_need(set(raw.get("session_ids", [])) == {context["session"]}
                          and raw.get("uploaded", [None])[-1] == context["info"]["name"]
                          and raw.get("group_values_sent", [None])[-1] == group, "tab summary does not belong to its raw state")
        context["bundle"] = bundle
        return context
    except (ValueError, TypeError, KeyError, IndexError, OSError, AttributeError) as exc:
        return {"ok": False, "problems": [str(exc)]}


def _journey_finish(kind, checks):
    return [dict(check, journey=kind) for check in checks]


def recover_checks(alerts_bad, dom_bad, verdict, delete_requests, chips, uploads,
                   frames, good_name, *, observation=None):
    """The checks of the recovery journey: a file that cannot be read, then one that can."""
    checks = []
    observed = observation if isinstance(observation, dict) else {}
    alerts_good = observed["alerts"].get("after_good") if isinstance(observed.get("alerts"), dict) else None
    dom_good = observed["dom"].get("after_good") if isinstance(observed.get("dom"), dict) else None
    bad_context = _journey_observed(observation, "recover", "sales_malformed.csv", "category", dom_bad, phase_index=0, no_result=True)
    good_context = _journey_observed(observation, "recover", "sales_basic.csv", "category", dom_good, phase_index=1)
    verdict = good_context  # Never trust the driver-supplied verdict.ok.
    texts = (alerts_bad or {}).get("alerts") or []
    errors = [text for text in texts if PARSE_ERROR.search(text)]
    checks.append(_check(
        "bad-csv", "file_uploaded",
        "the file the app cannot read to be handed to the uploader",
        "the uploader took the file" if uploads[0] else "the file input was not found",
        uploads[0],
    ))
    checks.append(_check(
        "bad-csv", "error_visible",
        "the page to say that the CSV cannot be parsed",
        errors[0] if errors else json.dumps(texts),
        bool(errors),
    ))
    if dom_bad is None:
        checks.append(_check(
            "bad-csv", "no_result",
            "no table for a file the app cannot read",
            "no DOM observation",
            False,
        ))
    else:
        filled = _filled_cells(dom_bad.get("table_cells"))
        seen = {"cells": dom_bad.get("table_cells"), "bars": dom_bad.get("chart_bars")}
        checks.append(_check(
            "bad-csv", "no_result",
            "no table for a file the app cannot read",
            json.dumps(seen),
            not (filled or dom_bad.get("chart_bars")),
        ))
    checks.append(_check(
        "recover", "file_uploaded",
        "the good file to be handed to the uploader",
        "the uploader took the file" if uploads[1] else "the file input was not found",
        uploads[1],
    ))
    checks.append(_check(
        "recover", "case_verdict",
        "the good file to restore the table and the chart",
        "; ".join((verdict or {}).get("problems") or ["no verdict"]),
        bool((verdict or {}).get("ok")),
    ))
    undecoded = [
        frame for frame in frames
        if (frame.get("decoded") or {}).get("message") == "undecoded"
    ]
    checks.append(_check(
        "recover", "frames_decoded",
        "the frames of the window to be decoded",
        json.dumps([frame.get("error") for frame in undecoded]) if undecoded
        else "every frame decoded",
        bool(frames) and not undecoded,
    ))
    if not delete_requests:
        checks.append(_check(
            "replace", "delete_status",
            "the removed file to be deleted with 204",
            "no delete request was sent",
            False,
        ))
    else:
        wrong = [
            str(request.get("status")) + " for " + str(request.get("url"))
            for request in delete_requests if request.get("status") != 204
        ]
        checks.append(_check(
            "replace", "delete_status",
            "the removed file to be deleted with 204",
            "; ".join(wrong) if wrong
            else json.dumps([request.get("status") for request in delete_requests]),
            not wrong,
        ))
    if chips is None:
        checks.append(_check(
            "replace", "old_file_gone",
            "the page to show only the file that was uploaded last",
            "no DOM observation",
            False,
        ))
    else:
        names = chips.get("chips") or []
        checks.append(_check(
            "replace", "old_file_gone",
            "the page to show only the file that was uploaded last",
            json.dumps(names),
            len(names) == 1 and good_name in names[0],
        ))
    checks.append(_check("bad-csv", "upload_proof", "this bad upload state and completion", bad_context["problems"], bad_context["ok"]))
    checks.append(_check("recover", "upload_proof", "this good upload with actual IPC and DOM values", good_context["problems"], good_context["ok"]))
    clean = (isinstance(alerts_good, dict) and alerts_good.get("alerts") == [] and alerts_good.get("exceptions") == []
             and isinstance(dom_good, dict) and dom_good.get("alerts") == [])
    checks.append(_check("recover", "no_stale_error", "no stale alerts or exceptions after recovery", alerts_good, clean))
    bound = False
    reason = "missing bad/good operation proof"
    if bad_context["ok"] and good_context["ok"]:
        try:
            _journey_need(bad_context["identity"] == good_context["identity"] and bad_context["session"] == good_context["session"], "recovery changed session/connection")
            _journey_need(bad_context["file_id"] != good_context["file_id"], "replacement reused the old file id")
            bad_bundle, good_bundle = bad_context["bundle"], good_context["bundle"]
            replace = good_bundle["window"]
            _journey_need(bad_bundle["window"]["end_timestamp"] <= replace["start_timestamp"], "replacement precedes bad upload completion")
            requests = _journey_http(good_bundle, replace)
            matching = [r for r in requests if r.get("method") == "DELETE" and r.get("url") == bad_context["delete_url"] and r.get("status") == 204]
            _journey_need(matching, "no DELETE204 for the old issued session/file URL in replacement window")
            declared = observed.get("file_urls", {}).get("issued")
            _journey_need(isinstance(declared, list) and any(u.get("file_id") == bad_context["file_id"] and _journey_url(good_bundle["url"], u.get("delete_url"), bad_context["session"], bad_context["file_id"]) == bad_context["delete_url"] for u in declared), "issued URL summary is not the old wire file")
            bound, reason = True, bad_context["delete_url"]
        except (ValueError, TypeError, KeyError, AttributeError) as exc:
            reason = str(exc)
    checks.append(_check("replace", "delete_bound", "DELETE204 for this old issued URL/session/file during replacement", reason, bound))
    return _journey_finish("recover", checks)


def empty_checks(alerts, rows, columns, dom, upload_ok, *, observation=None):
    """The checks of the empty result: the schema stays, the data does not."""
    checks = []
    texts = (alerts or {}).get("alerts") or []
    notes = [text for text in texts if re.search(r"(?i)no data rows|contains no data", text)]
    checks.append(_check(
        "empty-csv", "file_uploaded",
        "the file to be handed to the uploader",
        "the uploader took the file" if upload_ok else "the file input was not found",
        upload_ok,
    ))
    checks.append(_check(
        "empty-csv", "info_visible",
        "the page to say that the file has no data rows",
        notes[0] if notes else json.dumps(texts),
        bool(notes),
    ))
    context = _journey_observed(observation, "empty", "sales_empty.csv", "category", dom, empty=True)
    actual = context.get("table") or {}
    checks.append(_check("empty-csv", "result_present", "the operation's actual IPC table", actual, bool(actual)))
    checks.append(_check("empty-csv", "no_rows", "zero actual IPC rows", actual.get("rows"), "rows" in actual and actual["rows"] == [] and rows == []))
    checks.append(_check("empty-csv", "schema_kept", "all four expected field names/types in decoded IPC", actual.get("schema"),
                         bool(actual) and columns == actual.get("columns")))
    if dom is None:
        checks.append(_check(
            "empty-csv", "no_stale_view",
            "no stale table or chart for an empty result",
            "no DOM observation",
            False,
        ))
    else:
        filled = _filled_cells(dom.get("table_cells"))
        seen = {"cells": dom.get("table_cells"), "bars": dom.get("chart_bars")}
        checks.append(_check(
            "empty-csv", "no_stale_view",
            "no stale table or chart for an empty result",
            json.dumps(seen),
            not (filled or dom.get("chart_bars")),
        ))
    checks.append(_check("empty-csv", "operation_proof", "current upload/clientstate/same connection completion/HTTP/IPC/DOM", context["problems"], context["ok"]))
    return _journey_finish("empty", checks)


def sessions_checks(sessions_a, sessions_b, names_a, names_b, groups_a, groups_b,
                    dom_a, dom_b, uploads_a, uploads_b, *, observation=None):
    """The checks of the two sessions: each tab keeps its own file and controls."""
    checks = []
    checks.append(_check(
        "sessions", "file_uploaded_a",
        "the file of the first tab to be handed to the uploader",
        "the uploader took the file" if uploads_a else "the file input was not found",
        uploads_a,
    ))
    checks.append(_check(
        "sessions", "file_uploaded_b",
        "the file of the second tab to be handed to the uploader",
        "the uploader took the file" if uploads_b else "the file input was not found",
        uploads_b,
    ))
    ids_a = sessions_a or []
    ids_b = sessions_b or []
    checks.append(_check(
        "sessions", "session_ids", "a session id per tab",
        json.dumps([ids_a, ids_b]), bool(ids_a and ids_b)
    ))
    shared = sorted(set(ids_a) & set(ids_b))
    checks.append(_check(
        "sessions", "session_isolation", "a session id of its own per tab",
        json.dumps(shared), not shared
    ))
    name_a = (names_a or [None])[-1]
    name_b = (names_b or [None])[-1]
    checks.append(_check(
        "sessions", "upload_isolation", "each tab to keep its own file",
        json.dumps([name_a, name_b]),
        bool(name_a and name_b and name_a != name_b),
    ))
    checks.append(_check(
        "sessions", "control_isolation", "each tab to send its own group",
        json.dumps([groups_a, groups_b]), bool(groups_a and groups_b)
    ))
    group_a = (groups_a or [None])[-1]
    group_b = (groups_b or [None])[-1]
    checks.append(_check(
        "sessions", "group_isolation", "the group of each tab to be its own",
        json.dumps([group_a, group_b]),
        bool(group_a and group_b and group_a != group_b),
    ))
    if dom_a is None or dom_b is None:
        checks.append(_check(
            "sessions", "results_present", "each tab to render its own result",
            "no DOM observation", False
        ))
    else:
        rows_a = dom_a.get("table_cells") or []
        rows_b = dom_b.get("table_cells") or []
        checks.append(_check(
            "sessions", "results_present", "each tab to render its own result",
            json.dumps({"a": len(rows_a), "b": len(rows_b)}),
            bool(rows_a) and bool(rows_b),
        ))
    result_a = (dom_a or {}).get("table_cells") or (dom_a or {}).get("chart_labels")
    result_b = (dom_b or {}).get("table_cells") or (dom_b or {}).get("chart_labels")
    checks.append(_check(
        "sessions", "result_isolation", "a result of its own per tab",
        json.dumps([result_a, result_b]),
        bool(result_a and result_b and result_a != result_b),
    ))
    a = _journey_observed(observation, "sessions", "sales_basic.csv", "region", dom_a, tab="a")
    b = _journey_observed(observation, "sessions", "sales_unicode.csv", "category", dom_b, tab="b")
    for label, context, sessions, names, groups in (("a", a, ids_a, names_a, groups_a), ("b", b, ids_b, names_b, groups_b)):
        matches = context["ok"] and set(sessions or []) == {context.get("session")} and (names or [None])[-1] == context.get("info", {}).get("name") and (groups or [None])[-1] == ("region" if label == "a" else "category")
        checks.append(_check("sessions", "proof_" + label, "tab's own fixture, ClientState controls, successful completion, IPC and all DOM values", context["problems"] if not context["ok"] else "derived state/summary ownership", matches))
    if a["ok"] and b["ok"]:
        isolated = a["session"] != b["session"] and a["identity"][0] != b["identity"][0] and a["identity"][1] != b["identity"][1]
        for check in checks:
            if check["check"] == "session_isolation":
                check["ok"] = check["ok"] and isolated
    return _journey_finish("sessions", checks)


STAGE2_CASE_ALIASES = {
    "soft-invalid": "soft-invalid", "soft-amount": "soft-invalid",
    "non-utf8": "non-utf8", "not-utf8": "non-utf8",
    "filter-empty": "filter-empty", "filtered-empty": "filter-empty",
    "state": "state", "session-state": "state",
}


def canonical_stage2_case(name):
    """One mapping for CLI/loader IDs. Unknown cases never become basic."""
    if not isinstance(name, str) or name not in STAGE2_CASE_ALIASES:
        raise ValueError(f"unknown stage2 journey: {name!r}")
    return STAGE2_CASE_ALIASES[name]


STAGE2_REQUIRED = {
    "soft-invalid": ("contract", "inputs", "phase_sequence", "upload_binding", "soft_warning", "soft_no_error", "soft_values", "replacement_delete", "recovery_run", "recovery_values", "no_stale_alert"),
    "non-utf8": ("contract", "inputs", "phase_sequence", "upload_binding", "hard_utf8_error", "no_bad_result", "replacement_delete", "recovery_run", "recovery_values", "no_stale_alert"),
    "filter-empty": ("contract", "inputs", "phase_sequence", "baseline_upload", "slider200_state_run", "empty_schema_dom", "distinct_empty_note", "slider0_state_run", "restored_values", "same_file_session"),
    "state": ("contract", "inputs", "phase_sequence", "initial_run1_pulse0", "selector_once_counts", "upload_preparation", "pulse_once_counts", "distinct_run_markers", "fresh_unchanged_values", "same_file_session"),
}
JOURNEY_REQUIRED.update({kind: {(kind, key) for key in keys} for kind, keys in STAGE2_REQUIRED.items()})

# Fixed manifest coverage, never a caller-supplied list that can omit missing pictures.
# Each tuple is (step id, tab or None, phase index). A picture may attest multiple
# semantically identical steps, but J06-S1 requires a picture from each tab.
STAGE2_SCREENSHOTS = {
    "data-loop": [(sid, None, index) for sid, index in (
        ("J00-S2", 0), ("J01-S1", 0), ("J03-S1", 0), ("J00-S3", 1), ("J01-S2", 1),
        ("J02-S1", 1), ("J03-S3", 1), ("J00-S5", 2), ("J02-S2", 2), ("J02-S3", 3))],
    "recover": [("J07-S1", None, 0), ("J07-S3", None, 1)],
    "empty": [("J08-S1", None, 0)],
    "sessions": [("J06-S1", "a", 1), ("J06-S1", "b", 0), ("J01-S4", "b", 0)],
    "state": [("J04-S1", None, 0), ("J04-S2", None, 1), ("J04-S3", None, 3)],
    "soft-invalid": [("J07-S2", None, 0)],
    "non-utf8": [("J07-S4", None, 0), ("J07-S4", None, 1)],
    "filter-empty": [("J08-S2", None, 1), ("J08-S3", None, 2)],
}
# A capture observation budget, not a Streamlit execution/latency requirement.
# It also rejects a Date.now epoch substituted for CDP monotonic seconds when
# the last phase has no following action to supply an upper time boundary.
STAGE2_SCREENSHOT_MAX_LAG_SECONDS = 60.0
for _kind, _roles in STAGE2_SCREENSHOTS.items():
    JOURNEY_REQUIRED["screenshots/" + _kind] = {("screenshots", "records"), *{(sid, f"png_proof/{tab or 'main'}/{index}") for sid, tab, index in _roles}}


def _stage2_target_upload_run(frames, *, namespace, start, end, widget_id, file_id, file_name):
    """Pure-frame readiness for a newly issued upload, never the clear run.

    The driver polls with end=len(frames), then observes DOM/IPC/PNG only after
    ok. Indices refer to the original list; neither frames nor events change.
    Missing or invalid evidence is not ready, with an explicit reason.
    """
    try:
        _journey_need(isinstance(frames, list) and type(start) is int and type(end) is int
                      and 0 <= start < end <= len(frames), "missing upload frame window")
        _journey_need(all(isinstance(v, str) and v for v in (namespace, widget_id, file_id, file_name)),
                      "missing expected namespace/widget/file identity")
        selected = frames[start:end]
        _journey_need(all(f.get("namespace") == namespace for f in selected), "upload window crosses namespaces")
        identities = {(f.get("connection"), f.get("request_id")) for f in selected}
        _journey_need(len(identities) == 1 and all(v is not None and v != "" for v in next(iter(identities))),
                      "upload window crosses or lacks connection/requestId")
        # The established binder selects by filename; additionally require the
        # exact newly issued file ID before using its unchanged run logic.
        candidates = []
        for index in range(start, end):
            frame = frames[index]
            if frame.get("direction") != "client->server" or frame.get("decoded", {}).get("type") != "rerun_script":
                continue
            states = [v for v in frame["decoded"]["rerun_script"].get("widget_states", []) if v.get("id") == widget_id]
            if len(states) != 1 or states[0].get("value_field") != "file_uploader_state_value":
                continue
            infos = states[0].get("value_full", {}).get("uploadedFileInfo")
            if isinstance(infos, list) and len(infos) == 1 and infos[0].get("fileId") == file_id and infos[0].get("name") == file_name:
                candidates.append(index)
        _journey_need(len(candidates) == 1, "missing or ambiguous newly issued file ClientState")
        normalized = [dict(f, target=f.get("namespace")) for f in frames]
        proof = _journey_run_verdict(normalized, {"start": start, "end": end, "widget": widget_id, "target": namespace},
                                     {"action": "upload", "ok": True}, file_name, "category")
        _journey_need(proof["ok"] and proof["state_frame"] == candidates[0], "target file run proof failed")
        return {"ok": True, "problems": [], **{key: proof[key] for key in
                ("state_frame", "run_start_frame", "completion_frame", "script_run_id")}}
    except (ValueError, TypeError, KeyError, IndexError, AttributeError) as exc:
        return {"ok": False, "problems": [str(exc)]}


def soft_invalid_checks(*, observation=None):
    return _stage2_specific_checks("soft-invalid", observation)


def non_utf8_checks(*, observation=None):
    return _stage2_specific_checks("non-utf8", observation)


def filter_empty_checks(*, observation=None):
    return _stage2_specific_checks("filter-empty", observation)


def _stage2_typed_controls(deltas, state, dom, minimum=0, *, group="category", include_unknown=True):
    """Match each actual server Element's ID, one typed ClientState, and DOM."""
    _journey_need(isinstance(state, list) and isinstance(dom, dict), "missing controls/DOM")
    _journey_need(type(include_unknown) is bool, "invalid expected checkbox contract")
    ids = {}
    for kind, label, field, expected in (("selectbox", "Group by", "string_value", group),
                                         ("slider", "Minimum amount", "double_array_value", [minimum]),
                                         ("checkbox", "Include unknown region", "bool_value", include_unknown)):
        elements = [d for d in deltas if d.get("type") == "new_element" and d.get("element") == kind and d.get("label") == label]
        _journey_need(len(elements) == 1 and isinstance(elements[0].get("id"), str) and elements[0]["id"], "missing/ambiguous source Element: " + label)
        identity = elements[0]["id"]
        _journey_need(identity not in ids.values(), "controls share a source widget ID")
        ids[kind] = identity
        values = [v for v in state if v.get("id") == identity]
        _journey_need(len(values) == 1 and values[0].get("value_field") == field, "missing/duplicated/wrong-type ClientState: " + label)
        value = values[0]
        if kind == "slider":
            actual = value.get("value_full", {}).get("data")
            _journey_need(isinstance(actual, list) and len(actual) == 1 and type(actual[0]) in (int, float)
                          and actual == expected, "wrong explicit slider ClientState")
        elif kind == "checkbox":
            _journey_need(value.get("value") is include_unknown, "wrong explicit checkbox ClientState")
        else:
            _journey_need(value.get("value") == expected, "wrong explicit selector ClientState")
    _journey_need(not any(v.get("value_field") == "trigger_value" and v.get("value") is True for v in state), "unexpected callback/button trigger")
    _journey_need(dom.get("selectbox_value") == group and _same_cell_value(minimum, dom.get("slider_value"))
                  and dom.get("checkbox_checked") is include_unknown, "DOM controls contradict ClientState")
    return ids


def _stage2_specific_input(phase, filename):
    expected = {
        "sales_basic.csv": (737, "9692a718edc5bec8f3fee1cfec4f454338c8f8d675cd34c17cdb5bf4403d8d00"),
        "sales_with_missing.csv": (739, "ce8b7f62c729c856ad85c496e044c25ef0f3594e2b3b558fb31e9213122e512d"),
        "sales_latin1.csv": (735, "f73e63eb66c2dccd9285b573094b59c59e5dacd3ece0ef26d48ca3728371d541"),
    }
    path = REPO_ROOT / "tests/fixtures/csv" / filename
    data = path.read_bytes()
    action = phase["action"]
    _journey_need(action.get("action") == "upload" and action.get("ok") is True and not action.get("failed")
                  and pathlib.Path(action["file"]).resolve() == path.resolve()
                  and (len(data), hashlib.sha256(data).hexdigest()) == expected[filename]
                  and (action.get("file_bytes"), action.get("file_sha256")) == expected[filename], "wrong actual fixture/action fingerprint: " + filename)
    if filename == "sales_latin1.csv":
        try:
            data.decode("utf-8")
        except UnicodeDecodeError as exc:
            _journey_need(exc.start == 101 and data[exc.start] == 0xe9 and exc.reason == "invalid continuation byte", "wrong measured non-UTF8 input")
        else:
            raise ValueError("non-UTF8 fixture is valid UTF-8")


def _stage2_run_parts(observation, phase, proof):
    frames = observation["frames"]
    state = frames[proof["state_frame"]]["decoded"]["rerun_script"]["widget_states"]
    deltas = [f["decoded"]["delta"] for f in frames[proof["run_start_frame"]+1:proof["completion_frame"]]
              if f.get("direction") == "server->client" and f.get("decoded", {}).get("type") == "delta"]
    return state, deltas


def _stage2_specific_counters(deltas, dom, runs):
    if dom is not None:
        _journey_need((_stage2_counter(dom, "script_runs"), _stage2_counter(dom, "pulses")) == (runs, 0), "wrong DOM run/callback counters")
    for label, want in (("Script runs", runs), ("Pulses", 0)):
        values = [int(m[1]) for d in deltas if d.get("element") in ("text", "markdown") and isinstance(d.get("body"), str)
                  and (m := re.fullmatch(re.escape(label) + r":\s*(\d+)", d["body"].strip()))]
        _journey_need(values == [want], "wrong/missing/duplicated wire counter: " + label)


def _stage2_specific_alerts(deltas, dom, expected):
    alerts = [d.get("alert") for d in deltas if d.get("element") == "alert"]
    _journey_need(all(isinstance(v, dict) for v in alerts)
                  and [(v.get("format"), v.get("body")) for v in alerts] == expected,
                  "wrong/missing/stale wire error/warning/info")
    _journey_need(dom.get("exceptions") == [] and dom.get("alerts") == [body for _, body in expected], "wrong/missing/stale DOM alerts/exceptions")


def _stage2_replacement_evidence(kind, observation, bundle):
    phases, frames = observation["phases"], observation["frames"]
    filename = "sales_with_missing.csv" if kind == "soft-invalid" else "sales_latin1.csv"
    contexts, proofs, runs = [], [], []
    # Reuse existing issued URL, PUT, session, IPC/schema/value and DOM proof.
    # Only the driver success key is adapted; frames and phase events stay intact.
    adapted = dict(observation, uploads={"bad": observation["uploads"].get("soft" if kind == "soft-invalid" else "bad"),
                                        "good": observation["uploads"].get("good")})
    for index, name in enumerate((filename, "sales_basic.csv")):
        phase = phases[index]
        _stage2_specific_input(phase, name)
        current = _journey_bundle(adapted, phase_index=index)
        context = _journey_context(current, name, "category", phase["dom_after"], no_result=kind == "non-utf8" and index == 0)
        _journey_need(context["ok"], "; ".join(context["problems"]))
        uploader = current["window"]["widget"]
        proof = _stage2_target_upload_run(frames, namespace=observation["namespace"], start=phase["start"], end=phase["end"],
                                         widget_id=uploader, file_id=context["file_id"], file_name=name)
        _journey_need(proof["ok"], "; ".join(proof["problems"]))
        state, deltas = _stage2_run_parts(observation, phase, proof)
        _stage2_typed_controls(deltas, state, phase["dom_after"])
        _stage2_specific_counters(deltas, phase["dom_after"], 2 if index == 0 else 4)
        runs.append((state, deltas));contexts.append(context);proofs.append(proof)
    bad, good = contexts
    _journey_need(bad["identity"] == good["identity"] and bad["session"] == good["session"] and bad["file_id"] != good["file_id"], "replacement changed connection/session or reused file ID")
    phase = phases[1]
    http = _journey_http(bundle, phase)
    deletions = [h for h in http if h.get("method") == "DELETE" and h.get("url") == bad["delete_url"] and h.get("status") == 204]
    _journey_need(len(deletions) == 1, "no unique old-issued-file DELETE204 in replacement action window")
    _journey_need(not any(h.get("method") == "DELETE" and h.get("url") == good["delete_url"] for h in http), "new target file was deleted")
    _stage2_specific_alerts(runs[1][1], phase["dom_after"], [])
    _stage2_specific_clear_chain(observation, phase, proofs[1], good, bundle)
    if kind == "soft-invalid":
        message = "2 row(s) with an unusable 'amount' were excluded from the aggregation."
        _stage2_specific_alerts(runs[0][1], phases[0]["dom_after"], [("WARNING", message)])
        _journey_need(sum(row["row_count"] for row in bad["table"]["rows"]) == 10 and bad["table"]["row_count"] == 4, "soft result is not the measured 10 valid rows/four groups")
    else:
        prefix = "Could not parse the uploaded CSV: the uploaded file is not valid UTF-8"
        measured = (prefix, prefix + ": 'utf-8' codec can't decode byte 0xe9 in position 101: invalid continuation byte")
        errors = [d.get("alert", {}).get("body") for d in runs[0][1] if d.get("element") == "alert" and d.get("alert", {}).get("format") == "ERROR"]
        _journey_need(len(errors) == 1 and errors[0] in measured, "wrong measured non-UTF8 error")
        _stage2_specific_alerts(runs[0][1], phases[0]["dom_after"], [("ERROR", errors[0]), ("INFO", "Upload a valid CSV to continue.")])


def _stage2_specific_clear_chain(observation, phase, proof, good, bundle, *, before_runs=2):
    """Only the observed empty-uploader run may finish early before target run."""
    frames = observation["frames"]
    indices = range(phase["start"], phase["end"])
    clients = [i for i in indices if frames[i].get("direction") == "client->server" and frames[i].get("decoded", {}).get("type") == "rerun_script"]
    markers = [i for i in indices if frames[i].get("decoded", {}).get("type") == "new_session"]
    finishes = [i for i in indices if frames[i].get("decoded", {}).get("type") == "script_finished"]
    _journey_need(len(clients) == len(markers) == len(finishes) == 2 and clients[0] < markers[0] < clients[1]
                  and clients[1] == proof["state_frame"] and finishes[0] < markers[1] == proof["run_start_frame"]
                  and finishes[1] == proof["completion_frame"], "replacement is not the measured clear-state then new-target chain")
    clear = frames[clients[0]]["decoded"]["rerun_script"]["widget_states"]
    uploader = bundle["window"]["widget"]
    values = [v for v in clear if v.get("id") == uploader]
    _journey_need(len(values) == 1 and values[0].get("value_field") == "file_uploader_state_value"
                  and isinstance(values[0].get("value_full"), dict)
                  and values[0]["value_full"].get("uploadedFileInfo") in (None, []), "first replacement state did not clear the old uploader")
    old = frames[markers[0]]["decoded"]["new_session"]
    previous_ids = {f.get("decoded", {}).get("new_session", {}).get("script_run_id") for f in frames[:markers[0]]
                    if f.get("namespace") == observation["namespace"] and f.get("decoded", {}).get("type") == "new_session"}
    _journey_need(old.get("session_id") == good["session"] and old.get("script_run_id")
                  and old["script_run_id"] not in previous_ids and old["script_run_id"] != proof["script_run_id"], "clear/target run marker/session mismatch")
    status = frames[finishes[0]]["decoded"]["script_finished"].get("status")
    _journey_need(type(status) is int and status in (0, 2), "clear run compiled/failed instead of finishing or yielding to rerun")
    _journey_need(status != 2 or clients[1] < finishes[0], "early clear finish has no superseding target ClientState")
    deltas = [f["decoded"]["delta"] for f in frames[markers[0]+1:finishes[0]] if f.get("decoded", {}).get("type") == "delta"]
    _stage2_typed_controls(deltas, clear, phase["dom_before"])
    _journey_need(not any(d.get("element") in ("dataframe", "table", "vega_lite_chart") for d in deltas), "clear run rendered stale result")
    alerts = [d.get("alert", {}) for d in deltas if d.get("element") == "alert"]
    _journey_need([(v.get("format"), v.get("body")) for v in alerts] == [("INFO", "Upload a CSV to see the aggregated result.")], "clear run did not show the measured empty-uploader info")
    if status == 0:
        _stage2_specific_counters(deltas, None, before_runs+1)
    else:
        # An early rerun may stop before captions, but emitted captions must be truthful.
        for label, want in (("Script runs", before_runs+1), ("Pulses", 0)):
            values = [int(m[1]) for d in deltas if isinstance(d.get("body"), str)
                      and (m := re.fullmatch(re.escape(label) + r":\s*(\d+)", d["body"].strip()))]
            _journey_need(values in ([], [want]), "interrupted clear run has wrong counters")
    _journey_need((_stage2_counter(phase["dom_before"], "script_runs"), _stage2_counter(phase["dom_before"], "pulses")) == (before_runs, 0), "wrong before-replacement counters")


def _filtered_empty_view(table, charts, dom, deltas):
    """Only measured zero-row filtering mode accepts double/large_string keys."""
    columns = ["group_key", "row_count", "total_amount", "avg_amount"]
    types = [line.split(": ", 1)[1].removesuffix(" not null") for line in table["schema"].splitlines()[:4]]
    _journey_need(table["columns"] == columns and len(types) == 4 and types[1:] == ["int64", "double", "double"]
                  and types[0] in ("double", "large_string") and table["row_count"] == 0 and table["rows"] == [], "filter-empty schema/rows mismatch")
    _journey_need(dom.get("table_present") is True and isinstance(dom.get("table_cells"), list)
                  and len(dom["table_cells"]) in (0, 4) and not _filled_cells(dom["table_cells"])
                  and not charts and dom.get("chart_present") is False and dom.get("chart_bars") == 0
                  and dom.get("chart_marks") == "", "filtered-empty DOM/chart contains stale data")
    _stage2_specific_alerts(deltas, dom, [("INFO", "No rows match the current filters.")])


def _stage2_filtered_evidence(observation, bundle, *, baseline_runs=2):
    phases, frames = observation["phases"], observation["frames"]
    _stage2_specific_input(phases[0], "sales_basic.csv")
    adapted = dict(observation, uploads={"bad": observation.get("uploads", {}).get("file")})
    upload_bundle = _journey_bundle(adapted, phase_index=0)
    baseline = _journey_context(upload_bundle, "sales_basic.csv", "category", phases[0]["dom_after"])
    _journey_need(baseline["ok"], "; ".join(baseline["problems"]))
    upload_proof = _stage2_target_upload_run(frames, namespace=observation["namespace"], start=phases[0]["start"], end=phases[0]["end"],
        widget_id=upload_bundle["window"]["widget"], file_id=baseline["file_id"], file_name="sales_basic.csv")
    _journey_need(upload_proof["ok"], "; ".join(upload_proof["problems"]))
    state, deltas = _stage2_run_parts(observation, phases[0], upload_proof)
    _stage2_typed_controls(deltas, state, phases[0]["dom_after"])
    _stage2_specific_counters(deltas, phases[0]["dom_after"], baseline_runs)
    _stage2_specific_alerts(deltas, phases[0]["dom_after"], [])
    run_ids = {upload_proof["script_run_id"]}
    for index, minimum in ((1, 200), (2, 0)):
        phase = phases[index]
        action = phase["action"]
        _journey_need(action.get("action") == "slider" and action.get("label") == "Minimum amount"
                      and type(action.get("value")) in (int, float) and action["value"] == minimum, "wrong filter action")
        run = _stage2_phase_run(observation, phase)
        _journey_need(run["identity"] == baseline["identity"] and run["session"] == baseline["session"]
                      and run["run"] not in run_ids, "filter changed connection/session or reused run")
        run_ids.add(run["run"])
        state = frames[run["state_index"]]["decoded"]["rerun_script"]["widget_states"]
        ids = _stage2_typed_controls(run["deltas"], state, phase["dom_after"], minimum)
        _stage2_specific_counters(run["deltas"], phase["dom_after"], index+baseline_runs)
        _journey_need((_stage2_counter(phase["dom_before"], "script_runs"), _stage2_counter(phase["dom_before"], "pulses")) == (index+baseline_runs-1, 0), "wrong before-filter counters")
        uploaders = [d for d in run["deltas"] if d.get("element") == "file_uploader" and d.get("label") == "Upload sales CSV"]
        _journey_need(len(uploaders) == 1 and uploaders[0].get("id") == upload_bundle["window"]["widget"], "filter changed uploader widget")
        values = [v for v in state if v.get("id") == uploaders[0]["id"]]
        _journey_need(len(values) == 1 and values[0].get("value_field") == "file_uploader_state_value"
                      and values[0].get("value_full", {}).get("uploadedFileInfo") == [baseline["info"]], "filter changed/lost uploaded file")
        _journey_need(not any(h.get("method") in ("PUT", "DELETE") for h in _journey_http(bundle, phase)), "filter unexpectedly uploaded/deleted a file")
        tables = [d for d in run["deltas"] if d.get("element") in ("dataframe", "table")]
        charts = [d for d in run["deltas"] if d.get("element") == "vega_lite_chart"]
        _journey_need(len(tables) == 1, "filter has no unique fresh table in target run")
        table = _journey_ipc(tables[0].get("arrow"), bundle)
        columns = ["group_key", "row_count", "total_amount", "avg_amount"]
        types = [line.split(": ", 1)[1].removesuffix(" not null") for line in table["schema"].splitlines()[:4]]
        _journey_need(table["columns"] == columns and len(types) == 4 and types[1:] == ["int64", "double", "double"], "filtered schema/order/types mismatch")
        dom = phase["dom_after"]
        if minimum == 200:
            _filtered_empty_view(table, charts, dom, run["deltas"])
        else:
            _journey_need(types[0] == "large_string" and table["rows"] == baseline["table"]["rows"]
                          and table["row_count"] == baseline["table"]["row_count"], "restored IPC differs from the real baseline values")
            window = {"start": phase["start"], "end": phase["end"], "target": observation["namespace"], "widget": ids["slider"]}
            verdict = data_loop_verdict({"kind": "slider", "label": "Minimum amount"}, bundle["frames"], window,
                                       {"action": "slider", "ok": True}, phase["dom_before"], dom)
            _journey_need(verdict["ok"], "; ".join(verdict["problems"]))
            _journey_need(len(charts) == 1, "restored chart is absent/duplicated")
            spec = charts[0].get("vega_lite_spec") or {}
            _journey_need(spec.get("mark", {}).get("type") == "bar" and spec.get("encoding", {}).get("x", {}).get("field") == "group_key"
                          and spec["encoding"]["x"].get("sort") == [v["group_key"] for v in table["rows"]]
                          and spec.get("encoding", {}).get("y", {}).get("field") == "total_amount", "restored chart fields/order mismatch")
            datasets = [v for v in charts[0].get("vega_lite_datasets", []) if v.get("name") == spec.get("data", {}).get("name")]
            _journey_need(len(datasets) == 1 and _journey_ipc(datasets[0].get("arrow"), bundle)["sha256"] == table["sha256"], "restored named dataset differs from table")
            _stage2_specific_alerts(run["deltas"], dom, [])


def _stage2_specific_checks(kind, observation):
    """Three bounded cases share the reviewed reader, run binder and PNG proof."""
    try:
        _journey_need(isinstance(observation, dict) and observation.get("contract") == "journey-stage2-v1"
                      and observation.get("journey") == kind, "missing/wrong specific case contract")
        names = {"soft-invalid": ["upload-soft", "replace-baseline"], "non-utf8": ["upload-utf8", "replace-baseline"],
                 "filter-empty": ["upload-baseline", "slider-200", "slider-0"]}[kind]
        phases = observation.get("phases")
        _journey_need(isinstance(phases, list) and [p.get("name") for p in phases] == names, "missing/reordered specific phases")
        _journey_need(all(phases[i]["end"] <= phases[i+1]["start"] for i in range(len(phases)-1)), "specific phase windows overlap")
        bundle = _journey_bundle(observation, phase_index=0)
        _journey_need(observation.get("namespace") == bundle["source"], "observation namespace differs from frames")
        _journey_need(all(p.get("action", {}).get("ok") is True and not p["action"].get("failed") for p in phases), "unobserved/failed case action")
        _journey_need(all(type(f["decoded"]["script_finished"].get("status")) is int for p in phases
                          for f in observation["frames"][p["start"]:p["end"]] if f.get("decoded", {}).get("type") == "script_finished"), "invalid completion status type")
        if kind == "filter-empty":
            _stage2_filtered_evidence(observation, bundle)
        else:
            _stage2_replacement_evidence(kind, observation, bundle)
        pictures = journey_result(screenshot_checks(observation=observation))
        _journey_need(pictures["ok"], "PNG proof failed: " + "; ".join(str(v.get("actual")) for v in pictures["failures"]))
    except (ValueError, TypeError, KeyError, IndexError, OSError, AttributeError) as exc:
        actual, ok = str(exc), False
    else:
        actual, ok = "actual file/state/run/HTTP/IPC/DOM/PNG evidence checked", True
    return _journey_finish(kind, [_check(kind, key, "complete measured specific-case evidence", actual, ok) for key in STAGE2_REQUIRED[kind]])


def _stage2_phase_run(observation, phase):
    """J04's bounded one-input/one-run contract, using recorded frames only."""
    frames = observation["frames"]
    start, end = phase.get("start"), phase.get("end")
    _journey_need(type(start) is int and type(end) is int and 0 <= start < end <= len(frames), "missing phase frame window")
    selected = frames[start:end]
    identity = (observation.get("namespace"), selected[0].get("request_id"), selected[0].get("connection"))
    _journey_need(isinstance(identity[0], str) and identity[0] and identity[1] and identity[2] is not None, "missing source/connection/requestId")
    _journey_need(all((f.get("namespace"), f.get("request_id"), f.get("connection")) == identity for f in selected), "crossed phase source/connection/requestId")
    stamps = [f.get("timestamp") for f in selected]
    _journey_need(all(type(t) in (int, float) and math.isfinite(t) for t in stamps) and stamps == sorted(stamps)
                  and phase.get("start_timestamp") == stamps[0] and phase.get("end_timestamp") == stamps[-1], "phase clock differs from raw")
    clients = [i for i in range(start, end) if frames[i].get("direction") == "client->server" and frames[i].get("decoded", {}).get("type") == "rerun_script"]
    runs = [i for i in range(start, end) if frames[i].get("direction") == "server->client" and frames[i].get("decoded", {}).get("type") == "new_session"]
    finishes = [i for i in range(start, end) if frames[i].get("direction") == "server->client" and frames[i].get("decoded", {}).get("type") == "script_finished"]
    _journey_need(len(clients) == len(runs) == len(finishes) == 1 and clients[0] < runs[0] < finishes[0], "phase must contain one actual ClientState/new run/completion")
    _journey_need(frames[finishes[0]]["decoded"]["script_finished"].get("status") == 0, "phase run failed")
    session = frames[runs[0]]["decoded"]["new_session"]
    _journey_need(session.get("script_run_id") and session.get("session_id"), "missing real run/session marker")
    _journey_need(not any(f.get("decoded", {}).get("message") == "undecoded" for f in selected), "undecoded phase")
    return {"identity": identity, "session": session["session_id"], "run": session["script_run_id"], "state_index": clients[0],
            "finish_index": finishes[0], "deltas": [f["decoded"]["delta"] for f in frames[runs[0]+1:finishes[0]]
                if f.get("direction") == "server->client" and f.get("decoded", {}).get("type") == "delta"]}


def _stage2_counter(dom, key):
    _journey_need(isinstance(dom, dict) and key in dom and type(dom[key]) in (str, int), "missing actual DOM counter: " + key)
    text = str(dom[key])
    _journey_need(re.fullmatch(r"\d+", text.strip()) is not None, "invalid DOM counter: " + key)
    return int(text)


def _stage2_static_view(observation, phase, run, *, expected_rows=None):
    """Fresh J04 view validation without data_loop's mandatory-change rule."""
    deltas = [d for d in run["deltas"] if d.get("type") == "new_element"]
    tables = [d for d in deltas if d.get("element") == "dataframe"]
    charts = [d for d in deltas if d.get("element") == "vega_lite_chart"]
    _journey_need(len(tables) == len(charts) == 1, "phase has no unique fresh table/chart in its run")
    kept = phase.get("ipc")
    _journey_need(isinstance(kept, dict) and kept.get("table") and kept.get("chart"), "missing phase IPC artifacts")
    arrows = [kept["table"].get("arrow"), kept["chart"].get("arrow"), *[v.get("arrow") for v in kept["chart"].get("datasets", [])]]
    files = {a["sha256"]: a["file"] for a in arrows if a and a.get("sha256") and a.get("file")}
    bundle = {"ipc_dir": observation["ipc_dir"], "ipc_files": files}
    table = _journey_ipc(tables[0].get("arrow"), bundle)
    _journey_need(all(kept["table"]["arrow"].get(k) == table[k] for k in ("sha256", "bytes", "schema", "columns", "rows", "row_count")), "phase table artifact summary differs from wire")
    columns = ["group_key", "row_count", "total_amount", "avg_amount"]
    _journey_need(table["columns"] == columns and [s.split(": ", 1)[1].removesuffix(" not null") for s in table["schema"].splitlines()[:4]] == ["large_string", "int64", "double", "double"], "state result schema mismatch")
    if expected_rows is None:
        from refcore import parse_csv, aggregate
        data = (REPO_ROOT / "tests/fixtures/csv/sales_basic.csv").read_bytes()
        expected = [{"group_key": v.group_key, "row_count": v.row_count, "total_amount": float(v.total_amount), "avg_amount": float(v.avg_amount)} for v in aggregate(parse_csv(data).rows, "region", 0, True)]
    else:
        expected = expected_rows
    _journey_need(table["rows"] == expected and table["row_count"] == len(expected), "state IPC does not contain the expected region totals")
    dom = phase["dom_after"]
    cells = [row[c] for row in expected for c in columns]
    _journey_need(dom.get("table_present") is True and dom.get("chart_present") is True and isinstance(dom.get("table_cells"), list)
                  and len(dom["table_cells"]) == len(cells) and all(_same_cell_value(a, b) for a, b in zip(cells, dom["table_cells"])), "state DOM cells differ from actual data")
    chart = charts[0]
    spec = chart.get("vega_lite_spec") or {}
    name = spec.get("data", {}).get("name")
    datasets = [v for v in chart.get("vega_lite_datasets", []) if v.get("name") == name]
    _journey_need(len(datasets) == 1 and _journey_ipc(datasets[0].get("arrow"), bundle)["sha256"] == table["sha256"], "state chart references different or missing IPC")
    _journey_need(kept["chart"].get("vega_lite_spec") == spec, "phase chart spec is not the actual wire spec")
    _journey_need(spec.get("mark", {}).get("type") == "bar" and spec.get("encoding", {}).get("x", {}).get("field") == "group_key"
                  and spec["encoding"]["x"].get("sort") == [r["group_key"] for r in expected]
                  and spec.get("encoding", {}).get("y", {}).get("field") == "total_amount", "state chart does not encode the region totals")
    bars = _bar_geometry(dom.get("chart_marks"))
    _journey_need(type(dom.get("chart_bars")) is int and dom["chart_bars"] == len(expected) == len(bars), "state DOM bar count differs from data")
    ratios = [bar["height"] / row["total_amount"] for bar, row in zip(bars, expected)]
    baselines = [bar["top"] + bar["height"] for bar in bars]
    _journey_need(all(math.isfinite(v) and v > 0 for v in ratios) and max(ratios)-min(ratios) <= max(1e-6, max(ratios)*1e-6)
                  and max(baselines)-min(baselines) <= 1e-6, "state bar geometry differs from the actual totals")
    return {"rows": table["rows"], "columns": columns, "encoding": spec["encoding"], "mark": spec["mark"]}


def state_checks(*, observation=None):
    """J04 is browser rerun behavior; it does not claim stop/rerun framework APIs."""
    checks = []
    def record(key, ok, actual):
        checks.append(_check("state", key, "strict stage2 state evidence", actual, ok))
    try:
        _journey_need(isinstance(observation, dict) and observation.get("contract") == "journey-stage2-v1" and observation.get("journey") == "state", "missing stage2 state observation")
        record("contract", True, "journey-stage2-v1/state")
        phases = observation.get("phases")
        _journey_need(isinstance(phases, list) and [p.get("name") for p in phases] == ["initial", "selector", "upload-baseline", "pulse"], "missing or reordered required phases")
        _journey_need(all(phases[i]["end"] <= phases[i+1]["start"] for i in range(3)), "phase frame windows overlap")
        record("phase_sequence", True, [p["name"] for p in phases])
        action = phases[2]["action"]
        file = REPO_ROOT / "tests/fixtures/csv/sales_basic.csv"
        data = file.read_bytes()
        _journey_need(action.get("file_sha256") == hashlib.sha256(data).hexdigest() and action.get("file_bytes") == len(data)
                      and pathlib.Path(action["file"]).resolve() == file.resolve(), "wrong or missing baseline input fingerprint")
        record("inputs", True, action["file_sha256"])
        runs = [_stage2_phase_run(observation, phase) for phase in phases]
        _journey_need(len({r["run"] for r in runs}) == 4, "run markers are missing or reused")
        record("distinct_run_markers", True, [r["run"] for r in runs])
        _journey_need(len({r["identity"] for r in runs}) == len({r["session"] for r in runs}) == 1, "state actions switched source/connection/session")
        frames = observation["frames"]
        states = []
        for index, (phase, run, expected) in enumerate(zip(phases, runs, [(1,0),(2,0),(3,0),(4,1)])):
            _journey_need(phase.get("action", {}).get("ok") is True and not phase["action"].get("failed"), "phase action failed or was not observed")
            dom = phase.get("dom_after")
            actual = (_stage2_counter(dom, "script_runs"), _stage2_counter(dom, "pulses"))
            _journey_need(actual == expected, "wrong DOM run/pulse count in " + phase["name"])
            if index:
                before = phase.get("dom_before")
                _journey_need((_stage2_counter(before, "script_runs"), _stage2_counter(before, "pulses")) == [(1,0),(2,0),(3,0)][index-1], "wrong or missing before-action counters")
            bodies = [d.get("body") for d in run["deltas"] if d.get("element") in ("text", "markdown") and isinstance(d.get("body"), str)]
            for label, want in zip(("Script runs", "Pulses"), expected):
                values = [int(m[1]) for body in bodies if (m := re.fullmatch(re.escape(label) + r":\s*(\d+)", body.strip()))]
                _journey_need(values == [want], "wire counter missing/wrong/duplicated: " + label)
            group = "category" if index == 0 else "region"
            _journey_need(dom.get("selectbox_value") == group and _same_cell_value(0, dom.get("slider_value")) and dom.get("checkbox_checked") is True, "state DOM controls are wrong")
            state = frames[run["state_index"]]["decoded"]["rerun_script"].get("widget_states")
            _journey_need(isinstance(state, list), "missing ClientState widgets")
            states.append(state)
            ids = {d.get("label"): d.get("id") for d in run["deltas"] if d.get("element") in ("selectbox", "button", "file_uploader", "slider", "checkbox")}
            if index:
                expected_source_widget_ids = {}
                for kind, label, field in (("selectbox", "Group by", "string_value"),
                                           ("slider", "Minimum amount", "double_array_value"),
                                           ("checkbox", "Include unknown region", "bool_value")):
                    elements = [d for d in run["deltas"] if d.get("type") == "new_element"
                                and d.get("element") == kind and d.get("label") == label]
                    _journey_need(len(elements) == 1 and isinstance(elements[0].get("id"), str)
                                  and elements[0]["id"], "missing/ambiguous source Element: " + label)
                    widget_id = elements[0]["id"]
                    _journey_need(widget_id not in expected_source_widget_ids.values(), "source controls share a widget ID")
                    expected_source_widget_ids[kind] = widget_id
                    selected = [v for v in state if v.get("id") == widget_id]
                    _journey_need(len(selected) == 1 and selected[0].get("value_field") == field,
                                  "missing/duplicated/wrong-type ClientState: " + label)
                    value = selected[0]
                    if kind == "slider":
                        values = value.get("value_full", {}).get("data")
                        _journey_need(isinstance(values, list) and len(values) == 1
                                      and type(values[0]) in (int, float) and values[0] == 0,
                                      "slider ClientState is not the explicit numeric [0]")
                    elif kind == "checkbox":
                        _journey_need(value.get("value") is True, "checkbox ClientState is not explicit true")
                    else:
                        _journey_need(value.get("value") == "region", "selector ClientState is not region")
            triggers = [v for v in state if v.get("value_field") == "trigger_value" and v.get("value") is True]
            if index == 3:
                _journey_need(phase["action"].get("action") == "button" and phase["action"].get("label") == "Pulse"
                              and len(triggers) == 1 and ids.get("Pulse") and triggers[0].get("id") == ids["Pulse"], "Pulse missing, doubled, or bound to another button")
            else:
                _journey_need(not triggers, "unexpected trigger before Pulse")
        _journey_need(phases[0]["action"].get("action") == "initial" and phases[1]["action"].get("action") == "select-option" and phases[1]["action"].get("option") == "region", "wrong initial/selector action")
        record("initial_run1_pulse0", True, [1,0])
        record("selector_once_counts", True, [2,0])
        record("pulse_once_counts", True, [4,1])
        # Reuse the reviewed uploader proof exactly. This adapter only names its
        # existing success flag and selected phase; it does not synthesize frames.
        prepared_observation = dict(observation, phases=[phases[2]], uploads={"good": observation.get("uploads", {}).get("file")})
        bundle = _journey_bundle(prepared_observation)
        prepared = _journey_context(bundle, "sales_basic.csv", "region", phases[2]["dom_after"])
        _journey_need(prepared["ok"], "; ".join(prepared["problems"]))
        record("upload_preparation", True, prepared["file_id"])
        file_id = prepared["info"]
        for values in states[2:]:
            infos = [v.get("value_full", {}).get("uploadedFileInfo") for v in values if v.get("value_field") == "file_uploader_state_value"]
            _journey_need(infos == [[file_id]], "Pulse changed/dropped the uploaded file")
        record("same_file_session", True, prepared["file_id"])
        before_view = _stage2_static_view(observation, phases[2], runs[2])
        after_view = _stage2_static_view(observation, phases[3], runs[3])
        _journey_need(before_view == after_view, "Pulse changed the table/chart data")
        record("fresh_unchanged_values", True, "fresh IPC in each run; same schema/rows/encoding")
    except (ValueError, TypeError, KeyError, IndexError, OSError, AttributeError) as exc:
        error = str(exc)
    else:
        error = "missing required proof"
    seen = {c["check"] for c in checks}
    checks.extend(_check("state", key, "strict stage2 state evidence", error, False) for key in STAGE2_REQUIRED["state"] if key not in seen)
    return _journey_finish("state", checks)


def _png_phase_record(observation, raw, index, record):
    """The same file/hash/clock proof for leaf and sequence phase records."""
    phase = raw["phases"][index]
    source = raw.get("namespace")
    start, end = phase["start"], phase["end"]
    _journey_need(type(start) is int and type(end) is int and 0 <= start < end <= len(raw["frames"]), "missing screenshot phase window")
    selected = raw["frames"][start:end]
    _journey_need(source and all(f.get("namespace") == source and f.get("request_id") and f.get("connection") is not None for f in selected), "screenshot phase source missing/mixed")
    _journey_need(len({(f["request_id"], f["connection"]) for f in selected}) == 1, "screenshot phase mixed connections")
    file = pathlib.Path(record["file"])
    root = pathlib.Path(observation["ipc_dir"]).resolve()
    path = (root / file).resolve()
    _journey_need(not file.is_absolute() and ".." not in file.parts and path.is_relative_to(root) and path.is_file(), "missing/unsafe relative PNG artifact")
    png = path.read_bytes()
    _journey_need(png.startswith(b"\x89PNG\r\n\x1a\n") and isinstance(record.get("sha256"), str)
                  and hashlib.sha256(png).hexdigest() == record["sha256"], "PNG bytes/SHA mismatch")
    finish = [f for f in selected if f.get("direction") == "server->client" and f.get("decoded", {}).get("type") == "script_finished"
              and f["decoded"]["script_finished"].get("status") == 0]
    stamp, observed_end = record.get("timestamp"), phase.get("observation_end_timestamp")
    _journey_need(finish and all(type(t) in (int, float) and math.isfinite(t) for t in (stamp, observed_end)), "missing same-clock screenshot/completion time")
    _journey_need(phase["start_timestamp"] <= phase["end_timestamp"] <= stamp <= observed_end
                  and all(f["timestamp"] <= stamp for f in finish), "PNG is outside completed phase observation window")
    _journey_need(0 <= observed_end - phase["end_timestamp"] <= STAGE2_SCREENSHOT_MAX_LAG_SECONDS, "PNG observation clock/lag is outside the capture budget")
    later = raw["phases"][index+1:]
    _journey_need(all(stamp < p["start_timestamp"] for p in later), "PNG crossed into another action phase")
    _journey_need(not any(f.get("namespace") == source and phase["end_timestamp"] < f.get("timestamp", -1) <= stamp
                          and f.get("decoded", {}).get("type") in ("rerun_script", "new_session") for f in raw["frames"][end:]), "PNG is stale after another run/action")
    return record["file"]


def screenshot_checks(*, observation=None):
    """File/hash/time proof only. Independent review still judges the picture."""
    kind = observation.get("journey") if isinstance(observation, dict) else None
    roles = STAGE2_SCREENSHOTS.get(kind)
    if roles is None:
        return [_check("screenshots", "records", "known complete screenshot contract", "missing/unknown observation", False)]
    checks = []
    records = observation.get("screenshots")
    allowed = {sid for sid, _, _ in roles}
    valid_records = (observation.get("contract") == "journey-stage2-v1" and isinstance(records, list) and records
                     and all(isinstance(r, dict) and isinstance(r.get("step_ids"), list) and r["step_ids"]
                             and set(r["step_ids"]) <= allowed and len(r["step_ids"]) == len(set(r["step_ids"])) for r in records))
    checks.append(_check("screenshots", "records", "stage2 screenshot records for the fixed steps", records, valid_records))
    for sid, tab, index in roles:
        try:
            _journey_need(valid_records, "missing or malformed screenshot records")
            raw = observation["tabs"][tab] if tab else observation
            phase = raw["phases"][index]
            source = raw.get("namespace")
            candidates = [r for r in records if sid in r["step_ids"] and r.get("phase") == phase.get("name") and r.get("namespace") == source]
            _journey_need(len(candidates) == 1, "missing/duplicate screenshot for this phase and namespace")
            actual, ok = _png_phase_record(observation, raw, index, candidates[0]), True
        except (ValueError, TypeError, KeyError, IndexError, OSError, AttributeError) as exc:
            actual, ok = str(exc), False
        checks.append(_check(sid, f"png_proof/{tab or 'main'}/{index}", "original PNG/hash/source/completed phase time", actual, ok))
    return _journey_finish("screenshots/" + kind, checks)


# J01 contract follows the measured continuous 1.66.1 channel/BOM wire oracle.
J01_CASE = "j01-sequence"
J01_CONTRACT = "journey-j01-input-v1"
J01_PHASES = (
    "initial", "upload-baseline", "group-region", "group-channel",
    "prepare-category", "upload-unicode", "upload-bom",
)
J01_INPUTS = {
    "upload-baseline": "sales_basic.csv",
    "upload-unicode": "sales_unicode.csv",
    "upload-bom": "sales_utf8_bom.csv",
}
J01_FILE_FINGERPRINTS = {
    "sales_basic.csv": (737, "9692a718edc5bec8f3fee1cfec4f454338c8f8d675cd34c17cdb5bf4403d8d00"),
    "sales_unicode.csv": (241, "376dbccff31cd90039eec950d61d6650ee920ca8cf6f1e06e2c0b425ca747b7f"),
    "sales_utf8_bom.csv": (244, "2ecb023d2ce037a3d55ac9d322b4d7a18c9df5c710bcf5929cb95b21358fe551"),
}
J01_ACTIONS = {
    "initial": {"action": "initial"},
    "upload-baseline": {"action": "upload"},
    "group-region": {"action": "select-option", "label": "Group by", "option": "region"},
    "group-channel": {"action": "select-option", "label": "Group by", "option": "channel"},
    "prepare-category": {"action": "select-option", "label": "Group by", "option": "category"},
    "upload-unicode": {"action": "upload"},
    "upload-bom": {"action": "upload"},
}
J01_PNG_ROLES = {
    "initial": (), "upload-baseline": ("J01-S1",), "group-region": ("J01-S2",),
    "group-channel": ("J01-S3",), "prepare-category": (),
    "upload-unicode": ("J01-S4",), "upload-bom": ("J01-S5",),
}
# Original application expectations: key, row count, decimal total, decimal mean.
# These are not synthetic producer observations or new protocol goldens.
J01_EXPECTED_ROWS = {
    "upload-baseline": (("Books", 3, "245.75", "81.92"), ("Games", 3, "409.48", "136.49"),
                        ("Music", 3, "139.00", "46.33"), ("Toys", 3, "104.49", "34.83")),
    "group-region": (("(missing)", 1, "88.00", "88.00"), ("East", 2, "209.49", "104.75"),
                     ("North", 3, "264.50", "88.17"), ("South", 2, "245.24", "122.62"),
                     ("UNKNOWN", 2, "40.49", "20.25"), ("West", 2, "51.00", "25.50")),
    "group-channel": (("Online", 6, "361.99", "60.33"), ("Retail", 6, "536.73", "89.46")),
    "upload-unicode": (("Bücher", 1, "120.50", "120.50"), ("Jogos", 1, "149.50", "149.50"),
                       ("游戏", 1, "199.99", "199.99")),
}
J01_EXPECTED_ROWS["prepare-category"] = J01_EXPECTED_ROWS["upload-baseline"]
J01_EXPECTED_ROWS["upload-bom"] = J01_EXPECTED_ROWS["upload-unicode"]
# BOM must have fresh upload/state/run/Arrow/chart frames. Only its logical
# result is equivalent; neither a different IPC SHA nor dataset name is required.
J01_REQUIRED = ("contract", "phase_order", "fixture_bytes", "same_source_session", "run_ledger", "typed_controls",
                "baseline_values", "region_values", "channel_values", "prepare_category", "unicode_values",
                "bom_equivalence", "replacement_http", "fresh_run_ipc", "png_coverage")
JOURNEY_REQUIRED[J01_CASE] = {(J01_CASE, key) for key in J01_REQUIRED}


def j01_checks(*, observation=None):
    """J01 uses the existing continuous-frame checker, with bounded BOM equivalence."""
    if not isinstance(observation, dict) or observation.get("journey") != J01_CASE:
        return _journey_finish(J01_CASE, [_check(J01_CASE, key, "complete strict J01 evidence", "missing/wrong J01 observation", False) for key in J01_REQUIRED])
    return sequence_checks(observation=observation)


# J03 pointer/ARIA shape and six-phase data transitions are measured on 1.66.1.
J03_CASE = "j03-sequence"
J03_CONTRACT = "journey-j03-sync-v1"
J03_PHASES = (
    "initial", "upload-baseline", "slider-100", "prepare-slider-zero",
    "group-region", "slider-200",
)
J03_INPUTS = {"upload-baseline": "sales_basic.csv"}
J03_ACTIONS = {
    "initial": {"action": "initial"},
    "upload-baseline": {"action": "upload"},
    "slider-100": {"action": "slider", "label": "Minimum amount", "value": 100},
    "prepare-slider-zero": {"action": "slider", "label": "Minimum amount", "value": 0},
    "group-region": {"action": "select-option", "label": "Group by", "option": "region"},
    "slider-200": {"action": "slider", "label": "Minimum amount", "value": 200},
}
J03_PNG_ROLES = {
    "initial": (), "upload-baseline": ("J03-S1",), "slider-100": ("J03-S2",),
    "prepare-slider-zero": (), "group-region": ("J03-S3",), "slider-200": ("J03-S4",),
}
J03_REQUIRED = ("contract", "phase_order", "fixture_bytes", "same_source_session", "run_ledger", "typed_controls",
                "pointer_100", "pointer_prepare_zero", "pointer_200", "baseline_values", "filtered_100_values",
                "restore_categories", "region_values", "empty_schema_no_chart", "png_coverage")
JOURNEY_REQUIRED[J03_CASE] = {(J03_CASE, key) for key in J03_REQUIRED}


def j03_checks(*, observation=None):
    """J03 reuses the continuous-frame layer and measured pointer/empty rules."""
    if not isinstance(observation, dict) or observation.get("journey") != J03_CASE:
        return _journey_finish(J03_CASE, [_check(J03_CASE, key, "complete strict J03 evidence", "missing/wrong J03 observation", False) for key in J03_REQUIRED])
    return sequence_checks(observation=observation)


# J02 follows the measured continuous 1.66.1 reference chain. S5 observes the
# ledger, never an additional input or run.
J02_CASE = "j02-sequence"
J02_CONTRACT = "journey-j02-filter-v1"
J02_PHASES = (
    "initial", "upload-baseline", "group-region", "exclude-unknown",
    "slider-100", "group-category",
)
J02_INPUTS = {"upload-baseline": "sales_basic.csv"}
J02_FILE_FINGERPRINTS = {"sales_basic.csv": J01_FILE_FINGERPRINTS["sales_basic.csv"]}
J02_ACTIONS = {
    "initial": {"action": "initial"},
    "upload-baseline": {"action": "upload"},
    "group-region": {"action": "select-option", "label": "Group by", "option": "region"},
    "exclude-unknown": {"action": "checkbox", "label": "Include unknown region", "value": False},
    "slider-100": {"action": "slider", "label": "Minimum amount", "value": 100},
    "group-category": {"action": "select-option", "label": "Group by", "option": "category"},
}
J02_PNG_ROLES = {
    "initial": (), "upload-baseline": (), "group-region": ("J02-S1",),
    "exclude-unknown": ("J02-S2",), "slider-100": ("J02-S3",),
    "group-category": ("J02-S4", "J02-S5"),
}
# One unchanged final PNG can attest S4's result and S5's visible counters.
# Publication must identify that byte-for-byte sharing, not claim a new capture.
J02_COLUMNS = ("group_key", "row_count", "total_amount", "avg_amount")
J02_TYPES = ("large_string", "int64", "double", "double")
J02_EXPECTED_ROWS = {
    "upload-baseline": J01_EXPECTED_ROWS["upload-baseline"],
    "group-region": J01_EXPECTED_ROWS["group-region"],
    "exclude-unknown": (("East", 2, "209.49", "104.75"), ("North", 3, "264.50", "88.17"),
                        ("South", 2, "245.24", "122.62"), ("West", 2, "51.00", "25.50")),
    "slider-100": (("East", 1, "149.50", "149.50"), ("North", 1, "120.50", "120.50"),
                   ("South", 1, "199.99", "199.99")),
    "group-category": (("Books", 1, "120.50", "120.50"), ("Games", 2, "349.49", "174.75")),
}
J02_REQUIRED = ("contract", "phase_order", "fixture_bytes", "same_source_session", "run_ledger", "typed_controls",
                "baseline_values", "region_values", "exclude_unknown_values", "threshold_values", "category_values",
                "false_oneof", "pointer_100", "fresh_run_ipc", "png_ledger_roles")
JOURNEY_REQUIRED[J02_CASE] = {(J02_CASE, key) for key in J02_REQUIRED}


def j02_checks(*, observation=None):
    """Strict same-session filtering, with explicit false and read-only S5."""
    if not isinstance(observation, dict) or observation.get("journey") != J02_CASE:
        return _journey_finish(J02_CASE, [_check(J02_CASE, key, "complete strict J02 evidence", "missing/wrong J02 observation", False) for key in J02_REQUIRED])
    return sequence_checks(observation=observation)


# J00 measured contract. Note/Apply are first-screen presence/membership
# assertions, not submit or Pulse actions (those belong to J05).
J00_CASE = "j00-sequence"
J00_CONTRACT = "journey-j00-integrated-v1"
J00_PHASES = (
    "initial", "upload-baseline", "group-region", "prepare-category",
    "slider-100", "prepare-slider-zero", "prepare-region", "exclude-unknown",
)
J00_INPUTS = {"upload-baseline": "sales_basic.csv"}
J00_FILE_FINGERPRINTS = {"sales_basic.csv": J01_FILE_FINGERPRINTS["sales_basic.csv"]}
J00_ACTIONS = {
    "initial": {"action": "initial"},
    "upload-baseline": {"action": "upload"},
    "group-region": {"action": "select-option", "label": "Group by", "option": "region"},
    "prepare-category": {"action": "select-option", "label": "Group by", "option": "category"},
    "slider-100": {"action": "slider", "label": "Minimum amount", "value": 100},
    "prepare-slider-zero": {"action": "slider", "label": "Minimum amount", "value": 0},
    "prepare-region": {"action": "select-option", "label": "Group by", "option": "region"},
    "exclude-unknown": {"action": "checkbox", "label": "Include unknown region", "value": False},
}
J00_PNG_ROLES = {
    "initial": ("J00-S1",), "upload-baseline": ("J00-S2",), "group-region": ("J00-S3",),
    "prepare-category": (), "slider-100": ("J00-S4",), "prepare-slider-zero": (), "prepare-region": (),
    "exclude-unknown": ("J00-S5", "J00-S6"),
}
# S6 is read-only ledger/counter observation sharing the final original PNG.
# Actual form IDs and Note/Apply membership must come from retained protobuf
# and the existing forms canonical helper, never a new decoder or label guess.
J00_FORM_LABELS = ("Note", "Apply note")
J00_COLUMNS = J02_COLUMNS
J00_TYPES = J02_TYPES
J00_EXPECTED_ROWS = {
    "upload-baseline": J01_EXPECTED_ROWS["upload-baseline"],
    "group-region": J01_EXPECTED_ROWS["group-region"],
    "prepare-category": J01_EXPECTED_ROWS["upload-baseline"],
    "slider-100": J02_EXPECTED_ROWS["group-category"],
    "prepare-slider-zero": J01_EXPECTED_ROWS["upload-baseline"],
    "prepare-region": J01_EXPECTED_ROWS["group-region"],
    "exclude-unknown": J02_EXPECTED_ROWS["exclude-unknown"],
}
J00_REQUIRED = ("contract", "phase_order", "fixture_bytes", "same_source_session", "run_ledger", "typed_controls",
                "baseline_values", "region_values", "category_restore_values", "threshold_values", "slider_restore_values",
                "known_region_values", "false_oneof", "pointer_100_and_zero", "fresh_run_ipc", "png_ledger_roles",
                "initial_form_binding", "untouched_note", "untriggered_apply")
JOURNEY_REQUIRED[J00_CASE] = {(J00_CASE, key) for key in J00_REQUIRED}


def j00_checks(*, observation=None):
    """Strict integrated chain; Note/Apply are observed, never operated."""
    if not isinstance(observation, dict) or observation.get("journey") != J00_CASE:
        return _journey_finish(J00_CASE, [_check(J00_CASE, key, "complete strict J00 evidence", "missing/wrong J00 observation", False) for key in J00_REQUIRED])
    return sequence_checks(observation=observation)


# J06 has independent per-tab frame cursors. Readonly views may have no frames;
# their fresh DOM reads refer to a previously verified checkpoint, not new IPC.
J06_CASE = "j06-sequence"
J06_CONTRACT = "journey-j06-isolation-v1"
J06_PHASES = ("initial", "a-upload", "a-pulse-1", "a-pulse-2", "a-pulse-3", "b-untouched",
              "b-upload-preparation", "b-group-region", "a-refresh")
J06_INPUTS = {"a-upload":"sales_basic.csv", "b-upload-preparation":"sales_basic.csv"}
J06_ACTIONS = {
    "initial":{"action":"initial", "actor":"both"},
    "a-upload":{"action":"upload", "actor":"a"},
    **{f"a-pulse-{i}":{"action":"pulse", "actor":"a", "label":"Pulse"} for i in (1,2,3)},
    "b-untouched":{"action":"observe", "actor":None},
    "b-upload-preparation":{"action":"upload", "actor":"b"},
    "b-group-region":{"action":"select-option", "actor":"b", "label":"Group by", "option":"region"},
    "a-refresh":{"action":"refresh", "actor":"a"},
}
J06_MODES = {name:dict(zip(("a","b"), modes)) for name,modes in zip(J06_PHASES, (
    ("initial","initial"), ("upload","readonly"), ("pulse","readonly"), ("pulse","readonly"),
    ("pulse","readonly"), ("readonly","readonly"), ("readonly","upload"),
    ("readonly","select"), ("refresh","readonly")), strict=True)}
J06_PNG_ROLES = {name:({"initial":("J06-S1",), "a-pulse-3":("J06-S2",),
                      "b-untouched":("J06-S3",), "b-group-region":("J06-S4",),
                      "a-refresh":("J06-S5",)}.get(name, ())) for name in J06_PHASES}
J06_REQUIRED = ("contract", "phase_order", "pre_navigation_recording", "fresh_handshakes", "distinct_sessions",
                "connection_epochs", "frame_coverage", "target_runs", "run_ledger", "typed_controls", "fixture_bytes",
                "http_ownership", "golden_table_chart_dom", "readonly_peer", "b_untouched", "a_refresh_reset",
                "b_retained", "png_coverage")
JOURNEY_REQUIRED[J06_CASE] = {(J06_CASE,key) for key in J06_REQUIRED}
J06_OBSERVATION_FIELDS = {
    "root":("journey", "contract", "url", "ipc_dir", "tabs", "phases", "screenshots"),
    "tab":("namespace", "target_id", "recorder_started_timestamp", "frames", "events", "http_timeline", "epochs"),
    "epoch":("id", "connection", "request_id", "navigation_timestamp", "navigation_event", "handshake_event", "response_event"),
    "phase":("name", "action", "action_timestamp", "observation_end_timestamp", "views"),
    "view":("mode", "epoch", "start", "end", "start_timestamp", "end_timestamp", "read_start_timestamp",
             "read_end_timestamp", "dom_before", "dom_after", "client_states", "completions", "ipc", "checkpoint"),
    "checkpoint":("epoch", "script_run_id", "finish_frame"),
    "png":("phase", "tab", "namespace", "epoch", "file", "sha256", "timestamp", "step_ids"),
    "dom":("script_runs", "pulses", "selectbox_value", "slider_value", "checkbox_checked", "uploaded_files",
           "table_present", "table_cells", "chart_present", "chart_bars", "chart_marks", "alerts", "exceptions"),
}
# events are original CDP {method, params}; epoch *_event values are indices
# into that tab's events. navigation_event is Network.requestWillBeSent for
# type=Document; handshake/response use the matching WebSocket requestId.
# navigation_timestamp is the CDP-clock command time, preceding that event.
# view.read_start_timestamp is the CDP clock immediately after dom_before;
# read_end_timestamp immediately after dom_after. action_timestamp lies
# between both tabs' reads. start/end delimit frames in that read interval.
# initial dom_before is None; all other dom_before values are actual reads.
# For empty readonly ranges: timestamps=None, states/completions=[], IPC=None
# for both table/chart. checkpoint always references the last verified run;
# initial/action/refresh checkpoints reference their just-completed target.
# Frames retain raw base64/bytes/SHA. ref_hash is resolved per frontend cache,
# with reference metadata replacing cached metadata, never another tab's cache.


def j06_checks(*, observation=None):
    """One continuous two-tab chain, including explicit readonly observations."""
    try:
        _j06_verify(observation)
    except (ValueError, TypeError, KeyError, IndexError, OSError, AttributeError) as exc:
        actual, ok = str(exc), False
    else:
        actual, ok = "strict J06 two-tab chain verified; PNG visual review remains independent", True
    return _journey_finish(J06_CASE, [_check(J06_CASE,key,"complete strict J06 evidence",actual,ok) for key in J06_REQUIRED])


def _j06_number(value):
    return type(value) in (int,float) and math.isfinite(value)


def _j06_materialize_frames(tab):
    """Official frontend cache semantics, isolated per page/connection epoch.

    The frozen frontend caches only metadata.cacheable messages, refreshes age
    on a hit, substitutes reference metadata, and ages after a non-early finish.
    Raw frames and events are never rewritten. The returned copy is for existing
    run/Arrow helpers and the producer's derived phase summaries only.
    """
    from streamlit.proto.ForwardMsg_pb2 import ForwardMsg

    wire = [e for e in tab["events"] if e.get("method") in
            ("Network.webSocketFrameSent", "Network.webSocketFrameReceived")
            and e.get("params", {}).get("response", {}).get("opcode") == 2]
    frames = tab["frames"]
    _journey_need(isinstance(frames,list) and frames and len(wire) == len(frames), "J06 raw frame/event stream is incomplete")
    result, cache, epoch, count, age, fragments = [], {}, None, 0, None, []
    stamps = []
    for frame,event in zip(frames,wire):
        params = event["params"]
        payload = base64.b64decode(params["response"]["payloadData"], validate=True)
        direction = "client->server" if event["method"].endswith("Sent") else "server->client"
        _journey_need(frame.get("namespace") == tab["namespace"] and frame.get("direction") == direction
                      and frame.get("request_id") == params.get("requestId") and frame.get("timestamp") == params.get("timestamp")
                      and _j06_number(frame.get("timestamp")) and type(frame.get("connection")) is int
                      and frame.get("base64") == params["response"]["payloadData"] and frame.get("bytes") == len(payload)
                      and frame.get("sha256") == hashlib.sha256(payload).hexdigest(), "J06 raw frame is not bound to its actual CDP event")
        stamps.append(frame["timestamp"])
        identity = (frame["connection"], frame["request_id"])
        if identity != epoch:
            _journey_need(identity not in {(f["connection"],f["request_id"]) for f in result}, "J06 returned to a superseded epoch")
            cache, epoch, count, age, fragments = {}, identity, 0, None, []
        decoded = summarise_back(payload) if direction == "client->server" else summarise_forward(payload)
        _journey_need(frame.get("decoded") == decoded, "J06 raw decoded summary differs from protobuf")
        effective = payload
        if direction == "server->client":
            msg = ForwardMsg(); msg.ParseFromString(payload)
            kind = msg.WhichOneof("type")
            if kind != "ref_hash" and msg.metadata.cacheable:
                _journey_need(bool(msg.hash), "J06 cacheable message has no hash")
                if msg.hash in cache:
                    cache[msg.hash][1] = count
                else:
                    cache[msg.hash] = [payload,count,msg.delta.fragment_id if kind == "delta" else ""]
            if kind == "ref_hash":
                _journey_need(msg.ref_hash in cache and msg.HasField("metadata"), "J06 missing/foreign/expired cache reference or metadata")
                saved = cache[msg.ref_hash]; saved[1] = count
                resolved = ForwardMsg(); resolved.ParseFromString(saved[0]); resolved.metadata.CopyFrom(msg.metadata)
                effective = resolved.SerializeToString(); msg = resolved; kind = msg.WhichOneof("type")
            if kind == "new_session":
                age = msg.new_session.config.max_cached_message_age
                fragments = list(msg.new_session.fragment_ids_this_run)
            if kind == "script_finished" and msg.script_finished != 2 and age is not None:
                count += 1
                cache = {key:value for key,value in cache.items()
                         if (fragments and (not value[2] or value[2] not in fragments)) or count-value[1] <= age}
            decoded = summarise_forward(effective)
        result.append(dict(frame,decoded=decoded))
    _journey_need(stamps == sorted(stamps), "J06 frame clock moved backwards")
    return result


def _j06_epochs(tab, url, expected_ids):
    from urllib.parse import urlsplit

    epochs, events = tab["epochs"], tab["events"]
    _journey_need(isinstance(epochs,list) and tuple(e.get("id") for e in epochs) == expected_ids
                  and _j06_number(tab["recorder_started_timestamp"]) and tab["target_id"], "J06 missing epochs/target/recorder start")
    identities, navigation_times = set(), []
    for item in epochs:
        for key in ("navigation_event","handshake_event","response_event"):
            _journey_need(type(item[key]) is int and 0 <= item[key] < len(events), "J06 missing actual navigation/handshake event index")
        nav, handshake, response = [events[item[k]] for k in ("navigation_event","handshake_event","response_event")]
        np, hp, rp = nav["params"],handshake["params"],response["params"]
        request = hp["request"]
        headers = {k.lower():v for k,v in request["headers"].items()}
        protocols = headers.get("sec-websocket-protocol", "").split(",")
        _journey_need(nav["method"] == "Network.requestWillBeSent" and np.get("type") == "Document"
                      and urlsplit(np["request"]["url"])[:3] == urlsplit(url)[:3]
                      and handshake["method"] == "Network.webSocketWillSendHandshakeRequest"
                      and response["method"] == "Network.webSocketHandshakeResponseReceived"
                      and len(protocols) == 2 and protocols[0].strip() == "streamlit" and protocols[1].strip()
                      and rp["response"]["status"] == 101
                      and {k.lower():v for k,v in rp["response"]["headers"].items()}.get("sec-websocket-protocol") == "streamlit",
                      "J06 fresh navigation/handshake is missing or not a two-entry fresh connection")
        times = (tab["recorder_started_timestamp"],item["navigation_timestamp"],np["timestamp"],hp["timestamp"],rp["timestamp"])
        _journey_need(all(_j06_number(t) for t in times) and times[0] < times[1] <= times[2] <= times[3] <= times[4]
                      and item["request_id"] == hp["requestId"] == rp["requestId"]
                      and type(item["connection"]) is int, "J06 recorder attached late or handshake clock/ownership is wrong")
        identity = (item["connection"],item["request_id"])
        _journey_need(identity not in identities and identity in {(f["connection"],f["request_id"]) for f in tab["frames"]}, "J06 missing/reused connection epoch")
        epoch_frames = [f for f in tab["frames"] if (f["connection"],f["request_id"]) == identity]
        _journey_need(all(rp["timestamp"] <= f["timestamp"] for f in epoch_frames), "J06 epoch frame precedes its HTTP101 response")
        closed = [e["params"] for e in events if e.get("method") == "Network.webSocketClosed"
                  and e.get("params",{}).get("requestId") == item["request_id"]]
        _journey_need(len(closed) <= 1 and (not closed or _j06_number(closed[0].get("timestamp"))
                      and rp["timestamp"] <= closed[0]["timestamp"]
                      and all(f["timestamp"] <= closed[0]["timestamp"] for f in epoch_frames)), "J06 epoch frame is outside its actual socket lifetime")
        identities.add(identity); navigation_times.append(item["navigation_timestamp"])
    _journey_need(navigation_times == sorted(set(navigation_times))
                  and identities == {(f["connection"],f["request_id"]) for f in tab["frames"]}
                  and len({e["request_id"] for e in epochs}) == len(epochs)
                  and [e["connection"] for e in epochs] == list(range(len(epochs))), "J06 undeclared/reused navigation/connection")
    document_indices = {i for i,e in enumerate(events) if e.get("method") == "Network.requestWillBeSent" and e.get("params",{}).get("type") == "Document"}
    handshake_indices = {i for i,e in enumerate(events) if e.get("method") == "Network.webSocketWillSendHandshakeRequest"}
    _journey_need(document_indices == {e["navigation_event"] for e in epochs}
                  and handshake_indices == {e["handshake_event"] for e in epochs}, "J06 hidden navigation/handshake")
    return {e["id"]:e for e in epochs}


def _j06_dom(dom):
    _journey_need(isinstance(dom,dict) and set(J06_OBSERVATION_FIELDS["dom"]) <= dom.keys(), "J06 missing actual DOM fields (including uploaded_files)")
    _journey_need(isinstance(dom["uploaded_files"],list) and dom["exceptions"] == [], "J06 missing uploader DOM or visible exception")
    return {key:dom[key] for key in J06_OBSERVATION_FIELDS["dom"]}


def _j06_empty(run, dom):
    _stage2_specific_counters(run["deltas"],dom,1)
    _stage2_specific_alerts(run["deltas"],dom,[("INFO","Upload a CSV to see the aggregated result.")])
    _journey_need(dom["uploaded_files"] == [] and dom["table_present"] is False and dom["table_cells"] == []
                  and dom["chart_present"] is False and dom["chart_bars"] == 0 and not dom["chart_marks"]
                  and dom["selectbox_value"] == "category" and _same_cell_value(0,dom["slider_value"])
                  and dom["checkbox_checked"] is True
                  and not any(d.get("element") in ("dataframe","vega_lite_chart","table") for d in run["deltas"]), "J06 fresh page has retained data/controls")
    for kind,label,want in (("file_uploader","Upload sales CSV",None), ("selectbox","Group by",0),
                             ("slider","Minimum amount",[0.]), ("checkbox","Include unknown region",True)):
        elements = [d for d in run["deltas"] if d.get("element") == kind and d.get("label") == label]
        _journey_need(len(elements) == 1 and elements[0].get("id"), "J06 missing fresh source control")
        if want is not None:
            value = elements[0].get("widget",{}).get("default")
            _journey_need(value is True if kind == "checkbox" else type(value) is int and value == 0 if kind == "selectbox" else value == want,
                          "J06 fresh wire control defaults are wrong")


def _j06_active(observation, tab, phase, view, previous):
    mode, dom = view["mode"], view["dom_after"]
    local = dict(view,name=phase["name"],action=phase["action"])
    adapted = dict(observation,namespace=tab["namespace"],frames=tab["frames"],http_timeline=tab["http_timeline"],
                   phases=[local],uploads={"good":True})
    run = _stage2_phase_run(adapted,local)
    marker = next(i for i in range(view["start"],view["end"]) if tab["frames"][i]["decoded"].get("type") == "new_session")
    for index in range(view["start"],view["end"]):
        if marker < index < run["finish_index"] or index in (run["state_index"],marker,run["finish_index"]):
            continue
        decoded = tab["frames"][index]["decoded"]
        kind = decoded.get("type")
        quiet = kind in ("app_heartbeat","heartbeat_ack") or kind == "session_status_changed" and not decoded["session_status_changed"].get("script_is_running")
        upload_exchange = mode == "upload" and index < run["state_index"] and kind in ("file_urls_request","file_urls_response")
        _journey_need(quiet or upload_exchange, "J06 business output lies outside its target run")
    states = tab["frames"][run["state_index"]]["decoded"]["rerun_script"].get("widget_states")
    if mode in ("initial","refresh"):
        _journey_need(states == [] and view["ipc"] == {"table":None,"chart":None}, "J06 fresh page sent retained widget state/IPC")
        _j06_empty(run,dom)
        context = {"info":None,"group":"category","runs":1,"pulses":0,"session":run["session"]}
    else:
        _journey_need(previous is not None and run["session"] == previous["session"], "J06 ordinary action switched session")
        _journey_need(len({s.get("id") for s in states}) == len(states), "J06 duplicate typed widget ID")
        group = "region" if mode == "select" else "category"
        triggers = [s for s in states if s.get("value_field") == "trigger_value" and s.get("value") is True]
        filtered = [s for s in states if s not in triggers]
        _stage2_typed_controls(run["deltas"],filtered,dom,group=group)
        pulses = previous["pulses"] + (mode == "pulse")
        if mode == "pulse":
            buttons = [d for d in run["deltas"] if d.get("element") == "button" and d.get("label") == "Pulse"]
            _journey_need(len(buttons) == 1 and len(triggers) == 1 and triggers[0].get("id") == buttons[0].get("id"), "J06 missing/duplicate/wrong Pulse trigger")
        else:
            _journey_need(not triggers, "J06 unexpected button trigger")
        for label,key,want in (("Script runs","script_runs",previous["runs"]+1), ("Pulses","pulses",pulses)):
            values = [int(m[1]) for d in run["deltas"] if d.get("element") in ("text","markdown")
                      and isinstance(d.get("body"),str) and (m := re.fullmatch(re.escape(label)+r":\s*(\d+)",d["body"].strip()))]
            _journey_need(_stage2_counter(dom,key) == want and values == [want], "J06 wire/DOM counter missing, duplicated or wrong: " + label)
        _stage2_specific_alerts(run["deltas"],dom,[])
        _journey_need(dom["uploaded_files"] == ["sales_basic.csv"], "J06 uploader DOM does not contain its file")
        if mode == "upload":
            _stage2_specific_input(local,"sales_basic.csv")
            bundle = _journey_bundle(adapted)
            proof = _journey_context(bundle,"sales_basic.csv","category",dom)
            _journey_need(proof["ok"], "J06 upload ownership: " + str(proof["problems"]))
            info = proof["info"]
        else:
            uploaders = [d for d in run["deltas"] if d.get("element") == "file_uploader" and d.get("label") == "Upload sales CSV"]
            _journey_need(len(uploaders) == 1, "J06 missing uploader source")
            values = [s for s in states if s.get("id") == uploaders[0].get("id")]
            _journey_need(len(values) == 1 and values[0].get("value_field") == "file_uploader_state_value"
                          and values[0].get("value_full",{}).get("uploadedFileInfo") == [previous["info"]], "J06 ordinary action changed/lost file ownership")
            info = previous["info"]
        expected = [{"group_key":k,"row_count":n,"total_amount":float(t),"avg_amount":float(a)}
                    for k,n,t,a in J01_EXPECTED_ROWS["group-region" if group == "region" else "upload-baseline"]]
        _stage2_static_view(adapted,local,run,expected_rows=expected)
        context = {"info":info,"group":group,"runs":previous["runs"]+1,"pulses":pulses,"session":run["session"]}
    context.update(checkpoint={"epoch":view["epoch"],"script_run_id":run["run"],"finish_frame":run["finish_index"]},
                   signature=_j06_dom(dom))
    return context


def _j06_verify(observation):
    _journey_need(isinstance(observation,dict) and observation.get("journey") == J06_CASE
                  and observation.get("contract") == J06_CONTRACT, "J06 missing/wrong contract")
    phases, tabs = observation["phases"],observation["tabs"]
    _journey_need(isinstance(phases,list) and tuple(p.get("name") for p in phases) == J06_PHASES
                  and set(tabs) == {"a","b"}, "J06 missing/reordered phases or tab")
    _journey_need(tabs["a"]["namespace"] != tabs["b"]["namespace"] and tabs["a"]["target_id"] != tabs["b"]["target_id"], "J06 tabs share namespace/target")
    materialized, epochs, previous, covered, runs, sessions = {}, {}, {}, {}, set(), {}
    for key in ("a","b"):
        materialized[key] = dict(tabs[key],frames=_j06_materialize_frames(tabs[key]))
        epochs[key] = _j06_epochs(materialized[key],observation["url"],("a0","a1") if key == "a" else ("b0",))
        covered[key] = set()
    last_end = None
    for index,phase in enumerate(phases):
        name, action = phase["name"], phase["action"]
        _journey_need(all(action.get(k) == v for k,v in J06_ACTIONS[name].items()) and action.get("ok") is True
                      and not action.get("failed") and set(phase["views"]) == {"a","b"}, "J06 wrong/failed actual action or missing peer view")
        at, end = phase["action_timestamp"],phase["observation_end_timestamp"]
        _journey_need(_j06_number(at) and _j06_number(end) and at < end and (last_end is None or last_end < at), "J06 phase clock/order is invalid")
        for key in ("a","b"):
            tab, view = materialized[key],phase["views"][key]
            frames = tab["frames"]
            mode = J06_MODES[name][key]
            epoch_id = "a1" if key == "a" and name == "a-refresh" else key+"0"
            epoch = epochs[key][epoch_id]
            start, stop, before, after = view["start"],view["end"],view["read_start_timestamp"],view["read_end_timestamp"]
            _journey_need(view["mode"] == mode and view["epoch"] == epoch_id and type(start) is int and type(stop) is int
                          and 0 <= start <= stop <= len(frames) and all(_j06_number(t) for t in (before,after))
                          and (last_end is None or last_end < before) and before <= at < after <= end,
                          "J06 view mode/epoch or fresh DOM read clock is missing/wrong")
            expected_indices = [i for i,f in enumerate(frames) if before < f["timestamp"] <= after]
            _journey_need(expected_indices == list(range(start,stop))
                          and start == sum(f["timestamp"] <= before for f in frames)
                          and stop == sum(f["timestamp"] <= after for f in frames), "J06 readonly/action frame cursor differs from actual read interval")
            _journey_need(not covered[key].intersection(expected_indices), "J06 overlapping frame windows")
            covered[key].update(expected_indices)
            selected = frames[start:stop]
            _journey_need(all((f["connection"],f["request_id"]) == (epoch["connection"],epoch["request_id"]) for f in selected), "J06 crossed connection epoch")
            _journey_need(view["start_timestamp"] == (selected[0]["timestamp"] if selected else None)
                          and view["end_timestamp"] == (selected[-1]["timestamp"] if selected else None), "J06 view frame timestamps mismatch")
            signature = _j06_dom(view["dom_after"])
            if index:
                _journey_need(_j06_dom(view["dom_before"]) == previous[key]["signature"], "J06 prior DOM changed without its recorded action")
            else:
                _journey_need(view["dom_before"] is None, "J06 initial DOM is not a fresh navigation")
            if mode == "readonly":
                _journey_need(signature == previous[key]["signature"] and view["client_states"] == [] and view["completions"] == []
                              and view["ipc"] == {"table":None,"chart":None}, "J06 readonly peer changed or invented a new run/IPC")
                _journey_need(all(f["decoded"].get("type") in ("app_heartbeat","heartbeat_ack","session_status_changed")
                                  and not f["decoded"].get("session_status_changed",{}).get("script_is_running") for f in selected), "J06 hidden business run/result in readonly peer")
            else:
                context = _j06_active(observation,tab,phase,view,previous.get(key))
                marker = context["checkpoint"]["script_run_id"]
                _journey_need(marker not in runs, "J06 reused target run ID")
                runs.add(marker)
                if mode in ("initial","refresh"):
                    _journey_need(context["session"] not in sessions.values()
                                  and before <= epoch["navigation_timestamp"] <= after, "J06 refresh/initial session was reused or navigation is outside action")
                    sessions[epoch_id] = context["session"]
                previous[key] = context
                expected_states = [{k:s.get(k) for k in ("id","value_field","value")}
                                   for f in selected if f["decoded"].get("type") == "rerun_script"
                                   for s in f["decoded"]["rerun_script"]["widget_states"]]
                completions = [{"frame":i,"connection":f["connection"],"request_id":f["request_id"],
                                "status":f["decoded"]["script_finished"].get("status"),"status_name":f["decoded"]["script_finished"].get("status_name")}
                               for i,f in enumerate(selected) if f["decoded"].get("type") == "script_finished"]
                _journey_need(view["client_states"] == expected_states and view["completions"] == completions,
                              "J06 derived state/completion summary differs from effective wire")
            _journey_need(view["checkpoint"] == previous[key]["checkpoint"], "J06 checkpoint is not its last verified successful target")
            mutations = [h for h in tab["http_timeline"] if h.get("method") in ("PUT","DELETE")
                         and before < h.get("timestamp",-1) <= after]
            _journey_need(not mutations if mode != "upload" else len(mutations) == 1 and mutations[0].get("method") == "PUT"
                          and mutations[0].get("status") == 204, "J06 unexpected/missing HTTP mutation in active/readonly view")
        last_end = end
    for key,tab in materialized.items():
        _journey_need(all(i in covered[key] or f["decoded"].get("type") in ("app_heartbeat","heartbeat_ack","session_status_changed")
                          and not f["decoded"].get("session_status_changed",{}).get("script_is_running")
                          for i,f in enumerate(tab["frames"])), "J06 hidden business frames outside phase/read cursors")
        _j06_http_events(tab)
    _j06_pngs(observation)


def _j06_http_events(tab):
    """HTTP ownership checks use the timeline, whose mutations must match CDP."""
    mutations = [h for h in tab["http_timeline"] if h.get("method") in ("PUT","DELETE")]
    events = tab["events"]
    sent = [e["params"] for e in events if e.get("method") == "Network.requestWillBeSent"
            and e.get("params",{}).get("request",{}).get("method") in ("PUT","DELETE")]
    _journey_need(len(mutations) == len(sent) == 1, "J06 missing/extra HTTP upload event")
    for request in mutations:
        matched = [p for p in sent if p.get("requestId") == request.get("request_id")]
        replies = [e["params"] for e in events if e.get("method") == "Network.responseReceived"
                   and e.get("params",{}).get("requestId") == request.get("request_id")]
        _journey_need(len(matched) == len(replies) == 1 and matched[0]["request"]["method"] == request["method"]
                      and matched[0]["request"]["url"] == request["url"] and matched[0]["timestamp"] == request["timestamp"]
                      and replies[0]["response"]["status"] == request["status"] and replies[0]["timestamp"] == request["response_timestamp"],
                      "J06 HTTP timeline differs from actual CDP request/response")


def _j06_pngs(observation):
    records, phases = observation["screenshots"],observation["phases"]
    _journey_need(isinstance(records,list) and len(records) == 18, "J06 requires 18 actual phase/tab PNGs")
    paths = set()
    for phase in phases:
        for key in ("a","b"):
            view, tab = phase["views"][key],observation["tabs"][key]
            matches = [r for r in records if r.get("phase") == phase["name"] and r.get("tab") == key]
            _journey_need(len(matches) == 1, "J06 missing/duplicate phase/tab PNG")
            record = matches[0]
            _journey_need(record["namespace"] == tab["namespace"] and record["epoch"] == view["epoch"]
                          and record["step_ids"] == list(J06_PNG_ROLES[phase["name"]]), "J06 PNG source/epoch/business role differs")
            if not record["step_ids"]:
                _journey_need(record.get("role") in ("preparation","intermediate"), "J06 intermediate PNG not identified")
            file, root = pathlib.Path(record["file"]),pathlib.Path(observation["ipc_dir"]).resolve()
            path = (root/file).resolve()
            _journey_need(not file.is_absolute() and ".." not in file.parts and path.is_relative_to(root)
                          and path.is_file() and path not in paths, "J06 missing/unsafe/reused PNG")
            data = path.read_bytes(); stamp = record["timestamp"]
            _journey_need(data.startswith(b"\x89PNG\r\n\x1a\n") and hashlib.sha256(data).hexdigest() == record["sha256"]
                          and _j06_number(stamp) and view["read_end_timestamp"] <= stamp <= phase["observation_end_timestamp"]
                          and 0 <= stamp-view["read_end_timestamp"] <= STAGE2_SCREENSHOT_MAX_LAG_SECONDS, "J06 PNG SHA/clock mismatch")
            paths.add(path)


J09_CASE = "j09-sequence"
J09_CONTRACT = "journey-j09-reconnect-v1"
J09_AUTO_OBSERVE_SECONDS = 5
J09_PREFIX = ("initial", "upload-baseline", "pulse-1", "pulse-2", "reconnect-observe")
J09_PHASES = {"natural":J09_PREFIX+("refresh",),
              "ui-probe":J09_PREFIX+("probe-region","probe-category","refresh")}
J09_INPUTS = {"upload-baseline":"sales_basic.csv"}
J09_ACTIONS = {
    "initial":{"action":"initial"}, "upload-baseline":{"action":"upload"},
    "pulse-1":{"action":"pulse","label":"Pulse"}, "pulse-2":{"action":"pulse","label":"Pulse"},
    "reconnect-observe":{"action":"close-websocket"},
    "probe-region":{"action":"select-option","label":"Group by","option":"region"},
    "probe-category":{"action":"select-option","label":"Group by","option":"category"},
    "refresh":{"action":"refresh"},
}
J09_PNG_ROLES = {name:({"initial":("J09-S1",),"reconnect-observe":("J09-S2",),
                       "probe-category":("J09-S2",),"refresh":("J09-S3",)}.get(name,()))
                 for name in J09_PHASES["ui-probe"]}
J09_REQUIRED = ("contract", "phase_plan", "pre_navigation_recording", "fresh_handshakes", "actual_close",
                "reconnect_three_entries", "document_epochs", "raw_frame_binding", "document_cache", "auto_observation",
                "branch_matches_wire", "target_run_boundaries", "typed_controls", "fixture_http_ownership", "no_new_upload",
                "same_session_recovered", "run_pulse_ledger", "golden_table_chart_dom", "refresh_reset", "png_coverage")
J09_OBSERVATION_FIELDS = {
    "root":("journey","contract","plan","url","ipc_dir","page","phases","screenshots"),
    "page":J06_OBSERVATION_FIELDS["tab"],
    "epoch":("id","connection","request_id","document_event","navigation_timestamp","navigation_event","handshake_event","response_event"),
    "phase":("name","action","epoch","action_timestamp","observation_end_timestamp","start","end","start_timestamp","end_timestamp",
             "read_start_timestamp","read_end_timestamp","dom_before","dom_after","client_states","completions","ipc","checkpoint"),
    "close":("request_id","command_timestamp","completed_timestamp","evaluation_result","closed_event"),
    "auto_observation":("start_timestamp","end_timestamp"),
    "checkpoint":J06_OBSERVATION_FIELDS["checkpoint"],
    "dom":J06_OBSERVATION_FIELDS["dom"],
    "png":("phase","namespace","epoch","file","sha256","timestamp","step_ids"),
}
JOURNEY_REQUIRED[J09_CASE] = {(J09_CASE,key) for key in J09_REQUIRED}
# Single page, complete raw frames/events, same field meanings as J06. Epochs
# are e0/d0, e1/d0, e2/d1. document_event references a real Document request;
# e1 has navigation_event/navigation_timestamp=None, sharing e0.document_event.
# reconnect-observe additionally carries close and auto_observation dictionaries.
# Its epoch is e1 but its cursor may include e0's closing frames. The 5s window
# starts at e1's actual HTTP101. No-run observation has no new checkpoint/IPC;
# ui-probe proves s0 recovery in its first new run, not in the bare handshake.
# Other phases are single epoch. PNG records cover every actual phase, 6/8;
# empty step_ids require role=preparation. S4 is explicitly outside this bounded
# contract and remains optional/slow/unmeasured in the original manifest.


def j09_checks(*, observation=None):
    """Bounded CSV reconnect/refresh proof; optional slow S4 is not asserted."""
    try:
        _j09_verify(observation)
    except (ValueError,TypeError,KeyError,IndexError,OSError,AttributeError) as exc:
        actual,ok = str(exc),False
    else:
        actual,ok = "J09 bounded evidence verified; S4 unmeasured and PNG visual review independent",True
    return _journey_finish(J09_CASE, [_check(J09_CASE,key,"complete strict J09 evidence",actual,ok) for key in J09_REQUIRED])


def _j09_verify(observation):
    _journey_need(isinstance(observation,dict) and observation.get("journey") == J09_CASE
                  and observation.get("contract") == J09_CONTRACT and observation.get("plan") in J09_PHASES, "J09 missing/wrong contract or closed plan")
    phases,page = observation["phases"],observation["page"]
    _journey_need(isinstance(phases,list) and tuple(p.get("name") for p in phases) == J09_PHASES[observation["plan"]], "J09 incomplete/reordered plan")
    epochs = _j09_epochs(page,observation["url"])
    page = dict(page,frames=_j09_materialize_frames(page));frames = page["frames"]
    covered,targets,previous,last_end = set(),set(),None,None
    for phase in phases:
        name,action = phase["name"],phase["action"]
        _journey_need(all(action.get(k) == v for k,v in J09_ACTIONS[name].items()) and action.get("ok") is True
                      and not action.get("failed"), "J09 failed/unobserved/wrong action")
        at,end,before,after = [phase[k] for k in ("action_timestamp","observation_end_timestamp","read_start_timestamp","read_end_timestamp")]
        start,stop = phase["start"],phase["end"]
        _journey_need(all(_j06_number(t) for t in (at,end,before,after)) and before <= at < after <= end
                      and (last_end is None or last_end < before) and type(start) is int and type(stop) is int
                      and start == sum(f["timestamp"] <= before for f in frames) and stop == sum(f["timestamp"] <= after for f in frames), "J09 stale read clock/frame cursor")
        selected = frames[start:stop]
        _journey_need(0 <= start <= stop <= len(frames) and phase["start_timestamp"] == (selected[0]["timestamp"] if selected else None)
                      and phase["end_timestamp"] == (selected[-1]["timestamp"] if selected else None)
                      and not covered.intersection(range(start,stop)), "J09 invalid/overlapping frame window")
        covered.update(range(start,stop));_j06_dom(phase["dom_after"])
        if previous is None:_journey_need(phase["dom_before"] is None, "J09 initial state was not fresh")
        else:_journey_need(_j06_dom(phase["dom_before"]) == previous["signature"], "J09 state changed outside recorded actions")
        expected_epoch = "e2" if name == "refresh" else "e1" if name.startswith("probe-") or name == "reconnect-observe" else "e0"
        _journey_need(phase["epoch"] == expected_epoch, "J09 wrong phase connection epoch")
        allowed = {epochs[expected_epoch]["request_id"]}
        if name == "reconnect-observe":allowed.add(epochs["e0"]["request_id"])
        _journey_need(all(f["request_id"] in allowed for f in selected), "J09 phase crossed an unrelated connection")
        previous_checkpoint = previous["checkpoint"] if previous else None
        if name == "reconnect-observe":
            _journey_need(previous["pulses"] == 2, "J09 pre-close Pulse count is not two")
            previous = _j09_reconnect(observation,page,phase,previous,epochs)
        elif name.startswith("probe-"):
            previous = _j09_result_run(observation,page,phase,previous)
        else:
            modes = {"initial":"initial","upload-baseline":"upload","pulse-1":"pulse","pulse-2":"pulse","refresh":"refresh"}
            view = dict(phase,mode=modes[name]);context = _j06_active(observation,page,phase,view,previous)
            if name in ("initial","refresh"):
                _journey_need(before <= epochs[expected_epoch]["navigation_timestamp"] <= after, "J09 navigation is outside its explicit action")
            if name == "refresh":
                _journey_need(context["session"] != previous["session"], "J09 F5 reused s0")
            previous = context
        checkpoint = previous["checkpoint"]
        _journey_need(phase["checkpoint"] == checkpoint, "J09 checkpoint is not an actually verified result")
        if checkpoint != previous_checkpoint:
            _journey_need(checkpoint["script_run_id"] not in targets, "J09 target run reused")
            targets.add(checkpoint["script_run_id"])
        _journey_need(phase["client_states"] == [{k:s.get(k) for k in ("id","value_field","value")}
                      for f in selected if f["decoded"].get("type") == "rerun_script" for s in f["decoded"]["rerun_script"]["widget_states"]]
                      and phase["completions"] == [{"frame":i,"connection":f["connection"],"request_id":f["request_id"],
                          "status":f["decoded"]["script_finished"].get("status"),"status_name":f["decoded"]["script_finished"].get("status_name")}
                          for i,f in enumerate(selected) if f["decoded"].get("type") == "script_finished"], "J09 summaries differ from effective wire")
        last_end = end
    _journey_need(all(i in covered or _j09_quiet(f["decoded"]) for i,f in enumerate(frames)), "J09 hidden run/output between phases or DOM/PNG")
    _j06_http_events(page) # Exactly one actual PUT in the entire flow, no DELETE.
    _j09_pngs(observation)


def _j09_materialize_frames(page):
    """Decode original protobuf; reconnect preserves d0 cache, F5 starts d1.

    This is J09-local because J06's reviewed cache has only fresh page epochs.
    Cache payload substitution/metadata/age follows the frozen frontend, while
    raw frames and events remain immutable and separately available for audit.
    """
    from streamlit.proto.ForwardMsg_pb2 import ForwardMsg

    events = [e for e in page["events"] if e.get("method") in ("Network.webSocketFrameSent","Network.webSocketFrameReceived")
              and e.get("params",{}).get("response",{}).get("opcode") == 2]
    _journey_need(len(events) == len(page["frames"]) and events, "J09 missing raw frame/events")
    documents = {(e["connection"],e["request_id"]):e["document_event"] for e in page["epochs"]}
    result,cache,document,count,age,fragments = [],{},None,0,None,[]
    for frame,event in zip(page["frames"],events):
        params = event["params"];encoded = params["response"]["payloadData"]
        data = base64.b64decode(encoded,validate=True)
        direction = "client->server" if event["method"].endswith("Sent") else "server->client"
        _journey_need(frame.get("namespace") == page["namespace"] and frame.get("direction") == direction
                      and frame.get("request_id") == params.get("requestId") and frame.get("timestamp") == params.get("timestamp")
                      and _j06_number(frame.get("timestamp")) and type(frame.get("connection")) is int
                      and frame.get("base64") == encoded and frame.get("bytes") == len(data)
                      and frame.get("sha256") == hashlib.sha256(data).hexdigest(), "J09 raw frame/CDP binding differs")
        doc = documents[(frame["connection"],frame["request_id"])]
        if doc != document:
            _journey_need(doc not in {documents[(f["connection"],f["request_id"])] for f in result}, "J09 returned to an obsolete document")
            cache,document,count,age,fragments = {},doc,0,None,[]
        decoded = summarise_back(data) if direction == "client->server" else summarise_forward(data)
        _journey_need(decoded == frame.get("decoded"), "J09 claimed decoded summary differs from raw")
        if direction == "server->client":
            message = ForwardMsg();message.ParseFromString(data)
            kind = message.WhichOneof("type")
            if kind != "ref_hash" and message.metadata.cacheable:
                _journey_need(bool(message.hash), "J09 cacheable message without hash")
                if message.hash in cache:cache[message.hash][1] = count
                else:cache[message.hash] = [data,count,message.delta.fragment_id if kind == "delta" else ""]
            if kind == "ref_hash":
                _journey_need(message.ref_hash in cache and message.HasField("metadata"), "J09 missing/expired/foreign-document cache reference")
                saved = cache[message.ref_hash];saved[1] = count
                resolved = ForwardMsg();resolved.ParseFromString(saved[0]);resolved.metadata.CopyFrom(message.metadata)
                message = resolved;kind = message.WhichOneof("type")
            if kind == "new_session":
                age = message.new_session.config.max_cached_message_age;fragments = list(message.new_session.fragment_ids_this_run)
            if kind == "script_finished" and message.script_finished != 2 and age is not None:
                count += 1
                cache = {k:v for k,v in cache.items() if fragments and (not v[2] or v[2] not in fragments) or count-v[1] <= age}
            decoded = summarise_forward(message.SerializeToString())
        result.append(dict(frame,decoded=decoded))
    _journey_need([f["timestamp"] for f in result] == sorted(f["timestamp"] for f in result), "J09 nonmonotonic frame clock")
    return result


def _j09_epochs(page,url):
    from urllib.parse import urlsplit

    epochs,events = page["epochs"],page["events"]
    _journey_need(page["namespace"] and page["target_id"] and _j06_number(page["recorder_started_timestamp"])
                  and [e.get("id") for e in epochs] == ["e0","e1","e2"], "J09 missing page/three epochs")
    _journey_need(epochs[0]["document_event"] == epochs[1]["document_event"] != epochs[2]["document_event"], "J09 reconnect changed document or F5 reused it")
    identities = set()
    for index,epoch in enumerate(epochs):
        _journey_need(epoch["connection"] == index and epoch["request_id"] not in {e["request_id"] for e in epochs[:index]}, "J09 reused epoch connection/requestId")
        for field in ("document_event","handshake_event","response_event"):
            _journey_need(type(epoch[field]) is int and 0 <= epoch[field] < len(events), "J09 missing actual epoch event index")
        doc,hs,response = [events[epoch[k]] for k in ("document_event","handshake_event","response_event")]
        dp,hp,rp = doc["params"],hs["params"],response["params"]
        headers = {k.lower():v for k,v in hp["request"]["headers"].items()}
        protocols = [v.strip() for v in headers.get("sec-websocket-protocol","").split(",")]
        _journey_need(doc["method"] == "Network.requestWillBeSent" and dp.get("type") == "Document"
                      and urlsplit(dp["request"]["url"])[:3] == urlsplit(url)[:3]
                      and hs["method"] == "Network.webSocketWillSendHandshakeRequest"
                      and response["method"] == "Network.webSocketHandshakeResponseReceived"
                      and hp["requestId"] == rp["requestId"] == epoch["request_id"]
                      and rp["response"]["status"] == 101
                      and {k.lower():v for k,v in rp["response"]["headers"].items()}.get("sec-websocket-protocol") == "streamlit"
                      and len(protocols) == (3 if index == 1 else 2) and protocols[0] == "streamlit" and all(protocols), "J09 actual handshake/document/protocol count differs")
        times = (page["recorder_started_timestamp"],dp["timestamp"],hp["timestamp"],rp["timestamp"])
        _journey_need(all(_j06_number(t) for t in times) and times[0] < times[1] <= times[2] <= times[3], "J09 epoch clock/late recorder")
        if index == 1:
            _journey_need(epoch["navigation_event"] is None and epoch["navigation_timestamp"] is None, "J09 reconnect is an undeclared reload")
        else:
            _journey_need(epoch["navigation_event"] == epoch["document_event"] and _j06_number(epoch["navigation_timestamp"])
                          and times[0] < epoch["navigation_timestamp"] <= times[1], "J09 missing navigation command boundary")
        identity = (epoch["connection"],epoch["request_id"]);identities.add(identity)
        frames = [f for f in page["frames"] if (f["connection"],f["request_id"]) == identity]
        _journey_need(frames and all(rp["timestamp"] <= f["timestamp"] for f in frames), "J09 WS frame precedes HTTP101")
        closed = [e["params"] for e in events if e.get("method") == "Network.webSocketClosed" and e.get("params",{}).get("requestId") == epoch["request_id"]]
        _journey_need(len(closed) <= 1 and (not closed or _j06_number(closed[0].get("timestamp")) and all(f["timestamp"] <= closed[0]["timestamp"] for f in frames)), "J09 frame beyond actual closed socket")
    _journey_need(identities == {(f["connection"],f["request_id"]) for f in page["frames"]}
                  and {i for i,e in enumerate(events) if e.get("method") == "Network.webSocketWillSendHandshakeRequest"} == {e["handshake_event"] for e in epochs}
                  and {i for i,e in enumerate(events) if e.get("method") == "Network.requestWillBeSent" and e.get("params",{}).get("type") == "Document"} == {epochs[0]["document_event"],epochs[2]["document_event"]}, "J09 hidden connection/navigation")
    return {e["id"]:e for e in epochs}


def _j09_quiet(decoded):
    return decoded.get("type") in ("app_heartbeat","heartbeat_ack") or decoded.get("type") == "session_status_changed" and not decoded["session_status_changed"].get("script_is_running")


def _j09_result_run(observation,page,phase,previous,*,natural=False):
    """New-connection result proves recovery; no run is invented at HTTP101."""
    frames = page["frames"];indices = range(phase["start"],phase["end"])
    markers = [i for i in indices if frames[i]["decoded"].get("type") == "new_session"]
    finishes = [i for i in indices if frames[i]["decoded"].get("type") == "script_finished"]
    clients = [i for i in indices if frames[i]["decoded"].get("type") == "rerun_script"]
    _journey_need(len(markers) == len(finishes) == 1 and markers[0] < finishes[0]
                  and (len(clients) <= 1 if natural else len(clients) == 1)
                  and (not clients or clients[0] < markers[0]), "J09 incomplete/extra natural or probe run")
    marker,finish = markers[0],finishes[0]
    epoch = page["epochs"][1]
    selected = [frames[i] for i in range(marker,finish+1)]
    _journey_need(all((f["connection"],f["request_id"]) == (epoch["connection"],epoch["request_id"]) for f in selected)
                  and frames[finish]["decoded"]["script_finished"].get("status") == 0
                  and isinstance(frames[marker]["decoded"]["new_session"].get("script_run_id"),str)
                  and frames[marker]["decoded"]["new_session"]["script_run_id"]
                  and frames[marker]["decoded"]["new_session"].get("session_id") == previous["session"], "J09 result is not successful recovery of s0 on e1")
    for i in indices:
        if marker <= i <= finish or i in clients:continue
        _journey_need(_j09_quiet(frames[i]["decoded"]), "J09 output lies outside the target recovery/probe run")
    deltas = [f["decoded"]["delta"] for f in selected if f["decoded"].get("type") == "delta"]
    group = "region" if phase["name"] == "probe-region" else "category"
    dom = phase["dom_after"]
    _journey_need(dom["uploaded_files"] == ["sales_basic.csv"] and dom["selectbox_value"] == group
                  and _same_cell_value(0,dom["slider_value"]) and dom["checkbox_checked"] is True, "J09 recovery/probe controls or file changed")
    if clients:
        frame = frames[clients[0]]
        _journey_need((frame["connection"],frame["request_id"]) == (epoch["connection"],epoch["request_id"]), "J09 old connection supplied recovery state")
        states = frame["decoded"]["rerun_script"]["widget_states"]
        _journey_need(len({s.get("id") for s in states}) == len(states), "J09 duplicate typed widget")
        _stage2_typed_controls(deltas,states,dom,group=group)
        uploaders = [d for d in deltas if d.get("element") == "file_uploader" and d.get("label") == "Upload sales CSV"]
        _journey_need(len(uploaders) == 1, "J09 missing uploader source")
        values = [s for s in states if s.get("id") == uploaders[0].get("id")]
        _journey_need(len(values) == 1 and values[0].get("value_field") == "file_uploader_state_value"
                      and values[0].get("value_full",{}).get("uploadedFileInfo") == [previous["info"]], "J09 recovery changed/lost retained file ID")
    count = previous["runs"]+1
    for label,key,want in (("Script runs","script_runs",count),("Pulses","pulses",2)):
        values = [int(m[1]) for d in deltas if d.get("element") in ("text","markdown") and isinstance(d.get("body"),str)
                  and (m := re.fullmatch(re.escape(label)+r":\s*(\d+)",d["body"].strip()))]
        _journey_need(values == [want] and _stage2_counter(dom,key) == want, "J09 recovery counter/extra Pulse mismatch")
    expected = [{"group_key":k,"row_count":n,"total_amount":float(t),"avg_amount":float(a)}
                for k,n,t,a in J01_EXPECTED_ROWS["group-region" if group == "region" else "upload-baseline"]]
    _stage2_static_view(observation,phase,{"deltas":deltas},expected_rows=expected)
    _stage2_specific_alerts(deltas,dom,[])
    return dict(previous,group=group,runs=count,signature=_j06_dom(dom),
                checkpoint={"epoch":"e1","script_run_id":frames[marker]["decoded"]["new_session"]["script_run_id"],"finish_frame":finish})


def _j09_close_success(value):
    """Full Runtime.evaluate response observed from the real close hook.

    Do not accept an extracted truthy value: errors/exceptions alongside the
    alleged result contradict successful execution of this explicit action.
    """
    return (type(value) is dict and set(value) == {"id","result"}
            and type(value["id"]) is int and value["id"] > 0
            and type(value["result"]) is dict and set(value["result"]) == {"result"}
            and value["result"]["result"] == {"type":"string","value":"closed"})


def _j09_reconnect(observation,page,phase,previous,epochs):
    events,frames = page["events"],page["frames"]
    close,window = phase["close"],phase["auto_observation"]
    _journey_need(type(close["closed_event"]) is int and 0 <= close["closed_event"] < len(events), "J09 missing actual closed event")
    event = events[close["closed_event"]];params = event["params"]
    hs = events[epochs["e1"]["handshake_event"]]["params"]
    response = events[epochs["e1"]["response_event"]]["params"]
    _journey_need(event["method"] == "Network.webSocketClosed" and params["requestId"] == close["request_id"] == epochs["e0"]["request_id"]
                  and _j09_close_success(close["evaluation_result"]) and all(_j06_number(t) for t in (close["command_timestamp"],close["completed_timestamp"],params["timestamp"]))
                  and close["command_timestamp"] == phase["action_timestamp"] and close["command_timestamp"] <= close["completed_timestamp"] <= phase["read_end_timestamp"]
                  and close["command_timestamp"] <= params["timestamp"] <= hs["timestamp"], "J09 no genuine old-socket close before automatic reconnect")
    header = {k.lower():v for k,v in hs["request"]["headers"].items()}
    _journey_need(header["sec-websocket-protocol"].split(",")[2].strip() == previous["session"], "J09 reconnect third protocol entry is not s0")
    _journey_need(window["start_timestamp"] == response["timestamp"] and _j06_number(window["end_timestamp"])
                  and window["start_timestamp"]+J09_AUTO_OBSERVE_SECONDS <= window["end_timestamp"] <= phase["read_end_timestamp"], "J09 incomplete real 5-second no-input observation")
    selected = frames[phase["start"]:phase["end"]]
    _journey_need(all(_j09_quiet(f["decoded"]) or f["timestamp"] <= window["end_timestamp"] for f in selected), "J09 omitted late run activity from auto observation")
    new = [f for f in selected if f["request_id"] == epochs["e1"]["request_id"]]
    started = any(not _j09_quiet(f["decoded"]) for f in new)
    if observation["plan"] == "ui-probe":
        _journey_need(not started and all(_j09_quiet(f["decoded"]) for f in selected)
                      and phase["dom_after"] == phase["dom_before"] and phase["client_states"] == [] and phase["completions"] == []
                      and phase["ipc"] == {"table":None,"chart":None}, "J09 natural activity was hidden by ui-probe or stale DOM claimed new proof")
        return previous
    _journey_need(started, "J09 natural branch has no actual new-connection run")
    return _j09_result_run(observation,page,phase,previous,natural=True)


def _j09_pngs(observation):
    records,phases,page = observation["screenshots"],observation["phases"],observation["page"]
    _journey_need(isinstance(records,list) and len(records) == len(phases), "J09 missing/extra 6-or-8 phase pictures")
    paths = set();root = pathlib.Path(observation["ipc_dir"]).resolve()
    for phase in phases:
        matches = [r for r in records if r.get("phase") == phase["name"]]
        _journey_need(len(matches) == 1, "J09 missing/duplicate phase PNG")
        record = matches[0];file = pathlib.Path(record["file"]);path = (root/file).resolve();stamp = record["timestamp"]
        _journey_need(record["namespace"] == page["namespace"] and record["epoch"] == phase["epoch"]
                      and record["step_ids"] == list(J09_PNG_ROLES[phase["name"]])
                      and (record["step_ids"] or record.get("role") == "preparation"), "J09 wrong PNG source/epoch/step role")
        _journey_need(not file.is_absolute() and ".." not in file.parts and path.is_relative_to(root) and path.is_file() and path not in paths, "J09 missing/unsafe/reused PNG")
        data = path.read_bytes()
        _journey_need(data.startswith(b"\x89PNG\r\n\x1a\n") and hashlib.sha256(data).hexdigest() == record["sha256"]
                      and _j06_number(stamp) and phase["read_end_timestamp"] <= stamp <= phase["observation_end_timestamp"]
                      and stamp-phase["read_end_timestamp"] <= STAGE2_SCREENSHOT_MAX_LAG_SECONDS, "J09 PNG SHA/clock mismatch")
        paths.add(path)


J09_SLOW_CASE = "j09-slow-sequence"
J09_SLOW_CONTRACT = "journey-j09-expiry-v1"
J09_SLOW_BASE_CRITERIA_SHA256 = "46537c0dc56f5327662012dc4766b86536b990e7d7da4f8a9a416061c64c5aed"
J09_SLOW_TTL_SECONDS = 120
J09_SLOW_HOLD_SECONDS = 135
J09_SLOW_SUFFIX = ("s4-upload-baseline", "s4-pulse", "s4-disconnected-hold",
                   "s4-expired-reconnect", "s4-recovery-read")
J09_SLOW_PHASES = {plan:prefix+J09_SLOW_SUFFIX for plan,prefix in J09_PHASES.items()}
J09_SLOW_INPUTS = dict(J09_INPUTS, **{"s4-upload-baseline":"sales_basic.csv"})
J09_SLOW_ACTIONS = dict(J09_ACTIONS, **{
    "s4-upload-baseline":{"action":"upload"}, "s4-pulse":{"action":"pulse","label":"Pulse"},
    "s4-disconnected-hold":{"action":"close-and-hold"},
    "s4-expired-reconnect":{"action":"clear-block-and-reconnect"},
    "s4-recovery-read":{"action":"read-recovery"},
})
J09_SLOW_RECOVERY_ACTIONS = ("observe","rerun")
# Independently reviewed expired-recovery oracle, from the 2026-10-25 slow
# round. A separate reviewer audited both frozen raws end to end (integrity,
# provenance, real 135s hold windows, retry lifecycles, session semantics,
# both formal replays) and derived these values from the raw bytes. The
# semantics are identical on both runtimes; the evidence identities differ.
# Observed nuance the golden pins: the browser RETAINS the uploaded file chip
# after expiry and re-sends widget state referencing the AGED session's file;
# the reset is server-side -- counters back to 1/0, no table/chart, the info
# alert restored and null IPC.
J09_SLOW_ORACLE_SEMANTICS = {
    "aged": {
        "script_runs": "3", "pulses": "1", "uploaded_files": ["sales_basic.csv"],
        "table_present": True, "chart_bars": 4, "alerts": [],
        "selectbox_value": "category", "slider_value": "0", "checkbox_checked": True,
    },
    "recovered": {
        "script_runs": "1", "pulses": "0", "uploaded_files": ["sales_basic.csv"],
        "has_uploader": True, "table_present": False, "table_cells": [],
        "chart_present": False, "chart_bars": 0, "chart_marks": "", "exceptions": [],
        "alerts": ["Upload a CSV to see the aggregated result."],
        "selectbox_value": "category", "slider_value": "0", "checkbox_checked": True,
    },
    "recovered_ipc": {"table": None, "chart": None},
    "recovery_action": "rerun",
}
J09_SLOW_ORACLE_REVIEW = {
    "python": {
        "raw_sha256": "52690c154321b7030eee285c566779b24f14390681a13dca00f0db6afe87cd18",
        "aged_session_id": "04227a38-fa1e-4a2a-bdf0-1fb5beeb5a22",
        "recovered_session_id": "704f16ae-fcbb-4323-bc47-68e88180fb30",
        "hold_first_utc": "2026-10-25T05:59:46Z", "hold_last_utc": "2026-10-25T06:02:01Z", "hold_samples": 125,
        "screenshots": (
            "0f31248ed4afb3161e8109150303b9c49f5b7566ad455d4e4f3cba0348644b2e",
            "d0bfe9c32be9e08f18b926364bc93ae8d73bf20b7b1123ff19c7a266c3a12db9",
            "f8f8b15f59caf48fe1069051a7600931c1f73755ce3318c59780b4edbcce64d5",
            "db7276ccfefd3f2e9c47a182487021d6b7b4cb602406b037aba939122ca403a6",
            "db7276ccfefd3f2e9c47a182487021d6b7b4cb602406b037aba939122ca403a6",
            "9896d6d565c421bad6a1a7d910b37939ba520df6646837a1d0f1a928e2a0b892",
            "9bb5e3b4f38414e1079210a6c9b005f8a20aa11ac74b5efcbe8211e874c5a344",
            "0f31248ed4afb3161e8109150303b9c49f5b7566ad455d4e4f3cba0348644b2e",
            "d0bfe9c32be9e08f18b926364bc93ae8d73bf20b7b1123ff19c7a266c3a12db9",
            "f8f8b15f59caf48fe1069051a7600931c1f73755ce3318c59780b4edbcce64d5",
            "d722d1ff1f8390f5bd53090f285f3610ace42d903033645b6d9098046b217381",
            "f8f8b15f59caf48fe1069051a7600931c1f73755ce3318c59780b4edbcce64d5",
            "bc42c66c67e8bb82d84f0feb55779c8ac0fb866a6e23a62d07645baa27abed5b",
        ),
        "ttl_evidence": (
            "6a9348feb3744565b1062d1572aee47ad21508733ddceb1b620e2e6ce467f1a8",
            "ef9479bcd907e4573a695770c3bf9c7c407d73d85ee1f21dbca951dd0baa9f09",
            "2a21dec21d32ac4e12b823a61ecd19e66027f957fbcff21314c7d5ca75027178",
            "475e27d4d957a2d20ca31f882bcc7add8c7005a6bfdee81a92e3c3784fdc0b9c",
        ),
    },
    "native": {
        "raw_sha256": "9610adb11f75ece995fd13f120633324d3a11241094f450f25216c88a7d03d1f",
        "aged_session_id": "32bae1e8-eb5a-4c98-917a-25bc07587b04",
        "recovered_session_id": "c5679ee4-ce82-422d-b8a8-7b443667d481",
        "hold_first_utc": "2026-10-25T06:04:13Z", "hold_last_utc": "2026-10-25T06:06:29Z", "hold_samples": 126,
        "screenshots": (
            "cd514b9144c358dcbc7995a100fffca9f1b304e270e044861e055f12a2018704",
            "04d29bc70c225a00a30c09de97afc43e4f8113fac793551bfe66d9fb5654a0d1",
            "455839436fdde005a8fa1cb638181c3d196085245a00f500df390aba78e31993",
            "64f6d962a441d8bfc3e9c5ec8ca0627dd3fd7a55356c6789ff03903aff437221",
            "64f6d962a441d8bfc3e9c5ec8ca0627dd3fd7a55356c6789ff03903aff437221",
            "9e7f9299fbe2daf104834ffc5e513fa96e103bab3c45a7aa384c346dd0fef3fe",
            "7c6829ddfaf226ba0f86c243964a158cf567011692d9eb99a8d642a8545ef893",
            "cd514b9144c358dcbc7995a100fffca9f1b304e270e044861e055f12a2018704",
            "04d29bc70c225a00a30c09de97afc43e4f8113fac793551bfe66d9fb5654a0d1",
            "455839436fdde005a8fa1cb638181c3d196085245a00f500df390aba78e31993",
            "017075929e002e6bc448fe1202206843ea3f1bc32d2677bb3a0037635360fadf",
            "455839436fdde005a8fa1cb638181c3d196085245a00f500df390aba78e31993",
            "b4240058f01ce53a773c582c19a3b1f77f587e7de38f1fec57dde00a87f77f49",
        ),
        "ttl_evidence": (
            "101354402fc243ac10522dad25fbc3b82da9f2acd0279e3baed3ac76e8b65387",
            "eef1173d9cbb2c26e4471a5059254db07af7fb31cdadb06b049d36f1c3966b7d",
            "5ab7564d2de266fcb8c23bdca1b45cb5512fa74b0721fa9168ba7f443494da5e",
            "71e0bd33d947dd190c1561887c406ae6262026c67325fe7d171955734019fcc4",
            "42e54a740db398b0cad26681f9e28099e77d70c84abf3b85c62cf3d36121f418",
        ),
    },
}
J09_SLOW_TTL_EVIDENCE_KINDS = {"python":("process","config","effective-config","app-source"),
                             "native":("process","build","config","server-source","entry-source")}
J09_SLOW_PNG_ROLES = dict(J09_PNG_ROLES, **{name:(("J09-S4",) if name == "s4-recovery-read" else ()) for name in J09_SLOW_SUFFIX})
J09_SLOW_REQUIRED = ("contract", "single_capture", "base_range", "base_s1_s3", "prep_state", "effective_ttl120",
    "runtime_provenance", "scoped_block_rule", "actual_close", "hold_135_real_seconds", "no_101_during_hold",
    "retry_event_coverage", "unblock_boundary", "old_id_requested", "new_session_observed", "same_document_cache",
    "no_reupload_or_extra_actions", "actual_recovery_run", "recovery_oracle_verified", "png_sources")
J09_SLOW_OBSERVATION_FIELDS = dict(J09_OBSERVATION_FIELDS, **{
    "root":J09_OBSERVATION_FIELDS["root"]+("base_range","ttl_configuration","commands","hold","recovery"),
    "base_range":("phase_count","frame_end","event_end","http_end","screenshot_count","cutoff_timestamp"),
    "ttl_configuration":("runtime","effective_seconds","process_id","process_command_line","evidence"),
    "evidence":("kind","file","sha256"),
    "command":("target_id","method","params","started_monotonic","finished_monotonic","cdp_before","cdp_after","response"),
    "hold":("close","block_command","unblock_command","samples"),
    "sample":("cdp_timestamp","driver_monotonic","utc"),
    "recovery":("requested_session_id","observed_session_id","recovery_action","oracle_status"),
})
JOURNEY_REQUIRED[J09_SLOW_CASE] = {(J09_SLOW_CASE,key) for key in J09_SLOW_REQUIRED}
# One new complete capture: the original J09 prefix, then all five S4 phases.
# plan still selects natural/ui-probe only for S1-S3. S4's read-recovery phase
# records the actual observe/rerun string in recovery.recovery_action; no placeholder
# run. The recovery oracle is the independently reviewed 2026-10-25 golden:
# identical aged/recovered semantics on both runtimes (the browser keeps the
# file chip and re-references the aged session's file state; the server-side
# reset returns counters 1/0, removes table/chart, restores the info alert and
# emits null IPC) plus one of the two reviewed evidence identities. Synthetic
# or mutated evidence cannot satisfy both layers; the raw's capture-time
# recovery.oracle_status stays the driver's capture-time "unverified" string
# and is superseded by this reviewed judgment.
# The S3 fresh session s1/e2/d1 is explicitly populated by S4's upload + one
# Pulse before it is aged. Only two uploads total; no PUT/Pulse/F5 after prep.
# All attempts, including failed ones, remain in page.events. page.epochs keeps
# successful protocol epochs: e0/e1 share d0; e2 and recovered e3 share d1.
# No successful HTTP101 is allowed between the actual e2 closed event and the
# unblock command: its cdp_before must be >= closed timestamp + 135 real seconds.
# hold.close uses J09's full raw CDP close response and actual closed_event.
# block/unblock_command are indices into root.commands (target-only exact WS
# rule/clear); cdp_before/cdp_after come from actual Performance.getMetrics
# Timestamp reads bracketing that command. Apply/ack the scoped rule before
# native close, as actually measured by the short preflight. Samples retain
# real CDP/driver monotonic clocks plus UTC. Recompute
# interval membership from raw events, never a_responses_while_rule_active or
# a producer success boolean. No global network rule, proxy or virtual time.
# ttl_configuration.effective_seconds must be 120. Python evidence includes
# actual PID argv, config/config-source and runtime 1.66.1. Native evidence must
# include the sealed 769+dirty candidate/build manifest, source snapshot proving
# the 120s constructor/no override, launch config and matching running binary;
# merely quoting the current source default is insufficient. Evidence artifacts
# are relative to ipc_dir, preserving their original bytes and SHA256.
# base_range is captured at S3 completion, before any S4 action. All *_end values
# are exclusive cursors into this same full capture. No events/raw are rewritten.


def j09_slow_checks(*, observation=None):
    """Validate the S4 guards and the independently reviewed recovery oracle."""
    verified = set()
    try:
        _j09_slow_verify(observation,verified)
    except (ValueError,TypeError,KeyError,IndexError,OSError,AttributeError) as exc:
        failure = str(exc)
    else:
        failure = "guard pass complete"
    return _journey_finish(J09_SLOW_CASE, [_check(J09_SLOW_CASE,key,"complete real J09 including S4 evidence",
        "reviewed expired-recovery oracle verified" if key == "recovery_oracle_verified" and key in verified
        else "common guard verified" if key in verified else failure,
        key in verified) for key in J09_SLOW_REQUIRED])


def _j09_slow_recovery_oracle(observation):
    """The reviewed golden: matching semantics AND one of the reviewed identities."""
    phases = {phase["name"]: phase for phase in observation["phases"]}
    aged, recovered = phases["s4-pulse"], phases["s4-recovery-read"]
    semantics = J09_SLOW_ORACLE_SEMANTICS
    _journey_need({key: aged["dom_after"][key] for key in semantics["aged"]} == semantics["aged"],
                  "S4 oracle aged state differs from the reviewed golden")
    _journey_need({key: recovered["dom_after"][key] for key in semantics["recovered"]} == semantics["recovered"],
                  "S4 oracle recovered state differs from the reviewed golden")
    _journey_need(recovered["ipc"] == semantics["recovered_ipc"],
                  "S4 oracle recovered IPC differs from the reviewed golden")
    _journey_need(observation["recovery"]["recovery_action"] == semantics["recovery_action"],
                  "S4 oracle recovery action differs from the reviewed golden")
    samples = observation["hold"]["samples"]
    identity = (observation["recovery"]["requested_session_id"], observation["recovery"]["observed_session_id"],
                samples[0]["utc"], samples[-1]["utc"], len(samples),
                tuple(record["sha256"] for record in observation["screenshots"]),
                tuple(record["sha256"] for record in observation["ttl_configuration"]["evidence"]))
    reviewed = {(golden["aged_session_id"], golden["recovered_session_id"], golden["hold_first_utc"],
                 golden["hold_last_utc"], golden["hold_samples"], tuple(golden["screenshots"]),
                 tuple(golden["ttl_evidence"])) for golden in J09_SLOW_ORACLE_REVIEW.values()}
    _journey_need(identity in reviewed, "S4 oracle evidence identity is not one of the two reviewed raws")


def _j09_slow_base_view(observation):
    """Explicit, validated prefix projection; never a replacement for full raw.

    Only the S1-S3 validator consumes this view. The slow validator must still
    inspect every original tail frame/event/HTTP request and all S4 phases.
    This reader is also usable before S4 starts, when the capture has no tail.
    """
    import copy

    _journey_need(observation.get("journey") == J09_SLOW_CASE and observation.get("contract") == J09_SLOW_CONTRACT
                  and observation.get("plan") in J09_PHASES, "J09 slow missing versioned prefix contract")
    ranges,page = observation["base_range"],observation["page"]
    count = len(J09_PHASES[observation["plan"]])
    _journey_need(ranges["phase_count"] == ranges["screenshot_count"] == count
                  and tuple(p["name"] for p in observation["phases"][:count]) == J09_PHASES[observation["plan"]], "J09 slow prefix phase/PNG count differs")
    for key,items in (("frame_end",page["frames"]),("event_end",page["events"]),("http_end",page["http_timeline"]),
                      ("phase_count",observation["phases"]),("screenshot_count",observation["screenshots"])):
        _journey_need(type(ranges[key]) is int and 0 <= ranges[key] <= len(items), "J09 slow invalid exclusive prefix cursor: " + key)
    cut = ranges["cutoff_timestamp"]
    _journey_need(_j06_number(cut) and cut == observation["phases"][count-1]["observation_end_timestamp"]
                  and ranges["frame_end"] > 0 and all(f["timestamp"] <= cut for f in page["frames"][:ranges["frame_end"]])
                  and all(f["timestamp"] > cut for f in page["frames"][ranges["frame_end"]:]), "J09 slow prefix cutoff hides or borrows frames")
    binary = lambda events:sum(e.get("method") in ("Network.webSocketFrameSent","Network.webSocketFrameReceived")
                              and e.get("params",{}).get("response",{}).get("opcode") == 2 for e in events)
    _journey_need(binary(page["events"][:ranges["event_end"]]) == ranges["frame_end"]
                  and binary(page["events"]) == len(page["frames"]), "J09 slow prefix frame/event cursor mismatch")
    _journey_need(all(_j06_number(h.get("timestamp")) and h["timestamp"] <= cut for h in page["http_timeline"][:ranges["http_end"]])
                  and all(_j06_number(h.get("timestamp")) and h["timestamp"] > cut for h in page["http_timeline"][ranges["http_end"]:]), "J09 slow prefix HTTP cursor mismatch")
    prefix_page = dict(page,frames=page["frames"][:ranges["frame_end"]],events=page["events"][:ranges["event_end"]],
                       http_timeline=page["http_timeline"][:ranges["http_end"]],epochs=page["epochs"][:3])
    return copy.deepcopy(dict(journey=J09_CASE,contract=J09_CONTRACT,plan=observation["plan"],url=observation["url"],
        ipc_dir=observation["ipc_dir"],page=prefix_page,phases=observation["phases"][:count],screenshots=observation["screenshots"][:count]))


def _j09_slow_artifact(observation,record):
    root = pathlib.Path(observation["ipc_dir"]).resolve();file = pathlib.Path(record["file"]);path = (root/file).resolve()
    _journey_need(not file.is_absolute() and ".." not in file.parts and path.is_relative_to(root) and path.is_file(), "S4 missing/unsafe provenance artifact")
    data = path.read_bytes()
    _journey_need(hashlib.sha256(data).hexdigest() == record["sha256"], "S4 provenance artifact SHA mismatch")
    return data


def _j09_slow_ttl(observation):
    import tomllib
    from urllib.parse import urlsplit
    from streamlit.proto.ForwardMsg_pb2 import ForwardMsg

    ttl = observation["ttl_configuration"]
    _journey_need(type(ttl["effective_seconds"]) is int and ttl["effective_seconds"] == 120
                  and type(ttl["process_id"]) is int and ttl["process_id"] > 0 and ttl["runtime"] in ("python","native"), "S4 effective TTL/runtime/PID is not explicit 120")
    records = {r["kind"]:r for r in ttl["evidence"]}
    _journey_need(len(records) == len(ttl["evidence"]) and set(records) == set(J09_SLOW_TTL_EVIDENCE_KINDS[ttl["runtime"]]), "S4 missing/duplicate provenance kind")
    contents = {kind:_j09_slow_artifact(observation,r) for kind,r in records.items()}
    process = json.loads(contents["process"])
    processes = process if isinstance(process,list) else [process]
    matches = [p for p in processes if p.get("pid") == ttl["process_id"]]
    _journey_need(len(matches) == 1 and type(matches[0].get("pid")) is int and matches[0]["command_line"] == ttl["process_command_line"]
                  and matches[0]["port"] == urlsplit(observation["url"]).port, "S4 process/argv/listener identity differs")
    command = ttl["process_command_line"]
    if ttl["runtime"] == "python":
        config = tomllib.loads(contents["config"].decode("utf-8"))
        _journey_need(type(config["server"]["disconnectedSessionTTL"]) is int and config["server"]["disconnectedSessionTTL"] == 120
                      and re.findall(r"--server\.disconnectedSessionTTL(?:=|\s+)(\d+)(?=\s|$)",command) == ["120"]
                      and re.search(r"(?m)^\s*disconnectedSessionTTL\s*=\s*120\s*$",contents["effective-config"].decode("utf-8")), "S4 Python argv/config/effective configuration disagree")
        _journey_need(records["app-source"]["sha256"] == "475e27d4d957a2d20ca31f882bcc7add8c7005a6bfdee81a92e3c3784fdc0b9c", "S4 reference app source is not the frozen public fixture")
        found = False
        for frame in observation["page"]["frames"][:observation["base_range"]["frame_end"]]:
            if frame["direction"] != "server->client":continue
            message = ForwardMsg();message.ParseFromString(base64.b64decode(frame["base64"],validate=True))
            if message.WhichOneof("type") == "new_session":
                _journey_need(message.new_session.initialize.environment_info.streamlit_version == "1.66.1"
                              and message.new_session.main_script_path.replace("\\","/") in command.replace("\\","/"), "S4 Python actual NewSession runtime/app path mismatch")
                found = True
        _journey_need(found, "S4 no actual Python runtime NewSession")
    else:
        build = json.loads(contents["build"])
        _journey_need(records["build"]["sha256"] == "eef1173d9cbb2c26e4471a5059254db07af7fb31cdadb06b049d36f1c3966b7d"
                      and build["git_base"] == "76938fb643149424e69af0ddbccc3127be751178"
                      and "Dirty" in build["source_state"] and matches[0]["binary_sha256"] == build["binary_sha256"]
                      and build["binary_path"].replace("\\","/").lower() in command.replace("\\","/").lower()
                      and records["config"]["sha256"] == build["config_sha256"]
                      and records["entry-source"]["sha256"] == build["actual_data_app_sha256"]
                      and records["server-source"]["sha256"] == build["runtime_members"]["repo/streamlit/src/server.rs"], "S4 native process/build/source/config identity differs from sealed 769+dirty candidate")
        _journey_need(b"SessionStore::new(Duration::from_secs(120))" in contents["server-source"]
                      and not re.search(rb"\.\s*with_disconnected_session_ttl\s*\(",contents["entry-source"]), "S4 native compiled entry overrides retention or lacks the sealed 120s constructor")


def _j09_slow_command(observation,index):
    _journey_need(type(index) is int and 0 <= index < len(observation["commands"]), "S4 missing actual command index")
    command = observation["commands"][index]
    _journey_need(command["target_id"] == observation["page"]["target_id"]
                  and all(_j06_number(command[k]) for k in ("started_monotonic","finished_monotonic","cdp_before","cdp_after"))
                  and command["started_monotonic"] <= command["finished_monotonic"] and command["cdp_before"] <= command["cdp_after"]
                  and abs((command["cdp_after"]-command["cdp_before"])-(command["finished_monotonic"]-command["started_monotonic"])) <= 1,
                  "S4 command target/paired real clocks mismatch")
    response = command["response"]
    _journey_need(type(response) is dict and set(response) == {"id","result"} and type(response["id"]) is int and response["id"] > 0
                  and type(response["result"]) is dict, "S4 command failed or has contradictory response")
    return command


def _j09_slow_hold(observation,page,phase):
    from urllib.parse import urlsplit,urlunsplit

    hold,events = observation["hold"],page["events"]
    block = _j09_slow_command(observation,hold["block_command"]);clear = _j09_slow_command(observation,hold["unblock_command"])
    url = urlsplit(observation["url"]);ws = urlunsplit(("wss" if url.scheme == "https" else "ws",url.netloc,url.path.rstrip("/")+"/_stcore/stream","",""))
    _journey_need(block["method"] == clear["method"] == "Network.emulateNetworkConditionsByRule"
                  and block["params"] == {"matchedNetworkConditions":[{"urlPattern":ws,"offline":True,"latency":0,"downloadThroughput":-1,"uploadThroughput":-1}]}
                  and clear["params"] == {"matchedNetworkConditions":[]}
                  and set(block["response"]["result"]) == {"ruleIds"} and isinstance(block["response"]["result"]["ruleIds"],list)
                  and len(block["response"]["result"]["ruleIds"]) == 1 and isinstance(block["response"]["result"]["ruleIds"][0],str)
                  and block["response"]["result"]["ruleIds"][0] and clear["response"]["result"] == {"ruleIds":[]}, "S4 not an acknowledged exact target WS rule/clear")
    rules = [i for i,c in enumerate(observation["commands"]) if c["method"] == "Network.emulateNetworkConditionsByRule"]
    _journey_need(rules == [hold["block_command"],hold["unblock_command"]]
                  and not any(c["method"] in ("Network.emulateNetworkConditions","Network.overrideNetworkState","Emulation.setVirtualTimePolicy","Fetch.enable") for c in observation["commands"]), "S4 extra/global network or virtual-time intervention")
    close = hold["close"];index = close["closed_event"]
    _journey_need(type(index) is int and 0 <= index < len(events), "S4 missing actual closed event")
    event = events[index];closed = event["params"]["timestamp"]
    _journey_need(event["method"] == "Network.webSocketClosed" and event["params"]["requestId"] == close["request_id"] == page["epochs"][2]["request_id"]
                  and _j09_close_success(close["evaluation_result"])
                  and all(_j06_number(close[k]) for k in ("command_timestamp","completed_timestamp"))
                  and phase["action_timestamp"] <= block["cdp_before"] <= block["cdp_after"] <= close["command_timestamp"] <= closed
                  and close["command_timestamp"] <= close["completed_timestamp"] <= phase["read_end_timestamp"], "S4 explicit native close/rule order or old socket identity failed")
    samples = hold["samples"]
    _journey_need(isinstance(samples,list) and len(samples) >= 2, "S4 missing actual paired clock samples")
    times = []
    for sample in samples:
        instant = datetime.fromisoformat(sample["utc"].replace("Z","+00:00"))
        _journey_need(instant.utcoffset() is not None and _j06_number(sample["cdp_timestamp"]) and _j06_number(sample["driver_monotonic"]), "S4 invalid real clock/UTC sample")
        times.append((sample["cdp_timestamp"],sample["driver_monotonic"],instant.timestamp()))
    _journey_need(closed <= times[0][0] and times[-1][0] <= phase["read_end_timestamp"] <= clear["cdp_before"]
                  and all(all(a[k] < b[k] for k in (0,1,2)) for a,b in zip(times,times[1:]))
                  and times[-1][0]-times[0][0] >= 135 and times[-1][1]-times[0][1] >= 135
                  and all(abs((t[0]-times[0][0])-(t[1]-times[0][1])) <= 1 and abs((t[0]-times[0][0])-(t[2]-times[0][2])) <= 2
                          and abs((t[1]-t[0])-(block["started_monotonic"]-block["cdp_before"])) <= 1
                          and abs((t[1]-t[0])-(clear["started_monotonic"]-clear["cdp_before"])) <= 1 for t in times), "S4 no continuous >=135s real CDP+driver+UTC interval after close")
    _journey_need(not any(e.get("method") == "Network.webSocketHandshakeResponseReceived" and e["params"]["response"].get("status") == 101
                          and closed <= e["params"]["timestamp"] < clear["cdp_before"] for e in events), "S4 successful HTTP101 occurred during disconnected hold")
    _journey_need(not any(closed < f["timestamp"] < clear["cdp_before"] for f in page["frames"]), "S4 WS frames occurred during supposedly disconnected hold")
    return closed,clear,ws


def _j09_slow_epoch(observation,page,previous,closed,clear,ws):
    epochs,events = page["epochs"],page["events"]
    _journey_need([e["id"] for e in epochs] == ["e0","e1","e2","e3"], "S4 undeclared/missing successful epoch")
    e = epochs[3]
    _journey_need(e["document_event"] == epochs[2]["document_event"] and e["navigation_event"] is None and e["navigation_timestamp"] is None
                  and e["connection"] == 3 and e["request_id"] not in {p["request_id"] for p in epochs[:3]}, "S4 restore changed document or reused a connection")
    for key in ("handshake_event","response_event"):
        _journey_need(type(e[key]) is int and 0 <= e[key] < len(events), "S4 missing restore handshake event")
    hs,response = events[e["handshake_event"]],events[e["response_event"]]
    hp,rp = hs["params"],response["params"]
    protocols = [s.strip() for s in {k.lower():v for k,v in hp["request"]["headers"].items()}.get("sec-websocket-protocol","").split(",")]
    _journey_need(hs["method"] == "Network.webSocketWillSendHandshakeRequest" and response["method"] == "Network.webSocketHandshakeResponseReceived"
                  and hp["requestId"] == rp["requestId"] == e["request_id"] and rp["response"]["status"] == 101
                  and {k.lower():v for k,v in rp["response"]["headers"].items()}.get("sec-websocket-protocol") == "streamlit"
                  and len(protocols) == 3 and protocols[:2] == ["streamlit",protocols[1]] and protocols[1]
                  and protocols[2] == previous["session"] and clear["cdp_before"] <= hp["timestamp"] <= rp["timestamp"], "S4 restore did not request the expired s1 via its actual third subprotocol")
    success = [p["params"] for p in events if p.get("method") == "Network.webSocketHandshakeResponseReceived" and p["params"]["response"].get("status") == 101]
    _journey_need(len(success) == 4 and {p["requestId"] for p in success} == {p["request_id"] for p in epochs}, "S4 hidden successful reconnect")
    docs = {i for i,v in enumerate(events) if v.get("method") == "Network.requestWillBeSent" and v.get("params",{}).get("type") == "Document"}
    _journey_need(docs == {epochs[0]["document_event"],epochs[2]["document_event"]}, "S4 F5/new document occurred during expiry proof")
    tail = events[observation["base_range"]["event_end"]:]
    ids = {p["params"]["requestId"] for p in tail if p.get("method","").startswith("Network.webSocket")}
    successes = {p["request_id"] for p in epochs}
    blocked = 0
    for request in ids-successes:
        created = [p for p in tail if p.get("method") == "Network.webSocketCreated" and p["params"]["requestId"] == request]
        errors = [p for p in tail if p.get("method") in ("Network.webSocketFrameError","Network.webSocketClosed") and p["params"]["requestId"] == request]
        _journey_need(len(created) == 1 and created[0]["params"]["url"] == ws and errors
                      and all(_j06_number(p["params"].get("timestamp")) and p["params"]["timestamp"] >= closed for p in errors), "S4 incomplete/foreign retry lifecycle")
        if any(p["method"] == "Network.webSocketFrameError" and "ERR_INTERNET_DISCONNECTED" in p["params"].get("errorMessage","")
               and closed <= p["params"]["timestamp"] < clear["cdp_before"] for p in errors):blocked += 1
    _journey_need(blocked > 0, "S4 no actual failed target WS retry proves the block")
    _journey_need(all((f["connection"],f["request_id"]) in {(p["connection"],p["request_id"]) for p in epochs} for f in page["frames"])
                  and all(f["timestamp"] >= rp["timestamp"] for f in page["frames"] if f["request_id"] == e["request_id"]), "S4 restore frame/HTTP101 epoch mismatch")
    return e,rp["timestamp"]


def _j09_slow_run(observation,page,phase,epoch):
    frames = page["frames"];indices = range(phase["start"],phase["end"])
    starts = [i for i in indices if frames[i]["decoded"].get("type") == "new_session"]
    done = [i for i in indices if frames[i]["decoded"].get("type") == "script_finished"]
    clients = [i for i in indices if frames[i]["decoded"].get("type") == "rerun_script"]
    _journey_need(len(starts) == len(done) == 1 and starts[0] < done[0] and len(clients) <= 1
                  and (not clients or clients[0] < starts[0]), "S4 pending/extra recovery run cannot be replaced by a UI rerun")
    start,finish = starts[0],done[0];message = frames[start]["decoded"]["new_session"]
    _journey_need(message.get("session_id") and message.get("script_run_id") and frames[finish]["decoded"]["script_finished"].get("status") == 0
                  and all((frames[i]["connection"],frames[i]["request_id"]) == (epoch["connection"],epoch["request_id"]) for i in indices), "S4 recovery run missing success/session/epoch identity")
    for i in indices:
        if start <= i <= finish or i in clients:continue
        _journey_need(_j09_quiet(frames[i]["decoded"]), "S4 recovery output lies outside the target run")
    deltas = [frames[i]["decoded"]["delta"] for i in range(start+1,finish) if frames[i]["decoded"].get("type") == "delta"]
    dom = phase["dom_after"]
    alerts = [d.get("alert") for d in deltas if d.get("element") == "alert"]
    exceptions = [d.get("exception") for d in deltas if d.get("element") == "exception"]
    _journey_need(all(isinstance(a,dict) for a in alerts) and dom["alerts"] == [a.get("body") for a in alerts]
                  and len(dom["exceptions"]) == len(exceptions)
                  and all(isinstance(e,dict) and isinstance(text,str) and str(e.get("message") or e.get("type") or "") in text for e,text in zip(exceptions,dom["exceptions"])), "S4 actual recovery alerts/exceptions differ from DOM")
    for label,key in (("Script runs","script_runs"),("Pulses","pulses")):
        values = [int(m[1]) for d in deltas if d.get("element") in ("text","markdown") and isinstance(d.get("body"),str)
                  and (m := re.fullmatch(re.escape(label)+r":\s*(\d+)",d["body"].strip()))]
        _journey_need(values == [_stage2_counter(dom,key)], "S4 actual recovery counter/DOM mismatch")
    if clients:
        states = frames[clients[0]]["decoded"]["rerun_script"]["widget_states"]
        _journey_need(len({s.get("id") for s in states}) == len(states), "S4 duplicate recovery widget state")
        _stage2_typed_controls(deltas,states,dom,float(dom["slider_value"]),group=dom["selectbox_value"],include_unknown=dom["checkbox_checked"])
    tables = [d for d in deltas if d.get("element") == "dataframe"]
    charts = [d for d in deltas if d.get("element") == "vega_lite_chart"]
    _journey_need(len(tables) <= 1 and len(charts) <= 1, "S4 duplicate actual recovery result")
    # Self-consistency only. Whether any file/data/widget should survive is an
    # unverified oracle criterion, never inferred from this result's own rows.
    if tables:
        kept = phase["ipc"]["table"]["arrow"]
        table = _journey_ipc(tables[0]["arrow"],{"ipc_dir":observation["ipc_dir"],"ipc_files":{kept["sha256"]:kept["file"]}})
        if table["row_count"]:
            _stage2_static_view(observation,phase,{"deltas":deltas},expected_rows=table["rows"])
        else:
            _journey_need(dom["table_present"] is True and not _filled_cells(dom["table_cells"]) and not charts and dom["chart_present"] is False and dom["chart_bars"] == 0, "S4 stale empty result DOM/chart")
    else:
        _journey_need(not charts and phase["ipc"] == {"table":None,"chart":None} and dom["table_present"] is False
                      and not _filled_cells(dom["table_cells"]) and dom["chart_present"] is False and dom["chart_bars"] == 0, "S4 old DOM/IPC substituted for actual recovery output")
    return {"session":message["session_id"],"checkpoint":{"epoch":"e3","script_run_id":message["script_run_id"],"finish_frame":finish},"client":clients[0] if clients else None}


def _j09_slow_signature(dom):
    _journey_need(isinstance(dom,dict) and set(J06_OBSERVATION_FIELDS["dom"]) <= dom.keys()
                  and isinstance(dom["uploaded_files"],list) and isinstance(dom["exceptions"],list), "S4 missing fresh actual DOM fields")
    return {k:dom[k] for k in J06_OBSERVATION_FIELDS["dom"]}


def _j09_slow_summary(page,phase):
    selected = page["frames"][phase["start"]:phase["end"]]
    states = [{k:s.get(k) for k in ("id","value_field","value")} for f in selected if f["decoded"].get("type") == "rerun_script"
              for s in f["decoded"]["rerun_script"]["widget_states"]]
    completions = [{"frame":i,"connection":f["connection"],"request_id":f["request_id"],"status":f["decoded"]["script_finished"].get("status"),
                    "status_name":f["decoded"]["script_finished"].get("status_name")} for i,f in enumerate(selected) if f["decoded"].get("type") == "script_finished"]
    _journey_need(phase["client_states"] == states and phase["completions"] == completions, "S4 summaries do not match effective raw")


def _j09_slow_verify(observation,verified):
    _journey_need(isinstance(observation,dict) and observation.get("journey") == J09_SLOW_CASE and observation.get("contract") == J09_SLOW_CONTRACT
                  and observation.get("plan") in J09_SLOW_PHASES, "S4 missing versioned slow contract")
    verified.add("contract")
    _journey_need(tuple(p["name"] for p in observation["phases"]) == J09_SLOW_PHASES[observation["plan"]], "S4 missing/reordered complete single-capture phases")
    base = _j09_slow_base_view(observation);verified.add("base_range")
    result = journey_result(j09_checks(observation=base));_journey_need(result["ok"], "S4 original S1-S3 prefix failed: " + str(result["failures"][:1]))
    verified.add("base_s1_s3")
    _j09_slow_ttl(observation);verified.update(("effective_ttl120","runtime_provenance"))
    page = dict(observation["page"],frames=_j09_materialize_frames(observation["page"]))
    n = len(base["phases"]);phases = observation["phases"][n:];frames = page["frames"]
    base_phase = base["phases"][-1]
    previous = _j06_active(observation,page,base_phase,dict(base_phase,mode="refresh"),None)
    covered = set(range(observation["base_range"]["frame_end"]))
    targets = {f["decoded"]["new_session"]["script_run_id"] for f in frames[:observation["base_range"]["frame_end"]] if f["decoded"].get("type") == "new_session"}
    last_dom,last_end = previous["signature"],base_phase["observation_end_timestamp"]
    aged,natural,recovered = None,False,None
    for index,phase in enumerate(phases):
        name,action = phase["name"],phase["action"]
        _journey_need(all(action.get(k) == v for k,v in J09_SLOW_ACTIONS[name].items()) and action.get("ok") is True and not action.get("failed"), "S4 failed/unobserved/wrong explicit action")
        before,at,after,end = [phase[k] for k in ("read_start_timestamp","action_timestamp","read_end_timestamp","observation_end_timestamp")]
        start,stop = phase["start"],phase["end"]
        _journey_need(all(_j06_number(t) for t in (before,at,after,end)) and last_end < before <= at < after <= end
                      and type(start) is int and type(stop) is int and 0 <= start <= stop <= len(frames)
                      and start == sum(f["timestamp"] <= before for f in frames) and stop == sum(f["timestamp"] <= after for f in frames)
                      and not covered.intersection(range(start,stop)), "S4 action/read clocks or full frame cursors are invalid")
        covered.update(range(start,stop));selected = frames[start:stop]
        _journey_need(phase["start_timestamp"] == (selected[0]["timestamp"] if selected else None)
                      and phase["end_timestamp"] == (selected[-1]["timestamp"] if selected else None)
                      and _j09_slow_signature(phase["dom_before"]) == last_dom, "S4 stale DOM/timestamp or unrecorded transition")
        signature = _j09_slow_signature(phase["dom_after"])
        expected_epoch = "e2" if index < 3 else "e3"
        _journey_need(phase["epoch"] == expected_epoch and all(f["request_id"] == page["epochs"][2 if index < 3 else 3]["request_id"] for f in selected), "S4 crossed successful epoch")
        if index < 2:
            previous = _j06_active(observation,page,phase,dict(phase,mode="upload" if index == 0 else "pulse"),previous)
            _journey_need(phase["checkpoint"] == previous["checkpoint"] and previous["checkpoint"]["script_run_id"] not in targets, "S4 prep checkpoint/run reused")
            targets.add(previous["checkpoint"]["script_run_id"])
            if index == 1:
                aged = previous;verified.add("prep_state")
        elif index == 2:
            closed,clear,ws = _j09_slow_hold(observation,page,phase)
            _journey_need(all(_j09_quiet(f["decoded"]) for f in selected) and phase["ipc"] == {"table":None,"chart":None}
                          and phase["checkpoint"] == aged["checkpoint"], "S4 invented a run/result while disconnected")
            verified.update(("scoped_block_rule","actual_close","hold_135_real_seconds","no_101_during_hold"))
        elif index == 3:
            epoch,response_time = _j09_slow_epoch(observation,page,aged,closed,clear,ws)
            _journey_need(at <= clear["cdp_before"] <= clear["cdp_after"] <= after and after >= response_time, "S4 clear/actual recovery observation is outside its phase")
            natural = any(not _j09_quiet(f["decoded"]) for f in selected)
            if natural:recovered = _j09_slow_run(observation,page,phase,epoch)
            else:_journey_need(phase["ipc"] == {"table":None,"chart":None}, "S4 no-run reconnect invented fresh IPC")
            _journey_need(phase["checkpoint"] == (recovered["checkpoint"] if recovered else aged["checkpoint"]), "S4 HTTP101 was substituted for a verified run")
            verified.update(("retry_event_coverage","unblock_boundary","old_id_requested","same_document_cache"))
        else:
            actual = observation["recovery"]["recovery_action"]
            _journey_need(actual in J09_SLOW_RECOVERY_ACTIONS, "S4 missing actual observe/Rerun UI action")
            inputs = _j09_slow_post_close_inputs(observation,closed)
            if actual == "observe":
                _journey_need(not inputs, "S4 natural/observe concealed post-close Rerun input")
            else:
                _journey_need(len(inputs) == 2 and all(at <= observation["commands"][i]["cdp_before"] <= observation["commands"][i]["cdp_after"] <= after for i in inputs), "S4 Rerun input outside its single authorized recovery window")
            if natural:
                _journey_need(actual == "observe" and all(_j09_quiet(f["decoded"]) for f in selected)
                              and signature == last_dom and phase["ipc"] == {"table":None,"chart":None}, "S4 forced an extra rerun after natural completion")
            elif actual == "observe":
                recovered = _j09_slow_run(observation,page,phase,epoch)
            else:
                input_time = _j09_slow_rerun_input(observation,phase)
                _journey_need(all(_j09_quiet(f["decoded"]) for f in frames if f["request_id"] == epoch["request_id"] and f["timestamp"] < input_time), "S4 natural activity preceded actual Rerun dispatch")
                recovered = _j09_slow_run(observation,page,phase,epoch)
                _journey_need(recovered["client"] is not None and frames[recovered["client"]]["timestamp"] >= input_time, "S4 Rerun UI did not produce its new ClientState/run")
            _journey_need(recovered["session"] != aged["session"] and observation["recovery"]["requested_session_id"] == aged["session"]
                          and observation["recovery"]["observed_session_id"] == recovered["session"] and phase["checkpoint"] == recovered["checkpoint"]
                          and recovered["checkpoint"]["script_run_id"] not in targets, "S4 old session resumed or new ID/target run proof was forged")
            verified.update(("new_session_observed","actual_recovery_run"))
        _j09_slow_summary(page,phase);last_dom,last_end = signature,end
    _journey_need(all(i in covered or _j09_quiet(f["decoded"]) for i,f in enumerate(frames)), "S4 base range/tail windows hide business output")
    mutations = [h for h in page["http_timeline"] if h.get("method") in ("PUT","DELETE")]
    sent = [e for e in page["events"] if e.get("method") == "Network.requestWillBeSent" and e.get("params",{}).get("request",{}).get("method") in ("PUT","DELETE")]
    _journey_need(len(mutations) == len(sent) == 2 and all(h["method"] == "PUT" and h["status"] == 204 for h in mutations)
                  and all(h["response_timestamp"] <= phases[0]["read_end_timestamp"] for h in mutations), "S4 re-upload/DELETE occurred or HTTP evidence was omitted")
    for h in mutations:
        _j06_http_events(dict(http_timeline=[h],events=[e for e in page["events"] if e.get("params",{}).get("requestId") == h["request_id"]]))
    for f in frames[phases[1]["end"]:]:
        _journey_need(not any(s.get("value_field") == "trigger_value" and s.get("value") is True for s in f["decoded"].get("rerun_script",{}).get("widget_states",[])), "S4 extra Pulse/submit after prep")
    _journey_need(not any(c["method"] in ("Page.navigate","Page.reload") and c["cdp_before"] > observation["base_range"]["cutoff_timestamp"] for c in observation["commands"]), "S4 explicit F5/navigation bypassed expiry")
    verified.update(("single_capture","no_reupload_or_extra_actions"))
    _j09_slow_pngs(observation);verified.add("png_sources")
    _j09_slow_recovery_oracle(observation);verified.add("recovery_oracle_verified")


def _j09_slow_post_close_inputs(observation,closed):
    """Attribute raw input across the whole tail, not a chosen phase slice."""
    rerun,points = [],[]
    commands = sorted(enumerate(observation["commands"]),key=lambda pair:pair[1]["cdp_before"])
    for index,c in commands:
        if c["cdp_after"] < closed:continue
        if c["method"] == "Runtime.evaluate":
            expression = c["params"].get("expression","")
            item = "document.querySelector('[data-testid=stMainMenuItem-rerun]')" in expression
            menu = "[data-testid=stMainMenu]" in expression or "button[data-testid=stMainMenu]" in expression
            if not (item or menu):continue
            remote = _j09_slow_command(observation,index)["response"]["result"]
            _journey_need(set(remote) == {"result"}, "S4 post-close menu evaluation failed")
            value = remote["result"].get("value")
            if remote["result"].get("type") == "object" and isinstance(value,dict) and all(_j06_number(value.get(k)) for k in ("x","y")):
                points.append((c["cdp_after"],value,item))
        elif c["method"].startswith("Input."):
            c = _j09_slow_command(observation,index);p = c["params"]
            _journey_need(c["cdp_before"] >= closed, "S4 UI input straddled native close")
            if c["method"] == "Input.dispatchKeyEvent":
                _journey_need(p.get("key") == "r" and p.get("code") == "KeyR" and p.get("type") in ("rawKeyDown","keyUp") and not p.get("modifiers",0), "S4 unattributed post-close keyboard action")
                rerun.append(index)
            else:
                _journey_need(c["method"] == "Input.dispatchMouseEvent" and p.get("type") in ("mousePressed","mouseReleased") and p.get("button") == "left", "S4 unattributed post-close UI action")
                locations = [point for point in points if point[0] <= c["cdp_before"] and all(p.get(k) == point[1][k] for k in ("x","y"))]
                _journey_need(locations, "S4 post-close mouse input lacks actual menu geometry")
                if locations[-1][2]:rerun.append(index)
    return rerun


def _j09_slow_rerun_input(observation,phase):
    commands = [(i,c) for i,c in enumerate(observation["commands"])
                if phase["action_timestamp"] <= c["cdp_before"] <= c["cdp_after"] <= phase["read_end_timestamp"]]
    keys = [(i,c) for i,c in commands if c["method"] == "Input.dispatchKeyEvent"]
    if keys:
        _journey_need(len(keys) == 2, "S4 extra/missing Rerun key commands")
        down,up = [_j09_slow_command(observation,i) for i,c in keys]
        _journey_need(down["params"].get("type") == "rawKeyDown" and up["params"].get("type") == "keyUp"
                      and all(c["params"].get("key") == "r" and c["params"].get("code") == "KeyR" and not c["params"].get("modifiers",0) for c in (down,up))
                      and down["cdp_after"] <= up["cdp_before"], "S4 recovery input was not actual frontend Rerun")
        return down["cdp_before"]
    candidates = [(i,c) for i,c in commands if c["method"] == "Runtime.evaluate" and "document.querySelector('[data-testid=stMainMenuItem-rerun]')" in c["params"].get("expression","")]
    # click_visible first evaluates scrollIntoView (boolean), then reads the
    # post-scroll rectangle (object). Only that actual geometry locates input.
    probes = []
    for i,c in candidates:
        remote = _j09_slow_command(observation,i)["response"]["result"]
        _journey_need(set(remote) == {"result"}, "S4 menu evaluation failed")
        if remote["result"].get("type") == "object":probes.append((i,c))
        else:_journey_need(remote["result"].get("type") == "boolean" and remote["result"].get("value") is True, "S4 menu item was not actually visible")
    _journey_need(len(probes) == 1, "S4 no raw visible Rerun menu locator response")
    probe = _j09_slow_command(observation,probes[0][0]);remote = probe["response"]["result"]
    _journey_need(set(remote) == {"result"} and remote["result"].get("type") == "object" and type(remote["result"].get("value")) is dict, "S4 menu target evaluation failed")
    point = remote["result"]["value"]
    _journey_need(all(_j06_number(point.get(k)) for k in ("x","y")), "S4 menu locator has no actual point")
    clicks = [(i,c) for i,c in commands if c["method"] == "Input.dispatchMouseEvent" and c["cdp_before"] >= probe["cdp_after"]]
    _journey_need(len(clicks) == 2, "S4 missing/extra actual Rerun menu clicks")
    down,up = [_j09_slow_command(observation,i) for i,c in clicks]
    _journey_need([c["params"].get("type") for c in (down,up)] == ["mousePressed","mouseReleased"]
                  and all(c["params"].get("button") == "left" and c["params"].get("x") == point["x"] and c["params"].get("y") == point["y"] for c in (down,up))
                  and down["cdp_after"] <= up["cdp_before"], "S4 click did not target the actually located Rerun menu")
    return up["cdp_before"] # the menu click activates on mouse release


def _j09_slow_pngs(observation):
    records = observation["screenshots"];phases = observation["phases"];paths = set();root = pathlib.Path(observation["ipc_dir"]).resolve()
    _journey_need(len(records) == len(phases), "S4 missing full single-chain phase PNGs")
    for phase in phases:
        matches = [r for r in records if r.get("phase") == phase["name"]]
        _journey_need(len(matches) == 1, "S4 missing/duplicate PNG phase")
        r = matches[0];file = pathlib.Path(r["file"]);path = (root/file).resolve()
        _journey_need(r["namespace"] == observation["page"]["namespace"] and r["epoch"] == phase["epoch"] and r["step_ids"] == list(J09_SLOW_PNG_ROLES[phase["name"]])
                      and (r["step_ids"] or r.get("role") == "preparation") and not file.is_absolute() and ".." not in file.parts and path.is_relative_to(root) and path.is_file() and path not in paths, "S4 PNG source/role/path mismatch")
        data = path.read_bytes();stamp = r["timestamp"]
        _journey_need(data.startswith(b"\x89PNG\r\n\x1a\n") and hashlib.sha256(data).hexdigest() == r["sha256"] and _j06_number(stamp)
                      and phase["read_end_timestamp"] <= stamp <= phase["observation_end_timestamp"] and stamp-phase["read_end_timestamp"] <= STAGE2_SCREENSHOT_MAX_LAG_SECONDS, "S4 PNG hash/actual phase clock mismatch")
        paths.add(path)


SEQUENCE_CONTRACT = "journey-sequence-v1"
SEQUENCE_PHASES = {
    J00_CASE: J00_PHASES,
    J02_CASE: J02_PHASES,
    J03_CASE: J03_PHASES,
    J01_CASE: J01_PHASES,
    "j07-sequence": ("initial", "upload-malformed", "upload-soft", "good-after-soft", "upload-utf8", "good-after-utf8"),
    "j08-sequence": ("initial", "upload-header-only", "upload-baseline", "slider-200", "slider-0"),
}
SEQUENCE_INPUTS = {
    "upload-malformed": "sales_malformed.csv", "upload-soft": "sales_with_missing.csv",
    "good-after-soft": "sales_basic.csv", "upload-utf8": "sales_latin1.csv", "good-after-utf8": "sales_basic.csv",
    "upload-header-only": "sales_empty.csv", "upload-baseline": "sales_basic.csv",
}
_SEQUENCE_COMMON = ("contract", "phase_sequence", "fixture_inputs", "same_source_session", "no_reload_or_reconnect", "distinct_target_runs", "counter_continuity")
SEQUENCE_REQUIRED = {
    J00_CASE: J00_REQUIRED,
    J02_CASE: J02_REQUIRED,
    J03_CASE: J03_REQUIRED,
    J01_CASE: J01_REQUIRED,
    "j07-sequence": (*_SEQUENCE_COMMON, "malformed_error_no_result", "soft_warning_values", "recovery_after_soft", "utf8_error_no_result", "recovery_after_utf8", "png_phase_coverage"),
    "j08-sequence": (*_SEQUENCE_COMMON, "header_empty", "baseline_upload", "filter_empty", "slider200_once", "restore_values", "slider0_once", "png_phase_coverage"),
}
SEQUENCE_PNG_ROLES = {
    "initial": (), "upload-malformed": ("J07-S1",), "upload-soft": ("J07-S2",), "good-after-soft": ("J07-S3",),
    "upload-utf8": ("J07-S4",), "good-after-utf8": ("J07-S4",), "upload-header-only": ("J08-S1",),
    "upload-baseline": (), "slider-200": ("J08-S2",), "slider-0": ("J08-S3",),
}
JOURNEY_REQUIRED.update({kind: {(kind, key) for key in keys} for kind, keys in SEQUENCE_REQUIRED.items()})


def _j03_pointer(phase, minimum):
    """Observed single track click + ARIA/value snapshots, not just pointer.ok."""
    record = phase["action"].get("pointer")
    _journey_need(isinstance(record, dict) and record.get("ok") is True
                  and type(record.get("requested_value")) in (int, float) and record["requested_value"] == minimum, "missing/wrong actual slider pointer observation")
    for key, dom in (("before", phase["dom_before"]), ("after", phase["dom_after"])):
        snap = record.get(key)
        _journey_need(isinstance(snap, dict) and {"value", "min", "max", "step", "aria_value_now", "aria_value_text", "track", "viewport"} <= snap.keys(), "incomplete pointer/ARIA snapshot")
        _journey_need(all(_same_cell_value(want, snap[field]) for field,want in (("min", 0), ("max", 200), ("step", 10)))
                      and _same_cell_value(dom["slider_value"], snap["value"])
                      and _same_cell_value(snap["value"], snap["aria_value_text"])
                      and (snap["aria_value_now"] is None or _same_cell_value(snap["value"], snap["aria_value_now"])), "pointer/ARIA values contradict actual slider DOM")
    _journey_need(_same_cell_value(minimum, record["after"]["value"])
                  and not _same_cell_value(record["before"]["value"], record["after"]["value"]), "pointer did not change to the required slider value")
    point, track, viewport = record.get("pointer"), record["before"]["track"], record["before"]["viewport"]
    _journey_need(isinstance(point, dict) and point.get("method") == "single-track-click" and isinstance(track, dict)
                  and isinstance(viewport, list) and len(viewport) == 2
                  and all(type(v) in (int, float) and math.isfinite(v) and v > 0 for v in viewport), "missing real single-pointer geometry/viewport")
    _journey_need(all(type(track.get(k)) in (int, float) and math.isfinite(track[k]) for k in ("left", "right", "top", "bottom", "width", "height", "x", "y"))
                  and track["width"] > 0 and track["height"] > 0
                  and abs(track["right"]-track["left"]-track["width"]) <= 1e-6
                  and abs(track["bottom"]-track["top"]-track["height"]) <= 1e-6
                  and track["x"] == track["left"] and track["y"] == track["top"], "inconsistent pointer track geometry")
    x, y = point.get("x"), point.get("y")
    _journey_need(all(type(v) in (int, float) and math.isfinite(v) for v in (x,y))
                  and 0 <= x < viewport[0] and 0 <= y < viewport[1]
                  and track["left"] <= x < track["right"] and track["top"] <= y < track["bottom"], "pointer outside actual track/viewport")
    projected = 200 * (x-track["left"])/track["width"]
    _journey_need(abs(projected-minimum) <= 5 + 200/track["width"], "pointer coordinates do not target the observed slider value")


def _j03_phase(observation, phase, previous, before_runs):
    return _filter_control_phase(observation, phase, previous, before_runs, case=J03_CASE)


def _j02_phase(observation, phase, previous, before_runs):
    return _filter_control_phase(observation, phase, previous, before_runs, case=J02_CASE)


def _j02_schema(table):
    types = tuple(line.split(": ", 1)[1].removesuffix(" not null") for line in table["schema"].splitlines()[:4])
    _journey_need(table["columns"] == list(J02_COLUMNS) and types == J02_TYPES, "J02 nonempty schema/order/types mismatch")


def _filter_control_phase(observation, phase, previous, before_runs, *, case):
    """Closed J00/J02/J03 profiles reuse one real-file/control/data/run proof."""
    actions = {J00_CASE:J00_ACTIONS, J02_CASE:J02_ACTIONS, J03_CASE:J03_ACTIONS}[case]
    name = phase["name"]
    expected_rows = ([{"group_key":key,"row_count":count,"total_amount":float(total),"avg_amount":float(mean)}
                      for key,count,total,mean in (J00_EXPECTED_ROWS if case == J00_CASE else J02_EXPECTED_ROWS)[name]] if case in (J00_CASE, J02_CASE) else
                     None if name == "slider-200" else _j03_expected_rows(name))
    _journey_need(all(phase["action"].get(k) == v for k,v in actions[name].items()), "wrong filtering action/target")
    if name == "upload-baseline":
        context, proof, count = _sequence_upload(observation, phase, previous, before_runs)
        _journey_need(context["table"]["rows"] == expected_rows, "filtering baseline values mismatch")
        if case in (J00_CASE, J02_CASE):
            _j02_schema(context["table"])
        return context, proof, count
    _journey_need(previous is not None, "controls have no preceding upload")
    run = _stage2_phase_run(observation, phase)
    _journey_need(run["identity"] == previous["identity"] and run["session"] == previous["session"], "controls switched file source/session")
    if case == J00_CASE:
        minimum = 100 if name == "slider-100" else 0
        group = "region" if name in ("group-region", "prepare-region", "exclude-unknown") else "category"
        include_unknown = name != "exclude-unknown"
    elif case == J02_CASE:
        minimum = 100 if name in ("slider-100", "group-category") else 0
        group = "category" if name == "group-category" else "region"
        include_unknown = name == "group-region"
    else:
        minimum = actions[name]["value"] if actions[name]["action"] == "slider" else 0
        group = "region" if name in ("group-region", "slider-200") else "category"
        include_unknown = True
    state = observation["frames"][run["state_index"]]["decoded"]["rerun_script"]["widget_states"]
    ids = _stage2_typed_controls(run["deltas"], state, phase["dom_after"], minimum, group=group, include_unknown=include_unknown)
    if actions[name]["action"] == "slider":
        _journey_need(type(phase["action"].get("value")) in (int, float), "wrong slider target type")
        _j03_pointer(phase, minimum)
    elif actions[name]["action"] == "checkbox":
        record = phase["action"].get("checkbox")
        _journey_need(phase["action"].get("value") is False and isinstance(record, dict) and record.get("ok") is True
                      and record.get("requested_value") is False and record.get("before") is True and record.get("after") is False
                      and record.get("input_method") == "Space" and phase["dom_before"].get("checkbox_checked") is True,
                      "missing/contradictory actual checkbox uncheck observation")
    view = dict(observation, phases=observation["phases"][1:], uploads={"bad": observation["uploads"]["upload-baseline"]})
    bundle = _journey_bundle(view, phase_index=0)
    uploader = bundle["window"]["widget"]
    elements = [d for d in run["deltas"] if d.get("element") == "file_uploader" and d.get("label") == "Upload sales CSV"]
    values = [v for v in state if v.get("id") == uploader]
    _journey_need(len(elements) == 1 and elements[0].get("id") == uploader and len(values) == 1
                  and values[0].get("value_field") == "file_uploader_state_value"
                  and values[0].get("value_full", {}).get("uploadedFileInfo") == [previous["info"]], "control changed/lost the actual uploaded file")
    _journey_need(not any(h.get("method") in ("PUT", "DELETE") for h in _journey_http(bundle, phase)), "ordinary control uploaded/deleted a file")
    count = before_runs+1
    _stage2_specific_counters(run["deltas"], phase["dom_after"], count)
    tables = [d for d in run["deltas"] if d.get("element") == "dataframe"]
    charts = [d for d in run["deltas"] if d.get("element") == "vega_lite_chart"]
    _journey_need(len(tables) == 1, "target run has no unique fresh dataframe")
    table = _journey_ipc(tables[0].get("arrow"), bundle)
    if case in (J00_CASE, J02_CASE):
        _j02_schema(table)
    if case == J03_CASE and name == "slider-200":
        _filtered_empty_view(table, charts, phase["dom_after"], run["deltas"])
    else:
        _stage2_static_view(observation, phase, run, expected_rows=expected_rows)
        kind = {"slider":"slider", "select-option":"selectbox", "checkbox":"checkbox"}[actions[name]["action"]]
        window = {"start":phase["start"],"end":phase["end"],"target":observation["namespace"],"widget":ids[kind]}
        verdict = data_loop_verdict({"kind":kind,"label":actions[name]["label"]}, bundle["frames"], window,
                                   {"action":"select" if kind == "selectbox" else kind,"ok":True}, phase["dom_before"], phase["dom_after"])
        _journey_need(verdict["ok"], "; ".join(verdict["problems"]))
        _stage2_specific_alerts(run["deltas"], phase["dom_after"], [])
    context = dict(previous, table=table)
    return context, {"script_run_id":run["run"],"completion_frame":run["finish_index"]}, count


def _j03_expected_rows(name):
    rows = {
        "upload-baseline":J01_EXPECTED_ROWS["upload-baseline"],
        "slider-100":(("Books",1,"120.50","120.50"),("Games",2,"349.49","174.75")),
        "prepare-slider-zero":J01_EXPECTED_ROWS["upload-baseline"],
        "group-region":J01_EXPECTED_ROWS["group-region"],
    }[name]
    return [{"group_key":key,"row_count":count,"total_amount":float(total),"avg_amount":float(mean)} for key,count,total,mean in rows]


def _j01_bom_binding(bundle, proof):
    """Bind BOM transport without invoking the legacy must-change result check.

    Result equivalence is validated separately against fresh target-run IPC.
    This uses the existing run binder, issued-URL validator and HTTP reader.
    """
    frames, window = bundle["frames"], bundle["window"]
    state_frame = frames[proof["state_frame"]]
    states = state_frame["decoded"]["rerun_script"]["widget_states"]
    uploaders = [v for v in states if v.get("id") == window["widget"]]
    _journey_need(len(uploaders) == 1 and uploaders[0].get("value_field") == "file_uploader_state_value", "BOM has no unique typed uploader state")
    infos = uploaders[0].get("value_full", {}).get("uploadedFileInfo")
    _journey_need(isinstance(infos, list) and len(infos) == 1, "BOM must name exactly one new file")
    info = infos[0]
    _journey_need(info.get("name") == "sales_utf8_bom.csv" and int(info.get("size", -1)) == J01_FILE_FINGERPRINTS["sales_utf8_bom.csv"][0]
                  and isinstance(info.get("fileId"), str) and info["fileId"], "wrong BOM file identity/size")
    session = frames[proof["run_start_frame"]]["decoded"]["new_session"]["session_id"]
    file_id = info["fileId"]
    before = frames[window["start"]:proof["state_frame"]]
    requests = [(i, f["decoded"]["file_urls_request"]) for i,f in enumerate(before) if f.get("direction") == "client->server" and f.get("decoded", {}).get("type") == "file_urls_request"]
    _journey_need(len(requests) == 1, "missing/ambiguous BOM issued URL request")
    request_index, request = requests[0]
    _journey_need(request.get("session_id") == session and request.get("file_names") == ["sales_utf8_bom.csv"]
                  and request.get("request_id"), "BOM issued URL request does not belong to this input/session")
    responses = [f["decoded"]["file_urls_response"] for f in before[request_index+1:] if f.get("direction") == "server->client" and f.get("decoded", {}).get("type") == "file_urls_response"]
    issued = [u for r in responses if r.get("response_id") == request["request_id"] and not r.get("error_msg")
              for u in r.get("file_urls", []) if u.get("file_id") == file_id]
    _journey_need(len(issued) == 1, "no unique issued BOM file URL")
    urls = info.get("fileUrls") or {}
    _journey_need(urls.get("fileId") == file_id and urls.get("uploadUrl") == issued[0].get("upload_url")
                  and urls.get("deleteUrl") == issued[0].get("delete_url"), "BOM ClientState URLs differ from issued URLs")
    upload_url = _journey_url(bundle["url"], issued[0].get("upload_url"), session, file_id)
    delete_url = _journey_url(bundle["url"], issued[0].get("delete_url"), session, file_id)
    _journey_need(any(h.get("method") == "PUT" and h.get("url") == upload_url and h.get("status") == 204
                      and "multipart/form-data" in str(h.get("request_headers", {})).lower() for h in _journey_http(bundle, window)), "no matching actual BOM multipart PUT204")
    return {"ok": True, "problems": [], "identity": (bundle["source"], state_frame.get("request_id"), state_frame.get("connection")),
            "session": session, "file_id": file_id, "delete_url": delete_url, "info": info}


def _j01_phase(observation, phase, previous, before_runs):
    name = phase["name"]
    upload = name in J01_INPUTS
    expected_action = J01_ACTIONS[name]
    _journey_need(all(phase["action"].get(k) == v for k,v in expected_action.items()), "wrong J01 phase action/target")
    prefix = observation["phases"][1:observation["phases"].index(phase)+1]
    latest_upload = next(p for p in reversed(prefix) if p["name"] in J01_INPUTS)
    filename = J01_INPUTS[latest_upload["name"]]
    path = REPO_ROOT / "tests/fixtures/csv" / filename
    data = path.read_bytes()
    expected_size, expected_sha = J01_FILE_FINGERPRINTS[filename]
    _journey_need((len(data), hashlib.sha256(data).hexdigest()) == (expected_size, expected_sha), "J01 fixture bytes differ from frozen original")
    if upload:
        _journey_need(pathlib.Path(phase["action"]["file"]).resolve() == path.resolve()
                      and (phase["action"].get("file_bytes"), phase["action"].get("file_sha256")) == (expected_size, expected_sha), "J01 actual upload fingerprint/path mismatch")
    upload_ok = observation["uploads"][latest_upload["name"]]
    view = dict(observation, phases=prefix, uploads={"bad": upload_ok, "good": upload_ok})
    bundle = _journey_bundle(view, phase_index=len(prefix)-1)
    group = expected_action["option"] if not upload else "category"
    if not upload:
        # The new producer records action.ok, not the old derived 'changed'
        # boolean. Derive the operation from actual before/target values.
        changed = phase["dom_before"].get("selectbox_value") != group and phase["dom_after"].get("selectbox_value") == group
        bundle["action"] = {"action": "select", "ok": phase["action"].get("ok") is True and changed}
    proof = _journey_run_verdict(bundle["frames"], bundle["window"], bundle["action"], filename, group)
    _journey_need(proof["ok"], "; ".join(proof["problems"]))
    if name == "upload-bom":
        context = _j01_bom_binding(bundle, proof)
    else:
        context = _journey_context(bundle, filename, group, phase["dom_after"])
        _journey_need(context["ok"], "; ".join(context["problems"]))
    state, deltas = _stage2_run_parts(observation, phase, proof)
    _stage2_typed_controls(deltas, state, phase["dom_after"], group=group)
    uploader_elements = [d for d in deltas if d.get("element") == "file_uploader" and d.get("label") == "Upload sales CSV"]
    _journey_need(len(uploader_elements) == 1 and uploader_elements[0].get("id"), "J01 missing unique actual uploader Element")
    uploader_states = [v for v in state if v.get("id") == uploader_elements[0]["id"]]
    _journey_need(len(uploader_states) == 1 and uploader_states[0].get("value_field") == "file_uploader_state_value"
                  and uploader_states[0].get("value_full", {}).get("uploadedFileInfo") == [context["info"]], "J01 file state does not match this server widget/input")
    selected = observation["frames"][phase["start"]:phase["end"]]
    markers = [f for f in selected if f.get("decoded", {}).get("type") == "new_session"]
    if upload:
        target = _stage2_target_upload_run(observation["frames"], namespace=observation["namespace"], start=phase["start"], end=phase["end"],
            widget_id=bundle["window"]["widget"], file_id=context["file_id"], file_name=filename)
        _journey_need(target["ok"] and target["state_frame"] == proof["state_frame"], "J01 upload is not the newly issued target")
        if len(markers) == 2:
            _journey_need(previous is not None, "J01 clear run before any upload")
            _stage2_specific_clear_chain(observation, phase, proof, context, bundle, before_runs=before_runs)
        else:
            _journey_need(len(markers) == 1 and _stage2_phase_run(observation, phase)["run"] == proof["script_run_id"], "J01 unbound upload runs")
        if previous is not None:
            _journey_need(context["file_id"] != previous["file_id"], "J01 replacement reused old file ID")
            _journey_need(len([h for h in _journey_http(bundle, phase) if h.get("method") == "DELETE" and h.get("url") == previous["delete_url"] and h.get("status") == 204]) == 1, "J01 replacement lacks preceding-issued-file DELETE204")
        _journey_need(not any(h.get("method") == "DELETE" and h.get("url") == context["delete_url"] for h in _journey_http(bundle, phase)), "J01 new target was deleted")
    else:
        _journey_need(previous is not None and context["info"] == previous["info"] and len(markers) == 1
                      and _stage2_phase_run(observation, phase)["run"] == proof["script_run_id"], "J01 selector changed file or emitted multiple runs")
        _journey_need(not any(h.get("method") in ("PUT", "DELETE") for h in _journey_http(bundle, phase)), "J01 selector unexpectedly uploaded/deleted a file")
    _journey_need(previous is None or context["identity"] == previous["identity"] and context["session"] == previous["session"], "J01 source/session switched")
    count = before_runs + len(markers)
    _stage2_specific_counters(deltas, phase["dom_after"], count)
    _stage2_specific_alerts(deltas, phase["dom_after"], [])
    expected = [{"group_key":key,"row_count":rows,"total_amount":float(total),"avg_amount":float(mean)}
                for key,rows,total,mean in J01_EXPECTED_ROWS[name]]
    chart = [d for d in deltas if d.get("element") == "vega_lite_chart"]
    _journey_need(len(chart) == 1, "J01 has no unique fresh chart")
    spec = chart[0].get("vega_lite_spec") or {}
    if name == "upload-bom":
        _journey_need(previous is not None and previous["info"]["name"] == "sales_unicode.csv", "BOM lacks preceding Unicode upload")
        logical = _stage2_static_view(observation, phase, {"deltas":deltas}, expected_rows=expected)
        tables = [d for d in deltas if d.get("element") == "dataframe"]
        context["table"] = _journey_ipc(tables[0]["arrow"], bundle)
        _journey_need(logical["rows"] == previous["table"]["rows"] and logical["encoding"] == previous["chart_semantics"]["encoding"]
                      and logical["mark"] == previous["chart_semantics"]["mark"], "BOM changed logical Unicode data/chart")
    _journey_need(context["table"]["rows"] == expected and context["table"]["row_count"] == len(expected), "J01 full original values/order mismatch")
    context["chart_semantics"] = {"encoding":spec.get("encoding"),"mark":spec.get("mark")}
    return context, proof, count


def _sequence_upload(observation, phase, previous, before_runs):
    filename = SEQUENCE_INPUTS[phase["name"]]
    if filename in ("sales_empty.csv", "sales_malformed.csv"):
        expected = {"sales_empty.csv": (62, "0051f910f9780491c0ba47fe149f3bed4d8ce13b3106d73639227da51bd76bd4"),
                    "sales_malformed.csv": (303, "fbf671b3f566ff3bd62a39ceea76d40cc39b9bddb9565bde683953dcca0a89d5")}[filename]
        path = REPO_ROOT / "tests/fixtures/csv" / filename
        action, data = phase["action"], path.read_bytes()
        _journey_need(action.get("action") == "upload" and pathlib.Path(action["file"]).resolve() == path.resolve()
                      and (len(data), hashlib.sha256(data).hexdigest()) == expected
                      and (action.get("file_bytes"), action.get("file_sha256")) == expected, "wrong sequence fixture fingerprint")
    else:
        _stage2_specific_input(phase, filename)
    view = dict(observation, phases=[phase], uploads={"good": observation["uploads"][phase["name"]]})
    bundle = _journey_bundle(view)
    context = _journey_context(bundle, filename, "category", phase["dom_after"],
                               no_result=filename in ("sales_malformed.csv", "sales_latin1.csv"), empty=filename == "sales_empty.csv")
    _journey_need(context["ok"], "; ".join(context["problems"]))
    proof = _stage2_target_upload_run(observation["frames"], namespace=observation["namespace"], start=phase["start"], end=phase["end"],
        widget_id=bundle["window"]["widget"], file_id=context["file_id"], file_name=filename)
    _journey_need(proof["ok"], "; ".join(proof["problems"]))
    state, deltas = _stage2_run_parts(observation, phase, proof)
    _stage2_typed_controls(deltas, state, phase["dom_after"])
    selected = observation["frames"][phase["start"]:phase["end"]]
    markers = [f for f in selected if f.get("decoded", {}).get("type") == "new_session"]
    if len(markers) == 2:
        _journey_need(previous is not None, "clear run precedes any selected file")
        _stage2_specific_clear_chain(observation, phase, proof, context, bundle, before_runs=before_runs)
    else:
        _journey_need(len(markers) == 1, "unbound additional upload runs")
        one = _stage2_phase_run(observation, phase)
        _journey_need(one["run"] == proof["script_run_id"], "upload completion belongs to another run")
    count = before_runs + len(markers)
    _stage2_specific_counters(deltas, phase["dom_after"], count)
    if previous is not None:
        _journey_need(context["file_id"] != previous["file_id"], "replacement reused the preceding file ID")
        deletion = [h for h in _journey_http(bundle, phase) if h.get("method") == "DELETE" and h.get("status") == 204 and h.get("url") == previous["delete_url"]]
        _journey_need(len(deletion) == 1, "no unique preceding-issued-file DELETE204 in this sequence transition")
    _journey_need(not any(h.get("method") == "DELETE" and h.get("url") == context["delete_url"] for h in _journey_http(bundle, phase)), "sequence deleted its new target file")
    _sequence_output(filename, deltas, phase["dom_after"], context)
    return context, proof, count


def _sequence_output(filename, deltas, dom, context):
    if filename == "sales_malformed.csv":
        errors = [d.get("alert", {}).get("body") for d in deltas if d.get("element") == "alert" and d.get("alert", {}).get("format") == "ERROR"]
        _journey_need(errors == ["Could not parse the uploaded CSV: row 3: expected 8 fields, found 7"], "malformed fixture error must identify row 3, expected 8 fields, found 7 exactly")
        _stage2_specific_alerts(deltas, dom, [("ERROR", errors[0]), ("INFO", "Upload a valid CSV to continue.")])
    elif filename == "sales_latin1.csv":
        prefix = "Could not parse the uploaded CSV: the uploaded file is not valid UTF-8"
        errors = [d.get("alert", {}).get("body") for d in deltas if d.get("element") == "alert" and d.get("alert", {}).get("format") == "ERROR"]
        _journey_need(len(errors) == 1 and errors[0] in (prefix, prefix + ": 'utf-8' codec can't decode byte 0xe9 in position 101: invalid continuation byte"), "wrong sequence non-UTF8 error")
        _stage2_specific_alerts(deltas, dom, [("ERROR", errors[0]), ("INFO", "Upload a valid CSV to continue.")])
    elif filename == "sales_with_missing.csv":
        _stage2_specific_alerts(deltas, dom, [("WARNING", "2 row(s) with an unusable 'amount' were excluded from the aggregation.")])
        _journey_need(context["table"]["row_count"] == 4 and sum(v["row_count"] for v in context["table"]["rows"]) == 10, "wrong sequence soft values")
    elif filename == "sales_empty.csv":
        _stage2_specific_alerts(deltas, dom, [("INFO", "The uploaded CSV contains no data rows.")])
    else:
        _stage2_specific_alerts(deltas, dom, [])


def _j00_forms(observation):
    """Re-decode the retained form frames with the existing canonical helper.

    The collector retains raw protobuf for form registrations and ClientState;
    other deltas continue through the reviewed journey decoder/Arrow checks.
    """
    import importlib.util

    spec = importlib.util.spec_from_file_location("j00_forms_contract", REPO_ROOT / "tests/browser/forms_contract.py")
    canonical = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(canonical)
    expected_dom = {
        "text_inputs": [{"label":"Note", "value":"", "form_index":0}],
        "buttons": [{"label":"Pulse", "testid":"stButton", "form_index":-1},
                    {"label":"Apply note", "testid":"stFormSubmitButton", "form_index":0}],
        "forms": [{"index":0, "text_inputs":[{"label":"Note", "value":"", "form_index":0}],
                   "submit_buttons":[{"label":"Apply note", "testid":"stFormSubmitButton", "form_index":0}]}],
    }
    baseline = None
    for number, phase in enumerate(observation["phases"]):
        for dom in ([phase["dom_before"], phase["dom_after"]] if number else [phase["dom_after"]]):
            _journey_need(dom.get("form_membership") == expected_dom and dom.get("applied_note") == "",
                          "J00 Note/form DOM missing, edited, submitted or incorrectly associated")
            _journey_need(dom.get("has_uploader") is True and dom.get("has_button") is True
                          and dom.get("button_labels") == ["Pulse"], "J00 missing/extra initial external controls")
        deltas = [f["decoded"]["delta"] for f in observation["frames"][phase["start"]:phase["end"]]
                  if f.get("decoded", {}).get("type") == "delta"]
        for kind, label in (("file_uploader","Upload sales CSV"), ("selectbox","Group by"),
                            ("slider","Minimum amount"), ("checkbox","Include unknown region")):
            controls = [d for d in deltas if d.get("element") == kind and d.get("label") == label]
            _journey_need(len(controls) == 1 and controls[0].get("id")
                          and not controls[0].get("form_id") and not controls[0].get("widget", {}).get("disabled"),
                          "J00 missing/disabled/form-bound external control: " + label)
        registrations, blocks, clients = {}, [], []
        for frame in observation["frames"][phase["start"]:phase["end"]]:
            decoded = frame.get("decoded", {})
            delta = decoded.get("delta", {})
            is_client = decoded.get("type") == "rerun_script"
            is_form = (delta.get("block_type") == "form" or delta.get("element") == "text_input"
                       or delta.get("element") == "button" or "form_blocks" in frame)
            if not (is_client or is_form or "base64" in frame and frame.get("direction") == "server->client"):
                continue
            # The shared collector records [] for a non-form Element; the
            # forms-only recorder omits that empty cache. Normalize in memory.
            raw_frame = {k:v for k,v in frame.items() if k != "form_blocks" or v != []}
            problems, full = canonical._validate_frame(raw_frame, J00_CASE, phase["name"])
            _journey_need(not problems and full is not None, "J00 canonical form/state protobuf invalid: " + str(problems))
            payload = base64.b64decode(frame["base64"], validate=True)
            if is_client:
                _journey_need(summarise_back(payload).get("rerun_script") == decoded.get("rerun_script"),
                              "J00 typed ClientState differs from retained protobuf")
                clients.append((full.get("rerun_script", {}).get("widget_states", {}).get("widgets", []),
                                decoded["rerun_script"].get("widget_states")))
                continue
            _journey_need(summarise_forward(payload).get("delta") == delta, "J00 form Element/Block differs from retained protobuf")
            _journey_need(frame.get("official_forward") == full, "J00 official form sidecache differs from retained protobuf")
            raw_delta = full.get("delta", {})
            path = full.get("metadata", {}).get("delta_path")
            forms = canonical._form_blocks_from_forward(full)
            if forms:
                _journey_need(delta.get("block_type") == "form", "J00 form Block missing from decoded stream")
                blocks.append((forms[0], path))
            for kind, widget in raw_delta.get("new_element", {}).items():
                if kind not in ("text_input", "button"):
                    continue
                role = (kind, widget.get("label"))
                _journey_need(role in (("text_input","Note"), ("button","Apply note"), ("button","Pulse"))
                              and role not in registrations and widget.get("id") and delta.get("element") == kind
                              and delta.get("id") == widget["id"] and delta.get("label") == widget["label"]
                              and delta.get("form_id") == widget.get("form_id", ""), "J00 missing/ambiguous/misattributed form Element")
                registrations[role] = (widget, path)
        _journey_need(len(blocks) == 1 and blocks[0][0] == {"form_id":"apply_form", "border":True,
                      "enter_to_submit":True, "clear_on_submit":False}, "J00 missing/wrong actual apply_form Block")
        block_path = blocks[0][1]
        _journey_need(isinstance(block_path, list) and block_path and all(type(v) is int and v >= 0 for v in block_path)
                      and len(registrations) == 3, "J00 missing actual form path or Note/Apply/Pulse")
        note, note_path = registrations[("text_input","Note")]
        apply, apply_path = registrations[("button","Apply note")]
        pulse, pulse_path = registrations[("button","Pulse")]
        _journey_need(note.get("default") == "" and note.get("form_id") == "apply_form"
                      and apply.get("form_id") == "apply_form" and apply.get("is_form_submitter") is True
                      and not pulse.get("form_id") and not pulse.get("is_form_submitter")
                      and note_path == block_path+[0] and apply_path == block_path+[1]
                      and isinstance(pulse_path, list) and pulse_path[:len(block_path)] != block_path
                      and len({note["id"], apply["id"], pulse["id"]}) == 3
                      and all(not v.get("disabled") for v in (note,apply,pulse)), "J00 Note/Apply membership/default/path or external Pulse is incorrect")
        stable = (note, apply, pulse)
        if baseline is None:
            baseline = stable
        _journey_need(stable == baseline and len(clients) == 1, "J00 form widgets changed identity/defaults or extra ClientState")
        raw_states, states = clients[0]
        _journey_need(isinstance(states, list) and len({s["id"] for s in states}) == len(states)
                      and len({s["id"] for s in raw_states}) == len(raw_states), "J00 missing/duplicate typed ClientState")
        if not number:
            _journey_need(raw_states == [] and states == [], "J00 initial Note already has input")
        else:
            _journey_need([s for s in raw_states if s.get("id") == note["id"]] == [{"id":note["id"], "string_value":""}]
                          and [s for s in states if s.get("id") == note["id"]] == [{"id":note["id"], "value_field":"string_value", "value":""}],
                          "J00 Note was entered, missing or has a wrong typed state")
        _journey_need(not any(s.get("id") in (apply["id"],pulse["id"]) or s.get("trigger_value") is True for s in raw_states)
                      and not any(s.get("id") in (apply["id"],pulse["id"]) or s.get("value_field") == "trigger_value" and s.get("value") is True for s in states),
                      "J00 Apply/Pulse was triggered; applied_note alone is insufficient")


def _sequence_pngs(observation):
    records, phases = observation.get("screenshots"), observation["phases"]
    _journey_need(isinstance(records, list) and len(records) == len(phases), "missing/extra sequence phase pictures")
    files = set()
    for index, phase in enumerate(phases):
        candidates = [r for r in records if r.get("phase") == phase["name"] and r.get("namespace") == observation["namespace"]]
        _journey_need(len(candidates) == 1, "missing/ambiguous phase PNG")
        record = candidates[0]
        roles = J00_PNG_ROLES if observation["journey"] == J00_CASE else J02_PNG_ROLES if observation["journey"] == J02_CASE else J03_PNG_ROLES if observation["journey"] == J03_CASE else J01_PNG_ROLES if observation["journey"] == J01_CASE else SEQUENCE_PNG_ROLES
        _journey_need(record.get("step_ids") == list(roles[phase["name"]]), "phase PNG has wrong original-step role")
        if not record["step_ids"]:
            _journey_need(record.get("role") == "preparation", "preparation picture is not honestly identified")
        _journey_need(record.get("file") not in files, "one PNG file reused across sequence phases")
        files.add(_png_phase_record(observation, observation, index, record))


def sequence_checks(*, observation=None):
    """One continuous capture, never concatenated leaf observations."""
    kind = observation.get("journey") if isinstance(observation, dict) else None
    if not isinstance(kind, str) or kind not in SEQUENCE_REQUIRED:
        return [dict(_check("sequence", "contract", "known complete sequence", "missing/unknown sequence", False), journey="sequence-invalid")]
    try:
        contract = J00_CONTRACT if kind == J00_CASE else J02_CONTRACT if kind == J02_CASE else J03_CONTRACT if kind == J03_CASE else J01_CONTRACT if kind == J01_CASE else SEQUENCE_CONTRACT
        _journey_need(observation.get("contract") == contract, "wrong sequence contract")
        phases, frames = observation["phases"], observation["frames"]
        _journey_need(isinstance(phases, list) and tuple(p.get("name") for p in phases) == SEQUENCE_PHASES[kind], "missing/reordered/duplicated sequence phases")
        if "phase_ids" in observation:
            _journey_need(tuple(observation["phase_ids"]) == SEQUENCE_PHASES[kind], "published phase IDs contradict actual phase roles")
        _journey_need(isinstance(frames, list) and frames, "missing global frame stream")
        stamps = [f.get("timestamp") for f in frames]
        _journey_need(all(type(t) in (int, float) and math.isfinite(t) for t in stamps) and stamps == sorted(stamps), "global frame clock is missing/out of order")
        _journey_need(all(type(f["decoded"]["script_finished"].get("status")) is int for f in frames
                          if f.get("decoded", {}).get("type") == "script_finished"), "invalid sequence completion status type")
        source = observation["namespace"]
        identities = {(f.get("namespace"), f.get("connection"), f.get("request_id")) for f in frames}
        _journey_need(len(identities) == 1 and isinstance(source, str) and source and next(iter(identities))[0] == source
                      and next(iter(identities))[1] is not None and next(iter(identities))[2], "sequence switched namespace/connection/requestId")
        markers = [f["decoded"]["new_session"] for f in frames if f.get("decoded", {}).get("type") == "new_session"]
        _journey_need(markers and all(isinstance(m.get("session_id"), str) and m["session_id"] and isinstance(m.get("script_run_id"), str)
                                     and m["script_run_id"] for m in markers)
                      and len({m["session_id"] for m in markers}) == 1 and len({m["script_run_id"] for m in markers}) == len(markers), "sequence reset session or reused/missed run IDs")
        session = markers[0]["session_id"]
        covered = set()
        for index, phase in enumerate(phases):
            start, end = phase["start"], phase["end"]
            _journey_need(type(start) is int and type(end) is int and 0 <= start < end <= len(frames)
                          and (index == 0 or phases[index-1]["end"] <= start), "sequence windows overlap/reorder or are not global indices")
            _journey_need(phase["action"].get("ok") is True and not phase["action"].get("failed"), "sequence action failed/unobserved")
            covered.update(range(start, end))
            if index:
                _journey_need(phases[index-1]["end_timestamp"] < phase["start_timestamp"], "sequence clock goes backwards")
                for key in ("script_runs", "pulses", "table_present", "table_cells", "chart_present", "chart_bars", "alerts", "selectbox_value", "slider_value", "checkbox_checked"):
                    _journey_need(key in phase["dom_before"] and key in phases[index-1]["dom_after"]
                                  and phase["dom_before"][key] == phases[index-1]["dom_after"][key], "sequence DOM continuity mismatch: " + key)
        business = ("rerun_script", "new_session", "script_finished", "delta", "file_urls_request", "file_urls_response")
        _journey_need(all(i in covered for i,f in enumerate(frames) if f.get("decoded", {}).get("type") in business), "unobserved run/state/result between sequence phases")
        initial = phases[0]
        _journey_need(initial["action"].get("action") == "initial", "missing initial action")
        initial_run = _stage2_phase_run(observation, initial)
        initial_state = frames[initial_run["state_index"]]["decoded"]["rerun_script"].get("widget_states")
        _journey_need(initial_state == [] and initial_run["session"] == session, "sequence did not start from a fresh empty ClientState")
        initial_completions = [{"frame":i,"connection":f.get("connection"),"request_id":f.get("request_id"),
                                "status":f["decoded"]["script_finished"].get("status"),"status_name":f["decoded"]["script_finished"].get("status_name")}
                               for i,f in enumerate(frames[initial["start"]:initial["end"]]) if f.get("decoded", {}).get("type") == "script_finished"]
        _journey_need(initial.get("client_states") == [] and initial.get("completions") == initial_completions
                      and initial.get("ipc") == {"table":None,"chart":None}, "initial summaries contradict actual frames")
        _stage2_specific_counters(initial_run["deltas"], initial["dom_after"], 1)
        _stage2_specific_alerts(initial_run["deltas"], initial["dom_after"], [("INFO", "Upload a CSV to see the aggregated result.")])
        for element, label, expected in (("selectbox", "Group by", 0), ("slider", "Minimum amount", [0.0]), ("checkbox", "Include unknown region", True)):
            controls = [d for d in initial_run["deltas"] if d.get("element") == element and d.get("label") == label]
            _journey_need(len(controls) == 1 and controls[0].get("id") and isinstance(controls[0].get("widget"), dict)
                          and controls[0]["widget"].get("id") == controls[0]["id"] and controls[0]["widget"].get("label") == label,
                          "missing/ambiguous initial source Element: " + label)
            value = controls[0]["widget"].get("default")
            _journey_need((type(value) is int and value == expected) if element == "selectbox" else
                          (isinstance(value, list) and len(value) == 1 and type(value[0]) in (int, float) and value == expected) if element == "slider" else value is True,
                          "initial wire default contradicts required controls: " + label)
            if element == "selectbox":
                _journey_need(controls[0]["widget"].get("options") == ["category", "region", "channel"], "initial selector options/order mismatch")
        _journey_need(initial["dom_after"].get("table_present") is False and initial["dom_after"].get("table_cells") == []
                      and initial["dom_after"].get("chart_present") is False and initial["dom_after"].get("chart_bars") == 0
                      and initial["dom_after"].get("selectbox_value") == "category" and _same_cell_value(0, initial["dom_after"].get("slider_value"))
                      and initial["dom_after"].get("checkbox_checked") is True
                      and not any(d.get("element") in ("dataframe", "table", "vega_lite_chart") for d in initial_run["deltas"]), "initial phase already has a result")
        count, previous, targets, files = 1, None, {initial_run["run"]}, set()
        baseline_runs = None
        for phase in phases[1:]:
            if kind in (J00_CASE, J02_CASE, J03_CASE):
                if kind == J00_CASE:
                    context, proof, count = _filter_control_phase(observation, phase, previous, count, case=J00_CASE)
                else:
                    validator = _j02_phase if kind == J02_CASE else _j03_phase
                    context, proof, count = validator(observation, phase, previous, count)
                _journey_need(context["session"] == session, "J03 session changed")
                if phase["name"] in J03_INPUTS:
                    _journey_need(context["file_id"] not in files, "J03 recycled an earlier file ID")
                    files.add(context["file_id"])
                previous = context
                target, finish = proof["script_run_id"], proof["completion_frame"]
            elif kind == J01_CASE:
                context, proof, count = _j01_phase(observation, phase, previous, count)
                _journey_need(context["session"] == session, "J01 session changed")
                if phase["name"] in J01_INPUTS:
                    _journey_need(context["file_id"] not in files, "J01 recycled an earlier file ID")
                    files.add(context["file_id"])
                previous = context
                target, finish = proof["script_run_id"], proof["completion_frame"]
            elif phase["name"] in SEQUENCE_INPUTS:
                context, proof, count = _sequence_upload(observation, phase, previous, count)
                _journey_need(context["session"] == session and context["file_id"] not in files, "sequence switched session or recycled an old issued file ID")
                files.add(context["file_id"]);previous = context
                target, finish = proof["script_run_id"], proof["completion_frame"]
                if phase["name"] == "upload-baseline":baseline_runs = count
            else:
                run = _stage2_phase_run(observation, phase)
                _journey_need(run["session"] == session, "filter session reset")
                count += 1
                _stage2_specific_counters(run["deltas"], phase["dom_after"], count)
                target, finish = run["run"], run["finish_index"]
            _journey_need(target not in targets and frames[finish]["decoded"]["script_finished"].get("status") == 0, "target reused a run or did not terminate successfully")
            targets.add(target)
            _journey_need(not any(f.get("decoded", {}).get("type") in ("delta", "rerun_script", "new_session") for f in frames[finish+1:phase["end"]]), "phase result/state belongs to a run after target completion")
        if kind == "j08-sequence":
            view = dict(observation, phases=phases[2:], uploads={"file": observation["uploads"]["upload-baseline"]})
            _stage2_filtered_evidence(view, _journey_bundle(view, phase_index=0), baseline_runs=baseline_runs)
        if kind == J00_CASE:
            _j00_forms(observation)
        _sequence_pngs(observation)
    except (ValueError, TypeError, KeyError, IndexError, OSError, AttributeError) as exc:
        actual, ok = str(exc), False
    else:
        actual, ok = "continuous original frames, actual counters and per-phase evidence verified", True
    return _journey_finish(kind, [_check(kind, key, "complete same-page sequence proof", actual, ok) for key in SEQUENCE_REQUIRED[kind]])


def suite_failures(required, results) -> list[dict]:
    """The cases the suite needs but the page did not deliver.

    A case that was never made, or whose verdict is not ok, is a failure.
    Only a case the suite does not ask for may be absent.
    """
    failures = []
    by_label = {result.get("label"): result for result in results}
    for label in required:
        result = by_label.get(label)
        if result is None:
            failures.append(
                {
                    "step": f"suite-{label}",
                    "check": "case_executed",
                    "expected": "the case to run against this page",
                    "actual": "not executed",
                }
            )
        elif result.get("skipped"):
            failures.append(
                {
                    "step": f"suite-{label}",
                    "check": "case_executed",
                    "expected": "the case to run against this page",
                    "actual": result.get("reason", "skipped"),
                }
            )
        elif not result.get("ok"):
            failures.append(
                {
                    "step": f"suite-{label}",
                    "check": "case_verdict",
                    "expected": "the widget to send a changed value and the page to show it",
                    "actual": "; ".join(result.get("problems") or ["no verdict"]),
                }
            )
    return failures


def suite_counts(required, results) -> dict:
    """How many cases the suite expected, how many ran and how many asserted."""
    by_label = {result.get("label"): result for result in results}
    executed = [
        label
        for label in required
        if by_label.get(label) and not by_label[label].get("skipped")
    ]
    asserted = [label for label in executed if by_label[label].get("ok")]
    return {"expected": len(required), "executed": len(executed), "asserted": len(asserted)}


def dom_value_for(markdown, label: str):
    """The value the page shows for one widget, e.g. "40" or "(40, 80)"."""
    for line in markdown or []:
        if line.startswith(label + ":"):
            return line.split(":", 1)[1].strip()
    return None


def wire_value_of(state):
    """The value the client sent, in the shape the proto carries it.

    A slider sends a DoubleArray, so its value is the list inside that
    message; a selectbox sends a string and a checkbox a boolean.
    """
    if not state:
        return None
    full = state.get("value_full")
    if isinstance(full, dict) and "data" in full:
        return full["data"]
    return state.get("value")


def widget_value_matches(dom_text, wire_value) -> bool:
    """Does the value on the page match the value the client sent?

    A float is compared with a tolerance, a range is compared element by
    element and must have the same length, and a string or a boolean is
    compared as such.  A range is written "(40, 80)" by Python and "40..80"
    by Rust, so both spellings are accepted.
    """
    if dom_text is None or wire_value is None:
        return False
    if isinstance(wire_value, bool):
        return dom_text.lower() == ("true" if wire_value else "false")
    if isinstance(wire_value, str):
        return dom_text.strip("'\"") == wire_value
    if isinstance(wire_value, (int, float)):
        try:
            return abs(float(dom_text) - float(wire_value)) <= 1e-9
        except ValueError:
            return False
    if isinstance(wire_value, list):
        text = dom_text.strip()
        if text.startswith("(") and text.endswith(")"):
            text = text[1:-1]
        if ".." in text:
            text = text.replace("..", ",")
        parts = [part.strip() for part in text.split(",") if part.strip()]
        if len(parts) != len(wire_value):
            return False
        try:
            return all(abs(float(part) - float(value)) <= 1e-9 for part, value in zip(parts, wire_value))
        except ValueError:
            return False
    return False

STATUS_ORACLE = [
    {"body": "INFO-BODY plain information", "format": "INFO"},
    {"body": "SUCCESS-BODY the operation succeeded", "format": "SUCCESS"},
    {"body": "WARNING-BODY something needs attention", "format": "WARNING"},
    {"body": "ERROR-BODY something failed", "format": "ERROR"},
    {"body": "INFO-EMOJI-BODY \U0001f4a1 this body starts with an emoji", "format": "INFO"},
    {"body": "INFO-NOICON-BODY \U0001f4a1 body keeps its emoji", "format": "INFO"},
    {"body": "SUCCESS-MATERIAL-BODY material icon", "format": "SUCCESS", "icon": ":material/thumb_up:"},
    {"body": "WARNING-WIDTH-BODY fixed width", "format": "WARNING", "width": 240},
    {"body": "ERROR-TITLE-BODY with a title", "format": "ERROR", "title": "ERROR-TITLE"},
    {"body": "INFO-LEADING-EMOJI this body starts with an emoji", "format": "INFO", "icon": "\U0001f4a1"},
    {"body": "\U0001f4a1 INFO-LEADING-NOICON body keeps its emoji", "format": "INFO"},
    {"body": "INFO-LEADING-MATERIAL body starts with a shortcode", "format": "INFO", "icon": ":material/thumb_up:"},
    {"body": "INFO-ICON-ZWJ body", "format": "INFO", "icon": "\U0001f469\u200d\U0001f4bb"},
    {"body": "INFO-ICON-SKIN body", "format": "INFO", "icon": "\U0001f44d\U0001f3fd"},
    {"body": "INFO-ICON-FLAG body", "format": "INFO", "icon": "\U0001f1e8\U0001f1f3"},
    {"body": "INFO-LEADING-COMPOSITE body starts with a composite emoji", "format": "INFO", "icon": "\U0001f469\u200d\U0001f4bb"},
]


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
        self.status_observation: dict | None = None
        self.widget_observation: dict | None = None
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
        ) if args.scenario in ("reconnect", "counter") else None

    def mark(self, name: str, note: str, expected: dict | None = None) -> dict:
        try:
            observation = self.ab.observe()
        except SystemExit as exc:
            observation = {"error": str(exc)[:200]}
        self.mark_observed(name, note, observation, expected)
        return observation

    def mark_observed(
        self,
        name: str,
        note: str,
        observation: dict,
        expected: dict | None = None,
    ) -> dict:
        """Record a step against an observation that was read some other way."""
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

    def window(self, recorder, label: str, start: int | None = None, end: int | None = None):
        """Record a click window in the recorder's own frame numbering.

        The finished trace lists the frames of every recorder in one list, so
        the windows are translated to that global space once the offsets are
        known.  Indexing them per recorder from the start would silently point
        at the wrong frames as soon as a second tab is open.
        """
        first = recorder.frame_count() if start is None else start
        last = recorder.frame_count() if end is None else end
        self.click_windows.append(
            {"click": label, "target": recorder.label, "start": first, "end": last}
        )
        return first, last

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
        start, end = self.window(self.recorders[0], "post-reconnect")
        self.ab.click("[data-testid='stButton']")
        self.ab.run("wait", "3000")
        end = self.recorders[0].frame_count()
        self.click_windows[-1]["end"] = end
        self.click_windows[-1]["require_new_connection"] = True
        self.click_windows[-1]["connection_before"] = connection_before_fault
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
            self.window(self.recorders[0], index + 1)
            self.ab.click("[data-testid='stButton']")
            self.ab.run("wait", "2500")
            # The window must be closed after the click, or it stays empty and
            # the helper rejects a click that the server did answer.
            self.click_windows[-1]["end"] = self.recorders[0].frame_count()
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

    def server_under_test(self) -> dict:
        """What was on the other end of the wire: the binary and its revision."""
        info: dict = {"target": self.args.target}
        if self.args.binary:
            path = pathlib.Path(self.args.binary)
            info["binary"] = str(path)
            if path.exists():
                info["binary_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
                info["binary_bytes"] = path.stat().st_size
            else:
                info["binary_sha256"] = None
        if self.args.source_version:
            info["source_version"] = self.args.source_version
        return info

    def status_dom(self) -> dict:
        """Read the rendered alerts back from the DOM, one entry per alert."""
        js = r"""(()=>{const alerts=[...document.querySelectorAll("[data-testid='stAlert']")].map(e=>{
const icon=e.querySelector("[data-testid='stAlertContentIcon']")||e.querySelector("img")||e.querySelector(".material-symbols-rounded");
const title=e.querySelector("[data-testid='stAlertTitle']")||e.querySelector("h3");
return {text:e.innerText.replace(/\s+/g," ").trim(),
width:Math.round(e.getBoundingClientRect().width),
icon_text:icon?(((icon.getAttribute("alt")||icon.textContent||"").trim())||null):null,
icon_html:icon?icon.outerHTML.slice(0,240):null,
title:title?title.innerText.trim():null};});
const exceptions=[...document.querySelectorAll("[data-testid='stException']")].map(e=>e.innerText.replace(/\s+/g," ").trim().slice(0,400));
return JSON.stringify({alerts,exceptions});})()"""
        raw = self.ab.run("eval", js)
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

    def scenario_status(self) -> None:
        """The status page: the four kinds plus the icon, width and title variants.

        The wire fields are compared against the Python 1.66.1 oracle, and the
        rendered page is measured in the DOM, so a server that drops the icon,
        the title or the fixed width is caught even though the page still looks
        plausible.
        """
        self.ab.run("wait", "6000")
        self.shot("30-status-page.png")
        wire: list[dict] = []
        finished: list[dict] = []
        for event in self.recorders[0].take():
            if event.get("method") != "Network.webSocketFrameReceived":
                continue
            frame = event["params"].get("response", {})
            if frame.get("opcode") != 2:
                continue
            decoded = _safe(summarise_forward, base64.b64decode(frame["payloadData"]))
            if decoded.get("type") == "delta":
                delta = decoded.get("delta", {})
                if delta.get("type") == "new_element" and delta.get("element") == "alert":
                    wire.append(delta.get("alert") or {})
            elif decoded.get("type") == "script_finished":
                finished.append(decoded.get("script_finished") or {})
        dom = self.status_dom()
        alerts = dom.get("alerts") or []
        mismatches = []
        for expected in STATUS_ORACLE:
            actual = next((a for a in wire if a.get("body") == expected["body"]), None)
            problems = []
            if actual is None:
                problems.append("no alert with this body on the wire")
            else:
                if actual.get("format") != expected["format"]:
                    problems.append(f"format {actual.get('format')!r} != {expected['format']!r}")
                if actual.get("icon") != expected.get("icon"):
                    problems.append(f"icon {actual.get('icon')!r} != {expected.get('icon')!r}")
                if actual.get("title") != expected.get("title"):
                    problems.append(f"title {actual.get('title')!r} != {expected.get('title')!r}")
                want_width = expected.get("width")
                got_width = (actual.get("widthConfig") or {}).get("pixelWidth")
                if want_width is None:
                    if not (actual.get("widthConfig") or {}).get("useStretch"):
                        problems.append(f"widthConfig {actual.get('widthConfig')!r} is not stretch")
                elif got_width != want_width:
                    problems.append(f"pixelWidth {got_width!r} != {want_width!r}")
            mismatches.append(
                {"body": expected["body"], "ok": not problems, "problems": problems, "actual": actual}
            )
        fixed = next(
            (a for a in alerts if "WARNING-WIDTH-BODY fixed width" in (a.get("text") or "")),
            None,
        )
        stretched = [a for a in alerts if a is not fixed]
        observation = {
            "alerts_rendered": len(alerts),
            "alert_texts": [a.get("text") for a in alerts],
            "alert_widths": [a.get("width") for a in alerts],
            "fixed_width_px": fixed.get("width") if fixed else None,
            "stretched_min_px": min((a.get("width") or 0) for a in stretched) if stretched else None,
            "exceptions": dom.get("exceptions") or [],
            "script_finished": finished,
            "script_finished_ok": any(f.get("status") == SCRIPT_FINISHED_SUCCESS for f in finished),
            "wire_alerts": wire,
            "oracle_mismatches": [m for m in mismatches if not m["ok"]],
            "oracle": mismatches,
        }
        self.status_observation = observation
        self.mark_observed(
            "status-page",
            "the status page rendered every alert and the server finished the script",
            observation,
            {
                "alerts_rendered": 17,
                "script_finished_ok": True,
                "fixed_width_px": 240,
                "exceptions": [],
                "oracle_mismatches": [],
            },
        )
        self.shot("31-status-details.png")

    def widget_wire(self, events) -> tuple[dict, list]:
        """The widget elements and the script results the server sent."""
        widgets: dict = {}
        finished: list = []
        for event in events:
            if event.get("method") != "Network.webSocketFrameReceived":
                continue
            frame = event["params"].get("response", {})
            if frame.get("opcode") != 2:
                continue
            decoded = _safe(summarise_forward, base64.b64decode(frame["payloadData"]))
            if decoded.get("type") == "delta":
                delta = decoded.get("delta", {})
                if delta.get("type") == "new_element" and delta.get("element") in WIDGET_ELEMENTS:
                    widgets.setdefault(delta["element"], delta.get("widget") or {})
            elif decoded.get("type") == "script_finished":
                finished.append(decoded.get("script_finished") or {})
        return widgets, finished

    def widget_dom(self) -> dict:
        """Read the rendered widgets back from the DOM."""
        raw = self.ab.run("eval", WIDGET_DOM_JS)
        try:
            value = json.loads(raw)
        except json.JSONDecodeError:
            return {"raw": raw[:400]}
        if isinstance(value, str):
            try:
                value = json.loads(value)
            except json.JSONDecodeError:
                return {"raw": raw[:400]}
        return value if isinstance(value, dict) else {"value": value}
        raw = self.ab.run("eval", js)
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

    def scenario_widgets(self) -> None:
        """The input widgets: their wire fields, their defaults and their reruns.

        The case selects one page of the reference app
        (tests/reference/widgets_app.py).  Every interaction is checked against
        the wire: the client has to send the new state of the widget and the
        server has to answer with a successful script_finished on the same
        connection.
        """
        case = self.args.case
        self.ab.run("wait", "5000")
        self.shot(f"40-widgets-{case}-open.png")
        widgets, finished = self.widget_wire(self.recorders[0].take())
        dom = self.widget_dom()
        observation: dict = {
            "case": case,
            "wire_widgets": widgets,
            "dom": dom,
            "script_finished": finished,
            "widgets_captured": len(
                [k for k in ("selectbox", "slider", "checkbox") if k in widgets]
            ),
            "has_exception": bool(dom.get("exceptions")),
            "all_disabled": bool(
                dom.get("selectbox_disabled")
                and dom.get("slider_disabled")
                and dom.get("checkbox_disabled")
            ),
        }
        if case in ("defaults", "options", "keys", "on_change"):
            current = dom.get("selectbox_value")
            option = "region" if current != "region" else "channel"
            for kind, action in (
                ("selectbox", "select"),
                ("slider", "move"),
                ("checkbox", "toggle"),
            ):
                widget_id = (widgets.get(kind) or {}).get("id")
                if not widget_id:
                    self.failures.append(
                        {
                            "step": f"widgets-{kind}",
                            "check": "widget_id",
                            "expected": "the widget id on the wire",
                            "actual": "not captured",
                        }
                    )
                    continue
                start = self.recorders[0].frame_count()
                if action == "select":
                    self.set_group(option)
                elif action == "move":
                    self.set_slider(10)
                else:
                    self.set_checkbox(False)
                self.click_windows.append(
                    {
                        "click": f"{kind}-{action}",
                        "target": self.recorders[0].label,
                        "start": start,
                        "end": self.recorders[0].frame_count(),
                        "widget": widget_id,
                    }
                )
                self.mark(f"widgets-{kind}", f"changed the {kind}", {})
                self.shot(f"41-widgets-{case}-{kind}.png")
            observation["after"] = self.widget_dom()
        self.widget_observation = observation
        expected: dict = {"has_exception": False}
        if case == "dup_key":
            expected = {"has_exception": True}
        if case == "disabled":
            expected = {"all_disabled": True, "has_exception": False}
        self.mark_observed(
            "widgets-page",
            f"the {case} page of the widget reference rendered",
            observation,
            expected,
        )

    def change_widget(self, case: dict) -> dict:
        """Make one widget change, with the agent-browser CLI.

        The slider is a React Aria widget: every thumb is a hidden
        input[type=range] inside the group that carries the label, and the
        checkbox input is visually hidden as well, so both are driven with a
        key press.
        """
        kind = case["kind"]
        label = case["label"]
        if kind == "slider":
            selector = (
                f"[data-testid='stSlider'] [role='group'][aria-label='{label}'] "
                f"input[type=range]:nth-of-type({case.get('thumb', 0) + 1})"
            )
            self.ab.run("focus", selector)
            for _ in range(case.get("times", 1)):
                self.ab.run("press", case.get("key", "ArrowRight"))
                time.sleep(0.5)
            return {"action": "press", "key": case.get("key", "ArrowRight")}
        if kind == "checkbox":
            selector = f"[data-testid='stCheckbox'] input[type=checkbox]"
            self.ab.run("focus", selector)
            self.ab.run("press", " ")
            return {"action": "press-Space"}
        if kind == "selectbox":
            self.ab.run("click", "[data-testid='stSelectbox'] button[aria-label='Open']")
            time.sleep(1.5)
            option = case.get("option", "region")
            self.ab.run("find", "text", option, "click")
            return {"action": "select-option", "option": option}
        raise SystemExit(f"unknown widget kind {kind!r}")

    def scenario_numeric(self) -> None:
        """The numeric representatives and the core controls.

        Every case is checked against the wire: the client has to send the
        widget's new value, the server has to answer with a successful
        script_finished on the same connection, and the value the page
        renders has to be the value that was sent.
        """
        suite = SUITES[self.args.suite]
        self.ab.run("wait", "5000")
        widgets, _finished = self.widget_wire(self.recorders[0].take())
        ids = {}
        for kind, payload in widgets.items():
            inner = payload.get(kind) or payload
            label = inner.get("label") if isinstance(inner, dict) else None
            if label:
                ids[(kind, label)] = inner.get("id")
        observations = []
        for case in suite["cases"]:
            label = case["label"]
            widget_id = ids.get((case["kind"], label))
            if not widget_id:
                # The page does not carry this widget: that is not a failure.
                observations.append(
                    {
                        "widget": case["kind"],
                        "label": label,
                        "widget_id": None,
                        "skipped": True,
                        "reason": "no such widget on this page",
                    }
                )
                continue
            start = self.recorders[0].frame_count()
            action = self.change_widget(case)
            self.click_windows.append(
                {
                    "click": f"{case['kind']}-{label}",
                    "target": self.recorders[0].label,
                    "start": start,
                    "end": self.recorders[0].frame_count(),
                    "widget": widget_id,
                }
            )
            dom = self.widget_dom()
            shown = dom_value_for(dom.get("markdown"), label)
            states = []
            for event in self.recorders[0].take():
                if event.get("method") != "Network.webSocketFrameSent":
                    continue
                decoded = _safe(
                    summarise_back,
                    _decode_payload(
                        event["params"].get("response", {}).get("opcode"),
                        event["params"].get("response", {}).get("payloadData", ""),
                    ),
                )
                for state in (decoded.get("rerun_script") or {}).get("widget_states", []):
                    if state.get("id") == widget_id:
                        states.append(state)
            wire_value = wire_value_of(states[-1] if states else None)
            matched = widget_value_matches(shown, wire_value)
            if not matched:
                self.failures.append(
                    {
                        "step": f"numeric-{label}",
                        "check": "value_matches_the_page",
                        "expected": wire_value,
                        "actual": shown,
                    }
                )
            observations.append(
                {
                    "widget": case["kind"],
                    "label": label,
                    "widget_id": widget_id,
                    "action": action,
                    "wire_value": wire_value,
                    "page_shows": shown,
                    "value_matches_the_page": matched,
                }
            )
        self.failures.extend(suite_failures(suite["required"], observations))
        counts = suite_counts(suite["required"], observations)
        self.widget_observation = {
            "case": self.args.suite,
            "widgets": widgets,
            "counts": counts,
            "interactions": observations,
        }
        self.mark_observed(
            "numeric-page",
            "every widget the suite requires sent its value and the page shows it",
            {
                "counts": counts,
                "interactions": observations,
                "mismatches": [
                    o for o in observations
                    if not o.get("skipped") and not o["value_matches_the_page"]
                ],
            },
            {"mismatches": []},
        )
        self.shot("40-numeric-page.png")

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

    def scenario_counter(self) -> None:
        """A generic session-counter server: isolation, recovery and refresh.

        It assumes the app exposes a session-scoped counter ("Pulses:" and
        "Script runs:") and a button, with no uploader and no chart.  The three
        behaviours it checks are the ones a Rust session implementation has to
        reproduce:

        * two tabs get two different sessions and cannot see each other;
        * after a real disconnect the frontend reconnects to the SAME session,
          the counter survives, and a click on the reconnected connection works;
        * after a reload the browser has forgotten the session, so a NEW
          session is issued and the counter is back to its initial value.
        """
        tab_a_index = self.current_tab_index()
        self.mark(
            "counter-open",
            "the counter app rendered",
            {"has_button": True, "pulses": "0", "script_runs": "1"},
        )
        self.shot("21-counter-open.png")

        # ---- two tabs, two sessions -------------------------------------
        before_ids = {t["id"] for t in page_targets(self.cdp_browser_url, self.host)}
        self.ab.run("tab", "new", self.args.url)
        self.ab.run("wait", "6000")
        new_targets = [
            t for t in page_targets(self.cdp_browser_url, self.host) if t["id"] not in before_ids
        ]
        if not new_targets:
            self.failures.append(
                {
                    "step": "counter",
                    "check": "second_tab",
                    "expected": "a second browser tab",
                    "actual": "no new page target appeared",
                }
            )
        else:
            self.recorders.append(CDP(new_targets[0]["webSocketDebuggerUrl"], label="tab-b"))
            self.recorders[-1].start()
            time.sleep(1.0)
        self.mark(
            "counter-tab-b",
            "a second tab starts its own fresh session",
            {"pulses": "0", "script_runs": "1"},
        )
        self.shot("22-counter-tab-b.png")

        self.window(self.recorders[-1], "tab-b")
        self.ab.click("[data-testid='stButton']")
        self.ab.run("wait", "2500")
        self.click_windows[-1]["end"] = self.recorders[-1].frame_count()
        self.mark("counter-tab-b-click", "clicking in tab B advances only tab B", {"pulses": "1"})
        self.shot("23-counter-tab-b-click.png")

        self.ab.run("tab", str(tab_a_index))
        self.ab.run("wait", "2000")
        self.mark(
            "counter-tab-a-isolated",
            "tab A is unaffected by what tab B did",
            {"pulses": "0", "script_runs": "1"},
        )

        session_a = _session_ids(self.recorders, "tab-a")
        session_b = _session_ids(self.recorders, "tab-b")
        if session_a and session_b and set(session_a) & set(session_b):
            self.failures.append(
                {
                    "step": "counter",
                    "check": "session_isolation",
                    "expected": "a different session id per tab",
                    "actual": f"both tabs used {sorted(set(session_a) & set(session_b))}",
                }
            )
        self.notes.append(f"tab A session id(s): {session_a or 'not captured'}")
        self.notes.append(f"tab B session id(s): {session_b or 'not captured'}")

        # ---- same-session recovery --------------------------------------
        for index in range(2):
            self.window(self.recorders[0], f"pre-recovery-{index + 1}")
            self.ab.click("[data-testid='stButton']")
            self.ab.run("wait", "2000")
            self.click_windows[-1]["end"] = self.recorders[0].frame_count()
        self.mark("counter-two-clicks", "two clicks in tab A", {"pulses": "2"})
        session_before = _session_ids(self.recorders, "tab-a")
        connection_before_fault = self.connection_index_before()

        closed = self.recorders[0].call(
            "Runtime.evaluate",
            {"expression": "window.__stWs ? (window.__stWs.close(), 'closed') : 'no socket'"},
            timeout=5.0,
        )
        self.notes.append(f"live socket closed through Runtime.evaluate: {closed}")
        if _evaluate_value(closed) != "closed":
            self.failures.append(
                {
                    "step": "counter",
                    "check": "socket_closed",
                    "expected": "the live socket to be closed",
                    "actual": str(closed)[:200],
                }
            )
        time.sleep(3.0)

        deadline = time.time() + 40
        reconnect_handshake = None
        while time.time() < deadline:
            for handshake in _handshakes(self.recorders[0]):
                if len(handshake.get("entries", [])) >= 3:
                    reconnect_handshake = handshake
                    break
            if reconnect_handshake:
                break
            time.sleep(1.0)
        time.sleep(4.0)
        self.mark(
            "counter-reconnected",
            "the frontend reconnected; the session and its counter survived",
            {"pulses": "2"},
        )
        self.shot("24-counter-reconnected.png")
        if reconnect_handshake:
            self.notes.append(
                "reconnect handshake Sec-WebSocket-Protocol: "
                + str(reconnect_handshake["headers"].get("Sec-WebSocket-Protocol"))
            )
        else:
            self.failures.append(
                {
                    "step": "counter",
                    "check": "reconnect_handshake",
                    "expected": "a handshake with three subprotocol entries",
                    "actual": "no such handshake was observed",
                }
            )

        start, end = self.window(self.recorders[0], "post-recovery")
        self.ab.click("[data-testid='stButton']")
        self.ab.run("wait", "3000")
        end = self.recorders[0].frame_count()
        self.click_windows[-1]["end"] = end
        self.click_windows[-1]["require_new_connection"] = True
        self.click_windows[-1]["connection_before"] = connection_before_fault
        self.mark(
            "counter-click-after-recovery",
            "the click on the reconnected session advanced the counter",
            {"pulses": "3"},
        )
        self.shot("25-counter-after-recovery.png")

        session_after = _session_ids(self.recorders, "tab-a")
        if session_before and session_after and session_before[-1] != session_after[-1]:
            self.failures.append(
                {
                    "step": "counter",
                    "check": "same_session",
                    "expected": f"the session {session_before[-1]} to be reused",
                    "actual": f"a different session {session_after[-1]}",
                }
            )
        self.notes.append(f"session id before the fault: {session_before or 'not captured'}")
        self.notes.append(f"session id after the recovery: {session_after or 'not captured'}")

        # ---- a reload starts a new session -------------------------------
        self.ab.run("reload")
        self.ab.run("wait", "7000")
        self.mark(
            "counter-after-reload",
            "a reload starts a new session and resets the counter",
            {"pulses": "0", "script_runs": "1"},
        )
        self.shot("26-counter-after-reload.png")
        session_reloaded = _session_ids(self.recorders, "tab-a")
        if session_before and session_reloaded and session_before[-1] == session_reloaded[-1]:
            self.failures.append(
                {
                    "step": "counter",
                    "check": "new_session_after_reload",
                    "expected": f"a session id other than {session_before[-1]}",
                    "actual": f"the same session {session_reloaded[-1]}",
                }
            )
        self.notes.append(f"session id after the reload: {session_reloaded or 'not captured'}")

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
        offsets: dict[str, int] = {}
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
                offsets.setdefault(target, len(frames))
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
                for item in request.get("postDataEntries") or []:
                    raw = base64.b64decode(item.get("bytes", "") or "")
                    entry["post_data_entries"] = [
                        {
                            "bytes": len(raw),
                            "sha256": hashlib.sha256(raw).hexdigest(),
                            "head": raw[:160].decode("utf-8", "replace"),
                            "base64": (
                                base64.b64encode(raw).decode("ascii")
                                if len(raw) <= 256 * 1024
                                else None
                            ),
                        }
                    ]
                    break
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

        translated = []
        for window in self.click_windows:
            offset = offsets.get(window.get("target"), 0)
            translated.append(
                {
                    **window,
                    "start": window["start"] + offset,
                    "end": window["end"] + offset,
                }
            )
        self.failures.extend(verify_click_windows(frames, translated))
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
            "kind": (
                "rust-browser-trace" if self.args.target == "rust" else "python-reference-browser-trace"
            ),
            "target": self.args.target,
            "scenario": self.args.scenario,
            "scope": (
                "RUST SIDE ONLY. The Rust implementation is exercised by this trace; the "
                "Python reference application is not. Black-box evidence over the real "
                "HTTP, WebSocket and protobuf surface of the server under test."
                if self.args.target == "rust"
                else "PYTHON SIDE ONLY. The Rust implementation is not exercised and is not "
                "verified by this trace. This is black-box evidence over the real HTTP, "
                "WebSocket and protobuf surface of the reference application."
            ),
            "server_under_test": self.server_under_test(),
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
            "status_observation": self.status_observation,
            "widget_observation": self.widget_observation,
            "steps": self.steps,
            "failures": self.failures,
            "notes": self.notes,
            "frames": frames,
        }


def parse_counter_texts(lines):
    """Extract the session counter values from rendered lines.

    A counter may be rendered as ``st.text`` or as ``st.write`` markdown, so
    both are accepted.  The prefix must match exactly, which keeps a stray
    "Pulses" in some other text from being read as the counter.
    """
    found: dict[str, str] = {}
    for line in lines or []:
        line = line.strip()
        for key, prefix in (("pulses", "Pulses:"), ("script_runs", "Script runs:")):
            if line.startswith(prefix):
                value = line[len(prefix) :].strip()
                if value:
                    found[key] = value
    return found


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
        # A window either names the widget whose state has to travel -- a
        # selectbox, a slider or a checkbox send their value, not a trigger --
        # or it is a button, which sends trigger_value.
        wanted_widget = window.get("widget")
        for offset, frame in enumerate(segment):
            if frame.get("direction") != "client->server":
                continue
            decoded = frame.get("decoded") or {}
            if decoded.get("type") != "rerun_script":
                continue
            states = decoded.get("rerun_script", {}).get("widget_states", [])
            if wanted_widget:
                if any(state.get("id") == wanted_widget for state in states):
                    trigger_position = offset
                    trigger_connection = frame.get("connection")
                continue
            for widget in states:
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
                    "expected": (
                        f"the state of widget {wanted_widget} inside the click window"
                        if wanted_widget
                        else "a trigger_value=true for the button inside the click window"
                    ),
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

        # A frame that carries no connection proves nothing: it may not be
        # counted as the same connection as the state frame, and 0 is a real
        # connection index.
        if trigger_position is not None and trigger_connection is None:
            failures.append(
                {
                    "step": f"click-{label}",
                    "check": "connection",
                    "expected": "the connection the state frame travelled on",
                    "actual": "the frame carries no connection",
                }
            )
        same_connection = [
            frame
            for frame in successful_after
            if frame.get("connection") is not None
            and frame.get("connection") == trigger_connection
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
        "--case",
        default="defaults",
        help="which page of the reference app the widgets scenario captures",
    )
    parser.add_argument(
        "--target",
        choices=("python", "rust"),
        default="python",
        help="which implementation the capture is about; it labels the trace, it does not change what is captured",
    )
    parser.add_argument(
        "--binary",
        default="",
        help="path to the server binary under test; its sha256 is recorded in the trace",
    )
    parser.add_argument(
        "--source-version",
        default="",
        help="source revision of the server under test",
    )
    parser.add_argument(
        "--clicks", type=int, default=3, help="how many times the smoke scenario clicks the button"
    )
    parser.add_argument(
        "--fixtures",
        default=str(REPO_ROOT / "tests" / "fixtures" / "csv"),
        help="directory holding the CSV fixtures",
    )
    args = parser.parse_args()
    require_decoder()
    return Capture(args).run()


if __name__ == "__main__":
    raise SystemExit(main())
