# Acceptance

Runtime compatibility is accepted only from black-box evidence against the pinned Python Streamlit 1.66.1 browser trace. Source inspection, compilation, health checks, AppTest, or a same-name Rust function can never imply compatibility.

The 1.66.1 runtime migration adds Rust regressions in `streamlit/tests/runtime/mod.rs` (loaded by the server module): health/host-config HTTP responses, unchanged index/JavaScript serving, a fresh two-entry WS handshake, four reruns including two button triggers and a reset, and heartbeat responses after each run. The real official-frontend [Rust button smoke](../tests/browser/rust-smoke/trace-smoke.json) records 36 frames and three clicks, each with a same-connection true trigger followed by `script_finished` status 0. This is retained UI/wire evidence for the minimal button demo, not completion of an upload journey, session restoration, or security-handshake compatibility; see [known compatibility gaps](compatibility.md).

## Required fresh-checkout checks

```powershell
python -m pytest tests/reference -q
python tests/journeys/validate_journeys.py
cargo fmt --all -- --check
cargo clippy --workspace --locked --all-targets -- -D warnings
cargo test --workspace --locked
```

The official docs cache is an ignored input under `target/upstream/docs`; when present, `tools/fetch_upstream.py` and `tools/verify_p0.py` can audit it and regenerate the two compatibility JSON files. These tools are optional local-cache checks, not fresh-checkout gates. `fetch_upstream.py --download` restores only the three locked archives and cannot reconstruct the captured catalog or HTML cache. If that cache is absent, do not run these two tools or claim that they automatically rebuild it.

## Gates

- Upstream artifacts and the documentation catalog match every hash in `upstream.lock.json`.
- The docs matrix has one row per captured canonical page with official URL, Rust plan, implementation status, compatibility status, and evidence links.
- A `partial` or `supported` compatibility status requires linked differential evidence. `supported` additionally requires API, wire, and official-frontend browser evidence.
- Failed or partial browser attempts retain their real artifacts and a failure reason; an unrun journey remains `not_run` with no attempt artifacts.
- No HTTP/WS differential failure is accepted. AppTest results are script-level oracle evidence and cannot replace wire evidence.

## Remaining first-release journeys

Read current whole-journey status, measured/deferred steps and linked evidence from [the journey manifest](../tests/journeys/journeys.json), and per-feature scope/status from [the compatibility matrix](../compatibility/api-compatibility-matrix.json). `not_run` means unmeasured, not necessarily unimplemented; captured pages are not a complete feature denominator. Forms/text input were integrated in `76938fb` and the CSV-app form integration in `e28f1d3`. Their presence does not replace whole-journey evidence or authorize a feature-matrix status change.

