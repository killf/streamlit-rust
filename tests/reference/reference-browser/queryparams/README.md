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


## JSON syntax and decoder acceptance reference (2026-10-31)

`disabled-json/trace.json` uses 24 isolated three-run sessions: 72 finishes,
34 snapshots, 38 exceptions and 252 widget/URL/exception/state events. Seventeen
malformed JSON strings produce `json.decoder.JSONDecodeError` before callbacks
and entry, and fail again on the following request. Python accepts NaN,
Infinity, -Infinity, a lone-surrogate escape and 1e9999 in these disabled inputs;
the application ignores them and preserves Live callbacks/recovery. [NaN] and
an object containing Infinity decode successfully, then fail as unhashable
list/dict in both requests. This distinguishes JSON syntax from container errors.

Exact messages include Python 3.14 trailing-comma wording and Unicode character
positions: the multiline emoji example is line 2 column 2, char 7 (not UTF-8
byte offset 10). `runtime.json` is explicitly post-capture interpreter readback:
Streamlit 1.66.1, Python 3.14.7. Original NewSession environment fields also
record the versions and are checked on every run. The trace remains unchanged.

Python gates bind raw PB to summaries, exact input lexemes, 24 session IDs,
all callbacks/snapshots and persistent failures. Coherent mutations of exception
kind, Unicode offset and accepted NaN input must fail. A separate direct parser
probe found Python accepts seven JSON decoder inputs whereas cached serde_json
1.0.145 Value decoding rejects all 24. Its existing IgnoredAny decoding accepts
the lone-surrogate/overflow cases, while still rejecting the other five special
inputs. That is library evidence, not Rust service WS parity.
The current Rust flow does not implement the new JSONDecodeError path. The
private scanner/IgnoredAny-adaptation/defer alternatives await a choice in
.codex/architecture.md; no production parser or dependency was added.


## Real Chrome history: replacement and same-document navigation (2026-10-31)

`history-ui/trace.json` and `tests/browser/rust-queryparams/history-ui/trace.json`
reuse the existing queryparams Python app/Rust example without code changes.
All UI actions used the computer-use browser API, including actual Back/Forward;
no synthetic history state, frontend injection or native-WS history flags.
Each trace retains raw CDP payloads, DOM snapshots/cursors, console logs and four
JPEGs. Reference versions are checked against the original NewSession frames;
the additional environment readback is explicitly post-capture.

The first journey started at `?mode=demo`, created Pick=c, selected Bound=y and
then x. Binding edits replace the current URL, so Back reached about:blank rather
than y. Forward reloaded with Pick=a/Bound=x. A direct document navigation to
`?mode=demo&bound=y`, Back and Forward showed the appropriate URL-seeded values.
These records preserve a Python Connecting/disabled intermediate snapshot and
one/two Python/Rust WebSocket onerror messages. CDP also reported buffer eviction
in both document journeys. Their 70/60 retained frames form seven/six complete
runs, but are not an exhaustive ledger of navigation requests or reconnections.
The unavailable history-inspection command and origin denial on about:blank are
recorded as observation limitations; neither was bypassed.

The second journey starts at `?bound=y`. The app writes mode=demo, creating a
same-document history entry. Create Pick=c, select Bound=x, Back, then Forward:

| Stage | URL query after the run | Pick | Bound | Request history flag |
| --- | --- | --- | --- | --- |
| initial | bound=y&mode=demo | a | y | false |
| pick-c | bound=y&mode=demo | c | y | false |
| bound-x | mode=demo | c | x | false |
| back-y | bound=y&mode=demo | c | y | true |
| forward-x | mode=demo | c | x | true |

Each side has exactly five complete runs/50 frames, one session ID, no buffer
eviction and no console warnings/errors. On Back the request still submits old
widget x, and on Forward old widget y: the URL wins, including absent-key default
restoration. Both navigation responses set the bound widget value explicitly.
Ordinary Pick=c persists throughout. The gate decodes every retained PB, asserts
message order/paths, inputs, URL writes, widget synchronization and output values,
then binds each same-document run to its observed DOM cursor. It verifies all
eight JPEGs and rejects five mutations, including wrong raw history flags and
coherently changed raw output/DOM. Reproduce with the same app, two fresh tabs,
local ports 18515/8515, and the two starting URLs above; prepare the tab/enable
Network recording before the recorded initial navigation. A preparation document
is explicitly outside the same-document capture.

This verifies one query-bound selectbox and one unbound creation-mode selectbox.
It does not close callback, fragment, multipage, other binding controls, reload
persistence or general browser-history compatibility. All owned tabs and servers
were closed; ports were read back free. No production API, queue policy or pending
JSON parser decision changed.


## Query percent decoding and writeback (2026-10-31)

`encoding/trace.json` reuses the existing values app and native-WS collector:

```
target/pyref-venv/Scripts/python.exe tests/browser/queryparams_values_capture.py --scenario encoding --out <new-directory>
```

Sixteen requests in one session each execute the existing eight snapshots and
seven URL mutations: 128 snapshots/112 URL writes, 240 interleaved events.
Original frames and decoded summaries are retained. The NewSession environment
records Streamlit 1.66.1/Python 3.14.7.final.0 and is checked on every run.

The old Rust decoder used an integer parser that accepts a leading plus, so
`tag=%+1&%+f=key` read a control value/key instead of Python's literal `% 1`/`% f`.
The fix only requires two ASCII hex digits after percent. The ordinary plus to
space rule still applies to malformed escapes; valid `%2B` remains a literal plus
and `%2520` decodes only once to `%20`. The first retained URL write is
`tag=replacement&tag=tail&%25+f=key&keep=ok`.

