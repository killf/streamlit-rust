//! Columnar data views using the same element pipeline as native inputs.
use crate::api::AppendChild;
use crate::charts::{self, AreaChartOptions, LineChartOptions, MapOptions, ScatterChartOptions, VEGA_SCHEMA_URL, chart_batch, chart_dataset};
use crate::data::{Array, ArrayRef, DataError, DataType, Field, Float64Array, Int64Array, LargeStringArray, RecordBatch, Schema, StringArray, to_ipc_stream};
use crate::elements::data::DataElement;
use crate::proto::{self, element};
use crate::pywire::py_dumps;
use serde_json::{Value, json};
use std::{cell::RefCell, rc::Rc, sync::Arc};

#[derive(Clone, Copy, Debug)]
pub enum DataSize {
    Auto,
    Stretch,
    Content,
    Pixels(i32),
}

impl From<i32> for DataSize {
    fn from(pixels: i32) -> Self {
        Self::Pixels(pixels)
    }
}

impl DataSize {
    pub(crate) fn width(self) -> Result<Option<proto::streamlit::WidthConfig>, DataError> {
        use proto::streamlit::width_config::WidthSpec;
        let width_spec = match self {
            Self::Stretch => WidthSpec::UseStretch(true),
            Self::Content => WidthSpec::UseContent(true),
            Self::Pixels(value) if value > 0 => WidthSpec::PixelWidth(value as u32),
            _ => return Err(DataError::InvalidOption("width must be stretch, content, or positive pixels".into())),
        };
        Ok(Some(proto::streamlit::WidthConfig { width_spec: Some(width_spec) }))
    }

    pub(crate) fn height(self) -> Result<Option<proto::streamlit::HeightConfig>, DataError> {
        use proto::streamlit::height_config::HeightSpec;
        let height_spec = match self {
            Self::Auto => return Ok(None),
            Self::Stretch => HeightSpec::UseStretch(true),
            Self::Content => HeightSpec::UseContent(true),
            Self::Pixels(value) if value > 0 => HeightSpec::PixelHeight(value as u32),
            _ => return Err(DataError::InvalidOption("height must be auto, stretch, content, or positive pixels".into())),
        };
        Ok(Some(proto::streamlit::HeightConfig { height_spec: Some(height_spec) }))
    }
}

pub struct DataframeOptions<'a> {
    data: &'a RecordBatch,
    width: DataSize,
    height: DataSize,
    hide_index: Option<bool>,
    column_order: Vec<String>,
}

impl<'a> DataframeOptions<'a> {
    pub fn new(data: &'a RecordBatch) -> Self {
        Self {
            data,
            width: DataSize::Stretch,
            height: DataSize::Auto,
            hide_index: None,
            column_order: Vec::new(),
        }
    }
    pub fn hide_index(mut self, hide: bool) -> Self {
        self.hide_index = Some(hide);
        self
    }
    pub fn column_order(mut self, columns: impl IntoIterator<Item = impl Into<String>>) -> Self {
        self.column_order = columns.into_iter().map(Into::into).collect();
        self
    }
    pub fn width(mut self, width: impl Into<DataSize>) -> Self {
        self.width = width.into();
        self
    }
    pub fn height(mut self, height: impl Into<DataSize>) -> Self {
        self.height = height.into();
        self
    }
}

impl<'a> From<&'a RecordBatch> for DataframeOptions<'a> {
    fn from(data: &'a RecordBatch) -> Self {
        Self::new(data)
    }
}

/// Table border modes accepted by the public reference API.
#[derive(Clone, Copy, Debug, Default)]
pub enum TableBorder {
    #[default]
    All,
    None,
    Horizontal,
}

impl From<bool> for TableBorder {
    fn from(show: bool) -> Self {
        if show { Self::All } else { Self::None }
    }
}

impl TryFrom<&str> for TableBorder {
    type Error = DataError;
    fn try_from(value: &str) -> Result<Self, Self::Error> {
        match value {
            "horizontal" => Ok(Self::Horizontal),
            _ => Err(DataError::InvalidOption("border must be true, false, or horizontal".into())),
        }
    }
}

