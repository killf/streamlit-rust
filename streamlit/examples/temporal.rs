//! Temporal sliders: date, time, datetime and their ranges on the measured
//! 1.66.1 wire. Mirrors tests/reference/temporal_app.py so the browser
//! differential compares identical pages; the echo lines format values the
//! way Python's repr does, on purpose.
use ::streamlit::*;
use chrono::{Datelike, NaiveDate, NaiveDateTime, NaiveTime, Timelike};

fn py_date(value: NaiveDate) -> String {
    format!("datetime.date({}, {}, {})", value.year(), value.month(), value.day())
}

fn py_time(value: NaiveTime) -> String {
    let micro = value.nanosecond() / 1_000;
    let mut text = format!("datetime.time({}, {}", value.hour(), value.minute());
    if value.second() != 0 || micro != 0 {
        text += &format!(", {}", value.second());
        if micro != 0 {
            text += &format!(", {micro}");
        }
    }
    text + ")"
}

fn py_datetime(value: NaiveDateTime) -> String {
    let time = value.time();
    let micro = time.nanosecond() / 1_000;
    let mut text = format!("datetime.datetime({}, {}, {}", value.year(), value.month(), value.day());
    if time.hour() != 0 || time.minute() != 0 || time.second() != 0 || time.nanosecond() != 0 {
        text += &format!(", {}, {}", time.hour(), time.minute());
        if time.second() != 0 || micro != 0 {
            text += &format!(", {}", time.second());
            if micro != 0 {
                text += &format!(", {micro}");
            }
        }
    }
    text + ")"
}

fn render(st: &Streamlit) {
    let date_value = st.slider(SliderOptions::new("date", NaiveDate::from_ymd_opt(2024, 3, 15).unwrap())).unwrap();
    let time_value = st.slider(SliderOptions::new("time", NaiveTime::from_hms_micro_opt(12, 30, 7, 123456).unwrap())).unwrap();
    let datetime_value = st.slider(SliderOptions::new("datetime", NaiveDate::from_ymd_opt(2024, 3, 15).unwrap().and_hms_micro_opt(12, 30, 7, 123456).unwrap())).unwrap();
    let date_pair = st.slider(SliderOptions::new("date-range", (NaiveDate::from_ymd_opt(2024, 3, 10).unwrap(), NaiveDate::from_ymd_opt(2024, 3, 20).unwrap()))).unwrap();
    let time_pair = st.slider(SliderOptions::new("time-range", (NaiveTime::from_hms_opt(9, 15, 0).unwrap(), NaiveTime::from_hms_opt(17, 45, 0).unwrap()))).unwrap();
    let datetime_pair = st
        .slider(SliderOptions::new(
            "datetime-range",
            (
                NaiveDate::from_ymd_opt(2024, 3, 10).unwrap().and_hms_micro_opt(9, 30, 7, 123456).unwrap(),
                NaiveDate::from_ymd_opt(2024, 3, 20).unwrap().and_hms_micro_opt(17, 45, 7, 654321).unwrap(),
            ),
        ))
        .unwrap();

    st.write(format!("date={}|date", py_date(date_value)));
    st.write(format!("time={}|time", py_time(time_value)));
    st.write(format!("datetime={}|datetime", py_datetime(datetime_value)));
    st.write(format!("date_pair=({}, {})|tuple", py_date(date_pair.0), py_date(date_pair.1)));
    st.write(format!("time_pair=({}, {})|tuple", py_time(time_pair.0), py_time(time_pair.1)));
    st.write(format!("datetime_pair=({}, {})|tuple", py_datetime(datetime_pair.0), py_datetime(datetime_pair.1)));
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
        8506,
    )
    .start()
    .await
}
