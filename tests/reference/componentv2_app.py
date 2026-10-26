"""st.components.v2.component reference fixture: one component registered with
inline HTML/CSS/JS and mounted once with a JSON data payload, a default state
value and its on_value_change callback registered (never fired)."""
import streamlit as st
import streamlit.components.v2 as components_v2

HTML = """
    <label style='padding-right: 1em;' for='txt'>Enter text</label>
    <input id='txt' type='text' />
"""
CSS = "label { color: red; }"
JS = """
    export default function(component) {
        const { setStateValue, parentElement } = component;
        const input = parentElement.querySelector('input');
        input.onkeydown = (e) => {
            if (e.key === 'Enter') {
                setStateValue('value', e.target.value);
            }
        };
    }
"""

text_input = components_v2.component("greeting", html=HTML, css=CSS, js=JS)

result = text_input(
    key="greeter",
    data={"label": "Name", "value": "hi"},
    default={"value": "hi"},
    on_value_change=lambda: None,
)
st.write(f"value={result.value}")
