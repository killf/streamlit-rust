# Rust browser journeys

`journeys.json` is the compact 10-journey / 43-step acceptance manifest. Every Rust run must use the official Streamlit 1.66.1 frontend and write artifacts under `tests/e2e/<journey>/`.

- `not_run`: no attempt artifacts.
- `failed`: retain partial artifacts, link them, record a failure reason, and waive any missing expected screenshot with a reason.
- `passed`: all expected screenshots exist and a verification method is recorded.

A failed journey is honest evidence, never compatibility. Python traces under `tests/reference/reference-browser/` are oracle inputs and do not verify Rust.

Validated by the Rust ledger test (part of `cargo test --workspace`, or directly):

```powershell
cargo test -p streamlit --test journey_ledger
```