//! Button-family regressions against the measured Python 1.66.1 wire (see
//! .codex/compatibility.md, Button family): st.toggle is a checkbox with
//! the TOGGLE style; st.feedback is a style-only element; st.pills and
//! st.segmented_control are button groups (content options, click mode,
//! index defaults); st.pagination carries num_pages/default/
//! max_visible_pages and never a stray value; st.menu_button reports its
//! one-shot string trigger; st.download_button carries the content-addressed
//! /media/<hash>.txt URL; st.link_button defaults to ignore_rerun with its
//! keyed id; st.page_link carries page/label/external.
use super::*;
use crate::InputWidgets;
use crate::proto;
use crate::proto::widget_state::Value as WireValue;

fn buttons_entry(st: &Streamlit) -> Pin<Box<dyn Future<Output = ()> + '_>> {
    Box::pin(async move {
        // Mirrors tests/reference/buttons_app.py.
        st.toggle(crate::ToggleOptions::new("Night mode").key("night")).unwrap();
        st.toggle(("Sound", true)).unwrap();

        let _stars = st.feedback(crate::FeedbackOptions::new(crate::FeedbackKind::Stars).key("rate")).unwrap();
        st.feedback(crate::FeedbackKind::Thumbs).unwrap();

        st.pills(crate::ButtonGroupOptions::new("Priority", ["low", "medium", "high"]).key("priority")).unwrap();
        st.pills(crate::ButtonGroupOptions::new("Tags", ["alpha", "beta", "gamma"]).selection_mode(crate::SelectionMode::Multi).default(["alpha"]).key("tags"))
            .unwrap();
        st.segmented_control(crate::ButtonGroupOptions::new("View", ["grid", "list"]).default(["grid"]).key("view")).unwrap();

        let page = st.pagination(crate::PaginationOptions::new(10).key("pager")).unwrap();
        st.write(format!("page={page}"));

        let pick = st.menu_button(crate::MenuButtonOptions::new("Export", ["CSV", "JSON"]).key("export")).unwrap();
        if pick.is_some() {
            st.write("picked");
        }

        st.download_button(crate::DownloadButtonOptions::new("Save report", "quarterly report body").file_name("report.txt").mime("text/plain").key("save"))
            .unwrap();
        st.link_button(crate::LinkButtonOptions::new("Docs", "https://docs.streamlit.io").key("docs")).unwrap();
        st.page_link(crate::PageLinkOptions::new("https://example.com").label("Example site")).unwrap();
    })
}

