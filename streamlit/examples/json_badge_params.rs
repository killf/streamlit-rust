//! json/badge/feedback parameter edges — the frozen json-badge-params
//! reference's calls: st.json expanded/collapsed, badge color/icon forms,
//! and disabled feedback.
use ::streamlit::*;
use streamlit::StreamlitApi;

fn render_strings(st: &Streamlit) -> Result<(), Box<dyn std::error::Error>> {
    let strings = [
        r#"{"a":1}"#,
        " \n { \"a\": 1 } \t",
        "[1, true, null]",
        r#""a string""#,
        "42",
        "true",
        "null",
        r#""""#,
        "",
        "not json",
        r#"{"unfinished":"#,
        r#"{"emoji":"🤖","中文":"值"}"#,
        "NaN",
        "Infinity",
        "{\"a\":1}\n{\"b\":2}",
    ];
    let controls = serde_json::json!([{"nested": "{\"a\": 1}", "🤖": "工具", "control": "\n\t"}, ["raw string", "🤖", {"a": 1}], null, false, 42]);

    // 1. 浏览器单例场景保留与参考 app 相同的输入和标题。
    if let Some(sample) = st.query_params().get("sample") {
        let index: usize = sample.parse()?;
        let text = strings.get(index).ok_or("unknown JSON string case")?;
        st.title(format!("JSON string {index}"));
        st.json_expanded(text, st.query_params().get("collapsed").as_deref() != Some("true"));
        return Ok(());
    }

    // 2. 完整字符串场景与固定参考的 36 个 JSON 元素保持一致。
    st.json(serde_json::json!({"string_cases": strings, "controls": controls}));
    for text in strings {
        st.json(text);
        st.json_expanded(text, false);
    }
    for value in controls.as_array().ok_or("structured controls must be an array")? {
        st.json(value);
    }
    Ok(())
}

fn render_numbers(st: &Streamlit) -> Result<(), Box<dyn std::error::Error>> {
    let texts = [
        "0.0",
        "-0.0",
        "1.0",
        "1e-4",
        "1e-5",
        "1e-6",
        "1e-7",
        "1e15",
        "1e16",
        "1e20",
        "1e21",
        "1.23e-7",
        "1.2345678901234567",
        "5e-324",
        "2.2250738585072014e-308",
        "1.7976931348623157e308",
        "NaN",
        "Infinity",
        "-Infinity",
    ];
    st.json(serde_json::json!({"number_cases": texts}));
    for text in texts {
        let value: f64 = text.parse()?;
        st.json(value);
        st.json([value]);
    }
    Ok(())
}

fn render(st: &Streamlit) -> Result<(), Box<dyn std::error::Error>> {
    if st.query_params().get("case").as_deref() == Some("numbers") {
        return render_numbers(st);
    }
    if st.query_params().get("case").as_deref() == Some("strings") {
        return render_strings(st);
    }
    st.title("Json badge feedback edges");
    st.json_expanded(serde_json::json!({"outer": {"inner": [1, 2]}}), true);
    st.json_expanded(serde_json::json!({"deep": {"a": {"b": {"c": 1}}}}), false);
    st.badge(BadgeOptions::new("New").icon(":material/rocket_launch:").color("green"));
    st.badge("Plain");
    st.feedback(FeedbackOptions::new(FeedbackKind::Thumbs).key("f1").disabled(true))?;
    Ok(())
}

#[main(host = "127.0.0.1", port = 8604)]
async fn main(st: &Streamlit) {
    if let Err(error) = render(st) {
        st.write(format!("Json/badge/feedback error: {error}"));
    }
}
