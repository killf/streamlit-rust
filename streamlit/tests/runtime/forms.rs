//! Real HTTP/WS coverage for the measured forms/text-input core.
use super::*;
use crate::proto;
use crate::{CheckboxOptions, FormOptions, FormSubmitButtonOptions, InputWidgets, StreamlitApi, TextInputOptions};
use serde_json::{Value, json};

fn layout_entry(st: &Streamlit) -> Pin<Box<dyn Future<Output = ()> + '_>> {
    Box::pin(async move {
        st.container()
            .form(FormOptions::new("in_container"), |form| {
                form.text_input(TextInputOptions::new("A").key("a"))?;
                form.form_submit_button("Apply A")
            })
            .unwrap();
        st.columns(2)[0]
            .form(FormOptions::new("in_column"), |form| {
                form.text_input(TextInputOptions::new("B").key("b"))?;
                form.form_submit_button("Apply B")
            })
            .unwrap();
        st.form(FormOptions::new("has_container"), |form| {
            form.container().text_input(TextInputOptions::new("C").key("c"))?;
            form.form_submit_button("Apply C")
        })
        .unwrap();
        st.form(FormOptions::new("has_columns"), |form| {
            let columns = form.columns(2);
            columns[0].text_input(TextInputOptions::new("D").key("d"))?;
            columns[1].text_input(TextInputOptions::new("E").key("e"))?;
            form.form_submit_button("Apply D")
        })
        .unwrap();
        st.text_input(TextInputOptions::new("Root").key("root")).unwrap();
        let outer = st.container();
        outer.container().write("DEEP");
        outer.write("SIBLING");
        st.write("TAIL");
        let columns = st.columns(2);
        columns[0].container().write("COLUMN_CHILD");
        columns[1].write("COLUMN_SIBLING");
        st.write("COLUMN_TAIL");
    })
}

#[actix_web::test]
async fn forms_layout_both_directions_emit_once_at_parent_paths_over_real_websocket() {
    let listener = std::net::TcpListener::bind("127.0.0.1:0").unwrap();
    let address = listener.local_addr().unwrap();
    let server = StreamlitServer::new(layout_entry, "127.0.0.1".into(), 0);
    let http_server = HttpServer::new(move || App::new().app_data(web::Data::new(server.clone())).configure(configure_routes)).workers(1).listen(listener).unwrap().run();
    let handle = http_server.handle();
    let task = actix_web::rt::spawn(http_server);
    let mut socket = sessions::connect(address, None).await;
    // Two complete runs prove the streaming tree and run-local registration
    // both reset, while the root widget keeps its original path and identity.
    for _ in 0..2 {
        send_binary(
            &mut socket,
            &BackMsg {
                r#type: Some(back_msg::Type::RerunScript(ClientState::default())),
            }
            .encode_to_vec(),
        )
        .await;
        let mut paths = std::collections::BTreeSet::new();
        let mut ids = std::collections::BTreeSet::new();
        let mut texts = Vec::new();
        let mut markers = Vec::new();
        let mut forms = 0;
        let mut submits = 0;
        let mut finished = 0;
        loop {
            let message = receive(&mut socket).await;
            let path = message.metadata.as_ref().map(|m| m.delta_path.clone()).unwrap_or_default();
            match message.r#type.unwrap() {
                forward_msg::Type::Delta(delta) => {
                    assert!(paths.insert(path.clone()), "duplicate delta path {path:?}");
                    match delta.r#type.unwrap() {
                        delta::Type::AddBlock(block) => forms += usize::from(matches!(block.r#type, Some(proto::block::Type::Form(_)))),
                        delta::Type::NewElement(element) => match element.r#type.unwrap() {
                            element::Type::TextInput(text) => {
                                assert!(ids.insert(text.id));
                                texts.push((text.label, text.form_id, path));
                            }
                            element::Type::Button(button) => {
                                assert!(ids.insert(button.id));
                                assert!(button.is_form_submitter);
                                submits += 1;
                            }
                            element::Type::Markdown(markdown) => markers.push((markdown.body, path)),
                            _ => (),
                        },
                        _ => (),
                    }
                }
                forward_msg::Type::ScriptFinished(status) => {
                    assert_eq!(status, 0);
                    finished += 1;
                }
                forward_msg::Type::SessionStatusChanged(status) if !status.script_is_running => break,
                _ => (),
            }
        }
        assert_eq!((forms, submits, finished), (4, 4, 1));
        assert_eq!(
            texts,
            vec![
                ("A".into(), "in_container".into(), vec![0, 0, 0, 0]),
                ("B".into(), "in_column".into(), vec![0, 1, 0, 0, 0]),
                ("C".into(), "has_container".into(), vec![0, 2, 0, 0]),
                ("D".into(), "has_columns".into(), vec![0, 3, 0, 0, 0]),
                ("E".into(), "has_columns".into(), vec![0, 3, 0, 1, 0]),
                ("Root".into(), "".into(), vec![0, 4]),
            ]
        );
        assert_eq!(
            markers,
            vec![
                ("DEEP".into(), vec![0, 5, 0, 0]),
                ("SIBLING".into(), vec![0, 5, 1]),
                ("TAIL".into(), vec![0, 6]),
                ("COLUMN_CHILD".into(), vec![0, 7, 0, 0, 0]),
                ("COLUMN_SIBLING".into(), vec![0, 7, 1, 0]),
                ("COLUMN_TAIL".into(), vec![0, 8]),
            ]
        );
    }
    sessions::disconnect(socket).await;
    handle.stop(true).await;
    task.await.unwrap().unwrap();
}

