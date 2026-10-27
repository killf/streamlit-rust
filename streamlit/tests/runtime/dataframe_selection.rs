//! Frozen frontend and explicit protocol selection inputs replayed over production WS.
//! Canvas geometry and visual sorting were verified by the Python capture;
//! the required-row protocol supplement makes no browser-interaction claim.
use super::*;
use crate::data::{ArrayRef, DataType, Field, Int64Array, RecordBatch, Schema, StringArray};
use crate::{DataApi, DataframeOptions, DataframeSelection, DataframeSelectionMode, OnSelect};
use serde::{Deserialize, Serialize};
use serde_json::{Value, json};
use std::sync::Arc;

const REFERENCE: &str = include_str!("../../../tests/reference/reference-browser/dataframe-selection/selection-input-output.json");
const REQUIRED_PROTOCOL_REFERENCE: &str = include_str!("../../../tests/reference/reference-browser/dataframe-required-protocol/required-protocol-input-output.json");

#[derive(Deserialize)]
struct Reference {
    schema_version: u32,
    reference_version: String,
    stages: Vec<Stage>,
}

#[derive(Clone, Deserialize)]
struct Stage {
    case: String,
    name: String,
    did_run: bool,
    frame_start: usize,
    frame_end: usize,
    input_rows: Vec<Row>,
    version: u64,
    visible: bool,
    run: u64,
    trigger: Option<String>,
    before: Value,
    expected_returned: Value,
    expected_key_present: bool,
    expected_keyed: Value,
    events: Vec<Value>,
    target_widget_states: Vec<SelectionInput>,
    #[serde(default)]
    all_widget_inputs: Vec<Value>,
    dataframes: Vec<CapturedDataframe>,
}

#[derive(Clone, Deserialize, Serialize)]
struct Row {
    id: String,
    qty: i64,
    label: String,
}

#[derive(Clone, Deserialize)]
struct SelectionInput {
    id: String,
    message_oneof: Option<String>,
    value_oneof: String,
    value: String,
}

#[derive(Clone, Deserialize)]
struct CapturedDataframe {
    delta_path: Vec<u32>,
    fields: Value,
}

fn selection_reference() -> TestResult<Reference> {
    let mut reference: Reference = serde_json::from_str(REFERENCE)?;
    assert_eq!(reference.schema_version, 1);
    assert_eq!(reference.reference_version, "1.66.1");
    assert_eq!(reference.stages.len(), 34);
    let protocol: Value = serde_json::from_str(REQUIRED_PROTOCOL_REFERENCE)?;
    assert_eq!(protocol["schema_version"], 1);
    assert_eq!(protocol["reference_version"], "1.66.1");
    assert_eq!(protocol["transport"], "native-websocket-protocol-probe");
    let stages = protocol["stages"].as_array().ok_or("required protocol reference must contain stages")?;
    assert_eq!(stages.len(), 8);

    // 仅适配紧凑参考的元数据；原始 widget oneof/value 和所有预期逐字保留。
    for stage in stages {
        let mut adapted = stage.clone();
        adapted["case"] = json!("required-protocol");
        adapted["did_run"] = json!(true);
        adapted["trigger"] = stage["button_trigger_label"].clone();
        reference.stages.push(serde_json::from_value(adapted)?);
    }
    Ok(reference)
}

fn input_batch(rows: &[Row]) -> TestResult<RecordBatch> {
    let fields = vec![Field::new("id", DataType::Utf8, true), Field::new("qty", DataType::Int64, true), Field::new("label", DataType::Utf8, true)];
    let columns: Vec<ArrayRef> = vec![
        Arc::new(StringArray::from(rows.iter().map(|row| row.id.as_str()).collect::<Vec<_>>())),
        Arc::new(Int64Array::from(rows.iter().map(|row| row.qty).collect::<Vec<_>>())),
        Arc::new(StringArray::from(rows.iter().map(|row| row.label.as_str()).collect::<Vec<_>>())),
    ];
    Ok(RecordBatch::try_new(Arc::new(Schema::new(fields)), columns)?)
}

fn record_callback(st: &Streamlit, key: &str) -> TestResult {
    let state = st.session_state();
    let mut events = state.get::<Vec<Value>>("events")?.unwrap_or_default();
    events.push(json!({"kind": "callback", "run_seen": state.get::<u64>("run")?.unwrap_or(0), "state": state.get::<Value>(key)?}));
    state.set("events", events)?;
    Ok(())
}

