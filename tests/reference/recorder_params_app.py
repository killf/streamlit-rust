"""Emit audio_input/camera_input creation-wire parameter variants."""
import streamlit as st

st.title("Recorder parameter edges")

# audio_input: an explicit sample rate rides the wire.
st.audio_input("Record note", sample_rate=44100, key="a1")

# camera_input: the default capture mode.
st.camera_input("Take a photo", key="c1")
