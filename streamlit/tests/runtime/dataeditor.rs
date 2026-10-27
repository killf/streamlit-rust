//! data_editor interaction regressions against the measured Python 1.66.1
//! wire (see .codex/compatibility.md, Column config): the committed edits
//! (one string_value JSON: edited_rows keyed by row with column-name keys,
//! added_rows as column-name-keyed cells — an untouched added row arrives
//! as `{}` — and deleted_rows positions) are applied server-side like the
//! reference's _apply_dataframe_edits: cell edits, then deletions, then
//! additions. The editor re-emits the original input table; the caller's
//! return value and the separately written dataframe carry the edited table.
use super::*;
use crate::DataApi;
use crate::data::{Array, Field, Int64Array, RecordBatch, Schema, StringArray};
use crate::proto::{WidgetState, WidgetStates, element, forward_msg, widget_state};
use serde_json::json;
use std::sync::Arc;

fn qty_label_batch(nullable: [bool; 2]) -> TestResult<RecordBatch> {
    let fields = vec![Field::new("qty", crate::data::DataType::Int64, nullable[0]), Field::new("label", crate::data::DataType::Utf8, nullable[1])];
    let arrays = vec![Arc::new(Int64Array::from(vec![1, 2])) as _, Arc::new(StringArray::from(vec!["a", "b"])) as _];
    Ok(RecordBatch::try_new(Arc::new(Schema::new(fields)), arrays)?)
}

#[test]
fn positive_out_of_range_deletions_return_error_without_panicking() -> TestResult {
    let original = qty_label_batch([false, false])?;
    let snapshot = original.clone();
    let reference: serde_json::Value = serde_json::from_str(include_str!("../../../tests/reference/reference-browser/dataeditor-invalid-rows/observations.json"))?;
    assert_eq!(reference["versions"]["streamlit"], "1.66.1");
    let mut compared = 0;
    for case in reference["cases"].as_array().ok_or("editor reference must include cases")? {
        let edits: serde_json::Value = serde_json::from_str(case["input_string_value"].as_str().ok_or("recorded edits must be a string")?)?;
        let has_negative = edits["deleted_rows"].as_array().into_iter().flatten().any(|value| value.as_i64().is_some_and(|value| value < 0)) || edits["edited_rows"].as_object().into_iter().flatten().any(|(row, _)| row.starts_with('-'));
        if has_negative {
            continue; // 负索引是另一个未确认差异，不把现有拒绝行为定为新规则。
        }
        let result = crate::data_api::apply_edits_for_test(&original, &edits);
        if case["outcome"] == "exception" {
            assert!(result.is_err(), "reference exception must become a DataError: {}", case["name"]);
        } else {
            let returned = result?;
            let qty = returned.column(0).as_any().downcast_ref::<Int64Array>().ok_or("returned quantity must stay int64")?;
            let label = returned.column(1).as_any().downcast_ref::<StringArray>().ok_or("returned labels must stay text")?;
            let rows = (0..returned.num_rows()).map(|row| json!({"qty": qty.value(row), "label": label.value(row)})).collect::<Vec<_>>();
            assert_eq!(json!(rows), case["working_after"]["rows"], "{}", case["name"]);
        }
        assert_eq!(original, snapshot, "caller input must stay unchanged: {}", case["name"]);
        compared += 1;
    }
    assert_eq!(compared, 13);
    // Rust 内部空表边界，复用同一删除首行输入，不冒称另一次 Python 采证。
    assert!(crate::data_api::apply_edits_for_test(&original.slice(0, 0), &json!({"deleted_rows": [0]})).is_err());
    Ok(())
}

