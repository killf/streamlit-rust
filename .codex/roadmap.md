# Roadmap

This document fixes the terminal goal and the milestone ladder for reaching verifiable runtime compatibility with the pinned Python Streamlit 1.66.1. It records goal structure and ordering only. Live progress stays in [the journey manifest](../tests/journeys/journeys.json) (whole journeys and steps) and [the compatibility matrix](../compatibility/api-compatibility-matrix.json) (per-API status and evidence); this file never duplicates those counts. Requirements and evidence rules stay in [acceptance](acceptance.md); known gaps and slider-type obligations stay in [compatibility](compatibility.md).

## Terminal goal

The project reaches **verifiable runtime compatibility with Python Streamlit 1.66.1** when all five end states hold:

1. The journey manifest shows all 10 journeys / 42 steps `passed`, including J09-S4 measured by a real slow disconnect (not by policy or inference).
2. Every captured matrix row (182 documentation entries) has left `absent`/`unverified` through linked black-box differential evidence, or carries an explicit recorded reason it does not apply.
3. All 21 API/wire obligations (A01–A10, W01–W11 in [acceptance](acceptance.md)) are closed with measured evidence; no obligation remains "carried forward".
4. The five required fresh-checkout checks (pytest reference suite, journey manifest validation, `cargo fmt --check`, `cargo clippy -D warnings`, `cargo test`) all pass.
5. The repository itself stays worth reading and trusting: the code carries no dead or superseded paths, every document is concise and readable for its human audience, the examples run against the current API, and obsolete code, tests and docs are removed promptly rather than archived in place.

Compatibility is only established by black-box evidence against the pinned reference; a milestone never advances a status without it.

## Cross-cutting quality acceptance

Feature completeness is necessary but not sufficient. The norms below bind every milestone and the terminal state alike; a milestone that ships behavior while failing any of them is not closed. The first full pass runs at the M0 close.

**Code quality.** `cargo clippy --workspace --locked --all-targets -- -D warnings` and `cargo fmt --all -- --check` stay green (already fresh-checkout gates). Beyond the tools: no dead code, no superseded duplicate paths, no speculative abstraction — the simplest implementation that passes its evidence chain wins, and public user-facing API carries rustdoc that agrees with the guide.

**Documentation readability and conciseness.** Every document states and serves a human audience: `README` and `docs/guide` for users, `.codex/` for process and contracts. Prefer rewriting a section over appending to it; when a sentence has grown into a paragraph, split it or cut it. Documentation follows the code it describes: a milestone that changes behavior updates or deletes the affected doc lines in the same change, and a doc that no longer describes anything real is deleted, not left to drift. Duplication of the live ledgers stays forbidden (see maintenance rules).

**Human-facing examples.** `streamlit/examples/` is product surface, not scratch space: every user-facing API added by a milestone appears in a minimal, runnable example; examples are edited or removed in the same milestone that changes their API; `docs/guide` stays an accurate index of what each example shows and how to run it. The usability bar: a human with only the Rust toolchain goes from fresh clone to a running app of their own using `README`, `docs/guide` and the examples, without reading server internals.

**Hygiene and cleanup.** Superseded code, tests that no longer exercise live behavior, spent probe scripts and stale doc sections are deleted in the milestone that retires them. Cleanup explicitly does not delete retained failure evidence or frozen capture artifacts: [acceptance](acceptance.md) requires failed and partial attempts to keep their real artifacts, and those are records, not clutter. Ignored `target/` rounds never migrate into the repository.

## Milestone ladder

Each milestone follows the same discipline: capture the Python 1.66.1 reference behavior first, implement in Rust, add runtime regressions, capture the real-browser Rust differential, then update the manifest/matrix. The five fresh-checkout checks and the cross-cutting quality pass above run at every milestone close.

