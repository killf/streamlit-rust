//! The per-connection request context: the whitelisted WebSocket handshake
//! headers plus the st_embed flag. The default whitelist reflects only common
//! non-credential headers — the frozen Python reference
//! (tests/reference/reference-browser/context-headers) passes every handshake
//! header through, which is available via RequestHeaderAccess::All.
use ::streamlit::*;

fn render(st: &Streamlit) {
    st.title("Request context");
    let context = st.request_context();
    st.code(
        serde_json::json!({
            "headers": context.headers,
            "url": context.url,
            "locale": context.locale,
            "timezone": context.timezone,
            "timezone_offset": context.timezone_offset,
            "theme": context.theme,
            "is_embedded": context.is_embedded,
        })
        .to_string(),
        "json",
    );
    if context.is_embedded {
        st.caption("Running embedded (st_embed=true).");
    }
    // Widen what is reflected on the server builder, e.g.
    // `.with_request_headers(RequestHeaderAccess::Selected(vec!["x-trust-user".into()]))`;
    // `All` mirrors the Python behavior including credentials — trusted
    // deployments only.
}

#[main(host = "127.0.0.1", port = 8590)]
async fn main(st: &Streamlit) {
    render(st);
}
