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
        // Mirrors tests/reference/queryparams_app.py.
        st.query_params().set("mode", "demo").expect("valid param");
        let pick = st.selectbox_creation(crate::SelectboxCreationOptions::new("Pick", ["a", "b"]).filter_mode(crate::SelectFilterMode::Contains)).expect("valid selectbox");
        st.write(format!("pick={}", pick.as_deref().unwrap_or("a")));
        let bound = st.selectbox(crate::SelectboxOptions::new("Bound", ["x", "y"]).key("bound").bind(crate::TextBind::QueryParams)).expect("valid selectbox");
        st.write(format!("bound={}", bound.unwrap_or("x")));
    })
}

#[actix_web::test]
async fn query_params_and_selectbox_upgrades_match_the_measured_wire() {
    let listener = std::net::TcpListener::bind("127.0.0.1:0").unwrap();
    let address = listener.local_addr().unwrap();
    let server = HttpServer::new(move || App::new().app_data(web::Data::new(StreamlitServer::new(queryparams_entry, "127.0.0.1".into(), 0))).configure(configure_routes))
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
        assert_eq!(page_info.expect("page_info_changed streams").query_string, expected_url, "run {query_string:?}");
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
    task.await.unwrap().unwrap();
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
