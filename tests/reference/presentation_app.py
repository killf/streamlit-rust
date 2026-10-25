"""Presentation reference fixture: a spinner context, one toast, balloons."""

import time

import streamlit as st

with st.spinner("Loading data"):
    time.sleep(2)
st.write("loaded")

st.toast("Saved successfully", icon="✅")
st.balloons()
