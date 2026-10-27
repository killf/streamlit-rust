//! Real WS regression for native columnar data changing across reruns.
use super::*;
use crate::data::{Int64Array, RecordBatch, from_ipc_stream, record_batch};
use crate::{BarChartOptions, DataApi, DataframeOptions};

fn data_entry(st: &Streamlit) -> Pin<Box<dyn Future<Output = ()> + '_>> {
    Box::pin(async move {
        let result: TestResult = async {
            let state = st.session_state();
            let revision = state.get::<i64>("data_revision")?.unwrap_or(0) + i64::from(st.button("Update data"));
            state.set("data_revision", revision)?;
            // New native arrays are built from the application state on every run;
            // this does not read pre-rendered tables or captured IPC at runtime.
            let batch = record_batch!(("group", Utf8, ["North", "South"]), ("amount", Int64, [10 + revision, 20 + revision]))?;
            st.dataframe(DataframeOptions::new(&batch).hide_index(true))?;
            st.bar_chart(BarChartOptions::new(&batch, "group", "amount"))?;
            Ok(())
        }
        .await;
        assert!(result.is_ok(), "data_entry fixture failed: {result:?}");
    })
}

#[actix_web::test]
async fn native_dataframe_and_bar_chart_really_update_over_the_same_websocket() -> TestResult {
    let listener = std::net::TcpListener::bind("127.0.0.1:0")?;
    let address = listener.local_addr()?;
    let state = StreamlitServer::new(data_entry, "127.0.0.1".into(), 0);
    let server = HttpServer::new(move || App::new().app_data(web::Data::new(state.clone())).configure(configure_routes)).workers(1).listen(listener)?.run();
    let handle = server.handle();
    let task = actix_web::rt::spawn(server);
    let mut stream = sessions::connect(address, None).await;
    let mut button_id = None;
    let mut session_id = None;
    let mut previous: Option<Vec<u8>> = None;
    let mut previous_dataset = None;
    for (click, expected_revision) in [(false, 0_i64), (true, 1), (true, 2), (false, 2)] {
        let widgets = if click {
            vec![WidgetState {
                id: button_id.clone().ok_or("Update data button must be rendered before clicking")?,
                value: Some(widget_state::Value::TriggerValue(true)),
            }]
        } else {
            vec![]
        };
        let message = BackMsg {
            r#type: Some(back_msg::Type::RerunScript(ClientState {
                widget_states: Some(WidgetStates { widgets }),
                ..Default::default()
            })),
        };
        send_binary(&mut stream, &message.encode_to_vec()).await;
        let mut dataframe = None;
        let mut dataframe_path = None;
        let mut chart = None;
        let mut chart_path = None;
        loop {
            let message = receive(&mut stream).await;
            match message.r#type {
                Some(forward_msg::Type::NewSession(new)) => {
                    let id = new.initialize.ok_or("NewSession must include initialization")?.session_id;
                    if let Some(previous) = &session_id {
                        assert_eq!(&id, previous);
                    } else {
                        session_id = Some(id);
                    }
                }
                Some(forward_msg::Type::Delta(delta)) => {
                    if let Some(delta::Type::NewElement(element)) = delta.r#type {
                        match element.r#type {
                            Some(element::Type::Button(button)) => button_id = Some(button.id),
                            Some(element::Type::Dataframe(frame)) => {
                                dataframe = Some(frame.arrow_data.ok_or("dataframe must include Arrow data")?.data);
                                dataframe_path = Some(message.metadata.ok_or("data element must include delta path metadata")?.delta_path);
                            }
                            Some(element::Type::VegaLiteChart(value)) => {
                                chart = Some(value);
                                chart_path = Some(message.metadata.ok_or("data element must include delta path metadata")?.delta_path);
                            }
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
        assert_eq!(dataframe_path.ok_or("dataframe delta path must be observed")?, vec![0, 1]);
        assert_eq!(chart_path.ok_or("chart delta path must be observed")?, vec![0, 2]);
        let dataframe = dataframe.ok_or("dataframe must be rendered")?;
        let chart = chart.ok_or("bar chart must be rendered")?;
        assert_eq!(chart.datasets[0].data.as_ref().ok_or("bar chart dataset must include Arrow data")?.data, dataframe);
        let batch: RecordBatch = from_ipc_stream(&dataframe)?.remove(0);
        assert!(batch.schema().metadata().contains_key("pandas"), "chart/dataframe data rides the reference's pandas-3 IPC stamp");
        let values = batch.column_by_name("amount").ok_or("dataframe must have amount column")?.as_any().downcast_ref::<Int64Array>().ok_or("amount column must be Int64")?;
        assert_eq!(values.values().as_ref(), &[10 + expected_revision, 20 + expected_revision]);
        let spec: serde_json::Value = serde_json::from_str(&chart.spec)?;
        assert_eq!(spec["data"]["name"], chart.datasets[0].name);
        if let Some(previous) = previous {
            assert_eq!(dataframe != previous, click, "a click changes actual Arrow bytes; an ordinary rerun retains values");
            assert_eq!(previous_dataset.as_ref().ok_or("previous chart dataset must be captured with dataframe")? != &chart.datasets[0].name, click);
        }
        previous = Some(dataframe);
        previous_dataset = Some(chart.datasets[0].name.clone());
    }
    drop(stream);
    handle.stop(false).await;
    task.await??;
    Ok(())
}

