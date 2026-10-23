use crate::elements::common::{Element, ElementWidth, RenderContext, TextAlignment};
use crate::elements::markdown::MarkdownElementType;
use crate::error::StreamlitError;
use crate::proto::streamlit::{TextAlignmentConfig, WidthConfig};
use crate::proto::{Delta, delta, delta_base_with_path, element, forward_msg};
use crate::utils::hash::hash;

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

    pub fn color(mut self, color: String) -> Self {
        self.color = color;
        self
    }

    pub fn icon(mut self, icon: String) -> Self {
        self.icon = icon;
        self
    }

    pub fn help(mut self, help: String) -> Self {
        self.help = Some(help);
        self
    }
    pub fn width(mut self, width: ElementWidth) -> Self {
        self.width = Some(width);
        self
    }
}

impl Element for BadgeElement {
    fn render(&self, context: &mut RenderContext) -> Result<(), StreamlitError> {
        let element_hash = hash(format!("badge_{}_{}_{}_{:?}_{:?}", self.color, self.icon, self.label, self.width, self.text_alignment).as_str());
        let mut msg = delta_base_with_path(context.delta_path.clone(), context.active_script_hash.clone(), element_hash);

        let width_config: Option<WidthConfig> = self.width.clone().map(Into::into);
        let text_alignment_config: Option<TextAlignmentConfig> = self.text_alignment.clone().map(Into::into);

        msg.r#type = Some(forward_msg::Type::Delta(Delta {
            fragment_id: String::new(),
            r#type: Some(delta::Type::NewElement(crate::proto::Element {
                has_one_shot_effect: None,
                height_config: None,
                width_config,
                text_alignment_config,
                r#type: Some(element::Type::Markdown(crate::proto::Markdown {
                    body: format!(":{}-badge[{} {}]", self.color, self.icon, self.label),
                    unterminated_parsing: false,
                    hide_anchors: false,
                    wrap: None,
                    allow_html: false,
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
