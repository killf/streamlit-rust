#![allow(dead_code)]

use crate::elements::common::{Element, RenderContext};
use crate::error::StreamlitError;
use crate::proto::{delta, delta_base_with_path, element, forward_msg, Checkbox as ProtoCheckbox, Delta};
use crate::utils::hash::hash;

pub(crate) struct CheckboxElement {
    id: String,
    key: String,
    label: String,
    value: bool,
    help: Option<String>,
    disabled: bool,
}

impl CheckboxElement {
    pub fn new(label: String, key: Option<String>) -> Self {
        let checkbox_key = key.unwrap_or_else(|| label.clone());
        let id = format!("checkbox_{}", checkbox_key);

        Self {
            id,
            key: checkbox_key,
            label,
            value: false,
            help: None,
            disabled: false,
        }
    }

    pub fn set_value(&mut self, value: bool) {
        self.value = value;
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
}

impl Element for CheckboxElement {
    fn render(&self, context: &mut RenderContext) -> Result<(), StreamlitError> {
        let element_hash = hash(format!("checkbox_{}_{}", self.key, self.value).as_str());
        let mut msg = delta_base_with_path(context.delta_path.clone(), context.active_script_hash.clone(), element_hash);

        msg.r#type = Some(forward_msg::Type::Delta(Delta {
            fragment_id: String::new(),
            r#type: Some(delta::Type::NewElement(crate::proto::Element {
                height_config: None,
                width_config: None,
                text_alignment_config: None,
                r#type: Some(element::Type::Checkbox(ProtoCheckbox {
                    id: self.id.clone(),
                    label: self.label.clone(),
                    default: false,
                    help: self.help.clone().unwrap_or_default(),
                    disabled: self.disabled,
                    form_id: String::new(),
                    value: self.value,
                    set_value: true,
                    label_visibility: None,
                    r#type: 0, // DEFAULT
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
