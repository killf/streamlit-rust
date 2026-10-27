//! components.v2 trigger demo: one registered component whose JS fires a
//! trigger event from a real button click; the app surfaces the per-event
//! trigger value. Mirrors tests/reference/componenttrigger_app.py.
use ::streamlit::*;
use streamlit::StreamlitApi;

const HTML: &str = "<button id='fire' type='button'>Fire</button>";
const CSS: &str = "button { color: red; }";
const JS: &str = "\n    export default function(component) {\n        const { parentElement, setTriggerValue } = component;\n        const button = parentElement.querySelector('button');\n        let count = 0;\n        button.onclick = () => {\n            count += 1;\n            setTriggerValue('ping', { count });\n        };\n    }\n";

fn render(st: &Streamlit) -> anyhow::Result<()> {
    let widget = ComponentV2::new("trigger_demo").html(HTML).css(CSS).js(JS);
    let result = st.component_v2(&widget, ComponentMount::new().key("triggers").events(["ping"]))?;
    st.write(format!("ping={}", streamlit::pywire::py_dumps(&result.get("ping").cloned().unwrap_or(serde_json::Value::Null))));
    Ok(())
}

#[tokio::main]
async fn main() -> std::io::Result<()> {
    StreamlitServer::new(
        |st| {
            Box::pin(async move {
                if let Err(error) = render(st) {
                    st.write(format!("Example error: {error}"));
                }
            })
        },
        "127.0.0.1".into(),
        8542,
    )
    .start()
    .await
}
