use ::streamlit::*;

fn status_error_contract(st: &Streamlit) -> Result<(), Box<dyn std::error::Error>> {
    let mut cases: Vec<serde_json::Value> = serde_json::from_str(
        r#"[
  {"icon": "🔥💡", "width": 0},
  {"icon": "👩‍x", "width": "bogus"},
  {"icon": "bad", "width": -1},
  {"icon": " :material/not_a_real_icon: ", "width": "bogus"},
  {"icon": ":material/Thumb_UP:", "width": 0},
  {"icon": ":material/thumb_up", "width": 0},
  {"icon": ":smile:", "width": 0},
  {"icon": "http://example.invalid/icon.png", "width": 0},
  {"icon": " spinner ", "width": 240},
  {"icon": "", "width": 0},
  {"icon": "🧊", "width": "bogus"},
  {"icon": "  ", "width": "content"},
  {"icon": "🧊", "width": 1},
  {"icon": "spinner", "width": 1},
  {"icon": ":material/thumb_up:", "width": 1},
  {"icon": ":material/not_a_real_icon:", "width": 1},
  {"icon": "not-an-icon", "width": 1},
  {"icon": ":+1:", "width": 1},
  {"icon": "https://example.invalid/xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx", "width": 1},
  {"icon": "🧊", "width": "'quoted"}
]"#,
    )?;
    for width in [
        "plain",
        "'quoted",
        "\"quoted",
        "'both\"",
        "slash\\end",
        "line\nnext",
        "\t\r\0",
        "\u{1f}\u{7f}",
        "中文🧊",
        "e\u{301}",
        "\u{a0}",
        "\u{2003}",
        "\u{200d}",
        "\u{e000}",
        "\u{378}",
        "\u{e0000}",
        "\u{2028}",
        "\u{85}",
    ] {
        cases.push(serde_json::json!({"icon": "🧊", "width": width}));
    }

    st.json(serde_json::json!({"error_cases": cases}));
    for (index, kwargs) in cases.iter().enumerate() {
        for kind in ["info", "success", "warning", "error"] {
            let mut options = StatusOptions::new("error boundary").icon(kwargs["icon"].as_str().ok_or("missing error icon")?);
            if let Some(width) = kwargs["width"].as_str() {
                options = options.width(width);
            } else {
                options = options.width(i32::try_from(kwargs["width"].as_i64().ok_or("missing error width")?)?);
            }
            let result = match kind {
                "info" => st.info(options),
                "success" => st.success(options),
                "warning" => st.warning(options),
                "error" => st.error(options),
                _ => return Err("unknown alert kind".into()),
            };
            let result = match result {
                Ok(()) => serde_json::json!({"index": index, "kind": kind, "returned": true}),
                Err(error) => serde_json::json!({"index": index, "kind": kind, "category": match &error { StatusError::InvalidWidth(_) => "width", StatusError::InvalidIcon(_) => "icon" }, "message": error.to_string()}),
            };
            st.json(result);
        }
    }
    Ok(())
}

