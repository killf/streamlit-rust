"""Regenerate the C-P0-04 acceptance fixtures.

Run from the repository root:

    python tests/fixtures/generate.py

The generator is deterministic: every fixture is written as UTF-8 (UTF-8 with BOM
where noted) using LF newlines, with no trailing whitespace and no trailing
blank line beyond the final newline.  ``manifest.json`` records the byte length
and SHA-256 of every fixture so that a Rust implementation can assert it loaded
the exact same bytes the reference oracle saw.

The dataset is intentionally small: 12 rows is the minimum that still exercises
every dimension the P0 journeys depend on.

    * 4 categories x 3 rows  -> group-by=category yields 4 non-empty groups
    * 6 regions x 1..3 rows  -> group-by=region yields 6 groups, including the
                                two "unknown region" shapes (blank, UNKNOWN)
    * 2 channels x 6 rows    -> group-by=channel yields 2 groups
    * amounts span 15.50..199.99 so the 0..200 slider actually partitions rows
    * four of the amount sums/averages land exactly on a x.xx5 boundary, so a
      naive binary-float rounding implementation diverges from the reference

See tests/reference/refcore.py for the aggregation contract these fixtures feed.
"""

from __future__ import annotations

import hashlib
import json
import pathlib

FIXTURES_DIR = pathlib.Path(__file__).resolve().parent
CSV_DIR = FIXTURES_DIR / "csv"

HEADER = "order_id,date,category,region,channel,product,amount,quantity"

# (order_id, date, category, region, channel, product, amount, quantity)
# `region` is deliberately empty on S-009 and literally "UNKNOWN" on S-010/S-011.
BASIC_ROWS: tuple[tuple[str, ...], ...] = (
    ("S-001", "2026-01-05", "Books", "North", "Online", "Atlas Guide", "120.50", "2"),
    ("S-002", "2026-01-06", "Books", "North", "Retail", "Bridge Manual", "80.00", "1"),
    ("S-003", "2026-01-07", "Books", "South", "Online", "Atlas Guide", "45.25", "1"),
    ("S-004", "2026-01-08", "Games", "South", "Retail", "Pixel Quest", "199.99", "1"),
    ("S-005", "2026-01-09", "Games", "East", "Online", "Circuit Breaker", "59.99", "3"),
    ("S-006", "2026-01-10", "Games", "East", "Retail", "Pixel Quest", "149.50", "1"),
    ("S-007", "2026-01-12", "Music", "West", "Online", "Vinyl Set", "32.75", "2"),
    ("S-008", "2026-01-13", "Music", "West", "Retail", "Cassette Pack", "18.25", "1"),
    ("S-009", "2026-01-14", "Music", "", "Online", "Vinyl Set", "88.00", "1"),
    ("S-010", "2026-01-15", "Toys", "UNKNOWN", "Retail", "Wooden Blocks", "24.99", "4"),
    ("S-011", "2026-01-16", "Toys", "UNKNOWN", "Online", "Puzzle Cube", "15.50", "2"),
    ("S-012", "2026-01-17", "Toys", "North", "Retail", "Wooden Blocks", "64.00", "2"),
)

UNICODE_ROWS: tuple[tuple[str, ...], ...] = (
    ("S-101", "2026-01-05", "Bücher", "Nörd", "Online", "Atlas Handbuch", "120.50", "2"),
    ("S-102", "2026-01-06", "游戏", "南方", "Retail", "像素任务", "199.99", "1"),
    ("S-103", "2026-01-07", "Jogos", "Oeste", "Online", "Pixel Quest", "149.50", "1"),
)

# Rows whose `amount` cell is unusable.  S-003 is blank, S-009 is not a number.
# Both must be excluded from the aggregation while the rest of the file stays
# usable -- this is the "soft" failure class, distinct from the ragged-row
# "hard" failure class in sales_malformed.csv.
MISSING_AMOUNT_ROWS = ("S-003", "S-009")


