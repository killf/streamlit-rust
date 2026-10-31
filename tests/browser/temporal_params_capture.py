"""One owned native temporal-parameter capture against pinned SDK or Rust.

Records original creation fields or opt-in keyed/unkeyed identity transitions; never
overwrites a trace and makes no browser/UI claim.
"""
import argparse
import base64
from datetime import datetime, timezone
import importlib.metadata
import hashlib
import json
from pathlib import Path
import socket
import subprocess
import sys
import time
import urllib.request

from google.protobuf.json_format import MessageToDict
from streamlit.proto.BackMsg_pb2 import BackMsg
from streamlit.proto.ForwardMsg_pb2 import ForwardMsg
from websockets.sync.client import connect

ROOT = Path(__file__).resolve().parents[2]
parser = argparse.ArgumentParser(description='Collect the temporal-parameter reference once; never overwrite.')
parser.add_argument('--out', type=Path, required=True)
mode = parser.add_mutually_exclusive_group()
mode.add_argument('--identity', action='store_true', help='eleven keyed time/datetime/date state and constraint transitions')
mode.add_argument('--unkeyed', action='store_true', help='eight unkeyed presentation, width and datetime bounds transitions')
parser.add_argument('--url', help='caller-owned Rust server URL (comparison capture)')
args = parser.parse_args()
OUT = args.out.resolve()
OUT.mkdir(parents=True, exist_ok=True)
assert not (OUT / 'trace.json').exists(), 'one capture, retain first result'
assert importlib.metadata.version('streamlit') == '1.66.1'

COMMAND = None
if args.url:
    URL = args.url.rstrip('/')
else:
    with socket.socket() as listener:
        listener.bind(('127.0.0.1', 0))
        PORT = listener.getsockname()[1]
    URL = f'http://127.0.0.1:{PORT}'
    COMMAND = [sys.executable, '-B', '-m', 'streamlit', 'run', str(ROOT / 'tests/reference/temporal_params_app.py'),
               '--server.address=127.0.0.1', f'--server.port={PORT}', '--server.headless=true',
               '--server.fileWatcherType=none', '--browser.gatherUsageStats=false']
TRACE = {'schema_version': 1, 'runtime': 'rust' if args.url else 'python', 'reference_version': '1.66.1',
         'captured_at_utc': datetime.now(timezone.utc).isoformat(),
         'scope': 'Element wire of temporal/slider creation-parameter edges over one native WS; no browser/UI claim.',
         'server_command': COMMAND, 'server_cleanup': 'caller-owned' if COMMAND is None else 'collector-owned',
         'url': URL, 'frames': [], 'elements': [], 'finishes': []}
TRACE['producer_sources_sha256'] = {path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest() for path in (
    'streamlit/examples/temporal_params.rs', 'tests/reference/temporal_params_app.py', 'tests/browser/temporal_params_capture.py')}
if args.identity or args.unkeyed:
    TRACE['scope'] = ('Eight unkeyed presentation/width/bounds runs' if args.unkeyed else 'Eleven keyed constraint/retention runs') + ' over one native WS; no browser/UI claim.'
SERVER = WS = None


