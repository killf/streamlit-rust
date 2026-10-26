//! Query-params demo (part one): the server-side param write on the measured
//! 1.66.1 wire. The creation-mode/filtered and query-bound selectbox of the
//! fixture land with the selectbox upgrade round.
use ::streamlit::*;

fn render(st: &Streamlit) {
    st.query_params().set("mode", "demo").expect("valid param");

    let pick = st.selectbox(("Pick", ["a", "b"])).expect("valid selectbox");
    st.write(format!("pick={}", pick.unwrap_or("a")));

    st.write("configured");
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
