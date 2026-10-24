# Streamlit Rust guide

This crate is an early Rust implementation of the Streamlit server. It is not yet Streamlit-compatible. The authoritative feature status is the [compatibility matrix](../../.codex/compatibility.md), not the presence of an example or same-name function.

## Run

```powershell
cargo run --example quickstart --locked
```

Run this development command from the repository root, then open `http://127.0.0.1:8503/`. The [runnable quickstart](../../streamlit/examples/quickstart.rs) displays a selectbox, slider, checkbox, and their returned values. No Python process is required. Debug builds can locate the repository's `www` from that root; installed executables use the sidecar/configuration described below.

The executable/native tests use `rustc 1.98.0-nightly (54333ff07 2026-05-22)` on Windows MSVC; stable Rust 1.95.0 also passes the workspace all-targets compilation check. A minimum supported Rust version has not been validated.

Use the same widget methods with concise inputs inside a function returning `Result<(), WidgetError>`:

```rust
use ::streamlit::*;

fn render(st: &Streamlit) -> Result<(), WidgetError> {
    let group = st.selectbox(("Group by", ["category", "region"]))?;
    let minimum = st.slider(("Minimum amount", 0_i64, 0..=200))?;
    let include = st.checkbox(("Include unknown", true))?;
    st.write(format!("{group:?}, minimum={minimum}, include={include}"));
    Ok(())
}
```

The quickstart entry handles a render error once and displays it. The current `#[streamlit::main]` macro accepts unit-returning user functions; put `?` in a fallible helper rather than giving the macro function a `Result` return type. The example uses port 8503; macro-based examples normally use 8501. `cargo run --example hello --locked` is the smallest text-only example. `basic` shows text/layout and `timer` shows async execution. All use the unmodified official Streamlit 1.66.1 frontend in `www/`.

| Input | Same defaults as the advanced builder |
|---|---|
| `st.checkbox("Include")?` | false initially |
| `st.checkbox(("Include", true))?` | explicit initial bool |
| `st.selectbox(("Group", ["category", "region"]))?` | first option selected; original option type returned |
| `st.slider(("Count", 0_i64))?` | integer bounds 0..100, step 1 |
| `st.slider(("Ratio", 0.25_f64))?` | float bounds 0..1, step 0.01 |
| `st.slider(("Amount", 20_i64, 10..=200))?` | explicit permitted bounds; initial value 20, step 1 |
| `st.slider(("Range", (20_i64, 80_i64)))?` | selected endpoints 20..80, permitted bounds still 0..100 |

Use the [advanced widget options](../../streamlit/src/widget_api.rs) for keys, callbacks, custom step/format, disabled state and other settings; the [widgets example](../../streamlit/examples/widgets.rs) shows them together. Concise calls keep the same defaults and `Result` error handling.

For a minimal button example:

```powershell
cargo run --example button --locked
```

The page shows a `Pulse` button and `Ready`. A click reruns the Rust function and shows `Pulse received`; further clicks request further reruns. This example has no file upload or persistent session counter.

## Run an installed executable from any directory

Build an executable, for example:

```powershell
cargo build --release --example quickstart --locked
```

Copy `target/release/examples/quickstart.exe` and the complete, unmodified `www/` directory into a fresh installation directory. The layout is `quickstart.exe` beside `www/index.html`, `www/static/`, and all other official frontend files. You can then launch that executable from any working directory; no Python process, repository checkout or build-machine path is required at runtime. Release builds do not look for `www` in the working directory.

To keep the frontend somewhere else, set its absolute directory before launching:

```powershell
$env:STREAMLIT_STATIC_DIR = 'C:\Apps\streamlit-demo\www'
& 'C:\Apps\streamlit-demo\quickstart.exe'
```

For a manually constructed `StreamlitServer`, call `.with_static_dir(path)` before `.start().await`. Selection order is the explicit builder, `STREAMLIT_STATIC_DIR`, executable-adjacent `www`, then a debug-only repository-root `www` fallback. Relative overrides are resolved against the startup working directory. Remove the environment override with `Remove-Item Env:STREAMLIT_STATIC_DIR` to use the executable sidecar again.

An empty or invalid explicit override is an error, even if another directory is valid. An existing but invalid executable sidecar also fails rather than falling back. Before listening, the server checks the official Streamlit 1.66.1 index and the presence/readability of its nonempty boot JS/CSS files; an incompatible or incomplete directory returns an actionable `std::io::Error`. Install the whole pinned bundle: this startup check does not authenticate every lazy-loaded chunk or replace distributing all official files.

## Session state and counter

```powershell
cargo run --example counter --locked
```

This example shows `Pulses` and `Script runs`. Clicking `Pulse` increments the current session's counter; an ordinary rerun preserves it. A socket reconnect can recover that session while it remains retained. If its previous function is still running, the replacement waits for that run to finish before taking ownership; reconnect does not cancel the function. A page refresh or a separate tab starts a new session and counter. Values are in memory only and disappear when the Rust server stops.

