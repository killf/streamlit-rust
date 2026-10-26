//! components.v2 demo: one registered component mounted once with a JSON
//! data payload and a default state. Mirrors
//! tests/reference/componentv2_app.py.
use ::streamlit::*;
use serde_json::json;
use streamlit::StreamlitApi;

const HTML: &str = "\n    <label style='padding-right: 1em;' for='txt'>Enter text</label>\n    <input id='txt' type='text' />\n";
const CSS: &str = "label { color: red; }";
const JS: &str = "\n    export default function(component) {\n        const { setStateValue, parentElement } = component;\n        const input = parentElement.querySelector('input');\n        input.onkeydown = (e) => {\n            if (e.key === 'Enter') {\n                setStateValue('value', e.target.value);\n            }\n        };\n    }\n";

fn render(st: &Streamlit) {
    let text_input = ComponentV2::new("greeting").html(HTML).css(CSS).js(JS);
    let state = st
        .component_v2(&text_input, ComponentMount::new().key("greeter").data(json!({"label": "Name", "value": "hi"})).default_state(json!({"value": "hi"})))
        .unwrap();
    st.write(format!("value={}", state.get("value").and_then(|value| value.as_str()).unwrap_or_default()));
}

#[tokio::main]
async fn main() -> std::io::Result<()> {
    StreamlitServer::new(
        |st| {
            Box::pin(async move {
                render(st);
            })
        },
        "127.0.0.1".into(),
        8539,
    )
    .start()
    .await
}
