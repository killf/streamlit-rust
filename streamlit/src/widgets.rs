//! Session-local input values and callback ordering. No process-global widget state.
use crate::proto::{WidgetState, widget_state};
use crate::{SessionState, Streamlit};
use chrono::{NaiveDate, NaiveDateTime, NaiveTime, Timelike};
use serde::Deserialize;
use serde_json::Value;
use std::collections::{HashMap, HashSet};
use std::sync::Arc;

/// A synchronous callback runs after all incoming values are applied and before main.
/// Captured Rust values replace Python's args/kwargs; the callback must be thread safe.
pub type WidgetCallback = Arc<dyn Fn(&Streamlit) + Send + Sync>;

/// The largest integer every f64 carries exactly. Both the numeric and the
/// temporal slider wires are f64 arrays; temporal values are integer epoch
/// microseconds, which stay inside this bound for roughly 1677..2262.
pub(crate) const JS_SAFE_INTEGER: f64 = 9_007_199_254_740_991.0;

/// 2000-01-01T00:00:00Z in microseconds: the anchor of time-of-day sliders,
/// measured on the pinned 1.66.1 reference wire.
pub(crate) const TIME_ANCHOR_MICROS: i64 = 946_684_800_000_000;

/// One temporal day/step in microseconds, as measured on the reference.
pub(crate) const DAY_MICROS: i64 = 86_400_000_000;

pub(crate) fn date_micros(date: NaiveDate) -> i64 {
    date.and_hms_opt(0, 0, 0).expect("midnight is valid for every date").and_utc().timestamp_micros()
}

pub(crate) fn time_micros(time: NaiveTime) -> i64 {
    let sub_second = (time.nanosecond() % 1_000_000_000) as i64 / 1_000;
    TIME_ANCHOR_MICROS + time.num_seconds_from_midnight() as i64 * 1_000_000 + sub_second
}

pub(crate) fn datetime_micros(value: NaiveDateTime) -> i64 {
    value.and_utc().timestamp_micros()
}

fn date_from_micros(micros: i64) -> Option<NaiveDate> {
    chrono::DateTime::from_timestamp_micros(micros).map(|value| value.date_naive())
}

fn time_from_micros(micros: i64) -> Option<NaiveTime> {
    let day = micros.checked_sub(TIME_ANCHOR_MICROS)?;
    if !(0..DAY_MICROS).contains(&day) {
        return None;
    }
    let seconds = (day / 1_000_000) as u32;
    let nanos = (day % 1_000_000 * 1_000) as u32;
    NaiveTime::from_num_seconds_from_midnight_opt(seconds, nanos)
}

fn datetime_from_micros(micros: i64) -> Option<NaiveDateTime> {
    chrono::DateTime::from_timestamp_micros(micros).map(|value| value.naive_utc())
}

/// The temporal slider kinds, measured on the pinned 1.66.1 wire: every value
/// is an integer number of epoch microseconds carried as a double. Naive
/// date-times encode as if UTC; a time-of-day encodes against the 2000-01-01
/// anchor above.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub(crate) enum TemporalKind {
    Datetime,
    Date,
    Time,
}

impl TemporalKind {
    /// The `Slider.DataType` enum value: DATETIME = 2, DATE = 3, TIME = 4.
    pub(crate) fn data_type(self) -> i32 {
        match self {
            Self::Datetime => 2,
            Self::Date => 3,
            Self::Time => 4,
        }
    }

    /// The typed JSON form (chrono serde strings) of one wire value.
    pub(crate) fn typed_value(self, micros: i64) -> Option<Value> {
        let value = match self {
            Self::Datetime => serde_json::to_value(datetime_from_micros(micros)?).ok()?,
            Self::Date => serde_json::to_value(date_from_micros(micros)?).ok()?,
            Self::Time => serde_json::to_value(time_from_micros(micros)?).ok()?,
        };
        Some(value)
    }

    /// The microseconds of one typed JSON value.
    pub(crate) fn micros(self, value: &Value) -> Option<i64> {
        match self {
            Self::Datetime => NaiveDateTime::deserialize(value).ok().map(datetime_micros),
            Self::Date => NaiveDate::deserialize(value).ok().map(date_micros),
            Self::Time => NaiveTime::deserialize(value).ok().map(time_micros),
        }
    }
}

