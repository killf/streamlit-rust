"""Emit remaining media/layout parameter variants onto the wire for capture."""
import streamlit as st

st.title("Media and layout edges")

# URL input to st.video: a direct URL rides the wire unchanged (no upload).
st.video("https://example.com/clip.mp4", start_time=1, end_time=5)

# SRT subtitle text: converted to VTT by the reference before storage.
st.video(
    b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp42isom\x00\x00\x00\x08free",
    subtitles={"en": "1\n00:00:01,000 --> 00:00:02,000\nHello SRT"},
)

# popover wrap; tabs width/height are block-level configs.
with st.popover("Wrapped", wrap=True):
    st.write("inside wrapped")
one, two = st.tabs(["A", "B"], default="B", width=500, height=200)
with one:
    st.write("one")
with two:
    st.write("two")
