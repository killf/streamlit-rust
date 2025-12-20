use crate::api::{get_app, StreamlitApp};
use crate::main_macro::execute_user_main;
use actix_web::{web, App, HttpRequest, HttpResponse, HttpServer, Responder};
use std::sync::Arc;

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

        let app_state = AppState {
            streamlit_app: self.app.clone(),
        };

        HttpServer::new(move || {
            App::new()
                .app_data(web::Data::new(app_state.clone()))
                .service(web::resource("/_stcore/stream").route(web::get().to(websocket_handler)))
                .service(web::resource("/_stcore/health").route(web::get().to(health_check)).route(web::head().to(health_check)))
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
struct AppState {
    streamlit_app: Arc<StreamlitApp>,
}

async fn websocket_handler(
    req: HttpRequest,
    stream: web::Payload,
    _state: web::Data<AppState>,
) -> Result<HttpResponse, actix_web::Error> {
    log::info!(
        "New WebSocket connection from: {}",
        req.connection_info().peer_addr().unwrap_or("unknown")
    );

    let (response, session, _msg_stream) = actix_ws::handle(&req, stream)?;

    // Simple echo handler for now
    tokio::spawn(async move {
        if let Err(e) = crate::websocket::handle_websocket_connection(
            session,
            futures_util::stream::empty::<Result<_, _>>(),
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
