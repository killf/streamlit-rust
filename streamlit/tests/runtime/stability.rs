//! M5 stability regressions: large payloads, a slow-reading client, and a
//! long-lived session under rerun/upload churn. Each fixture prints a
//! `stability_measurement=` line the measurement runner samples; the CI
//! assertions cover correctness and isolation, never a performance SLO.
use super::*;
use crate::data::{ArrayRef, Int64Array, RecordBatch};
use crate::{DataApi, InputWidgets};
use std::sync::Arc;

fn large_entry(st: &Streamlit) -> Pin<Box<dyn Future<Output = ()> + '_>> {
    Box::pin(async move {
        let result: TestResult = async {
            // Two wide tables and a chart dataset in ONE run: 100k-row frame,
            // a 50k x 4 frame, and a 200k-point chart dataset.
            let wide = crate::data::record_batch!(("idx", Int64, (0..100_000).map(|i| i as i64).collect::<Vec<_>>()), ("value", Int64, (0..100_000).map(|i| i * 2).collect::<Vec<_>>()))?;
            st.dataframe(&wide)?;
            let four = RecordBatch::try_from_iter(vec![
                ("a", Arc::new(Int64Array::from((0..50_000).map(|i| i as i64).collect::<Vec<_>>())) as ArrayRef),
                ("b", Arc::new(Int64Array::from((0..50_000).map(|i| i + 1).collect::<Vec<_>>())) as ArrayRef),
                ("c", Arc::new(Int64Array::from((0..50_000).map(|i| i + 2).collect::<Vec<_>>())) as ArrayRef),
                ("d", Arc::new(Int64Array::from((0..50_000).map(|i| i + 3).collect::<Vec<_>>())) as ArrayRef),
            ])?;
            st.dataframe(&four)?;
            let chart = crate::data::record_batch!(("series", Int64, (0..200_000).map(|i| i as i64 * 3).collect::<Vec<_>>()))?;
            st.line_chart(&chart)?;
            Ok(())
        }
        .await;
        assert!(result.is_ok(), "large_entry fixture failed: {result:?}");
    })
}

#[actix_web::test]
async fn large_payloads_render_correctly_and_survive_a_rerun() -> TestResult {
    let listener = std::net::TcpListener::bind("127.0.0.1:0")?;
    let address = listener.local_addr()?;
    let server = StreamlitServer::new(large_entry, "127.0.0.1".into(), 0);
    let server = HttpServer::new(move || App::new().app_data(web::Data::new(server.clone())).configure(configure_routes)).workers(1).listen(listener)?.run();
    let handle = server.handle();
    let task = actix_web::rt::spawn(server);
    let mut stream = sessions::connect(address, None).await;
    let began = std::time::Instant::now();
    let mut runs = 0;
    for _round in 0..2 {
        send_binary(
            &mut stream,
            &(BackMsg {
                r#type: Some(back_msg::Type::RerunScript(ClientState::default())),
            })
            .encode_to_vec(),
        )
        .await;
        let mut tables = 0;
        let mut charts = 0;
        let mut rows_seen = Vec::new();
        loop {
            let message = receive_large(&mut stream).await;
            match message.r#type {
                Some(forward_msg::Type::Delta(delta)) => {
                    if let Some(delta::Type::NewElement(element)) = delta.r#type {
                        match element.r#type {
                            Some(element::Type::Dataframe(frame)) => {
                                let bytes = frame.arrow_data.ok_or("dataframe arrow")?.data;
                                let batch = crate::data::from_ipc_stream(&bytes)?.remove(0);
                                rows_seen.push(batch.num_rows());
                                tables += 1;
                            }
                            Some(element::Type::VegaLiteChart(_)) => charts += 1,
                            _ => {}
                        }
                    }
                }
                Some(forward_msg::Type::ScriptFinished(status)) => {
                    assert_eq!(status, 0);
                    break;
                }
                _ => {}
            }
        }
        assert_eq!(tables, 2, "two dataframes per run");
        assert_eq!(charts, 1, "one chart dataset per run");
        assert_eq!(rows_seen, vec![100_000, 50_000], "the large tables decode with every row");
        runs += 1;
    }
    println!(
        "stability_measurement={}",
        serde_json::json!({
            "scenario": "large_payloads",
            "runs": runs,
            "rows_per_run": [100_000, 50_000],
            "chart_points": 200_000,
            "total_wall_seconds": began.elapsed().as_secs_f64(),
        })
    );
    drop(stream);
    handle.stop(false).await;
    task.await??;
    Ok(())
}

