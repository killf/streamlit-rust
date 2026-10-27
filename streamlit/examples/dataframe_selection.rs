//! Select an order, view its details, and edit the returned detail table.
use ::streamlit::*;
use std::sync::Arc;

use streamlit::data::{ArrayRef, Int64Array, RecordBatch, StringArray};

fn orders() -> anyhow::Result<RecordBatch> {
    Ok(RecordBatch::try_from_iter(vec![
        ("id", Arc::new(StringArray::from(vec!["rC", "rA", "rB"])) as ArrayRef),
        ("qty", Arc::new(Int64Array::from(vec![30, 10, 20])) as ArrayRef),
        ("label", Arc::new(StringArray::from(vec!["C", "A", "B"])) as ArrayRef),
    ])?)
}

fn render(st: &Streamlit) -> anyhow::Result<()> {
    let data = orders()?;
    st.title("Order selection and editing");
    let selected = st.dataframe(
        DataframeOptions::new(&data)
            .key("orders")
            .on_select(OnSelect::Rerun)
            .selection_mode(DataframeSelectionMode::SingleRow)
            .hide_index(true)
            .width(700)
            .height(190),
    )?;

    st.try_button(ButtonOptions::new("Ordinary rerun").key("ordinary-rerun"))?;
    st.write("Selection state");
    st.code(serde_json::to_string_pretty(&selected)?, "json");

    let Some(row) = selected.as_ref().and_then(|state| state.selection.rows.first()).copied() else {
        st.write("Select an order to see its details.");
        return Ok(());
    };
    if row >= data.num_rows() {
        st.write("The selected row is no longer in the current data.");
        return Ok(());
    }

    let detail = data.slice(row, 1);
    st.write("Selected order");
    let _ = st.dataframe(&detail)?;
    st.write("Edit detail");
    let edited = st.data_editor(DataEditorOptions::new(&detail).key(format!("detail-{row}")))?;
    st.write("Edited result");
    let _ = st.dataframe(&edited)?;
    Ok(())
}

#[main(host = "127.0.0.1", port = 8544)]
async fn main(st: &Streamlit) {
    if let Err(error) = render(st) {
        st.write(format!("Selection example error: {error}"));
    }
}
