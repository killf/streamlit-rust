"""Cache reference fixture: a cached pure function across reruns, a
parameter-keyed miss, st.cache_data.clear, and a st call inside a cached
function."""

import streamlit as st

count = st.session_state.get("runs", 0) + 1
st.session_state.runs = count


@st.cache_data
def double(n):
    return n * 2


@st.cache_data
def side_effect():
    st.write("inside cached fn")
    return 1


st.write(f"runs={count}")
st.write(f"cached={double(21)}")
st.write(f"cached_other={double(7)}")

try:
    st.write(f"side={side_effect()}")
except Exception as exc:  # the reference's own error path
    st.write(f"side_error={type(exc).__name__}")

if st.button("Again"):
    pass

if count == 2:
    st.cache_data.clear()
    st.write("cleared")
    st.write(f"cached_after_clear={double(21)}")
