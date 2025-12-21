use parking_lot::Mutex;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::sync::Arc;
use uuid::Uuid;

/// Streamlit Element types
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(tag = "type")]
pub enum StreamlitElement {
    Text {
        id: String,
        body: String,
        help: String,
    },
}

/// Streamlit Rust API - provides a Python-like Streamlit interface
#[derive(Clone)]
pub struct Streamlit {
    elements: Arc<Mutex<Vec<StreamlitElement>>>,
    widget_states: Arc<Mutex<HashMap<String, WidgetValue>>>,
    run_count: Arc<Mutex<i64>>,
}

impl Streamlit {
    pub fn new() -> Self {
        Self {
            elements: Arc::new(Mutex::new(Vec::new())),
            widget_states: Arc::new(Mutex::new(HashMap::new())),
            run_count: Arc::new(Mutex::new(0)),
        }
    }

    pub fn clear_elements(&self) {
        self.elements.lock().clear();
    }

    pub fn get_elements(&self) -> Vec<StreamlitElement> {
        self.elements.lock().clone()
    }

    pub fn increment_run_count(&self) {
        *self.run_count.lock() += 1;
    }

    pub fn get_run_count(&self) -> i64 {
        *self.run_count.lock()
    }

    pub fn set_widget_state(&self, key: &str, value: WidgetValue) {
        self.widget_states.lock().insert(key.to_string(), value);
    }

    pub fn get_widget_state(&self, key: &str) -> Option<WidgetValue> {
        self.widget_states.lock().get(key).cloned()
    }

    /// Write text to the app
    pub fn write(&self, content: &str) {
        let element = StreamlitElement::Text {
            id: Uuid::new_v4().to_string(),
            body: content.to_string(),
            help: String::default(),
        };
        self.elements.lock().push(element);
    }
}

impl Default for Streamlit {
    fn default() -> Self {
        Self::new()
    }
}

/// Widget value types
#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum WidgetValue {
    String(String),
    Float(f64),
    Integer(i64),
    Boolean(bool),
}

impl From<String> for WidgetValue {
    fn from(s: String) -> Self {
        WidgetValue::String(s)
    }
}

impl From<f64> for WidgetValue {
    fn from(f: f64) -> Self {
        WidgetValue::Float(f)
    }
}

impl From<i64> for WidgetValue {
    fn from(i: i64) -> Self {
        WidgetValue::Integer(i)
    }
}

impl From<bool> for WidgetValue {
    fn from(b: bool) -> Self {
        WidgetValue::Boolean(b)
    }
}

/// Global Streamlit app instance
static STREAMLIT_APP: std::sync::LazyLock<Streamlit> = std::sync::LazyLock::new(Streamlit::new);

/// Get the global Streamlit app instance
pub fn get_app() -> &'static Streamlit {
    &STREAMLIT_APP
}
