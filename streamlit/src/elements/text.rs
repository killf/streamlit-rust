//! The text family and one-shot presentation elements measured on the
//! Python 1.66.1 reference (see .codex/compatibility.md, Text elements):
//! plain text (wrapped, content width, left alignment), embedded html
//! (stretch width), the iframe (scrolling on by default, a 400 px default
//! height), the snow one-shot, and the empty placeholder st.echo
//! retro-fills with the echoed code at the placeholder's own path.

use crate::elements::common::*;
use crate::error::StreamlitError;
use crate::proto::{Delta, Empty, Html, IFrame, Snow, Text, delta, delta_base_with_path, element, forward_msg, i_frame};
use crate::utils::hash::hash;

pub(crate) struct TextElement {
    body: String,
    width: Option<ElementWidth>,
    text_alignment: Option<TextAlignment>,
}

impl TextElement {
    pub fn new(body: String) -> Self {
        Self { body, width: None, text_alignment: None }
    }

    pub fn width(mut self, width: ElementWidth) -> Self {
        self.width = Some(width);
        self
    }

    pub fn text_alignment(mut self, alignment: TextAlignment) -> Self {
        self.text_alignment = Some(alignment);
        self
    }
}

impl Element for TextElement {
    fn render(&self, context: &mut RenderContext) -> Result<(), StreamlitError> {
        let element_hash = hash(format!("text_{}_{:?}_{:?}", self.body, self.width, self.text_alignment).as_str());
        let mut msg = delta_base_with_path(context.delta_path.clone(), context.active_script_hash.clone(), element_hash);
        msg.r#type = Some(forward_msg::Type::Delta(Delta {
            fragment_id: String::new(),
            r#type: Some(delta::Type::NewElement(crate::proto::Element {
                width_config: Some(self.width.clone().map_or_else(|| ElementWidth::Content.into(), Into::into)),
                text_alignment_config: Some(self.text_alignment.clone().map_or_else(|| TextAlignment::Left.into(), Into::into)),
                r#type: Some(element::Type::Text(Text {
                    body: self.body.clone(),
                    wrap: Some(true),
                    ..Default::default()
                })),
                ..Default::default()
            })),
        }));
        context.push(msg);
        if let Some(index) = context.delta_path.last_mut() {
            *index += 1;
        }
        Ok(())
    }
}

pub(crate) struct HtmlElement {
    body: String,
}

impl HtmlElement {
    pub fn new(body: String) -> Self {
        Self { body }
    }
}

impl Element for HtmlElement {
    fn render(&self, context: &mut RenderContext) -> Result<(), StreamlitError> {
        let element_hash = hash(format!("html_{}", self.body).as_str());
        let mut msg = delta_base_with_path(context.delta_path.clone(), context.active_script_hash.clone(), element_hash);
        msg.r#type = Some(forward_msg::Type::Delta(Delta {
            fragment_id: String::new(),
            r#type: Some(delta::Type::NewElement(crate::proto::Element {
                width_config: Some(ElementWidth::Stretch.into()),
                r#type: Some(element::Type::Html(Html { body: self.body.clone(), ..Default::default() })),
                ..Default::default()
            })),
        }));
        context.push(msg);
        if let Some(index) = context.delta_path.last_mut() {
            *index += 1;
        }
        Ok(())
    }
}

pub(crate) struct IframeElement {
    src: i_frame::Type,
    scrolling: bool,
    height: Option<ElementHeight>,
}

impl IframeElement {
    pub fn src(url: String) -> Self {
        Self {
            src: i_frame::Type::Src(url),
            scrolling: true,
            height: None,
        }
    }

    pub fn srcdoc(html: String) -> Self {
        Self {
            src: i_frame::Type::Srcdoc(html),
            scrolling: true,
            height: None,
        }
    }

    pub fn height(mut self, height: ElementHeight) -> Self {
        self.height = Some(height);
        self
    }
}

impl Element for IframeElement {
    fn render(&self, context: &mut RenderContext) -> Result<(), StreamlitError> {
        let element_hash = hash(format!("iframe_{:?}_{}__{:?}", self.src, self.scrolling, self.height).as_str());
        let mut msg = delta_base_with_path(context.delta_path.clone(), context.active_script_hash.clone(), element_hash);
        msg.r#type = Some(forward_msg::Type::Delta(Delta {
            fragment_id: String::new(),
            r#type: Some(delta::Type::NewElement(crate::proto::Element {
                height_config: Some(self.height.clone().map_or_else(|| ElementHeight::Value(400).into(), Into::into)),
                width_config: Some(ElementWidth::Stretch.into()),
                r#type: Some(element::Type::Iframe(IFrame {
                    r#type: Some(self.src.clone()),
                    scrolling: self.scrolling,
                    ..Default::default()
                })),
                ..Default::default()
            })),
        }));
        context.push(msg);
        if let Some(index) = context.delta_path.last_mut() {
            *index += 1;
        }
        Ok(())
    }
}

