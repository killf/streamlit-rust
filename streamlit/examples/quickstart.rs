use ::streamlit::*;

fn render(st: &Streamlit) -> Result<(), WidgetError> {
    st.title("Streamlit Rust quickstart");
    let group = st.selectbox(("Group by", ["category", "region"]))?;
    let minimum = st.slider(("Minimum amount", 0_i64, 0..=200))?;
    let include = st.checkbox(("Include unknown", true))?;
    st.write(format!("Group by: {}", group.unwrap_or("none")));
    st.write(format!("Minimum amount: {minimum}"));
    st.write(format!("Include unknown: {include}"));
    Ok(())
}

#[tokio::main]
async fn main() -> std::io::Result<()> {
    // The current #[streamlit::main] macro accepts unit-returning functions.
    // Handle the fallible render once, without changing the runtime contract.
    StreamlitServer::new(
        |st| {
            Box::pin(async move {
                if let Err(error) = render(st) {
                    st.write(format!("Input error: {error}"));
                }
            })
        },
        "127.0.0.1".into(),
        8503,
    )
    .start()
    .await
}
