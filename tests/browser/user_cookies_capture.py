"""One owned capture of the unauthenticated st.user / st.context.cookies surface.

A native WebSocket carrying two probe cookies against the pinned 1.66.1
server; the echoed report and every frame are frozen verbatim. Python 1.66.1
has no local authenticator, so the authenticated path has no oracle — this
reference pins the anonymous baseline and the cookie parsing.
"""
import argparse
import base64
from datetime import datetime, timezone
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
parser = argparse.ArgumentParser(description='Collect the user/cookies reference once; never overwrite.')
parser.add_argument('--out', type=Path, required=True)
parser.add_argument('--url', help='caller-owned Rust server URL (comparison capture)')
args = parser.parse_args()
OUT = args.out.resolve()
OUT.mkdir(parents=True, exist_ok=True)
assert not (OUT / 'trace.json').exists(), 'one capture, retain first result'
assert importlib.metadata.version('streamlit') == '1.66.1'

PROBE_COOKIES = 'probe-flavor=oat; probe-session=42'
COMMAND = None
if args.url:
    URL = args.url.rstrip('/')
else:
    with socket.socket() as listener:
        listener.bind(('127.0.0.1', 0))
        PORT = listener.getsockname()[1]
    URL = f'http://127.0.0.1:{PORT}'
    COMMAND = [sys.executable, '-B', '-m', 'streamlit', 'run', str(ROOT / 'tests/reference/user_cookies_app.py'),
               '--server.address=127.0.0.1', f'--server.port={PORT}', '--server.headless=true',
               '--server.fileWatcherType=none', '--browser.gatherUsageStats=false']
TRACE = {'schema_version': 1, 'runtime': 'rust' if args.url else 'python', 'reference_version': '1.66.1',
         'captured_at_utc': datetime.now(timezone.utc).isoformat(),
         'scope': 'Anonymous st.user mapping and st.context.cookies parsing over one native WS with probe cookies; no authenticated oracle exists in 1.66.1.',
         'server_command': COMMAND, 'server_cleanup': 'caller-owned' if COMMAND is None else 'collector-owned', 'url': URL, 'probe_cookies': PROBE_COOKIES,
         'frames': [], 'runs': [], 'finishes': [], 'report': None}
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
                 open_timeout=10, close_timeout=5, max_size=None, legacy=True,
                 additional_headers={'Cookie': PROBE_COOKIES, 'User-Agent': 'UserProbe/1.0'})
    TRACE['handshake'] = {'status': WS.response.status_code, 'subprotocol': WS.subprotocol}
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
        if kind == 'new_session':
            TRACE['runs'].append(MessageToDict(message.new_session, preserving_proto_field_name=True))
        if kind == 'script_finished':
            TRACE['finishes'].append(message.script_finished)
            break
        if kind == 'delta' and message.delta.WhichOneof('type') == 'new_element':
            element = message.delta.new_element
            if element.WhichOneof('type') == 'code':
                TRACE['report'] = json.loads(element.code.code_text)
    WS.close()
    TRACE['cleanup'] = {'websocket_closed': True, 'server_stopped': True}
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
    save()
