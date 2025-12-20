use super::message_types::{StreamlitCommand, StreamlitMessage};
use crate::api::get_app;
use actix_ws::{Message, ProtocolError, Session};
use futures_util::StreamExt;

/// Simplified WebSocket handler for proto compatibility
/// This version works with JSON format but is designed to be easily
/// convertible to protobuf when protoc becomes available
pub async fn handle_websocket_connection(
    mut session: Session,
    mut msg_stream: impl futures_util::Stream<Item = Result<Message, ProtocolError>> + Unpin,
) -> Result<(), Box<dyn std::error::Error>> {
    log::info!("WebSocket proto handler started");

    // Send initial message with script information
    send_init_message(&mut session).await?;

    // Handle incoming messages
    while let Some(msg_result) = msg_stream.next().await {
        match msg_result {
            Ok(Message::Text(text)) => {
                log::debug!("Received text message: {}", text);
                handle_text_message(&mut session, &text).await?;
            }
            Ok(Message::Binary(data)) => {
                log::debug!("Received binary message: {} bytes", data.len());

                // Try to parse as UTF-8 JSON first (for compatibility)
                if let Ok(json_str) = String::from_utf8(data.to_vec()) {
                    handle_text_message(&mut session, &json_str).await?;
                } else {
                    log::warn!("Received non-UTF8 binary data, ignoring for now");
                }
            }
            Ok(Message::Close(reason)) => {
                log::info!("WebSocket connection closed: {:?}", reason);
                break;
            }
            Ok(Message::Ping(ping)) => {
                log::debug!("Received ping");
                session.pong(&ping).await?;
            }
            Ok(Message::Pong(_pong)) => {
                log::debug!("Received pong");
            }
            Ok(Message::Continuation(_)) => {
                log::debug!("Received continuation frame");
            }
            Ok(Message::Nop) => {
                log::debug!("Received nop");
            }
            Err(e) => {
                log::error!("WebSocket error: {}", e);
                break;
            }
        }
    }

    log::info!("WebSocket connection closed");
    Ok(())
}

async fn send_init_message(session: &mut Session) -> Result<(), Box<dyn std::error::Error>> {
    let init_msg = StreamlitMessage {
        type_field: "init".to_string(),
        data: serde_json::json!({
            "title": "Streamlit Rust App",
            "version": "0.1.0-rust"
        }),
    };

    let json = serde_json::to_string(&init_msg)?;
    session.text(json).await?;
    Ok(())
}

async fn handle_text_message(
    session: &mut Session,
    text: &str,
) -> Result<(), Box<dyn std::error::Error>> {
    log::debug!("Handling text message: {}", text);

    // Try to parse as a Streamlit command
    if let Ok(command) = serde_json::from_str::<StreamlitCommand>(text) {
        match command.command.as_str() {
            "run_script" => {
                log::info!("Run script command received");
                handle_run_script(session).await?;
            }
            "get_elements" => {
                log::info!("Get elements command received");
                handle_get_elements(session).await?;
            }
            "widget_event" => {
                log::info!("Widget event received");
                handle_widget_event(session, &command).await?;
            }
            _ => {
                log::warn!("Unknown command: {}", command.command);
            }
        }
    } else {
        log::debug!("Received non-command text: {}", text);
    }

    Ok(())
}

async fn handle_run_script(session: &mut Session) -> Result<(), Box<dyn std::error::Error>> {
    let app = get_app();

    // Clear previous elements and increment run count
    app.clear_elements();
    app.increment_run_count();

    // Create a simple demo app
    app.title("Hello from Streamlit Rust!");
    app.write("This is a demonstration of the Rust implementation.");

    // Get current elements and send them
    let elements = app.get_elements();
    let response = StreamlitMessage {
        type_field: "elements".to_string(),
        data: serde_json::json!({
            "elements": elements,
            "run_count": app.get_run_count()
        }),
    };

    let json = serde_json::to_string(&response)?;
    session.text(json).await?;

    Ok(())
}

async fn handle_get_elements(session: &mut Session) -> Result<(), Box<dyn std::error::Error>> {
    let app = get_app();
    let elements = app.get_elements();

    let response = StreamlitMessage {
        type_field: "elements".to_string(),
        data: serde_json::json!({
            "elements": elements,
            "run_count": app.get_run_count()
        }),
    };

    let json = serde_json::to_string(&response)?;
    session.text(json).await?;

    Ok(())
}

async fn handle_widget_event(
    session: &mut Session,
    command: &StreamlitCommand,
) -> Result<(), Box<dyn std::error::Error>> {
    // Extract widget information from the command
    if let Some(widget_data) = command.data.get("widget") {
        if let (Some(widget_id), Some(widget_value)) = (
            widget_data.get("id").and_then(|v| v.as_str()),
            widget_data.get("value"),
        ) {
            log::info!(
                "Widget {} updated with value: {:?}",
                widget_id,
                widget_value
            );

            // Update widget state in the app
            // This is a simplified version - real implementation would handle
            // different widget types and their value conversions
            let _app = get_app();

            // For now, just acknowledge the widget update
            let response = StreamlitMessage {
                type_field: "widget_ack".to_string(),
                data: serde_json::json!({
                    "widget_id": widget_id,
                    "status": "updated"
                }),
            };

            let json = serde_json::to_string(&response)?;
            session.text(json).await?;
        }
    }

    Ok(())
}
