//! Successful HTTP/WS upload path and native session isolation. Negative HTTP
//! status/body compatibility and DELETE remain pending dedicated reference data.
use super::*;
use crate::{FileUploaderOptions, InputWidgets, UploadedFiles};
use serde_json::{Value, json};

fn upload_entry(st: &Streamlit) -> Pin<Box<dyn Future<Output = ()> + '_>> {
    Box::pin(async move {
        let result: TestResult = async {
            let selected = st.file_uploader(FileUploaderOptions::new("Upload sales CSV").accepted_types(["csv"]).key("upload").on_change(|st| {
                let result = (|| -> TestResult {
                    let n = st.session_state().get::<u64>("uploads_changed")?.unwrap_or(0);
                    st.session_state().set("uploads_changed", n + 1)?;
                    Ok(())
                })();
                assert!(result.is_ok(), "upload callback fixture failed: {result:?}");
            }))?;
            let UploadedFiles::Single(file) = selected else {
                return Err("single-file uploader must return UploadedFiles::Single".into());
            };
            let content = file.map(|file| json!({"name":file.name(),"type":file.content_type(),"size":file.size(),"bytes":file.as_bytes()}));
            st.write(format!("uploaded={}", json!({"file":content,"callbacks":st.session_state().get::<u64>("uploads_changed")?.unwrap_or(0)})));
            Ok(())
        }
        .await;
        assert!(result.is_ok(), "upload_entry fixture failed: {result:?}");
    })
}

struct Run {
    session: String,
    widget: String,
    value: Value,
}
async fn run(socket: &mut TcpStream, widgets: Vec<WidgetState>) -> TestResult<Run> {
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
            Some(forward_msg::Type::NewSession(new)) => run.session = new.initialize.ok_or("NewSession must include initialization")?.session_id,
            Some(forward_msg::Type::Delta(crate::proto::Delta {
                r#type: Some(delta::Type::NewElement(element)), ..
            })) => match element.r#type {
                Some(element::Type::FileUploader(file)) => run.widget = file.id,
                Some(element::Type::Markdown(text)) => {
                    if let Some(value) = text.body.strip_prefix("uploaded=") {
                        run.value = serde_json::from_str(value)?;
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
    Ok(run)
}

async fn urls(socket: &mut TcpStream, session: &str) -> TestResult<crate::proto::FileUrLs> {
    let request = BackMsg {
        r#type: Some(back_msg::Type::FileUrlsRequest(crate::proto::FileUrLsRequest {
            request_id: "upload-request".into(),
            file_names: vec!["sales_basic.csv".into()],
            session_id: session.into(),
        })),
    };
    send_binary(socket, &request.encode_to_vec()).await;
    let Some(forward_msg::Type::FileUrlsResponse(response)) = receive(socket).await.r#type else {
        panic!("upload URL request must receive FileUrlsResponse")
    };
    assert_eq!(response.response_id, "upload-request");
    assert!(response.error_msg.is_empty());
    assert_eq!(response.file_urls.len(), 1);
    let urls = response.file_urls.into_iter().next().ok_or("upload URL response must contain one file")?;
    assert_eq!(urls.upload_url, format!("/_stcore/upload_file/{session}/{}", urls.file_id));
    assert_eq!(urls.delete_url, urls.upload_url);
    Ok(urls)
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

struct HttpResult {
    status: u16,
    headers: String,
    body: Vec<u8>,
}

async fn request(address: std::net::SocketAddr, method: &str, url: &str, auth: Option<(&str, &str)>, bytes: &[u8]) -> TestResult<HttpResult> {
    let mut headers = Vec::new();
    if let Some((cookie, header)) = auth {
        if !cookie.is_empty() {
            headers.push(("Cookie", format!("_streamlit_xsrf={cookie}")));
        }
        if !header.is_empty() {
            headers.push(("X-Xsrftoken", header.to_owned()));
        }
    }
    request_with_headers(address, method, url, headers, bytes).await
}

