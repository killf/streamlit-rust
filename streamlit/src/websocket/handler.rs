use crate::elements::common::RenderContext;
use crate::error::StreamlitError;
use crate::proto::{WidgetState, back_msg::Type, *};
use crate::session::SessionLease;
use crate::{Streamlit, StreamlitApi, StreamlitServer};
use actix_ws::{MessageStream, Session};
use futures_util::StreamExt;
use prost::Message;

async fn do_rerun_script(session: &mut Session, lease: &SessionLease, server: &StreamlitServer, widget_states: Vec<WidgetState>, query_string: String, page_hash: String, history_navigation: bool) -> Result<(), StreamlitError> {
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
    let mut incoming_query_string = Some(query_string);
    // The page the browser addressed by hash; a server-started rerun keeps
    // the current page unless st.switch_page picked another one (measured
    // 1.66.1 wire: the addressed page's hash rides NewSession).
    let mut incoming_page = if page_hash.is_empty() { None } else { Some(page_hash) };
    loop {
        let started = std::time::Instant::now();
        // 1. 新请求应用前端输入；服务端内层重跑延续状态，不重复回调。
        let callbacks = if let Some(incoming) = incoming.take() {
            lease.state.begin_widgets(incoming)
        } else {
            lease.state.continue_widgets();
            Vec::new()
        };
        lease.state.reset_run_control();
        // 2. 服务端重跑取最近一次公布的 URL，静默默认值折叠不替换该快照。
        if let Some(query_string) = incoming_query_string.take() {
            let mut query = lease.state.query_params.lock();
            query.load(&query_string);
            query.history_navigation = history_navigation;
        } else {
            lease.state.query_params.lock().begin_internal_run();
        }
        lease.state.navigation.lock().incoming_page_hash = incoming_page.clone();
        let st = Streamlit::with_session_state(lease.state.clone());

        // 创建 channel 用于流式发送消息
        let (tx, mut rx) = tokio::sync::mpsc::unbounded_channel::<crate::proto::ForwardMsg>();

        // 创建 RenderContext 并设置到 App 中，让 App::push 时能立即发送消息
        let context = RenderContext::with_sender(lease.id.clone(), tx.clone());
        st.app.lock().set_render_context(context);

        // 发送初始化消息（new_session）。测量的 1.66.1 wire 从不为根容器
        // 发送 add_block：官方前端在 new_session 时隐式创建它，python 参照
        // 的全部已发布 trace 中没有任何 main_container 宣告。
        {
            let mut app = st.app.lock();
            if let Some(context) = app.render_context_mut() {
                let main_script_hash = crate::utils::hash::hash("");
                context.active_script_hash = main_script_hash.clone();
                context.push(crate::elements::app::create_new_session(context.session_id.clone(), incoming_page.clone().unwrap_or_else(|| main_script_hash.clone()), main_script_hash));
                context.push(crate::elements::app::create_session_status_changed(true, false));
                context.delta_path.push(0);
                context.delta_path.push(0);
            }
        }

        log::info!("Executing user main function...");

        let state = lease.state.clone();
        // 使用 tokio::select! 并发执行用户代码和消息发送
        let entry_future = async {
            if let Some(message) = state.widget_input_error() {
                st.exception(crate::ExceptionOptions::new("TypeError", message));
            } else {
                for callback in callbacks {
                    callback(&st);
                }
                server.entry.call(&st).await;
            }

            state.finish_widgets();
            crate::query_params::flush_query_update(&mut st.app.lock());
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
            let mut bytes_sent = 0;
            while let Some(msg) = rx.recv().await {
                // rerun 丢弃仍在队列中的旧轮 Delta；已发送帧与 URL 消息保留。
                if lease.state.run_control() == Some(crate::session::RunControl::Rerun) && matches!(msg.r#type, Some(forward_msg::Type::Delta(_))) {
                    continue;
                }

                let payload = msg.encode_to_vec();
                let bytes = payload.len();
                log::debug!("Sending ForwardMsg frame={} kind={:?} bytes={}", count, msg.r#type.as_ref().map(std::mem::discriminant), bytes);
                session.binary(payload).await?;
                count += 1;
                bytes_sent += bytes;
            }
            log::info!("WebSocket send completed frames={} bytes={}", count, bytes_sent);
            Ok::<_, StreamlitError>(())
        };

        // 并发执行
        let (_, send_result) = tokio::join!(entry_future, send_future);
        send_result?;
        log::info!("Script run completed session={} elapsed_ms={}", lease.id, started.elapsed().as_millis());

        if lease.state.run_control() != Some(crate::session::RunControl::Rerun) {
            break;
        }
        // st.switch_page retargets the server-started next run; a plain
        // st.rerun keeps the page the browser addressed.
        if let Some(target) = lease.state.navigation.lock().switch_target.take() {
            incoming_page = Some(target);

            // switch_page 已发送空查询串，下一页也必须读取相同状态。
            lease.state.query_params.lock().clear();
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
                // The official frontend reports the page context (url, locale,
                // timezone, theme, embedded flag) with every rerun; the
                // request_context() snapshot reads it per run. Native clients
                // that send none keep the fields unset, exactly as the frozen
                // reference shows.
                lease.state.set_context_info(client_state.context_info);
                let widget_states = client_state.widget_states.map(|ws| ws.widgets).unwrap_or_default();
                do_rerun_script(session, lease, server, widget_states, client_state.query_string, client_state.page_script_hash, client_state.is_history_navigation).await?;
            }
            Type::AppHeartbeat(_) => {
                let reply = ForwardMsg {
                    r#type: Some(forward_msg::Type::HeartbeatAck(true)),
                    ..Default::default()
                };
                session.binary(reply.encode_to_vec()).await?;
            }
            _ => {
                log::error!("Unknown back_msg kind={:?}", std::mem::discriminant(&tp));
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
    log::debug!("Starting WebSocket message processing loop");

    while let Some(msg_result) = msg_stream.next().await {
        if !lease.is_current() {
            session.close(None).await?;
            break;
        }
        message_count += 1;
        match msg_result {
            Ok(actix_ws::Message::Binary(data)) => {
                log::debug!("Received binary protobuf frame={} bytes={}", message_count, data.len());

                match BackMsg::decode(data) {
                    Ok(back_msg) => {
                        log::debug!("Decoded BackMsg kind={:?}", back_msg.r#type.as_ref().map(std::mem::discriminant));
                        handle_back_message(&mut session, &lease, back_msg, server).await?;
                    }
                    Err(e) => {
                        log::warn!("Failed to decode BackMsg: {}", e);
                    }
                }
            }
            Ok(actix_ws::Message::Text(text)) => {
                log::debug!("Received text frame={} bytes={}", message_count, text.len());
            }
            Ok(actix_ws::Message::Close(reason)) => {
                log::info!("WebSocket close received code={:?} frames={}", reason.as_ref().map(|reason| reason.code), message_count);
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
    log::info!("Connection stats: received frames={}", message_count);
    if message_count == 0 {
        log::warn!("⚠️  No messages received from frontend - this suggests protobuf message format issues");
    }
    Ok(())
}