/// Static Markdown table. Arrow schema/index metadata is preserved; batches
/// without index metadata hide row numbers by default; hide_index(false) adds
/// an Arrow RangeIndex descriptor without changing data columns or values.
pub struct TableOptions<'a> {
    data: &'a RecordBatch,
    border: TableBorder,
    hide_index: Option<bool>,
    hide_header: bool,
    width: DataSize,
    height: DataSize,
    alt: Option<String>,
}

impl<'a> TableOptions<'a> {
    pub fn new(data: &'a RecordBatch) -> Self {
        Self {
            data,
            border: TableBorder::All,
            hide_index: None,
            hide_header: false,
            width: DataSize::Stretch,
            height: DataSize::Content,
            alt: None,
        }
    }
    pub fn border(mut self, border: impl Into<TableBorder>) -> Self {
        self.border = border.into();
        self
    }
    pub fn hide_index(mut self, hide: bool) -> Self {
        self.hide_index = Some(hide);
        self
    }
    pub fn hide_header(mut self, hide: bool) -> Self {
        self.hide_header = hide;
        self
    }
    pub fn width(mut self, width: impl Into<DataSize>) -> Self {
        self.width = width.into();
        self
    }
    pub fn height(mut self, height: impl Into<DataSize>) -> Self {
        self.height = height.into();
        self
    }
    pub fn alt(mut self, alt: impl Into<String>) -> Self {
        self.alt = Some(alt.into());
        self
    }
}

impl<'a> From<&'a RecordBatch> for TableOptions<'a> {
    fn from(data: &'a RecordBatch) -> Self {
        Self::new(data)
    }
}

#[derive(Default)]
struct NativeBar {
    x: Option<String>,
    y: Vec<String>,
    horizontal: bool,
    unsorted: bool,
    unstacked: bool,
}

/// Bar chart options: `native` follows the measured st.bar_chart rules; `new`
/// retains the existing explicit Vega mappings. This is a bounded API subset.
pub struct BarChartOptions<'a> {
    data: &'a RecordBatch,
    native: Option<NativeBar>,
    x: String,
    y: String,
    x_order: Option<Vec<String>>,
    tooltips: Vec<(String, String)>,
    plot_height: Option<u32>,
    width: DataSize,
    height: DataSize,
}

impl<'a> BarChartOptions<'a> {
    pub fn new(data: &'a RecordBatch, x: impl Into<String>, y: impl Into<String>) -> Self {
        Self {
            data,
            native: None,
            x: x.into(),
            y: y.into(),
            x_order: None,
            tooltips: Vec::new(),
            plot_height: None,
            width: DataSize::Stretch,
            height: DataSize::Content,
        }
    }
    /// Infer the index and numeric series as st.bar_chart does. The measured
    /// native subset accepts Int64/Float64 series and string/numeric categories.
    /// Use `new(data, x, y)` for the existing explicit Vega mapping API.
    pub fn native(data: &'a RecordBatch) -> Self {
        let mut options = Self::new(data, "", "");
        options.native = Some(NativeBar::default());
        options
    }
    fn native_config(&mut self) -> &mut NativeBar {
        let x = (!self.x.is_empty()).then(|| self.x.clone());
        let y = if self.y.is_empty() { Vec::new() } else { vec![self.y.clone()] };
        self.native.get_or_insert(NativeBar { x, y, ..Default::default() })
    }
    /// Select a native bar's category column instead of the implicit row index.
    pub fn x(mut self, column: impl Into<String>) -> Self {
        self.native_config().x = Some(column.into());
        self
    }
    pub fn y(mut self, column: impl Into<String>) -> Self {
        self.native_config().y = vec![column.into()];
        self
    }
    pub fn series(mut self, columns: impl IntoIterator<Item = impl Into<String>>) -> Self {
        self.native_config().y = columns.into_iter().map(Into::into).collect();
        self
    }
    pub fn horizontal(mut self, horizontal: bool) -> Self {
        self.native_config().horizontal = horizontal;
        self
    }
    /// false retains input category order; true uses Vega's default sorting.
    pub fn sort(mut self, sort: bool) -> Self {
        self.native_config().unsorted = !sort;
        self
    }
    /// Group native series side by side (the public stack=False behavior).
    pub fn side_by_side(mut self) -> Self {
        self.native_config().unstacked = true;
        self
    }
    pub fn x_order(mut self, values: impl IntoIterator<Item = impl Into<String>>) -> Self {
        self.x_order = Some(values.into_iter().map(Into::into).collect());
        self
    }
    pub fn tooltip(mut self, field: impl Into<String>, title: impl Into<String>) -> Self {
        self.tooltips.push((field.into(), title.into()));
        self
    }
    /// Set the plot's internal height independently of its container sizing.
    pub fn plot_height(mut self, pixels: u32) -> Self {
        self.plot_height = Some(pixels);
        self
    }
    pub fn width(mut self, width: impl Into<DataSize>) -> Self {
        self.width = width.into();
        self
    }
    pub fn height(mut self, height: impl Into<DataSize>) -> Self {
        self.height = height.into();
        self
    }
}

