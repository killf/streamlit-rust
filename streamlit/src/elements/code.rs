use crate::elements::common::*;
use crate::error::StreamlitError;
use crate::proto::streamlit::{TextAlignmentConfig, WidthConfig};
use crate::proto::{delta, delta_base_with_path, element, forward_msg, Delta};
use crate::utils::hash::hash;
use std::cell::RefCell;
use std::sync::Arc;

pub(crate) struct CodeElement {
    code_text: String,
    language: String,
    show_line_numbers: bool,
    wrap_lines: bool,
    width: Option<ElementWidth>,
    text_alignment: Option<TextAlignment>,
}

impl CodeElement {
    pub fn new(code_text: String, language: String) -> Self {
        Self {
            code_text,
            language,
            show_line_numbers: false,
            wrap_lines: false,
            width: None,
            text_alignment: None,
        }
    }
}

impl Element for CodeElement {
    fn render(&self, context: &mut RenderContext) -> Result<(), StreamlitError> {
        let element_hash = hash(format!("code_{}_{}_{}_{}_{:?}_{:?}", self.code_text, self.language, self.show_line_numbers, self.wrap_lines, self.width, self.text_alignment).as_str());
        let mut msg = delta_base_with_path(context.delta_path.clone(), context.active_script_hash.clone(), element_hash);

        let width_config: Option<WidthConfig> = if let Some(width) = self.width.clone() { Some(width.into()) } else { None };
        let text_alignment_config: Option<TextAlignmentConfig> = if let Some(align) = self.text_alignment.clone() { Some(align.into()) } else { None };

        msg.r#type = Some(forward_msg::Type::Delta(Delta {
            fragment_id: String::new(),
            r#type: Some(delta::Type::NewElement(crate::proto::Element {
                height_config: None,
                width_config,
                text_alignment_config,
                r#type: Some(element::Type::Code(crate::proto::Code {
                    code_text: self.code_text.clone(),
                    language: self.language.clone(),
                    show_line_numbers: self.show_line_numbers,
                    wrap_lines: self.wrap_lines,
                    #[allow(deprecated)]
                    height: 0,
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

pub struct Code {
    element: Arc<RefCell<CodeElement>>,
}

impl Code {
    pub(crate) fn new(element: Arc<RefCell<CodeElement>>) -> Self {
        Self { element }
    }

    pub fn body<T: ToString>(&self, value: T) -> &Self {
        self.element.borrow_mut().code_text = value.to_string();
        self
    }

    pub fn language<T: ToString>(&self, language: T) -> &Self {
        self.element.borrow_mut().language = language.to_string();
        self
    }

    pub fn show_line_numbers(&self, value: bool) -> &Self {
        self.element.borrow_mut().show_line_numbers = value;
        self
    }

    pub fn wrap_lines(&self, value: bool) -> &Self {
        self.element.borrow_mut().wrap_lines = value;
        self
    }

    pub fn width(&self, width: ElementWidth) -> &Self {
        self.element.borrow_mut().width = Some(width);
        self
    }

    pub fn text_alignment(&self, alignment: TextAlignment) -> &Self {
        self.element.borrow_mut().text_alignment = Some(alignment);
        self
    }
}
