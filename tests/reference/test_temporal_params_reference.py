"""Frozen temporal/slider creation-parameter evidence (python + rust)."""
import base64
import json
from pathlib import Path

import pytest

from google.protobuf.json_format import MessageToDict
from streamlit.proto.BackMsg_pb2 import BackMsg
from streamlit.proto.ForwardMsg_pb2 import ForwardMsg

PYTHON = Path(__file__).parent / "reference-browser/temporal-params"
RUST = Path(__file__).parents[1] / "browser/rust-temporal-params"


@pytest.mark.parametrize('target',('Single','Range'))
@pytest.mark.parametrize('text',('bad','2025-04-10','日期🧊'))
@pytest.mark.parametrize('peer_first',(False,True))
def test_sdk_disabled_date_strings_run_peer_then_fail_registration_and_recover(target,text,peer_first):
    from streamlit.testing.v1 import AppTest
    from streamlit.proto.WidgetStates_pb2 import WidgetStates

    app=AppTest.from_file(str(Path(__file__).parent/'widget_params_app.py'))
    app.query_params.update(probe='date-disabled',phase='disabled-assign');app.run()
    assert not app.exception
    identities={widget.label:widget.id for widget in (*app.date_input,*app.checkbox)}
    values=['2025-03-15' if target=='Single' else '2025-10-01', ['2025-03-15','2025-03-20'] if target=='Range' else ['2025-10-10','2025-10-20'],True]
    calls=[['peer',*values]]
    incoming=WidgetStates()
    for label in (('Peer',target) if peer_first else (target,'Peer')):
        widget=incoming.widgets.add(id=identities[label])
        if label=='Peer':widget.bool_value=True
        else:widget.string_value=text
    app.query_params['phase']='disabled-load';app._run(incoming)
    assert [error.message for error in app.exception]==['bad argument type for built-in operation']
    assert app.session_state['date_bound_calls']==calls
    for attempt in ('recovery','enable','edit'):
        incoming=WidgetStates();peer=attempt=='enable'
        if attempt!='recovery':
            dates=['2025-08-01'] if target=='Single' else ['2025-08-10','2025-08-20']
            if attempt=='edit':dates=['2025-11-01'] if target=='Single' else ['2025-11-10','2025-11-20']
            incoming.widgets.add(id=identities[target]).string_array_value.data[:]=dates
            values[0 if target=='Single' else 1]=dates[0] if target=='Single' else dates
            app.query_params['phase']='enabled-joint'
        values[2]=peer;incoming.widgets.add(id=identities['Peer']).bool_value=peer
        calls += [[source,*values] for source in ((target.lower(),'peer') if attempt=='edit' else ('peer',))]
        app._run(incoming)
        assert not app.exception
        assert json.loads(app.json[0].value)=={'phase':'disabled-load' if attempt=='recovery' else 'enabled-joint','values':values,'native':values,'calls':calls}
        assert {widget.label:widget.id for widget in (*app.date_input,*app.checkbox)}==identities
        assert all(not widget.proto.set_value for widget in app.date_input)


@pytest.mark.parametrize("kind,value,error", (("bool_value",True,"'bool' object is not iterable"), ("bool_value",False,"'bool' object is not iterable"),
    ("trigger_value",True,"'bool' object is not iterable"), ("trigger_value",False,"'bool' object is not iterable"), ("int_value",7,"'int' object is not iterable"),
    ("double_value",1.5,"'float' object is not iterable"), ("int_array_value",[7],"strptime() argument 1 must be str, not int"),
    ("double_array_value",[1.5],"strptime() argument 1 must be str, not float"), ("bytes_value",b'x',"strptime() argument 1 must be str, not int")))
@pytest.mark.parametrize("range_mode", (False,True))
@pytest.mark.parametrize("peer_first", (False,True))
def test_sdk_disabled_date_type_errors_precede_callbacks_and_block_recovery(kind,value,error,range_mode,peer_first):
    from streamlit.testing.v1 import AppTest
    from streamlit.proto.WidgetStates_pb2 import WidgetStates

    app = AppTest.from_string('''
import streamlit as st
from datetime import date
if 'calls' not in st.session_state:st.session_state.calls=[]
def changed(source):st.session_state.calls.append(source)
st.date_input('Day',value='''+('(date(2025,3,15),date(2025,3,20))' if range_mode else 'date(2025,3,15)')+''',key='day',disabled=True,on_change=changed,args=('day',))
st.checkbox('Peer',key='peer',on_change=changed,args=('peer',))
''').run()
    assert not app.exception
    identity, peer_id = app.date_input[0].id, app.checkbox[0].id
    incoming = WidgetStates()
    for label in (('peer','day') if peer_first else ('day','peer')):
        widget = incoming.widgets.add(id=peer_id if label=='peer' else identity)
        if label=='peer':widget.bool_value=True
        elif kind.endswith('array_value'):getattr(widget,kind).data[:]=value
        else:setattr(widget,kind,value)
    app._run(incoming)
    assert [exception.message for exception in app.exception] == [error]
    assert app.session_state['calls'] == [] and app.session_state['peer'] is True
    recovery = WidgetStates();recovery.widgets.add(id=identity).string_array_value.data[:] = ['2025-04-10','2025-04-20'] if range_mode else ['2025-04-10']
    recovery.widgets.add(id=peer_id).bool_value=False;app._run(recovery)
    assert [exception.message for exception in app.exception] == [error]
    assert app.session_state['calls'] == [] and app.session_state['peer'] is True


@pytest.mark.parametrize("bounds", ("both", "minimum", "maximum", "implicit"))
def test_sdk_date_mode_changes_follow_bound_policy(bounds):
    from streamlit.testing.v1 import AppTest
    from streamlit.proto.WidgetStates_pb2 import WidgetStates

    app = AppTest.from_string('''
import streamlit as st
from datetime import date
phase=st.session_state.get('phase','load')
range_mode=phase in ('range','range-edit','range-narrow','range-observe','range-recover')
high='2025-03-31' if phase in ('range-narrow','range-observe','range-recover') else '2025-03-15' if phase in ('single-narrow','single-recover','single-observe') else '2025-12-31'
kwargs={}
if ''' + repr(bounds) + ''' not in ('maximum','implicit'):kwargs['min_value']=date(2025,1,1)
if ''' + repr(bounds) + ''' not in ('minimum','implicit'):kwargs['max_value']=date.fromisoformat(high)
def wire(v):return [d.isoformat() for d in v] if isinstance(v,tuple) else v.isoformat()
if 'calls' not in st.session_state:st.session_state.calls=[]
def changed(source):st.session_state.calls.append([source,wire(st.session_state.day),st.session_state.peer])
v=st.date_input('Day',value=(date(2025,3,15),date(2025,3,20)) if range_mode else date(2025,3,15),key='day',on_change=changed,args=('day',),**kwargs)
st.checkbox('Peer',key='peer',on_change=changed,args=('peer',))
st.json([wire(v),wire(st.session_state.day),st.session_state.calls])
''').run()
    assert not app.exception
    identity, peer_id = app.date_input[0].id, app.checkbox[0].id
    calls = []
    steps = [('load',None), ('edit',(['2025-04-20'],True)), ('range',None), ('range-edit',(['2025-05-01','2025-05-10'],False)),
        ('single',None), ('single-edit',(['2025-06-01','2025-06-10'],True)), ('range-narrow',None), ('range-observe',None),
        ('range-recover',(['2025-03-10','2025-03-20'],False)), ('single-narrow',None), ('single-recover',(['2025-03-12'],True)), ('single-observe',None)]
    for index, (phase, submitted) in enumerate(steps):
        range_mode = phase in ('range','range-edit','range-narrow','range-observe','range-recover')
        if index:
            incoming = WidgetStates()
            if submitted:
                incoming.widgets.add(id=identity).string_array_value.data[:] = submitted[0]
                incoming.widgets.add(id=peer_id).bool_value = submitted[1]
                value = submitted[0] if range_mode else submitted[0][0]
                calls += [[source,value,submitted[1]] for source in ('day','peer')]
            app.session_state['phase'] = phase
            app._run(incoming)
        assert not app.exception
        value = ['2025-05-01','2025-05-10'] if phase=='range-edit' else ['2025-03-10','2025-03-20'] if phase=='range-recover' else ['2025-03-15','2025-03-20'] if range_mode else '2025-04-20' if phase=='edit' else '2025-06-01' if phase=='single-edit' else '2025-03-12' if phase in ('single-recover','single-observe') else '2025-03-15'
        if bounds == 'implicit':
            if phase == 'range':value = '2025-04-20'
            elif phase == 'single':value = ['2025-05-01','2025-05-10']
            elif phase in ('range-narrow','range-observe'):value = '2025-06-01'
            elif phase == 'single-narrow':value = ['2025-03-10','2025-03-20']
        assert json.loads(app.json[0].value) == [value,value,calls]
        widget = app.date_input[0].proto
        sync = bounds != 'implicit' and phase in ('range','single','range-narrow','single-narrow')
        assert widget.id == identity and widget.is_range is range_mode and widget.set_value is sync
        assert list(widget.value) == ([] if not sync else value if range_mode else [value])


