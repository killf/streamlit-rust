"""Video reference fixture: the committed one-second sample under its
default st.video call."""

import pathlib

import streamlit as st

# Deterministic ffmpeg output (see .codex/compatibility.md, Media route):
#   ffmpeg -f lavfi -i testsrc2=size=64x48:rate=10 -t 1 -pix_fmt yuv420p
#     -c:v libx264 -profile:v baseline -level 3.0
#     -x264-params keyint=10:min-keyint=10:scenecut=0:bframes=0 -b:v 48k
# The same committed bytes feed the Rust mirror, so the media address and
# the served body are byte-identical across runtimes.
SAMPLE = pathlib.Path(__file__).with_name("video_sample.mp4")
st.video(SAMPLE.read_bytes(), format="video/mp4")
