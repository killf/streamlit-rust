# Roadmap

This document fixes the terminal goal and the milestone ladder for reaching verifiable runtime compatibility with the pinned Python Streamlit 1.66.1. It records goal structure and ordering only. Live progress stays in [the journey manifest](../tests/journeys/journeys.json) (whole journeys and steps) and [the compatibility matrix](../compatibility/api-compatibility-matrix.json) (per-API status and evidence); this file never duplicates those counts. Requirements and evidence rules stay in [acceptance](acceptance.md); known gaps and slider-type obligations stay in [compatibility](compatibility.md).

## Terminal goal

The project reaches **verifiable runtime compatibility with Python Streamlit 1.66.1** when all four end states hold:

1. The journey manifest shows all 10 journeys / 42 steps `passed`, including J09-S4 measured by a real slow disconnect (not by policy or inference).
2. Every captured matrix row (182 documentation entries) has left `absent`/`unverified` through linked black-box differential evidence, or carries an explicit recorded reason it does not apply.
3. All 21 API/wire obligations (A01–A10, W01–W11 in [acceptance](acceptance.md)) are closed with measured evidence; no obligation remains "carried forward".
4. The five required fresh-checkout checks (pytest reference suite, journey manifest validation, `cargo fmt --check`, `cargo clippy -D warnings`, `cargo test`) all pass.

Compatibility is only established by black-box evidence against the pinned reference; a milestone never advances a status without it.

## Milestone ladder

Each milestone follows the same discipline: capture the Python 1.66.1 reference behavior first, implement in Rust, add runtime regressions, capture the real-browser Rust differential, then update the manifest/matrix. The five fresh-checkout checks run at every milestone close.

| Milestone | Scope | Exit criteria |
|---|---|---|
| **M0 — Close in-flight J09-S4** (current focus) | Commit the built J09-S4 capture/judge machinery; run the real slow measurement on the Python reference side (port 8604) and the Rust side (dedicated port and Chrome instance); validate with the 20 `j09_slow_checks` (fail-closed recovery oracle); record the observed upstream TTL policy in [compatibility](compatibility.md) replacing the local-120s-policy wording. | journeys.json shows J09 4/4 `passed` with real S4 artifacts; five checks green. |
| **M1 — Execution semantics** | `st.stop` / `st.rerun` / `st.quit` behind a bounded run-loop in the rerun handler (reference wire for rerun-triggered runs and stop's `ScriptFinished` status captured first); exception-element UI parity for duplicate keys (today a fallible `WidgetError`, upstream renders an Exception element). | Reference differential + runtime regressions for stop/rerun; J04 extended with a rerun step; obligations recorded in the matrix. |
| **M2 — Evidence upgrades and high-frequency input widgets** | Promote the 10 `candidate` rows plus the implemented-but-`absent` form/text_input/table/bar_chart/form_submit_button rows with browser differential evidence; temporal sliders (`SliderOptions<chrono::NaiveDate/NaiveTime/NaiveDateTime>` and pairs, per the slider table in [compatibility](compatibility.md), wire observed before implementation); new widgets radio, multiselect, number_input, text_area, each with the full evidence chain. | Promoted matrix rows carry linked evidence; each new widget has reference capture, Rust implementation, runtime tests, and a browser differential. |
| **M3 — Media and presentation surfaces** | W05 `GET /media/{file_id}` (upstream shape measured first); `st.image/audio/video` on that route; `st.metric/progress/spinner/toast/balloons`; line/area/scatter/map charts on the existing native inference base. | W05 closed with measured evidence; each media/presentation API follows the evidence chain. |
| **M4 — State and configuration subsystems** | `cache_data`/`cache_resource` (cross-rerun store, key hashing, invalidation, clear); `st.query_params` binding, persistent hidden widgets, selectbox new-options/filter mode; layouts expander/tabs/sidebar/popover/dialog; `st.set_page_config`. | Each subsystem has reference capture, Rust implementation, runtime regressions, and matrix promotion. |
| **M5 — Full convergence** | Multipage/`st.navigation`; remaining `absent` rows closed block-by-block following the captured official documentation catalog until no row remains `absent` and all W obligations are closed. | The four terminal-goal end states hold. |

## Maintenance rules

- The current-focus pointer moves only when the active milestone's exit criteria are met with retained evidence, never by plan or estimate.
- Milestone work items are ordered within the milestone but do not skip the reference-first rule; a measured contradiction with the reference stops the item and records the failure.
- journeys.json remains the only live step ledger and the matrix the only per-API ledger; roadmap updates at milestone close record only structure, ordering, and focus movement.
- Each milestone close updates this file's focus pointer and commits together with its evidence.
