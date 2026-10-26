"""Reference fixture: presentation leftovers on 1.66.1.

Driven by the m5 display2 probe (target/checks/m5-display2-pyref): the
sidebar logo (emoji form), the help viewer over a builtin, a skeleton
placeholder and st.pdf (whose pinned reference lacks the optional
streamlit-pdf component, so the measured shape is the framework
exception).
"""
import streamlit as st

st.logo("🏠", size="small")

st.help(len)

placeholder = st.skeleton(height=100)

st.pdf("https://example.com/sample.pdf")
