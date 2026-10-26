//! Text-family demo: the text, latex, html, iframe, snow, echo and
//! exception elements on the measured 1.66.1 wire. Mirrors
//! tests/reference/textelements_app.py.
use ::streamlit::*;
use streamlit::StreamlitApi;

fn render(st: &Streamlit) {
    st.text("plain text");
    st.sub_header("Sub header");
    st.latex("a^2 + b^2 = c^2");
    st.html("<p><b>bold</b> html</p>");
    st.iframe("https://example.com");
    st.snow();
    st.echo("st.write(\"echoed inside\")", |st| {
        st.write("echoed inside");
    });
    st.exception(ExceptionOptions::new("ValueError", "boom").trace("streamlit-rust: the application raised ValueError: boom"));
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
        8520,
    )
    .start()
    .await
}
