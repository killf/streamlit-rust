"""Emit selectbox/checkbox/pills creation-wire parameter variants."""
import streamlit as st

st.title("Select pills edges")

# selectbox: placeholder + disabled + help ride the creation wire.
st.selectbox("Placeholder", ["a", "b"], index=None, placeholder="pick one", help="sb help", key="s1")
st.selectbox("Disabled", ["a", "b"], disabled=True, key="s2")

# checkbox: help + disabled.
st.checkbox("Chatty", value=True, help="cb help", disabled=True, key="c1")

# pills: selection_mode multi + default + help.
st.pills("Multi", ["x", "y", "z"], selection_mode="multi", default=["x", "z"], help="p help", key="p1")
