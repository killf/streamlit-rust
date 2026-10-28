//! Real HTTP/WS regressions for the 1.66.1 transport boundary.
//! Included by server.rs to exercise the production route configuration without
//! exposing test-only routes or adding a second HTTP/WebSocket client dependency.
use super::*;
use crate::StreamlitApi;
use crate::proto::{BackMsg, ClientState, ForwardMsg, WidgetState, WidgetStates, back_msg, delta, element, forward_msg, widget_state};
use actix_web::test as http_test;
use prost::Message;
use std::time::Duration;
use tokio::io::{AsyncReadExt, AsyncWriteExt};
use tokio::net::TcpStream;

type TestResult<T = ()> = Result<T, Box<dyn std::error::Error>>;

mod buttons;
mod cache;
mod chartlibs;
mod charts;
mod chat;
mod colconfig;
mod componenttrigger;
mod componentv2;
mod data_views;
mod dataeditor;
mod dataframe_selection;
mod datetime;
mod display;
mod display2;
mod execution;
mod forms;
mod inputs;
mod layouts;
mod logging;
mod media;
mod navigation;
mod overlap;
mod pageconfig;
mod pickers;
mod presentation;
mod queryparams;
mod request_context;
mod sessions;
mod static_assets;
mod temporal;
mod textelements;
mod uploads;
mod widgets;
mod writestream;

fn entry(st: &Streamlit) -> Pin<Box<dyn Future<Output = ()> + '_>> {
    Box::pin(async move {
        st.title("Transport regression");
        st.caption("Caption stays a caption");
        st.code("let x = 1;", "rust");
        let clicked = st.button("Pulse");
        st.write(if clicked { "trigger=true" } else { "trigger=false" });
    })
}

#[actix_web::test]
async fn http_endpoints_and_official_assets() -> TestResult {
    let www = std::path::Path::new(env!("CARGO_MANIFEST_DIR")).join("../www");
    let app = http_test::init_service(App::new().configure(configure_routes).service(Files::new("/", &www).index_file("index.html"))).await;
    let response = http_test::call_service(&app, http_test::TestRequest::get().uri("/_stcore/health").to_request()).await;
    assert_eq!(response.status(), 200);
    assert_eq!(response.headers().get("content-type").map(|value| value.as_bytes()), Some(b"text/plain; charset=utf-8".as_slice()));
    assert_eq!(http_test::read_body(response).await.as_ref(), b"ok");

    let response = http_test::call_service(&app, http_test::TestRequest::get().uri("/_stcore/host-config").to_request()).await;
    assert_eq!(response.status(), 200);
    let config: serde_json::Value = http_test::read_body_json(response).await;
    // Observed from the pinned reference server's real HTTP response.
    assert_eq!(config.as_object().map(|object| object.len()), Some(7));
    assert_eq!(config["allowedOrigins"].as_array().map(|origins| origins.len()), Some(16));
    assert_eq!(config["allowedOrigins"][0], "https://devel.streamlit.test");
    for field in ["useExternalAuthToken", "enableCustomParentMessages", "enforceDownloadInNewTab", "blockErrorDialogs"] {
        assert_eq!(config[field], false);
    }
    assert_eq!(config["metricsUrl"], "");
    assert!(config["resourceCrossOriginMode"].is_null());

    let response = http_test::call_service(&app, http_test::TestRequest::get().uri("/").to_request()).await;
    assert_eq!(response.status(), 200);
    let index = std::fs::read(www.join("index.html"))?;
    assert_eq!(http_test::read_body(response).await.as_ref(), index);
    let html = std::str::from_utf8(&index)?;
    let script = html
        .split("src=\"")
        .skip(1)
        .filter_map(|rest| rest.split('"').next())
        .find(|path| path.ends_with(".js"))
        .ok_or("index.html must reference a JavaScript asset")?;
    let response = http_test::call_service(&app, http_test::TestRequest::get().uri(&format!("/{}", script.trim_start_matches("./"))).to_request()).await;
    assert_eq!(response.status(), 200);
    assert_eq!(http_test::read_body(response).await.as_ref(), std::fs::read(www.join(script))?);
    Ok(())
}

// Minimal RFC 6455 framing for test traffic. Client frames must be masked.
async fn send_binary(stream: &mut TcpStream, payload: &[u8]) {
    let mask = [0x12, 0x34, 0x56, 0x78];
    let mut frame = vec![0x82];
    if payload.len() < 126 {
        frame.push(0x80 | payload.len() as u8);
    } else {
        frame.push(0x80 | 126);
        assert!(payload.len() <= u16::MAX as usize, "test client framing supports payloads up to 65535 bytes; got {}", payload.len());
        frame.extend_from_slice(&(payload.len() as u16).to_be_bytes());
    }
    frame.extend_from_slice(&mask);
    frame.extend(payload.iter().enumerate().map(|(i, byte)| byte ^ mask[i % 4]));
    let sent = stream.write_all(&frame).await;
    assert!(sent.is_ok(), "sending masked binary WS frame ({} payload bytes) failed: {sent:?}", payload.len());
}

async fn receive(stream: &mut TcpStream) -> ForwardMsg {
    let received = tokio::time::timeout(Duration::from_secs(5), async {
        let mut header = [0; 2];
        stream.read_exact(&mut header).await?;
        assert_eq!(header[0], 0x82, "expected a complete binary WS frame");
        assert_eq!(header[1] & 0x80, 0, "server frames must not be masked");
        let length = match header[1] & 0x7f {
            126 => stream.read_u16().await? as usize,
            127 => usize::try_from(stream.read_u64().await?)?,
            value => value as usize,
        };
        assert!(length < 1024 * 1024);
        let mut body = vec![0; length];
        stream.read_exact(&mut body).await?;
        Ok::<_, Box<dyn std::error::Error>>(ForwardMsg::decode(body.as_slice())?)
    })
    .await;
    match received {
        Ok(Ok(message)) => message,
        Ok(Err(error)) => panic!("reading binary WS frame or decoding ForwardMsg failed: {error}"),
        Err(error) => panic!("WS response timed out (a rerun may be blocking subsequent requests): {error}"),
    }
}

