use crate::elements::common::RenderContext;
use crate::error::StreamlitError;
use crate::proto::{WidgetState, back_msg::Type, *};
use crate::session::SessionLease;
use crate::{Streamlit, StreamlitServer};
use actix_ws::{MessageStream, Session};
use futures_util::StreamExt;
use prost::Message;

async fn do_rerun_script(session: &mut Session, lease: &SessionLease, server: &StreamlitServer, widget_states: Vec<WidgetState>) -> Result<(), StreamlitError> {
    // Serialise runs even if a replacement connection arrives while its
    // predecessor is finishing. Stop/cancel remains outside this implementation.
    let _run = lease.run.lock().await;
    if !lease.is_current() {
        return Err(StreamlitError::Session("connection was superseded".into()));
    }
    // Only application values persist. The render tree and widget triggers are
    // rebuilt for each run, so a previous button click cannot become sticky.
    let st = Streamlit::with_session_state(lease.state.clone()).process_widget_states(widget_states);

    // 创建 channel 用于流式发送消息
    let (tx, mut rx) = tokio::sync::mpsc::unbounded_channel::<crate::proto::ForwardMsg>();

    // 创建 RenderContext 并设置到 App 中，让 App::push 时能立即发送消息
    let context = RenderContext::with_sender(lease.id.clone(), tx.clone());
    st.app.lock().set_render_context(context);

    // 发送初始化消息（new_session, main_block）
    {
        let mut app = st.app.lock();
        if let Some(context) = app.render_context_mut() {
            let main_script_hash = crate::utils::hash::hash("");
            context.active_script_hash = main_script_hash.clone();
            context.push(crate::elements::app::create_new_session(context.session_id.clone(), main_script_hash));
            context.push(crate::elements::app::create_session_status_changed(true, false));
            context.delta_path.push(0);
            context.push(crate::elements::app::create_main_block());
            context.delta_path.push(0);
        }
    }

    log::info!("Executing user main function...");

    // 使用 tokio::select! 并发执行用户代码和消息发送
    let entry_future = async {
        server.entry.call(&st).await;
        // 执行完毕后发送 script_finished
        let mut app = st.app.lock();
        if let Some(context) = app.render_context_mut() {
            context.push(crate::elements::app::create_script_finished());
            context.push(crate::elements::app::create_session_status_changed(false, false));
            context.sender.take();
        }
        drop(tx); // 关闭 sender
    };

    let send_future = async {
        let mut count = 0;
        while let Some(msg) = rx.recv().await {
            log::info!("Sending ForwardMsg #{}: {:?}", count, msg);
            session.binary(msg.encode_to_vec()).await?;
            count += 1;
        }
        log::info!("Sent {} messages total", count);
        Ok::<_, StreamlitError>(())
    };

    // 并发执行
    let (_, send_result) = tokio::join!(entry_future, send_future);
    send_result?;

    log::info!("Rerun script completed for session: {}", lease.id);
    Ok(())
}

async fn handle_back_message(session: &mut Session, lease: &SessionLease, back_msg: BackMsg, server: &StreamlitServer) -> Result<(), StreamlitError> {
    if let Some(tp) = back_msg.r#type {
        match tp {
            Type::RerunScript(client_state) => {
                log::info!("Handling rerun script request");
                let widget_states = client_state.widget_states.map(|ws| ws.widgets).unwrap_or_default();
                do_rerun_script(session, lease, server, widget_states).await?;
            }
            Type::AppHeartbeat(_) => {
                let reply = ForwardMsg {
                    r#type: Some(forward_msg::Type::HeartbeatAck(true)),
                    ..Default::default()
                };
                session.binary(reply.encode_to_vec()).await?;
            }
            _ => {
                log::error!("Unknown back_msg type: {:?}", tp);
            }
        }
    }
    Ok(())
}

pub(crate) async fn handle_connection(mut session: Session, mut msg_stream: MessageStream, server: &StreamlitServer, lease: SessionLease) -> Result<(), StreamlitError> {
    log::info!("=== Streamlit WebSocket handler started ===");

    log::info!("Attached session ID: {}", lease.id);

    // Handle incoming messages with proper processing
    let mut message_count = 0;
    log::info!("Complete message sequence sent, starting message processing loop...");

    while let Some(msg_result) = msg_stream.next().await {
        if !lease.is_current() {
            session.close(None).await?;
            break;
        }
        message_count += 1;
        log::info!("🔍 Processing message #{}", message_count);
        log::debug!("Message result: {:?}", msg_result);

        match msg_result {
            Ok(actix_ws::Message::Binary(data)) => {
                log::info!("Received binary protobuf message: {} bytes", data.len());

                match BackMsg::decode(data) {
                    Ok(back_msg) => {
                        log::info!("Successfully decoded BackMsg: {:?}", back_msg);
                        handle_back_message(&mut session, &lease, back_msg, server).await?;
                    }
                    Err(e) => {
                        log::warn!("Failed to decode BackMsg: {}", e);
                    }
                }
            }
            Ok(actix_ws::Message::Text(text)) => {
                log::info!("Received text message: {}", text);
            }
            Ok(actix_ws::Message::Close(reason)) => {
                log::info!("🚪 WebSocket connection closed: {:?}", reason);
                log::info!("📊 Total messages processed: {}", message_count);
                session.close(reason).await?;
                break;
            }
            Ok(actix_ws::Message::Ping(ping)) => {
                log::debug!("Received ping, sending pong");
                if let Err(e) = session.pong(&ping).await {
                    log::error!("Failed to send pong: {}", e);
                }
            }
            Ok(actix_ws::Message::Pong(_pong)) => {
                log::debug!("Received pong");
            }
            Ok(actix_ws::Message::Continuation(_)) => {
                log::debug!("Received continuation frame");
            }
            Ok(actix_ws::Message::Nop) => {
                log::debug!("Received nop");
            }
            Err(e) => {
                log::error!("WebSocket stream error: {}", e);
                break;
            }
        }
    }

    log::info!("Streamlit WebSocket connection closed");
    log::info!("📈 Connection stats: processed {} messages from frontend", message_count);
    if message_count == 0 {
        log::warn!("⚠️  No messages received from frontend - this suggests protobuf message format issues");
    }
    Ok(())
}