fn status_normalization(st: &Streamlit) -> Result<(), Box<dyn std::error::Error>> {
    let inputs: serde_json::Value = serde_json::from_str(
        r#"{
  "alert_cases": [
    {"body": "\n    alpha\n      beta\n", "kwargs": {"title": "\n  Title\n    detail\n"}},
    {"body": "\n    💡 alpha\n      beta\n", "kwargs": {"width": 240}},
    {"body": "\n    :material/thumb_up: alpha\n      beta\n", "kwargs": {"title": "\tTitle\n    detail"}},
    {"body": " \t💡 keep \n", "kwargs": {"icon": "", "width": 240}},
    {"body": " \t💡 keep \n", "kwargs": {"icon": " \t\n"}},
    {"body": "  body\r\n    next  ", "kwargs": {"icon": " 🧊 ", "width": 240}},
    {"body": " \u001cbody\u001f ", "kwargs": {"icon": "\u001c👩‍💻\u001f", "title": "\u001cTitle\u001f"}},
    {"body": "\u2003alpha\n\u2003beta", "kwargs": {"width": 240}},
    {"body": "💡\u001cafter", "kwargs": {}},
    {"body": " \t\n ", "kwargs": {"title": " \t\n ", "width": 240}},
    {"body": "plain [x] **bold**", "kwargs": {"icon": " :material/warning: "}},
    {"body": "\tfirst\n    second", "kwargs": {"title": "\n    **Title**\n", "width": 240}}
  ]
}"#,
    )?;
    st.json(inputs.clone());
    let mut results = Vec::new();
    for (index, case) in inputs["alert_cases"].as_array().ok_or("missing alert cases")?.iter().enumerate() {
        for kind in ["info", "success", "warning", "error"] {
            let kwargs = &case["kwargs"];
            let mut options = StatusOptions::new(case["body"].as_str().ok_or("missing alert body")?);
            if let Some(icon) = kwargs["icon"].as_str() {
                options = options.icon(icon);
            }
            if let Some(title) = kwargs["title"].as_str() {
                options = options.title(title);
            }
            if kwargs["width"] == 240 {
                options = options.width(240);
            }
            let result = match kind {
                "info" => st.info(options),
                "success" => st.success(options),
                "warning" => st.warning(options),
                "error" => st.error(options),
                _ => return Err("unknown alert kind".into()),
            };
            results.push(match result {
                Ok(()) => serde_json::json!({"index": index, "kind": kind, "returned": true}),
                Err(error) => serde_json::json!({"index": index, "kind": kind, "error": error.to_string()}),
            });
        }
    }
    st.json(serde_json::json!({"results": results}));
    Ok(())
}

fn status_page(st: &Streamlit) -> Result<(), StatusError> {
    st.title("Status element reference");
    st.info("INFO-BODY plain information")?;
    st.success("SUCCESS-BODY the operation succeeded")?;
    st.warning("WARNING-BODY something needs attention")?;
    st.error("ERROR-BODY something failed")?;

    st.info("INFO-EMOJI-BODY 💡 this body starts with an emoji")?;
    st.info(StatusOptions::new("INFO-NOICON-BODY 💡 body keeps its emoji").icon(""))?;
    st.success(StatusOptions::new("SUCCESS-MATERIAL-BODY material icon").icon(":material/thumb_up:"))?;
    st.warning(StatusOptions::new("WARNING-WIDTH-BODY fixed width").width(240))?;
    st.error(StatusOptions::new("ERROR-TITLE-BODY with a title").title("ERROR-TITLE"))?;
    st.info("💡 INFO-LEADING-EMOJI this body starts with an emoji")?;
    st.info(StatusOptions::new("💡 INFO-LEADING-NOICON body keeps its emoji").icon(""))?;
    st.info(":material/thumb_up: INFO-LEADING-MATERIAL body starts with a shortcode")?;
    st.info(StatusOptions::new("INFO-ICON-ZWJ body").icon("👩‍💻"))?;
    st.info(StatusOptions::new("INFO-ICON-SKIN body").icon("👍🏽"))?;
    st.info(StatusOptions::new("INFO-ICON-FLAG body").icon("🇨🇳"))?;
    st.info("👩‍💻 INFO-LEADING-COMPOSITE body starts with a composite emoji")?;
    st.info(StatusOptions::new("**MARKDOWN-BODY** with `inline code` and [a link](https://streamlit.io)").icon(""))?;
    Ok(())
}

#[main(host = "127.0.0.1", port = 8502)]
async fn main(st: &Streamlit) {
    if st.query_params().get("case").as_deref() == Some("error-contract") {
        if let Err(error) = status_error_contract(st) {
            st.exception(ExceptionOptions::new("StatusDiagnosticError", error.to_string()));
        }
        return;
    }

    if st.query_params().get("case").as_deref() == Some("normalization") {
        if let Err(error) = status_normalization(st) {
            st.exception(ExceptionOptions::new("StatusDiagnosticError", error.to_string()));
        }
        return;
    }

    status_page(st).expect("the status demo uses valid parameters")
}
