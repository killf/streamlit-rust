//! Temporal-slider regressions against the measured Python 1.66.1 wire
//! (see .codex/compatibility.md): integer epoch microseconds carried as
//! doubles, the 2000-01-01 time anchor, first-endpoint ±14-day default
//! windows for ranges, 15-minute default time steps, and microsecond-faithful
//! round trips.
use super::*;
use crate::InputWidgets;
use crate::SliderOptions;
use crate::proto;
use chrono::{NaiveDate, NaiveDateTime, NaiveTime};
use serde_json::{Value, json};

fn date(year: i32, month: u32, day: u32) -> TestResult<NaiveDate> {
    Ok(NaiveDate::from_ymd_opt(year, month, day).ok_or_else(|| format!("invalid temporal fixture date {year}-{month}-{day}"))?)
}

fn time(hour: u32, minute: u32, second: u32, micro: u32) -> TestResult<NaiveTime> {
    Ok(NaiveTime::from_hms_micro_opt(hour, minute, second, micro).ok_or_else(|| format!("invalid temporal fixture time {hour}:{minute}:{second}.{micro}"))?)
}

fn datetime(year: i32, month: u32, day: u32, hour: u32, minute: u32, second: u32, micro: u32) -> TestResult<NaiveDateTime> {
    Ok(date(year, month, day)?.and_hms_micro_opt(hour, minute, second, micro).ok_or("invalid temporal fixture datetime")?)
}

fn temporal_entry(st: &Streamlit) -> Pin<Box<dyn Future<Output = ()> + '_>> {
    Box::pin(async move {
        let result: TestResult = async {
            // The same fixtures as tests/reference/temporal_app.py, so the wire
            // below is directly comparable with the captured reference trace.
            let date_value = st.slider(SliderOptions::new("date", date(2024, 3, 15)?).key("date"))?;
            let time_value = st.slider(SliderOptions::new("time", time(12, 30, 7, 123456)?).key("time"))?;
            let datetime_value = st.slider(SliderOptions::new("datetime", datetime(2024, 3, 15, 12, 30, 7, 123456)?).key("datetime"))?;
            let date_pair = st.slider(SliderOptions::new("date-range", (date(2024, 3, 10)?, date(2024, 3, 20)?)).key("date-range"))?;
            let time_pair = st.slider(SliderOptions::new("time-range", (time(9, 15, 0, 0)?, time(17, 45, 0, 0)?)).key("time-range"))?;
            let datetime_pair = st.slider(SliderOptions::new("datetime-range", (datetime(2024, 3, 10, 9, 30, 7, 123456)?, datetime(2024, 3, 20, 17, 45, 7, 654321)?)).key("datetime-range"))?;
            st.write(
                json!({
                    "date": date_value,
                    "time": time_value,
                    "datetime": datetime_value,
                    "date_range": [date_pair.0, date_pair.1],
                    "time_range": [time_pair.0, time_pair.1],
                    "datetime_range": [datetime_pair.0, datetime_pair.1],
                })
                .to_string(),
            );

            Ok(())
        }
        .await;

        assert!(result.is_ok(), "temporal fixture must render successfully: {result:?}");
    })
}

#[derive(Default, Clone)]
struct SliderWire {
    id: String,
    min: f64,
    max: f64,
    step: f64,
    default: Vec<f64>,
    data_type: i32,
    format: String,
}

struct TemporalRun {
    sliders: std::collections::HashMap<String, SliderWire>,
    values: Value,
}

