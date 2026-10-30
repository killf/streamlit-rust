# queryparams: frozen browser chain

frozen capture data only

Cited by the compatibility matrix under: st.query_params, st.selectbox.

Provenance metadata (capture command, chrome version, exit code) is in [manifest.json](manifest.json); the capture commands and boundaries live in .codex/acceptance.md and the matrix rows above.

## Native WS value and mutation extension (2026-10-29)

[values/trace.json](values/trace.json) is a separate Python 1.66.1 native WS
capture, not an extension of the original browser interaction claims. The
[reference app](../../queryparams_values_app.py) reads repeated query values,
replaces a key, appends encoded text, stores and removes an empty list, deletes
a key, clears the store and restores repeated values.

Eight JSON snapshots are interleaved with seven exact `page_info_changed`
messages. Raw protobuf is retained and decoded by
`test_query_param_values_oracle_is_complete_and_backed_by_wire`; the Rust runtime
regression compares the same ordered snapshots and URL writes. `get` returns
the last repeated value, `get_all` retains URL order, and an empty-list key
exists even though it emits no query pair. URL writes preserve insertion order.

Collect with the pinned reference environment using
`python tests/browser/queryparams_values_capture.py --out <new-directory>`.
The collector owns and stops its server and refuses to overwrite a capture.
Only synthetic URL values are used. Browser URL round trips, embedded keys and
widget-bound mutation restrictions are outside this extension.

## Reserved and empty keys (2026-10-29)

[reserved/trace.json](reserved/trace.json) is a separate native WS capture using
the same app and collector with `--scenario reserved`. It retains nine JSON
reports and four URL writes. The raw frames are decoded by the existing Python
reference gate and replayed by the Rust regression
`query_param_reserved_and_empty_keys_match_frozen_reference`.

The application cannot read/list `embed` or `embed_options`, regardless of
case, and writes/deletes are rejected without a URL update or state mutation.
Public clear retains their exact original URL names and values. An empty key
and `st_embed` are ordinary keys. The reference covers empty-key replacement,
deletion, clear and restoration after clear, using only synthetic values.

The fixture catches rejected operations and reports error presence. This does
not compare Python exception classes/text or rendered error UI. The collector
closed its WS and terminated its owned server. The earlier values and browser
captures remain unchanged; browser embedding and widget binding are separate.

## Binding lifecycle (2026-10-29)

[binding/trace.json](binding/trace.json) records four runs on one native WS:
load, active selectbox plus sidebar text input, conditionally hidden widgets,
then ordinary manual writes after cleanup. Run two explicitly supplies both
URL values and widget states; it does not prove URL-only widget initialization.
The existing collector uses `--scenario binding` to reproduce the input sequence.

Eighteen JSON reports and five URL writes pin registration-time mutation
protection, case-sensitive keys, clear with no bound URL values, rejection
while bound values exist, protection until a hidden run finishes, one cleanup
URL before that run's finish, and successful writes on the following run.
Rust compares the complete ordered JSON/URL sequence. A unit control also
checks explicit unbinding, without claiming its browser/reference parity.

The capture initially retained the collector's legacy single-run
`query_string` header. It was corrected from the first raw BackMsg, with the
old value kept as `original_query_string_header`; the correction is noted in
the file. Raw frames, timestamps and observed results are unchanged. The raw
BackMsg sequence remains the authoritative input for all four runs.

Fresh URL seeding, remount/page restoration, dynamic binding combinations,
callbacks and real browser synchronization remain open.

## URL initialization and history priority (2026-10-29)

[seed/trace.json](seed/trace.json) records eight native WS runs with selectbox,
text input, a clearable selection and a creation-mode selection. Collect with
`--scenario seed`. The input sequence covers initial URL values without widget
states, frontend states that disagree with the URL, another URL-only request,
invalid/default values, empty values, code assignments, history navigation with
values and history navigation with missing values.

The Rust regression compares 32 widget `value`/`raw_value` and `set_value`
projections, eight application snapshots and nine URL corrections in order.
The Python gate decodes all raw frames and checks the eight request/finish
pairs, history flags and priority results. Invalid/default URL values are
removed but ordinary reruns can retain the prior control value; history with
missing parameters restores defaults and tells the frontend to resynchronize.
Programmatic assignments on an existing widget update/collapse the URL, while
frontend defaults can collapse stored parameters without another URL message.

