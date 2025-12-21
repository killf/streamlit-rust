use crate::api::{get_app, StreamlitElement};
use crate::proto::{back_msg::Type, Button as StreamlitButton, WidgetState, widget_state::Value, *};
use crate::Streamlit;
use actix_ws::{ProtocolError, Session};
use futures_util::StreamExt;
use prost::Message;

// Factory for creating ForwardMsg instances with cleaner separation of concerns
struct ForwardMsgFactory;

impl ForwardMsgFactory {
    /// Creates the base metadata for delta messages
    fn delta_metadata(element_index: u32) -> ForwardMsgMetadata {
        ForwardMsgMetadata {
            cacheable: false,
            delta_path: vec![0, element_index], // [main_container_index, element_index]
            element_dimension_spec: None,
            active_script_hash: "".to_string(),
        }
    }

    /// Creates the base ForwardMsg structure for delta messages
    fn delta_base(element_index: u32, _id: &str, element_hash: &str) -> ForwardMsg {
        let hash = format!("delta_0_{}_{}", element_index, element_hash);

        ForwardMsg {
            hash,
            metadata: Some(Self::delta_metadata(element_index)),
            debug_last_backmsg_id: "".to_string(),
            r#type: None, // Will be set by specific element methods
        }
    }

    /// Creates a text element ForwardMsg
    fn text_element(element_index: u32, id: &str, body: &str, help: &str) -> ForwardMsg {
        let element_hash = format!("text_{}_{}", id, body);
        let mut msg = Self::delta_base(element_index, id, &element_hash);

        msg.r#type = Some(forward_msg::Type::Delta(Delta {
            fragment_id: id.to_string(),
            r#type: Some(delta::Type::NewElement(Element {
                height_config: None,
                width_config: None,
                text_alignment_config: None,
                r#type: Some(element::Type::Text(Text {
                    body: body.to_string(),
                    help: help.to_string(),
                })),
            })),
        }));

        msg
    }

    /// Creates a title (h1) element ForwardMsg
    fn title_element(element_index: u32, id: &str, title: &str) -> ForwardMsg {
        let element_hash = format!("title_{}_{}", id, title);
        let mut msg = Self::delta_base(element_index, id, &element_hash);

        msg.r#type = Some(forward_msg::Type::Delta(Delta {
            fragment_id: id.to_string(),
            r#type: Some(delta::Type::NewElement(Element {
                height_config: None,
                width_config: None,
                text_alignment_config: None,
                r#type: Some(element::Type::Heading(Heading {
                    tag: "h1".to_string(),
                    anchor: "".to_string(),
                    body: title.to_string(),
                    help: "".to_string(),
                    hide_anchor: false,
                    divider: "".to_string(),
                })),
            })),
        }));

        msg
    }

    /// Creates a header element ForwardMsg
    fn header_element(element_index: u32, id: &str, body: &str, level: i32) -> ForwardMsg {
        let level_clamped = if level < 1 { 1 } else if level > 6 { 6 } else { level };
        let tag = format!("h{}", level_clamped);
        let element_hash = format!("header_{}_{}_{}", id, tag, body);
        let mut msg = Self::delta_base(element_index, id, &element_hash);

        msg.r#type = Some(forward_msg::Type::Delta(Delta {
            fragment_id: id.to_string(),
            r#type: Some(delta::Type::NewElement(Element {
                height_config: None,
                width_config: None,
                text_alignment_config: None,
                r#type: Some(element::Type::Heading(Heading {
                    tag,
                    anchor: "".to_string(),
                    body: body.to_string(),
                    help: "".to_string(),
                    hide_anchor: false,
                    divider: "".to_string(),
                })),
            })),
        }));

        msg
    }

    /// Creates a markdown element ForwardMsg
    fn markdown_element(element_index: u32, id: &str, body: &str) -> ForwardMsg {
        let element_hash = format!("markdown_{}_{}", id, body.chars().take(20).collect::<String>());
        let mut msg = Self::delta_base(element_index, id, &element_hash);

        msg.r#type = Some(forward_msg::Type::Delta(Delta {
            fragment_id: id.to_string(),
            r#type: Some(delta::Type::NewElement(Element {
                height_config: None,
                width_config: None,
                text_alignment_config: None,
                r#type: Some(element::Type::Markdown(Markdown {
                    body: body.to_string(),
                    allow_html: false,
                    is_caption: false,
                    element_type: 0,
                    help: "".to_string(),
                })),
            })),
        }));

        msg
    }

    /// Creates a code element ForwardMsg
    fn code_element(element_index: u32, id: &str, body: &str, language: &Option<String>) -> ForwardMsg {
        let element_hash = format!("code_{}_{}", id, body.chars().take(20).collect::<String>());
        let mut msg = Self::delta_base(element_index, id, &element_hash);

        msg.r#type = Some(forward_msg::Type::Delta(Delta {
            fragment_id: id.to_string(),
            r#type: Some(delta::Type::NewElement(Element {
                height_config: None,
                width_config: None,
                text_alignment_config: None,
                r#type: Some(element::Type::Code(Code {
                    code_text: body.to_string(),
                    language: language.clone().unwrap_or_else(|| "".to_string()),
                    show_line_numbers: false,
                    wrap_lines: true,
                    #[allow(deprecated)]
                    height: 0,
                })),
            })),
        }));

        msg
    }

    /// Creates an empty element ForwardMsg (used for dividers and empty elements)
    fn empty_element(element_index: u32, id: &str, element_type: &str) -> ForwardMsg {
        let element_hash = format!("{}_{}", element_type, id);
        let mut msg = Self::delta_base(element_index, id, &element_hash);

        msg.r#type = Some(forward_msg::Type::Delta(Delta {
            fragment_id: id.to_string(),
            r#type: Some(delta::Type::NewElement(Element {
                height_config: None,
                width_config: None,
                text_alignment_config: None,
                r#type: Some(element::Type::Empty(Empty {})),
            })),
        }));

        msg
    }

    /// Creates a button element ForwardMsg
    fn button_element(element_index: u32, id: &str, label: &str, key: &str) -> ForwardMsg {
        let element_hash = format!("button_{}_{}", key, label);
        let mut msg = Self::delta_base(element_index, id, &element_hash);

        let button = StreamlitButton {
            id: key.to_string(),
            label: label.to_string(),
            default: false,
            help: String::default(),
            form_id: String::default(),
            is_form_submitter: false,
            r#type: "secondary".to_string(),
            disabled: false,
            #[allow(deprecated)]
            use_container_width: false,
            icon: String::default(),
            shortcut: String::default(),
            icon_position: 0, // LEFT
        };

        msg.r#type = Some(forward_msg::Type::Delta(Delta {
            fragment_id: id.to_string(),
            r#type: Some(delta::Type::NewElement(Element {
                height_config: None,
                width_config: None,
                text_alignment_config: None,
                r#type: Some(element::Type::Button(button)),
            })),
        }));

        msg
    }

    /// Creates a container element ForwardMsg
    fn container_element(element_index: u32, id: &str, children: &[crate::api::StreamlitElement]) -> ForwardMsg {
        let element_hash = format!("container_{}_{}", id, children.len());
        let mut msg = Self::delta_base(element_index, id, &element_hash);

        msg.r#type = Some(forward_msg::Type::Delta(Delta {
            fragment_id: id.to_string(),
            r#type: Some(delta::Type::AddBlock(
                Block {
                    r#type: Some(block::Type::Vertical(
                        block::Vertical {
                            border: false,
                            #[allow(deprecated)]
                            height: 0,
                        }
                    )),
                    allow_empty: true,
                    id: Some(id.to_string()),
                    height_config: None,
                    width_config: None,
                }
            )),
        }));

        msg
    }

    /// Creates a columns element ForwardMsg
    fn columns_element(element_index: u32, id: &str, columns: &[crate::api::StreamlitElement], column_count: usize) -> ForwardMsg {
        let element_hash = format!("columns_{}_{}_cols", id, column_count);
        let mut msg = Self::delta_base(element_index, id, &element_hash);

        // Create horizontal columns layout
        msg.r#type = Some(forward_msg::Type::Delta(Delta {
            fragment_id: id.to_string(),
            r#type: Some(delta::Type::AddBlock(
                Block {
                    r#type: Some(block::Type::Horizontal(
                        block::Horizontal {
                            gap: "small".to_string(),
                        }
                    )),
                    allow_empty: true,
                    id: Some(id.to_string()),
                    height_config: None,
                    width_config: None,
                }
            )),
        }));

        msg
    }
}

