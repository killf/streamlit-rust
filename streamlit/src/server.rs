use crate::api::Streamlit;
use crate::websocket::handler::handle_connection;
use actix_web::http::header::{HeaderName, HeaderValue};
use actix_web::{get, web, App, HttpRequest, HttpResponse, HttpServer, Responder};

#[get("/_stcore/health")]
async fn health_check() -> impl Responder {
    HttpResponse::Ok().insert_header(("Content-Type", "text/html; charset=UTF-8")).body("ok")
}

#[get("/_stcore/host-config")]
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

    HttpResponse::Ok().insert_header(("Content-Type", "application/json")).json(host_config)
}

#[get("/_stcore/stream")]
async fn websocket_handler(req: HttpRequest, stream: web::Payload, state: web::Data<StreamlitServer>) -> Result<HttpResponse, actix_web::Error> {
    let (mut response, session, msg_stream) = actix_ws::handle(&req, stream)?;

    actix_web::rt::spawn(async move {
        if let Err(e) = handle_connection(session, msg_stream, state.get_ref()).await {
            log::error!("WebSocket connection error: {}", e);
        }
    });

    response.headers_mut().insert(HeaderName::from_static("sec-websocket-protocol"), HeaderValue::from_static("streamlit"));

    Ok(response)
}

#[derive(Clone)]
pub struct StreamlitServer {
    pub(crate) entry: fn(&Streamlit),
    pub(crate) host: String,
    pub(crate) port: u16,
}

impl StreamlitServer {
    pub fn new(entry: fn(&Streamlit), host: String, port: u16) -> Self {
        Self { entry, host, port }
    }

    pub async fn start(&self) -> std::io::Result<()> {
        log::info!("Starting Streamlit Rust Backend server on {}:{}", self.host.as_str(), self.port);

        let server = self.clone();
        HttpServer::new(move || App::new().app_data(web::Data::new(server.clone())).service(websocket_handler).service(health_check).service(host_config))
            .bind((self.host.as_str(), self.port))?
            .run()
            .await
    }
}
