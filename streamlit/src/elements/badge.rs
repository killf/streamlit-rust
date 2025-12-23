use crate::elements::common::{Element, ElementWidth, RenderContext, TextAlignment};
use crate::elements::markdown::MarkdownElementType;
use crate::error::StreamlitError;
use crate::proto::streamlit::{TextAlignmentConfig, WidthConfig};
use crate::proto::{delta, delta_base_with_path, element, forward_msg, Delta};
use crate::utils::hash::hash;
use std::cell::RefCell;
use std::sync::Arc;

pub(crate) struct BadgeElement {
    label: String,
    color: String,
    icon: String,
    help: Option<String>,
    width: Option<ElementWidth>,
    text_alignment: Option<TextAlignment>,
}

impl BadgeElement {
    pub fn new(label: String) -> BadgeElement {
        BadgeElement {
            label,
            color: "blue".to_string(),
            icon: String::new(),
            help: None,
            width: None,
            text_alignment: None,
        }
    }
}

impl Element for BadgeElement {
    fn render(&self, context: &mut RenderContext) -> Result<(), StreamlitError> {
        let element_hash = hash(format!("badge_{}_{}_{}_{:?}_{:?}", self.color, self.icon, self.label, self.width, self.text_alignment).as_str());
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
                    body: format!(":{}-badge[{} {}]", self.color, self.icon, self.label),
                    allow_html: false,
                    is_caption: false,
                    element_type: MarkdownElementType::Native as i32,
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

pub struct Badge {
    element: Arc<RefCell<BadgeElement>>,
}

impl Badge {
    pub(crate) fn new(element: Arc<RefCell<BadgeElement>>) -> Self {
        Self { element }
    }

    pub fn label<T: ToString>(self, value: T) -> Self {
        self.element.borrow_mut().label = value.to_string();
        self
    }

    pub fn color<T: ToString>(self, value: T) -> Self {
        self.element.borrow_mut().color = value.to_string();
        self
    }

    pub fn icon<T: ToString>(self, value: T) -> Self {
        self.element.borrow_mut().icon = value.to_string();
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