impl<'a> From<&'a RecordBatch> for BarChartOptions<'a> {
    fn from(data: &'a RecordBatch) -> Self {
        Self::native(data)
    }
}

pub trait DataApi {
    fn table<'a>(&self, data: impl Into<TableOptions<'a>>) -> Result<(), DataError>;
    fn dataframe<'a>(&self, data: impl Into<DataframeOptions<'a>>) -> Result<(), DataError>;
    fn bar_chart<'a>(&self, options: impl Into<BarChartOptions<'a>>) -> Result<(), DataError>;
    fn line_chart<'a>(&self, options: impl Into<LineChartOptions<'a>>) -> Result<(), DataError>;
    fn area_chart<'a>(&self, options: impl Into<AreaChartOptions<'a>>) -> Result<(), DataError>;
    fn scatter_chart<'a>(&self, options: impl Into<ScatterChartOptions<'a>>) -> Result<(), DataError>;
    fn map<'a>(&self, options: impl Into<MapOptions<'a>>) -> Result<(), DataError>;
}

fn append(this: &impl AppendChild, element: proto::Element) {
    this.push(Rc::new(RefCell::new(DataElement(element))));
}

fn arrow_data(data: &RecordBatch) -> Result<proto::ArrowData, DataError> {
    Ok(proto::ArrowData { data: to_ipc_stream(data)?, styler: None })
}

/// The library-chart datasets (altair, vega_lite inline values) ride the
/// exact pandas-3 IPC the pinned reference emits: large_string text columns
/// and the measured pandas metadata (creator stamp replicated from the
/// measured wire, not invented), serialized with python JSON separators.
pub(crate) fn chart_arrow_data(data: &RecordBatch) -> Result<proto::ArrowData, DataError> {
    let mut fields = Vec::with_capacity(data.num_columns());
    let mut columns: Vec<ArrayRef> = Vec::with_capacity(data.num_columns());
    for (index, field) in data.schema_ref().fields().iter().enumerate() {
        let array = data.column(index);
        if matches!(field.data_type(), DataType::Utf8) {
            let texts: Vec<&str> = array.as_any().downcast_ref::<StringArray>().expect("utf8 column").iter().map(Option::unwrap_or_default).collect();
            fields.push(Field::new(field.name(), DataType::LargeUtf8, field.is_nullable()));
            columns.push(Arc::new(LargeStringArray::from(texts)));
        } else {
            fields.push(field.as_ref().clone());
            columns.push(array.clone());
        }
    }
    let wire_columns: Vec<Value> = fields
        .iter()
        .map(|field| {
            let (pandas_type, numpy_type) = match field.data_type() {
                DataType::Utf8 | DataType::LargeUtf8 => ("object", "str"),
                DataType::Int64 => ("int64", "int64"),
                DataType::Float64 => ("float64", "float64"),
                DataType::Boolean => ("bool", "bool"),
                kind => return Err(DataError::InvalidOption(format!("chart dataset column type is not supported yet: {kind}"))),
            };
            Ok(json!({"name":field.name(),"field_name":field.name(),"pandas_type":pandas_type,"numpy_type":numpy_type,"metadata":null}))
        })
        .collect::<Result<_, DataError>>()?;
    let metadata = crate::pywire::py_dumps(&json!({
        "index_columns":[{"kind":"range","name":null,"start":0,"stop":data.num_rows(),"step":1}],
        "column_indexes":[{"name":null,"field_name":null,"pandas_type":"unicode","numpy_type":"str","metadata":{"encoding":"UTF-8"}}],
        "columns":wire_columns,
        "attributes":{},
        "creator":{"library":"pyarrow","version":"26.0.0"},
        "pandas_version":"3.1.0"
    }));
    let mut schema_metadata = data.schema_ref().metadata().clone();
    schema_metadata.insert("pandas".to_string(), metadata);
    let schema = Schema::new_with_metadata(fields, schema_metadata);
    let batch = RecordBatch::try_new(Arc::new(schema), columns)?;
    arrow_data(&batch)
}

