//! json/badge/feedback parameter edges — the frozen json-badge-params
//! reference's calls: st.json expanded/collapsed, badge color/icon forms,
//! and disabled feedback.
use ::streamlit::*;
use streamlit::StreamlitApi;

fn render(st: &Streamlit) -> Result<(), Box<dyn std::error::Error>> {
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
