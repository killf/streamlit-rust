use crate::core::AppendChild;
use crate::elements::common::{Anchor, Divider, ElementWidth, TextAlignment};
use crate::elements::title::HeadingElement;
use std::cell::RefCell;
use std::sync::Arc;

pub struct HeaderOption {
    body: String,
    anchor: Option<Anchor>,
    help: Option<String>,
    divider: Divider,
    width: ElementWidth,
    text_alignment: TextAlignment,
}

impl HeaderOption {
    pub fn new<T: ToString>(body: T) -> Self {
        Self {
            body: body.to_string(),
            anchor: None,
            help: None,
            divider: Divider::Bool(false),
            width: ElementWidth::Stretch,
            text_alignment: TextAlignment::Left,
        }
    }

    pub fn anchor<T: Into<Anchor>>(mut self, anchor: T) -> Self {
        self.anchor = Some(anchor.into());
        self
    }

    pub fn help<T: ToString>(mut self, help: T) -> Self {
        self.help = Some(help.to_string());
        self
    }

    pub fn divider<T: Into<Divider>>(mut self, divider: T) -> Self {
        self.divider = divider.into();
        self
    }

    pub fn width(mut self, width: ElementWidth) -> Self {
        self.width = width;
        self
    }

    pub fn text_alignment(mut self, alignment: TextAlignment) -> Self {
        self.text_alignment = alignment;
        self
    }
}

pub enum HeaderConfig {
    Text(String),
    Option(HeaderOption),
}

impl From<&str> for HeaderConfig {
    fn from(value: &str) -> Self {
        Self::Text(value.to_string())
    }
}

impl From<String> for HeaderConfig {
    fn from(value: String) -> Self {
        Self::Text(value)
    }
}

impl From<HeaderOption> for HeaderConfig {
    fn from(value: HeaderOption) -> Self {
        Self::Option(value)
    }
}

pub trait Header {
    fn title<T: Into<HeaderConfig>>(&self, body: T) {
        self.h1(body)
    }

    fn header<T: Into<HeaderConfig>>(&self, body: T) {
        self.h2(body)
    }

    fn sub_header<T: Into<HeaderConfig>>(&self, body: T) {
        self.h3(body)
    }

    fn h1<T: Into<HeaderConfig>>(&self, body: T);

    fn h2<T: Into<HeaderConfig>>(&self, body: T);

    fn h3<T: Into<HeaderConfig>>(&self, body: T);
}

impl<C: AppendChild> Header for C {
    fn h1<T: Into<HeaderConfig>>(&self, body: T) {
        handle(self, body, "h1")
    }

    fn h2<T: Into<HeaderConfig>>(&self, body: T) {
        handle(self, body, "h2")
    }

    fn h3<T: Into<HeaderConfig>>(&self, body: T) {
        handle(self, body, "h3")
    }
}

fn handle<C: AppendChild, T: Into<HeaderConfig>>(this: &C, data: T, tag: &str) {
    let element = match data.into() {
        HeaderConfig::Text(text) => HeadingElement::new(tag.to_string(), text),
        HeaderConfig::Option(option) => {
            let element = HeadingElement::new(tag.to_string(), option.body)
                .help(option.help.unwrap_or_default())
                .divider(option.divider.to_string())
                .width(option.width)
                .text_alignment(option.text_alignment);
            
            let element = if let Some(anchor) = option.anchor {
                match anchor {
                    Anchor::String(s) => element.hide_anchor(false).anchor(s),
                    Anchor::Bool(b) => element.hide_anchor(!b),
                }
            } else {
                element
            };

            element
        }
    };
    this.push(Arc::new(RefCell::new(element)));
}
