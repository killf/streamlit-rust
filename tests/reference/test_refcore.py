"""Pytest suite pinning the reference aggregation behaviour.

    python -m pytest tests/reference -q

These tests are the Python side of contract C-P0-04.  They assert that
``refcore.py`` still reproduces the committed golden file exactly, and they
lock down the handful of semantics that a Rust implementation is most likely to
get wrong:

* decimal rounding is HALF_UP, not Python's default banker's rounding, and not
  binary-float rounding;
* amount parsing rejects look-alikes such as ``NaN``, ``Infinity``, ``1_000``
  and ``1,000``;
* a UTF-8 BOM is stripped rather than becoming part of the first column name;
* unknown-region detection and group-key normalisation are exactly as specified.

The golden file is regenerated with ``python tests/reference/generate_golden.py``.
"""

from __future__ import annotations

import hashlib
import json
import pathlib
import sys
from pathlib import Path
from decimal import ROUND_HALF_UP, Decimal

import pytest

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from refcore import (  # noqa: E402
    AGGREGATION_CONTRACT_VERSION,
    MISSING_GROUP_KEY,
    CsvFormatError,
    aggregate,
    normalize_group_key,
    parse_csv,
    region_is_unknown,
)

FIXTURES_DIR = HERE.parent / "fixtures"
CSV_DIR = FIXTURES_DIR / "csv"
GOLDEN = json.loads((HERE / "golden" / "expected_aggregations.json").read_text(encoding="utf-8"))
MANIFEST = json.loads((FIXTURES_DIR / "manifest.json").read_text(encoding="utf-8"))


def _load(name: str) -> bytes:
    return (CSV_DIR / name).read_bytes()


# ---------------------------------------------------------------------------
# fixture integrity
# ---------------------------------------------------------------------------


def test_golden_targets_the_current_contract_version():
    assert GOLDEN["aggregation_contract_version"] == AGGREGATION_CONTRACT_VERSION


def test_fixture_digests_match_manifest():
    for entry in MANIFEST["fixtures"]:
        payload = (FIXTURES_DIR / entry["file"]).read_bytes()
        assert len(payload) == entry["bytes"], entry["file"]
        assert hashlib.sha256(payload).hexdigest() == entry["sha256"], entry["file"]


def test_fixture_digests_match_golden():
    for relative, digest in GOLDEN["fixture_sha256"].items():
        payload = (FIXTURES_DIR / relative).read_bytes()
        assert hashlib.sha256(payload).hexdigest() == digest, relative


def test_fixtures_use_lf_newlines_only():
    for entry in MANIFEST["fixtures"]:
        payload = (FIXTURES_DIR / entry["file"]).read_bytes()
        assert b"\r" not in payload, entry["file"]


# ---------------------------------------------------------------------------
# golden reproduction
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("case", GOLDEN["cases"], ids=lambda c: c["id"])
def test_aggregation_case_matches_golden(case):
    parsed = parse_csv(_load(Path(case["fixture"]).name))
    assert parsed.total_data_rows == case["parse"]["total_data_rows"]
    assert parsed.invalid_amount_rows == case["parse"]["invalid_amount_rows"]

    result = aggregate(parsed.rows, case["group_by"], case["min_amount"], case["include_unknown"])

    assert [a.group_key for a in result] == [r["group_key"] for r in case["rows"]]
    assert [a.row_count for a in result] == [r["row_count"] for r in case["rows"]]
    assert [str(a.total_amount) for a in result] == [r["total_amount"] for r in case["rows"]]
    assert [str(a.avg_amount) for a in result] == [r["avg_amount"] for r in case["rows"]]
    assert [float(a.total_amount).hex() for a in result] == [
        r["total_amount_f64"] for r in case["rows"]
    ]
    assert [float(a.avg_amount).hex() for a in result] == [
        r["avg_amount_f64"] for r in case["rows"]
    ]
    assert sum(a.row_count for a in result) == case["totals"]["row_count"]