fn forms_entry(st: &Streamlit) -> Pin<Box<dyn Future<Output = ()> + '_>> {
    Box::pin(async move {
        let callback = |st: &Streamlit| {
            let state = st.session_state();
            let values = json!({
                "note": state.get::<String>("default_note").unwrap(),
                "agree": state.get::<bool>("default_agree").unwrap(),
            });
            state.set("callback_values", values).unwrap();
        };
        let result = st.form(FormOptions::new("default_form").clear_on_submit(true), |form| {
            let note = form.text_input(TextInputOptions::new("Note").key("default_note"))?;
            let agree = form.checkbox(CheckboxOptions::new("Agree").key("default_agree"))?;
            let submitted = form.form_submit_button(FormSubmitButtonOptions::new("Apply").key("default_apply").on_click(callback))?;
            Ok((note, agree, submitted))
        });
        let (note, agree, submitted) = result.expect("measured form registration");
        st.write(format!(
            "values={}",
            json!({
                "note": note,
                "agree": agree,
                "submitted": submitted,
                "callback_values": st.session_state().get::<Value>("callback_values").unwrap(),
            })
        ));
    })
}

#[actix_web::test]
async fn forms_buffered_layout_keeps_deep_paths_and_empty_columns_once() {
    use crate::elements::common::{Element, RenderContext};
    let st = Streamlit::new();
    layout_entry(&st).await;
    let mut context = RenderContext {
        stream: vec![],
        delta_path: vec![],
        active_script_hash: String::new(),
        session_id: "buffered-layout".into(),
        sender: None,
    };
    st.app.lock().render(&mut context).unwrap();
    let mut paths = std::collections::BTreeSet::new();
    let mut widgets = std::collections::BTreeSet::new();
    let mut form_count = 0;
    let mut text_paths = Vec::new();
    for message in context.stream {
        if let Some(forward_msg::Type::Delta(delta)) = message.r#type {
            let path = message.metadata.unwrap().delta_path;
            assert!(paths.insert(path.clone()), "buffered duplicate path {path:?}");
            match delta.r#type.unwrap() {
                delta::Type::AddBlock(block) => form_count += usize::from(matches!(block.r#type, Some(proto::block::Type::Form(_)))),
                delta::Type::NewElement(element) => match element.r#type.unwrap() {
                    element::Type::TextInput(text) => {
                        assert!(widgets.insert(text.id));
                        text_paths.push(path);
                    }
                    element::Type::Button(button) => {
                        assert!(widgets.insert(button.id));
                    }
                    _ => (),
                },
                _ => (),
            }
        }
    }
    assert_eq!(form_count, 4);
    assert_eq!(widgets.len(), 10);
    assert_eq!(text_paths, vec![vec![0, 0, 0, 0], vec![0, 1, 0, 0, 0], vec![0, 2, 0, 0], vec![0, 3, 0, 0, 0], vec![0, 3, 0, 1, 0], vec![0, 4]]);
    for path in [vec![0, 1, 1], vec![0, 5, 0, 0], vec![0, 5, 1], vec![0, 6], vec![0, 7, 0, 0, 0], vec![0, 7, 1, 0], vec![0, 8]] {
        assert!(paths.contains(&path), "missing buffered path {path:?}");
    }
}

struct FormsRun {
    session_id: String,
    script_run_id: String,
    text_id: String,
    checkbox_id: String,
    submit_id: String,
    values: Value,
}