#[actix_web::test]
async fn button_family_matches_the_measured_wire() {
    let listener = std::net::TcpListener::bind("127.0.0.1:0").unwrap();
    let address = listener.local_addr().unwrap();
    let server = HttpServer::new(move || App::new().app_data(web::Data::new(StreamlitServer::new(buttons_entry, "127.0.0.1".into(), 0))).configure(configure_routes))
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

    let mut ids: std::collections::HashMap<&str, String> = std::collections::HashMap::new();
    for run in 1..=3 {
        let states = |ids: &std::collections::HashMap<&str, String>, with_trigger: bool| {
            let mut widgets = vec![
                WidgetState {
                    id: ids.get("night").cloned().unwrap_or_default(),
                    value: Some(WireValue::BoolValue(true)),
                },
                WidgetState {
                    id: ids.get("rate").cloned().unwrap_or_default(),
                    value: Some(WireValue::StringValue("2".into())),
                },
                WidgetState {
                    id: ids.get("priority").cloned().unwrap_or_default(),
                    value: Some(WireValue::StringArrayValue(proto::StringArray { data: vec!["high".into()] })),
                },
                WidgetState {
                    id: ids.get("tags").cloned().unwrap_or_default(),
                    value: Some(WireValue::StringArrayValue(proto::StringArray { data: vec!["alpha".into()] })),
                },
                WidgetState {
                    id: ids.get("view").cloned().unwrap_or_default(),
                    value: Some(WireValue::StringArrayValue(proto::StringArray { data: vec!["grid".into()] })),
                },
                WidgetState {
                    id: ids.get("pager").cloned().unwrap_or_default(),
                    value: Some(WireValue::IntValue(2)),
                },
            ];
            if with_trigger {
                widgets.push(WidgetState {
                    id: ids.get("export").cloned().unwrap_or_default(),
                    value: Some(WireValue::StringTriggerValue(proto::StringTriggerValue { data: Some("CSV".into()) })),
                });
            }
            widgets
        };
        send_binary(
            &mut stream,
            &(BackMsg {
                r#type: Some(back_msg::Type::RerunScript(ClientState {
                    widget_states: Some(WidgetStates { widgets: states(&ids, run == 2) }),
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
                Some(forward_msg::Type::Delta(delta)) => {
                    let Some(delta::Type::NewElement(element)) = delta.r#type else { continue };
                    let Some(kind) = element.r#type else { continue };
                    let entry = match kind {
                        element::Type::Checkbox(checkbox) => {
                            ids.entry("night").or_insert_with(|| checkbox.id.clone());
                            format!("toggle:{}:{}:{:?}:{:?}", checkbox.label, checkbox.default, proto::checkbox::StyleType::try_from(checkbox.r#type).ok(), path)
                        }
                        element::Type::Feedback(feedback) => {
                            ids.entry("rate").or_insert_with(|| feedback.id.clone());
                            format!("feedback:{:?}", proto::feedback::FeedbackType::try_from(feedback.r#type).ok())
                        }
                        element::Type::ButtonGroup(group) => {
                            format!(
                                "group:{}:{:?}:{:?}:{:?}:{:?}",
                                group.label,
                                group.options.iter().map(|option| option.content.clone()).collect::<Vec<_>>(),
                                proto::button_group::ClickMode::try_from(group.click_mode).ok(),
                                group.default,
                                proto::button_group::Style::try_from(group.style).ok()
                            )
                        }
                        element::Type::Pagination(pager) => {
                            ids.entry("pager").or_insert_with(|| pager.id.clone());
                            format!("pagination:{}:{}:{}:{}", pager.num_pages, pager.default, pager.max_visible_pages.unwrap_or(0), pager.value)
                        }
                        element::Type::MenuButton(menu) => {
                            ids.entry("export").or_insert_with(|| menu.id.clone());
                            format!("menu:{}:{:?}:{}", menu.label, menu.options, menu.r#type)
                        }
                        element::Type::DownloadButton(download) => {
                            format!("download:{}:{}", download.label, download.url)
                        }
                        element::Type::LinkButton(link) => {
                            format!("link:{}:{}:{}", link.label, link.url, link.ignore_rerun)
                        }
                        element::Type::PageLink(link) => {
                            format!("page_link:{}:{}:{}", link.page, link.label, link.external)
                        }
                        element::Type::Markdown(markdown) => format!("markdown:{:?}", markdown.body),
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
        if run == 1 {
            assert_eq!(
                joined,
                "toggle:Night mode:false:Some(Toggle):[0, 0] | toggle:Sound:true:Some(Toggle):[0, 1] | feedback:Some(Stars) | feedback:Some(Thumbs) | group:Priority:[\"low\", \"medium\", \"high\"]:Some(SingleSelect):[]:Some(Pills) | group:Tags:[\"alpha\", \"beta\", \"gamma\"]:Some(MultiSelect):[0]:Some(Pills) | group:View:[\"grid\", \"list\"]:Some(SingleSelect):[0]:Some(SegmentedControl) | pagination:10:1:7:0 | markdown:\"page=1\" | menu:Export:[\"CSV\", \"JSON\"]:secondary | download:Save report:/media/8dfe283c4516576ff59dfb1b6901332d.txt | link:Docs:https://docs.streamlit.io:true | page_link:https://example.com:Example site:true"
            );
        } else if run == 2 {
            // The committed interactions: the toggle, pill, pagination and
            // feedback states drive the run (page=2) and the menu pick
            // reports for exactly this run.
            assert!(joined.contains("markdown:\"page=2\""), "{joined}");
            assert!(joined.contains("markdown:\"picked\""), "{joined}");
        } else {
            // The one-shot trigger reset: the same states minus the menu
            // trigger keep the settled page without the pick marker.
            assert!(joined.contains("markdown:\"page=2\""), "{joined}");
            assert!(!joined.contains("picked"), "{joined}");
        }
    }

    drop(stream);
    handle.stop(false).await;
    task.await.unwrap().unwrap();
}

#[actix_web::test]
async fn feedback_decodes_its_three_wire_states() {
    use crate::widgets::{Codec, WidgetError};

    let decode = |wire: WireValue| -> Result<serde_json::Value, WidgetError> {
        let codec = Codec::Feedback { count: 5 };
        let value = codec.decode(&wire).ok_or(WidgetError::InvalidValue("undecodable".into()))?;
        codec.valid(&value).then_some(value).ok_or(WidgetError::InvalidValue("invalid".into()))
    };
    // The measured serde: "" is the explicit clear, a decimal string is the
    // picked icon, anything else is rejected fail-closed.
    assert_eq!(decode(WireValue::StringValue(String::new())).unwrap(), serde_json::Value::Null);
    assert_eq!(decode(WireValue::StringValue("2".into())).unwrap(), serde_json::json!(2));
    assert!(decode(WireValue::StringValue("bogus".into())).is_err());
    assert!(decode(WireValue::StringValue("7".into())).is_err());
    assert!(decode(WireValue::IntValue(2)).is_err());
}

#[actix_web::test]
async fn button_group_decodes_single_and_multi_selections() {
    use crate::widgets::Codec;

    let single = Codec::ButtonGroup {
        options: vec![("low".into(), serde_json::json!("low")), ("high".into(), serde_json::json!("high"))],
        multi: false,
    };
    let multi = Codec::ButtonGroup {
        options: vec![("alpha".into(), serde_json::json!("alpha")), ("beta".into(), serde_json::json!("beta"))],
        multi: true,
    };
    let wire = |labels: &[&str]| {
        WireValue::StringArrayValue(proto::StringArray {
            data: labels.iter().map(|label| label.to_string()).collect(),
        })
    };

    assert_eq!(single.decode(&wire(&["high"])).unwrap(), serde_json::json!(1));
    assert_eq!(single.decode(&wire(&[])).unwrap(), serde_json::Value::Null);
    assert!(single.decode(&wire(&["low", "high"])).is_none(), "a single-select group carries at most one label");
    assert_eq!(multi.decode(&wire(&["beta", "alpha"])).unwrap(), serde_json::json!([1, 0]), "multi-select preserves the browser's selection order");
    assert!(!single.valid(&serde_json::json!(2)), "an out-of-range index is rejected fail-closed");
    assert!(single.valid(&serde_json::Value::Null), "no selection is valid");
}
