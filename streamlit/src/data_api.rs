//! Columnar data views using the same element pipeline as native inputs.
use crate::api::AppendChild;
use crate::data::{DataError, DataType, RecordBatch, to_ipc_stream};
use crate::elements::data::DataElement;
use crate::proto::{self, element};
use serde_json::{Value, json};
use std::{cell::RefCell, rc::Rc};

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
    fn width(self) -> Result<Option<proto::streamlit::WidthConfig>, DataError> {
        use proto::streamlit::width_config::WidthSpec;
        let width_spec = match self {
            Self::Stretch => WidthSpec::UseStretch(true),
            Self::Content => WidthSpec::UseContent(true),
            Self::Pixels(value) if value > 0 => WidthSpec::PixelWidth(value as u32),
            _ => return Err(DataError::InvalidOption("width must be stretch, content, or positive pixels".into())),
        };
        Ok(Some(proto::streamlit::WidthConfig { width_spec: Some(width_spec) }))
    }

    fn height(self) -> Result<Option<proto::streamlit::HeightConfig>, DataError> {
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

/// A bar chart with explicit field mappings. Wider inference/selection APIs
/// require separate reference evidence; this is not the entire st.bar_chart API.
pub struct BarChartOptions<'a> {
    data: &'a RecordBatch,
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
            x: x.into(),
            y: y.into(),
            x_order: None,
            tooltips: Vec::new(),
            plot_height: None,
            width: DataSize::Stretch,
            height: DataSize::Content,
        }
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

pub trait DataApi {
    fn dataframe<'a>(&self, data: impl Into<DataframeOptions<'a>>) -> Result<(), DataError>;
    fn bar_chart(&self, options: BarChartOptions<'_>) -> Result<(), DataError>;
}

fn append(this: &impl AppendChild, element: proto::Element) {
    this.push(Rc::new(RefCell::new(DataElement(element))));
}

fn arrow_data(data: &RecordBatch) -> Result<proto::ArrowData, DataError> {
    Ok(proto::ArrowData { data: to_ipc_stream(data)?, styler: None })
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

impl<C: AppendChild> DataApi for C {
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

    fn bar_chart(&self, options: BarChartOptions<'_>) -> Result<(), DataError> {
        let x_type = field_type(options.data, &options.x)?;
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
        let mut encoding = json!({"x":x, "y":{"field":vega_literal_field(&options.y), "type":y_type}});
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
}

#[cfg(test)]
#[path = "../tests/data/mod.rs"]
mod tests;
