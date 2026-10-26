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
| `st.slider(("When", NaiveDate::from_ymd_opt(2024, 3, 15)?))?` | date bounds 2024-03-01..2024-03-29, step 1 day |

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

## Use a form and text input

```powershell
cargo run --example forms --locked
```

Open `http://127.0.0.1:8504/`. The example shows the measured business journey of `st.form`, `st.form_submit_button`, `st.text_input`, and an external button:

```rust
let (note, submitted) = st.form(FormOptions::new("apply_form"), |form| {
    let note = form.text_input(TextInputOptions::new("Note").key("note"))?;
    let submitted = form.form_submit_button(FormSubmitButtonOptions::new("Apply note").key("apply_note"))?;
    Ok((note, submitted))
})?;
if submitted {
    st.session_state().set("applied_note", note.clone())?;
}
let pulse_clicked = st.try_button(ButtonOptions::new("Pulse").key("pulse"))?;
```

Forms can be appended from the app, a container, or a column, and a form can contain the existing container and column helpers. The nested-layout wire order is covered by Rust render tests; it is not a browser-compatibility claim beyond the captured form cases.

Form keys are unique among forms; explicit widget keys remain unique across the page. A form and a widget may use the same key spelling. Anonymous widgets include their form in their identity. If the form closure returns an error or omits a submit button, its widgets are not emitted and their registrations are rolled back. Unrelated application state writes made by the closure are retained.

Values inside the form are staged by the official frontend and sent together when the submit button is clicked. Typing without submitting does not rerun the app; `Apply` applies the note, and the external `Pulse` button can then rerun the page three times without losing it. The submit trigger is one-shot. `TextInputOptions::new("Note")` defaults to an empty string; `value_none()` makes the initial return value `None` while leaving the visible field empty.

See [TextInputOptions](../../streamlit/src/widget_api.rs) for text types, validation, debounce and presentation options. Browser validation is performed by the official frontend; security-sensitive application code must still validate submitted values on the server.

Query binding and persistent hidden-widget state are not yet claimed complete. Form and submit-button layout fields beyond the measured defaults, exception elements beyond duplicate widget keys, and full widget lifecycle/error parity also remain outside a complete compatibility claim.

