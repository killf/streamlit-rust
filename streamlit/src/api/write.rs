use crate::core::AppendChild;
use crate::elements::markdown::MarkdownElement;
use std::cell::RefCell;
use std::sync::Arc;

pub struct WriteOption<T> {
    body: T,
    unsafe_allow_html: bool,
}

impl<T> WriteOption<T> {
    pub fn new(body: T) -> Self {
        Self { body, unsafe_allow_html: false }
    }

    pub fn unsafe_allow_html(mut self, value: bool) -> Self {
        self.unsafe_allow_html = value;
        self
    }
}

pub enum WriteConfig {
    Text(String),
    TextOption(WriteOption<String>),
}

impl From<&str> for WriteConfig {
    fn from(value: &str) -> Self {
        Self::Text(value.to_string())
    }
}

impl From<String> for WriteConfig {
    fn from(value: String) -> Self {
        Self::Text(value)
    }
}

impl From<(&str, bool)> for WriteConfig {
    fn from(value: (&str, bool)) -> Self {
        Self::TextOption(WriteOption {
            body: value.0.to_string(),
            unsafe_allow_html: value.1,
        })
    }
}

impl From<(String, bool)> for WriteConfig {
    fn from(value: (String, bool)) -> Self {
        Self::TextOption(WriteOption { body: value.0, unsafe_allow_html: value.1 })
    }
}

impl From<WriteOption<String>> for WriteConfig {
    fn from(value: WriteOption<String>) -> Self {
        Self::TextOption(value)
    }
}

pub trait Write {
    fn write<T: Into<WriteConfig>>(&self, data: T);
}

impl<C: AppendChild> Write for C {
    fn write<T: Into<WriteConfig>>(&self, data: T) {
        let element = match data.into() {
            WriteConfig::Text(text) => MarkdownElement::new(text),
            WriteConfig::TextOption(_) => todo!(),
        };
        self.push(Arc::new(RefCell::new(element)));
    }
}
