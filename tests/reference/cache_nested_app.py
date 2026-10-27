"""Pinned reference for nested cache output, execution counts, and replay positions."""

import json

import streamlit as st


counter_names = ("data_outer", "data_inner", "resource_outer", "resource_inner")
for name in counter_names:
    st.session_state.setdefault(name, 0)
st.session_state["round"] = st.session_state.get("round", 0) + 1


@st.cache_data
def data_inner(n):
    st.session_state["data_inner"] += 1
    st.write("data-inner")
    return n * 2


@st.cache_data
def data_outer(arg):
    st.session_state["data_outer"] += 1
    st.write(f"data-before-{arg}")
    value = data_inner(7)
    st.write(f"data-after-{arg}")
    return value + 1


@st.cache_resource
def resource_inner(n):
    st.session_state["resource_inner"] += 1
    st.write("resource-inner")
    return n * 2


@st.cache_resource
def resource_outer(arg):
    st.session_state["resource_outer"] += 1
    st.write(f"resource-before-{arg}")
    value = resource_inner(7)
    st.write(f"resource-after-{arg}")
    return value + 1


if st.session_state["round"] > 1:
    st.write("leading")

returned = {"data": {}, "resource": {}}
for arg in ("A", "B"):
    returned["data"][arg] = data_outer(arg)
    st.write(f"data-return-{arg}={returned['data'][arg]}")
for arg in ("A", "B"):
    returned["resource"][arg] = resource_outer(arg)
    st.write(f"resource-return-{arg}={returned['resource'][arg]}")

st.code(json.dumps({"round": st.session_state["round"], "returned": returned,
                    "counters": {name: st.session_state[name] for name in counter_names}}, sort_keys=True), language="json")
st.button("Again")