fn new_session(session_id: &str, script_run_id: &str) -> ForwardMsg {
    let hash = format!("new_session_{}", session_id);

    ForwardMsg {
        hash: hash.clone(),
        metadata: Some(ForwardMsgMetadata {
            cacheable: false,
            delta_path: vec![],
            element_dimension_spec: None,
            active_script_hash: "".to_string(),
        }),
        debug_last_backmsg_id: "".to_string(),
        r#type: Some(forward_msg::Type::NewSession(
            NewSession {
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
                    session_status: Some(SessionStatus {
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
            },
        )),
    }
}

fn new_script_finished_message() -> ForwardMsg {
    ForwardMsg {
        hash: "script_finished".to_string(),
        metadata: None,
        debug_last_backmsg_id: "".to_string(),
        r#type: Some(forward_msg::Type::ScriptFinished(
            forward_msg::ScriptFinishedStatus::FinishedSuccessfully as i32,
        )),
    }
}

fn new_main_block_delta() -> ForwardMsg {
    ForwardMsg {
        hash: "main_block".to_string(),
        metadata: Some(ForwardMsgMetadata {
            cacheable: false,
            delta_path: vec![0], // RootContainer.MAIN = 0
            element_dimension_spec: None,
            active_script_hash: "".to_string(),
        }),
        debug_last_backmsg_id: "".to_string(),
        r#type: Some(forward_msg::Type::Delta(
            Delta {
                fragment_id: "".to_string(),
                r#type: Option::from(delta::Type::AddBlock(
                    Block {
                        r#type: Some(block::Type::Vertical(
                            block::Vertical {
                                border: false,
                                #[allow(deprecated)]
                                height: 0, // deprecated field, required
                            }
                        )),
                        allow_empty: false,
                        id: Some("main_container".to_string()), // This is the crucial ID!
                        height_config: None,
                        width_config: None,
                    }
                )),
            },
        )),
    }
}

