# Streamlit Rust guide

This crate is an early Rust implementation of the Streamlit server. It is not yet Streamlit-compatible. The authoritative feature status is the [compatibility matrix](../compatibility.md), not the presence of an example or same-name function.

## Run

```powershell
cargo run --example hello
```

Examples are in `streamlit/examples/`. `hello` is the smallest starting point; `basic` shows the currently available text and layout API; `timer` shows async execution. The server currently expects the repository-root `www/` directory for static assets.

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

Known boundaries are significant: the table/chart APIs, file uploader, form, session state, cache, rerun semantics, and most input widgets are not implemented. `button` has Python reference wire evidence but no Rust compatibility claim.

## Reference evidence

Deterministic CSV fixtures are in `tests/fixtures`. The pinned Python application and browser collector are in `tests/reference`. Real Python HTTP/WS/protobuf traces and selected screenshots are committed under `tests/reference/reference-browser`; they establish the oracle behavior only and do not exercise the Rust server.