@pytest.mark.parametrize("case", GOLDEN["hard_failure_cases"], ids=lambda c: c["id"])
def test_hard_failure_case_matches_golden(case):
    with pytest.raises(CsvFormatError) as excinfo:
        parse_csv(_load(Path(case["fixture"]).name))
    assert excinfo.value.row_number == case["row_number"]
    assert str(excinfo.value) == case["message"]


# ---------------------------------------------------------------------------
# semantics a Rust implementation is most likely to get wrong
# ---------------------------------------------------------------------------


def test_rounding_is_half_up_not_bankers_rounding():
    # East = 59.99 + 149.50 = 209.49 over 2 rows -> 104.745 exactly.
    # Banker's rounding would give 104.74; half-up gives 104.75.
    parsed = parse_csv(_load("sales_basic.csv"))
    result = aggregate(parsed.rows, "region", 0, True)
    east = next(a for a in result if a.group_key == "East")
    assert east.avg_amount == Decimal("104.75")

    # UNKNOWN = 24.99 + 15.50 = 40.49 over 2 rows -> 20.245 exactly.
    unknown = next(a for a in result if a.group_key == "UNKNOWN")
    assert unknown.avg_amount == Decimal("20.25")

    # Retail = 536.73 over 6 rows -> 89.455 exactly.
    retail = next(a for a in aggregate(parsed.rows, "channel", 0, True) if a.group_key == "Retail")
    assert retail.avg_amount == Decimal("89.46")


def test_average_is_computed_from_the_unrounded_sum():
    # Books = 245.75 over 3 rows -> 81.91666... -> 81.92
    parsed = parse_csv(_load("sales_basic.csv"))
    books = next(a for a in aggregate(parsed.rows, "category", 0, True) if a.group_key == "Books")
    assert books.total_amount == Decimal("245.75")
    assert books.avg_amount == Decimal("81.92")
    # The average is (exact sum / count) rounded once, not the rounded average
    # of an already-rounded per-row value.
    assert books.avg_amount == (Decimal("245.75") / 3).quantize(Decimal("0.01"))
    assert books.avg_amount == (Decimal("245.75") / 3).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )


@pytest.mark.parametrize(
    "raw",
    ["", "   ", "not-a-number", "NaN", "nan", "Infinity", "inf", "1_000", "12.3.4", "1e3", "$5"],
)
def test_unusable_amount_cells_are_rejected(raw):
    payload = (
        "order_id,date,category,region,channel,product,amount,quantity\n"
        f"S-001,2026-01-05,Books,North,Online,Atlas Guide,{raw},2\n"
    ).encode("utf-8")
    parsed = parse_csv(payload)
    assert parsed.total_data_rows == 1
    assert parsed.invalid_amount_rows == 1
    assert aggregate(parsed.rows, "category", 0, True) == []


@pytest.mark.parametrize(
    "raw,expected",
    [("12.50", "12.50"), ("-3.5", "-3.5"), (".5", "0.5"), ("7.", "7.00"), ("0", "0.00")],
)
def test_valid_amount_cells_are_accepted(raw, expected):
    payload = (
        "order_id,date,category,region,channel,product,amount,quantity\n"
        f"S-001,2026-01-05,Books,North,Online,Atlas Guide,{raw},2\n"
    ).encode("utf-8")
    parsed = parse_csv(payload)
    assert parsed.invalid_amount_rows == 0
    assert parsed.rows[0].amount == Decimal(expected)
    # A negative amount is still a valid amount; it is the min_amount filter
    # that excludes it, which is asserted separately.
    assert aggregate(parsed.rows, "category", -100, True)[0].total_amount == Decimal(expected)


def test_thousands_separator_is_a_structural_error_not_a_cell_error():
    # "1,000" splits into an extra CSV field, so it is a hard parse failure
    # rather than an unusable amount cell.
    payload = (
        "order_id,date,category,region,channel,product,amount,quantity\n"
        "S-001,2026-01-05,Books,North,Online,Atlas Guide,1,000,2\n"
    ).encode("utf-8")
    with pytest.raises(CsvFormatError) as excinfo:
        parse_csv(payload)
    assert excinfo.value.row_number == 2