fn counter_entry(st: &Streamlit) -> Pin<Box<dyn Future<Output = ()> + '_>> {
    Box::pin(async move {
        let result: TestResult = (|| {
            let state = st.session_state();
            let rounds = state.get::<u64>("rounds")?.unwrap_or(0);
            let bumped = st.try_button(crate::ButtonOptions::new("Bump").key("bump"))?;
            let next = rounds + u64::from(bumped);
            state.set("rounds", next)?;
            st.write(format!("rounds={next}"));
            Ok(())
        })();
        assert!(result.is_ok(), "counter fixture failed: {result:?}");
    })
}

/// A long-lived session under churn: 300 reruns, every 25th carrying the bump
/// trigger; the counter must land exactly on the number of bumps and the
/// session identity must never change.
#[actix_web::test]
async fn a_long_session_survives_rerun_churn_with_exact_state() -> TestResult {
    let listener = std::net::TcpListener::bind("127.0.0.1:0")?;
    let address = listener.local_addr()?;
    let server = StreamlitServer::new(counter_entry, "127.0.0.1".into(), 0);
    let server = HttpServer::new(move || App::new().app_data(web::Data::new(server.clone())).configure(configure_routes)).workers(1).listen(listener)?.run();
    let handle = server.handle();
    let task = actix_web::rt::spawn(server);
    let mut stream = sessions::connect(address, None).await;
    let began = std::time::Instant::now();
    let mut session_id = String::new();
    let mut button_id: Option<String> = None;
    let mut last_rounds = 0;
    let total = 300;
    let bumps = 11;
    for round in 0..total {
        let trigger = round > 0 && round % 25 == 0 && round / 25 <= bumps;
        let widgets = match (&button_id, trigger) {
            (Some(id), true) => vec![WidgetState {
                id: id.clone(),
                value: Some(widget_state::Value::TriggerValue(true)),
            }],
            _ => vec![],
        };
        send_binary(
            &mut stream,
            &(BackMsg {
                r#type: Some(back_msg::Type::RerunScript(ClientState {
                    widget_states: Some(WidgetStates { widgets }),
                    ..Default::default()
                })),
            })
            .encode_to_vec(),
        )
        .await;
        let mut finished = false;
        loop {
            let message = receive(&mut stream).await;
            match message.r#type {
                Some(forward_msg::Type::NewSession(new)) => {
                    let id = new.initialize.ok_or("init")?.session_id;
                    if session_id.is_empty() {
                        session_id = id;
                    } else {
                        assert_eq!(id, session_id, "the long session must keep its identity");
                    }
                }
                Some(forward_msg::Type::Delta(delta)) => {
                    if let Some(delta::Type::NewElement(element)) = delta.r#type {
                        match element.r#type {
                            Some(element::Type::Button(button)) => button_id = Some(button.id),
                            Some(element::Type::Markdown(text)) => {
                                if let Some(value) = text.body.strip_prefix("rounds=") {
                                    last_rounds = value.parse()?;
                                }
                            }
                            _ => {}
                        }
                    }
                }
                Some(forward_msg::Type::ScriptFinished(status)) => {
                    assert_eq!(status, 0);
                    finished = true;
                }
                Some(forward_msg::Type::SessionStatusChanged(status)) if !status.script_is_running => {
                    assert!(finished);
                    break;
                }
                _ => {}
            }
        }
    }
    assert_eq!(last_rounds, bumps, "exactly the triggered bumps survive 300 reruns");
    println!(
        "stability_measurement={}",
        serde_json::json!({
            "scenario": "long_session_churn",
            "reruns": total,
            "bump_triggers": bumps,
            "final_rounds": last_rounds,
            "total_wall_seconds": began.elapsed().as_secs_f64(),
        })
    );
    drop(stream);
    handle.stop(false).await;
    task.await??;
    Ok(())
}

