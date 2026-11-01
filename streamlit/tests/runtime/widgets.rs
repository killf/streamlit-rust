//! Real WS value types come from the pinned Python closed-loop browser capture.
//! Parameter expectations below are docs/native contracts pending the fuller oracle.
use super::*;
use crate::proto;
use crate::{ButtonOptions, CheckboxOptions, InputWidgets, SelectboxOptions, SliderOptions};
use serde_json::{Value, json};
use std::collections::HashMap;

fn widgets_entry(st: &Streamlit) -> Pin<Box<dyn Future<Output = ()> + '_>> {
    Box::pin(async move {
        let result: TestResult = async {
            let callback = |st: &Streamlit| {
                let result = (|| -> TestResult {
                    let state = st.session_state();
                    let all_values = json!({
                        "group": state.get::<String>("group")?,
                        "amount": state.get::<i64>("amount")?,
                        "include": state.get::<bool>("include")?,
                    });
                    state.set("callback_values", all_values)?;
                    let n = state.get::<u64>("callbacks")?.unwrap_or(0);
                    state.set("callbacks", n + 1)?;
                    Ok(())
                })();
                assert!(result.is_ok(), "widget callback fixture failed: {result:?}");
            };
            let state = st.session_state();
            let group = st.selectbox(SelectboxOptions::new("Group by", ["category", "region", "channel"]).key("group").on_change(callback))?;
            let amount = st.slider(SliderOptions::new("Minimum amount", 0_i64).max(200).step(10).key("amount").on_change(callback))?;
            let include = st.checkbox(CheckboxOptions::new("Include unknown region").value(true).key("include").on_change(callback))?;
            let click = st.try_button(ButtonOptions::new("Pulse").key("pulse").on_click(callback))?;
            st.write(format!(
                "values={}",
                json!({
                    "group": group, "amount": amount, "include": include, "click": click,
                    "callbacks": state.get::<u64>("callbacks")?.unwrap_or(0),
                    "callback_values": state.get::<Value>("callback_values")?,
                })
            ));
            Ok(())
        }
        .await;
        assert!(result.is_ok(), "widgets_entry fixture failed: {result:?}");
    })
}

struct Run {
    id: String,
    inputs: HashMap<String, String>,
    values: Value,
    input_count: usize,

    // 本轮框架异常；成功轮保持为空。
    exceptions: Vec<proto::Exception>,
}

async fn rerun(stream: &mut TcpStream, widgets: Vec<WidgetState>) -> TestResult<Run> {
    let request = BackMsg {
        r#type: Some(back_msg::Type::RerunScript(ClientState {
            widget_states: Some(WidgetStates { widgets }),
            ..Default::default()
        })),
    };
    send_binary(stream, &request.encode_to_vec()).await;
    let mut run = Run {
        id: String::new(),
        inputs: HashMap::new(),
        values: Value::Null,
        input_count: 0,
        exceptions: Vec::new(),
    };
    let mut finished = false;
    loop {
        match receive(stream).await.r#type {
            Some(forward_msg::Type::NewSession(new)) => run.id = new.initialize.ok_or("NewSession must include initialization")?.session_id,
            Some(forward_msg::Type::Delta(proto::Delta { r#type: Some(delta::Type::NewElement(wire)), .. })) => {
                if matches!(&wire.r#type, Some(element::Type::Slider(_) | element::Type::Selectbox(_) | element::Type::Checkbox(_) | element::Type::Button(_))) {
                    run.input_count += 1;
                }
                match wire.r#type {
                    Some(element::Type::Selectbox(value)) => {
                        run.inputs.insert("group".into(), value.id);
                    }
                    Some(element::Type::Slider(value)) => {
                        let key = match value.label.as_str() {
                            "Rate" => "rate",
                            "Float range" => "range",
                            "Integer range" => "ints",
                            _ => "amount",
                        };
                        run.inputs.insert(key.into(), value.id);
                    }
                    Some(element::Type::Checkbox(value)) => {
                        let key = if matches!(value.label.as_str(), "cb0" | "cb1" | "tg0" | "tg1" | "target") { value.label } else { "include".into() };
                        run.inputs.insert(key, value.id);
                    }
                    Some(element::Type::TextInput(value)) if matches!(value.label.as_str(), "peer" | "target") => {
                        run.inputs.insert(value.label, value.id);
                    }
                    Some(element::Type::TextArea(value)) if value.label == "target" => {
                        run.inputs.insert(value.label, value.id);
                    }
                    Some(element::Type::Button(value)) => {
                        run.inputs.insert("pulse".into(), value.id);
                    }
                    Some(element::Type::DateInput(value)) => {
                        run.inputs.insert(value.label, value.id);
                    }
                    Some(element::Type::TimeInput(value)) => {
                        run.inputs.insert(value.label, value.id);
                    }
                    Some(element::Type::DateTimeInput(value)) => {
                        run.inputs.insert(value.label, value.id);
                    }
                    Some(element::Type::Markdown(value)) => {
                        if let Some(json) = value.body.strip_prefix("values=") {
                            run.values = serde_json::from_str(json)?;
                        }
                    }
                    Some(element::Type::Exception(error)) => run.exceptions.push(error),
                    _ => (),
                }
            }
            Some(forward_msg::Type::ScriptFinished(status)) => {
                assert_eq!(status, 0);
                assert!(!finished);
                finished = true;
            }
            Some(forward_msg::Type::SessionStatusChanged(status)) if !status.script_is_running => {
                assert!(finished);
                break;
            }
            _ => (),
        }
    }
    assert!(!run.id.is_empty());
    if run.values.is_null() {
        assert!(!run.exceptions.is_empty());
    } else {
        assert!(run.exceptions.is_empty());
    }
    Ok(run)
}

