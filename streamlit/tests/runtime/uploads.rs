//! Successful HTTP/WS upload path and native session isolation. Negative HTTP
//! status/body compatibility and DELETE remain pending dedicated reference data.
use super::*;
use crate::{FileUploaderOptions, InputWidgets, UploadedFiles};
use serde_json::{Value, json};

fn upload_entry(st: &Streamlit) -> Pin<Box<dyn Future<Output = ()> + '_>> {
    Box::pin(async move {
        let selected = st
            .file_uploader(FileUploaderOptions::new("Upload sales CSV").accepted_types(["csv"]).key("upload").on_change(|st| {
                let n = st.session_state().get::<u64>("uploads_changed").unwrap().unwrap_or(0);
                st.session_state().set("uploads_changed", n + 1).unwrap();
            }))
            .unwrap();
        let UploadedFiles::Single(file) = selected else { panic!() };
        let content = file.map(|file| json!({"name":file.name(),"type":file.content_type(),"size":file.size(),"bytes":file.as_bytes()}));
        st.write(format!("uploaded={}", json!({"file":content,"callbacks":st.session_state().get::<u64>("uploads_changed").unwrap().unwrap_or(0)})));
    })
}

struct Run {
    session: String,
    widget: String,
    value: Value,
}
async fn run(socket: &mut TcpStream, widgets: Vec<WidgetState>) -> Run {
    let request = BackMsg {
        r#type: Some(back_msg::Type::RerunScript(ClientState {
            widget_states: Some(WidgetStates { widgets }),
            ..Default::default()
        })),
    };
    send_binary(socket, &request.encode_to_vec()).await;
    let mut run = Run {
        session: String::new(),
        widget: String::new(),
        value: Value::Null,
    };
    let mut finished = false;
    loop {
        match receive(socket).await.r#type {
            Some(forward_msg::Type::NewSession(new)) => run.session = new.initialize.unwrap().session_id,
            Some(forward_msg::Type::Delta(crate::proto::Delta {
                r#type: Some(delta::Type::NewElement(element)), ..
            })) => match element.r#type {
                Some(element::Type::FileUploader(file)) => run.widget = file.id,
                Some(element::Type::Markdown(text)) => {
                    if let Some(value) = text.body.strip_prefix("uploaded=") {
                        run.value = serde_json::from_str(value).unwrap();
                    }
                }
                _ => (),
            },
            Some(forward_msg::Type::ScriptFinished(status)) => {
                assert_eq!(status, 0);
                finished = true;
            }
            Some(forward_msg::Type::SessionStatusChanged(status)) if !status.script_is_running => {
                assert!(finished);
                break;
            }
            _ => (),
        }
    }
    assert!(!run.widget.is_empty() && !run.session.is_empty() && !run.value.is_null());
    run
}

async fn urls(socket: &mut TcpStream, session: &str) -> crate::proto::FileUrLs {
    let request = BackMsg {
        r#type: Some(back_msg::Type::FileUrlsRequest(crate::proto::FileUrLsRequest {
            request_id: "upload-request".into(),
            file_names: vec!["sales_basic.csv".into()],
            session_id: session.into(),
        })),
    };
    send_binary(socket, &request.encode_to_vec()).await;
    let Some(forward_msg::Type::FileUrlsResponse(response)) = receive(socket).await.r#type else { panic!() };
    assert_eq!(response.response_id, "upload-request");
    assert!(response.error_msg.is_empty());
    assert_eq!(response.file_urls.len(), 1);
    let urls = response.file_urls.into_iter().next().unwrap();
    assert_eq!(urls.upload_url, format!("/_stcore/upload_file/{session}/{}", urls.file_id));
    assert_eq!(urls.delete_url, urls.upload_url);
    urls
}

fn file_state(widget: &str, urls: &crate::proto::FileUrLs) -> Vec<WidgetState> {
    vec![WidgetState {
        id: widget.into(),
        value: Some(widget_state::Value::FileUploaderStateValue(crate::proto::FileUploaderState {
            uploaded_file_info: vec![crate::proto::UploadedFileInfo {
                name: "sales_basic.csv".into(),
                size: 737,
                file_id: urls.file_id.clone(),
                file_urls: Some(urls.clone()),
            }],
        })),
    }]
}

