//! Authentication with fake credentials: the server reads a JSON identity
//! from the x-test-user header (any HTTP client can set it — local and test
//! use only; production implements RequestAuthenticator against a real
//! identity source) and the app reads it through st.user(). Cookies follow
//! the header whitelist: this server opts in, so st.request_context()
//! reflects them.
use std::sync::Arc;

use streamlit::StreamlitApi;
use streamlit::{HeaderAuthenticator, RequestHeaderAccess, Streamlit, StreamlitServer};

fn render(st: &Streamlit) {
    st.title("Authenticated app");
    let user = st.user();
    st.code(serde_json::json!(user.to_dict()).to_string(), "json");
    let context = st.request_context();
    st.code(
        serde_json::json!({
            "user": user.to_dict(),
            "cookies": context.cookies(),
        })
        .to_string(),
        "json",
    );
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    env_logger::Builder::from_default_env().init();
    let server = StreamlitServer::new(
        |st| {
            Box::pin(async move {
                render(st);
            })
        },
        "127.0.0.1".into(),
        8592,
    )
    .with_authenticator(Arc::new(HeaderAuthenticator::new("x-test-user")))
    .with_request_headers(RequestHeaderAccess::Selected(vec!["cookie".into(), "user-agent".into()]));
    let runtime = tokio::runtime::Builder::new_multi_thread().enable_all().build()?;
    runtime.block_on(server.start())?;
    Ok(())
}
