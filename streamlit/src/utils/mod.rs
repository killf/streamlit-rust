pub mod hash;

/// Streamlit 1.66.1 clean_text on the pinned Python 3.14 reference.
pub(crate) fn clean_text(body: &str) -> String {
    // 1. 只按 LF 分行；Tab 与空格必须逐字节匹配，Unicode 空白行不参与缩进。
    let whitespace = |character: char| character.is_whitespace() || matches!(character, '\u{1c}'..='\u{1f}');
    let mut margin: Option<&str> = None;
    for line in body.split('\n').filter(|line| !line.is_empty() && !line.chars().all(whitespace)) {
        let prefix = &line[..line.bytes().take_while(|byte| matches!(byte, b' ' | b'\t')).count()];
        margin = Some(match margin {
            None => prefix,
            Some(previous) => &previous[..previous.bytes().zip(prefix.bytes()).take_while(|(left, right)| left == right).count()],
        });
    }

    // 2. 清空全空白行，保留正文中的 CR/Unicode；最后按 Python 空白定义 strip。
    let margin = margin.map_or(0, str::len);
    let cleaned = body.split('\n').map(|line| if line.chars().all(whitespace) { "" } else { &line[margin..] }).collect::<Vec<_>>().join("\n");
    cleaned.trim_matches(whitespace).to_owned()
}

#[cfg(test)]
mod tests {
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
