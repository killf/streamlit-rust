//! components.v2 trigger regressions against the measured Python 1.66.1 wire
//! (see .codex/compatibility.md, Custom components): the component's
//! setTriggerValue payloads ride one internal json_trigger_value aggregator
//! ($$STREAMLIT_INTERNAL_KEY_<widget-id>__events) as a JSON array string of
//! {"event", "value"} objects; the mount surfaces the declared events (null
//! until they fire, the last payload per event, state overwriting
//! collisions), and the value resets after the run like every reference
//! trigger.
use super::*;
use crate::ComponentMount;
use crate::ComponentV2;
use crate::StreamlitApi;
use crate::proto::{element, forward_msg, widget_state};

const HTML: &str = "<button id='fire' type='button'>Fire</button>";
const CSS: &str = "button { color: red; }";
const JS: &str = "\n    export default function(component) {\n        const { parentElement, setTriggerValue } = component;\n        const button = parentElement.querySelector('button');\n        let count = 0;\n        button.onclick = () => {\n            count += 1;\n            setTriggerValue('ping', { count });\n        };\n    }\n";

fn componenttrigger_entry(st: &Streamlit) -> Pin<Box<dyn Future<Output = ()> + '_>> {
    Box::pin(async move {
        // Mirrors tests/reference/componenttrigger_app.py.
        let widget = ComponentV2::new("trigger_demo").html(HTML).css(CSS).js(JS);
        let result = st.component_v2(&widget, ComponentMount::new().key("triggers").events(["ping"])).unwrap();
        st.write(format!("ping={}", crate::pywire::py_dumps(&result.get("ping").cloned().unwrap_or(serde_json::Value::Null))));
    })
}

#[actix_web::test]
async fn trigger_round_trip_over_the_production_websocket() {
    let listener = std::net::TcpListener::bind("127.0.0.1:0").unwrap();
    let address = listener.local_addr().unwrap();
    let server = HttpServer::new(move || App::new().app_data(web::Data::new(StreamlitServer::new(componenttrigger_entry, "127.0.0.1".into(), 0))).configure(configure_routes))
        .workers(1)
        .listen(listener)
        .unwrap()
        .run();
    let handle = server.handle();
    let task = actix_web::rt::spawn(server);
    let mut stream = TcpStream::connect(address).await.unwrap();
    let request = format!("GET /_stcore/stream HTTP/1.1\r\nHost: {address}\r\nConnection: Upgrade\r\nUpgrade: websocket\r\nSec-WebSocket-Version: 13\r\nSec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==\r\nSec-WebSocket-Protocol: streamlit, test-xsrf\r\n\r\n");
    stream.write_all(request.as_bytes()).await.unwrap();
    let headers = tokio::time::timeout(Duration::from_secs(5), async {
        let mut response = Vec::new();
        while !response.ends_with(b"\r\n\r\n") {
            response.push(stream.read_u8().await.unwrap());
        }
        String::from_utf8(response).unwrap().to_ascii_lowercase()
    })
    .await
    .unwrap();
    assert!(headers.starts_with("http/1.1 101"));

    // (markdown body, incoming aggregator state) per stage: load, first
    // fire, second fire, plain rerun after the fire (one-shot reset).
    let stages: Vec<(&str, Option<&str>)> = vec![
        (r#"ping=null"#, None),
        (r#"ping={"count": 1}"#, Some(r#"[{"event":"ping","value":{"count":1}}]"#)),
        (r#"ping={"count": 2}"#, Some(r#"[{"event":"ping","value":{"count":2}}]"#)),
        (r#"ping=null"#, None),
    ];
    let mut component_id = String::new();
    for (expected_markdown, fired) in stages {
        let widgets = if component_id.is_empty() || fired.is_none() {
            vec![]
        } else {
            vec![WidgetState {
                id: format!("$$STREAMLIT_INTERNAL_KEY_{component_id}__events"),
                value: fired.map(|payload| widget_state::Value::JsonTriggerValue(payload.to_owned())),
            }]
        };
        send_binary(
            &mut stream,
            &(BackMsg {
                r#type: Some(back_msg::Type::RerunScript(ClientState {
                    widget_states: Some(WidgetStates { widgets }),
                    ..Default::default()
                })),
            })
            .encode_to_vec(),
        )
        .await;
        let mut components = 0usize;
        let mut trailing = String::new();
        loop {
            let message = receive(&mut stream).await;
            match message.r#type {
                Some(forward_msg::Type::NewSession(_)) => {}
                Some(forward_msg::Type::SessionStatusChanged(status)) if !status.script_is_running => break,
                Some(forward_msg::Type::Delta(delta)) => {
                    let Some(delta::Type::NewElement(element)) = delta.r#type else { continue };
                    match element.r#type {
                        Some(element::Type::BidiComponent(component)) => {
                            component_id = component.id.clone();
                            components += 1;
                        }
                        Some(element::Type::Markdown(markdown)) => trailing = markdown.body,
                        _ => {}
                    }
                }
                Some(forward_msg::Type::ScriptFinished(status)) => assert_eq!(status, 0),
                Some(forward_msg::Type::SessionStatusChanged(_)) => {}
                other => panic!("unexpected lifecycle response: {other:?}"),
            }
        }
        assert_eq!(components, 1, "the component mounts once per run");
        assert_eq!(trailing, expected_markdown);
    }
    assert!(component_id.starts_with("$$ID-") && component_id.ends_with("-triggers"), "the state widget id anchors the aggregator: {component_id}");

    drop(stream);
    handle.stop(false).await;
    task.await.unwrap().unwrap();
}