async fn forms_rerun(stream: &mut TcpStream, widgets: Vec<WidgetState>) -> FormsRun {
    send_binary(
        stream,
        &BackMsg {
            r#type: Some(back_msg::Type::RerunScript(ClientState {
                widget_states: Some(WidgetStates { widgets }),
                ..Default::default()
            })),
        }
        .encode_to_vec(),
    )
    .await;
    let mut run = FormsRun {
        session_id: String::new(),
        script_run_id: String::new(),
        text_id: String::new(),
        checkbox_id: String::new(),
        submit_id: String::new(),
        values: Value::Null,
    };
    let mut finished = false;
    let mut saw_form = false;
    while let Some(message) = receive(stream).await.r#type {
        match message {
            forward_msg::Type::NewSession(new) => {
                run.session_id = new.initialize.unwrap().session_id;
                run.script_run_id = new.script_run_id;
            }
            forward_msg::Type::Delta(proto::Delta { r#type: Some(delta::Type::AddBlock(block)), .. }) => {
                saw_form |= matches!(block.r#type, Some(proto::block::Type::Form(_)));
            }
            forward_msg::Type::Delta(proto::Delta { r#type: Some(delta::Type::NewElement(wire)), .. }) => match wire.r#type {
                Some(element::Type::TextInput(text)) => run.text_id = text.id,
                Some(element::Type::Checkbox(check)) => run.checkbox_id = check.id,
                Some(element::Type::Button(button)) if button.is_form_submitter => run.submit_id = button.id,
                Some(element::Type::Markdown(value)) => {
                    if let Some(json) = value.body.strip_prefix("values=") {
                        run.values = serde_json::from_str(json).unwrap();
                    }
                }
                _ => (),
            },
            forward_msg::Type::ScriptFinished(status) => {
                assert_eq!(status, 0);
                assert!(!finished);
                finished = true;
            }
            forward_msg::Type::SessionStatusChanged(status) if !status.script_is_running => {
                assert!(finished);
                break;
            }
            _ => (),
        }
    }
    assert!(saw_form);
    assert!(!run.session_id.is_empty() && !run.script_run_id.is_empty());
    assert!(!run.text_id.is_empty() && !run.checkbox_id.is_empty() && !run.submit_id.is_empty());
    assert!(!run.values.is_null());
    run
}

#[actix_web::test]
async fn forms_batch_text_checkbox_and_submit_over_one_real_websocket() {
    let listener = std::net::TcpListener::bind("127.0.0.1:0").unwrap();
    let address = listener.local_addr().unwrap();
    let server = StreamlitServer::new(forms_entry, "127.0.0.1".into(), 0);
    let http_server = HttpServer::new(move || App::new().app_data(web::Data::new(server.clone())).configure(configure_routes)).workers(1).listen(listener).unwrap().run();
    let handle = http_server.handle();
    let task = actix_web::rt::spawn(http_server);

    let mut socket = sessions::connect(address, None).await;
    let initial = forms_rerun(&mut socket, vec![]).await;
    assert_eq!(initial.values, json!({"note": "", "agree": false, "submitted": false, "callback_values": null}));
    let submitted = forms_rerun(
        &mut socket,
        vec![
            WidgetState {
                id: initial.text_id,
                value: Some(widget_state::Value::StringValue("hello".into())),
            },
            WidgetState {
                id: initial.checkbox_id,
                value: Some(widget_state::Value::BoolValue(true)),
            },
            WidgetState {
                id: initial.submit_id,
                value: Some(widget_state::Value::TriggerValue(true)),
            },
        ],
    )
    .await;
    assert_eq!(submitted.session_id, initial.session_id);
    assert_ne!(submitted.script_run_id, initial.script_run_id);
    assert_eq!(
        submitted.values,
        json!({
            "note": "hello",
            "agree": true,
            "submitted": true,
            "callback_values": {"note": "hello", "agree": true},
        })
    );
    let retained = forms_rerun(&mut socket, vec![]).await;
    assert_eq!(retained.session_id, initial.session_id);
    assert_ne!(retained.script_run_id, submitted.script_run_id);
    assert_eq!(retained.values["note"], "hello");
    assert_eq!(retained.values["agree"], true);
    assert_eq!(retained.values["submitted"], false, "trigger is one-shot");

    // This is the second submit sent by the official frontend after
    // clear_on_submit has reset the staged field to its empty default.
    let cleared = forms_rerun(
        &mut socket,
        vec![
            WidgetState {
                id: retained.text_id,
                value: Some(widget_state::Value::StringValue(String::new())),
            },
            WidgetState {
                id: retained.checkbox_id,
                value: Some(widget_state::Value::BoolValue(true)),
            },
            WidgetState {
                id: retained.submit_id,
                value: Some(widget_state::Value::TriggerValue(true)),
            },
        ],
    )
    .await;
    assert_eq!(cleared.values["note"], "");
    assert_eq!(cleared.values["submitted"], true);
    let after_clear = forms_rerun(&mut socket, vec![]).await;
    assert_eq!(after_clear.values["note"], "");
    assert_eq!(after_clear.values["submitted"], false);

    sessions::disconnect(socket).await;
    handle.stop(true).await;
    task.await.unwrap().unwrap();
}
