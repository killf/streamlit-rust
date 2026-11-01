"""Capture widget creation parameters over owned native WebSockets.

Supports original creation, integer boundaries and keyed dynamic-number runs against
the pinned SDK or a caller-owned Rust server; never overwrites a trace.
"""
import argparse
import base64
from datetime import datetime, timezone
import importlib.metadata
import hashlib
import json
from pathlib import Path
from urllib.parse import parse_qs, urlencode
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
parser = argparse.ArgumentParser(description='Collect the widget-parameter reference once; never overwrite.')
parser.add_argument('--out', type=Path, required=True)
parser.add_argument('--integer-bounds', action='store_true', help='opt-in unbounded and one-sided integer wire probe')
parser.add_argument('--number-sequence', action='store_true', help='keyed number dynamic bounds over one WS')
parser.add_argument('--form-identity', action='store_true', help='keyed/unkeyed inputs moving between forms and root')
parser.add_argument('--color', action='store_true', help='color defaults, widths and callback/state sequence')
parser.add_argument('--color-unkeyed', action='store_true', help='unkeyed color raw-default and effective-width identity')
parser.add_argument('--bool-width', action='store_true', help='keyed/unkeyed checkbox and toggle width identity')
parser.add_argument('--select-policy', action='store_true', help='keyed selectbox creation and multiselect limit identity')
parser.add_argument('--select-unkeyed', action='store_true', help='unkeyed variant of --select-policy, including placeholder/filter changes')
parser.add_argument('--radio-identity', action='store_true', help='keyed/unkeyed radio width, horizontal and raw captions identity')
parser.add_argument('--radio-empty', action='store_true', help='empty options/None-state variant of --radio-identity')
parser.add_argument('--time-empty', action='store_true', help='time ID-only, invalid/legacy formats and effective-default callbacks')
parser.add_argument('--datetime-empty', action='store_true', help='datetime defaults, bounds, legacy input and callback recovery')
parser.add_argument('--datetime-bounds', action='store_true', help='datetime native resets, joint input/bounds, code assignment and observation')
parser.add_argument('--date-single', action='store_true', help='single-date default/legacy/list/bounds normalization and callback sequence')
parser.add_argument('--date-bounds', action='store_true', help='single/complete-range native bounds, callback/reset order and code assignments')
parser.add_argument('--date-implicit', action='store_true', help='implicit-bound single/range mode retention and callback recovery')
parser.add_argument('--date-mode', action='store_true', help='explicit-bound single/range mode resets and callback recovery')
parser.add_argument('--date-strings', action='store_true', help='disabled date string errors after peer callbacks and subsequent recovery')
parser.add_argument('--date-errors', action='store_true', help='isolated disabled date early-type-error and blocked recovery sessions')
parser.add_argument('--date-disabled', action='store_true', help='disabled date callback exposure, restoration and enabled transitions')
parser.add_argument('--date-range', action='store_true', help='range missing/legacy/invalid/bounded inputs and registered-default callbacks')
parser.add_argument('--number-empty', action='store_true', help='numeric ID-only defaults, range/nonfinite fallback and peer callbacks')
parser.add_argument('--text-empty', action='store_true', help='text input/area ID-only defaults, Unicode truncation and peer callbacks')
parser.add_argument('--feedback-empty', action='store_true', help='feedback ID-only defaults, explicit clearing and callback ordering')
parser.add_argument('--feedback-identity', action='store_true', help='feedback raw default, width and keyed icon-type identity')
parser.add_argument('--group-defaults', action='store_true', help='button-group duplicate multi defaults and dynamic default identity')
parser.add_argument('--group-state', action='store_true', help='button-group dynamic options and invalid native-state filtering')
parser.add_argument('--group-policy', action='store_true', help='button-group required policy and keyed selection-mode identity')
parser.add_argument('--group-width', action='store_true', help='keyed/unkeyed pills and segmented-control width identity')
parser.add_argument('--radio-duplicates', action='store_true', help='duplicate radio options, peer changes and callback batch ordering')
parser.add_argument('--format-collisions', action='store_true', help='typed selections with duplicate formatted labels and reordered options')
parser.add_argument('--multi-limits', action='store_true', help='multiselect duplicate defaults and selection-count errors/recovery')
parser.add_argument('--multi-empty', action='store_true', help='multiselect empty/subset options and native typed state')
parser.add_argument('--select-empty', action='store_true', help='string/integer selectbox empty options and native state')
parser.add_argument('--number-permissive', action='store_true', help='equal bounds and nonpositive finite steps, plus rejected range controls')
parser.add_argument('--number-float', action='store_true', help='float variant of the keyed number sequence')
parser.add_argument('--number-unkeyed', action='store_true', help='unkeyed number identity across option changes')
parser.add_argument('--stop-after-run', action='store_true', help='stop after each unkeyed probe report')
parser.add_argument('--resume-after-stop', action='store_true', help='append normal completion and old-ID restoration after stopped runs')
parser.add_argument('--stop-lifecycle', action='store_true', help='button and URL-bound text around early stop and normal cleanup')
parser.add_argument('--url', help='caller-owned Rust server URL (comparison capture)')
args = parser.parse_args()
assert sum((args.integer_bounds, args.number_sequence, args.number_unkeyed, args.stop_lifecycle, args.number_permissive, args.form_identity, args.color, args.color_unkeyed, args.bool_width, args.select_policy, args.radio_identity, args.select_empty, args.multi_empty, args.multi_limits, args.format_collisions, args.radio_duplicates, args.group_width, args.group_policy, args.group_state, args.group_defaults, args.feedback_identity, args.feedback_empty, args.text_empty, args.number_empty, args.time_empty, args.datetime_empty, args.datetime_bounds, args.date_single, args.date_bounds, args.date_range, args.date_mode, args.date_implicit, args.date_disabled, args.date_errors, args.date_strings)) <= 1
assert not args.number_float or args.number_sequence
assert not args.select_unkeyed or args.select_policy
assert not args.radio_empty or args.radio_identity
assert not args.stop_after_run or args.number_unkeyed
assert not args.resume_after_stop or args.stop_after_run
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
    COMMAND = [sys.executable, '-B', '-m', 'streamlit', 'run', str(ROOT / 'tests/reference/widget_params_app.py'),
               '--server.address=127.0.0.1', f'--server.port={PORT}', '--server.headless=true',
               '--server.fileWatcherType=none', '--browser.gatherUsageStats=false']
