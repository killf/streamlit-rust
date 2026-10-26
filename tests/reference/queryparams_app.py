"""Query-params reference fixture: a server-side param write, a creation-mode
filtered selectbox and a query-bound selectbox."""

import streamlit as st

st.query_params["mode"] = "demo"

pick = st.selectbox("Pick", ["a", "b"], accept_new_options=True, filter_mode="contains")
st.write(f"pick={pick}")

bound = st.selectbox("Bound", ["x", "y"], key="bound", bind="query-params")
st.write(f"bound={bound}")
