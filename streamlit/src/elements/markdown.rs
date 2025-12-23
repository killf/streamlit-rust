use crate::elements::common::*;
use crate::error::StreamlitError;
use crate::proto::streamlit::{TextAlignmentConfig, WidthConfig};
use crate::proto::{Delta, ForwardMsg, delta, element, forward_msg};
use crate::websocket::factory::ForwardMsgFactory;
use actix_ws::Session;
use std::cell::RefCell;
use std::sync::Arc;

pub(crate) struct MarkdownElement {
    body: String,
    unsafe_allow_html: Option<bool>,
    help: Option<String>,
    width: Option<ElementWidth>,
    text_alignment: Option<TextAlignment>,
}

impl MarkdownElement {
    pub(crate) fn new(body: String) -> Self {
        Self {
            body,
            unsafe_allow_html: None,
            help: None,
            width: None,
            text_alignment: None,
        }
    }
}

impl Element for MarkdownElement {
    fn render(&self, context: &mut RenderContext) -> Result<(), StreamlitError> {
        let element_hash = ForwardMsgFactory::hash(format!("markdown_{}_{:?}_{:?}_{:?}", self.body, self.unsafe_allow_html, self.width, self.text_alignment).as_str());
        let mut msg = ForwardMsgFactory::delta_base_with_path(context.delta_path.clone(), context.active_script_hash.clone(), element_hash);

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
                    allow_html: self.unsafe_allow_html.unwrap_or(false),
                    is_caption: false,
                    element_type: 0,
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

    pub fn body(self, value: String) -> Self {
        self.element.borrow_mut().body = value;
        self
    }

    pub fn unsafe_allow_html(self, value: bool) -> Self {
        self.element.borrow_mut().unsafe_allow_html = Some(value);
        self
    }

    pub fn help(self, value: String) -> Self {
        self.element.borrow_mut().help = Some(value);
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