async fn run_once(stream: &mut TcpStream, session_id: &mut String, widgets: Vec<WidgetState>) -> TestResult<TemporalRun> {
    let request = BackMsg {
        r#type: Some(back_msg::Type::RerunScript(ClientState {
            widget_states: Some(WidgetStates { widgets }),
            ..Default::default()
        })),
    };
    send_binary(stream, &request.encode_to_vec()).await;
    let first = receive(stream).await;
    let Some(forward_msg::Type::NewSession(new_session)) = first.r#type else {
        panic!("a run must start with NewSession, got {:?}", first.r#type)
    };
    let init = new_session.initialize.ok_or("temporal NewSession must contain initialization")?;
    if session_id.is_empty() {
        *session_id = init.session_id;
    } else {
        assert_eq!(init.session_id, *session_id);
    }
    assert!(matches!(receive(stream).await.r#type, Some(forward_msg::Type::SessionStatusChanged(status)) if status.script_is_running));
    let mut run = TemporalRun {
        sliders: std::collections::HashMap::new(),
        values: Value::Null,
    };
    let mut finished = false;
    loop {
        match receive(stream).await.r#type {
            Some(forward_msg::Type::Delta(delta)) => {
                let Some(delta::Type::NewElement(element)) = delta.r#type else { continue };
                match element.r#type {
                    Some(element::Type::Slider(slider)) => {
                        run.sliders.insert(
                            slider.label.clone(),
                            SliderWire {
                                id: slider.id,
                                min: slider.min,
                                max: slider.max,
                                step: slider.step,
                                default: slider.default,
                                data_type: slider.data_type,
                                format: slider.format,
                            },
                        );
                    }
                    Some(element::Type::Markdown(text)) => run.values = serde_json::from_str(&text.body)?,
                    _ => {}
                }
            }
            Some(forward_msg::Type::ScriptFinished(status)) => {
                assert_eq!(status, 0);
                assert!(!finished);
                finished = true;
            }
            Some(forward_msg::Type::SessionStatusChanged(status)) if !status.script_is_running => break,
            other => panic!("unexpected lifecycle response: {other:?}"),
        }
    }
    assert!(!run.sliders.is_empty());
    assert!(!run.values.is_null());
    Ok(run)
}

fn state(run: &TemporalRun, label: &str, data: Vec<f64>) -> WidgetState {
    WidgetState {
        id: run.sliders[label].id.clone(),
        value: Some(widget_state::Value::DoubleArrayValue(proto::DoubleArray { data })),
    }
}

async fn start_server(entry: fn(&Streamlit) -> Pin<Box<dyn Future<Output = ()> + '_>>) -> TestResult<(std::net::SocketAddr, actix_web::dev::ServerHandle, tokio::task::JoinHandle<std::io::Result<()>>, TcpStream)> {
    let listener = std::net::TcpListener::bind("127.0.0.1:0")?;
    let address = listener.local_addr()?;
    let server = HttpServer::new(move || App::new().app_data(web::Data::new(StreamlitServer::new(entry, "127.0.0.1".into(), 0))).configure(configure_routes))
        .workers(1)
        .listen(listener)?
        .run();
    let handle = server.handle();
    let task = actix_web::rt::spawn(server);
    let mut stream = TcpStream::connect(address).await?;
    let request = format!("GET /_stcore/stream HTTP/1.1\r\nHost: {address}\r\nConnection: Upgrade\r\nUpgrade: websocket\r\nSec-WebSocket-Version: 13\r\nSec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==\r\nSec-WebSocket-Protocol: streamlit, test-xsrf\r\n\r\n");
    stream.write_all(request.as_bytes()).await?;
    let headers = tokio::time::timeout(Duration::from_secs(5), async {
        let mut response = Vec::new();
        while !response.ends_with(b"\r\n\r\n") {
            response.push(stream.read_u8().await?);
            assert!(response.len() < 8192);
        }
        Ok::<_, Box<dyn std::error::Error>>(String::from_utf8(response)?.to_ascii_lowercase())
    })
    .await??;
    assert!(headers.starts_with("http/1.1 101"));
    Ok((address, handle, task, stream))
}

fn assert_wire(run: &TemporalRun, label: &str, bounds_step: (f64, f64, f64), default: &[f64], wire_fields: (i32, &str)) {
    let wire = &run.sliders[label];
    assert_eq!((wire.min, wire.max, wire.step), bounds_step, "{label} bounds and step");
    assert_eq!(wire.default, default, "{label} default");
    assert_eq!((wire.data_type, wire.format.as_str()), wire_fields, "{label} enum and format");
}

