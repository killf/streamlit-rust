//! Column configuration for the data views against the measured 1.66.1 wire
//! (see .codex/compatibility.md, Column config): every helper builds the
//! exact JSON the reference's ``ColumnConfig``/``type_config`` produces,
//! with None fields dropped, and the whole mapping serializes as one JSON
//! string on the dataframe proto's ``columns`` field (the reference's
//! ``json.dumps`` defaults: ``, ``/``: `` separators).
use serde_json::{Map, Value};

fn text_value(text: &str) -> Value {
    Value::String(text.into())
}

/// One column's configuration. The base fields mirror the reference's
/// ColumnConfig; the typed helpers add a ``type_config`` object.
#[derive(Default, Clone)]
pub struct ColumnConfig {
    label: Option<Value>,
    width: Option<Value>,
    help: Option<Value>,
    disabled: Option<Value>,
    required: Option<Value>,
    pinned: Option<Value>,
    alignment: Option<Value>,
    default: Option<Value>,
    type_config: Option<Map<String, Value>>,
    /// The button column's widget key: never part of the columns JSON, it
    /// only identifies the column's click widget (button_click_widgets).
    key: Option<String>,
}

impl ColumnConfig {
    fn from_base(base: ColumnBase) -> Self {
        Self {
            label: base.label,
            width: base.width,
            help: base.help,
            disabled: base.disabled,
            required: base.required,
            pinned: base.pinned,
            alignment: base.alignment,
            ..Default::default()
        }
    }

    fn typed(mut self, kind: &str) -> Self {
        let mut config = Map::new();
        config.insert("type".into(), Value::String(kind.into()));
        self.type_config = Some(config);
        self
    }

    fn set(mut self, key: &str, value: Value) -> Self {
        self.type_config.as_mut().expect("typed column").insert(key.into(), value);
        self
    }

    /// The wire JSON object for this column (None fields dropped).
    pub fn wire(&self) -> Value {
        let mut out = Map::new();
        for (key, value) in [
            ("label", &self.label),
            ("width", &self.width),
            ("help", &self.help),
            ("disabled", &self.disabled),
            ("required", &self.required),
            ("pinned", &self.pinned),
            ("alignment", &self.alignment),
            ("default", &self.default),
        ] {
            if let Some(value) = value {
                out.insert(key.into(), value.clone());
            }
        }
        if let Some(config) = &self.type_config {
            out.insert("type_config".into(), Value::Object(config.clone()));
        }
        Value::Object(out)
    }

    /// Set the column's top-level default value.
    pub fn default_value(mut self, default: impl Into<Value>) -> Self {
        self.default = Some(default.into());
        self
    }
}

fn width_value(width: &str) -> Value {
    Value::String(width.into())
}

/// The seven base ColumnConfig fields every helper shares. The chained
/// builders replace the reference's positional parameters: only the fields
/// you set appear in the wire JSON.
///
/// ```text
/// ColumnBase::new(Some("Name")).width("medium").help("the name").pinned(true).alignment("center")
/// ```
#[derive(Default)]
pub struct ColumnBase {
    label: Option<Value>,
    width: Option<Value>,
    help: Option<Value>,
    disabled: Option<Value>,
    required: Option<Value>,
    pinned: Option<Value>,
    alignment: Option<Value>,
}

impl ColumnBase {
    pub fn new(label: Option<&str>) -> Self {
        Self {
            label: label.map(text_value),
            ..Default::default()
        }
    }

    /// The named width: "small", "medium" or "large".
    pub fn width(mut self, width: &str) -> Self {
        self.width = Some(width_value(width));
        self
    }

    /// A pixel width.
    pub fn width_px(mut self, pixels: i64) -> Self {
        self.width = Some(Value::from(pixels));
        self
    }

    pub fn help(mut self, help: &str) -> Self {
        self.help = Some(text_value(help));
        self
    }

    pub fn disabled(mut self, disabled: bool) -> Self {
        self.disabled = Some(Value::Bool(disabled));
        self
    }

    pub fn required(mut self, required: bool) -> Self {
        self.required = Some(Value::Bool(required));
        self
    }

    pub fn pinned(mut self, pinned: bool) -> Self {
        self.pinned = Some(Value::Bool(pinned));
        self
    }

    /// "left", "center" or "right".
    pub fn alignment(mut self, alignment: &str) -> Self {
        self.alignment = Some(text_value(alignment));
        self
    }
}

/// The plain column: label, width, help, disabled, required, pinned,
/// alignment — no type_config.
pub fn column(base: ColumnBase) -> ColumnConfig {
    ColumnConfig::from_base(base)
}

