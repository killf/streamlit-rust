//! Simplified WebSocket handler compatible with Streamlit frontend
//! Uses JSON format instead of protobuf for easier debugging

use crate::api::{get_app, StreamlitElement};
use actix_ws::{Message, ProtocolError, Session};
use futures_util::StreamExt;
use serde_json::json;

/// Handle WebSocket connection with Streamlit frontend compatibility (JSON mode)
pub async fn handle_simple_frontend_websocket_connection(
    mut session: Session,
    mut msg_stream: impl futures_util::Stream<Item = Result<Message, ProtocolError>> + Unpin,
) -> Result<(), Box<dyn std::error::Error>> {
    log::info!("=== Simple Frontend WebSocket handler started ===");

    // Generate session ID
    let session_id = uuid::Uuid::new_v4().to_string();
    log::info!("Generated session ID: {}", session_id);

    // Wait a moment before sending messages to let frontend settle
    tokio::time::sleep(tokio::time::Duration::from_millis(100)).await;

    // Send new_session message first
    log::info!("Sending new_session message...");
    if let Err(e) = send_new_session_message(&mut session, &session_id).await {
        log::error!("Failed to send new_session message: {}", e);
        return Err(e.into());
    }
    log::info!("new_session message sent successfully");

    // Add delay before sending script_finished
    tokio::time::sleep(tokio::time::Duration::from_millis(50)).await;

      // Handle incoming messages with better error handling
    let mut message_count = 0;
    log::info!("Starting message processing loop...");

    while let Some(msg_result) = msg_stream.next().await {
        message_count += 1;
        log::info!("🔍 Processing message #{}", message_count);
        match msg_result {
            Ok(Message::Binary(data)) => {
                log::info!("Received binary message: {} bytes", data.len());
                // Try to decode as UTF-8 JSON first
                match String::from_utf8(data.to_vec()) {
                    Ok(json_str) => {
                        log::info!("Binary data decoded as JSON: {}", json_str);
                        if let Err(e) = handle_json_message(&mut session, &json_str, &session_id).await {
                            log::error!("Error handling JSON message: {}", e);
                            // Don't break, continue processing other messages
                        }
                    }
                    Err(e) => {
                        log::warn!("Binary data is not valid UTF-8: {}", e);
                        // For now, just ignore non-UTF8 binary data
                    }
                }
            }
            Ok(Message::Text(text)) => {
                log::info!("Received text message: {}", text);
                if let Err(e) = handle_json_message(&mut session, &text, &session_id).await {
                    log::error!("Error handling JSON message: {}", e);
                    // Don't break, continue processing other messages
                }
            }
            Ok(Message::Close(reason)) => {
                log::info!("WebSocket connection closed: {:?}", reason);
                break;
            }
            Ok(Message::Ping(ping)) => {
                log::debug!("Received ping, sending pong");
                if let Err(e) = session.pong(&ping).await {
                    log::error!("Failed to send pong: {}", e);
                }
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
                log::error!("WebSocket stream error: {}", e);
                break;
            }
        }
    }

    log::info!("Frontend WebSocket connection closed");
    Ok(())
}

async fn send_new_session_message(
    session: &mut Session,
    session_id: &str,
) -> Result<(), Box<dyn std::error::Error>> {
    // Send a simple binary message that mimics Streamlit's format
    // Start with a simple text message first to see what format is expected
    let new_session_msg = json!({
        "type": "new_session",
        "session": {
            "session_id": session_id,
            "max_message_size": "268435456",
            "streamlit_version": "1.28.0",
            "python_version": "3.9.0",
            "installation_id": "rust-backend-test",
            "user_id": "test-user"
        }
    });

    let json_str = new_session_msg.to_string();
    log::info!("Sending new_session message: {}", json_str);

    // Try sending as both text and binary to see what frontend expects
    session.text(json_str.clone()).await?;

    // Also try as binary (UTF-8 encoded)
    session.text(json_str).await?;

    // Also send script_finished to indicate ready state
    send_script_finished_message(session).await?;

    Ok(())
}

async fn handle_json_message(
    session: &mut Session,
    json_str: &str,
    session_id: &str,
) -> Result<(), Box<dyn std::error::Error>> {
    // Try to parse as JSON
    if let Ok(data) = serde_json::from_str::<serde_json::Value>(json_str) {
        log::info!("Parsed JSON message: {}", serde_json::to_string_pretty(&data)?);

        // Handle different message types
        if let Some(msg_type) = data.get("command").and_then(|v| v.as_str()) {
            match msg_type {
                "rerun_script" => {
                    log::info!("Rerun script requested");
                    handle_rerun_script(session, session_id).await?;
                }
                "clear_cache" => {
                    log::info!("Clear cache requested");
                    // Handle cache clearing
                }
                "stop_script" => {
                    log::info!("Stop script requested");
                    // Handle script stopping
                }
                _ => {
                    log::warn!("Unknown command: {}", msg_type);
                }
            }
        } else {
            log::debug!("Received JSON without command field");
        }
    } else {
        log::warn!("Failed to parse JSON: {}", json_str);
    }

    Ok(())
}

async fn handle_rerun_script(
    session: &mut Session,
    session_id: &str,
) -> Result<(), Box<dyn std::error::Error>> {
    let app = get_app();

    // Clear previous elements and increment run count
    app.clear_elements();
    app.increment_run_count();

    // Execute the user's main function
    crate::server::execute_user_main();

    log::info!("Executed user main function, got {} elements", app.get_elements().len());

    // Send script_finished message
    send_script_finished_message(session).await?;

    // Send all elements
    send_elements_as_json(session, app.get_elements()).await?;

    log::info!("Rerun script completed for session: {}", session_id);
    Ok(())
}

async fn send_script_finished_message(
    session: &mut Session,
) -> Result<(), Box<dyn std::error::Error>> {
    let finished_msg = json!({
        "type": "script_finished",
        "scriptFinished": {
            "status": "finished_successfully",
            "progress": 1.0,
            "duration_ms": 100
        }
    });

    let json_str = finished_msg.to_string();
    log::info!("Sending script_finished message: {}", json_str);
    session.text(json_str).await?;
    Ok(())
}

async fn send_elements_as_json(
    session: &mut Session,
    elements: Vec<StreamlitElement>,
) -> Result<(), Box<dyn std::error::Error>> {
    log::info!("Sending {} elements", elements.len());

    for (index, element) in elements.iter().enumerate() {
        let element_json = json!({
            "type": "delta",
            "delta_id": index,
            "element": element
        });

        let json_str = element_json.to_string();
        log::info!("Sending element {}: {}", index, json_str);
        session.text(json_str).await?;
    }

    Ok(())
}