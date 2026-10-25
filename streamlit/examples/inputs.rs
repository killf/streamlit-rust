//! Input-widgets demo: radio, multiselect, number_input and text_area on the
//! measured 1.66.1 wire. Mirrors tests/reference/inputs_app.py so the browser
//! differential compares identical pages; the echo lines format values the
//! way Python's repr does, on purpose.
use ::streamlit::*;

fn py_option(value: &Option<String>) -> String {
    match value {
        Some(text) => format!("'{text}'"),
        None => "None".to_string(),
    }
}

fn render(st: &Streamlit) -> Result<(), WidgetError> {
    let channel = st.radio(("Channel", ["email", "sms", "push"]))?;
    let tags = st.multiselect(MultiselectOptions::new("Tags", ["alpha", "beta", "gamma"]).default_indices([0]))?;
    let count = st.number_input(("Count", 7_i64, 0..=100))?;
    let note = st.text_area(("Note", "first line\nsecond line"))?;

    let tags_repr = tags.iter().map(|tag| format!("'{tag}'")).collect::<Vec<_>>().join(", ");
    let note_repr = match &note {
        Some(text) => format!("'{}'", text.replace('\n', "\\n")),
        None => "None".to_string(),
    };
    st.write(format!("channel={}", py_option(&channel)));
    st.write(format!("tags=[{tags_repr}]"));
    st.write(format!("count={count} type=int"));
    st.write(format!("note={note_repr}"));
    Ok(())
}

#[tokio::main]
async fn main() -> std::io::Result<()> {
    StreamlitServer::new(
        |st| {
            Box::pin(async move {
                if let Err(error) = render(st) {
                    st.write(format!("Input error: {error}"));
                }
            })
        },
        "127.0.0.1".into(),
        8508,
    )
    .start()
    .await
}
