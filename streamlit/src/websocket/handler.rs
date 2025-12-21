use crate::api::{get_app, StreamlitElement};
use crate::proto::back_msg::Type;
use crate::Streamlit;
use actix_ws::{ProtocolError, Session};
use futures_util::StreamExt;
use prost::Message;

fn new_session(session_id: &str, script_run_id: &str) -> crate::proto::ForwardMsg {
    let hash = format!("new_session_{}", session_id);

    crate::proto::ForwardMsg {
        hash: hash.clone(),
        metadata: Some(crate::proto::ForwardMsgMetadata {
            cacheable: false,
            delta_path: vec![],
            element_dimension_spec: None,
            active_script_hash: "".to_string(),
        }),
        debug_last_backmsg_id: "".to_string(),
        r#type: Some(crate::proto::forward_msg::Type::NewSession(
            crate::proto::NewSession {
                initialize: Some(crate::proto::Initialize {
                    user_info: Some(crate::proto::UserInfo {
                        installation_id: "1".to_string(),
                        installation_id_v3: "1".to_string(),
                        installation_id_v4: "1".to_string(),
                    }),
                    environment_info: Some(crate::proto::EnvironmentInfo {
                        streamlit_version: "".to_string(),
                        python_version: "".to_string(),
                        server_os: "".to_string(),
                        has_display: false,
                    }),
                    session_status: Some(crate::proto::SessionStatus {
                        run_on_save: false,
                        script_is_running: false,
                    }),
                    command_line: "".to_string(),
                    session_id: session_id.to_string(),
                    is_hello: false,
                }),
                script_run_id: script_run_id.to_string(),
                name: "hello.py".to_string(),
                main_script_path: "hello.py".to_string(),
                config: Some(crate::proto::Config {
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
            },
        )),
    }
}

fn new_delta(delta_path_index: u32, element: &StreamlitElement) -> crate::proto::ForwardMsg {
    match element {
        StreamlitElement::Text { id, body, help } => {
            let element_hash = format!("text_{}_{}", id, body);
            let hash = format!("delta_{}_{}", delta_path_index, element_hash);
            crate::proto::ForwardMsg {
                hash,
                metadata: Some(crate::proto::ForwardMsgMetadata {
                    cacheable: false,
                    delta_path: vec![delta_path_index],
                    element_dimension_spec: None,
                    active_script_hash: "".to_string(),
                }),
                debug_last_backmsg_id: "".to_string(),
                r#type: Some(crate::proto::forward_msg::Type::Delta(
                    crate::proto::Delta {
                        fragment_id: id.to_string(),
                        r#type: Option::from(crate::proto::delta::Type::NewElement(
                            crate::proto::Element {
                                height_config: None,
                                width_config: None,
                                text_alignment_config: None,
                                r#type: Some(crate::proto::element::Type::Text(
                                    crate::proto::Text {
                                        body: body.to_string(),
                                        help: help.to_string(),
                                    },
                                )),
                            },
                        )),
                    },
                )),
            }
        }
    }
}

async fn send_new_session(
    session: &mut Session,
    session_id: &str,
) -> Result<(), Box<dyn std::error::Error>> {
    // Generate script run ID
    let script_run_id = uuid::Uuid::new_v4().to_string();

    let forward_msg = new_session(session_id, &script_run_id);
    let encoded = forward_msg.encode_to_vec();

    log::info!("Sending new_session: {:?} ", forward_msg);
    session.binary(encoded).await?;
    Ok(())
}

async fn send_elements(
    session: &mut Session,
    elements: Vec<StreamlitElement>,
) -> Result<(), Box<dyn std::error::Error>> {
    log::info!("Sending {} elements as protobuf", elements.len());

    for (index, element) in elements.iter().enumerate() {
        let forward_msg = new_delta(index as u32, element);
        let encoded = forward_msg.encode_to_vec();

        log::info!(
            "Sending element {} protobuf message: {} bytes",
            index,
            encoded.len()
        );
        session.binary(encoded).await?;
    }

    Ok(())
}

async fn handle_rerun_script(
    session: &mut Session,
    session_id: &str,
    entry: fn(&Streamlit),
) -> Result<(), Box<dyn std::error::Error>> {
    let app = get_app();

    // Clear previous elements and increment run count
    app.clear_elements();
    app.increment_run_count();

    // Execute the user's main function
    entry(app);

    log::info!(
        "Executed user main function, got {} elements",
        app.get_elements().len()
    );

    // Send all elements as deltas
    send_elements(session, app.get_elements()).await?;

    log::info!("Rerun script completed for session: {}", session_id);
    Ok(())
}

async fn handle_back_message(
    session: &mut Session,
    session_id: &str,
    back_msg: crate::proto::BackMsg,
    entry: fn(&Streamlit),
) -> Result<(), Box<dyn std::error::Error>> {
    if let Some(tp) = back_msg.r#type {
        match tp {
            Type::RerunScript(_state) => {
                log::info!("Handling rerun script request");
                handle_rerun_script(session, session_id, entry).await?;
            }
            _ => {}
        }
    }
    Ok(())
}

pub async fn handle_connection(
    mut session: Session,
    mut msg_stream: impl futures_util::Stream<Item = Result<actix_ws::Message, ProtocolError>> + Unpin,
    entry: fn(&Streamlit),
) -> Result<(), Box<dyn std::error::Error>> {
    log::info!("=== Streamlit WebSocket handler started ===");

    // Generate session ID
    let session_id = uuid::Uuid::new_v4().to_string();
    log::info!("Generated session ID: {}", session_id);

    // Send the complete official message sequence: new_session → session_state_changed
    log::info!("Sending complete message sequence starting with new_session...");
    send_new_session(&mut session, &session_id).await?;
    log::info!("Initial new_session protobuf message sent successfully");

    // Wait a moment then automatically execute the script once (to simulate frontend request)
    log::info!("Auto-triggering initial script execution...");
    handle_rerun_script(&mut session, &session_id, entry).await?;
    log::info!("Initial script execution completed");

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

                match crate::proto::BackMsg::decode(data) {
                    Ok(back_msg) => {
                        log::info!("Successfully decoded BackMsg: {:?}", back_msg);
                        handle_back_message(&mut session, &session_id, back_msg, entry).await?;
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
    log::info!(
        "📈 Connection stats: processed {} messages from frontend",
        message_count
    );
    if message_count == 0 {
        log::warn!(
            "⚠️  No messages received from frontend - this suggests protobuf message format issues"
        );
    }
    Ok(())
}