fn typed(kind: &str, base: ColumnBase) -> ColumnConfig {
    ColumnConfig::from_base(base).typed(kind)
}

macro_rules! column_helper {
    ($name:ident, $kind:literal) => {
        pub fn $name(base: ColumnBase) -> ColumnConfig {
            typed($kind, base)
        }
    };
}

column_helper!(checkbox_column, "checkbox");
column_helper!(json_column, "json");
column_helper!(image_column, "image");
column_helper!(audio_column, "audio");
column_helper!(video_column, "video");
column_helper!(list_column, "list");
column_helper!(markdown_column, "markdown");

/// TextColumn: default/max_chars/validate ride type_config.
pub fn text_column(base: ColumnBase, default: Option<&str>, max_chars: Option<i64>, validate: Option<&str>) -> ColumnConfig {
    let mut config = typed("text", base);
    config.default = default.map(text_value);
    if let Some(max_chars) = max_chars {
        config = config.set("max_chars", Value::from(max_chars));
    }
    if let Some(validate) = validate {
        config = config.set("validate", Value::String(validate.into()));
    }
    config
}

/// NumberColumn: min_value/max_value/format/step in that order.
pub fn number_column(base: ColumnBase, default: Option<Value>, format: Option<&str>, min_value: Option<Value>, max_value: Option<Value>, step: Option<Value>) -> ColumnConfig {
    let mut config = typed("number", base);
    config.default = default;
    if let Some(min) = min_value {
        config = config.set("min_value", min);
    }
    if let Some(max) = max_value {
        config = config.set("max_value", max);
    }
    if let Some(format) = format {
        config = config.set("format", Value::String(format.into()));
    }
    if let Some(step) = step {
        config = config.set("step", step);
    }
    config
}

/// SelectboxColumn: options as the raw labels.
pub fn selectbox_column(base: ColumnBase, default: Option<&str>, options: &[&str]) -> ColumnConfig {
    let mut config = typed("selectbox", base);
    config.default = default.map(text_value);
    config = config.set("options", Value::Array(options.iter().map(|option| Value::String((*option).into())).collect()));
    config
}

/// MultiselectColumn: options wrap as {"value": label}.
pub fn multiselect_column(base: ColumnBase, default: Option<Vec<&str>>, options: &[&str], accept_new_options: Option<bool>) -> ColumnConfig {
    let mut config = typed("multiselect", base);
    config.default = default.map(|items| Value::Array(items.into_iter().map(text_value).collect()));
    config = config.set("options", Value::Array(options.iter().map(|option| serde_json::json!({"value": option})).collect()));
    if let Some(accept) = accept_new_options {
        config = config.set("accept_new_options", Value::Bool(accept));
    }
    config
}

/// DateColumn: ISO dates, format/min/max/step in that order.
pub fn date_column(base: ColumnBase, default: Option<&str>, format: Option<&str>, min_value: Option<&str>, max_value: Option<&str>, step: Option<i64>) -> ColumnConfig {
    let mut config = typed("date", base);
    config.default = default.map(text_value);
    if let Some(format) = format {
        config = config.set("format", Value::String(format.into()));
    }
    if let Some(min) = min_value {
        config = config.set("min_value", Value::String(min.into()));
    }
    if let Some(max) = max_value {
        config = config.set("max_value", Value::String(max.into()));
    }
    if let Some(step) = step {
        config = config.set("step", Value::from(step));
    }
    config
}

/// DatetimeColumn: ISO datetimes, format/min/max/step/timezone.
pub fn datetime_column(base: ColumnBase, default: Option<&str>, format: Option<&str>, min_value: Option<&str>, max_value: Option<&str>, step: Option<Value>, timezone: Option<&str>) -> ColumnConfig {
    let mut config = typed("datetime", base);
    config.default = default.map(text_value);
    if let Some(format) = format {
        config = config.set("format", Value::String(format.into()));
    }
    if let Some(min) = min_value {
        config = config.set("min_value", Value::String(min.into()));
    }
    if let Some(max) = max_value {
        config = config.set("max_value", Value::String(max.into()));
    }
    if let Some(step) = step {
        config = config.set("step", step);
    }
    if let Some(timezone) = timezone {
        config = config.set("timezone", Value::String(timezone.into()));
    }
    config
}