fn temporal_lexical_entry(st: &Streamlit) -> Pin<Box<dyn Future<Output = ()> + '_>> {
    Box::pin(async move {
        let result: TestResult = async {
            let day = chrono::NaiveDate::from_ymd_opt(2025, 3, 15).ok_or("reference date")?;
            let min = chrono::NaiveDate::from_ymd_opt(2024, 1, 1).ok_or("minimum")?;
            let max = chrono::NaiveDate::from_ymd_opt(2026, 12, 31).ok_or("maximum")?;
            let minute = chrono::NaiveTime::from_hms_opt(12, 30, 0).ok_or("minute default")?;
            let second = chrono::NaiveTime::from_hms_opt(12, 30, 45).ok_or("second default")?;
            let changed = |kind: &'static str| {
                move |st: &Streamlit| {
                    let state = st.session_state();
                    let mut calls = state.get::<Vec<Value>>("lexical_calls").expect("callback log").unwrap_or_default();
                    calls.push(json!([kind, state.get::<Value>(kind).expect("callback input")]));
                    state.set("lexical_calls", calls).expect("save callback log");
                }
            };

            let date = st.date_input(crate::DateInputOptions::new("date").value(day).min(min).max(max).key("date").on_change(changed("date")))?;
            let crate::DateSelection::Single(date) = date else { return Err("single date expected".into()) };
            let datetime = st.datetime_input(
                crate::DateTimeInputOptions::new("datetime")
                    .value(day.and_time(minute))
                    .min(min.and_time(chrono::NaiveTime::MIN))
                    .max(max.and_hms_opt(23, 59, 0).ok_or("final minute")?)
                    .key("datetime")
                    .on_change(changed("datetime")),
            )?;
            let minute = st.time_input(crate::TimeInputOptions::new("minute").value(minute).step(900).key("minute").on_change(changed("minute")))?;
            let second = st.time_input(crate::TimeInputOptions::new("second").value(second).step(1).key("second").on_change(changed("second")))?;
            st.write(format!(
                "values={}",
                json!({
                    "date":date.to_string(), "datetime":datetime.map(|value|value.format("%Y-%m-%dT%H:%M").to_string()),
                    "minute":minute.map(|value|value.format("%H:%M").to_string()), "second":second.map(|value|value.format("%H:%M:%S").to_string()),
                    "calls":st.session_state().get::<Vec<Value>>("lexical_calls")?.unwrap_or_default(),
                })
            ));
            Ok(())
        }
        .await;
        assert!(result.is_ok(), "lexical fixture failed: {result:?}");
    })
}

#[actix_web::test]
async fn temporal_lexical_values_and_callbacks_match_sdk_over_real_ws() -> TestResult {
    let reference: Value = serde_json::from_str(include_str!("../../../tests/reference/reference-browser/temporal-params/trace.json"))?;
    let cases = reference["lexical_reference"]["cases"].as_array().ok_or("lexical cases")?;
    let listener = std::net::TcpListener::bind("127.0.0.1:0")?;
    let address = listener.local_addr()?;
    let server = HttpServer::new(move || App::new().app_data(web::Data::new(StreamlitServer::new(temporal_lexical_entry, "127.0.0.1".into(), 0))).configure(configure_routes))
        .workers(1)
        .listen(listener)?
        .run();
    let handle = server.handle();
    let task = actix_web::rt::spawn(server);
    let captured = tokio::time::timeout(Duration::from_secs(45), async {
        let mut runs = Vec::new();
        for case in cases {
            let mut socket = sessions::connect(address, None).await;
            let initial = rerun(&mut socket, vec![]).await?;
            let kind = case["kind"].as_str().ok_or("kind")?;
            let input = case["input"].as_str().ok_or("input")?;
            let wire = if matches!(kind, "date" | "datetime") {
                widget_state::Value::StringArrayValue(proto::StringArray { data: vec![input.into()] })
            } else {
                widget_state::Value::StringValue(input.into())
            };
            let changed = rerun(
                &mut socket,
                vec![WidgetState {
                    id: initial.inputs[kind].clone(),
                    value: Some(wire),
                }],
            )
            .await?;
            sessions::disconnect(socket).await;
            runs.push((initial, changed));
        }
        Ok::<_, Box<dyn std::error::Error>>(runs)
    })
    .await;
    handle.stop(false).await;
    task.await??;
    let runs = captured??;
    assert_eq!(cases.len(), 75);
    assert_eq!(runs.len(), cases.len());

    for ((initial, changed), case) in runs.into_iter().zip(cases) {
        let kind = case["kind"].as_str().ok_or("kind")?;
        let expected = if matches!(kind, "date" | "datetime") { &case["expected"][0] } else { &case["expected"] };
        assert_eq!(initial.inputs.len(), 4);
        assert_eq!(changed.inputs, initial.inputs);
        assert_eq!(changed.id, initial.id);
        assert_eq!(&changed.values[kind], expected, "{}", case["name"]);
        let calls = if initial.values[kind] == *expected { json!([]) } else { json!([[kind, expected]]) };
        assert_eq!(changed.values["calls"], calls, "{}", case["name"]);
        for peer in ["date", "datetime", "minute", "second"].into_iter().filter(|peer| *peer != kind) {
            assert_eq!(changed.values[peer], initial.values[peer], "{}: peer {peer}", case["name"]);
        }
    }
    Ok(())
}

fn late_registration_entry(st: &Streamlit) -> Pin<Box<dyn Future<Output = ()> + '_>> {
    Box::pin(async move {
        let result: TestResult = async {
            let changed = |source: &'static str| {
                move |st: &Streamlit| {
                    let state = st.session_state();
                    let mut calls = state.get::<Vec<Value>>("late_calls").expect("callback log").unwrap_or_default();
                    let peer = state.get::<Value>("peer").expect("peer state").expect("registered peer");
                    let target = state.get::<Value>("target").expect("target state").unwrap_or_else(|| Value::from("__missing__"));
                    calls.push(json!([source, peer, target]));
                    state.set("late_calls", calls).expect("save callbacks");
                }
            };
            let peer = st.text_input(crate::TextInputOptions::new("peer").value("closed").key("peer").on_change(changed("peer")))?.ok_or("peer text")?;
            let target = if peer == "closed" {
                Value::from("__hidden__")
            } else {
                let fields: Vec<_> = peer.split(':').collect();
                assert_eq!(fields.len(), 3);
                let disabled = fields[2] == "disabled";
                match fields[0] {
                    "checkbox" => Value::from(st.checkbox(CheckboxOptions::new("target").value(fields[1] == "true").key("target").disabled(disabled).on_change(changed("target")))?),
                    "toggle" => Value::from(st.toggle(crate::ToggleOptions::new("target").value(fields[1] == "true").key("target").disabled(disabled).on_change(changed("target")))?),
                    "text_input" => Value::from(st.text_input(crate::TextInputOptions::new("target").value(fields[1]).key("target").disabled(disabled).on_change(changed("target")))?.ok_or("target text")?),
                    "text_area" => Value::from(st.text_area(crate::TextAreaOptions::new("target", fields[1]).key("target").disabled(disabled).on_change(changed("target")))?.ok_or("target area")?),
                    _ => return Err("unexpected late widget kind".into()),
                }
            };
            st.write(format!("values={}", json!({"values":[peer,target],"calls":st.session_state().get::<Vec<Value>>("late_calls")?.unwrap_or_default()})));
            Ok(())
        }
        .await;
        assert!(result.is_ok(), "late fixture failed: {result:?}");
    })
}

