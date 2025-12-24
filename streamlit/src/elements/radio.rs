#![allow(dead_code)]

use crate::elements::common::{Element, RenderContext};
use crate::error::StreamlitError;
use crate::proto::{delta, delta_base_with_path, element, forward_msg, Radio as ProtoRadio, Delta};
use crate::utils::hash::hash;

pub(crate) struct RadioElement {
    id: String,
    key: String,
    label: String,
    options: Vec<String>,
    index: usize,
    help: Option<String>,
    disabled: bool,
    horizontal: bool,
}

impl RadioElement {
    pub fn new(label: String, options: Vec<String>, default_index: usize, key: Option<String>) -> Self {
        let radio_key = key.unwrap_or_else(|| label.clone());
        let id = format!("radio_{}", radio_key);

        // Ensure default_index is within bounds
        let index = if default_index >= options.len() {
            0
        } else {
            default_index
        };

        Self {
            id,
            key: radio_key,
            label,
            options,
            index,
            help: None,
            disabled: false,
            horizontal: false,
        }
    }

    pub fn set_index(&mut self, index: usize) {
        self.index = index.min(self.options.len().saturating_sub(1));
    }

    pub fn get_index(&self) -> usize {
        self.index
    }

    pub fn get_value(&self) -> String {
        self.options.get(self.index).cloned().unwrap_or_default()
    }

    pub fn get_key(&self) -> &str {
        &self.key
    }

    pub fn help(&mut self, help: String) {
        self.help = Some(help);
    }

    pub fn disabled(&mut self, disabled: bool) {
        self.disabled = disabled;
    }

    pub fn horizontal(&mut self, horizontal: bool) {
        self.horizontal = horizontal;
    }
}

impl Element for RadioElement {
    fn render(&self, context: &mut RenderContext) -> Result<(), StreamlitError> {
        let element_hash = hash(format!("radio_{}_{}", self.key, self.index).as_str());
        let mut msg = delta_base_with_path(context.delta_path.clone(), context.active_script_hash.clone(), element_hash);

        msg.r#type = Some(forward_msg::Type::Delta(Delta {
            fragment_id: String::new(),
            r#type: Some(delta::Type::NewElement(crate::proto::Element {
                height_config: None,
                width_config: None,
                text_alignment_config: None,
                r#type: Some(element::Type::Radio(ProtoRadio {
                    id: self.id.clone(),
                    label: self.label.clone(),
                    default: Some(self.index as i32),
                    options: self.options.clone(),
                    help: self.help.clone().unwrap_or_default(),
                    form_id: String::new(),
                    value: Some(self.index as i32),
                    set_value: true,
                    disabled: self.disabled,
                    horizontal: self.horizontal,
                    label_visibility: None,
                    captions: vec![],
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
