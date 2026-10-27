//! Presentation regressions against the measured Python 1.66.1 wire (see
//! .codex/compatibility.md, Presentation widgets): the spinner rides two
//! new_transient deltas (active, then cleared, consuming no element path),
//! the toast routes to the dedicated root path [2, 0] with a four-second
//! duration and a one-shot flag, and balloons occupy the container's next
//! slot with the one-shot flag.
use super::*;
use crate::ToastOptions;

fn presentation_entry(st: &Streamlit) -> Pin<Box<dyn Future<Output = ()> + '_>> {
    Box::pin(async move {
        // Mirrors tests/reference/presentation_app.py.
        st.spinner("Loading data", || {
            std::thread::sleep(Duration::from_secs(2));
        });
        st.write("loaded");
        st.toast(ToastOptions::new("Saved successfully").icon("\u{2705}"));
        st.balloons();
    })
}

#[actix_web::test]
async fn presentation_widgets_match_the_measured_wire() {
    let listener = std::net::TcpListener::bind("127.0.0.1:0").unwrap();
    let address = listener.local_addr().unwrap();
    let server = HttpServer::new(move || App::new().app_data(web::Data::new(StreamlitServer::new(presentation_entry, "127.0.0.1".into(), 0))).configure(configure_routes))
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

    let request = BackMsg {
        r#type: Some(back_msg::Type::RerunScript(ClientState {
            widget_states: Some(WidgetStates { widgets: vec![] }),
            ..Default::default()
        })),
    };
    send_binary(&mut stream, &request.encode_to_vec()).await;
    assert!(matches!(receive(&mut stream).await.r#type, Some(forward_msg::Type::NewSession(_))));
    assert!(matches!(receive(&mut stream).await.r#type, Some(forward_msg::Type::SessionStatusChanged(status)) if status.script_is_running));

    // (kind, path) of every streamed delta, in order.
    let mut timeline: Vec<(String, Vec<u32>, String)> = Vec::new();
    let mut toast: Option<crate::proto::Toast> = None;
    let mut balloons: Option<crate::proto::Balloons> = None;
    let mut one_shot_count = 0usize;
    let mut markdowns = Vec::new();
    let mut finished = false;
    loop {
        let message = receive(&mut stream).await;
        let path = message.metadata.as_ref().map(|meta| meta.delta_path.clone()).unwrap_or_default();
        match message.r#type {
            Some(forward_msg::Type::Delta(delta)) => match delta.r#type {
                Some(delta::Type::NewTransient(transient)) => {
                    let text = transient
                        .elements
                        .first()
                        .and_then(|element| element.r#type.clone())
                        .map(|kind| match kind {
                            element::Type::Spinner(spinner) => format!("spinner:{}", spinner.text),
                            other => format!("other:{other:?}"),
                        })
                        .unwrap_or_else(|| "cleared".into());
                    timeline.push(("new_transient".into(), path, text));
                }
                Some(delta::Type::NewElement(element)) => {
                    let one_shot = element.has_one_shot_effect.unwrap_or(false);
                    let kind = match element.r#type {
                        Some(element::Type::Toast(wire)) => {
                            toast = Some(wire);
                            "toast".to_string()
                        }
                        Some(element::Type::Balloons(wire)) => {
                            balloons = Some(wire);
                            "balloons".to_string()
                        }
                        Some(element::Type::Markdown(text)) => {
                            markdowns.push(text.body);
                            "markdown".to_string()
                        }
                        Some(other) => format!("unexpected:{other:?}"),
                        None => "empty".to_string(),
                    };
                    one_shot_count += usize::from(one_shot);
                    timeline.push(("new_element".into(), path, kind));
                }
                Some(delta::Type::AddBlock(_)) => panic!("the wire never announces a block for this app"),
                None => {}
            },
            Some(forward_msg::Type::ScriptFinished(status)) => {
                assert_eq!(status, 0);
                assert!(!finished);
                finished = true;
            }
            Some(forward_msg::Type::SessionStatusChanged(status)) if !status.script_is_running => break,
            other => panic!("unexpected lifecycle response: {other:?}"),
        }
    }
    assert!(finished);

    let describe = |timeline: &[(String, Vec<u32>, String)]| timeline.iter().map(|(kind, path, detail)| format!("{kind}{path:?}:{detail}")).collect::<Vec<_>>().join(" | ");
    assert_eq!(
        describe(&timeline),
        "new_transient[0, 0]:spinner:Loading data | new_transient[0, 0]:cleared | new_element[0, 0]:markdown | new_element[2, 0]:toast | new_element[0, 1]:balloons",
        "the measured delta order, kinds and paths"
    );
    assert_eq!(markdowns, ["loaded"]);

    let toast = toast.expect("toast wire");
    assert_eq!(toast.body, "Saved successfully");
    assert_eq!(toast.icon, "\u{2705}");
    assert_eq!(toast.duration, Some(4), "the measured default is an explicit four seconds");
    assert!(balloons.expect("balloons wire").show);
    assert_eq!(one_shot_count, 2, "toast and balloons are one-shot; markdown is not");

    drop(stream);
    handle.stop(false).await;
    task.await.unwrap().unwrap();
}
