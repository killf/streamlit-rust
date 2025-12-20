use log::{info, warn, error, debug};
use std::time::{SystemTime, UNIX_EPOCH};

pub fn init_logger() {
    env_logger::Builder::from_default_env()
        .filter_level(log::LevelFilter::Info)
        .init();
}

pub fn log_connection_details(session_id: &str, client_info: &str) {
    info!("New WebSocket connection - Session: {}, Client: {}", session_id, client_info);
}

pub fn log_script_execution(script_path: &str, duration_ms: u64, success: bool) {
    if success {
        info!("Script executed successfully - Path: {}, Duration: {}ms", script_path, duration_ms);
    } else {
        error!("Script execution failed - Path: {}, Duration: {}ms", script_path, duration_ms);
    }
}

pub fn log_widget_interaction(widget_id: &str, widget_type: &str, value: &str) {
    debug!("Widget interaction - ID: {}, Type: {}, Value: {}", widget_id, widget_type, value);
}

pub fn get_timestamp() -> u64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default()
        .as_millis() as u64
}