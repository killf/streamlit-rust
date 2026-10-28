"""The second M7 combined differential: an interactive flow through the real UI.

Every widget here carries its own frozen parity evidence; this page chains
upload -> checkbox -> selectbox -> row selection -> button+toast on one page
so widget state carriage, callbacks, and cross-widget interference are
observed in the real official frontend. The report block is the oracle.
"""
import json

import pandas as pd
import streamlit as st

st.title("Interactive combined")

files = st.file_uploader("Upload", accept_multiple_files=True, key="k")
checked = st.checkbox("Check", key="cb")
picked = st.selectbox("Pick", ["a", "b", "c"], key="sel")
frame = pd.DataFrame({"name": ["ann", "ben", "cy"], "score": [3, 1, 2]})
event = st.dataframe(frame, key="df", on_select="rerun", selection_mode="single-row")
row = int(event.selection.rows[0]) if event.selection.rows else None
applied = st.button("Apply", key="go")
if applied:
    st.toast("applied")

report = {
    "files": sorted(f.name for f in files),
    "checked": checked,
    "picked": picked,
    "row": row,
    "applied": applied,
}
st.code(json.dumps(report, ensure_ascii=False, sort_keys=True), language="json")
