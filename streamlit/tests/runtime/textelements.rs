//! Text-family regressions against the measured Python 1.66.1 wire (see
//! .codex/compatibility.md, Text elements): plain text is a wrapped,
//! content-width Text element; latex is markdown with the formula wrapped
//! in $$ display-math blocks; html stretches; the iframe scrolls with a
//! 400 px default height; snow is a one-shot; st.echo takes an empty
//! placeholder slot and retro-fills it with the code; st.exception shows
//! the caller-supplied type, message and trace in the stretch-width box.
use super::*;
use crate::ExceptionOptions;
use crate::proto;

const JSON_STRING_REFERENCE: &str = include_str!("../../../tests/reference/reference-browser/json-badge-params/strings/trace.json");

fn json_strings_entry(st: &Streamlit) -> Pin<Box<dyn Future<Output = ()> + '_>> {
    Box::pin(async move {
        let result: TestResult = (|| {
            let reference: serde_json::Value = serde_json::from_str(JSON_STRING_REFERENCE)?;
            let body = reference["elements"][0]["fields"]["body"].as_str().ok_or("missing JSON input report")?;
            let inputs: serde_json::Value = serde_json::from_str(body)?;
            st.json(inputs.clone());
            for text in inputs["string_cases"].as_array().ok_or("missing string cases")? {
                st.json(text.as_str().ok_or("string input required")?);
                st.json_expanded(text.clone(), false);
            }
            for value in inputs["controls"].as_array().ok_or("missing structured controls")? {
                st.json(value.clone());
            }
            Ok(())
        })();
        assert!(result.is_ok(), "JSON fixture failed: {result:?}");
    })
}

#[actix_web::test]
async fn json_strings_are_passthrough_while_structured_values_are_serialized() -> TestResult {
    // 1. 固定 Python 报告提供输入，同时覆盖 &str 和 Value::String 两个调用形态。
    let listener = std::net::TcpListener::bind("127.0.0.1:0")?;
    let address = listener.local_addr()?;
    let server = HttpServer::new(move || App::new().app_data(web::Data::new(StreamlitServer::new(json_strings_entry, "127.0.0.1".into(), 0))).configure(configure_routes))
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
                query_string: "case=strings".into(),
                ..Default::default()
            })),
        }
        .encode_to_vec(),
    )
    .await;
    let mut observed = Vec::new();
    let finish = loop {
        let message = receive(&mut stream).await;
        let path = message.metadata.as_ref().map(|metadata| metadata.delta_path.clone()).unwrap_or_default();
        match message.r#type {
            Some(forward_msg::Type::Delta(delta)) => {
                if let Some(delta::Type::NewElement(element)) = delta.r#type {
                    let stretch = matches!(element.width_config.and_then(|config| config.width_spec), Some(proto::streamlit::width_config::WidthSpec::UseStretch(true)));
                    let json = match element.r#type {
                        Some(element::Type::Json(json)) => Some(json),
                        _ => None,
                    };
                    observed.push((path, json, stretch));
                } else {
                    observed.push((path, None, false));
                }
            }
            Some(forward_msg::Type::ScriptFinished(status)) => break status,
            _ => {}
        }
    };
    drop(stream);
    handle.stop(false).await;
    task.await??;

    // 2. 输出期望来自原始元素帧，空 body/false 按 protobuf 缺省值处理。
    let reference: serde_json::Value = serde_json::from_str(JSON_STRING_REFERENCE)?;
    let mut expected = Vec::new();
    for frame in reference["frames"].as_array().ok_or("missing JSON frames")? {
        let message = &frame["message"];
        let Some(delta) = message.get("delta") else { continue };
        let element = &delta["new_element"];
        let json = element.get("json").ok_or("unexpected reference JSON element")?;
        let path: Vec<u32> = serde_json::from_value(message["metadata"]["delta_path"].clone())?;
        let wire = proto::Json {
            body: json["body"].as_str().unwrap_or("").into(),
            expanded: json["expanded"].as_bool().unwrap_or(false),
            max_expand_depth: json["max_expand_depth"].as_i64().map(i32::try_from).transpose()?,
        };
        expected.push((path, Some(wire), element["width_config"]["use_stretch"].as_bool().unwrap_or(false)));
    }
    assert_eq!(finish, 0);
    assert_eq!(expected.len(), 36);
    assert_eq!(observed, expected);
    Ok(())
}

