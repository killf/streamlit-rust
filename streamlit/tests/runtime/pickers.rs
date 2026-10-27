//! Picker-input regressions against the measured Python 1.66.1 wire (see
//! .codex/compatibility.md, Picker inputs): st.date_input carries its ISO
//! defaults and the ten-year min/max window (each range endpoint its own
//! side, isRange for two-endpoint values); st.time_input carries "HH:MM"
//! (whole-minute steps), the step seconds and the "24h" format;
//! st.color_picker carries its "#RRGGBB" default; st.select_slider is a
//! SELECT_SLIDER of option-label indices (first option default, step 1,
//! INT) whose wire state is the selected label(s); st.audio_input /
//! st.camera_input carry label/visibility (audio the 16000 Hz rate) and
//! report single-file uploader states.
use super::*;
use crate::InputWidgets;
use crate::proto;
use crate::proto::widget_state::Value as WireValue;

fn pickers_entry(st: &Streamlit) -> Pin<Box<dyn Future<Output = ()> + '_>> {
    Box::pin(async move {
        let result: TestResult = async {
            // Mirrors tests/reference/pickers_app.py.
            let start = chrono::NaiveDate::from_ymd_opt(2025, 1, 15).ok_or("fixture start date must be valid")?;
            st.date_input(crate::DateInputOptions::new("Start date").value(start).key("start"))?;
            st.date_input(
                crate::DateInputOptions::new("Window")
                    .value_range(start, chrono::NaiveDate::from_ymd_opt(2025, 2, 15).ok_or("fixture end date must be valid")?)
                    .key("window"),
            )?;

            st.time_input(crate::TimeInputOptions::new("Meeting").value(chrono::NaiveTime::from_hms_opt(14, 30, 0).ok_or("fixture meeting time must be valid")?).key("meeting"))?;

            st.color_picker(crate::ColorPickerOptions::new("Accent").value("#FF5733").key("accent"))?;

            st.select_slider(crate::SelectSliderOptions::new("Pick one", ["low", "medium", "high"]).key("one"))?;
            st.select_slider(crate::SelectSliderOptions::new("Pick range", ["a", "b", "c", "d"]).default(["b", "d"]).key("range"))?;

            st.audio_input(crate::AudioInputOptions::new("Voice note").key("voice"))?;
            st.camera_input(crate::CameraInputOptions::new("Snapshot").key("shot"))?;
            Ok(())
        }
        .await;
        assert!(result.is_ok(), "pickers_entry fixture failed: {result:?}");
    })
}

