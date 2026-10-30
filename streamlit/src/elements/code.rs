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
    pub fn new(mut code_text: String, language: String) -> Self {
        // Python 只各去掉一个边界 LF，不清理缩进、空格、CR 或其他 Unicode 空白。
        if code_text.starts_with('\n') {
            code_text.remove(0);
        }
        if code_text.ends_with('\n') {
            code_text.truncate(code_text.len() - 1);
        }

        let language = if language.is_empty() { "plaintext".to_string() } else { language };

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

#[cfg(test)]
mod tests {
    use super::CodeElement;

    #[test]
    fn code_preserves_whitespace_except_single_boundary_lfs() {
        let cases = [
            ("", ""),
            ("\n", ""),
            ("\n\n", ""),
            ("\n\n\n", "\n"),
            ("\n x\n", " x"),
            ("\n\n x\n\n", "\n x\n"),
            ("\r\nx\r\n", "\r\nx\r"),
            ("\n x \r\n", " x \r"),
            ("\talpha\n\t\tbeta\n", "\talpha\n\t\tbeta"),
            ("\u{85}line\u{2028}end\u{2029}", "\u{85}line\u{2028}end\u{2029}"),
        ];
        for (input, expected) in cases {
            let element = CodeElement::new(input.to_owned(), "python".into());
            assert_eq!(element.code_text, expected, "input {input:?}");
        }
    }

    #[test]
    fn code_empty_language_is_plaintext_and_other_tags_are_verbatim() {
        for (input, expected) in [("", "plaintext"), (" ", " "), ("RuSt", "RuSt"), ("made-up", "made-up")] {
            let element = CodeElement::new("body".into(), input.to_owned());
            assert_eq!(element.language, expected);
        }
    }
}
