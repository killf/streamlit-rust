use crate::api::Streamlit;
use crate::session::SessionStore;
use crate::websocket::handler::handle_connection;
use actix_files::Files;
use actix_web::http::header::{HeaderName, HeaderValue};
use actix_web::{App, HttpRequest, HttpResponse, HttpServer, Responder, delete, get, put, web};
use std::future::Future;
use std::pin::Pin;
use std::sync::Arc;
use std::time::Duration;

#[get("/_stcore/health")]
async fn health_check(req: HttpRequest) -> impl Responder {
    let mut response = HttpResponse::Ok();
    response.insert_header(("Cache-Control", "no-cache"));
    response.cookie(crate::upload::health_cookie(&req));
    response.content_type("text/plain; charset=utf-8").body("ok")
}

#[get("/_stcore/host-config")]
async fn host_config() -> impl Responder {
    let host_config = serde_json::json!({
        "allowedOrigins": [
            "https://devel.streamlit.test",
            "https://*.streamlit.apptest",
            "https://*.streamlitapp.test",
            "https://*.streamlitapp.com",
            "https://share.streamlit.io",
            "https://share-demo.streamlit.io",
            "https://share-head.streamlit.io",
            "https://share-staging.streamlit.io",
            "https://*.demo.streamlit.run",
            "https://*.head.streamlit.run",
            "https://*.staging.streamlit.run",
            "https://*.streamlit.run",
            "https://*.demo.streamlit.app",
            "https://*.head.streamlit.app",
            "https://*.staging.streamlit.app",
            "https://*.streamlit.app",
        ],
        "useExternalAuthToken": false,
        "enableCustomParentMessages": false,
        "enforceDownloadInNewTab": false,
        "metricsUrl": "",
        "blockErrorDialogs": false,
        "resourceCrossOriginMode": serde_json::Value::Null
    });

    HttpResponse::Ok().insert_header(("Content-Type", "application/json")).json(host_config)
}

#[get("/_stcore/stream")]
async fn websocket_handler(req: HttpRequest, stream: web::Payload, state: web::Data<StreamlitServer>) -> Result<HttpResponse, actix_web::Error> {
    let protocol = req
        .headers()
        .get("sec-websocket-protocol")
        .map(|value| value.to_str())
        .transpose()
        .map_err(|_| actix_web::error::ErrorBadRequest("invalid WebSocket subprotocol header"))?;
    let requested_id = reconnect_id(protocol).map(str::to_owned);
    let (mut response, session, msg_stream) = actix_ws::handle(&req, stream)?;

    actix_web::rt::spawn(async move {
        let lease = state.sessions.connect(requested_id.as_deref()).await;
        if let Err(e) = handle_connection(session, msg_stream, state.get_ref(), lease).await {
            log::error!("WebSocket connection error: {}", e);
        }
    });

    if req
        .headers()
        .get("sec-websocket-protocol")
        .and_then(|value| value.to_str().ok())
        .is_some_and(|value| value.split(',').any(|protocol| protocol.trim() == "streamlit"))
    {
        response.headers_mut().insert(HeaderName::from_static("sec-websocket-protocol"), HeaderValue::from_static("streamlit"));
    }

    Ok(response)
}

// The official browser sends protocol + token on a fresh connection, adding a
// session ID only when reconnecting. The token is not XSRF-validated yet.
fn reconnect_id(protocol: Option<&str>) -> Option<&str> {
    // Observed reference behavior treats the third entry as an opaque lookup,
    // including non-UUID strings. Unknown IDs create a new server-selected ID.
    protocol.and_then(|value| value.split(',').nth(2)).map(str::trim).filter(|id| !id.is_empty())
}

#[put("/_stcore/upload_file/{session_id}/{file_id}")]
async fn upload_file(req: HttpRequest, path: web::Path<(String, String)>, payload: actix_multipart::Multipart, server: web::Data<StreamlitServer>) -> Result<HttpResponse, crate::upload::UploadHttpError> {
    crate::upload::check_xsrf(&req)?;
    let (session_id, file_id) = path.into_inner();
    server.sessions.state_for_upload(&session_id).ok_or(crate::upload::UploadHttpError::SessionUnavailable)?;
    // This bounded native transport limit is the local 200 MiB default. Exact
    // limit/error boundary parity and per-widget overrides await their probes.
    let file = crate::upload::read_upload(payload, 200 * 1024 * 1024).await?;
    // Recheck after reading: a request cannot revive an expired session.
    let state = server.sessions.state_for_upload(&session_id).ok_or(crate::upload::UploadHttpError::SessionUnavailable)?;
    state.uploads.lock().insert(file_id, file.name, file.content_type, file.bytes);
    Ok(HttpResponse::NoContent().content_type("text/plain").finish())
}

#[delete("/_stcore/upload_file/{session_id}/{file_id}")]
async fn delete_upload(req: HttpRequest, path: web::Path<(String, String)>, server: web::Data<StreamlitServer>) -> Result<HttpResponse, crate::upload::UploadHttpError> {
    crate::upload::check_xsrf(&req)?;
    let (session_id, file_id) = path.into_inner();
    if let Some(state) = server.sessions.state_for_upload(&session_id) {
        state.uploads.lock().remove(&file_id);
    }
    // Official: idempotent, including missing file and unknown session; unlike PUT.
    Ok(HttpResponse::NoContent().finish())
}

fn configure_routes(config: &mut web::ServiceConfig) {
    config.service(websocket_handler).service(health_check).service(host_config).service(upload_file).service(delete_upload);
}

/// Handler type that can be either synchronous or asynchronous
pub enum Entry {
    Async(fn(&Streamlit) -> Pin<Box<dyn Future<Output = ()> + '_>>),
}

impl Clone for Entry {
    fn clone(&self) -> Self {
        match self {
            Entry::Async(f) => Entry::Async(*f),
        }
    }
}

impl Entry {
    /// Execute the handler (sync or async)
    pub async fn call(&self, st: &Streamlit) {
        match self {
            Entry::Async(f) => f(st).await,
        }
    }
}

#[derive(Clone)]
pub struct StreamlitServer {
    pub(crate) entry: Entry,
    pub(crate) host: String,
    pub(crate) port: u16,
    sessions: Arc<SessionStore>,
}

impl StreamlitServer {
    pub fn new(entry: fn(&Streamlit) -> Pin<Box<dyn Future<Output = ()> + '_>>, host: String, port: u16) -> Self {
        Self {
            entry: Entry::Async(entry),
            host,
            port,
            sessions: Arc::new(SessionStore::new(Duration::from_secs(120))),
        }
    }

    /// Set disconnected-session retention before starting the server.
    /// Connected sessions never expire. Expired/unknown reconnect IDs start a
    /// fresh empty session. Reconnecting a known ID assigns a new owner lease.
    /// This builder creates a new store and must not be used as a hot reload.
    pub fn with_disconnected_session_ttl(mut self, ttl: Duration) -> Self {
        self.sessions = Arc::new(SessionStore::new(ttl));
        self
    }

    pub async fn start(&self) -> std::io::Result<()> {
        log::info!("Starting Streamlit Rust Backend server on {}:{}", self.host.as_str(), self.port);

        let server = self.clone();
        HttpServer::new(move || App::new().app_data(web::Data::new(server.clone())).configure(configure_routes).service(Files::new("/", "./www").index_file("index.html")))
            .bind((self.host.as_str(), self.port))?
            .run()
            .await
    }
}

#[cfg(test)]
#[path = "../tests/runtime/mod.rs"]
mod tests;
