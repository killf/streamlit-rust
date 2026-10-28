use super::*;

fn paused_entry(st: &Streamlit) -> Pin<Box<dyn Future<Output = ()> + '_>> {
    Box::pin(async move {
        let result: TestResult = async {
            let state = st.session_state();
            if state.get::<bool>("pause_next")?.unwrap_or(false) {
                state.set("pause_next", false)?;
                st.write("old-paused");
                // The test, not elapsed wall time, releases this await. State and
                // output after it reproduce the original in-flight ownership bug.
                tokio::time::timeout(Duration::from_secs(5), async {
                    while !state.get::<bool>("release_old")?.unwrap_or(false) {
                        tokio::time::sleep(Duration::from_millis(1)).await;
                    }
                    Ok::<_, serde_json::Error>(())
                })
                .await??;
                state.set("phase", "old-completed-before-transfer")?;
                st.write("old-completed-before-transfer");
            } else {
                st.write(format!("before:{}", state.get::<String>("phase")?.unwrap_or_else(|| "empty".into())));
                state.set("phase", "new-owner")?;
                st.write("new-owner");
            }
            Ok(())
        }
        .await;
        assert!(result.is_ok(), "paused_entry fixture failed: {result:?}");
    })
}

async fn request_run(stream: &mut TcpStream) {
    send_binary(
        stream,
        &BackMsg {
            r#type: Some(back_msg::Type::RerunScript(ClientState::default())),
        }
        .encode_to_vec(),
    )
    .await;
}

fn markdown(message: ForwardMsg) -> Option<String> {
    if let Some(forward_msg::Type::Delta(delta)) = message.r#type
        && let Some(delta::Type::NewElement(element)) = delta.r#type
        && let Some(element::Type::Markdown(text)) = element.r#type
    {
        return Some(text.body);
    }
    None
}

async fn finish_run(stream: &mut TcpStream) -> Vec<String> {
    let mut texts = Vec::new();
    let mut finished = 0;
    loop {
        let message = receive(stream).await;
        match &message.r#type {
            Some(forward_msg::Type::ScriptFinished(status)) => {
                assert_eq!(*status, 0);
                finished += 1;
            }
            Some(forward_msg::Type::SessionStatusChanged(status)) if !status.script_is_running => break,
            _ => {}
        }
        if let Some(text) = markdown(message) {
            texts.push(text);
        }
    }
    assert_eq!(finished, 1);
    texts
}

#[actix_web::test]
async fn takeover_waits_for_awaiting_old_run_without_blocking_other_sessions() -> TestResult {
    let listener = std::net::TcpListener::bind("127.0.0.1:0")?;
    let address = listener.local_addr()?;
    let server_state = StreamlitServer::new(paused_entry, "127.0.0.1".into(), 0);
    let seed = server_state.sessions.connect(None, Default::default(), Default::default()).await;
    let id = seed.id.clone();
    let control = seed.state.clone();
    control.set("pause_next", true)?;
    drop(seed);
    let store = server_state.sessions.clone();
    let server = HttpServer::new(move || App::new().app_data(web::Data::new(server_state.clone())).configure(configure_routes)).workers(2).listen(listener)?.run();
    let handle = server.handle();
    let task = actix_web::rt::spawn(server);
    let mut old = sessions::connect(address, Some(&id)).await;
    request_run(&mut old).await;
    loop {
        if markdown(receive(&mut old).await).as_deref() == Some("old-paused") {
            break;
        }
    }
    let original_owner = store.owner_for_test(&id).ok_or("connected session must have an owner")?;
    // Upgrade succeeds while A is suspended; ownership must not transfer yet.
    let mut new = sessions::connect(address, Some(&id)).await;
    request_run(&mut new).await;
    assert!(tokio::time::timeout(Duration::from_millis(30), new.read_u8()).await.is_err());
    assert_eq!(store.owner_for_test(&id), Some(original_owner), "S1: ownership changed while the old entry was suspended");

    // This real third connection proves no registry-wide mutex is held across
    // the wait for A: a different session can render and finish before release.
    let mut other = sessions::connect(address, None).await;
    request_run(&mut other).await;
    assert_eq!(finish_run(&mut other).await, ["before:empty", "new-owner"]);
    assert!(!control.get::<bool>("release_old")?.unwrap_or(false));
    assert_eq!(store.owner_for_test(&id), Some(original_owner));

    control.set("release_old", true)?;
    assert_eq!(finish_run(&mut old).await, ["old-completed-before-transfer"]);
    let first_new = receive(&mut new).await;
    assert!(matches!(first_new.r#type, Some(forward_msg::Type::NewSession(session)) if session.initialize.as_ref().is_some_and(|init| init.session_id == id)));
    assert_ne!(store.owner_for_test(&id), Some(original_owner));
    assert_eq!(finish_run(&mut new).await, ["before:old-completed-before-transfer", "new-owner"]);

    // Once transferred, a stale socket must neither rerun nor send stale output.
    request_run(&mut old).await;
    let mut close = [0; 2];
    tokio::time::timeout(Duration::from_secs(5), old.read_exact(&mut close)).await??;
    assert_eq!(close[0], 0x88, "stale socket emitted output after ownership transferred");
    assert_eq!(control.get::<String>("phase")?.as_deref(), Some("new-owner"));
    drop(old);
    sessions::disconnect(new).await;
    sessions::disconnect(other).await;
    handle.stop(false).await;
    task.await??;
    Ok(())
}
