//! The measured built-in chart wire of 1.66.1: line, area and scatter ride
//! Vega-Lite specs with named Arrow datasets; the map rides one deck.gl JSON
//! string. Every byte is reproduced, not approximated: the dataset name is
//! the reference's `calc_hash(str(arrow_bytes))`, the Arrow IPC bytes carry
//! the same pandas schema metadata, and the spec strings use the reference's
//! `json.dumps` separators and construction order (see .codex/compatibility,
//! Charts).

use crate::api::AppendChild;
use crate::data::{Array, ArrayRef, DataError, DataType, Field, Float64Array, Int64Array, LargeStringArray, RecordBatch, Schema, to_ipc_stream};
use crate::data_api::DataSize;
use crate::elements::data::DataElement;
use crate::proto::{self, element};
use crate::pywire::{dataset_name, py_dumps};
use serde_json::{Value, json};
use std::{cell::RefCell, collections::HashMap, rc::Rc, sync::Arc};

const VEGA_SCHEMA: &str = "https://vega.github.io/schema/vega-lite/v5.20.1.json";
const GENERATED_INDEX: &str = "index -- streamlit-generated";
const GENERATED_COLOR: &str = "color -- streamlit-generated";
const GENERATED_VALUE: &str = "value -- streamlit-generated";

// The pinned reference environment's pandas metadata creator fields; the
// dataset bytes and names are only stable against this exact pair.
const CREATOR_VERSION: &str = "26.0.0";
const PANDAS_VERSION: &str = "3.1.0";

/// The st.map zoom ladder the reference bisects a degree distance over
/// (streamlit/elements/map.py _ZOOM_LEVELS, pinned 1.66.1: 21 entries).
const ZOOM_LEVELS: [f64; 21] = [360.0, 180.0, 90.0, 45.0, 22.5, 11.25, 5.625, 2.813, 1.406, 0.703, 0.352, 0.176, 0.088, 0.044, 0.022, 0.011, 0.005, 0.003, 0.001, 0.0005, 0.00025];
const DEFAULT_ZOOM_LEVEL: i32 = 12;

/// The empty map the reference serializes verbatim for empty data.
const EMPTY_MAP_JSON: &str = "{\"initialViewState\": {\"latitude\": 0, \"longitude\": 0, \"pitch\": 0, \"zoom\": 1}}";

/// One encoded channel in the measured key order: axis, field, scale,
/// extra..., title, type.
fn channel(grid: bool, integer_column: bool, field: &str, extra: &[(&str, Value)], title: &str, kind: &str) -> Value {
    let mut axis = json!({"grid": grid});
    if integer_column {
        axis["tickMinStep"] = json!(1);
    }
    let mut channel = json!({"axis": axis, "field": field, "scale": {}});
    for (key, value) in extra {
        channel[*key] = value.clone();
    }
    channel["title"] = json!(title);
    channel["type"] = json!(kind);
    channel
}

fn tooltip_field(field: &str, title: Option<&str>, kind: &str) -> Value {
    match title {
        Some(title) => json!({"field": field, "title": title, "type": kind}),
        None => json!({"field": field, "type": kind}),
    }
}

fn interval_param(name: &str) -> Value {
    json!({"name": name, "select": {"type": "interval", "encodings": ["x", "y"]}, "bind": "scales"})
}

pub(crate) const VEGA_SCHEMA_URL: &str = VEGA_SCHEMA;

/// The pandas schema metadata the reference's Arrow bytes carry: a generated
/// range index plus one entry per column, in frame order.
fn pandas_metadata(rows: i64, columns: &[(String, &str, &str)]) -> Value {
    json!({
        "index_columns": [{"kind": "range", "name": null, "start": 0, "stop": rows, "step": 1}],
        "column_indexes": [{"name": null, "field_name": null, "pandas_type": "unicode", "numpy_type": "str", "metadata": {"encoding": "UTF-8"}}],
        "columns": columns
            .iter()
            .map(|(name, pandas_type, numpy_type)| {
                json!({"name": name, "field_name": name, "pandas_type": pandas_type, "numpy_type": numpy_type, "metadata": null})
            })
            .collect::<Vec<_>>(),
        "attributes": {},
        "creator": {"library": "pyarrow", "version": CREATOR_VERSION},
        "pandas_version": PANDAS_VERSION,
    })
}