fn field_type(data: &RecordBatch, name: &str) -> Result<&'static str, DataError> {
    let schema = data.schema_ref();
    let field = schema.field_with_name(name).map_err(|_| DataError::InvalidOption(format!("column does not exist: {name}")))?;
    match field.data_type() {
        DataType::Utf8 | DataType::LargeUtf8 | DataType::Boolean => Ok("nominal"),
        DataType::Int8 | DataType::Int16 | DataType::Int32 | DataType::Int64 | DataType::UInt8 | DataType::UInt16 | DataType::UInt32 | DataType::UInt64 | DataType::Float32 | DataType::Float64 => Ok("quantitative"),
        value => Err(DataError::InvalidOption(format!("chart column type is not supported yet: {value}"))),
    }
}

// Measured on the reference: an integer y axis renders integer ticks
// (altair's default tickMinStep 1), a float axis does not.
fn field_is_integer(data: &RecordBatch, name: &str) -> bool {
    data.schema_ref()
        .field_with_name(name)
        .map(|field| {
            matches!(
                field.data_type(),
                DataType::Int8 | DataType::Int16 | DataType::Int32 | DataType::Int64 | DataType::UInt8 | DataType::UInt16 | DataType::UInt32 | DataType::UInt64
            )
        })
        .unwrap_or(false)
}

// Measured on the reference: the bar chart's x axis encodes strings as
// ordinal, while tooltips stay nominal.
fn x_field_type(data: &RecordBatch, name: &str) -> Result<&'static str, DataError> {
    match field_type(data, name)? {
        "nominal" => Ok("ordinal"),
        other => Ok(other),
    }
}

// Arrow columns are literal names, whereas Vega field strings are access paths.
// Escape each original character once; serde_json separately escapes the JSON
// representation. Schema lookup, IPC names, and tooltip titles stay unchanged.
fn vega_literal_field(name: &str) -> String {
    let mut field = String::with_capacity(name.len());
    for ch in name.chars() {
        if matches!(ch, '\\' | '.' | '[' | ']') {
            field.push('\\');
        }
        field.push(ch);
    }
    field
}

// Only interpret the public Arrow pandas index descriptor. We never synthesize
// pandas metadata: ordinary native batches use an implicit RangeIndex.
fn pandas_index(data: &RecordBatch) -> Result<Vec<Value>, DataError> {
    match data.schema_ref().metadata().get("pandas") {
        None => Ok(Vec::new()),
        Some(metadata) => {
            let metadata: Value = serde_json::from_str(metadata)?;
            Ok(metadata["index_columns"].as_array().cloned().unwrap_or_default())
        }
    }
}

// The official frontend requires an index descriptor to display virtual row
// numbers. Add only truthful Arrow/pandas interoperability metadata, with no
// invented pandas version or Python producer identity. Existing metadata wins.
fn with_range_index(data: &RecordBatch) -> Result<RecordBatch, DataError> {
    let columns = data
        .schema_ref()
        .fields()
        .iter()
        .map(|field| {
            let (pandas_type, numpy_type) = match field.data_type() {
                DataType::Utf8 | DataType::LargeUtf8 => ("unicode", "object"),
                DataType::Int8 => ("int8", "Int8"),
                DataType::Int16 => ("int16", "Int16"),
                DataType::Int32 => ("int32", "Int32"),
                DataType::Int64 => ("int64", "Int64"),
                DataType::UInt8 => ("uint8", "UInt8"),
                DataType::UInt16 => ("uint16", "UInt16"),
                DataType::UInt32 => ("uint32", "UInt32"),
                DataType::UInt64 => ("uint64", "UInt64"),
                DataType::Float32 => ("float32", "float32"),
                DataType::Float64 => ("float64", "float64"),
                DataType::Boolean => ("bool", "boolean"),
                kind => return Err(DataError::InvalidOption(format!("implicit table index metadata is not supported yet for {kind}; preserve an existing Arrow index descriptor"))),
            };
            Ok(json!({"name":field.name(),"field_name":field.name(),"pandas_type":pandas_type,"numpy_type":numpy_type,"metadata":null}))
        })
        .collect::<Result<Vec<_>, DataError>>()?;
    let mut metadata = data.schema_ref().metadata().clone();
    metadata.insert(
        "pandas",
        serde_json::to_string(&json!({
            "index_columns":[{"kind":"range","name":null,"start":0,"stop":data.num_rows(),"step":1}],
            "column_indexes":[{"name":null,"field_name":null,"pandas_type":"unicode","numpy_type":"object","metadata":{"encoding":"UTF-8"}}],
            "columns":columns
        }))?,
    );
    let schema = data.schema_ref().as_ref().clone().with_metadata(metadata);
    Ok(RecordBatch::try_new(Arc::new(schema), data.columns().to_vec())?)
}