@pytest.mark.parametrize("range_mode", (False, True))
@pytest.mark.parametrize("native_range", (False, True))
def test_sdk_implicit_date_bounds_preserve_native_single_and_complete_range_types(range_mode, native_range):
    from streamlit.testing.v1 import AppTest
    from streamlit.proto.WidgetStates_pb2 import WidgetStates

    app = AppTest.from_string('''
import streamlit as st
from datetime import date
if 'day' not in st.session_state:st.session_state.day=''' + ('(date(2050,2,1),date(2051,3,1))' if native_range else 'date(2050,2,1)') + '''
v=st.date_input('Day',value=''' + ('(date(2025,3,15),date(2025,3,20))' if range_mode else 'date(2025,3,15)') + ''',key='day')
def wire(v):return [d.isoformat() for d in v] if isinstance(v,tuple) else v.isoformat()
st.json([wire(v),wire(st.session_state.day)])
''').run()
    identity = app.date_input[0].id
    expected = ['2050-02-01','2051-03-01'] if native_range else '2050-02-01'
    for assign in (True,False):
        if not assign:app._run(WidgetStates())
        assert not app.exception and json.loads(app.json[0].value) == [expected,expected]
        widget = app.date_input[0].proto
        assert widget.id == identity and widget.is_range is range_mode and widget.set_value is assign
        assert list(widget.value) == ([] if not assign else expected if native_range else [expected])


@pytest.mark.parametrize("range_mode,assigned", ((False, False), (True, False), (False, 7), (True, 7), (False, ()), (True, ())))
def test_sdk_explicit_date_bounds_reset_non_date_native_shapes(range_mode, assigned):
    from streamlit.testing.v1 import AppTest

    app = AppTest.from_string('''
import streamlit as st
from datetime import date
st.session_state.day=''' + repr(assigned) + '''
value=st.date_input('Day',value=''' + ('(date(2025,3,15),date(2025,3,20))' if range_mode else 'date(2025,3,15)') + ''',min_value=date(2025,1,1),key='day')
def wire(v):return [d.isoformat() for d in v] if isinstance(v,tuple) else v.isoformat()
st.json([wire(value),wire(st.session_state.day)])
''').run()
    assert not app.exception
    expected = ['2025-03-15','2025-03-20'] if range_mode else '2025-03-15'
    assert json.loads(app.json[0].value) == [expected,expected]
    assert app.date_input[0].proto.set_value and list(app.date_input[0].proto.value) == (expected if range_mode else [expected])


@pytest.mark.parametrize("raw,expected", (
    (None, ['2025-03-15','2025-03-20']), (['2025/05/01','2025/05/10'], ['2025-05-01','2025-05-10']),
    (['bad','2025-05-10'], ['2025-03-15','2025-03-20']), (['2025-05-01','bad'], ['2025-03-15','2025-03-20']),
    (['2024-12-31','2025-05-10'], ['2025-03-15','2025-03-20']), (['2025-05-01','2026-01-01'], ['2025-03-15','2025-03-20']),
    (['2025-01-01','2025-12-31'], ['2025-01-01','2025-12-31']), (['2025-05-01','2025-05-01'], ['2025-05-01','2025-05-01']),
    (['2025-05-10','2025-05-01'], ['2025-05-10','2025-05-01']), (['2025-05-01','2025/05/10'], ['2025-05-01','2025-05-10']),
    (['bad'], ['2025-03-15','2025-03-20']), (['2025-05-01','bad','2025-05-10'], ['2025-03-15','2025-03-20'])))
def test_sdk_range_date_frontend_normalization_precedes_callbacks(raw, expected):
    import importlib.metadata
    from streamlit.proto.WidgetStates_pb2 import WidgetStates
    from streamlit.testing.v1 import AppTest

    assert importlib.metadata.version('streamlit') == '1.66.1'
    app = AppTest.from_string('''
import streamlit as st
from datetime import date
if 'calls' not in st.session_state:st.session_state.calls=[]
def wire(value):return [v.isoformat() for v in value]
def changed(source):st.session_state.calls.append([source,wire(st.session_state.selected_range),st.session_state.peer])
value=(date(2025,6,10),date(2025,6,20)) if st.session_state.get('defaults',False) else (date(2025,3,15),date(2025,3,20))
v=st.date_input('Range',value=value,min_value=date(2025,1,1),max_value=date(2025,12,31),key='selected_range',on_change=changed,args=('range',))
st.checkbox('Peer',key='peer',on_change=changed,args=('peer',))
st.json([wire(v),wire(st.session_state.selected_range),st.session_state.calls])
''').run()
    assert not app.exception
    identity, peer_id = app.date_input[0].id, app.checkbox[0].id
    incoming = WidgetStates();incoming.widgets.add(id=identity).string_array_value.data[:] = ['2025-04-10','2025-04-20'];incoming.widgets.add(id=peer_id).bool_value = True
    app._run(incoming)
    assert not app.exception
    assert json.loads(app.json[0].value)[2] == [['range',['2025-04-10','2025-04-20'],True],['peer',['2025-04-10','2025-04-20'],True]]
    incoming = WidgetStates();widget = incoming.widgets.add(id=identity)
    if raw is not None:widget.string_array_value.SetInParent();widget.string_array_value.data[:] = raw
    incoming.widgets.add(id=peer_id).bool_value = False
    app.session_state['defaults'] = True
    app._run(incoming)
    assert not app.exception
    report = json.loads(app.json[0].value)
    assert report[:2] == [expected, expected] and report[2][2:] == [['range',expected,False],['peer',expected,False]]
    assert app.date_input[0].id == identity and list(app.date_input[0].proto.default) == ['2025-06-10','2025-06-20'] and not app.date_input[0].proto.set_value
    incoming = WidgetStates();incoming.widgets.add(id=identity)
    app._run(incoming)
    assert not app.exception and json.loads(app.json[0].value)[:2] == [['2025-06-10','2025-06-20']]*2


