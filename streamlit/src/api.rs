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
        help: bool,
    },
    Markdown {
        id: String,
        body: String,
        allow_html: bool,
        help: bool,
    },
    Title {
        id: String,
        body: String,
    },
    Header {
        id: String,
        body: String,
    },
    Button {
        id: String,
        label: String,
        help: String,
        disabled: bool,
    },
    Slider {
        id: String,
        label: String,
        min_value: f64,
        max_value: f64,
        value: f64,
        step: f64,
        help: String,
        disabled: bool,
    },
    Selectbox {
        id: String,
        label: String,
        options: Vec<String>,
        index: usize,
        help: String,
        disabled: bool,
    },
    Checkbox {
        id: String,
        label: String,
        value: bool,
        help: String,
        disabled: bool,
    },
    TextInput {
        id: String,
        label: String,
        value: String,
        input_type: String,
        help: String,
        disabled: bool,
        max_chars: usize,
    },
    NumberInput {
        id: String,
        label: String,
        value: f64,
        min_value: f64,
        max_value: f64,
        step: f64,
        help: String,
        disabled: bool,
    },
}

/// Streamlit Rust API - provides a Python-like Streamlit interface
#[derive(Clone)]
pub struct StreamlitApp {
    elements: Arc<Mutex<Vec<StreamlitElement>>>,
    widget_states: Arc<Mutex<HashMap<String, WidgetValue>>>,
    run_count: Arc<Mutex<i64>>,
}

impl StreamlitApp {
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

    // Streamlit API methods

    /// Write text to the app
    pub fn write(&self, content: &str) {
        let element = StreamlitElement::Text {
            id: Uuid::new_v4().to_string(),
            body: content.to_string(),
            help: false,
        };
        self.elements.lock().push(element);
    }

    /// Write a title
    pub fn title(&self, content: &str) {
        let element = StreamlitElement::Title {
            id: Uuid::new_v4().to_string(),
            body: content.to_string(),
        };
        self.elements.lock().push(element);
    }

    /// Write a header
    pub fn header(&self, content: &str) {
        let element = StreamlitElement::Header {
            id: Uuid::new_v4().to_string(),
            body: content.to_string(),
        };
        self.elements.lock().push(element);
    }

    /// Write markdown
    pub fn markdown(&self, content: &str) {
        let element = StreamlitElement::Markdown {
            id: Uuid::new_v4().to_string(),
            body: content.to_string(),
            allow_html: false,
            help: false,
        };
        self.elements.lock().push(element);
    }

    /// Create a button
    pub fn button(&self, label: &str, key: Option<&str>) -> bool {
        let element_key = key
            .unwrap_or(&format!("button_{}", Uuid::new_v4()))
            .to_string();

        let element = StreamlitElement::Button {
            id: element_key.clone(),
            label: label.to_string(),
            help: String::new(),
            disabled: false,
        };
        self.elements.lock().push(element);

        // Get current state, default to false
        self.get_widget_state(&element_key)
            .map(|v| matches!(v, WidgetValue::Boolean(true)))
            .unwrap_or(false)
    }

    /// Create a slider
    pub fn slider(
        &self,
        label: &str,
        min: f64,
        max: f64,
        value: Option<f64>,
        key: Option<&str>,
    ) -> f64 {
        let element_key = key
            .unwrap_or(&format!("slider_{}", Uuid::new_v4()))
            .to_string();
        let default_value = value.unwrap_or((min + max) / 2.0);

        let element = StreamlitElement::Slider {
            id: element_key.clone(),
            label: label.to_string(),
            min_value: min,
            max_value: max,
            value: default_value,
            step: 1.0,
            help: String::new(),
            disabled: false,
        };
        self.elements.lock().push(element);

        // Get current state, default to provided value
        self.get_widget_state(&element_key)
            .and_then(|v| match v {
                WidgetValue::Float(f) => Some(f),
                WidgetValue::Integer(i) => Some(i as f64),
                _ => None,
            })
            .unwrap_or(default_value)
    }

    /// Create a text input
    pub fn text_input(&self, label: &str, value: Option<&str>, key: Option<&str>) -> String {
        let element_key = key
            .unwrap_or(&format!("text_input_{}", Uuid::new_v4()))
            .to_string();
        let default_value = value.unwrap_or("").to_string();

        let element = StreamlitElement::TextInput {
            id: element_key.clone(),
            label: label.to_string(),
            value: default_value.clone(),
            input_type: "default".to_string(),
            help: String::new(),
            disabled: false,
            max_chars: 0,
        };
        self.elements.lock().push(element);

        // Get current state, default to provided value
        self.get_widget_state(&element_key)
            .and_then(|v| match v {
                WidgetValue::String(s) => Some(s),
                _ => None,
            })
            .unwrap_or(default_value)
    }

