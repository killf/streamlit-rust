"""Emit text-family and misc element creation-wire parameter variants."""
import streamlit as st

st.title("Text misc parameter edges")

# text: the plain pre-formatted body.
st.text("plain body")

# latex: a display formula.
st.latex(r"\int_0^1 x^2 dx")

# help: the inline popover helper.
st.help(st.dataframe)

# divider: small and default stretch forms.
st.divider()
