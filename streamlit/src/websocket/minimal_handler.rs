//! Minimal WebSocket handler for debugging
//! This handler just accepts connections and sends simple responses

use actix_ws::{Message, ProtocolError, Session};
use futures_util::StreamExt;

/// Minimal WebSocket handler that accepts any connection
pub async fn handle_minimal_websocket_connection(
    mut session: Session,
    mut msg_stream: impl futures_util::Stream<Item = Result<Message, ProtocolError>> + Unpin,
) -> Result<(), Box<dyn std::error::Error>> {
    log::info!("=== Minimal WebSocket handler started ===");

    // Send a welcome message
    session.text("Connected to Streamlit Rust Backend").await?;
    log::info!("Sent welcome message");

    // Handle messages
    let mut count = 0;
    while let Some(msg_result) = msg_stream.next().await {
        count += 1;
        log::info!("Processing message #{}", count);

        match msg_result {
            Ok(Message::Text(text)) => {
                log::info!("Received text: {}", text);
                session.text(format!("Echo: {}", text)).await?;
            }
            Ok(Message::Binary(data)) => {
                log::info!("Received binary: {} bytes", data.len());
                // Try to decode as string
                if let Ok(text) = String::from_utf8(data.to_vec()) {
                    log::info!("Binary as text: {}", text);
                    session.text(format!("Echo binary: {}", text)).await?;
                } else {
                    session.text("Received binary data").await?;
                }
            }
            Ok(Message::Close(reason)) => {
                log::info!("Connection closing: {:?}", reason);
                break;
            }
            Ok(Message::Ping(ping)) => {
                log::debug!("Ping received");
                session.pong(&ping).await?;
            }
            Ok(Message::Pong(_)) => {
                log::debug!("Pong received");
            }
            Ok(_) => {
                log::debug!("Other message type");
            }
            Err(e) => {
                log::error!("Stream error: {}", e);
                break;
            }
        }
    }

    log::info!("WebSocket handler ending");
    Ok(())
}
