//! Write-stream regression against the measured Python 1.66.1 wire (see
//! .codex/compatibility.md, Write stream): st.write_stream grows one markdown
//! element per chunk — the accumulated body, cleaned like the reference's
//! clean_text, with unterminated parsing and the cursor on every chunk after
//! the first — and closes with a cursor-less flush. The reference's message
//! queue coalesces the placeholder with the first same-path write, so no
//! empty element ever reaches the wire.
use super::*;
use crate::StreamlitApi;
use crate::proto::forward_msg;

fn writestream_entry(st: &Streamlit) -> Pin<Box<dyn Future<Output = ()> + '_>> {
    Box::pin(async move {
        // Mirrors tests/reference/writestream_app.py.
        st.write_stream(["The ", "quick ", "**brown** ", "fox."]);
        st.write_stream_with_cursor("▌", ["Streamed ", "with ", "a ", "cursor."]);
    })
}

#[actix_web::test]
async fn write_stream_matches_the_measured_wire() -> TestResult {
    let listener = std::net::TcpListener::bind("127.0.0.1:0")?;
    let address = listener.local_addr()?;
    let server = HttpServer::new(move || App::new().app_data(web::Data::new(StreamlitServer::new(writestream_entry, "127.0.0.1".into(), 0))).configure(configure_routes))
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
        }
        Ok::<_, Box<dyn std::error::Error>>(String::from_utf8(response)?.to_ascii_lowercase())
    })
    .await??;
    assert!(headers.starts_with("http/1.1 101"));

    send_binary(
        &mut stream,
        &(BackMsg {
            r#type: Some(back_msg::Type::RerunScript(ClientState::default())),
        })
        .encode_to_vec(),
    )
    .await;

    let mut timeline: Vec<String> = Vec::new();
    loop {
        let message = receive(&mut stream).await;
        match message.r#type {
            Some(forward_msg::Type::NewSession(_)) => {}
            Some(forward_msg::Type::SessionStatusChanged(status)) if !status.script_is_running => break,
            Some(forward_msg::Type::Delta(delta)) => {
                let Some(delta::Type::NewElement(element)) = delta.r#type else { continue };
                let Some(kind) = element.r#type else { continue };
                if let element::Type::Markdown(markdown) = kind {
                    timeline.push(format!("markdown:{}:unterminated={}:wrap={:?}:type={}", markdown.body, markdown.unterminated_parsing, markdown.wrap, markdown.element_type));
                }
            }
            Some(forward_msg::Type::ScriptFinished(status)) => assert_eq!(status, 0),
            Some(forward_msg::Type::SessionStatusChanged(_)) => {}
            other => panic!("unexpected lifecycle response: {other:?}"),
        }
    }
    let joined = timeline.join(" | ");
    assert_eq!(
        joined,
        "markdown:The:unterminated=true:wrap=Some(true):type=1 | markdown:The quick:unterminated=true:wrap=Some(true):type=1 | markdown:The quick **brown**:unterminated=true:wrap=Some(true):type=1 | markdown:The quick **brown** fox.:unterminated=true:wrap=Some(true):type=1 | markdown:The quick **brown** fox.:unterminated=false:wrap=Some(true):type=1 | markdown:Streamed:unterminated=true:wrap=Some(true):type=1 | markdown:Streamed with ▌:unterminated=true:wrap=Some(true):type=1 | markdown:Streamed with a ▌:unterminated=true:wrap=Some(true):type=1 | markdown:Streamed with a cursor.▌:unterminated=true:wrap=Some(true):type=1 | markdown:Streamed with a cursor.:unterminated=false:wrap=Some(true):type=1",
        "the stream grows one markdown per chunk and closes with a cursor-less flush"
    );
    assert!(!joined.contains("empty"), "the placeholder is coalesced away like the reference queue does");

    drop(stream);
    handle.stop(false).await;
    task.await??;

    Ok(())
}