Original browser and earlier native captures remain unchanged. The owned
reference server and connection were closed after collection. No actual browser
Back/Forward operation is claimed. Disabled/forged packets, callbacks, bound
server-started reruns, remount and cross-page restoration remain open.

[seed-code/trace.json](seed-code/trace.json) adds two focused runs for initial
and history URL values overriding incompatible integer assignments to bound
string/select state. It uses `--scenario seed-code` and retains the original
eight-run capture unchanged. Eight widget synchronization projections and two
JSON reports match Rust; a discarded invalid value must not be deserialized
before the selected URL value. The owned reference server was stopped.


## Disabled submissions and callback ordering

[disabled-valid/trace.json](disabled-valid/trace.json) and
[disabled/trace.json](disabled/trace.json) retain independent nine-run captures
from the existing app and collector (`--scenario disabled-valid` / `disabled`).
They cover disabled text/select/checkbox submissions, code assignment, URL
correction, hiding/remounting, both disabled transitions, and enabled callbacks.
The valid capture has 44 widget projections, nine reports and five URL writes.

The malformed capture is intentionally retained: bool oneofs for disabled
text/select and a string for checkbox cause TypeError at select registration.
Plain is already emitted and Live's callback has run. There is no report or URL
correction in that run; script_finished is successful and the next rerun on the
same connection recovers. Its 40 widget projections, eight reports, three URL
writes and one exception form 52 ordered events. User selected this upstream
error/callback/recovery behavior on 2026-10-30, rather than atomic rejection or
silent ignoring. Existing captures were not overwritten to obtain a pass.

The Python gate decodes every original protobuf and checks requests, finishes,
error metadata and report outcomes. Rust compares ordered widget values, flags,
reports, URLs and exception type/message/flags, without fabricating Python
source stack frames. Actual browser error UI and other malformed types remain
unverified. Owned reference processes and sockets were closed by the collector.


## Server-started reruns with bound controls

[rerun/trace.json](rerun/trace.json) retains five client requests, each causing
two runs (`FINISHED_EARLY_FOR_RERUN`, then `FINISHED_SUCCESSFULLY`) without a
second client message. `--scenario rerun` uses the existing app and collector.
The 47 ordered events are 12 URL writes, 15 JSON reports, ten widget value/set
projections and ten finishes. The reports/deltas still queued when the first
synchronous run calls rerun are absent on this measured wire; URL writes remain.
Original captures have not been edited or replaced.

Cases cover initial URL values, frontend inputs with exactly one callback per
changed widget, rerun before either control registers, same-interaction code
assignment and history restoration of missing parameters. The inner rerun
retains frontend/code priority and unseen records. Its URL comes from the last
announced query string, including parameters silently collapsed only in the
prior run's store. Code assignments continue requesting frontend synchronization
through the internal rerun. The Python gate decodes all original protobuf and
checks every request/finish pair and the reports. Rust compares all 47 events.

User selected queue-level discard on 2026-10-30: only unsent old-run Delta
messages are discarded; already-sent frames and URL messages stay. A separate
Rust HTTP/WS regression yields after a first delta, then queues a second delta
and calls rerun, proving only the first survives. This is a runtime scheduling
boundary test, not a new Python/browser comparison. Actual browser behavior,
other scheduling windows, fragments and callback-requested reruns remain open.
The owned reference process and socket were closed after capture.


## Additional message types: policy expansion pending

Three new captures preserve their original observed scheduling windows:

- [navigation-rerun/trace.json](navigation-rerun/trace.json) uses the existing
  navigation_app.py: two client requests, three runs; queued old Navigation
  and ordinary Delta messages are absent after switch_page, while URL and
  lifecycle messages remain. The navigation Rust test now reads this raw
  synchronous reference separately from the retained historical browser trace.
- [rerun-messages/trace.json](rerun-messages/trace.json) retains a cold-call
  window where PageConfig, toast, markdown, balloons, a report and selectbox
  were already sent before interruption. This is timing evidence, not a
  deterministic Rust differential without reproducing the send boundary.
- [rerun-queue/trace.json](rerun-queue/trace.json) first warms the same calls,
  then records queue clearing: PageConfig, markdown and balloons disappear;
  toast, URL and lifecycle messages survive. The warm/control phase and the
  interrupted/completed pair form 11 normalized events in the Rust test.