TRACE = {'schema_version': 1, 'runtime': 'rust' if args.url else 'python', 'reference_version': '1.66.1',
         'captured_at_utc': datetime.now(timezone.utc).isoformat(),
         'scope': 'Element wire of widget creation-parameter edges over one native WS; no browser/UI claim.',
         'server_command': COMMAND, 'server_cleanup': 'caller-owned' if COMMAND is None else 'collector-owned',
         'url': URL, 'frames': [], 'elements': [], 'finishes': []}
if args.color or args.color_unkeyed or args.bool_width or args.select_policy or args.radio_identity or args.select_empty or args.multi_empty or args.multi_limits or args.format_collisions or args.radio_duplicates or args.group_width or args.group_policy or args.group_state or args.group_defaults or args.feedback_identity or args.feedback_empty or args.text_empty or args.number_empty or args.time_empty or args.datetime_empty or args.datetime_bounds or args.date_single or args.date_bounds or args.date_range or args.date_mode or args.date_implicit or args.date_disabled or args.date_errors or args.date_strings:
    TRACE['scope'] = 'Color defaults/widths and fifteen callback/state reruns on one native WS; no browser/UI claim.'
    TRACE['producer_sources_sha256'] = {path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest() for path in (
        'streamlit/examples/widget_params.rs', 'tests/reference/widget_params_app.py', 'tests/browser/widget_params_capture.py')}
if args.color_unkeyed:
    TRACE['scope'] = 'Fifteen unkeyed color raw-default/effective-width identity runs on one native WS; no browser/UI claim.'
if args.bool_width:
    TRACE['scope'] = 'Seven keyed/unkeyed checkbox and toggle width/state runs on one native WS; no browser/UI claim.'
if args.select_policy:
    TRACE['scope'] = 'Nine keyed selectbox creation/multiselect limit identity runs on one native WS; no browser/UI claim.'
if args.select_unkeyed:
    TRACE['scope'] = 'Seventeen unkeyed selection mode/limit/width/placeholder/filter runs on one native WS; no browser/UI claim.'
if args.radio_identity:
    TRACE['scope'] = 'Twelve keyed/unkeyed radio width/horizontal/raw-caption identity runs on one native WS; no browser/UI claim.'
if args.radio_empty:
    TRACE['scope'] = 'Fourteen keyed/unkeyed radio empty options/None/native-state runs on one native WS; no browser/UI claim.'
if args.select_empty:
    TRACE['scope'] = 'Fourteen string/integer selectbox empty options/None/native-state runs on one native WS; no browser/UI claim.'
if args.multi_empty:
    TRACE['scope'] = 'Twelve string/integer multiselect option filtering, empty and native-state runs on one native WS; no browser/UI claim.'
if args.multi_limits:
    TRACE['scope'] = 'Eight multiselect duplicate-default/count-error/recovery runs on one native WS; error representations are runtime-specific, no browser/UI claim.'
if args.format_collisions:
    TRACE['scope'] = 'Ten typed selectbox/multiselect duplicate-label, reordered-option and native-state runs on one native WS; no browser/UI claim.'
if args.radio_duplicates:
    TRACE['scope'] = 'Seven duplicate-radio/peer callback runs on one native WS; no browser/UI claim.'
if args.group_width:
    TRACE['scope'] = 'Seven keyed/unkeyed pills and segmented-control width runs on one native WS; no browser/UI claim.'
if args.group_policy:
    TRACE['scope'] = 'Ten pills/segmented-control required-policy and selection-mode runs on one native WS; no browser/UI claim.'
if args.group_state:
    TRACE['scope'] = 'Ten keyed pills/segmented-control dynamic option and native-state runs on one native WS; no browser/UI claim.'
if args.group_defaults:
    TRACE['scope'] = 'Eight pills/segmented-control duplicate-default and dynamic identity runs on one native WS; no browser/UI claim.'
if args.feedback_identity:
    TRACE['scope'] = 'Twelve keyed/unkeyed feedback raw-default, width and icon-type runs on one native WS; no browser/UI claim.'
if args.feedback_empty:
    TRACE['scope'] = 'Ten feedback ID-only default, clear, callback and native code-state runs on one native WS; no browser/UI claim.'
if args.text_empty:
    TRACE['scope'] = 'Eight text input/area ID-only default, Unicode and peer callback runs on one native WS; no browser/UI claim.'
if args.number_empty:
    TRACE['scope'] = 'Eleven numeric ID-only, bounded/nonfinite and implicit-limit callback runs on one native WS; no browser/UI claim.'
if args.time_empty:
    TRACE['scope'] = 'Twelve time ID-only, invalid/legacy-format, leap-second and effective-default callback runs on one native WS; no browser/UI claim.'
SERVER = WS = None
if args.datetime_empty:
    TRACE['scope'] = 'Eighteen datetime default/bounds/legacy-input and callback recovery runs on one native WS; no browser/UI claim.'
if args.datetime_bounds:
    TRACE['scope'] = 'Fourteen datetime native bounds/reset, joint input/callback and code-state runs on one native WS; no browser/UI claim.'
