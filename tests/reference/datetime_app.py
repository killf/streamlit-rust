"""Datetime-input fixture frozen against the pinned Python 1.66.1 server.

Both pickers are load-only: this frontend commits datetime values only
through its calendar widget (typing never triggers a rerun), so the chain
pins the load wire.
"""
from datetime import datetime

import streamlit as st

st.datetime_input("Launch window", value=datetime(2025, 3, 15, 14, 30), key="launch")
st.datetime_input("Optional slot", value=None, key="slot")
