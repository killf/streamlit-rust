use crate::api::{get_app, StreamlitElement};
use crate::proto::back_msg;
use crate::proto::back_msg::Type;
use crate::Streamlit;
use actix_ws::{ProtocolError, Session};
use futures_util::StreamExt;
use prost::Message;

#[derive(Debug, Clone)]
pub struct ForwardMsg {
    // Hash field (optional)
    pub hash: Option<String>,
    // Metadata field (optional)
    pub metadata: Option<ForwardMsgMetadata>,
    // Message type as oneof
    pub msg_type: ForwardMsgType,
}

#[derive(Debug, Clone)]
pub enum ForwardMsgType {
    NewSession(NewSession),
    SessionStateChanged(SessionState),
    Delta(Delta),
    ScriptFinished(ScriptFinishedStatus),
    // Add more types as needed
}

#[derive(Debug, Clone)]
pub struct ForwardMsgMetadata {
    pub cacheable: bool,
    pub delta_path: Vec<u32>,
    pub active_script_hash: Option<String>,
}

#[derive(Debug, Clone)]
pub struct NewSession {
    pub script_run_id: String,
    pub name: String,
    pub main_script_path: String,
    pub session_id: String,
    pub is_hello: bool,
}

#[derive(Debug, Clone)]
pub struct Initialize {
    pub user_info: UserInfo,
    pub environment_info: EnvironmentInfo,
    pub session_status: SessionStatus,
    pub session_id: String,
    pub is_hello: bool,
}

#[derive(Debug, Clone)]
pub struct UserInfo {
    pub installation_id: String,
    pub installation_id_v3: String,
    pub installation_id_v4: String,
}

#[derive(Debug, Clone)]
pub struct EnvironmentInfo {
    pub streamlit_version: String,
    pub python_version: String,
    pub server_os: String,
    pub has_display: bool,
}

#[derive(Debug, Clone)]
pub struct SessionStatus {
    pub run_on_save: bool,
    pub script_is_running: bool,
}

#[derive(Debug, Clone)]
pub struct SessionState {
    pub run_on_save: bool,
    pub script_is_running: bool,
}

#[derive(Debug, Clone)]
pub struct Delta {
    pub element: DeltaElement,
}

#[derive(Debug, Clone)]
pub enum DeltaElement {
    Text { id: String, body: String },
    Markdown { id: String, body: String },
    // Add more element types
}

#[derive(Debug, Clone)]
pub enum ScriptFinishedStatus {
    FinishedSuccessfully,
    FinishedWithCompileError,
    FinishedEarlyForRerun,
    FinishedFragmentRunSuccessfully,
}

impl ForwardMsg {
    fn new_session_state_changed(script_is_running: bool) -> Self {
        // Generate hash for session_state_changed message
        let hash = format!(
            "session_state_{}_{}",
            script_is_running,
            uuid::Uuid::new_v4()
        );

        Self {
            hash: Some(hash),
            metadata: Some(ForwardMsgMetadata {
                cacheable: false,
                delta_path: vec![],
                active_script_hash: None,
            }),
            msg_type: ForwardMsgType::SessionStateChanged(SessionState {
                run_on_save: false,
                script_is_running,
            }),
        }
    }

    fn new_script_finished() -> Self {
        // Generate hash for script_finished message
        let hash = format!("script_finished_{}", uuid::Uuid::new_v4());

        Self {
            hash: Some(hash),
            metadata: Some(ForwardMsgMetadata {
                cacheable: false,
                delta_path: vec![],
                active_script_hash: None,
            }),
            msg_type: ForwardMsgType::ScriptFinished(ScriptFinishedStatus::FinishedSuccessfully),
        }
    }

