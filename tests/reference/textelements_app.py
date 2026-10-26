"""Reference fixture: text-family and one-shot presentation elements on 1.66.1.

Driven by the m5 text-elements probe (target/checks/m5-textelements-pyref):
plain text, a subheader, latex, embedded html, an iframe, the snow one-shot,
an echo context writing code plus output, and a captured exception.
"""
import streamlit as st

st.text("plain text")
st.subheader("Sub header")
st.latex("a^2 + b^2 = c^2")
st.html("<p><b>bold</b> html</p>")
st.iframe("https://example.com")
st.snow()
with st.echo():
    st.write("echoed inside")
try:
    raise ValueError("boom")
except ValueError as error:
    st.exception(error)
