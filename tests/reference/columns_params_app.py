"""Emit st.columns parameter variants onto the wire for capture."""
import streamlit as st

st.title("Columns parameters")

# Defaults baseline: plain two equal columns.
left, right = st.columns(2)
left.write("default left")
right.write("default right")

# gap: medium and large.
m1, m2 = st.columns(2, gap="medium")
m1.write("medium")
large1, large2, large3 = st.columns(3, gap="large")
large1.write("large")

# border: true on both columns.
b1, b2 = st.columns(2, border=True)
b1.write("bordered")
b2.write("bordered")

# vertical_alignment: center and bottom.
c1, c2 = st.columns(2, vertical_alignment="center")
c1.write("centered")
v1, v2 = st.columns(2, vertical_alignment="bottom")
v1.write("bottom")

# Weighted spec with all parameters together.
w1, w2 = st.columns([3.0, 1.0], gap="large", border=True, vertical_alignment="center")
w1.write("weighted")
w2.write("weighted")