async fn request_with_headers(address: std::net::SocketAddr, method: &str, url: &str, headers: Vec<(&str, String)>, bytes: &[u8]) -> TestResult<HttpResult> {
    let mut socket = TcpStream::connect(address).await?;
    let mut body = Vec::new();
    let mut extra = String::new();
    if method == "PUT" {
        body.extend_from_slice(b"--native-test\r\nContent-Disposition: form-data; name=\"file\"; filename=\"sales_basic.csv\"\r\nContent-Type: text/csv\r\n\r\n");
        body.extend_from_slice(bytes);
        body.extend_from_slice(b"\r\n--native-test--\r\n");
        extra.push_str("Content-Type: multipart/form-data; boundary=native-test\r\n");
    }
    for (name, value) in headers {
        extra.push_str(&format!("{name}: {value}\r\n"));
    }
    let headers = format!("{method} {url} HTTP/1.1\r\nHost: {address}\r\n{extra}Content-Length: {}\r\nConnection: close\r\n\r\n", body.len());
    socket.write_all(headers.as_bytes()).await?;
    socket.write_all(&body).await?;
    let mut response = Vec::new();
    tokio::time::timeout(Duration::from_secs(5), socket.read_to_end(&mut response)).await??;
    let split = response.windows(4).position(|part| part == b"\r\n\r\n").ok_or("HTTP upload response must include header terminator")?;
    let headers = String::from_utf8(response[..split].to_vec())?;
    let status = headers.split_whitespace().nth(1).ok_or("HTTP upload status line must include a code")?.parse()?;
    Ok(HttpResult {
        status,
        headers,
        body: response[split + 4..].to_vec(),
    })
}

async fn duplicate_cookie_gate_preserves_storage(method: &str) -> TestResult {
    let listener = std::net::TcpListener::bind("127.0.0.1:0")?;
    let address = listener.local_addr()?;
    let state = StreamlitServer::new(upload_entry, "127.0.0.1".into(), 0);
    let server = HttpServer::new(move || App::new().app_data(web::Data::new(state.clone())).configure(configure_routes)).workers(2).listen(listener)?.run();
    let handle = server.handle();
    let task = actix_web::rt::spawn(server);
    let mut ws = sessions::connect(address, None).await;
    let initial = run(&mut ws, vec![]).await?;
    let urls = urls(&mut ws, &initial.session).await?;
    for separate_headers in [false, true] {
        assert_eq!(request(address, "PUT", &urls.upload_url, Some(("48dc", "48dc")), b"original").await?.status, 204);
        let mut headers = if separate_headers {
            vec![("Cookie", "_streamlit_xsrf=48dc".into()), ("Cookie", "_streamlit_xsrf=0000".into())]
        } else {
            vec![("Cookie", "_streamlit_xsrf=48dc; _streamlit_xsrf=0000".into())]
        };
        headers.push(("X-Xsrftoken", "48dc".into()));
        let result = request_with_headers(address, method, &urls.upload_url, headers, b"changed-by-duplicate").await?;
        let after = run(&mut ws, file_state(&initial.widget, &urls)).await?;
        assert_eq!((result.status, after.value["file"]["bytes"].clone()), (403, json!(b"original".as_slice())), "{method}, separate Cookie headers={separate_headers}");
        assert_eq!(result.body, b"XSRF token missing or invalid");
        let mut headers = if separate_headers {
            vec![("Cookie", "_streamlit_xsrf=0000".into()), ("Cookie", "_streamlit_xsrf=48dc".into())]
        } else {
            vec![("Cookie", "_streamlit_xsrf=0000; _streamlit_xsrf=48dc".into())]
        };
        headers.push(("X-Xsrftoken", "48dc".into()));
        let accepted = request_with_headers(address, method, &urls.upload_url, headers, b"accepted-last-cookie").await?;
        assert_eq!(accepted.status, 204, "last cookie matches");
        let after = run(&mut ws, file_state(&initial.widget, &urls)).await?;
        if method == "PUT" {
            assert_eq!(after.value["file"]["bytes"], json!(b"accepted-last-cookie".as_slice()));
        } else {
            assert!(after.value["file"].is_null());
        }
    }
    sessions::disconnect(ws).await;
    handle.stop(true).await;
    task.await??;
    Ok(())
}

#[actix_web::test]
async fn duplicate_cookie_gate_put_uses_last_cookie_without_changing_rejected_storage() -> TestResult {
    duplicate_cookie_gate_preserves_storage("PUT").await?;
    Ok(())
}

#[actix_web::test]
async fn duplicate_cookie_gate_delete_uses_last_cookie_without_changing_rejected_storage() -> TestResult {
    duplicate_cookie_gate_preserves_storage("DELETE").await?;
    Ok(())
}

async fn health_token(address: std::net::SocketAddr) -> TestResult<String> {
    let response = request(address, "GET", "/_stcore/health", None, &[]).await?;
    assert_eq!(response.status, 200);
    assert_eq!(response.body, b"ok");
    assert!(response.headers.to_lowercase().contains("cache-control: no-cache"));
    cookie_from_response(&response)
}