#[derive(Debug, thiserror::Error)]
pub enum WidgetError {
    #[error("widget key is already used in this run: {0}")]
    DuplicateKey(String),
    #[error("identical widgets need distinct explicit keys: {0}")]
    DuplicateId(String),
    #[error("invalid widget value: {0}")]
    InvalidValue(String),
    #[error(transparent)]
    Serialization(#[from] serde_json::Error),
}

#[derive(Clone)]
pub(crate) enum Codec {
    Trigger,
    Bool,
    Text {
        max_chars: Option<usize>,
    },
    Select(Vec<(String, Value)>),
    /// Creation-mode selectbox: a known label decodes to its index, an
    /// unknown label passes through as its string (accept_new_options).
    SelectCreation(Vec<(String, Value)>),
    /// Radio option labels; the wire state is the selected option's text.
    Radio(Vec<String>),
    /// Multiselect options paired with their native values; the wire state is
    /// the selected option texts, in selection order.
    MultiSelect(Vec<(String, Value)>),
    /// Number bounds in wire units; the state is int_value or double_value
    /// according to the measured integer/float split.
    NumberInput {
        min: Option<f64>,
        max: Option<f64>,
        integer: bool,
    },
    Slider {
        min: f64,
        max: f64,
        count: usize,
        integer: bool,
    },
    TemporalSlider {
        min: f64,
        max: f64,
        count: usize,
        kind: TemporalKind,
    },
    Files {
        store: Arc<parking_lot::Mutex<crate::upload::UploadStore>>,
        multiple: bool,
    },
    /// The chat input's submitted value: the data string of the
    /// chat_input_value state, absent data meaning None (the trigger
    /// resets after the run, like the reference).
    ChatInput,
    /// The feedback string state: "" (the user cleared, so None) or the
    /// decimal index of the picked icon, within the style's icon count.
    Feedback {
        count: usize,
    },
    /// The pagination page, 1-indexed within `num_pages`.
    Pagination {
        num_pages: u32,
    },
    /// pills/segmented_control: option labels paired with their native
    /// values; the wire is the selected label strings (one at most in
    /// single-select mode, in selection order in multi-select).
    ButtonGroup {
        options: Vec<(String, Value)>,
        multi: bool,
    },
    /// The menu button's one-shot string trigger: the selected option's
    /// label, resetting to None after the run like button triggers.
    StringTrigger(Vec<String>),
    /// A dataframe button column's one-shot string trigger: the click state
    /// as one JSON object ({"row": index, "label": text}), resetting to None
    /// after the run like the reference's ButtonClickSerde.
    ButtonColumn,
    /// A bidi component's persistent state: the whole state object as one
    /// JSON string (json_value), like the reference's BidiComponentSerde.
    JsonValue,
    /// A bidi component's trigger aggregator: json_trigger_value carries the
    /// fired events as one JSON array string of {"event", "value"} payloads
    /// (the frontend accumulates them), resetting to null after the run like
    /// every reference trigger.
    JsonTrigger,
    /// date_input: ISO "YYYY-MM-DD" strings, one for a single date or two
    /// for a range; the value stays a string and the emitter parses it.
    DateInput {
        range: bool,
    },
    /// time_input: "HH:MM" for whole-minute steps, "HH:MM:SS" otherwise.
    TimeInput {
        step: i64,
    },
    /// datetime_input: ISO "YYYY-MM-DDTHH:MM" strings (the reference also
    /// accepts the legacy "YYYY/MM/DD, HH:MM" spelling on input).
    DateTimeInput,
}

impl Codec {
    /// The reference's ButtonColumnClickState shape: a non-negative row
    /// index and a text label.
    fn button_click_shape(value: &Value) -> bool {
        value.as_object().is_some_and(|click| click.get("row").is_some_and(Value::is_u64) && click.get("label").is_some_and(Value::is_string))
    }

