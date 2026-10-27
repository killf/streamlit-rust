"""st.components.v2.component trigger reference fixture: one component whose
JS fires a trigger event from a real button click; the app surfaces the
per-event trigger value of the fired round-trip."""
import json

import streamlit as st
import streamlit.components.v2 as components_v2

HTML = "<button id='fire' type='button'>Fire</button>"
CSS = "button { color: red; }"
JS = """
    export default function(component) {
        const { parentElement, setTriggerValue } = component;
        const button = parentElement.querySelector('button');
        let count = 0;
        button.onclick = () => {
            count += 1;
            setTriggerValue('ping', { count });
        };
    }
"""

widget = components_v2.component("trigger_demo", html=HTML, css=CSS, js=JS)

result = widget(
    key="triggers",
    on_ping_change=lambda: None,
)
st.write(f"ping={json.dumps(result.ping)}")
