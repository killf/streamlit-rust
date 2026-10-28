"""Cross-capability combination page: the M7 combined differential fixture.

Every capability here already carries its own frozen parity evidence; this
page interleaves them on ONE page so ordering, delta paths, and cross-element
interference are diffed end to end.
"""
import io
import wave

import pandas as pd
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

st.title("Combined page")
st.caption("cross-capability differential")

with st.expander("Compact", icon=":material/add:", type="compact"):
    st.write("expander body")
    st.code("print('combined')", language="python")

left, right = st.columns([3.0, 1.0], gap="large", border=True, vertical_alignment="center")
with left:
    st.markdown("left column")
    st.dataframe(pd.DataFrame({"kind": ["a", "b"], "count": [3, 7]}))
with right:
    st.metric("Temperature", "72 °F", delta="2 °F")

tab_one, tab_two = st.tabs(["Alpha", "Beta"], default="Beta")
with tab_one:
    # The pinned altair cannot even import under Python 3.14 (the recorded
    # TypedDict failure); like the csv reference, the explicit spec carries
    # the same grouped counts.
    st.vega_lite_chart({
        "mark": "bar",
        "encoding": {"x": {"field": "g", "type": "nominal"}, "y": {"field": "c", "type": "quantitative"}},
        "data": {"values": [{"g": "x", "c": 2}, {"g": "y", "c": 5}]},
    })
with tab_two:
    st.vega_lite_chart({
        "mark": "bar",
        "encoding": {"x": {"field": "k", "type": "nominal"}, "y": {"field": "v", "type": "quantitative"}},
        "data": {"values": [{"k": "m", "v": 4}, {"k": "n", "v": 9}]},
    })

with st.popover("Primary", type="primary", use_container_width=True):
    st.audio(tone(), autoplay=True, loop=True, start_time=1.5, end_time=3.0)

with st.status("Working", expanded=False) as status:
    st.video(video, autoplay=True, muted=True, start_time=2, end_time=4)
    status.update(label="Done", state="complete", expanded=False)

st.toast("combined done", duration="long")
