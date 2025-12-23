use crate::elements::badge::{Badge, BadgeElement};
use crate::elements::code::{Code, CodeElement};
use crate::elements::common::Element;
use crate::elements::container::{Container, ContainerElement};
use crate::elements::markdown::{Markdown, MarkdownElement, MarkdownElementType};
use crate::elements::title::{Heading, HeadingElement};
use crate::elements::App;
use crate::memory::Allocator;
use crate::proto::WidgetState;
use parking_lot::Mutex;
use std::cell::RefCell;
use std::sync::Arc;

/// Streamlit Rust API - provides a Python-like Streamlit interface
pub struct Streamlit {
    pub(crate) app: Arc<Mutex<App>>,
    allocator: Allocator,
}

impl Streamlit {
    pub(crate) fn new() -> Self {
        Self {
            app: Arc::new(Mutex::new(App::new())),
            allocator: Allocator::new(),
        }
    }

    pub(crate) fn process_widget_states(self, widget_states: Vec<WidgetState>) -> Self {
        self.app.lock().process_widget_states(widget_states);
        self
    }
}

pub(crate) trait AppendChild {
    fn push(&self, element: Arc<RefCell<dyn Element>>);

    fn allocator(&self) -> &Allocator;
}

impl AppendChild for Streamlit {
    fn push(&self, element: Arc<RefCell<dyn Element>>) {
        self.app.lock().push(element);
    }

    fn allocator(&self) -> &Allocator {
        &self.allocator
    }
}

pub trait StreamlitApi {
    fn write<T: ToString>(&self, content: T) -> &Markdown;

    fn title<T: ToString>(&self, body: T) -> &Heading {
        self.h1(body)
    }

    fn header<T: ToString>(&self, body: T) -> &Heading {
        self.h2(body)
    }

    fn sub_header<T: ToString>(&self, body: T) -> &Heading {
        self.h3(body)
    }

    fn divider(&self) -> &Markdown;

    fn h1<T: ToString>(&self, body: T) -> &Heading;

    fn h2<T: ToString>(&self, body: T) -> &Heading;

    fn h3<T: ToString>(&self, body: T) -> &Heading;

    fn markdown<T: ToString>(&self, body: T) -> &Markdown;

    fn badge<T: ToString>(&self, label: T) -> &Badge;

    fn caption<T: ToString>(&self, body: T) -> &Markdown;

    fn code<T1: ToString, T2: ToString>(&self, code_text: T1, language: T2) -> &Code;

    fn container(&'_ self) -> &'_ Container<'_>;
}

impl<C: AppendChild> StreamlitApi for C {
    fn write<T: ToString>(&self, content: T) -> &Markdown {
        let element = Arc::new(RefCell::new(MarkdownElement::new(content.to_string())));
        self.push(element.clone());
        self.allocator().malloc(Markdown::new(element))
    }

    fn divider(&self) -> &Markdown {
        let element = Arc::new(RefCell::new(MarkdownElement::new("---".to_string()).element_type(MarkdownElementType::Divider)));
        self.push(element.clone());
        self.allocator().malloc(Markdown::new(element))
    }

    fn h1<T: ToString>(&self, body: T) -> &Heading {
        let element = Arc::new(RefCell::new(HeadingElement::new("h1".to_string(), body.to_string())));
        self.push(element.clone());
        self.allocator().malloc(Heading::new(element))
    }

    fn h2<T: ToString>(&self, body: T) -> &Heading {
        let element = Arc::new(RefCell::new(HeadingElement::new("h2".to_string(), body.to_string())));
        self.push(element.clone());
        self.allocator().malloc(Heading::new(element))
    }

    fn h3<T: ToString>(&self, body: T) -> &Heading {
        let element = Arc::new(RefCell::new(HeadingElement::new("h3".to_string(), body.to_string())));
        self.push(element.clone());
        self.allocator().malloc(Heading::new(element))
    }

    fn markdown<T: ToString>(&self, body: T) -> &Markdown {
        let element = Arc::new(RefCell::new(MarkdownElement::new(body.to_string())));
        self.push(element.clone());
        self.allocator().malloc(Markdown::new(element))
    }

    fn badge<T: ToString>(&self, label: T) -> &Badge {
        let element = Arc::new(RefCell::new(BadgeElement::new(label.to_string())));
        self.push(element.clone());
        self.allocator().malloc(Badge::new(element))
    }

    fn caption<T: ToString>(&self, body: T) -> &Markdown {
        let element = Arc::new(RefCell::new(MarkdownElement::new(body.to_string()).element_type(MarkdownElementType::Caption)));
        self.push(element.clone());
        self.allocator().malloc(Markdown::new(element))
    }

    fn code<T1: ToString, T2: ToString>(&self, code_text: T1, language: T2) -> &Code {
        let element = Arc::new(RefCell::new(CodeElement::new(code_text.to_string(), language.to_string())));
        self.push(element.clone());
        self.allocator().malloc(Code::new(element))
    }

    fn container(&self) -> &Container<'_> {
        let element = Arc::new(RefCell::new(ContainerElement::new()));
        self.push(element.clone());
        self.allocator().malloc(Container::new(element, self.allocator()))
    }

    // /// Display a button and return whether it was clicked
    // pub fn button(&self, label: &str, key: Option<&str>) -> bool {
    //     let button_key = key.unwrap_or(label);
    //
    //     // Generate consistent ID using the button key - this is the key fix!
    //     let element_id = format!("button-{}", button_key);
    //
    //     // Check if this button was previously clicked
    //     let was_clicked = self
    //         .get_widget_state(button_key)
    //         .and_then(|value| match value {
    //             WidgetValue::Boolean(b) => Some(b),
    //             _ => None,
    //         })
    //         .unwrap_or(false);
    //
    //     // Reset button state after checking
    //     if was_clicked {
    //         self.set_widget_state(button_key, WidgetValue::Boolean(false));
    //     }
    //
    //     // Create the button element with consistent ID
    //     let element = StreamlitElement::Button {
    //         id: element_id,
    //         label: label.to_string(),
    //         key: button_key.to_string(),
    //         clicked: was_clicked,
    //     };
    //     self.elements.lock().push(element);
    //
    //     was_clicked
    // }
}
