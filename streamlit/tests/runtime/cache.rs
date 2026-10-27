//! Cache regressions against the measured Python 1.66.1 wire (see
//! .codex/compatibility.md, Caching): every miss streams an empty-element
//! transient (the cleared-spinner shape) at the call site and records the
//! function's element output; every hit replays those elements at their
//! original paths with no transient; st.cache_clear() drops the store so
//! the next call remisses and recomputes.
use super::*;

#[derive(serde::Deserialize)]
#[serde(deny_unknown_fields)]
struct NestedCacheCases {
    schema_version: u32,
    reference_version: String,
    stages: Vec<NestedCacheStage>,
}

#[derive(serde::Deserialize)]
#[serde(deny_unknown_fields)]
struct NestedCacheStage {
    name: String,
    round: u32,
    timeline: Vec<NestedCacheFrame>,
    returned: serde_json::Value,
    counters: serde_json::Value,
}

#[derive(serde::Deserialize)]
#[serde(deny_unknown_fields)]
struct NestedCacheFrame {
    frame_index: usize,
    delta_path: Vec<u32>,
    delta: serde_json::Value,
}

fn nested_cache_reference_delta(value: &serde_json::Value) -> TestResult<crate::proto::Delta> {
    use crate::proto::streamlit::{HeightConfig, TextAlignmentConfig, WidthConfig, height_config, width_config};
    use serde_json::json;

    if value.get("new_transient").is_some() {
        assert_eq!(value, &json!({"new_transient": {}}), "the frozen transient is exactly the cleared shape");
        return Ok(crate::proto::Delta {
            r#type: Some(delta::Type::NewTransient(Default::default())),
            ..Default::default()
        });
    }
    let element = value.get("new_element").ok_or("nested cache reference must contain a new element or transient")?;
    let mut expected = crate::proto::Element::default();
    if let Some(markdown) = element.get("markdown") {
        let body = markdown["body"].as_str().ok_or("reference markdown must include its body")?;
        assert_eq!(value, &json!({"new_element": {"markdown": {"body": body, "element_type": "NATIVE", "wrap": true}, "text_alignment_config": {"alignment": "LEFT"}}}));
        expected.r#type = Some(element::Type::Markdown(crate::proto::Markdown {
            body: body.into(),
            element_type: crate::proto::markdown::Type::Native as i32,
            wrap: Some(true),
            ..Default::default()
        }));
        expected.text_alignment_config = Some(TextAlignmentConfig {
            alignment: crate::proto::streamlit::text_alignment_config::Alignment::Left as i32,
        });
    } else if let Some(code) = element.get("code") {
        let text = code["code_text"].as_str().ok_or("reference code must include its text")?;
        assert_eq!(
            value,
            &json!({"new_element": {"code": {"code_text": text, "language": "json"}, "height_config": {"use_content": true}, "width_config": {"use_stretch": true}}})
        );
        expected.r#type = Some(element::Type::Code(crate::proto::Code {
            code_text: text.into(),
            language: "json".into(),
            ..Default::default()
        }));
        expected.height_config = Some(HeightConfig {
            height_spec: Some(height_config::HeightSpec::UseContent(true)),
        });
        expected.width_config = Some(WidthConfig {
            width_spec: Some(width_config::WidthSpec::UseStretch(true)),
        });
    } else if let Some(button) = element.get("button") {
        let id = button["id"].as_str().ok_or("reference button must include its id")?;
        assert_eq!(value, &json!({"new_element": {"button": {"id": id, "label": "Again", "type": "secondary"}, "width_config": {"use_content": true}}}));
        expected.r#type = Some(element::Type::Button(crate::proto::Button {
            id: id.into(),
            label: "Again".into(),
            r#type: "secondary".into(),
            ..Default::default()
        }));
        expected.width_config = Some(WidthConfig {
            width_spec: Some(width_config::WidthSpec::UseContent(true)),
        });
    } else {
        return Err("unrecognized frozen nested cache element".into());
    }
    Ok(crate::proto::Delta {
        r#type: Some(delta::Type::NewElement(expected)),
        ..Default::default()
    })
}

