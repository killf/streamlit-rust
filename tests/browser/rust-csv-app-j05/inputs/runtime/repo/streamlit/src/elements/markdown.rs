use crate::elements::common::*;
use crate::error::StreamlitError;
use crate::proto::streamlit::{TextAlignmentConfig, WidthConfig};
use crate::proto::{Delta, delta, delta_base_with_path, element, forward_msg};
use crate::utils::hash::hash;

#[repr(i32)]
#[allow(unused)]
#[derive(Copy, Clone, PartialEq, Eq, Hash)]
pub(crate) enum MarkdownElementType {
    Unspecified = 0,
    Native = 1,
    Caption = 2,
    Code = 3,
    Latex = 4,
    Divider = 5,
}

pub(crate) struct MarkdownElement {
    body: String,
    unsafe_allow_html: bool,
    element_type: MarkdownElementType,
    help: Option<String>,
    width: Option<ElementWidth>,
    text_alignment: Option<TextAlignment>,
}

impl MarkdownElement {
    pub fn new(body: String) -> Self {
        Self {
            body,
            unsafe_allow_html: false,
            element_type: MarkdownElementType::Unspecified,
            help: None,
            width: None,
            text_alignment: None,
        }
    }

    pub fn unsafe_allow_html(mut self, unsafe_allow_html: bool) -> Self {
        self.unsafe_allow_html = unsafe_allow_html;
        self
    }

    pub fn text_alignment(mut self, text_alignment: TextAlignment) -> Self {
        self.text_alignment = Some(text_alignment);
        self
    }

    pub fn help(mut self, value: String) -> Self {
        self.help = Some(value);
        self
    }

    pub fn width(mut self, value: ElementWidth) -> Self {
        self.width = Some(value);
        self
    }

    pub fn element_type(mut self, value: MarkdownElementType) -> Self {
        self.element_type = value;
        self
    }
}

impl Element for MarkdownElement {
    fn render(&self, context: &mut RenderContext) -> Result<(), StreamlitError> {
        let element_hash = hash(format!("markdown_{}_{:?}_{:?}_{:?}", self.body, self.unsafe_allow_html, self.width, self.text_alignment).as_str());
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
                    body: self.body.clone(),
                    unterminated_parsing: false,
                    hide_anchors: false,
                    wrap: None,
                    allow_html: self.unsafe_allow_html,
                    element_type: self.element_type as i32,
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
