"""One owned Python 1.66.1 native WS zero-column public behavior capture."""
import argparse
import base64
from datetime import datetime,timezone
from importlib.metadata import version
import json
from pathlib import Path
import socket
import subprocess
import sys
import time
import urllib.request
import pyarrow as pa
from google.protobuf.json_format import MessageToDict
from streamlit.proto.BackMsg_pb2 import BackMsg
from streamlit.proto.ForwardMsg_pb2 import ForwardMsg
from websockets.sync.client import connect

ROOT=Path(__file__).resolve().parents[2]
parser=argparse.ArgumentParser(description='Collect only new zero-column reference scenarios; never overwrite an existing trace.')
parser.add_argument('--out',type=Path,required=True)
parser.add_argument('--inputs',type=Path,default=ROOT/'tests/reference/reference-browser/zero-columns/primary/inputs.json')
args=parser.parse_args()
OUT=args.out.resolve()
OUT.mkdir(parents=True,exist_ok=True)
assert not (OUT/'trace.json').exists(), 'one capture, retain first result'
assert version('streamlit')=='1.66.1'
input_path=args.inputs.resolve()
input_bytes=input_path.read_bytes()
INPUTS=json.loads(input_bytes)
(OUT/'inputs.json').write_bytes(input_bytes)
with socket.socket() as listener:
    listener.bind(('127.0.0.1',0))
    PORT=listener.getsockname()[1]
URL=f'http://127.0.0.1:{PORT}'
COMMAND=[sys.executable,'-B','-m','streamlit','run',str(ROOT/'tests/reference/zero_columns_app.py'),'--server.address=127.0.0.1',f'--server.port={PORT}',
         '--server.headless=true','--server.fileWatcherType=none','--browser.gatherUsageStats=false','--','--inputs',str(OUT/'inputs.json')]
TRACE={'schema_version':1,'runtime':'python','reference_version':'1.66.1','versions':{name:version(name) for name in ('streamlit','pandas','pyarrow')},
       'captured_at_utc':datetime.now(timezone.utc).isoformat(),'scope':'Actual public zero-column dataframe/data_editor/table returns plus native WS Arrow IPC; no browser/UI claim.',
       'server_command':COMMAND,'url':URL,'security_cli_overrides':[],'browser':None,'inputs_file':'inputs.json','frames':[],'cases':[],
       'runs':[],'finishes':[],'unhandled_exceptions':[]}
SERVER=WS=None


