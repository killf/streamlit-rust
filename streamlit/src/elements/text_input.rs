#![allow(dead_code)]

use crate::elements::common::{Element, RenderContext};
use crate::error::StreamlitError;
use crate::proto::{delta, delta_base_with_path, element, forward_msg, TextInput as ProtoTextInput, Delta};
use crate::utils::hash::hash;

pub(crate) struct TextInputElement {
    id: String,
    key: String,
    label: String,
    value: String,
    text_type: TextType,
    max_chars: Option<u32>,
    placeholder: Option<String>,
    help: Option<String>,
    disabled: bool,
}

#[derive(Clone, Copy)]
pub enum TextType {
    Default,
    Password,
}

impl TextInputElement {
    pub fn new(label: String, key: Option<String>) -> Self {
        let input_key = key.unwrap_or_else(|| label.clone());
        let id = format!("text_input_{}", input_key);

        Self {
            id,
            key: input_key,
            label,
            value: String::new(),
            text_type: TextType::Default,
            max_chars: None,
            placeholder: None,
            help: None,
            disabled: false,
        }
    }

    pub fn set_value(&mut self, value: String) {
        self.value = value;
    }

    pub fn get_key(&self) -> &str {
        &self.key
    }

    pub fn text_type(&mut self, text_type: TextType) {
        self.text_type = text_type;
    }

    pub fn max_chars(&mut self, max_chars: u32) {
        self.max_chars = Some(max_chars);
    }

    pub fn placeholder(&mut self, placeholder: String) {
        self.placeholder = Some(placeholder);
    }

    pub fn help(&mut self, help: String) {
        self.help = Some(help);
    }

    pub fn disabled(&mut self, disabled: bool) {
        self.disabled = disabled;
    }
}

impl Element for TextInputElement {
    fn render(&self, context: &mut RenderContext) -> Result<(), StreamlitError> {
        let element_hash = hash(format!("text_input_{}_{}", self.key, self.value).as_str());
        let mut msg = delta_base_with_path(context.delta_path.clone(), context.active_script_hash.clone(), element_hash);

        let text_type = match self.text_type {
            TextType::Default => 0,
            TextType::Password => 1,
        };

        msg.r#type = Some(forward_msg::Type::Delta(Delta {
            fragment_id: String::new(),
            r#type: Some(delta::Type::NewElement(crate::proto::Element {
                height_config: None,
                width_config: None,
                text_alignment_config: None,
                r#type: Some(element::Type::TextInput(ProtoTextInput {
                    id: self.id.clone(),
                    label: self.label.clone(),
                    default: None,
                    r#type: text_type,
                    max_chars: self.max_chars.unwrap_or(0),
                    help: self.help.clone().unwrap_or_default(),
                    form_id: String::new(),
                    value: if self.value.is_empty() { None } else { Some(self.value.clone()) },
                    set_value: !self.value.is_empty(),
                    autocomplete: String::new(),
                    placeholder: self.placeholder.clone().unwrap_or_default(),
                    disabled: self.disabled,
                    label_visibility: None,
                    icon: String::new(),
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