def _rows_to_csv(rows: tuple[tuple[str, ...], ...]) -> str:
    return HEADER + "\n" + "".join(",".join(r) + "\n" for r in rows)


def _with_invalid_amounts(rows: tuple[tuple[str, ...], ...]) -> str:
    out = []
    for row in rows:
        if row[0] == "S-003":
            row = row[:6] + ("",) + row[7:]
        elif row[0] == "S-009":
            row = row[:6] + ("not-a-number",) + row[7:]
        out.append(",".join(row))
    return HEADER + "\n" + "".join(r + "\n" for r in out)


# Ragged rows: a short row, a long row and an extra column.  Each of these is a
# hard, structural parse failure (not a per-cell soft failure).
MALFORMED_CSV = (
    HEADER
    + "\n"
    + "S-001,2026-01-05,Books,North,Online,Atlas Guide,120.50,2\n"
    + "S-002,2026-01-06,Books,North,Retail,Bridge Manual,80.00\n"
    + "S-003,2026-01-07,Books,South,Online,Atlas Guide,Extra,45.25,1\n"
    + "S-004,2026-01-08,Games,South,Retail,Pixel Quest,199.99,1,trailing\n"
)

DESCRIPTIONS = {
    "sales_basic.csv": "Baseline dataset: 12 rows, 4 categories, 6 regions (one blank, two UNKNOWN), 2 channels.",
    "sales_with_missing.csv": "Baseline with 2 unusable amount cells (S-003 blank, S-009 not-a-number); 10 rows remain aggregatable.",
    "sales_empty.csv": "Header only, zero data rows.",
    "sales_malformed.csv": "Ragged rows (short, long, extra column): hard structural parse failure.",
    "sales_unicode.csv": "3 rows with non-ASCII UTF-8 values in category/region/product.",
    "sales_utf8_bom.csv": "Byte-identical content to sales_unicode.csv but prefixed with a UTF-8 BOM.",
}


def main() -> None:
    CSV_DIR.mkdir(parents=True, exist_ok=True)

    basic = _rows_to_csv(BASIC_ROWS)
    unicode_csv = _rows_to_csv(UNICODE_ROWS)

    files: list[tuple[str, bytes, str]] = [
        ("sales_basic.csv", basic.encode("utf-8"), "utf-8"),
        ("sales_with_missing.csv", _with_invalid_amounts(BASIC_ROWS).encode("utf-8"), "utf-8"),
        ("sales_empty.csv", (HEADER + "\n").encode("utf-8"), "utf-8"),
        ("sales_malformed.csv", MALFORMED_CSV.encode("utf-8"), "utf-8"),
        ("sales_unicode.csv", unicode_csv.encode("utf-8"), "utf-8"),
        ("sales_utf8_bom.csv", unicode_csv.encode("utf-8-sig"), "utf-8-sig"),
    ]

    entries = []
    for name, payload, encoding in files:
        path = CSV_DIR / name
        path.write_bytes(payload)
        entries.append(
            {
                "file": "csv/" + name,
                "bytes": len(payload),
                "sha256": hashlib.sha256(payload).hexdigest(),
                "encoding": encoding,
                "newline": "lf",
                "description": DESCRIPTIONS[name],
            }
        )

    manifest = {
        "schema_version": 1,
        "contract_id": "C-P0-04",
        "target": "streamlit-rust P0 acceptance fixtures",
        "reference_version": "1.66.1",
        "generator": "tests/fixtures/generate.py",
        "notes": (
            "Byte-stable fixtures: LF newlines, UTF-8 unless the encoding field says "
            "utf-8-sig, no trailing whitespace. The sha256 field pins the content so a "
            "Rust implementation can assert it loaded exactly the bytes the Python "
            "reference oracle saw."
        ),
        "fixtures": entries,
    }
    (FIXTURES_DIR / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )

    for entry in entries:
        print(f"{entry['file']:<28} {entry['bytes']:>5} B  sha256:{entry['sha256'][:16]}")


if __name__ == "__main__":
    main()
