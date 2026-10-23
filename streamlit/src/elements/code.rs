use crate::elements::common::*;
use crate::error::StreamlitError;
use crate::proto::streamlit::{HeightConfig, TextAlignmentConfig, WidthConfig};
use crate::proto::{Delta, delta, delta_base_with_path, element, forward_msg};
use crate::utils::hash::hash;

pub(crate) struct CodeElement {
    code_text: String,
    language: String,
    show_line_numbers: bool,
    wrap_lines: bool,
    width: Option<ElementWidth>,
    height: Option<ElementHeight>,
    text_alignment: Option<TextAlignment>,
}

impl CodeElement {
    pub fn new(code_text: String, language: String) -> Self {
        Self {
            code_text,
            language,
            show_line_numbers: false,
            wrap_lines: false,
            width: None,
            height: None,
            text_alignment: None,
        }
    }

    pub fn show_line_numbers(mut self, value: bool) -> Self {
        self.show_line_numbers = value;
        self
    }

    pub fn wrap_lines(mut self, value: bool) -> Self {
        self.wrap_lines = value;
        self
    }

    pub fn width(mut self, width: ElementWidth) -> Self {
        self.width = Some(width);
        self
    }

    pub fn height(mut self, height: ElementHeight) -> Self {
        self.height = Some(height);
        self
    }
}

impl Element for CodeElement {
    fn render(&self, context: &mut RenderContext) -> Result<(), StreamlitError> {
        let element_hash = hash(format!("code_{}_{}_{}_{}_{:?}_{:?}", self.code_text, self.language, self.show_line_numbers, self.wrap_lines, self.width, self.text_alignment).as_str());
        let mut msg = delta_base_with_path(context.delta_path.clone(), context.active_script_hash.clone(), element_hash);

        let width_config: Option<WidthConfig> = self.width.clone().map(Into::into);
        let height_config: Option<HeightConfig> = self.height.clone().map(Into::into);
        let text_alignment_config: Option<TextAlignmentConfig> = self.text_alignment.clone().map(Into::into);

        msg.r#type = Some(forward_msg::Type::Delta(Delta {
            fragment_id: String::new(),
            r#type: Some(delta::Type::NewElement(crate::proto::Element {
                has_one_shot_effect: None,
                height_config,
                width_config,
                text_alignment_config,
                r#type: Some(element::Type::Code(crate::proto::Code {
                    code_text: self.code_text.clone(),
                    language: self.language.clone(),
                    show_line_numbers: self.show_line_numbers,
                    wrap_lines: self.wrap_lines,
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