fn render_selection(st: &Streamlit) -> TestResult {
    let reference = selection_reference()?;
    let index: usize = st.query_params().get("stage").ok_or("selection fixture requires its stage index")?.parse()?;
    let stage = reference.stages.get(index).ok_or("selection fixture stage index is out of range")?;
    let state = st.session_state();
    let key = format!("selection-{}", stage.case);

    // 1. 主程序及程序写入复刻夹具动作；返回值和 keyed state 不从预期填充。
    let run = state.get::<u64>("run")?.unwrap_or(0) + 1;
    state.set("run", run)?;
    let mut events = state.get::<Vec<Value>>("events")?.unwrap_or_default();
    events.push(json!({"kind": "main", "run": run}));
    state.set("events", events)?;
    let before = state.get::<Value>(&key)?;

    st.caption(format!("Synthetic case: {}", stage.case));
    for (column, label) in st.columns(3).iter().zip(["Probe", "Replace data", "Toggle visible"]) {
        column.button(label);
    }
    if stage.case == "single-combo" {
        for (column, label) in st.columns(3).iter().zip(["Program rows", "Program columns", "Program cells"]) {
            column.button(label);
        }
    }
    if stage.case == "required-protocol" {
        for (column, label) in st.columns(3).iter().zip(["Empty table", "Restore table", "Program empty rows"]) {
            column.button(label);
        }
    }
    let program = match stage.trigger.as_deref() {
        Some("Program rows") => Some(json!({"rows": [0]})),
        Some("Program columns") => Some(json!({"columns": ["id"]})),
        Some("Program cells") => Some(json!({"cells": [[0, "qty"]]})),
        Some("Program empty rows") => Some(json!({"rows": []})),
        _ => None,
    };
    if let Some(selection) = program {
        state.set(&key, json!({"selection": selection}))?;
    }

    // 2. 使用原始输入表与官方模式组合；row_height=32 仅是 Python 夹具配置。
    let batch = input_batch(&stage.input_rows)?;
    let configs = ["id", "qty", "label"].into_iter().fold(crate::column_config::ColumnConfigs::new(), |configs, name| {
        configs.add(name, crate::column_config::column(crate::column_config::ColumnBase::new(None).width_px(160)))
    });
    let mut options = DataframeOptions::new(&batch).key(&key).hide_index(true).width(700).height(190).column_config(configs);
    match stage.case.as_str() {
        "ignore" => {}
        "multi" | "multi-shrink" => options = options.on_select(OnSelect::Rerun),
        "single-combo" => {
            let callback_key = key.clone();
            options = options
                .on_select(OnSelect::callback(move |st| {
                    if let Err(error) = record_callback(st, &callback_key) {
                        st.code(json!({"callback_error": error.to_string()}).to_string(), "json");
                    }
                }))
                .selection_modes([DataframeSelectionMode::SingleRow, DataframeSelectionMode::SingleColumn, DataframeSelectionMode::SingleCell])
                .selection_default(DataframeSelection {
                    rows: vec![1],
                    columns: vec!["qty".into()],
                    cells: vec![(2, "label".into())],
                });
        }
        "multi-combo" => {
            options = options
                .on_select(OnSelect::Rerun)
                .selection_modes([DataframeSelectionMode::MultiRow, DataframeSelectionMode::MultiColumn, DataframeSelectionMode::MultiCell])
        }
        "required" => options = options.on_select(OnSelect::Rerun).selection_mode(DataframeSelectionMode::SingleRowRequired),
        "required-protocol" => {
            let callback_key = key.clone();
            options = options.selection_mode(DataframeSelectionMode::SingleRowRequired).on_select(OnSelect::callback(move |st| {
                if let Err(error) = record_callback(st, &callback_key) {
                    st.code(json!({"callback_error": error.to_string()}).to_string(), "json");
                }
            }));
        }
        _ => return Err("unknown frozen selection case".into()),
    }
    let returned = if stage.visible { st.dataframe(options)? } else { None };
    let keyed = state.get::<Value>(&key)?;
    st.code(
        json!({"run": run, "version": stage.version, "visible": stage.visible, "before": before,
               "returned": returned, "key_present": keyed.is_some(), "keyed": keyed, "events": state.get::<Vec<Value>>("events")?})
        .to_string(),
        "json",
    );
    Ok(())
}

fn selection_entry(st: &Streamlit) -> Pin<Box<dyn Future<Output = ()> + '_>> {
    Box::pin(async move {
        if let Err(error) = render_selection(st) {
            st.code(json!({"fixture_error": error.to_string()}).to_string(), "json");
        }
    })
}

