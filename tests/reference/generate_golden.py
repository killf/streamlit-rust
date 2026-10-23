"""Regenerate tests/reference/golden/expected_aggregations.json.

    python tests/reference/generate_golden.py

The golden file is the machine-readable statement of what the reference
Streamlit 1.66.1 application produces for each fixture and control combination.
Both the Python reference test suite and the Rust implementation assert against
it, so the two sides cannot drift apart silently.

Every numeric expectation is stored twice:

* as an exact decimal string, e.g. ``"245.75"`` -- the normative value, rounded
  half-up to two decimal places;
* as the IEEE-754 double nearest to that decimal, as ``float.hex()`` -- the
  value actually carried on the wire, so a Rust implementation can assert
  bit-equality rather than merely approximate equality.

No expected value in this file was typed by hand: every entry is produced by
``refcore.py`` running over the committed fixtures.
"""

from __future__ import annotations

import hashlib
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from refcore import (  # noqa: E402
    AGGREGATION_CONTRACT_VERSION,
    CsvFormatError,
    aggregate,
    parse_csv,
)

FIXTURES_DIR = HERE.parent / "fixtures"
CSV_DIR = FIXTURES_DIR / "csv"
GOLDEN_PATH = HERE / "golden" / "expected_aggregations.json"

# (case_id, fixture, group_by, min_amount, include_unknown)
CASES: tuple[tuple[str, str, str, int, bool], ...] = (
    ("G01", "sales_basic.csv", "category", 0, True),
    ("G02", "sales_basic.csv", "category", 0, False),
    ("G03", "sales_basic.csv", "region", 0, True),
    ("G04", "sales_basic.csv", "region", 0, False),
    ("G05", "sales_basic.csv", "channel", 0, True),
    ("G06", "sales_basic.csv", "channel", 0, False),
    ("G07", "sales_basic.csv", "category", 50, True),
    ("G08", "sales_basic.csv", "category", 100, True),
    ("G09", "sales_with_missing.csv", "category", 0, True),
    ("G10", "sales_with_missing.csv", "region", 0, True),
    ("G11", "sales_empty.csv", "category", 0, True),
    ("G12", "sales_unicode.csv", "category", 0, True),
    ("G13", "sales_utf8_bom.csv", "category", 0, True),
    ("G14", "sales_basic.csv", "region", 100, False),
    ("G15", "sales_basic.csv", "category", 50, False),
)

# (case_id, fixture, expected_row_number)
HARD_FAILURE_CASES: tuple[tuple[str, str, int], ...] = (
    ("G-H01", "sales_malformed.csv", 3),
)


def _fixture_sha256() -> dict[str, str]:
    manifest = json.loads((FIXTURES_DIR / "manifest.json").read_text(encoding="utf-8"))
    return {entry["file"]: entry["sha256"] for entry in manifest["fixtures"]}


def main() -> None:
    digests = _fixture_sha256()
    cases = []

    for case_id, fixture, group_by, min_amount, include_unknown in CASES:
        payload = (CSV_DIR / fixture).read_bytes()
        parsed = parse_csv(payload)
        result = aggregate(parsed.rows, group_by, min_amount, include_unknown)
        cases.append(
            {
                "id": case_id,
                "fixture": f"csv/{fixture}",
                "group_by": group_by,
                "min_amount": min_amount,
                "include_unknown": include_unknown,
                "parse": {
                    "total_data_rows": parsed.total_data_rows,
                    "invalid_amount_rows": parsed.invalid_amount_rows,
                },
                "rows": [
                    {
                        "group_key": a.group_key,
                        "row_count": a.row_count,
                        "total_amount": str(a.total_amount),
                        "total_amount_f64": float(a.total_amount).hex(),
                        "avg_amount": str(a.avg_amount),
                        "avg_amount_f64": float(a.avg_amount).hex(),
                    }
                    for a in result
                ],
                "totals": {
                    "row_count": sum(a.row_count for a in result),
                    "total_amount": str(
                        sum((a.total_amount for a in result), start=result[0].total_amount * 0)
                        if result
                        else 0
                    ),
                },
            }
        )

    hard_failures = []
    for case_id, fixture, expected_row_number in HARD_FAILURE_CASES:
        payload = (CSV_DIR / fixture).read_bytes()
        try:
            parse_csv(payload)
        except CsvFormatError as exc:
            hard_failures.append(
                {
                    "id": case_id,
                    "fixture": f"csv/{fixture}",
                    "error_type": "CsvFormatError",
                    "row_number": exc.row_number,
                    "message": str(exc),
                }
            )
            if exc.row_number != expected_row_number:
                raise SystemExit(
                    f"{case_id}: expected row_number {expected_row_number}, got {exc.row_number}"
                )
        else:
            raise SystemExit(f"{case_id}: expected CsvFormatError, but parsing succeeded")

    golden = {
        "schema_version": 1,
        "contract_id": "C-P0-04",
        "aggregation_contract_version": AGGREGATION_CONTRACT_VERSION,
        "generated_by": "tests/reference/generate_golden.py",
        "reference": {
            "streamlit": "1.66.1",
            "purpose": "development-only oracle; not shipped, not production",
        },
        "notes": [
            "Numeric expectations are exact decimals rounded half-up to 2 places.",
            "The *_f64 fields are the IEEE-754 doubles carried on the wire; assert bit-equality.",
            "Group keys are sorted ascending by Unicode code point.",
            "totals.total_amount is the sum of the *rounded* group totals, for convenience only.",
        ],
        "fixture_sha256": digests,
        "cases": cases,
        "hard_failure_cases": hard_failures,
    }

    GOLDEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    GOLDEN_PATH.write_text(
        json.dumps(golden, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(f"wrote {GOLDEN_PATH.relative_to(HERE.parent.parent)}")
    print(f"  {len(cases)} aggregation cases, {len(hard_failures)} hard-failure cases")
    for case in cases:
        keys = ", ".join(r["group_key"] for r in case["rows"]) or "(none)"
        print(f"  {case['id']}: {case['fixture']} {case['group_by']} "
              f"min={case['min_amount']} unknown={case['include_unknown']} -> {keys}")


if __name__ == "__main__":
    main()
