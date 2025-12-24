use crate::elements::common::{Element, ElementWidth, RenderContext, TextAlignment};
use crate::error::StreamlitError;
use crate::proto::streamlit::{TextAlignmentConfig, WidthConfig};
use crate::proto::{delta, delta_base_with_path, element, forward_msg, Delta};
use crate::utils::hash::hash;

pub(crate) struct HeadingElement {
    tag: String,
    body: String,
    anchor: String,
    help: String,
    divider: String,
    hide_anchor: bool,
    width: Option<ElementWidth>,
    text_alignment: Option<TextAlignment>,
}

impl HeadingElement {
    pub fn new(tag: String, body: String) -> HeadingElement {
        Self {
            tag,
            body,
            anchor: String::new(),
            help: String::new(),
            divider: String::new(),
            hide_anchor: false,
            width: None,
            text_alignment: None,
        }
    }

    pub fn help(mut self, value: String) -> Self {
        self.help = value;
        self
    }

    pub fn divider(mut self, value: String) -> Self {
        self.divider = value;
        self
    }

    pub fn width(mut self, value: ElementWidth) -> Self {
        self.width = Some(value);
        self
    }

    pub fn text_alignment(mut self, value: TextAlignment) -> Self {
        self.text_alignment = Some(value);
        self
    }

    pub fn hide_anchor(mut self, value: bool) -> Self {
        self.hide_anchor = value;
        self
    }

    pub fn anchor(mut self, value: String) -> Self {
        self.anchor = value;
        self
    }
}

impl Element for HeadingElement {
    fn render(&self, context: &mut RenderContext) -> Result<(), StreamlitError> {
        let element_hash = hash(format!("heading_{}_{:?}_{:?}_{:?}", self.tag, self.body, self.width, self.text_alignment).as_str());
        let mut msg = delta_base_with_path(context.delta_path.clone(), context.active_script_hash.clone(), element_hash);

        let width_config: Option<WidthConfig> = if let Some(width) = self.width.clone() { Some(width.into()) } else { None };
        let text_alignment_config: Option<TextAlignmentConfig> = if let Some(align) = self.text_alignment.clone() { Some(align.into()) } else { None };

        msg.r#type = Some(forward_msg::Type::Delta(Delta {
            fragment_id: String::new(),
            r#type: Some(delta::Type::NewElement(crate::proto::Element {
                height_config: None,
                width_config,
                text_alignment_config,
                r#type: Some(element::Type::Heading(crate::proto::Heading {
                    tag: self.tag.clone(),
                    anchor: self.anchor.clone(),
                    body: self.body.clone(),
                    help: self.help.to_string(),
                    hide_anchor: self.hide_anchor,
                    divider: self.divider.clone(),
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
