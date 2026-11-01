"""Frozen media/layout edge evidence (python reference + rust browser)."""
import base64
import json
import hashlib

import pytest
import re
from pathlib import Path

from google.protobuf.json_format import MessageToDict
from streamlit.proto.BackMsg_pb2 import BackMsg
from streamlit.proto.ForwardMsg_pb2 import ForwardMsg

PYTHON = Path(__file__).parent / "reference-browser/media-more"
RUST = Path(__file__).parents[1] / "browser/rust-media-more"


def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def frames(capture):
    for frame in capture["frames"]:
        data = base64.b64decode(frame["base64"], validate=True)
        assert len(data) == frame["bytes"]
        message = BackMsg() if frame["direction"] == "client->server" else ForwardMsg()
        message.ParseFromString(data)
        assert MessageToDict(message, preserving_proto_field_name=True) == frame["message"]
        yield message


def normalized(capture):
    out = []
    for element in capture["elements"]:
        fields = dict(element["fields"])
        blob = json.dumps(fields, sort_keys=True)
        blob = re.sub(r"[0-9a-f]{32}", "<digest32>", blob)
        out.append((element["kind"], json.loads(blob), element.get("url") or None, element.get("block", {})))
    return out


def test_python_reference_edges():
    raw = read(PYTHON / "trace.json")
    assert raw["runtime"] == "python" and raw["reference_version"] == "1.66.1"
    assert raw["successful"] and "producer_error" not in raw
    assert raw["server_cleanup"] == "collector-owned" and raw["cleanup"]["server_stopped"] is True
    assert raw["finishes"] == [0]
    elements = raw["elements"]
    assert [element["kind"] for element in elements] == ["video", "video", "add_block:popover", "add_block:tab_container", "add_block:tab", "add_block:tab"]
    # URL input rides the wire unchanged with the playback knobs.
    url_video = elements[0]["fields"]
    assert url_video["url"] == "https://example.com/clip.mp4"
    assert url_video["type"] == "NATIVE" and url_video["start_time"] == 1 and url_video["end_time"] == 5
    assert not url_video["url"].startswith("/media/")
    # The SRT subtitle became a .vtt media track on the byte-upload video.
    srt_video = elements[1]["fields"]
    assert srt_video["url"].startswith("/media/") and srt_video["url"].endswith(".mp4")
    track = srt_video["subtitles"][0]
    assert track["label"] == "en" and track["url"].endswith(".vtt")
    # popover wrap rides the message; tabs width/height ride the BLOCK.
    assert elements[2]["fields"] == {"label": "Wrapped", "type": "secondary", "open": False, "wrap": True}
    assert elements[2]["block"] == {"width_config": {"use_content": True}}
    assert elements[3]["fields"] == {"default_tab_index": 1}
    assert elements[3]["block"] == {"width_config": {"pixel_width": 500}, "height_config": {"pixel_height": 200}}


def test_historical_rust_edges_retain_the_unmeasured_srt_content_gap():
    raw = read(RUST / "trace.json")
    assert raw["runtime"] == "rust" and raw["server_cleanup"] == "caller-owned"
    assert raw["finishes"] == [0]
    python = read(PYTHON / "trace.json")
    assert python["elements"][1]["fields"]["subtitles"][0]["url"] != raw["elements"][1]["fields"]["subtitles"][0]["url"]
    # The old digest-normalized comparison did not establish SRT byte parity.
    left, right = normalized(python), normalized(raw)
    assert len(left) == len(right) == 6
    for a, b in zip(left, right):
        assert a == b, (a, b)


SUBTITLE_CASES = read(PYTHON/'subtitle-text/cases.json')['cases']
UNICODE_SUBTITLE_CASES = read(PYTHON/'subtitle-text/cases.json')['unicode_cases']
LABEL_SUBTITLE_CASES = read(PYTHON/'subtitle-text/cases.json')['label_cases']
URL_SUBTITLE_CASES = read(PYTHON/'subtitle-text/cases.json')['url_cases']


