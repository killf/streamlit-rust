"""Emit layout/streaming parameter variants onto the wire for capture."""
import time

import streamlit as st

st.title("Layout parameters")

# Expander: collapsed default, compact type, an icon.
with st.expander("Compact collapsed", expanded=False, icon=":material/add:", type="compact"):
    st.write("inside compact")
with st.expander("Plain expanded", expanded=True):
    st.write("inside plain")

# Popover: primary type, stretch width, disabled, help text.
with st.popover("Primary", type="primary", use_container_width=True, disabled=True, help=" popover help"):
    st.write("inside popover")

# Tabs: three labels with the middle one selected by default.
one, two, three = st.tabs(["Alpha", "Beta", "Gamma"], default="Beta")
with one:
    st.write("tab one")
with two:
    st.write("tab two")
with three:
    st.write("tab three")

# Dialog: large width variant.
@st.dialog("Wide", width="large")
def wide():
    st.write("inside dialog")


wide()

# Streaming: toast durations, status states, spinner show_time.
st.toast("short default")
st.toast("long", duration="long")
st.toast("ms", duration=1500)

with st.status("Working", expanded=False) as status:
    st.write("step")
    status.update(label="Done", state="complete", expanded=False)

with st.status("Broken") as broken:
    broken.update(state="error")

with st.spinner("Timing", show_time=True):
    time.sleep(0.05)
