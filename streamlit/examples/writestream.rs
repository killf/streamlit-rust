//! Write-stream demo: chunked text streamed into one growing markdown
//! element. Mirrors tests/reference/writestream_app.py.
use ::streamlit::*;
use streamlit::StreamlitApi;

fn render(st: &Streamlit) {
    st.write_stream(["The ", "quick ", "**brown** ", "fox."]);
    st.write_stream_with_cursor("▌", ["Streamed ", "with ", "a ", "cursor."]);
}

#[main(host = "127.0.0.1", port = 8527)]
async fn main(st: &Streamlit) {
    render(st);
}
