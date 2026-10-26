//! Datetime-input demo: the combined date-and-time picker. Mirrors
//! tests/reference/datetime_app.py.
use ::streamlit::*;

fn render(st: &Streamlit) {
    let launch = chrono::NaiveDate::from_ymd_opt(2025, 3, 15).unwrap().and_hms_opt(14, 30, 0).unwrap();
    st.datetime_input(DateTimeInputOptions::new("Launch window").value(launch).key("launch")).unwrap();
    st.datetime_input(DateTimeInputOptions::new("Optional slot").value_none().key("slot")).unwrap();
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
        8526,
    )
    .start()
    .await
}