    pub(crate) fn decode(&self, wire: &widget_state::Value) -> Option<Value> {
        match (self, wire) {
            (Self::Trigger, widget_state::Value::TriggerValue(value)) => Some((*value).into()),
            (Self::Bool, widget_state::Value::BoolValue(value)) => Some((*value).into()),
            (Self::Text { .. }, widget_state::Value::StringValue(value)) => Some(Value::String(value.clone())),
            (Self::Select(options), widget_state::Value::StringValue(label)) => options.iter().position(|(text, _)| text == label).map(Value::from),
            (Self::SelectCreation(options), widget_state::Value::StringValue(label)) => Some(match options.iter().position(|(text, _)| text == label) {
                Some(index) => Value::from(index),
                // A freshly typed value keeps its label as the native value.
                None => Value::String(label.clone()),
            }),
            (Self::Radio(options), widget_state::Value::StringValue(label)) => options.iter().position(|text| text == label).map(Value::from),
            (Self::MultiSelect(options), widget_state::Value::StringArrayValue(array)) => {
                let indices: Option<Vec<Value>> = array.data.iter().map(|label| options.iter().position(|(text, _)| text == label).map(Value::from)).collect();
                indices.map(Value::Array)
            }
            (Self::NumberInput { integer, .. }, widget_state::Value::IntValue(value)) if *integer => Some(Value::from(*value)),
            (Self::NumberInput { integer, .. }, widget_state::Value::DoubleValue(value)) if !*integer => Some(Value::from(*value)),
            (Self::Files { store, multiple }, widget_state::Value::FileUploaderStateValue(state)) => {
                let store = store.lock();
                let ids: Vec<Value> = state.uploaded_file_info.iter().filter(|file| store.get(&file.file_id).is_some()).map(|file| Value::String(file.file_id.clone())).collect();
                if !multiple && ids.len() > 1 {
                    return None;
                }
                Some(Value::Array(ids))
            }
            (Self::ChatInput, widget_state::Value::ChatInputValue(value)) => Some(match value.data.as_deref() {
                Some("") | None => Value::Null,
                Some(data) => Value::String(data.to_owned()),
            }),
            (Self::Feedback { .. }, widget_state::Value::StringValue(value)) => Some(if value.is_empty() { Value::Null } else { value.parse::<u64>().ok().map(Value::from)? }),
            (Self::Pagination { num_pages }, widget_state::Value::IntValue(value)) => {
                let num_pages = *num_pages as u64;
                (*value >= 1 && *value as u64 <= num_pages).then(|| (*value as u64).into())
            }
            (Self::ButtonGroup { options, multi }, widget_state::Value::StringArrayValue(array)) => {
                let indices: Option<Vec<Value>> = array.data.iter().map(|label| options.iter().position(|(text, _)| text == label).map(Value::from)).collect();
                let indices = indices?;
                if *multi {
                    Some(Value::Array(indices))
                } else if indices.len() <= 1 {
                    Some(indices.into_iter().next().unwrap_or(Value::Null))
                } else {
                    None
                }
            }
            (Self::StringTrigger(options), widget_state::Value::StringTriggerValue(trigger)) => trigger.data.as_deref().and_then(|label| options.iter().position(|option| option == label).map(Value::from)),
            (Self::ButtonColumn, widget_state::Value::StringTriggerValue(trigger)) => Some(match trigger.data.as_deref() {
                None | Some("") => Value::Null,
                Some(data) => serde_json::from_str::<Value>(data).ok().filter(Self::button_click_shape)?,
            }),
            (Self::JsonValue, widget_state::Value::JsonValue(text)) => serde_json::from_str::<Value>(text).ok(),
            (Self::JsonTrigger, widget_state::Value::JsonTriggerValue(text)) => Some(match serde_json::from_str::<Value>(text) {
                Ok(Value::Array(list)) => Value::Array(list),
                Ok(Value::Null) => Value::Null,
                Ok(single) => Value::Array(vec![single]),
                // The reference's handle_deserialize keeps an unparsable
                // payload as its raw string, list-normalized.
                Err(_) => Value::Array(vec![Value::String(text.clone())]),
            }),
            (Self::DateInput { range }, widget_state::Value::StringArrayValue(array)) => {
                let dates: Option<Vec<Value>> = array.data.iter().map(|text| chrono::NaiveDate::parse_from_str(text, "%Y-%m-%d").ok().map(|_| Value::String(text.clone()))).collect();
                let dates = dates?;
                if *range {
                    (dates.len() == 2).then(|| Value::Array(dates))
                } else if dates.len() <= 1 {
                    Some(dates.into_iter().next().unwrap_or(Value::Null))
                } else {
                    None
                }
            }
            (Self::TimeInput { step }, widget_state::Value::StringValue(text)) => {
                let format = if step % 60 != 0 { "%H:%M:%S" } else { "%H:%M" };
                if text.is_empty() {
                    return Some(Value::Null);
                }
                chrono::NaiveTime::parse_from_str(text, format).ok().map(|_| Value::String(text.clone()))
            }
            (Self::DateTimeInput, widget_state::Value::StringArrayValue(array)) => {
                // One entry, minute precision; an empty array is the cleared
                // picker. The ISO spelling is canonical; the legacy
                // "YYYY/MM/DD, HH:MM" form is accepted and re-normalized.
                let parse = |text: &str| {
                    chrono::NaiveDateTime::parse_from_str(text, "%Y-%m-%dT%H:%M")
                        .or_else(|_| chrono::NaiveDateTime::parse_from_str(text, "%Y/%m/%d, %H:%M"))
                        .map(|moment| moment.format("%Y-%m-%dT%H:%M").to_string())
                };
                match array.data.first() {
                    None => Some(Value::Null),
                    Some(text) => parse(text).ok().map(Value::String),
                }
            }
            (Codec::Slider { count, integer, .. }, widget_state::Value::DoubleArrayValue(array)) if array.data.len() == *count => {
                let values: Vec<Value> = array.data.iter().map(|value| if *integer { Value::from(*value as i64) } else { Value::from(*value) }).collect();
                let result = if *count == 1 { values[0].clone() } else { Value::Array(values) };
                // Validate the wire numbers before converting them to integers.
                if array.data.iter().any(|value| !value.is_finite() || (*integer && value.fract() != 0.0)) {
                    return None;
                }
                self.valid(&result).then_some(result)
            }
            (Codec::TemporalSlider { count, kind, .. }, widget_state::Value::DoubleArrayValue(array)) if array.data.len() == *count => {
                // Temporal wires carry integer epoch microseconds as doubles.
                if array.data.iter().any(|value| !value.is_finite() || value.fract() != 0.0 || value.abs() > JS_SAFE_INTEGER) {
                    return None;
                }
                let mut values = Vec::with_capacity(*count);
                for value in &array.data {
                    values.push(kind.typed_value(*value as i64)?);
                }
                let result = if *count == 1 { values[0].clone() } else { Value::Array(values) };
                self.valid(&result).then_some(result)
            }
            _ => None,
        }
    }