/// The pandas type pair a column reports, for the bounded column set.
fn pandas_kind(data_type: &DataType) -> Result<(&'static str, &'static str), DataError> {
    match data_type {
        DataType::Int8 | DataType::Int16 | DataType::Int32 | DataType::Int64 | DataType::UInt8 | DataType::UInt16 | DataType::UInt32 | DataType::UInt64 => Ok(("int64", "int64")),
        DataType::Float32 | DataType::Float64 => Ok(("float64", "float64")),
        DataType::Utf8 | DataType::LargeUtf8 => Ok(("object", "str")),
        other => Err(DataError::InvalidOption(format!("chart column type is not supported yet: {other}"))),
    }
}

fn is_integer(data_type: &DataType) -> bool {
    matches!(data_type, DataType::Int8 | DataType::Int16 | DataType::Int32 | DataType::Int64 | DataType::UInt8 | DataType::UInt16 | DataType::UInt32 | DataType::UInt64)
}

fn is_numeric(data_type: &DataType) -> bool {
    is_integer(data_type) || matches!(data_type, DataType::Float32 | DataType::Float64)
}

/// Assemble the batch the reference serializes: the columns plus the pandas
/// metadata its IPC bytes carry on the schema. String columns widen to
/// large_string, the arrow type a pandas str column takes.
pub(crate) fn chart_batch(columns: Vec<(Field, ArrayRef)>) -> Result<RecordBatch, DataError> {
    let rows = columns.first().map(|(_, values)| values.len()).unwrap_or(0) as i64;
    let described: Vec<(String, &str, &str)> = columns
        .iter()
        .map(|(field, _)| {
            let (pandas_type, numpy_type) = pandas_kind(field.data_type())?;
            Ok::<_, DataError>((field.name().to_string(), pandas_type, numpy_type))
        })
        .collect::<Result<_, _>>()?;
    let mut metadata = HashMap::with_capacity(1);
    metadata.insert("pandas".to_string(), py_dumps(&pandas_metadata(rows, &described)));
    let columns: Vec<(Field, ArrayRef)> = columns
        .into_iter()
        .map(|(mut field, values)| {
            if matches!(field.data_type(), DataType::Utf8) {
                let widened = values
                    .as_any()
                    .downcast_ref::<crate::data::StringArray>()
                    .expect("utf8 column")
                    .iter()
                    .map(|value| value.map(|value| value.to_string()))
                    .collect::<LargeStringArray>();
                field = Field::new(field.name(), DataType::LargeUtf8, field.is_nullable());
                return (field, Arc::new(widened) as ArrayRef);
            }
            (field, values)
        })
        .collect();
    let fields: Vec<Field> = columns.iter().map(|(field, _)| field.clone()).collect();
    let arrays: Vec<ArrayRef> = columns.into_iter().map(|(_, values)| values).collect();
    Ok(RecordBatch::try_new(Arc::new(Schema::new_with_metadata(fields, metadata)), arrays)?)
}

/// Serialize one batch and name it the way the reference does.
pub(crate) fn chart_dataset(batch: &RecordBatch) -> Result<(String, Vec<u8>), DataError> {
    let ipc = to_ipc_stream(batch)?;
    Ok((dataset_name(&ipc), ipc))
}

fn vega_element(this: &impl AppendChild, spec: String, name: &str, ipc: Vec<u8>) -> Result<(), DataError> {
    this.push(Rc::new(RefCell::new(DataElement(proto::Element {
        width_config: DataSize::Stretch.width()?,
        height_config: DataSize::Content.height()?,
        r#type: Some(element::Type::VegaLiteChart(proto::VegaLiteChart {
            spec,
            datasets: vec![proto::ArrowNamedDataSet {
                name: name.to_string(),
                has_name: true,
                data: Some(proto::ArrowData { data: ipc, styler: None }),
            }],
            theme: "streamlit".into(),
            ..Default::default()
        })),
        ..Default::default()
    }))));
    Ok(())
}

fn numeric_columns(data: &RecordBatch) -> Vec<String> {
    data.schema_ref().fields().iter().filter(|field| is_numeric(field.data_type())).map(|field| field.name().clone()).collect()
}

fn column(data: &RecordBatch, name: &str) -> Result<ArrayRef, DataError> {
    data.column_by_name(name).cloned().ok_or_else(|| DataError::InvalidOption(format!("column does not exist: {name}")))
}

/// Line chart options: the measured native subset (one int64 series over a
/// generated index).
pub struct LineChartOptions<'a> {
    data: &'a RecordBatch,
    y: Option<String>,
}