#[actix_web::test]
async fn first_registration_json_errors_callbacks_and_recovery_match_sdk_over_ws() -> TestResult {
    let reference: Value = serde_json::from_str(include_str!("../../../tests/reference/reference-browser/widget-params/trace.json"))?;
    let cases = reference["late_widget_registration_reference"]["cases"].as_array().ok_or("late cases")?;
    assert_eq!(cases.len(), 144);
    let listener = std::net::TcpListener::bind("127.0.0.1:0")?;
    let address = listener.local_addr()?;
    let configuration = StreamlitServer::new(late_registration_entry, "127.0.0.1".into(), 0);
    let store = configuration.sessions.clone();
    let server = HttpServer::new(move || App::new().app_data(web::Data::new(configuration.clone())).configure(configure_routes)).workers(1).listen(listener)?.run();
    let handle = server.handle();
    let task = actix_web::rt::spawn(server);

    // 1. 独立 witness 会话获取未来 ID；接收会话从未登记目标，不篡改 metadata。
    let captured = tokio::time::timeout(Duration::from_secs(60), async {
        let mut identities = HashMap::new();
        let mut runs = Vec::new();
        for case in cases {
            let mode = case["mode"].as_str().ok_or("mode")?;
            if !identities.contains_key(mode) {
                let mut witness = sessions::connect(address, None).await;
                let initial = rerun(&mut witness, vec![]).await?;
                let shown = rerun(
                    &mut witness,
                    vec![WidgetState {
                        id: initial.inputs["peer"].clone(),
                        value: Some(widget_state::Value::StringValue(mode.into())),
                    }],
                )
                .await?;
                identities.insert(mode.to_owned(), shown.inputs["target"].clone());
                sessions::disconnect(witness).await;
            }
            let target_id = &identities[mode];
            let mut socket = sessions::connect(address, None).await;
            let initial = rerun(&mut socket, vec![]).await?;
            let state = store.state_for_upload(&initial.id).ok_or("session state")?;
            let mut reports = Vec::new();
            for phase in ["submit", "repeat", "repair"] {
                let incoming = if phase == "repeat" {
                    vec![]
                } else {
                    let field = if phase == "submit" { "input_bytes" } else { "repair_bytes" };
                    let bytes = serde_json::from_value::<Vec<u8>>(case[field].clone())?;
                    let mut target = WidgetState::decode(bytes.as_slice())?;
                    target.id = target_id.clone();
                    let peer = WidgetState {
                        id: initial.inputs["peer"].clone(),
                        value: Some(widget_state::Value::StringValue(mode.into())),
                    };
                    if phase == "repair" || case["peer_first"] == true { vec![peer, target] } else { vec![target, peer] }
                };
                let run = rerun(&mut socket, incoming).await?;
                let calls = state.get::<Value>("late_calls")?.unwrap_or_else(|| json!([]));
                reports.push((run, calls));
            }
            sessions::disconnect(socket).await;
            runs.push((initial, target_id.clone(), reports));
        }
        assert_eq!(identities.len(), 12);
        Ok::<_, Box<dyn std::error::Error>>(runs)
    })
    .await;
    handle.stop(false).await;
    task.await??;
    let runs = captured??;

    // 2. 登记轮保留 Peer 输出/callback，后续错误轮没有主函数输出或新 callback。
    for ((initial, target_id, reports), case) in runs.into_iter().zip(cases) {
        assert_eq!(initial.inputs.len(), 1);
        assert_eq!(initial.values, json!({"values":["closed","__hidden__"],"calls":[]}));
        let expected = case["expected"].as_array().ok_or("expected")?;
        assert_eq!(reports.len(), expected.len());
        for (index, ((run, calls), expected)) in reports.into_iter().zip(expected).enumerate() {
            assert_eq!(run.id, initial.id);
            assert_eq!(calls, expected["calls"], "{} phase {index}", case["name"]);
            let controls = expected["controls"].as_array().ok_or("controls")?;
            assert_eq!(run.inputs.len(), controls.len(), "{} phase {index}", case["name"]);
            for key in controls {
                let key = key.as_str().ok_or("control key")?;
                assert_eq!(run.inputs.get(key), Some(if key == "target" { &target_id } else { &initial.inputs[key] }));
            }
            if expected["accepted"] == true {
                assert_eq!(run.values, expected["report"], "{} phase {index}", case["name"]);
            } else {
                assert!(run.values.is_null());
                assert_eq!(run.exceptions.len(), 1);
                let error = &run.exceptions[0];
                assert_eq!(error.r#type, expected["error_type"]);
                assert_eq!(error.message, expected["error"]);
                assert_eq!(error.message_is_markdown, expected["message_is_markdown"]);
                assert_eq!(error.is_streamlit_exception, expected["is_streamlit_exception"]);
            }
        }
    }
    Ok(())
}

fn bool_coercion_entry(st: &Streamlit) -> Pin<Box<dyn Future<Output = ()> + '_>> {
    bool_entry(st, false)
}

fn bool_disabled_entry(st: &Streamlit) -> Pin<Box<dyn Future<Output = ()> + '_>> {
    bool_entry(st, true)
}