fn frozen_editor_stages() -> TestResult<Vec<(String, Option<String>)>> {
    let raw: serde_json::Value = serde_json::from_str(include_str!("../../../tests/reference/reference-browser/dataeditor/trace-dataeditor.json"))?;
    assert_eq!(raw["schema_version"], 1);
    assert_eq!(raw["observation"]["journey"], "dataeditor-grid");
    assert_eq!(raw["observation"]["contract"], "journey-dataeditor-v1");
    let mut inputs = Vec::new();
    let mut reference_id = None;
    for stage in raw["observation"]["stages"].as_array().ok_or("frozen editor stages must be an array")? {
        let name = stage["name"].as_str().ok_or("frozen editor stage must have a name")?;
        let requests: Vec<_> = stage["new_frames"].as_array().ok_or("frozen editor stage must include frames")?.iter().filter(|frame| frame["summary"]["type"] == "rerun_script").collect();
        assert_eq!(requests.len(), 1, "one browser rerun per frozen stage {name}");
        let states = requests[0]["summary"]["rerun_script"]["widget_states"].as_array().ok_or("frozen rerun must contain widget states")?;
        assert!(states.len() <= 1, "the measured editor has at most one state");
        let payload = if let Some(state) = states.first() {
            assert_eq!(state["value_field"], "string_value");
            let id = state["id"].as_str().ok_or("frozen editor state must have an id")?;
            assert!(id.starts_with("$$ID-") && id.ends_with("-editor"));
            assert_eq!(reference_id.get_or_insert_with(|| id.to_owned()), id, "frozen editor id is stable");
            Some(state["value"].as_str().ok_or("frozen editor state must carry its JSON string")?.to_owned())
        } else {
            None
        };
        inputs.push((name.to_owned(), payload));
    }
    assert_eq!(inputs.iter().map(|(name, _)| name.as_str()).collect::<Vec<_>>(), ["01-load", "02-edit-cell", "03-add-row", "04-edit-added-row"]);
    Ok(inputs)
}

fn dataeditor_entry(st: &Streamlit) -> Pin<Box<dyn Future<Output = ()> + '_>> {
    Box::pin(async move {
        let result: TestResult = async {
            // Frozen Python edits are reused with a Rust-only nonnullable input boundary.
            let original = qty_label_batch([false, false])?;
            let snapshot = original.clone();
            let edited = st.data_editor(crate::DataEditorOptions::new(&original).num_rows(crate::EditorRows::Dynamic).key("editor"))?;
            assert_eq!(original, snapshot, "editing must not mutate the caller input batch");
            st.dataframe(crate::DataframeOptions::new(&edited))?;
            st.write(format!("rows={}", edited.num_rows()));

            Ok(())
        }
        .await;

        assert!(result.is_ok(), "dataeditor fixture must render successfully: {result:?}");
    })
}

fn editor_recovery_entry(st: &Streamlit) -> Pin<Box<dyn Future<Output = ()> + '_>> {
    Box::pin(async move {
        let result: TestResult = (|| {
            let original = qty_label_batch([true, true])?;
            let snapshot = original.clone();
            match st.data_editor(crate::DataEditorOptions::new(&original).num_rows(crate::EditorRows::Dynamic).key("editor")) {
                Ok(edited) => {
                    st.dataframe(&edited)?;
                    st.write(format!("rows={}", edited.num_rows()));
                }
                Err(error) => st.write(format!("editor-error: {error}")),
            }
            assert_eq!(original, snapshot);
            Ok(())
        })();
        assert!(result.is_ok(), "recovery fixture setup failed: {result:?}");
    })
}

