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
        log::info!("Starting Streamlit Rust Backend server on {}:{}", host, port);

        let app_state = AppState {
            streamlit_app: self.app.clone(),
        };

        HttpServer::new(move || {
            App::new()
                .app_data(web::Data::new(app_state.clone()))
                .service(web::resource("/_stcore/stream").route(web::get().to(websocket_handler)))
                .service(web::resource("/_stcore/health").route(web::get().to(health_check)))
                .service(web::resource("/").route(web::get().to(index_handler)))
                .service(web::resource("/api/run").route(web::post().to(run_script_handler)))
                .service(actix_files::Files::new("/static", "./static").show_files_listing())
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
    log::info!("New WebSocket connection from: {}", req.connection_info().peer_addr().unwrap_or("unknown"));

    let (response, session, _msg_stream) = actix_ws::handle(&req, stream)?;

    // Simple echo handler for now
    tokio::spawn(async move {
        if let Err(e) = crate::websocket::handle_websocket_connection(session, futures_util::stream::empty::<Result<_, _>>()).await {
            log::error!("WebSocket connection error: {}", e);
        }
    });

    Ok(response)
}


async fn health_check() -> impl Responder {
    HttpResponse::Ok().json(serde_json::json!({
        "status": "healthy",
        "version": "0.1.0-rust",
        "timestamp": chrono::Utc::now().to_rfc3339()
    }))
}

async fn index_handler() -> impl Responder {
    HttpResponse::Ok().body(r#"
<!DOCTYPE html>
<html>
<head>
    <title>Streamlit Rust Backend</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 40px; }
        .container { max-width: 800px; margin: 0 auto; }
        .endpoint { background: #f5f5f5; padding: 10px; margin: 10px 0; border-radius: 5px; }
        code { background: #e0e0e0; padding: 2px 4px; border-radius: 3px; }
    </style>
</head>
<body>
    <div class="container">
        <h1>Streamlit Rust Backend</h1>
        <p>This is a Rust implementation of Streamlit backend.</p>

        <h2>API Endpoints</h2>
        <div class="endpoint">
            <strong>WebSocket:</strong> <code>ws://localhost:8502/_stcore/stream</code>
        </div>
        <div class="endpoint">
            <strong>Health Check:</strong> <code>GET /_stcore/health</code>
        </div>
        <div class="endpoint">
            <strong>Run Script:</strong> <code>POST /api/run</code>
        </div>

        <h2>Usage</h2>
        <p>Connect your Streamlit frontend to this backend to run Rust-powered Streamlit applications.</p>
    </div>
</body>
</html>
    "#)
}

async fn run_script_handler(
    req_body: web::Bytes,
    state: web::Data<AppState>,
) -> Result<HttpResponse, actix_web::Error> {
    log::info!("Received script execution request");

    let script_content = String::from_utf8_lossy(&req_body);

    // Clear previous elements and increment run count
    state.streamlit_app.clear_elements();
    state.streamlit_app.increment_run_count();

    // Execute the user's main function if it exists
    execute_user_main();

    // If no user function was registered, show a default message and script content
    if state.streamlit_app.get_elements().is_empty() {
        state.streamlit_app.title("Hello from Rust!");
        state.streamlit_app.write("This is a demonstration of the Streamlit Rust backend.");
        state.streamlit_app.write("Script content received:");
        state.streamlit_app.write(&script_content);
    }

    let elements = state.streamlit_app.get_elements();

    Ok(HttpResponse::Ok().json(serde_json::json!({
        "type": "script_result",
        "elements": elements,
        "run_count": state.streamlit_app.get_run_count()
    })))
}

