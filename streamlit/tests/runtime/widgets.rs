//! Real WS value types come from the pinned Python closed-loop browser capture.
//! Parameter expectations below are docs/native contracts pending the fuller oracle.
use super::*;
use crate::proto;
use crate::{ButtonOptions, CheckboxOptions, InputWidgets, SelectboxOptions, SliderOptions};
use serde_json::{Value, json};
use std::collections::HashMap;

fn widgets_entry(st: &Streamlit) -> Pin<Box<dyn Future<Output = ()> + '_>> {
    Box::pin(async move {
        let callback = |st: &Streamlit| {
            let state = st.session_state();
            let all_values = json!({
                "group": state.get::<String>("group").unwrap(),
                "amount": state.get::<i64>("amount").unwrap(),
                "include": state.get::<bool>("include").unwrap(),
            });
            state.set("callback_values", all_values).unwrap();
            let n = state.get::<u64>("callbacks").unwrap().unwrap_or(0);
            state.set("callbacks", n + 1).unwrap();
        };
        let state = st.session_state();
        let group = st.selectbox(SelectboxOptions::new("Group by", ["category", "region", "channel"]).key("group").on_change(callback)).unwrap();
        let amount = st.slider(SliderOptions::new("Minimum amount", 0_i64).max(200).step(10).key("amount").on_change(callback)).unwrap();
        let include = st.checkbox(CheckboxOptions::new("Include unknown region").value(true).key("include").on_change(callback)).unwrap();
        let click = st.try_button(ButtonOptions::new("Pulse").key("pulse").on_click(callback)).unwrap();
        st.write(format!(
            "values={}",
            json!({
                "group": group, "amount": amount, "include": include, "click": click,
                "callbacks": state.get::<u64>("callbacks").unwrap().unwrap_or(0),
                "callback_values": state.get::<Value>("callback_values").unwrap(),
            })
        ));
    })
}

struct Run {
    id: String,
    inputs: HashMap<String, String>,
    values: Value,
    input_count: usize,
}

async fn rerun(stream: &mut TcpStream, widgets: Vec<WidgetState>) -> Run {
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
    };
    let mut finished = false;
    loop {
        match receive(stream).await.r#type {
            Some(forward_msg::Type::NewSession(new)) => run.id = new.initialize.unwrap().session_id,
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
                        run.inputs.insert("include".into(), value.id);
                    }
                    Some(element::Type::Button(value)) => {
                        run.inputs.insert("pulse".into(), value.id);
                    }
                    Some(element::Type::Markdown(value)) => {
                        if let Some(json) = value.body.strip_prefix("values=") {
                            run.values = serde_json::from_str(json).unwrap();
                        }
                    }
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
    assert!(!run.values.is_null());
    run
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
async fn typed_widgets_rerun_callback_restore_fresh_and_two_session_isolation() {
    let listener = std::net::TcpListener::bind("127.0.0.1:0").unwrap();
    let address = listener.local_addr().unwrap();
    let state = StreamlitServer::new(widgets_entry, "127.0.0.1".into(), 0);
    let server = HttpServer::new(move || App::new().app_data(web::Data::new(state.clone())).configure(configure_routes)).workers(2).listen(listener).unwrap().run();
    let handle = server.handle();
    let task = actix_web::rt::spawn(server);
    let mut a = sessions::connect(address, None).await;
    let initial = rerun(&mut a, vec![]).await;
    assert_eq!(initial.inputs.len(), 4);
    assert_eq!(initial.values, json!({"group":"category", "amount":0,"include":true,"click":false,"callbacks":0,"callback_values":null}));
    let changed = rerun(&mut a, states(&initial, true)).await;
    let expected = json!({"group":"region", "amount":100,"include":false});
    assert_eq!(changed.values["callback_values"], expected, "each callback must see every newly applied input");
    assert_eq!(changed.values["callbacks"], 4);
    assert_eq!(changed.values["click"], true);
    assert_eq!(changed.id, initial.id);
    assert_eq!(changed.inputs, initial.inputs);
    let repeat = rerun(&mut a, states(&changed, false)).await;
    assert_eq!(repeat.values["callbacks"], 4, "full persistent state resends do not trigger extra callbacks");
    assert_eq!(repeat.values["click"], false);
    let mut b = sessions::connect(address, None).await;
    let (a_run, b_run) = tokio::join!(rerun(&mut a, states(&repeat, true)), rerun(&mut b, vec![]));
    assert_eq!(a_run.values["callbacks"], 5);
    assert_eq!(b_run.values["group"], "category");
    assert_eq!(b_run.values["amount"], 0);
    assert_eq!(b_run.values["callbacks"], 0);
    assert_ne!(a_run.id, b_run.id);
    sessions::disconnect(a).await;
    let mut restored = sessions::connect(address, Some(&initial.id)).await;
    let recovered = rerun(&mut restored, vec![]).await;
    assert_eq!(recovered.id, initial.id);
    assert_eq!(recovered.values["group"], "region");
    assert_eq!(recovered.values["amount"], 100);
    assert_eq!(recovered.values["include"], false);
    assert_eq!(recovered.values["click"], false);
    assert_eq!(recovered.values["callbacks"], 5);
    let mut refresh = sessions::connect(address, None).await;
    let fresh = rerun(&mut refresh, vec![]).await;
    assert_ne!(fresh.id, initial.id);
    assert_eq!(fresh.values, initial.values);
    sessions::disconnect(restored).await;
    sessions::disconnect(refresh).await;
    sessions::disconnect(b).await;
    handle.stop(true).await;
    task.await.unwrap().unwrap();
}

