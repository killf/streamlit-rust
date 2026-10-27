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

const STATE_CASES: &str = include_str!("../../../tests/reference/reference-browser/componentv2-state/state-cases.json");

#[derive(serde::Deserialize)]
struct StateCases {
    schema_version: u32,
    reference_version: String,
    default_state: serde_json::Value,
    stages: Vec<StateStage>,
}

#[derive(Clone, serde::Deserialize)]
struct StateStage {
    name: String,
    browser_widget_states: Vec<StateInput>,
    expected_result: serde_json::Value,
    expected_keyed_state: serde_json::Value,
}

#[derive(Clone, serde::Deserialize)]
struct StateInput {
    id: String,
    json_value: String,
}

fn componentv2_entry(st: &Streamlit) -> Pin<Box<dyn Future<Output = ()> + '_>> {
    Box::pin(async move {
        let result: TestResult = async {
            // Mirrors tests/reference/componentv2_app.py.
            let text_input = ComponentV2::new("greeting").html(HTML).css(CSS).js(JS);
            let state = st.component_v2(&text_input, ComponentMount::new().key("greeter").data(json!({"label": "Name", "value": "hi"})).default_state(json!({"value": "hi"})))?;
            st.write(format!("value={}", state.get("value").and_then(|value| value.as_str()).unwrap_or_default()));

            Ok(())
        }
        .await;

        assert!(result.is_ok(), "componentv2 fixture must render successfully: {result:?}");
    })
}

fn partial_state_entry(st: &Streamlit) -> Pin<Box<dyn Future<Output = ()> + '_>> {
    Box::pin(async move {
        let result: TestResult = async {
            let cases: StateCases = serde_json::from_str(STATE_CASES)?;
            let component = ComponentV2::new("partial_state").html(HTML).js(JS);
            let mounted = st.component_v2(&component, ComponentMount::new().key("partial").default_state(cases.default_state))?;
            let session = st.session_state().get::<serde_json::Value>("partial")?;
            st.write(format!("component-state={}", json!({"mount": mounted, "session": session})));
            Ok(())
        }
        .await;
        assert!(result.is_ok(), "partial component state fixture must render: {result:?}");
    })
}