@pytest.mark.parametrize("raw", ([], ['2025-01-15'], ['2025-01-15','2025-02-15','2025-03-15']))
def test_sdk_range_serde_variable_lengths_remain_an_open_rust_boundary(raw):
    """SDK-only shape evidence; Rust's public model choice is still pending."""
    import importlib.metadata
    from datetime import date
    from streamlit.elements.widgets.time_widgets import DateInputSerde, _DateInputValues

    assert importlib.metadata.version('streamlit') == '1.66.1'
    serde = DateInputSerde(_DateInputValues.from_raw_values(value=(date(2025,3,15),date(2025,3,20)),
        min_value=date(2025,1,1),max_value=date(2025,12,31)))
    value = serde.deserialize(raw)
    assert type(value) is tuple and [item.isoformat() for item in value] == raw
    assert serde.serialize(value) == raw


@pytest.mark.parametrize("range_mode", (False, True))
def test_sdk_date_native_bound_resets_after_callbacks_and_preserves_implicit_values(range_mode):
    """Full native dates only; no None/partial-range compatibility claim."""
    import importlib.metadata
    from streamlit.proto.WidgetStates_pb2 import WidgetStates
    from streamlit.testing.v1 import AppTest

    assert importlib.metadata.version("streamlit") == "1.66.1"
    app = AppTest.from_string('''
import streamlit as st
from datetime import date
range_mode=''' + repr(range_mode) + '''
phase=st.session_state.get('phase','load')
parse=date.fromisoformat
def native(start,end):return (parse(start),parse(end)) if range_mode else parse(start)
def wire(value):return [v.isoformat() for v in value] if isinstance(value,tuple) else value.isoformat()
if 'calls' not in st.session_state:st.session_state.calls=[]
def changed():st.session_state.calls.append(wire(st.session_state.day))
assignments={'assign':('2026-02-01','2026-03-01'),'implicit':('2050-02-01','2050-03-01'),'minimum':('2025-02-01','2025-03-20'),'maximum':('2025-04-20','2025-05-20'),'lower':('2025-02-28','2025-03-20')}
if phase in assignments:st.session_state.day=native(*assignments[phase])
kwargs={}
if phase not in ('implicit','implicit-observe'):
    low='2025-02-01' if phase=='minimum' else '2025-03-01' if phase in ('lower','final') else '2025-01-01'
    high='2025-04-10' if phase in ('narrow','observe','joint','assign') else ('2025-05-20' if range_mode else '2025-04-20') if phase=='maximum' else '2025-12-31'
    kwargs=dict(min_value=parse(low),max_value=parse(high))
value=st.date_input('Day',value=native('2025-03-15','2025-03-20'),key='day',on_change=changed,**kwargs)
st.json([wire(value),wire(st.session_state.day),st.session_state.calls])
''').run()
    assert not app.exception
    identity = app.date_input[0].id
    calls = []
    for phase in ('edit','narrow','observe','widen','joint','assign','implicit','implicit-observe','minimum','maximum','lower','final'):
        incoming = WidgetStates()
        submitted = ('2025-04-20','2025-05-20') if phase=='edit' else ('2025-04-25','2025-05-25') if phase=='joint' else None
        if submitted:
            values = list(submitted) if range_mode else [submitted[0]]
            incoming.widgets.add(id=identity).string_array_value.data[:] = values
            calls.append(values if range_mode else values[0])
        app.session_state['phase'] = phase
        app._run(incoming)
        assert not app.exception
        pair = ('2025-04-20','2025-05-20') if phase in ('edit','maximum') else ('2050-02-01','2050-03-01') if phase in ('implicit','implicit-observe') else ('2025-02-01','2025-03-20') if phase=='minimum' else ('2025-03-15','2025-03-20')
        expected = list(pair) if range_mode else pair[0]
        assert json.loads(app.json[0].value) == [expected, expected, calls]
        widget = app.date_input[0].proto
        sync = phase in ('narrow','joint','assign','implicit','minimum','maximum','lower')
        assert widget.id == identity and widget.is_range is range_mode and widget.set_value is sync
        assert list(widget.value) == ([] if not sync else list(pair) if range_mode else [pair[0]])


@pytest.mark.parametrize("raw,expected", ((None, "2025-03-15"), (["bad"], "2025-03-15"), (["2025/05/07"], "2025-05-07"),
    (["2025-05-07"], "2025-05-07"), (["2025-05-07", "2025-06-08"], "2025-05-07"), (["2025-05-07", "bad"], "2025-03-15"),
    (["2026-01-01"], "2025-03-15"), (["2025-05-07", "2026-01-01"], "2025-03-15"), (["2025-01-01"], "2025-01-01"), (["2025-12-31"], "2025-12-31")))
def test_sdk_single_date_normalizes_full_list_and_uses_registered_defaults(raw, expected):
    """Raw AppTest input, no normal-browser packet claim."""
    import importlib.metadata
    from streamlit.proto.WidgetStates_pb2 import WidgetStates
    from streamlit.testing.v1 import AppTest

    assert importlib.metadata.version("streamlit") == "1.66.1"
    app = AppTest.from_string('''
import streamlit as st
from datetime import date
if 'calls' not in st.session_state:st.session_state.calls=[]
def changed(source):st.session_state.calls.append([source,st.session_state.day.isoformat(),st.session_state.peer])
v=st.date_input('Day',value=date(2025,6,10) if st.session_state.get('defaults',False) else date(2025,3,15),min_value=date(2025,1,1),max_value=date(2025,12,31),key='day',on_change=changed,args=('day',))
st.checkbox('Peer',key='peer',on_change=changed,args=('peer',))
st.json([v.isoformat(),st.session_state.day.isoformat(),st.session_state.calls])
''').run()
    assert not app.exception
    identity, peer_id = app.date_input[0].id, app.checkbox[0].id
    incoming = WidgetStates()
    incoming.widgets.add(id=identity).string_array_value.data[:] = ['2025-04-20']
    incoming.widgets.add(id=peer_id).bool_value = True
    app._run(incoming)
    assert not app.exception
    assert json.loads(app.json[0].value) == ['2025-04-20', '2025-04-20', [['day','2025-04-20',True],['peer','2025-04-20',True]]]
    incoming = WidgetStates()
    widget = incoming.widgets.add(id=identity)
    if raw is not None:
        widget.string_array_value.SetInParent();widget.string_array_value.data[:] = raw
    incoming.widgets.add(id=peer_id).bool_value = False
    app.session_state['defaults'] = True
    app._run(incoming)
    assert not app.exception
    report = json.loads(app.json[0].value)
    assert report[:2] == [expected, expected]
    assert report[2][2:] == [['day',expected,False],['peer',expected,False]]
    assert app.date_input[0].id == identity and list(app.date_input[0].proto.default) == ['2025-06-10']
    assert not app.date_input[0].proto.set_value
    incoming = WidgetStates();incoming.widgets.add(id=identity)
    app._run(incoming)
    assert not app.exception and json.loads(app.json[0].value)[:2] == ['2025-06-10'] * 2


@pytest.mark.parametrize("minimum,assigned,expected", ((True, "07:59", "12:30"), (True, "08:00", "08:00"),
                                                       (False, "16:01", "12:30"), (False, "16:00", "16:00")))
