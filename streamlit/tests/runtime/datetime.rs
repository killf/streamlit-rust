//! Datetime-input regression against the measured Python 1.66.1 wire (see
//! .codex/compatibility.md, Picker inputs / datetime): st.datetime_input
//! carries its ISO "YYYY-MM-DDTHH:MM" default, the ten-year min/max window
//! around the value's date (min at 00:00, max at 23:59), the 15-minute step
//! and the YYYY/MM/DD display format; a None-valued picker carries no
//! default and anchors its window on today. Its state is a string array of
//! one ISO datetime (empty = cleared).
use super::*;
use crate::InputWidgets;
use crate::proto;
use crate::proto::element;
use crate::proto::forward_msg;
use crate::proto::widget_state::Value as WireValue;

fn datetime_entry(st: &Streamlit) -> Pin<Box<dyn Future<Output = ()> + '_>> {
    Box::pin(async move {
        let result: TestResult = async {
            // Mirrors tests/reference/datetime_app.py.
            let launch = chrono::NaiveDate::from_ymd_opt(2025, 3, 15)
                .ok_or("datetime fixture date 2025-03-15 must exist")?
                .and_hms_opt(14, 30, 0)
                .ok_or("datetime fixture time 14:30 must exist")?;
            st.datetime_input(crate::DateTimeInputOptions::new("Launch window").value(launch).key("launch"))?;
            st.datetime_input(crate::DateTimeInputOptions::new("Optional slot").value_none().key("slot"))?;

            Ok(())
        }
        .await;

        assert!(result.is_ok(), "datetime fixture must render successfully: {result:?}");
    })
}

#[actix_web::test]
async fn datetime_input_matches_the_measured_wire() -> TestResult {
    let listener = std::net::TcpListener::bind("127.0.0.1:0")?;
    let address = listener.local_addr()?;
    let server = HttpServer::new(move || App::new().app_data(web::Data::new(StreamlitServer::new(datetime_entry, "127.0.0.1".into(), 0))).configure(configure_routes))
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
        }
        Ok::<_, Box<dyn std::error::Error>>(String::from_utf8(response)?.to_ascii_lowercase())
    })
    .await??;
    assert!(headers.starts_with("http/1.1 101"));

    send_binary(
        &mut stream,
        &(BackMsg {
            r#type: Some(back_msg::Type::RerunScript(ClientState::default())),
        })
        .encode_to_vec(),
    )
    .await;

    // The None picker's window anchors on today, computed with the same
    // shift the emitter uses so the assertion stays date-independent.
    let today = chrono::Local::now().date_naive();
    let shift = |date: chrono::NaiveDate, years: i32| {
        use chrono::Datelike;
        chrono::NaiveDate::from_ymd_opt(date.year() + years, date.month(), date.day())
            .or_else(|| chrono::NaiveDate::from_ymd_opt(date.year() + years, date.month(), (date.day() - 1).max(1)))
            .expect("a shifted date always exists")
    };
    let expected_slot_min = format!("{}T00:00", shift(today, -10).format("%Y-%m-%d"));
    let expected_slot_max = format!("{}T23:59", shift(today, 10).format("%Y-%m-%d"));

    let mut timeline: Vec<String> = Vec::new();
    loop {
        let message = receive(&mut stream).await;
        match message.r#type {
            Some(forward_msg::Type::NewSession(_)) => {}
            Some(forward_msg::Type::SessionStatusChanged(status)) if !status.script_is_running => break,
            Some(forward_msg::Type::Delta(delta)) => {
                let Some(delta::Type::NewElement(element)) = delta.r#type else { continue };
                let Some(kind) = element.r#type else { continue };
                if let element::Type::DateTimeInput(datetime) = kind {
                    timeline.push(format!("datetime:{}:{:?}:{}:{}:{}:{}:{}", datetime.label, datetime.default, datetime.min, datetime.max, datetime.step, datetime.format, datetime.is_range));
                }
            }
            Some(forward_msg::Type::ScriptFinished(status)) => assert_eq!(status, 0),
            Some(forward_msg::Type::SessionStatusChanged(_)) => {}
            other => panic!("unexpected lifecycle response: {other:?}"),
        }
    }
    let joined = timeline.join(" | ");
    let expected = format!("datetime:Launch window:[\"2025-03-15T14:30\"]:2015-03-15T00:00:2035-03-15T23:59:900:YYYY/MM/DD:false | datetime:Optional slot:[]:{expected_slot_min}:{expected_slot_max}:900:YYYY/MM/DD:false");
    assert_eq!(joined, expected);

    drop(stream);
    handle.stop(false).await;
    task.await??;

    Ok(())
}

#[actix_web::test]
async fn datetime_codec_decodes_the_measured_wire() {
    use crate::widgets::Codec;

    let codec = Codec::DateTimeInput;
    let wire = |labels: &[&str]| {
        WireValue::StringArrayValue(proto::StringArray {
            data: labels.iter().map(|label| label.to_string()).collect(),
        })
    };
    assert_eq!(codec.decode(&wire(&["2025-03-15T14:30"])), Some(serde_json::json!("2025-03-15T14:30")));
    // The legacy spelling is accepted and re-normalized to ISO.
    assert_eq!(codec.decode(&wire(&["2025/03/15, 14:30"])), Some(serde_json::json!("2025-03-15T14:30")));
    assert_eq!(codec.decode(&wire(&[])), Some(serde_json::Value::Null), "the empty array is the cleared picker");
    assert!(codec.decode(&wire(&["not-a-datetime"])).is_none(), "a malformed datetime is rejected fail-closed");
}