/// A client that reads one frame per 20ms while another session runs
/// full-speed: the fast session completes its runs unaffected, and the slow
/// session still drains every frame afterwards.
#[actix_web::test]
async fn a_slow_reader_does_not_block_a_fast_session() -> TestResult {
    let listener = std::net::TcpListener::bind("127.0.0.1:0")?;
    let address = listener.local_addr()?;
    let server = StreamlitServer::new(counter_entry, "127.0.0.1".into(), 0);
    let server = HttpServer::new(move || App::new().app_data(web::Data::new(server.clone())).configure(configure_routes)).workers(1).listen(listener)?.run();
    let handle = server.handle();
    let task = actix_web::rt::spawn(server);
    let mut slow = sessions::connect(address, None).await;
    // Park the slow session with one rerun; it reads exactly one frame then
    // waits, holding unread payload in its socket.
    send_binary(
        &mut slow,
        &(BackMsg {
            r#type: Some(back_msg::Type::RerunScript(ClientState::default())),
        })
        .encode_to_vec(),
    )
    .await;
    let _ = receive(&mut slow).await;
    // The fast session runs to completion while the slow one idles mid-stream.
    let began = std::time::Instant::now();
    let mut fast = sessions::connect(address, None).await;
    let mut fast_runs = 0;
    for _ in 0..20 {
        send_binary(
            &mut fast,
            &(BackMsg {
                r#type: Some(back_msg::Type::RerunScript(ClientState::default())),
            })
            .encode_to_vec(),
        )
        .await;
        let mut finished = false;
        loop {
            match receive(&mut fast).await.r#type {
                Some(forward_msg::Type::ScriptFinished(status)) => {
                    assert_eq!(status, 0);
                    fast_runs += 1;
                    finished = true;
                }
                Some(forward_msg::Type::SessionStatusChanged(status)) if !status.script_is_running && finished => break,
                _ => {}
            }
        }
    }
    let fast_seconds = began.elapsed().as_secs_f64();
    assert_eq!(fast_runs, 20, "the fast session completes every run while the slow client idles");
    // The slow session now drains its remaining frames and finishes cleanly.
    let mut slow_finished = false;
    let drain_deadline = std::time::Instant::now() + Duration::from_secs(10);
    while std::time::Instant::now() < drain_deadline {
        if let Some(forward_msg::Type::ScriptFinished(_)) = receive(&mut slow).await.r#type {
            slow_finished = true;
            break;
        }
    }
    assert!(slow_finished, "the slow session drains and finishes after the fast one");
    println!(
        "stability_measurement={}",
        serde_json::json!({
            "scenario": "slow_reader_isolation",
            "fast_session_runs": fast_runs,
            "fast_session_seconds": fast_seconds,
            "slow_session_finished": slow_finished,
        })
    );
    drop(slow);
    drop(fast);
    handle.stop(false).await;
    task.await??;
    Ok(())
}

/// The shared receive() caps frames at 1 MiB; the large-payload frames exceed
/// it, so this reader accepts up to 64 MiB bodies.
async fn receive_large(stream: &mut TcpStream) -> ForwardMsg {
    use tokio::io::AsyncReadExt;
    let mut header = [0u8; 2];
    stream.read_exact(&mut header).await.expect("large frame header");
    assert_eq!(header[0], 0x82, "expected a complete binary WS frame");
    assert_eq!(header[1] & 0x80, 0, "server frames must not be masked");
    let length = match header[1] & 0x7f {
        126 => stream.read_u16().await.expect("len16") as usize,
        127 => usize::try_from(stream.read_u64().await.expect("len64")).expect("len fits"),
        value => value as usize,
    };
    assert!(length < 64 * 1024 * 1024, "large frame exceeded 64 MiB: {length}");
    let mut body = vec![0u8; length];
    stream.read_exact(&mut body).await.expect("large frame body");
    prost::Message::decode(body.as_slice()).expect("decode large ForwardMsg")
}

