"""Drive the reference app through every P0 scenario and record the evidence.

    python tests/reference/run_reference.py --out target/checks/reference-run/reference-run.json

This is the ``ref`` half of the evidence pair required by
tests/journeys/journeys.json.  The ``browser`` half is produced separately by
running the same scenarios against a real browser (official 1.66.1 frontend).

The script is a *verification* run, not just a dumper: every scenario carries
explicit expectations and the process exits non-zero if any of them is not met.
So a green run is itself the evidence that the expectations recorded in the
journey manifest are the ones Streamlit 1.66.1 actually produces.

Every scenario runs in its own session, so the expectations do not depend on
the order in which the scenarios are executed.

Note on what AppTest can and cannot show
-----------------------------------------
AppTest drives the script directly.  It faithfully reproduces Streamlit's form
gating -- a widget inside ``st.form`` does not reach the script until the form
is submitted (REF-16/REF-17).  What it does *not* reproduce is the browser's
network behaviour: the absence of a rerun request while typing, WebSocket
reconnect, and page reload are browser-only evidence and are marked as such in
the journey manifest.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
from datetime import datetime, timezone

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from streamlit.testing.v1 import AppTest  # noqa: E402

FIXTURES_DIR = HERE.parent / "fixtures" / "csv"
APP_PATH = HERE / "app.py"

TIMEOUT = 30


class Recorder:
    """Runs scenarios and accumulates observations plus expectation failures."""

    def __init__(self) -> None:
        self.scenarios: list[dict] = []
        self.failures: list[str] = []

    def check(self, scenario_id: str, label: str, actual, expected) -> None:
        if actual != expected:
            self.failures.append(
                f"{scenario_id}: {label}\n     expected: {expected!r}\n     actual:   {actual!r}"
            )

    def record(
        self, scenario_id: str, journeys: list[str], title: str, purpose: str, observations: dict
    ) -> None:
        self.scenarios.append(
            {
                "id": scenario_id,
                "journeys": journeys,
                "title": title,
                "purpose": purpose,
                "observations": observations,
            }
        )


def _fresh() -> AppTest:
    at = AppTest.from_file(str(APP_PATH), default_timeout=TIMEOUT)
    at.run()
    return at


def _upload(at: AppTest, filename: str) -> None:
    payload = (FIXTURES_DIR / filename).read_bytes()
    at.file_uploader(key="upload").set_value((filename, payload, "text/csv"))
    at.run()


def _texts(at: AppTest) -> list[str]:
    return [t.value for t in at.text]


def _counter(at: AppTest, label: str) -> str:
    for text in _texts(at):
        if text.startswith(label):
            return text
    return ""


def _table(at: AppTest) -> list[dict]:
    if len(at.dataframe) == 0:
        return []
    frame = at.dataframe[0].value
    return [
        {
            "group_key": str(row["group_key"]),
            "row_count": int(row["row_count"]),
            "total_amount": f"{float(row['total_amount']):.2f}",
            "avg_amount": f"{float(row['avg_amount']):.2f}",
        }
        for _, row in frame.iterrows()
    ]


def _chart_present(at: AppTest) -> bool:
    return len(at.get("vega_lite_chart")) > 0


def _snapshot(at: AppTest) -> dict:
    return {
        "run_count": _counter(at, "Script runs:"),
        "pulses": _counter(at, "Pulses:"),
        "applied_note": _counter(at, "Applied note:"),
        "errors": [e.value for e in at.error],
        "warnings": [w.value for w in at.warning],
        "infos": [i.value for i in at.info],
        "table": _table(at),
        "chart_present": _chart_present(at),
    }


def _session(
    upload: str | None = None,
    group_by: str | None = None,
    min_amount: int | None = None,
    include_unknown: bool | None = None,
) -> AppTest:
    """Start a fresh session and apply the requested controls."""
    at = _fresh()
    if upload is not None:
        _upload(at, upload)
    if group_by is not None:
        at.selectbox(key="group_by").set_value(group_by)
        at.run()
    if min_amount is not None:
        at.slider(key="min_amount").set_value(min_amount)
        at.run()
    if include_unknown is not None:
        at.checkbox(key="include_unknown").set_value(include_unknown)
        at.run()
    return at


BASIC_CATEGORY = [
    {"group_key": "Books", "row_count": 3, "total_amount": "245.75", "avg_amount": "81.92"},
    {"group_key": "Games", "row_count": 3, "total_amount": "409.48", "avg_amount": "136.49"},
    {"group_key": "Music", "row_count": 3, "total_amount": "139.00", "avg_amount": "46.33"},
    {"group_key": "Toys", "row_count": 3, "total_amount": "104.49", "avg_amount": "34.83"},
]

BASIC_REGION_ALL = [
    {"group_key": "(missing)", "row_count": 1, "total_amount": "88.00", "avg_amount": "88.00"},
    {"group_key": "East", "row_count": 2, "total_amount": "209.49", "avg_amount": "104.75"},
    {"group_key": "North", "row_count": 3, "total_amount": "264.50", "avg_amount": "88.17"},
    {"group_key": "South", "row_count": 2, "total_amount": "245.24", "avg_amount": "122.62"},
    {"group_key": "UNKNOWN", "row_count": 2, "total_amount": "40.49", "avg_amount": "20.25"},
    {"group_key": "West", "row_count": 2, "total_amount": "51.00", "avg_amount": "25.50"},
]

BASIC_REGION_KNOWN = [
    {"group_key": "East", "row_count": 2, "total_amount": "209.49", "avg_amount": "104.75"},
    {"group_key": "North", "row_count": 3, "total_amount": "264.50", "avg_amount": "88.17"},
    {"group_key": "South", "row_count": 2, "total_amount": "245.24", "avg_amount": "122.62"},
    {"group_key": "West", "row_count": 2, "total_amount": "51.00", "avg_amount": "25.50"},
]

BASIC_CHANNEL = [
    {"group_key": "Online", "row_count": 6, "total_amount": "361.99", "avg_amount": "60.33"},
    {"group_key": "Retail", "row_count": 6, "total_amount": "536.73", "avg_amount": "89.46"},
]

MISSING_CATEGORY = [
    {"group_key": "Books", "row_count": 2, "total_amount": "200.50", "avg_amount": "100.25"},
    {"group_key": "Games", "row_count": 3, "total_amount": "409.48", "avg_amount": "136.49"},
    {"group_key": "Music", "row_count": 2, "total_amount": "51.00", "avg_amount": "25.50"},
    {"group_key": "Toys", "row_count": 3, "total_amount": "104.49", "avg_amount": "34.83"},
]

UNICODE_CATEGORY = [
    {"group_key": "Bücher", "row_count": 1, "total_amount": "120.50", "avg_amount": "120.50"},
    {"group_key": "Jogos", "row_count": 1, "total_amount": "149.50", "avg_amount": "149.50"},
    {"group_key": "游戏", "row_count": 1, "total_amount": "199.99", "avg_amount": "199.99"},
]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, help="path of the JSON report to write")
    args = parser.parse_args()

    rec = Recorder()

    # -- REF-01: cold start -------------------------------------------------
    at = _fresh()
    obs = _snapshot(at)
    rec.record("REF-01", ["J00"], "Cold start, no file uploaded", "empty state", obs)
    rec.check("REF-01", "errors", obs["errors"], [])
    rec.check("REF-01", "run_count", obs["run_count"], "Script runs: 1")
    rec.check("REF-01", "pulses", obs["pulses"], "Pulses: 0")
    rec.check("REF-01", "infos", obs["infos"], ["Upload a CSV to see the aggregated result."])
    rec.check("REF-01", "table rows", len(obs["table"]), 0)
    rec.check("REF-01", "chart present", obs["chart_present"], False)

    # -- REF-02: canonical widget inventory --------------------------------
    inventory = {
        "file_uploader": [{"label": w.label, "key": w.key} for w in at.file_uploader],
        "selectbox": [
            {"label": w.label, "key": w.key, "options": list(w.options)} for w in at.selectbox
        ],
        "slider": [
            {
                "label": w.label,
                "key": w.key,
                "min": w.min,
                "max": w.max,
                "step": w.step,
                "value": w.value,
            }
            for w in at.slider
        ],
        "checkbox": [{"label": w.label, "key": w.key, "value": w.value} for w in at.checkbox],
        "button": [{"label": w.label, "key": w.key, "form_id": w.form_id} for w in at.button],
        "text_input": [{"label": w.label, "key": w.key, "form_id": w.form_id} for w in at.text_input],
        "title": [t.value for t in at.title],
    }
    rec.record("REF-02", ["J00"], "Canonical widget inventory", "widget labels/keys/limits", inventory)
    rec.check("REF-02", "uploader label", inventory["file_uploader"][0]["label"], "Upload sales CSV")
    rec.check(
        "REF-02",
        "selectbox options",
        inventory["selectbox"][0]["options"],
        ["category", "region", "channel"],
    )
    rec.check(
        "REF-02",
        "slider bounds",
        (
            inventory["slider"][0]["min"],
            inventory["slider"][0]["max"],
            inventory["slider"][0]["step"],
        ),
        (0, 200, 10),
    )
    rec.check("REF-02", "checkbox default", inventory["checkbox"][0]["value"], True)
    rec.check(
        "REF-02",
        "button labels",
        [b["label"] for b in inventory["button"]],
        ["Pulse", "Apply note"],
    )
    rec.check(
        "REF-02",
        "form membership",
        [(b["label"], b["form_id"]) for b in inventory["button"]],
        [("Pulse", ""), ("Apply note", "apply_form")],
    )
    rec.check(
        "REF-02",
        "text input form membership",
        [(t["label"], t["form_id"]) for t in inventory["text_input"]],
        [("Note", "apply_form")],
    )

    # -- REF-03: upload the baseline ---------------------------------------
    at = _session(upload="sales_basic.csv")
    obs = _snapshot(at)
    rec.record("REF-03", ["J01"], "Upload sales_basic.csv", "data input and aggregation", obs)
    rec.check("REF-03", "errors", obs["errors"], [])
    rec.check("REF-03", "warnings", obs["warnings"], [])
    rec.check("REF-03", "table", obs["table"], BASIC_CATEGORY)
    rec.check("REF-03", "chart present", obs["chart_present"], True)

    # -- REF-04: group by region -------------------------------------------
    at = _session(upload="sales_basic.csv", group_by="region")
    obs = _snapshot(at)
    rec.record("REF-04", ["J01"], "Group by = region", "grouping", obs)
    rec.check("REF-04", "table", obs["table"], BASIC_REGION_ALL)

    # -- REF-05: group by channel ------------------------------------------
    at = _session(upload="sales_basic.csv", group_by="channel")
    obs = _snapshot(at)
    rec.record("REF-05", ["J01"], "Group by = channel", "grouping", obs)
    rec.check("REF-05", "table", obs["table"], BASIC_CHANNEL)

    # -- REF-06: slider filter ---------------------------------------------
    at = _session(upload="sales_basic.csv", group_by="category", min_amount=100)
    obs = _snapshot(at)
    rec.record("REF-06", ["J02"], "Minimum amount = 100", "widget filtering", obs)
    rec.check(
        "REF-06",
        "table",
        obs["table"],
        [
            {"group_key": "Books", "row_count": 1, "total_amount": "120.50", "avg_amount": "120.50"},
            {"group_key": "Games", "row_count": 2, "total_amount": "349.49", "avg_amount": "174.75"},
        ],
    )
    rec.check("REF-06", "chart present", obs["chart_present"], True)

    # -- REF-07: slider filter that excludes every group -------------------
    at = _session(upload="sales_basic.csv", group_by="category", min_amount=200)
    obs = _snapshot(at)
    rec.record("REF-07", ["J02", "J08"], "Minimum amount = 200 (no rows match)", "widget filtering", obs)
    rec.check("REF-07", "table rows", len(obs["table"]), 0)
    rec.check("REF-07", "infos", obs["infos"], ["No rows match the current filters."])
    rec.check("REF-07", "chart present", obs["chart_present"], False)

    # -- REF-08: include_unknown off ----------------------------------------
    at = _session(upload="sales_basic.csv", group_by="region", include_unknown=False)
    obs = _snapshot(at)
    rec.record("REF-08", ["J02"], "Include unknown region = off", "widget filtering", obs)
    rec.check("REF-08", "table", obs["table"], BASIC_REGION_KNOWN)

    # -- REF-09: soft failure (unusable amount cells) -----------------------
    at = _session(upload="sales_with_missing.csv", group_by="category")
    obs = _snapshot(at)
    rec.record("REF-09", ["J07"], "Upload sales_with_missing.csv", "upload parse error and recovery", obs)
    rec.check("REF-09", "errors", obs["errors"], [])
    rec.check(
        "REF-09",
        "warnings",
        obs["warnings"],
        ["2 row(s) with an unusable 'amount' were excluded from the aggregation."],
    )
    rec.check("REF-09", "table", obs["table"], MISSING_CATEGORY)

    # -- REF-10: hard failure (ragged rows) ---------------------------------
    at = _session(upload="sales_malformed.csv")
    obs = _snapshot(at)
    rec.record("REF-10", ["J07"], "Upload sales_malformed.csv", "upload parse error and recovery", obs)
    rec.check(
        "REF-10",
        "errors",
        obs["errors"],
        ["Could not parse the uploaded CSV: row 3: expected 8 fields, found 7"],
    )
    rec.check("REF-10", "infos", obs["infos"], ["Upload a valid CSV to continue."])
    rec.check("REF-10", "table rows", len(obs["table"]), 0)
    rec.check("REF-10", "chart present", obs["chart_present"], False)

    # -- REF-11: recovery after a hard failure ------------------------------
    at = _session(upload="sales_malformed.csv")
    _upload(at, "sales_basic.csv")
    obs = _snapshot(at)
    rec.record("REF-11", ["J07"], "Recover by uploading a valid CSV", "upload parse error and recovery", obs)
    rec.check("REF-11", "errors", obs["errors"], [])
    rec.check("REF-11", "warnings", obs["warnings"], [])
    rec.check("REF-11", "table group count", len(obs["table"]), 4)
    rec.check("REF-11", "chart present", obs["chart_present"], True)

    # -- REF-12: empty dataset ----------------------------------------------
    at = _session(upload="sales_empty.csv")
    obs = _snapshot(at)
    rec.record("REF-12", ["J08"], "Upload sales_empty.csv", "empty data", obs)
    rec.check("REF-12", "errors", obs["errors"], [])
    rec.check("REF-12", "infos", obs["infos"], ["The uploaded CSV contains no data rows."])
    rec.check("REF-12", "table rows", len(obs["table"]), 0)
    rec.check("REF-12", "chart present", obs["chart_present"], False)

    # -- REF-13 / REF-14: unicode and BOM -----------------------------------
    at = _session(upload="sales_unicode.csv", group_by="category")
    unicode_obs = _snapshot(at)
    rec.record("REF-13", ["J01"], "Upload sales_unicode.csv", "non-ASCII payloads", unicode_obs)
    rec.check("REF-13", "table", unicode_obs["table"], UNICODE_CATEGORY)

    at = _session(upload="sales_utf8_bom.csv", group_by="category")
    bom_obs = _snapshot(at)
    rec.record("REF-14", ["J01"], "Upload sales_utf8_bom.csv", "UTF-8 BOM handling", bom_obs)
    rec.check("REF-14", "table", bom_obs["table"], UNICODE_CATEGORY)
    rec.check("REF-14", "errors", bom_obs["errors"], [])

    # -- REF-15: button pulse ------------------------------------------------
    at = _session(upload="sales_basic.csv")
    before = _snapshot(at)
    for _ in range(3):
        at.button(key="pulse").click()
        at.run()
    obs = _snapshot(at)
    rec.record("REF-15", ["J04", "J05"], "Click Pulse three times", "state and rerun", obs)
    rec.check("REF-15", "pulses", obs["pulses"], "Pulses: 3")
    rec.check(
        "REF-15",
        "run_count delta",
        int(obs["run_count"].split(":")[1]) - int(before["run_count"].split(":")[1]),
        3,
    )
    rec.check("REF-15", "table unchanged by the pulse", obs["table"], before["table"])

    # -- REF-16: form widget value does not reach the script before submit ---
    at = _session(upload="sales_basic.csv")
    at.text_input(key="note").set_value("hello")
    at.run()
    obs = _snapshot(at)
    rec.record("REF-16", ["J05"], "Type in the form without submitting", "form submit and button pulse", obs)
    rec.check("REF-16", "applied_note", obs["applied_note"], "Applied note:")

    # -- REF-17: form submit -------------------------------------------------
    at = _session(upload="sales_basic.csv")
    at.text_input(key="note").set_value("hello")
    at.button(key="apply_note").click()
    at.run()
    obs = _snapshot(at)
    rec.record("REF-17", ["J05"], "Submit the form", "form submit and button pulse", obs)
    rec.check("REF-17", "applied_note", obs["applied_note"], "Applied note: hello")

    report = {
        "schema_version": 1,
        "contract_id": "C-P0-04",
        "generated_by": "tests/reference/run_reference.py",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "reference": {
            "streamlit": "1.66.1",
            "app": "tests/reference/app.py",
            "harness": "streamlit.testing.v1.AppTest",
            "purpose": "development-only oracle; not shipped, not production",
        },
        "expectations_met": not rec.failures,
        "failures": rec.failures,
        "scenarios": rec.scenarios,
    }

    out = pathlib.Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n"
    )

    print(f"wrote {out}")
    print(f"  scenarios: {len(rec.scenarios)}  failures: {len(rec.failures)}")
    for failure in rec.failures:
        print("  FAIL " + failure)
    return 1 if rec.failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
