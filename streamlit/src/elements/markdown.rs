use crate::elements::common::*;
use std::cell::RefCell;
use std::sync::Arc;

pub(crate) struct MarkdownElement {
    body: String,
    unsafe_allow_html: Option<bool>,
    help: Option<String>,
    width: ElementWidth,
    text_alignment: TextAlignment,
}

impl MarkdownElement {
    fn new(body: String) -> Self {
        Self {
            body,
            unsafe_allow_html: None,
            help: None,
            width: ElementWidth::Stretch,
            text_alignment: TextAlignment::Left,
        }
    }
}

impl Element for MarkdownElement {
    fn render(&self) {}
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

    pub fn width(mut self, width: ElementWidth) -> Self {
        self.element.borrow_mut().width = width;
        self
    }

    pub fn text_alignment(mut self, alignment: TextAlignment) -> Self {
        self.element.borrow_mut().text_alignment = alignment;
        self
    }
}
