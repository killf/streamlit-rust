#![allow(dead_code)]

use crate::elements::common::{Element, RenderContext};
use crate::error::StreamlitError;
use crate::proto::{delta, delta_base_with_path, element, forward_msg, Selectbox as ProtoSelectbox, Delta};
use crate::utils::hash::hash;

pub(crate) struct SelectboxElement {
    id: String,
    key: String,
    label: String,
    options: Vec<String>,
    index: usize,
    help: Option<String>,
    disabled: bool,
    placeholder: Option<String>,
}

impl SelectboxElement {
    pub fn new(label: String, options: Vec<String>, default_index: usize, key: Option<String>) -> Self {
        let selectbox_key = key.unwrap_or_else(|| label.clone());
        let id = format!("selectbox_{}", selectbox_key);

        // Ensure default_index is within bounds
        let index = if default_index >= options.len() {
            0
        } else {
            default_index
        };

        Self {
            id,
            key: selectbox_key,
            label,
            options,
            index,
            help: None,
            disabled: false,
            placeholder: None,
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

    pub fn placeholder(&mut self, placeholder: String) {
        self.placeholder = Some(placeholder);
    }
}

impl Element for SelectboxElement {
    fn render(&self, context: &mut RenderContext) -> Result<(), StreamlitError> {
        let element_hash = hash(format!("selectbox_{}_{}", self.key, self.index).as_str());
        let mut msg = delta_base_with_path(context.delta_path.clone(), context.active_script_hash.clone(), element_hash);

        msg.r#type = Some(forward_msg::Type::Delta(Delta {
            fragment_id: String::new(),
            r#type: Some(delta::Type::NewElement(crate::proto::Element {
                height_config: None,
                width_config: None,
                text_alignment_config: None,
                r#type: Some(element::Type::Selectbox(ProtoSelectbox {
                    id: self.id.clone(),
                    label: self.label.clone(),
                    default: Some(self.index as i32),
                    options: self.options.clone(),
                    help: self.help.clone().unwrap_or_default(),
                    form_id: String::new(),
                    raw_value: Some(self.get_value()),
                    set_value: true,
                    disabled: self.disabled,
                    label_visibility: None,
                    placeholder: self.placeholder.clone().unwrap_or_default(),
                    accept_new_options: None,
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
