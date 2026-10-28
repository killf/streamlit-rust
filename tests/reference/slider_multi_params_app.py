"""Emit slider/multiselect creation-wire parameter variants."""
import datetime

import streamlit as st

st.title("Slider multiselect edges")

# slider: datetime values with an explicit time step; date-only values.
st.slider("Datetime stepped", value=datetime.datetime(2024, 3, 15, 12, 0),
          min_value=datetime.datetime(2024, 3, 1), max_value=datetime.datetime(2024, 3, 31),
          step=datetime.timedelta(minutes=30), key="s1")
st.slider("Date window", value=datetime.date(2024, 6, 15),
          min_value=datetime.date(2024, 6, 1), max_value=datetime.date(2024, 6, 30), key="s2")

# multiselect: default selections ride the creation wire.
st.multiselect("Defaults", ["p", "q", "r"], default=["q", "r"], key="m1")