#[actix_web::test]
async fn frozen_invalid_editor_input_recovers_on_the_same_websocket() -> TestResult {
    let reference: serde_json::Value = serde_json::from_str(include_str!("../../../tests/reference/reference-browser/dataeditor-invalid-rows/protocol-first/protocol-input-output.json"))?;
    assert_eq!(reference["reference_version"], "1.66.1");
    let expected = reference["stages"].as_array().ok_or("protocol stages are missing")?.clone();
    assert_eq!(expected.len(), 4);
    let stages = expected.clone();
    let listener = std::net::TcpListener::bind("127.0.0.1:0")?;
    let address = listener.local_addr()?;
    let server = HttpServer::new(move || App::new().app_data(web::Data::new(StreamlitServer::new(editor_recovery_entry, "127.0.0.1".into(), 0))).configure(configure_routes))
        .workers(1)
        .listen(listener)?
        .run();
    let handle = server.handle();
    let task = actix_web::rt::spawn(server);
    let mut capture = actix_web::rt::spawn(async move {
        let mut stream = sessions::connect(address, None).await;
        let (mut editor_id, mut session_id) = (String::new(), String::new());
        let mut runs = Vec::new();
        for stage in stages {
            let widgets = stage["input_string_value"]
                .as_str()
                .map(|payload| {
                    vec![WidgetState {
                        id: editor_id.clone(),
                        value: Some(widget_state::Value::StringValue(payload.into())),
                    }]
                })
                .unwrap_or_default();
            send_binary(
                &mut stream,
                &BackMsg {
                    r#type: Some(back_msg::Type::RerunScript(ClientState {
                        widget_states: Some(WidgetStates { widgets }),
                        ..Default::default()
                    })),
                }
                .encode_to_vec(),
            )
            .await;
            let (mut frames, mut messages, mut finishes) = (Vec::new(), Vec::new(), Vec::new());
            loop {
                match receive(&mut stream).await.r#type {
                    Some(forward_msg::Type::NewSession(run)) => {
                        let id = run.initialize.ok_or("new session initialization is missing")?.session_id;
                        if session_id.is_empty() {
                            session_id = id;
                        } else {
                            assert_eq!(session_id, id);
                        }
                    }
                    Some(forward_msg::Type::Delta(delta)) => {
                        if let Some(delta::Type::NewElement(element)) = delta.r#type {
                            match element.r#type {
                                Some(element::Type::Dataframe(frame)) => {
                                    if frame.editing_mode == 2 {
                                        if editor_id.is_empty() {
                                            editor_id = frame.id.clone();
                                        } else {
                                            assert_eq!(editor_id, frame.id);
                                        }
                                    }
                                    frames.push(frame);
                                }
                                Some(element::Type::Markdown(message)) => messages.push(message.body),
                                _ => {}
                            }
                        }
                    }
                    Some(forward_msg::Type::ScriptFinished(status)) => finishes.push(status),
                    Some(forward_msg::Type::SessionStatusChanged(status)) if !status.script_is_running => break,
                    _ => {}
                }
            }
            runs.push((frames, messages, finishes));
        }
        Ok::<_, Box<dyn std::error::Error>>(runs)
    });
    // 任一输入失败也先回收连接任务与自有 server，再进行输出断言。
    let captured = tokio::time::timeout(Duration::from_secs(10), &mut capture).await;
    if captured.is_err() {
        capture.abort();
        let _ = capture.await;
    }
    handle.stop(false).await;
    task.await??;
    let runs = captured???;
    for (expected, (frames, messages, finishes)) in expected.iter().zip(runs) {
        assert_eq!(finishes, [0]);
        println!("editor recovery stage={} frames={} messages={messages:?} finishes={finishes:?}", expected["name"], frames.len());
        if !expected["exceptions"].as_array().ok_or("reference exceptions are missing")?.is_empty() {
            assert!(frames.is_empty(), "invalid editing must not emit a partial table");
            assert!(messages.iter().any(|message| message.starts_with("editor-error:") && message.contains("out of range")));
            continue;
        }
        assert_eq!(messages, serde_json::from_value::<Vec<String>>(expected["markdowns"].clone())?);
        let expected_frames = expected["dataframes"].as_array().ok_or("reference dataframes are missing")?;
        assert_eq!(frames.len(), expected_frames.len());
        for (frame, expected) in frames.iter().zip(expected_frames) {
            let batch = crate::data::from_ipc_stream(&frame.arrow_data.as_ref().ok_or("frame data is missing")?.data)?.into_iter().next().ok_or("frame must contain a batch")?;
            let qty = batch.column(0).as_any().downcast_ref::<Int64Array>().ok_or("qty must be int64")?;
            let labels = batch.column(1).as_any().downcast_ref::<crate::data::LargeStringArray>().ok_or("labels must be large text")?;
            let actual = (0..batch.num_rows()).map(|row| json!({"qty": qty.value(row), "label": labels.value(row)})).collect::<Vec<_>>();
            assert_eq!(json!(actual), expected["rows"]);
        }
    }
    Ok(())
}