    fn new_delta(delta_path_index: u32, element: DeltaElement) -> Self {
        // Generate hash based on element content
        let element_hash = match &element {
            DeltaElement::Text { id, body } => format!("text_{}_{}", id, body),
            DeltaElement::Markdown { id, body } => format!("markdown_{}_{}", id, body),
        };
        let hash = format!("delta_{}_{}", delta_path_index, element_hash);

        Self {
            hash: Some(hash),
            metadata: Some(ForwardMsgMetadata {
                cacheable: true,
                delta_path: vec![0, delta_path_index], // [0, index] for main container
                active_script_hash: None,
            }),
            msg_type: ForwardMsgType::Delta(Delta { element }),
        }
    }

    // Manual protobuf encoding for ForwardMsg
    fn encode(&self) -> Vec<u8> {
        let mut buf = Vec::new();

        // Encode hash (field 1)
        if let Some(ref hash) = self.hash {
            encode_string_field(1, hash, &mut buf);
        }

        // Encode metadata (field 2)
        if let Some(ref metadata) = self.metadata {
            encode_bytes_field(2, metadata.encode(), &mut buf);
        }

        // Encode message type (oneof fields - use official field numbers!)
        match &self.msg_type {
            ForwardMsgType::NewSession(new_session) => {
                encode_bytes_field(4, new_session.encode(), &mut buf); // field 4
            }
            ForwardMsgType::Delta(delta) => {
                encode_bytes_field(5, delta.encode(), &mut buf); // field 5 ✓
            }
            ForwardMsgType::ScriptFinished(status) => {
                // ScriptFinished is an enum, so use varint encoding
                let status_value = match status {
                    ScriptFinishedStatus::FinishedSuccessfully => 0,
                    ScriptFinishedStatus::FinishedWithCompileError => 1,
                    ScriptFinishedStatus::FinishedEarlyForRerun => 2,
                    ScriptFinishedStatus::FinishedFragmentRunSuccessfully => 3,
                };
                encode_varint_field(6, status_value, &mut buf); // field 6 ✓
            }
            ForwardMsgType::SessionStateChanged(session_state) => {
                encode_bytes_field(9, session_state.encode(), &mut buf); // field 9 ✓
            }
        }

        buf
    }
}

impl ForwardMsgMetadata {
    fn encode(&self) -> Vec<u8> {
        let mut buf = Vec::new();
        encode_varint_field(1, self.cacheable as u64, &mut buf);
        if !self.delta_path.is_empty() {
            encode_uint32_repeated_field(2, &self.delta_path, &mut buf);
        }
        if let Some(ref hash) = self.active_script_hash {
            encode_string_field(4, hash, &mut buf);
        }
        buf
    }
}