| Milestone | Scope | Exit criteria |
|---|---|---|
| **M0 — Close in-flight J09-S4** (closed 2026-10-25) | Commit the built J09-S4 capture/judge machinery; run the real slow measurement on the Python reference side (port 8604) and the Rust side (dedicated port and Chrome instance); validate with the 20 `j09_slow_checks` (fail-closed recovery oracle); record the observed upstream TTL policy in [compatibility](compatibility.md) replacing the local-120s-policy wording. | journeys.json shows J09 4/4 `passed` with real S4 artifacts; five checks green. |
| **M1 — Execution semantics** (current focus) | `st.stop` / `st.rerun` / `st.quit` behind a bounded run-loop in the rerun handler (reference wire for rerun-triggered runs and stop's `ScriptFinished` status captured first); exception-element UI parity for duplicate keys (today a fallible `WidgetError`, upstream renders an Exception element). | Reference differential + runtime regressions for stop/rerun; J04 extended with a rerun step; obligations recorded in the matrix. |
| **M2 — Evidence upgrades and high-frequency input widgets** | Promote the 10 `candidate` rows plus the implemented-but-`absent` form/text_input/table/bar_chart/form_submit_button rows with browser differential evidence; temporal sliders (`SliderOptions<chrono::NaiveDate/NaiveTime/NaiveDateTime>` and pairs, per the slider table in [compatibility](compatibility.md), wire observed before implementation); new widgets radio, multiselect, number_input, text_area, each with the full evidence chain. | Promoted matrix rows carry linked evidence; each new widget has reference capture, Rust implementation, runtime tests, and a browser differential. |
| **M3 — Media and presentation surfaces** | W05 `GET /media/{file_id}` (upstream shape measured first); `st.image/audio/video` on that route; `st.metric/progress/spinner/toast/balloons`; line/area/scatter/map charts on the existing native inference base. | W05 closed with measured evidence; each media/presentation API follows the evidence chain. |
| **M4 — State and configuration subsystems** | `cache_data`/`cache_resource` (cross-rerun store, key hashing, invalidation, clear); `st.query_params` binding, persistent hidden widgets, selectbox new-options/filter mode; layouts expander/tabs/sidebar/popover/dialog; `st.set_page_config`. | Each subsystem has reference capture, Rust implementation, runtime regressions, and matrix promotion. |
| **M5 — Full convergence** | Multipage/`st.navigation`; remaining `absent` rows closed block-by-block following the captured official documentation catalog until no row remains `absent` and all W obligations are closed. | The four terminal-goal end states hold. |

M0 status (2026-10-25, closed): the machinery was committed; both real slow measurements ran to completion — Python 1.66.1 on 8604 and the sealed 769+dirty candidate on 8501, each with a genuine >=135-second single-socket disconnect, all 13 phases, and formal replay of 20 executed / 19 asserted under capture-time criteria `cedbc864...`. Both sides requested the aged session id on the three-entry reconnect and received a NEW session id with a server-side state reset (the browser retains the file chip and re-references the aged session's file). A capture-side defect was fixed for this round: the previous attempt's `effective-config` evidence was written in the Windows ANSI codepage and failed the judge's strict UTF-8 decode; the regenerated evidence is real UTF-8. An independent reviewer then audited both frozen chains end to end and derived the recovery golden from the raw bytes; the reviewed golden is integrated into `j09_slow_checks` (final criteria `aa0f7042...`) and both published replays return 20 executed / 20 asserted with exit 0. J09-S4 is promoted to `passed` and J09 is 4/4; the focus moves to M1.

## Maintenance rules

- The current-focus pointer moves only when the active milestone's exit criteria are met with retained evidence, never by plan or estimate.
- Milestone work items are ordered within the milestone but do not skip the reference-first rule; a measured contradiction with the reference stops the item and records the failure.
- journeys.json remains the only live step ledger and the matrix the only per-API ledger; roadmap updates at milestone close record only structure, ordering, and focus movement.
- A feature is done when it works, is evidence-verified, reads like the rest of the codebase, is documented concisely for its audience, is shown in an example (when user-facing), and leaves nothing superseded behind. Any missing subset is an open task, not a finished feature.
- Milestone close runs the quality pass: the clippy/fmt gates, an example build, a documentation accuracy check of everything the milestone touched, and a cleanup sweep for retired code, tests and docs.
- Each milestone close updates this file's focus pointer and commits together with its evidence.
