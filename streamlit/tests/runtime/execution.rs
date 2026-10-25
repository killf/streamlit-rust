//! Execution-semantics regressions: the st.rerun/st.stop run-loop and the
//! suppression of later elements and session-state writes, against the
//! measured Python 1.66.1 wire recorded in .codex/compatibility.md.
use super::*;

fn rerun_entry(st: &Streamlit) -> Pin<Box<dyn Future<Output = ()> + '_>> {
    Box::pin(async move {
        st.markdown("runs-marker");
        let initialized: Option<bool> = st.session_state().get("initialized").ok().flatten();
        if initialized.is_none() {
            st.session_state().set("initialized", true).unwrap();
            st.rerun();
            st.markdown("unreachable-after-rerun");
        }
        st.markdown("epilogue");
    })
}

fn stop_entry(st: &Streamlit) -> Pin<Box<dyn Future<Output = ()> + '_>> {
    Box::pin(async move {
        let stopped: Option<bool> = st.session_state().get("stopped").ok().flatten();
        if stopped.is_none() {
            st.markdown("before-stop");
            st.session_state().set("stopped", true).unwrap();
            st.stop();
            st.markdown("after-stop");
            st.session_state().set("late", true).unwrap();
        } else {
            let late = st.session_state().get::<bool>("late").ok().flatten().is_some();
            st.markdown(format!("late-is-present={late}"));
        }
    })
}

fn duplicate_key_entry(st: &Streamlit) -> Pin<Box<dyn Future<Output = ()> + '_>> {
    Box::pin(async move {
        let armed: Option<bool> = st.session_state().get("armed").ok().flatten();
        if armed.is_none() {
            st.markdown("first");
            st.session_state().set("armed", true).unwrap();
            return;
        }
        // Later runs hit the takeover: upstream raises on every rerun too.
        let _first = crate::InputWidgets::selectbox(st, crate::SelectboxOptions::new("Group by", ["category", "region"]).key("group")).unwrap();
        let second = crate::InputWidgets::selectbox(st, crate::SelectboxOptions::new("Other group by", ["category", "region"]).key("group")).unwrap();
        assert_eq!(second, Some("category"), "the takeover returns the requested default");
        st.markdown("unreachable-after-duplicate");
    })
}

struct RunTrace {
    markdowns: Vec<String>,
    exceptions: Vec<(String, String)>,
    finish_statuses: Vec<i32>,
}

/// Receive one full run: NewSession, running status, streamed deltas, finish,
/// idle status. Panics on any out-of-order lifecycle message.
async fn receive_run(stream: &mut TcpStream, session_id: &mut String, run_ids: &mut std::collections::HashSet<String>) -> RunTrace {
    let first = receive(stream).await;
    let Some(forward_msg::Type::NewSession(new_session)) = first.r#type else {
        panic!("a run must start with NewSession, got {:?}", first.r#type)
    };
    let init = new_session.initialize.unwrap();
    if session_id.is_empty() {
        *session_id = init.session_id;
    } else {
        assert_eq!(init.session_id, *session_id, "an in-run rerun keeps the session");
    }
    assert!(run_ids.insert(new_session.script_run_id), "every run needs a fresh script_run_id");
    assert!(matches!(receive(stream).await.r#type, Some(forward_msg::Type::SessionStatusChanged(status)) if status.script_is_running));
    let mut trace = RunTrace {
        markdowns: vec![],
        exceptions: vec![],
        finish_statuses: vec![],
    };
    loop {
        match receive(stream).await.r#type {
            Some(forward_msg::Type::Delta(delta)) => {
                if let Some(delta::Type::NewElement(new_element)) = delta.r#type {
                    match new_element.r#type {
                        Some(element::Type::Markdown(text)) => trace.markdowns.push(text.body),
                        Some(element::Type::Exception(exception)) => trace.exceptions.push((exception.r#type, exception.message)),
                        _ => {}
                    }
                }
            }
            Some(forward_msg::Type::ScriptFinished(status)) => trace.finish_statuses.push(status),
            Some(forward_msg::Type::SessionStatusChanged(status)) if !status.script_is_running => break,
            other => panic!("unexpected lifecycle response: {other:?}"),
        }
    }
    trace
}

async fn start_server(entry: fn(&Streamlit) -> Pin<Box<dyn Future<Output = ()> + '_>>) -> (std::net::SocketAddr, actix_web::dev::ServerHandle, tokio::task::JoinHandle<std::io::Result<()>>, TcpStream) {
    let listener = std::net::TcpListener::bind("127.0.0.1:0").unwrap();
    let address = listener.local_addr().unwrap();
    let server = HttpServer::new(move || App::new().app_data(web::Data::new(StreamlitServer::new(entry, "127.0.0.1".into(), 0))).configure(configure_routes))
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
    (address, handle, task, stream)
}

fn rerun_request() -> Vec<u8> {
    BackMsg {
        r#type: Some(back_msg::Type::RerunScript(ClientState {
            widget_states: Some(WidgetStates { widgets: vec![] }),
            ..Default::default()
        })),
    }
    .encode_to_vec()
}