fn bool_entry(st: &Streamlit, lifecycle: bool) -> Pin<Box<dyn Future<Output = ()> + '_>> {
    Box::pin(async move {
        let result: TestResult = async {
            let phase = st.session_state().get::<String>("peer")?.unwrap_or_else(|| "base".into());
            let disabled = lifecycle && !matches!(phase.as_str(), "enable" | "edit" | "recover");
            let flipped = lifecycle && !matches!(phase.as_str(), "base" | "submit" | "recover");
            let changed = |source: &'static str| {
                move |st: &Streamlit| {
                    let state = st.session_state();
                    let mut calls = state.get::<Vec<Value>>("bool_calls").expect("callback log").unwrap_or_default();
                    let mut snapshot = vec![Value::from(source)];
                    for key in ["cb0", "cb1", "tg0", "tg1", "peer"] {
                        snapshot.push(state.get::<Value>(key).expect("callback value").expect("registered peer"));
                    }
                    calls.push(Value::Array(snapshot));
                    state.set("bool_calls", calls).expect("save callbacks");
                }
            };
            let mut values = Vec::new();
            for (key, default, toggle) in [("cb0", false, false), ("cb1", true, false), ("tg0", false, true), ("tg1", true, true)] {
                let default = if flipped { !default } else { default };
                let value = if toggle {
                    st.toggle(crate::ToggleOptions::new(key).value(default).key(key).disabled(disabled).on_change(changed(key)))?
                } else {
                    st.checkbox(CheckboxOptions::new(key).value(default).key(key).disabled(disabled).on_change(changed(key)))?
                };
                values.push(Value::Bool(value));
            }
            values.push(Value::String(
                st.text_input(crate::TextInputOptions::new("peer").value("base").key("peer").on_change(changed("peer")))?.ok_or("peer must have a text value")?,
            ));
            st.write(format!("values={}", json!({"values":values,"calls":st.session_state().get::<Vec<Value>>("bool_calls")?.unwrap_or_default()})));
            Ok(())
        }
        .await;
        assert!(result.is_ok(), "bool fixture failed: {result:?}");
    })
}

#[actix_web::test]
async fn boolean_wire_coercion_callbacks_and_recovery_match_sdk_over_ws() -> TestResult {
    assert_boolean_reference("bool_coercion_reference", false).await
}