#[actix_web::test]
async fn picker_inputs_match_the_measured_wire() -> TestResult {
    let listener = std::net::TcpListener::bind("127.0.0.1:0")?;
    let address = listener.local_addr()?;
    let server = HttpServer::new(move || App::new().app_data(web::Data::new(StreamlitServer::new(pickers_entry, "127.0.0.1".into(), 0))).configure(configure_routes))
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

    let mut ids: std::collections::HashMap<&str, String> = std::collections::HashMap::new();
    for run in 1..=2 {
        let states = |ids: &std::collections::HashMap<&str, String>| {
            vec![WidgetState {
                id: ids.get("one").cloned().unwrap_or_default(),
                value: Some(WireValue::StringArrayValue(proto::StringArray { data: vec!["medium".into()] })),
            }]
        };
        send_binary(
            &mut stream,
            &(BackMsg {
                r#type: Some(back_msg::Type::RerunScript(ClientState {
                    widget_states: Some(WidgetStates { widgets: states(&ids) }),
                    ..Default::default()
                })),
            })
            .encode_to_vec(),
        )
        .await;
        let mut timeline: Vec<String> = Vec::new();
        loop {
            let message = receive(&mut stream).await;
            match message.r#type {
                Some(forward_msg::Type::NewSession(_)) => {}
                Some(forward_msg::Type::SessionStatusChanged(status)) if !status.script_is_running => break,
                Some(forward_msg::Type::Delta(delta)) => {
                    let Some(delta::Type::NewElement(element)) = delta.r#type else { continue };
                    let Some(kind) = element.r#type else { continue };
                    let entry = match kind {
                        element::Type::DateInput(date) => {
                            ids.entry("start").or_insert_with(|| date.id.clone());
                            format!("date:{}:{:?}:{}:{}:{}", date.label, date.default, date.is_range, date.min, date.max)
                        }
                        element::Type::TimeInput(time) => {
                            format!("time:{}:{:?}:{}:{:?}", time.label, time.default, time.step, time.format)
                        }
                        element::Type::ColorPicker(color) => {
                            format!("color:{}:{}", color.label, color.default)
                        }
                        element::Type::Slider(slider) => {
                            ids.entry("one").or_insert_with(|| slider.id.clone());
                            format!("slider:{}:{:?}:{:?}:{:?}:{:?}:{:?}", slider.label, slider.default, slider.min, slider.max, slider.step, slider.options)
                        }
                        element::Type::AudioInput(audio) => {
                            ids.entry("voice").or_insert_with(|| audio.id.clone());
                            format!("audio:{}:{:?}", audio.label, audio.sample_rate)
                        }
                        element::Type::CameraInput(camera) => {
                            format!("camera:{}", camera.label)
                        }
                        other => format!("{other:?}"),
                    };
                    timeline.push(entry);
                }
                Some(forward_msg::Type::ScriptFinished(status)) => assert_eq!(status, 0),
                Some(forward_msg::Type::SessionStatusChanged(_)) => {}
                other => panic!("unexpected lifecycle response: {other:?}"),
            }
        }
        let joined = timeline.join(" | ");
        assert_eq!(
            joined,
            "date:Start date:[\"2025-01-15\"]:false:2015-01-15:2035-01-15 | date:Window:[\"2025-01-15\", \"2025-02-15\"]:true:2015-01-15:2035-02-15 | time:Meeting:Some(\"14:30\"):900:Some(\"24h\") | color:Accent:#FF5733 | slider:Pick one:[0.0]:0.0:2.0:1.0:[\"low\", \"medium\", \"high\"] | slider:Pick range:[1.0, 3.0]:0.0:3.0:1.0:[\"a\", \"b\", \"c\", \"d\"] | audio:Voice note:Some(16000) | camera:Snapshot",
            "run {run}"
        );
    }

    drop(stream);
    handle.stop(false).await;
    task.await??;
    Ok(())
}

#[actix_web::test]
async fn date_and_time_codecs_decode_the_measured_wire() -> TestResult {
    use crate::widgets::Codec;

    let single = Codec::DateInput { range: false };
    let range = Codec::DateInput { range: true };
    let wire = |labels: &[&str]| {
        WireValue::StringArrayValue(proto::StringArray {
            data: labels.iter().map(|label| label.to_string()).collect(),
        })
    };

    assert_eq!(single.decode(&wire(&["2025-01-15"])).ok_or("single date codec must decode valid ISO date")?, serde_json::json!("2025-01-15"));
    assert!(single.decode(&wire(&["not-a-date"])).is_none(), "a malformed ISO date is rejected fail-closed");
    assert!(range.decode(&wire(&["2025-01-15"])).is_none(), "a range needs exactly two dates");
    assert_eq!(range.decode(&wire(&["2025-01-15", "2025-02-15"])).ok_or("range date codec must decode two valid dates")?, serde_json::json!(["2025-01-15", "2025-02-15"]));

    let coarse = Codec::TimeInput { step: 900 };
    let fine = Codec::TimeInput { step: 1 };
    assert_eq!(coarse.decode(&WireValue::StringValue("14:30".into())).ok_or("coarse time codec must decode HH:MM")?, serde_json::json!("14:30"));
    assert!(coarse.decode(&WireValue::StringValue("14:30:45".into())).is_none(), "whole-minute steps carry HH:MM only");
    assert_eq!(fine.decode(&WireValue::StringValue("14:30:45".into())).ok_or("fine time codec must decode HH:MM:SS")?, serde_json::json!("14:30:45"));
    assert_eq!(
        coarse.decode(&WireValue::StringValue(String::new())).ok_or("cleared time must decode to JSON null")?,
        serde_json::Value::Null,
        "the empty string is the cleared time"
    );
    Ok(())
}
