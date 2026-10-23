# C-P0-04 reference application

**Development only.** This directory is a behavioural oracle for the Rust
implementation. It is not shipped, it is not part of any production path, and
the Rust server must never start it. Its only job is to turn "what should
happen" into a set of values that were produced by a known-good Streamlit
1.66.1 run rather than by the build under test.

| file | role |
|---|---|
| `refcore.py` | The oracle. Parsing and aggregation, standard library only (`csv` + `decimal`). No Streamlit, no pandas, no altair. |
| `app.py` | The Streamlit 1.66.1 application. Wires `refcore` into widgets and renders the result. |
| `generate_golden.py` | Regenerates `golden/expected_aggregations.json` from the committed fixtures. |
| `test_refcore.py` | pytest suite pinning `refcore` against the golden file and against the semantics a Rust implementation is most likely to get wrong. |
| `run_reference.py` | Drives the app through every P0 scenario with `streamlit.testing.v1.AppTest` and writes the `ref` evidence. |
| `golden/expected_aggregations.json` | The machine-readable expected values -- the **application contract snapshot** of this reference app. |
| `requirements.txt` | The pinned reference environment. |

The golden file is the **application contract snapshot**, not an independently
authored oracle: it is regenerated from the committed fixtures by `refcore.py`,
so `test_refcore.py` checking `refcore.py` against it is not by itself an
independent proof. The independent check is the second path --
`run_reference.py` drives the real Streamlit 1.66.1 application and asserts
expected values written out as literals there, separate from the golden file.

## Running it

```
python -m venv .venv-ref
.venv-ref\Scripts\pip install -r tests/reference/requirements.txt

.venv-ref\Scripts\python -m pytest tests/reference -q
.venv-ref\Scripts\python tests\reference\generate_golden.py
.venv-ref\Scripts\python tests\reference\run_reference.py --out target/checks/reference-run/reference-run.json
```

`run_reference.py` is a verification run, not just a dumper: every scenario
carries explicit expectations and the process exits non-zero if any of them is
not met. A green run is the evidence that the expectations recorded in
`../journeys/journeys.json` are the ones Streamlit 1.66.1 actually produces.

To serve the app for manual inspection:

```
.venv-ref\Scripts\streamlit run tests\reference\app.py --server.headless true
```

## Why the core avoids pandas

`refcore.py` uses only the Python standard library. That is deliberate:

* The expected values must not drift when pandas or altair is upgraded. They
  are regenerated from the committed fixtures, so a dependency bump cannot
  silently change the oracle.
* Decimal arithmetic makes the contract unambiguous. The fixtures contain
  averages that land exactly on a `x.xx5` boundary, where Python's default
  banker's rounding, binary-float rounding and half-up rounding disagree. The
  contract says half-up, and the golden file records the exact decimal string
  *and* the IEEE-754 double that travels on the wire.
* The Rust implementation will parse CSV with its own parser, so the oracle
  should not be a pandas behaviour in disguise.

pandas and altair are used only to render the table and the chart, exactly as
the Rust implementation will use Arrow to do so.

## The aggregation contract

The normative statement is the module docstring of `refcore.py`. In short:
hard failures (structural) and soft failures (per-cell) are distinct;
amounts must match `^[+-]?(\d+(\.\d*)?|\.\d+)$`; totals and averages are
rounded HALF_UP to two places; `include_unknown` always filters the `region`
column; group keys are sorted by Unicode code point and an empty key becomes
`(missing)`.

## Widget contract

`app.py` documents the canonical widget order at the top of the file. The Rust
implementation should mirror it -- labels, widget keys and order -- because
the browser journeys locate widgets by those identifiers. The table is
rendered with the column order `group_key`, `row_count`, `total_amount`,
`avg_amount` and the index hidden.