if args.date_single:
    TRACE['scope'] = 'Sixteen single-date default/legacy/list/bounds and callback runs on one native WS; no empty/range/browser claim.'
if args.date_bounds:
    TRACE['scope'] = 'Thirteen single/complete-range native bounds/reset and callback runs on one native WS; no empty/partial/browser claim.'
if args.date_implicit:
    TRACE['scope'] = 'Twelve keyed single/range implicit-bound native-type retention and callback runs on one native WS; no None/partial/browser claim.'
if args.date_mode:
    TRACE['scope'] = 'Twelve keyed single/range explicit-bound mode reset and callback runs on one native WS; no implicit/empty/partial/browser claim.'
if args.date_strings:
    TRACE['scope'] = 'Twelve isolated disabled date nonempty string error sessions with peer callbacks, recovery, reenable and edit; no trigger/None/browser claim.'
if args.date_errors:
    TRACE['scope'] = 'Thirty-six isolated disabled date protobuf-type-error sessions, load/error/blocked recovery; no JSON/string/empty-container/browser claim.'
if args.date_disabled:
    TRACE['scope'] = 'Twelve single/complete-range disabled callback exposure, restore, code-assignment and recovery runs on one native WS; no wrong-oneof/partial/browser claim.'
if args.date_range:
    TRACE['scope'] = 'Nineteen range missing/legacy/invalid/bounded and registered-default callback runs on one native WS; no valid empty/partial/browser claim.'


