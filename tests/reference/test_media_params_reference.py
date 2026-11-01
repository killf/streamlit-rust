"""Frozen media playback-parameter evidence (python reference + rust browser)."""
import base64
import hashlib
import json
import io
import wave

import pytest
from pathlib import Path

from google.protobuf.json_format import MessageToDict
from streamlit.proto.BackMsg_pb2 import BackMsg
from streamlit.proto.ForwardMsg_pb2 import ForwardMsg

PYTHON = Path(__file__).parent / "reference-browser/media-params"
RUST = Path(__file__).parents[1] / "browser/rust-media-params"


def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


MEDIA_TIME_CASES = read(PYTHON / 'trace.json')['playback_time_cases']
MEDIA_MIME_CASES = read(PYTHON / 'trace.json')['mime_cases']


def test_full_mime_registry_proposal_replays_sdk_and_builtin_alternative():
    import importlib.metadata
    import mimetypes
    import platform
    import sys
    from streamlit.runtime.memory_media_file_storage import get_extension_for_mimetype
    from streamlit.testing.v1 import AppTest

    record = read(PYTHON / 'trace.json')['mime_registry_proposal']
    assert record['sdk'] == importlib.metadata.version('streamlit') == '1.66.1'
    assert record['python'] == platform.python_version() == '3.14.7'
    assert record['platform'] == sys.platform == 'win32'
    seeds = record['registry_seeds']
    assert len(seeds) == len(set(seeds)) == 278
    mimetypes.init()
    assert seeds == sorted(set(mimetypes._db.types_map_inv[0])
                           | set(mimetypes._db.types_map_inv[1])
                           | {'audio/wav', 'text/vtt'})
    queries = sorted(set(seeds) | {value.lower() for value in seeds}
                     | {value.upper() for value in seeds}
                     | {value + '; codecs=test' for value in seeds}
                     | {'', 'not-a-mime', 'audio/x-codex-unknown',
                        'video/x-codex-unknown', 'application/x-codex-unknown'})
    assert len(queries) == 886
    assert set(record['extensions']) == set(record['builtin_extensions']) == set(queries)
    builtin = mimetypes.MimeTypes()
    for mime in queries:
        assert get_extension_for_mimetype(mime) == record['extensions'][mime], mime
        expected_builtin = {'audio/wav': '.wav', 'text/vtt': '.vtt'}.get(
            mime, builtin.guess_extension(mime, strict=False)) or ''
        assert expected_builtin == record['builtin_extensions'][mime], mime
    assert sum(record['extensions'][mime] != record['builtin_extensions'][mime]
               for mime in queries) == 161

    source = ('import streamlit as st\nfor mime in ' + repr(queries)
              + ':\n st.audio(b"ftyp",format=mime)\n st.video(b"ftyp",format=mime)')
    app = AppTest.from_string(source, default_timeout=30).run()
    assert not app.exception
    assert record['public_player_count'] == 1772
    for kind in ('audio', 'video'):
        players = app.get(kind)
        assert len(players) == len(queries)
        for mime, player in zip(queries, players):
            digest = hashlib.blake2b(b'4:ftyp' + mime.encode(), digest_size=16).hexdigest()
            assert player.proto.url == '/mock/media/' + digest + record['extensions'][mime], (kind, mime)


