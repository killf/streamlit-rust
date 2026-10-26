//! Presentation-leftover regressions against the measured Python 1.66.1 wire
//! (see .codex/compatibility.md, Presentation leftovers): st.logo rides its
//! own ForwardMsg carrying metadata (the frontend's logo handler
//! dereferences activeScriptHash, so a metadata-less logo blanks the page);
//! st.help streams the {docString, type, name, value} help_info element;
//! st.skeleton streams the all-default Skeleton with a pixel height config;
//! st.pdf without the optional streamlit-pdf component raises the measured
//! StreamlitAPIException element (markdown, isStreamlitException).
use super::*;
use crate::StreamlitApi;
use crate::proto::element;
use crate::proto::forward_msg;

fn display2_entry(st: &Streamlit) -> Pin<Box<dyn Future<Output = ()> + '_>> {
    Box::pin(async move {
        // Mirrors tests/reference/display2_app.py.
        st.logo(crate::LogoOptions::new("🏠").small());
        st.help(crate::HelpOptions::new("Return the number of items in a container.", "builtin_function_or_method").name("len").value("builtins.len(obj, /)"));
        let _placeholder = st.skeleton(crate::SkeletonOptions::new().height(100));
        st.pdf("https://example.com/sample.pdf");
    })
}

#[actix_web::test]
async fn presentation_leftovers_match_the_measured_wire() {
    let listener = std::net::TcpListener::bind("127.0.0.1:0").unwrap();
    let address = listener.local_addr().unwrap();
    let server = HttpServer::new(move || App::new().app_data(web::Data::new(StreamlitServer::new(display2_entry, "127.0.0.1".into(), 0))).configure(configure_routes))
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

    let mut timeline: Vec<String> = Vec::new();
    loop {
        let message = receive(&mut stream).await;
        match message.r#type {
            Some(forward_msg::Type::NewSession(_)) => {}
            Some(forward_msg::Type::SessionStatusChanged(status)) if !status.script_is_running => break,
            Some(forward_msg::Type::Logo(logo)) => {
                // The reference stamps metadata on every enqueued ForwardMsg
                // (script_run_context.enqueue); without it the frontend's
                // logo handler throws and unmounts the whole page.
                let metadata = message.metadata.clone().expect("the logo message carries metadata");
                assert!(!metadata.active_script_hash.is_empty(), "logo metadata names the active script");
                assert!(!metadata.cacheable);
                assert!(metadata.delta_path.is_empty());
                timeline.push(format!(
                    "logo:{}:{}:{}",
                    logo.image,
                    crate::proto::logo::ImageType::try_from(logo.image_type).map(|kind| format!("{kind:?}")).unwrap_or_else(|_| logo.image_type.to_string()),
                    logo.size
                ));
            }
            Some(forward_msg::Type::Delta(delta)) => {
                let Some(delta::Type::NewElement(element)) = delta.r#type else { continue };
                let Some(kind) = element.r#type else { continue };
                let entry = match kind {
                    element::Type::HelpInfo(help) => {
                        let stretch = matches!(element.width_config, Some(ref config) if matches!(config.width_spec, Some(crate::proto::streamlit::width_config::WidthSpec::UseStretch(true))));
                        format!("help:{}:{}:{}:{}:stretch={}", help.doc_string, help.r#type, help.name, help.value, stretch)
                    }
                    element::Type::Skeleton(_) => {
                        let height = match element.height_config {
                            Some(ref config) => match config.height_spec {
                                Some(crate::proto::streamlit::height_config::HeightSpec::PixelHeight(pixels)) => format!("pixel:{pixels}"),
                                other => format!("other:{other:?}"),
                            },
                            None => "none".to_string(),
                        };
                        format!("skeleton:{height}")
                    }
                    element::Type::Exception(exception) => {
                        format!("exception:{}:{}:markdown={}:streamlit={}", exception.r#type, exception.message, exception.message_is_markdown, exception.is_streamlit_exception)
                    }
                    other => format!("{other:?}"),
                };
                timeline.push(entry);
            }
            Some(forward_msg::Type::ScriptFinished(status)) => assert_eq!(status, 0),
            Some(forward_msg::Type::SessionStatusChanged(_)) => {}
            other => panic!("unexpected lifecycle response: {other:?}"),
        }
    }
    let joined = timeline.join(" | ");
    assert_eq!(
        joined,
        "logo:🏠:Emoji:small | help:Return the number of items in a container.:builtin_function_or_method:len:builtins.len(obj, /):stretch=true | skeleton:pixel:100 | exception:streamlit.errors.StreamlitAPIException:The PDF viewer requires the `streamlit-pdf` component to be installed.\n\nPlease run `pip install streamlit[pdf]` to install it.\n\nFor more information, see the Streamlit PDF documentation at https://docs.streamlit.io/develop/api-reference/media/st.pdf.:markdown=true:streamlit=true"
    );

    drop(stream);
    handle.stop(false).await;
    task.await.unwrap().unwrap();
}