const JSON_NUMBER_REFERENCE: &str = include_str!("../../../tests/reference/reference-browser/json-badge-params/numbers/trace.json");

fn json_numbers_entry(st: &Streamlit) -> Pin<Box<dyn Future<Output = ()> + '_>> {
    Box::pin(async move {
        let result: TestResult = (|| {
            let reference: serde_json::Value = serde_json::from_str(JSON_NUMBER_REFERENCE)?;
            let inputs: serde_json::Value = serde_json::from_str(reference["elements"][0]["fields"]["body"].as_str().ok_or("missing number inputs")?)?;
            st.json(inputs.clone());
            for text in inputs["number_cases"].as_array().ok_or("missing number cases")? {
                let value: f64 = text.as_str().ok_or("number text required")?.parse()?;
                if value.is_finite() {
                    st.json(value);
                    st.json([value]);
                }
            }
            Ok(())
        })();
        assert!(result.is_ok(), "JSON numeric fixture failed: {result:?}");
    })
}

#[actix_web::test]
async fn finite_json_numbers_match_python_wire() -> TestResult {
    // 1. 真实服务器验证标量及嵌套有限数值；非有限值的已知差异仍独立开放。
    let listener = std::net::TcpListener::bind("127.0.0.1:0")?;
    let address = listener.local_addr()?;
    let server = HttpServer::new(move || App::new().app_data(web::Data::new(StreamlitServer::new(json_numbers_entry, "127.0.0.1".into(), 0))).configure(configure_routes))
        .workers(1)
        .listen(listener)?
        .run();
    let handle = server.handle();
    let task = actix_web::rt::spawn(server);
    let mut stream = sessions::connect(address, None).await;
    send_binary(
        &mut stream,
        &BackMsg {
            r#type: Some(back_msg::Type::RerunScript(ClientState::default())),
        }
        .encode_to_vec(),
    )
    .await;
    let mut observed = Vec::new();
    let finish = loop {
        let message = receive(&mut stream).await;
        let path = message.metadata.as_ref().map(|metadata| metadata.delta_path.clone()).unwrap_or_default();
        match message.r#type {
            Some(forward_msg::Type::Delta(delta)) => {
                let Some(delta::Type::NewElement(element)) = delta.r#type else { panic!("unexpected numeric delta") };
                let Some(element::Type::Json(json)) = element.r#type else { panic!("unexpected numeric element") };
                let stretch = matches!(element.width_config.and_then(|config| config.width_spec), Some(proto::streamlit::width_config::WidthSpec::UseStretch(true)));
                observed.push((path, json, stretch));
            }
            Some(forward_msg::Type::ScriptFinished(status)) => break status,
            _ => {}
        }
    };
    drop(stream);
    handle.stop(false).await;
    task.await??;

    // 2. Python 门已把消息投影绑定到原始帧；比较 33 个元素的路径、深度 presence 和宽度。
    let reference: serde_json::Value = serde_json::from_str(JSON_NUMBER_REFERENCE)?;
    let mut expected = Vec::new();
    for frame in reference["frames"].as_array().ok_or("missing numeric frames")? {
        if frame["direction"] != "server->client" {
            continue;
        }
        let message = &frame["message"];
        let Some(delta) = message.get("delta") else { continue };
        let element = &delta["new_element"];
        let json = element.get("json").ok_or("unexpected numeric reference element")?;
        let path: Vec<u32> = serde_json::from_value(message["metadata"]["delta_path"].clone())?;
        let wire = proto::Json {
            body: json["body"].as_str().ok_or("missing number body")?.into(),
            expanded: json["expanded"].as_bool().unwrap_or(false),
            max_expand_depth: json["max_expand_depth"].as_i64().map(i32::try_from).transpose()?,
        };
        expected.push((path, wire, element["width_config"]["use_stretch"].as_bool().unwrap_or(false)));
    }
    assert_eq!(expected.len(), 39, "19 scalar/array pairs and the input report");
    assert_eq!(finish, 0);
    assert_eq!(observed.len(), 33, "16 finite scalar/array pairs and the input report");
    assert_eq!(observed, expected[..33]);
    Ok(())
}

const CODE_TEXT_REFERENCE: &str = include_str!("../../../tests/reference/reference-browser/code-logo-params/code-text/trace.json");