fn new_delta_with_parent(element_index: u32, element: &StreamlitElement) -> ForwardMsg {
    // Use factory methods to create the appropriate ForwardMsg based on element type
    match element {
        StreamlitElement::Text { id, body, help } => {
            ForwardMsgFactory::text_element(element_index, id, body, help)
        }
        StreamlitElement::Title { id, title } => {
            ForwardMsgFactory::title_element(element_index, id, title)
        }
        StreamlitElement::Header { id, body, level } => {
            ForwardMsgFactory::header_element(element_index, id, body, *level)
        }
        StreamlitElement::Markdown { id, body } => {
            ForwardMsgFactory::markdown_element(element_index, id, body)
        }
        StreamlitElement::Code { id, body, language } => {
            ForwardMsgFactory::code_element(element_index, id, body, language)
        }
        StreamlitElement::Divider { id } => {
            ForwardMsgFactory::empty_element(element_index, id, "divider")
        }
        StreamlitElement::Empty { id } => {
            ForwardMsgFactory::empty_element(element_index, id, "empty")
        }
        StreamlitElement::Button { id, label, key, clicked: _ } => {
            ForwardMsgFactory::button_element(element_index, id, label, key)
        }
        StreamlitElement::Container { id, children, key: _ } => {
            ForwardMsgFactory::container_element(element_index, id, children)
        }
        StreamlitElement::Columns { id, columns, column_count, key: _ } => {
            ForwardMsgFactory::columns_element(element_index, id, columns, *column_count)
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

/// Recursively send elements and their children
async fn send_elements_recursive(
    session: &mut Session,
    elements: Vec<StreamlitElement>,
    base_path: &[u32],
) -> Result<(), Box<dyn std::error::Error>> {
    for (index, element) in elements.iter().enumerate() {
        let mut element_path = base_path.to_vec();
        element_path.push(index as u32);

        match element {
            StreamlitElement::Container { id, children, key: _ } => {
                // Send the container block first
                let container_msg = new_delta_with_parent(index as u32, element);
                let encoded = container_msg.encode_to_vec();
                log::info!("Sending container {} protobuf message: {} bytes", id, encoded.len());
                session.binary(encoded).await?;

                // Recursively send container children with nested path
                if !children.is_empty() {
                    let child_path = element_path;
                    Box::pin(send_elements_recursive(session, children.clone(), &child_path)).await?;
                }
            }
            StreamlitElement::Columns { id, columns, column_count: _, key: _ } => {
                // Send the columns block first
                let columns_msg = new_delta_with_parent(index as u32, element);
                let encoded = columns_msg.encode_to_vec();
                log::info!("Sending columns {} protobuf message: {} bytes", id, encoded.len());
                session.binary(encoded).await?;

                // Recursively send column contents with nested path
                for (col_idx, column) in columns.iter().enumerate() {
                    let mut col_path = element_path.clone();
                    col_path.push(col_idx as u32);

                    match column {
                        StreamlitElement::Container { id: container_id, children, key: _ } => {
                            // Send column container
                            let container_msg = ForwardMsgFactory::container_element(col_idx as u32, container_id, children);
                            let encoded = container_msg.encode_to_vec();
                            log::info!("Sending column {} container {} protobuf message: {} bytes", col_idx, container_id, encoded.len());
                            session.binary(encoded).await?;

                            // Send container children
                            if !children.is_empty() {
                                let child_path = col_path;
                                Box::pin(send_elements_recursive(session, children.clone(), &child_path)).await?;
                            }
                        }
                        _ => {
                            // Send regular column element
                            let element_msg = new_delta_with_parent(col_idx as u32, column);
                            let encoded = element_msg.encode_to_vec();
                            log::info!("Sending column {} element protobuf message: {} bytes", col_idx, encoded.len());
                            session.binary(encoded).await?;
                        }
                    }
                }
            }
            _ => {
                // Send regular element
                let element_msg = new_delta_with_parent(index as u32, element);
                let encoded = element_msg.encode_to_vec();
                log::info!("Sending element protobuf message: {} bytes", encoded.len());
                session.binary(encoded).await?;
            }
        }
    }
    Ok(())
}

async fn send_elements(
    session: &mut Session,
    elements: Vec<StreamlitElement>,
) -> Result<(), Box<dyn std::error::Error>> {
    log::info!("Sending {} elements as protobuf", elements.len());

    // First, create a main block container (RootContainer.MAIN = 0)
    let main_block_msg = new_main_block_delta();
    let block_encoded = main_block_msg.encode_to_vec();
    log::info!("Sending main block protobuf message: {} bytes", block_encoded.len());
    session.binary(block_encoded).await?;

    // Then send all elements as children of the main block (delta_path: [0, element_index])
    send_elements_recursive(session, elements, &[0]).await?;

    Ok(())
}

async fn handle_rerun_script(
    session: &mut Session,
    session_id: &str,
    entry: fn(&Streamlit),
    widget_states: Option<Vec<WidgetState>>,
) -> Result<(), Box<dyn std::error::Error>> {
    let app = get_app();

    // Clear previous elements and increment run count
    app.clear_elements();
    app.increment_run_count();

    // Process widget states (button clicks, etc.)
    if let Some(states) = widget_states {
        log::info!("Processing {} widget states", states.len());
        for widget_state in states {
            if let Some(value) = widget_state.value {
                match value {
                    Value::TriggerValue(clicked) => {
                        // This is a button click
                        log::info!(
                            "Button '{}' clicked: {}",
                            widget_state.id,
                            clicked
                        );
                        app.set_widget_state(&widget_state.id, crate::api::WidgetValue::Boolean(clicked));
                    }
                    _ => {
                        log::info!("Received other widget type: {}", widget_state.id);
                    }
                }
            }
        }
    }

    // Execute the user's main function
    entry(app);

    log::info!(
        "Executed user main function, got {} elements",
        app.get_elements().len()
    );

    // Send all elements as deltas
    send_elements(session, app.get_elements()).await?;

    // Send script_finished message (this is crucial!)
    let script_finished_msg = new_script_finished_message();
    let encoded = script_finished_msg.encode_to_vec();
    log::info!("Sending script_finished message: {} bytes", encoded.len());
    session.binary(encoded).await?;

    log::info!("Rerun script completed for session: {}", session_id);
    Ok(())
}

async fn handle_back_message(
    session: &mut Session,
    session_id: &str,
    back_msg: BackMsg,
    entry: fn(&Streamlit),
) -> Result<(), Box<dyn std::error::Error>> {
    if let Some(tp) = back_msg.r#type {
        match tp {
            Type::RerunScript(client_state) => {
                log::info!("Handling rerun script request");
                let widget_states = client_state
                    .widget_states
                    .map(|ws| ws.widgets);
                handle_rerun_script(session, session_id, entry, widget_states).await?;
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
    handle_rerun_script(&mut session, &session_id, entry, None).await?;
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

                match BackMsg::decode(data) {
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