impl NewSession {
    fn encode(&self) -> Vec<u8> {
        let mut buf = Vec::new();

        // field 1: Initialize (nested message)
        let mut initialize_buf = Vec::new();

        // Initialize.field 1: UserInfo
        let mut user_info_buf = Vec::new();
        encode_string_field(1, "rust-installation-id-v4", &mut user_info_buf);
        encode_string_field(5, "rust-installation-v3", &mut user_info_buf);
        encode_string_field(6, "rust-installation-v4", &mut user_info_buf);
        encode_bytes_field(1, user_info_buf, &mut initialize_buf);

        // Initialize.field 3: EnvironmentInfo
        let mut env_info_buf = Vec::new();
        encode_string_field(1, "1.28.0", &mut env_info_buf); // streamlit_version
        encode_string_field(2, "3.9.0", &mut env_info_buf); // python_version
        encode_string_field(3, "windows", &mut env_info_buf); // server_os
        encode_bool_field(4, false, &mut env_info_buf); // has_display
        encode_bytes_field(3, env_info_buf, &mut initialize_buf);

        // Initialize.field 4: SessionStatus
        let mut session_status_buf = Vec::new();
        encode_bool_field(1, false, &mut session_status_buf); // run_on_save
        encode_bool_field(2, false, &mut session_status_buf); // script_is_running
        encode_bytes_field(4, session_status_buf, &mut initialize_buf);

        // Initialize.field 6: session_id
        encode_string_field(6, &self.session_id, &mut initialize_buf);

        // Initialize.field 7: is_hello
        encode_bool_field(7, self.is_hello, &mut initialize_buf);

        encode_bytes_field(1, initialize_buf, &mut buf);

        // field 2: script_run_id
        encode_string_field(2, &self.script_run_id, &mut buf);

        // field 3: name
        encode_string_field(3, &self.name, &mut buf);

        // field 4: main_script_path
        encode_string_field(4, &self.main_script_path, &mut buf);

        // field 6: Config (empty config for now)
        let mut config_buf = Vec::new();
        encode_bool_field(2, false, &mut config_buf); // gather_usage_stats
        encode_int32_field(3, 100, &mut config_buf); // max_cached_message_age
        encode_bool_field(5, true, &mut config_buf); // allow_run_on_save
        encode_bool_field(6, false, &mut config_buf); // hide_top_bar
        encode_bool_field(7, false, &mut config_buf); // hide_sidebar_nav
        encode_varint_field(8, 0, &mut config_buf); // toolbar_mode AUTO
        encode_bytes_field(6, config_buf, &mut buf);

        // field 7: CustomThemeConfig (empty theme for now)
        let mut theme_buf = Vec::new();
        encode_varint_field(6, 0, &mut theme_buf); // BaseTheme LIGHT
        encode_bytes_field(7, theme_buf, &mut buf);

        // field 8: app_pages - Add at least one page (the main page)
        let mut app_page_buf = Vec::new();
        encode_string_field(1, "main_page_hash", &mut app_page_buf); // page_script_hash
        encode_string_field(2, &self.name, &mut app_page_buf); // page_name
        encode_string_field(3, "", &mut app_page_buf); // icon (empty)
        encode_bool_field(4, true, &mut app_page_buf); // is_default
        encode_string_field(5, "", &mut app_page_buf); // section_header (empty)
        encode_string_field(6, "/", &mut app_page_buf); // url_pathname
        encode_bytes_field(8, app_page_buf, &mut buf); // Add as repeated field

        // field 9: page_script_hash
        encode_string_field(9, "main_page_hash", &mut buf);

        buf
    }
}

impl SessionState {
    fn encode(&self) -> Vec<u8> {
        let mut buf = Vec::new();
        encode_bool_field(1, self.run_on_save, &mut buf);
        encode_bool_field(2, self.script_is_running, &mut buf);
        buf
    }
}

impl Delta {
    fn encode(&self) -> Vec<u8> {
        let mut buf = Vec::new();

        // Create proper Element message for Delta
        match &self.element {
            DeltaElement::Text { id: _, body } => {
                // Create a Text element first
                let mut text_buf = Vec::new();
                encode_string_field(1, body, &mut text_buf); // Text.body

                // Create Element with Text as oneof type
                let mut element_buf = Vec::new();
                encode_bytes_field(1, text_buf, &mut element_buf); // Element.text (field 1)

                // Delta with new_element (Official field number: 3)
                encode_bytes_field(3, element_buf, &mut buf); // Delta.new_element = 3 ✓
            }
            DeltaElement::Markdown { id: _, body } => {
                // Create a Markdown element first
                let mut markdown_buf = Vec::new();
                encode_string_field(1, body, &mut markdown_buf); // Markdown.body

                // Create Element with Markdown as oneof type
                let mut element_buf = Vec::new();
                encode_bytes_field(2, markdown_buf, &mut element_buf); // Element.markdown (field 2)

                // Delta with new_element (Official field number: 3)
                encode_bytes_field(3, element_buf, &mut buf); // Delta.new_element = 3 ✓
            }
        }

        buf
    }
}

// Helper functions for protobuf encoding
fn encode_string_field(field_number: u32, value: &str, buf: &mut Vec<u8>) {
    let key = (field_number as u64) << 3 | 2; // wire type 2 (length-delimited)
    encode_varint(key, buf);
    encode_varint(value.len() as u64, buf);
    buf.extend_from_slice(value.as_bytes());
}