def test_sdk_datetime_one_sided_native_bounds_are_inclusive(minimum, assigned, expected):
    from streamlit.testing.v1 import AppTest

    app = AppTest.from_string('''
import streamlit as st
from datetime import datetime
parse=lambda clock:datetime.strptime('2025-03-15T'+clock,'%Y-%m-%dT%H:%M')
st.session_state.moment=parse(''' + repr(assigned) + ''')
kwargs=dict(min_value=parse('08:00')) if ''' + repr(minimum) + ''' else dict(max_value=parse('16:00'))
v=st.datetime_input('Moment',value=parse('12:30'),key='moment',**kwargs)
st.json([v.strftime('%Y-%m-%dT%H:%M'),st.session_state.moment.strftime('%Y-%m-%dT%H:%M')])
''').run()
    assert not app.exception
    assert json.loads(app.json[0].value) == ["2025-03-15T" + expected] * 2
    assert app.datetime_input[0].proto.set_value
    assert list(app.datetime_input[0].proto.value) == ["2025-03-15T" + expected]


def test_sdk_datetime_explicit_bounds_reset_native_state_without_extra_callback():
    """Raw AppTest observation runs intentionally submit no widget values."""
    import importlib.metadata
    from streamlit.proto.WidgetStates_pb2 import WidgetStates
    from streamlit.testing.v1 import AppTest

    assert importlib.metadata.version("streamlit") == "1.66.1"
    app = AppTest.from_string('''
import streamlit as st
from datetime import datetime
phase=st.session_state.get('phase','load')
if 'calls' not in st.session_state:st.session_state.calls=[]
def changed():st.session_state.calls.append(st.session_state.moment.strftime('%Y-%m-%dT%H:%M') if st.session_state.moment else None)
if phase=='assign':st.session_state.moment=datetime(2025,3,15,19)
if phase=='implicit':st.session_state.moment=datetime(2050,3,15,19)
kwargs={} if phase=='implicit' else dict(min_value=datetime(2025,3,15,8),max_value=datetime(2025,3,15,16 if phase in ('narrow','assign','none') else 18))
v=st.datetime_input('Moment',value=None if phase in ('none','null-observe') else datetime(2025,3,15,12,30),key='moment',on_change=changed,**kwargs)
st.json([None if v is None else v.strftime('%Y-%m-%dT%H:%M'),None if st.session_state.moment is None else st.session_state.moment.strftime('%Y-%m-%dT%H:%M'),st.session_state.calls])
''').run()
    assert not app.exception
    identity = app.datetime_input[0].id
    assert json.loads(app.json[0].value) == ["2025-03-15T12:30", "2025-03-15T12:30", []]
    for phase, expected in (("edit", "2025-03-15T17:00"), ("narrow", "2025-03-15T12:30"), ("observe", "2025-03-15T12:30"),
                            ("assign", "2025-03-15T12:30"), ("implicit", "2050-03-15T19:00"), ("none", None), ("null-observe", None)):
        incoming = WidgetStates()
        if phase == "edit":
            incoming.widgets.add(id=identity).string_array_value.data[:] = ["2025-03-15T17:00"]
        app.session_state["phase"] = phase
        app._run(incoming)
        assert not app.exception
        assert json.loads(app.json[0].value) == [expected, expected, ["2025-03-15T17:00"]]
        widget = app.datetime_input[0].proto
        assert widget.id == identity
        sync = phase in ("narrow", "assign", "implicit", "none")
        assert widget.set_value is sync
        assert list(widget.value) == ([] if not sync or expected is None else [expected])
        assert list(widget.default) == ([] if phase in ("none", "null-observe") else ["2025-03-15T12:30"])


DATETIME_INPUT_CASES = (
    (None, None), ([], None), (["not-a-datetime"], None),
    (["bad", "2025-03-15T15:47"], None),
    (["2025-03-15T07:59"], None), (["2025-03-15T18:01"], None),
    (["2025-03-15T15:47:00"], None),
    (["2025-03-15T08:00"], "2025-03-15T08:00"),
    (["2025-03-15T18:00"], "2025-03-15T18:00"),
    (["2025-03-15T15:47"], "2025-03-15T15:47"),
    (["2025/03/15, 15:47"], "2025-03-15T15:47"),
    (["2025-03-15T15:47", "bad"], "2025-03-15T15:47"),
)


@pytest.mark.parametrize("default", (None, "2025-03-15T12:30"))
@pytest.mark.parametrize("raw,expected", DATETIME_INPUT_CASES)
def test_sdk_datetime_serde_falls_back_to_effective_default(default, raw, expected):
    """SDK serde evidence only; these inputs are not a browser capture."""
    from datetime import datetime
    from streamlit.elements.widgets.time_widgets import DateTimeInputSerde

    parse = lambda text: datetime.strptime(text, "%Y-%m-%dT%H:%M")
    serde = DateTimeInputSerde(None if default is None else parse(default),
                              parse("2025-03-15T08:00"), parse("2025-03-15T18:00"))
    result = expected if expected is not None else default
    assert serde.deserialize(raw) == (None if result is None else parse(result))
    assert serde.serialize(serde.deserialize(raw)) == ([] if result is None else [result])


@pytest.mark.parametrize("raw,expected", DATETIME_INPUT_CASES)
def test_sdk_datetime_raw_input_callbacks_and_registered_defaults(raw, expected):
    """AppTest with injected protobuf; not native WS or normal browser input."""
    import importlib.metadata
    from datetime import datetime
    from streamlit.proto.WidgetStates_pb2 import WidgetStates
    from streamlit.testing.v1 import AppTest

    assert importlib.metadata.version("streamlit") == "1.66.1"
    app = AppTest.from_string('''
import streamlit as st
from datetime import datetime
parse=lambda value:datetime.strptime(value,'%Y-%m-%dT%H:%M')
if 'calls' not in st.session_state:st.session_state.calls=[]
def changed():
    def wire(value):return None if value is None else value.strftime('%Y-%m-%dT%H:%M')
    st.session_state.calls.append([wire(st.session_state.moment),wire(st.session_state.optional),st.session_state.peer])
next_default=st.session_state.get('next_default',False)
value=parse('2025-03-15T16:20' if next_default else '2025-03-15T12:30')
kwargs=dict(min_value=parse('2025-03-15T08:00'),max_value=parse('2025-03-15T18:00'),on_change=changed)
st.datetime_input('Moment',value=value,key='moment',**kwargs)
st.datetime_input('Optional',value=value if next_default else None,key='optional',**kwargs)
st.checkbox('Peer',key='peer',on_change=changed)
st.json(st.session_state.calls)
''').run()
    parse = lambda text: datetime.strptime(text, "%Y-%m-%dT%H:%M")
    assert not app.exception
    ids = [widget.id for widget in app.datetime_input]
    peer_id = app.checkbox[0].id
    for widget in app.datetime_input:
        widget.set_value(parse("2025-03-15T14:35"))
    app.run()
    assert not app.exception
    assert json.loads(app.json[0].value) == [["2025-03-15T14:35", "2025-03-15T14:35", False]] * 2

    incoming = WidgetStates()
    for widget_id in ids:
        widget = incoming.widgets.add(id=widget_id)
        if raw is not None:
            widget.string_array_value.SetInParent()
            widget.string_array_value.data[:] = raw
    incoming.widgets.add(id=peer_id).bool_value = True
    app.session_state["next_default"] = True
    app._run(incoming)
    assert not app.exception
    assert json.loads(app.json[0].value)[2:] == [[expected or "2025-03-15T12:30", expected, True]] * 3
    assert [widget.id for widget in app.datetime_input] == ids
    assert [list(widget.proto.default) for widget in app.datetime_input] == [
        ["2025-03-15T16:20"], [] if expected is None else ["2025-03-15T16:20"]]
    assert all(not widget.proto.set_value for widget in app.datetime_input)

    incoming = WidgetStates()
    for widget_id in ids:
        incoming.widgets.add(id=widget_id)
    app._run(incoming)
    assert not app.exception
    assert [widget.value for widget in app.datetime_input] == [
        parse("2025-03-15T16:20"), None if expected is None else parse("2025-03-15T16:20")]


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