#[actix_web::test]
async fn temporal_sliders_match_the_measured_wire_and_round_trip_states() -> TestResult {
    let (_address, handle, task, mut stream) = start_server(temporal_entry).await?;
    let mut session_id = String::new();

    let first = run_once(&mut stream, &mut session_id, vec![]).await?;
    // The exact numbers captured from the pinned Python 1.66.1 reference.
    assert_wire(&first, "date", (1709251200000000.0, 1711670400000000.0, 86400000000.0), &[1710460800000000.0], (3, "YYYY-MM-DD"));
    assert_wire(&first, "time", (946684800000000.0, 946771199999999.0, 900000000.0), &[946729807123456.0], (4, "HH:mm"));
    assert_wire(&first, "datetime", (1709296207123456.0, 1711715407123456.0, 86400000000.0), &[1710505807123456.0], (2, "YYYY-MM-DD"));
    // A range's default window hangs off the FIRST endpoint: value0 ± 14 days.
    assert_wire(&first, "date-range", (1708819200000000.0, 1711238400000000.0, 86400000000.0), &[1710028800000000.0, 1710892800000000.0], (3, "YYYY-MM-DD"));
    assert_wire(&first, "time-range", (946684800000000.0, 946771199999999.0, 900000000.0), &[946718100000000.0, 946748700000000.0], (4, "HH:mm"));
    assert_wire(&first, "datetime-range", (1708853407123456.0, 1711272607123456.0, 86400000000.0), &[1710063007123456.0, 1710956707654321.0], (2, "YYYY-MM-DD"));
    // First-run returns keep the microsecond components the fixture asked for.
    assert_eq!(first.values["date"], json!("2024-03-15"));
    assert_eq!(first.values["time"], json!("12:30:07.123456"));
    assert_eq!(first.values["datetime"], json!("2024-03-15T12:30:07.123456"));
    assert_eq!(first.values["date_range"], json!(["2024-03-10", "2024-03-20"]));
    assert_eq!(first.values["time_range"], json!(["09:15:00", "17:45:00"]));
    assert_eq!(first.values["datetime_range"], json!(["2024-03-10T09:30:07.123456", "2024-03-20T17:45:07.654321"]));

    // The reference's End/Home landings: a time snaps to the 15-minute grid
    // (23:45, not the off-grid 23:59:59.999999 max), dates keep midnight, and
    // datetimes keep their time-of-day and microseconds on both ends.
    let second = run_once(
        &mut stream,
        &mut session_id,
        vec![
            state(&first, "date", vec![1711670400000000.0]),
            state(&first, "time", vec![946770300000000.0]),
            state(&first, "datetime", vec![1709296207123456.0]),
            state(&first, "date-range", vec![1708819200000000.0, 1711238400000000.0]),
            state(&first, "time-range", vec![946684800000000.0, 946770300000000.0]),
            state(&first, "datetime-range", vec![1708853407123456.0, 1711272607123456.0]),
        ],
    )
    .await?;
    assert_eq!(second.values["date"], json!("2024-03-29"));
    assert_eq!(second.values["time"], json!("23:45:00"));
    assert_eq!(second.values["datetime"], json!("2024-03-01T12:30:07.123456"));
    assert_eq!(second.values["date_range"], json!(["2024-02-25", "2024-03-24"]));
    assert_eq!(second.values["time_range"], json!(["00:00:00", "23:45:00"]));
    assert_eq!(second.values["datetime_range"], json!(["2024-02-25T09:30:07.123456", "2024-03-24T09:30:07.123456"]));

    // A batch with one invalid temporal state (fractional microseconds, plus a
    // reversed range) is rejected whole: every value keeps its previous state.
    let third = run_once(
        &mut stream,
        &mut session_id,
        vec![state(&first, "time", vec![946729807123456.5]), state(&first, "date-range", vec![1710892800000000.0, 1710028800000000.0])],
    )
    .await?;
    assert_eq!(third.values["time"], json!("23:45:00"));
    assert_eq!(third.values["date_range"], json!(["2024-02-25", "2024-03-24"]));

    drop(stream);
    handle.stop(false).await;
    task.await??;

    Ok(())
}
