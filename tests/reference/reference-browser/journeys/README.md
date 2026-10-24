# Reference journeys of the data app

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

**Where the evidence came from**

The capture ran once, in `target\final-427F-20261024T162828`, and the files here are those bytes.
The raw keeps the capture-time `ipc_dir` of that directory; the IPC payloads
are the `arrow-N.bin` files **beside each raw** (the reference IPC is 1640
bytes and carries the pandas metadata block), so a replay resolves them next
to the raw instead of in the ignored `target/` tree.

Regenerate with the same commands as the Rust raws, with
`--url http://127.0.0.1:8601/` and without `--binary`; the scope of these
raws is "PYTHON SIDE ONLY".