@pytest.mark.parametrize('case',SUBTITLE_CASES+UNICODE_SUBTITLE_CASES+LABEL_SUBTITLE_CASES,ids=lambda case:case['name'])
def test_subtitle_oracle_replays_sdk_helper_and_public_video(case):
    import importlib.metadata
    from streamlit.elements.lib.subtitle_utils import _handle_string_or_path_data
    from streamlit.testing.v1 import AppTest

    assert importlib.metadata.version('streamlit')=='1.66.1' and len(SUBTITLE_CASES)==22 and len(UNICODE_SUBTITLE_CASES)==12
    assert len(LABEL_SUBTITLE_CASES)==12
    app=AppTest.from_string('import streamlit as st\nst.video(b"ftyp",subtitles={'+repr(case['label'])+':'+repr(case['input'])+'})').run()
    if case['accepted']:
        body=_handle_string_or_path_data(case['input'])
        assert body==bytes(case['content_bytes'])==base64.b64decode(case['content_base64'],validate=True)
        filename=hashlib.blake2b(case['label'].encode(),digest_size=16).hexdigest()+'.vtt'
        url='/media/'+hashlib.blake2b(str(len(body)).encode()+b':'+body+b'text/vtt'+filename.encode(),digest_size=16).hexdigest()+'.vtt'
        assert not app.exception and case['url']==url and case['apptest_url']=='/mock'+url
        assert app.get('video')[0].proto.subtitles[0].url==case['apptest_url']
    else:
        with pytest.raises(Exception) as error:_handle_string_or_path_data(case['input'])
        assert type(error.value).__name__==case['helper_error_type']
        assert [(e.proto.type,e.message) for e in app.exception]==[(case['error_type'],case['error'])]
        assert all(e.proto.message_is_markdown and e.proto.is_streamlit_exception for e in app.exception)


@pytest.mark.parametrize('case',URL_SUBTITLE_CASES,ids=lambda case:case['name'])
def test_url_subtitles_replay_full_sdk_video_and_errors(case):
    from streamlit.elements.lib.subtitle_utils import _handle_string_or_path_data
    from streamlit.proto.Video_pb2 import Video
    from streamlit.testing.v1 import AppTest

    assert len(URL_SUBTITLE_CASES)==8
    source='import streamlit as st\nst.video('+repr(case['url'])+',subtitles='+repr(dict(case['subtitles']))
    source+=',start_time='+repr(case['start_time'])+',end_time='+repr(case['end_time'])
    source+=',loop='+repr(case['loop'])+',muted='+repr(case['muted'])+')'
    app=AppTest.from_string(source).run()
    if case['accepted']:
        assert not app.exception and len(app.get('video'))==1
        video=app.get('video')[0].proto
        assert video.SerializeToString()==base64.b64decode(case['apptest_video_base64'],validate=True)
        assert MessageToDict(video,preserving_proto_field_name=True)==case['apptest_video']
        assert len(video.subtitles)==len(case['tracks'])==len(case['subtitles'])
        for track,expected,(label,text) in zip(video.subtitles,case['tracks'],case['subtitles']):
            body=_handle_string_or_path_data(text)
            assert body==bytes(expected['content_bytes'])
            assert hashlib.sha256(body).hexdigest()==expected['content_sha256']
            filename=hashlib.blake2b(label.encode(),digest_size=16).hexdigest()+'.vtt'
            url='/media/'+hashlib.blake2b(str(len(body)).encode()+b':'+body+b'text/vtt'+filename.encode(),digest_size=16).hexdigest()+'.vtt'
            assert track.label==label==expected['label'] and track.url=='/mock'+url and url==expected['url']
            track.url=url
        canonical=Video()
        canonical_bytes=base64.b64decode(case['video_base64'],validate=True)
        assert canonical_bytes==bytes(case['video_bytes'])
        canonical.ParseFromString(canonical_bytes)
        assert video==canonical and video.url==case['url']
    else:
        assert not app.get('video') and len(app.exception)==1
        error=app.exception[0].proto
        assert (error.type,error.message)==(case['error_type'],case['error'])
        assert error.message_is_markdown==case['message_is_markdown']
        assert error.is_streamlit_exception==case['is_streamlit_exception']


