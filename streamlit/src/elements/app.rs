use crate::elements::common::{Element, RenderContext};
use crate::error::StreamlitError;
use crate::proto::{Block, Config, Delta, EnvironmentInfo, ForwardMsg, ForwardMsgMetadata, Initialize, NewSession, SessionStatus, UserInfo, block, delta, forward_msg};
use crate::utils::hash::hash;
use std::cell::RefCell;
use std::collections::HashSet;
use std::rc::Rc;

pub(crate) struct App {
    pub(crate) session_state: crate::SessionState,
    elements: Vec<Rc<RefCell<dyn Element>>>,
    form_keys: HashSet<String>,
    main_script: String,
    render_context: Option<RenderContext>,
}

impl App {
    pub fn new() -> Self {
        Self {
            session_state: Default::default(),
            elements: Default::default(),
            form_keys: HashSet::new(),
            main_script: Default::default(),
            render_context: None,
        }
    }

    /// Form keys have their own run-local namespace.
    pub(crate) fn claim_form_key(&mut self, key: &str) -> bool {
        self.form_keys.insert(key.to_owned())
    }

    pub(crate) fn release_form_key(&mut self, key: &str) {
        self.form_keys.remove(key);
    }

    pub fn set_render_context(&mut self, context: RenderContext) {
        self.render_context = Some(context);
    }

    pub fn render_context_mut(&mut self) -> Option<&mut RenderContext> {
        self.render_context.as_mut()
    }

    pub fn push(&mut self, element: Rc<RefCell<dyn Element>>) {
        // st.rerun()/st.stop() ended this run's output: later elements never
        // reach the wire, matching the measured upstream semantics.
        if self.session_state.run_control().is_some() {
            return;
        }
        // 如果设置了 render_context，立即 render 这个元素
        if let Some(ref mut context) = self.render_context
            && let Err(e) = element.borrow().render(context)
        {
            log::error!("Failed to render element immediately: {}", e);
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
        context.push(create_script_finished(forward_msg::ScriptFinishedStatus::FinishedSuccessfully));
        Ok(())
    }
}

pub(crate) fn create_new_session(session_id: String, main_script_hash: String) -> ForwardMsg {
    ForwardMsg {
        hash: "".to_string(),
        metadata: Some(ForwardMsgMetadata {
            cacheable: false,
            delta_path: vec![],
            active_script_hash: main_script_hash.clone(),
        }),
        r#type: Some(forward_msg::Type::NewSession(NewSession {
            initialize: Some(Initialize {
                user_info: Some(UserInfo {
                    installation_id: "".to_string(),
                    installation_id_v3: "".to_string(),
                    installation_id_v4: "".to_string(),
                }),
                environment_info: Some(EnvironmentInfo {
                    streamlit_version: "1.66.1".to_string(),
                    python_version: "".to_string(),
                    server_os: "".to_string(),
                    has_display: false,
                }),
                session_status: Some(SessionStatus { run_on_save: false, script_is_running: false }),
                recommend_skills_install: false,
                skills_nudge_suppressed_reason: String::new(),
                session_id,
                is_hello: false,
            }),
            script_run_id: uuid::Uuid::new_v4().to_string(),
            name: "Streamlit Rust".to_string(),
            main_script_path: "".to_string(),
            config: Some(Config {
                gather_usage_stats: false,
                max_cached_message_age: 0,
                show_error_links: crate::proto::config::ShowErrorLinks::False as i32,
                disable_data_export: false,
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
        r#type: Some(forward_msg::Type::SessionStatusChanged(SessionStatus { run_on_save, script_is_running })),
    }
}

pub(crate) fn create_main_block() -> ForwardMsg {
    ForwardMsg {
        hash: "main_block".to_string(),
        metadata: Some(ForwardMsgMetadata {
            cacheable: false,
            delta_path: vec![0],
            active_script_hash: String::new(),
        }),
        r#type: Some(forward_msg::Type::Delta(Delta {
            fragment_id: String::new(),
            r#type: Option::from(delta::Type::AddBlock(Block {
                autoscroll: None,
                r#type: Some(block::Type::Vertical(block::Vertical { border: false })),
                allow_empty: false,
                id: Some("main_container".to_string()), // This is the crucial ID!
                height_config: None,
                width_config: None,
            })),
        })),
    }
}

pub(crate) fn create_script_finished(status: forward_msg::ScriptFinishedStatus) -> ForwardMsg {
    ForwardMsg {
        hash: "script_finished".to_string(),
        metadata: None,
        r#type: Some(forward_msg::Type::ScriptFinished(status as i32)),
    }
}
