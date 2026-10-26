"""Reference fixture: picker inputs on 1.66.1.

Driven by the m5 pickers probe (target/checks/m5-pickers-pyref): date
input (single and range), time input, color picker, select sliders
(single and range) and the audio/camera inputs, with a load pass and
committed interactions on the date, time, color and single select slider.
"""
from datetime import date, time

import streamlit as st

st.date_input("Start date", date(2025, 1, 15), key="start")
st.date_input("Window", (date(2025, 1, 15), date(2025, 2, 15)), key="window")

st.time_input("Meeting", time(14, 30), key="meeting")

st.color_picker("Accent", "#FF5733", key="accent")

st.select_slider("Pick one", ["low", "medium", "high"], key="one")
st.select_slider("Pick range", ["a", "b", "c", "d"], value=("b", "d"), key="range")

st.audio_input("Voice note", key="voice")
st.camera_input("Snapshot", key="shot")
