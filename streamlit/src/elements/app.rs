use crate::elements::common::{Element, RenderContext};
use crate::error::StreamlitError;
use crate::proto::widget_state::Value;
use crate::proto::{block, delta, forward_msg, Block, Config, Delta, EnvironmentInfo, ForwardMsg, ForwardMsgMetadata, Initialize, NewSession, SessionStatus, UserInfo, WidgetState};
use crate::utils::hash::hash;
use serde::{Deserialize, Serialize};
use std::cell::RefCell;
use std::collections::HashMap;
use std::sync::Arc;

pub(crate) struct App {
    elements: Vec<Arc<RefCell<dyn Element>>>,
    widget_states: HashMap<String, WidgetValue>,
    main_script: String,
    render_context: Option<RenderContext>,
}

impl App {
    pub fn new() -> Self {
        Self {
            elements: Default::default(),
            widget_states: Default::default(),
            main_script: Default::default(),
            render_context: None,
        }
    }

    pub fn set_render_context(&mut self, context: RenderContext) {
        self.render_context = Some(context);
    }

    pub fn render_context_mut(&mut self) -> Option<&mut RenderContext> {
        self.render_context.as_mut()
    }

    pub fn render_context(&self) -> Option<&RenderContext> {
        self.render_context.as_ref()
    }

    pub fn get_widget_state(&self, widget_id: &str) -> Option<WidgetValue> {
        self.widget_states.get(widget_id).cloned()
    }

    pub fn set_widget_state(&mut self, key: String, value: WidgetValue) {
        self.widget_states.insert(key.to_string(), value);
    }

    pub fn process_widget_states(&mut self, widget_states: Vec<WidgetState>) {
        log::info!("Processing {} widget states", widget_states.len());
        for widget_state in widget_states {
            if let Some(value) = widget_state.value {
                match value {
                    Value::TriggerValue(clicked) => {
                        log::info!("Button '{}' clicked: {}", widget_state.id, clicked);
                        self.set_widget_state(widget_state.id, WidgetValue::Boolean(clicked));
                    }
                    _ => {
                        log::info!("Received other widget type: {} - {:?}", widget_state.id, value);
                    }
                }
            }
        }
    }

    pub fn push(&mut self, element: Arc<RefCell<dyn Element>>) {
        // 如果设置了 render_context，立即 render 这个元素
        if let Some(ref mut context) = self.render_context {
            if let Err(e) = element.borrow().render(context) {
                log::error!("Failed to render element immediately: {}", e);
            }
        }

        // 仍然保存元素，用于后续的批量 render（兼容模式）
        self.elements.push(element);
    }
}

impl Element for App {
    fn render(&self, context: &mut RenderContext) -> Result<(), StreamlitError> {
        let main_script_hash = hash(self.main_script.as_str());
        context.active_script_hash = main_script_hash.clone();

        // 1. New Session
        context.push(create_new_session(context.session_id.clone(), main_script_hash));
        context.push(create_session_status_changed(true, false));

        // 2. Main Block
        context.delta_path.push(0);
        context.push(create_main_block());

        context.delta_path.push(0);
        for element in self.elements.iter() {
            element.borrow().render(context)?;
        }

        // 3. Finished
        context.push(create_script_finished());
        Ok(())
    }
}

pub(crate) fn create_new_session(session_id: String, main_script_hash: String) -> ForwardMsg {
    ForwardMsg {
        hash: "".to_string(),
        metadata: Some(ForwardMsgMetadata {
            cacheable: false,
            delta_path: vec![],
            element_dimension_spec: None,
            active_script_hash: main_script_hash.clone(),
        }),
        debug_last_backmsg_id: "".to_string(),
        r#type: Some(forward_msg::Type::NewSession(NewSession {
            initialize: Some(Initialize {
                user_info: Some(UserInfo {
                    installation_id: "".to_string(),
                    installation_id_v3: "".to_string(),
                    installation_id_v4: "".to_string(),
                }),
                environment_info: Some(EnvironmentInfo {
                    streamlit_version: "".to_string(),
                    python_version: "".to_string(),
                    server_os: "".to_string(),
                    has_display: false,
                }),
                session_status: Some(SessionStatus { run_on_save: false, script_is_running: false }),
                command_line: "".to_string(),
                session_id,
                is_hello: false,
            }),
            script_run_id: uuid::Uuid::new_v4().to_string(),
            name: "".to_string(),
            main_script_path: "".to_string(),
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
            page_script_hash: main_script_hash.clone(),
            fragment_ids_this_run: vec![],
            main_script_hash,
        })),
    }
}

pub(crate) fn create_session_status_changed(script_is_running: bool, run_on_save: bool) -> ForwardMsg {
    ForwardMsg {
        hash: "session_status_changed".to_string(),
        metadata: None,
        debug_last_backmsg_id: "".to_string(),
        r#type: Some(forward_msg::Type::SessionStatusChanged(SessionStatus { run_on_save, script_is_running })),
    }
}

pub(crate) fn create_main_block() -> ForwardMsg {
    ForwardMsg {
        hash: "main_block".to_string(),
        metadata: Some(ForwardMsgMetadata {
            cacheable: false,
            delta_path: vec![0],
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
                    height: 0,
                })),
                allow_empty: false,
                id: Some("main_container".to_string()), // This is the crucial ID!
                height_config: None,
                width_config: None,
            })),
        })),
    }
}

pub(crate) fn create_script_finished() -> ForwardMsg {
    ForwardMsg {
        hash: "script_finished".to_string(),
        metadata: None,
        debug_last_backmsg_id: "".to_string(),
        r#type: Some(forward_msg::Type::ScriptFinished(forward_msg::ScriptFinishedStatus::FinishedSuccessfully as i32)),
    }
}

/// Widget value types
#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum WidgetValue {
    String(String),
    Float(f64),
    Integer(i64),
    Boolean(bool),
}

impl From<String> for WidgetValue {
    fn from(s: String) -> Self {
        WidgetValue::String(s)
    }
}

impl From<f64> for WidgetValue {
    fn from(f: f64) -> Self {
        WidgetValue::Float(f)
    }
}

impl From<i64> for WidgetValue {
    fn from(i: i64) -> Self {
        WidgetValue::Integer(i)
    }
}

impl From<bool> for WidgetValue {
    fn from(b: bool) -> Self {
        WidgetValue::Boolean(b)
    }
}
