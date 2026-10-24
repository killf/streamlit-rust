"""Reference app for the four numeric slider shapes.

DEVELOPMENT ONLY -- an oracle for the C-P0-04 numeric capture.  It is never
shipped and the Rust server must not start it.  It renders the same four
representatives as the Rust widgets example:

    Minimum amount   an int slider, one value, 0..200 step 10
    Ratio            a float slider, one value, 0..1 step 0.05
    Amount range     an int range slider, a tuple of two values, 20..80
    Ratio range      a float range slider, a tuple of two values, 0.2..0.8

    /?case=numeric
"""

from __future__ import annotations

import streamlit as st

st.set_page_config(page_title="streamlit-rust numeric reference", layout="wide")

CASE = st.query_params.get("case", "numeric")

st.title("Numeric widget reference")

if CASE == "numeric":
    amount = st.slider(
        "Minimum amount", min_value=0, max_value=200, value=0, step=10, key="min_amount"
    )
    ratio = st.slider(
        "Ratio", min_value=0.0, max_value=1.0, value=0.25, step=0.05, key="ratio"
    )
    amount_range = st.slider(
        "Amount range", min_value=0, max_value=200, value=(20, 80), step=10, key="amount_range"
    )
    ratio_range = st.slider(
        "Ratio range", min_value=0.0, max_value=1.0, value=(0.2, 0.8), step=0.1, key="ratio_range"
    )
    st.write(f"Minimum amount: {amount!r}")
    st.write(f"Ratio: {ratio!r}")
    st.write(f"Amount range: {amount_range!r}")
    st.write(f"Ratio range: {ratio_range!r}")

else:
    st.error(f"unknown case {CASE!r}")