#[actix_web::test]
async fn st_rerun_finishes_early_and_the_server_starts_the_next_run_without_a_backmsg() {
    let (_address, handle, task, mut stream) = start_server(rerun_entry).await;
    // Exactly ONE BackMsg: the in-run rerun must not wait for the browser.
    send_binary(&mut stream, &rerun_request()).await;
    let mut session_id = String::new();
    let mut run_ids = std::collections::HashSet::new();
    let first = receive_run(&mut stream, &mut session_id, &mut run_ids).await;
    assert_eq!(first.finish_statuses, [2], "the aborted run finishes FINISHED_EARLY_FOR_RERUN");
    assert_eq!(first.markdowns, ["runs-marker"], "elements streamed before st.rerun stay; later ones are suppressed");
    let second = receive_run(&mut stream, &mut session_id, &mut run_ids).await;
    assert_eq!(second.finish_statuses, [0]);
    assert_eq!(second.markdowns, ["runs-marker", "epilogue"], "the rerun re-executes with persisted state and renders the epilogue");
    drop(stream);
    handle.stop(false).await;
    task.await.unwrap().unwrap();
}

#[actix_web::test]
async fn st_stop_finishes_successfully_and_suppresses_later_elements_and_writes() {
    let (_address, handle, task, mut stream) = start_server(stop_entry).await;
    send_binary(&mut stream, &rerun_request()).await;
    let mut session_id = String::new();
    let mut run_ids = std::collections::HashSet::new();
    let first = receive_run(&mut stream, &mut session_id, &mut run_ids).await;
    assert_eq!(first.finish_statuses, [0], "st.stop finishes FINISHED_SUCCESSFULLY on the measured wire");
    assert_eq!(first.markdowns, ["before-stop"], "the prefix stays and the epilogue never emits");
    send_binary(&mut stream, &rerun_request()).await;
    let second = receive_run(&mut stream, &mut session_id, &mut run_ids).await;
    assert_eq!(second.finish_statuses, [0]);
    assert_eq!(second.markdowns, ["late-is-present=false"], "a session-state write after st.stop() never lands");
    drop(stream);
    handle.stop(false).await;
    task.await.unwrap().unwrap();
}

#[actix_web::test]
async fn duplicate_widget_key_renders_the_reference_exception_and_suppresses_the_rest() {
    let (_address, handle, task, mut stream) = start_server(duplicate_key_entry).await;
    let mut session_id = String::new();
    let mut run_ids = std::collections::HashSet::new();
    send_binary(&mut stream, &rerun_request()).await;
    let first = receive_run(&mut stream, &mut session_id, &mut run_ids).await;
    assert_eq!(first.finish_statuses, [0]);
    assert_eq!(first.markdowns, ["first"]);
    assert!(first.exceptions.is_empty());
    send_binary(&mut stream, &rerun_request()).await;
    let second = receive_run(&mut stream, &mut session_id, &mut run_ids).await;
    assert_eq!(second.finish_statuses, [0], "the takeover run finishes FINISHED_SUCCESSFULLY (measured dup_key wire)");
    assert!(second.markdowns.is_empty(), "nothing renders after the exception element");
    assert_eq!(
        second.exceptions,
        [(
            "streamlit.errors.StreamlitDuplicateElementKey".to_owned(),
            "There are multiple elements with the same `key='group'`. To fix this, please make sure that the `key` argument is unique for each element you create.".to_owned(),
        )],
        "the exception element matches the reference type and message exactly"
    );
    // A third rerun proves the session keeps serving; upstream raises again.
    send_binary(&mut stream, &rerun_request()).await;
    let third = receive_run(&mut stream, &mut session_id, &mut run_ids).await;
    assert_eq!(third.finish_statuses, [0]);
    assert_eq!(third.exceptions.len(), 1);
    drop(stream);
    handle.stop(false).await;
    task.await.unwrap().unwrap();
}
