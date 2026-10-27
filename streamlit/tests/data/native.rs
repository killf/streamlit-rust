//! Full public Python 1.66.1 browser specs; only the dataset hash is normalized.
use super::*;

const BAR_DEFAULT: &str = r##"{"data": {"name": "DATASET"}, "mark": {"type": "bar"}, "encoding": {"color": {"field": "color -- streamlit-generated", "legend": {"titlePadding": 5, "offset": 5, "orient": "bottom"}, "title": " ", "type": "nominal"}, "tooltip": [{"field": "index -- streamlit-generated", "title": "index", "type": "quantitative"}, {"field": "value -- streamlit-generated", "title": "value", "type": "quantitative"}, {"field": "color -- streamlit-generated", "title": "color", "type": "nominal"}], "x": {"axis": {"grid": false, "tickMinStep": 1}, "field": "index -- streamlit-generated", "scale": {}, "title": "", "type": "ordinal"}, "y": {"axis": {"grid": true}, "field": "value -- streamlit-generated", "scale": {}, "title": "", "type": "quantitative"}}, "height": 0, "params": [{"name": "param_1", "select": {"type": "interval", "encodings": ["x", "y"]}, "bind": "scales"}], "width": 0, "$schema": "https://vega.github.io/schema/vega-lite/v5.20.1.json", "autosize": {"type": "fit", "contains": "padding"}}"##;

const BAR_XY: &str = r##"{"data": {"name": "DATASET"}, "mark": {"type": "bar"}, "encoding": {"tooltip": [{"field": "col -- streamlit-generated-0", "title": "group.name", "type": "nominal"}, {"field": "col -- streamlit-generated-1", "title": "amount[0]", "type": "quantitative"}], "x": {"axis": {"grid": false}, "field": "col -- streamlit-generated-0", "scale": {}, "title": "group.name", "type": "ordinal"}, "y": {"axis": {"grid": true}, "field": "col -- streamlit-generated-1", "scale": {}, "title": "amount[0]", "type": "quantitative"}}, "height": 260, "params": [{"name": "param_1", "select": {"type": "interval", "encodings": ["x", "y"]}, "bind": "scales"}], "width": 480, "$schema": "https://vega.github.io/schema/vega-lite/v5.20.1.json", "autosize": {"type": "fit", "contains": "padding"}}"##;

const BAR_HORIZONTAL: &str = r##"{"data": {"name": "DATASET"}, "mark": {"type": "bar"}, "encoding": {"tooltip": [{"field": "col -- streamlit-generated-0", "title": "group.name", "type": "nominal"}, {"field": "col -- streamlit-generated-1", "title": "amount[0]", "type": "quantitative"}], "x": {"axis": {"grid": true}, "field": "col -- streamlit-generated-1", "scale": {}, "title": "amount[0]", "type": "quantitative"}, "y": {"axis": {"grid": false}, "field": "col -- streamlit-generated-0", "scale": {}, "sort": null, "title": "group.name", "type": "ordinal"}}, "height": 260, "params": [{"name": "param_1", "select": {"type": "interval", "encodings": ["x", "y"]}, "bind": "scales"}], "width": 0, "$schema": "https://vega.github.io/schema/vega-lite/v5.20.1.json", "autosize": {"type": "fit", "contains": "padding"}}"##;

const BAR_MULTIPLE: &str = r##"{"data": {"name": "DATASET"}, "mark": {"type": "bar"}, "encoding": {"color": {"field": "color -- streamlit-generated", "legend": {"titlePadding": 5, "offset": 5, "orient": "bottom"}, "title": " ", "type": "nominal"}, "tooltip": [{"field": "col -- streamlit-generated-0", "title": "group.name", "type": "nominal"}, {"field": "value -- streamlit-generated", "title": "value", "type": "quantitative"}, {"field": "color -- streamlit-generated", "title": "color", "type": "nominal"}], "x": {"axis": {"grid": false}, "field": "col -- streamlit-generated-0", "scale": {}, "title": "group.name", "type": "ordinal"}, "xOffset": {"field": "color -- streamlit-generated"}, "y": {"axis": {"grid": true}, "field": "value -- streamlit-generated", "scale": {}, "stack": false, "title": "", "type": "quantitative"}, "yOffset": {}}, "height": 260, "params": [{"name": "param_1", "select": {"type": "interval", "encodings": ["x", "y"]}, "bind": "scales"}], "width": 0, "$schema": "https://vega.github.io/schema/vega-lite/v5.20.1.json", "autosize": {"type": "fit", "contains": "padding"}}"##;

