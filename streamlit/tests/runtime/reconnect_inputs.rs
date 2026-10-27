//! Interface regression only: real HTTP upload + WS selector/state recovery.
//! This does not exercise the browser, CSV aggregation, or the optional slow TTL.
use super::*;
use crate::{FileUploaderOptions, InputWidgets, SelectboxOptions, UploadedFiles};
use serde_json::{Value, json};
use std::collections::{HashMap, HashSet};

fn inputs(st: &Streamlit) -> Pin<Box<dyn Future<Output = ()> + '_>> {
    Box::pin(async move {
        let result: TestResult = async {
            let UploadedFiles::Single(file) = st.file_uploader(FileUploaderOptions::new("Upload sales CSV").accepted_types(["csv"]).key("upload"))? else {
                return Err("single-file uploader must return UploadedFiles::Single".into());
            };
            let group = st.selectbox(SelectboxOptions::new("Group by", ["category", "region"]).key("group_by"))?;
            let state = st.session_state();
            let pulses = state.get::<u64>("pulses")?.unwrap_or(0) + u64::from(st.button("Pulse"));
            let runs = state.get::<u64>("runs")?.unwrap_or(0) + 1;
            state.set("pulses", pulses)?;
            state.set("runs", runs)?;
            st.write(format!("reconnect_inputs={}", json!({"file":file.map(|f|f.as_bytes().to_vec()),"group":group,"pulses":pulses,"runs":runs})));
            Ok(())
        }
        .await;
        assert!(result.is_ok(), "inputs fixture failed: {result:?}");
    })
}

struct InputRun {
    session: String,
    run: String,
    ids: HashMap<&'static str, String>,
    values: Value,
}

async fn run(socket: &mut TcpStream, widgets: Vec<WidgetState>) -> TestResult<InputRun> {
    let message = BackMsg {
        r#type: Some(back_msg::Type::RerunScript(ClientState {
            widget_states: Some(WidgetStates { widgets }),
            ..Default::default()
        })),
    };
    send_binary(socket, &message.encode_to_vec()).await;
    let Some(forward_msg::Type::NewSession(new)) = receive(socket).await.r#type else { panic!("run must begin with NewSession") };
    let mut result = InputRun {
        session: new.initialize.ok_or("NewSession must include initialization")?.session_id,
        run: new.script_run_id,
        ids: HashMap::new(),
        values: Value::Null,
    };
    let mut finished = 0;
    let mut markers = 0;
    loop {
        match receive(socket).await.r#type {
            Some(forward_msg::Type::Delta(delta)) => {
                if let Some(delta::Type::NewElement(element)) = delta.r#type {
                    match element.r#type {
                        Some(element::Type::FileUploader(widget)) => assert!(result.ids.insert("upload", widget.id).is_none()),
                        Some(element::Type::Selectbox(widget)) => assert!(result.ids.insert("group", widget.id).is_none()),
                        Some(element::Type::Button(widget)) => assert!(result.ids.insert("pulse", widget.id).is_none()),
                        Some(element::Type::Markdown(text)) if text.body.starts_with("reconnect_inputs=") => {
                            markers += 1;
                            result.values = serde_json::from_str(text.body.strip_prefix("reconnect_inputs=").ok_or("input report must have reconnect_inputs prefix")?)?;
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
            Some(forward_msg::Type::NewSession(_)) => panic!("duplicate run initialization"),
            _ => {}
        }
    }
    assert_eq!((finished, markers, result.ids.len()), (1, 1, 3));
    assert!(!result.run.is_empty());
    Ok(result)
}