#[actix_web::test]
async fn repeated_widget_ids_callbacks_errors_and_recovery_match_sdk_over_ws() -> TestResult {
    let reference: Value = serde_json::from_str(include_str!("../../../tests/reference/reference-browser/widget-params/trace.json"))?;
    let cases = reference["widget_duplicates_reference"]["cases"].as_array().ok_or("duplicate cases")?;
    assert_eq!(cases.len(), 212);
    let listener = std::net::TcpListener::bind("127.0.0.1:0")?;
    let address = listener.local_addr()?;
    let configuration = StreamlitServer::new(bool_coercion_entry, "127.0.0.1".into(), 0);
    let store = configuration.sessions.clone();
    let server = HttpServer::new(move || App::new().app_data(web::Data::new(configuration.clone())).configure(configure_routes)).workers(1).listen(listener)?.run();
    let handle = server.handle();
    let task = actix_web::rt::spawn(server);

    // 1. 真实 socket 执行原始重复包、空重跑及修复；结束后再断言，确保清理服务器。
    let captured = tokio::time::timeout(Duration::from_secs(60), async {
        let mut runs = Vec::new();
        for case in cases {
            let mut socket = sessions::connect(address, None).await;
            let initial = rerun(&mut socket, vec![]).await?;
            let state = store.state_for_upload(&initial.id).ok_or("session state")?;
            let mut reports = Vec::new();
            for phase in ["submit", "repeat", "repair"] {
                let incoming = if phase == "submit" {
                    case["packet"]
                        .as_array()
                        .ok_or("packet")?
                        .iter()
                        .map(|entry| {
                            let bytes = serde_json::from_value::<Vec<u8>>(entry["bytes"].clone())?;
                            let mut widget = WidgetState::decode(bytes.as_slice())?;
                            let key = entry["key"].as_str().ok_or("key")?;
                            widget.id = initial.inputs.get(key).cloned().unwrap_or_else(|| key.into());
                            Ok::<_, Box<dyn std::error::Error>>(widget)
                        })
                        .collect::<Result<Vec<_>, _>>()?
                } else if phase == "repair" {
                    let key = case["key"].as_str().ok_or("key")?;
                    vec![
                        WidgetState {
                            id: initial.inputs[key].clone(),
                            value: Some(widget_state::Value::BoolValue(key.ends_with('0'))),
                        },
                        WidgetState {
                            id: initial.inputs["peer"].clone(),
                            value: Some(widget_state::Value::StringValue("repair".into())),
                        },
                    ]
                } else {
                    vec![]
                };
                let report = rerun(&mut socket, incoming).await?;
                let calls = state.get::<Value>("bool_calls")?.unwrap_or_else(|| json!([]));
                reports.push((report, calls));
            }
            sessions::disconnect(socket).await;
            runs.push((initial, reports));
        }
        Ok::<_, Box<dyn std::error::Error>>(runs)
    })
    .await;
    handle.stop(false).await;
    task.await??;
    let runs = captured??;

    // 2. 同时核对正常返回、首错/后续集合顺序允许项、实际 callback 日志和部分输出。
    assert_eq!(runs.len(), cases.len());
    for ((initial, reports), case) in runs.into_iter().zip(cases) {
        assert_eq!(initial.inputs.len(), 5);
        let expected = case["expected"].as_array().ok_or("expected")?;
        assert_eq!(reports.len(), expected.len());
        for (index, ((report, calls), expected)) in reports.into_iter().zip(expected).enumerate() {
            assert_eq!(report.id, initial.id);
            if expected["accepted"] == true {
                assert_eq!(report.inputs, initial.inputs);
                assert_eq!(report.values, expected["report"], "{} phase {index}", case["name"]);
                assert_eq!(calls, expected["report"]["calls"]);
            } else {
                assert!(report.values.is_null());
                assert_eq!(report.exceptions.len(), 1, "{} phase {index}", case["name"]);
                let error = &report.exceptions[0];
                assert_eq!(error.r#type, expected["error_type"], "{} phase {index}", case["name"]);
                if index > 0
                    && let Some(permitted) = case["later_error_messages"].as_array()
                {
                    assert!(permitted.iter().any(|message| message == &error.message), "{} phase {index}: {}", case["name"], error.message);
                } else {
                    assert_eq!(error.message, expected["error"], "{} phase {index}", case["name"]);
                }
                assert_eq!(error.message_is_markdown, expected["message_is_markdown"]);
                assert_eq!(error.is_streamlit_exception, expected["is_streamlit_exception"]);
                assert_eq!(calls, expected["calls"], "{} phase {index}", case["name"]);
                let controls = expected["rendered_controls"].as_array().ok_or("rendered controls")?;
                assert_eq!(report.inputs.len(), controls.len());
                for key in controls {
                    let key = key.as_str().ok_or("control key")?;
                    assert_eq!(report.inputs.get(key), initial.inputs.get(key));
                }
            }
        }
    }
    Ok(())
}

#[actix_web::test]
async fn disabled_boolean_callbacks_and_lifecycle_match_sdk_over_ws() -> TestResult {
    assert_boolean_reference("bool_disabled_reference", true).await
}

#[actix_web::test]
async fn boolean_json_numbers_constants_and_surrogates_match_sdk_over_ws() -> TestResult {
    assert_boolean_reference("bool_json_reference", false).await
}

async fn assert_boolean_reference(reference_key: &str, lifecycle: bool) -> TestResult {
    let reference: Value = serde_json::from_str(include_str!("../../../tests/reference/reference-browser/widget-params/trace.json"))?;
    let reference = &reference[reference_key];
    let cases = reference["cases"].as_array().ok_or("bool cases")?;
    let phases = if lifecycle {
        reference["phases"].as_array().ok_or("phases")?.iter().map(|phase| phase.as_str().ok_or("phase")).collect::<Result<Vec<_>, _>>()?
    } else {
        vec!["submit", "missing", "recover"]
    };
    assert_eq!(phases.len(), if lifecycle { 7 } else { 3 });
    let listener = std::net::TcpListener::bind("127.0.0.1:0")?;
    let address = listener.local_addr()?;
    let entry = if lifecycle { bool_disabled_entry } else { bool_coercion_entry };
    let server = HttpServer::new(move || App::new().app_data(web::Data::new(StreamlitServer::new(entry, "127.0.0.1".into(), 0))).configure(configure_routes))
        .workers(1)
        .listen(listener)?
        .run();
    let handle = server.handle();
    let task = actix_web::rt::spawn(server);
    let captured = tokio::time::timeout(Duration::from_secs(45), async {
        let mut runs = Vec::new();
        for case in cases {
            let mut socket = sessions::connect(address, None).await;
            let initial = rerun(&mut socket, vec![]).await?;
            let key = case["key"].as_str().ok_or("key")?;
            let mut reports = Vec::new();
            for &phase in &phases {
                let mut target = WidgetState { id: initial.inputs[key].clone(), value: None };
                if matches!(phase, "submit" | "disabled-again") {
                    let bytes = serde_json::from_value::<Vec<u8>>(case["input_bytes"].clone())?;
                    target = WidgetState::decode(bytes.as_slice())?;
                    target.id = initial.inputs[key].clone();
                } else if matches!(phase, "edit" | "recover") {
                    target.value = Some(widget_state::Value::BoolValue(key.ends_with(if !lifecycle || phase == "edit" { '0' } else { '1' })));
                }
                let peer = WidgetState {
                    id: initial.inputs["peer"].clone(),
                    value: Some(widget_state::Value::StringValue(phase.into())),
                };
                let incoming = if matches!(phase, "changed" | "enable") {
                    vec![peer]
                } else if phase == "missing" {
                    vec![peer, target]
                } else {
                    vec![target, peer]
                };
                reports.push(rerun(&mut socket, incoming).await?);
            }
            sessions::disconnect(socket).await;
            runs.push((initial, reports));
        }
        Ok::<_, Box<dyn std::error::Error>>(runs)
    })
    .await;
    handle.stop(false).await;
    task.await??;
    let runs = captured??;
    assert_eq!(cases.len(), if reference_key == "bool_json_reference" { 172 } else { 176 });
    assert_eq!(runs.len(), cases.len());
    for ((initial, reports), case) in runs.into_iter().zip(cases) {
        assert_eq!(initial.inputs.len(), 5);
        let expected = case["expected"].as_array().ok_or("expected phases")?;
        assert_eq!(reports.len(), expected.len());
        for (report, expected) in reports.into_iter().zip(expected) {
            assert_eq!(report.inputs, initial.inputs);
            assert_eq!(report.id, initial.id);
            assert_eq!(&report.values, expected, "{}", case["name"]);
        }
    }
    Ok(())
}

#[actix_web::test]
async fn malformed_json_errors_callbacks_and_session_isolation_match_sdk_over_ws() -> TestResult {
    let reference: Value = serde_json::from_str(include_str!("../../../tests/reference/reference-browser/widget-params/trace.json"))?;
    let cases = reference["json_input_errors_reference"]["cases"].as_array().ok_or("error cases")?;
    assert_eq!(cases.len(), 96);

    for disabled in [false, true] {
        let listener = std::net::TcpListener::bind("127.0.0.1:0")?;
        let address = listener.local_addr()?;
        let entry = if disabled { bool_disabled_entry } else { bool_coercion_entry };
        let configuration = StreamlitServer::new(entry, "127.0.0.1".into(), 0);
        let store = configuration.sessions.clone();
        let server = HttpServer::new(move || App::new().app_data(web::Data::new(configuration.clone())).configure(configure_routes)).workers(1).listen(listener)?.run();
        let handle = server.handle();
        let task = actix_web::rt::spawn(server);
        let captured = tokio::time::timeout(Duration::from_secs(45), async {
            let mut runs = Vec::new();
            for (case_index, case) in cases.iter().enumerate().filter(|(_, case)| case["disabled"] == disabled) {
                let key = case["key"].as_str().ok_or("key")?;
                let partner = case["partner"].as_str().ok_or("partner")?;
                let normal = |run: &Run, phase: &str| {
                    [key, partner]
                        .into_iter()
                        .map(|name| WidgetState {
                            id: run.inputs[name].clone(),
                            value: Some(if name == "peer" { widget_state::Value::StringValue(phase.into()) } else { widget_state::Value::BoolValue(!name.ends_with('1')) }),
                        })
                        .collect()
                };
                let mut socket = sessions::connect(address, None).await;
                let initial = rerun(&mut socket, vec![]).await?;
                let state = store.state_for_upload(&initial.id).ok_or("session state")?;
                let warm = rerun(&mut socket, normal(&initial, "warm")).await?;
                let mut failures = Vec::new();

                for phase in ["bad", "empty", "repair", "repeat"] {
                    let incoming = if phase == "bad" {
                        let target = WidgetState {
                            id: initial.inputs[key].clone(),
                            value: Some(widget_state::Value::JsonValue(case["input"].as_str().ok_or("input")?.into())),
                        };
                        let peer = WidgetState {
                            id: initial.inputs[partner].clone(),
                            value: Some(if partner == "peer" { widget_state::Value::StringValue("bad".into()) } else { widget_state::Value::BoolValue(false) }),
                        };
                        if case["peer_first"] == true { vec![peer, target] } else { vec![target, peer] }
                    } else if phase == "repair" {
                        normal(&initial, "repair")
                    } else {
                        vec![]
                    };
                    let run = rerun(&mut socket, incoming).await?;
                    let calls = state.get::<Value>("bool_calls")?.ok_or("callback log")?;
                    let partner_value = state.get::<Value>(partner)?.ok_or("partner state")?;
                    failures.push((run, calls, partner_value));
                }
                sessions::disconnect(socket).await;
                let mut fresh_socket = sessions::connect(address, None).await;
                let fresh = rerun(&mut fresh_socket, vec![]).await?;
                let fresh_edit = rerun(&mut fresh_socket, normal(&fresh, "fresh")).await?;
                sessions::disconnect(fresh_socket).await;
                runs.push((case_index, initial, warm, failures, fresh, fresh_edit));
            }
            Ok::<_, Box<dyn std::error::Error>>(runs)
        })
        .await;
        handle.stop(false).await;
        task.await??;
        let runs = captured??;
        assert_eq!(runs.len(), 48);

        for (index, initial, warm, failures, fresh, fresh_edit) in runs {
            let case = &cases[index];
            assert_eq!(warm.inputs, initial.inputs);
            assert_eq!(warm.values, case["warm"], "{}", case["name"]);
            let expected = case["errors"].as_array().ok_or("errors")?;
            assert_eq!(failures.len(), expected.len());
            for ((run, calls, partner), expected) in failures.into_iter().zip(expected) {
                assert_eq!(run.id, initial.id);
                assert!(run.inputs.is_empty() && run.values.is_null());
                assert_eq!(run.exceptions.len(), 1, "{}", case["name"]);
                let error = &run.exceptions[0];
                assert_eq!(error.r#type, expected["error_type"], "{}", case["name"]);
                assert_eq!(error.message, expected["error"], "{}", case["name"]);
                assert_eq!(Some(error.message_is_markdown), expected["message_is_markdown"].as_bool());
                assert_eq!(Some(error.is_streamlit_exception), expected["is_streamlit_exception"].as_bool());
                assert_eq!(calls, expected["calls"], "{}", case["name"]);
                assert_eq!(partner, expected["partner"], "{}", case["name"]);
            }
            assert_ne!(fresh.id, initial.id);
            assert_eq!(fresh.inputs, fresh_edit.inputs);
            assert_eq!(fresh.values, case["fresh"][0], "{}", case["name"]);
            assert_eq!(fresh_edit.values, case["fresh"][1], "{}", case["name"]);
        }
    }
    Ok(())
}

fn states(run: &Run, pulse: bool) -> Vec<WidgetState> {
    use widget_state::Value::*;
    let mut values = vec![
        WidgetState {
            id: run.inputs["group"].clone(),
            value: Some(StringValue("region".into())),
        },
        WidgetState {
            id: run.inputs["amount"].clone(),
            value: Some(DoubleArrayValue(proto::DoubleArray { data: vec![100.0] })),
        },
        WidgetState {
            id: run.inputs["include"].clone(),
            value: Some(BoolValue(false)),
        },
    ];
    if pulse {
        values.push(WidgetState {
            id: run.inputs["pulse"].clone(),
            value: Some(TriggerValue(true)),
        });
    }
    values
}

#[actix_web::test]
async fn typed_widgets_rerun_callback_restore_fresh_and_two_session_isolation() -> TestResult {
    let listener = std::net::TcpListener::bind("127.0.0.1:0")?;
    let address = listener.local_addr()?;
    let state = StreamlitServer::new(widgets_entry, "127.0.0.1".into(), 0);
    let server = HttpServer::new(move || App::new().app_data(web::Data::new(state.clone())).configure(configure_routes)).workers(2).listen(listener)?.run();
    let handle = server.handle();
    let task = actix_web::rt::spawn(server);
    let mut a = sessions::connect(address, None).await;
    let initial = rerun(&mut a, vec![]).await?;
    assert_eq!(initial.inputs.len(), 4);
    assert_eq!(initial.values, json!({"group":"category", "amount":0,"include":true,"click":false,"callbacks":0,"callback_values":null}));
    let changed = rerun(&mut a, states(&initial, true)).await?;
    let expected = json!({"group":"region", "amount":100,"include":false});
    assert_eq!(changed.values["callback_values"], expected, "each callback must see every newly applied input");
    assert_eq!(changed.values["callbacks"], 4);
    assert_eq!(changed.values["click"], true);
    assert_eq!(changed.id, initial.id);
    assert_eq!(changed.inputs, initial.inputs);
    let repeat = rerun(&mut a, states(&changed, false)).await?;
    assert_eq!(repeat.values["callbacks"], 4, "full persistent state resends do not trigger extra callbacks");
    assert_eq!(repeat.values["click"], false);
    let mut b = sessions::connect(address, None).await;
    let (a_run, b_run) = tokio::join!(rerun(&mut a, states(&repeat, true)), rerun(&mut b, vec![]));
    let (a_run, b_run) = (a_run?, b_run?);
    assert_eq!(a_run.values["callbacks"], 5);
    assert_eq!(b_run.values["group"], "category");
    assert_eq!(b_run.values["amount"], 0);
    assert_eq!(b_run.values["callbacks"], 0);
    assert_ne!(a_run.id, b_run.id);
    sessions::disconnect(a).await;
    let mut restored = sessions::connect(address, Some(&initial.id)).await;
    let recovered = rerun(&mut restored, vec![]).await?;
    assert_eq!(recovered.id, initial.id);
    assert_eq!(recovered.values["group"], "region");
    assert_eq!(recovered.values["amount"], 100);
    assert_eq!(recovered.values["include"], false);
    assert_eq!(recovered.values["click"], false);
    assert_eq!(recovered.values["callbacks"], 5);
    let mut refresh = sessions::connect(address, None).await;
    let fresh = rerun(&mut refresh, vec![]).await?;
    assert_ne!(fresh.id, initial.id);
    assert_eq!(fresh.values, initial.values);
    sessions::disconnect(restored).await;
    sessions::disconnect(refresh).await;
    sessions::disconnect(b).await;
    handle.stop(true).await;
    task.await??;
    Ok(())
}

fn sliders_entry(st: &Streamlit) -> Pin<Box<dyn Future<Output = ()> + '_>> {
    Box::pin(async move {
        let result: TestResult = async {
            let rate = st.slider(SliderOptions::new("Rate", 0.25).format("percent").key("rate"))?;
            let range = st.slider(SliderOptions::new("Float range", (-0.5, 0.5)).min(-1.0).max(1.0).key("range"))?;
            let ints = st.slider(SliderOptions::new("Integer range", [2_i64, 8_i64]).max(10).key("ints"))?;
            st.write(format!("values={}", json!({"rate":rate,"range":range,"ints":ints})));
            Ok(())
        }
        .await;
        assert!(result.is_ok(), "sliders_entry fixture failed: {result:?}");
    })
}

#[actix_web::test]
async fn float_scalar_and_numeric_ranges_roundtrip_over_websocket() -> TestResult {
    // Docs-backed numeric type coverage. Float/range frontend differential
    // evidence is still required; this test does not manufacture such evidence.
    let listener = std::net::TcpListener::bind("127.0.0.1:0")?;
    let address = listener.local_addr()?;
    let state = StreamlitServer::new(sliders_entry, "127.0.0.1".into(), 0);
    let server = HttpServer::new(move || App::new().app_data(web::Data::new(state.clone())).configure(configure_routes)).workers(1).listen(listener)?.run();
    let handle = server.handle();
    let task = actix_web::rt::spawn(server);
    let mut socket = sessions::connect(address, None).await;
    let initial = rerun(&mut socket, vec![]).await?;
    assert_eq!(initial.inputs.len(), 3);
    assert_eq!(initial.values, json!({"rate":0.25,"range":[-0.5,0.5],"ints":[2,8]}));
    let updates = [("rate", vec![0.75]), ("range", vec![-0.25, 0.75]), ("ints", vec![4.0, 10.0])]
        .into_iter()
        .map(|(key, data)| WidgetState {
            id: initial.inputs[key].clone(),
            value: Some(widget_state::Value::DoubleArrayValue(proto::DoubleArray { data })),
        })
        .collect();
    let updated = rerun(&mut socket, updates).await?;
    assert_eq!(updated.id, initial.id);
    assert_eq!(updated.values, json!({"rate":0.75,"range":[-0.25,0.75],"ints":[4,10]}));
    let retained = rerun(&mut socket, vec![]).await?;
    assert_eq!(retained.values, updated.values);
    sessions::disconnect(socket).await;
    handle.stop(true).await;
    task.await??;
    Ok(())
}

#[derive(Clone, Debug, PartialEq)]
struct NullOption;
impl std::fmt::Display for NullOption {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.write_str("Null option")
    }
}
impl serde::Serialize for NullOption {
    fn serialize<S: serde::Serializer>(&self, serializer: S) -> Result<S::Ok, S::Error> {
        serializer.serialize_none()
    }
}

