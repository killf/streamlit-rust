"""Deterministic aggregation core for the streamlit-rust P0 reference app.

This module is the *oracle*.  It deliberately depends on nothing but the Python
standard library (``csv`` + ``decimal``) so that its output cannot drift with a
pandas/altair release, and so that the Rust implementation has an unambiguous,
decimal-exact contract to reproduce.

Scope: this file is a **development-only** reference.  It is not shipped and
not part of any production path.  It exists so that the P0 user journeys
(tests/journeys/journeys.json) can state expected values that were derived from
a known-good Streamlit 1.66.1 run rather than from the Rust build under test.

--------------------------------------------------------------------------
The aggregation contract (normative for the Rust implementation)
--------------------------------------------------------------------------
Schema
    The CSV header must contain the columns ``amount`` and ``region``.  Extra
    columns are allowed and are carried through untouched.  Column order is not
    significant.  A missing required column is a hard error.

Two failure classes, deliberately distinct
    HARD  (``CsvFormatError``) -- the file cannot be parsed as this schema at
          all: not UTF-8, empty file, missing required column, or a data row
          whose field count differs from the header's field count.  The app
          shows an error and renders no table and no chart.  The uploader
          stays live so the user can upload a good file and recover.
    SOFT -- an individual ``amount`` cell is unusable (empty, or not a plain
          decimal literal).  The row is excluded from the aggregation and
          counted; every other row in the file still aggregates.

Amount parsing
    A cell is a valid amount iff, after stripping surrounding whitespace, it
    matches ``^[+-]?(\\d+(\\.\\d*)?|\\.\\d+)$``.  Everything else -- including
    ``""``, ``"not-a-number"``, ``"NaN"``, ``"Infinity"``, ``"1_000"`` and
    ``"1,000"`` -- is invalid.  (Note that Python's ``Decimal`` would happily
    accept ``NaN``, ``Infinity`` and ``1_000``; the explicit pattern is what
    keeps the reference aligned with a plain Rust decimal parser.)

Region unknownness
    After stripping whitespace and lowercasing, a region is *unknown* iff it is
    one of ``""``, ``"unknown"``, ``"n/a"``, ``"na"``, ``"null"``, ``"none"``,
    ``"-"``.  The ``include_unknown`` checkbox drops rows with an unknown
    region.  This filter always looks at the ``region`` column, independently
    of which column is currently selected for grouping.

Group keys
    The group key is the selected column's value with surrounding whitespace
    removed.  An empty group key is normalised to the literal ``"(missing)"``.
    Group keys are sorted ascending by Unicode code point (identical to
    ascending UTF-8 byte order, so Python's ``sorted`` and Rust's ``Ord`` on
    ``String`` agree).

Filtering
    A row contributes only if its amount is valid AND ``amount >= min_amount``
    AND (``include_unknown`` OR the row's region is not unknown).

Rounding
    Totals and averages are exact decimals rounded to 2 decimal places using
    ``ROUND_HALF_UP`` (ties away from zero).  The average is computed from the
    *unrounded* exact sum divided by the row count, then rounded once.
    Binary-float rounding is deliberately avoided: four of the fixture cases
    land exactly on a ``x.xx5`` boundary and a naive ``f64`` implementation
    diverges from the reference there.
"""

from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP, localcontext
from typing import Sequence

__all__ = [
    "AGGREGATION_CONTRACT_VERSION",
    "Aggregate",
    "CsvFormatError",
    "GROUP_BY_CHOICES",
    "MISSING_GROUP_KEY",
    "ParseResult",
    "Row",
    "aggregate",
    "normalize_group_key",
    "parse_csv",
    "region_is_unknown",
]

#: Bump whenever the normative contract above changes in an observable way.
AGGREGATION_CONTRACT_VERSION = "1.0.0"

CSV_HEADER_REQUIRED_COLUMNS: tuple[str, ...] = ("amount", "region")
AMOUNT_COLUMN = "amount"
REGION_COLUMN = "region"
GROUP_BY_CHOICES: tuple[str, ...] = ("category", "region", "channel")

MISSING_GROUP_KEY = "(missing)"
UNKNOWN_REGION_VALUES = frozenset({"", "unknown", "n/a", "na", "null", "none", "-"})

_AMOUNT_RE = re.compile(r"^[+-]?(?:\d+(?:\.\d*)?|\.\d+)$")
_TWO_PLACES = Decimal("0.01")
#: Working precision for the intermediate division.  50 digits is far more than
#: any fixture needs and keeps ``sum / count`` exact for the tie cases.
_WORKING_PRECISION = 50