def check_subtitle_http(capture, *, before=False):
    assert capture['runtime'] in ('python','rust') and capture['reference_version']=='1.66.1'
    assert capture['successful'] and 'producer_error' not in capture and capture['finishes']==[0]
    assert capture['cleanup']['websocket_closed'] and capture['cleanup']['server_stopped' if capture['runtime']=='python' else 'caller_server_stopped']
    messages=list(frames(capture))
    sessions=[m.new_session for m in messages if m.WhichOneof('type')=='new_session']
    assert len(sessions)==1 and sessions[0].initialize.environment_info.streamlit_version=='1.66.1'
    assert sessions[0].initialize.session_id and sessions[0].script_run_id
    tracks=[]
    for m in messages:
        if m.WhichOneof('type')=='delta' and m.delta.WhichOneof('type')=='new_element' and m.delta.new_element.WhichOneof('type')=='video':
            video=m.delta.new_element.video
            for track in video.subtitles:tracks.append((track.label,track.url,list(m.metadata.delta_path),MessageToDict(video,preserving_proto_field_name=True)))
    assert len(tracks)==1 and tracks[0][0]=='en' and tracks[0][2]==[0,2]
    videos=[e for e in capture['elements'] if e['kind']=='video'];assert len(videos)==2
    assert videos[1]['fields']==tracks[0][3] and videos[1]['delta_path']==tracks[0][2]
    responses=capture['subtitle_responses'];assert len(responses)==1
    response=responses[0];assert response['element_index']==videos[1]['index'] and response['label']==tracks[0][0] and response['url']==tracks[0][1]
    body=base64.b64decode(response['body_base64'],validate=True)
    assert len(body)==response['body_bytes'] and hashlib.sha256(body).hexdigest()==response['body_sha256']
    case=next(c for c in SUBTITLE_CASES if c['name']=='srt-one')
    expected=b'WEBVTT\n\n00:00:01.000 --> .00:00:02\nHello SRT\n' if before else bytes(case['content_bytes'])
    assert body==expected
    filename=hashlib.blake2b(b'en',digest_size=16).hexdigest()+'.vtt'
    url='/media/'+hashlib.blake2b(str(len(body)).encode()+b':'+body+b'text/vtt'+filename.encode(),digest_size=16).hexdigest()+'.vtt'
    assert response['url']==url and response['status']==200
    headers={key:value for key,value in response['headers'].items() if key not in ('date','server','connection')}
    assert headers=={'content-type':'text/vtt; charset=utf-8','content-length':str(len(body)),'accept-ranges':'bytes'}
    if not before:assert url==case['url']
    return (url,headers,body)


@pytest.mark.parametrize('root',(PYTHON,RUST),ids=('python','rust'))
def test_srt_public_wire_url_and_actual_http_bytes(root):
    check_subtitle_http(read(root/'subtitle-text/trace.json'))


def test_srt_current_http_matches_sdk_without_digest_normalization():
    captures=[read(root/'subtitle-text/trace.json') for root in (PYTHON,RUST)]
    assert captures[0]['producer_sources_sha256']==captures[1]['producer_sources_sha256']
    assert captures[1]['subtitle_semantics_match'] is True and captures[1]['semantic_match'] is False
    assert check_subtitle_http(captures[0])==check_subtitle_http(captures[1])


def test_srt_before_preserves_actual_corrupted_time_counter_and_newline():
    capture=read(RUST/'subtitle-before/trace.json');assert capture['subtitle_semantics_match'] is False
    check_subtitle_http(capture,before=True)
    with pytest.raises(AssertionError):check_subtitle_http(capture)


@pytest.mark.parametrize('mutation',('counter','end-time','newline','caption','mime','status','url','label'))
def test_srt_http_gate_rejects_coherent_wrong_content(mutation):
    capture=read(PYTHON/'subtitle-text/trace.json');response=capture['subtitle_responses'][0];body=base64.b64decode(response['body_base64']);old_url=response['url']
    if mutation in ('counter','end-time','newline','caption'):
        if mutation=='counter':body=body.replace(b'\n\n1\n',b'\n\n',1)
        elif mutation=='end-time':body=body.replace(b'00:00:02.000',b'.00:00:02',1)
        elif mutation=='newline':body+=b'\n'
        else:body=body.replace(b'Hello SRT',b'Wrong SRT')
        filename=hashlib.blake2b(b'en',digest_size=16).hexdigest()+'.vtt'
        response['url']='/media/'+hashlib.blake2b(str(len(body)).encode()+b':'+body+b'text/vtt'+filename.encode(),digest_size=16).hexdigest()+'.vtt'
        response.update(body_base64=base64.b64encode(body).decode(),body_bytes=len(body),body_sha256=hashlib.sha256(body).hexdigest());response['headers']['content-length']=str(len(body))
    elif mutation=='mime':response['headers']['content-type']='text/plain'
    elif mutation=='status':response['status']=404
    elif mutation=='url':response['url']='/media/'+'0'*32+'.vtt'
    else:response['label']='fr'
    new_url=response['url'];new_label=response['label'];changed=0
    for frame in capture['frames']:
        if frame['direction']!='server->client':continue
        m=ForwardMsg();m.ParseFromString(base64.b64decode(frame['base64']))
        if m.WhichOneof('type')=='delta' and m.delta.WhichOneof('type')=='new_element' and m.delta.new_element.WhichOneof('type')=='video' and m.delta.new_element.video.subtitles:
            track=m.delta.new_element.video.subtitles[0];assert track.url==old_url;track.url=new_url;track.label=new_label
            raw=m.SerializeToString();frame.update(base64=base64.b64encode(raw).decode(),bytes=len(raw),message=MessageToDict(m,preserving_proto_field_name=True));changed+=1
    assert changed==1
    for element in capture['elements']:
        if element['kind']=='video' and element['fields'].get('subtitles'):
            element['fields']['subtitles'][0].update(url=new_url,label=new_label)
    with pytest.raises(AssertionError):check_subtitle_http(capture)
