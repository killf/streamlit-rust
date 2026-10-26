//! Button-family demo: toggle, feedback, pills, segmented control,
//! pagination, menu button, download button, link button and page link on
//! the measured 1.66.1 wire. Mirrors tests/reference/buttons_app.py.
use ::streamlit::*;
use streamlit::{InputWidgets, StreamlitApi};

fn render(st: &Streamlit) {
    st.toggle(ToggleOptions::new("Night mode").key("night")).unwrap();
    st.toggle(("Sound", true)).unwrap();

    let _stars = st.feedback(FeedbackOptions::new(FeedbackKind::Stars).key("rate")).unwrap();
    st.feedback(FeedbackKind::Thumbs).unwrap();

    st.pills(ButtonGroupOptions::new("Priority", ["low", "medium", "high"]).key("priority")).unwrap();
    st.pills(ButtonGroupOptions::new("Tags", ["alpha", "beta", "gamma"]).selection_mode(SelectionMode::Multi).default(["alpha"]).key("tags")).unwrap();
    st.segmented_control(ButtonGroupOptions::new("View", ["grid", "list"]).default(["grid"]).key("view")).unwrap();

    let page = st.pagination(PaginationOptions::new(10).key("pager")).unwrap();
    st.write(format!("page={page}"));

    st.menu_button(MenuButtonOptions::new("Export", ["CSV", "JSON"]).key("export")).unwrap();

    st.download_button(DownloadButtonOptions::new("Save report", "quarterly report body").file_name("report.txt").mime("text/plain").key("save")).unwrap();
    st.link_button(LinkButtonOptions::new("Docs", "https://docs.streamlit.io").key("docs")).unwrap();
    st.page_link(PageLinkOptions::new("https://example.com").label("Example site")).unwrap();
}

#[tokio::main]
async fn main() -> std::io::Result<()> {
    StreamlitServer::new(
        |st| {
            Box::pin(async move {
                render(st);
            })
        },
        "127.0.0.1".into(),
        8523,
    )
    .start()
    .await
}
