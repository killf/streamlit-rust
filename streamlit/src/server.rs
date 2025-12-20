use crate::api::{get_app, Streamlit};
use actix_web::{web, App, HttpRequest, HttpResponse, HttpServer, Responder};
use std::sync::Arc;

/// StreamlitServer - main server implementation
pub struct StreamlitServer {
    app: Arc<Streamlit>,
    entry: fn(&Streamlit),
}

impl StreamlitServer {
    pub fn new(entry: fn(&Streamlit)) -> Self {
        Self {
            app: Arc::new(get_app().clone()),
            entry,
        }
    }

    pub async fn start(&self, host: &str, port: u16) -> std::io::Result<()> {
        log::info!(
            "Starting Streamlit Rust Backend server on {}:{}",
            host,
            port
        );

        let app_state = AppState { entry: self.entry };

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

    pub fn get_app(&self) -> Arc<Streamlit> {
        self.app.clone()
    }

    pub fn execute_user_main(&self) {
        // Clear previous elements and increment run count
        let app = self.app.clone();
        app.clear_elements();
        app.increment_run_count();

        (self.entry)(&app);

        log::info!(
            "Executed user main function, got {} elements",
            app.get_elements().len()
        );
    }
}

#[derive(Clone)]
struct AppState {
    entry: fn(&Streamlit),
}

async fn websocket_handler(
    req: HttpRequest,
    stream: web::Payload,
    state: web::Data<AppState>,
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
        log::info!(
            "Added Sec-WebSocket-Protocol: {} to handshake response",
            protocol
        );
    }

    // Handle WebSocket connection in the same async context
    // to avoid Send issues with MessageStream
    actix_web::rt::spawn(async move {
        if let Err(e) =
            crate::websocket::handle_streamlit_websocket_connection(session, msg_stream, state.entry).await
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
