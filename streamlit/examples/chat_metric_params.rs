//! Chat/metric/progress parameter edges — the frozen chat-metric-params
//! reference's calls: an emoji chat avatar, the metric no-delta/zero/off/
//! negative rules, and progress with a text label.
use ::streamlit::*;
use streamlit::StreamlitApi;

fn render(st: &Streamlit) -> Result<(), Box<dyn std::error::Error>> {
    st.title("Chat metric progress edges");
    let message = st.chat_message(ChatMessageOptions::new("Helper").avatar("🛠️"));
    message.write("inside");
    st.metric(MetricOptions::new("No delta", "42"));
    st.metric(MetricOptions::new("Zero delta", "5").delta("0"));
    st.metric(MetricOptions::new("Gray", "7").delta("3").delta_color(DeltaColor::Off));
    st.metric(MetricOptions::new("Negative", "9").delta("-2"));
    st.progress_options(ProgressOptions::new(50).text("Halfway there"))?;
    Ok(())
}

#[main(host = "127.0.0.1", port = 8602)]
async fn main(st: &Streamlit) {
    if let Err(error) = render(st) {
        st.write(format!("Chat/metric/progress error: {error}"));
    }
}