fn repeat_column(column: &ArrayRef, repeats: usize) -> Result<ArrayRef, DataError> {
    macro_rules! repeat {
        ($array:ty) => {{
            let array = column.as_any().downcast_ref::<$array>().expect("type checked");
            Arc::new(<$array>::from((0..repeats).flat_map(|_| array.iter()).collect::<Vec<_>>())) as ArrayRef
        }};
    }
    Ok(match column.data_type() {
        DataType::Int64 => repeat!(Int64Array),
        DataType::Float64 => repeat!(Float64Array),
        DataType::Utf8 => repeat!(crate::data::StringArray),
        DataType::LargeUtf8 => repeat!(LargeStringArray),
        DataType::Boolean => repeat!(crate::data::BooleanArray),
        kind => return Err(DataError::InvalidOption(format!("native bar category type is not supported yet: {kind}"))),
    })
}

fn melt_values(data: &RecordBatch, columns: &[String]) -> Result<ArrayRef, DataError> {
    let arrays = columns.iter().map(|name| data.column_by_name(name).expect("validated column")).collect::<Vec<_>>();
    let integer = arrays.iter().all(|a| a.data_type() == &DataType::Int64);
    if integer {
        let values = arrays.iter().flat_map(|a| a.as_any().downcast_ref::<Int64Array>().expect("type checked").iter()).collect::<Vec<_>>();
        return Ok(Arc::new(Int64Array::from(values)));
    }
    let mut values = Vec::with_capacity(data.num_rows() * columns.len());
    for array in arrays {
        match array.data_type() {
            DataType::Float64 => values.extend(array.as_any().downcast_ref::<Float64Array>().expect("type checked").iter()),
            DataType::Int64 => {
                for value in array.as_any().downcast_ref::<Int64Array>().expect("type checked").iter() {
                    // Do not silently lose integer precision while promoting a
                    // mixed numeric series to the observed Float64 wire type.
                    if value.is_some_and(|n| n.unsigned_abs() > (1_u64 << 53)) {
                        return Err(DataError::InvalidOption("mixed numeric series would lose Int64 precision".into()));
                    }
                    values.push(value.map(|n| n as f64));
                }
            }
            kind => return Err(DataError::InvalidOption(format!("native bar series type is not supported yet: {kind}; use Int64 or Float64"))),
        }
    }
    Ok(Arc::new(Float64Array::from(values)))
}