fn code_text_entry(st: &Streamlit) -> Pin<Box<dyn Future<Output = ()> + '_>> {
    Box::pin(async move {
        let result: TestResult = (|| {
            let reference: serde_json::Value = serde_json::from_str(CODE_TEXT_REFERENCE)?;
            let inputs: serde_json::Value = serde_json::from_str(reference["elements"][0]["fields"]["body"].as_str().ok_or("missing code input report")?)?;
            st.json(inputs.clone());
            for case in inputs["code_cases"].as_array().ok_or("missing code cases")? {
                let width = match case["width"].as_str() {
                    Some("stretch") => crate::ElementWidth::Stretch,
                    Some("content") => crate::ElementWidth::Content,
                    None => crate::ElementWidth::Value(i32::try_from(case["width"].as_i64().ok_or("missing code width")?)?),
                    _ => return Err("unknown code width".into()),
                };
                let height = match case["height"].as_str() {
                    Some("stretch") => crate::ElementHeight::Stretch,
                    Some("content") => crate::ElementHeight::Content,
                    None => crate::ElementHeight::Value(i32::try_from(case["height"].as_i64().ok_or("missing code height")?)?),
                    _ => return Err("unknown code height".into()),
                };
                st.code_options(
                    crate::CodeOptions::new(case["body"].as_str().ok_or("missing code body")?, case["language"].as_str().unwrap_or_default())
                        .line_numbers(case["line_numbers"].as_bool().ok_or("missing line_numbers")?)
                        .wrap_lines(case["wrap_lines"].as_bool().ok_or("missing wrap_lines")?)
                        .width(width)
                        .height(height),
                );
            }
            Ok(())
        })();
        assert!(result.is_ok(), "code fixture failed: {result:?}");
    })
}

#[actix_web::test]
async fn code_text_language_and_layout_match_frozen_reference() -> TestResult {
    // 1. 公共 builder 经生产服务器发出代码及布局，输入报告与输出期望分开读取。
    let listener = std::net::TcpListener::bind("127.0.0.1:0")?;
    let address = listener.local_addr()?;
    let server = HttpServer::new(move || App::new().app_data(web::Data::new(StreamlitServer::new(code_text_entry, "127.0.0.1".into(), 0))).configure(configure_routes))
        .workers(1)
        .listen(listener)?
        .run();
    let handle = server.handle();
    let task = actix_web::rt::spawn(server);
    let mut stream = sessions::connect(address, None).await;
    send_binary(
        &mut stream,
        &BackMsg {
            r#type: Some(back_msg::Type::RerunScript(ClientState::default())),
        }
        .encode_to_vec(),
    )
    .await;
    let mut observed = Vec::new();
    let finish = loop {
        let message = receive(&mut stream).await;
        let path = message.metadata.as_ref().map(|metadata| metadata.delta_path.clone()).unwrap_or_default();
        match message.r#type {
            Some(forward_msg::Type::Delta(delta)) => {
                let Some(delta::Type::NewElement(element)) = delta.r#type else { panic!("unexpected code delta") };
                observed.push((path, element));
            }
            Some(forward_msg::Type::ScriptFinished(status)) => break status,
            _ => {}
        }
    };
    drop(stream);
    handle.stop(false).await;
    task.await??;

    // 2. 参考消息投影由 Python 门绑定原始 protobuf；比较完整 Element 与路径。
    let reference: serde_json::Value = serde_json::from_str(CODE_TEXT_REFERENCE)?;
    let mut expected = Vec::new();
    for frame in reference["frames"].as_array().ok_or("missing code reference frames")? {
        let message = &frame["message"];
        let Some(delta) = message.get("delta") else { continue };
        let element = &delta["new_element"];
        let kind = if let Some(code) = element.get("code") {
            element::Type::Code(proto::Code {
                code_text: code["code_text"].as_str().unwrap_or_default().into(),
                language: code["language"].as_str().ok_or("missing reference code language")?.into(),
                show_line_numbers: code["show_line_numbers"].as_bool().unwrap_or(false),
                wrap_lines: code["wrap_lines"].as_bool().unwrap_or(false),
            })
        } else {
            let json = element.get("json").ok_or("unexpected code reference element")?;
            element::Type::Json(proto::Json {
                body: json["body"].as_str().ok_or("missing report body")?.into(),
                expanded: true,
                max_expand_depth: None,
            })
        };
        let width = &element["width_config"];
        let width_spec = if let Some(pixels) = width["pixel_width"].as_u64() {
            proto::streamlit::width_config::WidthSpec::PixelWidth(u32::try_from(pixels)?)
        } else if width["use_content"] == true {
            proto::streamlit::width_config::WidthSpec::UseContent(true)
        } else if width["use_stretch"] == true {
            proto::streamlit::width_config::WidthSpec::UseStretch(true)
        } else {
            return Err("missing reference width".into());
        };
        let height_config = if let Some(height) = element.get("height_config") {
            let height_spec = if let Some(pixels) = height["pixel_height"].as_u64() {
                proto::streamlit::height_config::HeightSpec::PixelHeight(u32::try_from(pixels)?)
            } else if height["use_content"] == true {
                proto::streamlit::height_config::HeightSpec::UseContent(true)
            } else if height["use_stretch"] == true {
                proto::streamlit::height_config::HeightSpec::UseStretch(true)
            } else {
                return Err("missing reference height".into());
            };
            Some(proto::streamlit::HeightConfig { height_spec: Some(height_spec) })
        } else {
            None
        };
        let path: Vec<u32> = serde_json::from_value(message["metadata"]["delta_path"].clone())?;
        expected.push((
            path,
            proto::Element {
                r#type: Some(kind),
                width_config: Some(proto::streamlit::WidthConfig { width_spec: Some(width_spec) }),
                height_config,
                ..Default::default()
            },
        ));
    }
    assert_eq!(finish, 0);
    assert_eq!(expected.len(), 28);
    assert_eq!(observed, expected);
    Ok(())
}

