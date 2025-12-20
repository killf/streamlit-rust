use crate::api::{get_app, StreamlitApp};
use crate::streamlit::Streamlit;
use actix_web::{web, App, HttpRequest, HttpResponse, HttpServer, Responder};
use std::sync::Arc;

/// Global function registry for Streamlit apps
pub static mut STREAMLIT_MAIN_FUNCTION: Option<fn(&mut Streamlit)> = None;

/// Set the main function for the Streamlit app
pub fn set_main_function(f: fn(&mut Streamlit)) {
    unsafe {
        STREAMLIT_MAIN_FUNCTION = Some(f);
    }
}

/// Get the main function for the Streamlit app
pub fn get_main_function() -> Option<fn(&mut Streamlit)> {
    unsafe { STREAMLIT_MAIN_FUNCTION }
}

/// Execute the user's main function if it exists
/// This function operates on the global StreamlitApp
pub fn execute_user_main() {
    if let Some(user_main) = get_main_function() {
        // Create a Streamlit instance that uses the global app
        let mut st = Streamlit::new();
        user_main(&mut st);

        // The elements are automatically added to the global app through StreamlitApp
    }
}

/// StreamlitServer - main server implementation
pub struct StreamlitServer {
    app: Arc<StreamlitApp>,
}

impl StreamlitServer {
    pub fn new() -> Self {
        Self {
            app: Arc::new(get_app().clone()),
        }
    }

    pub async fn start(&self, host: &str, port: u16) -> std::io::Result<()> {
        log::info!(
            "Starting Streamlit Rust Backend server on {}:{}",
            host,
            port
        );

        let app_state = AppState;

        HttpServer::new(move || {
            App::new()
                .app_data(web::Data::new(app_state.clone()))
                .service(web::resource("/_stcore/stream").route(web::get().to(websocket_handler)))
                .service(
                    web::resource("/_stcore/health")
                        .route(web::get().to(health_check))
                        .route(web::head().to(health_check)),
                )
                .service(web::resource("/_stcore/host-config").route(web::get().to(host_config)))
        })
        .bind((host, port))?
        .run()
        .await
    }

    pub fn get_app(&self) -> Arc<StreamlitApp> {
        self.app.clone()
    }
}

impl Default for StreamlitServer {
    fn default() -> Self {
        Self::new()
    }
}

#[derive(Clone)]
struct AppState;

async fn websocket_handler(
    req: HttpRequest,
    stream: web::Payload,
    _state: web::Data<AppState>,
) -> Result<HttpResponse, actix_web::Error> {
    log::info!(
        "New WebSocket connection from: {}",
        req.connection_info().peer_addr().unwrap_or("unknown")
    );

    // Extract and log WebSocket protocol information
    let mut selected_protocol = None;
    if let Some(protocols) = req.headers().get("Sec-WebSocket-Protocol") {
        if let Ok(protocol_str) = protocols.to_str() {
            log::info!("Client WebSocket protocols: {}", protocol_str);
            // Client sends: "streamlit, 2|session_id|..."
            // We need to respond with "streamlit" to complete the handshake
            if protocol_str.contains("streamlit") {
                selected_protocol = Some("streamlit");
                log::info!("Selected WebSocket subprotocol: streamlit");
            }
        }
    }

    // Perform WebSocket handshake with the selected protocol
    let (mut response, session, msg_stream) = actix_ws::handle(&req, stream)?;

    // Add the selected subprotocol to the response headers
    if let Some(protocol) = selected_protocol {
        response.headers_mut().insert(
            actix_web::http::header::HeaderName::from_static("sec-websocket-protocol"),
            actix_web::http::header::HeaderValue::from_static(protocol),
        );
        log::info!("Added Sec-WebSocket-Protocol: {} to handshake response", protocol);
    }

    // Handle WebSocket connection in the same async context
    // to avoid Send issues with MessageStream
    actix_web::rt::spawn(async move {
        if let Err(e) = crate::websocket::handle_streamlit_websocket_connection(
            session,
            msg_stream,
        )
        .await
        {
            log::error!("WebSocket connection error: {}", e);
        }
    });

    Ok(response)
}

async fn health_check() -> impl Responder {
    HttpResponse::Ok()
        .insert_header(("Cache-Control", "no-cache"))
        .insert_header(("Access-Control-Allow-Origin", "*"))
        .insert_header(("Content-Type", "text/html; charset=UTF-8"))
        .body("ok")
}

async fn host_config() -> impl Responder {
    let host_config = serde_json::json!({
        "allowedOrigins": [
            "*",
        ],
        "useExternalAuthToken": false,
        "enableCustomParentMessages": false,
        "enforceDownloadInNewTab": false,
        "metricsUrl": "",
        "blockErrorDialogs": false,
        "resourceCrossOriginMode": serde_json::Value::Null
    });

    HttpResponse::Ok()
        .insert_header(("Cache-Control", "no-cache"))
        .insert_header(("Access-Control-Allow-Origin", "*"))
        .insert_header(("Content-Type", "application/json"))
        .json(host_config)
}