#[actix_web::test]
async fn repeated_reruns_button_trigger_reset_and_heartbeat_over_real_websocket() -> TestResult {
    let listener = std::net::TcpListener::bind("127.0.0.1:0")?;
    let address = listener.local_addr()?;
    let server = HttpServer::new(|| App::new().app_data(web::Data::new(StreamlitServer::new(entry, "127.0.0.1".into(), 0))).configure(configure_routes))
        .workers(1)
        .listen(listener)?
        .run();
    let handle = server.handle();
    let task = actix_web::rt::spawn(server);
    let mut stream = TcpStream::connect(address).await?;
    // Fresh browser handshake: exactly two entries, never a fake reconnect id.
    let request = format!("GET /_stcore/stream HTTP/1.1\r\nHost: {address}\r\nConnection: Upgrade\r\nUpgrade: websocket\r\nSec-WebSocket-Version: 13\r\nSec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==\r\nSec-WebSocket-Protocol: streamlit, test-xsrf\r\n\r\n");
    stream.write_all(request.as_bytes()).await?;
    let headers = tokio::time::timeout(Duration::from_secs(5), async {
        let mut response = Vec::new();
        while !response.ends_with(b"\r\n\r\n") {
            response.push(stream.read_u8().await?);
            assert!(response.len() < 8192);
        }
        Ok::<_, Box<dyn std::error::Error>>(String::from_utf8(response)?.to_ascii_lowercase())
    })
    .await??;
    assert!(headers.starts_with("http/1.1 101"));
    assert!(headers.contains("sec-websocket-protocol: streamlit\r\n"));
    assert!(!headers.contains("test-xsrf"));

    let mut button_id = String::new();
    let mut session_id = String::new();
    let mut run_ids = std::collections::HashSet::new();
    // First render, two clicked reruns, then a plain rerun proving one-shot reset.
    for click in [false, true, true, false] {
        let widgets = if click {
            vec![WidgetState {
                id: button_id.clone(),
                value: Some(widget_state::Value::TriggerValue(true)),
            }]
        } else {
            vec![]
        };
        let request = BackMsg {
            r#type: Some(back_msg::Type::RerunScript(ClientState {
                widget_states: Some(WidgetStates { widgets }),
                ..Default::default()
            })),
        };
        send_binary(&mut stream, &request.encode_to_vec()).await;
        let first = receive(&mut stream).await;
        let Some(forward_msg::Type::NewSession(new_session)) = first.r#type else { panic!("rerun must start with NewSession") };
        let init = new_session.initialize.ok_or("NewSession must include initialization")?;
        assert!(uuid::Uuid::parse_str(&init.session_id).is_ok(), "server-selected session id must be a UUID: {}", init.session_id);
        if session_id.is_empty() {
            session_id = init.session_id;
        } else {
            assert_eq!(init.session_id, session_id);
        }
        assert_eq!(init.environment_info.ok_or("NewSession must include environment information")?.streamlit_version, "1.66.1");
        assert!(run_ids.insert(new_session.script_run_id));
        assert!(matches!(receive(&mut stream).await.r#type, Some(forward_msg::Type::SessionStatusChanged(status)) if status.script_is_running));
        let mut finished = 0;
        let mut markdown = Vec::new();
        loop {
            let msg = receive(&mut stream).await;
            match msg.r#type {
                Some(forward_msg::Type::Delta(delta)) => {
                    if let Some(delta::Type::NewElement(element)) = delta.r#type {
                        match element.r#type {
                            Some(element::Type::Button(button)) => {
                                if button_id.is_empty() {
                                    button_id = button.id;
                                } else {
                                    assert_eq!(button.id, button_id);
                                }
                            }
                            Some(element::Type::Markdown(text)) => markdown.push(text),
                            _ => {}
                        }
                    }
                }
                Some(forward_msg::Type::ScriptFinished(status)) => {
                    assert_eq!(status, 0);
                    finished += 1;
                }
                Some(forward_msg::Type::SessionStatusChanged(status)) if !status.script_is_running => break,
                _ => panic!("unexpected lifecycle response"),
            }
        }
        assert_eq!(finished, 1);
        assert!(!button_id.is_empty());
        assert!(markdown.iter().any(|text| text.body == format!("trigger={click}")));
        assert!(markdown.iter().any(|text| text.body == "Caption stays a caption" && text.element_type == 2));
        // Official BackMsg app_heartbeat field 17, then ForwardMsg heartbeat_ack field 26.
        send_binary(&mut stream, &[0x88, 0x01, 0x01]).await;
        let ack = receive(&mut stream).await;
        assert!(matches!(ack.r#type, Some(forward_msg::Type::HeartbeatAck(true))));
        assert_eq!(ack.encode_to_vec(), [0xd0, 0x01, 0x01]);
    }
    // A malformed protobuf must not prevent the next valid control request.
    send_binary(&mut stream, &[0xff]).await;
    send_binary(&mut stream, &[0x88, 0x01, 0x01]).await;
    assert!(matches!(receive(&mut stream).await.r#type, Some(forward_msg::Type::HeartbeatAck(true))));
    drop(stream);
    handle.stop(false).await;
    task.await??;
    Ok(())
}
