# Rust zero-column browser evidence (accepted A: virtual RangeIndex)

This is the Rust counterpart of the frozen [Python 1.66.1 zero-columns
reference](../../reference/reference-browser/zero-columns/README.md), captured
with the same four-stage flow (**Two rows** `zero-two`, **Ordinary rerun**
`zero-rerun`): zero-initial → two-rows → ordinary-rerun → zero-again over one
page with a dataframe, an enabled and a disabled fixed editor, and a
`table(hide_index=False)`, all fed zero-column Arrow batches with explicit 0/2
rows.

The captured command sequence was:

```powershell
cargo test -p streamlit --lib --locked zero_column
cargo clippy --workspace --locked --all-targets -- -D warnings
cargo fmt --all -- --check
cargo test --workspace --locked
cargo build -p streamlit --example zero_columns --locked
./target/debug/examples/zero_columns.exe          # 127.0.0.1:8580, caller owned
./target/pyref-venv/Scripts/python.exe tests/browser/zero_columns_capture.py --url http://127.0.0.1:8580/ --out target/checks/zero-columns-rust/ui
```

`trace.json` records 76 protobuf frames, the four stage DOM snapshots, console
errors, and the collector cleanup audit; [manifest.json](manifest.json) pins
per-file bytes and SHA256. The caller-owned Rust server process is not part of
the archive; the collector profile lived under ignored `target/`.

## Observed result and the deliberate divergence

With two rows, all three grids — including the plain dataframe — render the
virtual RangeIndex cells `0`/`1`, and the table renders its index rows `0`/`1`;
an ordinary rerun keeps them and unchecking returns every view to empty. No
`stException` and no console errors occurred.

This is the accepted option A divergence from the pinned Python reference,
where the same direct-Arrow dataframe shows two `Error during cell creation`
cells and the table renders an empty frame (wire without an index
descriptor). The Rust display conversion keeps the explicit row count and
synthesizes the pandas RangeIndex descriptor, so the official frontend can
create the cells; see the architecture decision record and
`test_zero_columns_reference.py` for the side-by-side assertions. The frozen
Python error evidence is retained unchanged.

## Boundaries

One successful run on one machine with the owned headless Chrome; the Python
protocol references (9+3 cases) were not re-captured and remain the wire
authority for the calls themselves. Dynamic-row editing, arbitrary
schema/metadata combinations, non-empty-column behavior differences, and
keyboard/accessibility rendering are not covered here; the WS-level regression
`zero_column_views_render_virtual_range_index_over_the_same_flow` pins the
wire shape (row count, zero columns, range descriptor) for every stage.