def save():
    (OUT/'trace.json').write_text(json.dumps(TRACE,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')


def record(direction,raw,message):
    TRACE['frames'].append({'direction':direction,'bytes':len(raw),'base64':base64.b64encode(raw).decode(),
                            'message':MessageToDict(message,preserving_proto_field_name=True)})


try:
    with (OUT/'server.log').open('w',encoding='utf-8') as server_log:
        SERVER=subprocess.Popen(COMMAND,cwd=ROOT,stdout=server_log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
        TRACE['server_pid']=SERVER.pid
        deadline=time.monotonic()+25
        while True:
            try:
                with urllib.request.urlopen(URL+'/_stcore/health',timeout=1) as response:
                    TRACE['health']={'method':'GET','path':'/_stcore/health','status':response.status,'headers':list(response.headers.items()),
                                     'body_base64':base64.b64encode(response.read()).decode()}
                break
            except OSError:
                if time.monotonic()>deadline or SERVER.poll() is not None:
                    raise RuntimeError('owned Python server failed to start')
                time.sleep(0.1)
        WS=connect(f'ws://127.0.0.1:{PORT}/_stcore/stream',origin=URL,subprotocols=['streamlit'],proxy=None,
                   open_timeout=10,close_timeout=5,max_size=None,legacy=True)
        TRACE['handshake']={'status':WS.response.status_code,'headers':list(WS.response.headers.raw_items()),'subprotocol':WS.subprotocol}
        request=BackMsg()
        request.rerun_script.SetInParent()
        raw=request.SerializeToString()
        record('client->server',raw,request)
        WS.send(raw)
        finished=False
        current=None
        while True:
            raw=WS.recv(timeout=20)
            if not isinstance(raw,bytes):
                raise RuntimeError('expected binary ForwardMsg')
            message=ForwardMsg()
            message.ParseFromString(raw)
            record('server->client',raw,message)
            kind=message.WhichOneof('type')
            if kind=='new_session':
                TRACE['runs'].append(MessageToDict(message.new_session,preserving_proto_field_name=True))
            if kind=='delta' and message.delta.WhichOneof('type')=='new_element':
                element=message.delta.new_element
                element_kind=element.WhichOneof('type')
                if element_kind=='markdown' and element.markdown.body.startswith('zero-case='):
                    label=element.markdown.body.removeprefix('zero-case=')
                    current={'label':label,('tables' if label.endswith('/table-index') else 'dataframes'):[],'report':None}
                    TRACE['cases'].append(current)
                elif element_kind in ('dataframe','table'):
                    if current is None:
                        raise RuntimeError('dataframe emitted before its explicit case marker')
                    frame=getattr(element,element_kind)
                    fields=MessageToDict(frame,preserving_proto_field_name=True)
                    fields.pop('arrow_data',None)
                    ipc=frame.arrow_data.data
                    observed={'frame_index':len(TRACE['frames'])-1,'delta_path':list(message.metadata.delta_path),'fields':fields,
                              'arrow_ipc_base64':base64.b64encode(ipc).decode(),'arrow_ipc_bytes':len(ipc)}
                    try:
                        table=pa.ipc.open_stream(ipc).read_all()
                        observed.update(num_rows=table.num_rows,num_columns=table.num_columns,rows=table.to_pylist(),
                                        schema={'fields':[{'name':field.name,'type':str(field.type),'nullable':field.nullable} for field in table.schema],
                                                'metadata':[{'key_base64':base64.b64encode(key).decode(),'value_base64':base64.b64encode(value).decode()}
                                                            for key,value in (table.schema.metadata or {}).items()]})
                    except Exception as error:
                        observed.update(ipc_parse_exception_type=type(error).__name__,ipc_parse_exception_message=str(error))
                    current['tables' if element_kind=='table' else 'dataframes'].append(observed)
                    (OUT/(current['label'].replace('/','--')+'.arrow')).write_bytes(ipc)
                elif element_kind=='code':
                    report=json.loads(element.code.code_text)
                    if current is None or current['label']!=report['label']:
                        raise RuntimeError('public return report is not paired to its actual case')
                    current['report']=report
                    print(report['label'],json.dumps({'input_shape':[report['input_before'].get('num_rows'),report['input_before'].get('num_columns')],
                          'outcome':report['outcome'],'returned':report.get('returned'),'exception_type':report.get('exception_type'),
                          'wire_shapes':[[frame.get('num_rows'),frame.get('num_columns')] for frame in current.get('dataframes',current.get('tables',[]))],
                          'input_unchanged':report['caller_input_unchanged']}),flush=True)
                elif element_kind=='exception':
                    TRACE['unhandled_exceptions'].append(MessageToDict(element.exception,preserving_proto_field_name=True))
            if kind=='script_finished':
                TRACE['finishes'].append(message.script_finished)
                finished=True
            if kind=='session_status_changed' and finished and not message.session_status_changed.script_is_running:
                break
        TRACE['completed_cases']=len(TRACE['cases'])
        save()
        if len(TRACE['cases'])!=len(INPUTS['cases']) or any(case['report'] is None for case in TRACE['cases']):
            raise RuntimeError('public app did not complete all new cases')
except Exception as error:
    TRACE['producer_error']=f'{type(error).__name__}: {error}'
    raise
finally:
    errors=[]
    def attempt(step,action):
        try:
            return True,action()
        except Exception as error:
            errors.append({'step':step,'error':f'{type(error).__name__}: {error}'})
            return False,None
    if WS is not None:
        attempt('websocket.close',WS.close)
    if SERVER is not None and SERVER.poll() is None:
        attempt('owned_tree.taskkill',lambda:subprocess.run(['taskkill','/PID',str(SERVER.pid),'/T','/F'],check=True,
                 stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=10,creationflags=subprocess.CREATE_NO_WINDOW))
    if SERVER is not None:
        waited,_=attempt('server.wait',lambda:SERVER.wait(timeout=10))
        if not waited:
            attempt('server.kill',SERVER.kill)
            attempt('server.wait_after_kill',lambda:SERVER.wait(timeout=10))
    listeners=subprocess.run(['powershell.exe','-NoProfile','-Command',f'@(Get-NetTCPConnection -State Listen -LocalPort {PORT} -ErrorAction SilentlyContinue).Count'],
                             capture_output=True,text=True,timeout=10,creationflags=subprocess.CREATE_NO_WINDOW)
    TRACE['cleanup']={'websocket_closed':WS is None or WS.state.name=='CLOSED','close_code':None if WS is None else WS.close_code,
                      'server_stopped':SERVER is None or SERVER.poll() is not None,'listener_count':listeners.stdout.strip(),
                      'listener_check_exit_code':listeners.returncode,'browser_started':False}
    TRACE['cleanup_errors']=errors
    save()
    compact={'schema_version':1,'reference_version':'1.66.1','versions':TRACE['versions'],'scope':TRACE['scope'],'raw_file':'trace.json','inputs_file':'inputs.json',
             'cases':TRACE['cases'],'finishes':TRACE['finishes'],'unhandled_exceptions':TRACE['unhandled_exceptions'],
             'cleanup':TRACE['cleanup'],'cleanup_errors':errors}
    (OUT/'zero-column-cases.json').write_text(json.dumps(compact,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    if errors or not TRACE['cleanup']['websocket_closed'] or not TRACE['cleanup']['server_stopped'] or listeners.stdout.strip()!='0':
        raise RuntimeError('owned-resource cleanup not fully confirmed')