fn encode_bytes_field(field_number: u32, value: Vec<u8>, buf: &mut Vec<u8>) {
    let key = (field_number as u64) << 3 | 2; // wire type 2 (length-delimited)
    encode_varint(key, buf);
    encode_varint(value.len() as u64, buf);
    buf.extend_from_slice(&value);
}

fn encode_varint_field(field_number: u32, value: u64, buf: &mut Vec<u8>) {
    let key = (field_number as u64) << 3 | 0; // wire type 0 (varint)
    encode_varint(key, buf);
    encode_varint(value, buf);
}

fn encode_uint32_repeated_field(field_number: u32, values: &[u32], buf: &mut Vec<u8>) {
    for value in values {
        encode_varint_field(field_number, *value as u64, buf);
    }
}

fn encode_varint(mut value: u64, buf: &mut Vec<u8>) {
    while value >= 0x80 {
        buf.push((value | 0x80) as u8);
        value >>= 7;
    }
    buf.push(value as u8);
}

fn encode_bool_field(field_number: u32, value: bool, buf: &mut Vec<u8>) {
    encode_varint_field(field_number, if value { 1 } else { 0 }, buf);
}

fn encode_int32_field(field_number: u32, value: i32, buf: &mut Vec<u8>) {
    let key = (field_number as u64) << 3 | 0; // wire type 0 (varint)
    encode_varint(key, buf);
    encode_varint(value as u64, buf);
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

    // Wait a moment before sending initial message
    tokio::time::sleep(tokio::time::Duration::from_millis(50)).await;

    // Send the complete official message sequence: new_session → session_state_changed
    log::info!("Sending complete message sequence starting with new_session...");
    send_new_session_protobuf(&mut session, &session_id).await?;
    log::info!("Initial new_session protobuf message sent successfully");

    // Short delay before session_state_changed (mimicking official behavior)
    tokio::time::sleep(tokio::time::Duration::from_millis(10)).await;

    // Send initial session_state_changed message (script not running)
    log::info!("Sending initial session_state_changed protobuf message...");
    send_session_state_changed(&mut session, false).await?;
    log::info!("Initial session_state_changed protobuf message sent successfully");

    // Wait a moment then automatically execute the script once (to simulate frontend request)
    tokio::time::sleep(tokio::time::Duration::from_millis(100)).await;
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

                // Try to decode as Streamlit BackMsg
                // match decode_back_msg(&data) {
                //     Ok(back_msg) => {
                //         log::info!("Successfully decoded BackMsg: {:?}", back_msg);
                //         handle_back_message(&mut session, &session_id, back_msg, entry).await?;
                //     }
                //     Err(e) => {
                //         log::warn!("Failed to decode BackMsg: {}", e);
                //         log::info!("Raw message bytes: {:?}", &data[..data.len().min(50)]);
                //         // Try to see if it's just text data
                //         if let Ok(text) = String::from_utf8(data.to_vec()) {
                //             log::info!("Binary data as text: {}", text);
                //         }
                //     }
                // }
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
            _ => {
                log::error!("Unknown message type");
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

// Define BackMsg structure (simplified version based on frontend code)
#[derive(Debug, Clone)]
pub enum BackMsg {
    ClearCache,
    RerunScript,
    StopScript,
    DebugDisconnectWebsocket,
    Unknown,
}

// Define message types that might be expected
#[derive(Debug, Clone)]
pub struct SessionReport {
    pub session_id: String,
    pub run_count: u32,
}

#[derive(Debug, Clone)]
pub struct SessionInfo {
    pub session_id: String,
    pub run_count: u32,
}

async fn handle_back_message(
    session: &mut Session,
    session_id: &str,
    back_msg: crate::proto::BackMsg,
    entry: fn(&Streamlit),
) -> Result<(), Box<dyn std::error::Error>> {
    if let Some(tp) = back_msg.r#type {
        match tp {
            Type::RerunScript(state) => {
                log::info!("Handling rerun script request");
                handle_rerun_script(session, session_id, entry).await?;
            }
            _ => {}
        }
    }
    Ok(())
}

async fn send_new_session_protobuf(
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

async fn send_script_finished_protobuf(
    session: &mut Session,
) -> Result<(), Box<dyn std::error::Error>> {
    // Create protobuf-compatible ScriptFinished message
    let forward_msg = ForwardMsg::new_script_finished();
    let encoded = forward_msg.encode();

    log::info!(
        "Sending script_finished protobuf message: {} bytes",
        encoded.len()
    );
    session.binary(encoded).await?;
    Ok(())
}

async fn send_session_state_changed(
    session: &mut Session,
    script_is_running: bool,
) -> Result<(), Box<dyn std::error::Error>> {
    let forward_msg = ForwardMsg::new_session_state_changed(script_is_running);
    let encoded = forward_msg.encode();

    log::info!(
        "Sending session_state_changed (script_is_running: {}) protobuf message: {} bytes",
        script_is_running,
        encoded.len()
    );
    session.binary(encoded).await?;
    Ok(())
}

async fn handle_rerun_script(
    session: &mut Session,
    session_id: &str,
    entry: fn(&Streamlit),
) -> Result<(), Box<dyn std::error::Error>> {
    let app = get_app();

    // Send session_state_changed: script is starting
    log::info!("Sending session_state_changed (script_is_running: true)...");
    send_session_state_changed(session, true).await?;

    // Clear previous elements and increment run count
    app.clear_elements();
    app.increment_run_count();

    // Execute the user's main function
    entry(app);

    log::info!(
        "Executed user main function, got {} elements",
        app.get_elements().len()
    );

    // Send script_finished message
    send_script_finished_protobuf(session).await?;

    // Send all elements as deltas
    send_elements_as_protobuf(session, app.get_elements()).await?;

    // Send session_state_changed: script finished
    log::info!("Sending session_state_changed (script_is_running: false)...");
    send_session_state_changed(session, false).await?;

    log::info!("Rerun script completed for session: {}", session_id);
    Ok(())
}

async fn send_elements_as_protobuf(
    session: &mut Session,
    elements: Vec<StreamlitElement>,
) -> Result<(), Box<dyn std::error::Error>> {
    log::info!("Sending {} elements as protobuf", elements.len());

    for (index, element) in elements.iter().enumerate() {
        let delta_element = match element {
            StreamlitElement::Text { id, body, .. } => DeltaElement::Text {
                id: id.clone(),
                body: body.clone(),
            },
            StreamlitElement::Title { id, body } => DeltaElement::Text {
                id: id.clone(),
                body: format!("# {}", body),
            },
            StreamlitElement::Header { id, body } => DeltaElement::Text {
                id: id.clone(),
                body: format!("## {}", body),
            },
            StreamlitElement::Markdown { id, body, .. } => DeltaElement::Markdown {
                id: id.clone(),
                body: body.clone(),
            },
            _ => {
                // For other elements, convert to text for now
                DeltaElement::Text {
                    id: format!("element_{}", index),
                    body: format!("{:?}", element),
                }
            }
        };

        let forward_msg = ForwardMsg::new_delta(index as u32, delta_element);
        let encoded = forward_msg.encode();

        log::info!(
            "Sending element {} protobuf message: {} bytes",
            index,
            encoded.len()
        );
        session.binary(encoded).await?;
    }

    Ok(())
}

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
                initialize: None,
                script_run_id: script_run_id.to_string(),
                name: "hello.py".to_string(),
                main_script_path: "hello.py".to_string(),
                config: None,
                custom_theme: None,
                app_pages: vec![],
                page_script_hash: hash.clone(),
                fragment_ids_this_run: vec![],
                main_script_hash: hash,
            },
        )),
    }
}
