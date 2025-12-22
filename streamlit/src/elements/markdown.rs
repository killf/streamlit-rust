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

pub struct Markdown {
    inner: Arc<RefCell<MarkdownElement>>,
}

impl Markdown {
    pub fn unsafe_allow_html(self, value: bool) -> Self {
        self.inner.borrow_mut().unsafe_allow_html = Some(value);
        self
    }

    pub fn help(self, value: String) -> Self {
        self.inner.borrow_mut().help = Some(value);
        self
    }
}
