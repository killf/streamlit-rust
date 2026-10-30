pub mod hash;

pub(crate) fn python_whitespace(character: char) -> bool {
    character.is_whitespace() || matches!(character, '\u{1c}'..='\u{1f}')
}

/// Python 3.14 dedent；帮助文本保留首尾空行，不执行 strip。
pub(crate) fn dedent_text(body: &str) -> String {
    // 1. 只按 LF 分行；Tab 与空格必须逐字节匹配，Unicode 空白行不参与缩进。
    let mut margin: Option<&str> = None;
    for line in body.split('\n').filter(|line| !line.is_empty() && !line.chars().all(python_whitespace)) {
        let prefix = &line[..line.bytes().take_while(|byte| matches!(byte, b' ' | b'\t')).count()];
        margin = Some(match margin {
            None => prefix,
            Some(previous) => &previous[..previous.bytes().zip(prefix.bytes()).take_while(|(left, right)| left == right).count()],
        });
    }

    // 2. 清空全空白行，保留正文中的 CR/Unicode 与首尾换行。
    let margin = margin.map_or(0, str::len);
    body.split('\n').map(|line| if line.chars().all(python_whitespace) { "" } else { &line[margin..] }).collect::<Vec<_>>().join("\n")
}

/// Streamlit 1.66.1 clean_text on the pinned Python 3.14 reference.
pub(crate) fn clean_text(body: &str) -> String {
    dedent_text(body).trim_matches(python_whitespace).to_owned()
}

#[cfg(test)]
mod tests {
    #[test]
    fn help_dedent_keeps_boundary_whitespace() {
        for (input, expected) in [
            ("\n    Tip\n      detail\n", "\nTip\n  detail\n"),
            ("\tTip\n    detail", "\tTip\n    detail"),
            ("  Tip\r\n    detail\r\n", "Tip\r\n  detail\r\n"),
            ("\u{2003}Tip\n\u{2003}detail", "\u{2003}Tip\n\u{2003}detail"),
            (" \t\n\u{a0}", "\n"),
        ] {
            assert_eq!(super::dedent_text(input), expected, "input: {input:?}");
        }
    }

    #[test]
    fn text_cleaning_preserves_prefix_and_line_boundaries() {
        for (input, expected) in [
            ("\n    alpha\n      beta\n    gamma\n", "alpha\n  beta\ngamma"),
            ("\talpha\n    beta", "alpha\n    beta"),
            (" \talpha\n \tbeta", "alpha\nbeta"),
            ("  alpha\n \tbeta", "alpha\n\tbeta"),
            ("  alpha\n \t \n    beta", "alpha\n\n  beta"),
            ("\n  alpha\r\n    beta\r\n", "alpha\r\n  beta"),
            ("  alpha\r    beta", "alpha\r    beta"),
            ("\u{2003}alpha\n\u{2003}beta", "alpha\n\u{2003}beta"),
            ("\u{1c}alpha\u{1f}", "alpha"),
            ("  alpha\n\u{a0}\n    beta", "alpha\n\n  beta"),
            (" \t\n\t  ", ""),
            ("\n  中文\n    🧊\n", "中文\n  🧊"),
        ] {
            assert_eq!(super::clean_text(input), expected, "input: {input:?}");
        }
    }
}
