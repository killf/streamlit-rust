//! data_editor interaction regressions against the measured Python 1.66.1
//! wire (see .codex/compatibility.md, Column config): the committed edits
//! (one string_value JSON: edited_rows keyed by row with column-name keys,
//! added_rows as column-name-keyed cells — an untouched added row arrives
//! as `{}` — and deleted_rows positions) are applied server-side like the
//! reference's _apply_dataframe_edits: cell edits, then deletions, then
//! additions; the re-emitted dataframe and the caller's return value carry
//! the edited table.
use super::*;
use crate::DataApi;
use crate::data::{Array, Field, Int64Array, RecordBatch, Schema, StringArray};
use crate::proto::{WidgetState, WidgetStates, element, forward_msg, widget_state};
use serde_json::json;
use std::sync::Arc;

fn qty_label_batch() -> TestResult<RecordBatch> {
    let fields = vec![Field::new("qty", crate::data::DataType::Int64, true), Field::new("label", crate::data::DataType::Utf8, true)];
    let arrays = vec![Arc::new(Int64Array::from(vec![1, 2])) as _, Arc::new(StringArray::from(vec!["a", "b"])) as _];
    Ok(RecordBatch::try_new(Arc::new(Schema::new(fields)), arrays)?)
}

fn dataeditor_entry(st: &Streamlit) -> Pin<Box<dyn Future<Output = ()> + '_>> {
    Box::pin(async move {
        let result: TestResult = async {
            // Mirrors tests/reference/dataeditor_app.py.
            let edited = st.data_editor(crate::DataEditorOptions::new(&qty_label_batch()?).num_rows(crate::EditorRows::Dynamic).key("editor"))?;
            st.dataframe(crate::DataframeOptions::new(&edited))?;
            st.write(format!("rows={}", edited.num_rows()));

            Ok(())
        }
        .await;

        assert!(result.is_ok(), "dataeditor fixture must render successfully: {result:?}");
    })
}

