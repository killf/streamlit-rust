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
    Title {
        id: String,
        title: String,
    },
    Header {
        id: String,
        body: String,
        level: i32, // 1-6 for h1-h6
    },
    Markdown {
        id: String,
        body: String,
    },
    Code {
        id: String,
        body: String,
        language: Option<String>,
    },
    Divider {
        id: String,
    },
    Empty {
        id: String,
    },
    Button {
        id: String,
        label: String,
        key: String,
        clicked: bool,
    },
    Container {
        id: String,
        key: Option<String>,
        children: Vec<StreamlitElement>,
    },
    Columns {
        id: String,
        key: Option<String>,
        columns: Vec<StreamlitElement>,
        column_count: usize,
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

    /// Set the page title
    pub fn title(&self, title: &str) {
        let element = StreamlitElement::Title {
            id: Uuid::new_v4().to_string(),
            title: title.to_string(),
        };
        self.elements.lock().push(element);
    }

    /// Display header text (frontend only supports H1-H3)
    pub fn header(&self, body: &str, level: i32) {
        let element = StreamlitElement::Header {
            id: Uuid::new_v4().to_string(),
            body: body.to_string(),
            level: level.clamp(1, 3),
        };
        self.elements.lock().push(element);
    }

    /// Display markdown text
    pub fn markdown(&self, body: &str) {
        let element = StreamlitElement::Markdown {
            id: Uuid::new_v4().to_string(),
            body: body.to_string(),
        };
        self.elements.lock().push(element);
    }

    /// Display code with optional syntax highlighting
    pub fn code(&self, body: &str, language: Option<&str>) {
        let element = StreamlitElement::Code {
            id: Uuid::new_v4().to_string(),
            body: body.to_string(),
            language: language.map(|s| s.to_string()),
        };
        self.elements.lock().push(element);
    }

    /// Display a horizontal divider
    pub fn divider(&self) {
        let element = StreamlitElement::Divider {
            id: Uuid::new_v4().to_string(),
        };
        self.elements.lock().push(element);
    }

    /// Display an empty placeholder
    pub fn empty(&self) {
        let element = StreamlitElement::Empty {
            id: Uuid::new_v4().to_string(),
        };
        self.elements.lock().push(element);
    }

    /// Display a button and return whether it was clicked
    pub fn button(&self, label: &str, key: Option<&str>) -> bool {
        let button_key = key.unwrap_or(label);

        // Generate consistent ID using the button key - this is the key fix!
        let element_id = format!("button-{}", button_key);

        // Check if this button was previously clicked
        let was_clicked = self.get_widget_state(button_key)
            .and_then(|value| match value {
                WidgetValue::Boolean(b) => Some(b),
                _ => None,
            })
            .unwrap_or(false);

        // Reset button state after checking
        if was_clicked {
            self.set_widget_state(button_key, WidgetValue::Boolean(false));
        }

        // Create the button element with consistent ID
        let element = StreamlitElement::Button {
            id: element_id,
            label: label.to_string(),
            key: button_key.to_string(),
            clicked: was_clicked,
        };
        self.elements.lock().push(element);

        was_clicked
    }

    /// Create a simple container (for now, just groups elements)
    pub fn container(&self) -> SimpleContainer {
        SimpleContainer::new(self.elements.clone())
    }

    /// Create simple columns (for now, just returns separate containers)
    pub fn columns<const N: usize>(&self) -> [SimpleContainer; N] {
        let mut cols = Vec::with_capacity(N);
        for _ in 0..N {
            cols.push(SimpleContainer::new(self.elements.clone()));
        }
        cols.try_into().unwrap()
    }

    /// Display text with a specific heading level (shortcut for common headers)
    pub fn h1(&self, body: &str) {
        self.header(body, 1);
    }

    pub fn h2(&self, body: &str) {
        self.header(body, 2);
    }

    pub fn h3(&self, body: &str) {
        self.header(body, 3);
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

/// Simple Container for basic grouping functionality
#[derive(Debug, Clone)]
pub struct SimpleContainer {
    elements: Arc<Mutex<Vec<StreamlitElement>>>,
    parent_elements: Arc<Mutex<Vec<StreamlitElement>>>,
}

impl SimpleContainer {
    fn new(parent_elements: Arc<Mutex<Vec<StreamlitElement>>>) -> Self {
        Self {
            elements: Arc::new(Mutex::new(Vec::new())),
            parent_elements,
        }
    }

    pub fn write(&self, content: &str) {
        let element = StreamlitElement::Text {
            id: Uuid::new_v4().to_string(),
            body: content.to_string(),
            help: String::default(),
        };
        self.elements.lock().push(element);
        self.sync_to_parent();
    }

    pub fn button(&self, label: &str, key: Option<&str>) -> bool {
        let button_key = key.unwrap_or(label);
        let element_id = format!("button-{}", button_key);

        // Check if this button was previously clicked
        let app = get_app();
        let was_clicked = app.get_widget_state(button_key)
            .and_then(|value| match value {
                WidgetValue::Boolean(b) => Some(b),
                _ => None,
            })
            .unwrap_or(false);

        // Reset button state after checking
        if was_clicked {
            app.set_widget_state(button_key, WidgetValue::Boolean(false));
        }

        let element = StreamlitElement::Button {
            id: element_id,
            label: label.to_string(),
            key: button_key.to_string(),
            clicked: was_clicked,
        };
        self.elements.lock().push(element);
        self.sync_to_parent();

        was_clicked
    }

    fn sync_to_parent(&self) {
        let children = self.elements.lock().clone();
        let container_element = StreamlitElement::Container {
            id: Uuid::new_v4().to_string(),
            key: None,
            children,
        };
        self.parent_elements.lock().push(container_element);
    }
}

pub type StreamlitContainer = SimpleContainer;
pub type StreamlitColumn = SimpleContainer;

/// Global Streamlit app instance
static STREAMLIT_APP: std::sync::LazyLock<Streamlit> = std::sync::LazyLock::new(Streamlit::new);

/// Get the global Streamlit app instance
pub fn get_app() -> &'static Streamlit {
    &STREAMLIT_APP
}
