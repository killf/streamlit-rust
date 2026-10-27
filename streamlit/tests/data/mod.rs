use super::*;
use crate::Streamlit;
use crate::data::{ArrayRef, BooleanArray, Field, Float64Array, Int64Array, LargeStringArray, Schema, StringArray, from_ipc_stream};
use crate::elements::common::RenderContext;
use crate::proto::{ForwardMsg, delta, forward_msg};
use anyhow::Context;
use prost::Message;
use std::sync::Arc;

fn reference() -> anyhow::Result<Value> {
    Ok(serde_json::from_str(include_str!("../../../tests/reference/reference-browser/data-loop/upload/trace-data-loop.json"))?)
}

fn reference_element(kind: &str) -> anyhow::Result<Value> {
    reference()?["frames"]
        .as_array()
        .context("upload reference must contain its frames array")?
        .iter()
        .find_map(|frame| {
            let delta = &frame["decoded"]["delta"];
            (delta["element"] == kind).then(|| delta["element_full"].clone())
        })
        .with_context(|| format!("upload reference must contain {kind} element"))
}

fn reference_batch() -> anyhow::Result<RecordBatch> {
    from_ipc_stream(include_bytes!("../../../tests/reference/reference-browser/data-loop/upload/arrow-1.bin"))?
        .into_iter()
        .next()
        .context("upload Arrow reference must contain a record batch")
}

fn native_reference_batch() -> anyhow::Result<RecordBatch> {
    let original = reference_batch()?;
    // Recreate every value in native Rust arrays, preserving the actual
    // captured nullable flags and schema metadata instead of inventing pandas.
    RecordBatch::try_new(
        original.schema(),
        vec![
            Arc::new(LargeStringArray::from(vec!["Books", "Games", "Music", "Toys"])),
            Arc::new(Int64Array::from(vec![3, 3, 3, 3])),
            Arc::new(Float64Array::from(vec![245.75, 409.48, 139.0, 104.49])),
            Arc::new(Float64Array::from(vec![81.92, 136.49, 46.33, 34.83])),
        ],
    )
    .map_err(Into::into)
}

fn render<T>(call: impl FnOnce(&Streamlit) -> Result<T, DataError>) -> anyhow::Result<(ForwardMsg, Vec<u32>)> {
    let st = Streamlit::new();
    let (sender, mut receiver) = tokio::sync::mpsc::unbounded_channel();
    let mut context = RenderContext::with_sender("data-test".into(), sender);
    context.delta_path = vec![0, 0];
    context.active_script_hash = "data-script".into();
    st.app.lock().set_render_context(context);

    call(&st)?;
    let message = receiver.try_recv()?;
    assert!(receiver.try_recv().is_err());

    let decoded = ForwardMsg::decode(message.encode_to_vec().as_slice())?;
    assert_eq!(decoded.metadata.as_ref().context("rendered data message must contain metadata")?.delta_path, vec![0, 0]);
    assert_eq!(decoded.metadata.as_ref().context("rendered data message must contain metadata")?.active_script_hash, "data-script");
    let path = st.app.lock().render_context_mut().context("data test must retain its render context")?.delta_path.clone();

    Ok((decoded, path))
}

fn new_element(message: ForwardMsg) -> proto::Element {
    let Some(forward_msg::Type::Delta(delta)) = message.r#type else { panic!("missing delta") };
    let Some(delta::Type::NewElement(element)) = delta.r#type else { panic!("missing element") };
    element
}

#[test]
fn native_ipc_stream_preserves_the_reference_schema_rows_and_metadata() -> anyhow::Result<()> {
    let native = native_reference_batch()?;
    assert_eq!(native, reference_batch()?);
    let encoded = to_ipc_stream(&native)?;
    assert_eq!(&encoded[..4], &[255; 4]);
    assert!(!encoded.starts_with(b"ARROW1"));
    let decoded = from_ipc_stream(&encoded)?;
    assert_eq!(decoded, vec![native]);
    let pandas: Value = serde_json::from_str(decoded[0].schema().metadata().get("pandas").context("Arrow batch must retain its pandas metadata")?)?;
    assert_eq!(pandas["index_columns"][0]["kind"], "range");
    assert_eq!(pandas["index_columns"][0]["stop"], 4);

    Ok(())
}

