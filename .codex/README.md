# Local agent configuration

This directory contains the local model/agent registry and current development documents: [architecture](architecture.md), [compatibility policy](compatibility.md), and [acceptance requirements](acceptance.md). Keep `docs/` exclusively for installation, usage, examples, and public API documentation. Development plans, architecture decisions, compatibility explanations, acceptance criteria/evidence indexes, agent contracts, and research progress belong in the existing `.codex/` structure. The machine-readable matrix and baseline under `compatibility/` are tool outputs and retain their generator-bound paths. Actual test fixtures, traces, and screenshots stay under `tests/`; temporary logs and debug outputs belong under ignored `target/`. The root README links to these development documents instead of duplicating their checks. Process history and superseded contracts are ignored under `target/checks/agent-history/`.

Verify the frozen role/model mapping with:

```powershell
python .codex/verify_roles.py
```

Current CSV-completion stage: the app owner writes only `streamlit/examples/data_app.rs` and `docs/guide/README.md`; framework/Cargo/official bytes stay frozen.
Carver owns shared journey criteria/tests and Popper owns the driver/real captures; preserve their files and the user's IDE deletions. The unverified multifile prototype is archived under ignored `target/checks/unverified-reference/` for future work. J04 has independently passed its complete three-step browser sequence. Hooke has independently closed the J07 row999/text-tamper counterexample; the four whole raw captures, 22 PNGs and 12 mutations passed. Hooke independently passed the guard, both Python-command identities and all three Chrome obs tests with zero skips. Forms/text input remain on the unmerged isolated branch and are not mainline capabilities. Follow the bounded order, versioned UI preparation proposals and final submission boundary in [acceptance](acceptance.md#remaining-first-release-journeys). Carver independently passed these documents and the explicit UI preparations; integrate these three documents as a separate documentation commit.

Positive-only checkpoint at commit `1c6161d`: the limited upload subset and data D1 fix have
independently passed review. The native CSV example has three passing tests,
including four captured Arrow results, malformed-input recovery and empty-schema
handling. These are not browser error-recovery, empty-data or two-session E2E
passes. At that historical checkpoint browser validation awaited the B1 fix;
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
independently passed review. The four whole raw/PNG/mutation checks, both command identities and three obs tests have passed with zero Chrome skips; final pytest/phase commit is in progress; no complete security or
compatibility claim follows from these subset reviews.

Build/check provenance for the current candidate: `rustc 1.98.0-nightly
(54333ff07 2026-05-22)`, active toolchain `nightly-x86_64-pc-windows-msvc` (host
default). No `rust-toolchain` or `rust-toolchain.toml` exists in the repository.
Workspace locked tests (66 tests + 2 doctests), fmt check and all-targets strict
clippy passed with unchanged Rust/Cargo inputs. This validates that nightly
toolchain, not stable Rust or MSRV. Arrow 60 / actix-multipart 0.8.5 declare Rust
1.88; this dependency declaration is not a workspace test on Rust 1.88. Existing
gate logs are under ignored `target/checks/final-security-{fmt,tests,clippy}.log`.

## forms-text-input writer boundary

For this isolated branch, the GLM engineer owns the Rust API/render/widget/session changes, Rust tests, example, user guide, and strict forms contract. MiniMax QA owns only the forms fixture/case files, thin collector, and reference raw/PNG evidence under the forms evidence directories; it does not edit Rust or the shared decoder framework.
