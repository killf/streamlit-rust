//! Cache regressions against the measured Python 1.66.1 wire (see
//! .codex/compatibility.md, Caching): every miss streams an empty-element
//! transient (the cleared-spinner shape) at the call site and records the
//! function's element output; every hit replays those elements at their
//! original paths with no transient; st.cache_clear() drops the store so
//! the next call remisses and recomputes.
use super::*;

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
async fn cache_miss_transient_and_hit_replay_match_the_measured_wire() {
    let listener = std::net::TcpListener::bind("127.0.0.1:0").unwrap();
    let address = listener.local_addr().unwrap();
    let server = HttpServer::new(move || App::new().app_data(web::Data::new(StreamlitServer::new(cache_entry, "127.0.0.1".into(), 0))).configure(configure_routes))
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
    task.await.unwrap().unwrap();
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