def comparable(capture):
    out = []
    for element in capture["elements"]:
        fields = dict(element["fields"])
        fields.pop("id", None)
        out.append((element["kind"], fields))
    return out


def test_python_reference_temporal_edges():
    raw = read(PYTHON / "trace.json")
    assert raw["runtime"] == "python" and raw["reference_version"] == "1.66.1"
    assert raw["successful"] and "producer_error" not in raw
    assert raw["server_cleanup"] == "collector-owned" and raw["cleanup"]["server_stopped"] is True
    assert raw["finishes"] == [0]
    widgets = {element["fields"]["label"]: element["fields"] for element in raw["elements"] if element["kind"] != "heading"}
    bounded = widgets["Bounded"]
    assert bounded["default"] == ["2024-03-15"] and bounded["min"] == "2024-01-01" and bounded["max"] == "2024-12-31"
    assert bounded["format"] == "YYYY/MM/DD"
    formatted = widgets["Formatted"]
    assert formatted["format"] == "DD/MM/YYYY"
    assert (formatted["min"], formatted["max"]) == ("2014-06-01", "2034-06-01"), "the unbounded window is value ± 10 years"
    slider = widgets["Range"]
    assert slider["type"] == "SELECT_SLIDER" and slider["default"] == [0.0, 2.0] and slider["options"] == ["low", "mid", "high"]
    assert (slider["max"], slider["step"], slider["format"]) == (2.0, 1.0, "%s")
    assert "min" not in slider, "the select slider omits min at index 0 (proto default)"
    stepped = widgets["Stepped"]
    assert stepped["step"] == "900" and stepped["format"] == "24h" and stepped["default"] == "12:30"


def test_rust_temporal_matches_field_for_field():
    raw = read(RUST / "trace.json")
    assert raw["runtime"] == "rust" and raw["server_cleanup"] == "caller-owned"
    assert raw["finishes"] == [0]
    python = read(PYTHON / "trace.json")
    left, right = comparable(python), comparable(raw)
    assert len(left) == len(right) == 5
    for a, b in zip(left, right):
        assert a == b, (a, b)


IDENTITY_PHASES = ("load", "edit", "policy", "step", "edit-step", "format", "edit-format", "defaults", "bounds", "restore", "observe")
IDENTITY_VALUES = (
    ("12:30", "2024-03-15T12:30", "2024-03-15"),
    ("13:45", "2024-06-01T13:45", "2024-06-01"),
    ("13:45", "2024-06-01T13:45", "2024-06-01"),
    ("12:30", "2024-03-15T12:30", "2024-06-01"),
    ("14:00", "2024-06-01T14:00", "2024-06-01"),
    ("14:00", "2024-03-15T12:30", "2024-03-15"),
    ("15:00", "2024-07-04T15:00", "2024-07-04"),
    ("15:00", "2024-07-04T15:00", "2024-07-04"),
    ("15:00", "2024-07-04T15:00", "2024-07-04"),
    ("12:30", "2024-03-15T12:30", "2024-03-15"),
    ("12:30", "2024-03-15T12:30", "2024-03-15"),
)


def identity_runs(capture):
    runs, emitted = [], []
    for message in frames(capture):
        kind = message.WhichOneof("type")
        if isinstance(message, BackMsg):
            assert kind == "rerun_script"
            runs.append({"request": message.rerun_script, "sessions": [], "finishes": [], "entries": []})
        elif kind == "new_session":
            runs[-1]["sessions"].append(message.new_session)
        elif kind == "script_finished":
            runs[-1]["finishes"].append(message.script_finished)
        elif kind == "delta":
            assert message.delta.WhichOneof("type") == "new_element"
            element = message.delta.new_element
            entry_kind = element.WhichOneof("type")
            assert entry_kind in ("time_input", "date_time_input", "date_input", "json")
            view = getattr(element, entry_kind)
            fields = MessageToDict(view, preserving_proto_field_name=True)
            emitted.append((entry_kind, fields, list(message.metadata.delta_path)))
            runs[-1]["entries"].append((entry_kind, view, element, list(message.metadata.delta_path)))
    return runs, emitted


def check_keyed_temporal_identity(capture):
    assert capture["reference_version"] == "1.66.1" and capture["successful"] and "producer_error" not in capture
    assert len(capture["frames"]) == 98 and capture["finishes"] == [0] * 11
    assert capture["cleanup"]["websocket_closed"]
    if capture["runtime"] == "python":
        assert capture["cleanup"]["server_stopped"]
    runs, emitted = identity_runs(capture)
    assert emitted == [(entry["kind"], entry["fields"], entry["delta_path"]) for entry in capture["elements"]]
    assert len(runs) == 11 and len(emitted) == 44
    groups = ((0, 0, 0, 1, 1, 1, 1, 1, 1, 0, 0), (0, 0, 0, 1, 1, 2, 2, 2, 2, 0, 0), (0, 0, 0, 0, 0, 1, 1, 1, 1, 0, 0))
    ids, sessions, run_ids = ({}, {}, {}), set(), set()
    for index, (run, phase, values) in enumerate(zip(runs, IDENTITY_PHASES, IDENTITY_VALUES, strict=True)):
        request = run["request"]
        assert request.query_string == "probe=identity&phase=" + phase and not request.is_history_navigation
        assert len(run["sessions"]) == 1 and run["finishes"] == [0]
        session = run["sessions"][0]
        assert session.initialize.environment_info.streamlit_version == "1.66.1"
        sessions.add(session.initialize.session_id)
        run_ids.add(session.script_run_id)
        assert [entry[0] for entry in run["entries"]] == ["time_input", "date_time_input", "date_input", "json"]
        for position, (_, _, _, path) in enumerate(run["entries"]):
            assert path == [0, position]
        clock, moment, date = [entry[1] for entry in run["entries"][:3]]
        for position, (key, label) in enumerate((("clock", "Clock"), ("moment", "Moment"), ("date", "Date"))):
            _, widget, element, _ = run["entries"][position]
            assert widget.id.endswith("-" + key) and widget.id == ids[position].setdefault(groups[position][index], widget.id)
            assert widget.label == label and widget.help == phase and not widget.form_id
            assert widget.disabled == (phase == "policy") and widget.label_visibility.value == (1 if phase == "policy" else 0)
            assert MessageToDict(element.width_config, preserving_proto_field_name=True) == ({"pixel_width": 360} if phase == "policy" else {"use_stretch": True})
            assert not widget.set_value and not element.HasField("has_one_shot_effect")
        step = 1800 if 3 <= index <= 8 else 900
        display_format = "DD/MM/YYYY" if 5 <= index <= 8 else "YYYY/MM/DD"
        default_date = "2024-04-20" if phase in ("defaults", "bounds") else "2024-03-15"
        default_time = "10:00" if phase in ("defaults", "bounds") else "12:30"
        assert clock.default == default_time and clock.HasField("default") and not clock.HasField("value")
        assert clock.step == moment.step == step and clock.format == ("12h" if 5 <= index <= 8 else "24h")
        assert list(moment.default) == [default_date + "T" + default_time] and list(date.default) == [default_date]
        assert not moment.value and not date.value and not date.is_range
        assert moment.format == date.format == display_format
        low, high = (("2024-01-01", "2024-12-31") if phase == "bounds" else ("2014" + default_date[4:], "2034" + default_date[4:]))
        assert (date.min, date.max, moment.min, moment.max) == (low, high, low + "T00:00", high + "T23:59")
        assert json.loads(run["entries"][3][1].body) == {"phase": phase, "values": list(values), "native": list(values)}
        incoming = request.widget_states.widgets
        if phase in ("edit", "edit-step", "edit-format"):
            assert len(incoming) == 3
            assert [(widget.id, widget.WhichOneof("value")) for widget in incoming] == [
                (clock.id, "string_value"), (moment.id, "string_array_value"), (date.id, "string_array_value")]
            assert incoming[0].string_value == values[0]
            assert list(incoming[1].string_array_value.data) == [values[1]] and list(incoming[2].string_array_value.data) == [values[2]]
        else:
            assert not incoming
    assert [len(set(group.values())) for group in ids] == [2, 3, 2]
    assert len(sessions) == 1 and len(run_ids) == 11


