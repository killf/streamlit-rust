//! The second M7 combined differential's Rust side — the interactive mirror
//! of tests/reference/combined_interactive_app.py: multi-file upload,
//! checkbox, selectbox, single-row dataframe selection, and button+toast,
//! with the report block as the oracle.
use ::streamlit::*;
use std::sync::Arc;

use streamlit::StreamlitApi;
use streamlit::data::{ArrayRef, Int64Array, LargeStringArray, RecordBatch};

fn frame() -> Result<RecordBatch, arrow_schema::ArrowError> {
    RecordBatch::try_from_iter(vec![("name", Arc::new(LargeStringArray::from(vec!["ann", "ben", "cy"])) as ArrayRef), ("score", Arc::new(Int64Array::from(vec![3, 1, 2])) as ArrayRef)])
}

fn render(st: &Streamlit) -> Result<(), Box<dyn std::error::Error>> {
    st.title("Interactive combined");
    let files = st.file_uploader(FileUploaderOptions::new("Upload").multiple_files().key("k"))?;
    let checked = st.checkbox(CheckboxOptions::new("Check").key("cb"))?;
    let picked = st.selectbox(SelectboxOptions::new("Pick", ["a", "b", "c"]).key("sel"))?;
    let selected = st.dataframe(
        DataframeOptions::new(&frame()?)
            .key("df")
            .on_select(OnSelect::Rerun)
            .selection_mode(DataframeSelectionMode::SingleRow)
            .hide_index(true)
            .width(700)
            .height(190),
    )?;
    let applied = st.try_button(ButtonOptions::new("Apply").key("go"))?;
    if applied {
        st.toast(ToastOptions::new("applied"));
    }
    let names: Vec<String> = match &files {
        UploadedFiles::Multiple(list) => {
            let mut names: Vec<String> = list.iter().map(|file| file.name().to_string()).collect();
            names.sort();
            names
        }
        UploadedFiles::Single(_) => Vec::new(),
    };
    let row = selected.as_ref().and_then(|state| state.selection.rows.first().copied());
    let report = serde_json::json!({
        "files": names,
        "checked": checked,
        "picked": picked,
        "row": row,
        "applied": applied,
    });
    st.code(serde_json::to_string(&report)?, "json");
    Ok(())
}

#[main(host = "127.0.0.1", port = 8598)]
async fn main(st: &Streamlit) {
    if let Err(error) = render(st) {
        st.write(format!("Interactive combined error: {error}"));
    }
}