/// The snow one-shot: `has_one_shot_effect`, no width or height config, like
/// balloons.
pub(crate) struct SnowElement;

impl Element for SnowElement {
    fn render(&self, context: &mut RenderContext) -> Result<(), StreamlitError> {
        let mut msg = delta_base_with_path(context.delta_path.clone(), context.active_script_hash.clone(), hash("snow"));
        msg.r#type = Some(forward_msg::Type::Delta(Delta {
            fragment_id: String::new(),
            r#type: Some(delta::Type::NewElement(crate::proto::Element {
                has_one_shot_effect: Some(true),
                r#type: Some(element::Type::Snow(Snow { show: true })),
                ..Default::default()
            })),
        }));
        context.push(msg);
        if let Some(index) = context.delta_path.last_mut() {
            *index += 1;
        }
        Ok(())
    }
}

/// The empty placeholder: no fields, no configs. It consumes a container
/// slot that a later element can replace (st.echo retro-fills its slot
/// with the echoed code; the st.empty handle overwrites it via write).
pub(crate) struct EmptyElement;

impl Element for EmptyElement {
    fn render(&self, context: &mut RenderContext) -> Result<(), StreamlitError> {
        let mut msg = delta_base_with_path(context.delta_path.clone(), context.active_script_hash.clone(), hash("empty"));
        msg.r#type = Some(forward_msg::Type::Delta(Delta {
            fragment_id: String::new(),
            r#type: Some(delta::Type::NewElement(crate::proto::Element {
                r#type: Some(element::Type::Empty(Empty {})),
                ..Default::default()
            })),
        }));
        context.push(msg);
        if let Some(index) = context.delta_path.last_mut() {
            *index += 1;
        }
        Ok(())
    }
}

pub(crate) struct JsonElement {
    body: String,
    expanded: bool,
}

impl JsonElement {
    pub fn new(body: String, expanded: bool) -> Self {
        Self { body, expanded }
    }
}

impl Element for JsonElement {
    fn render(&self, context: &mut RenderContext) -> Result<(), StreamlitError> {
        let element_hash = hash(format!("json_{}_{}", self.body, self.expanded).as_str());
        let mut msg = delta_base_with_path(context.delta_path.clone(), context.active_script_hash.clone(), element_hash);
        msg.r#type = Some(forward_msg::Type::Delta(Delta {
            fragment_id: String::new(),
            r#type: Some(delta::Type::NewElement(crate::proto::Element {
                width_config: Some(ElementWidth::Stretch.into()),
                r#type: Some(element::Type::Json(crate::proto::Json {
                    body: self.body.clone(),
                    expanded: self.expanded,
                    ..Default::default()
                })),
                ..Default::default()
            })),
        }));
        context.push(msg);
        if let Some(index) = context.delta_path.last_mut() {
            *index += 1;
        }
        Ok(())
    }
}

/// The spacer: no fields; both the width and height configs carry the same
/// pixel value (the measured `st.space(3)` shape).
pub(crate) struct SpaceElement {
    size: u32,
}

impl SpaceElement {
    pub fn new(size: u32) -> Self {
        Self { size }
    }
}

impl Element for SpaceElement {
    fn render(&self, context: &mut RenderContext) -> Result<(), StreamlitError> {
        let element_hash = hash(format!("space_{}", self.size).as_str());
        let mut msg = delta_base_with_path(context.delta_path.clone(), context.active_script_hash.clone(), element_hash);
        msg.r#type = Some(forward_msg::Type::Delta(Delta {
            fragment_id: String::new(),
            r#type: Some(delta::Type::NewElement(crate::proto::Element {
                height_config: Some(ElementHeight::Value(self.size as i32).into()),
                width_config: Some(ElementWidth::Value(self.size as i32).into()),
                r#type: Some(element::Type::Space(crate::proto::Space {})),
                ..Default::default()
            })),
        }));
        context.push(msg);
        if let Some(index) = context.delta_path.last_mut() {
            *index += 1;
        }
        Ok(())
    }
}
