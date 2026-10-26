"""Chart-library fixture frozen against the pinned Python 1.66.1 server.

Load-only: the differential pins each library chart's full element wire.
"""
import altair as alt
import pandas as pd
import plotly.graph_objects as go
import pydeck as pdk
import streamlit as st

bars = pd.DataFrame({"kind": ["a", "b"], "count": [3, 7]})

st.altair_chart(alt.Chart(bars).mark_bar().encode(x="kind", y="count"))

st.vega_lite_chart({
    "mark": "bar",
    "encoding": {
        "x": {"field": "kind", "type": "nominal"},
        "y": {"field": "count", "type": "quantitative"},
    },
    "data": {"values": [{"kind": "a", "count": 3}, {"kind": "b", "count": 7}]},
})

st.plotly_chart(go.Figure(go.Bar(x=["a", "b"], y=[3, 7])))

st.pydeck_chart(
    pdk.Deck(
        layers=[
            pdk.Layer(
                "ScatterplotLayer",
                data=[{"position": [0.0, 0.0], "size": 4}],
                get_radius=100,
                get_color=[255, 0, 0],
            )
        ],
        initial_view_state=pdk.ViewState(latitude=0.0, longitude=0.0, zoom=1),
    )
)

st.graphviz_chart("digraph { a -> b }")

st.mermaid_chart("graph LR\n    A[Start] --> B{Decision}")

st.echarts_chart({
    "xAxis": {"type": "category", "data": ["a", "b"]},
    "yAxis": {"type": "value"},
    "series": [{"type": "bar", "data": [3, 7]}],
})