@pytest.mark.parametrize('case', MEDIA_MIME_CASES, ids=lambda case: case['name'])
def test_media_mime_replays_sdk_players_storage_and_asgi_get(case):
    import asyncio
    import importlib.metadata
    from starlette.applications import Starlette
    from streamlit.runtime.memory_media_file_storage import (
        MemoryMediaFileStorage, MediaFileKind, get_extension_for_mimetype,
    )
    from streamlit.testing.v1 import AppTest
    from streamlit.web.server.starlette.starlette_routes import create_media_routes

    assert importlib.metadata.version('streamlit') == '1.66.1'
    assert len(MEDIA_MIME_CASES) == 45
    mime = case['mime']
    assert get_extension_for_mimetype(mime) == case['extension']
    digest = hashlib.blake2b(b'4:ftyp' + mime.encode(), digest_size=16).hexdigest()
    assert case['url'] == '/media/' + digest + case['extension']

    for kind in ('audio', 'video'):
        app = AppTest.from_string('import streamlit as st\nst.' + kind + '(b"ftyp",format=' + repr(mime) + ')').run()
        assert not app.exception and len(app.get(kind)) == 1
        proto = app.get(kind)[0].proto
        expected = case['players'][kind]
        assert MessageToDict(proto, preserving_proto_field_name=True) == expected['apptest_fields']
        assert proto.SerializeToString() == base64.b64decode(expected['apptest_proto_base64'], validate=True)
        assert proto.url == '/mock' + case['url']
        proto.url = case['url']
        assert proto.SerializeToString() == bytes(expected['proto_bytes'])

    storage = MemoryMediaFileStorage('/media')
    file_id = storage.load_and_get_id(b'ftyp', mime, MediaFileKind.MEDIA)
    assert storage.get_url(file_id) == case['url']
    route_app = Starlette(routes=create_media_routes(storage, None))
    events = []

    async def receive():
        return {'type': 'http.request', 'body': b'', 'more_body': False}

    async def send(message):
        events.append(message)

    async def get():
        await route_app(dict(type='http', http_version='1.1', method='GET', scheme='http',
                             path=case['url'], raw_path=case['url'].encode(), query_string=b'',
                             headers=[(b'host', b'localhost')], server=('127.0.0.1', 0),
                             client=('127.0.0.1', 0)), receive, send)

    asyncio.run(get())
    starts = [event for event in events if event['type'] == 'http.response.start']
    assert len(starts) == 1
    expected = case['sdk_asgi_get']
    assert starts[0]['status'] == expected['status'] == 200
    assert {key.decode(): value.decode() for key, value in starts[0]['headers']} == expected['headers']
    body = b''.join(event['body'] for event in events if event['type'] == 'http.response.body')
    assert body == bytes(expected['body_bytes']) == b'ftyp'
    assert hashlib.sha256(body).hexdigest() == expected['body_sha256']


@pytest.mark.parametrize('case', MEDIA_TIME_CASES, ids=lambda case: case['name'])
def test_numeric_media_times_replay_sdk_players_and_error_precedence(case):
    import importlib.metadata
    from streamlit.proto.Audio_pb2 import Audio
    from streamlit.proto.Video_pb2 import Video
    from streamlit.testing.v1 import AppTest

    assert importlib.metadata.version('streamlit') == '1.66.1' and len(MEDIA_TIME_CASES) == 52
    source = 'import streamlit as st\nst.' + case['kind'] + '(b"ftyp"'
    for key in ('start_time', 'end_time'):
        value = case[key]
        if value is not None:
            literal = 'float(' + repr(value) + ')' if isinstance(value, str) else repr(value)
            source += ',' + key + '=' + literal
    app = AppTest.from_string(source + ')').run()
    if case['accepted']:
        assert not app.exception and len(app.get(case['kind'])) == 1
        proto = app.get(case['kind'])[0].proto
        assert MessageToDict(proto, preserving_proto_field_name=True) == case['apptest_proto']
        assert proto.SerializeToString() == base64.b64decode(case['apptest_proto_base64'], validate=True)
        mime, extension = ('audio/wav', 'wav') if case['kind'] == 'audio' else ('video/mp4', 'mp4')
        url = '/media/' + hashlib.blake2b(b'4:ftyp' + mime.encode(), digest_size=16).hexdigest() + '.' + extension
        assert proto.url == '/mock' + url
        proto.url = url
        canonical = Audio() if case['kind'] == 'audio' else Video()
        canonical.ParseFromString(bytes(case['proto_bytes']))
        assert proto == canonical
    else:
        assert not app.get(case['kind']) and len(app.exception) == 1
        error = app.exception[0].proto
        assert (error.type, error.message) == (case['error_type'], case['error'])
        assert error.message_is_markdown == case['message_is_markdown']
        assert error.is_streamlit_exception == case['is_streamlit_exception']


