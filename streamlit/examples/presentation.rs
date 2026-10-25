//! Presentation demo: spinner, toast and balloons on the measured 1.66.1
//! wire. Mirrors tests/reference/presentation_app.py so the browser
//! differential compares identical pages.
use ::streamlit::*;
use std::time::Duration;

fn render(st: &Streamlit) {
    st.spinner("Loading data", || {
        std::thread::sleep(Duration::from_secs(2));
    });
    st.write("loaded");
    st.toast(ToastOptions::new("Saved successfully").icon("\u{2705}"));
    st.balloons();
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
        8511,
    )
    .start()
    .await
}