Use the native typed state API inside your app:

```rust
let state = st.session_state();
let count = state.get::<u64>("count")?.unwrap_or(0);
state.set("count", count + 1)?;
state.remove("obsolete");
```

`get` returns `Ok(None)` for a missing key and an error for a type mismatch. `set` accepts JSON-serializable Rust values; failed serialization leaves the old value intact. `remove` returns the previous JSON value if present; deleting a key does not reset a widget that is still rendered. Each browser session has its own state. Explicit input-widget keys bind to these values. Set a key before instantiating its widget; `set` rejects assignment after that widget is instantiated in the current run, and assigning button keys is forbidden. Values do not persist across server restarts. Disconnected state is retained for 120 seconds by default; manual server construction can set this local policy with `with_disconnected_session_ttl(Duration)`. Retention is not a compatibility claim about Streamlit's default TTL.

## Upload a CSV and update data views

```powershell
cargo run --example data_app --locked
```

Run the development command from the repository root and open `http://127.0.0.1:8501/`; installed binaries follow the same sidecar/configuration rules above. Stop another example using that port first. Upload the [sample CSV](../../tests/fixtures/csv/sales_basic.csv) to the [data app](../../streamlit/examples/data_app.rs), which computes a dataframe and an explicitly configured bar chart in Rust. Change **Group by**, **Include unknown region**, or **Minimum amount** to recompute the displayed data. The running app needs no Python process or Python runtime.

The CSV needs lowercase `amount` and `region` headers. Optional `category` and `channel` columns provide additional grouping choices. Unusable amount cells are excluded with a warning; other rows still aggregate. Malformed rows report the CSV record number and expected/actual field counts. Non-UTF-8 files are rejected. Both hard failures show an error instead of data views; select a valid CSV in the same uploader to recover.

A header-only file shows **The uploaded CSV contains no data rows.** To filter all sample rows out, set **Minimum amount** to 200: **No rows match the current filters.** appears with an empty four-column dataframe and no chart. Set the slider back to 0 to restore the results without reloading. Totals and averages use this application's decimal HALF_UP rule, not a universal Streamlit rounding rule; averages round once from the unrounded sum divided by the count. Decimals exceeding the example's native precision are rejected instead of silently rounded.

Below the results, **Interaction** contains **Pulse**, followed by **Script runs: N** and **Pulses: N**. Each script run increments the session's run count once; clicking Pulse increments both counters once while leaving the aggregate data unchanged. Filter changes rerun the script without adding a pulse. These counters are session-local and start at 1/0 on the first run of a fresh session; they do not implement the developer `st.rerun`/`st.stop` APIs or the reference application's Note form.

Inside a fallible render function, read the original uploaded bytes:

```rust
let files = st.file_uploader(
    FileUploaderOptions::new("Upload sales CSV").accepted_types(["csv"]).key("upload")
)?;
if let Some(file) = files.as_slice().first() {
    st.write(format!("{}: {} bytes", file.name(), file.size()));
    let original_bytes: &[u8] = file.as_bytes();
    // Pass original_bytes to your Rust parser.
}
```

`UploadedFile` also implements `Read`, `Seek`, and `AsRef<[u8]>`; new handles start reading at zero. `content_type()` returns the supplied MIME type when present. The uploader returns `UploadedFiles::Single(Option<UploadedFile>)` by default; multiple/directory modes use `UploadedFiles::Multiple(Vec<UploadedFile>)`. Uploader keys are read-only; callbacks can resolve their files with `st.session_state().uploaded_files("upload")?`.

Start with the single-file CSV path. The server accepts one file part per upload request, with a local 200 MiB file-content ceiling; it rejects oversized files without storing them. HTTP PUT and DELETE now require a cookie and header with matching decoded XSRF tokens. Health responses issue or remask the cookie. DELETE removes the stored file; resending its old widget ID cannot restore the bytes, though previously returned Rust handles remain readable. Clearing a widget state alone does not delete a file: deletion depends on the frontend's DELETE request. The updated frontend upload/clear path and security boundaries still need final validation; this is not complete XSRF or production-security compatibility.

There is no total per-session upload quota, and expiry is checked lazily rather than by a background cleanup timer. Multiple/directory workflows, replacement/error boundaries and upstream session-expiry behavior remain incomplete or unverified. Session IDs are reconnect handles, not user authorization: valid XSRF credentials do not bind an upload URL to a particular user or issued file token. Do not expose this endpoint to untrusted clients as a production-ready security boundary. See [upload/widget options](../../streamlit/src/widget_api.rs) and [data view options](../../streamlit/src/data_api.rs) for the advanced API. Data views cover limited table/chart paths, not the complete selection/streaming surface.

