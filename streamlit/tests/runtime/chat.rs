//! Chat regressions against the measured Python 1.66.1 wire (see
//! .codex/compatibility.md, Chat elements): st.chat_message streams a
//! chat_message block (name, avatar defaulting to the name, ICON type,
//! allowEmpty, stretch width) with children at [slot, 0]; st.chat_input is
//! a trigger widget routed to the bottom root [3, 0] (placeholder, 200 MB
//! upload cap, 16000 Hz sample rate, auto-position marker) that returns
//! the submitted prompt on the run it triggered and None afterwards, with
//! the state riding chat_input_value{data, file_uploader_state}.
use super::*;
use crate::InputWidgets;
use crate::proto;

fn chat_entry(st: &Streamlit) -> Pin<Box<dyn Future<Output = ()> + '_>> {
    Box::pin(async move {
        // Mirrors tests/reference/chat_app.py.
        let user = st.chat_message("user");
        user.write("hello from user");

        let assistant = st.chat_message(crate::ChatMessageOptions::new("assistant").avatar(":material/robot:"));
        assistant.write("hello from assistant");

        if let Some(prompt) = st.chat_input("Say something").unwrap() {
            st.write(format!("echo: {prompt}"));
        }
    })
}

#[actix_web::test]
async fn chat_elements_match_the_measured_wire() {
    let listener = std::net::TcpListener::bind("127.0.0.1:0").unwrap();
    let address = listener.local_addr().unwrap();
    let server = HttpServer::new(move || App::new().app_data(web::Data::new(StreamlitServer::new(chat_entry, "127.0.0.1".into(), 0))).configure(configure_routes))
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

    let mut chat_widget_id = String::new();
    for run in 1..=2 {
        let states = if run == 1 {
            vec![]
        } else {
            vec![WidgetState {
                id: chat_widget_id.clone(),
                value: Some(widget_state::Value::ChatInputValue(proto::ChatInputValue {
                    data: Some("hi".into()),
                    file_uploader_state: Some(proto::FileUploaderState::default()),
                    audio_file_info: None,
                })),
            }]
        };
        send_binary(
            &mut stream,
            &(BackMsg {
                r#type: Some(back_msg::Type::RerunScript(ClientState {
                    widget_states: Some(WidgetStates { widgets: states }),
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
                        let Some(block_type) = block.r#type else { continue };
                        let proto::block::Type::ChatMessage(chat) = block_type else { continue };
                        let width = block.width_config.and_then(|config| config.width_spec).map(|spec| match spec {
                            proto::streamlit::width_config::WidthSpec::UseStretch(_) => "stretch".to_string(),
                            other => format!("{other:?}"),
                        });
                        timeline.push(format!(
                            "chat_message:{}:{}:{:?}:{:?}:w{:?}:{:?}",
                            chat.name,
                            chat.avatar,
                            proto::block::chat_message::AvatarType::try_from(chat.avatar_type).ok(),
                            block.allow_empty,
                            width,
                            path
                        ));
                    }
                    Some(delta::Type::NewElement(element)) => {
                        let kind = element.r#type.as_ref().map(|kind| match kind {
                            element::Type::Markdown(markdown) => format!("markdown:{:?}{:?}", markdown.body, path),
                            element::Type::ChatInput(chat) => {
                                chat_widget_id = chat.id.clone();
                                format!(
                                    "chat_input:{}:{}:{}:{}:{:?}{:?}",
                                    chat.placeholder,
                                    chat.max_upload_size_mb,
                                    chat.audio_sample_rate.unwrap_or(0),
                                    chat.is_auto_positioned_at_bottom,
                                    chat.accept_file,
                                    path
                                )
                            }
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
        if run == 1 {
            // Load: two chat blocks with children, then the bottom-routed
            // chat input consuming no main slot.
            assert_eq!(
                timeline.join(" | "),
                "chat_message:user:user:Some(Icon):true:wSome(\"stretch\"):[0, 0] | markdown:\"hello from user\"[0, 0, 0] | chat_message:assistant::material/robot::Some(Icon):true:wSome(\"stretch\"):[0, 1] | markdown:\"hello from assistant\"[0, 1, 0] | chat_input:Say something:200:16000:true:0[3, 0]"
            );
        } else {
            // The Enter commit: the chat_input_value data round trips and
            // the echo streams after the messages at the next main slot.
            assert_eq!(
                timeline.join(" | "),
                "chat_message:user:user:Some(Icon):true:wSome(\"stretch\"):[0, 0] | markdown:\"hello from user\"[0, 0, 0] | chat_message:assistant::material/robot::Some(Icon):true:wSome(\"stretch\"):[0, 1] | markdown:\"hello from assistant\"[0, 1, 0] | chat_input:Say something:200:16000:true:0[3, 0] | markdown:\"echo: hi\"[0, 2]"
            );
        }
    }

    drop(stream);
    handle.stop(false).await;
    task.await.unwrap().unwrap();
}
