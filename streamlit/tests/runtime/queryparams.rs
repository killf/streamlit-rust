//! Query-params regressions against the measured Python 1.66.1 wire (see
//! .codex/compatibility.md, Query params): writes stream one
//! page_info_changed{query_string} at the call point merged with the
//! browser-reported URL state (alphabetically sorted k=v pairs), the
//! creation-mode selectbox carries acceptNewOptions plus the filter mode and
//! keeps a freshly typed label as its string state, and a bound selectbox
//! carries queryParamKey.
use super::*;
use crate::InputWidgets;
use crate::proto::{PageInfo, forward_msg};

fn queryparams_entry(st: &Streamlit) -> Pin<Box<dyn Future<Output = ()> + '_>> {
    Box::pin(async move {
        let result: TestResult = async {
            // Mirrors tests/reference/queryparams_app.py.
            st.query_params().set("mode", "demo")?;
            let pick = st.selectbox_creation(crate::SelectboxCreationOptions::new("Pick", ["a", "b"]).filter_mode(crate::SelectFilterMode::Contains))?;
            st.write(format!("pick={}", pick.as_deref().unwrap_or("a")));
            let bound = st.selectbox(crate::SelectboxOptions::new("Bound", ["x", "y"]).key("bound").bind(crate::TextBind::QueryParams))?;
            st.write(format!("bound={}", bound.unwrap_or("x")));
            Ok(())
        }
        .await;
        assert!(result.is_ok(), "query params fixture failed: {result:?}");
    })
}

fn queryparams_rerun_entry(st: &Streamlit) -> Pin<Box<dyn Future<Output = ()> + '_>> {
    Box::pin(async move {
        let result: TestResult = async {
            let state = st.session_state();
            let runs = state.get::<u32>("runs")?.unwrap_or(0) + 1;
            state.set("runs", runs)?;
            let ready = st.query_params().get("ready");
            st.write(format!("run={runs};ready={}", ready.as_deref().unwrap_or("missing")));
            // 独立计数让旧实现也在第三轮结束，避免错误重载 URL 后无限 rerun。
            if ready.is_none() && runs < 3 {
                st.query_params().set("ready", "1")?;
                st.rerun();
            }
            Ok(())
        }
        .await;
        assert!(result.is_ok(), "query params rerun fixture failed: {result:?}");
    })
}

fn switched_queryparams_entry(st: &Streamlit) -> Pin<Box<dyn Future<Output = ()> + '_>> {
    Box::pin(async move {
        let first = crate::Page::new("Main", |st| {
            let result: TestResult = (|| {
                st.query_params().set("written", "main")?;
                st.switch_page("two")?;
                Ok(())
            })();
            assert!(result.is_ok(), "source page fixture failed: {result:?}");
        })
        .default(true)
        .url_path("render_main");

        let second = crate::Page::new("Two", |st| {
            let result: TestResult = (|| {
                let state = st.session_state();
                let visits = state.get::<u8>("target_visits")?.unwrap_or(0) + 1;
                state.set("target_visits", visits)?;
                st.write(format!("target={}", serde_json::to_string(&st.query_params().to_vec())?));
                if visits == 1 {
                    st.query_params().set("target", "1")?;
                    st.rerun();
                }
                Ok(())
            })();
            assert!(result.is_ok(), "target page fixture failed: {result:?}");
        })
        .url_path("two");

        st.navigation([first, second]).run();
    })
}