#[test]
fn native_ipc_roundtrips_null_utf8_numeric_boolean_and_empty_data() -> anyhow::Result<()> {
    let schema = Arc::new(
        Schema::new(vec![
            Field::new("text", DataType::Utf8, true),
            Field::new("number", DataType::Int64, true),
            Field::new("value", DataType::Float64, true),
            Field::new("flag", DataType::Boolean, true),
        ])
        .with_metadata(std::collections::BTreeMap::from([("origin".to_string(), "native-rust".to_string())])),
    );
    let arrays: Vec<ArrayRef> = vec![
        Arc::new(StringArray::from(vec![Some("中文 🦀"), None, Some("")])),
        Arc::new(Int64Array::from(vec![Some(i64::MAX), None, Some(i64::MIN)])),
        Arc::new(Float64Array::from(vec![None, Some(-12.5), Some(0.0)])),
        Arc::new(BooleanArray::from(vec![Some(true), Some(false), None])),
    ];
    let batch = RecordBatch::try_new(schema.clone(), arrays)?;
    assert_eq!(from_ipc_stream(&to_ipc_stream(&batch)?)?, vec![batch]);
    let empty = RecordBatch::new_empty(schema);
    assert_eq!(from_ipc_stream(&to_ipc_stream(&empty)?)?, vec![empty]);

    Ok(())
}

#[test]
fn malformed_ipc_and_mismatched_schema_or_lengths_return_errors() -> anyhow::Result<()> {
    assert!(from_ipc_stream(b"ARROW1not-a-stream").is_err());
    let encoded = to_ipc_stream(&native_reference_batch()?)?;
    assert!(from_ipc_stream(&encoded[..encoded.len() / 2]).is_err());
    let schema = Arc::new(Schema::new(vec![Field::new("a", DataType::Int64, false), Field::new("b", DataType::Utf8, false)]));
    assert!(RecordBatch::try_new(schema.clone(), vec![Arc::new(Int64Array::from(vec![1, 2])), Arc::new(StringArray::from(vec!["one"]))]).is_err());
    assert!(RecordBatch::try_new(schema, vec![Arc::new(Int64Array::from(vec![1])), Arc::new(Int64Array::from(vec![2]))]).is_err());

    Ok(())
}

#[test]
fn dataframe_matches_full_captured_element_with_logical_ipc_comparison() -> anyhow::Result<()> {
    let batch = native_reference_batch()?;
    let (message, path) = render(|st| st.dataframe(DataframeOptions::new(&batch).hide_index(true).column_order(["group_key", "row_count", "total_amount", "avg_amount"])))?;
    assert_eq!(path, vec![0, 1]);
    let element = new_element(message);
    let captured = reference_element("dataframe")?;
    let expected_columns: Value = serde_json::from_str(captured["dataframe"]["columns"].as_str().context("data reference requires captured[\"dataframe\"][\"columns\"].as_str()")?)?;
    let Some(element::Type::Dataframe(frame)) = element.r#type else { panic!("missing dataframe") };
    let actual_columns: Value = serde_json::from_str(&frame.columns)?;
    assert_eq!(actual_columns, expected_columns);
    assert_eq!(from_ipc_stream(&frame.arrow_data.as_ref().context("rendered table must contain its Arrow data")?.data)?, vec![batch]);
    let expected = proto::Dataframe {
        arrow_data: frame.arrow_data.clone(),
        columns: frame.columns.clone(),
        column_order: captured["dataframe"]["columnOrder"]
            .as_array()
            .context("data reference requires captured[\"dataframe\"][\"columnOrder\"].as_array()")?
            .iter()
            .map(|v| v.as_str().context("reference column order entries must be strings").map(str::to_owned))
            .collect::<anyhow::Result<Vec<_>>>()?,
        ..Default::default()
    };
    assert_eq!(frame, expected, "all non-IPC fields must match captured presence/defaults");
    assert_eq!(
        element.width_config.context("rendered data element must contain width_config")?.width_spec,
        Some(proto::streamlit::width_config::WidthSpec::UseStretch(true))
    );
    assert!(element.height_config.is_none());
    assert!(element.text_alignment_config.is_none());
    assert!(element.has_one_shot_effect.is_none());
    assert_eq!(captured["widthConfig"]["useStretch"], true);

    Ok(())
}

