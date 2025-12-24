#![allow(dead_code)]

use crate::elements::common::{Element, RenderContext};
use crate::error::StreamlitError;
use crate::proto::{delta, delta_base_with_path, element, forward_msg, ColorPicker as ProtoColorPicker, Delta};
use crate::utils::hash::hash;

pub(crate) struct ColorPickerElement {
    id: String,
    key: String,
    label: String,
    default_value: String,
    help: Option<String>,
    disabled: bool,
}

impl ColorPickerElement {
    pub fn new(label: String, default_value: String, key: Option<String>) -> Self {
        let picker_key = key.unwrap_or_else(|| label.clone());
        let id = format!("color_picker_{}", picker_key);

        Self {
            id,
            key: picker_key,
            label,
            default_value,
            help: None,
            disabled: false,
        }
    }

    pub fn help(&mut self, help: String) {
        self.help = Some(help);
    }

    pub fn disabled(&mut self, disabled: bool) {
        self.disabled = disabled;
    }

    pub fn get_key(&self) -> &str {
        &self.key
    }
}

impl Element for ColorPickerElement {
    fn render(&self, context: &mut RenderContext) -> Result<(), StreamlitError> {
        let element_hash = hash(format!("color_picker_{}_{}", self.key, self.default_value).as_str());
        let mut msg = delta_base_with_path(context.delta_path.clone(), context.active_script_hash.clone(), element_hash);

        msg.r#type = Some(forward_msg::Type::Delta(Delta {
            fragment_id: String::new(),
            r#type: Some(delta::Type::NewElement(crate::proto::Element {
                height_config: None,
                width_config: None,
                text_alignment_config: None,
                r#type: Some(element::Type::ColorPicker(ProtoColorPicker {
                    id: self.id.clone(),
                    label: self.label.clone(),
                    default: self.default_value.clone(),
                    help: self.help.clone().unwrap_or_default(),
                    form_id: String::new(),
                    value: String::new(),
                    set_value: false,
                    disabled: self.disabled,
                    label_visibility: None,
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

pub struct ColorPicker {
    value: String,
}

impl ColorPicker {
    pub(crate) fn new(value: String) -> Self {
        Self { value }
    }

    /// Get the selected color value (hex format)
    pub fn value(&self) -> &str {
        &self.value
    }
}
