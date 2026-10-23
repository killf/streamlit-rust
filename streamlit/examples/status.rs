use ::streamlit::*;

fn status_page(st: &Streamlit) -> Result<(), StatusError> {
    st.title("Status element reference");
    st.info("INFO-BODY plain information")?;
    st.success("SUCCESS-BODY the operation succeeded")?;
    st.warning("WARNING-BODY something needs attention")?;
    st.error("ERROR-BODY something failed")?;

    st.info("INFO-EMOJI-BODY 💡 this body starts with an emoji")?;
    st.info(StatusOptions::new("INFO-NOICON-BODY 💡 body keeps its emoji").icon(""))?;
    st.success(StatusOptions::new("SUCCESS-MATERIAL-BODY material icon").icon(":material/thumb_up:"))?;
    st.warning(StatusOptions::new("WARNING-WIDTH-BODY fixed width").width(240))?;
    st.error(StatusOptions::new("ERROR-TITLE-BODY with a title").title("ERROR-TITLE"))?;
    st.info("💡 INFO-LEADING-EMOJI this body starts with an emoji")?;
    st.info(StatusOptions::new("💡 INFO-LEADING-NOICON body keeps its emoji").icon(""))?;
    st.info(":material/thumb_up: INFO-LEADING-MATERIAL body starts with a shortcode")?;
    st.info(StatusOptions::new("INFO-ICON-ZWJ body").icon("👩‍💻"))?;
    st.info(StatusOptions::new("INFO-ICON-SKIN body").icon("👍🏽"))?;
    st.info(StatusOptions::new("INFO-ICON-FLAG body").icon("🇨🇳"))?;
    st.info("👩‍💻 INFO-LEADING-COMPOSITE body starts with a composite emoji")?;
    st.info(StatusOptions::new("**MARKDOWN-BODY** with `inline code` and [a link](https://streamlit.io)").icon(""))?;
    Ok(())
}

#[tokio::main]
async fn main() -> std::io::Result<()> {
    env_logger::Builder::from_default_env().init();
    StreamlitServer::new(|st| Box::pin(async move { status_page(st).expect("the status demo uses valid parameters") }), "127.0.0.1".to_string(), 8502)
        .start()
        .await
}