@pytest.mark.parametrize("root", (PYTHON, RUST), ids=("python", "rust"))
def test_keyed_temporal_constraints_and_retention(root):
    check_keyed_temporal_identity(read(root / "keyed-identity/trace.json"))


def test_pre_fix_temporal_identity_remains_a_known_mismatch():
    capture = read(RUST / "keyed-identity/before/trace.json")
    runs, _ = identity_runs(capture)
    assert json.loads(runs[3]["entries"][3][1].body)["values"][:2] == ["13:45", "2024-06-01T13:45"]
    assert [len({run["entries"][position][1].id for run in runs}) for position in range(3)] == [1, 1, 1]
    with pytest.raises(AssertionError):
        check_keyed_temporal_identity(capture)


@pytest.mark.parametrize("mutation", ("clock-step-id", "moment-format-id", "date-format-id", "retained-value", "policy-width"))
def test_temporal_identity_gate_rejects_coherent_wrong_wire(mutation):
    capture = read(PYTHON / "keyed-identity/trace.json")
    source_runs, _ = identity_runs(capture)
    run = -1
    target = 3 if mutation == "clock-step-id" else 5 if mutation in ("moment-format-id", "date-format-id") else 7 if mutation == "retained-value" else 2
    for frame in capture["frames"]:
        if frame["direction"] == "client->server":
            run += 1
            continue
        if run != target:
            continue
        message = ForwardMsg()
        message.ParseFromString(base64.b64decode(frame["base64"]))
        if message.WhichOneof("type") != "delta" or message.delta.WhichOneof("type") != "new_element":
            continue
        element = message.delta.new_element
        kind = element.WhichOneof("type")
        if mutation in ("clock-step-id", "moment-format-id", "date-format-id"):
            position = {"clock-step-id": 0, "moment-format-id": 1, "date-format-id": 2}[mutation]
            if kind != ("time_input", "date_time_input", "date_input")[position]:
                continue
            getattr(element, kind).id = source_runs[target - 1]["entries"][position][1].id
        elif mutation == "retained-value" and kind == "json":
            report = json.loads(element.json.body)
            report["values"][0] = report["native"][0] = "10:00"
            element.json.body = json.dumps(report)
        elif mutation == "policy-width" and kind == "time_input":
            element.width_config.pixel_width = 361
        else:
            continue
        raw = message.SerializeToString()
        frame.update(base64=base64.b64encode(raw).decode(), bytes=len(raw), message=MessageToDict(message, preserving_proto_field_name=True))
    _, emitted = identity_runs(capture)
    capture["elements"] = [{"kind": kind, "fields": fields, "delta_path": path} for kind, fields, path in emitted]
    with pytest.raises(AssertionError):
        check_keyed_temporal_identity(capture)


def test_sdk_unkeyed_temporal_display_and_bounds_identity():
    """Live pinned SDK AppTest oracle; not a native WS or browser capture."""
    import datetime
    import importlib.metadata

    from streamlit.testing.v1 import AppTest

    assert importlib.metadata.version("streamlit") == "1.66.1"
    app = AppTest.from_string('''
import datetime
import streamlit as st

phase = st.session_state.get("phase", "load")
width = {"width": 360} if phase == "width" else {}
clock = st.time_input("Clock", datetime.time(12, 30), format="12h" if phase == "format" else "24h", **width)
moment = st.datetime_input("Moment", datetime.datetime(2024, 3, 15, 12, 30),
    min_value=datetime.datetime(2024, 1, 1) if phase == "bounds" else None,
    max_value=datetime.datetime(2024, 12, 31, 23, 59) if phase == "bounds" else None, **width)
date = st.date_input("Date", datetime.date(2024, 3, 15), **width)
st.json([clock.isoformat(), moment.isoformat(), date.isoformat()])
''')
    phases = ("load", "edit", "format", "width", "restore", "edit-bounds", "bounds", "observe")
    groups = ((0, 0, 0, 1, 0, 0, 0, 0), (0, 0, 0, 1, 0, 0, 2, 0), (0, 0, 0, 1, 0, 0, 0, 0))
    expected = (
        ["12:30:00", "2024-03-15T12:30:00", "2024-03-15"],
        ["13:45:00", "2024-06-01T13:45:00", "2024-06-01"],
        ["13:45:00", "2024-06-01T13:45:00", "2024-06-01"],
        ["12:30:00", "2024-03-15T12:30:00", "2024-03-15"],
        ["12:30:00", "2024-03-15T12:30:00", "2024-03-15"],
        ["13:45:00", "2024-06-01T13:45:00", "2024-06-01"],
        ["13:45:00", "2024-03-15T12:30:00", "2024-06-01"],
        ["13:45:00", "2024-03-15T12:30:00", "2024-06-01"],
    )
    ids = [[], [], []]
    for index, phase in enumerate(phases):
        app.session_state["phase"] = phase
        if phase in ("edit", "edit-bounds"):
            app.time_input[0].set_value(datetime.time(13, 45))
            app.get("date_time_input")[0].set_value(datetime.datetime(2024, 6, 1, 13, 45))
            app.date_input[0].set_value(datetime.date(2024, 6, 1))
        app.run()
        assert not app.exception
        assert json.loads(app.json[0].value) == expected[index], phase
        widgets = (app.time_input[0], app.get("date_time_input")[0], app.date_input[0])
        for position, widget in enumerate(widgets):
            for earlier in range(index):
                assert (widget.id == ids[position][earlier]) == (groups[position][index] == groups[position][earlier]), (phase, position, earlier)
            ids[position].append(widget.id)
    assert [len(set(widget_ids)) for widget_ids in ids] == [2, 3, 2]


UNKEYED_PHASES = ("load", "edit", "format", "width", "restore", "edit-bounds", "bounds", "observe")
UNKEYED_VALUES = (
    ("12:30", "2024-03-15T12:30", "2024-03-15"),
    ("13:45", "2024-06-01T13:45", "2024-06-01"),
    ("13:45", "2024-06-01T13:45", "2024-06-01"),
    ("12:30", "2024-03-15T12:30", "2024-03-15"),
    ("12:30", "2024-03-15T12:30", "2024-03-15"),
    ("13:45", "2024-06-01T13:45", "2024-06-01"),
    ("13:45", "2024-03-15T12:30", "2024-06-01"),
    ("13:45", "2024-03-15T12:30", "2024-06-01"),
)


