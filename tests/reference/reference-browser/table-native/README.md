# Python 1.66.1 table / native bar reference

This is a selected archive of real official-browser WebSocket/DOM observations,
not generated goldens. [archive.json](archive.json) records every copied file's
SHA256, byte count, original target path and IPC reference mapping. Raw JSON and
IPC bytes were copied unchanged from `target/checks/table-reference/`.

The primary cases are `table-default`, `table-explicit`, `bar-default` and
`bar-horizontal`, each before and after a real Update data click on the same
WebSocket. Initial runs alone are retained for hidden/custom-index tables,
XY/multiple/single bars, mixed large integers and four selected errors. These
support the bounded parameter tests; they do not imply additional Rust browser
coverage. The matching Rust four-view capture is
[rust-table-native](../../../browser/rust-table-native/README.md).

There are 18 raw records, 10 distinct IPC streams and two screenshots. Shared
table IPC and XY/horizontal IPC are stored once under `ipc/<sha256>.bin`.
Historical `arrow.file` strings inside raw JSON are deliberately unchanged.
Resolve them through the matching `records[].ipc_references` in archive.json;
`archive_path` values are relative to the repository root. This is the path
relocation map, not a modification of historical CDP events or decoded fields.

The public-only [fixture](../../table_app.py) is development evidence and is not
a production dependency. Its reviewed final SHA256 is
`04218d51170c98fa60d32ee2e1fe7acae8d74bed8f907f65a2fc35d546c3fdde`.
Later isolated cases were appended during capture; existing earlier case calls
were preserved. Runtime checks in the same reference venv reported Python
3.12.6, Streamlit 1.66.1, pandas 3.1.0 and PyArrow 26.0.0. Public API authority:
[table](https://docs.streamlit.io/develop/api-reference/data/st.table) and
[bar_chart](https://docs.streamlit.io/develop/api-reference/charts/st.bar_chart).
Those documentation pages displayed 1.66.0; measured runtime was 1.66.1.

Actual launch commands, from the repository root (ports must be free):

```powershell
target/pyref-venv/Scripts/python.exe -m streamlit run tests/reference/table_app.py --server.headless=true --server.port=8605 --browser.gatherUsageStats=false
agent-browser --session table-reference open about:blank
agent-browser --session table-reference get cdp-url
```

Capture used one-off Python stdin importing the existing
`tests/reference/capture_browser_trace.py` `CDP`/`_decode_payload` and
`tests/browser/numeric_capture.py` `Page`. It attached before Page.navigate to
`http://127.0.0.1:8605/?case=<case>`, waited for script_finished and rendered
values, clicked the actual button with CDP input events, then recorded the next
completed run. Official protobuf and PyArrow decoded the received bytes. No new
parallel recorder/decoder/probe framework is introduced here. The launch
commands alone do not replay the historical capture; the archived raw is the
measurement authority. The shared verdict was not used as a PASS oracle.

Default table retains UTF-8/Markdown/null data; Markdown renders as strong text
and null as blank. Default bar has eight melted IPC rows: `(index=2,cost,null)`
has no mark, while `(index=3,sales,0)` retains a zero-height mark. All seven
nonnull index/series/value tuples were compared individually. Explicit table
uses horizontal borders, visible index/header, 480x220 element layout and an
accessible name. Horizontal bars swap coordinate encodings and preserve data
order with `sort:null`.

Selected invalid calls are caught by the fixture and emitted as JSON with the
actual exception class/message. `FINISHED_SUCCESSFULLY` therefore indicates
completion of the catching script, not success of the invalid API call. No
table/chart IPC is emitted for those calls.

Known numeric difference: Python promotes mixed Int64/Float64 series to Float64,
rounding `9007199254740993` to `9007199254740992` and `9223372036854775807` to
`9223372036854775808`. Rust currently rejects magnitudes above 2^53 in that mixed
promotion, including some larger exactly representable even integers. This is
an explicit partial-compatibility gap. Other numeric/color/stack/selection and
complex index combinations are not covered in full.
