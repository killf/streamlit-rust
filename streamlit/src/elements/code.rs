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
        // 官方前端按 hash 复用整个 Element，即使 cacheable=false，高度也必须参与身份。
        // Debug 元组为字符串字段保留边界和转义，避免正文/语言中的下划线产生相同输入。
        let identity = (&self.code_text, &self.language, self.show_line_numbers, self.wrap_lines, &self.width, &self.height, &self.text_alignment);
        let element_hash = hash(&format!("code_{identity:?}"));
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
    use super::{CodeElement, Element, ElementHeight, RenderContext};

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

    #[test]
    fn height_changes_invalidate_code_element_hash() -> Result<(), Box<dyn std::error::Error>> {
        let mut hashes = Vec::new();
        for height in [120, 240, 120] {
            let (sender, _receiver) = tokio::sync::mpsc::unbounded_channel();
            let mut context = RenderContext::with_sender("code-height".into(), sender);
            context.delta_path = vec![0, 0];
            CodeElement::new("print('same body')".into(), "python".into()).height(ElementHeight::Value(height)).render(&mut context)?;
            assert_eq!(context.stream.len(), 1);
            hashes.push(context.stream.pop().ok_or("missing code message")?.hash);
        }

        assert!(!hashes[0].is_empty());
        assert_ne!(hashes[0], hashes[1], "height-only changes must replace the previous frontend element");
        assert_eq!(hashes[0], hashes[2], "restoring the same code/layout restores its hash");
        Ok(())
    }

    #[test]
    fn code_body_and_language_boundaries_cannot_alias() -> Result<(), Box<dyn std::error::Error>> {
        let cases = [("left_right", "python", "left", "right_python"), ("a_\"b", "c", "a", "\"b_c"), ("🤖_工具", "python", "🤖", "工具_python")];
        for (body, language, other_body, other_language) in cases {
            let mut hashes = Vec::new();
            for (text, tag) in [(body, language), (other_body, other_language), (body, language)] {
                let (sender, _receiver) = tokio::sync::mpsc::unbounded_channel();
                let mut context = RenderContext::with_sender("code-identity".into(), sender);
                context.delta_path = vec![0, 0];
                CodeElement::new(text.into(), tag.into()).render(&mut context)?;
                hashes.push(context.stream.pop().ok_or("missing code identity message")?.hash);
            }

            assert_ne!(hashes[0], hashes[1], "distinct body/language fields must not alias");
            assert_eq!(hashes[0], hashes[2]);
        }
        Ok(())
    }
}
