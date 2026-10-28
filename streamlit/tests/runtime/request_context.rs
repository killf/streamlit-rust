//! Real WS regressions for st.request_context() against the frozen Python
//! reference (tests/reference/reference-browser/context-headers): the Rust
//! default whitelists common non-credential handshake headers, All mirrors
//! the measured pass-everything behavior, and is_embedded follows the
//! st_embed query parameter.
use super::*;
use crate::proto::{ClientState, back_msg, forward_msg};
use serde_json::json;

fn context_entry(st: &Streamlit) -> Pin<Box<dyn Future<Output = ()> + '_>> {
    Box::pin(async move {
        let context = st.request_context();
        st.code(
            json!({
                "headers": context.headers,
                "url": context.url,
                "locale": context.locale,
                "timezone": context.timezone,
                "timezone_offset": context.timezone_offset,
                "theme": context.theme,
                "is_embedded": context.is_embedded,
            })
            .to_string(),
            "json",
        );
    })
}

/// A raw WebSocket handshake carrying the probe headers; the shared test
/// helper does not support custom headers.
async fn connect_with_probes(address: std::net::SocketAddr) -> TestResult<TcpStream> {
    let mut stream = TcpStream::connect(address).await?;
    stream
        .write_all(
            format!(
                "GET /_stcore/stream HTTP/1.1\r\nHost: {address}\r\nConnection: Upgrade\r\nUpgrade: websocket\r\n\
             Sec-WebSocket-Version: 13\r\nSec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==\r\nSec-WebSocket-Protocol: streamlit\r\n\
             Origin: http://127.0.0.1\r\n\
             User-Agent: M4Probe/1.0\r\nAccept-Language: zh-CN\r\nX-M4-Probe: alpha\r\nCookie: session=secret\r\n\r\n"
            )
            .as_bytes(),
        )
        .await?;
    let mut response = Vec::new();
    while !response.ends_with(b"\r\n\r\n") {
        response.push(stream.read_u8().await?);
    }
    let response = String::from_utf8(response)?;
    assert!(response.to_ascii_lowercase().starts_with("http/1.1 101"), "handshake failed: {response}");
    Ok(stream)
}

async fn run_context(stream: &mut TcpStream, query_string: &str) -> TestResult<serde_json::Value> {
    send_binary(
        stream,
        &(BackMsg {
            r#type: Some(back_msg::Type::RerunScript(ClientState {
                query_string: query_string.into(),
                context_info: Some(crate::proto::ContextInfo {
                    timezone: Some("Asia/Shanghai".into()),
                    timezone_offset: Some(-480),
                    locale: Some("zh-CN".into()),
                    url: Some("http://127.0.0.1:8590/".into()),
                    is_embedded: Some(query_string.contains("st_embed=true")),
                    color_scheme: Some("dark".into()),
                }),
                ..Default::default()
            })),
        })
        .encode_to_vec(),
    )
    .await;
    let mut report = None;
    loop {
        let message = receive(stream).await;
        match message.r#type {
            Some(forward_msg::Type::Delta(delta)) => {
                if let Some(delta::Type::NewElement(element)) = delta.r#type
                    && let Some(element::Type::Code(code)) = element.r#type
                {
                    report = Some(serde_json::from_str(&code.code_text)?);
                }
            }
            Some(forward_msg::Type::ScriptFinished(status)) => {
                assert_eq!(status, 0);
                // Drain the whole run so the next call starts clean.
                return report.ok_or_else(|| "context element missing before script finished".into());
            }
            _ => {}
        }
    }
}

