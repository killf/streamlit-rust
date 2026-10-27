//! Button-family demo: toggle, feedback, pills, segmented control,
//! pagination, menu button, download button, link button and page link on
//! the measured 1.66.1 wire. Mirrors tests/reference/buttons_app.py.
use ::streamlit::*;
use streamlit::{InputWidgets, StreamlitApi};

fn render(st: &Streamlit) -> anyhow::Result<()> {
    st.toggle(ToggleOptions::new("Night mode").key("night"))?;
    st.toggle(("Sound", true))?;

    let _stars = st.feedback(FeedbackOptions::new(FeedbackKind::Stars).key("rate"))?;
    st.feedback(FeedbackKind::Thumbs)?;

    st.pills(ButtonGroupOptions::new("Priority", ["low", "medium", "high"]).key("priority"))?;
    st.pills(ButtonGroupOptions::new("Tags", ["alpha", "beta", "gamma"]).selection_mode(SelectionMode::Multi).default(["alpha"]).key("tags"))?;
    st.segmented_control(ButtonGroupOptions::new("View", ["grid", "list"]).default(["grid"]).key("view"))?;

    let page = st.pagination(PaginationOptions::new(10).key("pager"))?;
    st.write(format!("page={page}"));

    st.menu_button(MenuButtonOptions::new("Export", ["CSV", "JSON"]).key("export"))?;

    st.download_button(DownloadButtonOptions::new("Save report", "quarterly report body").file_name("report.txt").mime("text/plain").key("save"))?;
    st.link_button(LinkButtonOptions::new("Docs", "https://docs.streamlit.io").key("docs"))?;
    st.page_link(PageLinkOptions::new("https://example.com").label("Example site"))?;
    Ok(())
}

#[tokio::main]
async fn main() -> std::io::Result<()> {
    StreamlitServer::new(
        |st| {
            Box::pin(async move {
                if let Err(error) = render(st) {
                    st.write(format!("Example error: {error}"));
                }
            })
        },
        "127.0.0.1".into(),
        8523,
    )
    .start()
    .await
}
