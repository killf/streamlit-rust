"""Emit date_input/select_slider creation-wire parameter variants."""
import datetime

import streamlit as st

st.title("Temporal parameter edges")

# date_input: explicit value, min/max window, a custom display format.
st.date_input("Bounded", value=datetime.date(2024, 3, 15),
              min_value=datetime.date(2024, 1, 1), max_value=datetime.date(2024, 12, 31), key="d1")
st.date_input("Formatted", value=datetime.date(2024, 6, 1), format="DD/MM/YYYY", key="d2")

# select_slider: a range default (two endpoints) with custom labels.
st.select_slider("Range", options=["low", "mid", "high"], value=("low", "high"), key="s1")

# time_input: step rides the creation wire.
st.time_input("Stepped", value=datetime.time(12, 30), step=900, key="t1")