fn append_native_bar(this: &impl AppendChild, options: &BarChartOptions<'_>, native: &NativeBar) -> Result<(), DataError> {
    if options.x_order.is_some() || !options.tooltips.is_empty() || options.plot_height.is_some() {
        return Err(DataError::InvalidOption("native bar uses automatic tooltips; use height/sort or the explicit mapping API".into()));
    }
    if matches!(options.height, DataSize::Auto) {
        return Err(DataError::InvalidOption("native bar height must be content, stretch, or positive pixels".into()));
    }
    let width_config = options.width.width()?;
    let height_config = options.height.height()?;
    let source = options.data;
    let index = pandas_index(source)?;
    let ys = if native.y.is_empty() {
        source
            .schema_ref()
            .fields()
            .iter()
            .map(|f| f.name())
            .filter(|name| Some(name.as_str()) != native.x.as_deref() && !index.iter().any(|v| v.as_str() == Some(name.as_str())))
            .cloned()
            .collect::<Vec<_>>()
    } else {
        native.y.clone()
    };
    if ys.is_empty() {
        return Err(DataError::InvalidOption("native bar needs at least one numeric series".into()));
    }
    let mut unique = std::collections::HashSet::new();
    for name in &ys {
        field_type(source, name)?;
        if !unique.insert(name) || native.x.as_ref() == Some(name) {
            return Err(DataError::InvalidOption("native bar category and series columns must be distinct".into()));
        }
        if !matches!(source.column_by_name(name).expect("validated column").data_type(), DataType::Int64 | DataType::Float64) {
            return Err(DataError::InvalidOption(format!("native bar series {name} must be Int64 or Float64")));
        }
    }
    let (x_name, x_title, x_tooltip_type, x_column) = if let Some(x) = &native.x {
        let kind = field_type(source, x)?;
        let column = source.column_by_name(x).expect("validated column").clone();
        let name = if x.chars().any(|c| matches!(c, '.' | '[' | ']' | '\\')) { "col -- streamlit-generated-0".to_string() } else { x.clone() };
        (name, x.clone(), kind, column)
    } else {
        let (start, step) = if let Some(range) = index.first() {
            if range["kind"] != "range" {
                return Err(DataError::InvalidOption("native bar inferred index currently supports only RangeIndex; select x explicitly".into()));
            }
            (range["start"].as_i64().unwrap_or(0), range["step"].as_i64().unwrap_or(1))
        } else {
            (0, 1)
        };
        let values = (0..source.num_rows())
            .map(|i| {
                i64::try_from(i)
                    .ok()
                    .and_then(|i| i.checked_mul(step))
                    .and_then(|offset| start.checked_add(offset))
                    .ok_or_else(|| DataError::InvalidOption("range index overflows Int64".into()))
            })
            .collect::<Result<Vec<_>, _>>()?;
        ("index -- streamlit-generated".into(), "".into(), "quantitative", Arc::new(Int64Array::from(values)) as ArrayRef)
    };
    let wide = ys.len() > 1;
    let mut fields = Vec::new();
    let mut arrays = Vec::new();
    let repeats = if wide { ys.len() } else { 1 };
    let x_values = repeat_column(&x_column, repeats)?;
    fields.push(Field::new(&x_name, x_values.data_type().clone(), x_values.is_nullable()));
    arrays.push(x_values);
    let y_name;
    let y_title;
    if wide {
        let color = "color -- streamlit-generated";
        if x_name == color || x_name == "value -- streamlit-generated" {
            return Err(DataError::InvalidOption("native bar category conflicts with a generated series field".into()));
        }
        let colors = Arc::new(LargeStringArray::from(ys.iter().flat_map(|name| std::iter::repeat_n(name.as_str(), source.num_rows())).collect::<Vec<_>>())) as ArrayRef;
        fields.push(Field::new(color, DataType::LargeUtf8, false));
        arrays.push(colors);
        y_name = "value -- streamlit-generated".to_string();
        y_title = String::new();
        let values = melt_values(source, &ys)?;
        fields.push(Field::new(&y_name, values.data_type().clone(), values.is_nullable()));
        arrays.push(values);
    } else {
        y_title = ys[0].clone();
        y_name = if y_title.chars().any(|c| matches!(c, '.' | '[' | ']' | '\\')) { "col -- streamlit-generated-1".into() } else { y_title.clone() };
        if y_name == x_name {
            return Err(DataError::InvalidOption("native bar generated field name collision".into()));
        }
        let values = source.column_by_name(&ys[0]).expect("validated column").clone();
        fields.push(Field::new(&y_name, values.data_type().clone(), values.is_nullable()));
        arrays.push(values);
    }
    let batch = chart_batch(fields.into_iter().zip(arrays).collect())?;
    let (name, ipc) = chart_dataset(&batch)?;
    let mut category = json!({"axis":{"grid":false},"field":vega_literal_field(&x_name),"scale":{},"title":x_title,"type":"ordinal"});
    if x_tooltip_type == "quantitative" {
        category["axis"]["tickMinStep"] = json!(1);
    }
    if native.unsorted {
        category["sort"] = Value::Null;
    }
    let inferred_single = !wide && native.y.is_empty();
    let mut value = json!({"axis":{"grid":true},"field":vega_literal_field(&y_name),"scale":{},"title":if inferred_single { "" } else { &y_title },"type":"quantitative"});
    if batch.column_by_name(&y_name).expect("constructed field").data_type() == &DataType::Int64 {
        value["axis"]["tickMinStep"] = json!(1);
    }
    // The measured tooltip rule: a field carries a title only when its wire
    // name is generated (the index) or an alias of a dotted/bracketed
    // original, never for a plain column name.
    let x_tooltip = if x_name == "index -- streamlit-generated" {
        json!({"field":vega_literal_field(&x_name),"title":"index","type":x_tooltip_type})
    } else if x_name != x_title {
        json!({"field":vega_literal_field(&x_name),"title":x_title,"type":x_tooltip_type})
    } else {
        json!({"field":vega_literal_field(&x_name),"type":x_tooltip_type})
    };
    let y_tooltip = if y_name == "value -- streamlit-generated" {
        json!({"field":vega_literal_field(&y_name),"title":"value","type":"quantitative"})
    } else if y_name != y_title {
        json!({"field":vega_literal_field(&y_name),"title":y_title,"type":"quantitative"})
    } else {
        json!({"field":vega_literal_field(&y_name),"type":"quantitative"})
    };
    let tooltip = json!([x_tooltip, y_tooltip]);
    let mut encoding = if native.horizontal {
        json!({"x":value,"y":category,"tooltip":tooltip})
    } else {
        json!({"x":category,"y":value,"tooltip":tooltip})
    };
    if wide {
        encoding["color"] = json!({"field":"color -- streamlit-generated","legend":{"titlePadding":5,"offset":5,"orient":"bottom"},"title":" ","type":"nominal"});
        encoding["tooltip"].as_array_mut().expect("array").push(json!({"field":"color -- streamlit-generated","title":"color","type":"nominal"}));
        if native.unstacked {
            let (value_axis, category_offset, value_offset) = if native.horizontal { ("x", "yOffset", "xOffset") } else { ("y", "xOffset", "yOffset") };
            encoding[value_axis]["stack"] = json!(false);
            encoding[category_offset] = json!({"field":"color -- streamlit-generated"});
            encoding[value_offset] = json!({});
        }
    }
    let spec = json!({"data":{"name":name},"mark":{"type":"bar"},"encoding":encoding,
        "height":if let DataSize::Pixels(value) = options.height { value } else { 0 },
        "params":[{"name":"param_1","select":{"type":"interval","encodings":["x","y"]},"bind":"scales"}],
        "width":if let DataSize::Pixels(value) = options.width { value } else { 0 },
        "$schema":VEGA_SCHEMA_URL,"autosize":{"type":"fit","contains":"padding"}});
    append(
        this,
        proto::Element {
            width_config,
            height_config,
            r#type: Some(element::Type::VegaLiteChart(proto::VegaLiteChart {
                spec: py_dumps(&spec),
                datasets: vec![proto::ArrowNamedDataSet {
                    name,
                    has_name: true,
                    data: Some(proto::ArrowData { data: ipc, styler: None }),
                }],
                theme: "streamlit".into(),
                ..Default::default()
            })),
            ..Default::default()
        },
    );
    Ok(())
}

