//! Navigation regressions against the measured Python 1.66.1 wire (see
//! .codex/compatibility.md, Multipage navigation): st.navigation streams
//! one navigation ForwardMsg with the pages (each named by the BLAKE2b/16
//! hash of its url path), the browser addresses reruns by page hash, the
//! default page serves an unaddressed load, and st.switch_page finishes the
//! run FINISHED_EARLY_FOR_RERUN after streaming the empty query string
//! while the server starts the next run on the target page without any
//! browser request.
use super::*;
use crate::Page;
use crate::navigation::page_hash;
use crate::proto::widget_state;

fn render_main(st: &Streamlit) {
    let hits = st.session_state().get::<i64>("hits").ok().flatten().unwrap_or(0) + 1;
    st.session_state().set("hits", hits).expect("valid state write");
    st.write(format!("page=main hits={hits}"));
    if st.button("Switch") {
        st.switch_page("two").expect("registered page");
    }
}

fn render_two(st: &Streamlit) {
    st.write("page=two");
}

fn navigation_entry(st: &Streamlit) -> Pin<Box<dyn Future<Output = ()> + '_>> {
    Box::pin(async move {
        // Mirrors tests/reference/navigation_app.py.
        let nav = st.navigation([Page::new("Main", render_main).icon(":material/home:").default(true).url_path("render_main"), Page::new("Two", render_two).url_path("two")]);
        nav.run();
    })
}