fn compare_report(report: &Value, stage: &Stage) {
    assert_eq!(report["run"], stage.run, "{} {} run", stage.case, stage.name);
    assert_eq!(report["version"], stage.version);
    assert_eq!(report["visible"], stage.visible);
    assert_eq!(report["before"], stage.before, "{} {} state before the call", stage.case, stage.name);
    assert_eq!(report["returned"], stage.expected_returned, "{} {} typed return", stage.case, stage.name);
    assert_eq!(report["key_present"], stage.expected_key_present);
    assert_eq!(report["keyed"], stage.expected_keyed, "{} {} raw keyed state, including partial program writes", stage.case, stage.name);
    assert_eq!(report["events"], json!(stage.events), "{} {} complete callback/main sequence", stage.case, stage.name);
}

fn selection_json(value: Option<&str>) -> TestResult<Option<Value>> {
    Ok(value.map(serde_json::from_str).transpose()?)
}

fn compare_dataframe(frame: &crate::proto::Dataframe, path: &[u32], element: &crate::proto::Element, reference: &CapturedDataframe) -> TestResult {
    assert_eq!(path, reference.delta_path);
    let expected_columns = reference.fields["columns"].as_str().ok_or("frozen dataframe must contain its columns JSON")?;
    assert_eq!(serde_json::from_str::<Value>(&frame.columns)?, serde_json::from_str::<Value>(expected_columns)?);
    let actual_modes = frame
        .selection_mode
        .iter()
        .map(|mode| crate::proto::dataframe::SelectionMode::try_from(*mode).map(|mode| mode.as_str_name().to_owned()))
        .collect::<Result<Vec<_>, _>>()?;
    let expected_modes: Vec<String> = reference.fields.get("selection_mode").map_or_else(|| Ok(Vec::new()), |modes| serde_json::from_value(modes.clone()))?;
    assert_eq!(actual_modes, expected_modes);
    for (actual, name) in [(frame.selection_state.as_deref(), "selection_state"), (frame.selection_default.as_deref(), "selection_default")] {
        let expected = reference.fields.get(name).and_then(Value::as_str).map(serde_json::from_str::<Value>).transpose()?;
        assert_eq!(selection_json(actual)?, expected, "dataframe {name} presence and value");
    }
    assert_eq!(element.width_config.as_ref().and_then(|config| config.width_spec.as_ref()), Some(&crate::proto::streamlit::width_config::WidthSpec::PixelWidth(700)));
    assert_eq!(element.height_config.as_ref().and_then(|config| config.height_spec.as_ref()), Some(&crate::proto::streamlit::height_config::HeightSpec::PixelHeight(190)));
    Ok(())
}

