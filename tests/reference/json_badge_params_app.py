"""Emit st.json/st.badge/st.feedback creation-wire parameter variants."""
import streamlit as st

st.title("Json badge feedback edges")

# st.json: expanded default and collapsed (the pinned 1.66.1 API has no
# depth parameter — the measured boundary).
st.json({"outer": {"inner": [1, 2]}}, expanded=True)
st.json({"deep": {"a": {"b": {"c": 1}}}}, expanded=False)

# st.badge: the icon/color variants ride the message.
st.badge("New", icon=":material/rocket_launch:", color="green")
st.badge("Plain")

# st.feedback: the positional kind plus disabled riding the wire.
st.feedback("thumbs", key="f1", disabled=True)