fn cookie_from_response(response: &HttpResult) -> TestResult<String> {
    let value = response
        .headers
        .lines()
        .find_map(|line| {
            let (name, value) = line.split_once(':')?;
            name.eq_ignore_ascii_case("set-cookie").then_some(value)
        })
        .ok_or("health response must include Set-Cookie")?;
    let token = value.trim().strip_prefix("_streamlit_xsrf=").ok_or("health response must set the _streamlit_xsrf cookie")?;
    Ok(token.split(';').next().ok_or("XSRF cookie must contain a value")?.to_owned())
}

async fn put(address: std::net::SocketAddr, url: &str, bytes: &[u8]) -> TestResult {
    let token = health_token(address).await?;
    let response = request(address, "PUT", url, Some((&token, &token)), bytes).await?;
    assert_eq!(response.status, 204);
    assert!(response.headers.to_lowercase().contains("content-type: text/plain"));
    Ok(())
}

#[actix_web::test]
async fn real_http_ws_upload_bytes_callbacks_reconnect_fresh_and_isolation() -> TestResult {
    let listener = std::net::TcpListener::bind("127.0.0.1:0")?;
    let address = listener.local_addr()?;
    let state = StreamlitServer::new(upload_entry, "127.0.0.1".into(), 0);
    let server = HttpServer::new(move || App::new().app_data(web::Data::new(state.clone())).configure(configure_routes)).workers(2).listen(listener)?.run();
    let handle = server.handle();
    let task = actix_web::rt::spawn(server);
    let mut a = sessions::connect(address, None).await;
    let initial = run(&mut a, vec![]).await?;
    assert_eq!(initial.value, json!({"file":null,"callbacks":0}));
    let a_urls = urls(&mut a, &initial.session).await?;
    let fixture = include_bytes!("../../../tests/fixtures/csv/sales_basic.csv");
    assert_eq!(fixture.len(), 737);
    put(address, &a_urls.upload_url, fixture).await?;
    let uploaded = run(&mut a, file_state(&initial.widget, &a_urls)).await?;
    assert_eq!(uploaded.value["file"]["bytes"], json!(fixture.as_slice()));
    assert_eq!(uploaded.value["file"]["size"], 737);
    assert_eq!(uploaded.value["callbacks"], 1);
    let repeated = run(&mut a, file_state(&initial.widget, &a_urls)).await?;
    assert_eq!(repeated.value, uploaded.value);
    let mut b = sessions::connect(address, None).await;
    let other = run(&mut b, vec![]).await?;
    assert_ne!(other.session, initial.session);
    let spoofed = run(&mut b, file_state(&other.widget, &a_urls)).await?;
    assert!(spoofed.value["file"].is_null(), "foreign IDs must not expose bytes");
    let b_urls = urls(&mut b, &other.session).await?;
    put(address, &b_urls.upload_url, b"other session").await?;
    let different = run(&mut b, file_state(&other.widget, &b_urls)).await?;
    assert_eq!(different.value["file"]["bytes"], json!(b"other session".as_slice()));
    sessions::disconnect(a).await;
    let mut restored = sessions::connect(address, Some(&initial.session)).await;
    let recovered = run(&mut restored, vec![]).await?;
    assert_eq!(recovered.session, initial.session);
    assert_eq!(recovered.value, uploaded.value);
    let mut fresh = sessions::connect(address, None).await;
    let empty = run(&mut fresh, vec![]).await?;
    assert_ne!(empty.session, initial.session);
    assert!(empty.value["file"].is_null());
    sessions::disconnect(restored).await;
    sessions::disconnect(fresh).await;
    sessions::disconnect(b).await;
    handle.stop(true).await;
    task.await??;
    Ok(())
}