    /// Create a checkbox
    pub fn checkbox(&self, label: &str, value: Option<bool>, key: Option<&str>) -> bool {
        let element_key = key
            .unwrap_or(&format!("checkbox_{}", Uuid::new_v4()))
            .to_string();
        let default_value = value.unwrap_or(false);

        let element = StreamlitElement::Checkbox {
            id: element_key.clone(),
            label: label.to_string(),
            value: default_value,
            help: String::new(),
            disabled: false,
        };
        self.elements.lock().push(element);

        // Get current state, default to provided value
        self.get_widget_state(&element_key)
            .map(|v| matches!(v, WidgetValue::Boolean(true)))
            .unwrap_or(default_value)
    }

    /// Create a selectbox
    pub fn selectbox(
        &self,
        label: &str,
        options: Vec<String>,
        index: Option<usize>,
        key: Option<&str>,
    ) -> String {
        let element_key = key
            .unwrap_or(&format!("selectbox_{}", Uuid::new_v4()))
            .to_string();
        let default_index = index.unwrap_or(0);
        let default_value = options.get(default_index).cloned().unwrap_or_default();

        let element = StreamlitElement::Selectbox {
            id: element_key.clone(),
            label: label.to_string(),
            options: options.clone(),
            index: default_index,
            help: String::new(),
            disabled: false,
        };
        self.elements.lock().push(element);

        // Get current state, default to provided value
        self.get_widget_state(&element_key)
            .and_then(|v| match v {
                WidgetValue::String(s) => Some(s),
                WidgetValue::Integer(i) => options.get(i as usize).cloned(),
                _ => None,
            })
            .unwrap_or(default_value)
    }

    /// Create a number input
    pub fn number_input(
        &self,
        label: &str,
        min: f64,
        max: f64,
        value: Option<f64>,
        key: Option<&str>,
    ) -> f64 {
        let element_key = key
            .unwrap_or(&format!("number_input_{}", Uuid::new_v4()))
            .to_string();
        let default_value = value.unwrap_or((min + max) / 2.0);

        let element = StreamlitElement::NumberInput {
            id: element_key.clone(),
            label: label.to_string(),
            value: default_value,
            min_value: min,
            max_value: max,
            step: 1.0,
            help: String::new(),
            disabled: false,
        };
        self.elements.lock().push(element);

        // Get current state, default to provided value
        self.get_widget_state(&element_key)
            .and_then(|v| match v {
                WidgetValue::Float(f) => Some(f),
                WidgetValue::Integer(i) => Some(i as f64),
                _ => None,
            })
            .unwrap_or(default_value)
    }
}

impl Default for StreamlitApp {
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
static STREAMLIT_APP: std::sync::LazyLock<StreamlitApp> =
    std::sync::LazyLock::new(StreamlitApp::new);

/// Get the global Streamlit app instance
pub fn get_app() -> &'static StreamlitApp {
    &STREAMLIT_APP
}

/// Convenience functions that match the Python Streamlit API
pub fn write(content: &str) {
    get_app().write(content);
}

pub fn title(content: &str) {
    get_app().title(content);
}

pub fn header(content: &str) {
    get_app().header(content);
}

pub fn markdown(content: &str) {
    get_app().markdown(content);
}

pub fn button(label: &str) -> bool {
    button_with_key(label, None)
}

pub fn button_with_key(label: &str, key: Option<&str>) -> bool {
    get_app().button(label, key)
}

pub fn slider(label: &str, min: f64, max: f64) -> f64 {
    slider_with_value(label, min, max, None, None)
}

pub fn slider_with_value(
    label: &str,
    min: f64,
    max: f64,
    value: Option<f64>,
    key: Option<&str>,
) -> f64 {
    get_app().slider(label, min, max, value, key)
}

pub fn text_input(label: &str) -> String {
    text_input_with_value(label, None, None)
}

pub fn text_input_with_value(label: &str, value: Option<&str>, key: Option<&str>) -> String {
    get_app().text_input(label, value, key)
}

pub fn checkbox(label: &str) -> bool {
    checkbox_with_value(label, None, None)
}

pub fn checkbox_with_value(label: &str, value: Option<bool>, key: Option<&str>) -> bool {
    get_app().checkbox(label, value, key)
}

pub fn selectbox(label: &str, options: Vec<String>) -> String {
    selectbox_with_index(label, options, None, None)
}

pub fn selectbox_with_index(
    label: &str,
    options: Vec<String>,
    index: Option<usize>,
    key: Option<&str>,
) -> String {
    get_app().selectbox(label, options, index, key)
}

pub fn number_input(label: &str, min: f64, max: f64) -> f64 {
    number_input_with_value(label, min, max, None, None)
}

pub fn number_input_with_value(
    label: &str,
    min: f64,
    max: f64,
    value: Option<f64>,
    key: Option<&str>,
) -> f64 {
    get_app().number_input(label, min, max, value, key)
}
