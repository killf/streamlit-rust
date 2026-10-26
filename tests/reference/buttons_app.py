"""Reference fixture: the button family on 1.66.1.

Driven by the m5 buttons probe (target/checks/m5-buttons-pyref): toggle,
feedback, pills, segmented_control, pagination, menu_button,
download_button, link_button and an external page_link, with a load pass
and one interaction pass per widget.
"""
import streamlit as st

st.toggle("Night mode", key="night")
st.toggle("Sound", value=True)

stars = st.feedback("stars", key="rate")
st.feedback("thumbs")

st.pills("Priority", ["low", "medium", "high"], key="priority")
st.pills(
    "Tags",
    ["alpha", "beta", "gamma"],
    selection_mode="multi",
    default=["alpha"],
    key="tags",
)
st.segmented_control("View", ["grid", "list"], default="grid", key="view")

page = st.pagination(10, key="pager")
st.write(f"page={page}")

st.menu_button("Export", ["CSV", "JSON"], key="export")

st.download_button(
    "Save report",
    "quarterly report body",
    file_name="report.txt",
    mime="text/plain",
    key="save",
)
st.link_button("Docs", "https://docs.streamlit.io", key="docs")
st.page_link("https://example.com", label="Example site")