#[actix_web::test]
async fn real_http_xsrf_gate_and_delete_follow_official_session_boundaries() -> TestResult {
    let listener = std::net::TcpListener::bind("127.0.0.1:0")?;
    let address = listener.local_addr()?;
    let state = StreamlitServer::new(upload_entry, "127.0.0.1".into(), 0);
    let observer = state.clone();
    let server = HttpServer::new(move || App::new().app_data(web::Data::new(state.clone())).configure(configure_routes)).workers(2).listen(listener)?.run();
    let handle = server.handle();
    let task = actix_web::rt::spawn(server);
    let mut a = sessions::connect(address, None).await;
    let a_run = run(&mut a, vec![]).await?;
    let a_urls = urls(&mut a, &a_run.session).await?;
    let mut b = sessions::connect(address, None).await;
    let b_run = run(&mut b, vec![]).await?;
    let token_a = health_token(address).await?;
    let token_b = health_token(address).await?;
    assert_ne!(token_a, token_b);
    let fixture = include_bytes!("../../../tests/fixtures/csv/sales_basic.csv");
    let uploaded = request(address, "PUT", &a_urls.upload_url, Some((&token_a, &token_a)), fixture).await?;
    assert_eq!(uploaded.status, 204);
    let retained = observer
        .sessions
        .state_for_upload(&a_run.session)
        .ok_or("connected upload session must remain available")?
        .uploads
        .lock()
        .get(&a_urls.file_id)
        .ok_or("successful upload must retain file bytes")?;
    for method in ["PUT", "DELETE"] {
        for auth in [None, Some((token_a.as_str(), "")), Some(("", token_a.as_str())), Some((token_a.as_str(), token_b.as_str()))] {
            let response = request(address, method, &a_urls.upload_url, auth, b"forbidden replacement").await?;
            assert_eq!(response.status, 403);
            assert_eq!(response.body, b"XSRF token missing or invalid");
            assert!(response.headers.to_lowercase().contains("content-type: text/plain; charset=utf-8"));
            let output = run(&mut a, file_state(&a_run.widget, &a_urls)).await?;
            assert_eq!(output.value["file"]["bytes"], json!(fixture.as_slice()), "rejected request changed application-visible storage");
        }
    }
    let unknown = "/_stcore/upload_file/unknown-session/unknown-file";
    for input in ["48dc", "2|12345678|0011|1"] {
        let response = request(address, "GET", "/_stcore/health", Some((input, "")), &[]).await?;
        assert_eq!(response.status, 200);
        let refreshed = cookie_from_response(&response)?;
        assert_ne!(refreshed, input);
        assert!(refreshed.starts_with("2|"));
        let accepted = request(address, "DELETE", unknown, Some((&refreshed, input)), &[]).await?;
        assert_eq!(accepted.status, 204, "health must preserve the decoded token");
        if input.starts_with("2|") {
            assert_eq!(refreshed.split('|').nth(3), Some("1"));
        }
    }
    // Replay independently observed cookie/header pairs through actual HTTP,
    // not only the decoder helper. DELETE's unknown-session no-op isolates XSRF.
    let issued = "2|f65b844a|be87e919eefd1a85bb0153c1f211778e|1792824916";
    let legacy = "48dc6d5318a69ecf4d5ad78b044af3c4";
    let remasked = "2|12345678|5ae83b2b0a92c8b75f6e81f3167ea5bc|1792824916";
    for (cookie, header, status) in [
        (issued, issued, 204),
        (issued, remasked, 204),
        (issued, legacy, 204),
        (legacy, issued, 204),
        (legacy, legacy, 204),
        ("48dc", "48dc", 204),
        (issued, "2|12345678|5ae83b2b0a92c8b75f6e81f3167ea5bc|1", 204),
        (issued, "2|12345678|5be83b2b0a92c8b75f6e81f3167ea5bc|1792824916", 403),
        ("invalid-token", "invalid-token", 403),
        (issued, "2%7Cf65b844a%7Cbe87e919eefd1a85bb0153c1f211778e%7C1792824916", 403),
        ("2|12345678|0011| 1", "2|12345678|0011| 1", 204),
        ("2|12345678|0011|1_0", "2|12345678|0011|1_0", 204),
    ] {
        let result = request(address, "DELETE", unknown, Some((cookie, header)), &[]).await?;
        assert_eq!(result.status, status);
        if status == 403 {
            assert_eq!(result.body, b"XSRF token missing or invalid");
        } else {
            assert!(result.body.is_empty());
            assert!(!result.headers.to_lowercase().contains("content-type:"));
        }
    }
    assert_eq!(request(address, "PUT", unknown, None, fixture).await?.status, 403);
    let unknown_put = request(address, "PUT", unknown, Some((&token_b, &token_b)), fixture).await?;
    assert_eq!(unknown_put.status, 400);
    assert_eq!(unknown_put.body, crate::upload::UploadHttpError::SessionUnavailable.to_string().as_bytes());
    assert!(unknown_put.headers.to_lowercase().contains("content-type: text/plain; charset=utf-8"));
    // Official accepts valid B XSRF credentials for A's known URL: CSRF is not
    // a second user/session identity layer. Still isolate widget-state reads.
    assert_eq!(request(address, "PUT", &a_urls.upload_url, Some((&token_b, &token_b)), b"B replaced A").await?.status, 204);
    let replaced = run(&mut a, file_state(&a_run.widget, &a_urls)).await?;
    assert_eq!(replaced.value["file"]["bytes"], json!(b"B replaced A".as_slice()));
    let foreign = run(&mut b, file_state(&b_run.widget, &a_urls)).await?;
    assert!(foreign.value["file"].is_null());
    for url in [&a_urls.delete_url, &a_urls.delete_url, &format!("/_stcore/upload_file/{}/never-uploaded", a_run.session), unknown] {
        let response = request(address, "DELETE", url, Some((&token_b, &token_b)), &[]).await?;
        assert_eq!(response.status, 204);
        assert!(response.body.is_empty());
        assert!(!response.headers.to_lowercase().contains("content-type:"));
    }
    assert!(observer.sessions.state_for_upload(&a_run.session).ok_or("connected upload session must remain available")?.uploads.lock().get(&a_urls.file_id).is_none());
    let stale = run(&mut a, file_state(&a_run.widget, &a_urls)).await?;
    assert!(stale.value["file"].is_null(), "deleted file must not resurrect from a stale client state");
    assert_eq!(retained.as_bytes(), fixture, "already returned immutable handles remain readable");
    sessions::disconnect(a).await;
    sessions::disconnect(b).await;
    handle.stop(true).await;
    task.await??;
    Ok(())
}

