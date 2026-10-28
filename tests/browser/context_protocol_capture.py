"""One owned Python 1.66.1 st.context protocol capture with fixed probe headers.

Connects a native WebSocket carrying deterministic probe headers and records
the echoed st.context report plus every ForwardMsg; never overwrites an
existing trace.
"""
import argparse
import base64
from datetime import datetime, timezone
from importlib.metadata import version
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
parser = argparse.ArgumentParser(description='Collect the st.context reference once; never overwrite an existing trace.')
parser.add_argument('--out', type=Path, required=True)
args = parser.parse_args()
OUT = args.out.resolve()
OUT.mkdir(parents=True, exist_ok=True)
assert not (OUT / 'trace.json').exists(), 'one capture, retain first result'
assert version('streamlit') == '1.66.1'

PROBE_HEADERS = {'User-Agent': 'M4ContextProbe/1.0', 'X-M4-Probe': 'alpha', 'Accept-Language': 'zh-CN,zh;q=0.9'}
with socket.socket() as listener:
    listener.bind(('127.0.0.1', 0))
    PORT = listener.getsockname()[1]
URL = f'http://127.0.0.1:{PORT}'
COMMAND = [sys.executable, '-B', '-m', 'streamlit', 'run', str(ROOT / 'tests/reference/context_app.py'),
           '--server.address=127.0.0.1', f'--server.port={PORT}', '--server.headless=true',
           '--server.fileWatcherType=none', '--browser.gatherUsageStats=false']
TRACE = {'schema_version': 1, 'runtime': 'python', 'reference_version': '1.66.1',
         'versions': {name: version(name) for name in ('streamlit',)},
         'captured_at_utc': datetime.now(timezone.utc).isoformat(),
         'scope': 'Actual public st.context reflection over one native WS connection with fixed probe headers; no browser/UI claim.',
         'server_command': COMMAND, 'url': URL, 'probe_headers': PROBE_HEADERS,
         'frames': [], 'runs': [], 'finishes': [], 'unhandled_exceptions': [], 'report': None}
SERVER = WS = None


def save():
    (OUT / 'trace.json').write_text(json.dumps(TRACE, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def record(direction, raw, message):
    TRACE['frames'].append({'direction': direction, 'bytes': len(raw), 'base64': base64.b64encode(raw).decode(),
                            'message': MessageToDict(message, preserving_proto_field_name=True)})


try:
    with (OUT / 'server.log').open('w', encoding='utf-8') as server_log:
        SERVER = subprocess.Popen(COMMAND, cwd=ROOT, stdout=server_log, stderr=subprocess.STDOUT,
                                  creationflags=subprocess.CREATE_NO_WINDOW)
        TRACE['server_pid'] = SERVER.pid
        deadline = time.monotonic() + 25
        while True:
            try:
                with urllib.request.urlopen(URL + '/_stcore/health', timeout=1) as response:
                    TRACE['health'] = {'status': response.status, 'body': response.read().decode()}
                break
            except OSError:
                if time.monotonic() > deadline or SERVER.poll() is not None:
                    raise RuntimeError('owned Python server failed to start')
                time.sleep(0.1)
        WS = connect(f'ws://127.0.0.1:{PORT}/_stcore/stream', origin=URL, subprotocols=['streamlit'], proxy=None,
                     open_timeout=10, close_timeout=5, max_size=None, additional_headers=PROBE_HEADERS)
        TRACE['handshake'] = {'status': WS.response.status_code, 'subprotocol': WS.subprotocol,
                              'headers': list(WS.response.headers.items())}
        request = BackMsg()
        request.rerun_script.SetInParent()
        raw = request.SerializeToString()
        record('client->server', raw, request)
        WS.send(raw)
        while True:
            raw = WS.recv(timeout=20)
            if not isinstance(raw, bytes):
                raise RuntimeError('expected binary ForwardMsg')
            message = ForwardMsg()
            message.ParseFromString(raw)
            record('server->client', raw, message)
            kind = message.WhichOneof('type')
            if kind == 'new_session':
                TRACE['runs'].append(MessageToDict(message.new_session, preserving_proto_field_name=True))
            if kind == 'script_finished':
                TRACE['finishes'].append(message.script_finished)
                break
            if kind == 'delta' and message.delta.WhichOneof('type') == 'new_element':
                element = message.delta.new_element
                if element.WhichOneof('type') == 'code':
                    TRACE['report'] = json.loads(element.code.code_text)
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
            if message.WhichOneof('type') == 'script_finished':
                TRACE['finishes'].append(message.script_finished)
                break
        TRACE['cleanup'] = {'websocket_closed': True}
        WS.close()
        TRACE['cleanup']['close_code'] = WS.protocol.close_rcvd.code if WS.protocol.close_rcvd else None
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
        try:
            SERVER.terminate()
            SERVER.wait(timeout=10)
            TRACE['cleanup'] = TRACE.get('cleanup', {}) | {'server_stopped': True}
        except Exception:
            TRACE.setdefault('cleanup_errors', []).append('server stop failed')
    save()
