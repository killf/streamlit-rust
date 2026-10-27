use super::*;

#[path = "reconnect_inputs.rs"]
mod reconnect_inputs;

async fn assert_handshake_idle(stream: &mut TcpStream) {
    // The acknowledged heartbeat makes this a live handler observation, not a
    // sleep before the server has attached the socket. Neither message runs main.
    send_binary(stream, &[0x88, 0x01, 0x01]).await;
    assert!(matches!(receive(stream).await.r#type, Some(forward_msg::Type::HeartbeatAck(true))));
    assert!(tokio::time::timeout(Duration::from_millis(75), stream.read_u8()).await.is_err(), "handshake/heartbeat unexpectedly emitted application output");
}

fn counter(st: &Streamlit) -> Pin<Box<dyn Future<Output = ()> + '_>> {
    Box::pin(async move {
        let result: TestResult = async {
            let state = st.session_state();
            let pulses = state.get::<u64>("pulses")?.unwrap_or(0) + u64::from(st.button("Pulse"));
            state.set("pulses", pulses)?;
            let runs = state.get::<u64>("runs")?.unwrap_or(0) + 1;
            state.set("runs", runs)?;
            st.write(format!("Pulses: {pulses}"));
            st.write(format!("Runs: {runs}"));
            Ok(())
        }
        .await;
        assert!(result.is_ok(), "counter fixture failed: {result:?}");
    })
}

async fn start(ttl: Duration) -> TestResult<(std::net::SocketAddr, actix_web::dev::ServerHandle, actix_web::rt::task::JoinHandle<std::io::Result<()>>)> {
    let listener = std::net::TcpListener::bind("127.0.0.1:0")?;
    let address = listener.local_addr()?;
    // One server-owned registry shared across workers, like production start().
    let state = StreamlitServer::new(counter, "127.0.0.1".into(), 0).with_disconnected_session_ttl(ttl);
    let server = HttpServer::new(move || App::new().app_data(web::Data::new(state.clone())).configure(configure_routes)).workers(2).listen(listener)?.run();
    let handle = server.handle();
    Ok((address, handle, actix_web::rt::spawn(server)))
}

pub(super) async fn connect(address: std::net::SocketAddr, requested_id: Option<&str>) -> TcpStream {
    let protocol = requested_id.map_or_else(|| "streamlit, test-token".to_owned(), |id| format!("streamlit, test-token, {id}"));
    let (stream, headers) = match handshake(address, &protocol).await {
        Ok(connection) => connection,
        Err(error) => panic!("WebSocket handshake with {address} failed: {error}"),
    };
    assert!(headers.starts_with("http/1.1 101"), "{headers}");
    assert!(headers.contains("sec-websocket-protocol: streamlit\r\n"));
    stream
}

async fn handshake(address: std::net::SocketAddr, protocol: &str) -> TestResult<(TcpStream, String)> {
    tokio::time::timeout(Duration::from_secs(5), async {
        let mut stream = TcpStream::connect(address).await?;
        let request = format!("GET /_stcore/stream HTTP/1.1\r\nHost: {address}\r\nConnection: Upgrade\r\nUpgrade: websocket\r\nSec-WebSocket-Version: 13\r\nSec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==\r\nSec-WebSocket-Protocol: {protocol}\r\n\r\n");
        stream.write_all(request.as_bytes()).await?;
        let mut headers = Vec::new();
        while !headers.ends_with(b"\r\n\r\n") {
            headers.push(stream.read_u8().await?);
            assert!(headers.len() < 8192);
        }
        Ok::<_, Box<dyn std::error::Error>>((stream, String::from_utf8(headers)?.to_ascii_lowercase()))
    })
    .await?
}

struct Run {
    session_id: String,
    button_id: String,
    pulses: u64,
    runs: u64,
}

async fn rerun(stream: &mut TcpStream, clicked_button: Option<&str>) -> TestResult<Run> {
    let widgets = clicked_button
        .map(|id| WidgetState {
            id: id.to_owned(),
            value: Some(widget_state::Value::TriggerValue(true)),
        })
        .into_iter()
        .collect();
    let msg = BackMsg {
        r#type: Some(back_msg::Type::RerunScript(ClientState {
            widget_states: Some(WidgetStates { widgets }),
            ..Default::default()
        })),
    };
    send_binary(stream, &msg.encode_to_vec()).await;
    let mut session_id = None;
    let mut button_id = None;
    let mut pulses = None;
    let mut runs = None;
    let mut finished = 0;
    loop {
        match receive(stream).await.r#type {
            Some(forward_msg::Type::NewSession(new)) => session_id = Some(new.initialize.ok_or("NewSession must include initialization")?.session_id),
            Some(forward_msg::Type::Delta(delta)) => {
                if let Some(delta::Type::NewElement(element)) = delta.r#type {
                    match element.r#type {
                        Some(element::Type::Button(button)) => button_id = Some(button.id),
                        Some(element::Type::Markdown(text)) => {
                            if let Some(value) = text.body.strip_prefix("Pulses: ") {
                                pulses = Some(value.parse()?);
                            }
                            if let Some(value) = text.body.strip_prefix("Runs: ") {
                                runs = Some(value.parse()?);
                            }
                        }
                        _ => {}
                    }
                }
            }
            Some(forward_msg::Type::ScriptFinished(status)) => {
                assert_eq!(status, 0);
                finished += 1;
            }
            Some(forward_msg::Type::SessionStatusChanged(status)) if !status.script_is_running => break,
            _ => {}
        }
    }
    assert_eq!(finished, 1);
    Ok(Run {
        session_id: session_id.ok_or("counter run must report session id")?,
        button_id: button_id.ok_or("counter run must render Pulse button")?,
        pulses: pulses.ok_or("counter run must report Pulses value")?,
        runs: runs.ok_or("counter run must report Runs value")?,
    })
}