/// The multiple-file mode against the frozen Python 1.66.1 reference
/// (reference-browser/uploads-multi): one batched URL request for every
/// selected file, per-file PUTs, and the widget state carrying the full
/// uploaded_file_info list — removal keeps the remaining files in order.
fn multi_upload_entry(st: &Streamlit) -> Pin<Box<dyn Future<Output = ()> + '_>> {
    Box::pin(async move {
        let result: TestResult = async {
            let selected = st.file_uploader(FileUploaderOptions::new("Upload files").multiple_files().key("multi-upload"))?;
            let UploadedFiles::Multiple(files) = selected else {
                return Err("multiple-file uploader must return UploadedFiles::Multiple".into());
            };
            let content: Vec<Value> = files.iter().map(|file| json!({"name":file.name(),"size":file.size(),"bytes_head":file.as_bytes().iter().take(5).copied().collect::<Vec<_>>()})).collect();
            st.write(format!("uploaded={}", json!({"count":files.len(),"files":content})));
            Ok(())
        }
        .await;
        assert!(result.is_ok(), "multi_upload_entry fixture failed: {result:?}");
    })
}

async fn put_file(address: std::net::SocketAddr, url: &str, name: &str, content_type: &str, bytes: &[u8]) -> TestResult<u16> {
    let token = health_token(address).await?;
    let mut socket = TcpStream::connect(address).await?;
    let mut body = Vec::new();
    body.extend_from_slice(format!("--native-test\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{name}\"\r\nContent-Type: {content_type}\r\n\r\n").as_bytes());
    body.extend_from_slice(bytes);
    body.extend_from_slice(b"\r\n--native-test--\r\n");
    let headers = format!(
        "PUT {url} HTTP/1.1\r\nHost: {address}\r\nContent-Type: multipart/form-data; boundary=native-test\r\nCookie: _streamlit_xsrf={token}\r\nX-Xsrftoken: {token}\r\nContent-Length: {}\r\nConnection: close\r\n\r\n",
        body.len()
    );
    socket.write_all(headers.as_bytes()).await?;
    socket.write_all(&body).await?;
    let mut response = Vec::new();
    tokio::time::timeout(Duration::from_secs(5), socket.read_to_end(&mut response)).await??;
    let text = String::from_utf8(response)?;
    Ok(text.split_whitespace().nth(1).ok_or("upload response must carry a status")?.parse()?)
}

async fn multi_run(socket: &mut TcpStream, infos: Vec<crate::proto::UploadedFileInfo>, widget: &str) -> TestResult<Value> {
    let request = BackMsg {
        r#type: Some(back_msg::Type::RerunScript(ClientState {
            widget_states: Some(WidgetStates {
                widgets: vec![WidgetState {
                    id: widget.into(),
                    value: Some(widget_state::Value::FileUploaderStateValue(crate::proto::FileUploaderState { uploaded_file_info: infos })),
                }],
            }),
            ..Default::default()
        })),
    };
    send_binary(socket, &request.encode_to_vec()).await;
    let mut report = Value::Null;
    let mut finished = false;
    loop {
        match receive(socket).await.r#type {
            Some(forward_msg::Type::Delta(delta)) => {
                if let Some(delta::Type::NewElement(element)) = delta.r#type
                    && let Some(element::Type::Markdown(text)) = element.r#type
                    && let Some(value) = text.body.strip_prefix("uploaded=")
                {
                    report = serde_json::from_str(value)?;
                }
            }
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
    assert!(!report.is_null(), "the multi uploader must echo its report");
    Ok(report)
}

