use crate::api::StreamlitElement;
use crate::proto::{Button as StreamlitButton, *};

pub(crate) struct ForwardMsgFactory;

impl ForwardMsgFactory {
    pub fn hash(txt: &str) -> String {
        let md5 = md5::compute(txt.as_bytes());
        format!("{:x}", md5)
    }

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

    pub(crate) fn delta_base_with_path(delta_path: Vec<u32>, active_script_hash: String, hash: String) -> ForwardMsg {
        ForwardMsg {
            hash,
            metadata: Some(ForwardMsgMetadata {
                cacheable: false,
                delta_path,
                element_dimension_spec: None,
                active_script_hash,
            }),
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
                r#type: Some(element::Type::Text(Text { body: body.to_string(), help: help.to_string() })),
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
        let level_clamped = if level < 1 {
            1
        } else if level > 6 {
            6
        } else {
            level
        };
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
    pub(crate) fn markdown_element(delta_path: Vec<u32>, active_script_hash: String, id: &str, body: String) -> ForwardMsg {
        let element_hash = Self::hash(format!("markdown_{}", body).as_str());
        let mut msg = Self::delta_base_with_path(delta_path, active_script_hash, element_hash);

        msg.r#type = Some(forward_msg::Type::Delta(Delta {
            fragment_id: id.to_string(),
            r#type: Some(delta::Type::NewElement(Element {
                height_config: None,
                width_config: None,
                text_alignment_config: None,
                r#type: Some(element::Type::Markdown(Markdown {
                    body,
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

    // /// Creates a container element ForwardMsg
    // fn container_element(element_index: u32, id: &str, children: &[crate::api::StreamlitElement]) -> ForwardMsg {
    //     let element_hash = format!("container_{}_{}", id, children.len());
    //     let mut msg = Self::delta_base(element_index, id, &element_hash);
    //
    //     msg.r#type = Some(forward_msg::Type::Delta(Delta {
    //         fragment_id: id.to_string(),
    //         r#type: Some(delta::Type::AddBlock(Block {
    //             r#type: Some(block::Type::Vertical(block::Vertical {
    //                 border: false,
    //                 #[allow(deprecated)]
    //                 height: 0,
    //             })),
    //             allow_empty: true,
    //             id: Some(id.to_string()),
    //             height_config: None,
    //             width_config: None,
    //         })),
    //     }));
    //
    //     msg
    // }

    // /// Creates a columns element ForwardMsg
    // fn columns_element(element_index: u32, id: &str, columns: &[crate::api::StreamlitElement], column_count: usize) -> ForwardMsg {
    //     let element_hash = format!("columns_{}_{}_cols", id, column_count);
    //     let mut msg = Self::delta_base(element_index, id, &element_hash);
    //
    //     // Create horizontal columns layout
    //     msg.r#type = Some(forward_msg::Type::Delta(Delta {
    //         fragment_id: id.to_string(),
    //         r#type: Some(delta::Type::AddBlock(Block {
    //             r#type: Some(block::Type::Horizontal(block::Horizontal { gap: "small".to_string() })),
    //             allow_empty: true,
    //             id: Some(id.to_string()),
    //             height_config: None,
    //             width_config: None,
    //         })),
    //     }));
    //
    //     msg
    // }
}

pub fn new_session(session_id: &str, script_run_id: &str) -> ForwardMsg {
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
    }
}

pub fn new_session_status_changed(script_is_running: bool, run_on_save: bool) -> ForwardMsg {
    ForwardMsg {
        hash: "session_status_changed".to_string(),
        metadata: None,
        debug_last_backmsg_id: "".to_string(),
        r#type: Some(forward_msg::Type::SessionStatusChanged(SessionStatus { run_on_save, script_is_running })),
    }
}

pub fn new_script_finished_message() -> ForwardMsg {
    ForwardMsg {
        hash: "script_finished".to_string(),
        metadata: None,
        debug_last_backmsg_id: "".to_string(),
        r#type: Some(forward_msg::Type::ScriptFinished(forward_msg::ScriptFinishedStatus::FinishedSuccessfully as i32)),
    }
}

pub fn new_main_block_delta() -> ForwardMsg {
    ForwardMsg {
        hash: "main_block".to_string(),
        metadata: Some(ForwardMsgMetadata {
            cacheable: false,
            delta_path: vec![0], // RootContainer.MAIN = 0
            element_dimension_spec: None,
            active_script_hash: String::new(),
        }),
        debug_last_backmsg_id: String::new(),
        r#type: Some(forward_msg::Type::Delta(Delta {
            fragment_id: String::new(),
            r#type: Option::from(delta::Type::AddBlock(Block {
                r#type: Some(block::Type::Vertical(block::Vertical {
                    border: false,
                    #[allow(deprecated)]
                    height: 0, // deprecated field, required
                })),
                allow_empty: false,
                id: Some("main_container".to_string()), // This is the crucial ID!
                height_config: None,
                width_config: None,
            })),
        })),
    }
}

pub fn new_delta_with_parent(element_index: u32, element: &StreamlitElement) -> ForwardMsg {
    match element {
        StreamlitElement::Text { id, body, help } => ForwardMsgFactory::text_element(element_index, id, body, help),
        StreamlitElement::Title { id, title } => ForwardMsgFactory::title_element(element_index, id, title),
        StreamlitElement::Header { id, body, level } => ForwardMsgFactory::header_element(element_index, id, body, *level),
        StreamlitElement::Markdown { id, body } => todo!(),
        StreamlitElement::Code { id, body, language } => ForwardMsgFactory::code_element(element_index, id, body, language),
        StreamlitElement::Divider { id } => ForwardMsgFactory::empty_element(element_index, id, "divider"),
        StreamlitElement::Empty { id } => ForwardMsgFactory::empty_element(element_index, id, "empty"),
        StreamlitElement::Button { id, label, key, clicked: _ } => ForwardMsgFactory::button_element(element_index, id, label, key),
    }
}
