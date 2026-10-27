//! Datetime-input demo: the combined date-and-time picker. Mirrors
//! tests/reference/datetime_app.py.
use ::streamlit::*;

fn render(st: &Streamlit) -> anyhow::Result<()> {
    let launch = chrono::NaiveDate::from_ymd_opt(2025, 3, 15)
        .ok_or_else(|| anyhow::anyhow!("invalid example date or time"))?
        .and_hms_opt(14, 30, 0)
        .ok_or_else(|| anyhow::anyhow!("invalid example date or time"))?;
    st.datetime_input(DateTimeInputOptions::new("Launch window").value(launch).key("launch"))?;
    st.datetime_input(DateTimeInputOptions::new("Optional slot").value_none().key("slot"))?;
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
        8526,
    )
    .start()
    .await
}