#[actix_web::test]
async fn navigation_pages_switch_and_session_state_match_the_measured_wire() -> TestResult {
    let listener = std::net::TcpListener::bind("127.0.0.1:0")?;
    let address = listener.local_addr()?;
    let server = HttpServer::new(move || App::new().app_data(web::Data::new(StreamlitServer::new(navigation_entry, "127.0.0.1".into(), 0))).configure(configure_routes))
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

    let main_hash = page_hash("render_main");
    let two_hash = page_hash("two");
    let main_script_hash = crate::utils::hash::hash("");
    let mut button_id = String::new();

    async fn rerun(stream: &mut TcpStream, states: Vec<WidgetState>, page: String) {
        send_binary(
            stream,
            &(BackMsg {
                r#type: Some(back_msg::Type::RerunScript(ClientState {
                    widget_states: Some(WidgetStates { widgets: states }),
                    page_script_hash: page,
                    ..Default::default()
                })),
            })
            .encode_to_vec(),
        )
        .await;
    }

    // The measured timeline entries: NewSession's page hash, the navigation
    // message's current page, element bodies with paths, the page_info
    // payload and the finish statuses.
    let mut runs_finished = 0;

    {
        // Run 1: unaddressed load runs the default page.
        rerun(&mut stream, vec![], String::new()).await;
        let mut timeline_run1: Vec<String> = Vec::new();
        loop {
            let message = receive(&mut stream).await;
            let path = message.metadata.as_ref().map(|meta| meta.delta_path.clone()).unwrap_or_default();
            match message.r#type {
                Some(forward_msg::Type::NewSession(session)) => {
                    assert_eq!(session.page_script_hash, main_script_hash, "an unaddressed load reports the main script hash");
                    timeline_run1.push(format!("new_session:{}", session.page_script_hash));
                }
                Some(forward_msg::Type::SessionStatusChanged(status)) if !status.script_is_running => break,
                Some(forward_msg::Type::Delta(delta)) => match delta.r#type {
                    Some(delta::Type::AddBlock(_)) => {}
                    Some(delta::Type::NewElement(element)) => match element.r#type {
                        Some(element::Type::Markdown(text)) => timeline_run1.push(format!("markdown:{}{:?}", text.body, path)),
                        Some(element::Type::Button(button)) => {
                            button_id = button.id.clone();
                            timeline_run1.push(format!("button:{}{:?}", button.label, path));
                        }
                        Some(other) => panic!("unexpected element: {other:?}"),
                        None => {}
                    },
                    _ => {}
                },
                Some(forward_msg::Type::Navigation(nav)) => {
                    assert_eq!(nav.position, crate::proto::navigation::Position::Sidebar as i32);
                    assert_eq!(nav.sections, vec![String::new()]);
                    let pages: Vec<_> = nav
                        .app_pages
                        .iter()
                        .map(|page| (page.page_script_hash.as_str(), page.page_name.as_str(), page.icon.as_str(), page.is_default, page.url_pathname.as_str()))
                        .collect();
                    assert_eq!(pages, vec![(main_hash.as_str(), "Main", ":material/home:", true, ""), (two_hash.as_str(), "Two", "", false, "two"),]);
                    timeline_run1.push(format!("navigation:{}", nav.page_script_hash));
                }
                Some(forward_msg::Type::ScriptFinished(status)) => assert_eq!(status, 0),
                Some(forward_msg::Type::SessionStatusChanged(_)) => {}
                other => panic!("unexpected lifecycle response: {other:?}"),
            }
        }
        assert_eq!(timeline_run1.join(" | "), format!("new_session:{main_script_hash} | navigation:{main_hash} | markdown:page=main hits=1[0, 0] | button:Switch[0, 1]"));
    }

    {
        // Run 2: the browser addresses Two by its page hash.
        rerun(&mut stream, vec![], two_hash.clone()).await;
        let mut timeline_run2: Vec<String> = Vec::new();
        loop {
            let message = receive(&mut stream).await;
            let path = message.metadata.as_ref().map(|meta| meta.delta_path.clone()).unwrap_or_default();
            match message.r#type {
                Some(forward_msg::Type::NewSession(session)) => {
                    assert_eq!(session.page_script_hash, two_hash);
                    timeline_run2.push(format!("new_session:{}", session.page_script_hash));
                }
                Some(forward_msg::Type::SessionStatusChanged(status)) if !status.script_is_running => break,
                Some(forward_msg::Type::Delta(delta)) => match delta.r#type {
                    Some(delta::Type::AddBlock(_)) => {}
                    Some(delta::Type::NewElement(element)) => match element.r#type {
                        Some(element::Type::Markdown(text)) => timeline_run2.push(format!("markdown:{}{:?}", text.body, path)),
                        Some(other) => panic!("unexpected element: {other:?}"),
                        None => {}
                    },
                    _ => {}
                },
                Some(forward_msg::Type::Navigation(nav)) => timeline_run2.push(format!("navigation:{}", nav.page_script_hash)),
                Some(forward_msg::Type::ScriptFinished(status)) => assert_eq!(status, 0),
                Some(forward_msg::Type::SessionStatusChanged(_)) => {}
                other => panic!("unexpected lifecycle response: {other:?}"),
            }
        }
        assert_eq!(
            timeline_run2.join(" | "),
            format!("new_session:{two_hash} | navigation:{two_hash} | markdown:page=two[0, 0]"),
            "session state survives the page round trip only in later Main runs"
        );
    }

    {
        // Run 3: the Switch trigger switches pages -- the current run ends
        // FINISHED_EARLY_FOR_RERUN after the empty page_info, then the
        // server alone runs Two.
        rerun(
            &mut stream,
            vec![WidgetState {
                id: button_id.clone(),
                value: Some(widget_state::Value::TriggerValue(true)),
            }],
            main_hash.clone(),
        )
        .await;
        let mut timeline_run3: Vec<String> = Vec::new();
        loop {
            let message = receive(&mut stream).await;
            let path = message.metadata.as_ref().map(|meta| meta.delta_path.clone()).unwrap_or_default();
            match message.r#type {
                Some(forward_msg::Type::NewSession(session)) => timeline_run3.push(format!("new_session:{}", session.page_script_hash)),
                Some(forward_msg::Type::SessionStatusChanged(status)) if !status.script_is_running => {
                    runs_finished += 1;
                    if runs_finished == 2 {
                        break;
                    }
                }
                Some(forward_msg::Type::Delta(delta)) => match delta.r#type {
                    Some(delta::Type::AddBlock(_)) => {}
                    Some(delta::Type::NewElement(element)) => match element.r#type {
                        Some(element::Type::Markdown(text)) => timeline_run3.push(format!("markdown:{}{:?}", text.body, path)),
                        Some(element::Type::Button(button)) => timeline_run3.push(format!("button:{}{:?}", button.label, path)),
                        Some(other) => panic!("unexpected element: {other:?}"),
                        None => {}
                    },
                    _ => {}
                },
                Some(forward_msg::Type::Navigation(nav)) => timeline_run3.push(format!("navigation:{}", nav.page_script_hash)),
                Some(forward_msg::Type::PageInfoChanged(info)) => timeline_run3.push(format!("page_info:{}", info.query_string)),
                Some(forward_msg::Type::ScriptFinished(status)) => timeline_run3.push(format!("finished:{status}")),
                Some(forward_msg::Type::SessionStatusChanged(_)) => {}
                other => panic!("unexpected lifecycle response: {other:?}"),
            }
        }
        // 原始同步 WS 记录与旧浏览器调度窗口分别保留，不从 Rust 构造期望。
        let reference: serde_json::Value = serde_json::from_str(include_str!("../../../tests/reference/reference-browser/queryparams/navigation-rerun/trace.json"))?;
        let mut request_count = 0;
        let mut expected = Vec::new();
        for frame in reference["frames"].as_array().ok_or("missing navigation reference frames")? {
            let message = &frame["message"];
            if message.get("rerun_script").is_some() {
                request_count += 1;
            }
            if request_count != 2 {
                continue;
            }
            if let Some(session) = message.get("new_session") {
                expected.push(format!("new_session:{}", session["page_script_hash"].as_str().ok_or("missing page hash")?));
            }
            if let Some(nav) = message.get("navigation") {
                expected.push(format!("navigation:{}", nav["page_script_hash"].as_str().ok_or("missing navigation hash")?));
            }
            if let Some(info) = message.get("page_info_changed") {
                expected.push(format!("page_info:{}", info["query_string"].as_str().unwrap_or("")));
            }
            if let Some(markdown) = message["delta"]["new_element"].get("markdown") {
                let path: Vec<u32> = serde_json::from_value(message["metadata"]["delta_path"].clone())?;
                expected.push(format!("markdown:{}{path:?}", markdown["body"].as_str().ok_or("missing markdown")?));
            }
            if let Some(status) = message.get("script_finished") {
                let status = match status.as_str() {
                    Some("FINISHED_EARLY_FOR_RERUN") => 2,
                    Some("FINISHED_SUCCESSFULLY") => 0,
                    other => panic!("unexpected reference finish: {other:?}"),
                };
                expected.push(format!("finished:{status}"));
            }
        }
        assert_eq!(request_count, 2);
        assert_eq!(expected.len(), 7);
        assert_eq!(timeline_run3, expected, "switch_page queue behavior follows the synchronous native reference");
    }

    drop(stream);
    handle.stop(false).await;
    task.await??;

    Ok(())
}
