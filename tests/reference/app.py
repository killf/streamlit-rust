"""streamlit-rust P0 reference application (Streamlit 1.66.1).

DEVELOPMENT ONLY.  This app is a behavioural oracle for the P0 user journeys
described in tests/journeys/journeys.json.  It is **not** shipped, **not** part
of any production path, and must not be started by the Rust server.  The Rust
implementation is expected to reproduce the behaviour encoded here, not to call
this code.

The aggregation rules themselves live in ``refcore.py`` (standard library only)
so that the expected values in the journeys are decimal-exact and independent of
pandas/altair release drift.  This module only wires that core into Streamlit
widgets.

Canonical widget order
----------------------
The Rust implementation should mirror this order, because the browser journeys
locate widgets by position and by ``data-testid``:

    1. file_uploader  "Upload sales CSV"            key=upload
    2. selectbox     "Group by"                     key=group_by
    3. slider        "Minimum amount"               key=min_amount
    4. checkbox      "Include unknown region"       key=include_unknown
    5. (result)      table, then chart
    6. button        "Pulse"                        key=pulse
    7. form          key=apply_form, containing
                       text_input     "Note"         key=note
                       form_submit_button "Apply note" key=apply_note
    8. counters      "Script runs", "Pulses", "Applied note"

Run it with the pinned interpreter (see tests/reference/README.md):

    streamlit run tests/reference/app.py --server.headless true
"""

from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent))

from refcore import (  # noqa: E402  (path setup must precede the import)
    AGGREGATION_CONTRACT_VERSION,
    GROUP_BY_CHOICES,
    CsvFormatError,
    aggregate,
    parse_csv,
)

st.set_page_config(page_title="streamlit-rust P0 reference", layout="wide")

# --------------------------------------------------------------------------
# Run counter: incremented exactly once per script run (i.e. per rerun).
# --------------------------------------------------------------------------
st.session_state.setdefault("run_count", 0)
st.session_state["run_count"] += 1
run_count = st.session_state["run_count"]

st.session_state.setdefault("pulse_count", 0)
st.session_state.setdefault("applied_note", "")

st.title("streamlit-rust P0 reference")
st.caption(
    "Development-only reference app running against Streamlit "
    f"{st.__version__}. Aggregation contract v{AGGREGATION_CONTRACT_VERSION}. "
    "Not shipped and not part of the production path."
)

# --------------------------------------------------------------------------
# 1-4: input and filters
# --------------------------------------------------------------------------
uploaded = st.file_uploader("Upload sales CSV", type=["csv"], key="upload")

group_by = st.selectbox("Group by", options=list(GROUP_BY_CHOICES), key="group_by")
min_amount = st.slider(
    "Minimum amount", min_value=0, max_value=200, value=0, step=10, key="min_amount"
)
include_unknown = st.checkbox("Include unknown region", value=True, key="include_unknown")

TABLE_COLUMNS = ("group_key", "row_count", "total_amount", "avg_amount")


def _empty_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "group_key": pd.Series([], dtype="object"),
            "row_count": pd.Series([], dtype="int64"),
            "total_amount": pd.Series([], dtype="float64"),
            "avg_amount": pd.Series([], dtype="float64"),
        }
    )


def _result_frame(result) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "group_key": [a.group_key for a in result],
            "row_count": pd.Series([a.row_count for a in result], dtype="int64"),
            "total_amount": pd.Series([float(a.total_amount) for a in result], dtype="float64"),
            "avg_amount": pd.Series([float(a.avg_amount) for a in result], dtype="float64"),
        }
    )


# --------------------------------------------------------------------------
# 5: result -- table, then chart
# --------------------------------------------------------------------------
st.subheader("Aggregated result")

if uploaded is None:
    st.info("Upload a CSV to see the aggregated result.")
else:
    try:
        parsed = parse_csv(uploaded.getvalue())
    except CsvFormatError as exc:
        # HARD failure: no table, no chart, uploader stays live so the user can
        # upload a good file and recover.
        st.error(f"Could not parse the uploaded CSV: {exc}")
        st.info("Upload a valid CSV to continue.")
    else:
        if parsed.invalid_amount_rows:
            # SOFT failure: unusable amount cells are excluded, everything else
            # still aggregates.
            st.warning(
                f"{parsed.invalid_amount_rows} row(s) with an unusable 'amount' "
                "were excluded from the aggregation."
            )
        if parsed.total_data_rows == 0:
            st.info("The uploaded CSV contains no data rows.")
            st.dataframe(
                _empty_frame(),
                width="stretch",
                hide_index=True,
                column_order=list(TABLE_COLUMNS),
            )
        else:
            result = aggregate(parsed.rows, group_by, min_amount, include_unknown)
            if not result:
                st.info("No rows match the current filters.")
            frame = _result_frame(result)
            st.dataframe(
                frame,
                width="stretch",
                hide_index=True,
                column_order=list(TABLE_COLUMNS),
            )
            if result:
                chart = (
                    alt.Chart(frame)
                    .mark_bar()
                    .encode(
                        x=alt.X("group_key:N", sort=[a.group_key for a in result]),
                        y=alt.Y("total_amount:Q"),
                        tooltip=[
                            alt.Tooltip("group_key:N", title="group"),
                            alt.Tooltip("row_count:Q", title="rows"),
                            alt.Tooltip("total_amount:Q", title="total"),
                            alt.Tooltip("avg_amount:Q", title="avg"),
                        ],
                    )
                    .properties(height=260)
                )
                st.altair_chart(chart, width="stretch")

# --------------------------------------------------------------------------
# 6-8: interaction widgets and counters
# --------------------------------------------------------------------------
st.subheader("Interaction")

pulse_clicked = st.button("Pulse", key="pulse")
if pulse_clicked:
    st.session_state["pulse_count"] = st.session_state["pulse_count"] + 1

with st.form("apply_form", clear_on_submit=False):
    note_input = st.text_input("Note", key="note")
    submitted = st.form_submit_button("Apply note", key="apply_note")

if submitted:
    # Only the submit makes the form's widget values reach the server, so this
    # assignment happens exactly on the submitting run.
    st.session_state["applied_note"] = note_input

st.text(f"Script runs: {run_count}")
st.text(f"Pulses: {st.session_state['pulse_count']}")
st.text(f"Applied note: {st.session_state['applied_note']}")