fn nested_cache_entry(st: &Streamlit) -> Pin<Box<dyn Future<Output = ()> + '_>> {
    Box::pin(async move {
        let result: TestResult = async {
            let state = st.session_state();
            let round = state.get::<u32>("round")?.unwrap_or(0) + 1;
            state.set("round", round)?;
            if round > 1 {
                st.write("leading");
            }
            let data_outer = std::cell::Cell::new(state.get::<u32>("data_outer")?.unwrap_or(0));
            let data_inner = std::cell::Cell::new(state.get::<u32>("data_inner")?.unwrap_or(0));
            let resource_outer = std::cell::Cell::new(state.get::<u32>("resource_outer")?.unwrap_or(0));
            let resource_inner = std::cell::Cell::new(state.get::<u32>("resource_inner")?.unwrap_or(0));
            let mut data_returns = serde_json::Map::new();
            for arg in ["A", "B"] {
                let value = st.cache_data("nested-data-outer").call(arg, |arg: &str| {
                    data_outer.set(data_outer.get() + 1);
                    st.write(format!("data-before-{arg}"));
                    let inner = st.cache_data("nested-data-inner").call(7_i64, |n| {
                        data_inner.set(data_inner.get() + 1);
                        st.write("data-inner");
                        n * 2
                    });
                    st.write(format!("data-after-{arg}"));
                    inner + 1
                });
                st.write(format!("data-return-{arg}={value}"));
                data_returns.insert(arg.into(), value.into());
            }
            let mut resource_returns = serde_json::Map::new();
            for arg in ["A", "B"] {
                let value = st.cache_resource("nested-resource-outer").call(arg, |arg: &str| {
                    resource_outer.set(resource_outer.get() + 1);
                    st.write(format!("resource-before-{arg}"));
                    let inner = st.cache_resource("nested-resource-inner").call(7_i64, |n| {
                        resource_inner.set(resource_inner.get() + 1);
                        st.write("resource-inner");
                        n * 2
                    });
                    st.write(format!("resource-after-{arg}"));
                    *inner + 1
                });
                st.write(format!("resource-return-{arg}={value}"));
                resource_returns.insert(arg.into(), (*value).into());
            }
            for (key, value) in [("data_outer", data_outer.get()), ("data_inner", data_inner.get()), ("resource_outer", resource_outer.get()), ("resource_inner", resource_inner.get())] {
                state.set(key, value)?;
            }
            let report = serde_json::json!({
                "counters": {"data_inner": data_inner.get(), "data_outer": data_outer.get(), "resource_inner": resource_inner.get(), "resource_outer": resource_outer.get()},
                "returned": {"data": data_returns, "resource": resource_returns},
                "round": round,
            });
            st.code(crate::pywire::py_dumps(&report), "json");
            st.button("Again");
            Ok(())
        }
        .await;
        assert!(result.is_ok(), "nested cache fixture must render: {result:?}");
    })
}