fn registration_boundaries(st: &Streamlit) -> Pin<Box<dyn Future<Output = ()> + '_>> {
    Box::pin(async move {
        let result: TestResult = async {
            // Only public application APIs are used here, including the failed call
            // and its correction. Failure must not claim a widget key or append UI.
            let state = st.session_state();
            state.set("amount", 4_000_000_000_u64)?;
            let wide_failed = st.slider(SliderOptions::new("Amount", 0_i32).max(5_000_000_000.0).key("amount")).is_err();
            state.set("amount", 3.0_f64)?;
            let conversion_failed = matches!(st.slider(SliderOptions::new("Amount", 0_i32).key("amount")), Err(crate::WidgetError::Serialization(_)));
            let correction_allowed = state.set("amount", 1_i32).is_ok();
            let retry = st.slider(SliderOptions::new("Amount", 0_i32).key("amount"))?;

            let custom = st.selectbox(SelectboxOptions::new("Custom null", [NullOption]).key("custom"))?;
            let unit = st.selectbox(SelectboxOptions::with_format_func("Unit", [()], |_| "unit".into()).key("unit"))?;
            let json_null = st.selectbox(SelectboxOptions::new("JSON null", [Value::Null]).key("json_null"))?;
            let optional = st.selectbox(
                SelectboxOptions::with_format_func("Optional", [None::<i32>, Some(7)], |value| value.map_or_else(|| "None".into(), |n| n.to_string()))
                    .index(None)
                    .key("optional"),
            )?;
            st.write(format!(
                "values={}",
                json!({
                    "wide_failed":wide_failed, "conversion_failed":conversion_failed,
                    "correction_allowed":correction_allowed, "retry":retry,
                    "custom_null_selected":custom == Some(NullOption),
                    "unit_selected":unit == Some(()), "json_null_selected":json_null == Some(Value::Null),
                    "optional_selected_null":optional == Some(None), "optional_unselected":optional.is_none(),
                    "custom_key_present":state.get::<Value>("custom")? == Some(Value::Null),
                })
            ));
            Ok(())
        }
        .await;
        assert!(result.is_ok(), "registration_boundaries fixture failed: {result:?}");
    })
}