Other cases cover short/bad percent tokens; hex letter case; space/plus;
NUL, tab, CR, LF and DEL; Chinese/emoji/raw Unicode; invalid and truncated UTF-8;
encoded ampersand/equal/hash/question/slash; semicolon and extra equals;
repeated/empty/Unicode-equivalent keys; and the existing mutation order.
Static initial-state literals bind the frozen meaning, raw PB is bound to each
summary, and URL writes are independently checked against standard urlencode.
Four coherent mutations of a raw value, key, replacement-character count or
request lexeme must fail. Source fingerprints do not gate behavior evidence.

Rust unit and real-WS regressions failed before the production change; all 240
events match after it. This is native protocol/API evidence, with no new DOM,
screenshot, browser-normalization or general input-grammar claim. The existing
browser history records were reused, not recaptured for this decoder fix.
The reference socket/server were closed and its port 49353 was read back free.


## Text lengths, callbacks and value sources (2026-10-31)

`text-length/trace.json` reuses the query-selected forms reference, with the
existing form-max-chars-cjk handler's new probe=length branch. Without that flag
the original case is unchanged. The existing native collector accepts
`--scenario text-length`; it creates one fresh WS per kind/limit/default and
never overwrites an old capture. Its source is development-only.

Eight sessions x nine requests cover text_input/text_area with max_chars=5,
max_chars=0, no limit, and a None default. Each records load, ASCII, Unicode,
same-prefix/different-suffix, ZWJ sequence, empty input, application assignment,
retention without input and later input recovery. There are 72 snapshots and
72 widget synchronization projections; 928 original frames and decoded summaries
are retained. Every NewSession records and checks Python 1.66.1/3.14.7.final.0.

Both widgets slice defaults and incoming string values by Python Unicode code
points before comparing changes/dispatching callbacks. Thus a five-code-point
Chinese/emoji/combining-mark prefix is retained; changing only its discarded
suffix does not cause another callback. A ZWJ sequence can be split by that
limit; this is not grapheme counting. Zero deserializes to an empty string,
whereas None means no limit and a None default stays None until input arrives.
The wire still carries the original untruncated default and the configured
max_chars. Code assignment to code長🧊extra is not truncated, sends an explicit
value synchronization, and remains on the next request; later frontend input
is deserialized and truncated again. Callback logs contain the deserialized
value, not the discarded suffix.

The Rust codec now truncates while decoding string input, validates the native
text type separately, and normalizes only the two widgets' default values.
Public APIs and all other codec policies stay as before. The old form unit's
oversized-string batch rejection expectation is corrected to acceptance with
truncated text, checkbox/submit updates and a submit callback observing that
value. This form unit does not turn the above outside-form native capture into
complete form/browser coverage.

Python gates bind raw PB to summaries, exact request strings/inputs, eight
session identities, all state/callback values and raw widget fields. Four
coherent wrong-wire mutations (Unicode truncation, extra callback, truncated
code assignment and missing widget synchronization) must fail. Rust replay
compares every ordered kind/default/max_chars/set_value/value plus snapshot.
The collector closed all sockets and its server; port 54262 was read back free.
Browser typing/IME/UTF-16 limits, query-bound lengths, dynamic max_chars reset,
other invalid oneofs and complete field/UI parity remain open. Earlier browser
and protocol records were retained, not rewritten or silently upgraded.


## Keyed text limits changing across runs (2026-10-31)

`text-reset/trace.json` reuses the same forms probe without app changes; collect
with the existing native collector's --scenario text-reset into a new directory.
Two sessions (text_input control and text_area) have 12 runs each, 310 original
frames and 48 ordered widget/state projections. Limits follow
5 -> 3 -> 5 -> 0 -> None -> 5, with typed edits between transitions. A same-limit
None-default change checks that a new default is ignored after initialization.

Both widgets reset to the new deserialized default when the limit changes,
without invoking on_change for the reset. Returning to limit 5 uses the earlier
ID but gets abcde, not the old typed prefix. With no limit, retained🧊text remains
when only the default changes to None. Four real edits per session produce four
callbacks; resets preserve the callback log. Zero and no limit have distinct
IDs although both omit the numeric max_chars field on the wire.

Identity is checked as within-runtime equality relations: for each 12-run group,
the original ID's first occurrence positions are
0/0/2/2/0/5/6/6/6/6/0/0. Runtime-specific ID digest strings are not equated across
Python and Rust. Full widget kind/default/limit/set_value/value and native
return/state/callback projections are also compared. Every raw frame is bound
to its decoded summary; exact request/typed strings, session/version metadata,
static values and four coherent mutations guard the reference. One mutation
collapses all area IDs and also rewrites client references, leaving valid PB and
otherwise correct states; it must still fail the identity relation gate.

The old Rust keyed text_area ignored max_chars and kept one ID/old state.
Unit and complete 48-event real-WS regressions failed before the one-expression
production correction. text_input, unkeyed area identity and generic element
hashing were not changed. All owned sockets/server were closed and port 62136
was read back free. This does not establish browser remount/IME, simultaneous
native assignment and limit change, stale old-ID submission, other parameters
or complete field/identity/UI parity. Prior captures and pending decisions are
retained; no reference was rewritten to turn the old behavior green.
