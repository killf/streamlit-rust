//! Picker demo: date input (single and range), time input, color picker,
//! select sliders (single and range) and the audio/camera inputs on the
//! measured 1.66.1 wire. Mirrors tests/reference/pickers_app.py.
use ::streamlit::*;
use streamlit::InputWidgets;

fn render(st: &Streamlit) -> anyhow::Result<()> {
    use chrono::NaiveDate;

    let start = NaiveDate::from_ymd_opt(2025, 1, 15).ok_or_else(|| anyhow::anyhow!("invalid example date or time"))?;
    st.date_input(DateInputOptions::new("Start date").value(start).key("start"))?;
    st.date_input(
        DateInputOptions::new("Window")
            .value_range(start, NaiveDate::from_ymd_opt(2025, 2, 15).ok_or_else(|| anyhow::anyhow!("invalid example date or time"))?)
            .key("window"),
    )?;

    st.time_input(
        TimeInputOptions::new("Meeting")
            .value(chrono::NaiveTime::from_hms_opt(14, 30, 0).ok_or_else(|| anyhow::anyhow!("invalid example date or time"))?)
            .key("meeting"),
    )?;

    st.color_picker(ColorPickerOptions::new("Accent").value("#FF5733").key("accent"))?;

    st.select_slider(SelectSliderOptions::new("Pick one", ["low", "medium", "high"]).key("one"))?;
    st.select_slider(SelectSliderOptions::new("Pick range", ["a", "b", "c", "d"]).default(["b", "d"]).key("range"))?;

    st.audio_input(AudioInputOptions::new("Voice note").key("voice"))?;
    st.camera_input(CameraInputOptions::new("Snapshot").key("shot"))?;
    Ok(())
}

#[tokio::main]
async fn main() -> std::io::Result<()> {
    StreamlitServer::new(
        |st| {
            Box::pin(async move {
                if let Err(error) = render(st) {
                    st.write(format!("Example error: {error}"));
                }
            })
        },
        "127.0.0.1".into(),
        8524,
    )
    .start()
    .await
}