fn native_views_entry(st: &Streamlit) -> Pin<Box<dyn Future<Output = ()> + '_>> {
    Box::pin(async move {
        let result: TestResult = async {
            use crate::data::{ArrayRef, Float64Array};
            let state = st.session_state();
            let revision = state.get::<i64>("native_revision")?.unwrap_or(0) + i64::from(st.button("Update native data"));
            state.set("native_revision", revision)?;
            let data = RecordBatch::try_from_iter(vec![
                ("sales", std::sync::Arc::new(Int64Array::from(vec![12 + revision, 24, -3, 0])) as ArrayRef),
                ("cost", std::sync::Arc::new(Float64Array::from(vec![Some(4.0), Some(8.0 + revision as f64), None, Some(2.0)])) as ArrayRef),
            ])?;
            st.table(&data)?;
            st.bar_chart(&data)?;
            Ok(())
        }
        .await;
        assert!(result.is_ok(), "native_views_entry fixture failed: {result:?}");
    })
}

#[actix_web::test]
async fn native_table_and_inferred_bar_update_values_nulls_and_dataset_on_one_websocket() -> TestResult {
    use crate::data::Float64Array;
    let listener = std::net::TcpListener::bind("127.0.0.1:0")?;
    let address = listener.local_addr()?;
    let state = StreamlitServer::new(native_views_entry, "127.0.0.1".into(), 0);
    let server = HttpServer::new(move || App::new().app_data(web::Data::new(state.clone())).configure(configure_routes)).workers(1).listen(listener)?.run();
    let handle = server.handle();
    let task = actix_web::rt::spawn(server);
    let mut stream = sessions::connect(address, None).await;
    let mut button_id = None;
    let mut session_id = None;
    let mut previous: Option<(Vec<u8>, String)> = None;
    for (click, revision) in [(false, 0), (true, 1), (true, 2), (false, 2)] {
        let widgets = if click {
            vec![WidgetState {
                id: button_id.clone().ok_or("Update data button must be rendered before clicking")?,
                value: Some(widget_state::Value::TriggerValue(true)),
            }]
        } else {
            vec![]
        };
        let message = BackMsg {
            r#type: Some(back_msg::Type::RerunScript(ClientState {
                widget_states: Some(WidgetStates { widgets }),
                ..Default::default()
            })),
        };
        send_binary(&mut stream, &message.encode_to_vec()).await;
        let mut table = None;
        let mut chart = None;
        loop {
            let message = receive(&mut stream).await;
            match message.r#type {
                Some(forward_msg::Type::NewSession(new)) => {
                    let id = new.initialize.ok_or("NewSession must include initialization")?.session_id;
                    if let Some(old) = &session_id {
                        assert_eq!(old, &id);
                    } else {
                        session_id = Some(id);
                    }
                }
                Some(forward_msg::Type::Delta(delta)) => {
                    if let Some(delta::Type::NewElement(element)) = delta.r#type {
                        match element.r#type {
                            Some(element::Type::Button(button)) => button_id = Some(button.id),
                            Some(element::Type::Table(value)) => {
                                assert_eq!(message.metadata.ok_or("data element must include delta path metadata")?.delta_path, vec![0, 1]);
                                table = Some(value);
                            }
                            Some(element::Type::VegaLiteChart(value)) => {
                                assert_eq!(message.metadata.ok_or("data element must include delta path metadata")?.delta_path, vec![0, 2]);
                                chart = Some(value);
                            }
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
        let table = table.ok_or("native table must be rendered")?;
        assert!(table.hide_index);
        assert!(!table.hide_header);
        let table_bytes = table.arrow_data.ok_or("native table must include Arrow data")?.data;
        let data = from_ipc_stream(&table_bytes)?.remove(0);
        assert_eq!(data.column(0).as_any().downcast_ref::<Int64Array>().ok_or("sales column must be Int64")?.values().as_ref(), &[12 + revision, 24, -3, 0]);
        let chart = chart.ok_or("bar chart must be rendered")?;
        let series = from_ipc_stream(&chart.datasets[0].data.as_ref().ok_or("bar chart dataset must include Arrow data")?.data)?.remove(0);
        let values = series.column(2).as_any().downcast_ref::<Float64Array>().ok_or("chart series values must be Float64")?;
        assert_eq!(values, &Float64Array::from(vec![Some(12.0 + revision as f64), Some(24.0), Some(-3.0), Some(0.0), Some(4.0), Some(8.0 + revision as f64), None, Some(2.0)]));
        assert_eq!(series.num_rows(), 8);
        let spec: serde_json::Value = serde_json::from_str(&chart.spec)?;
        assert_eq!(spec["data"]["name"], chart.datasets[0].name);
        if let Some((bytes, name)) = previous {
            assert_eq!(bytes != table_bytes, click);
            assert_eq!(name != chart.datasets[0].name, click);
        }
        previous = Some((table_bytes, chart.datasets[0].name.clone()));
    }
    drop(stream);
    handle.stop(false).await;
    task.await??;
    Ok(())
}
