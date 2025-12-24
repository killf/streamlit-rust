#![allow(dead_code)]

use crate::elements::common::{Element, RenderContext};
use crate::error::StreamlitError;
use crate::proto::{delta, delta_base_with_path, element, forward_msg, Spinner as ProtoSpinner, Delta};
use crate::utils::hash::hash;

pub(crate) struct SpinnerElement {
    text: String,
    show_time: bool,
}

impl SpinnerElement {
    pub fn new(text: String) -> Self {
        Self {
            text,
            show_time: false,
        }
    }

    pub fn set_text(&mut self, text: String) {
        self.text = text;
    }

    pub fn show_time(&mut self, show_time: bool) {
        self.show_time = show_time;
    }
}

impl Element for SpinnerElement {
    fn render(&self, context: &mut RenderContext) -> Result<(), StreamlitError> {
        let element_hash = hash(format!("spinner_{}_{}", self.text, self.show_time).as_str());
        let mut msg = delta_base_with_path(context.delta_path.clone(), context.active_script_hash.clone(), element_hash);

        msg.r#type = Some(forward_msg::Type::Delta(Delta {
            fragment_id: String::new(),
            r#type: Some(delta::Type::NewElement(crate::proto::Element {
                height_config: None,
                width_config: None,
                text_alignment_config: None,
                r#type: Some(element::Type::Spinner(ProtoSpinner {
                    text: self.text.clone(),
                    cache: false,
                    show_time: self.show_time,
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