#[actix_web::test]
async fn page_switch_clears_previous_query_but_target_rerun_keeps_new_writes() -> TestResult {
    // 1. 带非空 URL 请求首个页面，随后由服务端切页并普通重跑。
    let listener = std::net::TcpListener::bind("127.0.0.1:0")?;
    let address = listener.local_addr()?;
    let server = HttpServer::new(move || App::new().app_data(web::Data::new(StreamlitServer::new(switched_queryparams_entry, "127.0.0.1".into(), 0))).configure(configure_routes))
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
                query_string: "seed=browser".into(),
                page_script_hash: "4e89e30dce2a0c9070887e292d3255e7".into(),
                ..Default::default()
            })),
        }
        .encode_to_vec(),
    )
    .await;

    // 2. 保留跨轮事件顺序；整体限时防止持续输出掩盖意外重跑。
    let mut timeline = Vec::new();
    let completed = tokio::time::timeout(Duration::from_secs(5), async {
        let mut successful = false;
        loop {
            match receive(&mut stream).await.r#type {
                Some(forward_msg::Type::NewSession(session)) => timeline.push(format!("session:{}", session.page_script_hash)),
                Some(forward_msg::Type::PageInfoChanged(info)) => timeline.push(format!("query:{}", info.query_string)),
                Some(forward_msg::Type::Delta(delta)) => {
                    if let Some(delta::Type::NewElement(element)) = delta.r#type
                        && let Some(element::Type::Markdown(text)) = element.r#type
                    {
                        timeline.push(text.body);
                    }
                }
                Some(forward_msg::Type::ScriptFinished(status)) => {
                    timeline.push(format!("finish:{status}"));
                    successful = status == 0;
                }
                Some(forward_msg::Type::SessionStatusChanged(status)) if !status.script_is_running && successful => break,
                Some(forward_msg::Type::Navigation(_) | forward_msg::Type::SessionStatusChanged(_)) => {}
                other => panic!("unexpected query/navigation response: {other:?}"),
            }
        }
    })
    .await;

    // 3. 清理自己启动的服务后再检查，失败也不遗留监听端口。
    drop(stream);
    handle.stop(false).await;
    task.await??;
    completed?;
    assert_eq!(
        timeline,
        [
            "session:4e89e30dce2a0c9070887e292d3255e7",
            "query:seed=browser&written=main",
            "query:",
            "finish:2",
            "session:d681734f8c454b90df4d5feea7487445",
            "target=[]",
            "query:target=1",
            "finish:2",
            "session:d681734f8c454b90df4d5feea7487445",
            "target=[[\"target\",\"1\"]]",
            "finish:0",
        ]
    );
    Ok(())
}

#[actix_web::test]
async fn query_params_write_survives_server_started_rerun() -> TestResult {
    let listener = std::net::TcpListener::bind("127.0.0.1:0")?;
    let address = listener.local_addr()?;
    let server = HttpServer::new(move || App::new().app_data(web::Data::new(StreamlitServer::new(queryparams_rerun_entry, "127.0.0.1".into(), 0))).configure(configure_routes))
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

    let mut runs = 0;
    let mut markdowns = Vec::new();
    let mut finish_statuses = Vec::new();
    loop {
        match receive(&mut stream).await.r#type {
            Some(forward_msg::Type::NewSession(_)) => runs += 1,
            Some(forward_msg::Type::Delta(delta)) => {
                if let Some(delta::Type::NewElement(element)) = delta.r#type
                    && let Some(element::Type::Markdown(text)) = element.r#type
                {
                    markdowns.push(text.body);
                }
            }
            Some(forward_msg::Type::ScriptFinished(status)) => finish_statuses.push(status),
            Some(forward_msg::Type::SessionStatusChanged(status)) if !status.script_is_running && finish_statuses.last() == Some(&0) => break,
            Some(forward_msg::Type::PageInfoChanged(_) | forward_msg::Type::SessionStatusChanged(_)) => {}
            other => panic!("unexpected lifecycle response: {other:?}"),
        }
    }
    drop(stream);
    handle.stop(false).await;
    task.await??;

    assert_eq!(
        (runs, &finish_statuses, &markdowns),
        (2, &vec![2, 0], &vec!["run=1;ready=missing".to_string(), "run=2;ready=1".to_string()]),
        "one BackMsg must produce two runs; the server-started run must retain the query write"
    );
    Ok(())
}

