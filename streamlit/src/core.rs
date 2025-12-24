use crate::elements::common::Element;
use crate::elements::App;
use crate::proto::WidgetState;
use parking_lot::Mutex;
use std::cell::RefCell;
use std::sync::Arc;

/// Streamlit Rust API - provides a Python-like Streamlit interface
pub struct Streamlit {
    pub(crate) app: Arc<Mutex<App>>,
}

impl Streamlit {
    pub(crate) fn new() -> Self {
        Self { app: Arc::new(Mutex::new(App::new())) }
    }

    pub(crate) fn process_widget_states(self, widget_states: Vec<WidgetState>) -> Self {
        self.app.lock().process_widget_states(widget_states);
        self
    }
}

pub(crate) trait AppendChild {
    fn push(&self, element: Arc<RefCell<dyn Element>>);
}

impl AppendChild for Streamlit {
    fn push(&self, element: Arc<RefCell<dyn Element>>) {
        self.app.lock().push(element);
    }
}
