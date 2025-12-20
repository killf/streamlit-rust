// Test utilities for common test functions
use actix_web::{web, HttpResponse, Responder};
use std::sync::Arc;
use streamlit::api::StreamlitApp;

pub struct AppState {
    pub streamlit_app: Arc<StreamlitApp>,
}

pub async fn health_check() -> impl Responder {
    HttpResponse::Ok().json(serde_json::json!({
        "status": "healthy",
        "version": "0.1.0-rust",
        "timestamp": chrono::Utc::now().to_rfc3339()
    }))
}

pub async fn index_handler() -> impl Responder {
    HttpResponse::Ok().body(
        r#"
<!DOCTYPE html>
<html>
<head>
    <title>Streamlit Rust Backend</title>
</head>
<body>
    <h1>Streamlit Rust Backend Test</h1>
</body>
</html>
    "#,
    )
}

pub async fn run_script_handler(
    req_body: web::Bytes,
    state: web::Data<AppState>,
) -> Result<HttpResponse, actix_web::Error> {
    let _script_content = String::from_utf8_lossy(&req_body);

    state.streamlit_app.clear_elements();
    state.streamlit_app.increment_run_count();

    state.streamlit_app.title("Hello from Rust!");
    state.streamlit_app.write("Test script execution");

    let elements = state.streamlit_app.get_elements();

    Ok(HttpResponse::Ok().json(serde_json::json!({
        "type": "script_result",
        "elements": elements,
        "run_count": state.streamlit_app.get_run_count()
    })))
}