fn table_batch(revision: i64) -> anyhow::Result<RecordBatch> {
    RecordBatch::try_from_iter(vec![
        ("group.name", Arc::new(LargeStringArray::from(vec![Some("图书"), Some("Café"), Some("**Music**"), None])) as ArrayRef),
        ("amount[0]", Arc::new(Int64Array::from(vec![Some(12 + revision), None, Some(-3), Some(0)])) as ArrayRef),
        ("path\\label", Arc::new(LargeStringArray::from(vec![Some("普通"), Some("naïve"), None, Some("fin")])) as ArrayRef),
    ])
    .map_err(Into::into)
}

fn named_batch(revision: i64) -> anyhow::Result<RecordBatch> {
    RecordBatch::try_from_iter(vec![
        ("group.name", Arc::new(LargeStringArray::from(vec!["图书", "Café", "Music", "Toys"])) as ArrayRef),
        ("amount[0]", Arc::new(Float64Array::from(vec![Some(12.0 + revision as f64), Some(24.0), Some(-3.0), None])) as ArrayRef),
        ("other", Arc::new(Int64Array::from(vec![4, 8 + revision, 1, 2])) as ArrayRef),
    ])
    .map_err(Into::into)
}

fn default_batch(revision: i64) -> anyhow::Result<RecordBatch> {
    RecordBatch::try_from_iter(vec![
        ("sales", Arc::new(Int64Array::from(vec![12 + revision, 24, -3, 0])) as ArrayRef),
        ("cost", Arc::new(Float64Array::from(vec![Some(4.0), Some(8.0 + revision as f64), None, Some(2.0)])) as ArrayRef),
    ])
    .map_err(Into::into)
}

#[test]
fn native_table_defaults_and_explicit_fields_match_the_public_browser() -> anyhow::Result<()> {
    let data = table_batch(0)?;
    let default = new_element(render(|st| st.table(&data))?.0);
    let Some(element::Type::Table(table)) = default.r#type else { panic!("table") };
    assert_eq!(table.border_mode, 0);
    assert!(table.hide_index);
    assert!(!table.hide_header);
    assert_eq!(table.alt, None);
    assert_eq!(from_ipc_stream(&table.arrow_data.context("rendered table must contain its Arrow data")?.data)?.as_slice(), std::slice::from_ref(&data));
    assert_eq!(
        default.width_config.context("rendered data element must contain width_config")?.width_spec,
        Some(proto::streamlit::width_config::WidthSpec::UseStretch(true))
    );
    assert_eq!(
        default.height_config.context("rendered data element must contain height_config")?.height_spec,
        Some(proto::streamlit::height_config::HeightSpec::UseContent(true))
    );
    let explicit = new_element(render(|st| st.table(TableOptions::new(&data).border(TableBorder::Horizontal).hide_index(false).hide_header(false).width(480).height(220).alt("UTF8 table")))?.0);
    let Some(element::Type::Table(table)) = explicit.r#type else { panic!("table") };
    assert_eq!(table.border_mode, 2);
    assert!(!table.hide_index);
    assert!(!table.hide_header);
    assert_eq!(table.alt.as_deref(), Some("UTF8 table"));
    assert_eq!(
        explicit.width_config.context("rendered data element must contain width_config")?.width_spec,
        Some(proto::streamlit::width_config::WidthSpec::PixelWidth(480))
    );
    assert_eq!(
        explicit.height_config.context("rendered data element must contain height_config")?.height_spec,
        Some(proto::streamlit::height_config::HeightSpec::PixelHeight(220))
    );
    let hidden = new_element(render(|st| st.table(TableOptions::new(&data).border(false).hide_header(true).width(DataSize::Content)))?.0);
    let Some(element::Type::Table(table)) = hidden.r#type else { panic!("table") };
    assert_eq!(table.border_mode, 1);
    assert!(table.hide_header && table.hide_index);
    assert_eq!(
        hidden.width_config.context("rendered data element must contain width_config")?.width_spec,
        Some(proto::streamlit::width_config::WidthSpec::UseContent(true))
    );

    Ok(())
}