    pub(crate) fn valid(&self, value: &Value) -> bool {
        match self {
            Self::Trigger | Self::Bool => value.is_boolean(),
            Self::ChatInput => value.is_null() || value.is_string(),
            Self::Feedback { count } => value.is_null() || value.as_u64().is_some_and(|index| index < *count as u64),
            Self::Pagination { num_pages } => value.as_u64().is_some_and(|page| (1..=*num_pages as u64).contains(&page)),
            Self::ButtonGroup { options, multi } => {
                let within = |index: &Value| index.as_u64().is_some_and(|index| index < options.len() as u64);
                if *multi { value.as_array().is_some_and(|indices| indices.iter().all(within)) } else { value.is_null() || within(value) }
            }
            Self::StringTrigger(options) => value.is_null() || value.as_u64().is_some_and(|index| index < options.len() as u64),
            Self::ButtonColumn => value.is_null() || Self::button_click_shape(value),
            Self::JsonValue => true,
            Self::JsonTrigger => value.is_null() || value.is_array(),
            Self::DateInput { range } => {
                let iso = |item: &Value| item.as_str().is_some_and(|text| chrono::NaiveDate::parse_from_str(text, "%Y-%m-%d").is_ok());
                if *range {
                    value.as_array().is_some_and(|dates| dates.len() == 2 && dates.iter().all(iso))
                } else {
                    value.is_null() || iso(value)
                }
            }
            Self::TimeInput { step } => {
                let format = if step % 60 != 0 { "%H:%M:%S" } else { "%H:%M" };
                value.is_null() || value.as_str().is_some_and(|text| chrono::NaiveTime::parse_from_str(text, format).is_ok())
            }
            Self::DateTimeInput => {
                let iso = |text: &str| chrono::NaiveDateTime::parse_from_str(text, "%Y-%m-%dT%H:%M").is_ok();
                value.is_null() || value.as_str().is_some_and(iso)
            }
            Self::Text { max_chars } => value.is_null() || value.as_str().is_some_and(|text| max_chars.is_none_or(|limit| text.chars().count() <= limit)),
            Self::Select(options) => value.is_null() || value.as_u64().is_some_and(|index| index < options.len() as u64),
            Self::SelectCreation(options) => value.is_null() || value.is_string() || value.as_u64().is_some_and(|index| index < options.len() as u64),
            Self::Radio(options) => value.is_null() || value.as_u64().is_some_and(|index| index < options.len() as u64),
            Self::MultiSelect(options) => value.as_array().is_some_and(|indices| indices.iter().all(|index| index.as_u64().is_some_and(|i| i < options.len() as u64))),
            Self::NumberInput { min, max, integer } => value
                .as_f64()
                .is_some_and(|number| number.is_finite() && (!*integer || number.fract() == 0.0) && min.is_none_or(|bound| number >= bound) && max.is_none_or(|bound| number <= bound)),
            Self::Files { multiple, .. } => value.as_array().is_some_and(|ids| (*multiple || ids.len() <= 1) && ids.iter().all(Value::is_string)),
            Codec::Slider { min, max, count, integer } => {
                let values = match value {
                    Value::Array(values) if *count == 2 => values.clone(),
                    _ if *count == 1 => vec![value.clone()],
                    _ => return false,
                };
                values.len() == *count && values.iter().all(|value| value.as_f64().is_some_and(|v| v.is_finite() && v >= *min && v <= *max && (!*integer || v.fract() == 0.0))) && (*count == 1 || values[0].as_f64() <= values[1].as_f64())
            }
            Codec::TemporalSlider { min, max, count, kind } => {
                let values = match value {
                    Value::Array(values) if *count == 2 => values.clone(),
                    _ if *count == 1 => vec![value.clone()],
                    _ => return false,
                };
                let Some(micros) = values.iter().map(|value| kind.micros(value)).collect::<Option<Vec<i64>>>() else {
                    return false;
                };
                micros.len() == *count && micros.iter().all(|value| (*value as f64) >= *min && (*value as f64) <= *max) && (*count == 1 || micros[0] <= micros[1])
            }
        }
    }