#[actix_web::test]
async fn request_context_reflects_the_server_header_whitelist() -> TestResult {
    let listener = std::net::TcpListener::bind("127.0.0.1:0")?;
    let address = listener.local_addr()?;
    let server = StreamlitServer::new(context_entry, "127.0.0.1".into(), 0);
    let server = actix_web::rt::spawn(HttpServer::new(move || App::new().app_data(web::Data::new(server.clone())).configure(configure_routes)).workers(1).listen(listener)?.run());
    // connect_with_probes spawns its own server task handle below.
    let mut stream = connect_with_probes(address).await?;
    let report = run_context(&mut stream, "").await?;
    let headers = report["headers"].as_object().ok_or("headers must be an object")?;
    assert_eq!(headers.get("user-agent").and_then(|v| v.as_str()), Some("M4Probe/1.0"));
    assert_eq!(headers.get("accept-language").and_then(|v| v.as_str()), Some("zh-CN"));
    assert!(headers.contains_key("host") && headers.contains_key("origin"), "standard transport-adjacent headers");
    // The credential and the non-whitelisted probe stay hidden by default.
    assert!(!headers.contains_key("cookie"), "credentials must not leak by default");
    assert!(!headers.contains_key("x-m4-probe"), "non-whitelisted probes stay hidden");
    assert!(!headers.contains_key("sec-websocket-key"), "transport noise stays hidden");
    assert_eq!(report["is_embedded"], json!(false));
    // The page context rides the rerun's context_info, exactly as the real
    // frontend reports it (frozen python browser reference).
    assert_eq!(report["url"], json!("http://127.0.0.1:8590/"));
    assert_eq!(report["locale"], json!("zh-CN"));
    assert_eq!(report["timezone"], json!("Asia/Shanghai"));
    assert_eq!(report["timezone_offset"], json!(-480));
    assert_eq!(report["theme"], json!("dark"));
    // The embedded flag rides the browser's context report.
    let embedded = run_context(&mut stream, "st_embed=true").await?;
    assert_eq!(embedded["is_embedded"], json!(true), "query: {embedded}");
    let headers_keys = embedded["headers"].as_object().ok_or("headers")?.keys().cloned().collect::<Vec<_>>();
    assert_eq!(headers_keys, ["accept-language", "host", "origin", "user-agent"], "same whitelist every run");
    drop(stream);
    server.abort();
    let _ = server.await;
    Ok(())
}

#[actix_web::test]
async fn request_context_all_mirrors_the_measured_python_surface() -> TestResult {
    let listener = std::net::TcpListener::bind("127.0.0.1:0")?;
    let address = listener.local_addr()?;
    let server = StreamlitServer::new(context_entry, "127.0.0.1".into(), 0).with_request_headers(crate::RequestHeaderAccess::All);
    let server = actix_web::rt::spawn(HttpServer::new(move || App::new().app_data(web::Data::new(server.clone())).configure(configure_routes)).workers(1).listen(listener)?.run());
    let mut stream = connect_with_probes(address).await?;
    let report = run_context(&mut stream, "").await?;
    let headers = report["headers"].as_object().ok_or("headers")?;
    // The frozen reference reflects every handshake header, credentials and
    // transport headers included; Rust names are lowercase by design.
    for name in ["user-agent", "accept-language", "x-m4-probe", "cookie", "sec-websocket-key", "sec-websocket-protocol"] {
        assert!(headers.contains_key(name), "All must reflect {name}");
    }
    assert_eq!(headers.get("x-m4-probe").and_then(|v| v.as_str()), Some("alpha"));
    assert_eq!(headers.get("cookie").and_then(|v| v.as_str()), Some("session=secret"));
    drop(stream);
    server.abort();
    let _ = server.await;
    Ok(())
}

fn user_entry(st: &Streamlit) -> Pin<Box<dyn Future<Output = ()> + '_>> {
    Box::pin(async move {
        let user = st.user();
        let context = st.request_context();
        st.code(
            json!({
                "user": user.to_dict(),
                "cookies": context.cookies(),
            })
            .to_string(),
            "json",
        );
    })
}

