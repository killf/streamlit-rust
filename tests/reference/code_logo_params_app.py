"""Emit code/skeleton/logo creation-wire parameter variants."""
import streamlit as st

st.title("Code skeleton logo edges")

# st.code: an exotic language tag and line numbers.
st.code("print('hi')", language="rust", line_numbers=True)

# st.skeleton: the default placeholder shape.
st.skeleton()

# st.logo: an emoji image rides the measured small-size load shape.
st.logo("🧊")
