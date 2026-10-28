"""Emit audio/video element parameter variants onto the wire for capture."""
import io
import wave

import streamlit as st


def tone() -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as writer:
        writer.setnchannels(1)
        writer.setsampwidth(2)
        writer.setframerate(8000)
        writer.writeframes(b"\x00\x00" * 800)
    return buffer.getvalue()


video = b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp42isom\x00\x00\x00\x08free"

st.title("Media parameters")
st.audio(tone())
st.audio(tone(), autoplay=True, loop=True, start_time=1.5, end_time=3.0, format="audio/wav")
st.audio(tone(), format="audio/x-wav")
st.video(video)
st.video(video, autoplay=True, muted=True, loop=True, start_time=2, end_time=4)
st.video(video, subtitles={"en": "WEBVTT\n\n00:00:00.000 --> 00:00:02.000\nHello"})
st.video(video, subtitles={"en": "data:application/vtt;base64,ZW4="})  # invalid: must be VTT/SRT text
