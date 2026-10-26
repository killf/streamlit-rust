"""Page-config reference fixture: one full st.set_page_config call, then a write."""

import streamlit as st

st.set_page_config(
    page_title="Wide demo",
    page_icon=":material/check_circle:",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        "Get help": "https://docs.streamlit.io/",
        "Report a bug": "https://github.com/streamlit/streamlit/issues",
        "About": "### About text\nCreated with the reference fixture.",
    },
)

st.write("configured")