#[actix_web::test]
async fn failed_typed_registration_can_retry_and_selected_null_survives_real_reruns() -> TestResult {
    let listener = std::net::TcpListener::bind("127.0.0.1:0")?;
    let address = listener.local_addr()?;
    let state = StreamlitServer::new(registration_boundaries, "127.0.0.1".into(), 0);
    let server = HttpServer::new(move || App::new().app_data(web::Data::new(state.clone())).configure(configure_routes)).workers(1).listen(listener)?.run();
    let handle = server.handle();
    let task = actix_web::rt::spawn(server);
    let mut socket = sessions::connect(address, None).await;
    let initial = rerun(&mut socket, vec![]).await?;
    let expected = json!({
        "wide_failed":true,"conversion_failed":true,"correction_allowed":true,"retry":1,
        "custom_null_selected":true,"unit_selected":true,"json_null_selected":true,
        "optional_selected_null":false,"optional_unselected":true,"custom_key_present":true,
    });
    assert_eq!(initial.input_count, 5, "failed registrations must not append UI elements");
    assert_eq!(initial.values, expected);
    // The last selectbox is initially unselected. Select its legitimate None
    // option via the real StringValue wire, and retain Some(None) next run too.
    let selected = rerun(
        &mut socket,
        vec![WidgetState {
            id: initial.inputs["group"].clone(),
            value: Some(widget_state::Value::StringValue("None".into())),
        }],
    )
    .await?;
    let mut selected_expected = expected;
    selected_expected["optional_selected_null"] = true.into();
    selected_expected["optional_unselected"] = false.into();
    assert_eq!(selected.values, selected_expected);
    let retained = rerun(&mut socket, vec![]).await?;
    assert_eq!(retained.values, selected_expected);
    assert_eq!(retained.id, initial.id);
    sessions::disconnect(socket).await;
    handle.stop(true).await;
    task.await??;
    Ok(())
}