## Tables and native bar charts

```powershell
cargo run --example tables --locked -- --native
```

Run the development command from the repository root and open `http://127.0.0.1:8503/`; stop another example on that port first. **Update data** changes the values rendered by the [tables example](../../streamlit/examples/tables.rs). Installed copies use the sidecar/configuration rules above and need no Python runtime.

Pass a native Arrow `RecordBatch` directly from a fallible render helper:

```rust
use ::streamlit::{DataApi, Streamlit, data::{DataError, RecordBatch}};

fn render_data(st: &Streamlit, batch: &RecordBatch) -> Result<(), DataError> {
    st.table(batch)?;
    // For a batch containing numeric series:
    st.bar_chart(batch)?;
    Ok(())
}
```

Use `TableOptions::new(&batch)` for borders, index/header visibility, size and alternative text. Use `BarChartOptions::native(&batch).x("group").y("amount")` to choose columns; the measured subset also exposes horizontal layout, sorting and side-by-side series. Bare `st.bar_chart(&batch)` uses the row index as categories and the supplied numeric series. `BarChartOptions::new(&batch, "group", "amount")` keeps the explicit mapping API used by `data_app`.

Support is partial: the native bar path covers the measured Int64/Float64 series and string/numeric categories, including the captured null/negative-value configurations. Other Arrow types, color rules and stack variants are not fully covered. Mixed large integer/float input can return a Rust error where Python rounds; do not rely on matching that conversion. Selection, `add_rows` and the complete table/chart surface remain incomplete. See [data options](../../streamlit/src/data_api.rs) for the current typed API.

## Input widgets

```powershell
cargo run --example widgets --locked
```

Open `http://127.0.0.1:8501/`. The example renders selectbox, checkbox, integer and floating-point scalar sliders, integer tuple and floating-point array range sliders, a disabled button, and returned values. Each changed input updates its returned value and increments the callback count. It does not render a data table or implement date/time sliders.

```rust
let group = st.selectbox(
    SelectboxOptions::new("Group by", ["category", "region"]).key("group_by")
)?;
let minimum = st.slider(
    SliderOptions::new("Minimum amount", 0_i64).max(200).step(10).key("minimum")
)?;
let include = st.checkbox(
    CheckboxOptions::new("Include unknown").value(true).key("include")
)?;
```

These methods return `Result` and also work in containers and columns. Selectbox returns an original option (`Option<T>`), not its display label or index. `.index(None)` starts empty; `.format_func(|option| ...)` changes labels only. Use `SelectboxOptions::with_format_func(...)` for types without Display, including `Option<T>` and `()`. A selected None option returns `Some(None)`; an unselected `Option<T>` selectbox returns `None`. Empty options disable selection. Checkbox defaults to content width; selectbox and slider stretch. Numeric sliders accept `i32`, `i64`, `f64`, or two scalar endpoints of the same type as `(T, T)` or `[T; 2]`. Pass the lower bound as the initial value to start there. Bounds and step must be finite, ordered, and positive as appropriate; integer bounds stay within JavaScript's exact integer range and the chosen Rust return type (`i32` or `i64`). `.format(...)` changes slider display only. Date/time sliders and adding new selectbox options are not available yet.

Use `.on_change(|st| { ... })` on inputs or `ButtonOptions::new("Apply").on_click(|st| { ... })` for a button callback. Incoming widget values are applied together, then synchronous callbacks execute before main. Captures must be `Send + Sync + 'static`; callbacks can read updated keys and write application state. `.ignore_rerun(true)` buffers an input change in the frontend until another event reruns the script. Default reruns preserve input values and one-shot buttons reset each run. Give repeated widgets distinct keys: duplicate keys or automatic IDs return `WidgetError`. The original `button` returns `bool` and panics on a registration error; use `try_button` for a `Result`.

Widget keys are removed at the end of a run if that widget was not rendered; unrelated application keys remain. Keyed slider bounds/step changes reset its value. These behaviors do not establish full widget identity, cleanup-exception or callback/error parity, or complete compatibility.

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

## Current API

Available APIs include text and layout, static status messages, `button`, `selectbox`, numeric `slider`, `checkbox`, and native session state. See the [text/layout/status API](../../streamlit/src/api.rs), [widget options](../../streamlit/src/widget_api.rs), and [session API](../../streamlit/src/session.rs).

Upload and columnar data views currently cover the limited paths described above. General table/chart APIs, selection/add_rows, forms, cache, stop/cancel, query binding, persistent hidden widgets, date/time sliders, and most other input widgets remain incomplete or absent. Widget failures are Rust `Result` errors; Python-style exception elements and matching exception UI are not implemented. Native session values, reruns, retained-session reconnects, synchronous callbacks, explicit widget keys and one-shot button triggers are available, without a claim of complete Streamlit compatibility.
