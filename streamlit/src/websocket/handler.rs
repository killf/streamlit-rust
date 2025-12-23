use crate::api::StreamlitElement;
use crate::elements::common::{Element, RenderContext};
use crate::proto::{back_msg::Type, widget_state::Value, WidgetState, *};
use crate::{Streamlit, StreamlitServer};
use actix_ws::{MessageStream, Session};
use futures_util::StreamExt;
use prost::Message;

async fn send_new_session(session: &mut Session, session_id: &str) -> Result<(), Box<dyn std::error::Error>> {
    // Generate script run ID
    let script_run_id = uuid::Uuid::new_v4().to_string();
    // let forward_msg = new_session(session_id, &script_run_id);

    let hash = format!("new_session_{}", session_id);

    let forward_msg = ForwardMsg {
        hash: hash.clone(),
        metadata: Some(ForwardMsgMetadata {
            cacheable: false,
            delta_path: vec![],
            element_dimension_spec: None,
            active_script_hash: "".to_string(),
        }),
        debug_last_backmsg_id: "".to_string(),
        r#type: Some(forward_msg::Type::NewSession(NewSession {
            initialize: Some(Initialize {
                user_info: Some(UserInfo {
                    installation_id: "1".to_string(),
                    installation_id_v3: "1".to_string(),
                    installation_id_v4: "1".to_string(),
                }),
                environment_info: Some(EnvironmentInfo {
                    streamlit_version: "".to_string(),
                    python_version: "".to_string(),
                    server_os: "".to_string(),
                    has_display: false,
                }),
                session_status: Some(SessionStatus { run_on_save: false, script_is_running: false }),
                command_line: "".to_string(),
                session_id: session_id.to_string(),
                is_hello: false,
            }),
            script_run_id: script_run_id.to_string(),
            name: "hello.py".to_string(),
            main_script_path: "hello.py".to_string(),
            config: Some(Config {
                gather_usage_stats: false,
                max_cached_message_age: 0,
                mapbox_token: "".to_string(),
                allow_run_on_save: false,
                hide_top_bar: false,
                hide_sidebar_nav: false,
                toolbar_mode: 0,
            }),
            custom_theme: None,
            app_pages: vec![],
            page_script_hash: hash.clone(),
            fragment_ids_this_run: vec![],
            main_script_hash: hash,
        })),
    };

    log::info!("Sending: {:?} ", forward_msg);
    session.binary(forward_msg.encode_to_vec()).await?;
    Ok(())
}

async fn send_session_status_changed(session: &mut Session, script_is_running: bool, run_on_save: bool) -> Result<(), Box<dyn std::error::Error>> {
    let forward_msg = ForwardMsg {
        hash: "session_status_changed".to_string(),
        metadata: None,
        debug_last_backmsg_id: "".to_string(),
        r#type: Some(forward_msg::Type::SessionStatusChanged(SessionStatus { run_on_save, script_is_running })),
    };

    log::info!("Sending: {:?} ", forward_msg);
    session.binary(forward_msg.encode_to_vec()).await?;
    Ok(())
}

async fn send_script_finished(session: &mut Session) -> Result<(), Box<dyn std::error::Error>> {
    let forward_msg = ForwardMsg {
        hash: "script_finished".to_string(),
        metadata: None,
        debug_last_backmsg_id: "".to_string(),
        r#type: Some(forward_msg::Type::ScriptFinished(forward_msg::ScriptFinishedStatus::FinishedSuccessfully as i32)),
    };

    log::info!("Sending: {:?} ", forward_msg);
    session.binary(forward_msg.encode_to_vec()).await?;
    Ok(())
}

async fn do_rerun_script(session: &mut Session, session_id: &str, server: &StreamlitServer, widget_states: Option<Vec<WidgetState>>) -> Result<(), Box<dyn std::error::Error>> {
    // Send the complete official message sequence: new_session → session_state_changed → delta → ... → page_profile → script_finished → session_status_changed
    log::info!("Sending complete message sequence starting with new_session...");
    send_new_session(session, &session_id).await?;
    send_session_status_changed(session, true, false).await?;

    let st = Streamlit::new().process_widget_states(widget_states);

    log::info!("Executing user main function...");
    (server.entry)(&st);
    log::info!("Executed user main function, got {} elements", st.get_elements().len());

    let mut context = RenderContext::new();
    st.render(&mut context)?;

    // Send all elements as deltas
    for msg in context.stream.iter() {
        log::info!("ForwardMsg {:?}", msg);
        session.binary(msg.encode_to_vec()).await?;
    }

    // Send script_finished message (this is crucial!)
    send_script_finished(session).await?;

    log::info!("Rerun script completed for session: {}", session_id);
    Ok(())
}

async fn handle_back_message(session: &mut Session, session_id: &str, back_msg: BackMsg, server: &StreamlitServer) -> Result<(), Box<dyn std::error::Error>> {
    if let Some(tp) = back_msg.r#type {
        match tp {
            Type::RerunScript(client_state) => {
                log::info!("Handling rerun script request");
                let widget_states = client_state.widget_states.map(|ws| ws.widgets);
                do_rerun_script(session, session_id, server, widget_states).await?;
            }
            _ => {
                log::error!("Unknown back_msg type: {:?}", tp);
            }
        }
    }
    Ok(())
}

pub async fn handle_connection(mut session: Session, mut msg_stream: MessageStream, server: &StreamlitServer) -> Result<(), Box<dyn std::error::Error>> {
    log::info!("=== Streamlit WebSocket handler started ===");

    // Generate session ID
    let session_id = uuid::Uuid::new_v4().to_string();
    log::info!("Generated session ID: {}", session_id);

    // Handle incoming messages with proper processing
    let mut message_count = 0;
    log::info!("Complete message sequence sent, starting message processing loop...");

    while let Some(msg_result) = msg_stream.next().await {
        message_count += 1;
        log::info!("🔍 Processing message #{}", message_count);
        log::debug!("Message result: {:?}", msg_result);

        match msg_result {
            Ok(actix_ws::Message::Binary(data)) => {
                log::info!("Received binary protobuf message: {} bytes", data.len());

                match BackMsg::decode(data) {
                    Ok(back_msg) => {
                        log::info!("Successfully decoded BackMsg: {:?}", back_msg);
                        handle_back_message(&mut session, &session_id, back_msg, server).await?;
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