async fn replay(address: std::net::SocketAddr, stages: Vec<Stage>) -> TestResult {
    let mut stream = sessions::connect(address, None).await;
    let mut case = String::new();
    let mut native_id = String::new();
    let mut button_ids: std::collections::HashMap<String, String> = std::collections::HashMap::new();
    let mut session_id = None;
    let mut last_report = None;
    for (index, stage) in stages.iter().enumerate() {
        if case != stage.case {
            if !case.is_empty() {
                stream = sessions::connect(address, None).await;
            }
            case.clone_from(&stage.case);
            native_id.clear();
            button_ids.clear();
            session_id = None;
            last_report = None;
        }

        // 3. 无浏览器重跑的阶段不制造 rerun；WS 只确认空闲，排序几何留给原始采集。
        if !stage.did_run {
            assert_eq!(stage.frame_start, stage.frame_end);
            assert!(stage.target_widget_states.is_empty());
            compare_report(last_report.as_ref().ok_or("bounded stage must follow a completed run")?, stage);
            send_binary(&mut stream, &[0x88, 0x01, 0x01]).await;
            assert!(matches!(receive(&mut stream).await.r#type, Some(forward_msg::Type::HeartbeatAck(true))));
            assert!(tokio::time::timeout(Duration::from_millis(75), stream.read_u8()).await.is_err(), "bounded stage must not execute main");
            continue;
        }

        let mut widgets = Vec::new();
        for input in &stage.target_widget_states {
            assert_eq!(input.message_oneof.as_deref(), if stage.case == "required-protocol" { None } else { Some("rerun_script") });
            assert_eq!(input.value_oneof, "string_value");
            assert!(input.id.ends_with(&format!("-selection-{}", stage.case)));
            assert!(!native_id.is_empty(), "a completed load supplies the actual native id");
            widgets.push(WidgetState {
                id: native_id.clone(),
                value: Some(widget_state::Value::StringValue(input.value.clone())),
            });
        }
        if stage.case == "required-protocol" {
            let mut trigger_count = 0;
            for input in &stage.all_widget_inputs {
                match input["value_oneof"].as_str() {
                    Some("string_value") => assert!(stage.target_widget_states.iter().any(|target| input["id"] == target.id && input["value"] == target.value)),
                    Some("trigger_value") => {
                        let label = stage.trigger.as_ref().ok_or("required protocol trigger must have its recorded button label")?;
                        let id = button_ids.get(label).ok_or("required protocol button must be rendered before its trigger")?;
                        assert_eq!(input["value"], true);
                        widgets.push(WidgetState {
                            id: id.clone(),
                            value: Some(widget_state::Value::TriggerValue(true)),
                        });
                        trigger_count += 1;
                    }
                    _ => return Err("unexpected required protocol widget oneof".into()),
                }
            }
            assert_eq!(trigger_count, usize::from(stage.trigger.is_some()));
        }
        send_binary(
            &mut stream,
            &BackMsg {
                r#type: Some(back_msg::Type::RerunScript(ClientState {
                    query_string: format!("stage={index}"),
                    widget_states: Some(WidgetStates { widgets }),
                    ..Default::default()
                })),
            }
            .encode_to_vec(),
        )
        .await;

        let mut reports = Vec::new();
        let mut dataframes = Vec::new();
        let mut finishes = Vec::new();
        loop {
            let message = receive(&mut stream).await;
            match message.r#type {
                Some(forward_msg::Type::NewSession(new)) => {
                    let id = new.initialize.ok_or("selection NewSession must carry initialization")?.session_id;
                    assert_eq!(session_id.get_or_insert_with(|| id.clone()), &id, "each case retains one session");
                }
                Some(forward_msg::Type::Delta(delta)) => {
                    if let Some(delta::Type::NewElement(element)) = delta.r#type {
                        match element.r#type.as_ref() {
                            Some(element::Type::Dataframe(frame)) => dataframes.push((message.metadata.ok_or("dataframe requires its delta path")?.delta_path, frame.clone(), element)),
                            Some(element::Type::Code(code)) => reports.push(serde_json::from_str::<Value>(&code.code_text)?),
                            Some(element::Type::Button(button)) => {
                                button_ids.insert(button.label.clone(), button.id.clone());
                            }
                            _ => {}
                        }
                    }
                }
                Some(forward_msg::Type::ScriptFinished(status)) => finishes.push(status),
                Some(forward_msg::Type::SessionStatusChanged(status)) if !status.script_is_running => break,
                _ => {}
            }
        }
        assert_eq!(finishes, [0], "{} {} finishes successfully once", stage.case, stage.name);
        assert_eq!(reports.len(), 1, "{} {} reports or fixture errors: {reports:?}", stage.case, stage.name);
        let report = reports.pop().ok_or("selection run requires its report")?;
        compare_report(&report, stage);
        last_report = Some(report);
        assert_eq!(dataframes.len(), stage.dataframes.len(), "hidden runs must not render a dataframe");
        for ((path, frame, element), captured) in dataframes.iter().zip(&stage.dataframes) {
            compare_dataframe(frame, path, element, captured)?;
            if stage.case == "ignore" {
                assert!(frame.id.is_empty(), "Ignore does not register a selection widget");
            } else {
                assert!(frame.id.ends_with(&format!("-selection-{}", stage.case)));
                if native_id.is_empty() {
                    native_id.clone_from(&frame.id);
                }
                assert_eq!(native_id, frame.id, "keyed table identity survives replacement, shrinking, and restoration");
            }
        }
    }
    Ok(())
}

#[actix_web::test]
async fn frozen_dataframe_selection_inputs_match_return_state_callbacks_and_wire() -> TestResult {
    let reference = selection_reference()?;
    assert_eq!(reference.stages.len(), 42);
    let listener = std::net::TcpListener::bind("127.0.0.1:0")?;
    let address = listener.local_addr()?;
    let server = HttpServer::new(move || App::new().app_data(web::Data::new(StreamlitServer::new(selection_entry, "127.0.0.1".into(), 0))).configure(configure_routes))
        .workers(1)
        .listen(listener)?
        .run();
    let handle = server.handle();
    let server_task = actix_web::rt::spawn(server);
    let mut capture_task = actix_web::rt::spawn(replay(address, reference.stages));
    let captured = tokio::time::timeout(Duration::from_secs(20), &mut capture_task).await;
    if captured.is_err() {
        capture_task.abort();
        let _ = capture_task.await;
    }
    handle.stop(false).await;
    server_task.await??;
    captured???;
    Ok(())
}
