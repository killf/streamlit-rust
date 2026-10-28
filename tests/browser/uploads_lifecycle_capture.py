"""One owned protocol capture of upload concurrency and session-expiry (python).

Against a pinned 1.66.1 server with --server.disconnectedSessionTTL=3:
A) two concurrent PUTs to distinct URLs, B) two concurrent PUTs racing on one
URL (both statuses plus the surviving content read back through the widget),
C) PUT and DELETE to a live URL after the socket dropped and the retention
TTL elapsed, D) an unknown-session PUT control. Every HTTP exchange and WS
frame is recorded verbatim; never overwrites an existing trace.
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
import threading
import time
import urllib.error
import urllib.request

from google.protobuf.json_format import MessageToDict
from streamlit.proto.BackMsg_pb2 import BackMsg
from streamlit.proto.ForwardMsg_pb2 import ForwardMsg
from websockets.sync.client import connect

ROOT = Path(__file__).resolve().parents[2]
parser = argparse.ArgumentParser(description='Collect the upload lifecycle reference once; never overwrite.')
parser.add_argument('--out', type=Path, required=True)
parser.add_argument('--url', help='caller-owned Rust server URL (comparison capture)')
args = parser.parse_args()
OUT = args.out.resolve()
OUT.mkdir(parents=True, exist_ok=True)
assert not (OUT / 'trace.json').exists(), 'one capture, retain first result'
assert importlib.metadata.version('streamlit') == '1.66.1'

TTL_SECONDS = 3
GAMMA_A = b'gamma-version-A'
GAMMA_B = b'gamma-version-B-longer'

with socket.socket() as listener:
    listener.bind(('127.0.0.1', 0))
    PORT = listener.getsockname()[1]
URL = f'http://127.0.0.1:{PORT}'
COMMAND = [sys.executable, '-B', '-m', 'streamlit', 'run', str(ROOT / 'tests/reference/uploads_multi_app.py'),
           '--server.address=127.0.0.1', f'--server.port={PORT}', '--server.headless=true',
           '--server.fileWatcherType=none', '--browser.gatherUsageStats=false',
           f'--server.disconnectedSessionTTL={TTL_SECONDS}']
TRACE = {'schema_version': 1, 'runtime': 'python', 'reference_version': '1.66.1',
         'captured_at_utc': datetime.now(timezone.utc).isoformat(),
         'scope': 'Actual upload concurrency and disconnected-session expiry over native WS + HTTP with a 3s TTL; no browser claim.',
         'server_command': COMMAND, 'url': URL, 'ttl_seconds': TTL_SECONDS,
         'frames': [], 'http': [], 'stages': {}}
SERVER = WS = None


def save():
    (OUT / 'trace.json').write_text(json.dumps(TRACE, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def record(direction, raw, message):
    TRACE['frames'].append({'direction': direction, 'bytes': len(raw), 'base64': base64.b64encode(raw).decode(),
                            'message': MessageToDict(message, preserving_proto_field_name=True)})


def http_exchange(label, method, url, name, body):
    payload = b'--probe\r\nContent-Disposition: form-data; name="file"; filename="' + name.encode() + b'"\r\nContent-Type: application/octet-stream\r\n\r\n' + body + b'\r\n--probe--\r\n'
    request = urllib.request.Request(url, data=(payload if method == 'PUT' else None), method=method)
    if method == 'PUT':
        request.add_header('Content-Type', 'multipart/form-data; boundary=probe')
    request.add_header('Cookie', f'_streamlit_xsrf={TOKEN[0]}')
    request.add_header('X-Xsrftoken', TOKEN[0])
    started = time.monotonic()
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            status = response.status
    except urllib.error.HTTPError as error:
        status = error.code
    entry = {'label': label, 'method': method, 'path': url.split('/_stcore')[-1], 'status': status,
             'elapsed_ms': round((time.monotonic() - started) * 1000, 1)}
    TRACE['http'].append(entry)
    return status


try:
    SERVER = subprocess.Popen(COMMAND, cwd=ROOT, stdout=(OUT / 'server.log').open('w', encoding='utf-8'),
                              stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW)
    TRACE['server_pid'] = SERVER.pid
    deadline = time.monotonic() + 25
    while True:
        try:
            with urllib.request.urlopen(URL + '/_stcore/health', timeout=1) as response:
                TRACE['health'] = {'status': response.status, 'body': response.read().decode()}
                TRACE['health']['set_cookie'] = response.headers.get('Set-Cookie', '')
            break
        except OSError:
            if time.monotonic() > deadline or SERVER.poll() is not None:
                raise RuntimeError('owned Python server failed to start')
            time.sleep(0.1)
    TOKEN = [TRACE['health']['set_cookie'].split('_streamlit_xsrf=')[1].split(';')[0]]

    WS = connect(f'ws://127.0.0.1:{PORT}/_stcore/stream', origin=URL, subprotocols=['streamlit'], proxy=None,
                 open_timeout=10, close_timeout=5, max_size=None, legacy=True)
    TRACE['handshake'] = {'status': WS.response.status_code, 'subprotocol': WS.subprotocol}
    request = BackMsg()
    request.rerun_script.SetInParent()
    raw = request.SerializeToString()
    record('client->server', raw, request)
    WS.send(raw)
    widget = session = None
    while True:
        raw = WS.recv(timeout=20)
        message = ForwardMsg()
        message.ParseFromString(raw)
        record('server->client', raw, message)
        kind = message.WhichOneof('type')
        if kind == 'new_session':
            session = message.new_session.initialize.session_id
        if kind == 'delta' and message.delta.WhichOneof('type') == 'new_element':
            element = message.delta.new_element
            if element.WhichOneof('type') == 'file_uploader':
                widget = element.file_uploader.id
        if kind == 'script_finished':
            break
    assert widget and session, 'uploader widget and session must render'

    request = BackMsg()
    request.file_urls_request.request_id = 'lifecycle'
    for name in ('alpha.txt', 'beta.csv', 'gamma.bin'):
        request.file_urls_request.file_names.append(name)
    request.file_urls_request.session_id = session
    raw = request.SerializeToString()
    record('client->server', raw, request)
    WS.send(raw)
    urls = {}
    while True:
        raw = WS.recv(timeout=20)
        message = ForwardMsg()
        message.ParseFromString(raw)
        record('server->client', raw, message)
        if message.WhichOneof('type') == 'file_urls_response':
            for entry in message.file_urls_response.file_urls:
                urls[entry.file_id] = URL + entry.upload_url
            break
    assert len(urls) == 3
    alpha, beta, gamma = urls, urls, urls
    ids = list(urls)

    # A) concurrent PUTs to distinct URLs.
    statuses = {}
    def distinct(key, file_id, name, body):
        statuses[key] = http_exchange(f'concurrent-distinct-{key}', 'PUT', urls[file_id], name, body)
    threads = [threading.Thread(target=distinct, args=('alpha', ids[0], 'alpha.txt', b'content-alpha')),
               threading.Thread(target=distinct, args=('beta', ids[1], 'beta.csv', b'content-beta'))]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    TRACE['stages']['concurrent_distinct'] = dict(statuses)

    # B) concurrent PUTs racing on one URL; then read the surviving content.
    race = {}
    def racer(key, body):
        race[key] = http_exchange(f'concurrent-same-{key}', 'PUT', urls[ids[2]], 'gamma.bin', body)
    threads = [threading.Thread(target=racer, args=('A', GAMMA_A)),
               threading.Thread(target=racer, args=('B', GAMMA_B))]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    TRACE['stages']['concurrent_same_url'] = dict(race)
    request = BackMsg()
    state = request.rerun_script.widget_states.widgets.add()
    state.id = widget
    info = state.file_uploader_state_value.uploaded_file_info.add()
    info.name = 'gamma.bin'
    info.size = len(GAMMA_B)
    info.file_id = ids[2]
    raw = request.SerializeToString()
    record('client->server', raw, request)
    WS.send(raw)
    while True:
        raw = WS.recv(timeout=20)
        message = ForwardMsg()
        message.ParseFromString(raw)
        record('server->client', raw, message)
        kind = message.WhichOneof('type')
        if kind == 'delta' and message.delta.WhichOneof('type') == 'new_element':
            element = message.delta.new_element
            if element.WhichOneof('type') == 'code':
                report = json.loads(element.code.code_text)
                TRACE['stages']['surviving_content'] = report
                break
        if kind == 'script_finished':
            break

    # C) expiry: drop the socket, outlive the TTL, then PUT and DELETE.
    WS.close()
    time.sleep(TTL_SECONDS + 2)
    TRACE['stages']['after_expiry_put'] = http_exchange('after-expiry-put', 'PUT', urls[ids[0]], 'alpha.txt', b'after-expiry')
    TRACE['stages']['after_expiry_delete'] = http_exchange('after-expiry-delete', 'DELETE', urls[ids[0]], 'alpha.txt', b'')

    # D) unknown-session PUT control.
    TRACE['stages']['unknown_session_put'] = http_exchange(
        'unknown-session-put', 'PUT', URL + '/_stcore/upload_file/00000000-0000-0000-0000-000000000000/00000000-0000-0000-0000-000000000000', 'x.txt', b'x')

    TRACE['cleanup'] = {'server_stopped': True}
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
