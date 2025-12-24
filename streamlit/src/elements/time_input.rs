#![allow(dead_code)]

use crate::elements::common::{Element, RenderContext};
use crate::error::StreamlitError;
use crate::proto::{delta, delta_base_with_path, element, forward_msg, TimeInput as ProtoTimeInput, Delta};
use crate::utils::hash::hash;

pub(crate) struct TimeInputElement {
    id: String,
    key: String,
    label: String,
    default_value: Option<String>,
    help: Option<String>,
    disabled: bool,
    step: i64,
}

impl TimeInputElement {
    pub fn new(label: String, default_value: Option<String>, key: Option<String>) -> Self {
        let input_key = key.unwrap_or_else(|| label.clone());
        let id = format!("time_input_{}", input_key);

        Self {
            id,
            key: input_key,
            label,
            default_value,
            help: None,
            disabled: false,
            step: 60, // Default step: 60 seconds
        }
    }

    pub fn help(&mut self, help: String) {
        self.help = Some(help);
    }

    pub fn disabled(&mut self, disabled: bool) {
        self.disabled = disabled;
    }

    pub fn step(&mut self, step: i64) {
        self.step = step;
    }

    pub fn get_key(&self) -> &str {
        &self.key
    }
}

impl Element for TimeInputElement {
    fn render(&self, context: &mut RenderContext) -> Result<(), StreamlitError> {
        let element_hash = hash(format!("time_input_{}_{}", self.key, self.default_value.as_ref().map(|s| s.as_str()).unwrap_or("")).as_str());
        let mut msg = delta_base_with_path(context.delta_path.clone(), context.active_script_hash.clone(), element_hash);

        msg.r#type = Some(forward_msg::Type::Delta(Delta {
            fragment_id: String::new(),
            r#type: Some(delta::Type::NewElement(crate::proto::Element {
                height_config: None,
                width_config: None,
                text_alignment_config: None,
                r#type: Some(element::Type::TimeInput(ProtoTimeInput {
                    id: self.id.clone(),
                    label: self.label.clone(),
                    default: self.default_value.clone(),
                    help: self.help.clone().unwrap_or_default(),
                    form_id: String::new(),
                    value: None,
                    set_value: false,
                    disabled: self.disabled,
                    label_visibility: None,
                    step: self.step,
                    ..Default::default()
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

pub struct TimeInput {
    value: Option<String>,
}

impl TimeInput {
    pub(crate) fn new(value: Option<String>) -> Self {
        Self { value }
    }

    /// Get the selected time value
    pub fn value(&self) -> Option<&str> {
        self.value.as_deref()
    }
}
