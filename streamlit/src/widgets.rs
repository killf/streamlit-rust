//! Session-local input values and callback ordering. No process-global widget state.
use crate::proto::{WidgetState, widget_state};
use crate::{SessionState, Streamlit};
use serde_json::Value;
use std::collections::{HashMap, HashSet};
use std::sync::Arc;

/// A synchronous callback runs after all incoming values are applied and before main.
/// Captured Rust values replace Python's args/kwargs; the callback must be thread safe.
pub type WidgetCallback = Arc<dyn Fn(&Streamlit) + Send + Sync>;

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
    Select(Vec<(String, Value)>),
    Slider { min: f64, max: f64, count: usize, integer: bool },
    Files { store: Arc<parking_lot::Mutex<crate::upload::UploadStore>>, multiple: bool },
}

impl Codec {
    fn decode(&self, wire: &widget_state::Value) -> Option<Value> {
        match (self, wire) {
            (Self::Trigger, widget_state::Value::TriggerValue(value)) => Some((*value).into()),
            (Self::Bool, widget_state::Value::BoolValue(value)) => Some((*value).into()),
            (Self::Select(options), widget_state::Value::StringValue(label)) => options.iter().position(|(text, _)| text == label).map(Value::from),
            (Self::Files { store, multiple }, widget_state::Value::FileUploaderStateValue(state)) => {
                let store = store.lock();
                let ids: Vec<Value> = state.uploaded_file_info.iter().filter(|file| store.get(&file.file_id).is_some()).map(|file| Value::String(file.file_id.clone())).collect();
                if !multiple && ids.len() > 1 {
                    return None;
                }
                Some(Value::Array(ids))
            }
            (Self::Slider { count, integer, .. }, widget_state::Value::DoubleArrayValue(array)) if array.data.len() == *count => {
                let values: Vec<Value> = array.data.iter().map(|value| if *integer { Value::from(*value as i64) } else { Value::from(*value) }).collect();
                let result = if *count == 1 { values[0].clone() } else { Value::Array(values) };
                // Validate the wire numbers before converting them to integers.
                if array.data.iter().any(|value| !value.is_finite() || (*integer && value.fract() != 0.0)) {
                    return None;
                }
                self.valid(&result).then_some(result)
            }
            _ => None,
        }
    }

    pub(crate) fn valid(&self, value: &Value) -> bool {
        match self {
            Self::Trigger | Self::Bool => value.is_boolean(),
            Self::Select(options) => value.is_null() || value.as_u64().is_some_and(|index| index < options.len() as u64),
            Self::Files { multiple, .. } => value.as_array().is_some_and(|ids| (*multiple || ids.len() <= 1) && ids.iter().all(Value::is_string)),
            Self::Slider { min, max, count, integer } => {
                let values = match value {
                    Value::Array(values) if *count == 2 => values.clone(),
                    _ if *count == 1 => vec![value.clone()],
                    _ => return false,
                };
                values.len() == *count && values.iter().all(|value| value.as_f64().is_some_and(|v| v.is_finite() && v >= *min && v <= *max && (!*integer || v.fract() == 0.0))) && (*count == 1 || values[0].as_f64() <= values[1].as_f64())
            }
        }
    }

    // Selection presence is internal state, distinct from the selected native
    // value: Some(index) may legitimately project to JSON null in session state.
    fn session_value(&self, value: &Value) -> Value {
        match self {
            Self::Select(options) => value.as_u64().and_then(|index| options.get(index as usize)).map(|(_, native)| native.clone()).unwrap_or(Value::Null),
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
        Ok(native.clone())
    }
}

struct Record {
    key: Option<String>,
    value: Value,
    codec: Codec,
    callback: Option<WidgetCallback>,
}

#[derive(Default)]
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

    pub(crate) fn register_widget<T>(&self, spec: WidgetSpec<'_>, resolve: impl FnOnce(&Value) -> Result<T, WidgetError>) -> Result<(String, T, bool), WidgetError> {
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
}
