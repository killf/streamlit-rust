use crate::api::Streamlit;
use crate::session::SessionStore;
use crate::websocket::handler::handle_connection;
use actix_files::Files;
use actix_web::http::header::{HeaderName, HeaderValue};
use actix_web::{App, HttpRequest, HttpResponse, HttpServer, Responder, delete, get, put, web};
use std::future::Future;
use std::io::{self, Read};
use std::path::{Path, PathBuf};
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

// The measured media route (see .codex/compatibility.md, Media route): the
// browser resolves the element's relative URL `GET /media/{file_id}.{ext}`. A
// full request answers 200 with `accept-ranges: bytes`; a `bytes=a-b`
// Range request answers 206 with `content-range` and the sliced body.
// Content types ride the store's addressing, so the extension is cosmetic.
#[get("/media/{name}")]
async fn media_file(req: HttpRequest, path: web::Path<String>) -> HttpResponse {
    use actix_web::http::header::{ACCEPT_RANGES, CONTENT_RANGE, CONTENT_TYPE, Charset, ContentDisposition, DispositionParam, DispositionType, ExtendedValue};

    let name = path.into_inner();
    let (id, extension) = name.rsplit_once('.').unwrap_or((&name, ""));
    let Some(file) = crate::media::stored_file(id) else {
        return HttpResponse::NotFound().finish();
    };
    let mime = if file.download {
        file.mime.as_str()
    } else {
        match extension {
            "png" => "image/png",
            "jpg" | "jpeg" => "image/jpeg",
            "webp" => "image/webp",
            "gif" => "image/gif",
            "wav" => "audio/wav",
            "mp3" => "audio/mpeg",
            "ogg" => "audio/ogg",
            "flac" => "audio/flac",
            "aac" => "audio/aac",
            "mp4" => "video/mp4",
            "webm" => "video/webm",
            "ogv" => "video/ogg",
            _ => return HttpResponse::NotFound().finish(),
        }
    };
    let bytes = file.bytes;
    let range = match req.headers().get("range").filter(|value| !value.as_bytes().is_empty()) {
        Some(header) => match header.to_str().ok().and_then(|header| crate::media::ByteRange::parse(header, bytes.len() as u64)) {
            Some(range) => Some(range),
            None => {
                return HttpResponse::RangeNotSatisfiable()
                    .insert_header((CONTENT_RANGE, format!("bytes */{}", bytes.len())))
                    .content_type("text/plain; charset=utf-8")
                    .body("Invalid range");
            }
        },
        None => None,
    };
    let mut response = if range.is_some() { HttpResponse::PartialContent() } else { HttpResponse::Ok() };
    response.insert_header((ACCEPT_RANGES, "bytes"));
    // 1. 只补响应头；原 MIME 仍决定内容地址和默认文件后缀。
    let content_type = if mime.starts_with("text/") && !mime.to_ascii_lowercase().contains("charset=") {
        format!("{mime}; charset=utf-8")
    } else {
        mime.to_owned()
    };
    response.insert_header((CONTENT_TYPE, content_type));

    if file.download {
        // 2. 默认名和特殊字符遵循已测下载行为，扩展参数接收未编码的 UTF-8。
        let name = file.file_name.filter(|name| !name.is_empty()).unwrap_or_else(|| format!("streamlit_download{}", crate::media::download_extension(mime)));
        let filename = if name.bytes().all(|byte| byte.is_ascii_alphanumeric() || b"/-._~".contains(&byte)) {
            DispositionParam::Filename(name)
        } else {
            DispositionParam::FilenameExt(ExtendedValue {
                charset: Charset::Ext("utf-8".into()),
                language_tag: None,
                value: name.into_bytes(),
            })
        };

        response.insert_header(ContentDisposition {
            disposition: DispositionType::Attachment,
            parameters: vec![filename],
        });
    }

    match range {
        Some(range) => {
            let total = bytes.len() as u64;
            let start = range.start as usize;
            let end = range.end as usize;
            response.insert_header((CONTENT_RANGE, format!("bytes {}-{}/{}", range.start, range.end, total))).body(bytes.slice(start..=end))
        }
        None => response.body(bytes),
    }
}

fn configure_routes(config: &mut web::ServiceConfig) {
    config.service(websocket_handler).service(health_check).service(host_config).service(upload_file).service(delete_upload).service(media_file);
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
    static_dir: Option<PathBuf>,
}

impl StreamlitServer {
    pub fn new(entry: fn(&Streamlit) -> Pin<Box<dyn Future<Output = ()> + '_>>, host: String, port: u16) -> Self {
        Self {
            entry: Entry::Async(entry),
            host,
            port,
            sessions: Arc::new(SessionStore::new(Duration::from_secs(120))),
            static_dir: None,
        }
    }

