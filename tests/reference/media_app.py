"""Media reference fixture: an in-memory image, an in-memory WAV, and the
no-media presentation widgets, on one page."""

import io
import struct
import wave

import numpy as np
import streamlit as st

# A deterministic 8x8 RGBA gradient: no filesystem dependency.
rgba = np.arange(0, 1024, 4, dtype=np.uint8).reshape(8, 8, 4)
rgba[..., 3] = 255
st.image(rgba, caption="gradient")

# A deterministic half-second 440 Hz mono WAV, synthesized in memory.
samples = []
for index in range(11025):
    samples.append(int(20000 * __import__("math").sin(2 * 3.141592653589793 * 440 * index / 22050)))
buffer = io.BytesIO()
with wave.open(buffer, "wb") as wav:
    wav.setnchannels(1)
    wav.setsampwidth(2)
    wav.setframerate(22050)
    wav.writeframes(struct.pack("<" + "h" * len(samples), *samples))
st.audio(buffer.getvalue(), format="audio/wav")

st.metric(label="Temperature", value="72 °F", delta="2 °F")
st.metric(label="Wind", value="8 mph", delta="-3 mph", delta_color="inverse")

progress = st.progress(50)
progress.progress(75)
