"""Emit widget creation-wire parameter variants for the M3 differential."""
import streamlit as st

if st.query_params.get("probe") == "number-sequence":
    phase = st.query_params.get("phase", "load")
    if phase == "assign":
        st.session_state["number"] = 8

    def changed():
        st.session_state["number_calls"] = st.session_state.get("number_calls", []) + [st.session_state["number"]]

    low = 3 if phase == "raise-min" else 0 if phase != "load" and phase != "edit" else None
    high = 6 if phase == "narrow-max" else 10 if phase not in ("load", "edit", "zero-min") else None
    value = st.number_input("Dynamic", value=5 if phase == "default" else 4, min_value=low, max_value=high,
                            step=2 if phase == "step" else 1, key="number", on_change=changed,
                            disabled=phase == "disabled")
    st.json({"phase": phase, "value": value, "state": st.session_state["number"],
             "callbacks": st.session_state.get("number_calls", [])})
    st.stop()

st.title("Widget parameter edges")

# number_input: the float path (FLOAT enum, unset format) plus min/max/step.
st.number_input("Float free", value=1.5)
st.number_input("Float bounded", min_value=0.25, max_value=9.75, value=2.5, step=0.25)
st.number_input("Int bounded", min_value=2, max_value=8, value=4, step=2)

# radio: index=None (no default), horizontal, captions.
st.radio("Plain", ["a", "b"], index=None, key="r1")
st.radio("Horizontal", ["x", "y"], horizontal=True, captions=["first", "second"], key="r2")

# text_area: max_chars, placeholder, height.
st.text_area("Bounded", value="hello", max_chars=10, placeholder="type here", height=200, key="t1")

# multiselect: max_selections rides the creation wire.
st.multiselect("Capped", ["p", "q", "r"], max_selections=2, key="m1")


# Opt-in boundary probe leaves the original eight-element reference intact.
if st.query_params.get("probe") == "integer-bounds":
    st.number_input("Int free", value=4)
    st.number_input("Int min only", value=4, min_value=2)
    st.number_input("Int max only", value=4, max_value=8)
    st.number_input("Int zero min", value=4, min_value=0)
    st.number_input("Int zero max", value=-4, max_value=0)
    st.number_input("Int safe high", value=9007199254740991)
    st.number_input("Int safe low", value=-9007199254740991)
