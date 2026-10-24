# Local agent configuration

This directory contains the local model/agent registry and current development documents: [architecture](architecture.md), [compatibility policy](compatibility.md), and [acceptance requirements](acceptance.md). Keep `docs/` exclusively for project usage documentation; development planning, architecture, and acceptance belong in `.codex/`. Process history and superseded contracts are ignored under `target/checks/agent-history/`.

Verify the frozen role/model mapping with:

```powershell
python .codex/verify_roles.py
```

Current data-loop writers: the upload/runtime owner owns `server.rs`, `session.rs`,
`widgets.rs`, `widget_api.rs`, `elements/input.rs`, the new upload module, `lib.rs`,
all Cargo files, upload runtime tests, `data_app.rs`, and the usage guide. Carver
owns only new `data.rs`, `data_api.rs`, `elements/data.rs`, `elements/mod.rs`, data
tests, and the tables example. Module exports/dependencies and any shared render
entry are coordinated through the upload owner; reuse the existing render path.
QA owns reference/browser capture files. Keep all official www/proto bytes and
the user's three IDE deletions intact. Scope/semantics come from public docs,
protocol and real captures; incomplete upload/data paths are not compatibility PASS.

Positive-only checkpoint at commit `1c6161d`: the limited upload subset and data D1 fix have
independently passed review. The native CSV example has three passing tests,
including four captured Arrow results, malformed-input recovery and empty-schema
handling. These are not browser error-recovery, empty-data or two-session E2E
passes. Final-candidate browser validation still awaits QA's B1 verifier fix;
DELETE, cleanup and authorization remain partial. Freeze the guide and QA changes
before the final workspace fmt/clippy/test, reference pytest, journey validation,
affected Python compilation, local-link and diff checks. Do not commit before
final independent review; preserve official frontend/protocol bytes.

Historical upload review boundary at that checkpoint: another session's file ID cannot resolve through the
current session's widget state, but HTTP PUT checks only whether the URL's session
exists. A valid session accepts an unissued file ID (204); unknown-session PUT
currently returns 500 and DELETE returns 405. Knowing another session ID may allow
insertion/overwrite; requester/token authorization is absent. Clearing a widget
does not release stored bytes or prevent ID reuse; no session-wide quota exists
and expiry is lazy. These local observations are gaps, not upstream-compatible
error/status or security promises. Keep core frozen pending the independent
official-server HTTP/XSRF/DELETE/session oracle, then address the remaining scope.

Current candidate: the bounded XSRF/DELETE fixes and native table/bar subset have
independently passed review. Final browser error/empty-data/two-session acceptance
and the remaining shared-tool checks are still pending; no complete security or
compatibility claim follows from these subset reviews.

Build/check provenance for the current candidate: `rustc 1.98.0-nightly
(54333ff07 2026-05-22)`, active toolchain `nightly-x86_64-pc-windows-msvc` (host
default). No `rust-toolchain` or `rust-toolchain.toml` exists in the repository.
Workspace locked tests (66 tests + 2 doctests), fmt check and all-targets strict
clippy passed with unchanged Rust/Cargo inputs. This validates that nightly
toolchain, not stable Rust or MSRV. Arrow 60 / actix-multipart 0.8.5 declare Rust
1.88; this dependency declaration is not a workspace test on Rust 1.88. Existing
gate logs are under ignored `target/checks/final-security-{fmt,tests,clippy}.log`.
