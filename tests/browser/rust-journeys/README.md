# Rust data journeys

## J01: continuous input and aggregation

[j01-sequence/trace-data-loop.json](j01-sequence/trace-data-loop.json) is the
unchanged 165-frame capture from `target/j01-rust-preserved-20261025T002726`,
with its four adjacent IPC files and seven PNGs. SHA256:
`ec3f21129a47da4c09fbff278605907eb1d26527d034d5c001d5833d6de5e71d`.
Its binary/source identity is the historical 943/810f build recorded in the
raw, build base `ef359b1`, capture HEAD `1f2a852`; this is not a claim about
later source changes.

The raw retains its capture-time 15/15/15 result and exit 0. Its capture-time
criteria SHA was not recorded. Hooke independently reviewed the complete
Python/Rust chains and their PNGs; final replay of both unchanged raws gives
15 expected / 15 executed / 15 asserted, no failures, under criteria SHA256
`5e8cc8ee305dde3615dffea3b09f05ed1d3ea88e1f6a41c06fd9b2e68d7714c3`.
This is a **final replay identity**, not metadata backfilled into the raw.
The subsequently reviewed producer is `tests/browser/numeric_capture.py`, SHA256
`85071c856c0d0af709b71c26cd4885f9b7277c373ad6a590d017e0d3d092b1f6`;
that hash is not asserted as the capture-time driver identity.

The shared `journey-j01-input-v1` contract keeps five original business steps:
S1/S2/S3/S4/S5 map to PNGs 02/03/04/06/07, copied byte-for-byte to
`tests/e2e/J01/J01-S1.png` through `J01-S5.png`. PNGs 01 and 05 retain initial
and explicit category/0/on preparation evidence. Phase roles and all PNG hashes
remain in the raw. No reload or reconnect joins the phases; runs are
1/2/3/4/5/7/9 and pulses stay 0. Unicode and BOM have equal logical results
and IPC, with distinct issued file IDs, target runs and new result frames.

Replay the archived bytes with the pinned interpreter, resolving adjacent
IPC/PNG files in memory; never rewrite the historical `ipc_dir` in the raw:

```python
import json
from pathlib import Path
from capture_browser_trace import j01_checks, journey_result
raw = Path("tests/browser/rust-journeys/j01-sequence/trace-data-loop.json")
observation = json.loads(raw.read_bytes())["observation"]
observation["ipc_dir"] = str(raw.parent.resolve())
result = journey_result(j01_checks(observation=observation))
print(result)
assert result["ok"] and result["counts"]["asserted"] == 15
```

Run with `target/pyref-venv/Scripts/python.exe` and
`PYTHONPATH=tests/reference`; use the corresponding reference raw path to replay
Python. The docs cache label is 1.66.0; the measured Python runtime is 1.66.1.

The data app of the Rust implementation, driven with the official Streamlit
1.66.1 frontend: the closed loop and the three journeys of the data app.

**Server under test**

- binary `target/checks/data-app-live/data-app-csv-stage2-20261024T172854620.exe`
- sha256 `9430149DE61EA521AE873D2AE77A97A62D9BE5F63F547F00E9D5F7A1D23F4A57`
- source sha256 `810f4c1ecffa419a5f9217c311d4e863faef71e6e3779eb69fba2c6516d0f2f7`
- config sha256 `a552d879a67c536617e42933128e85329f30aafadd83cb34fd763f55ba2f26fc`
- the four raws of this round were captured against this binary; the four rows
  above carry the earlier one (`427F3AF7...`)
- `HEAD 1c6161d` plus the owner's uncommitted increment

**The captures**

| raw | journey | expected | executed | asserted | failures | exit |
|---|---|---|---|---|---|---|
| [data-loop/](data-loop/trace-data-loop.json) | upload, group by region, unknown off, minimum 100 | 3 | 3 | 3 | none | 0 |
| [recover/](recover/trace-data-loop.json) | a file that cannot be read, then a good one | 12 | 12 | 12 | none | 0 |
| [empty/](empty/trace-data-loop.json) | a file without data rows | 7 | 7 | 7 | none | 0 |
| [sessions/](sessions/trace-data-loop.json) | two tabs, two sessions | 11 | 11 | 11 | none | 0 |
| [state/](state/trace-data-loop.json) | first load, one control, one upload, the Pulse click | 14 | 14 | 14 | none | 0 |
| [soft-invalid/](soft-invalid/trace-data-loop.json) | the file with two unusable amounts, then the good file | 13 | 13 | 2 | the criterion of the case is not written | 1 |
| [non-utf8/](non-utf8/trace-data-loop.json) | the file that is not UTF-8, then the good file | 13 | 13 | 3 | the criterion of the case is not written | 1 |
| [filter-empty/](filter-empty/trace-data-loop.json) | the slider that empties the table, and back | 13 | 13 | 3 | the criterion of the case is not written | 1 |
| [j07-sequence/](j07-sequence/trace-data-loop.json) | the whole parse journey in one session | 13 | 13 | 13 | none | 0 |
| [j08-sequence/](j08-sequence/trace-data-loop.json) | the whole empty journey in one session | 14 | 14 | 14 | none | 0 |

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
$binNew = "target/checks/data-app-live/data-app-csv-stage2-20261024T172854620.exe sha256 9430149DE61EA521AE873D2AE77A97A62D9BE5F63F547F00E9D5F7A1D23F4A57"
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
target\pyref-venv\Scripts\python.exe tests\browser\numeric_capture.py --url http://127.0.0.1:8501/ \
    --case data-loop --journey state --files "$fx\sales_basic.csv" \
    --label rust-state --out target\rust-state --binary $binNew --scope "RUST SIDE ONLY"