#[actix_web::test]
async fn multiple_file_uploads_batch_urls_states_and_removal_semantics() -> TestResult {
    let listener = std::net::TcpListener::bind("127.0.0.1:0")?;
    let address = listener.local_addr()?;
    let server = StreamlitServer::new(multi_upload_entry, "127.0.0.1".into(), 0);
    let server = HttpServer::new(move || App::new().app_data(web::Data::new(server.clone())).configure(configure_routes)).workers(1).listen(listener)?.run();
    let handle = server.handle();
    let task = actix_web::rt::spawn(server);
    let mut stream = sessions::connect(address, None).await;
    // One explicit rerun renders the widget and creates the session.
    send_binary(
        &mut stream,
        &(BackMsg {
            r#type: Some(back_msg::Type::RerunScript(ClientState::default())),
        })
        .encode_to_vec(),
    )
    .await;
    let mut widget = String::new();
    let mut session = String::new();
    loop {
        match receive(&mut stream).await.r#type {
            Some(forward_msg::Type::NewSession(new)) => session = new.initialize.ok_or("NewSession must include initialization")?.session_id,
            Some(forward_msg::Type::Delta(delta)) => {
                if let Some(delta::Type::NewElement(element)) = delta.r#type
                    && let Some(element::Type::FileUploader(file)) = element.r#type
                {
                    assert!(file.multiple_files && !file.accept_directory, "the wire element must mark multiple mode");
                    widget = file.id;
                }
            }
            Some(forward_msg::Type::ScriptFinished(status)) => {
                assert_eq!(status, 0);
                break;
            }
            _ => (),
        }
    }
    assert!(!widget.is_empty() && !session.is_empty());
    // The reference batches one URL request for both files.
    let request = BackMsg {
        r#type: Some(back_msg::Type::FileUrlsRequest(crate::proto::FileUrLsRequest {
            request_id: "multi".into(),
            file_names: vec!["alpha.txt".into(), "beta.csv".into()],
            session_id: session.clone(),
        })),
    };
    send_binary(&mut stream, &request.encode_to_vec()).await;
    let urls = loop {
        if let Some(forward_msg::Type::FileUrlsResponse(response)) = receive(&mut stream).await.r#type {
            assert_eq!(response.response_id, "multi");
            break response.file_urls;
        }
    };
    assert_eq!(urls.len(), 2, "one batched request yields both upload urls");
    assert_eq!(put_file(address, &urls[0].upload_url, "alpha.txt", "text/plain", b"alpha-payload-01\n").await?, 204);
    assert_eq!(put_file(address, &urls[1].upload_url, "beta.csv", "text/csv", b"key,value\na,1\nb,2\n").await?, 204);
    let info = |name: &str, size: u64, urls: &crate::proto::FileUrLs| crate::proto::UploadedFileInfo {
        name: name.into(),
        size,
        file_id: urls.file_id.clone(),
        file_urls: Some(urls.clone()),
    };
    let both = multi_run(&mut stream, vec![info("alpha.txt", 17, &urls[0]), info("beta.csv", 18, &urls[1])], &widget).await?;
    assert_eq!(both["count"], json!(2));
    assert_eq!(both["files"][0]["name"], json!("alpha.txt"));
    assert_eq!(both["files"][0]["bytes_head"], json!([97, 108, 112, 104, 97]));
    assert_eq!(both["files"][1]["name"], json!("beta.csv"));
    // Removing one file keeps the survivor in order.
    let one = multi_run(&mut stream, vec![info("beta.csv", 18, &urls[1])], &widget).await?;
    assert_eq!(one["count"], json!(1));
    assert_eq!(one["files"][0]["name"], json!("beta.csv"));
    // An empty state clears the selection.
    let empty = multi_run(&mut stream, vec![], &widget).await?;
    assert_eq!(empty["count"], json!(0));
    drop(stream);
    handle.stop(false).await;
    task.await??;
    Ok(())
}