def check_unkeyed_temporal_wire(capture):
    assert capture["reference_version"] == "1.66.1" and capture["successful"] and "producer_error" not in capture
    assert len(capture["frames"]) == 71 and capture["finishes"] == [0] * 8
    assert capture["cleanup"]["websocket_closed"]
    assert capture["cleanup"]["server_stopped" if capture["runtime"] == "python" else "caller_server_stopped"]
    kinds = []
    for message in frames(capture):
        kind = message.WhichOneof("type")
        kinds.append((kind, message.session_status_changed.script_is_running) if kind == "session_status_changed" else kind)
    expected_kinds = []
    for index in range(8):
        expected_kinds += ["rerun_script"] + ([("session_status_changed", False)] if index else [])
        expected_kinds += ["new_session", ("session_status_changed", True)] + ["delta"] * 4 + ["script_finished"]
    assert kinds == expected_kinds
    runs, emitted = identity_runs(capture)
    assert len(runs) == 8 and len(emitted) == 32
    assert emitted == [(entry["kind"], entry["fields"], entry["delta_path"]) for entry in capture["elements"]]
    groups = ((0, 0, 0, 1, 0, 0, 0, 0), (0, 0, 0, 1, 0, 0, 2, 0), (0, 0, 0, 1, 0, 0, 0, 0))
    ids, sessions, run_ids = ([], [], []), set(), set()
    for index, (run, phase, values) in enumerate(zip(runs, UNKEYED_PHASES, UNKEYED_VALUES, strict=True)):
        request = run["request"]
        assert request.query_string == "probe=unkeyed&phase=" + phase and not request.is_history_navigation
        assert len(run["sessions"]) == 1 and run["finishes"] == [0]
        session = run["sessions"][0]
        assert session.initialize.environment_info.streamlit_version == "1.66.1"
        sessions.add(session.initialize.session_id)
        run_ids.add(session.script_run_id)
        assert [entry[0] for entry in run["entries"]] == ["time_input", "date_time_input", "date_input", "json"]
        assert [entry[3] for entry in run["entries"]] == [[0, position] for position in range(4)]
        for position, label in enumerate(("Clock", "Moment", "Date")):
            _, widget, element, _ = run["entries"][position]
            assert widget.id and widget.label == label and not widget.help and not widget.form_id
            assert not widget.disabled and widget.label_visibility.value == 0 and not widget.ignore_rerun
            assert not widget.set_value and not element.HasField("has_one_shot_effect")
            assert MessageToDict(element.width_config, preserving_proto_field_name=True) == ({"pixel_width": 360} if phase == "width" else {"use_stretch": True})
            for earlier in range(index):
                assert (widget.id == ids[position][earlier]) == (groups[position][index] == groups[position][earlier]), (phase, position, earlier)
            ids[position].append(widget.id)
        clock, moment, date = [entry[1] for entry in run["entries"][:3]]
        assert len({clock.id, moment.id, date.id}) == 3
        assert clock.HasField("default") and clock.default == "12:30" and not clock.HasField("value")
        assert clock.format == ("12h" if phase == "format" else "24h") and clock.step == moment.step == 900
        assert list(moment.default) == ["2024-03-15T12:30"] and list(date.default) == ["2024-03-15"]
        assert not moment.value and not date.value and not date.is_range and not moment.is_range
        assert moment.format == date.format == "YYYY/MM/DD"
        assert (date.min, date.max) == ("2014-03-15", "2034-03-15")
        assert (moment.min, moment.max) == (("2024-01-01T00:00", "2024-12-31T23:59") if phase == "bounds" else ("2014-03-15T00:00", "2034-03-15T23:59"))
        assert json.loads(run["entries"][3][1].body) == {"phase": phase, "values": list(values), "native": []}
        incoming = request.widget_states.widgets
        if phase in ("edit", "edit-bounds"):
            assert len(incoming) == 3
            assert [(widget.id, widget.WhichOneof("value")) for widget in incoming] == [
                (ids[0][index - 1], "string_value"), (ids[1][index - 1], "string_array_value"), (ids[2][index - 1], "string_array_value")]
            assert incoming[0].string_value == values[0]
            assert list(incoming[1].string_array_value.data) == [values[1]] and list(incoming[2].string_array_value.data) == [values[2]]
        else:
            assert not incoming
    assert len(sessions) == 1 and len(run_ids) == 8
    assert [len(set(widget_ids)) for widget_ids in ids] == [2, 3, 2]


@pytest.mark.parametrize("root", (PYTHON, RUST), ids=("python", "rust"))
def test_unkeyed_temporal_native_sequence(root):
    check_unkeyed_temporal_wire(read(root / "unkeyed-identity/trace.json"))


def test_unkeyed_temporal_elements_match_field_for_field():
    left = read(PYTHON / "unkeyed-identity/trace.json")
    right = read(RUST / "unkeyed-identity/trace.json")
    assert left["producer_sources_sha256"] == right["producer_sources_sha256"]
    for capture in (left, right):
        check_unkeyed_temporal_wire(capture)
    sdk_runs, _ = identity_runs(left)
    rust_runs, _ = identity_runs(right)
    for sdk, rust in zip(sdk_runs, rust_runs, strict=True):
        for sdk_entry, rust_entry in zip(sdk["entries"], rust["entries"], strict=True):
            elements = []
            for kind, _, element, _ in (sdk_entry, rust_entry):
                fields = MessageToDict(element, preserving_proto_field_name=True)
                if kind == "json":
                    fields[kind]["body"] = json.loads(fields[kind]["body"])
                else:
                    fields[kind].pop("id")
                elements.append(fields)
            assert elements[0] == elements[1]


@pytest.mark.parametrize("mutation", ("time-format-id", "date-width-id", "datetime-bounds-id", "retained-value", "stale-input-id", "width"))
def test_unkeyed_temporal_gate_rejects_wrong_wire(mutation):
    capture = read(PYTHON / "unkeyed-identity/trace.json")
    source_runs, _ = identity_runs(capture)
    target = {"time-format-id": 2, "date-width-id": 3, "datetime-bounds-id": 6, "retained-value": 2, "stale-input-id": 5, "width": 3}[mutation]
    run = -1
    for frame in capture["frames"]:
        client = frame["direction"] == "client->server"
        if client:
            run += 1
        if run != target:
            continue
        message = BackMsg() if client else ForwardMsg()
        message.ParseFromString(base64.b64decode(frame["base64"]))
        if mutation == "stale-input-id" and client:
            message.rerun_script.widget_states.widgets[0].id = source_runs[3]["entries"][0][1].id
        elif not client and message.WhichOneof("type") == "delta" and message.delta.WhichOneof("type") == "new_element":
            element = message.delta.new_element
            kind = element.WhichOneof("type")
            position = {"time-format-id": 0, "date-width-id": 2, "datetime-bounds-id": 1}.get(mutation)
            if position is not None and kind == ("time_input", "date_time_input", "date_input")[position]:
                getattr(element, kind).id = "wrong-format-identity" if mutation == "time-format-id" else source_runs[0]["entries"][position][1].id
            elif mutation == "retained-value" and kind == "json":
                report = json.loads(element.json.body)
                report["values"][0] = "12:30"
                element.json.body = json.dumps(report)
            elif mutation == "width" and kind == "date_input":
                element.width_config.pixel_width = 361
            else:
                continue
        else:
            continue
        raw = message.SerializeToString()
        frame.update(base64=base64.b64encode(raw).decode(), bytes=len(raw), message=MessageToDict(message, preserving_proto_field_name=True))
    _, emitted = identity_runs(capture)
    capture["elements"] = [{"kind": kind, "fields": fields, "delta_path": path} for kind, fields, path in emitted]
    with pytest.raises(AssertionError):
        check_unkeyed_temporal_wire(capture)