target\pyref-venv\Scripts\python.exe tests\browser\numeric_capture.py --url http://127.0.0.1:8501/ \
    --case data-loop --journey soft-invalid --files "$fx\sales_with_missing.csv,$fx\sales_basic.csv" \
    --label rust-soft-invalid --out target\rust-soft-invalid --binary $binNew --scope "RUST SIDE ONLY"
target\pyref-venv\Scripts\python.exe tests\browser\numeric_capture.py --url http://127.0.0.1:8501/ \
    --case data-loop --journey non-utf8 --files "$fx\sales_latin1.csv,$fx\sales_basic.csv" \
    --label rust-non-utf8 --out target\rust-non-utf8 --binary $binNew --scope "RUST SIDE ONLY"
target\pyref-venv\Scripts\python.exe tests\browser\numeric_capture.py --url http://127.0.0.1:8501/ \
    --case data-loop --journey filter-empty --files "$fx\sales_basic.csv" \
    --label rust-filter-empty --out target\rust-filter-empty --binary $binNew --scope "RUST SIDE ONLY"
~~~
target\pyref-venv\Scripts\python.exe tests\browser\numeric_capture.py --url http://127.0.0.1:8501/ \
    --case data-loop --journey j07-sequence --out target\rust-j07-sequence \
    --label rust-j07-sequence --binary $binNew --scope "RUST SIDE ONLY" --build-base ef359b1
target\pyref-venv\Scripts\python.exe tests\browser\numeric_capture.py --url http://127.0.0.1:8501/ \
    --case data-loop --journey j08-sequence --out target\rust-j08-sequence \
    --label rust-j08-sequence --binary $binNew --scope "RUST SIDE ONLY" --build-base ef359b1
~~~

The driver is `tests/browser/numeric_capture.py` (sha256
`AF2519D40235883E3A09F8EAE5D6AA52A0E3969695EE482B41C66580080662A4` for the two whole journeys,
`4194835B77379A2E63D783D292183B70061DBD8D221575EFE8C50D0A5BF462AD` for the four raws of this round,
`9EDC3FA1D456E5592771C448AC5E600C99D71398C5E55CCB7E8A541F61E5F966` when the four rows above were captured; the driver now names the journeys in one
constant (`A8F93500D544780F9358AE9D6F015424C882BA1249FE4CDE141A32426E31D5D0`), which changed no byte of a capture); the
criteria live in `tests/reference/capture_browser_trace.py` (sha256
`FF39DD51F8439ABED32205C50395D0E4CAFA7194BCF37A0338F62DD6E0139C00` for the two whole journeys,
`1D1A5C8415C8D212948045EF75B971E9AC278E4C925D3110CD75AA70C3AB422F` for the four raws of this round,
`B29B4F85AC9BEBE885C4B3EEE8E2142D8A44DC4724C6A9F1075BB09062DA08F6`, re-validated against `DA2E746A8267E1DFAC65CF0CB5513B3C6B729B33C5035C3CF5C253F016925D9A`, for the four rows above).
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

**The four raws of this round**

They were recorded on 2026-10-24 against the binary above, with the upload
window bound the way the shared reader binds it: the window of an upload is
the request of the URLs of the newly issued file, the state that names that
file, the server run that answered it and that run's successful completion.
The Rust app answers a replacement in two runs -- first the run that clears
the uploader, then the run of the new file -- and the window holds both, with
the completion of the run of the new file at its end.  The earlier rule, which
stopped at the first successful completion, ended the window at the clearing
run and left the result outside it.

`state/` is a pass: the shared criterion judges the counters of the window,
the distinct script run ids and the three pictures, and it holds.  The other
three are measured but not judged -- the criterion of those cases is not
written yet, so the entry exits 1 and the journeys of
`tests/journeys/journeys.json` stay `failed` for exactly those parts.

**The two whole journeys**

`j07-sequence/` and `j08-sequence/` are one capture each: the whole journey is
driven in one tab and one session, never a page per case.  The parse journey
reads the malformed file, the file with two unusable amounts, a good file, the
file that is not UTF-8 and a good file again -- the counters read 2, 4, 6, 8,
10 and the session id is the same in every step.  The empty journey reads the
file without rows, a good file, the filter that leaves no row and the filter
back -- the counters read 2, 4, 5, 6, so the filter is one run and the way
back is one run, without a reload and without a new session.

Every step is bound to the run that answered it: the window of an upload is
the request of the URLs of the newly issued file, the state that names that
file, the server run that answered it and that run's successful completion.
The Rust app answers a replacement in two runs -- first the run that clears
the uploader, then the run of the new file -- and the window holds both, with
the completion of the run of the new file at its end.

The shared criterion of the whole journey is `sequence_checks` in
`tests/reference/capture_browser_trace.py`; the phase names, the inputs and
the picture roles are its own, and the driver reads them from there.

**What these captures do not cover**

The parse-error wording of the Rust app differs from the reference text
(`Could not parse the uploaded CSV: CSV error: record 2 ...` against
`Could not parse the uploaded CSV: row 3: expected 8 fields, found 7`); that
case and the recovery of it (J07-S1 and J07-S3) were not run in this round.