#[actix_web::test]
async fn nested_cache_hits_replay_inner_and_outer_output_at_shifted_paths() -> TestResult {
    let cases: NestedCacheCases = serde_json::from_str(include_str!("../../../tests/reference/reference-browser/cache-nested/cache-cases.json"))?;
    assert_eq!(cases.schema_version, 1);
    assert_eq!(cases.reference_version, "1.66.1");
    assert_eq!(cases.stages.iter().map(|stage| stage.name.as_str()).collect::<Vec<_>>(), ["load", "again"]);
    let listener = std::net::TcpListener::bind("127.0.0.1:0")?;
    let address = listener.local_addr()?;
    let server = HttpServer::new(move || App::new().app_data(web::Data::new(StreamlitServer::new(nested_cache_entry, "127.0.0.1".into(), 0))).configure(configure_routes))
        .workers(1)
        .listen(listener)?
        .run();
    let handle = server.handle();
    let server_task = actix_web::rt::spawn(server);
    let mut capture_task = actix_web::rt::spawn(async move {
        let mut socket = sessions::connect(address, None).await;
        let mut runs = Vec::new();
        let mut sessions = Vec::new();
        let mut finishes = Vec::new();
        let mut button_id = String::new();
        for round in 0..2 {
            let widgets = if round == 1 {
                vec![WidgetState {
                    id: button_id.clone(),
                    value: Some(widget_state::Value::TriggerValue(true)),
                }]
            } else {
                vec![]
            };
            send_binary(
                &mut socket,
                &BackMsg {
                    r#type: Some(back_msg::Type::RerunScript(ClientState {
                        widget_states: Some(WidgetStates { widgets }),
                        ..Default::default()
                    })),
                }
                .encode_to_vec(),
            )
            .await;
            let mut deltas = Vec::new();
            loop {
                let message = receive(&mut socket).await;
                match message.r#type {
                    Some(forward_msg::Type::NewSession(new)) => sessions.push(new.initialize.ok_or("NewSession must include initialization")?.session_id),
                    Some(forward_msg::Type::Delta(delta)) => {
                        if let Some(delta::Type::NewElement(element)) = delta.r#type.as_ref()
                            && let Some(element::Type::Button(button)) = element.r#type.as_ref()
                        {
                            button_id = button.id.clone();
                        }
                        deltas.push((message.metadata.ok_or("cache delta must include its path")?.delta_path, delta));
                    }
                    Some(forward_msg::Type::ScriptFinished(status)) => finishes.push(status),
                    Some(forward_msg::Type::SessionStatusChanged(status)) if !status.script_is_running => break,
                    _ => {}
                }
            }
            runs.push(deltas);
        }
        Ok::<_, Box<dyn std::error::Error>>((runs, sessions, finishes))
    });
    let captured = tokio::time::timeout(Duration::from_secs(10), &mut capture_task).await;
    if captured.is_err() {
        capture_task.abort();
        let _ = capture_task.await;
    }
    handle.stop(false).await;
    server_task.await??;
    let (runs, sessions, finishes) = captured???;

    assert_eq!(finishes, [0, 0]);
    assert_eq!(sessions.len(), 2);
    assert_eq!(sessions[0], sessions[1], "both rounds use one retained cache session");
    assert_eq!(runs.len(), cases.stages.len());
    let mut native_button_id = None;
    for (deltas, stage) in runs.iter().zip(&cases.stages) {
        // 只接受既有的领先根 AddBlock 差异；其余所有 delta 都参与比较。
        let deltas = match deltas.first() {
            Some((path, crate::proto::Delta { r#type: Some(delta::Type::AddBlock(block)), .. })) if path == &[0] && block.id.as_deref() == Some("main_container") => &deltas[1..],
            _ => deltas.as_slice(),
        };
        let code = deltas
            .iter()
            .find_map(|(_, delta)| match delta.r#type.as_ref() {
                Some(delta::Type::NewElement(element)) => match element.r#type.as_ref() {
                    Some(element::Type::Code(code)) => Some(code),
                    _ => None,
                },
                _ => None,
            })
            .ok_or("nested cache round must report return values and execution counters")?;
        let report: serde_json::Value = serde_json::from_str(&code.code_text)?;
        assert_eq!(report, serde_json::json!({"round": stage.round, "returned": stage.returned, "counters": stage.counters}));
        assert_eq!(deltas.len(), stage.timeline.len(), "every delta participates in stage {}", stage.name);
        for ((path, actual), frame) in deltas.iter().zip(&stage.timeline) {
            let expected = nested_cache_reference_delta(&frame.delta)?;
            let mut actual = actual.clone();
            if let Some(delta::Type::NewElement(element)) = actual.r#type.as_mut()
                && let Some(element::Type::Button(button)) = element.r#type.as_mut()
            {
                let digest = button.id.strip_prefix("$$ID-").and_then(|id| id.strip_suffix("-None")).ok_or("native Again button id must retain its opaque digest and None key suffix")?;
                assert_eq!(digest.len(), 32);
                assert!(digest.bytes().all(|byte| byte.is_ascii_hexdigit()));
                assert_eq!(native_button_id.get_or_insert_with(|| button.id.clone()), &button.id, "Again button id is stable across rounds");
                button.id = frame.delta["new_element"]["button"]["id"].as_str().ok_or("matching reference frame must contain a button id")?.into();
            }
            assert_eq!(path, &frame.delta_path, "stage {} frame {} path", stage.name, frame.frame_index);
            assert_eq!(actual.encode_to_vec(), expected.encode_to_vec(), "stage {} frame {} full delta: {actual:?} vs {expected:?}", stage.name, frame.frame_index);
        }
    }
    Ok(())
}

fn cache_entry(st: &Streamlit) -> Pin<Box<dyn Future<Output = ()> + '_>> {
    Box::pin(async move {
        // Mirrors tests/reference/cache_app.py.
        let runs = st.session_state().get::<i64>("runs").ok().flatten().unwrap_or(0) + 1;
        st.session_state().set("runs", runs).expect("valid state write");

        st.write(format!("runs={runs}"));

        let cached = st.cache_data("double").call(21, |n: i64| n * 2);
        st.write(format!("cached={cached}"));

        let other = st.cache_data("double").call(7, |n: i64| n * 2);
        st.write(format!("cached_other={other}"));

        let side = st.cache_data("side").call((), |()| {
            st.write("inside cached fn");
            1
        });
        st.write(format!("side={side}"));

        st.button("Again");

        if runs == 2 {
            st.cache_clear();
            st.write("cleared");
            let again = st.cache_data("double").call(21, |n: i64| n * 2);
            st.write(format!("cached_after_clear={again}"));
        }
    })
}