#[actix_web::test]
async fn reconnect_retains_upload_through_selector_only_runs_without_replaying_pulse() -> TestResult {
    let listener = std::net::TcpListener::bind("127.0.0.1:0")?;
    let address = listener.local_addr()?;
    let server_state = StreamlitServer::new(inputs, "127.0.0.1".into(), 0);
    let server = HttpServer::new(move || App::new().app_data(web::Data::new(server_state.clone())).configure(configure_routes)).workers(2).listen(listener)?.run();
    let handle = server.handle();
    let task = actix_web::rt::spawn(server);
    let mut socket = connect(address, None).await;
    assert_handshake_idle(&mut socket).await;
    let first = run(&mut socket, vec![]).await?;
    assert_eq!(first.values, json!({"file":null,"group":"category","pulses":0,"runs":1}));
    let mut runs = HashSet::from([first.run]);

    let request = BackMsg {
        r#type: Some(back_msg::Type::FileUrlsRequest(crate::proto::FileUrLsRequest {
            request_id: "retained-upload".into(),
            file_names: vec!["sales_basic.csv".into()],
            session_id: first.session.clone(),
        })),
    };
    send_binary(&mut socket, &request.encode_to_vec()).await;
    let Some(forward_msg::Type::FileUrlsResponse(response)) = receive(&mut socket).await.r#type else { panic!() };
    assert_eq!(response.response_id, "retained-upload");
    assert!(response.error_msg.is_empty());
    assert_eq!(response.file_urls.len(), 1);
    let urls = &response.file_urls[0];
    assert_eq!(urls.upload_url, format!("/_stcore/upload_file/{}/{}", first.session, urls.file_id));
    let bytes = include_bytes!("../../../tests/fixtures/csv/sales_basic.csv");
    // One real multipart PUT, before the disconnect. The fixed matching XSRF
    // cookie/header follows the already covered HTTP gate; no new auth oracle.
    let mut body = b"--retained\r\nContent-Disposition: form-data; name=\"file\"; filename=\"sales_basic.csv\"\r\nContent-Type: text/csv\r\n\r\n".to_vec();
    body.extend_from_slice(bytes);
    body.extend_from_slice(b"\r\n--retained--\r\n");
    let mut http = TcpStream::connect(address).await?;
    let headers = format!(
        "PUT {} HTTP/1.1\r\nHost: {address}\r\nCookie: _streamlit_xsrf=48dc\r\nX-Xsrftoken: 48dc\r\nContent-Type: multipart/form-data; boundary=retained\r\nContent-Length: {}\r\nConnection: close\r\n\r\n",
        urls.upload_url,
        body.len()
    );
    http.write_all(headers.as_bytes()).await?;
    http.write_all(&body).await?;
    let mut reply = Vec::new();
    tokio::time::timeout(Duration::from_secs(5), http.read_to_end(&mut reply)).await??;
    assert!(reply.starts_with(b"HTTP/1.1 204 "));
    let uploaded = run(
        &mut socket,
        vec![WidgetState {
            id: first.ids["upload"].clone(),
            value: Some(widget_state::Value::FileUploaderStateValue(crate::proto::FileUploaderState {
                uploaded_file_info: vec![crate::proto::UploadedFileInfo {
                    file_id: urls.file_id.clone(),
                    name: "sales_basic.csv".into(),
                    size: bytes.len() as u64,
                    file_urls: Some(urls.clone()),
                }],
            })),
        }],
    )
    .await?;
    assert_eq!(uploaded.session, first.session);
    assert_eq!(uploaded.values, json!({"file":bytes.as_slice(),"group":"category","pulses":0,"runs":2}));
    assert!(runs.insert(uploaded.run));
    for pulse in 1..=2 {
        let click = run(
            &mut socket,
            vec![WidgetState {
                id: first.ids["pulse"].clone(),
                value: Some(widget_state::Value::TriggerValue(true)),
            }],
        )
        .await?;
        assert_eq!(click.session, first.session);
        assert_eq!(click.values, json!({"file":bytes.as_slice(),"group":"category","pulses":pulse,"runs":pulse+2}));
        assert!(runs.insert(click.run));
    }
    disconnect(socket).await;
    let mut restored = connect(address, Some(&first.session)).await;
    assert_handshake_idle(&mut restored).await;
    // No PUT, file-state resubmission, or trigger after recovery: only two real
    // selector batches, proving both the stored bytes and one-shot reset.
    for (group, expected_runs) in [("region", 5), ("category", 6)] {
        let next = run(
            &mut restored,
            vec![WidgetState {
                id: first.ids["group"].clone(),
                value: Some(widget_state::Value::StringValue(group.into())),
            }],
        )
        .await?;
        assert_eq!(next.session, first.session);
        assert_eq!(next.ids, first.ids);
        assert_eq!(next.values, json!({"file":bytes.as_slice(),"group":group,"pulses":2,"runs":expected_runs}));
        assert!(runs.insert(next.run));
    }
    assert_eq!(runs.len(), 6);
    let mut fresh = connect(address, None).await;
    assert_handshake_idle(&mut fresh).await;
    let reset = run(&mut fresh, vec![]).await?;
    assert_ne!(reset.session, first.session);
    assert_eq!(reset.values, json!({"file":null,"group":"category","pulses":0,"runs":1}));
    assert!(runs.insert(reset.run));
    disconnect(fresh).await;
    disconnect(restored).await;
    handle.stop(false).await;
    task.await??;
    Ok(())
}