impl<'a> LineChartOptions<'a> {
    pub fn native(data: &'a RecordBatch) -> Self {
        Self { data, y: None }
    }
    /// Select the single numeric series; default is the only numeric column.
    pub fn y(mut self, column: impl Into<String>) -> Self {
        self.y = Some(column.into());
        self
    }
}

impl<'a> From<&'a RecordBatch> for LineChartOptions<'a> {
    fn from(data: &'a RecordBatch) -> Self {
        Self::native(data)
    }
}

/// Area chart options: the measured native subset (every numeric series
/// melted into one long-form color/value frame).
pub struct AreaChartOptions<'a> {
    data: &'a RecordBatch,
}

impl<'a> AreaChartOptions<'a> {
    pub fn native(data: &'a RecordBatch) -> Self {
        Self { data }
    }
}

impl<'a> From<&'a RecordBatch> for AreaChartOptions<'a> {
    fn from(data: &'a RecordBatch) -> Self {
        Self::native(data)
    }
}

/// Scatter chart options: the measured native subset (explicit numeric x and
/// y columns, no generated index).
pub struct ScatterChartOptions<'a> {
    data: &'a RecordBatch,
    x: String,
    y: String,
}

impl<'a> ScatterChartOptions<'a> {
    pub fn new(data: &'a RecordBatch, x: impl Into<String>, y: impl Into<String>) -> Self {
        Self { data, x: x.into(), y: y.into() }
    }
}

/// Map options: the measured native subset (default or named latitude and
/// longitude columns, auto viewport).
pub struct MapOptions<'a> {
    data: &'a RecordBatch,
    latitude: Option<String>,
    longitude: Option<String>,
    zoom: Option<i32>,
}

impl<'a> MapOptions<'a> {
    pub fn new(data: &'a RecordBatch) -> Self {
        Self {
            data,
            latitude: None,
            longitude: None,
            zoom: None,
        }
    }
    pub fn latitude(mut self, column: impl Into<String>) -> Self {
        self.latitude = Some(column.into());
        self
    }
    pub fn longitude(mut self, column: impl Into<String>) -> Self {
        self.longitude = Some(column.into());
        self
    }
    /// The deck.gl zoom level; None bisects the data's extent over the
    /// reference's ladder.
    pub fn zoom(mut self, zoom: i32) -> Self {
        self.zoom = Some(zoom);
        self
    }
}

impl<'a> From<&'a RecordBatch> for MapOptions<'a> {
    fn from(data: &'a RecordBatch) -> Self {
        Self::new(data)
    }
}

pub(crate) fn render_line_chart(this: &impl AppendChild, options: &LineChartOptions<'_>) -> Result<(), DataError> {
    let numeric = numeric_columns(options.data);
    if numeric.len() != 1 {
        return Err(DataError::InvalidOption(format!("line chart expects exactly one numeric series, found {}", numeric.len())));
    }
    let y_name = options.y.clone().unwrap_or_else(|| numeric[0].clone());
    if !numeric.contains(&y_name) {
        return Err(DataError::InvalidOption(format!("line chart series is not a numeric column: {y_name}")));
    }
    let rows = options.data.num_rows() as i64;
    let index = Int64Array::from((0..rows).collect::<Vec<_>>());
    let values = column(options.data, &y_name)?;
    let integer_values = is_integer(values.data_type());
    let batch = chart_batch(vec![(Field::new(GENERATED_INDEX, DataType::Int64, true), Arc::new(index) as ArrayRef), (Field::new(&y_name, values.data_type().clone(), true), values)])?;
    let (name, ipc) = chart_dataset(&batch)?;
    let encoding = json!({
        "tooltip": [
            tooltip_field(GENERATED_INDEX, Some("index"), "quantitative"),
            tooltip_field(&y_name, None, "quantitative"),
        ],
        "x": channel(false, true, GENERATED_INDEX, &[], "", "quantitative"),
        "y": channel(true, integer_values, &y_name, &[], "", "quantitative"),
    });
    let layers = json!([
        {"mark": {"type": "line"}, "encoding": encoding, "name": "view_1"},
        {"mark": {"type": "point", "opacity": 0}, "encoding": encoding, "name": "view_2"},
        {
            "mark": {"type": "point", "filled": true, "size": 65},
            "encoding": encoding,
            "transform": [{"filter": {"param": "param_1", "empty": false}}],
        },
    ]);
    let spec = json!({
        "layer": layers,
        "config": {"legend": {"symbolType": "stroke"}},
        "data": {"name": name},
        "height": 0,
        "params": [
            {
                "name": "param_1",
                "select": {
                    "type": "point",
                    "clear": "mouseleave",
                    "fields": [GENERATED_INDEX],
                    "nearest": true,
                    "on": "mousemove",
                },
                "views": ["view_2"],
            },
            {
                "name": "param_2",
                "select": {"type": "interval", "encodings": ["x", "y"]},
                "bind": "scales",
                "views": ["view_1"],
            },
        ],
        "width": 0,
        "$schema": VEGA_SCHEMA,
        "autosize": {"type": "fit", "contains": "padding"},
    });
    vega_element(this, py_dumps(&spec), &name, ipc)
}