    // Selection presence is internal state, distinct from the selected native
    // value: Some(index) may legitimately project to JSON null in session state.
    fn session_value(&self, value: &Value) -> Value {
        match self {
            Self::Select(options) => value.as_u64().and_then(|index| options.get(index as usize)).map(|(_, native)| native.clone()).unwrap_or(Value::Null),
            Self::SelectCreation(options) => match value.as_u64().and_then(|index| options.get(index as usize)).map(|(_, native)| native.clone()) {
                Some(native) => native,
                // A freshly typed label already is the native value.
                None => value.clone(),
            },
            Self::Radio(options) => value.as_u64().and_then(|index| options.get(index as usize)).cloned().map(Value::String).unwrap_or(Value::Null),
            Self::MultiSelect(options) => Value::Array(
                value
                    .as_array()
                    .map(|indices| indices.iter().filter_map(|index| index.as_u64().and_then(|i| options.get(i as usize)).map(|(_, native)| native.clone())).collect())
                    .unwrap_or_default(),
            ),
            Self::ButtonGroup { options, multi } if *multi => Value::Array(
                value
                    .as_array()
                    .map(|indices| indices.iter().filter_map(|index| index.as_u64().and_then(|i| options.get(i as usize)).map(|(_, native)| native.clone())).collect())
                    .unwrap_or_default(),
            ),
            Self::ButtonGroup { options, multi } => {
                debug_assert!(!*multi);
                value.as_u64().and_then(|index| options.get(index as usize)).map(|(_, native)| native.clone()).unwrap_or(Value::Null)
            }
            Self::StringTrigger(options) => value.as_u64().and_then(|index| options.get(index as usize)).cloned().map(Value::String).unwrap_or(Value::Null),
            _ => value.clone(),
        }
    }

    fn read_session_value(&self, native: &Value, previous: Option<&Record>) -> Result<Value, WidgetError> {
        if let Self::Select(options) = self {
            if let Some(previous) = previous
                && previous.codec.session_value(&previous.value) == *native
            {
                if previous.value.is_null() {
                    return Ok(Value::Null);
                }
                // Preserve the selected occurrence if its native value is
                // unchanged; otherwise remap after keyed options are reordered.
                if let Some(index) = previous.value.as_u64()
                    && options.get(index as usize).is_some_and(|(_, value)| value == native)
                {
                    return Ok(index.into());
                }
            }
            return options
                .iter()
                .position(|(_, value)| value == native)
                .map(Value::from)
                .or_else(|| native.is_null().then_some(Value::Null))
                .ok_or_else(|| WidgetError::InvalidValue("session value is absent from selectbox options".into()));
        }
        if let Self::Radio(options) = self {
            return native
                .as_str()
                .and_then(|text| options.iter().position(|option| option == text))
                .map(Value::from)
                .or_else(|| native.is_null().then_some(Value::Null))
                .ok_or_else(|| WidgetError::InvalidValue("session value is absent from radio options".into()));
        }
        if let Self::MultiSelect(options) = self {
            let Some(items) = native.as_array() else {
                return Err(WidgetError::InvalidValue("multiselect session value must be an array".into()));
            };
            let mut indices = Vec::with_capacity(items.len());
            for item in items {
                let index = options.iter().position(|(_, value)| value == item).ok_or_else(|| WidgetError::InvalidValue("session value is absent from multiselect options".into()))?;
                indices.push(Value::from(index));
            }
            return Ok(Value::Array(indices));
        }
        if let Self::ButtonGroup { options, multi } = self {
            if *multi {
                let Some(items) = native.as_array() else {
                    return Err(WidgetError::InvalidValue("multi-select session value must be an array".into()));
                };
                let mut indices = Vec::with_capacity(items.len());
                for item in items {
                    let index = options.iter().position(|(_, value)| value == item).ok_or_else(|| WidgetError::InvalidValue("session value is absent from options".into()))?;
                    indices.push(Value::from(index));
                }
                return Ok(Value::Array(indices));
            }
            return native
                .as_str()
                .and_then(|text| options.iter().position(|(label, _)| label == text))
                .map(Value::from)
                .or_else(|| native.is_null().then_some(Value::Null))
                .ok_or_else(|| WidgetError::InvalidValue("session value is absent from options".into()));
        }
        if let Self::StringTrigger(options) = self {
            return native
                .as_str()
                .and_then(|text| options.iter().position(|option| option == text))
                .map(Value::from)
                .or_else(|| native.is_null().then_some(Value::Null))
                .ok_or_else(|| WidgetError::InvalidValue("session value is absent from options".into()));
        }
        Ok(native.clone())
    }
}

/// The value a one-shot widget resets to between runs, or None for widgets
/// that keep their state: buttons and link/download triggers to false, the
/// chat input to its empty value, the menu button to no selection.
fn one_shot_reset(codec: &Codec) -> Option<Value> {
    match codec {
        Codec::Trigger => Some(Value::Bool(false)),
        Codec::ChatInput | Codec::StringTrigger(_) | Codec::ButtonColumn | Codec::JsonTrigger => Some(Value::Null),
        _ => None,
    }
}

#[derive(Clone)]
struct Record {
    key: Option<String>,
    value: Value,
    codec: Codec,
    callback: Option<WidgetCallback>,
}

#[derive(Clone, Default)]
pub(crate) struct WidgetRegistry {
    records: HashMap<String, Record>,
    seen: HashSet<String>,
    keys: HashSet<String>,
    active: bool,
    dirty_keys: HashSet<String>,
    /// Incoming widget states whose widget is not registered yet this run;
    /// the reference applies the browser's state at widget creation, so
    /// these land when the widget registers (for example after another
    /// page left it unrendered).
    pending: Vec<crate::proto::WidgetState>,
}

pub(crate) struct WidgetSpec<'a> {
    pub(crate) kind: &'a str,
    pub(crate) key: Option<&'a str>,
    pub(crate) identity: &'a str,
    pub(crate) default: Value,
    pub(crate) codec: Codec,
    pub(crate) callback: Option<WidgetCallback>,
}

