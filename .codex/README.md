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

Current data-loop checkpoint: the limited upload subset and data D1 fix have
independently passed review. The native CSV example has three passing tests,
including four captured Arrow results, malformed-input recovery and empty-schema
handling. These are not browser error-recovery, empty-data or two-session E2E
passes. Final-candidate browser validation still awaits QA's B1 verifier fix;
DELETE, cleanup and authorization remain partial. Freeze the guide and QA changes
before the final workspace fmt/clippy/test, reference pytest, journey validation,
affected Python compilation, local-link and diff checks. Do not commit before
final independent review; preserve official frontend/protocol bytes.

Upload review boundary: another session's file ID cannot resolve through the
current session's widget state, but HTTP PUT checks only whether the URL's session
exists. A valid session accepts an unissued file ID (204); unknown-session PUT
currently returns 500 and DELETE returns 405. Knowing another session ID may allow
insertion/overwrite; requester/token authorization is absent. Clearing a widget
does not release stored bytes or prevent ID reuse; no session-wide quota exists
and expiry is lazy. These local observations are gaps, not upstream-compatible
error/status or security promises. Keep core frozen pending the independent
official-server HTTP/XSRF/DELETE/session oracle, then address the remaining scope.