@pytest.mark.parametrize(
    "region,unknown",
    [
        ("", True),
        ("   ", True),
        ("UNKNOWN", True),
        ("unknown", True),
        ("N/A", True),
        ("na", True),
        ("null", True),
        ("None", True),
        ("-", True),
        ("North", False),
        ("UNKNOWNISH", False),
    ],
)
def test_region_unknown_detection(region, unknown):
    assert region_is_unknown(region) is unknown


def test_empty_group_key_normalises_to_missing():
    assert normalize_group_key("") == MISSING_GROUP_KEY
    assert normalize_group_key("   ") == MISSING_GROUP_KEY
    assert normalize_group_key(" North ") == "North"


def test_group_keys_sort_by_code_point():
    parsed = parse_csv(_load("sales_basic.csv"))
    keys = [a.group_key for a in aggregate(parsed.rows, "region", 0, True)]
    assert keys == ["(missing)", "East", "North", "South", "UNKNOWN", "West"]
    assert keys == sorted(keys)


def test_utf8_bom_is_stripped_and_matches_plain_utf8():
    with_bom = parse_csv(_load("sales_utf8_bom.csv"))
    without_bom = parse_csv(_load("sales_unicode.csv"))
    assert with_bom.header == without_bom.header
    assert with_bom.header[0] == "order_id"
    assert [a.group_key for a in aggregate(with_bom.rows, "category", 0, True)] == [
        a.group_key for a in aggregate(without_bom.rows, "category", 0, True)
    ]


def test_non_ascii_group_keys_survive():
    parsed = parse_csv(_load("sales_unicode.csv"))
    keys = [a.group_key for a in aggregate(parsed.rows, "category", 0, True)]
    assert keys == ["Bücher", "Jogos", "游戏"]


def test_empty_csv_has_header_but_no_rows():
    parsed = parse_csv(_load("sales_empty.csv"))
    assert parsed.total_data_rows == 0
    assert parsed.invalid_amount_rows == 0
    assert aggregate(parsed.rows, "category", 0, True) == []


def test_soft_failures_exclude_only_the_bad_rows():
    parsed = parse_csv(_load("sales_with_missing.csv"))
    assert parsed.total_data_rows == 12
    assert parsed.invalid_amount_rows == 2
    assert parsed.valid_rows == 10
    result = aggregate(parsed.rows, "category", 0, True)
    assert sum(a.row_count for a in result) == 10


def test_missing_required_column_is_a_hard_failure():
    payload = b"order_id,category\nS-001,Books\n"
    with pytest.raises(CsvFormatError) as excinfo:
        parse_csv(payload)
    assert "amount" in str(excinfo.value)


def test_empty_file_is_a_hard_failure():
    with pytest.raises(CsvFormatError):
        parse_csv(b"")


def test_ragged_row_is_a_hard_failure():
    payload = (
        "order_id,date,category,region,channel,product,amount,quantity\n"
        "S-001,2026-01-05,Books,North,Online,Atlas Guide,120.50,2\n"
        "S-002,2026-01-06,Books,North,Retail,Bridge Manual,80.00\n"
    ).encode("utf-8")
    with pytest.raises(CsvFormatError) as excinfo:
        parse_csv(payload)
    assert excinfo.value.row_number == 3


def test_min_amount_filter_partitions_rows():
    parsed = parse_csv(_load("sales_basic.csv"))
    assert sum(a.row_count for a in aggregate(parsed.rows, "category", 0, True)) == 12
    assert sum(a.row_count for a in aggregate(parsed.rows, "category", 50, True)) == 7
    assert sum(a.row_count for a in aggregate(parsed.rows, "category", 100, True)) == 3
    assert sum(a.row_count for a in aggregate(parsed.rows, "category", 200, True)) == 0


def test_include_unknown_filter_always_applies_to_region():
    parsed = parse_csv(_load("sales_basic.csv"))
    # Dropping unknown regions removes 3 rows regardless of the grouping column.
    for group_by in ("category", "region", "channel"):
        kept = aggregate(parsed.rows, group_by, 0, True)
        dropped = aggregate(parsed.rows, group_by, 0, False)
        assert sum(a.row_count for a in kept) == 12
        assert sum(a.row_count for a in dropped) == 9