impl WidgetRegistry {
    pub(crate) fn mark_write(&mut self, key: &str) {
        self.dirty_keys.insert(key.into());
    }
    pub(crate) fn check_write(&self, key: &str) -> serde_json::Result<()> {
        use serde::ser::Error;
        if self.records.values().any(|record| record.key.as_deref() == Some(key) && matches!(record.codec, Codec::Trigger | Codec::Files { .. })) {
            return Err(serde_json::Error::custom("button and uploader keys are read-only"));
        }
        if self.active && self.keys.contains(key) {
            return Err(serde_json::Error::custom("cannot modify a widget key after instantiation in this run"));
        }
        Ok(())
    }
}

impl SessionState {
    pub(crate) fn form_checkpoint(&self) -> (WidgetRegistry, HashMap<String, Value>) {
        let registry = self.widgets.lock();
        (registry.clone(), self.values.lock().clone())
    }

    pub(crate) fn rollback_form(&self, checkpoint: (WidgetRegistry, HashMap<String, Value>)) {
        let mut registry = self.widgets.lock();
        let mut values = self.values.lock();
        // Only restore widget-associated values; unrelated application writes
        // in the user's fallible closure retain their ordinary semantics.
        for key in registry.records.values().filter_map(|record| record.key.as_ref()) {
            if let Some(value) = checkpoint.1.get(key) {
                values.insert(key.clone(), value.clone());
            } else {
                values.remove(key);
            }
        }
        *registry = checkpoint.0;
    }

    pub(crate) fn begin_widgets(&self, incoming: Vec<WidgetState>) -> Vec<WidgetCallback> {
        let mut registry = self.widgets.lock();
        registry.active = true;
        registry.seen.clear();
        registry.keys.clear();
        registry.pending.clear();
        let mut values = self.values.lock();
        for record in registry.records.values_mut() {
            // Trigger widgets are one-shot: buttons reset to false, the chat
            // input to its empty (null) value, the menu button to null.
            if let Some(reset) = one_shot_reset(&record.codec) {
                record.value = reset.clone();
                if let Some(key) = &record.key {
                    values.insert(key.clone(), reset);
                }
            }
        }
        let mut callbacks = Vec::new();
        let mut received = HashSet::new();
        // Validate the whole recognized batch before applying any field or
        // scheduling a callback. Invalid text must never reach submit code.
        if incoming.iter().any(|widget| {
            registry
                .records
                .get(&widget.id)
                .is_some_and(|record| widget.value.as_ref().and_then(|wire| record.codec.decode(wire)).is_none_or(|value| !record.codec.valid(&value)))
        }) {
            return callbacks;
        }
        for widget in incoming {
            if !received.insert(widget.id.clone()) {
                continue;
            }
            if !registry.records.contains_key(&widget.id) {
                // Applied at registration, like the reference's lazy
                // widget-state application.
                registry.pending.push(widget);
                continue;
            }
            let Some(record) = registry.records.get_mut(&widget.id) else { continue };
            let Some(value) = widget.value.as_ref().and_then(|wire| record.codec.decode(wire)) else { continue };
            let changed = record.value != value;
            record.value = value.clone();
            if let Some(key) = &record.key {
                values.insert(key.clone(), record.codec.session_value(&value));
            }
            if changed && let Some(callback) = &record.callback {
                callbacks.push(callback.clone());
            }
        }
        callbacks
    }