    /// Select the unmodified official frontend directory.
    ///
    /// This overrides `STREAMLIT_STATIC_DIR` and the executable's adjacent `www`.
    /// Relative paths are resolved from the working directory when `start` is
    /// called. An empty, invalid or incompatible directory fails before binding;
    /// it never falls back to another directory.
    pub fn with_static_dir(mut self, path: impl Into<PathBuf>) -> Self {
        self.static_dir = Some(path.into());
        self
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
        let cwd = std::env::current_dir()?;
        let environment = std::env::var_os("STREAMLIT_STATIC_DIR");
        let assets = resolve_static_dir(self.static_dir.as_deref(), environment.as_deref().map(Path::new), std::env::current_exe, &cwd, cfg!(debug_assertions))?;
        log::info!("Serving static assets from {} ({})", assets.path.display(), assets.source);
        log::info!("Starting Streamlit Rust Backend server on {}:{}", self.host.as_str(), self.port);

        let server = self.clone();
        HttpServer::new(move || App::new().app_data(web::Data::new(server.clone())).configure(configure_routes).service(Files::new("/", &assets.path).index_file("index.html")))
            .bind((self.host.as_str(), self.port))?
            .run()
            .await
    }
}

// A small version identity only: the frontend itself remains an external sidecar.
const OFFICIAL_INDEX: &str = include_str!("../assets/frontend-index.html");

struct StaticDirectory {
    path: PathBuf,
    source: &'static str,
}

fn static_error(source: &str, path: &Path, error: io::Error) -> io::Error {
    io::Error::new(
        error.kind(),
        format!(
            "static assets ({source}) at {}: {error}; supply the complete official Streamlit 1.66.1 www directory via with_static_dir or STREAMLIT_STATIC_DIR",
            path.display()
        ),
    )
}

fn boot_assets() -> impl Iterator<Item = &'static str> {
    // The exact pinned index uses double-quoted, relative boot/preload URLs.
    // We do not parse or accept arbitrary HTML supplied by an installation.
    OFFICIAL_INDEX.split('"').filter_map(|value| value.strip_prefix("./")).filter(|value| value.ends_with(".js") || value.ends_with(".css"))
}

fn validate_static_dir(path: &Path, cwd: &Path, source: &'static str) -> io::Result<StaticDirectory> {
    let validate = || {
        if path.as_os_str().is_empty() {
            return Err(io::Error::new(io::ErrorKind::InvalidInput, "empty directory path"));
        }
        let root = std::fs::canonicalize(if path.is_absolute() { path.to_path_buf() } else { cwd.join(path) })?;
        if !root.is_dir() {
            return Err(io::Error::new(io::ErrorKind::InvalidInput, "not a directory"));
        }
        std::fs::read_dir(&root)?;
        let index = checked_asset(&root, "index.html")?;
        if std::fs::read(&index).map_err(|error| io::Error::new(error.kind(), format!("{}: {error}", index.display())))? != OFFICIAL_INDEX.as_bytes() {
            return Err(io::Error::new(io::ErrorKind::InvalidData, "index.html does not match the pinned official 1.66.1 index"));
        }
        for name in boot_assets() {
            let asset = checked_asset(&root, name)?;
            if std::fs::File::open(&asset)
                .and_then(|mut file| file.read(&mut [0]))
                .map_err(|error| io::Error::new(error.kind(), format!("{}: {error}", asset.display())))?
                == 0
            {
                return Err(io::Error::new(io::ErrorKind::InvalidData, format!("empty boot asset {name}")));
            }
        }
        Ok(StaticDirectory { path: root, source })
    };
    validate().map_err(|error| static_error(source, path, error))
}

fn checked_asset(root: &Path, name: &str) -> io::Result<PathBuf> {
    let path = root.join(name);
    let canonical = std::fs::canonicalize(&path).map_err(|error| io::Error::new(error.kind(), format!("{}: {error}", path.display())))?;
    if !canonical.starts_with(root) || !canonical.is_file() {
        return Err(io::Error::new(io::ErrorKind::InvalidData, format!("{} is not a regular file inside the selected static directory", path.display())));
    }
    Ok(canonical)
}

// Inputs are captured once by start(), or supplied privately by tests. No global
// environment or CWD changes are needed, including when tests run concurrently.
fn resolve_static_dir(builder: Option<&Path>, environment: Option<&Path>, executable: impl FnOnce() -> io::Result<PathBuf>, cwd: &Path, development: bool) -> io::Result<StaticDirectory> {
    if let Some(path) = builder {
        return validate_static_dir(path, cwd, "builder");
    }
    if let Some(path) = environment {
        return validate_static_dir(path, cwd, "STREAMLIT_STATIC_DIR");
    }
    let executable = executable().map_err(|error| io::Error::new(error.kind(), format!("static assets: could not locate executable: {error}")))?;
    let adjacent = executable.parent().ok_or_else(|| io::Error::new(io::ErrorKind::InvalidInput, "static assets: executable has no parent directory"))?.join("www");
    match std::fs::symlink_metadata(&adjacent) {
        Ok(_) => return validate_static_dir(&adjacent, cwd, "executable sidecar"),
        Err(error) if error.kind() == io::ErrorKind::NotFound => {}
        Err(error) => return Err(static_error("executable sidecar", &adjacent, error)),
    }
    if development && ["Cargo.toml", "streamlit/Cargo.toml", "streamlit-macros/Cargo.toml"].iter().all(|name| cwd.join(name).is_file()) {
        return validate_static_dir(&cwd.join("www"), cwd, "debug repository fallback");
    }
    Err(static_error(
        "executable sidecar",
        &adjacent,
        io::Error::new(io::ErrorKind::NotFound, "no static directory; CWD fallback is restricted to debug repository-root runs"),
    ))
}

#[cfg(test)]
#[path = "../tests/runtime/mod.rs"]
mod tests;
