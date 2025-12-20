mod common;

use actix_web::{test, web, App};
use common::{health_check, index_handler, run_script_handler, AppState};
use streamlit::server::StreamlitServer;

#[actix_web::test]
async fn test_health_check() {
    let server = StreamlitServer::new();
    let app_state = AppState {
        streamlit_app: server.get_app(),
    };

    let app = test::init_service(
        App::new()
            .app_data(web::Data::new(app_state))
            .route("/_stcore/health", web::get().to(health_check)),
    )
    .await;

    let req = test::TestRequest::get().uri("/_stcore/health").to_request();
    let resp = test::call_service(&app, req).await;

    assert!(resp.status().is_success());
}

#[actix_web::test]
async fn test_index_handler() {
    let app = test::init_service(App::new().route("/", web::get().to(index_handler))).await;

    let req = test::TestRequest::get().uri("/").to_request();
    let resp = test::call_service(&app, req).await;

    assert!(resp.status().is_success());
}

#[actix_web::test]
async fn test_run_script_handler() {
    let server = StreamlitServer::new();
    let app_state = AppState {
        streamlit_app: server.get_app(),
    };

    let app = test::init_service(
        App::new()
            .app_data(web::Data::new(app_state))
            .route("/api/run", web::post().to(run_script_handler)),
    )
    .await;

    let req = test::TestRequest::post()
        .uri("/api/run")
        .set_payload("test script")
        .to_request();

    let resp = test::call_service(&app, req).await;

    assert!(resp.status().is_success());
}