Product behavior follows official [widget semantics](https://docs.streamlit.io/develop/concepts/architecture/widget-behavior), [session state](https://docs.streamlit.io/develop/concepts/architecture/session-state), [uploader](https://docs.streamlit.io/develop/api-reference/widgets/st.file_uploader), [dataframe](https://docs.streamlit.io/develop/api-reference/data/st.dataframe), and [forms](https://docs.streamlit.io/develop/concepts/architecture/forms). API pages currently show 1.66.0; execution evidence must use 1.66.1. CSV aggregates and literal messages below are application contracts from the [existing 10-journey / 42-step manifest](../tests/journeys/journeys.json), not claims derived from Python framework implementation.

The table below preserves acceptance obligations, not a second live progress ledger. Follow remaining work in the manifest, reusing the reviewed API/capture helpers and explicit preparations below; add implementation only when a measured failure identifies missing behavior.

| Journey | Acceptance obligation / minimum acceptance |
|---|---|
| J01 (5 steps) | Ordered category/region/channel aggregates, Unicode keys, BOM-equivalent output. Existing upload/dataframe methods cover the core; require 5/5 original assertions, cell-by-cell Arrow/DOM agreement and 0 BOM leaks. Establish the grouping reset needed before the Unicode replacement cases. |
| J02 (5) | Preserve the other controls while filtering, exclude the two unknown keys, inclusive amount threshold, then category regrouping. Require 5/5 assertions; each ordinary changed control causes exactly one run/completion and runs delta +1; absent groups must not become zero rows. |
| J03 (4) | Table/chart update in the same run, order/value geometry and removal of stale/empty chart. Require 4/4 assertions, table row count = bar count, value-proportional bars, and no chart element/DOM at the empty stage. Shared Vega wire does not prove every chart API. |
| J06 (5) | Two live contexts with upload + three pulses + filtering + A-only reload. Require 5/5 assertions: distinct IDs, 0 cross-session file/counter/result changes, A gets a fresh ID on reload and B keeps its ID/state. Earlier counter-only isolation does not prove this combined journey. |
| J09 (4; S4 measured and passed 2026-10-25) | Fresh two-entry handshake, genuine disconnect followed by three-entry same-ID recovery preserving two pulses and uploaded aggregation, then reload reset. Require S1-S3 3/3, both handshake headers/NewSession IDs, retained file result and DOM counters. S4 is closed by the reviewed slow-expiry round: a genuine >=135-second disconnect on both runtimes, the old-ID reconnect answered with a new session and a server-side reset, the fail-closed recovery oracle satisfied only by the two reviewed raws (both published chains replay 20/20/20, exit 0). |
| J05 (3) | Combine Note, Applied note, runs and Pulse in one session. Require 3/3: before submit no value submission and runs delta 0; submit delta +1 with hello applied and input retained; three pulses give pulses=3 and runs delta +3. Isolated note/agree fixtures do not cover this; J05 itself does not require a CSV/table. |
| J00 (6) | Final integrated title/upload/three filters/Pulse/form/counters plus aggregate/chart loop. Require 6/6 original assertions; existing component evidence does not replace this exact integrated whole-journey run. |

Explicit preparations independently passed Carver review; version them before new continuous Python/Rust capture. Keep the original 10 journeys / 42 step IDs and expected results; add these visible actions to the relevant step's preparation, with no hidden reset or expected-value rewrite:

| Step boundary | Explicit UI action and state to prove |
|---|---|
| J00-S4 | After S3's six region groups, visibly choose category while minimum=0 and include-unknown=true; await that run. Then move minimum to 100. The original two groups are now coherent: Books 1/120.50 and Games 2/349.49, two bars. |
| J00-S5 | Starting from category/100/on, visibly move minimum to 0, await completion, then choose region and await completion. Record six groups/12 rows before unchecking include-unknown; the original four known groups/9 rows and four bars must follow that click. S6 counts all preparation runs as well as the named actions. |
| J03-S3 | After S2's category/100/on two-group result, visibly reset minimum to 0 and await the restored four categories. Then choose region; verify six keys including missing/UNKNOWN, six table rows and six bars in that operation's run. S4 subsequently moves minimum to 200, retaining region/on, and must remove the chart entirely. |
| J06-S4 | First finish S3 with B still empty and A's upload + pulses=3 intact. Then upload sales_basic.csv in B with category/0/on; verify B's own four-group baseline and A unchanged. Change B's group to region, obtaining six groups while A keeps its original table/chart/counters. S5 reloads only A; B must retain its session ID, uploaded file and region result. |
| J01-S4/S5 | After channel verification, explicitly restore category/0/on before replacing the upload with Unicode CSV. Replace with the BOM equivalent under the same controls. Verify original Unicode keys, totals and ordering plus BOM equivalence; any auto-reset from replacement is an observation to record, not an assumed precondition. |

Each preparation action is real UI input with before/after control values, the target ClientState value, same-request/connection successful completion, and the resulting table/chart DOM/Arrow. For these normal changed controls, require one rerun and runs delta +1 per action; use an observed run ledger for upload/preparation rather than inventing a fixed total. Capture the dependent chain in the same page/session, including unchanged A snapshots after B operations. Require the original per-step PNGs and all original assertions; a written manifest entry alone is not acceptance. If the Python reference contradicts this proposal, retain the failure and review the contract before claiming Rust parity.

For each whole journey, verify every original assertion (100%), allow 0 unexplained missing artifacts/mismatches, and retain screenshots for every required step. Link frozen binary/source/driver/criteria provenance and actual same-connection request/completion windows to DOM/Arrow observations. Dependency-linked recovery/count steps must share session continuity. Positive raw, a PNG, or isolated API tests alone cannot close a missing guard or prove all 42 steps.

## API and wire differential obligations

These 21 obligations replace the removed interface-diff metadata file. They are acceptance requirements, not a claim of Rust compatibility. The Python browser traces under `tests/reference/reference-browser/` are the wire oracle where marked; Rust progress must be assessed per obligation against equivalent black-box evidence and recorded in the current matrix.

| ID | Surface | Rust requirement | Reference evidence |
|---|---|---|---|
| A01 | st.file_uploader | the Rust uploader must return the uploaded bytes unchanged and must not raise on malformed CSV | golden `G01` |
| A02 | st.selectbox | the Rust selector must expose the same option set and initial selection; the returned value must be the selected option, never an index | golden `G01` |
| A03 | st.slider | the Rust slider must clamp and quantise identically, and the filter it drives must use >= on the amount, not > | golden `G07` |
| A04 | st.checkbox | the Rust checkbox defaults to on and its false branch must apply the same unknown-region rule as the oracle | golden `G02` |
| A05 | st.button | the Rust button must return a one-shot trigger value and cause exactly one rerun per click | reference run `REF-15` |
| A06 | st.form + st.form_submit_button | the Rust form must gate its children's values on an explicit submit, and must not clear the field on submit when clear_on_submit is false | reference run `REF-16` |
| A07 | st.dataframe | the Rust dataframe must emit the same column order, the same hidden index and an empty-but-present table for the empty case | golden `G01` |
| A08 | st.altair_chart / st.vega_lite_chart | the Rust chart must be omitted entirely in the empty case, matching the oracle's absent element rather than an empty spec | reference run `REF-03` |
| A09 | st.text / st.markdown | the Rust text element must carry the same literal content so that the browser journeys can assert on it | reference run `REF-01` |
| A10 | st.session_state | the Rust session state must be per-session, survive reruns and reject assignment to a live widget key | reference run `REF-15` |
| W01 | HTTP GET /_stcore/health | the Rust server must expose the same path and body. NOTE: this is an interface probe, not a UI pass. | Python browser trace `tests/reference/reference-browser/closed-loop/trace.json#/http_requests` |
| W02 | HTTP GET /_stcore/host-config | the Rust server must return the same JSON keys with the same defaults. NOTE: interface probe, not a UI pass. | Python browser trace `tests/reference/reference-browser/closed-loop/trace.json#/http_requests` |
| W03 | HTTP GET / and static assets | the Rust server must serve the official frontend unmodified, byte for byte. NOTE: interface probe, not a UI pass. | Python browser trace `tests/reference/reference-browser/closed-loop/trace.json#/http_requests` |
| W04 | HTTP PUT /_stcore/upload_file/{session_id}/{file_id} | the Rust upload route must accept PUT on that path shape, take the single uploaded file regardless of its field name, and answer 204 | Python browser trace `tests/reference/reference-browser/closed-loop/trace.json#/upload_contract` |
| W05 | HTTP GET /media/{file_id} | the Rust media route must mirror the upstream shape. This case is out of the P0 closed loop and is carried forward, not a UI pass. | not measured |
| W06 | WebSocket handshake GET /_stcore/stream | the Rust server must accept a two-entry subprotocol header on a fresh load, select 'streamlit', and return the session id in NewSession.initialize.session_id | Python browser trace `tests/reference/reference-browser/closed-loop/trace.json#/websocket_handshake` |
| W07 | WebSocket ForwardMsg lifecycle | the Rust server must emit the same message kinds and the same script_finished status value | Python browser trace `tests/reference/reference-browser/closed-loop/trace.json#/frames` |
| W08 | WebSocket BackMsg rerun_script and WidgetStates | the Rust server must treat one BackMsg as exactly one rerun and must not receive form children before a submit | Python browser trace `tests/reference/reference-browser/closed-loop/trace.json#/button_trace` |
| W09 | protobuf Element oneof names | the Rust proto must use the same oneof member names and numbers so the official frontend renders the elements | Python browser trace `tests/reference/reference-browser/closed-loop/trace.json#/frames` |
| W10 | protobuf WidgetState value encoding | the Rust server must decode each widget kind from the same field and must keep widget ids stable across reruns | Python browser trace `tests/reference/reference-browser/closed-loop/trace.json#/frames` |
| W11 | WebSocket reconnect handshake /_stcore/stream | on a socket-only reconnect, recover the retained session identified by the opaque third subprotocol entry; a page refresh uses a fresh two-entry handshake and new session. Unknown UUID and non-UUID IDs must start a new server-selected session, as measured by the reference probe. Rust two-worker HTTP/WS regressions cover these lookups and stale-owner Drop protection. The session core, controlled-await ownership boundary, and final Rust browser subset have independently passed review: retained same-ID recovery with a subsequent increment, fresh-ID reset, and two-tab isolation. Original-socket fate and upstream expiry policy remain separate gaps; this is partial evidence, not full takeover or security-handshake compatibility. | Python [reconnect handshakes](../tests/reference/reference-browser/reconnect/trace-reconnect.json#/websocket_handshakes) record the first connection closing and the second using a third subprotocol entry with the same session ID; [post-reconnect observations](../tests/reference/reference-browser/reconnect/trace-reconnect.json#/steps) show Pulses 2 retained, then 2→3 with a successful server response on the new connection. Python [refresh handshakes](../tests/reference/reference-browser/refresh/trace-refresh.json#/websocket_handshakes) are the separate fresh-load reference; [Rust S1 observations](../tests/browser/rust-counter-s1/trace-counter.json#/steps) record the measured Rust subset. |