def save():
    (OUT / 'trace.json').write_text(json.dumps(TRACE, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def record(direction, raw, message):
    TRACE['frames'].append({'direction': direction, 'bytes': len(raw), 'base64': base64.b64encode(raw).decode(),
                            'message': MessageToDict(message, preserving_proto_field_name=True)})


try:
    if COMMAND is not None:
        SERVER = subprocess.Popen(COMMAND, cwd=ROOT, stdout=(OUT / 'server.log').open('w', encoding='utf-8'),
                                  stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW)
        TRACE['server_pid'] = SERVER.pid
    deadline = time.monotonic() + 25
    while True:
        try:
            with urllib.request.urlopen(URL + '/_stcore/health', timeout=1) as response:
                TRACE['health'] = {'status': response.status, 'body': response.read().decode()}
            break
        except OSError:
            if time.monotonic() > deadline or SERVER is not None and SERVER.poll() is not None:
                raise RuntimeError('server unavailable')
            time.sleep(0.1)
    WS = connect(URL.replace('http', 'ws') + '/_stcore/stream', origin=URL, subprotocols=['streamlit'], proxy=None,
                 open_timeout=10, close_timeout=5, max_size=None, legacy=True)
    phases = ("load", "edit", "policy", "step", "edit-step", "format", "edit-format", "defaults", "bounds", "restore", "observe") if args.identity else ("load",)
    if args.unkeyed:
        phases = ("load", "edit", "format", "width", "restore", "edit-bounds", "bounds", "observe")
    widget_ids = {}
    for phase in phases:
        request = BackMsg()
        request.rerun_script.SetInParent()
        if args.identity or args.unkeyed:
            request.rerun_script.query_string = "probe=" + ("unkeyed" if args.unkeyed else "identity") + "&phase=" + phase
            if phase in ("edit", "edit-step", "edit-format", "edit-bounds"):
                clock, moment, date = {"edit": ("13:45", "2024-06-01T13:45", "2024-06-01"),
                                       "edit-step": ("14:00", "2024-06-01T14:00", "2024-06-01"),
                                       "edit-format": ("15:00", "2024-07-04T15:00", "2024-07-04"),
                                       "edit-bounds": ("13:45", "2024-06-01T13:45", "2024-06-01")}[phase]
                for key, value in (("clock", clock), ("moment", moment), ("date", date)):
                    widget = request.rerun_script.widget_states.widgets.add()
                    widget.id = widget_ids[key]
                    if key == "clock":
                        widget.string_value = value
                    else:
                        widget.string_array_value.data.append(value)
        raw = request.SerializeToString()
        record('client->server', raw, request)
        WS.send(raw)
        index = 0
        while True:
            raw = WS.recv(timeout=20)
            message = ForwardMsg()
            message.ParseFromString(raw)
            record('server->client', raw, message)
            kind = message.WhichOneof('type')
            if kind == 'script_finished':
                TRACE['finishes'].append(message.script_finished)
                break
            if kind != 'delta':
                continue
            delta_kind = message.delta.WhichOneof('type')
            if delta_kind == 'add_block':
                block = message.delta.add_block
                allowed = block.WhichOneof('type')
                if allowed is not None:
                    view = getattr(block, allowed)
                    fields = MessageToDict(view, preserving_proto_field_name=True)
                    block_level = {}
                    if block.HasField('width_config'):
                        block_level['width_config'] = MessageToDict(block.width_config, preserving_proto_field_name=True)
                    if block.HasField('height_config'):
                        block_level['height_config'] = MessageToDict(block.height_config, preserving_proto_field_name=True)
                    TRACE['elements'].append({'index': index, 'kind': f'add_block:{allowed}', 'fields': fields, 'block': block_level,
                                              'url': None, 'delta_path': list(message.metadata.delta_path)})
                    index += 1
            elif delta_kind == 'new_element':
                element = message.delta.new_element
                element_kind = element.WhichOneof('type')
                if element_kind is not None:
                    view = getattr(element, element_kind)
                    fields = MessageToDict(view, preserving_proto_field_name=True)
                    if (args.identity or args.unkeyed) and element_kind in ('time_input', 'date_time_input', 'date_input'):
                        widget_ids[{'time_input': 'clock', 'date_time_input': 'moment', 'date_input': 'date'}[element_kind]] = view.id
                    url = getattr(view, 'url', '') if hasattr(view, 'url') else ''
                    TRACE['elements'].append({'index': index, 'kind': element_kind, 'fields': fields,
                                              'url': url, 'delta_path': list(message.metadata.delta_path)})
                    index += 1
    WS.close()
    TRACE['cleanup'] = {'websocket_closed': True}
    TRACE['successful'] = True
except Exception as error:
    TRACE['producer_error'] = f'{type(error).__name__}: {error}'
    raise
finally:
    if WS is not None:
        try:
            WS.close()
        except Exception:
            pass
    if SERVER is not None:
        SERVER.terminate()
        SERVER.wait(timeout=10)
        TRACE['cleanup'] = TRACE.get('cleanup', {}) | {'server_stopped': True}
    save()