#[actix_web::test]
async fn partial_component_state_preserves_defaults_in_mount_and_session() -> TestResult {
    let cases: StateCases = serde_json::from_str(STATE_CASES)?;
    assert_eq!(cases.schema_version, 1);
    assert_eq!(cases.reference_version, "1.66.1");
    assert_eq!(cases.stages.iter().map(|stage| stage.name.as_str()).collect::<Vec<_>>(), ["load", "set-bye", "ordinary-rerun", "set-null"]);
    let mut expected = cases.stages;
    // 额外空输入是 Rust 内部保留边界，不属于 Python 冻结的普通重跑输入。
    let last = expected.last().ok_or("component state reference must include stages")?;
    expected.push(StateStage {
        name: "rust-empty-incoming-after-null".into(),
        browser_widget_states: vec![],
        expected_result: last.expected_result.clone(),
        expected_keyed_state: last.expected_keyed_state.clone(),
    });
    let stages = expected.clone();
    let listener = std::net::TcpListener::bind("127.0.0.1:0")?;
    let address = listener.local_addr()?;
    let server = HttpServer::new(move || App::new().app_data(web::Data::new(StreamlitServer::new(partial_state_entry, "127.0.0.1".into(), 0))).configure(configure_routes))
        .workers(1)
        .listen(listener)?
        .run();
    let handle = server.handle();
    let server_task = actix_web::rt::spawn(server);

    // 采集任务隔离协议断言；失败或超时也先回收连接和服务，再报告结果。
    let mut capture_task = actix_web::rt::spawn(async move {
        let mut stream = sessions::connect(address, None).await;
        let mut component_id = String::new();
        let mut component_ids = Vec::new();
        let mut sessions = Vec::new();
        let mut finishes = Vec::new();
        let mut reports: Vec<serde_json::Value> = Vec::new();
        let mut reference_id = None;
        for stage in stages {
            let widgets = stage
                .browser_widget_states
                .into_iter()
                .map(|input| {
                    assert!(!component_id.is_empty(), "load must provide the actual native component id before state updates");
                    let previous = reference_id.get_or_insert_with(|| input.id.clone());
                    assert_eq!(previous, &input.id, "the frozen updates address one component instance");
                    WidgetState {
                        id: component_id.clone(),
                        value: Some(widget_state::Value::JsonValue(input.json_value)),
                    }
                })
                .collect();
            send_binary(
                &mut stream,
                &BackMsg {
                    r#type: Some(back_msg::Type::RerunScript(ClientState {
                        widget_states: Some(WidgetStates { widgets }),
                        ..Default::default()
                    })),
                }
                .encode_to_vec(),
            )
            .await;
            loop {
                match receive(&mut stream).await.r#type {
                    Some(forward_msg::Type::NewSession(new)) => sessions.push(new.initialize.ok_or("NewSession must include initialization")?.session_id),
                    Some(forward_msg::Type::Delta(delta)) => {
                        if let Some(delta::Type::NewElement(element)) = delta.r#type {
                            match element.r#type {
                                Some(element::Type::BidiComponent(component)) => {
                                    component_id = component.id;
                                    component_ids.push(component_id.clone());
                                }
                                Some(element::Type::Markdown(markdown)) => {
                                    if let Some(report) = markdown.body.strip_prefix("component-state=") {
                                        reports.push(serde_json::from_str(report)?);
                                    }
                                }
                                _ => {}
                            }
                        }
                    }
                    Some(forward_msg::Type::ScriptFinished(status)) => finishes.push(status),
                    Some(forward_msg::Type::SessionStatusChanged(status)) if !status.script_is_running => break,
                    _ => {}
                }
            }
        }
        Ok::<_, Box<dyn std::error::Error>>((reports, finishes, sessions, component_ids))
    });
    let captured = tokio::time::timeout(Duration::from_secs(10), &mut capture_task).await;
    if captured.is_err() {
        capture_task.abort();
        let _ = capture_task.await;
    }
    handle.stop(false).await;
    server_task.await??;
    let (reports, finishes, sessions, component_ids) = captured???;

    assert_eq!(finishes, vec![0; expected.len()], "every reference stage and Rust retention check finish once");
    assert_eq!(sessions.len(), expected.len());
    assert!(sessions.windows(2).all(|pair| pair[0] == pair[1]), "all runs use one retained session");
    assert_eq!(component_ids.len(), expected.len());
    assert!(component_ids.iter().all(|id| !id.is_empty() && id == &component_ids[0]), "the update uses the actual stable component id");
    assert_eq!(reports.len(), expected.len());
    for (report, stage) in reports.iter().zip(&expected) {
        assert_eq!(report.get("mount"), Some(&stage.expected_result), "mount result at stage {}", stage.name);
        assert_eq!(report.get("session"), Some(&stage.expected_keyed_state), "keyed session state at stage {}", stage.name);
    }
    Ok(())
}

#[actix_web::test]
async fn component_v2_matches_the_measured_wire() -> TestResult {
    let listener = std::net::TcpListener::bind("127.0.0.1:0")?;
    let address = listener.local_addr()?;
    let server = HttpServer::new(move || App::new().app_data(web::Data::new(StreamlitServer::new(componentv2_entry, "127.0.0.1".into(), 0))).configure(configure_routes))
        .workers(1)
        .listen(listener)?
        .run();
    let handle = server.handle();
    let task = actix_web::rt::spawn(server);
    let mut stream = TcpStream::connect(address).await?;
    let request = format!("GET /_stcore/stream HTTP/1.1\r\nHost: {address}\r\nConnection: Upgrade\r\nUpgrade: websocket\r\nSec-WebSocket-Version: 13\r\nSec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==\r\nSec-WebSocket-Protocol: streamlit, test-xsrf\r\n\r\n");
    stream.write_all(request.as_bytes()).await?;
    let headers = tokio::time::timeout(Duration::from_secs(5), async {
        let mut response = Vec::new();
        while !response.ends_with(b"\r\n\r\n") {
            response.push(stream.read_u8().await?);
        }
        Ok::<_, Box<dyn std::error::Error>>(String::from_utf8(response)?.to_ascii_lowercase())
    })
    .await??;
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
    task.await??;

    Ok(())
}
