//! data_editor demo: a dynamic editor over a typed two-column frame whose
//! committed edits are applied server-side. Uses the reference's values with
//! inferred nonnullable input fields; edited nulls can widen the returned schema.
use ::streamlit::*;
use std::sync::Arc;

use streamlit::data::{ArrayRef, Int64Array, RecordBatch, StringArray};

fn data_batch() -> anyhow::Result<RecordBatch> {
    Ok(RecordBatch::try_from_iter(vec![
        ("qty", Arc::new(Int64Array::from(vec![1, 2])) as ArrayRef),
        ("label", Arc::new(StringArray::from(vec!["a", "b"])) as ArrayRef),
    ])?)
}

fn render(st: &Streamlit) -> anyhow::Result<()> {
    let edited = st.data_editor(DataEditorOptions::new(&data_batch()?).num_rows(EditorRows::Dynamic).key("editor"))?;
    st.dataframe(DataframeOptions::new(&edited))?;
    st.write(format!("rows={}", edited.num_rows()));
    Ok(())
}

#[main(host = "127.0.0.1", port = 8541)]
async fn main(st: &Streamlit) {
    if let Err(error) = render(st) {
        st.write(format!("Example error: {error}"));
    }
}
