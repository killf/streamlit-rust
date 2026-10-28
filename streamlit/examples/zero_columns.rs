//! Zero-column data views: a checkbox toggles between 0- and 2-row Arrow
//! batches with no physical columns. Under the accepted virtual RangeIndex
//! presentation the dataframe, both fixed editors, and the index-showing
//! table render the row numbers; the same inputs error or render an empty
//! frame on the pinned Python 1.66.1 reference (see
//! tests/reference/reference-browser/zero-columns/README.md).
use ::streamlit::*;
use std::sync::Arc;

use streamlit::data::{ArrayRef, Int64Array, RecordBatch};

// Mirrors the Python fixture: build a one-column frame, then drop the
// column. Projection keeps the explicit row count; there is no column left.
fn zero_column(two: bool) -> Result<RecordBatch, streamlit::data::DataError> {
    let values = if two { vec![1, 2] } else { vec![] };
    let source = RecordBatch::try_from_iter(vec![("drop", Arc::new(Int64Array::from(values)) as ArrayRef)])?;
    Ok(source.project(&[])?)
}

#[main(host = "127.0.0.1", port = 8580)]
async fn main(st: &Streamlit) {
    let result: Result<(), Box<dyn std::error::Error>> = (|| {
        st.title("Zero-column data");
        let two = st.checkbox(CheckboxOptions::from(("Two rows", false)).key("zero-two"))?;
        let data = zero_column(two)?;
        st.caption(format!("zero-input rows={} columns={}", data.num_rows(), data.num_columns()));
        st.caption("zero-case=dataframe");
        st.dataframe(&data)?;
        st.caption("zero-case=editor-disabled-fixed");
        let disabled = st.data_editor(DataEditorOptions::new(&data).disabled(true).num_rows(EditorRows::Fixed).key("zero-disabled"))?;
        st.caption(format!("zero-return=disabled rows={} columns={}", disabled.num_rows(), disabled.num_columns()));
        st.caption("zero-case=editor-fixed");
        let enabled = st.data_editor(DataEditorOptions::new(&data).num_rows(EditorRows::Fixed).key("zero-editor"))?;
        st.caption(format!("zero-return=enabled rows={} columns={}", enabled.num_rows(), enabled.num_columns()));
        st.caption("zero-case=table-index");
        st.table(TableOptions::new(&data).hide_index(false))?;
        st.button(ButtonOptions::new("Ordinary rerun").key("zero-rerun"));
        Ok(())
    })();
    if let Err(error) = result {
        st.write(format!("Zero-column example error: {error}"));
    }
}