fn sliders_entry(st: &Streamlit) -> Pin<Box<dyn Future<Output = ()> + '_>> {
    Box::pin(async move {
        let rate = st.slider(SliderOptions::new("Rate", 0.25).format("percent").key("rate")).unwrap();
        let range = st.slider(SliderOptions::new("Float range", (-0.5, 0.5)).min(-1.0).max(1.0).key("range")).unwrap();
        let ints = st.slider(SliderOptions::new("Integer range", [2_i64, 8_i64]).max(10).key("ints")).unwrap();
        st.write(format!("values={}", json!({"rate":rate,"range":range,"ints":ints})));
    })
}

#[actix_web::test]
async fn float_scalar_and_numeric_ranges_roundtrip_over_websocket() {
    // Docs-backed numeric type coverage. Float/range frontend differential
    // evidence is still required; this test does not manufacture such evidence.
    let listener = std::net::TcpListener::bind("127.0.0.1:0").unwrap();
    let address = listener.local_addr().unwrap();
    let state = StreamlitServer::new(sliders_entry, "127.0.0.1".into(), 0);
    let server = HttpServer::new(move || App::new().app_data(web::Data::new(state.clone())).configure(configure_routes)).workers(1).listen(listener).unwrap().run();
    let handle = server.handle();
    let task = actix_web::rt::spawn(server);
    let mut socket = sessions::connect(address, None).await;
    let initial = rerun(&mut socket, vec![]).await;
    assert_eq!(initial.inputs.len(), 3);
    assert_eq!(initial.values, json!({"rate":0.25,"range":[-0.5,0.5],"ints":[2,8]}));
    let updates = [("rate", vec![0.75]), ("range", vec![-0.25, 0.75]), ("ints", vec![4.0, 10.0])]
        .into_iter()
        .map(|(key, data)| WidgetState {
            id: initial.inputs[key].clone(),
            value: Some(widget_state::Value::DoubleArrayValue(proto::DoubleArray { data })),
        })
        .collect();
    let updated = rerun(&mut socket, updates).await;
    assert_eq!(updated.id, initial.id);
    assert_eq!(updated.values, json!({"rate":0.75,"range":[-0.25,0.75],"ints":[4,10]}));
    let retained = rerun(&mut socket, vec![]).await;
    assert_eq!(retained.values, updated.values);
    sessions::disconnect(socket).await;
    handle.stop(true).await;
    task.await.unwrap().unwrap();
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
        // Only public application APIs are used here, including the failed call
        // and its correction. Failure must not claim a widget key or append UI.
        let state = st.session_state();
        state.set("amount", 4_000_000_000_u64).unwrap();
        let wide_failed = st.slider(SliderOptions::new("Amount", 0_i32).max(5_000_000_000.0).key("amount")).is_err();
        state.set("amount", 3.0_f64).unwrap();
        let conversion_failed = matches!(st.slider(SliderOptions::new("Amount", 0_i32).key("amount")), Err(crate::WidgetError::Serialization(_)));
        let correction_allowed = state.set("amount", 1_i32).is_ok();
        let retry = st.slider(SliderOptions::new("Amount", 0_i32).key("amount")).unwrap();

        let custom = st.selectbox(SelectboxOptions::new("Custom null", [NullOption]).key("custom")).unwrap();
        let unit = st.selectbox(SelectboxOptions::with_format_func("Unit", [()], |_| "unit".into()).key("unit")).unwrap();
        let json_null = st.selectbox(SelectboxOptions::new("JSON null", [Value::Null]).key("json_null")).unwrap();
        let optional = st
            .selectbox(
                SelectboxOptions::with_format_func("Optional", [None::<i32>, Some(7)], |value| value.map_or_else(|| "None".into(), |n| n.to_string()))
                    .index(None)
                    .key("optional"),
            )
            .unwrap();
        st.write(format!(
            "values={}",
            json!({
                "wide_failed":wide_failed, "conversion_failed":conversion_failed,
                "correction_allowed":correction_allowed, "retry":retry,
                "custom_null_selected":custom == Some(NullOption),
                "unit_selected":unit == Some(()), "json_null_selected":json_null == Some(Value::Null),
                "optional_selected_null":optional == Some(None), "optional_unselected":optional.is_none(),
                "custom_key_present":state.get::<Value>("custom").unwrap() == Some(Value::Null),
            })
        ));
    })
}

#[actix_web::test]
async fn failed_typed_registration_can_retry_and_selected_null_survives_real_reruns() {
    let listener = std::net::TcpListener::bind("127.0.0.1:0").unwrap();
    let address = listener.local_addr().unwrap();
    let state = StreamlitServer::new(registration_boundaries, "127.0.0.1".into(), 0);
    let server = HttpServer::new(move || App::new().app_data(web::Data::new(state.clone())).configure(configure_routes)).workers(1).listen(listener).unwrap().run();
    let handle = server.handle();
    let task = actix_web::rt::spawn(server);
    let mut socket = sessions::connect(address, None).await;
    let initial = rerun(&mut socket, vec![]).await;
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
    .await;
    let mut selected_expected = expected;
    selected_expected["optional_selected_null"] = true.into();
    selected_expected["optional_unselected"] = false.into();
    assert_eq!(selected.values, selected_expected);
    let retained = rerun(&mut socket, vec![]).await;
    assert_eq!(retained.values, selected_expected);
    assert_eq!(retained.id, initial.id);
    sessions::disconnect(socket).await;
    handle.stop(true).await;
    task.await.unwrap().unwrap();
}
