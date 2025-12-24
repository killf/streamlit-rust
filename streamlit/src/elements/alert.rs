use crate::elements::common::{Element, RenderContext};
use crate::error::StreamlitError;
use crate::proto::{alert, delta, delta_base_with_path, element, forward_msg, Alert, Delta};
use crate::utils::hash::hash;
use std::fmt;

/// Alert format enum
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum AlertFormat {
    Error,
    Warning,
    Info,
    Success,
}

impl AlertFormat {
    fn as_alert_format(&self) -> i32 {
        match self {
            AlertFormat::Error => alert::Format::Error as i32,
            AlertFormat::Warning => alert::Format::Warning as i32,
            AlertFormat::Info => alert::Format::Info as i32,
            AlertFormat::Success => alert::Format::Success as i32,
        }
    }
}

pub struct AlertElement {
    body: String,
    format: AlertFormat,
    icon: String,
}

impl AlertElement {
    pub fn new(body: String, format: AlertFormat) -> Self {
        Self {
            body,
            format,
            icon: String::new(),
        }
    }

    pub fn body(&self) -> &str {
        &self.body
    }

    pub fn format(&self) -> AlertFormat {
        self.format
    }

    pub fn icon(&self) -> &str {
        &self.icon
    }

    pub fn set_icon(&mut self, icon: String) {
        self.icon = icon;
    }
}

impl Element for AlertElement {
    fn render(&self, context: &mut RenderContext) -> Result<(), StreamlitError> {
        let element_hash = hash(format!("alert_{}_{}_{}", self.format.as_alert_format(), self.icon, self.body).as_str());
        let mut msg = delta_base_with_path(context.delta_path.clone(), context.active_script_hash.clone(), element_hash);

        msg.r#type = Some(forward_msg::Type::Delta(Delta {
            fragment_id: String::new(),
            r#type: Some(delta::Type::NewElement(crate::proto::Element {
                height_config: None,
                width_config: None,
                text_alignment_config: None,
                r#type: Some(element::Type::Alert(Alert {
                    body: self.body.clone(),
                    format: self.format.as_alert_format(),
                    icon: self.icon.clone(),
                    width_config: None,
                })),
            })),
        }));

        context.push(msg);

        if let Some(index) = context.delta_path.pop() {
            context.delta_path.push(index + 1);
        }

        Ok(())
    }
}

pub struct Error {
    element: std::sync::Arc<std::cell::RefCell<AlertElement>>,
}

impl Error {
    pub(crate) fn new(element: std::sync::Arc<std::cell::RefCell<AlertElement>>) -> Self {
        Self { element }
    }
}

impl fmt::Display for Error {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "Error: {}", self.element.borrow().body())
    }
}

pub struct Warning {
    element: std::sync::Arc<std::cell::RefCell<AlertElement>>,
}

impl Warning {
    pub(crate) fn new(element: std::sync::Arc<std::cell::RefCell<AlertElement>>) -> Self {
        Self { element }
    }
}

impl fmt::Display for Warning {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "Warning: {}", self.element.borrow().body())
    }
}

pub struct Info {
    element: std::sync::Arc<std::cell::RefCell<AlertElement>>,
}

impl Info {
    pub(crate) fn new(element: std::sync::Arc<std::cell::RefCell<AlertElement>>) -> Self {
        Self { element }
    }
}

impl fmt::Display for Info {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "Info: {}", self.element.borrow().body())
    }
}

pub struct Success {
    element: std::sync::Arc<std::cell::RefCell<AlertElement>>,
}

impl Success {
    pub(crate) fn new(element: std::sync::Arc<std::cell::RefCell<AlertElement>>) -> Self {
        Self { element }
    }
}

impl fmt::Display for Success {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "Success: {}", self.element.borrow().body())
    }
}
