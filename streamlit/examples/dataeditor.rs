//! data_editor demo: a dynamic editor over a typed two-column frame whose
//! committed edits are applied server-side. Mirrors
//! tests/reference/dataeditor_app.py.
use ::streamlit::*;
use std::sync::Arc;

use streamlit::data::{DataType, Field, Int64Array, RecordBatch, Schema, StringArray};

fn data_batch() -> RecordBatch {
    let fields = vec![Field::new("qty", DataType::Int64, true), Field::new("label", DataType::Utf8, true)];
    let arrays = vec![Arc::new(Int64Array::from(vec![1, 2])) as _, Arc::new(StringArray::from(vec!["a", "b"])) as _];
    RecordBatch::try_new(Arc::new(Schema::new(fields)), arrays).unwrap()
}

fn render(st: &Streamlit) {
    let edited = st.data_editor(DataEditorOptions::new(&data_batch()).num_rows(EditorRows::Dynamic).key("editor")).unwrap();
    st.dataframe(DataframeOptions::new(&edited)).unwrap();
    st.write(format!("rows={}", edited.num_rows()));
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
        8541,
    )
    .start()
    .await
}