pub(crate) fn render_area_chart(this: &impl AppendChild, options: &AreaChartOptions<'_>) -> Result<(), DataError> {
    let numeric = numeric_columns(options.data);
    if numeric.is_empty() {
        return Err(DataError::InvalidOption("area chart needs at least one numeric series".into()));
    }
    let mut index_values = Vec::with_capacity(options.data.num_rows() * numeric.len());
    let mut color_values = Vec::with_capacity(options.data.num_rows() * numeric.len());
    let mut value_values: Vec<i64> = Vec::with_capacity(options.data.num_rows() * numeric.len());
    for series in &numeric {
        let array = column(options.data, series)?;
        let values = array.as_any().downcast_ref::<Int64Array>().ok_or_else(|| DataError::InvalidOption(format!("area chart series is not an int64 column: {series}")))?;
        for (row, value) in values.iter().enumerate() {
            index_values.push(row as i64);
            color_values.push(series.as_str());
            value_values.push(value.unwrap_or(0));
        }
    }
    let batch = chart_batch(vec![
        (Field::new(GENERATED_INDEX, DataType::Int64, true), Arc::new(Int64Array::from(index_values)) as ArrayRef),
        (Field::new(GENERATED_COLOR, DataType::LargeUtf8, true), Arc::new(LargeStringArray::from(color_values)) as ArrayRef),
        (Field::new(GENERATED_VALUE, DataType::Int64, true), Arc::new(Int64Array::from(value_values)) as ArrayRef),
    ])?;
    let (name, ipc) = chart_dataset(&batch)?;
    let encoding = json!({
        "color": {
            "field": GENERATED_COLOR,
            "legend": {"titlePadding": 5, "offset": 5, "orient": "bottom"},
            "title": " ",
            "type": "nominal",
        },
        "opacity": {"value": 0.7},
        "tooltip": [
            tooltip_field(GENERATED_INDEX, Some("index"), "quantitative"),
            tooltip_field(GENERATED_VALUE, Some("value"), "quantitative"),
            tooltip_field(GENERATED_COLOR, Some("color"), "nominal"),
        ],
        "x": channel(false, true, GENERATED_INDEX, &[], "", "quantitative"),
        "y": channel(true, true, GENERATED_VALUE, &[("stack", json!(false))], "", "quantitative"),
    });
    let spec = json!({
        "data": {"name": name},
        "mark": {"type": "area"},
        "encoding": encoding,
        "height": 0,
        "params": [interval_param("param_1")],
        "width": 0,
        "$schema": VEGA_SCHEMA,
        "autosize": {"type": "fit", "contains": "padding"},
    });
    vega_element(this, py_dumps(&spec), &name, ipc)
}

pub(crate) fn render_scatter_chart(this: &impl AppendChild, options: &ScatterChartOptions<'_>) -> Result<(), DataError> {
    let x_values = column(options.data, &options.x)?;
    let y_values = column(options.data, &options.y)?;
    if !is_numeric(x_values.data_type()) || !is_numeric(y_values.data_type()) {
        return Err(DataError::InvalidOption("scatter chart x and y must be numeric columns".into()));
    }
    // The reference serializes pandas frames whose arrow fields are nullable
    // regardless of the data, so the chart batch declares them nullable too.
    let batch = chart_batch(vec![
        (Field::new(&options.x, x_values.data_type().clone(), true), x_values.clone()),
        (Field::new(&options.y, y_values.data_type().clone(), true), y_values.clone()),
    ])?;
    let (name, ipc) = chart_dataset(&batch)?;
    let encoding = json!({
        "size": {"value": 100},
        "tooltip": [
            tooltip_field(&options.x, None, "quantitative"),
            tooltip_field(&options.y, None, "quantitative"),
        ],
        "x": channel(false, is_integer(x_values.data_type()), &options.x, &[], &options.x, "quantitative"),
        "y": channel(true, is_integer(y_values.data_type()), &options.y, &[], &options.y, "quantitative"),
    });
    let spec = json!({
        "data": {"name": name},
        "mark": {"type": "circle"},
        "encoding": encoding,
        "height": 0,
        "params": [interval_param("param_1")],
        "width": 0,
        "$schema": VEGA_SCHEMA,
        "autosize": {"type": "fit", "contains": "padding"},
    });
    vega_element(this, py_dumps(&spec), &name, ipc)
}

