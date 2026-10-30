//! code/skeleton/logo parameter edges — the frozen code-logo-params
//! reference's calls: an exotic language tag with line numbers, the default
//! skeleton, and an emoji logo at its measured default size.
use ::streamlit::*;
use streamlit::StreamlitApi;

fn render_code_text(st: &Streamlit) -> Result<(), Box<dyn std::error::Error>> {
    let bodies = [
        "",
        "\n",
        "\n\n",
        "\n\n\n",
        "\nprint('hi')\n",
        "\n\n  indented\n\n",
        "  leading\n    nested  \n",
        "\r\nwindows\r\n",
        "\rreturn\r",
        "\n spaced \r\n",
        "\talpha\n\t\tbeta\n",
        "\u{0085}line\u{2028}end\u{2029}",
        "Unicode 🤖 中文\n",
    ];
    let languages = ["python", "", "RuSt", "made-up", " "];
    let widths = [serde_json::json!("stretch"), serde_json::json!("content"), serde_json::json!(240)];
    let heights = [serde_json::json!("content"), serde_json::json!("stretch"), serde_json::json!(120)];
    let mut cases = Vec::new();
    for index in 0..bodies.len() * 2 {
        cases.push(serde_json::json!({"body": bodies[index / 2], "language": languages[index % languages.len()],
            "line_numbers": index % 2 == 1, "wrap_lines": index % 3 == 0,
            "width": widths[index % 3],
            "height": heights[index / 3 % 3]}));
    }
    cases.push(serde_json::json!({"body": "\nplain None language\n", "language": null, "line_numbers": true,
        "wrap_lines": true, "width": "content", "height": 120}));
    st.json(serde_json::json!({"code_cases": cases}));
    for case in cases {
        let width = match case["width"].as_str() {
            Some("content") => ElementWidth::Content,
            Some("stretch") => ElementWidth::Stretch,
            None => ElementWidth::Value(i32::try_from(case["width"].as_i64().ok_or("invalid code width")?)?),
            _ => return Err("unknown code width".into()),
        };
        let height = match case["height"].as_str() {
            Some("stretch") => ElementHeight::Stretch,
            Some("content") => ElementHeight::Content,
            None => ElementHeight::Value(i32::try_from(case["height"].as_i64().ok_or("invalid code height")?)?),
            _ => return Err("unknown code height".into()),
        };
        st.code_options(
            CodeOptions::new(case["body"].as_str().ok_or("missing code body")?, case["language"].as_str().unwrap_or_default())
                .line_numbers(case["line_numbers"].as_bool().ok_or("invalid line_numbers")?)
                .wrap_lines(case["wrap_lines"].as_bool().ok_or("invalid wrap_lines")?)
                .width(width)
                .height(height),
        );
    }
    Ok(())
}

fn render(st: &Streamlit) -> Result<(), Box<dyn std::error::Error>> {
    if st.query_params().get("case").as_deref() == Some("code-text") {
        return render_code_text(st);
    }
    st.title("Code skeleton logo edges");
    st.code_options(CodeOptions::new("print('hi')", "rust").line_numbers(true));
    st.skeleton(SkeletonOptions::new());
    st.logo(LogoOptions::new("🧊"));
    Ok(())
}

#[main(host = "127.0.0.1", port = 8607)]
async fn main(st: &Streamlit) {
    if let Err(error) = render(st) {
        st.write(format!("Code/skeleton/logo error: {error}"));
    }
}