#[actix_web::test]
async fn committed_edits_apply_serverside_over_the_production_websocket() -> TestResult {
    let inputs = frozen_editor_stages()?;
    let capture_inputs = inputs.clone();
    let listener = std::net::TcpListener::bind("127.0.0.1:0")?;
    let address = listener.local_addr()?;
    let server = HttpServer::new(move || App::new().app_data(web::Data::new(StreamlitServer::new(dataeditor_entry, "127.0.0.1".into(), 0))).configure(configure_routes))
        .workers(1)
        .listen(listener)?
        .run();
    let handle = server.handle();
    let task = actix_web::rt::spawn(server);
    let mut capture_task = actix_web::rt::spawn(async move {
        let mut stream = sessions::connect(address, None).await;
        let mut editor_id = String::new();
        let mut runs = Vec::new();
        let mut finishes = Vec::new();
        for (_, state) in capture_inputs {
            let widgets = if let Some(payload) = state {
                assert!(!editor_id.is_empty(), "load must provide the native editor id");
                vec![WidgetState {
                    id: editor_id.clone(),
                    value: Some(widget_state::Value::StringValue(payload)),
                }]
            } else {
                vec![]
            };
            send_binary(
                &mut stream,
                &BackMsg {
                    r#type: Some(back_msg::Type::RerunScript(ClientState {
                        widget_states: Some(WidgetStates { widgets }),
                        ..Default::default()
                    })),
                }
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
                    Some(forward_msg::Type::ScriptFinished(status)) => {
                        assert_eq!(status, 0);
                        finishes.push(status);
                    }
                    Some(forward_msg::Type::SessionStatusChanged(_)) => {}
                    other => panic!("unexpected lifecycle response: {other:?}"),
                }
            }
            runs.push((dataframes, trailing));
        }
        Ok::<_, Box<dyn std::error::Error>>((runs, finishes))
    });
    let captured = tokio::time::timeout(Duration::from_secs(10), &mut capture_task).await;
    if captured.is_err() {
        capture_task.abort();
        let _ = capture_task.await;
    }
    handle.stop(false).await;
    task.await??;
    let (runs, finishes) = captured???;
    assert_eq!(finishes, [0, 0, 0, 0]);
    assert_eq!(runs.len(), inputs.len());
    // Values follow the existing Python wire; nullability flags are the selected Rust contract.
    let expected = [
        ("rows=2", vec![Some(1.0), Some(2.0)], true, [false, false]),
        ("rows=2", vec![Some(7.0), Some(2.0)], true, [false, false]),
        ("rows=3", vec![Some(7.0), Some(2.0), None], false, [true, true]),
        ("rows=3", vec![Some(7.0), Some(2.0), Some(9.0)], true, [false, true]),
    ];
    for (((name, state), (dataframes, trailing)), (expected_rows, expected_qty, expect_int, expected_nullable)) in inputs.into_iter().zip(runs).zip(expected) {
        let state = state.as_deref().unwrap_or("{}");
        assert_eq!(trailing, expected_rows, "the edits change the row count the app sees");
        assert_eq!(dataframes.len(), 2, "the editor and the written table");
        // The editor element keeps the ORIGINAL table; the written table
        // carries the applied edits, int columns upcasting to float64 under
        // an added null like pandas.
        let editor = &dataframes[0];
        let editor_batch: RecordBatch = crate::data::from_ipc_stream(&editor.arrow_data.as_ref().ok_or("data editor must emit its Arrow data")?.data)?.remove(0);
        assert_eq!(
            editor_batch.schema().fields().iter().map(|field| field.is_nullable()).collect::<Vec<_>>(),
            [false, false],
            "editor must keep the original nonnullable schema"
        );
        let editor_labels = editor_batch
            .column_by_name("label")
            .ok_or("editor must retain original label column")?
            .as_any()
            .downcast_ref::<crate::data::LargeStringArray>()
            .ok_or("editor labels must be LargeStringArray")?;
        assert_eq!(editor_labels.iter().collect::<Vec<_>>(), [Some("a"), Some("b")], "editor must keep the original labels");
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
        assert_eq!(
            decoded.schema().fields().iter().map(|field| field.is_nullable()).collect::<Vec<_>>(),
            expected_nullable,
            "only output columns containing null become nullable at {name}"
        );
    }
    Ok(())
}