fn zoom_level(distance: f64) -> i32 {
    for index in 0..ZOOM_LEVELS.len() - 1 {
        if ZOOM_LEVELS[index + 1] < distance && distance <= ZOOM_LEVELS[index] {
            return index as i32;
        }
    }
    DEFAULT_ZOOM_LEVEL
}

pub(crate) fn render_map(this: &impl AppendChild, options: &MapOptions<'_>) -> Result<(), DataError> {
    // The reference serializes its fixed EMPTY_MAP for empty data instead of
    // folding an extent over zero rows.
    if options.data.num_rows() == 0 {
        this.push(Rc::new(RefCell::new(DataElement(proto::Element {
            width_config: DataSize::Stretch.width()?,
            height_config: DataSize::Pixels(500).height()?,
            r#type: Some(element::Type::DeckGlJsonChart(proto::DeckGlJsonChart {
                json: EMPTY_MAP_JSON.into(),
                ..Default::default()
            })),
            ..Default::default()
        }))));
        return Ok(());
    }
    let latitude = options.latitude.clone().unwrap_or_else(|| "lat".into());
    let longitude = options.longitude.clone().unwrap_or_else(|| "lon".into());
    let lat_values = f64_column(options.data, &latitude)?;
    let lon_values = f64_column(options.data, &longitude)?;
    let min_lat = lat_values.iter().flatten().fold(f64::INFINITY, f64::min);
    let max_lat = lat_values.iter().flatten().fold(f64::NEG_INFINITY, f64::max);
    let min_lon = lon_values.iter().flatten().fold(f64::INFINITY, f64::min);
    let max_lon = lon_values.iter().flatten().fold(f64::NEG_INFINITY, f64::max);
    let center_lat = (max_lat + min_lat) / 2.0;
    let center_lon = (max_lon + min_lon) / 2.0;
    let zoom = options.zoom.unwrap_or_else(|| zoom_level((max_lat - min_lat).abs().max((max_lon - min_lon).abs())));
    // The reference charts the used columns sorted by name, so every data
    // row carries its values under alphabetically ordered keys.
    let mut row_columns = vec![latitude.clone(), longitude.clone()];
    row_columns.sort();
    row_columns.dedup();
    let rows: Vec<Value> = (0..options.data.num_rows())
        .map(|row| {
            let pairs: Vec<(String, Value)> = row_columns
                .iter()
                .map(|name| {
                    let value = if *name == latitude { lat_values.value(row) } else { lon_values.value(row) };
                    (name.clone(), json!(value))
                })
                .collect();
            Value::Object(pairs.into_iter().collect())
        })
        .collect();
    let spec = json!({
        "initialViewState": {"latitude": center_lat, "longitude": center_lon, "pitch": 0, "zoom": zoom},
        "layers": [{
            "@@type": "ScatterplotLayer",
            "getPosition": format!("@@=[{longitude}, {latitude}]"),
            "getRadius": 100,
            "radiusMinPixels": 3,
            "radiusUnits": "meters",
            "getFillColor": [200, 30, 0, 160],
            "data": rows,
        }],
    });
    this.push(Rc::new(RefCell::new(DataElement(proto::Element {
        width_config: DataSize::Stretch.width()?,
        height_config: DataSize::Pixels(500).height()?,
        r#type: Some(element::Type::DeckGlJsonChart(proto::DeckGlJsonChart { json: py_dumps(&spec), ..Default::default() })),
        ..Default::default()
    }))));
    Ok(())
}

fn f64_column(data: &RecordBatch, name: &str) -> Result<Float64Array, DataError> {
    let values = column(data, name)?;
    match values.data_type() {
        DataType::Float64 => Ok(values.as_any().downcast_ref::<Float64Array>().expect("float64 column").clone()),
        DataType::Int64 => Ok(values.as_any().downcast_ref::<Int64Array>().expect("int64 column").iter().map(|value| value.map(|value| value as f64)).collect()),
        other => Err(DataError::InvalidOption(format!("map latitude/longitude must be float or int columns: {other}"))),
    }
}