class CsvFormatError(Exception):
    """Raised for hard (structural) CSV problems."""

    def __init__(self, message: str, row_number: int | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.row_number = row_number

    def __str__(self) -> str:  # pragma: no cover - trivial
        if self.row_number is None:
            return self.message
        return f"row {self.row_number}: {self.message}"


@dataclass(frozen=True)
class Row:
    """One parsed data row."""

    order_id: str
    date: str
    category: str
    region: str
    channel: str
    product: str
    amount: Decimal | None
    quantity: str
    raw_amount: str


@dataclass(frozen=True)
class ParseResult:
    """Outcome of parsing an uploaded file."""

    header: tuple[str, ...]
    rows: tuple[Row, ...]
    total_data_rows: int
    invalid_amount_rows: int

    @property
    def valid_rows(self) -> int:
        return self.total_data_rows - self.invalid_amount_rows


@dataclass(frozen=True)
class Aggregate:
    """One row of the aggregated result table."""

    group_key: str
    row_count: int
    total_amount: Decimal
    avg_amount: Decimal


def region_is_unknown(region: str) -> bool:
    """Return True iff ``region`` counts as unknown for the include_unknown filter."""
    return region.strip().lower() in UNKNOWN_REGION_VALUES


def normalize_group_key(raw: str) -> str:
    """Strip a group key and map the empty string to ``(missing)``."""
    stripped = raw.strip()
    return stripped if stripped else MISSING_GROUP_KEY


def _decode(data: bytes) -> str:
    if not data:
        raise CsvFormatError("the uploaded file is empty")
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise CsvFormatError(f"the uploaded file is not valid UTF-8: {exc}") from exc
    return text


def _parse_amount(raw: str) -> Decimal | None:
    candidate = raw.strip()
    if not _AMOUNT_RE.match(candidate):
        return None
    try:
        value = Decimal(candidate)
    except InvalidOperation:  # pragma: no cover - guarded by the regex
        return None
    if not value.is_finite():  # pragma: no cover - guarded by the regex
        return None
    return value


def parse_csv(data: bytes) -> ParseResult:
    """Parse uploaded bytes into rows.

    Raises
    ------
    CsvFormatError
        For hard problems: non-UTF-8 bytes, an empty file, a missing required
        column, or a data row whose field count differs from the header's.
    """
    text = _decode(data)
    reader = csv.reader(io.StringIO(text, newline=""))
    try:
        records = list(reader)
    except csv.Error as exc:
        raise CsvFormatError(f"the file is not valid CSV: {exc}") from exc

    if not records:
        raise CsvFormatError("the uploaded file is empty")

    header = tuple(cell.strip() for cell in records[0])
    if not header or all(cell == "" for cell in header):
        raise CsvFormatError("the CSV header row is empty")

    lowered = {cell.lower() for cell in header}
    missing = [c for c in CSV_HEADER_REQUIRED_COLUMNS if c not in lowered]
    if missing:
        raise CsvFormatError(
            "the CSV header is missing required column(s): " + ", ".join(missing)
        )

    index = {name: position for position, name in enumerate(header)}

    def cell(row: Sequence[str], name: str) -> str:
        position = index.get(name)
        if position is None:
            return ""
        return row[position].strip()

    rows: list[Row] = []
    invalid_amount_rows = 0
    total_data_rows = 0

    for offset, record in enumerate(records[1:]):
        if not record:
            # A physically blank line is skipped and is not an error.
            continue
        row_number = offset + 2  # 1-based, header is line 1
        if len(record) != len(header):
            raise CsvFormatError(
                f"expected {len(header)} fields, found {len(record)}", row_number=row_number
            )
        total_data_rows += 1
        raw_amount = cell(record, AMOUNT_COLUMN)
        amount = _parse_amount(raw_amount)
        if amount is None:
            invalid_amount_rows += 1
        rows.append(
            Row(
                order_id=cell(record, "order_id"),
                date=cell(record, "date"),
                category=cell(record, "category"),
                region=cell(record, REGION_COLUMN),
                channel=cell(record, "channel"),
                product=cell(record, "product"),
                amount=amount,
                quantity=cell(record, "quantity"),
                raw_amount=raw_amount,
            )
        )

    return ParseResult(
        header=header,
        rows=tuple(rows),
        total_data_rows=total_data_rows,
        invalid_amount_rows=invalid_amount_rows,
    )


def _group_key(row: Row, group_by: str) -> str:
    if group_by == "category":
        return normalize_group_key(row.category)
    if group_by == "region":
        return normalize_group_key(row.region)
    if group_by == "channel":
        return normalize_group_key(row.channel)
    raise ValueError(f"unsupported group_by: {group_by!r}")


def aggregate(
    rows: Sequence[Row],
    group_by: str,
    min_amount: Decimal | int | str = 0,
    include_unknown: bool = True,
) -> list[Aggregate]:
    """Filter and group ``rows`` according to the aggregation contract."""
    if group_by not in GROUP_BY_CHOICES:
        raise ValueError(f"unsupported group_by: {group_by!r}")
    threshold = Decimal(str(min_amount))

    counts: dict[str, int] = {}
    sums: dict[str, Decimal] = {}

    for row in rows:
        if row.amount is None:
            continue
        if row.amount < threshold:
            continue
        if not include_unknown and region_is_unknown(row.region):
            continue
        key = _group_key(row, group_by)
        counts[key] = counts.get(key, 0) + 1
        sums[key] = sums.get(key, Decimal(0)) + row.amount

    result: list[Aggregate] = []
    with localcontext() as ctx:
        ctx.prec = _WORKING_PRECISION
        for key in sorted(counts):
            count = counts[key]
            total = sums[key]
            result.append(
                Aggregate(
                    group_key=key,
                    row_count=count,
                    total_amount=total.quantize(_TWO_PLACES, rounding=ROUND_HALF_UP),
                    avg_amount=(total / count).quantize(_TWO_PLACES, rounding=ROUND_HALF_UP),
                )
            )
    return result