// Close the actual WebSocket without a reload, as the browser oracle does.
// Confirm the server's close reply before making a reconnect request; an HTTP
// keep-alive socket need not reach TCP EOF at this point.
pub(super) async fn disconnect(mut stream: TcpStream) {
    let closed: TestResult = async {
        stream.write_all(&[0x88, 0x80, 0x12, 0x34, 0x56, 0x78]).await?;
        tokio::time::timeout(Duration::from_secs(5), async {
            let mut header = [0; 2];
            stream.read_exact(&mut header).await?;
            assert_eq!(header[0], 0x88);
            assert_eq!(header[1] & 0x80, 0);
            let mut body = vec![0; header[1] as usize];
            stream.read_exact(&mut body).await?;
            Ok::<_, std::io::Error>(())
        })
        .await??;
        Ok(())
    }
    .await;
    assert!(closed.is_ok(), "closing WebSocket and receiving close acknowledgement failed: {closed:?}");
}

#[actix_web::test]
async fn counter_survives_reruns_reconnects_and_stays_isolated_across_workers() -> TestResult {
    let (address, handle, task) = start(Duration::from_secs(120)).await?;
    let mut a = connect(address, None).await;
    assert_handshake_idle(&mut a).await;
    let first = rerun(&mut a, None).await?;
    assert_eq!((first.pulses, first.runs), (0, 1));
    let id = first.session_id;
    for expected in [1, 2] {
        let run = rerun(&mut a, Some(&first.button_id)).await?;
        assert_eq!(run.session_id, id);
        assert_eq!(run.pulses, expected);
    }
    let ordinary = rerun(&mut a, None).await?;
    assert_eq!((ordinary.pulses, ordinary.runs), (2, 4), "ordinary rerun must retain state without replaying trigger");

    let mut b = connect(address, None).await;
    let second = rerun(&mut b, None).await?;
    assert_ne!(second.session_id, id);
    assert_eq!((second.pulses, second.runs), (0, 1));
    let (a_run, b_run) = tokio::try_join!(rerun(&mut a, Some(&first.button_id)), rerun(&mut b, None))?;
    assert_eq!((a_run.pulses, b_run.pulses), (3, 0));
    assert_eq!(b_run.session_id, second.session_id);

    disconnect(a).await;
    let mut restored = connect(address, Some(&id)).await;
    assert_handshake_idle(&mut restored).await;
    let after = rerun(&mut restored, None).await?;
    assert_eq!(after.session_id, id);
    assert_eq!((after.pulses, after.runs), (3, 6));
    let incremented = rerun(&mut restored, Some(&after.button_id)).await?;
    assert_eq!(incremented.pulses, 4, "post-reconnect click must really execute");
    assert_eq!(rerun(&mut b, Some(&second.button_id)).await?.pulses, 1);
    assert_eq!(rerun(&mut restored, None).await?.pulses, 4);
    disconnect(restored).await;

    // Refresh/fresh load omits the third subprotocol and starts from zero.
    let mut fresh = connect(address, None).await;
    assert_handshake_idle(&mut fresh).await;
    let reset = rerun(&mut fresh, None).await?;
    assert_ne!(reset.session_id, id);
    assert_ne!(reset.session_id, second.session_id);
    assert_eq!((reset.pulses, reset.runs), (0, 1));
    disconnect(fresh).await;
    disconnect(b).await;
    handle.stop(false).await;
    task.await??;
    Ok(())
}

