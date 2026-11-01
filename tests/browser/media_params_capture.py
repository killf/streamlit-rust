"""One owned protocol capture of audio/video parameter variants (python/rust).

A native WebSocket against the pinned 1.66.1 server (or a caller-owned Rust
server): the six element emissions are recorded frame by frame and the
audio/video element fields summarized per case; never overwrites a trace.
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
parser = argparse.ArgumentParser(description='Collect the media-parameter reference once; never overwrite.')
parser.add_argument('--out', type=Path, required=True)
parser.add_argument('--http-head', action='store_true', help='capture raw GET/HEAD Range and If-Range responses for emitted audio/video/subtitle assets')
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
    COMMAND = [sys.executable, '-B', '-m', 'streamlit', 'run', str(ROOT / 'tests/reference/media_params_app.py'),
               '--server.address=127.0.0.1', f'--server.port={PORT}', '--server.headless=true',
               '--server.fileWatcherType=none', '--browser.gatherUsageStats=false']
TRACE = {'schema_version': 1, 'runtime': 'rust' if args.url else 'python', 'reference_version': '1.66.1',
         'captured_at_utc': datetime.now(timezone.utc).isoformat(),
         'scope': 'Element wire of six audio/video parameter variants over one native WS; no browser/UI claim.',
         'server_command': COMMAND, 'server_cleanup': 'caller-owned' if COMMAND is None else 'collector-owned',
         'url': URL, 'frames': [], 'elements': [], 'finishes': []}
if args.http_head:
    TRACE['scope'] = 'Public audio/video/subtitle URLs linked to raw GET/HEAD, Range and If-Range responses; no browser playback claim.'
    TRACE['producer_sources_sha256'] = {path:hashlib.sha256((ROOT/path).read_bytes()).hexdigest() for path in ('streamlit/examples/media_params.rs','tests/reference/media_params_app.py','tests/browser/media_params_capture.py')}
SERVER = WS = None


def save():
    (OUT / 'trace.json').write_text(json.dumps(TRACE, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')


def record(direction, raw, message):
    TRACE['frames'].append({'direction': direction, 'bytes': len(raw), 'base64': base64.b64encode(raw).decode(),
                            'message': MessageToDict(message, preserving_proto_field_name=True)})


def http_response(method, path, headers):
    authority=URL.removeprefix('http://')
    host,port=authority.rsplit(':',1)
    raw=(method+' '+path+' HTTP/1.1\r\nHost: '+authority+'\r\nConnection: close\r\n'+''.join(name+': '+value+'\r\n' for name,value in headers.items())+'\r\n').encode('ascii')
    with socket.create_connection((host,int(port)),timeout=10) as connection:
        connection.sendall(raw);parts=[]
        while chunk:=connection.recv(65536):parts.append(chunk)
    response=b''.join(parts);header,body=response.split(b'\r\n\r\n',1)
    lines=header.decode('iso-8859-1').split('\r\n')
    fields={name.lower():value.strip() for name,value in (line.split(':',1) for line in lines[1:])}
    return {'method':method,'url':path,'request_headers':headers,'request_bytes':len(raw),'request_base64':base64.b64encode(raw).decode(),
            'status':int(lines[0].split(' ')[1]),'headers':fields,'response_bytes':len(response),'response_base64':base64.b64encode(response).decode(),
            'body_base64':base64.b64encode(body).decode(),'body_bytes':len(body)}


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
        if kind == 'delta' and message.delta.WhichOneof('type') == 'new_element':
            element = message.delta.new_element
            element_kind = element.WhichOneof('type')
            if element_kind in ('audio', 'video'):
                view = getattr(element, element_kind)
                fields = MessageToDict(view, preserving_proto_field_name=True)
                fields.pop('url', None)
                TRACE['elements'].append({'index': index, 'kind': element_kind, 'fields': fields,
                                          'url': view.url, 'delta_path': list(message.metadata.delta_path)})
                index += 1
    if args.http_head:
        elements=TRACE['elements'];assert len(elements)==6
        TRACE['http_assets']=[{'name':name,'element_index':index,'url':elements[index]['url']} for name,index in (('audio',0),('audio-bare',2),('video',3))]
        track=elements[5]['fields']['subtitles'][0];assert track['label']=='en'
        TRACE['http_assets'].append({'name':'subtitle','element_index':5,'label':track['label'],'url':track['url']})
        TRACE['http_responses']=[]
        for asset in TRACE['http_assets']:
            for headers in ({},{'Range':'bytes=0-3'},{'Range':'bytes=-4'},{'Range':'bytes=9999999-'},
                            {'Range':'bytes=0-3','If-Range':'"mismatch"'},{'Range':'bytes=0-3','If-Range':'Thu, 01 Jan 1970 00:00:00 GMT'}):
                for method in ('GET','HEAD'):
                    TRACE['http_responses'].append({'asset':asset['name'],**http_response(method,asset['url'],headers)})
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
