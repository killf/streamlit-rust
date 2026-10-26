//! components.v2 regressions against the measured Python 1.66.1 wire (see
//! .codex/compatibility.md, Custom components): the mounted instance
//! streams a bidi_component element whose id is the instance's widget id
//! (`$$ID-<digest>-<key>`, masked in the browser traces), carrying the
//! definition's inline HTML/CSS/JS, the empty source paths, the isolated
//! style flag and the JSON payload with the reference's json.dumps
//! separators at stretch width and content height; the mount returns the
//! default state object.
use super::*;
use crate::ComponentMount;
use crate::ComponentV2;
use crate::StreamlitApi;
use crate::proto::{element, forward_msg};
use serde_json::json;

const HTML: &str = "\n    <label style='padding-right: 1em;' for='txt'>Enter text</label>\n    <input id='txt' type='text' />\n";
const CSS: &str = "label { color: red; }";
const JS: &str = "\n    export default function(component) {\n        const { setStateValue, parentElement } = component;\n        const input = parentElement.querySelector('input');\n        input.onkeydown = (e) => {\n            if (e.key === 'Enter') {\n                setStateValue('value', e.target.value);\n            }\n        };\n    }\n";

fn componentv2_entry(st: &Streamlit) -> Pin<Box<dyn Future<Output = ()> + '_>> {
    Box::pin(async move {
        // Mirrors tests/reference/componentv2_app.py.
        let text_input = ComponentV2::new("greeting").html(HTML).css(CSS).js(JS);
        let state = st
            .component_v2(&text_input, ComponentMount::new().key("greeter").data(json!({"label": "Name", "value": "hi"})).default_state(json!({"value": "hi"})))
            .unwrap();
        st.write(format!("value={}", state.get("value").and_then(|value| value.as_str()).unwrap_or_default()));
    })
}

#[actix_web::test]
async fn component_v2_matches_the_measured_wire() {
    let listener = std::net::TcpListener::bind("127.0.0.1:0").unwrap();
    let address = listener.local_addr().unwrap();
    let server = HttpServer::new(move || App::new().app_data(web::Data::new(StreamlitServer::new(componentv2_entry, "127.0.0.1".into(), 0))).configure(configure_routes))
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

    send_binary(
        &mut stream,
        &(BackMsg {
            r#type: Some(back_msg::Type::RerunScript(ClientState::default())),
        })
        .encode_to_vec(),
    )
    .await;

    let mut components = Vec::new();
    let mut trailing = String::new();
    loop {
        let message = receive(&mut stream).await;
        match message.r#type {
            Some(forward_msg::Type::NewSession(_)) => {}
            Some(forward_msg::Type::SessionStatusChanged(status)) if !status.script_is_running => break,
            Some(forward_msg::Type::Delta(delta)) => {
                let Some(delta::Type::NewElement(element)) = delta.r#type else { continue };
                match element.r#type {
                    Some(element::Type::BidiComponent(component)) => components.push(component),
                    Some(element::Type::Markdown(markdown)) => trailing = markdown.body,
                    _ => {}
                }
            }
            Some(forward_msg::Type::ScriptFinished(status)) => assert_eq!(status, 0),
            Some(forward_msg::Type::SessionStatusChanged(_)) => {}
            other => panic!("unexpected lifecycle response: {other:?}"),
        }
    }
    assert_eq!(components.len(), 1, "exactly one mounted instance");
    assert_eq!(trailing, "value=hi", "the mount returns the default state");

    let component = &components[0];
    let digest = component.id.strip_prefix("$$ID-").and_then(|rest| rest.strip_suffix("-greeter")).unwrap_or_default();
    assert_eq!(digest.len(), 32, "the reference's fast-hash digest length: {}", component.id);
    assert!(digest.chars().all(|c| c.is_ascii_hexdigit()), "hex digest: {}", component.id);
    assert_eq!(component.component_name, "greeting");
    assert_eq!(component.html_content.as_deref(), Some(HTML));
    assert_eq!(component.css_content.as_deref(), Some(CSS));
    assert_eq!(component.js_content.as_deref(), Some(JS));
    assert_eq!(component.js_source_path.as_deref(), Some(""));
    assert_eq!(component.css_source_path.as_deref(), Some(""));
    assert!(component.isolate_styles);
    assert_eq!(component.form_id, "");
    match &component.data {
        Some(crate::proto::bidi_component::Data::Json(payload)) => assert_eq!(payload, r#"{"label": "Name", "value": "hi"}"#),
        other => panic!("the JSON payload must ride the data oneof: {other:?}"),
    }

    drop(stream);
    handle.stop(false).await;
    task.await.unwrap().unwrap();
}