/// TimeColumn: "HH:MM:SS" strings, format/min/max/step.
pub fn time_column(base: ColumnBase, default: Option<&str>, format: Option<&str>, min_value: Option<&str>, max_value: Option<&str>, step: Option<Value>) -> ColumnConfig {
    let mut config = typed("time", base);
    config.default = default.map(text_value);
    if let Some(format) = format {
        config = config.set("format", Value::String(format.into()));
    }
    if let Some(min) = min_value {
        config = config.set("min_value", Value::String(min.into()));
    }
    if let Some(max) = max_value {
        config = config.set("max_value", Value::String(max.into()));
    }
    if let Some(step) = step {
        config = config.set("step", step);
    }
    config
}

/// LinkColumn: url default, max_chars/validate/display_text.
pub fn link_column(base: ColumnBase, url: Option<&str>, max_chars: Option<i64>, validate: Option<&str>, display_text: Option<&str>) -> ColumnConfig {
    let mut config = typed("link", base);
    config.default = url.map(text_value);
    if let Some(max_chars) = max_chars {
        config = config.set("max_chars", Value::from(max_chars));
    }
    if let Some(validate) = validate {
        config = config.set("validate", Value::String(validate.into()));
    }
    if let Some(display) = display_text {
        config = config.set("display_text", Value::String(display.into()));
    }
    config
}

macro_rules! chart_column {
    ($name:ident, $kind:literal) => {
        /// The chart column: y_min/y_max/color.
        pub fn $name(base: ColumnBase, y_min: Option<Value>, y_max: Option<Value>, color: Option<&str>) -> ColumnConfig {
            let mut config = typed($kind, base);
            if let Some(min) = y_min {
                config = config.set("y_min", min);
            }
            if let Some(max) = y_max {
                config = config.set("y_max", max);
            }
            if let Some(color) = color {
                config = config.set("color", Value::String(color.into()));
            }
            config
        }
    };
}

chart_column!(area_chart_column, "area_chart");
chart_column!(bar_chart_column, "bar_chart");
chart_column!(line_chart_column, "line_chart");

/// ProgressColumn: format/min_value/max_value/step/color.
pub fn progress_column(base: ColumnBase, format: Option<&str>, min_value: Option<Value>, max_value: Option<Value>, step: Option<Value>, color: Option<&str>) -> ColumnConfig {
    let mut config = typed("progress", base);
    if let Some(format) = format {
        config = config.set("format", Value::String(format.into()));
    }
    if let Some(min) = min_value {
        config = config.set("min_value", min);
    }
    if let Some(max) = max_value {
        config = config.set("max_value", max);
    }
    if let Some(step) = step {
        config = config.set("step", step);
    }
    if let Some(color) = color {
        config = config.set("color", Value::String(color.into()));
    }
    config
}

/// ButtonColumn: always read-only (disabled), button_type rides type_config.
/// The key names the column's click widget on the dataframe proto
/// (button_click_widgets); it is never serialized into the columns JSON.
pub fn button_column(base: ColumnBase, button_type: Option<&str>, key: Option<&str>) -> ColumnConfig {
    let mut config = typed("button", base);
    config.disabled = Some(Value::Bool(true));
    if let Some(kind) = button_type {
        config = config.set("button_type", Value::String(kind.into()));
    }
    config.key = key.map(str::to_owned);
    config
}

/// A column-config mapping: ordered (column, config) pairs.
#[derive(Default)]
pub struct ColumnConfigs {
    entries: Vec<(String, ColumnConfig)>,
}

impl ColumnConfigs {
    pub fn new() -> Self {
        Self::default()
    }

    pub fn add(mut self, column: impl Into<String>, config: ColumnConfig) -> Self {
        self.entries.push((column.into(), config));
        self
    }

    pub fn is_empty(&self) -> bool {
        self.entries.is_empty()
    }

    /// The button columns as (column name, widget key) pairs, in mapping
    /// order — the entries that register one click widget each on the
    /// dataframe proto's button_click_widgets.
    pub(crate) fn button_columns(&self) -> Vec<(String, Option<String>)> {
        self.entries
            .iter()
            .filter(|(_, config)| config.type_config.as_ref().is_some_and(|typed| typed.get("type").is_some_and(Value::is_string) && typed["type"] == "button"))
            .map(|(column, config)| (column.clone(), config.key.clone()))
            .collect()
    }

    /// Serialize like the reference's _convert_column_config_to_json:
    /// the mapping as one JSON object (None values already dropped per
    /// column), ``json.dumps`` default separators.
    pub fn wire(&self) -> String {
        let mut out = Map::new();
        for (column, config) in &self.entries {
            out.insert(column.clone(), config.wire());
        }
        crate::pywire::py_dumps(&Value::Object(out))
    }
}