def frames(capture):
    for frame in capture["frames"]:
        data = base64.b64decode(frame["base64"], validate=True)
        assert len(data) == frame["bytes"]
        message = BackMsg() if frame["direction"] == "client->server" else ForwardMsg()
        message.ParseFromString(data)
        assert MessageToDict(message, preserving_proto_field_name=True) == frame["message"]
        yield message


def exceptions_of(capture):
    out = []
    for message in frames(capture):
        if message.WhichOneof("type") == "delta" and message.delta.WhichOneof("type") == "new_element":
            element = message.delta.new_element
            if element.WhichOneof("type") == "exception":
                out.append(element.exception)
    return out


def test_python_reference_playback_parameters():
    raw = read(PYTHON / "trace.json")
    assert raw["runtime"] == "python" and raw["reference_version"] == "1.66.1"
    assert raw["successful"] and "producer_error" not in raw
    assert raw["server_cleanup"] == "collector-owned" and raw["cleanup"]["server_stopped"] is True
    elements = raw["elements"]
    assert [element["kind"] for element in elements] == ["audio", "audio", "audio", "video", "video", "video"]
    audio_default, audio_params, audio_xwav, video_default, video_params, video_subtitles = (element["fields"] for element in elements)
    # The measured defaults carry only the stretch width.
    assert audio_default == {"width_config": {"use_stretch": True}}
    assert video_default == {"type": "NATIVE", "width_config": {"use_stretch": True}}
    # Times truncate to whole seconds; loop/autoplay ride along; the id is the
    # $$ID-<32hex>-None shape on autoplay only.
    assert audio_params["start_time"] == 1 and audio_params["end_time"] == 3
    assert audio_params["loop"] is True and audio_params["autoplay"] is True
    assert audio_params["id"].startswith("$")
    assert audio_params["id"].startswith("$" * 2 + "ID-") and audio_params["id"].endswith("-None") and len(audio_params["id"]) == 42
    assert video_params["muted"] is True and video_params["start_time"] == 2 and video_params["end_time"] == 4
    assert video_params["id"].startswith("$$ID-")
    # The format decides the address suffix: audio/wav -> .wav, audio/x-wav -> bare.
    assert elements[0]["url"].endswith(".wav") and elements[2]["url"].count(".") == 0
    # Subtitles ride one track with a .vtt media URL.
    track = video_subtitles["subtitles"][0]
    assert track["label"] == "en" and track["url"].endswith(".vtt")
    # Content addressing: identical bytes share one URL.
    assert elements[0]["url"] == elements[1]["url"] and elements[3]["url"] == elements[5]["url"]
    # The invalid subtitle renders the framework's API exception.
    exceptions = exceptions_of(raw)
    assert len(exceptions) == 1
    assert exceptions[0].type == "streamlit.errors.StreamlitAPIException"
    assert exceptions[0].message.startswith("Failed to process the provided subtitle 'en'")
    assert exceptions[0].message_is_markdown and exceptions[0].is_streamlit_exception
    assert raw["finishes"] == [0]


