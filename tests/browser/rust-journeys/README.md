# Rust data journeys

The data app of the Rust implementation, driven with the official Streamlit
1.66.1 frontend: the closed loop and the three journeys of the data app.

**Server under test**

- binary `target/checks/data-app-live/data-app-security-final-20261024T152745018.exe`
- sha256 `427F3AF719559C14B8A207660B9BA562D42C6F2C9A6B16E7C3864DED9B1D3A19`
- source sha256 `13373cf614f0f16db351d51a72fdc4902504d7952dd53258625c9bae58b09531`
- config sha256 `a552d879a67c536617e42933128e85329f30aafadd83cb34fd763f55ba2f26fc`
- `HEAD 1c6161d` plus the owner's uncommitted increment

**The captures**

| raw | journey | expected | executed | asserted | failures | exit |
|---|---|---|---|---|---|---|
| [data-loop/](data-loop/trace-data-loop.json) | upload, group by region, unknown off, minimum 100 | 3 | 3 | 3 | none | 0 |
| [recover/](recover/trace-data-loop.json) | a file that cannot be read, then a good one | 12 | 12 | 12 | none | 0 |
| [empty/](empty/trace-data-loop.json) | a file without data rows | 7 | 7 | 7 | none | 0 |
| [sessions/](sessions/trace-data-loop.json) | two tabs, two sessions | 11 | 11 | 11 | none | 0 |

The counts are the checks of the journey, not the steps of the manifest: every
check says what it expected, what it saw and whether it held, and the shared
criterion requires the whole fixed set of them.

**What the pages showed**

- the upload: the client asks for the upload URLs, the server answers with the
  file id and the upload and delete URLs, the browser puts the file there with
  a `PUT` that answered **204**.
- the recovery: the malformed CSV answered the error
  `Could not parse the uploaded CSV: CSV error: record 2 (line: 3, byte: 119):
  found record with 7 fields, but the previous record has 8 fields` together
  with `Upload a valid CSV to continue.`, no table and no chart.  Replacing
  the file with `sales_basic.csv` answered a **DELETE 204** for the file the
  server had signed out, left only the new file on the page and restored the
  table and the chart.
- the empty file: `The uploaded CSV contains no data rows.`, the four columns
  of the file with no body row and no bar.
- the two tabs: different session ids, their own file, their own group
  (`region` against `category`) and their own result.

**Where the evidence came from**

The capture ran once, in `target\final-427F-20261024T162828`, under the criteria
`B29B4F85AC9BEBE885C4B3EEE8E2142D8A44DC4724C6A9F1075BB09062DA08F6`, and the files here are those bytes.
The same raws were re-validated against the newer criterion `DA2E746A8267E1DFAC65CF0CB5513B3C6B729B33C5035C3CF5C253F016925D9A`,
which binds the result to the run that carries the target state, by the script
run id the server names in NewSession: the same counts and the same verdicts
(191 related tests).  A capture under the newer criterion stands in
`target\final-427F-20261024T164330`.
The raw keeps the capture-time `ipc_dir` of that directory; the IPC payloads
are the `arrow-N.bin` files **beside each raw** (one per digest, 1224 bytes
each -- the Rust IPC does not carry the pandas metadata block of the
reference), so a replay resolves them next to the raw instead of in the
ignored `target/` tree.

**Regenerate** (the paths are absolute: Chrome resolves a relative path
against its own working directory and the uploader would get no file):

~~~powershell
$fx = (Resolve-Path tests\fixtures\csv).Path
$bin = "target/checks/data-app-live/data-app-security-final-20261024T152745018.exe sha256 427F3AF719559C14B8A207660B9BA562D42C6F2C9A6B16E7C3864DED9B1D3A19"
target\pyref-venv\Scripts\python.exe tests\browser\numeric_capture.py --url http://127.0.0.1:8501/ \
    --case data-loop --files "$fx\sales_basic.csv" --label rust-final-positive \
    --out target\rust-positive --binary $bin --scope "RUST SIDE ONLY"
target\pyref-venv\Scripts\python.exe tests\browser\numeric_capture.py --url http://127.0.0.1:8501/ \
    --case data-loop --journey recover --files "$fx\sales_malformed.csv,$fx\sales_basic.csv" \
    --label rust-final-recover --out target\rust-recover --binary $bin --scope "RUST SIDE ONLY"
target\pyref-venv\Scripts\python.exe tests\browser\numeric_capture.py --url http://127.0.0.1:8501/ \
    --case data-loop --journey empty --files "$fx\sales_empty.csv" \
    --label rust-final-empty --out target\rust-empty --binary $bin --scope "RUST SIDE ONLY"
target\pyref-venv\Scripts\python.exe tests\browser\numeric_capture.py --url http://127.0.0.1:8501/ \
    --case data-loop --journey sessions --files "$fx\sales_basic.csv,$fx\sales_unicode.csv" \
    --label rust-final-sessions --out target\rust-sessions --binary $bin --scope "RUST SIDE ONLY"
~~~

The driver is `tests/browser/numeric_capture.py` (sha256
`9EDC3FA1D456E5592771C448AC5E600C99D71398C5E55CCB7E8A541F61E5F966`); the
criteria live in `tests/reference/capture_browser_trace.py` (sha256
`B29B4F85AC9BEBE885C4B3EEE8E2142D8A44DC4724C6A9F1075BB09062DA08F6`, re-validated against `DA2E746A8267E1DFAC65CF0CB5513B3C6B729B33C5035C3CF5C253F016925D9A`).
The `agent-browser` CLI could not start its daemon in this environment, so
the entry drives the same real Chrome over the DevTools Protocol; the reason
is recorded in the `capture` block of every raw.  The decoder needs the
pinned interpreter `target\pyref-venv\Scripts\python.exe` (streamlit
1.66.1 with its protobuf definitions); without it the entry stops before it
records anything.

**The earlier closed loop**

`tests/browser/rust-data-loop/` was the same closed loop against the earlier
build `data-app-20261024T141223140.exe` (sha256
`F8A0D4CA241F64F98CC7CF5736869491DE07D958E0428C2EC3EB687DC9AC44A3`).  Its raw
carries the kind and the scope of a Python reference capture, because the
positive path labelled itself that way before the label was taken from the
command line; the raw is left as it is and the capture above supersedes it.

**What these captures do not cover**

The parse-error wording of the Rust app differs from the reference text
(`Could not parse the uploaded CSV: CSV error: record 2 ...` against
`Could not parse the uploaded CSV: row 3: expected 8 fields, found 7`), the
soft failure of the unusable amounts and the non-UTF-8 file were not captured,
and no screenshot was taken.  The journeys of `tests/journeys/journeys.json`
stay `failed` for exactly those parts.
