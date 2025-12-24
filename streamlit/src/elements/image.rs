#![allow(dead_code)]

use crate::elements::common::{Element, RenderContext};
use crate::error::StreamlitError;
use crate::proto::{delta, delta_base_with_path, element, forward_msg, Delta, Image as ProtoImage, ImageList};
use crate::utils::hash::hash;
use std::sync::Arc;
use std::cell::RefCell;

/// Image element for displaying images
pub struct ImageElement {
    url: Option<String>,
    caption: Option<String>,
}

impl ImageElement {
    pub fn new() -> Self {
        Self {
            url: None,
            caption: None,
        }
    }

    pub fn url(mut self, url: String) -> Self {
        self.url = Some(url);
        self
    }

    pub fn caption(mut self, caption: String) -> Self {
        self.caption = Some(caption);
        self
    }

    pub fn set_url(&mut self, url: String) {
        self.url = Some(url);
    }

    pub fn set_caption(&mut self, caption: String) {
        self.caption = Some(caption);
    }
}

impl Default for ImageElement {
    fn default() -> Self {
        Self::new()
    }
}

impl Element for ImageElement {
    fn render(&self, context: &mut RenderContext) -> Result<(), StreamlitError> {
        let element_hash = hash(format!("image_{:?}_{:?}", self.url, self.caption).as_str());
        let mut msg = delta_base_with_path(context.delta_path.clone(), context.active_script_hash.clone(), element_hash);

        msg.r#type = Some(forward_msg::Type::Delta(Delta {
            fragment_id: String::new(),
            r#type: Some(delta::Type::NewElement(crate::proto::Element {
                height_config: None,
                width_config: None,
                text_alignment_config: None,
                r#type: Some(element::Type::Imgs(ImageList {
                    imgs: vec![ProtoImage {
                        url: self.url.clone().unwrap_or_default(),
                        caption: self.caption.clone().unwrap_or_default(),
                        ..Default::default()
                    }],
                    ..Default::default()
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

pub struct Image<'a> {
    element: Arc<RefCell<ImageElement>>,
    allocator: std::rc::Rc<std::cell::RefCell<crate::memory::Allocator>>,
    parent: Option<&'a dyn crate::api::AppendChild>,
}

impl<'a> Image<'a> {
    pub(crate) fn new(element: Arc<RefCell<ImageElement>>, allocator: std::rc::Rc<std::cell::RefCell<crate::memory::Allocator>>, parent: Option<&'a dyn crate::api::AppendChild>) -> Self {
        if let Some(p) = parent {
            p.push(element.clone());
        }
        Self { element, allocator, parent }
    }

    /// Set image caption
    pub fn caption(&self, caption: &str) -> &Self {
        self.element.borrow_mut().set_caption(caption.to_string());
        self
    }

    /// Set image URL
    pub fn url(&self, url: &str) -> &Self {
        self.element.borrow_mut().set_url(url.to_string());
        self
    }
}