PRECISION_CASES = ("minute-floor", "reversed-seconds", "reversed-micros", "previous-minute", "next-minute", "reversed-minutes",
                   "empty-reversed-seconds", "fraction-boundary-wide", "no-bounds", "max-only", "min-only")
PRECISION_ERRORS = {
    "previous-minute": ("StreamlitValueAboveMaxError", "The `value` 2024-03-15 12:30:00 is greater than the `max_value` 2024-03-15 12:29:00."),
    "next-minute": ("StreamlitValueBelowMinError", "The `value` 2024-03-15 12:30:00 is less than the `min_value` 2024-03-15 12:31:00."),
    "reversed-minutes": ("StreamlitInvalidMinMaxError", "The `min_value`, set to 2024-03-15 12:31:00, cannot be greater than the `max_value`, set to 2024-03-15 12:30:00."),
}


def check_datetime_precision(capture):
    assert capture["reference_version"] == "1.66.1" and capture["successful"] and "producer_error" not in capture
    if capture["runtime"] == "rust":
        assert capture.get("precision_acceptance_match") is True and capture["semantic_match"] is False
    assert capture["cleanup"]["websocket_closed"] and capture["finishes"] == [0]
    assert capture["cleanup"]["server_stopped" if capture["runtime"] == "python" else "caller_server_stopped"]
    messages = list(frames(capture))
    assert [message.WhichOneof("type") for message in messages] == ["rerun_script", "new_session", "session_status_changed"] + ["delta"] * 9 + ["script_finished"]
    assert messages[2].session_status_changed.script_is_running
    assert messages[1].new_session.initialize.environment_info.streamlit_version == "1.66.1"
    request = messages[0].rerun_script
    assert request.query_string == "probe=precision" and not request.widget_states.widgets and not request.is_history_navigation
    runs, emitted = identity_runs(capture)
    assert len(runs) == 1 and len(emitted) == 9
    assert emitted == [(entry["kind"], entry["fields"], entry["delta_path"]) for entry in capture["elements"]]
    entries = runs[0]["entries"]
    accepted = [name for name in PRECISION_CASES if name not in PRECISION_ERRORS]
    assert [entry[0] for entry in entries] == ["date_time_input"] * 8 + ["json"]
    assert [entry[3] for entry in entries] == [[0, index] for index in range(9)]
    reports = json.loads(entries[-1][1].body)
    assert [report["case"] for report in reports] == list(PRECISION_CASES)
    for report in reports:
        name = report["case"]
        if name in PRECISION_ERRORS:
            error_type, error = PRECISION_ERRORS[name]
            if capture["runtime"] == "rust":
                error_type = "InvalidValue"
                error = "invalid widget value: datetime_input " + ("min is after max" if name == "reversed-minutes" else "value is outside min/max")
            assert report == {"case": name, "accepted": False, "error_type": error_type, "error": error}
        else:
            assert report == {"case": name, "accepted": True, "value": None if name == "empty-reversed-seconds" else "2024-03-15T12:30"}
    ids = []
    for name, (_, widget, element, _) in zip(accepted, entries[:-1], strict=True):
        assert widget.label == name and widget.id.endswith("-" + name)
        ids.append(widget.id)
        assert list(widget.default) == ([] if name == "empty-reversed-seconds" else ["2024-03-15T12:30"])
        expected_min = "2014-03-15T00:00" if name in ("no-bounds", "max-only") else "2024-03-15T12:29" if name == "fraction-boundary-wide" else "2024-03-15T12:30"
        expected_max = "2034-03-15T23:59" if name in ("no-bounds", "min-only") else "2024-03-15T12:30"
        assert (widget.min, widget.max) == (expected_min, expected_max)
        assert widget.step == 900 and widget.format == "YYYY/MM/DD" and not widget.is_range
        assert not widget.value and not widget.set_value and not element.HasField("has_one_shot_effect")
        assert not widget.disabled and not widget.help and not widget.form_id and not widget.ignore_rerun and widget.label_visibility.value == 0
        assert MessageToDict(element.width_config, preserving_proto_field_name=True) == {"use_stretch": True}
    assert len(set(ids)) == 8


@pytest.mark.parametrize("root", (PYTHON, RUST), ids=("python", "rust"))
def test_datetime_precision_acceptance_and_rejections(root):
    check_datetime_precision(read(root / "precision/trace.json"))


def test_datetime_precision_accepted_elements_match_field_for_field():
    captures = [read(root / "precision/trace.json") for root in (PYTHON, RUST)]
    assert captures[0]["producer_sources_sha256"] == captures[1]["producer_sources_sha256"]
    normalized = []
    for capture in captures:
        check_datetime_precision(capture)
        runs, _ = identity_runs(capture)
        widgets = []
        for kind, _, element, _ in runs[0]["entries"][:-1]:
            fields = MessageToDict(element, preserving_proto_field_name=True)
            fields[kind].pop("id")
            widgets.append(fields)
        normalized.append(widgets)
    assert normalized[0] == normalized[1]


def test_datetime_precision_before_preserves_five_false_rejections():
    capture = read(RUST / "precision/before/trace.json")
    assert capture["successful"] and capture["semantic_match"] is False
    assert len(capture["frames"]) == 8 and len(capture["elements"]) == 4 and capture["finishes"] == [0]
    runs, _ = identity_runs(capture)
    reports = json.loads(runs[0]["entries"][-1][1].body)
    assert [report["case"] for report in reports if report["accepted"]] == ["fraction-boundary-wide", "no-bounds", "max-only"]
    assert [entry[1].label for entry in runs[0]["entries"][:-1]] == ["fraction-boundary-wide", "no-bounds", "max-only"]
    with pytest.raises(AssertionError):
        check_datetime_precision(capture)


@pytest.mark.parametrize("mutation", ("default-seconds", "wrong-bound", "empty-default", "false-rejection", "invalid-accepted"))
def test_datetime_precision_gate_rejects_wrong_wire(mutation):
    capture = read(PYTHON / "precision/trace.json")
    for frame in capture["frames"]:
        if frame["direction"] != "server->client":
            continue
        message = ForwardMsg()
        message.ParseFromString(base64.b64decode(frame["base64"]))
        if message.WhichOneof("type") != "delta" or message.delta.WhichOneof("type") != "new_element":
            continue
        element = message.delta.new_element
        kind = element.WhichOneof("type")
        if kind == "date_time_input" and element.date_time_input.label == ("empty-reversed-seconds" if mutation == "empty-default" else "minute-floor"):
            if mutation == "wrong-bound":
                element.date_time_input.min = "2024-03-15T12:31"
            elif mutation in ("default-seconds", "empty-default"):
                element.date_time_input.default[:] = ["2024-03-15T12:30:45"]
            else:
                continue
        elif kind == "json" and mutation in ("false-rejection", "invalid-accepted"):
            reports = json.loads(element.json.body)
            if mutation == "false-rejection":
                reports[0] = {"case": "minute-floor", "accepted": False, "error_type": "InvalidValue", "error": "unexpected rejection"}
            else:
                reports[3] = {"case": "previous-minute", "accepted": True, "value": "2024-03-15T12:30"}
            element.json.body = json.dumps(reports)
        else:
            continue
        raw = message.SerializeToString()
        frame.update(base64=base64.b64encode(raw).decode(), bytes=len(raw), message=MessageToDict(message, preserving_proto_field_name=True))
    _, emitted = identity_runs(capture)
    capture["elements"] = [{"kind": kind, "fields": fields, "delta_path": path} for kind, fields, path in emitted]
    with pytest.raises(AssertionError):
        check_datetime_precision(capture)
