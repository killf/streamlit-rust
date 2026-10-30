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

const LOGO_STRING_REFERENCE: &str = include_str!("../../../tests/reference/reference-browser/code-logo-params/logo-strings/trace.json");

fn logo_strings_entry(st: &Streamlit) -> Pin<Box<dyn Future<Output = ()> + '_>> {
    Box::pin(async move {
        let result: TestResult = (|| {
            let reference: serde_json::Value = serde_json::from_str(LOGO_STRING_REFERENCE)?;
            let body = reference["elements"][0]["fields"]["body"].as_str().ok_or("missing logo input report")?;
            let inputs: serde_json::Value = serde_json::from_str(body)?;
            st.json(inputs.clone());
            for (index, case) in inputs["logo_cases"].as_array().ok_or("missing logo cases")?.iter().enumerate() {
                let image = case["image"].as_str().ok_or("missing logo image")?;
                let mut options = if index % 2 == 0 { crate::LogoOptions::new(image) } else { crate::LogoOptions::new(image.to_owned()) };
                options = options.icon_image(case["icon_image"].as_str().ok_or("missing logo icon")?.to_owned());
                options = match case["size"].as_str() {
                    Some("small") => options.small(),
                    Some("large") => options.large(),
                    Some("medium") => options,
                    _ => return Err("unknown logo size".into()),
                };
                if let Some(link) = case["link"].as_str() {
                    options = options.link(link);
                }
                st.logo(options);
            }
            Ok(())
        })();
        assert!(result.is_ok(), "logo fixture failed: {result:?}");
    })
}

#[actix_web::test]
async fn logo_unicode_strings_and_icon_images_match_frozen_reference() -> TestResult {
    // 1. 固定报告只提供输入，真实 WS 保留每个 Logo 的载荷与元数据形态。
    let listener = std::net::TcpListener::bind("127.0.0.1:0")?;
    let address = listener.local_addr()?;
    let server = HttpServer::new(move || App::new().app_data(web::Data::new(StreamlitServer::new(logo_strings_entry, "127.0.0.1".into(), 0))).configure(configure_routes))
        .workers(1)
        .listen(listener)?
        .run();
    let handle = server.handle();
    let task = actix_web::rt::spawn(server);
    let mut stream = sessions::connect(address, None).await;
    send_binary(
        &mut stream,
        &BackMsg {
            r#type: Some(back_msg::Type::RerunScript(ClientState {
                query_string: "case=logo-strings".into(),
                ..Default::default()
            })),
        }
        .encode_to_vec(),
    )
    .await;
    let mut observed = Vec::new();
    let mut metadata = Vec::new();
    let mut reports = Vec::new();
    let mut unexpected = 0;
    let finish = loop {
        let message = receive(&mut stream).await;
        match message.r#type {
            Some(forward_msg::Type::Logo(logo)) => {
                observed.push(logo);
                metadata.push(message.metadata.map(|metadata| (!metadata.active_script_hash.is_empty(), metadata.delta_path)).unwrap_or_default());
            }
            Some(forward_msg::Type::Delta(delta)) => {
                if let Some(delta::Type::NewElement(element)) = delta.r#type
                    && let Some(element::Type::Json(json)) = element.r#type
                {
                    reports.push(json.body);
                } else {
                    unexpected += 1;
                }
            }
            Some(forward_msg::Type::ScriptFinished(status)) => break status,
            _ => {}
        }
    };
    drop(stream);
    handle.stop(false).await;
    task.await??;

    // 2. 完整 Logo 期望取自原始帧，IMAGE 缺省与空 link 按 protobuf 语义解释。
    let reference: serde_json::Value = serde_json::from_str(LOGO_STRING_REFERENCE)?;
    let mut expected = Vec::new();
    for frame in reference["frames"].as_array().ok_or("missing logo frames")? {
        let Some(logo) = frame["message"].get("logo") else { continue };
        let kind = |field: &str| -> TestResult<i32> { Ok(crate::proto::logo::ImageType::from_str_name(logo[field].as_str().unwrap_or("IMAGE")).ok_or("unknown reference logo kind")? as i32) };
        expected.push(crate::proto::Logo {
            image: logo["image"].as_str().unwrap_or("").into(),
            link: logo["link"].as_str().unwrap_or("").into(),
            icon_image: logo["icon_image"].as_str().unwrap_or("").into(),
            size: logo["size"].as_str().unwrap_or("").into(),
            image_type: kind("image_type")?,
            icon_image_type: kind("icon_image_type")?,
        });
    }
    assert_eq!(finish, 0);
    assert_eq!(unexpected, 0);
    assert_eq!(reports, [reference["elements"][0]["fields"]["body"].as_str().ok_or("missing reference report")?]);
    assert_eq!(expected.len(), 18);
    assert!(metadata.iter().all(|(hash_present, path)| *hash_present && path.is_empty()));
    let mismatches = observed.iter().zip(&expected).filter(|(actual, expected)| actual != expected).count();
    assert_eq!(observed, expected, "{mismatches}/18 Logo payloads differ");
    Ok(())
}

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
async fn presentation_leftovers_match_the_measured_wire() -> TestResult {
    let listener = std::net::TcpListener::bind("127.0.0.1:0")?;
    let address = listener.local_addr()?;
    let server = HttpServer::new(move || App::new().app_data(web::Data::new(StreamlitServer::new(display2_entry, "127.0.0.1".into(), 0))).configure(configure_routes))
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
    task.await??;

    Ok(())
}
