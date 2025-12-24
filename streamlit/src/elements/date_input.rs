#![allow(dead_code)]

use crate::elements::common::{Element, RenderContext};
use crate::error::StreamlitError;
use crate::proto::{delta, delta_base_with_path, element, forward_msg, DateInput as ProtoDateInput, Delta};
use crate::utils::hash::hash;

pub(crate) struct DateInputElement {
    id: String,
    key: String,
    label: String,
    default_value: Vec<String>,
    min: Option<String>,
    max: Option<String>,
    is_range: bool,
    help: Option<String>,
    disabled: bool,
    format: Option<String>,
}

impl DateInputElement {
    pub fn new(label: String, default_value: Vec<String>, key: Option<String>) -> Self {
        let input_key = key.unwrap_or_else(|| label.clone());
        let id = format!("date_input_{}", input_key);

        Self {
            id,
            key: input_key,
            label,
            default_value,
            min: None,
            max: None,
            is_range: false,
            help: None,
            disabled: false,
            format: None,
        }
    }

    pub fn min(&mut self, min: String) {
        self.min = Some(min);
    }

    pub fn max(&mut self, max: String) {
        self.max = Some(max);
    }

    pub fn is_range(&mut self, is_range: bool) {
        self.is_range = is_range;
    }

    pub fn help(&mut self, help: String) {
        self.help = Some(help);
    }

    pub fn disabled(&mut self, disabled: bool) {
        self.disabled = disabled;
    }

    pub fn format(&mut self, format: String) {
        self.format = Some(format);
    }

    pub fn get_key(&self) -> &str {
        &self.key
    }
}

impl Element for DateInputElement {
    fn render(&self, context: &mut RenderContext) -> Result<(), StreamlitError> {
        let element_hash = hash(format!("date_input_{}_{}", self.key, self.default_value.join(",")).as_str());
        let mut msg = delta_base_with_path(context.delta_path.clone(), context.active_script_hash.clone(), element_hash);

        msg.r#type = Some(forward_msg::Type::Delta(Delta {
            fragment_id: String::new(),
            r#type: Some(delta::Type::NewElement(crate::proto::Element {
                height_config: None,
                width_config: None,
                text_alignment_config: None,
                r#type: Some(element::Type::DateInput(ProtoDateInput {
                    id: self.id.clone(),
                    label: self.label.clone(),
                    default: self.default_value.clone(),
                    min: self.min.clone().unwrap_or_default(),
                    max: self.max.clone().unwrap_or_default(),
                    is_range: self.is_range,
                    help: self.help.clone().unwrap_or_default(),
                    form_id: String::new(),
                    value: vec![],
                    set_value: false,
                    disabled: self.disabled,
                    label_visibility: None,
                    format: self.format.clone().unwrap_or_default(),
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

pub struct DateInput {
    value: Vec<String>,
}

impl DateInput {
    pub(crate) fn new(value: Vec<String>) -> Self {
        Self { value }
    }

    /// Get the selected date value(s)
    pub fn value(&self) -> &[String] {
        &self.value
    }

    /// Get the first date value
    pub fn first(&self) -> Option<&str> {
        self.value.first().map(|s| s.as_str())
    }
}