async fn put(address: std::net::SocketAddr, url: &str, bytes: &[u8]) {
    let mut socket = TcpStream::connect(address).await.unwrap();
    let mut body = b"--native-test\r\nContent-Disposition: form-data; name=\"file\"; filename=\"sales_basic.csv\"\r\nContent-Type: text/csv\r\n\r\n".to_vec();
    body.extend_from_slice(bytes);
    body.extend_from_slice(b"\r\n--native-test--\r\n");
    let headers = format!(
        "PUT {url} HTTP/1.1\r\nHost: {address}\r\nContent-Type: multipart/form-data; boundary=native-test\r\nContent-Length: {}\r\nConnection: close\r\n\r\n",
        body.len()
    );
    socket.write_all(headers.as_bytes()).await.unwrap();
    socket.write_all(&body).await.unwrap();
    let mut response = Vec::new();
    tokio::time::timeout(Duration::from_secs(5), socket.read_to_end(&mut response)).await.unwrap().unwrap();
    let response = String::from_utf8_lossy(&response).to_lowercase();
    assert!(response.starts_with("http/1.1 204"), "{response}");
    assert!(response.contains("content-type: text/plain\r\n"));
}

#[actix_web::test]
async fn real_http_ws_upload_bytes_callbacks_reconnect_fresh_and_isolation() {
    let listener = std::net::TcpListener::bind("127.0.0.1:0").unwrap();
    let address = listener.local_addr().unwrap();
    let state = StreamlitServer::new(upload_entry, "127.0.0.1".into(), 0);
    let server = HttpServer::new(move || App::new().app_data(web::Data::new(state.clone())).configure(configure_routes)).workers(2).listen(listener).unwrap().run();
    let handle = server.handle();
    let task = actix_web::rt::spawn(server);
    let mut a = sessions::connect(address, None).await;
    let initial = run(&mut a, vec![]).await;
    assert_eq!(initial.value, json!({"file":null,"callbacks":0}));
    let a_urls = urls(&mut a, &initial.session).await;
    let fixture = include_bytes!("../../../tests/fixtures/csv/sales_basic.csv");
    assert_eq!(fixture.len(), 737);
    put(address, &a_urls.upload_url, fixture).await;
    let uploaded = run(&mut a, file_state(&initial.widget, &a_urls)).await;
    assert_eq!(uploaded.value["file"]["bytes"], json!(fixture.as_slice()));
    assert_eq!(uploaded.value["file"]["size"], 737);
    assert_eq!(uploaded.value["callbacks"], 1);
    let repeated = run(&mut a, file_state(&initial.widget, &a_urls)).await;
    assert_eq!(repeated.value, uploaded.value);
    let mut b = sessions::connect(address, None).await;
    let other = run(&mut b, vec![]).await;
    assert_ne!(other.session, initial.session);
    let spoofed = run(&mut b, file_state(&other.widget, &a_urls)).await;
    assert!(spoofed.value["file"].is_null(), "foreign IDs must not expose bytes");
    let b_urls = urls(&mut b, &other.session).await;
    put(address, &b_urls.upload_url, b"other session").await;
    let different = run(&mut b, file_state(&other.widget, &b_urls)).await;
    assert_eq!(different.value["file"]["bytes"], json!(b"other session".as_slice()));
    sessions::disconnect(a).await;
    let mut restored = sessions::connect(address, Some(&initial.session)).await;
    let recovered = run(&mut restored, vec![]).await;
    assert_eq!(recovered.session, initial.session);
    assert_eq!(recovered.value, uploaded.value);
    let mut fresh = sessions::connect(address, None).await;
    let empty = run(&mut fresh, vec![]).await;
    assert_ne!(empty.session, initial.session);
    assert!(empty.value["file"].is_null());
    sessions::disconnect(restored).await;
    sessions::disconnect(fresh).await;
    sessions::disconnect(b).await;
    handle.stop(true).await;
    task.await.unwrap().unwrap();
}