#[test]
fn configured_bar_matches_real_altair_bar_spec_without_claiming_default_bar_chart_parity() -> anyhow::Result<()> {
    let batch = native_reference_batch()?;
    let options = BarChartOptions::new(&batch, "group_key", "total_amount")
        .x_order(["Books", "Games", "Music", "Toys"])
        .tooltip("group_key", "group")
        .tooltip("row_count", "rows")
        .tooltip("total_amount", "total")
        .tooltip("avg_amount", "avg")
        .plot_height(260);
    let (message, _) = render(|st| st.bar_chart(options))?;
    let element = new_element(message);
    let Some(element::Type::VegaLiteChart(chart)) = element.r#type else { panic!("missing chart") };
    let capture = reference_element("vega_lite_chart")?;
    let mut expected: Value = serde_json::from_str(capture["vegaLiteChart"]["spec"].as_str().context("data reference requires capture[\"vegaLiteChart\"][\"spec\"].as_str()")?)?;
    let actual: Value = serde_json::from_str(&chart.spec)?;
    // Dataset names are opaque content hashes, not frontend-visible semantics.
    expected["data"]["name"] = actual["data"]["name"].clone();
    // The capture is a real st.altair_chart spec; the 2026-10-25 elements
    // chain measured st.bar_chart encoding string x axes as ordinal instead.
    expected["encoding"]["x"]["type"] = json!("ordinal");
    assert_eq!(actual, expected);
    assert!(chart.data.is_none());
    assert_eq!(chart.datasets.len(), 1);
    assert!(chart.datasets[0].has_name);
    assert_eq!(actual["data"]["name"], chart.datasets[0].name);
    assert_eq!(from_ipc_stream(&chart.datasets[0].data.as_ref().context("chart dataset must contain its Arrow data")?.data)?, vec![batch]);
    assert_eq!(chart.theme, capture["vegaLiteChart"]["theme"].as_str().context("data reference requires capture[\"vegaLiteChart\"][\"theme\"].as_str()")?);
    assert!(!chart.use_container_width);
    assert!(chart.id.is_empty() && chart.form_id.is_empty() && chart.selection_mode.is_empty());
    assert!(chart.alt.is_none());
    assert_eq!(
        element.width_config.context("rendered data element must contain width_config")?.width_spec,
        Some(proto::streamlit::width_config::WidthSpec::UseStretch(true))
    );
    assert_eq!(
        element.height_config.context("rendered data element must contain height_config")?.height_spec,
        Some(proto::streamlit::height_config::HeightSpec::UseContent(true))
    );

    Ok(())
}

