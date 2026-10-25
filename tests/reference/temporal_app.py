"""Temporal-slider reference fixture: date/time/datetime wire behavior.

Renders one slider per temporal type plus the pair variants and echoes each
returned value with its type, so one capture observes the default bounds, the
wire encoding, and the precision the application receives back. The microsecond
components are deliberate: they reveal whether the wire stores exact
epoch-microsecond integers or loses precision.
"""
import datetime as dt

import streamlit as st

date_value = st.slider("date", value=dt.date(2024, 3, 15))
time_value = st.slider("time", value=dt.time(12, 30, 7, 123456))
datetime_value = st.slider("datetime", value=dt.datetime(2024, 3, 15, 12, 30, 7, 123456))
date_pair = st.slider("date-range", value=(dt.date(2024, 3, 10), dt.date(2024, 3, 20)))
time_pair = st.slider("time-range", value=(dt.time(9, 15), dt.time(17, 45)))
datetime_pair = st.slider(
    "datetime-range",
    value=(
        dt.datetime(2024, 3, 10, 9, 30, 7, 123456),
        dt.datetime(2024, 3, 20, 17, 45, 7, 654321),
    ),
)

st.write(f"date={date_value!r}|{type(date_value).__name__}")
st.write(f"time={time_value!r}|{type(time_value).__name__}")
st.write(f"datetime={datetime_value!r}|{type(datetime_value).__name__}")
st.write(f"date_pair={date_pair!r}|{type(date_pair).__name__}")
st.write(f"time_pair={time_pair!r}|{type(time_pair).__name__}")
st.write(f"datetime_pair={datetime_pair!r}|{type(datetime_pair).__name__}")
