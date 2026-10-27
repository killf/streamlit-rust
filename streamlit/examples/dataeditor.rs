//! data_editor demo: a dynamic editor over a typed two-column frame whose
//! committed edits are applied server-side. Mirrors
//! tests/reference/dataeditor_app.py.
use ::streamlit::*;
use std::sync::Arc;

use streamlit::data::{DataType, Field, Int64Array, RecordBatch, Schema, StringArray};

fn data_batch() -> anyhow::Result<RecordBatch> {
    let fields = vec![Field::new("qty", DataType::Int64, true), Field::new("label", DataType::Utf8, true)];
    let arrays = vec![Arc::new(Int64Array::from(vec![1, 2])) as _, Arc::new(StringArray::from(vec!["a", "b"])) as _];
    Ok(RecordBatch::try_new(Arc::new(Schema::new(fields)), arrays)?)
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
