use crate::elements::common::*;
use crate::error::StreamlitError;
use crate::proto::streamlit::{TextAlignmentConfig, WidthConfig};
use crate::proto::{delta, delta_base_with_path, element, forward_msg, Delta};
use crate::utils::hash::hash;
use std::cell::RefCell;
use std::sync::Arc;

#[repr(i32)]
#[allow(unused)]
#[derive(Copy, Clone, PartialEq, Eq, Hash)]
pub(crate) enum MarkdownElementType {
    Unspecified = 0,
    Native = 1,
    Caption = 2,
    Code = 3,
    Latex = 4,
    Divider = 5,
}

pub(crate) struct MarkdownElement {
    body: String,
    unsafe_allow_html: bool,
    element_type: MarkdownElementType,
    is_caption: bool,
    help: Option<String>,
    width: Option<ElementWidth>,
    text_alignment: Option<TextAlignment>,
}

impl MarkdownElement {
    pub fn new(body: String) -> Self {
        Self {
            body,
            unsafe_allow_html: false,
            element_type: MarkdownElementType::Unspecified,
            is_caption: false,
            help: None,
            width: None,
            text_alignment: None,
        }
    }

    pub fn element_type(mut self, value: MarkdownElementType) -> Self {
        if value == MarkdownElementType::Caption {
            self.is_caption = true;
        }
        self.element_type = value;
        self
    }
}

impl Element for MarkdownElement {
    fn render(&self, context: &mut RenderContext) -> Result<(), StreamlitError> {
        let element_hash = hash(format!("markdown_{}_{:?}_{:?}_{:?}", self.body, self.unsafe_allow_html, self.width, self.text_alignment).as_str());
        let mut msg = delta_base_with_path(context.delta_path.clone(), context.active_script_hash.clone(), element_hash);

        let width_config: Option<WidthConfig> = if let Some(width) = self.width.clone() { Some(width.into()) } else { None };
        let text_alignment_config: Option<TextAlignmentConfig> = if let Some(align) = self.text_alignment.clone() { Some(align.into()) } else { None };

        msg.r#type = Some(forward_msg::Type::Delta(Delta {
            fragment_id: String::new(),
            r#type: Some(delta::Type::NewElement(crate::proto::Element {
                height_config: None,
                width_config,
                text_alignment_config,
                r#type: Some(element::Type::Markdown(crate::proto::Markdown {
                    body: self.body.clone(),
                    allow_html: self.unsafe_allow_html,
                    is_caption: self.is_caption,
                    element_type: self.element_type as i32,
                    help: self.help.clone().unwrap_or_default(),
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

pub struct Markdown {
    element: Arc<RefCell<MarkdownElement>>,
}

impl Markdown {
    pub(crate) fn new(element: Arc<RefCell<MarkdownElement>>) -> Self {
        Self { element }
    }

    pub fn body<T: ToString>(self, value: T) -> Self {
        self.element.borrow_mut().body = value.to_string();
        self
    }

    pub fn unsafe_allow_html(self, value: bool) -> Self {
        self.element.borrow_mut().unsafe_allow_html = value;
        self
    }

    pub fn help<T: ToString>(self, value: T) -> Self {
        self.element.borrow_mut().help = Some(value.to_string());
        self
    }

    pub fn width(self, width: ElementWidth) -> Self {
        self.element.borrow_mut().width = Some(width);
        self
    }

    pub fn text_alignment(self, alignment: TextAlignment) -> Self {
        self.element.borrow_mut().text_alignment = Some(alignment);
        self
    }
}
