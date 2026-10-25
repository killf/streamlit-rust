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
}

impl Codec {
    fn decode(&self, wire: &widget_state::Value) -> Option<Value> {
        match (self, wire) {
            (Self::Trigger, widget_state::Value::TriggerValue(value)) => Some((*value).into()),
            (Self::Bool, widget_state::Value::BoolValue(value)) => Some((*value).into()),
            (Self::Text { .. }, widget_state::Value::StringValue(value)) => Some(Value::String(value.clone())),
            (Self::Select(options), widget_state::Value::StringValue(label)) => options.iter().position(|(text, _)| text == label).map(Value::from),
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
            Self::Text { max_chars } => value.is_null() || value.as_str().is_some_and(|text| max_chars.is_none_or(|limit| text.chars().count() <= limit)),
            Self::Select(options) => value.is_null() || value.as_u64().is_some_and(|index| index < options.len() as u64),
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
            Self::Radio(options) => value.as_u64().and_then(|index| options.get(index as usize)).cloned().map(Value::String).unwrap_or(Value::Null),
            Self::MultiSelect(options) => Value::Array(
                value
                    .as_array()
                    .map(|indices| indices.iter().filter_map(|index| index.as_u64().and_then(|i| options.get(i as usize)).map(|(_, native)| native.clone())).collect())
                    .unwrap_or_default(),
            ),
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
        Ok(native.clone())
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
        let mut values = self.values.lock();
        for record in registry.records.values_mut() {
            if matches!(record.codec, Codec::Trigger) {
                record.value = false.into();
                if let Some(key) = &record.key {
                    values.insert(key.clone(), false.into());
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
        let WidgetSpec { kind, key, identity, default, codec, callback } = spec;
        let identity_fields = serde_json::to_string(&(kind, identity, key))?;
        let id = format!("$$ID-{}-{}", crate::utils::hash::hash(&identity_fields), key.unwrap_or("None"));
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
        if matches!(codec, Codec::Trigger | Codec::Files { .. }) && key.is_some_and(|key| values.contains_key(key)) && !registry.records.contains_key(&id) {
            return Err(WidgetError::InvalidValue("button and uploader state cannot be preseeded".into()));
        }
        // A constraint-dependent identity change resets the old widget binding.
        let changed_identity = key.is_some_and(|key| registry.records.iter().any(|(old_id, record)| old_id != &id && record.key.as_deref() == Some(key)));
        let value = if changed_identity {
            default
        } else if matches!(codec, Codec::Trigger) {
            registry.records.get(&id).map(|record| record.value.clone()).unwrap_or(default)
        } else {
            if let Some(native) = key.and_then(|key| values.get(key)) {
                codec.read_session_value(native, if registry.dirty_keys.contains(key.unwrap()) { None } else { registry.records.get(&id) })?
            } else {
                registry.records.get(&id).map(|record| record.value.clone()).unwrap_or(default)
            }
        };
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
            if matches!(record.codec, Codec::Trigger) {
                record.value = false.into();
                if let Some(key) = &record.key {
                    values.insert(key.clone(), false.into());
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
    fn removed_upload_cannot_be_rebound_by_resending_old_file_state() {
        let state = SessionState::default();
        state.uploads.lock().insert("removed".into(), "old.csv".into(), Some("text/csv".into()), vec![1, 2, 3]);
        let retained = state.uploads.lock().get("removed").unwrap();
        let codec = Codec::Files { store: state.uploads.clone(), multiple: false };
        let old_wire = widget_state::Value::FileUploaderStateValue(crate::proto::FileUploaderState {
            uploaded_file_info: vec![crate::proto::UploadedFileInfo { file_id: "removed".into(), ..Default::default() }],
        });
        assert_eq!(codec.decode(&old_wire), Some(serde_json::json!(["removed"])));
        assert!(state.uploads.lock().remove("removed"));
        assert_eq!(codec.decode(&old_wire), Some(serde_json::json!([])));
        assert!(!state.uploads.lock().remove("removed"));
        assert_eq!(retained.as_bytes(), &[1, 2, 3]);
    }

    #[test]
    fn malformed_numeric_payloads_do_not_mutate_values_or_schedule_callbacks() {
        let state = SessionState::default();
        state.begin_widgets(vec![]);
        let callback: WidgetCallback = Arc::new(|_| panic!("invalid input must not schedule a callback"));
        let (id, _, _) = state
            .register_widget(
                WidgetSpec {
                    kind: "slider",
                    key: Some("range"),
                    identity: "range",
                    default: serde_json::json!([2, 8]),
                    codec: Codec::Slider { min: 0.0, max: 10.0, count: 2, integer: true },
                    callback: Some(callback),
                },
                |value| Ok(value.clone()),
            )
            .unwrap();
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
            assert_eq!(state.get::<[i64; 2]>("range").unwrap(), Some([2, 8]));
        }
        let callbacks = state.begin_widgets(vec![WidgetState {
            id,
            value: Some(widget_state::Value::BoolValue(true)),
        }]);
        assert!(callbacks.is_empty());
        assert_eq!(state.get::<[i64; 2]>("range").unwrap(), Some([2, 8]));
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
