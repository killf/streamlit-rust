"""Pinned Python reference for component defaults and frontend state updates."""

import json

import streamlit as st
import streamlit.components.v2 as components_v2


component = components_v2.component(
    "default_state_probe",
    html="<button id='bye'>Set bye</button><button id='null'>Set null</button>",
    js="""
    export default function({ parentElement, setStateValue }) {
        parentElement.querySelector('#bye').onclick = () => setStateValue('value', 'bye');
        parentElement.querySelector('#null').onclick = () => setStateValue('value', null);
    }
    """,
)

result = component(
    key="greeter",
    default={"value": "hi", "untouched": 7},
    on_value_change=lambda: None,
    on_untouched_change=lambda: None,
)
st.code(json.dumps({"result": dict(result), "session_state": dict(st.session_state["greeter"])}, sort_keys=True), language="json")
st.button("Ordinary rerun")