#[actix_web::test]
async fn cache_miss_transient_and_hit_replay_match_the_measured_wire() -> TestResult {
    let listener = std::net::TcpListener::bind("127.0.0.1:0")?;
    let address = listener.local_addr()?;
    let server = HttpServer::new(move || App::new().app_data(web::Data::new(StreamlitServer::new(cache_entry, "127.0.0.1".into(), 0))).configure(configure_routes))
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

    for run in 1..=2 {
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
        let mut timeline: Vec<(String, Vec<u32>)> = Vec::new();
        loop {
            let message = receive(&mut stream).await;
            let path = message.metadata.as_ref().map(|meta| meta.delta_path.clone()).unwrap_or_default();
            match message.r#type {
                Some(forward_msg::Type::NewSession(_)) => {}
                Some(forward_msg::Type::SessionStatusChanged(status)) if !status.script_is_running => break,
                Some(forward_msg::Type::Delta(delta)) => match delta.r#type {
                    Some(delta::Type::AddBlock(_)) => {}
                    Some(delta::Type::NewTransient(_)) => timeline.push(("transient".into(), path)),
                    Some(delta::Type::NewElement(element)) => match element.r#type {
                        Some(element::Type::Markdown(text)) => timeline.push((format!("markdown:{}", text.body), path)),
                        Some(element::Type::Button(button)) => timeline.push((format!("button:{}", button.label), path)),
                        Some(other) => panic!("unexpected element: {other:?}"),
                        None => {}
                    },
                    _ => {}
                },
                Some(forward_msg::Type::ScriptFinished(status)) => assert_eq!(status, 0),
                Some(forward_msg::Type::SessionStatusChanged(_)) => {}
                other => panic!("unexpected lifecycle response: {other:?}"),
            }
        }
        let describe = |timeline: &[(String, Vec<u32>)]| timeline.iter().map(|(kind, path)| format!("{kind}{path:?}")).collect::<Vec<_>>().join(" | ");
        if run == 1 {
            // Miss run: each miss streams its empty transient at the entry
            // path AFTER the function returns -- before the outside write
            // for an element-free function, after the emitted element for
            // one with side effects (the measured stage 01 shape).
            assert_eq!(
                describe(&timeline),
                "markdown:runs=1[0, 0] | transient[0, 1] | markdown:cached=42[0, 1] | transient[0, 2] | markdown:cached_other=14[0, 2] | markdown:inside cached fn[0, 3] | transient[0, 3] | markdown:side=1[0, 4] | button:Again[0, 5]",
            );
        } else {
            // Hit run: no transients; the function-internal element replays
            // at its recorded path AND consumes that slot like a live
            // render, so following writes land after it; clear() then
            // remisses double with a transient (the measured stage 02
            // shape).
            assert_eq!(
                describe(&timeline),
                "markdown:runs=2[0, 0] | markdown:cached=42[0, 1] | markdown:cached_other=14[0, 2] | markdown:inside cached fn[0, 3] | markdown:side=1[0, 4] | button:Again[0, 5] | markdown:cleared[0, 6] | transient[0, 7] | markdown:cached_after_clear=42[0, 7]",
            );
        }
    }

    drop(stream);
    handle.stop(false).await;
    task.await??;

    Ok(())
}

#[test]
fn cache_keys_are_argument_sensitive_and_clear_drops_entries() {
    use crate::SessionState;
    use crate::elements::common::RenderContext;

    let state = SessionState::default();
    state.begin_widgets(vec![]);
    let st = crate::Streamlit::with_session_state(state.clone());
    let (sender, _receiver) = tokio::sync::mpsc::unbounded_channel();
    st.app.lock().set_render_context(RenderContext::with_sender("unit".into(), sender));
    let computations = std::cell::Cell::new(0);
    let bump = |n: i64| {
        computations.set(computations.get() + 1);
        n * 2
    };
    assert_eq!(st.cache_data("double").call(21, bump), 42);
    assert_eq!(st.cache_data("double").call(21, bump), 42, "same argument hits");
    assert_eq!(computations.get(), 1);
    assert_eq!(st.cache_data("double").call(7, bump), 14, "another argument remisses");
    assert_eq!(computations.get(), 2);
    let shared = st.cache_resource("model").call((), |()| vec![1, 2, 3]);
    assert_eq!(*shared, vec![1, 2, 3]);
    let again = st.cache_resource("model").call((), |()| vec![9]);
    assert_eq!(*again, vec![1, 2, 3], "resources are shared, never rebuilt");
    assert_eq!(computations.get(), 2);
    st.cache_clear();
    assert_eq!(st.cache_data("double").call(21, bump), 42);
    assert_eq!(computations.get(), 3, "clear drops every entry");
}
