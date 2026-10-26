"""Layouts reference fixture: sidebar, expander, tabs, popover, dialog."""

import streamlit as st

with st.sidebar:
    st.write("side note")

with st.expander("Details", expanded=True):
    st.write("inside expander")

tab_one, tab_two = st.tabs(["One", "Two"])
with tab_one:
    st.write("first tab")
with tab_two:
    st.write("second tab")

with st.popover("Open settings"):
    st.write("inside popover")


@st.dialog("Confirm")
def confirm():
    st.write("inside dialog")


confirm()