/// M5 capacity edge: many live sessions at once, each carrying its own state.
/// Every session must finish its run, keep its identity on reconnect, and
/// retain its own counter — no cross-talk, no eviction while connected.
#[actix_web::test]
async fn many_concurrent_sessions_hold_independent_state() -> TestResult {
    const SESSIONS: usize = 64;
    let listener = std::net::TcpListener::bind("127.0.0.1:0")?;
    let address = listener.local_addr()?;
    let server = StreamlitServer::new(counter_entry, "127.0.0.1".into(), 0);
    let server = HttpServer::new(move || App::new().app_data(web::Data::new(server.clone())).configure(configure_routes)).workers(1).listen(listener)?.run();
    let handle = server.handle();
    let task = actix_web::rt::spawn(server);
    let began = std::time::Instant::now();

    // Open all sessions first; each parks after its first run.
    let mut parked = Vec::new();
    for index in 0..SESSIONS {
        let mut stream = sessions::connect(address, None).await;
        send_binary(
            &mut stream,
            &(BackMsg {
                r#type: Some(back_msg::Type::RerunScript(ClientState::default())),
            })
            .encode_to_vec(),
        )
        .await;
        let mut session_id = String::new();
        let mut button_id = String::new();
        loop {
            match receive(&mut stream).await.r#type {
                Some(forward_msg::Type::NewSession(new)) => session_id = new.initialize.ok_or("init")?.session_id,
                Some(forward_msg::Type::Delta(delta)) => {
                    if let Some(delta::Type::NewElement(element)) = delta.r#type
                        && let Some(element::Type::Button(button)) = element.r#type
                    {
                        button_id = button.id;
                    }
                }
                Some(forward_msg::Type::ScriptFinished(_)) => break,
                _ => {}
            }
        }
        parked.push((index, stream, session_id, button_id));
    }
    assert_eq!(parked.len(), SESSIONS);

    // Every session now bumps exactly once: each holds its own identity.
    let mut bumps_ok = 0;
    for (index, stream, session_id, button_id) in parked.iter_mut() {
        let _ = index;
        send_binary(
            stream,
            &(BackMsg {
                r#type: Some(back_msg::Type::RerunScript(ClientState {
                    widget_states: Some(WidgetStates {
                        widgets: vec![WidgetState {
                            id: button_id.clone(),
                            value: Some(widget_state::Value::TriggerValue(true)),
                        }],
                    }),
                    ..Default::default()
                })),
            })
            .encode_to_vec(),
        )
        .await;
        let mut rounds = None;
        let mut seen_id = String::new();
        loop {
            match receive(stream).await.r#type {
                Some(forward_msg::Type::NewSession(new)) => seen_id = new.initialize.ok_or("init")?.session_id,
                Some(forward_msg::Type::Delta(delta)) => {
                    if let Some(delta::Type::NewElement(element)) = delta.r#type
                        && let Some(element::Type::Markdown(text)) = element.r#type
                        && let Some(value) = text.body.strip_prefix("rounds=")
                    {
                        rounds = Some(value.parse::<u64>()?);
                    }
                }
                Some(forward_msg::Type::ScriptFinished(_)) => break,
                _ => {}
            }
        }
        assert_eq!(seen_id, *session_id, "a connected session keeps its identity");
        assert_eq!(rounds, Some(1), "each session saw exactly its own bump");
        bumps_ok += 1;
    }
    assert_eq!(bumps_ok, SESSIONS);
    println!(
        "stability_measurement={}",
        serde_json::json!({
            "scenario": "session_capacity",
            "concurrent_sessions": SESSIONS,
            "bumps_landed": bumps_ok,
            "total_wall_seconds": began.elapsed().as_secs_f64(),
        })
    );
    drop(parked);
    handle.stop(false).await;
    task.await??;
    Ok(())
}
