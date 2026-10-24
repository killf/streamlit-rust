# Reference journeys of the data app

## J09: bounded reconnect and refresh, S4 unmeasured

[Original Python raw](j09-sequence/trace-data-loop.json), SHA256
`b4d244ce30b918dcc5ff2f9a775863858faf9d6dced6c5df8afc0bc1e6b34b3d`,
retains 161 frames, all eight PNGs, two deduplicated IPCs and its loaded source
files. Actual NewSession reports Streamlit 1.66.1/reference app. The original
capture used producer b79814, not the later native producer15b606; both used
criteria46537. The exact hashes and original bytes remain in raw/capture-source.

Historical capture completed with 20/20/20, no failures, exit0. Its invocation
is [execution-manifest](j09-sequence/execution-manifest.json)'s `executable`,
then `tests/browser/numeric_capture.py`, then its exact `argv`. That actual
browser command is distinct from the following formal-archive replay, which
was executed with 20/20/20, no failures, exit0:

```powershell
target/pyref-venv/Scripts/python.exe tests/browser/numeric_capture.py --replay tests/reference/reference-browser/journeys/j09-sequence/trace-data-loop.json
```

The [native J09 section](../../../browser/rust-journeys/README.md#j09-bounded-reconnect-and-refresh-s4-unmeasured)
records the measured S1-S3 roles, observe-plus-probe evidence, preparation
actions, current replay identities and one shared recoverable candidate.
This actual ui-probe plan observed no natural run for 5.133 seconds after
HTTP101, then used real region/category selections to demonstrate recovery.
It does not claim that an automatic run can never occur. Optional S4's
greater-than-120-second disconnected expiry remains unmeasured, with no PNG
or passed result. Original 17 targets were retained; only the own tab closed.

## J06: continuous two-tab isolation

[Original raw](j06-sequence/trace-data-loop.json), SHA256
`2da6690d97ab151356cad0cc0cc74dc1aa87452caa6dc7005a8eae44a2edbc2e`,
retains 208 frames (A138/B70), all 18 PNGs, two deduplicated IPCs and both
loaded source files. Both actual NewSession messages report Streamlit 1.66.1
and the reference app. A has epochs a0/a1; B keeps b0. The original 17 targets
were retained and only the two capture-owned tabs were closed.

The historical browser capture completed with 18/18/18, no failures, exit 0.
Its exact invocation is the executable from the
[execution manifest](j06-sequence/execution-manifest.json), followed by
`tests/browser/numeric_capture.py` and that manifest's `argv`. The historical
output directory is retained as metadata; do not rerun into it. This is
separate from the following read-only command, actually executed on the
formal archive with 18/18/18, no failures, exit 0:

```powershell
target/pyref-venv/Scripts/python.exe tests/browser/numeric_capture.py --replay tests/reference/reference-browser/journeys/j06-sequence/trace-data-loop.json
```

The [Rust J06 section](../../../browser/rust-journeys/README.md#j06-continuous-two-tab-isolation)
records the five original step roles, all preparation/intermediate phases,
unchanged producer/criteria hashes and shared candidate source recovery.
Each phase has two separate tab images; these are not stitched or represented
as one simultaneous screenshot. All nine phases remain in the raw.

## J00 and J02: original captures, separate final replay

[J00](j00-sequence/trace-data-loop.json) retains 185 frames, eight PNGs and
four IPCs; SHA256
`f1b1470686fa91dd0ea5d715287a8e47e5d88e01bb22f521bb6ee91e619dcc27`.
[J02](j02-sequence/trace-data-loop.json) retains 139 frames, six PNGs and
five IPCs; SHA256
`dd6eb79fc7194c4a32e8d8b85727abc78997756b38654283b1dfecd7dbeba65f`.
Both measured the actual `tests/reference/app.py` on Python Streamlit 1.66.1
at loopback8601 with the official frontend; both keep their actual
**NOT VERIFIED, 1/1/0, capture exit 1**. Their source snapshots are original
bytes: J00 84/08/0b, J02 e0db/3b, with exact hashes in adjacent
`capture-source/SHA256SUMS`. No cached status was changed to imply capture-time
acceptance.

After independent Hooke candidate review, these exact repository commands
were run on the archived evidence, returning exit 0 with final results
**J00 19/19/19 and J02 15/15/15**, no failures:

```powershell
target\pyref-venv\Scripts\python.exe tests/browser/numeric_capture.py --replay tests/reference/reference-browser/journeys/j00-sequence/trace-data-loop.json
target\pyref-venv\Scripts\python.exe tests/browser/numeric_capture.py --replay tests/reference/reference-browser/journeys/j02-sequence/trace-data-loop.json
```

The [Rust publication](../../../browser/rust-journeys/README.md#j00-and-j02-integrated-formal-example)
records the exact final 1990 criteria/replay producer SHA, step/prep/shared-PNG
mapping, capture-versus-verification history and one self-contained 130-input
7297/42e54 candidate. Its per-journey `verification.json` files provide the
integration owner's step updates; they do not change the 10 journeys or 42
original steps. The docs cache remains labelled 1.66.0, distinct from the
measured 1.66.1 runtime.

## J03: continuous table/chart oracle

[j03-sequence/trace-data-loop.json](j03-sequence/trace-data-loop.json) is the
original Python 1.66.1 same-page six-phase capture at
`http://127.0.0.1:8601/`, SHA256
`5798c11f1eba559988d98da1978cd79de8fee1e6cbd4bdc0cc15132bbfbf8ec5`.
All 139 frames, four adjacent IPC payloads and six PNGs retain their bytes.
The raw retains **NOT VERIFIED, 1/1/0, capture exit 1**. The observed 842B stub
source snapshot was not retained; no capture-time version was backfilled.
Hooke's final independent review and replay verify 15/15/15 with no failures.
The exact final criteria SHA, four-step/preparation mapping, portable replay
and the Rust 8505 candidate's self-contained build inputs are documented in
[the Rust J03 section](../../../browser/rust-journeys/README.md#j03-table-and-chart-synchronization).
The 1.66.0 docs-cache label remains distinct from the measured 1.66.1 runtime.

## J01: unchanged Python oracle, final independent replay

[j01-sequence/trace-data-loop.json](j01-sequence/trace-data-loop.json) preserves
the 209-frame same-page Python 1.66.1 capture from
`target/j01-preflight-20261025T001649` at `http://127.0.0.1:8601/`, using
`tests/reference/app.py` and the pinned `target/pyref-venv/Scripts/python.exe`.
Its SHA256 is
`1cb74c36db6e25cdee19054c59a6fd9473571107c54148bbbb4e2497aab31478`.
All four adjacent IPC files and seven PNGs are the original bytes.

The raw deliberately retains **NOT VERIFIED, 1/1/0, capture exit 1** from the
unfinished predicate. Capture-time criteria SHA was not recorded. It is not
rewritten to claim capture-time success. Hooke's final independent review and
replay give 15/15/15 with no failures; the exact final criteria SHA, portable
replay instructions and five-step/preparation mapping are in the
[Rust J01 evidence description](../../../browser/rust-journeys/README.md#j01-continuous-input-and-aggregation).
That final replay also validates the Rust chain, rather than treating a
reference result as Rust proof. The docs cache label 1.66.0 is distinct from
the measured runtime 1.66.1. Both raws retain their capture metadata unchanged.

The same three journeys as `tests/browser/rust-journeys/`, recorded against
the Python reference application (streamlit 1.66.1, `tests/reference/app.py`)
with the official frontend.

| raw | journey | expected | executed | asserted | failures | exit |
|---|---|---|---|---|---|---|
| [recover/](recover/trace-data-loop.json) | a file that cannot be read, then a good one | 12 | 12 | 12 | none | 0 |
| [empty/](empty/trace-data-loop.json) | a file without data rows | 7 | 7 | 7 | none | 0 |
| [sessions/](sessions/trace-data-loop.json) | two tabs, two sessions | 11 | 11 | 11 | none | 0 |

The reference app answers the parse error with `Could not parse the uploaded
CSV: row 3: expected 8 fields, found 7`, the replacement answers a DELETE
204 for the file the server signed out, the empty file keeps its four columns
with no body row and no bar, and the two tabs keep their own session, file,
group and result -- the same values the Rust raws carry.

**The reference app answers the upload in three runs** (the good-file state at
44 arrives while the previous run is still streaming, the table of the good
file comes at 60/61 and the run ends at 70), where the Rust app answers it in
one.  The criterion binds the result to the run that carries the target state
and the result, by the script run id the server names in NewSession, so both
orders are judged the same way.

**The two whole journeys**

`j07-sequence/` and `j08-sequence/` are one capture each: the whole journey in
one tab and one session, never a page per case.  The parse journey reads the
malformed file, the file with two unusable amounts, a good file, the file that
is not UTF-8 and a good file again; the empty journey reads the file without
rows, a good file, the filter that leaves no row and the filter back.  The
counters are the same on both sides (2, 4, 6, 8, 10 and 2, 4, 5, 6), and the
filter is one run and the way back is one run, without a reload.

| raw | journey | expected | executed | asserted | failures | exit |
|---|---|---|---|---|---|---|
| [j07-sequence/](j07-sequence/trace-data-loop.json) | the whole parse journey in one session | 13 | 13 | 13 | none | 0 |
| [j08-sequence/](j08-sequence/trace-data-loop.json) | the whole empty journey in one session | 14 | 14 | 14 | none | 0 |

The criterion is `sequence_checks` in `tests/reference/capture_browser_trace.py`;
the phase names, the inputs and the picture roles are its own.

**The cases the shared criterion does not judge yet**

Four cases the shared criterion does not judge yet.  Each was recorded by the
permanent entry (`tests/browser/numeric_capture.py --case data-loop --journey
<case>`), in its own tab, with the screenshot of the state the page showed and
the counters the page read.  The raws carry the evidence and an explicit
failure -- the criterion for them is not written yet, so they are not a pass.

The four raws below were recorded again on 2026-10-24 with the upload window
bound the way the shared reader binds it: the window of an upload is the
request of the URLs of the newly issued file, the state that names that file,
the server run that answered it and that run's successful completion.  The
run that clears the uploader is inside the window and never its end, so the
run that carries the result is never left out.  The raws that the earlier
recording left behind are kept in `target/superseded-journeys-20261024T183803`
with their hashes.

| case | what the page showed | screenshot | checks |
|---|---|---|---|
| [soft-amount/](soft-amount/trace-data-loop.json) | the warning "2 row(s) with an unusable 'amount' were excluded from the aggregation." and the four groups of the ten remaining rows (Books 2/200.50/100.25, Games 3/409.48/136.49, Music 2/51.00/25.50, Toys 3/104.49/34.83) with four bars; the runs counter goes 1 -> 2 | 01-soft-warning.png | 13 expected, 2 asserted, exit 1 |
| [not-utf8/](not-utf8/trace-data-loop.json) | the error "Could not parse the uploaded CSV: the uploaded file is not valid UTF-8: 'utf-8' codec can't decode byte 0xe9 in position 101: invalid continuation byte" with "Upload a valid CSV to continue.", no table and no chart | 01-not-utf8-error.png | 13 expected, 3 asserted, exit 1 |
| [filtered-empty/](filtered-empty/trace-data-loop.json) | the baseline (runs 1 -> 2), then the slider at 200 in one change (runs 2 -> 3): "No rows match the current filters.", the table with its four columns and no body row, no chart -- and the slider back at 0 (runs 3 -> 4) brings the four baseline groups with four bars again | 01-no-rows-match.png, 02-recovered.png | 13 expected, 3 asserted, exit 1 |
| [session-state/](session-state/trace-data-loop.json) | the first load reads "Script runs: 1" and "Pulses: 0"; the selector change makes it 2 and leaves the pulses at 0; the upload makes it 3; the Pulse click makes it "Script runs: 4" and "Pulses: 1" while the table stays the same.  The click is a real mouse event on the visible button and its window carries the trigger the client sent | 01-initial.png, 02-after-upload.png, 03-after-selector.png, 04-after-pulse.png | 14 expected, 14 asserted, exit 0 |

The screenshots are the real page in a 1264x1800 viewport, taken after the
result has drawn; the raw records the size of each of them.

**The empty result types its first column differently on each side**: the
reference sends `group_key: double` with zero rows, the Rust build sends
`group_key: large_string`.  A criterion that compares the types of an empty
result has to allow that difference, or compare the column names and the
row count only.

The byte position in the UTF-8 message belongs to the fixture
`tests/fixtures/csv/sales_latin1.csv` (sha256
`f73e63eb66c2dccd9285b573094b59c59e5dacd3ece0ef26d48ca3728371d541`).
**Where the evidence came from**

The capture ran once, in `target\final-427F-20261024T162828`, and the files here are those bytes.
The raw keeps the capture-time `ipc_dir` of that directory; the IPC payloads
are the `arrow-N.bin` files **beside each raw** (the reference IPC is 1640
bytes and carries the pandas metadata block), so a replay resolves them next
to the raw instead of in the ignored `target/` tree.

Regenerate with the same commands as the Rust raws, with
`--url http://127.0.0.1:8601/` and without `--binary`; the scope of these
raws is "PYTHON SIDE ONLY".

The driver of this round is `tests/browser/numeric_capture.py` (sha256
`4194835B77379A2E63D783D292183B70061DBD8D221575EFE8C50D0A5BF462AD`) and the
shared reader it waits for is `tests/reference/capture_browser_trace.py`
(sha256 `1D1A5C8415C8D212948045EF75B971E9AC278E4C925D3110CD75AA70C3AB422F`).
The raws of this round are the bytes of `target/stage2-ref-20261024T182810`.
