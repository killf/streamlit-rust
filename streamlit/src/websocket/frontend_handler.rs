//! WebSocket handler that's compatible with Streamlit frontend
//! This handles protobuf messages and matches the expected frontend behavior

use crate::api::{get_app, StreamlitElement};
use actix_ws::{Message, ProtocolError, Session};
use futures_util::StreamExt;

use crate::proto::proto::{BackMsg, ForwardMsg, NewSession};
use prost::Message as ProstMessage;

/// Handle WebSocket connection with Streamlit frontend compatibility
pub async fn handle_frontend_websocket_connection(
    mut session: Session,
    mut msg_stream: impl futures_util::Stream<Item = Result<Message, ProtocolError>> + Unpin,
) -> Result<(), Box<dyn std::error::Error>> {
    log::info!("Frontend WebSocket handler started");

    // Generate session ID
    let session_id = uuid::Uuid::new_v4().to_string();

    // Send initial new_session message
    send_new_session_message(&mut session, &session_id).await?;

    // Handle incoming messages
    while let Some(msg_result) = msg_stream.next().await {
        match msg_result {
            Ok(Message::Binary(data)) => {
                log::debug!("Received binary message: {} bytes", data.len());
                handle_binary_message(&mut session, &data, &session_id).await?;
            }
            Ok(Message::Text(text)) => {
                log::warn!("Received unexpected text message: {}", text);
                // Frontend should only send binary, but handle gracefully
                handle_text_message_fallback(&mut session, &text, &session_id).await?;
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

    log::info!("Frontend WebSocket connection closed");
    Ok(())
}

async fn send_new_session_message(
    session: &mut Session,
    session_id: &str,
) -> Result<(), Box<dyn std::error::Error>> {
    {
        let new_session = NewSession {
            session_id: session_id.to_string(),
            max_message_size: "268435456".to_string(), // 256MB
        };

        let forward_msg = ForwardMsg {
            hash: generate_hash(),
            metadata: Some(create_default_metadata()),
            r#type: Some(crate::proto::forward_msg::Type::NewSession(new_session)),
        };

        let data = forward_msg.encode_to_vec();
        session.binary(data).await?;
    }

    log::info!("Sent new session message for session: {}", session_id);
    Ok(())
}

async fn handle_binary_message(
    session: &mut Session,
    data: &[u8],
    session_id: &str,
) -> Result<(), Box<dyn std::error::Error>> {
    {
        // Try to parse as BackMsg
        if let Ok(back_msg) = BackMsg::decode(data) {
            handle_backmsg(session, back_msg, session_id).await?;
        } else {
            log::warn!("Failed to decode binary message as BackMsg");
        }
    }

    Ok(())
}

async fn handle_backmsg(
    session: &mut Session,
    back_msg: BackMsg,
    session_id: &str,
) -> Result<(), Box<dyn std::error::Error>> {
    use crate::proto::back_msg::Type;

    if let Some(msg_type) = back_msg.r#type {
        match msg_type {
            Type::ClearCache(_) => {
                log::info!("Clear cache requested");
                // Handle cache clearing
            }
            Type::RerunScript(client_state) => {
                log::info!("Rerun script requested");
                handle_rerun_script(session, client_state, session_id).await?;
            }
            Type::StopScript(_) => {
                log::info!("Stop script requested");
                // Handle script stopping
            }
            Type::DebugDisconnectWebsocket(_) => {
                log::info!("Debug disconnect requested");
                // Handle debug disconnect
            }
            Type::DebugShutdownRuntime(_) => {
                log::info!("Debug shutdown requested");
                // Handle debug shutdown
            }
            Type::AppHeartbeat(_) => {
                log::debug!("App heartbeat received");
                // Handle heartbeat
            }
            _ => {
                log::warn!("Unhandled BackMsg type: {:?}", msg_type);
            }
        }
    }

    Ok(())
}

async fn handle_text_message_fallback(
    session: &mut Session,
    text: &str,
    session_id: &str,
) -> Result<(), Box<dyn std::error::Error>> {
    // Fallback handling for JSON messages
    if let Ok(json) = serde_json::from_str::<serde_json::Value>(text) {
        log::debug!("Received JSON message: {}", json);

        if let Some(command) = json.get("command").and_then(|v| v.as_str()) {
            match command {
                "rerun_script" => {
                    log::info!("Rerun script requested via JSON");
                    handle_rerun_script_fallback(session, session_id).await?;
                }
                _ => {
                    log::warn!("Unknown JSON command: {}", command);
                }
            }
        }
    }

    Ok(())
}

async fn handle_rerun_script(
    session: &mut Session,
    _client_state: Option<crate::proto::ClientState>,
    session_id: &str,
) -> Result<(), Box<dyn std::error::Error>> {
    let app = get_app();

    // Clear previous elements and increment run count
    app.clear_elements();
    app.increment_run_count();

    // Execute the user's main function
    crate::server::execute_user_main();

    // Send script_finished message
    send_script_finished_message(session).await?;

    // Send all elements as delta messages
    send_elements_as_deltas(session, app.get_elements()).await?;

    log::info!("Script rerun completed for session: {}", session_id);
    Ok(())
}

async fn handle_rerun_script_fallback(
    session: &mut Session,
    session_id: &str,
) -> Result<(), Box<dyn std::error::Error>> {
    let app = get_app();

    // Clear previous elements and increment run count
    app.clear_elements();
    app.increment_run_count();

    // Execute the user's main function
    crate::server::execute_user_main();

    // Send script finished message
    send_script_finished_message_fallback(session).await?;

    // Send elements as JSON
    send_elements_as_json(session, app.get_elements()).await?;

    log::info!(
        "Script rerun completed (fallback) for session: {}",
        session_id
    );
    Ok(())
}

async fn send_script_finished_message(
    session: &mut Session,
) -> Result<(), Box<dyn std::error::Error>> {
    let forward_msg = ForwardMsg {
        hash: generate_hash(),
        metadata: Some(create_default_metadata()),
        r#type: Some(crate::proto::forward_msg::Type::ScriptFinished(
            ScriptFinishedStatus::FinishedSuccessfully as i32,
        )),
    };

    let data = forward_msg.encode_to_vec();
    session.binary(data).await?;
    Ok(())
}