fn code_height_entry(st: &Streamlit) -> Pin<Box<dyn Future<Output = ()> + '_>> {
    Box::pin(async move {
        let result: TestResult = (|| {
            let height: i32 = st.query_params().get("code_height").ok_or("missing test height")?.parse()?;
            st.code_options(crate::CodeOptions::new("print('same body')", "python").height(height).width(360));
            Ok(())
        })();
        assert!(result.is_ok(), "code-height fixture failed: {result:?}");
    })
}

#[actix_web::test]
async fn code_height_changes_on_one_connection_invalidate_the_element_hash() -> TestResult {
    // 1. 同一连接、同一路径及相同代码，只让高度往返变化。
    let listener = std::net::TcpListener::bind("127.0.0.1:0")?;
    let address = listener.local_addr()?;
    let server = HttpServer::new(move || App::new().app_data(web::Data::new(StreamlitServer::new(code_height_entry, "127.0.0.1".into(), 0))).configure(configure_routes))
        .workers(1)
        .listen(listener)?
        .run();
    let handle = server.handle();
    let task = actix_web::rt::spawn(server);
    let mut stream = sessions::connect(address, None).await;
    let mut hashes = Vec::new();
    for height in [120, 240, 120] {
        send_binary(
            &mut stream,
            &BackMsg {
                r#type: Some(back_msg::Type::RerunScript(ClientState {
                    query_string: format!("code_height={height}"),
                    ..Default::default()
                })),
            }
            .encode_to_vec(),
        )
        .await;
        let mut codes = Vec::new();
        let finish = loop {
            let message = receive(&mut stream).await;
            if let Some(forward_msg::Type::ScriptFinished(status)) = message.r#type {
                break status;
            }
            if let Some(forward_msg::Type::Delta(delta)) = message.r#type {
                let metadata = message.metadata.ok_or("missing code metadata")?;
                assert_eq!(metadata.delta_path, [0, 0]);
                assert!(!metadata.cacheable, "full messages still require correct element identity");
                let Some(delta::Type::NewElement(element)) = delta.r#type else { panic!("unexpected code-height delta") };
                let Some(element::Type::Code(code)) = element.r#type else { panic!("unexpected code-height element") };
                assert_eq!(code.code_text, "print('same body')");
                assert_eq!(element.height_config.and_then(|value| value.height_spec), Some(proto::streamlit::height_config::HeightSpec::PixelHeight(u32::try_from(height)?)));
                codes.push(message.hash);
            }
        };
        assert_eq!(finish, 0);
        assert_eq!(codes.len(), 1);
        hashes.push(codes.pop().ok_or("missing code-height output")?);
    }
    drop(stream);
    handle.stop(false).await;
    task.await??;

    // 2. Python 参考的 A→B→A 内容身份关系，保证前端不复用旧高度。
    assert!(!hashes[0].is_empty());
    assert_ne!(hashes[0], hashes[1]);
    assert_eq!(hashes[0], hashes[2]);
    Ok(())
}