#[actix_web::test]
async fn query_params_and_selectbox_upgrades_match_the_measured_wire() -> TestResult {
    let listener = std::net::TcpListener::bind("127.0.0.1:0")?;
    let address = listener.local_addr()?;
    let server = HttpServer::new(move || App::new().app_data(web::Data::new(StreamlitServer::new(queryparams_entry, "127.0.0.1".into(), 0))).configure(configure_routes))
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

    // Run two: the browser reports the bound pick in its URL and the typed
    // creation value in widget state, like the measured stage 03.
    let mut pick_id = String::new();
    let mut bound_id = String::new();
    for (query_string, pick_state, expected_url, expected_pick, expected_bound) in [("", "", "mode=demo", "pick=a", "bound=x"), ("bound=y&mode=demo", "c", "bound=y&mode=demo", "pick=c", "bound=y")] {
        let widgets = if pick_id.is_empty() {
            vec![]
        } else {
            vec![
                WidgetState {
                    id: pick_id.clone(),
                    value: Some(widget_state::Value::StringValue(pick_state.into())),
                },
                WidgetState {
                    id: bound_id.clone(),
                    value: Some(widget_state::Value::StringValue("y".into())),
                },
            ]
        };
        send_binary(
            &mut stream,
            &(BackMsg {
                r#type: Some(back_msg::Type::RerunScript(ClientState {
                    query_string: query_string.into(),
                    widget_states: Some(WidgetStates { widgets }),
                    ..Default::default()
                })),
            })
            .encode_to_vec(),
        )
        .await;
        let mut page_info: Option<PageInfo> = None;
        let mut selects: Vec<crate::proto::Selectbox> = Vec::new();
        let mut markdowns = Vec::new();
        let mut finished = false;
        loop {
            let message = receive(&mut stream).await;
            match message.r#type {
                Some(forward_msg::Type::NewSession(_)) => {}
                Some(forward_msg::Type::SessionStatusChanged(status)) if !status.script_is_running => break,
                Some(forward_msg::Type::PageInfoChanged(info)) => page_info = Some(info),
                Some(forward_msg::Type::Delta(delta)) => match delta.r#type {
                    Some(delta::Type::AddBlock(_)) => {}
                    Some(delta::Type::NewElement(element)) => match element.r#type {
                        Some(element::Type::Selectbox(select)) => selects.push(select),
                        Some(element::Type::Markdown(text)) => markdowns.push(text.body),
                        Some(other) => panic!("unexpected element: {other:?}"),
                        None => {}
                    },
                    _ => {}
                },
                Some(forward_msg::Type::ScriptFinished(status)) => {
                    assert_eq!(status, 0);
                    assert!(!finished);
                    finished = true;
                }
                Some(forward_msg::Type::SessionStatusChanged(_)) => {}
                other => panic!("unexpected lifecycle response: {other:?}"),
            }
        }
        assert!(finished);
        // One merged, alphabetically sorted query string per write, like the
        // measured page_info_changed.
        assert_eq!(page_info.ok_or("query params write must stream page_info_changed")?.query_string, expected_url, "run {query_string:?}");
        assert_eq!(selects.len(), 2);
        let creation = &selects[0];
        assert_eq!(creation.label, "Pick");
        assert_eq!(creation.options, vec!["a", "b"]);
        assert_eq!(creation.accept_new_options, Some(true));
        assert_eq!(creation.filter_mode, crate::proto::streamlit::SelectWidgetFilterMode::FilterModeContains as i32);
        assert!(creation.query_param_key.is_none());
        let bound = &selects[1];
        assert_eq!(bound.label, "Bound");
        assert_eq!(bound.query_param_key.as_deref(), Some("bound"));
        assert_eq!(bound.accept_new_options, Some(false));
        assert_eq!(bound.filter_mode, crate::proto::streamlit::SelectWidgetFilterMode::FilterModeFuzzy as i32);
        pick_id = creation.id.clone();
        bound_id = bound.id.clone();
        assert_eq!(markdowns, vec![expected_pick, expected_bound]);
    }

    drop(stream);
    handle.stop(false).await;
    task.await??;
    Ok(())
}

#[test]
fn query_param_store_round_trips_and_serializes_like_the_reference() {
    let mut store = crate::query_params::QueryParamStore::default();
    store.load("bound=y&mode=demo");
    assert_eq!(store.serialize(), "bound=y&mode=demo");
    store.set("mode", vec!["demo".into()]);
    assert_eq!(store.serialize(), "bound=y&mode=demo", "an equal write keeps the merged state");
    store.set("alpha", vec!["one".into(), "two".into()]);
    assert_eq!(store.serialize(), "alpha=one&alpha=two&bound=y&mode=demo");
    assert_eq!(store.get("mode"), Some("demo"));
    assert_eq!(store.get_all("alpha"), &["one".to_string(), "two".to_string()]);
    assert!(store.remove("bound"));
    assert_eq!(store.serialize(), "alpha=one&alpha=two&mode=demo");
    store.load("q=%E4%B8%AD%E6%96%87+text");
    assert_eq!(store.get("q"), Some("\u{4e2d}\u{6587} text"));
    assert_eq!(store.serialize(), "q=%E4%B8%AD%E6%96%87+text", "non-ascii round-trips percent-encoded like urlencode");
    store.clear();
    assert_eq!(store.serialize(), "");
}