    pub(crate) fn register_widget<T>(&self, spec: WidgetSpec<'_>, resolve: impl Fn(&Value) -> Result<T, WidgetError>) -> Result<(String, T, bool), WidgetError> {
        let WidgetSpec { kind, key, .. } = spec;
        let identity_fields = serde_json::to_string(&(kind, spec.identity, key))?;
        let id = format!("$$ID-{}-{}", crate::utils::hash::hash(&identity_fields), key.unwrap_or("None"));
        self.register_widget_with_id(spec, &id, resolve)
    }

    /// Registration under an externally derived id — the bidi component's
    /// trigger aggregator ($$STREAMLIT_INTERNAL_KEY_<widget-id>__events),
    /// whose id the frontend recomputes from the state widget's id.
    pub(crate) fn register_widget_with_id<T>(&self, spec: WidgetSpec<'_>, id: &str, resolve: impl Fn(&Value) -> Result<T, WidgetError>) -> Result<(String, T, bool), WidgetError> {
        let WidgetSpec {
            kind,
            key,
            identity: _,
            default,
            codec,
            callback,
        } = spec;
        let id = id.to_owned();
        let mut registry = self.widgets.lock();
        if let Some(key) = key
            && registry.keys.contains(key)
        {
            return Err(WidgetError::DuplicateKey(key.into()));
        }
        if registry.seen.contains(&id) {
            return Err(WidgetError::DuplicateId(id));
        }
        let mut values = self.values.lock();
        if matches!(codec, Codec::Trigger | Codec::Files { .. } | Codec::ChatInput | Codec::StringTrigger(_) | Codec::ButtonColumn) && key.is_some_and(|key| values.contains_key(key)) && !registry.records.contains_key(&id) {
            return Err(WidgetError::InvalidValue("button, chat input, menu button and uploader state cannot be preseeded".into()));
        }
        // A constraint-dependent identity change resets the old widget binding.
        let changed_identity = key.is_some_and(|key| registry.records.iter().any(|(old_id, record)| old_id != &id && record.key.as_deref() == Some(key)));
        // A state the browser sent while this widget was not registered
        // (for example on a run that rendered another page) applies here,
        // exactly like begin_widgets would have applied it to the record.
        // on_change callbacks of these late applications do not run.
        let pending_value = registry
            .pending
            .iter()
            .position(|state| state.id == id)
            .map(|position| registry.pending.remove(position))
            .and_then(|state| state.value.as_ref().and_then(|wire| codec.decode(wire)))
            .filter(|applied| codec.valid(applied));
        let base_value = if changed_identity {
            default
        } else if one_shot_reset(&codec).is_some() {
            registry.records.get(&id).map(|record| record.value.clone()).unwrap_or(default)
        } else {
            if let Some(key) = key
                && let Some(native) = values.get(key)
            {
                codec.read_session_value(native, if registry.dirty_keys.contains(key) { None } else { registry.records.get(&id) })?
            } else {
                registry.records.get(&id).map(|record| record.value.clone()).unwrap_or(default)
            }
        };
        let value = pending_value.unwrap_or(base_value);
        if !codec.valid(&value) {
            return Err(WidgetError::InvalidValue(format!("value does not match {kind}")));
        }
        // Resolve every fallible native conversion before committing a key,
        // record or value. Resolvers here only convert built-in scalar/index
        // types; user callbacks and option cloning never run under these locks.
        let resolved = resolve(&value)?;
        let set_value = key.is_some_and(|key| registry.dirty_keys.contains(key));
        if let Some(key) = key {
            values.insert(key.into(), codec.session_value(&value));
            registry.keys.insert(key.into());
            registry.dirty_keys.remove(key);
        }
        registry.seen.insert(id.clone());
        registry.active = true;
        registry.records.insert(
            id.clone(),
            Record {
                key: key.map(str::to_owned),
                value: value.clone(),
                codec,
                callback,
            },
        );
        Ok((id, resolved, set_value))
    }