impl<C: AppendChild> DataApi for C {
    fn table<'a>(&self, data: impl Into<TableOptions<'a>>) -> Result<(), DataError> {
        let options = data.into();
        if matches!(options.height, DataSize::Auto) {
            return Err(DataError::InvalidOption("table height must be content, stretch, or positive pixels".into()));
        }
        let index = pandas_index(options.data)?;
        let indexed;
        let data = if options.hide_index == Some(false) && !options.data.schema_ref().metadata().contains_key("pandas") {
            indexed = with_range_index(options.data)?;
            &indexed
        } else {
            options.data
        };
        let element = proto::Element {
            width_config: options.width.width()?,
            height_config: options.height.height()?,
            r#type: Some(element::Type::Table(proto::Table {
                arrow_data: Some(arrow_data(data)?),
                border_mode: match options.border {
                    TableBorder::All => 0,
                    TableBorder::None => 1,
                    TableBorder::Horizontal => 2,
                },
                hide_index: options.hide_index.unwrap_or(!index.iter().any(Value::is_string)),
                hide_header: options.hide_header,
                alt: options.alt,
            })),
            ..Default::default()
        };
        append(self, element);
        Ok(())
    }

    fn dataframe<'a>(&self, data: impl Into<DataframeOptions<'a>>) -> Result<(), DataError> {
        let options = data.into();
        let mut columns = json!({});
        if let Some(hidden) = options.hide_index {
            columns["_index"] = json!({"hidden":hidden});
        }
        let element = proto::Element {
            width_config: options.width.width()?,
            height_config: options.height.height()?,
            r#type: Some(element::Type::Dataframe(proto::Dataframe {
                arrow_data: Some(arrow_data(options.data)?),
                columns: serde_json::to_string(&columns)?,
                column_order: options.column_order,
                ..Default::default()
            })),
            ..Default::default()
        };
        append(self, element);
        Ok(())
    }

    fn bar_chart<'a>(&self, options: impl Into<BarChartOptions<'a>>) -> Result<(), DataError> {
        let options = options.into();
        if let Some(native) = &options.native {
            return append_native_bar(self, &options, native);
        }
        let x_type = x_field_type(options.data, &options.x)?;
        let y_type = field_type(options.data, &options.y)?;
        if y_type != "quantitative" {
            return Err(DataError::InvalidOption("bar chart y must be numeric".into()));
        }
        if options.plot_height == Some(0) {
            return Err(DataError::InvalidOption("plot height must be positive".into()));
        }
        let data = arrow_data(options.data)?;
        let name = format!("{:x}", md5::compute(&data.data));
        let mut x = json!({"field":vega_literal_field(&options.x), "type":x_type});
        if let Some(order) = options.x_order {
            x["sort"] = json!(order);
        }
        let mut y = json!({"field":vega_literal_field(&options.y), "type":y_type});
        if field_is_integer(options.data, &options.y) {
            y["axis"] = json!({"grid": true, "tickMinStep":1});
        }
        let mut encoding = json!({"x":x, "y":y});
        if !options.tooltips.is_empty() {
            let tooltips = options
                .tooltips
                .into_iter()
                .map(|(field, title)| {
                    let kind = field_type(options.data, &field)?;
                    Ok(json!({"field":vega_literal_field(&field),"title":title,"type":kind}))
                })
                .collect::<Result<Vec<Value>, DataError>>()?;
            encoding["tooltip"] = json!(tooltips);
        }
        let mut spec = json!({
            "data":{"name":name}, "mark":{"type":"bar"}, "encoding":encoding,
            "$schema":"https://vega.github.io/schema/vega-lite/v5.20.1.json",
            "autosize":{"type":"fit","contains":"padding"}
        });
        if let Some(height) = options.plot_height {
            spec["height"] = json!(height);
        }
        let element = proto::Element {
            width_config: options.width.width()?,
            height_config: options.height.height()?,
            r#type: Some(element::Type::VegaLiteChart(proto::VegaLiteChart {
                spec: serde_json::to_string(&spec)?,
                datasets: vec![proto::ArrowNamedDataSet { name, has_name: true, data: Some(data) }],
                theme: "streamlit".into(),
                ..Default::default()
            })),
            ..Default::default()
        };
        append(self, element);
        Ok(())
    }

    fn line_chart<'a>(&self, options: impl Into<LineChartOptions<'a>>) -> Result<(), DataError> {
        charts::render_line_chart(self, &options.into())
    }

    fn area_chart<'a>(&self, options: impl Into<AreaChartOptions<'a>>) -> Result<(), DataError> {
        charts::render_area_chart(self, &options.into())
    }

    fn scatter_chart<'a>(&self, options: impl Into<ScatterChartOptions<'a>>) -> Result<(), DataError> {
        charts::render_scatter_chart(self, &options.into())
    }

    fn map<'a>(&self, options: impl Into<MapOptions<'a>>) -> Result<(), DataError> {
        charts::render_map(self, &options.into())
    }
}

#[cfg(test)]
#[path = "../tests/data/mod.rs"]
mod tests;
