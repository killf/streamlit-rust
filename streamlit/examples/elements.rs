//! Elements parity demo: the fifteen display, layout, form and data APIs of
//! the elements differential chain. Mirrors tests/reference/elements_app.py
//! so the browser differential compares identical pages; the form echo line
//! formats values the way Python's repr does, on purpose.
use ::streamlit::*;
use arrow_array::{Int64Array, RecordBatch, StringArray};
use arrow_schema::{DataType, Field, Schema};
use std::sync::Arc;

fn batch() -> RecordBatch {
    RecordBatch::try_new(
        Arc::new(Schema::new(vec![Field::new("kind", DataType::Utf8, false), Field::new("count", DataType::Int64, false)])),
        vec![Arc::new(StringArray::from(vec!["a", "b"])), Arc::new(Int64Array::from(vec![1, 2]))],
    )
    .unwrap()
}

fn render(st: &Streamlit) {
    st.title("Elements parity title");
    st.header("Header level");
    st.caption(CaptionOptions::new("A caption line"));
    st.badge(BadgeOptions::new("BETA"));
    st.divider();
    st.code("print('hello')", "python");
    st.markdown("**bold** and `inline`");
    st.write("plain write");

    if let [left, right] = st.columns(2) {
        left.write("left column");
        right.write("right column");
    }

    let container = st.container();
    container.write("inside container");

    let (note, submitted) = st
        .form(FormOptions::new("note_form"), |form| {
            let note = form.text_input(TextInputOptions::new("Note").value("hello"))?;
            let submitted = form.form_submit_button(FormSubmitButtonOptions::new("Apply"))?;
            Ok::<_, WidgetError>((note, submitted))
        })
        .unwrap();
    let note_repr = match &note {
        Some(text) => format!("'{text}'"),
        None => "None".to_string(),
    };
    let submitted_repr = if submitted { "True" } else { "False" };
    st.write(format!("form: note={note_repr} submitted={submitted_repr}"));

    let data = batch();
    st.table(&data).unwrap();
    st.bar_chart(BarChartOptions::new(&data, "kind", "count")).unwrap();
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
        8507,
    )
    .start()
    .await
}
