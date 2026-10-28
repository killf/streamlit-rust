"""Emit chat/metric/progress creation-wire parameter variants."""
import streamlit as st

st.title("Chat metric progress edges")

# chat_message: emoji-type avatar and a nested element.
with st.chat_message("Helper", avatar="🛠️"):
    st.write("inside")

# metric: no-delta, zero delta, off/gray, and negative normal.
st.metric("No delta", value=42)
st.metric("Zero delta", value=5, delta=0)
st.metric("Gray", value=7, delta="3", delta_color="off")
st.metric("Negative", value=9, delta="-2")

# progress: text label and a float value.
st.progress(50, text="Halfway there")
st.progress(25.5)
