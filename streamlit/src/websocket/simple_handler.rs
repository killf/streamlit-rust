use actix_ws::{Message, ProtocolError, Session};
use futures_util::StreamExt;
use log::info;
use std::time::Instant;

pub async fn handle_websocket_connection(
    mut session: Session,
    mut stream: impl StreamExt<Item = Result<Message, ProtocolError>> + Unpin,
) -> Result<(), Box<dyn std::error::Error>> {
    info!("WebSocket connection established");

    let mut last_ping = Instant::now();
    let ping_interval = std::time::Duration::from_secs(30);

    // Send a welcome message
    session.text("Welcome to Streamlit Rust Backend!").await?;

    while let Some(msg_result) = stream.next().await {
        match msg_result {
            Ok(msg) => {
                match msg {
                    Message::Text(text) => {
                        info!("Received text: {}", text);
                        session.text(format!("Echo: {}", text)).await?;
                    }
                    Message::Binary(data) => {
                        info!("Received binary data: {} bytes", data.len());
                        // For now, just echo it back
                        session.binary(data).await?;
                    }
                    Message::Ping(payload) => {
                        info!("Received ping, sending pong");
                        session.pong(&payload).await?;
                        last_ping = Instant::now();
                    }
                    Message::Pong(_) => {
                        info!("Received pong");
                        last_ping = Instant::now();
                    }
                    Message::Close(reason) => {
                        info!("Received close: {:?}", reason);
                        break;
                    }
                    Message::Continuation(_) => {
                        info!("Received continuation frame");
                    }
                    Message::Nop => {
                        info!("Received nop");
                    }
                }
            }
            Err(e) => {
                log::error!("WebSocket error: {}", e);
                break;
            }
        }

        // Check for timeout
        if last_ping.elapsed() > ping_interval * 2 {
            log::warn!("Connection timeout, closing");
            break;
        }

        // Send periodic ping
        if last_ping.elapsed() > ping_interval {
            if let Err(e) = session.ping(b"ping").await {
                log::error!("Failed to send ping: {}", e);
                break;
            }
        }
    }

    // Close the connection
    let _ = session.close(None).await;
    info!("WebSocket connection closed");

    Ok(())
}