def test_historical_rust_capture_preserves_subtitle_address_gap():
    raw = read(RUST / "trace.json")
    assert raw["runtime"] == "rust" and raw["server_cleanup"] == "caller-owned"
    python = read(PYTHON / "trace.json")
    assert raw["elements"][5]["fields"]["subtitles"][0]["url"] != python["elements"][5]["fields"]["subtitles"][0]["url"]
    for rust_element, python_element in zip(raw["elements"], python["elements"]):
        assert rust_element["kind"] == python_element["kind"]
        fields = dict(rust_element["fields"])
        reference = dict(python_element["fields"])
        # Preserve the historical subtitle-address failure here; the new HTTP
        # capture compares the complete label-derived address and original bytes.
        fields.pop("id", None), reference.pop("id", None)
        if "subtitles" in fields:
            for track in fields["subtitles"]:
                track["url"] = track["url"].rsplit(".", 1)[-1]
            for track in reference["subtitles"]:
                track["url"] = track["url"].rsplit(".", 1)[-1]
        assert fields == reference, f"{rust_element['index']}: {fields} vs {reference}"
        # Content addressing makes the payload URLs identical cross-runtime.
        assert rust_element["url"] == python_element["url"], rust_element["index"]
        assert rust_element["url"].endswith(".wav") if rust_element["index"] in (0, 1) else True
    assert raw["finishes"] == [0]
    exceptions = exceptions_of(raw)
    assert len(exceptions) == 1
    assert exceptions[0].type == "streamlit.errors.StreamlitAPIException"
    assert exceptions[0].message == exceptions_of(python)[0].message
    assert exceptions[0].message_is_markdown and exceptions[0].is_streamlit_exception


HTTP_HEADERS = ({},{'Range':'bytes=0-3'},{'Range':'bytes=-4'},{'Range':'bytes=9999999-'},
    {'Range':'bytes=0-3','If-Range':'"mismatch"'},{'Range':'bytes=0-3','If-Range':'Thu, 01 Jan 1970 00:00:00 GMT'})


def http_inputs():
    buffer=io.BytesIO()
    with wave.open(buffer,'wb') as wav:
        wav.setnchannels(1);wav.setsampwidth(2);wav.setframerate(8000);wav.writeframes(b'\x00\x00'*800)
    video=b'\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp42isom\x00\x00\x00\x08free'
    return {'audio':(buffer.getvalue(),'audio/wav','wav'),'audio-bare':(buffer.getvalue(),'audio/x-wav',''),
            'video':(video,'video/mp4','mp4'),'subtitle':(b'WEBVTT\n\n00:00:00.000 --> 00:00:02.000\nHello','text/vtt','vtt')}


def http_semantics(headers):
    return {key:value for key,value in headers.items() if key not in ('date','server','connection')}


