//! Temporal/slider creation-parameter edges — the frozen temporal-params
//! reference's calls: date_input bounds and custom format, a select_slider
//! range default, and time_input's step.
use ::streamlit::*;
use streamlit::StreamlitApi;

fn render(st: &Streamlit) -> Result<(), WidgetError> {
    st.title("Temporal parameter edges");
    st.date_input(
        DateInputOptions::new("Bounded")
            .value(chrono::NaiveDate::from_ymd_opt(2024, 3, 15).ok_or(WidgetError::InvalidValue("bad date".into()))?)
            .min(chrono::NaiveDate::from_ymd_opt(2024, 1, 1).ok_or(WidgetError::InvalidValue("bad date".into()))?)
            .max(chrono::NaiveDate::from_ymd_opt(2024, 12, 31).ok_or(WidgetError::InvalidValue("bad date".into()))?)
            .key("d1"),
    )?;
    st.date_input(
        DateInputOptions::new("Formatted")
            .value(chrono::NaiveDate::from_ymd_opt(2024, 6, 1).ok_or(WidgetError::InvalidValue("bad date".into()))?)
            .format("DD/MM/YYYY")
            .key("d2"),
    )?;
    st.select_slider(SelectSliderOptions::new("Range", ["low", "mid", "high"]).default(["low", "high"]).key("s1"))?;
    st.time_input(TimeInputOptions::new("Stepped").value(chrono::NaiveTime::from_hms_opt(12, 30, 0).ok_or(WidgetError::InvalidValue("bad time".into()))?).step(900).key("t1"))?;
    Ok(())
}

#[main(host = "127.0.0.1", port = 8600)]
async fn main(st: &Streamlit) {
    if let Err(error) = render(st) {
        st.write(format!("Temporal params error: {error}"));
    }
}