#[test]
fn nonnullable_inputs_relax_only_columns_with_output_nulls() -> TestResult {
    let stages = frozen_editor_stages()?;
    let empty_row: serde_json::Value = serde_json::from_str(stages[2].1.as_deref().ok_or("frozen add-row stage must include edits")?)?;
    let qty_filled: serde_json::Value = serde_json::from_str(stages[3].1.as_deref().ok_or("frozen added-row edit stage must include edits")?)?;
    let ordinary = RecordBatch::try_from_iter(vec![
        ("qty", Arc::new(Int64Array::from(vec![1, 2])) as crate::data::ArrayRef),
        ("label", Arc::new(StringArray::from(vec!["a", "b"])) as crate::data::ArrayRef),
    ])?;
    assert_eq!(ordinary.schema().fields().iter().map(|field| field.is_nullable()).collect::<Vec<_>>(), [false, false]);
    let cases = [
        ("nonnullable qty", qty_label_batch([false, true])?, [false, true]),
        ("nonnullable label", qty_label_batch([true, false])?, [true, true]),
        ("nonnullable both", qty_label_batch([false, false])?, [false, true]),
        ("try_from_iter", ordinary, [false, true]),
    ];
    for (case, batch, filled_nullable) in cases {
        let original = batch.clone();
        let result = data_editor_edits_for_test(&batch, &empty_row);
        assert!(result.is_ok(), "{case}: applying the frozen empty row must succeed: {result:?}");
        let empty = result?;
        assert_eq!(empty.schema().fields().iter().map(|field| field.is_nullable()).collect::<Vec<_>>(), [true, true], "{case}");
        assert_eq!(empty.column(0).data_type(), &crate::data::DataType::Float64, "{case}: added numeric null retains the measured upcast");
        assert_eq!(empty.columns().iter().map(|column| column.null_count()).collect::<Vec<_>>(), [1, 1], "{case}");

        let filled = data_editor_edits_for_test(&batch, &qty_filled)?;
        assert_eq!(filled.schema().fields().iter().map(|field| field.is_nullable()).collect::<Vec<_>>(), filled_nullable, "{case}: a filled qty column keeps its original flag");
        assert_eq!(filled.column(0).data_type(), &crate::data::DataType::Int64);
        assert_eq!(filled.columns().iter().map(|column| column.null_count()).collect::<Vec<_>>(), [0, 1]);
        assert_eq!(batch, original, "{case}: original schema and contents remain unchanged");
    }

    // Rust-only controls extend the frozen edits explicitly; these inputs were not browser captures.
    let batch = qty_label_batch([false, false])?;
    let original = batch.clone();
    let mut label_filled = empty_row;
    label_filled["added_rows"][0]["label"] = json!("c");
    let only_qty_null = data_editor_edits_for_test(&batch, &label_filled)?;
    assert_eq!(only_qty_null.schema().fields().iter().map(|field| field.is_nullable()).collect::<Vec<_>>(), [true, false], "a complete text column must not be widened");
    assert_eq!(only_qty_null.column(0).data_type(), &crate::data::DataType::Float64);
    assert_eq!(only_qty_null.columns().iter().map(|column| column.null_count()).collect::<Vec<_>>(), [1, 0]);

    let mut fully_filled = qty_filled;
    fully_filled["added_rows"][0]["label"] = json!("c");
    let complete = data_editor_edits_for_test(&batch, &fully_filled)?;
    assert_eq!(complete.schema().fields().iter().map(|field| field.is_nullable()).collect::<Vec<_>>(), [false, false], "fully populated output keeps both flags");
    assert_eq!(complete.column(0).data_type(), &crate::data::DataType::Int64);
    assert_eq!(complete.columns().iter().map(|column| column.null_count()).collect::<Vec<_>>(), [0, 0]);
    assert_eq!(batch, original, "the controls also leave original schema and contents unchanged");
    Ok(())
}

#[test]
fn apply_edits_follows_the_reference_order() -> TestResult {
    let batch = qty_label_batch([false, false])?;
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