def check_media_http(capture, *, before=False):
    assert capture['runtime'] in ('python','rust')
    assert capture['successful'] and 'producer_error' not in capture and capture['reference_version']=='1.66.1'
    assert capture['cleanup']['websocket_closed'] and capture['cleanup']['server_stopped' if capture['runtime']=='python' else 'caller_server_stopped']
    assert capture['finishes']==[0] and len(capture['frames'])==12
    messages=list(frames(capture));kinds=[m.WhichOneof('type') for m in messages]
    assert kinds==['rerun_script','new_session','session_status_changed']+['delta']*8+['script_finished']
    assert not messages[0].rerun_script.query_string and not messages[0].rerun_script.widget_states.widgets
    assert messages[1].new_session.initialize.environment_info.streamlit_version=='1.66.1'
    assert messages[1].new_session.initialize.session_id and messages[1].new_session.script_run_id
    assert messages[2].session_status_changed.script_is_running
    emitted=[]
    for message in messages:
        if message.WhichOneof('type')=='delta' and message.delta.new_element.WhichOneof('type') in ('audio','video'):
            kind=message.delta.new_element.WhichOneof('type');fields=MessageToDict(getattr(message.delta.new_element,kind),preserving_proto_field_name=True);url=fields.pop('url')
            emitted.append({'index':len(emitted),'kind':kind,'fields':fields,'url':url,'delta_path':list(message.metadata.delta_path)})
    assert emitted==capture['elements'] and [e['kind'] for e in emitted]==['audio']*3+['video']*3
    assert [e['delta_path'] for e in emitted]==[[0,index] for index in range(1,7)]
    exceptions=exceptions_of(capture);assert len(exceptions)==1 and exceptions[0].type=='streamlit.errors.StreamlitAPIException'
    assets=[{'name':name,'element_index':index,'url':emitted[index]['url']} for name,index in (('audio',0),('audio-bare',2),('video',3))]
    track=emitted[5]['fields']['subtitles'][0];assert track['label']=='en'
    assets.append({'name':'subtitle','element_index':5,'label':track['label'],'url':track['url']})
    assert assets==capture['http_assets'] and len(capture['http_responses'])==48
    normalized=[];offset=0;inputs=http_inputs()
    for asset in assets:
        name=asset['name'];payload,mime,extension=inputs[name]
        filename=(hashlib.blake2b(b'en',digest_size=16).hexdigest()+'.vtt').encode() if name=='subtitle' and not before else b''
        digest=hashlib.blake2b(str(len(payload)).encode()+b':'+payload+mime.encode()+filename,digest_size=16).hexdigest()
        expected_url='/media/'+digest+('.'+extension if extension else '')
        assert asset['url']==expected_url
        for headers in HTTP_HEADERS:
            for method in ('GET','HEAD'):
                response=capture['http_responses'][offset];offset+=1
                assert (response['asset'],response['method'],response['url'],response['request_headers'])==(name,method,asset['url'],headers)
                request=base64.b64decode(response['request_base64'],validate=True)
                expected=(method+' '+asset['url']+' HTTP/1.1\r\nHost: '+capture['url'].removeprefix('http://')+'\r\nConnection: close\r\n'+''.join(key+': '+value+'\r\n' for key,value in headers.items())+'\r\n').encode('ascii')
                assert request==expected and len(request)==response['request_bytes']
                raw=base64.b64decode(response['response_base64'],validate=True);assert len(raw)==response['response_bytes']
                head,body=raw.split(b'\r\n\r\n',1);lines=head.decode('iso-8859-1').split('\r\n')
                assert lines[0].split(' ')[:2]==['HTTP/1.1',str(response['status'])]
                pairs=[line.split(':',1) for line in lines[1:]];actual={key.lower():value.strip() for key,value in pairs}
                assert len(actual)==len(pairs) and actual==response['headers']
                assert body==base64.b64decode(response['body_base64'],validate=True) and len(body)==response['body_bytes']
                expected_headers={'content-type':mime+('; charset=utf-8' if mime.startswith('text/') else ''),'accept-ranges':'bytes'}
                range_header=headers.get('Range')
                if before and (method=='HEAD' or name in ('audio-bare','subtitle')):
                    status=404;expected_headers={'content-length':'0'};expected_body=b''
                elif range_header=='bytes=9999999-':
                    status=416;expected_headers={'content-type':'text/plain; charset=utf-8','content-range':'bytes */'+str(len(payload)),'content-length':'13'};expected_body=b'Invalid range'
                else:
                    status=206 if range_header else 200
                    if range_header:
                        start,end=(len(payload)-4,len(payload)-1) if range_header=='bytes=-4' else (0,3)
                        expected_body=payload[start:end+1];expected_headers['content-range']=f'bytes {start}-{end}/{len(payload)}'
                    else:expected_body=payload
                    expected_headers['content-length']=str(len(expected_body))
                if method=='HEAD':expected_body=b''
                assert response['status']==status and http_semantics(actual)==expected_headers and body==expected_body,(name,method,headers)
                normalized.append((name,method,asset['url'],headers,status,expected_headers,body))
    assert offset==48
    return normalized


@pytest.mark.parametrize('root',(PYTHON,RUST),ids=('python','rust'))
def test_public_media_get_head_range_and_subtitle_bytes(root):
    check_media_http(read(root/'http/trace.json'))


def test_current_media_http_matches_reference_without_url_normalization():
    captures=[read(root/'http/trace.json') for root in (PYTHON,RUST)]
    assert captures[0]['producer_sources_sha256']==captures[1]['producer_sources_sha256']
    assert captures[1]['http_semantics_match'] is True and captures[1]['semantic_match'] is False
    assert check_media_http(captures[0])==check_media_http(captures[1])


def test_media_http_before_retains_actual_head_bare_and_subtitle_failures():
    capture=read(RUST/'http-before/trace.json');assert capture['semantic_match'] is False
    check_media_http(capture,before=True)
    assert sum(r['status']==404 for r in capture['http_responses'])==36
    with pytest.raises(AssertionError):check_media_http(capture)


