//! Query-params demo: a server-side param write, a creation-mode filtered
//! selectbox and a query-bound selectbox on the measured 1.66.1 wire.
//! Mirrors tests/reference/queryparams_app.py.
use ::streamlit::*;

fn render(st: &Streamlit) {
    st.query_params().set("mode", "demo").expect("valid param");

    let pick = st.selectbox_creation(SelectboxCreationOptions::new("Pick", ["a", "b"]).filter_mode(SelectFilterMode::Contains)).expect("valid selectbox");
    st.write(format!("pick={}", pick.as_deref().unwrap_or("a")));

    let bound = st.selectbox(SelectboxOptions::new("Bound", ["x", "y"]).key("bound").bind(TextBind::QueryParams)).expect("valid selectbox");
    st.write(format!("bound={}", bound.unwrap_or("x")));
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
        8515,
    )
    .start()
    .await
}
