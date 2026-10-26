use crate::elements::common::RenderContext;
use crate::error::StreamlitError;
use crate::proto::{WidgetState, back_msg::Type, *};
use crate::session::SessionLease;
use crate::{Streamlit, StreamlitServer};
use actix_ws::{MessageStream, Session};
use futures_util::StreamExt;
use prost::Message;

async fn do_rerun_script(session: &mut Session, lease: &SessionLease, server: &StreamlitServer, widget_states: Vec<WidgetState>, query_string: String) -> Result<(), StreamlitError> {
    // Serialise runs even if a replacement connection arrives while its
    // predecessor is finishing.
    let _run = lease.run.lock().await;
    if !lease.is_current() {
        return Err(StreamlitError::Session("connection was superseded".into()));
    }
    // Browser widget states apply to the first run only: a run that
    // `st.rerun()` starts re-executes with the registry values and no second
    // BackMsg (measured 1.66.1 wire). Each run rebuilds the render tree,
    // re-zeroes trigger widgets and gets a fresh run id; only application
    // values persist.
    let mut incoming = Some(widget_states);
    let incoming_query_string = query_string;
    loop {
        let callbacks = lease.state.begin_widgets(incoming.take().unwrap_or_default());
        lease.state.reset_run_control();
        // The URL state the browser reports with this rerun seeds the run's
        // query parameters (st.query_params reads and merges from it).
        lease.state.query_params.lock().load(&incoming_query_string);
        let st = Streamlit::with_session_state(lease.state.clone());

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

        let state = lease.state.clone();
        // 使用 tokio::select! 并发执行用户代码和消息发送
        let entry_future = async {
            for callback in callbacks {
                callback(&st);
            }
            server.entry.call(&st).await;
            state.finish_widgets();
            // 执行完毕后发送 script_finished。测量到的 1.66.1 wire：
            // st.rerun() 中止的 run 以 FINISHED_EARLY_FOR_RERUN 结束，
            // st.stop() 与正常结束都以 FINISHED_SUCCESSFULLY 结束。
            let status = match state.run_control() {
                Some(crate::session::RunControl::Rerun) => crate::proto::forward_msg::ScriptFinishedStatus::FinishedEarlyForRerun,
                _ => crate::proto::forward_msg::ScriptFinishedStatus::FinishedSuccessfully,
            };
            let mut app = st.app.lock();
            app.flush_deferred();
            if let Some(context) = app.render_context_mut() {
                context.push(crate::elements::app::create_script_finished(status));
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

        if lease.state.run_control() != Some(crate::session::RunControl::Rerun) {
            break;
        }
        log::info!("st.rerun() requested within the run; starting the next run for session {}", lease.id);
    }

    log::info!("Rerun script completed for session: {}", lease.id);
    Ok(())
}

async fn handle_back_message(session: &mut Session, lease: &SessionLease, back_msg: BackMsg, server: &StreamlitServer) -> Result<(), StreamlitError> {
    if let Some(tp) = back_msg.r#type {
        match tp {
            Type::FileUrlsRequest(request) => {
                // URLs always belong to the socket's actual session, never a
                // client-supplied foreign session ID. Invalid-request parity
                // remains pending the dedicated reference probe.
                let response = crate::upload::file_urls(&lease.id, request);
                let message = ForwardMsg {
                    r#type: Some(forward_msg::Type::FileUrlsResponse(response)),
                    ..Default::default()
                };
                session.binary(message.encode_to_vec()).await?;
            }
            Type::RerunScript(client_state) => {
                log::info!("Handling rerun script request");
                let widget_states = client_state.widget_states.map(|ws| ws.widgets).unwrap_or_default();
                do_rerun_script(session, lease, server, widget_states, client_state.query_string).await?;
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
