"""One owned Python 1.66.1 st.context capture through the REAL frontend.

The native-WS reference (context-headers) showed url/locale/timezone/theme
empty because they come from the browser session. This collector loads the
same echo app in a real Chrome and records every wire frame plus the rendered
report, measuring exactly what the official frontend supplies.
"""
import argparse
import base64
from datetime import datetime, timezone
import importlib.metadata
import json
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import time
import urllib.request

from google.protobuf.json_format import MessageToDict
from streamlit.proto.BackMsg_pb2 import BackMsg
from streamlit.proto.ForwardMsg_pb2 import ForwardMsg

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "tests/browser"), str(ROOT / "tests/reference")]
from componentv2_state_capture import Recorder, free_port
from componenttrigger_capture import CHROME_CANDIDATES, evaluate, http_json

parser = argparse.ArgumentParser(description='Collect the browser-path st.context reference once; never overwrite.')
parser.add_argument('--out', type=Path, required=True)
args = parser.parse_args()
OUT = args.out.resolve()
OUT.mkdir(parents=True, exist_ok=True)
assert not (OUT / 'trace.json').exists(), 'one capture, retain first result'
assert importlib.metadata.version('streamlit') == '1.66.1'

with socket.socket() as listener:
    listener.bind(('127.0.0.1', 0))
    PORT = listener.getsockname()[1]
URL = f'http://127.0.0.1:{PORT}/?embed=true&m4=browser'
COMMAND = [sys.executable, '-B', '-m', 'streamlit', 'run', str(ROOT / 'tests/reference/context_app.py'),
           '--server.address=127.0.0.1', f'--server.port={PORT}', '--server.headless=true',
           '--server.fileWatcherType=none', '--browser.gatherUsageStats=false']
TRACE = {'schema_version': 1, 'runtime': 'python', 'reference_version': '1.66.1',
         'captured_at_utc': datetime.now(timezone.utc).isoformat(),
         'scope': 'Actual st.context reflection through the official frontend in a real Chrome; one load.',
         'server_command': COMMAND, 'url': URL, 'frames': [], 'report': None}
SERVER = CHROME = RECORDER = None


def record(direction, raw, message):
    TRACE['frames'].append({'direction': direction, 'bytes': len(raw), 'base64': base64.b64encode(raw).decode(),
                            'message': MessageToDict(message, preserving_proto_field_name=True)})


try:
    with (OUT / 'server.log').open('w', encoding='utf-8') as server_log:
        SERVER = subprocess.Popen(COMMAND, cwd=ROOT, stdout=server_log, stderr=subprocess.STDOUT,
                                  creationflags=subprocess.CREATE_NO_WINDOW)
        deadline = time.monotonic() + 25
        while True:
            try:
                with urllib.request.urlopen(URL.split('?')[0].rstrip('/') + '/_stcore/health', timeout=1) as response:
                    TRACE['health'] = {'status': response.status, 'body': response.read().decode()}
                break
            except OSError:
                if time.monotonic() > deadline or SERVER.poll() is not None:
                    raise RuntimeError('owned Python server failed to start')
                time.sleep(0.1)
        profile = (OUT / 'chrome-profile').resolve()
        profile.mkdir()
        chrome_path = next(path for path in CHROME_CANDIDATES if Path(path).is_file())
        chrome_port = free_port()
        CHROME = subprocess.Popen([chrome_path, '--headless=new', '--disable-gpu', f'--remote-debugging-port={chrome_port}',
                                   f'--user-data-dir={profile}', '--no-first-run', '--no-default-browser-check', 'about:blank'],
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=subprocess.CREATE_NO_WINDOW)
        time.sleep(2.5)
        assert CHROME.poll() is None, 'owned Chrome failed to start'
        target = http_json(f"http://127.0.0.1:{chrome_port}/json/new?about:blank", method="PUT")
        RECORDER = Recorder(target["webSocketDebuggerUrl"])
        RECORDER.start()
        RECORDER.call("Network.enable")
        RECORDER.call("Page.navigate", {"url": URL})
        deadline = time.monotonic() + 15
        while True:
            code = evaluate(RECORDER, "document.querySelector('[data-testid=stCode]')?.innerText || ''")
            if code.strip().startswith('{'):
                break
            if time.monotonic() > deadline:
                raise RuntimeError('context report never rendered')
            time.sleep(0.3)
        TRACE['report'] = json.loads(code)
        TRACE['dom'] = {'code_text': code, 'exceptions': evaluate(RECORDER, "JSON.stringify([...document.querySelectorAll('[data-testid=stException]')].map(e=>e.innerText))")}
        png = RECORDER.call("Page.captureScreenshot", {"format": "png"})["result"]["data"]
        (OUT / 'page.png').write_bytes(base64.b64decode(png))
        for event in RECORDER.take():
            method = event.get('method')
            if method == 'Network.webSocketFrameSent':
                payload = event['params']['response']['payloadData']
                try:
                    raw = base64.b64decode(payload)
                except Exception:
                    continue
                message = BackMsg()
                if message.ParseFromString(raw) and message.WhichOneof('type'):
                    record('client->server', raw, message)
            elif method == 'Network.webSocketFrameReceived':
                payload = event['params']['response']['payloadData']
                try:
                    raw = base64.b64decode(payload)
                except Exception:
                    continue
                message = ForwardMsg()
                if message.ParseFromString(raw) and message.WhichOneof('type'):
                    record('server->client', raw, message)
        TRACE['successful'] = True
except Exception as error:
    TRACE['producer_error'] = f'{type(error).__name__}: {error}'
    raise
finally:
    if RECORDER is not None:
        RECORDER.stop()
    if CHROME is not None:
        CHROME.terminate()
        CHROME.wait()
    profile = OUT / 'chrome-profile'
    if profile.exists():
        shutil.rmtree(profile, ignore_errors=True)
        TRACE['profile_cleaned'] = not profile.exists()
    if SERVER is not None:
        SERVER.terminate()
        SERVER.wait(timeout=10)
        TRACE['server_stopped'] = True
    (OUT / 'trace.json').write_text(json.dumps(TRACE, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