#[actix_web::test]
async fn committed_edits_apply_serverside_over_the_production_websocket() -> TestResult {
    let listener = std::net::TcpListener::bind("127.0.0.1:0")?;
    let address = listener.local_addr()?;
    let server = HttpServer::new(move || App::new().app_data(web::Data::new(StreamlitServer::new(dataeditor_entry, "127.0.0.1".into(), 0))).configure(configure_routes))
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

    // (edits-state JSON, expected markdown, expected qty column, int-or-float)
    // pairs, mirroring the measured journey stages: the plain load, a cell
    // edit, an empty added row (the int column upcasts to float64 under the
    // added null, like pandas), then a typed one (back to int64).
    let stages: Vec<(&str, &str, Vec<Option<f64>>, bool)> = vec![
        (r#"{}"#, "rows=2", vec![Some(1.0), Some(2.0)], true),
        (r#"{"edited_rows":{"0":{"qty":7}},"added_rows":[],"deleted_rows":[]}"#, "rows=2", vec![Some(7.0), Some(2.0)], true),
        (r#"{"edited_rows":{"0":{"qty":7}},"added_rows":[{}],"deleted_rows":[]}"#, "rows=3", vec![Some(7.0), Some(2.0), None], false),
        (r#"{"edited_rows":{"0":{"qty":7}},"added_rows":[{"qty":9}],"deleted_rows":[]}"#, "rows=3", vec![Some(7.0), Some(2.0), Some(9.0)], true),
    ];
    let mut editor_id = String::new();
    for (state, expected_rows, expected_qty, expect_int) in stages {
        let widgets = if editor_id.is_empty() && state == "{}" {
            vec![]
        } else {
            vec![WidgetState {
                id: editor_id.clone(),
                value: Some(widget_state::Value::StringValue(state.to_owned())),
            }]
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
        let mut dataframes = Vec::new();
        let mut trailing = String::new();
        loop {
            let message = receive(&mut stream).await;
            match message.r#type {
                Some(forward_msg::Type::NewSession(_)) => {}
                Some(forward_msg::Type::SessionStatusChanged(status)) if !status.script_is_running => break,
                Some(forward_msg::Type::Delta(delta)) => {
                    let Some(delta::Type::NewElement(element)) = delta.r#type else { continue };
                    match element.r#type {
                        Some(element::Type::Dataframe(frame)) => {
                            if frame.editing_mode == 2 && !frame.id.is_empty() {
                                editor_id = frame.id.clone();
                            }
                            dataframes.push(frame);
                        }
                        Some(element::Type::Markdown(markdown)) => trailing = markdown.body,
                        _ => {}
                    }
                }
                Some(forward_msg::Type::ScriptFinished(status)) => assert_eq!(status, 0),
                Some(forward_msg::Type::SessionStatusChanged(_)) => {}
                other => panic!("unexpected lifecycle response: {other:?}"),
            }
        }
        assert_eq!(trailing, expected_rows, "the edits change the row count the app sees");
        assert_eq!(dataframes.len(), 2, "the editor and the written table");
        // The editor element keeps the ORIGINAL table; the written table
        // carries the applied edits, int columns upcasting to float64 under
        // an added null like pandas.
        let editor = &dataframes[0];
        let editor_batch: RecordBatch = crate::data::from_ipc_stream(&editor.arrow_data.as_ref().ok_or("data editor must emit its Arrow data")?.data)?.remove(0);
        let editor_qty = editor_batch
            .column_by_name("qty")
            .ok_or("edited Arrow schema must retain qty column")?
            .as_any()
            .downcast_ref::<Int64Array>()
            .ok_or("edited Arrow column must be Int64Array")?;
        assert_eq!(editor_qty.values().as_ref(), &[1, 2], "the editor re-emits the original data every run");
        let written = &dataframes[1];
        let decoded: RecordBatch = crate::data::from_ipc_stream(&written.arrow_data.as_ref().ok_or("data editor must emit its Arrow data")?.data)?.remove(0);
        let qty_column = decoded.column_by_name("qty").ok_or("edited Arrow schema must retain qty column")?;
        let actual: Vec<Option<f64>> = if expect_int {
            let qty = qty_column.as_any().downcast_ref::<Int64Array>().ok_or("edited Arrow column must be Int64Array")?;
            (0..qty.len()).map(|index| if qty.is_null(index) { None } else { Some(qty.value(index) as f64) }).collect()
        } else {
            let qty = qty_column.as_any().downcast_ref::<crate::data::Float64Array>().ok_or("edited Arrow column must be crate::data::Float64Array")?;
            (0..qty.len()).map(|index| if qty.is_null(index) { None } else { Some(qty.value(index)) }).collect()
        };
        assert_eq!(actual, expected_qty, "the applied qty column after {state}");
        let is_int = qty_column.data_type() == &crate::data::DataType::Int64;
        assert_eq!(is_int, expect_int, "the dtype follows the pandas upcast");
        // The added row's untouched label cell is null on the written table
        // (measured python wire: None, never an empty string).
        let label_column = decoded.column_by_name("label").ok_or("edited Arrow schema must retain label column")?;
        let texts = label_column.as_any().downcast_ref::<crate::data::LargeStringArray>().ok_or("edited Arrow column must be crate::data::LargeStringArray")?;
        let labels: Vec<Option<String>> = (0..texts.len()).map(|index| if texts.is_null(index) { None } else { Some(texts.value(index).to_owned()) }).collect();
        let expected_labels: Vec<Option<String>> = match expected_qty.len() {
            2 => vec![Some("a".to_owned()), Some("b".to_owned())],
            _ => vec![Some("a".to_owned()), Some("b".to_owned()), None],
        };
        assert_eq!(labels, expected_labels, "the label column after {state}");
    }

    drop(stream);
    handle.stop(false).await;
    task.await??;

    Ok(())
}

#[test]
fn apply_edits_follows_the_reference_order() -> TestResult {
    let batch = qty_label_batch()?;
    let edits = json!({
        "edited_rows": {"0": {"qty": 5, "label": "x"}},
        "deleted_rows": [1],
        "added_rows": [{"qty": 9}],
    });
    let edited = data_editor_edits_for_test(&batch, &edits)?;
    let qty = edited
        .column_by_name("qty")
        .ok_or("edited Arrow schema must retain qty column")?
        .as_any()
        .downcast_ref::<Int64Array>()
        .ok_or("edited Arrow column must be Int64Array")?;
    let label = edited
        .column_by_name("label")
        .ok_or("edited Arrow schema must retain label column")?
        .as_any()
        .downcast_ref::<StringArray>()
        .ok_or("edited Arrow column must be StringArray")?;
    assert_eq!(qty.values().as_ref(), &[5, 9]);
    // The added row's untouched text cell is null, not an empty string
    // (measured written table: label column ends in None).
    assert_eq!(label.iter().collect::<Vec<_>>(), vec![Some("x"), None]);

    Ok(())
}

/// Direct access for the unit test (the emitter path is covered by the WS
/// regression above).
fn data_editor_edits_for_test(batch: &RecordBatch, edits: &serde_json::Value) -> TestResult<RecordBatch> {
    Ok(crate::data_api::apply_edits_for_test(batch, edits)?)
}
