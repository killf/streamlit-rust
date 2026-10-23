# C-P0-04 fixtures

Deterministic CSV inputs for the P0 acceptance journeys.

| file | rows | purpose |
|---|---|---|
| `csv/sales_basic.csv` | 12 | The baseline. Valid rows only. |
| `csv/sales_with_missing.csv` | 12 | Two unusable `amount` cells (S-003 blank, S-009 `not-a-number`). The "soft" failure class. |
| `csv/sales_empty.csv` | 0 | Header only. The "empty file" state. |
| `csv/sales_malformed.csv` | 4 | Ragged rows: one short, one long, one extra column. The "hard" failure class. |
| `csv/sales_unicode.csv` | 3 | Non-ASCII UTF-8 values in `category`, `region` and `product`. |
| `csv/sales_utf8_bom.csv` | 3 | Byte-identical content to `sales_unicode.csv`, prefixed with a UTF-8 BOM. |

`manifest.json` records the byte length, the SHA-256 and the encoding of every
fixture. The digests are the contract: a Rust implementation can assert it
loaded exactly the bytes the Python reference oracle saw. The journey
validator re-checks them on every run (rule R7).

## Regenerating

```
python tests/fixtures/generate.py
```

The generator is the single source of truth for the fixture bytes. It writes
UTF-8 with LF newlines and no trailing whitespace; only
`sales_utf8_bom.csv` carries a BOM. Re-running it must not change any digest.

## Why the dataset is this small

Twelve rows is the minimum that still exercises every dimension the journeys
depend on:

* 4 categories x 3 rows, so grouping by `category` yields four non-empty groups.
* 6 distinct regions (`North`, `South`, `East`, `West`, blank, `UNKNOWN`),
  so the `include_unknown` filter has something to remove and the empty group
  key has something to normalise.
* 2 channels x 6 rows.
* Amounts spanning 15.50..199.99, so the 0..200 slider actually partitions
  rows instead of leaving most of the range inert.
* Four of the group averages land exactly on a `x.xx5` rounding boundary
  (104.745, 20.245, 89.455, 174.745), so a binary-float implementation
  diverges from the decimal reference and the difference is caught.

## Schema

```
order_id,date,category,region,channel,product,amount,quantity
```

`amount` is the only aggregated column. `region` additionally drives the
`include_unknown` filter. `quantity` and `product` are carried but never
aggregated -- they exist to prove the parser handles a realistic sales CSV
rather than only the columns it happens to use.

See `../reference/refcore.py` for the full parsing and aggregation contract.
