# Data loop reference (Python 1.66.1)

Uploads \`tests/fixtures/csv/sales_basic.csv` to the pinned Python 1.66.1
reference app with the official frontend and then changes the three filters.
Every stage keeps the table's Arrow payload, the chart's spec and datasets, the
rendered cells and bars, the client state and the completion that followed it.

- `upload/`: the upload exchange and the first table and chart.
- `updates/`: the upload and the three filter changes, stage by stage.

## The upload

| step | what happened |
|---|---|
| the client asks for upload URLs | `file_urls_request` {request_id, file_names: ["sales_basic.csv"], session_id} |
| the server answers | `file_urls_response` {response_id (the same id), file_urls: [{file_id, upload_url, delete_url}], error_msg: ""} |
| the browser uploads the file | `PUT` `/_stcore/upload_file/<session_id>/<file_id>`, `Content-Type: multipart/form-data; boundary=...` -> **204**, `text/plain` |
| the widget state that follows | `file_uploader_state_value` with `uploadedFileInfo` [{name, size, fileId, fileUrls:{fileId, uploadUrl, deleteUrl}}] |

The uploader element is
`{id: "$$ID-19480263d3eb5977e56726a4936e1a89-upload", label: "Upload sales CSV", type: [".csv"], maxUploadSizeMb: 200, labelVisibility: {}, widthConfig: {useStretch: true}}`.

## The stages

Each stage names the value the client sent, the rows the server sent back as
Arrow, what the page showed and the frames that carry the state and the
completion.

| stage | the client sent | the rows | bars | Arrow |
|---|---|---|---|---|
| after the upload | -- | Books 3/245.75, Games 3/409.48, Music 3/139, Toys 3/104.49 | 4 | `arrow-1.bin` sha `2ef28720…9a5c2` |
| Group by -> region | `"category"` -> `"region"` | (missing) 1/88, East 2/209.49, North 3/264.5, South 2/245.24, UNKNOWN 2/40.49, West 2/51 | 6 | `arrow-2.bin` sha `ebee1250…d5179` |
| Include unknown region off | `true` -> `false` | East 2/209.49, North 3/264.5, South 2/245.24, West 2/51 | 4 | `arrow-3.bin` sha `a9b51a91…0301d` |
| Minimum amount 100 | `[0]` -> `[100]` | East 1/149.5, North 1/120.5, South 1/199.99 | 3 | `arrow-4.bin` sha `6b6f0ef9…aa73` |

The chart names its data set by a hash that changes with every stage
(`b4d4aa9b…`, `32bd595f…`, `dde7debe…`, `efb49298…`), and the table and the
chart carry the same Arrow payload, which is therefore stored once per digest.

The Arrow schema is
`group_key: large_string`, `row_count: int64`, `total_amount: double`,
`avg_amount: double`, with the pandas metadata block.

**The order matters.**  With the filters in the order *group -> slider ->
checkbox* the checkbox changes nothing: the only row with a missing region has
an amount of 88.00, which the slider at 100 has already excluded, and
"UNKNOWN" is a literal region value.  That capture is kept under
`target/data-loop-steps3/` and is not part of the repository.

## Superseded

The first capture of the upload alone, before the filter stages, was
`trace-data-loop.json` with sha256
`0a62601c2d36c48f54e4cf6f59062527120ad7245ecb419c8ab3d95572f5b430`.  It was
not edited; the capture with the stages is a new file.

## The strict capture

`updates-strict/` is the same capture with the strict verdict: every stage is
tied to the result this step caused -- the Arrow the server sent inside the
window, the rows the page shows and the geometry the chart actually drew.

| stage | the Arrow of the step | the rows on the page | the chart marks |
|---|---|---|---|
| Group by -> region | `arrow-2.bin` | (missing) 1/88, East 2/209.49, ... | the bar paths change |
| Include unknown region off | `arrow-3.bin` | East 2/209.49, North 3/264.5, ... | the bar paths change |
| Minimum amount 100 | `arrow-4.bin` | East 1/149.5, North 1/120.5, South 1/199.99 | the bar paths change |

The chart evidence is the drawn geometry, not the number of bars: the probe
collects the `d` attribute of every bar path, and the scale with it in the
axis labels.  A hover tooltip was tried and did not materialise in the headless
browser, so it is not part of the evidence.  A stage passes only when

- the action ran and the widget's own state in the window carries a changed
  value,
- a `script_finished` with status 0 follows it on the same connection,
- the window carries the Arrow of this step, and the page shows its rows,
- the table's cells changed, the chart drew new marks, and the number of bars
  is the number of rows.

`updates/` (sha256
`9b1e058401f43d761d6633dfc603d83fb0fed243ff10a04daaa263378c0a0d07`) is the
earlier capture of the same three stages, before the strict verdict and
without the chart geometry.  It was not edited and it is kept for the record;
`updates-strict/` (sha256
`82399d788f9237a560daf1e88310cbeefe271f243396f6ab7a2fa1199519f35a`) supersedes
it.

The entry reports what it did and fails when it did not work: the trace carries
the counts (`expected`, `executed`, `asserted`) and the failures, and the
command exits non-zero when there are any.

Regenerate:

~~~powershell
python -m streamlit run tests\\reference\\app.py --server.headless true --server.port 8601
python tests\\browser\\numeric_capture.py --url "http://127.0.0.1:8601/" --case data-loop \\
    --fixture tests\\fixtures\\csv\\sales_basic.csv --label python-data-loop
~~~

The `agent-browser` CLI could not start its daemon in this environment, so the
entry drives the same real Chrome over the DevTools Protocol: the file is
handed to the browser with `DOM.setFileInputFiles` and the browser uploads it
itself.  The reason is recorded in the `capture` block of the raw.