The basic form flow is available; support beyond it remains partial. See [form validation scope](../../.codex/compatibility.md#forms-validation-scope) for the reference/Rust coverage and remaining limits.

Duration strings currently support `0`, milliseconds such as `250ms`, and seconds such as `0.25s`, up to one minute. The example uses a fallible render helper and handles its error once. The CSV `data_app` also includes the Note form described below.

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

Under **Interaction**, type in **Note** and click **Apply note** to update **Applied note**. Editing alone does not submit the form or rerun the page. The submitted note stays in the input; to clear the applied note, empty the field and submit again. Changing filters or clicking **Pulse** preserves the last applied note and the uploaded data. **Script runs** counts completed app executions, while **Pulses** increases only when Pulse is clicked. These values belong to the current browser session. The interaction controls remain available after a CSV parse error so you can continue interacting and replace the upload with a valid file.

The CSV needs lowercase `amount` and `region` headers. Optional `category` and `channel` columns provide additional grouping choices. Unusable amount cells are excluded with a warning; other rows still aggregate. Malformed rows report the CSV record number and expected/actual field counts. Non-UTF-8 files are rejected. Both hard failures show an error instead of data views; select a valid CSV in the same uploader to recover.

A header-only file shows **The uploaded CSV contains no data rows.** To filter all sample rows out, set **Minimum amount** to 200: **No rows match the current filters.** appears with an empty four-column dataframe and no chart. Set the slider back to 0 to restore the results without reloading. Totals and averages use this application's decimal HALF_UP rule, not a universal Streamlit rounding rule; averages round once from the unrounded sum divided by the count. Decimals exceeding the example's native precision are rejected instead of silently rounded.

Below the results, **Interaction** contains **Pulse**, followed by **Script runs: N** and **Pulses: N**. Each script run increments the session's run count once; clicking Pulse increments both counters once while leaving the aggregate data unchanged. Filter changes rerun the script without adding a pulse. These counters are session-local and start at 1/0 on the first run of a fresh session; this data app does not use the `st.rerun`/`st.stop` execution controls — the [execution example](#execution-semantics-rerun-and-stop) demonstrates them.

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

## Line, area, scatter charts and maps

```powershell
cargo run --example charts --locked
```

Open `http://127.0.0.1:8512/` (stop another example on that port first). The [charts example](../../streamlit/examples/charts.rs) mirrors the Python reference fixture of the charts differential chain: one line, area and scatter chart plus one map, rendered byte-for-byte like the reference page.

```rust
st.line_chart(batch)?;                                          // one numeric series over a generated index
st.area_chart(batch)?;                                          // every numeric series melted into one area
st.scatter_chart(ScatterChartOptions::new(batch, "x", "y"))?;   // explicit numeric columns
st.map(batch)?;                                                 // latitude/longitude columns, auto viewport
```

`MapOptions::new(batch).latitude("lat").longitude("lon").zoom(12)` renames the coordinate columns or pins the zoom; the default bisects the data's extent over the reference's zoom ladder. Line charts require exactly one numeric series and area charts int64 series — out-of-subset input returns an error instead of approximating. The chart datasets' Arrow bytes come from the Rust writer (semantically identical, including the pandas metadata; the content-derived dataset name therefore differs from a pyarrow run, which the frontend never observes).

## Input widgets

```powershell
cargo run --example widgets --locked
```

Open `http://127.0.0.1:8501/`. The example renders selectbox, checkbox, integer and floating-point scalar sliders, integer tuple and floating-point array range sliders, a disabled button, and returned values. Each changed input updates its returned value and increments the callback count. It does not render a data table; date/time sliders have their own [example](#temporal-sliders).

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

These methods return `Result` and also work in containers and columns. Selectbox returns an original option (`Option<T>`), not its display label or index. `.index(None)` starts empty; `.format_func(|option| ...)` changes labels only. Use `SelectboxOptions::with_format_func(...)` for types without Display, including `Option<T>` and `()`. A selected None option returns `Some(None)`; an unselected `Option<T>` selectbox returns `None`. Empty options disable selection. Checkbox defaults to content width; selectbox and slider stretch. Numeric sliders accept `i32`, `i64`, `f64`, or two scalar endpoints of the same type as `(T, T)` or `[T; 2]`. Pass the lower bound as the initial value to start there. Bounds and step must be finite, ordered, and positive as appropriate; integer bounds stay within JavaScript's exact integer range and the chosen Rust return type (`i32` or `i64`). `.format(...)` changes slider display only. Date/time sliders are covered below; adding new selectbox options is not available yet.

Use `.on_change(|st| { ... })` on inputs or `ButtonOptions::new("Apply").on_click(|st| { ... })` for a button callback. Incoming widget values are applied together, then synchronous callbacks execute before main. Captures must be `Send + Sync + 'static`; callbacks can read updated keys and write application state. `.ignore_rerun(true)` buffers an input change in the frontend until another event reruns the script. Default reruns preserve input values and one-shot buttons reset each run. Give repeated widgets distinct keys: a duplicate explicit key makes the framework render the duplicate-key exception box and stop that run's remaining output (see [Execution semantics](#execution-semantics-rerun-and-stop)); colliding automatic IDs return `WidgetError`. The original `button` returns `bool` and panics on a registration error; use `try_button` for a `Result`.

Widget keys are removed at the end of a run if that widget was not rendered; unrelated application keys remain. Keyed slider bounds/step changes reset its value. These behaviors do not establish full widget identity, cleanup-exception or callback/error parity, or complete compatibility.

## Choice and text inputs

```powershell
cargo run --example inputs --locked
```

Open `http://127.0.0.1:8508/`. Radio, multiselect, number_input and text_area follow the same value-first style, with a one-line shorthand beside every full-options form:

```rust
let channel = st.radio(("Channel", ["email", "sms", "push"]))?;            // Option<String>, first option checked
let tags = st.multiselect(("Tags", ["alpha", "beta", "gamma"]))?;          // Vec<T>, nothing preselected
let count = st.number_input(("Count", 7_i64, 0..=100))?;                   // i64, step 1
let note = st.text_area(("Note", "first line\nsecond line"))?;             // Option<String>

let pick = st.radio(RadioOptions::new("Channel", ["email", "sms"]).index(None).key("channel"))?;
let tagged = st.multiselect(
    MultiselectOptions::new("Tags", ["alpha", "beta", "gamma"]).default_indices([0]).key("tags"),
)?;
let ratio = st.number_input(NumberInputOptions::new("Ratio", 0.5_f64).min(0.0).max(1.0).step(0.05))?;
let remark = st.text_area(TextAreaOptions::new("Note", "").value_none().max_chars(200).placeholder("Add a note"))?;
```

`st.radio` returns the selected option's text (`Option<String>`); `.index(None)` starts unchecked. `st.multiselect` returns `Vec<T>` of the selected original options; `.default_indices([0, 2])` preselects by position and `.format_func(|item| ...)` changes labels only. `st.number_input` returns `i64` or `f64` as declared — the plain `("Count", 7_i64)` starts at the value with step 1 and no bounds, and the range tuple `("Count", 7_i64, 0..=100)` pins explicit bounds in one expression; floats start with step 0.01. `st.text_area` returns `Option<String>`; `.value_none()` starts the return value as `None` while the field stays empty. All four commit the way the official frontend does — radio and multiselect immediately, number_input and text_area when the control loses focus. The integer wire shapes (default indices, `%d` format, `INT` data type, `accept_new_options`/`select_all` flags, string/string-array/int states) are the measured 1.66.1 contract behind [journey-inputs-v1](../../tests/browser/inputs_contract.py); the float number_input path follows the same encoding but is not yet reference-measured.

## Media and metrics

```powershell
cargo run --example media --locked
```

Open `http://127.0.0.1:8509/`. Images, audio, metrics and progress follow the measured 1.66.1 media route — each media asset is served from `GET /media/{file_id}.{ext}`, a content address the reference derives as BLAKE2b-128 over `"{len}:" + bytes + mime type`:

```rust
let shot = st.image((gradient, "gradient"));                  // (RgbaImage, caption) or plain RgbaImage
st.audio((wav_bytes, "audio/wav"));                          // (bytes, MIME type)
st.metric(MetricOptions::new("Temperature", "72 °F").delta("2 °F"));
st.metric(MetricOptions::new("Wind", "8 mph").delta("-3 mph").delta_color(DeltaColor::Inverse));

let bar = st.progress(50)?;
bar.set(75);                                                  // coalesces: one delta with the final value
```

`RgbaImage::new(width, height, pixels)` takes `width*height*4` RGBA8 bytes and is the measured `st.image` input shape. Metrics derive their arrow direction and color from the delta's first number word plus the `DeltaColor` mode (`Normal`, `Inverse`, `Off`). `st.progress` returns a handle whose updates coalesce into the single final-value delta the reference streams at the end of the run. The wire shapes behind [journey-media-v1](../../tests/browser/media_contract.py).

`st.video((bytes, "video/mp4"))` follows the same route with the measured NATIVE element and stretch width inside its message; the chain behind [journey-video-v1](../../tests/browser/video_contract.py) serves a committed sample byte-identically across runtimes.

For feedback moments: `st.spinner("Loading data", || { ... })` streams a transient spinner around the closure and clears it on exit (consuming no element slot), `st.toast(ToastOptions::new("Saved").icon("✅"))` shows a four-second one-shot toast routed to the frontend's dedicated toast slot, and `st.balloons()` celebrates — all on the measured timeline behind [journey-presentation-v1](../../tests/browser/presentation_contract.py).

## Temporal sliders

```powershell
cargo run --example temporal --locked
```

Open `http://127.0.0.1:8506/`. `st.slider` also accepts `chrono::NaiveDate`, `NaiveTime`, `NaiveDateTime`, or two endpoints of one type as `(T, T)` / `[T; 2]`. On the wire — measured against Python 1.66.1 with the official frontend — every temporal value is an integer number of epoch microseconds carried as a double: a naive date-time encodes as if UTC, and a time of day counts from 2000-01-01 00:00:00. Without explicit bounds, a date or date-time spans its value ± 14 days with a daily step, a time spans the full day with a 15-minute step, and a range hangs its window off the first endpoint. Microsecond components round-trip exactly; values outside the exactly-representable double range (roughly 1677–2262) are rejected as invalid instead of silently losing precision. `.min(...)`/`.max(...)` accept the temporal type itself, and `.step(...)` accepts a `chrono::TimeDelta` (whole microseconds only):

```rust
use chrono::{NaiveDate, NaiveTime, TimeDelta};

let when = st.slider(("When", NaiveDate::from_ymd_opt(2024, 3, 15)?))?;
let at = st.slider(("At", NaiveTime::from_hms_opt(9, 30, 0)?))?;
let window = st.slider((
    "Window",
    (NaiveDate::from_ymd_opt(2024, 3, 10)?, NaiveDate::from_ymd_opt(2024, 3, 20)?),
))
.step(TimeDelta::days(1))?;
```

## The elements page

```powershell
cargo run --example elements --locked
```

Open `http://127.0.0.1:8507/`. One page shows the text and layout APIs (title, header, caption, badge, divider, code, markdown, write), two columns, a container, a working form with a text input and submit button, a table and a bar chart. It mirrors the Python reference fixture of the elements differential chain, so what you see is byte-for-byte the rendered reference page.

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

## Execution semantics: rerun and stop

```powershell
cargo run --example execution --locked
```

`st.rerun()` aborts the current run and starts the next one immediately, without a browser request; `st.stop()` ends the run but keeps everything rendered so far. After either call, later element pushes and session-state writes of the same run have no effect. Guard `rerun` so it fires exactly once — for example with a session-state flag — or the app reruns forever:

```rust
if st.session_state().get::<bool>("initialized").ok().flatten().is_none() {
    st.session_state().set("initialized", true)?;
    st.rerun();
}
st.write("rendered from the second run");
```

Both follow the measured Streamlit 1.66.1 wire: an aborted rerun finishes with `FINISHED_EARLY_FOR_RERUN`, a stopped run still finishes `FINISHED_SUCCESSFULLY`, and elements streamed before the call stay on the page. The [execution example](../../streamlit/examples/execution.rs) mirrors the reference fixture and lets you watch both behaviors through the selector.

A widget whose explicit `key` is already live in the run no longer returns an error: like Python Streamlit, the framework itself renders the `StreamlitDuplicateElementKey` exception box (the red box users know), suppresses every later element of that run and still finishes successfully; your code receives the widget's default value and keeps running with its output suppressed. Invalid options (bad widths, out-of-range indexes, illegal form layouts and so on) remain ordinary `Result` errors you handle yourself. Press **Show duplicate-key error** in the [widgets example](#input-widgets) to see the rendered box; only its trace line differs from Python, because Rust cannot know your source line.

## Layouts: sidebar, expander, tabs, popover, and dialogs

```powershell
cargo run --example layouts --locked
```

Open `http://127.0.0.1:8513/`. Every layout container is a handle you write into, mirroring the Python `with` blocks:

```rust
let sidebar = st.sidebar();
sidebar.write("side note");

let expander = st.expander(ExpanderOptions::new("Details").expanded(true));
expander.write("inside expander");

let tabs = st.tabs(["One", "Two"]);
tabs[0].write("first tab");
tabs[1].write("second tab");

let popover = st.popover("Open settings");
popover.write("inside popover");

st.dialog("Confirm", |dialog| {
    dialog.write("inside dialog");
});
```

Use | Rust form
--- | ---
Sidebar | `st.sidebar()` — a write handle fixed to the sidebar root; elements interleave with the main flow.
Expander | `st.expander("Details")` or `ExpanderOptions::new("Details").expanded(true).icon(":material/info:")`.
Tabs | `st.tabs(["A", "B"])` returns one handle per label; also `TabsOptions::new(["A", "B"])`.
Popover | `st.popover("Open settings")` or `PopoverOptions::new(label).icon(...)`.
Dialog | `st.dialog("Confirm", \|dialog\| { dialog.write("..."); })` — opens the modal, streams the body, and closes the scope like a called `@st.dialog` function.

The wire follows the measured 1.66.1 shapes: tab blocks are all emitted when `st.tabs` is called (before any child), expander and popover children stream at the slot's own index, and a dialog opens as a block pair on the event root with the reference's `$$ID-<hash>-None` naming. `DialogOptions::new(title)` carries `.width(DialogWidth::Large)`, `.position(DialogPosition::Left)`, `.dismissible(false)` and `.icon(...)`. The [layouts example](../../streamlit/examples/layouts.rs) mirrors the reference fixture of the layouts differential chain, so the rendered page matches the Python reference.

## Page configuration

```rust
st.set_page_config(
    PageConfigOptions::new()
        .page_title("Wide demo")
        .page_icon(":material/check_circle:")
        .layout(PageLayout::Wide)
        .initial_sidebar_state(InitialSidebarState::Expanded)
        .menu_items(
            MenuItems::new()
                .get_help("https://docs.streamlit.io/")
                .report_bug("https://github.com/streamlit/streamlit/issues")
                .about("### About text"),
        ),
);
```

A plain title string works too: `st.set_page_config("Wide demo")`. The call must come before the first element to take visual effect, exactly like Python. Like the measured 1.66.1 reference, every call streams one `page_config_changed` message at the call point and unset fields inherit the previous config — a second call does not fail, it streams an update. The [pageconfig example](../../streamlit/examples/pageconfig.rs) mirrors the reference fixture of the page-config differential chain.

## URL query parameters

```rust
let params = st.query_params();
params.set("mode", "demo")?;              // streams the merged URL state
let mode = params.get("mode");            // Some("demo") once the browser reports it
for (key, value) in params.to_vec() { /* ... */ }
```

The handle reads the URL state the browser reports with every rerun; writes stream one `page_info_changed` at the call point and merge into the current URL (alphabetically sorted, percent-encoded like Python's urlencode). `get_all`, `set_all`, `remove` (missing keys error, like Python) and `clear` are available.

Selectboxes can bind to the URL and accept new values:

```rust
let pick = st.selectbox_creation(
    SelectboxCreationOptions::new("Pick", ["a", "b"]).filter_mode(SelectFilterMode::Contains),
)?;                                       // Option<String>; typed values are accepted
let bound = st.selectbox(
    SelectboxOptions::new("Bound", ["x", "y"]).key("bound").bind(TextBind::QueryParams),
)?;                                       // queryParamKey on the wire; the frontend syncs the URL
```

The [queryparams example](../../streamlit/examples/queryparams.rs) mirrors the reference fixture of the query-params differential chain, so the URL behavior matches the Python reference.

## Caching

```rust
let doubled = st.cache_data("double").call(21, |n: i64| n * 2);  // 42, computed once per argument
let shared = st.cache_resource("model").call((), |()| vec![1, 2, 3]);  // Arc<Vec<i32>>, built once and shared
st.cache_clear();                                                // drop every entry of this session
```

A miss runs the function, streams one empty spinner-shaped transient at the call site and records everything the function streamed (an `st.write` inside a cached function replays on every hit at its original position); a hit replays those elements with no transient and the value comes back without recomputation. Keys are the name plus the JSON serialization of the argument, so `call(21, ...)` and `call(7, ...)` are distinct entries. Unlike Python's process-wide store, the cache lives in the session state. The [cache example](../../streamlit/examples/cache.rs) mirrors the reference fixture of the cache differential chain.

## Multipage navigation

```rust
fn main_page(st: &Streamlit) { st.write("page=main"); }
fn other_page(st: &Streamlit) { st.write("page=two"); }

let nav = st.navigation([
    Page::new("Main", main_page).icon(":material/home:").default(true),
    Page::new("Two", other_page).url_path("two"),
]);
nav.run();                                  // runs the page the browser addressed
st.switch_page("two")?;                     // or switch programmatically
```

`st.navigation` renders the sidebar nav (one page per entry; a page's url path is its identity and defaults to its sanitized title) and `nav.run()` executes the addressed page, or the default one on a first load. Session state persists across pages. `st.switch_page` finishes the current run and the server immediately runs the target page, exactly like the reference. The [navigation example](../../streamlit/examples/navigation.rs) mirrors the reference fixture of the navigation differential chain.

## Current API

Available APIs include text and layout, static status messages, `button`, `selectbox` (including creation mode, filter modes and query binding), numeric and date/time `slider`, `checkbox`, the measured `form`/`form_submit_button`/`text_input` core, native session state, the layout containers (sidebar, expander, tabs, popover, dialog), `set_page_config`, `query_params`, `cache_data`/`cache_resource`, multipage navigation (`navigation`/`Page`/`switch_page`), media and chart elements, and the `st.rerun`/`st.stop` execution controls. See the [text/layout/status API](../../streamlit/src/api.rs), [layout containers](../../streamlit/src/elements/layouts.rs), [widget options](../../streamlit/src/widget_api.rs), [query params](../../streamlit/src/query_params.rs), [cache](../../streamlit/src/cache.rs), [navigation](../../streamlit/src/navigation.rs), and [session API](../../streamlit/src/session.rs).

Upload and columnar data views currently cover the limited paths described above. General table/chart APIs, selection, complete forms/text-input behavior, persistent hidden widgets, and most other input widgets remain incomplete or absent (`st.quit` does not exist in 1.66.1; the Rust cache is session-scoped, not process-wide like Python's). Duplicate widget keys render the framework exception box as described above; other widget failures are Rust `Result` errors you handle yourself. Native session values, reruns, retained-session reconnects, synchronous callbacks, explicit widget keys and one-shot button triggers are available, without a claim of complete Streamlit compatibility.