/// The frozen widget-params reference: the number-input FLOAT path (%0.2f,
/// default step 0.01, f64 sentinels when unbounded, %d + 0.0 for integers),
/// radio index=None (no default) and horizontal+captions, text_area
/// max_chars/placeholder with the height on the element config, and
/// multiselect max_selections.
fn widget_params_entry(st: &Streamlit) -> Pin<Box<dyn Future<Output = ()> + '_>> {
    Box::pin(async move {
        let result: TestResult = (|| {
            st.number_input(crate::NumberInputOptions::<f64>::new("Float free", 1.5))?;
            st.number_input(crate::NumberInputOptions::<f64>::new("Float bounded", 2.5).min(0.25).max(9.75).step(0.25))?;
            st.number_input(crate::NumberInputOptions::<i64>::new("Int bounded", 4).min(2).max(8).step(2.0))?;
            st.radio(crate::RadioOptions::new("Plain", ["a", "b"]).index(None).key("r1"))?;
            st.radio(crate::RadioOptions::new("Horizontal", ["x", "y"]).horizontal(true).captions(["first", "second"]).key("r2"))?;
            st.text_area(crate::TextAreaOptions::new("Bounded", "hello").max_chars(10).placeholder("type here").height(200).key("t1"))?;
            st.multiselect(crate::MultiselectOptions::new("Capped", ["p", "q", "r"]).max_selections(2).key("m1"))?;
            Ok(())
        })();
        assert!(result.is_ok(), "widget_params fixture failed: {result:?}");
    })
}

#[actix_web::test]
async fn widget_parameter_edges_match_the_frozen_reference() -> TestResult {
    let listener = std::net::TcpListener::bind("127.0.0.1:0")?;
    let address = listener.local_addr()?;
    let server = StreamlitServer::new(widget_params_entry, "127.0.0.1".into(), 0);
    let server = HttpServer::new(move || App::new().app_data(web::Data::new(server.clone())).configure(configure_routes)).workers(1).listen(listener)?.run();
    let handle = server.handle();
    let task = actix_web::rt::spawn(server);
    let mut stream = sessions::connect(address, None).await;
    send_binary(
        &mut stream,
        &(BackMsg {
            r#type: Some(back_msg::Type::RerunScript(ClientState::default())),
        })
        .encode_to_vec(),
    )
    .await;
    let mut numbers = Vec::new();
    let mut radios = Vec::new();
    let mut textarea: Option<(proto::TextArea, Option<crate::proto::streamlit::HeightConfig>)> = None;
    let mut multiselect: Option<proto::MultiSelect> = None;
    loop {
        let message = receive(&mut stream).await;
        match message.r#type {
            Some(forward_msg::Type::Delta(delta)) => {
                if let Some(delta::Type::NewElement(element)) = delta.r#type {
                    match element.r#type {
                        Some(element::Type::NumberInput(number)) => numbers.push(number),
                        Some(element::Type::Radio(radio)) => radios.push(radio),
                        Some(element::Type::TextArea(area)) => textarea = Some((area, element.height_config)),
                        Some(element::Type::Multiselect(select)) => multiselect = Some(select),
                        _ => {}
                    }
                }
            }
            Some(forward_msg::Type::ScriptFinished(status)) => {
                assert_eq!(status, 0);
                break;
            }
            _ => {}
        }
    }
    assert_eq!(numbers.len(), 3);
    let (free, bounded, int_bounded) = (&numbers[0], &numbers[1], &numbers[2]);
    assert_eq!(free.format, "%0.2f");
    assert_eq!(free.data_type, proto::number_input::DataType::Float as i32);
    assert!((free.step - 0.01).abs() < f64::EPSILON, "the float default step");
    assert!((free.min - f64::MIN).abs() <= 0.0 || free.min == f64::MIN);
    assert_eq!(free.max, f64::MAX);
    assert!(!free.has_min && !free.has_max);
    assert_eq!(bounded.format, "%0.2f");
    assert!(bounded.has_min && bounded.has_max);
    assert!((bounded.min - 0.25).abs() < f64::EPSILON && (bounded.max - 9.75).abs() < f64::EPSILON && (bounded.step - 0.25).abs() < f64::EPSILON);
    assert_eq!(int_bounded.format, "%d");
    assert_eq!(int_bounded.data_type, proto::number_input::DataType::Int as i32);
    assert_eq!(radios.len(), 2);
    assert_eq!(radios[0].default, None, "index=None emits no default");
    assert!(radios[1].horizontal);
    assert_eq!(radios[1].captions, ["first", "second"]);
    assert_eq!(radios[1].default, Some(0));
    let (area, height) = textarea.ok_or("text_area must render")?;
    assert_eq!(area.max_chars, 10);
    assert_eq!(area.placeholder, "type here");
    let height = height.ok_or("the height rides the element config")?;
    assert!(matches!(height.height_spec, Some(crate::proto::streamlit::height_config::HeightSpec::PixelHeight(200))));
    let select = multiselect.ok_or("multiselect must render")?;
    assert_eq!(select.max_selections, 2);
    drop(stream);
    handle.stop(false).await;
    task.await??;
    Ok(())
}