All raw protobuf and request/finish sequences are checked offline. The current
Delta-only Rust send policy fails the warm queue comparison (toast is dropped
and config retained); the broad Rust regression also found old Navigation
remaining on the switch run. These are retained red evidence, not passed
compatibility claims. The user has been asked whether to expand to the pinned
upstream lifecycle/toast retain list, make a smaller extension, or keep the
known differences. That new decision is pending; the previous choice covered
only Delta discard. All owned reference servers and sockets were closed.


## Additional disabled wire types (2026-10-30)

`disabled-types/trace.json` retains the first single-session attempt: 17 runs,
13 TypeErrors and four snapshots. An array-shaped selectbox value poisons later
runs; later input types in that session cannot be judged independently.
`disabled-types-isolated/trace.json` therefore uses eight fresh WS sessions,
three runs each (load, malformed, recovery on the same WS). It has 24 finishes,
19 snapshots and five TypeErrors; 24 NewSession messages are run lifecycle,
not 24 independent sessions. Session IDs bind each three-run group.

Selectbox bool/int fail after Plain with the integer TypeError; double has the
real-number TypeError. Live callbacks already ran and recovery snapshots retain
two callbacks. The array fails at path [0,0] and still fails on recovery. JSON
selectbox input, bool Plain/Text input and string Check input are ignored in
these measured Python cases. Raw protobuf, real Python stack frames and failed
attempts are retained; stack lengths differ between early/later errors.

Rust now replays all eight cases: 24 runs/130 widget, URL, exception and state
events, plus the original 17-run/40-event single-session sequence. Array errors
precede callbacks and application entry; subsequent requests still fail, while
fresh sessions remain independent. The measured JSON/Plain/Text/Check ignore
behavior also matches. Exception delta_path, type, message and flags are strict;
Python source stacks are preserved without claiming equivalent Rust stack paths.
The collector owns reconnect sockets with ExitStack. No new capture was needed
for this runtime fix. Real browser error UI, enabled/creation selectbox variants,
other oneofs and arbitrary JSON shapes remain open; this does not claim complete
malformed-input compatibility.


## Sixteen-case follow-up (2026-10-30)

`disabled-types-more/trace.json` keeps the original eight cases and adds JSON
list/dict/null/string, int/double arrays, empty bytes and trigger. Sixteen fresh
WS sessions run three steps each: 48 finishes, 33 state snapshots, 15 TypeErrors
and 230 widget/URL/exception/state events. Both older captures remain unchanged.

JSON list/dict and the three repeated-array wire types fail before callbacks
and application entry, and fail again on the following request. JSON null/string
are ignored in these measured cases. Empty bytes produces `expected bytes, str
found`; trigger produces the integer TypeError. Both preserve the Live callback
and recover on the next request. Rust strictly replays the whole new capture,
including exception paths, while retaining the older eight-case and poisoned
session regressions. Container units cover both incoming widget orders.

That sixteen-case fixture contains only empty bytes. The following update adds
nonempty payloads without a production decoder or a new dependency. Python gates check raw PB binding, sessions,
request oneofs, state/callback ledgers and distinct list/dict/bytes errors. JSON
syntax errors, nonempty bytes, enabled/creation controls, arbitrary further
combinations and real error UI remain unverified.


## Nonempty bytes follow-up (2026-10-30)

`disabled-types-bytes/trace.json` retains nineteen isolated three-run cases,
including the prior sixteen and three nonempty bytes submissions: x, quote/NUL/
backslash/CR/LF, and bytes(range(256)). It contains 57 finishes, 39 snapshots,
18 TypeErrors and 272 widget/URL/exception/state events. All earlier captures
remain unchanged. New bytes cases fail at registration after Plain and the Live
callback, then recover on the same WS with both callbacks preserved.

A private Rust test helper now decodes the frozen protobuf JSON's standard
Base64, including non-UTF-8 bytes and control characters, without production
code or dependency changes. Unit vectors check padding/alphabet rejection and
the exact 0..255 payload; the actual WS differential replays all 57 runs.
Python binds every raw PB to its summary and asserts exact bytes. A coherent
reverse-byte-order mutation must fail even though the exception text is unchanged.
JSON syntax errors, other inputs/parameter combinations and real UI remain open.