async fn send_script_finished_message_fallback(
    session: &mut Session,
) -> Result<(), Box<dyn std::error::Error>> {
    let json_message = serde_json::json!({
        "type": "script_finished",
        "status": "finished_successfully"
    });
    session.text(json_message.to_string()).await?;
    Ok(())
}

async fn send_elements_as_deltas(
    session: &mut Session,
    elements: Vec<StreamlitElement>,
) -> Result<(), Box<dyn std::error::Error>> {
    for (index, element) in elements.iter().enumerate() {
        // Convert StreamlitElement to JSON first, then to protobuf Delta
        let json_value = serde_json::to_value(element)?;
        if let Some(delta) = json_to_delta(&json_value, index as u32)? {
            let forward_msg = ForwardMsg {
                hash: generate_hash(),
                metadata: Some(create_metadata_with_path(&[index as u32])),
                r#type: Some(crate::proto::forward_msg::Type::Delta(delta)),
            };

            let data = forward_msg.encode_to_vec();
            session.binary(data).await?;
        }
    }
    Ok(())
}

async fn send_elements_as_json(
    session: &mut Session,
    elements: Vec<StreamlitElement>,
) -> Result<(), Box<dyn std::error::Error>> {
    // Convert StreamlitElement to JSON
    let json_elements: Vec<serde_json::Value> = elements
        .into_iter()
        .map(|el| serde_json::to_value(el).unwrap_or_default())
        .collect();

    let json_message = serde_json::json!({
        "type": "elements",
        "elements": json_elements
    });
    session.text(json_message.to_string()).await?;
    Ok(())
}

fn json_to_delta(
    json_element: &serde_json::Value,
    index: u32,
) -> Result<Option<crate::proto::Delta>, Box<dyn std::error::Error>> {
    use crate::proto::{element, Delta, Element};

    let element_type = json_element
        .get("type")
        .and_then(|v| v.as_str())
        .unwrap_or("text");

    let element = match element_type {
        "text" => {
            let body = json_element
                .get("body")
                .and_then(|v| v.as_str())
                .unwrap_or("");
            Some(Element {
                id: format!("element_{}", index),
                allow_hover: false,
                r#type: Some(element::Type::Text(Text {
                    body: body.to_string(),
                })),
            })
        }
        "markdown" => {
            let body = json_element
                .get("body")
                .and_then(|v| v.as_str())
                .unwrap_or("");
            Some(Element {
                id: format!("element_{}", index),
                allow_hover: false,
                r#type: Some(element::Type::Text(Text {
                    body: body.to_string(),
                })),
            })
        }
        _ => {
            log::warn!("Unsupported element type: {}", element_type);
            None
        }
    };

    Ok(element.map(|el| Delta {
        r#type: Some(crate::proto::delta::Type::NewElement(el)),
    }))
}

fn generate_hash() -> String {
    use std::collections::hash_map::DefaultHasher;
    use std::hash::{Hash, Hasher};

    let mut hasher = DefaultHasher::new();
    std::time::SystemTime::now().hash(&mut hasher);
    format!("{:x}", hasher.finish())
}

fn create_default_metadata() -> crate::proto::ForwardMsgMetadata {
    crate::proto::ForwardMsgMetadata {
        cacheable: false,
        delta_path: vec![],
        active_script_hash: "default".to_string(),
    }
}

fn create_metadata_with_path(path: &[u32]) -> crate::proto::ForwardMsgMetadata {
    crate::proto::ForwardMsgMetadata {
        cacheable: false,
        delta_path: path.to_vec(),
        active_script_hash: "default".to_string(),
    }
}