fn textelements_entry(st: &Streamlit) -> Pin<Box<dyn Future<Output = ()> + '_>> {
    Box::pin(async move {
        // Mirrors tests/reference/textelements_app.py.
        st.text("plain text");
        st.sub_header("Sub header");
        st.latex("a^2 + b^2 = c^2");
        st.html("<p><b>bold</b> html</p>");
        st.iframe("https://example.com");
        st.snow();
        st.echo("st.write(\"echoed inside\")", |st| {
            st.write("echoed inside");
        });
        st.exception(ExceptionOptions::new("ValueError", "boom").trace("streamlit-rust: the application raised ValueError: boom"));
    })
}

#[actix_web::test]
async fn text_family_elements_match_the_measured_wire() -> TestResult {
    let listener = std::net::TcpListener::bind("127.0.0.1:0")?;
    let address = listener.local_addr()?;
    let server = HttpServer::new(move || App::new().app_data(web::Data::new(StreamlitServer::new(textelements_entry, "127.0.0.1".into(), 0))).configure(configure_routes))
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
            assert!(response.len() < 8192);
        }
        Ok::<_, Box<dyn std::error::Error>>(String::from_utf8(response)?.to_ascii_lowercase())
    })
    .await??;
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
                Some(delta::Type::AddBlock(_)) => {}
                Some(delta::Type::NewElement(element)) => {
                    let kind = element.r#type.as_ref().map(|kind| match kind {
                        element::Type::Text(text) => format!("text:{}{:?}{:?}", text.body, text.wrap, path),
                        element::Type::Heading(heading) => format!("heading:{}:{}{:?}", heading.tag, heading.body, path),
                        element::Type::Markdown(markdown) => format!("markdown:{:?}{:?}", markdown.body, path),
                        element::Type::Html(html) => format!("html:{}{:?}", html.body, path),
                        element::Type::Iframe(iframe) => {
                            let source = match iframe.r#type.as_ref() {
                                Some(proto::i_frame::Type::Src(url)) => format!("src:{url}"),
                                Some(proto::i_frame::Type::Srcdoc(html)) => format!("srcdoc:{html}"),
                                None => "none".to_string(),
                            };
                            let height = element.height_config.and_then(|config| config.height_spec).map(|spec| match spec {
                                proto::streamlit::height_config::HeightSpec::PixelHeight(pixels) => format!("px:{pixels}"),
                                proto::streamlit::height_config::HeightSpec::UseContent(_) => "content".to_string(),
                                proto::streamlit::height_config::HeightSpec::UseStretch(_) => "stretch".to_string(),
                                other => format!("{other:?}"),
                            });
                            format!("iframe:{}:scroll:{}:h{:?}:{:?}", source, iframe.scrolling, height, path)
                        }
                        element::Type::Snow(snow) => format!("snow:{}:one-shot:{:?}{:?}", snow.show, element.has_one_shot_effect, path),
                        element::Type::Empty(_) => format!("empty{:?}", path),
                        element::Type::Code(code) => format!("code:{}:{}{:?}", code.code_text, code.language, path),
                        element::Type::Exception(exception) => format!("exception:{}:{}:{:?}{:?}", exception.r#type, exception.message, exception.stack_trace, path),
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
        "text:plain textSome(true)[0, 0] | heading:h3:Sub header[0, 1] | markdown:\"$$\\na^2 + b^2 = c^2\\n$$\"[0, 2] | html:<p><b>bold</b> html</p>[0, 3] | iframe:src:https://example.com:scroll:true:hSome(\"px:400\"):[0, 4] | snow:true:one-shot:Some(true)[0, 5] | empty[0, 6] | markdown:\"echoed inside\"[0, 7] | code:st.write(\"echoed inside\"):python[0, 6] | exception:ValueError:boom:[\"streamlit-rust: the application raised ValueError: boom\"][0, 8]"
    );
    assert_eq!(timeline.len(), 10, "exactly the ten measured element frames");

    drop(stream);
    handle.stop(false).await;
    task.await??;

    Ok(())
}