#[actix_web::test]
async fn header_identity_and_cookies_ride_the_connection() -> TestResult {
    let listener = std::net::TcpListener::bind("127.0.0.1:0")?;
    let address = listener.local_addr()?;
    let server = StreamlitServer::new(user_entry, "127.0.0.1".into(), 0)
        .with_authenticator(std::sync::Arc::new(crate::HeaderAuthenticator::new("x-test-user")))
        .with_request_headers(crate::RequestHeaderAccess::Selected(vec!["cookie".into(), "user-agent".into()]));
    let server = actix_web::rt::spawn(HttpServer::new(move || App::new().app_data(web::Data::new(server.clone())).configure(configure_routes)).workers(1).listen(listener)?.run());
    let mut stream = TcpStream::connect(address).await?;
    stream
        .write_all(
            format!(
                "GET /_stcore/stream HTTP/1.1\r\nHost: {address}\r\nConnection: Upgrade\r\nUpgrade: websocket\r\n\
                 Sec-WebSocket-Version: 13\r\nSec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==\r\nSec-WebSocket-Protocol: streamlit\r\n\
                 Cookie: probe-flavor=oat; probe-session=42\r\n\
                 X-Test-User: {{\"sub\":\"u1\",\"name\":\"Ada\",\"roles\":[\"admin\"],\"team\":\"core\"}}\r\n\r\n"
            )
            .as_bytes(),
        )
        .await?;
    let mut response = Vec::new();
    while !response.ends_with(b"\r\n\r\n") {
        response.push(stream.read_u8().await?);
    }
    assert!(String::from_utf8(response)?.to_ascii_lowercase().starts_with("http/1.1 101"));
    let report = run_context(&mut stream, "").await?;
    let user = report["user"].as_object().ok_or("user mapping")?;
    // The fake credential resolved the identity; the mapping mirrors the
    // reference's dict shape (standard fields + claims).
    assert_eq!(user.get("sub").and_then(|v| v.as_str()), Some("u1"));
    assert_eq!(user.get("name").and_then(|v| v.as_str()), Some("Ada"));
    assert_eq!(user.get("roles").and_then(|v| v.as_str()), Some("admin"));
    assert_eq!(user.get("team").and_then(|v| v.as_str()), Some("core"));
    // Cookies are visible because this server whitelisted the cookie header.
    let cookies = report["cookies"].as_object().ok_or("cookies")?;
    assert_eq!(cookies.get("probe-flavor").and_then(|v| v.as_str()), Some("oat"));
    assert_eq!(cookies.get("probe-session").and_then(|v| v.as_str()), Some("42"));
    drop(stream);
    server.abort();
    let _ = server.await;
    Ok(())
}

#[actix_web::test]
async fn without_an_authenticator_the_user_mapping_is_the_anonymous_baseline() -> TestResult {
    let listener = std::net::TcpListener::bind("127.0.0.1:0")?;
    let address = listener.local_addr()?;
    let server = StreamlitServer::new(user_entry, "127.0.0.1".into(), 0);
    let server = actix_web::rt::spawn(HttpServer::new(move || App::new().app_data(web::Data::new(server.clone())).configure(configure_routes)).workers(1).listen(listener)?.run());
    let mut stream = TcpStream::connect(address).await?;
    stream
        .write_all(
            format!(
                "GET /_stcore/stream HTTP/1.1\r\nHost: {address}\r\nConnection: Upgrade\r\nUpgrade: websocket\r\n\
                 Sec-WebSocket-Version: 13\r\nSec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==\r\nSec-WebSocket-Protocol: streamlit\r\n\
                 Cookie: probe-flavor=oat\r\n\r\n"
            )
            .as_bytes(),
        )
        .await?;
    let mut response = Vec::new();
    while !response.ends_with(b"\r\n\r\n") {
        response.push(stream.read_u8().await?);
    }
    let report = run_context(&mut stream, "").await?;
    // The frozen reference: anonymous st.user is an empty mapping, and the
    // default Standard whitelist keeps cookies invisible.
    assert_eq!(report["user"].as_object().ok_or("user")?.len(), 0);
    assert_eq!(report["cookies"].as_object().ok_or("cookies")?.len(), 0, "cookies leaked: {report}");
    drop(stream);
    server.abort();
    let _ = server.await;
    Ok(())
}