#[test]
fn vega_literal_columns_are_escaped_once_without_renaming_arrow_fields() -> anyhow::Result<()> {
    let cases = [
        ("group.name", "amount[0]", r"group\.name", r"amount\[0\]"),
        (r"group\.name", r"amount\[0]", r"group\\\.name", r"amount\\\[0\]"),
        (r"group\\name", r"amount\value", r"group\\\\name", r"amount\\value"),
        ("group[name]", "amount.value", r"group\[name\]", r"amount\.value"),
        ("group_key", "amount", "group_key", "amount"),
    ];
    for (x, y, expected_x, expected_y) in cases {
        let batch = RecordBatch::try_from_iter(vec![(x, Arc::new(StringArray::from(vec!["North"])) as ArrayRef), (y, Arc::new(Int64Array::from(vec![42])) as ArrayRef)])?;
        let (message, _) = render(|st| st.bar_chart(BarChartOptions::new(&batch, x, y).tooltip(x, "Group literal").tooltip(y, "Amount literal")))?;
        let Some(element::Type::VegaLiteChart(chart)) = new_element(message).r#type else { panic!("missing chart") };
        let spec: Value = serde_json::from_str(&chart.spec)?;
        let bytes = &chart.datasets[0].data.as_ref().context("chart dataset must contain its Arrow data")?.data;
        let decoded = from_ipc_stream(bytes)?.remove(0);
        // The dataset rides the reference's pandas-3 IPC (large_string text
        // columns and the creator stamp); compare names and values logically.
        assert_eq!(decoded.schema().field(0).name(), x);
        assert_eq!(decoded.schema().field(1).name(), y);
        assert!(decoded.schema().metadata().contains_key("pandas"));
        let texts = decoded
            .column_by_name(x)
            .with_context(|| format!("decoded Arrow schema must retain column {:?}", x))?
            .as_any()
            .downcast_ref::<LargeStringArray>()
            .context("Arrow text column must be LargeStringArray")?;
        assert_eq!(texts.iter().map(|text| text.unwrap_or_default().to_string()).collect::<Vec<_>>(), vec!["North"]);
        let values = decoded
            .column_by_name(y)
            .with_context(|| format!("decoded Arrow schema must retain column {:?}", y))?
            .as_any()
            .downcast_ref::<Int64Array>()
            .context("Arrow numeric column must be Int64Array")?;
        assert_eq!(values.values().as_ref(), &[42]);
        if std::env::var_os("STREAMLIT_DATA_D1_PROBE").is_some() {
            // Optional verification output lets the actual Vega accessor consume
            // the API's spec and Python-decoded native IPC, without a JS runtime
            // becoming a requirement of the normal Rust test suite.
            let ipc_hex: String = bytes.iter().map(|b| format!("{b:02x}")).collect();
            println!("DATA_FIELD_PROBE={}", json!({"x":x,"y":y,"spec":spec,"ipc_hex":ipc_hex}));
        }
        assert_eq!(spec["encoding"]["x"]["field"], expected_x, "literal x column: {x:?}");
        assert_eq!(spec["encoding"]["y"]["field"], expected_y, "literal y column: {y:?}");
        assert_eq!(spec["encoding"]["tooltip"][0]["field"], expected_x);
        assert_eq!(spec["encoding"]["tooltip"][1]["field"], expected_y);
        assert_eq!(spec["encoding"]["tooltip"][0]["title"], "Group literal");
        assert_eq!(spec["encoding"]["tooltip"][1]["title"], "Amount literal");
    }

    Ok(())
}

#[test]
fn vega_escaped_paths_are_not_treated_as_alternate_schema_column_names() -> anyhow::Result<()> {
    let batch = RecordBatch::try_from_iter(vec![("group.name", Arc::new(StringArray::from(vec!["North"])) as ArrayRef), ("amount[0]", Arc::new(Int64Array::from(vec![42])) as ArrayRef)])?;
    let st = Streamlit::new();
    let (sender, mut receiver) = tokio::sync::mpsc::unbounded_channel();
    st.app.lock().set_render_context(RenderContext::with_sender("literal-schema-test".into(), sender));
    // Callers supply raw schema names. Already escaped names refer to different
    // literal columns, so they must not bypass missing-column validation.
    assert!(st.bar_chart(BarChartOptions::new(&batch, r"group\.name", "amount[0]")).is_err());
    assert!(st.bar_chart(BarChartOptions::new(&batch, "group.name", r"amount\[0\]")).is_err());
    assert!(st.bar_chart(BarChartOptions::new(&batch, "group.name", "amount[0]").tooltip(r"group\.name", "missing")).is_err());
    assert!(receiver.try_recv().is_err());

    Ok(())
}

#[test]
fn invalid_data_view_options_do_not_append_or_advance_the_render_path() -> anyhow::Result<()> {
    let batch = native_reference_batch()?;
    let st = Streamlit::new();
    let (sender, mut receiver) = tokio::sync::mpsc::unbounded_channel();
    let mut context = RenderContext::with_sender("bad-data".into(), sender);
    context.delta_path = vec![0, 0];
    st.app.lock().set_render_context(context);
    assert!(st.dataframe(DataframeOptions::new(&batch).width(0)).is_err());
    assert!(st.dataframe(DataframeOptions::new(&batch).height(-1)).is_err());
    assert!(st.bar_chart(BarChartOptions::new(&batch, "missing", "total_amount")).is_err());
    assert!(st.bar_chart(BarChartOptions::new(&batch, "row_count", "group_key")).is_err());
    assert!(st.bar_chart(BarChartOptions::new(&batch, "group_key", "total_amount").tooltip("missing", "bad")).is_err());
    assert!(receiver.try_recv().is_err());
    assert_eq!(st.app.lock().render_context_mut().context("data test must retain its render context")?.delta_path, vec![0, 0]);

    Ok(())
}

