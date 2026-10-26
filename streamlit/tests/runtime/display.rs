//! Display-container regressions against the measured Python 1.66.1 wire
//! (see .codex/compatibility.md, Display containers): st.json streams the
//! Python json.dumps rendering with stretch width; st.status is an
//! expandable block (RUNNING/spinner) whose update re-streams the same
//! path (COMPLETE/:material/check:); st.empty takes a slot and the handle
//! overwrites that slot without advancing the cursor; st.space is a square
//! spacer with both configs set to the pixel value; st.bottom streams
//! children at the fixed root [3].
use super::*;
use crate::proto;

fn display_entry(st: &Streamlit) -> Pin<Box<dyn Future<Output = ()> + '_>> {
    Box::pin(async move {
        // Mirrors tests/reference/display_app.py.
        st.json_expanded(serde_json::json!({"a": 1, "b": [true, null]}), true);

        let status = st.status(crate::StatusContainerOptions::new("Working...").expanded(true));
        status.write("step one");
        status.write("step two");
        status.update(Some("Done".into()), Some(crate::StatusState::Complete), Some(false));

        let slot = st.empty();
        slot.write("replaced");

        st.space(3);

        let bottom = st.bottom();
        bottom.write("bottom line");
    })
}

#[actix_web::test]
async fn display_containers_match_the_measured_wire() {
    let listener = std::net::TcpListener::bind("127.0.0.1:0").unwrap();
    let address = listener.local_addr().unwrap();
    let server = HttpServer::new(move || App::new().app_data(web::Data::new(StreamlitServer::new(display_entry, "127.0.0.1".into(), 0))).configure(configure_routes))
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
            assert!(response.len() < 8192);
        }
        String::from_utf8(response).unwrap().to_ascii_lowercase()
    })
    .await
    .unwrap();
    assert!(headers.starts_with("http/1.1 101"));

    send_binary(
        &mut stream,
        &(BackMsg {
            r#type: Some(back_msg::Type::RerunScript(ClientState {
                widget_states: Some(WidgetStates { widgets: vec![] }),
                ..Default::default()
            })),
        })
        .encode_to_vec(),
    )
    .await;
    let mut timeline: Vec<String> = Vec::new();
    loop {
        let message = receive(&mut stream).await;
        let path = message.metadata.as_ref().map(|meta| meta.delta_path.clone()).unwrap_or_default();
        match message.r#type {
            Some(forward_msg::Type::NewSession(_)) => {}
            Some(forward_msg::Type::SessionStatusChanged(status)) if !status.script_is_running => break,
            Some(forward_msg::Type::Delta(delta)) => match delta.r#type {
                Some(delta::Type::AddBlock(block)) => {
                    let Some(block_type) = block.r#type else { panic!("unexpected block {block:?}") };
                    let proto::block::Type::Expandable(expandable) = block_type else { continue };
                    let width = block.width_config.and_then(|config| config.width_spec).map(|spec| match spec {
                        proto::streamlit::width_config::WidthSpec::UseStretch(_) => "stretch".to_string(),
                        proto::streamlit::width_config::WidthSpec::UseContent(_) => "content".to_string(),
                        proto::streamlit::width_config::WidthSpec::PixelWidth(pixels) => format!("px:{pixels}"),
                        other => format!("{other:?}"),
                    });
                    timeline.push(format!("status:{}:{}:{}:{:?}:{:?}:w{:?}:{:?}", expandable.label, expandable.icon, expandable.state, expandable.expanded, block.allow_empty, width, path));
                }
                Some(delta::Type::NewElement(element)) => {
                    let kind = element.r#type.as_ref().map(|kind| match kind {
                        element::Type::Json(json) => format!("json:{}:{}:{:?}", json.body, json.expanded, path),
                        element::Type::Empty(_) => format!("empty{:?}", path),
                        element::Type::Space(_) => {
                            let width = element.width_config.and_then(|config| config.width_spec).map(|spec| match spec {
                                proto::streamlit::width_config::WidthSpec::PixelWidth(pixels) => format!("px:{pixels}"),
                                other => format!("{other:?}"),
                            });
                            let height = element.height_config.and_then(|config| config.height_spec).map(|spec| match spec {
                                proto::streamlit::height_config::HeightSpec::PixelHeight(pixels) => format!("px:{pixels}"),
                                other => format!("{other:?}"),
                            });
                            format!("space:w{:?}:h{:?}{:?}", width, height, path)
                        }
                        element::Type::Markdown(markdown) => format!("markdown:{:?}{:?}", markdown.body, path),
                        other => format!("{other:?}{:?}", path),
                    });
                    timeline.push(kind.unwrap_or_else(|| format!("unset{:?}", path)));
                }
                _ => {}
            },
            Some(forward_msg::Type::ScriptFinished(status)) => assert_eq!(status, 0),
            Some(forward_msg::Type::SessionStatusChanged(_)) => {}
            other => panic!("unexpected lifecycle response: {other:?}"),
        }
    }
    let describe = timeline.join(" | ");
    assert_eq!(
        describe,
        "json:{\"a\": 1, \"b\": [true, null]}:true:[0, 0] | status:Working...:spinner:1:Some(true):true:wSome(\"stretch\"):[0, 1] | markdown:\"step one\"[0, 1, 0] | markdown:\"step two\"[0, 1, 1] | status:Done::material/check::2:Some(false):true:wSome(\"stretch\"):[0, 1] | empty[0, 2] | markdown:\"replaced\"[0, 2] | space:wSome(\"px:3\"):hSome(\"px:3\")[0, 3] | markdown:\"bottom line\"[3, 0]"
    );

    drop(stream);
    handle.stop(false).await;
    task.await.unwrap().unwrap();
}
