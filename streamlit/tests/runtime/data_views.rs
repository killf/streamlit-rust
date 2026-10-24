//! Real WS regression for native columnar data changing across reruns.
use super::*;
use crate::data::{Int64Array, RecordBatch, from_ipc_stream, record_batch};
use crate::{BarChartOptions, DataApi, DataframeOptions};

fn data_entry(st: &Streamlit) -> Pin<Box<dyn Future<Output = ()> + '_>> {
    Box::pin(async move {
        let state = st.session_state();
        let revision = state.get::<i64>("data_revision").unwrap().unwrap_or(0) + i64::from(st.button("Update data"));
        state.set("data_revision", revision).unwrap();
        // New native arrays are built from the application state on every run;
        // this does not read pre-rendered tables or captured IPC at runtime.
        let batch = record_batch!(("group", Utf8, ["North", "South"]), ("amount", Int64, [10 + revision, 20 + revision])).unwrap();
        st.dataframe(DataframeOptions::new(&batch).hide_index(true)).unwrap();
        st.bar_chart(BarChartOptions::new(&batch, "group", "amount")).unwrap();
    })
}

#[actix_web::test]
async fn native_dataframe_and_bar_chart_really_update_over_the_same_websocket() {
    let listener = std::net::TcpListener::bind("127.0.0.1:0").unwrap();
    let address = listener.local_addr().unwrap();
    let state = StreamlitServer::new(data_entry, "127.0.0.1".into(), 0);
    let server = HttpServer::new(move || App::new().app_data(web::Data::new(state.clone())).configure(configure_routes)).workers(1).listen(listener).unwrap().run();
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
                id: button_id.clone().unwrap(),
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
                    let id = new.initialize.unwrap().session_id;
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
                                dataframe = Some(frame.arrow_data.unwrap().data);
                                dataframe_path = Some(message.metadata.unwrap().delta_path);
                            }
                            Some(element::Type::VegaLiteChart(value)) => {
                                chart = Some(value);
                                chart_path = Some(message.metadata.unwrap().delta_path);
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
        assert_eq!(dataframe_path.unwrap(), vec![0, 1]);
        assert_eq!(chart_path.unwrap(), vec![0, 2]);
        let dataframe = dataframe.unwrap();
        let chart = chart.unwrap();
        assert_eq!(chart.datasets[0].data.as_ref().unwrap().data, dataframe);
        let batch: RecordBatch = from_ipc_stream(&dataframe).unwrap().remove(0);
        assert!(batch.schema().metadata().is_empty(), "ordinary native Arrow data needs no fabricated pandas metadata");
        let values = batch.column_by_name("amount").unwrap().as_any().downcast_ref::<Int64Array>().unwrap();
        assert_eq!(values.values().as_ref(), &[10 + expected_revision, 20 + expected_revision]);
        let spec: serde_json::Value = serde_json::from_str(&chart.spec).unwrap();
        assert_eq!(spec["data"]["name"], chart.datasets[0].name);
        if let Some(previous) = previous {
            assert_eq!(dataframe != previous, click, "a click changes actual Arrow bytes; an ordinary rerun retains values");
            assert_eq!(previous_dataset.as_ref().unwrap() != &chart.datasets[0].name, click);
        }
        previous = Some(dataframe);
        previous_dataset = Some(chart.datasets[0].name.clone());
    }
    drop(stream);
    handle.stop(false).await;
    task.await.unwrap().unwrap();
}

fn native_views_entry(st: &Streamlit) -> Pin<Box<dyn Future<Output = ()> + '_>> {
    Box::pin(async move {
        use crate::data::{ArrayRef, Float64Array};
        let state = st.session_state();
        let revision = state.get::<i64>("native_revision").unwrap().unwrap_or(0) + i64::from(st.button("Update native data"));
        state.set("native_revision", revision).unwrap();
        let data = RecordBatch::try_from_iter(vec![
            ("sales", std::sync::Arc::new(Int64Array::from(vec![12 + revision, 24, -3, 0])) as ArrayRef),
            ("cost", std::sync::Arc::new(Float64Array::from(vec![Some(4.0), Some(8.0 + revision as f64), None, Some(2.0)])) as ArrayRef),
        ])
        .unwrap();
        st.table(&data).unwrap();
        st.bar_chart(&data).unwrap();
    })
}

#[actix_web::test]
async fn native_table_and_inferred_bar_update_values_nulls_and_dataset_on_one_websocket() {
    use crate::data::Float64Array;
    let listener = std::net::TcpListener::bind("127.0.0.1:0").unwrap();
    let address = listener.local_addr().unwrap();
    let state = StreamlitServer::new(native_views_entry, "127.0.0.1".into(), 0);
    let server = HttpServer::new(move || App::new().app_data(web::Data::new(state.clone())).configure(configure_routes)).workers(1).listen(listener).unwrap().run();
    let handle = server.handle();
    let task = actix_web::rt::spawn(server);
    let mut stream = sessions::connect(address, None).await;
    let mut button_id = None;
    let mut session_id = None;
    let mut previous: Option<(Vec<u8>, String)> = None;
    for (click, revision) in [(false, 0), (true, 1), (true, 2), (false, 2)] {
        let widgets = if click {
            vec![WidgetState {
                id: button_id.clone().unwrap(),
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
                    let id = new.initialize.unwrap().session_id;
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
                                assert_eq!(message.metadata.unwrap().delta_path, vec![0, 1]);
                                table = Some(value);
                            }
                            Some(element::Type::VegaLiteChart(value)) => {
                                assert_eq!(message.metadata.unwrap().delta_path, vec![0, 2]);
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
        let table = table.unwrap();
        assert!(table.hide_index);
        assert!(!table.hide_header);
        let table_bytes = table.arrow_data.unwrap().data;
        let data = from_ipc_stream(&table_bytes).unwrap().remove(0);
        assert_eq!(data.column(0).as_any().downcast_ref::<Int64Array>().unwrap().values().as_ref(), &[12 + revision, 24, -3, 0]);
        let chart = chart.unwrap();
        let series = from_ipc_stream(&chart.datasets[0].data.as_ref().unwrap().data).unwrap().remove(0);
        let values = series.column(2).as_any().downcast_ref::<Float64Array>().unwrap();
        assert_eq!(values, &Float64Array::from(vec![Some(12.0 + revision as f64), Some(24.0), Some(-3.0), Some(0.0), Some(4.0), Some(8.0 + revision as f64), None, Some(2.0)]));
        assert_eq!(series.num_rows(), 8);
        let spec: serde_json::Value = serde_json::from_str(&chart.spec).unwrap();
        assert_eq!(spec["data"]["name"], chart.datasets[0].name);
        if let Some((bytes, name)) = previous {
            assert_eq!(bytes != table_bytes, click);
            assert_eq!(name != chart.datasets[0].name, click);
        }
        previous = Some((table_bytes, chart.datasets[0].name.clone()));
    }
    drop(stream);
    handle.stop(false).await;
    task.await.unwrap().unwrap();
}
