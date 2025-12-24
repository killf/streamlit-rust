#![allow(dead_code)]

use crate::elements::common::{Element, RenderContext};
use crate::error::StreamlitError;
use crate::proto::{delta, delta_base_with_path, element, forward_msg, Progress as ProtoProgress, Delta};
use crate::utils::hash::hash;

pub(crate) struct ProgressElement {
    value: u32,
    text: String,
}

impl ProgressElement {
    pub fn new(value: u32, text: String) -> Self {
        Self {
            value: value.min(100), // Cap at 100
            text,
        }
    }

    pub fn set_value(&mut self, value: u32) {
        self.value = value.min(100);
    }

    pub fn set_text(&mut self, text: String) {
        self.text = text;
    }
}

impl Element for ProgressElement {
    fn render(&self, context: &mut RenderContext) -> Result<(), StreamlitError> {
        let element_hash = hash(format!("progress_{}_{}", self.value, self.text).as_str());
        let mut msg = delta_base_with_path(context.delta_path.clone(), context.active_script_hash.clone(), element_hash);

        msg.r#type = Some(forward_msg::Type::Delta(Delta {
            fragment_id: String::new(),
            r#type: Some(delta::Type::NewElement(crate::proto::Element {
                height_config: None,
                width_config: None,
                text_alignment_config: None,
                r#type: Some(element::Type::Progress(ProtoProgress {
                    value: self.value,
                    text: self.text.clone(),
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
