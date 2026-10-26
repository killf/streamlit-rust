"""Write-stream fixture frozen against the pinned Python 1.66.1 server."""
import time

import streamlit as st


def plain():
    for word in ["The ", "quick ", "**brown** ", "fox."]:
        yield word
        time.sleep(0.05)


def with_cursor():
    for word in ["Streamed ", "with ", "a ", "cursor."]:
        yield word
        time.sleep(0.05)


st.write_stream(plain())
st.write_stream(with_cursor(), cursor="▌")