    pub(crate) fn finish_widgets(&self) {
        let mut registry = self.widgets.lock();
        let mut values = self.values.lock();
        let seen = registry.seen.clone();
        let live_keys = registry.keys.clone();
        registry.records.retain(|id, record| {
            if !seen.contains(id) {
                if let Some(key) = &record.key
                    && !live_keys.contains(key)
                {
                    values.remove(key);
                }
                return false;
            }
            if let Some(reset) = one_shot_reset(&record.codec) {
                record.value = reset.clone();
                if let Some(key) = &record.key {
                    values.insert(key.clone(), reset);
                }
            }
            true
        });
        registry.active = false;
        registry.dirty_keys.clear();
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn removed_upload_cannot_be_rebound_by_resending_old_file_state() -> anyhow::Result<()> {
        let state = SessionState::default();
        state.uploads.lock().insert("removed".into(), "old.csv".into(), Some("text/csv".into()), vec![1, 2, 3]);
        let retained = state.uploads.lock().get("removed").ok_or_else(|| anyhow::anyhow!("test upload must be retained before removal"))?;
        let codec = Codec::Files { store: state.uploads.clone(), multiple: false };
        let old_wire = widget_state::Value::FileUploaderStateValue(crate::proto::FileUploaderState {
            uploaded_file_info: vec![crate::proto::UploadedFileInfo { file_id: "removed".into(), ..Default::default() }],
        });
        assert_eq!(codec.decode(&old_wire), Some(serde_json::json!(["removed"])));
        assert!(state.uploads.lock().remove("removed"));
        assert_eq!(codec.decode(&old_wire), Some(serde_json::json!([])));
        assert!(!state.uploads.lock().remove("removed"));
        assert_eq!(retained.as_bytes(), &[1, 2, 3]);

        Ok(())
    }

    #[test]
    fn malformed_numeric_payloads_do_not_mutate_values_or_schedule_callbacks() -> anyhow::Result<()> {
        let state = SessionState::default();
        state.begin_widgets(vec![]);
        let callback: WidgetCallback = Arc::new(|_| panic!("invalid input must not schedule a callback"));
        let (id, _, _) = state.register_widget(
            WidgetSpec {
                kind: "slider",
                key: Some("range"),
                identity: "range",
                default: serde_json::json!([2, 8]),
                codec: Codec::Slider { min: 0.0, max: 10.0, count: 2, integer: true },
                callback: Some(callback),
            },
            |value| Ok(value.clone()),
        )?;
        state.finish_widgets();
        // These are native decoder robustness tests, not claims about Python's
        // error handling for fabricated client payloads.
        let bad = [vec![1.0], vec![2.0, 3.0, 4.0], vec![8.0, 2.0], vec![-1.0, 8.0], vec![2.5, 8.0], vec![f64::NAN, 8.0], vec![2.0, f64::INFINITY]];
        for data in bad {
            let callbacks = state.begin_widgets(vec![WidgetState {
                id: id.clone(),
                value: Some(widget_state::Value::DoubleArrayValue(crate::proto::DoubleArray { data })),
            }]);
            assert!(callbacks.is_empty());
            assert_eq!(state.get::<[i64; 2]>("range")?, Some([2, 8]));
        }
        let callbacks = state.begin_widgets(vec![WidgetState {
            id,
            value: Some(widget_state::Value::BoolValue(true)),
        }]);
        assert!(callbacks.is_empty());
        assert_eq!(state.get::<[i64; 2]>("range")?, Some([2, 8]));

        Ok(())
    }

    #[test]
    fn temporal_codec_decodes_measured_micros_and_rejects_fabricated_payloads() {
        let kind = TemporalKind::Time;
        let codec = Codec::TemporalSlider {
            min: TIME_ANCHOR_MICROS as f64,
            max: (TIME_ANCHOR_MICROS + DAY_MICROS - 1) as f64,
            count: 1,
            kind,
        };
        // The reference End key: 23:45 on the 15-minute grid.
        let wire = widget_state::Value::DoubleArrayValue(crate::proto::DoubleArray { data: vec![946770300000000.0] });
        assert_eq!(codec.decode(&wire), Some(serde_json::json!("23:45:00")));
        // Microseconds round-trip through the typed JSON form.
        let wire = widget_state::Value::DoubleArrayValue(crate::proto::DoubleArray { data: vec![946729807123456.0] });
        assert_eq!(codec.decode(&wire), Some(serde_json::json!("12:30:07.123456")));
        // Fractional microseconds, off-grid times and wrong counts never decode.
        for data in [vec![946729807123456.5], vec![1710460800000000.0], vec![], vec![946684800000000.0, 946770300000000.0]] {
            let wire = widget_state::Value::DoubleArrayValue(crate::proto::DoubleArray { data });
            assert_eq!(codec.decode(&wire), None, "fabricated temporal payload must not decode");
        }
        // Typed JSON values validate against the same bounds; a reversed pair fails.
        let codec = Codec::TemporalSlider {
            min: 1709251200000000.0,
            max: 1711670400000000.0,
            count: 2,
            kind: TemporalKind::Date,
        };
        assert!(codec.valid(&serde_json::json!(["2024-03-10", "2024-03-20"])));
        assert!(!codec.valid(&serde_json::json!(["2024-03-20", "2024-03-10"])));
        assert!(!codec.valid(&serde_json::json!(["2024-04-01", "2024-04-02"])));
        assert!(!codec.valid(&serde_json::json!("2024-03-15")));
    }
}