#[actix_web::test]
async fn local_zero_retention_and_unknown_lookup_start_empty_sessions() -> TestResult {
    // Zero retention makes expiry deterministic at the first disconnected lookup.
    let (address, handle, task) = start(Duration::ZERO).await?;
    let mut old = connect(address, None).await;
    let run = rerun(&mut old, None).await?;
    assert_eq!(rerun(&mut old, Some(&run.button_id)).await?.pulses, 1);
    disconnect(old).await;
    let mut expired = connect(address, Some(&run.session_id)).await;
    let replacement = rerun(&mut expired, None).await?;
    assert_ne!(replacement.session_id, run.session_id);
    assert_eq!((replacement.pulses, replacement.runs), (0, 1));
    let unknown_id = uuid::Uuid::new_v4().to_string();
    let mut unknown = connect(address, Some(&unknown_id)).await;
    let replacement = rerun(&mut unknown, None).await?;
    assert_ne!(replacement.session_id, unknown_id);
    assert_eq!((replacement.pulses, replacement.runs), (0, 1));
    disconnect(expired).await;
    disconnect(unknown).await;
    // The official browser probe accepted an opaque non-UUID third entry too.
    let mut opaque = connect(address, Some("unknown-session")).await;
    let replacement = rerun(&mut opaque, None).await?;
    assert_ne!(replacement.session_id, "unknown-session");
    assert_eq!((replacement.pulses, replacement.runs), (0, 1));
    disconnect(opaque).await;
    handle.stop(false).await;
    task.await??;
    Ok(())
}

#[actix_web::test]
async fn known_id_accepts_new_owner_and_old_connection_drop_cannot_expire_it() -> TestResult {
    // Zero retention makes an erroneous stale-owner disconnect immediately
    // observable on the next lookup, instead of hiding it behind a long TTL.
    let (address, handle, task) = start(Duration::ZERO).await?;
    let mut original = connect(address, None).await;
    let first = rerun(&mut original, None).await?;
    assert_eq!(rerun(&mut original, Some(&first.button_id)).await?.pulses, 1);
    let mut replacement = connect(address, Some(&first.session_id)).await;
    let recovered = rerun(&mut replacement, None).await?;
    assert_eq!(recovered.session_id, first.session_id);
    assert_eq!(recovered.pulses, 1);
    disconnect(original).await;
    assert_eq!(rerun(&mut replacement, None).await?.pulses, 1);
    let mut latest = connect(address, Some(&first.session_id)).await;
    let recovered = rerun(&mut latest, None).await?;
    assert_eq!(recovered.session_id, first.session_id);
    assert_eq!(recovered.pulses, 1, "old lease must not mark the replacement disconnected");
    disconnect(replacement).await;
    assert_eq!(rerun(&mut latest, Some(&recovered.button_id)).await?.pulses, 2);
    assert_eq!(rerun(&mut latest, None).await?.pulses, 2);
    disconnect(latest).await;
    handle.stop(false).await;
    task.await??;
    Ok(())
}
