"""Emit widget creation-wire parameter variants for the M3 differential."""
import streamlit as st

st.title("Widget parameter edges")

# number_input: the float path (FLOAT enum, unset format) plus min/max/step.
st.number_input("Float free", value=1.5)
st.number_input("Float bounded", min_value=0.25, max_value=9.75, value=2.5, step=0.25)
st.number_input("Int bounded", min_value=2, max_value=8, value=4, step=2)

# radio: index=None (no default), horizontal, captions.
st.radio("Plain", ["a", "b"], index=None, key="r1")
st.radio("Horizontal", ["x", "y"], horizontal=True, captions=["first", "second"], key="r2")

# text_area: max_chars, placeholder, height.
st.text_area("Bounded", value="hello", max_chars=10, placeholder="type here", height=200, key="t1")

# multiselect: max_selections rides the creation wire.
st.multiselect("Capped", ["p", "q", "r"], max_selections=2, key="m1")
