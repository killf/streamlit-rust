"""Reference fixture: display-container and json elements on 1.66.1.

Driven by the m5 display probe (target/checks/m5-display-pyref): a json
body, a status container with two children, an empty slot overwritten once,
a spacer and the bottom container.
"""
import streamlit as st

st.json({"a": 1, "b": [True, None]}, expanded=True)

with st.status("Working...", expanded=True) as status:
    st.write("step one")
    st.write("step two")
    status.update(label="Done", state="complete", expanded=False)

slot = st.empty()
slot.write("replaced")

st.space(3)

with st.bottom:
    st.write("bottom line")
