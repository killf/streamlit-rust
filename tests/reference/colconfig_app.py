"""Column-config and data-editor fixture frozen against the pinned Python
1.66.1 server. One dataframe carrying all 21 column-config helpers, plus a
data_editor with a small grid."""
import datetime

import pandas as pd
import streamlit as st
from streamlit import column_config as cc

frame = pd.DataFrame(
    {
        "name": ["alpha", "beta"],
        "title": ["Chief", "Deputy"],
        "score": [1, 2],
        "done": [True, False],
        "kind": ["a", "b"],
        "tags": [["x"], ["y"]],
        "day": [datetime.date(2025, 1, 2), datetime.date(2025, 2, 3)],
        "moment": [datetime.datetime(2025, 1, 2, 3, 4), datetime.datetime(2025, 2, 3, 4, 5)],
        "clock": [datetime.time(3, 4), datetime.time(4, 5)],
        "items": [["a", "b"], ["c"]],
        "payload": [{"k": 1}, {"k": 2}],
        "notes": ["**bold**", "plain"],
        "site": ["https://example.com", "https://example.org"],
        "pic": ["a", "b"],
        "trend": [1, 2],
        "count": [3, 4],
        "signal": [5, 6],
        "fill": [50, 60],
        "clip": ["c1", "c2"],
        "reel": ["r1", "r2"],
        "act": ["go", "stop"],
    }
)

st.dataframe(
    frame,
    column_config={
        "name": cc.Column("Name", width="medium", help="the name", pinned=True, alignment="center"),
        "title": cc.TextColumn("Title", default="hi", max_chars=10, validate=r"^h"),
        "score": cc.NumberColumn("Score", default=1, format="%d", min_value=0, max_value=10, step=1),
        "done": cc.CheckboxColumn("Done", default=True),
        "kind": cc.SelectboxColumn("Kind", default="a", options=["a", "b"]),
        "tags": cc.MultiselectColumn("Tags", default=["x"], options=["x", "y"], accept_new_options=True),
        "day": cc.DateColumn("Day", default=datetime.date(2025, 1, 2), format="YYYY/MM/DD", min_value=datetime.date(2024, 1, 1), max_value=datetime.date(2026, 1, 1), step=1),
        "moment": cc.DatetimeColumn("Moment", default=datetime.datetime(2025, 1, 2, 3, 4), format="YYYY/MM/DD HH:mm", min_value=datetime.datetime(2024, 1, 1), max_value=datetime.datetime(2026, 1, 1), step=60, timezone="UTC"),
        "clock": cc.TimeColumn("Clock", default=datetime.time(3, 4), format="HH:mm", min_value=datetime.time(1, 0), max_value=datetime.time(23, 0), step=60),
        "items": cc.ListColumn("Items", default=["a"]),
        "payload": cc.JsonColumn("Payload"),
        "notes": cc.MarkdownColumn("Notes", default="**bold**"),
        "site": cc.LinkColumn("Site", default="https://example.com", max_chars=40, validate=r"^https", display_text="open"),
        "pic": cc.ImageColumn("Pic"),
        "trend": cc.AreaChartColumn("Trend", y_min=0, y_max=10, color="#ff0000"),
        "count": cc.BarChartColumn("Count", y_min=0, y_max=10, color="#00ff00"),
        "signal": cc.LineChartColumn("Signal", y_min=0, y_max=10, color="#0000ff"),
        "fill": cc.ProgressColumn("Fill", format="%d", min_value=0, max_value=100, step=1, color="green"),
        "clip": cc.AudioColumn("Clip"),
        "reel": cc.VideoColumn("Reel"),
        "act": cc.ButtonColumn("Act", type="primary", key="act"),
    },
)

edited = st.data_editor(pd.DataFrame({"qty": [1, 2]}), num_rows="dynamic", key="editor")
st.write(f"edits={edited.shape}")