#[test]
fn all_four_browser_update_stages_preserve_rows_metadata_and_change_ipc_and_datasets() -> anyhow::Result<()> {
    let root = std::path::Path::new(env!("CARGO_MANIFEST_DIR")).join("../tests/reference/reference-browser/data-loop/updates");
    let reference: Value = serde_json::from_slice(&std::fs::read(root.join("trace-data-loop.json"))?)?;
    let stages = reference["stages"].as_array().context("data reference requires reference[\"stages\"].as_array()")?;
    assert_eq!(stages.len(), 4);
    let mut payloads = std::collections::HashSet::new();
    let mut dataset_names = std::collections::HashSet::new();
    for stage in stages {
        let file = stage["table"]["arrow"]["file"].as_str().context("data reference requires stage[\"table\"][\"arrow\"][\"file\"].as_str()")?;
        assert_eq!(stage["chart"]["datasets"][0]["arrow"]["file"], file);
        let captured = from_ipc_stream(&std::fs::read(root.join(file))?)?.remove(0);
        let rows = stage["table"]["rows"].as_array().context("data reference requires stage[\"table\"][\"rows\"].as_array()")?;
        let groups: Vec<_> = rows.iter().map(|r| r["group_key"].as_str().context("reference update row must contain its group_key")).collect::<anyhow::Result<Vec<_>>>()?;
        let batch = RecordBatch::try_new(
            captured.schema(),
            vec![
                Arc::new(LargeStringArray::from(groups.clone())),
                Arc::new(Int64Array::from(
                    rows.iter().map(|r| r["row_count"].as_i64().context("reference update row must contain numeric row_count")).collect::<anyhow::Result<Vec<_>>>()?,
                )),
                Arc::new(Float64Array::from(
                    rows.iter().map(|r| r["total_amount"].as_f64().context("reference update row must contain numeric total_amount")).collect::<anyhow::Result<Vec<_>>>()?,
                )),
                Arc::new(Float64Array::from(
                    rows.iter().map(|r| r["avg_amount"].as_f64().context("reference update row must contain numeric avg_amount")).collect::<anyhow::Result<Vec<_>>>()?,
                )),
            ],
        )?;
        assert_eq!(batch, captured);
        let (table_message, _) = render(|st| st.dataframe(DataframeOptions::new(&batch).hide_index(true).column_order(["group_key", "row_count", "total_amount", "avg_amount"])))?;
        let Some(element::Type::Dataframe(table)) = new_element(table_message).r#type else { panic!("missing dataframe") };
        let payload = table.arrow_data.context("rendered table must contain its Arrow data")?.data;
        assert_eq!(from_ipc_stream(&payload)?, vec![captured]);
        assert_eq!(
            serde_json::from_str::<Value>(&table.columns)?,
            serde_json::from_str::<Value>(stage["table"]["arrow_fields"]["columns"].as_str().context("data reference requires stage[\"table\"][\"arrow_fields\"][\"columns\"].as_str()")?)?
        );
        let (chart_message, _) = render(|st| {
            st.bar_chart(
                BarChartOptions::new(&batch, "group_key", "total_amount")
                    .x_order(groups)
                    .tooltip("group_key", "group")
                    .tooltip("row_count", "rows")
                    .tooltip("total_amount", "total")
                    .tooltip("avg_amount", "avg")
                    .plot_height(260),
            )
        })?;
        let Some(element::Type::VegaLiteChart(chart)) = new_element(chart_message).r#type else { panic!("missing chart") };
        assert_eq!(chart.datasets[0].data.as_ref().context("chart dataset must contain its Arrow data")?.data, payload);
        let actual_spec: Value = serde_json::from_str(&chart.spec)?;
        let mut expected_spec = stage["chart"]["spec"].clone();
        expected_spec["data"]["name"] = json!(chart.datasets[0].name);
        // The stage capture is a real altair spec; st.bar_chart encodes its
        // string x axis as ordinal (measured on the 2026-10-25 elements chain).
        expected_spec["encoding"]["x"]["type"] = json!("ordinal");
        assert_eq!(actual_spec, expected_spec);
        assert!(payloads.insert(payload), "every reference action must change serialized data");
        assert!(dataset_names.insert(chart.datasets[0].name.clone()));
    }

    Ok(())
}

