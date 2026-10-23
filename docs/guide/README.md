# Streamlit Rust guide

This crate is an early Rust implementation of the Streamlit server. It is not yet Streamlit-compatible. The authoritative feature status is the [compatibility matrix](../../.codex/compatibility.md), not the presence of an example or same-name function.

## Run

```powershell
cargo run --example hello
```

Run these commands from the repository root, then open `http://127.0.0.1:8501/`. Examples are in `streamlit/examples/`. `hello` is the smallest starting point; `basic` shows the currently available text and layout API; `timer` shows async execution. The server expects the repository-root `www/` directory, which contains the unmodified official Streamlit 1.66.1 frontend. Running the Rust server does not require Python.

For a minimal button example:

```powershell
cargo run --example button --locked
```

The page shows a `Pulse` button and `Ready`. A click reruns the Rust function and shows `Pulse received`; further clicks request further reruns. Three successive clicks were exercised through the official frontend, with each receiving a successful server completion; the [recorded smoke](../../tests/browser/rust-smoke/trace-smoke.json) covers this minimal demo. This example has no file upload or persistent session counter.

## Minimal application

```rust
use ::streamlit::*;

#[main]
async fn main(st: &Streamlit) {
    st.title("Sales dashboard");
    st.write("Upload a CSV to see aggregated data.");
}
```

The macro requires `async fn main(st: &Streamlit)`. Doctest compilation uses `rust,no_run` so it does not start a server during `cargo test`.

## Current API

The developer surface currently centers on `title`, `header`, `sub_header`, `markdown`, `caption`, `code`, `write`, `badge`, `divider`, containers, columns, and `button`. Signatures are in `streamlit/src/api.rs`; behavior is intentionally not marked compatible until differential tests pass.

Known boundaries are significant: the table/chart APIs, file uploader, form, persistent session state, cache, cancellation/reconnect semantics, and most input widgets are not implemented. Ordinary browser-requested reruns and button trigger values are handled, but `button` still has no Rust compatibility claim.

## Reference evidence

Deterministic CSV fixtures are in `tests/fixtures`. The pinned Python application and browser collector are in `tests/reference`. Real Python HTTP/WS/protobuf traces and selected screenshots are committed under `tests/reference/reference-browser`; they establish the oracle behavior only and do not exercise the Rust server.