#[test]
fn table_preserves_custom_arrow_index_without_creating_pandas_metadata() -> anyhow::Result<()> {
    let data = table_batch(0)?;
    let mut fields = data.schema_ref().fields().to_vec();
    fields.push(Arc::new(Field::new("__index_level_0__", DataType::LargeUtf8, false)));
    let mut columns = data.columns().to_vec();
    columns.push(Arc::new(LargeStringArray::from(vec!["甲", "乙", "丙", "丁"])));
    // The public Arrow pandas index descriptor, as observed in the custom-index capture.
    let schema = Schema::new(fields).with_metadata(std::collections::BTreeMap::from([("pandas".into(), r#"{"index_columns":["__index_level_0__"]}"#.into())]));
    let indexed = RecordBatch::try_new(Arc::new(schema), columns)?;
    let element = new_element(render(|st| st.table(&indexed))?.0);
    let Some(element::Type::Table(table)) = element.r#type else { panic!("table") };
    assert!(!table.hide_index);
    assert_eq!(from_ipc_stream(&table.arrow_data.context("rendered table must contain its Arrow data")?.data)?, [indexed]);
    assert!(data.schema_ref().metadata().is_empty());

    Ok(())
}

fn chart(options: impl FnOnce(&Streamlit) -> Result<(), DataError>) -> anyhow::Result<(Value, RecordBatch)> {
    let element = new_element(render(options)?.0);
    let Some(element::Type::VegaLiteChart(chart)) = element.r#type else { panic!("chart") };
    assert!(!chart.use_container_width);
    assert_eq!(chart.theme, "streamlit");
    assert!(chart.id.is_empty() && chart.form_id.is_empty());
    let mut spec: Value = serde_json::from_str(&chart.spec)?;
    assert_eq!(spec["data"]["name"], chart.datasets[0].name);
    assert!(chart.datasets[0].has_name);
    let batch = from_ipc_stream(&chart.datasets[0].data.as_ref().context("chart dataset must contain its Arrow data")?.data)?.remove(0);
    // The reference serializes chart data through pandas, so the batch
    // carries the measured pandas schema metadata.
    let pandas: Value = serde_json::from_str(batch.schema_ref().metadata().get("pandas").context("Arrow batch must retain its pandas metadata")?)?;
    assert_eq!(pandas["creator"], json!({"library": "pyarrow", "version": "26.0.0"}));
    assert_eq!(pandas["pandas_version"], "3.1.0");
    spec["data"]["name"] = json!("DATASET");
    Ok((spec, batch))
}

#[test]
fn default_bar_matches_complete_browser_spec_and_all_eight_melted_values() -> anyhow::Result<()> {
    let mut previous = None;
    for revision in [0, 1] {
        let data = default_batch(revision)?;
        let (spec, batch) = chart(|st| st.bar_chart(&data))?;
        assert_eq!(spec, serde_json::from_str::<Value>(BAR_DEFAULT)?);
        assert_eq!(
            batch.schema_ref().fields().iter().map(|f| f.name().as_str()).collect::<Vec<_>>(),
            ["index -- streamlit-generated", "color -- streamlit-generated", "value -- streamlit-generated"]
        );
        assert_eq!(batch.column(0).as_any().downcast_ref::<Int64Array>().context("Arrow column must be Int64Array")?, &Int64Array::from(vec![0, 1, 2, 3, 0, 1, 2, 3]));
        assert_eq!(
            batch.column(1).as_any().downcast_ref::<LargeStringArray>().context("Arrow column must be LargeStringArray")?,
            &LargeStringArray::from(vec!["sales", "sales", "sales", "sales", "cost", "cost", "cost", "cost"])
        );
        assert_eq!(
            batch.column(2).as_any().downcast_ref::<Float64Array>().context("Arrow column must be Float64Array")?,
            &Float64Array::from(vec![Some(12.0 + revision as f64), Some(24.0), Some(-3.0), Some(0.0), Some(4.0), Some(8.0 + revision as f64), None, Some(2.0)])
        );
        let bytes = to_ipc_stream(&batch)?;
        if let Some(previous) = previous {
            assert_ne!(bytes, previous);
        }
        previous = Some(bytes);
    }

    Ok(())
}

#[test]
fn native_xy_horizontal_and_grouped_series_match_full_measured_specs() -> anyhow::Result<()> {
    let data = named_batch(0)?;
    let (spec, batch) = chart(|st| st.bar_chart(BarChartOptions::native(&data).x("group.name").y("amount[0]").width(480).height(260)))?;
    assert_eq!(spec, serde_json::from_str::<Value>(BAR_XY)?);
    assert_eq!(batch.num_columns(), 2);
    assert_eq!(batch.num_rows(), 4);
    assert_eq!(batch.column(0), data.column(0));
    assert_eq!(batch.column(1), data.column(1));
    let (spec, _) = chart(|st| st.bar_chart(BarChartOptions::native(&data).x("group.name").y("amount[0]").horizontal(true).sort(false).height(260)))?;
    assert_eq!(spec, serde_json::from_str::<Value>(BAR_HORIZONTAL)?);
    let (spec, batch) = chart(|st| st.bar_chart(BarChartOptions::native(&data).x("group.name").series(["amount[0]", "other"]).side_by_side().height(260)))?;
    assert_eq!(spec, serde_json::from_str::<Value>(BAR_MULTIPLE)?);
    assert_eq!(batch.num_rows(), 8);
    assert_eq!(batch.column(2).null_count(), 1);
    assert_eq!(
        batch.column(2).as_any().downcast_ref::<Float64Array>().context("Arrow column must be Float64Array")?,
        &Float64Array::from(vec![Some(12.0), Some(24.0), Some(-3.0), None, Some(4.0), Some(8.0), Some(1.0), Some(2.0)])
    );

    Ok(())
}

#[test]
fn native_errors_append_nothing_and_do_not_silently_drop_or_round_data() -> anyhow::Result<()> {
    let data = default_batch(0)?;
    let st = Streamlit::new();
    let (sender, mut receiver) = tokio::sync::mpsc::unbounded_channel();
    let mut context = RenderContext::with_sender("invalid-native".into(), sender);
    context.delta_path = vec![0, 0];
    st.app.lock().set_render_context(context);
    assert!(TableBorder::try_from("vertical").is_err());
    assert!(st.table(TableOptions::new(&data).width(0)).is_err());
    assert!(st.table(TableOptions::new(&data).height(0)).is_err());
    assert!(st.bar_chart(BarChartOptions::native(&data).width(0)).is_err());
    assert!(st.bar_chart(BarChartOptions::native(&data).x("missing")).is_err());
    assert!(st.bar_chart(BarChartOptions::native(&data).series(["sales", "sales"])).is_err());
    let data = RecordBatch::try_from_iter(vec![("large", Arc::new(Int64Array::from(vec![i64::MAX])) as ArrayRef), ("float", Arc::new(Float64Array::from(vec![1.0])) as ArrayRef)])?;
    assert!(st.bar_chart(&data).is_err());
    assert!(receiver.try_recv().is_err());
    assert_eq!(st.app.lock().render_context_mut().context("data test must retain its render context")?.delta_path, vec![0, 0]);

    Ok(())
}

const BAR_SINGLE: &str = r##"{"data": {"name": "DATASET"}, "mark": {"type": "bar"}, "encoding": {"tooltip": [{"field": "index -- streamlit-generated", "title": "index", "type": "quantitative"}, {"field": "sales", "type": "quantitative"}], "x": {"axis": {"grid": false, "tickMinStep": 1}, "field": "index -- streamlit-generated", "scale": {}, "title": "", "type": "ordinal"}, "y": {"axis": {"grid": true, "tickMinStep": 1}, "field": "sales", "scale": {}, "title": "", "type": "quantitative"}}, "height": 0, "params": [{"name": "param_1", "select": {"type": "interval", "encodings": ["x", "y"]}, "bind": "scales"}], "width": 0, "$schema": "https://vega.github.io/schema/vega-lite/v5.20.1.json", "autosize": {"type": "fit", "contains": "padding"}}"##;

#[test]
fn explicit_table_row_numbers_have_real_interoperable_range_index_metadata() -> anyhow::Result<()> {
    let data = table_batch(0)?;
    let element = new_element(render(|st| st.table(TableOptions::new(&data).hide_index(false)))?.0);
    let Some(element::Type::Table(table)) = element.r#type else { panic!("table") };
    let output = from_ipc_stream(&table.arrow_data.context("rendered table must contain its Arrow data")?.data)?.remove(0);
    assert_eq!(output.columns(), data.columns());
    let metadata: Value = serde_json::from_str(output.schema_ref().metadata().get("pandas").context("Arrow batch must retain its pandas metadata")?)?;
    assert_eq!(metadata["index_columns"], json!([{"kind":"range","name":null,"start":0,"stop":4,"step":1}]));
    assert_eq!(metadata["columns"][1]["field_name"], "amount[0]");
    assert_eq!(metadata["columns"][1]["numpy_type"], "Int64");
    assert!(metadata.get("pandas_version").is_none());
    assert!(data.schema_ref().metadata().is_empty());

    Ok(())
}

#[test]
fn inferred_single_int64_bar_matches_its_measured_tooltips_axis_ticks_and_title() -> anyhow::Result<()> {
    let data = RecordBatch::try_from_iter(vec![("sales", Arc::new(Int64Array::from(vec![12, 24, -3, 0])) as ArrayRef)])?;
    let (spec, batch) = chart(|st| st.bar_chart(&data))?;
    assert_eq!(spec, serde_json::from_str::<Value>(BAR_SINGLE)?);
    assert_eq!(batch.column(1), data.column(0));

    Ok(())
}