def save():
    (OUT / 'trace.json').write_text(json.dumps(TRACE, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')


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
                 open_timeout=10, close_timeout=5, max_size=None, legacy=True)
    steps = [("load", None), ("edit", 7), ("zero-min", None), ("narrow-max", None), ("grow", None),
             ("default", None), ("edit-low", 1), ("raise-min", None), ("step", None),
             ("disabled", None), ("recover", None), ("assign", None)] if args.number_sequence else [("load", None)]
    if args.number_float:
        steps = [(phase, 7.25 if phase == "edit" else 1.25 if phase == "edit-low" else None) for phase, _ in steps]
    if args.number_unkeyed:
        steps = [("load", None), ("edit", 7), ("disabled", None), ("hidden", None), ("ignore", None), ("none", None),
                 ("explicit-step", None), ("explicit-edit", 9), ("restore-step", None), ("minzero", None), ("min-edit", 8),
                 ("restore-min", None), ("width", None), ("width-edit", 6), ("help", None), ("restore", None),
                 ("default", None), ("step2", None), ("maxzero", None), ("negative-edit", -7), ("maxnone", None)]
    if args.resume_after_stop:
        steps += [("normal-resume", None), ("explicit-step", None)]
    if args.stop_lifecycle:
        steps = [(phase, None) for phase in ("load", "submit", "peek", "resume", "hide", "after-hide", "restore", "after-restore")]
    if args.form_identity:
        steps = [(phase, None) for phase in ("load", "edit", "form-a", "form-b", "form-edit", "root-return", "form-a-return")]
    if args.color:
        steps = [("defaults", None), ("load", None), ("short", "abc"), ("short-hash", "#AbC"), ("long", "00ffAA"),
                 ("invalid", "#12"), ("empty", ""), ("lower", "#abcdef"), ("invalid-after-edit", "oops"),
                 ("default-change", None), ("changed-invalid", "!"), ("width", None), ("assign", None),
                 ("native-invalid", None), ("observe", None), ("recover", "123abc")]
    if args.color_unkeyed:
        steps = [("load", None), ("edit", "#a1b2c3"), ("explicit", None), ("explicit-edit", "#112233"),
                 ("width-zero", None), ("width-edit", "#445566"), ("width-neg", None), ("width-one", None),
                 ("width39", None), ("width40", None), ("width41", None), ("width41-edit", "#778899"),
                 ("width40-return", None), ("implicit-return", None), ("observe", None)]
    form_identity_ids = {}
    if args.bool_width:
        steps = [(phase, True if phase in ('edit', 'width-edit', 'edit-restored') else None)
                 for phase in ('load', 'edit', 'width', 'width-edit', 'restore', 'edit-restored', 'observe')]
    bool_ids = {}
    if args.select_policy:
        steps = [(phase, phase in ('edit', 'mode-edit', 'limit-edit'))
                 for phase in ('load', 'edit', 'mode', 'mode-edit', 'width', 'limit', 'limit-edit', 'restore', 'observe')]
        if args.select_unkeyed:
            steps = [(phase, phase.endswith('edit')) for phase in (
                'load', 'edit', 'mode', 'mode-edit', 'width', 'limit', 'limit-edit', 'placeholder', 'placeholder-edit',
                'filter', 'filter-edit', 'filter-return', 'empty-placeholder', 'empty-edit', 'space-placeholder', 'restore', 'observe')]
    select_ids = {}
    if args.radio_identity:
        steps = [(phase, phase.endswith('edit')) for phase in ('load', 'edit', 'width', 'width-edit', 'horizontal', 'horizontal-edit',
                 'captions', 'captions-edit', 'empty', 'empty-edit', 'restore', 'observe')]
        if args.radio_empty:
            steps = [(phase, phase in ('edit', 'none-edit')) for phase in ('load', 'edit', 'empty', 'empty-observe', 'empty-none',
                     'restore', 'none', 'none-edit', 'none-observe', 'restore-index', 'assign-none', 'observe', 'assign-missing', 'missing-observe')]
    radio_ids = {}
    if args.select_empty:
        steps = [(phase, phase in ('edit', 'none-edit')) for phase in ('load', 'edit', 'empty', 'empty-observe', 'empty-none',
                 'restore', 'none', 'none-edit', 'none-observe', 'restore-index', 'assign-none', 'observe', 'assign-missing', 'missing-observe')]
    if args.multi_empty:
        steps = [(phase, phase == 'edit') for phase in ('load', 'edit', 'subset', 'reorder', 'restore', 'assign-partial', 'observe', 'assign-repeat', 'repeat-observe', 'empty', 'empty-observe', 'restore-final')]
    if args.multi_limits:
        steps = [(phase, phase in ('over', 'edit-limit')) for phase in ('load', 'over', 'observe', 'repair', 'repair-observe', 'edit-limit', 'partial', 'repair-final')]
    if args.format_collisions:
        steps = [(phase, phase in ('edit', 'other', 'repeat', 'reorder-edit', 'restore-edit')) for phase in ('load', 'edit', 'other', 'repeat', 'reorder', 'reorder-edit', 'assign', 'observe', 'restore', 'restore-edit')]
    if args.radio_duplicates:
        steps = [(phase, phase not in ('load', 'observe')) for phase in ('load', 'same', 'other', 'back', 'peer', 'both', 'observe')]
    if args.group_width:
        steps = [(phase, phase in ('edit', 'width-edit', 'restore-edit')) for phase in ('load', 'edit', 'width', 'width-edit', 'restore', 'restore-edit', 'observe')]
    if args.group_policy:
        steps = [(phase, phase in ('edit', 'required-edit', 'multi-edit', 'restore-edit')) for phase in ('load', 'edit', 'required', 'required-edit', 'optional', 'multi', 'multi-edit', 'restore', 'restore-edit', 'observe')]
    if args.group_state:
        steps = [(phase, phase in ('edit', 'recover')) for phase in ('load', 'edit', 'subset', 'empty', 'return', 'assign', 'observe', 'clear', 'recover', 'observe-final')]
    if args.group_defaults:
        steps = [(phase, phase in ('edit', 'default-edit', 'return-edit')) for phase in ('load', 'edit', 'default', 'default-edit', 'empty', 'return', 'return-edit', 'observe')]
    if args.feedback_identity:
        steps = [(phase, value) for phase, value in (('load', None), ('edit', 4), ('zero', None), ('zero-edit', 3), ('width', None), ('width-edit', 2), ('faces', None), ('faces-edit', 4), ('thumbs', None), ('thumbs-edit', 1), ('restore', None), ('observe', None))]
    if args.feedback_empty:
        steps = [(phase, values) for phase, values in (('load', None), ('edit', ('4', None)), ('clear', ('', None)), ('peer', (None, '3')), ('default', None), ('fallback', (None, '')), ('assign', None), ('observe', None), ('clear-both', ('', '')), ('recover', ('1', None)))]
    if args.text_empty:
        steps = [(phase, values) for phase, values in (('load', None), ('edit', ('EDIT🙂X', None, True)), ('area', (None, '第一\n行🙂XQ', True)), ('clear', ('', '', False)), ('default', None), ('fallback', (None, None, True)), ('observe', None), ('recover', ('OK', '恢复\n🙂', False)))]
    if args.number_empty:
        steps = [(phase, values) for phase, values in (('load', None), ('edit', (7, None, True)), ('float', (None, 3.5, True)), ('bounds', (99, -99.0, False)), ('default', None), ('fallback', (None, None, True)), ('limits', (None, float('nan'), False)), ('unbounded', None), ('high', (2**63-1, float('inf'), True)), ('recover', (0, -5.0, False)), ('observe', None))]
    if args.time_empty:
        steps = [(phase, values) for phase, values in (('load', None), ('edit', ('13:45', None, True)), ('seconds', (None, '08:09:10', True)), ('formats', ('14:15:59', '09:10', False)), ('invalid', ('not-a-time', '25:99:88', True)), ('empty', ('', '', False)), ('defaults', None), ('fallback', (None, None, True)), ('leap', ('23:59:60', '23:59:60', False)), ('recover', ('01:02:03', '04:05:06', True)), ('observe', None), ('reset', (None, None, False)))]
    time_empty_ids = {}
    datetime_empty_ids = {}
    if args.datetime_empty:
        steps = [('load', None), ('edit', (['2025-03-15T14:35'], True)), ('missing', (None, False)),
                 ('legacy', (['2025/03/15, 15:47'], True)), ('invalid', (['bad'], False)),
                 ('below', (['2025-03-15T07:59'], True)), ('above', (['2025-03-15T18:01'], False)),
                 ('minimum', (['2025-03-15T08:00'], True)), ('maximum', (['2025-03-15T18:00'], False)),
                 ('surplus', (['2025-03-15T15:47', 'bad'], True)), ('empty', ([], False)), ('defaults', None),
                 ('fallback', (None, True)), ('bad-first', (['bad', '2025-03-15T15:47'], False)),
                 ('seconds', (['2025-03-15T15:47:00'], True)), ('recover', (['2025-03-15T15:47'], False)),
                 ('observe', None), ('reset', (None, True))]
    if args.datetime_bounds:
        steps = [('load', None), ('edit', (['2025-03-15T17:00'], True)), ('narrow', None), ('observe', None), ('widen', None),
                 ('joint', (['2025-03-15T17:00'], False)), ('assign', None), ('implicit', None), ('implicit-observe', None),
                 ('explicit-none', None), ('none-observe', None), ('recover', (['2025-03-15T15:47'], True)), ('reset', None), ('final', None)]
    number_empty_ids = {}
    date_single_ids = {}
    if args.date_single:
        steps = [('load', None), ('edit', (['2025-04-20'], True)), ('missing', (None, False)), ('legacy', (['2025/05/07'], True)),
                 ('surplus', (['2025-05-07', '2025-06-08'], False)), ('bad-tail', (['2025-05-07', 'bad'], True)),
                 ('bad-first', (['bad', '2025-05-07'], False)), ('below', (['2024-12-31'], True)),
                 ('above-tail', (['2025-05-07', '2026-01-01'], False)), ('minimum', (['2025-01-01'], True)),
                 ('maximum', (['2025-12-31'], False)), ('defaults', None), ('fallback', (None, True)), ('observe', None),
                 ('recover', (['2025-07-15'], False)), ('invalid', (['bad'], True))]
    if args.date_mode or args.date_implicit:
        steps = [('load', None), ('edit', (['2025-04-20'], True)), ('range', None), ('range-edit', (['2025-05-01', '2025-05-10'], False)),
                 ('single', None), ('single-edit', (['2025-06-01', '2025-06-10'], True)), ('range-narrow', None), ('range-observe', None),
                 ('range-recover', (['2025-03-10', '2025-03-20'], False)), ('single-narrow', None), ('single-recover', (['2025-03-12'], True)), ('single-observe', None)]
    text_empty_ids = {}
    date_bounds_ids = {}
    if args.date_bounds:
        steps = [('load', None), ('edit', ('2025-04-20', '2025-05-20', True)), ('narrow', None), ('observe', None), ('widen', None),
                 ('joint', ('2025-04-25', '2025-05-25', False)), ('assign', None), ('implicit', None), ('implicit-observe', None),
                 ('minimum', None), ('maximum', None), ('lower', None), ('final', None)]
    if args.date_range:
        steps = [('load', None), ('range-edit', ('2025-04-01', ['2025-04-10', '2025-04-20'], True)), ('range-missing', (None, None, False)),
                 ('range-legacy', ('2025-04-01', ['2025/05/01', '2025/05/10'], True)), ('range-bad-start', ('2025-04-01', ['bad', '2025-05-10'], False)),
                 ('range-bad-end', ('2025-04-01', ['2025-05-01', 'bad'], True)), ('range-low', ('2025-04-01', ['2024-12-31', '2025-05-10'], False)),
                 ('range-high', ('2025-04-01', ['2025-05-01', '2026-01-01'], True)), ('range-minmax', ('2025-04-01', ['2025-01-01', '2025-12-31'], False)),
                 ('range-equal', ('2025-04-01', ['2025-05-01', '2025-05-01'], True)), ('range-reverse', ('2025-04-01', ['2025-05-10', '2025-05-01'], False)),
                 ('range-mixed', ('2025-04-01', ['2025-05-01', '2025/05/10'], True)), ('range-invalid-one', ('2025-04-01', ['bad'], False)),
                 ('range-invalid-many', ('2025-04-01', ['2025-05-01', 'bad', '2025-05-10'], True)), ('range-defaults', None),
                 ('range-fallback', (None, None, False)), ('range-observe', None), ('range-recover', ('2025-04-01', ['2025-07-01', '2025-07-10'], True)),
                 ('range-invalid-final', ('2025-04-01', ['bad', '2025-07-10'], False))]
    if args.date_disabled:
        steps = [('disabled-load', None), ('disabled-forged', ('2025-04-01', ['2025-04-10','2025-04-20'], True)), ('disabled-observe', None),
                 ('enabled-joint', ('2025-05-01', ['2025-05-10','2025-05-20'], False)), ('enabled-edit', ('2025-06-01', ['2025-06-10','2025-06-20'], True)),
                 ('disabled-joint', ('2025-07-01', ['2025-07-10','2025-07-20'], False)), ('disabled-invalid', ('bad', ['bad','2025-08-20'], True)),
                 ('disabled-legacy', ('2025/08/01', ['2025/08/10','2025/08/20'], False)), ('disabled-assign', ('2025-09-01', ['2025-09-10','2025-09-20'], True)),
                 ('disabled-final', None), ('enabled-return', None), ('enabled-recover', ('2025-11-01', ['2025-11-10','2025-11-20'], False))]
    if args.date_errors:
        TRACE['cases'] = [{'target':target,'kind':kind,'value':value,'peer_first':peer_first}
                          for target in ('Single','Range')
                          for kind,value in (('bool_value',True),('bool_value',False),('trigger_value',True),('trigger_value',False),
                                             ('int_value',7),('double_value',1.5),('int_array_value',[7]),('double_array_value',[1.5]),('bytes_value','eA=='))
                          for peer_first in (False,True)]
        steps = [(attempt,None) for case in TRACE['cases'] for attempt in ('load','malformed','recovery')]
    if args.date_strings:
        TRACE['cases'] = [{'target':target,'value':text,'peer_first':peer_first} for target in ('Single','Range')
                          for text in ('bad','2025-04-10','日期🧊') for peer_first in (False,True)]
        steps = [(attempt,None) for case in TRACE['cases'] for attempt in ('seed','malformed','recovery','enable','edit')]
    feedback_ids = {}
    group_ids = {}
    empty_select_ids = {}
    lifecycle_bound, lifecycle_ids = "url", {}
    number_id = None
    color_id = None
    for step_index, (phase, submitted) in enumerate(steps):
        request = BackMsg()
        if args.date_errors or args.date_strings:
            case_index, attempt = divmod(step_index,5 if args.date_strings else 3)
            case = TRACE['cases'][case_index]
            if attempt == 0 and case_index:
                WS.close()
                WS = connect(URL.replace('http','ws')+'/_stcore/stream',origin=URL,subprotocols=['streamlit'],proxy=None,
                             open_timeout=10,close_timeout=5,max_size=None,legacy=True)
                date_bounds_ids.clear()
            fixture_phase = ('disabled-assign' if attempt == 0 else 'disabled-load' if attempt < 3 else 'enabled-joint') if args.date_strings else 'disabled-load'
            request.rerun_script.query_string = 'probe=date-disabled&phase='+fixture_phase+'&case='+str(case_index)+'&attempt='+phase
            if attempt:
                order = ('Peer',) if args.date_strings and attempt == 2 else ('Peer',case['target']) if case['peer_first'] and (not args.date_strings or attempt == 1) else (case['target'],'Peer')
                for label in order:
                    widget = request.rerun_script.widget_states.widgets.add(id=date_bounds_ids[label])
                    if label == 'Peer':widget.bool_value = attempt in (1,3)
                    elif args.date_strings:
                        if attempt == 1:widget.string_value = case['value']
                        else:widget.string_array_value.data[:] = (['2025-08-01'] if label == 'Single' else ['2025-08-10','2025-08-20']) if attempt == 3 else (['2025-11-01'] if label == 'Single' else ['2025-11-10','2025-11-20'])
                    elif attempt == 2:widget.string_array_value.data[:] = ['2025-04-10'] if label == 'Single' else ['2025-04-10','2025-04-20']
                    elif case['kind'].endswith('array_value'):getattr(widget,case['kind']).data[:] = case['value']
                    elif case['kind'] == 'bytes_value':widget.bytes_value = base64.b64decode(case['value'],validate=True)
                    else:setattr(widget,case['kind'],case['value'])

        if args.date_bounds or args.date_range or args.date_disabled:
            request.rerun_script.query_string = 'probe=' + ('date-disabled' if args.date_disabled else 'date-range' if args.date_range else 'date-bounds') + '&phase=' + phase
            if submitted is not None:
                if args.date_range or args.date_disabled:
                    single, dates, peer = submitted
                else:
                    start, end, peer = submitted
                    single, dates = start, [start, end]
                for label in ('Single', 'Range', 'Peer'):
                    widget = request.rerun_script.widget_states.widgets.add(id=date_bounds_ids[label])
                    if label == 'Peer': widget.bool_value = peer
                    elif label == 'Single' and single is not None: widget.string_array_value.data[:] = [single]
                    elif label == 'Range' and dates is not None:
                        widget.string_array_value.SetInParent();widget.string_array_value.data[:] = dates
        if args.date_single or args.date_mode or args.date_implicit:
            request.rerun_script.query_string = 'probe=' + ('date-implicit' if args.date_implicit else 'date-mode' if args.date_mode else 'date-single') + '&phase=' + phase
            if submitted is not None:
                values, peer = submitted
                for label in ('Day', 'Peer'):
                    widget = request.rerun_script.widget_states.widgets.add(id=date_single_ids[label])
                    if label == 'Peer': widget.bool_value = peer
                    elif values is not None:
                        widget.string_array_value.SetInParent();widget.string_array_value.data[:] = values
        if args.datetime_empty or args.datetime_bounds:
            request.rerun_script.query_string = 'probe=' + ('datetime-bounds' if args.datetime_bounds else 'datetime-empty') + '&phase=' + phase
            if submitted is not None:
                values, peer = submitted
                for label in ('Moment', 'Optional', 'Peer'):
                    widget = request.rerun_script.widget_states.widgets.add(id=datetime_empty_ids[label])
                    if label == 'Peer':
                        widget.bool_value = peer
                    elif values is not None:
                        widget.string_array_value.SetInParent()
                        widget.string_array_value.data[:] = values
        if args.time_empty:
            request.rerun_script.query_string = 'probe=time-empty&phase=' + phase
            if submitted is not None:
                for label, value in zip(('Minute', 'Seconds', 'Peer'), submitted, strict=True):
                    widget = request.rerun_script.widget_states.widgets.add()
                    widget.id = time_empty_ids[label]
                    if label == 'Peer':
                        widget.bool_value = value
                    elif value is not None:
                        widget.string_value = value
        if args.number_empty:
            request.rerun_script.query_string = 'probe=number-empty&phase=' + phase
            if submitted is not None:
                for label, value in zip(('Integer', 'Float', 'Peer'), submitted, strict=True):
                    widget = request.rerun_script.widget_states.widgets.add()
                    widget.id = number_empty_ids[label]
                    if label == 'Peer':
                        widget.bool_value = value
                    elif value is not None:
                        if label == 'Integer':
                            widget.int_value = value
                        else:
                            widget.double_value = value
        if args.text_empty:
            request.rerun_script.query_string = 'probe=text-empty&phase=' + phase
            if submitted is not None:
                for label, value in zip(('Input', 'Area', 'Peer'), submitted, strict=True):
                    widget = request.rerun_script.widget_states.widgets.add()
                    widget.id = text_empty_ids[label]
                    if label == 'Peer':
                        widget.bool_value = value
                    elif value is not None:
                        widget.string_value = value
        if args.feedback_empty:
            request.rerun_script.query_string = 'probe=feedback-empty&phase=' + phase
            if submitted is not None:
                for position, value in enumerate(submitted):
                    widget = request.rerun_script.widget_states.widgets.add()
                    widget.id = feedback_ids[position]
                    if value is not None:
                        widget.string_value = value
        if args.feedback_identity:
            request.rerun_script.query_string = 'probe=feedback-identity&phase=' + phase
            if submitted is not None:
                for position in range(2):
                    widget = request.rerun_script.widget_states.widgets.add()
                    widget.id = feedback_ids[position]
                    widget.string_value = str(submitted)
        if args.group_defaults:
            request.rerun_script.query_string = 'probe=group-defaults&phase=' + phase
            if submitted:
                for label in ('Plain pills', 'Keyed pills', 'Plain segments', 'Keyed segments'):
                    widget = request.rerun_script.widget_states.widgets.add()
                    widget.id = group_ids[label]
                    widget.string_array_value.data.extend(['Alpha', 'Beta', 'Alpha'] if phase == 'edit' else ['Beta', 'Beta'] if phase == 'default-edit' else ['Alpha'])
        if args.group_state:
            request.rerun_script.query_string = 'probe=group-state&phase=' + phase
            if submitted:
                for position, label in enumerate(('Single pills', 'Multi pills', 'Single segments', 'Multi segments')):
                    widget = request.rerun_script.widget_states.widgets.add()
                    widget.id = group_ids[label]
                    widget.string_array_value.data.extend(['Alpha'] if position % 2 == 0 else ['Beta', 'Alpha', 'Beta'] if phase == 'edit' else ['Alpha', 'Beta'])
        if args.group_policy:
            request.rerun_script.query_string = 'probe=group-policy&phase=' + phase
            if submitted:
                for label in ('Plain pills', 'Keyed pills', 'Plain segments', 'Keyed segments'):
                    widget = request.rerun_script.widget_states.widgets.add()
                    widget.id = group_ids[label]
                    widget.string_array_value.data.extend(['Beta', 'Alpha'] if phase == 'multi-edit' else ['Alpha'] if phase == 'required-edit' else ['Beta'])
        if args.group_width:
            request.rerun_script.query_string = 'probe=group-width&phase=' + phase
            if submitted:
                for label in ('Plain pills', 'Keyed pills', 'Plain segments', 'Keyed segments'):
                    widget = request.rerun_script.widget_states.widgets.add()
                    widget.id = group_ids[label]
                    widget.string_array_value.data.extend(['Beta'])
        if args.radio_duplicates:
            request.rerun_script.query_string = 'probe=radio-duplicates&phase=' + phase
            if submitted:
                for label in ('Choice', 'Peer'):
                    widget = request.rerun_script.widget_states.widgets.add()
                    widget.id = radio_ids[label]
                    widget.string_value = ('Other' if phase in ('other', 'both') else 'Same') if label == 'Choice' else ('Ready' if phase == 'peer' else 'Idle')
        if args.format_collisions:
            request.rerun_script.query_string = 'probe=format-collisions&phase=' + phase
            if submitted:
                for label in ('Choice', 'Keyed choice', 'Choices'):
                    widget = request.rerun_script.widget_states.widgets.add()
                    widget.id = empty_select_ids[label]
                    text = 'Other' if phase == 'other' else 'Same'
                    if label == 'Choices':
                        widget.string_array_value.data.extend([text] * (2 if phase in ('repeat', 'reorder-edit') else 1))
                    else:
                        widget.string_value = text
        if args.multi_limits:
            request.rerun_script.query_string = 'probe=multi-limits&phase=' + phase
            if submitted:
                widget = request.rerun_script.widget_states.widgets.add()
                widget.id = empty_select_ids['State']
                widget.string_array_value.data.extend(['1', '2', '3'] if phase == 'over' else ['1', '3'])
        if args.multi_empty:
            request.rerun_script.query_string = 'probe=multi-empty&phase=' + phase
            if submitted:
                for label in ('Choice', 'Keyed choice', 'Number'):
                    widget = request.rerun_script.widget_states.widgets.add()
                    widget.id = empty_select_ids[label]
                    widget.string_array_value.data.extend(['1', '2'] if label == 'Number' else ['Alpha', 'Beta'])
        if args.select_empty:
            request.rerun_script.query_string = 'probe=select-empty&phase=' + phase
            if submitted:
                for label in ('Choice', 'Keyed choice', 'Number'):
                    widget = request.rerun_script.widget_states.widgets.add()
                    widget.id = empty_select_ids[label]
                    widget.string_value = '2' if label == 'Number' else 'Beta'
        if args.radio_identity:
            request.rerun_script.query_string = 'probe=' + ('radio-empty' if args.radio_empty else 'radio-identity') + '&phase=' + phase
            if submitted:
                for label in ('Choice', 'Keyed choice'):
                    widget = request.rerun_script.widget_states.widgets.add()
                    widget.id = radio_ids[label]
                    widget.string_value = 'Beta'
        if args.select_policy:
            request.rerun_script.query_string = "probe=" + ("select-policy-unkeyed" if args.select_unkeyed else "select-policy") + "&phase=" + phase
            if submitted:
                widget = request.rerun_script.widget_states.widgets.add()
                widget.id = select_ids['selectbox']
                widget.string_value = 'Novel' if phase == 'mode-edit' else 'Beta'
                widget = request.rerun_script.widget_states.widgets.add()
                widget.id = select_ids['multiselect']
                widget.string_array_value.data.extend(['Beta', 'Charlie'] if phase == 'mode-edit' else ['Beta'] if phase == 'edit' else ['Charlie'])
        if args.bool_width:
            request.rerun_script.query_string = "probe=bool-width&phase=" + phase
            if submitted is not None:
                assert len(bool_ids) == 4
                for label in ('Unkeyed check', 'Unkeyed toggle', 'Keyed check', 'Keyed toggle'):
                    widget = request.rerun_script.widget_states.widgets.add()
                    widget.id = bool_ids[label]
                    widget.bool_value = submitted
        if args.color or args.color_unkeyed:
            request.rerun_script.query_string = "probe=" + ("color-unkeyed" if args.color_unkeyed else "color") + "&phase=" + phase
            if submitted is not None:
                widget = request.rerun_script.widget_states.widgets.add()
                widget.id = color_id
                widget.string_value = submitted
        if args.number_sequence or args.number_unkeyed:
            request.rerun_script.query_string = "probe=" + ("number-unkeyed" if args.number_unkeyed else "number-float" if args.number_float else "number-sequence") + "&phase=" + phase
            if args.stop_after_run and step_index < 21:
                request.rerun_script.query_string += "&stop=on"
            if submitted is not None:
                assert number_id is not None
                widget = request.rerun_script.widget_states.widgets.add()
                widget.id = number_id
                if args.number_float:
                    widget.double_value = submitted
                else:
                    widget.int_value = submitted
        if args.stop_lifecycle:
            request.rerun_script.query_string = "probe=stop-lifecycle&phase=" + phase
            if lifecycle_bound is not None:
                request.rerun_script.query_string += "&" + urlencode({"bound": lifecycle_bound})
            if phase == "submit":
                for key, value in (("fire", True), ("plain", "edited"), ("bound", "changed")):
                    widget = request.rerun_script.widget_states.widgets.add()
                    widget.id = lifecycle_ids[key]
                    if key == "fire":
                        widget.trigger_value = value
                    else:
                        widget.string_value = value
        request.rerun_script.SetInParent()
        if args.form_identity:
            request.rerun_script.query_string = "probe=form-identity&phase=" + phase
            if phase in ("edit", "form-edit"):
                for key, value in (("number", 7 if phase == "edit" else 8), ("note", "EDIT" if phase == "edit" else "NEXT"), ("unkeyed", 9 if phase == "edit" else 6)):
                    widget = request.rerun_script.widget_states.widgets.add()
                    widget.id = form_identity_ids[key]
                    if key == "note":
                        widget.string_value = value
                    else:
                        widget.int_value = value
                if phase == "form-edit":
                    widget = request.rerun_script.widget_states.widgets.add()
                    widget.id = form_identity_ids["apply"]
                    widget.trigger_value = True
        if args.number_permissive:
            request.rerun_script.query_string = "probe=number-permissive"
        if args.integer_bounds:
            request.rerun_script.query_string = "probe=integer-bounds"
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
            if args.stop_lifecycle and kind == 'page_info_changed':
                lifecycle_bound = parse_qs(message.page_info_changed.query_string, keep_blank_values=True).get('bound', [None])[-1]
            if kind == 'script_finished':
                TRACE['finishes'].append(message.script_finished)
                break
            if kind != 'delta':
                continue
            delta_kind = message.delta.WhichOneof('type')
            if delta_kind == 'add_block':
                block = message.delta.add_block
                allowed = block.WhichOneof('type')
                if allowed is not None:
                    view = getattr(block, allowed)
                    fields = MessageToDict(view, preserving_proto_field_name=True)
                    block_level = {}
                    if block.HasField('width_config'):
                        block_level['width_config'] = MessageToDict(block.width_config, preserving_proto_field_name=True)
                    if block.HasField('height_config'):
                        block_level['height_config'] = MessageToDict(block.height_config, preserving_proto_field_name=True)
                    TRACE['elements'].append({'index': index, 'kind': f'add_block:{allowed}', 'fields': fields, 'block': block_level,
                                              'url': None, 'delta_path': list(message.metadata.delta_path)})
                    index += 1
            elif delta_kind == 'new_element':
                element = message.delta.new_element
                element_kind = element.WhichOneof('type')
                if element_kind is not None:
                    view = getattr(element, element_kind)
                    fields = MessageToDict(view, preserving_proto_field_name=True)
                    if (args.color or args.color_unkeyed) and element_kind == 'color_picker' and view.label == ('Unkeyed accent' if args.color_unkeyed else 'Accent'):
                        color_id = view.id
                    if args.bool_width and element_kind == 'checkbox':
                        bool_ids[view.label] = view.id
                    if args.select_policy and element_kind in ('selectbox', 'multiselect'):
                        select_ids[element_kind] = view.id
                    if args.time_empty and element_kind in ('time_input', 'checkbox'):
                        time_empty_ids[view.label] = view.id
                    if (args.datetime_empty or args.datetime_bounds) and element_kind in ('date_time_input', 'checkbox'):
                        datetime_empty_ids[view.label] = view.id
                    if (args.date_single or args.date_mode or args.date_implicit) and element_kind in ('date_input', 'checkbox'):
                        date_single_ids[view.label] = view.id
                    if (args.date_bounds or args.date_range or args.date_disabled or args.date_errors or args.date_strings) and element_kind in ('date_input', 'checkbox'):
                        date_bounds_ids[view.label] = view.id
                    if args.number_empty and element_kind in ('number_input', 'checkbox'):
                        number_empty_ids[view.label] = view.id
                    if args.text_empty and element_kind in ('text_input', 'text_area', 'checkbox'):
                        text_empty_ids[view.label] = view.id
                    if (args.feedback_identity or args.feedback_empty) and element_kind == 'feedback':
                        feedback_ids[index] = view.id
                    if (args.group_width or args.group_policy or args.group_state or args.group_defaults) and element_kind == 'button_group':
                        group_ids[view.label] = view.id
                    if (args.radio_identity or args.radio_duplicates) and element_kind == 'radio':
                        radio_ids[view.label] = view.id
                    if args.format_collisions and element_kind in ('selectbox', 'multiselect'):
                        empty_select_ids[view.label] = view.id
                    if args.multi_limits and element_kind == 'multiselect':
                        empty_select_ids[view.label] = view.id
                    if args.multi_empty and element_kind == 'multiselect':
                        empty_select_ids[view.label] = view.id
                    if args.select_empty and element_kind == 'selectbox':
                        empty_select_ids[view.label] = view.id
                    if args.stop_lifecycle and element_kind in ('button', 'text_input'):
                        lifecycle_ids[view.id.rsplit('-', 1)[-1]] = view.id
                    if args.form_identity and element_kind in ('number_input', 'text_input', 'button'):
                        key = 'unkeyed' if view.label == 'Unkeyed' else view.id.rsplit('-', 1)[-1]
                        form_identity_ids[key] = view.id
                    if element_kind == 'number_input':
                        number_id = view.id
                    url = getattr(view, 'url', '') if hasattr(view, 'url') else ''
                    TRACE['elements'].append({'index': index, 'kind': element_kind, 'fields': fields,
                                              'url': url, 'delta_path': list(message.metadata.delta_path)})
                    index += 1
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
