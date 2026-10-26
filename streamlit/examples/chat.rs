//! Chat demo: chat messages and the chat input on the measured 1.66.1
//! wire. Mirrors tests/reference/chat_app.py.
use ::streamlit::*;
use streamlit::{InputWidgets, StreamlitApi};

fn render(st: &Streamlit) {
    let user = st.chat_message("user");
    user.write("hello from user");

    let assistant = st.chat_message(ChatMessageOptions::new("assistant").avatar(":material/robot:"));
    assistant.write("hello from assistant");

    if let Some(prompt) = st.chat_input("Say something").unwrap() {
        st.write(format!("echo: {prompt}"));
    }
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
        8522,
    )
    .start()
    .await
}
