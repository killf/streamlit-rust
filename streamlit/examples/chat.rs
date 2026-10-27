//! Chat demo: chat messages and the chat input on the measured 1.66.1
//! wire. Mirrors tests/reference/chat_app.py.
use ::streamlit::*;
use streamlit::{InputWidgets, StreamlitApi};

fn render(st: &Streamlit) -> anyhow::Result<()> {
    let user = st.chat_message("user");
    user.write("hello from user");

    let assistant = st.chat_message(ChatMessageOptions::new("assistant").avatar(":material/robot:"));
    assistant.write("hello from assistant");

    if let Some(prompt) = st.chat_input("Say something")? {
        st.write(format!("echo: {prompt}"));
    }
    Ok(())
}

#[main(host = "127.0.0.1", port = 8522)]
async fn main(st: &Streamlit) {
    if let Err(error) = render(st) {
        st.write(format!("Example error: {error}"));
    }
}
