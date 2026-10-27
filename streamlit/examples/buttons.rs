//! Button-family demo: toggle, feedback, pills, segmented control,
//! pagination, menu button, download button, link button and page link on
//! the measured 1.66.1 wire. Mirrors tests/reference/buttons_app.py, with
//! additional default-byte and Unicode CSV filename download cases.
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

    st.download_button(DownloadButtonOptions::new("Save default bytes", b"id,region\nA,north\n".to_vec()).key("save-default-bytes").ignore_rerun(true))?;
    st.download_button(
        DownloadButtonOptions::new("Save Unicode CSV", b"id,region\nA,north\n".to_vec())
            .file_name("数据 é.csv")
            .mime("text/csv")
            .key("save-unicode-csv")
            .ignore_rerun(true),
    )?;
    Ok(())
}

#[main(host = "127.0.0.1", port = 8523)]
async fn main(st: &Streamlit) {
    if let Err(error) = render(st) {
        st.write(format!("Example error: {error}"));
    }
}
