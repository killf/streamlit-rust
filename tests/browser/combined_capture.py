"""One owned protocol capture of layout/streaming parameter variants.

A native WebSocket against the pinned 1.66.1 server (or a caller-owned Rust
server): every new_element and new_transient element is recorded with its
kind and full wire dict, so parameter deltas are diffable call by call. Never
overwrites an existing trace.
"""
import argparse
import base64
from datetime import datetime, timezone
import hashlib
import importlib.metadata
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
parser = argparse.ArgumentParser(description='Collect the M7 combined differential once; never overwrite.')
parser.add_argument('--out', type=Path, required=True)
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
    COMMAND = [sys.executable, '-B', '-m', 'streamlit', 'run', str(ROOT / 'tests/reference/combined_app.py'),
               '--server.address=127.0.0.1', f'--server.port={PORT}', '--server.headless=true',
               '--server.fileWatcherType=none', '--browser.gatherUsageStats=false']
TRACE = {'schema_version': 1, 'runtime': 'rust' if args.url else 'python', 'reference_version': '1.66.1',
         'captured_at_utc': datetime.now(timezone.utc).isoformat(),
         'scope': 'Cross-capability combined page element wire over one native WS; no browser/UI claim.',
         'server_command': COMMAND, 'server_cleanup': 'caller-owned' if COMMAND is None else 'collector-owned',
         'url': URL, 'frames': [], 'elements': [], 'finishes': []}
SERVER = WS = None


def save():
    (OUT / 'trace.json').write_text(json.dumps(TRACE, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def record(direction, raw, message):
    TRACE['frames'].append({'direction': direction, 'bytes': len(raw), 'base64': base64.b64encode(raw).decode(),
                            'message': MessageToDict(message, preserving_proto_field_name=True)})


def record_element(element, transient):
    inner = element.WhichOneof('type')
    if inner is None:
        return
    view = getattr(element, inner)
    fields = MessageToDict(view, preserving_proto_field_name=True)
    if inner == 'markdown':
        fields.pop('body', None)
        fields['body_sha16'] = hashlib.sha256(view.body.encode()).hexdigest()[:16]
    TRACE['elements'].append({'kind': inner, 'transient': transient, 'fields': fields})


def note(message, path=None):
    delta = message.delta
    kind = delta.WhichOneof('type')
    if kind == 'new_element':
        record_element(delta.new_element, transient=False)
    elif kind == 'new_transient':
        for element in delta.new_transient.elements:
            record_element(element, transient=True)
    elif kind == 'add_block':
        block = delta.add_block
        allowed = block.WhichOneof('type')
        if allowed is None:
            return
        view = getattr(block, allowed)
        fields = MessageToDict(view, preserving_proto_field_name=True)
        block_level = {}
        if block.id:
            block_level['id'] = block.id
        if block.HasField('width_config'):
            block_level['width_config'] = MessageToDict(block.width_config, preserving_proto_field_name=True)
        if block.HasField('height_config'):
            block_level['height_config'] = MessageToDict(block.height_config, preserving_proto_field_name=True)
        TRACE['elements'].append({'kind': f'add_block:{allowed}', 'transient': False,
                                  'fields': fields, 'block': block_level,
                                  'delta_path': list(message.metadata.delta_path) if message.metadata else []})


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
    request = BackMsg()
    request.rerun_script.SetInParent()
    raw = request.SerializeToString()
    record('client->server', raw, request)
    WS.send(raw)
    while True:
        raw = WS.recv(timeout=20)
        message = ForwardMsg()
        message.ParseFromString(raw)
        record('server->client', raw, message)
        kind = message.WhichOneof('type')
        if kind == 'script_finished':
            TRACE['finishes'].append(message.script_finished)
            break
        if kind == 'delta':
            note(message)
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
