use crate::elements::common::{Element, ElementWidth, RenderContext};
use crate::error::StreamlitError;
use crate::proto::{Delta, Element as WireElement, Exception, delta, delta_base_with_path, forward_msg};

/// The framework-rendered exception element, mirroring the measured 1.66.1 wire
/// (reference: tests/reference/reference-browser/widgets/dup_key). Upstream
/// raises `StreamlitDuplicateElementKey`, the framework renders this element
/// and the run ends there, still finishing `FINISHED_SUCCESSFULLY`.
pub(crate) struct ExceptionElement {
    kind: String,
    key: String,
}

impl ExceptionElement {
    pub(crate) fn duplicate_key(kind: &str, key: &str) -> Self {
        Self { kind: kind.to_owned(), key: key.to_owned() }
    }

    fn wire(&self) -> WireElement {
        WireElement {
            r#type: Some(crate::proto::element::Type::Exception(Exception {
                r#type: "streamlit.errors.StreamlitDuplicateElementKey".to_owned(),
                message: format!(
                    "There are multiple elements with the same `key='{}'`. To fix this, please make sure that the `key` argument is unique for each element you create.",
                    self.key
                ),
                message_is_markdown: true,
                // Upstream shows the app source line of the raise; Rust cannot
                // know the caller's source, so this line states the real
                // context instead of fabricating a Python-looking path.
                stack_trace: vec![format!("streamlit-rust: the {} widget registered the duplicate key='{}'", self.kind, self.key)],
                is_streamlit_exception: true,
                width_config: Some(ElementWidth::Stretch.into()),
                ..Default::default()
            })),
            ..Default::default()
        }
    }
}

impl Element for ExceptionElement {
    fn render(&self, context: &mut RenderContext) -> Result<(), StreamlitError> {
        let element = self.wire();
        let mut message = delta_base_with_path(context.delta_path.clone(), context.active_script_hash.clone(), crate::utils::hash::hash(&format!("{element:?}")));
        message.r#type = Some(forward_msg::Type::Delta(Delta {
            fragment_id: String::new(),
            r#type: Some(delta::Type::NewElement(element)),
        }));
        context.push(message);
        if let Some(index) = context.delta_path.last_mut() {
            *index += 1;
        }
        Ok(())
    }
}

/// The application exception element `st.exception` renders (the measured
/// 1.66.1 shape: the bare type name, the message, the caller-supplied trace
/// lines, the stretch width, no streamlit-error flag).
pub(crate) struct AppException {
    kind: String,
    message: String,
    stack_trace: Vec<String>,
}

impl AppException {
    pub(crate) fn new(kind: String, message: String, stack_trace: Vec<String>) -> Self {
        Self { kind, message, stack_trace }
    }
}

impl Element for AppException {
    fn render(&self, context: &mut RenderContext) -> Result<(), StreamlitError> {
        let element = WireElement {
            r#type: Some(crate::proto::element::Type::Exception(Exception {
                r#type: self.kind.clone(),
                message: self.message.clone(),
                stack_trace: self.stack_trace.clone(),
                width_config: Some(ElementWidth::Stretch.into()),
                ..Default::default()
            })),
            ..Default::default()
        };
        let mut message = delta_base_with_path(context.delta_path.clone(), context.active_script_hash.clone(), crate::utils::hash::hash(&format!("{element:?}")));
        message.r#type = Some(forward_msg::Type::Delta(Delta {
            fragment_id: String::new(),
            r#type: Some(delta::Type::NewElement(element)),
        }));
        context.push(message);
        if let Some(index) = context.delta_path.last_mut() {
            *index += 1;
        }
        Ok(())
    }
}
