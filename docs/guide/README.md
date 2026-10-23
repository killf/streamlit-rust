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

## Session state and counter

```powershell
cargo run --example counter --locked
```

This example shows `Pulses` and `Script runs`. Clicking `Pulse` increments the current session's counter; an ordinary rerun preserves it. A socket reconnect can recover that session while it remains retained. If its previous function is still running, the replacement waits for that run to finish before taking ownership; reconnect does not cancel the function. A page refresh or a separate tab starts a new session and counter. Values are in memory only and disappear when the Rust server stops.

Use the native typed state API inside your app:

```rust
let state = st.session_state();
let count = state.get::<u64>("count").expect("count must be an integer").unwrap_or(0);
state.set("count", count + 1).expect("counter is JSON-serializable");
state.remove("obsolete");
```

`get` returns `Ok(None)` for a missing key and an error for a type mismatch. `set` accepts JSON-serializable Rust values; failed serialization leaves the old value intact. `remove` returns the previous JSON value if present. Each browser session has its own state. This application-value API does not yet implement automatic widget-key binding, callbacks, or persistence across server restarts. Disconnected state is retained for 120 seconds by default; manual server construction can set this local policy with `with_disconnected_session_ttl(Duration)`. Retention is not a compatibility claim about Streamlit's default TTL.

## Information, warnings, errors, and success messages

```powershell
cargo run --example status --locked
```

Open `http://127.0.0.1:8502/` for this example. The same methods work on the app, containers, and columns:

```rust
st.info("Information").expect("valid status");
st.warning("Please check the input").expect("valid status");
st.error(StatusOptions::new("The operation failed").title("Error")).expect("valid status");
st.success(StatusOptions::new("Saved").icon(":material/thumb_up:")).expect("valid status");
```

Supported options and behavior:

| Use | Rust example or behavior |
|---|---|
| Four message kinds | `info`, `warning`, `error`, and `success` accept a string or `StatusOptions`. |
| Markdown body | ``StatusOptions::new("**Details** with `inline code`")`` passes the body to the official frontend's Markdown renderer. |
| Optional title | `.title("Summary")` adds a title; it is empty by default. |
| Width | Default `.width("stretch")`, or a positive pixel count such as `.width(240)`. `"content"` and nonpositive widths are rejected. |
| Leading body icon | Without `.icon(...)`, a leading emoji or Material shortcode becomes the icon and is removed from the body; emoji elsewhere stay in the body. |
| No icon | `.icon("")` suppresses extraction and preserves a leading emoji in the body. |
| Material icon | An explicit `.icon(":material/thumb_up:")` uses the supplied shortcode. |
| One emoji sequence | Explicit `.icon("👩‍💻")`, `.icon("👍🏽")`, and `.icon("🇨🇳")` preserve the entire sequence; a leading `👩‍💻` can also be extracted from the body. |

Each call returns `Result<(), StatusError>`. Invalid widths or icons return an error without appending that message; earlier messages remain. Two independent emoji such as `.icon("🔥💡")` are rejected. Icons must be strings in Rust. The listed compound emoji are the measured examples, not a claim that every Unicode sequence behaves identically to Python Streamlit.

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

The developer surface currently centers on `title`, `header`, `sub_header`, `markdown`, `caption`, `code`, `write`, `badge`, `divider`, `info`, `warning`, `error`, `success`, containers, columns, `button`, and native application session state. Signatures are in `streamlit/src/api.rs` and `streamlit/src/session.rs`; behavior is not marked fully compatible from source availability alone.

Known boundaries are significant: the table/chart APIs, file uploader, form, cache, stop/cancel, callbacks, automatic widget-state association, and most input widgets are not implemented. Native application session values, ordinary reruns, retained-session reconnects, and one-shot button triggers are implemented; this does not establish complete Streamlit execution or API compatibility.

## Reference evidence

Deterministic CSV fixtures are in `tests/fixtures`. The pinned Python application and browser collector are in `tests/reference`. Real Python HTTP/WS/protobuf traces and selected screenshots are committed under `tests/reference/reference-browser`; they establish the oracle behavior only and do not exercise the Rust server.

The [Rust counter observations](../../tests/browser/rust-counter-s1/trace-counter.json) cover session recovery, fresh-load reset, and tab isolation. The [Rust status observations](../../tests/browser/rust-status/trace-status.json) cover the static message example and its measured options. These examples do not implement a complete file-upload/data journey.
