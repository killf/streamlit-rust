//! Write-stream demo: chunked text streamed into one growing markdown
//! element. Mirrors tests/reference/writestream_app.py.
use ::streamlit::*;
use streamlit::StreamlitApi;

fn render(st: &Streamlit) {
    st.write_stream(["The ", "quick ", "**brown** ", "fox."]);
    st.write_stream_with_cursor("▌", ["Streamed ", "with ", "a ", "cursor."]);
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
        8527,
    )
    .start()
    .await
}
