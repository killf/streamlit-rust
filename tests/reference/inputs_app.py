"""Input-widgets reference fixture: radio, multiselect, number_input and
text_area wire behavior, driven by real browser input in the differential."""
import streamlit as st

channel = st.radio("Channel", ["email", "sms", "push"], index=0)
tags = st.multiselect("Tags", ["alpha", "beta", "gamma"], default=["alpha"])
count = st.number_input("Count", value=7, min_value=0, max_value=100, step=1)
note = st.text_area("Note", value="first line\nsecond line")

st.write(f"channel={channel!r}")
st.write(f"tags={tags!r}")
st.write(f"count={count!r} type={type(count).__name__}")
st.write(f"note={note!r}")
