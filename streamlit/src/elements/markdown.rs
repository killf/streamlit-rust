use crate::elements::common::*;
use crate::error::StreamlitError;
use crate::proto::streamlit::{TextAlignmentConfig, WidthConfig};
use crate::proto::{Delta, delta, delta_base_with_path, element, forward_msg};
use crate::utils::clean_text;
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
    unterminated_parsing: bool,
    wrap: Option<bool>,
}

impl MarkdownElement {
    pub fn new(body: String) -> Self {
        Self {
            body: clean_text(&body),
            unsafe_allow_html: false,
            element_type: MarkdownElementType::Native,
            help: None,
            width: None,
            text_alignment: None,
            unterminated_parsing: false,
            wrap: Some(true),
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

    /// Text wrapping; None leaves the field unset (measured unset on
    /// latex, divider, and badge markdown).
    pub(crate) fn wrap(mut self, value: Option<bool>) -> Self {
        self.wrap = value;
        self
    }

    pub fn element_type(mut self, value: MarkdownElementType) -> Self {
        self.element_type = value;
        self
    }

    /// Keep unclosed markdown syntax renderable mid-stream, like the
    /// reference's write_stream intermediates.
    pub fn unterminated(mut self) -> Self {
        self.unterminated_parsing = true;
        self
    }
}

impl Element for MarkdownElement {
    fn render(&self, context: &mut RenderContext) -> Result<(), StreamlitError> {
        let element_hash = hash(format!("markdown_{}_{:?}_{:?}_{:?}_{}_{:?}", self.body, self.unsafe_allow_html, self.width, self.text_alignment, self.unterminated_parsing, self.wrap).as_str());
        let mut msg = delta_base_with_path(context.delta_path.clone(), context.active_script_hash.clone(), element_hash);

        let width_config: Option<WidthConfig> = self.width.clone().map(Into::into);
        // LaTeX 参考不发送对齐配置；其余既有路径保留默认 LEFT。
        let text_alignment_config: Option<TextAlignmentConfig> = if matches!(self.element_type, MarkdownElementType::Latex) {
            None
        } else {
            Some(self.text_alignment.clone().map(Into::into).unwrap_or_else(|| TextAlignment::Left.into()))
        };

        msg.r#type = Some(forward_msg::Type::Delta(Delta {
            fragment_id: String::new(),
            r#type: Some(delta::Type::NewElement(crate::proto::Element {
                has_one_shot_effect: None,
                height_config: None,
                width_config,
                text_alignment_config,
                r#type: Some(element::Type::Markdown(crate::proto::Markdown {
                    body: self.body.clone(),
                    unterminated_parsing: self.unterminated_parsing,
                    hide_anchors: false,
                    wrap: self.wrap,
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
