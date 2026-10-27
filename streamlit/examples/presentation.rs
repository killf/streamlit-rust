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

#[main(host = "127.0.0.1", port = 8511)]
async fn main(st: &Streamlit) {
    render(st);
}