def test_media_http_rust_inputs_and_cases_are_exact_raw_response_projections():
    capture=read(PYTHON/'http/trace.json');check_media_http(capture)
    compact=read(PYTHON/'http/cases.json');assert compact['reference_version']=='1.66.1'
    expected=[]
    for asset in capture['http_assets']:
        payload,mime,_=http_inputs()[asset['name']]
        expected.append({**asset,'mime':mime,'input_bytes':list(payload)})
    assert compact['assets']==expected
    assert compact['cases']==[{key:r[key] for key in ('asset','method','url','request_headers','status')}|{'headers':http_semantics(r['headers']),'body_bytes':list(base64.b64decode(r['body_base64'],validate=True))} for r in capture['http_responses']]


@pytest.mark.parametrize('mutation',('status','head-body','head-length','content-type','subtitle-url','body-byte','if-range','method'))
def test_media_http_gate_rejects_coherent_wrong_raw_responses(mutation):
    capture=read(PYTHON/'http/trace.json')
    if mutation=='subtitle-url':
        old=capture['http_assets'][-1]['url'];new=old.replace(old.rsplit('/',1)[-1].split('.')[0],'0'*32)
        capture['http_assets'][-1]['url']=new;capture['elements'][5]['fields']['subtitles'][0]['url']=new
        for frame in capture['frames']:
            if frame['direction']!='server->client':continue
            m=ForwardMsg();m.ParseFromString(base64.b64decode(frame['base64']))
            if m.WhichOneof('type')=='delta' and m.delta.new_element.WhichOneof('type')=='video' and m.delta.new_element.video.subtitles:
                m.delta.new_element.video.subtitles[0].url=new;raw=m.SerializeToString();frame.update(base64=base64.b64encode(raw).decode(),bytes=len(raw),message=MessageToDict(m,preserving_proto_field_name=True))
        for response in capture['http_responses']:
            if response['asset']=='subtitle':
                response['url']=new;raw=base64.b64decode(response['request_base64']).replace(old.encode(),new.encode());response.update(request_base64=base64.b64encode(raw).decode(),request_bytes=len(raw))
    else:
        index=1 if mutation in ('head-body','head-length','method') else 8 if mutation=='if-range' else 0
        r=capture['http_responses'][index];raw=base64.b64decode(r['response_base64']);head,body=raw.split(b'\r\n\r\n',1)
        if mutation=='method':
            r['method']='GET';request=base64.b64decode(r['request_base64']).replace(b'HEAD ',b'GET ',1);r.update(request_base64=base64.b64encode(request).decode(),request_bytes=len(request))
        elif mutation=='status':head=head.replace(b'200 OK',b'201 Created',1);r['status']=201
        elif mutation=='head-body':body=b'x'
        elif mutation=='head-length':head=head.replace(b'content-length: 1644',b'content-length: 1',1)
        elif mutation=='content-type':head=head.replace(b'audio/wav',b'text/plain',1)
        elif mutation=='body-byte':body=bytes([body[0]^1])+body[1:]
        elif mutation=='if-range':
            head=head.replace(b'206 Partial Content',b'200 OK',1);head=b'\r\n'.join(line for line in head.split(b'\r\n') if not line.lower().startswith(b'content-range:'));head=head.replace(b'content-length: 4',b'content-length: 1644',1);body=http_inputs()['audio'][0];r['status']=200
        raw=head+b'\r\n\r\n'+body;r.update(response_base64=base64.b64encode(raw).decode(),response_bytes=len(raw),body_base64=base64.b64encode(body).decode(),body_bytes=len(body))
        r['headers']={key.lower():value.strip() for key,value in (line.split(':',1) for line in head.decode('iso-8859-1').split('\r\n')[1:])}
        assert raw!=base64.b64decode(read(PYTHON/'http/trace.json')['http_responses'][index]['response_base64']) or mutation=='method'
    with pytest.raises(AssertionError):check_media_http(capture)
