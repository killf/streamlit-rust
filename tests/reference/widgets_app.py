"""Reference app for the input widgets.

DEVELOPMENT ONLY -- an oracle for the C-P0-04 widget capture.  It is never
shipped and the Rust server must not start it.

Every case is a separate script run, selected with `?case=...`.  The error
cases have to stand alone: a bad argument raises inside the script, which
aborts the whole run, so it must not sit in the same run as the other widgets.

    /?case=defaults   selectbox, slider, checkbox with their default values
    /?case=options    the option list, the index and the default of each widget
    /?case=keys       widgets bound to session_state through a key
    /?case=on_change  on_change callbacks, and the order they run in
    /?case=disabled   the disabled variants of the three widgets
    /?case=dup_key    two widgets with the same key -> the error semantics
    /?case=none_option  a None option, selected by index 0
    /?case=none_unset   the same options with index=None, nothing selected
"""

from __future__ import annotations

import streamlit as st

st.set_page_config(page_title="streamlit-rust widgets reference", layout="wide")

CASE = st.query_params.get("case", "defaults")

st.title("Widget reference")

if CASE == "defaults":
    group = st.selectbox("Group by", ["category", "region", "channel"])
    amount = st.slider("Minimum amount", min_value=0, max_value=200, value=0, step=10)
    unknown = st.checkbox("Include unknown region", value=True)
    st.write(f"returned selectbox: {group!r} ({type(group).__name__})")
    st.write(f"returned slider: {amount!r} ({type(amount).__name__})")
    st.write(f"returned checkbox: {unknown!r} ({type(unknown).__name__})")

elif CASE == "options":
    group = st.selectbox("Group by", ["category", "region", "channel"], index=1)
    amount = st.slider("Minimum amount", min_value=0, max_value=200, value=50, step=10)
    unknown = st.checkbox("Include unknown region", value=False)
    st.write(f"returned selectbox: {group!r}")
    st.write(f"returned slider: {amount!r}")
    st.write(f"returned checkbox: {unknown!r}")

elif CASE == "none_option":
    # A None option is a legal option: index 0 selects it.
    group = st.selectbox("Group by", [None, "red"], index=0)
    st.write(f"returned selectbox: {group!r} ({type(group).__name__})")

elif CASE == "none_unset":
    # index=None means that nothing is selected yet.
    group = st.selectbox("Group by", [None, "red"], index=None)
    st.write(f"returned selectbox: {group!r} ({type(group).__name__})")

elif CASE == "keys":
    # A widget with a key takes its value from session_state and writes it
    # back there.  The seeded values show the direction session_state -> widget.
    st.session_state["group_by"] = "channel"
    st.session_state["min_amount"] = 50
    st.session_state["include_unknown"] = False
    group = st.selectbox("Group by", ["category", "region", "channel"], key="group_by")
    amount = st.slider("Minimum amount", 0, 200, 0, 10, key="min_amount")
    unknown = st.checkbox("Include unknown region", value=True, key="include_unknown")
    st.write(f"session_state[group_by]: {st.session_state.get('group_by')!r}")
    st.write(f"session_state[min_amount]: {st.session_state.get('min_amount')!r}")
    st.write(f"session_state[include_unknown]: {st.session_state.get('include_unknown')!r}")

elif CASE == "on_change":
    if "order" not in st.session_state:
        st.session_state["order"] = []

    def note_selectbox():
        st.session_state["order"].append("callback:selectbox")

    def note_slider():
        st.session_state["order"].append("callback:slider")

    def note_checkbox():
        st.session_state["order"].append("callback:checkbox")

    group = st.selectbox("Group by", ["category", "region", "channel"], on_change=note_selectbox)
    amount = st.slider("Minimum amount", 0, 200, 0, 10, on_change=note_slider)
    unknown = st.checkbox("Include unknown region", value=True, on_change=note_checkbox)
    st.session_state["order"].append("script")
    st.write(f"order: {st.session_state['order']}")

elif CASE == "disabled":
    group = st.selectbox("Group by", ["category", "region", "channel"], disabled=True)
    amount = st.slider("Minimum amount", 0, 200, 50, 10, disabled=True)
    unknown = st.checkbox("Include unknown region", value=True, disabled=True)
    st.write(f"returned selectbox: {group!r}")
    st.write(f"returned slider: {amount!r}")
    st.write(f"returned checkbox: {unknown!r}")

elif CASE == "dup_key":
    st.selectbox("Group by", ["category", "region"], key="the_same_key")
    st.selectbox("Other group by", ["category", "region"], key="the_same_key")

else:
    st.error(f"unknown case {CASE!r}")