#[test]
fn csv_workbench_frozen_editor_inputs_match_independent_python_downloads() -> anyhow::Result<()> {
    let base = std::path::Path::new(env!("CARGO_MANIFEST_DIR")).join("../tests/reference/reference-browser/csv-workbench");
    let reference: Value = serde_json::from_slice(&std::fs::read(base.join("csv-input-output.json"))?)?;
    assert_eq!(reference["reference_version"], "1.66.1");
    let stages = reference["stages"].as_array().context("frozen workbench stages are missing")?;
    let stage = |name: &str| -> anyhow::Result<&Value> { stages.iter().find(|stage| stage["capture"] == "main-complete" && stage["name"] == name).context("frozen main stage is missing") };
    let input = |name: &str, marker: &str| -> anyhow::Result<String> {
        stage(name)?["widget_inputs"]
            .as_array()
            .context("widget input is missing")?
            .iter()
            .find(|input| input["id"].as_str().is_some_and(|id| id.contains(marker)))
            .and_then(|input| input["value"].as_str())
            .map(str::to_owned)
            .context("recorded string_value is missing")
    };
    let rows = |batch: &RecordBatch| -> anyhow::Result<Vec<Vec<String>>> {
        let columns = batch.columns().iter().map(|column| column.as_any().downcast_ref::<StringArray>().context("text column expected")).collect::<anyhow::Result<Vec<_>>>()?;
        Ok((0..batch.num_rows())
            .map(|row| columns.iter().map(|column| if column.is_null(row) { String::new() } else { column.value(row).to_owned() }).collect())
            .collect())
    };

    // 1. 原始 BOM CSV 和真实排序选择作为输入，下载数据只提供独立输出预期。
    let source = std::fs::read(base.join(stage("upload-bom")?["input"]["file"].as_str().context("upload fixture is missing")?))?;
    let text = std::str::from_utf8(&source)?;
    let mut reader = csv::Reader::from_reader(text.strip_prefix('\u{feff}').unwrap_or(text).as_bytes());
    let headers = reader.headers()?.clone();
    let original = reader.records().collect::<Result<Vec<_>, _>>()?;
    let batch = RecordBatch::try_from_iter(
        headers
            .iter()
            .enumerate()
            .map(|(column, name)| (name, Arc::new(StringArray::from(original.iter().map(|row| &row[column]).collect::<Vec<_>>())) as ArrayRef)),
    )?;
    let selection: DataframeState = serde_json::from_str(&input("select-sorted-first", "-wb-rows-")?)?;
    let selected = *selection.selection.rows.first().context("recorded selection must contain a row")?;
    assert!(selected < batch.num_rows());
    let st = Streamlit::new();
    st.session_state().set("frozen-detail", input("edit-detail-unapplied", "-wb-detail-")?)?;
    let detail_source = batch.slice(selected, 1);
    let detail = st.data_editor(DataEditorOptions::new(&detail_source).key("frozen-detail"))?;
    let applied: Vec<Vec<String>> = serde_json::from_value(stage("download-applied")?["download"]["rows"].clone())?;
    assert_eq!(rows(&detail)?, vec![applied[selected].clone()]);
    let unchanged: Vec<Vec<String>> = serde_json::from_value(stage("download-unapplied")?["download"]["rows"].clone())?;
    assert_eq!(rows(&batch)?, unchanged, "the editor must not mutate the uploaded input");

    // 2. 实际新增 StringValue 经同一生产编辑入口，空单元格按 CSV 约定比较。
    st.session_state().set("frozen-new", input("edit-new-row", "-wb-add-")?)?;
    let empty = batch.slice(0, 0);
    let added = st.data_editor(DataEditorOptions::new(&empty).key("frozen-new").num_rows(EditorRows::Dynamic))?;
    let appended: Vec<Vec<String>> = serde_json::from_value(stage("download-appended")?["download"]["rows"].clone())?;
    assert_eq!(rows(&added)?, appended[applied.len()..]);
    assert_eq!(detail.schema().fields().iter().map(|field| field.name()).collect::<Vec<_>>(), headers.iter().collect::<Vec<_>>());
    Ok(())
}

mod native;
