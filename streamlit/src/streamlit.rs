/// Main Streamlit struct for user-facing API
/// This provides the interface used in examples like hello.rs
pub struct Streamlit {
    // No longer stores its own app instance, uses the global one
}

impl Streamlit {
    /// Create a new Streamlit instance that uses the global app
    pub fn new() -> Self {
        Self {}
    }

    /// Write a title to the app
    pub fn title(&mut self, content: &str) {
        crate::api::get_app().title(content);
    }

    /// Write text to the app
    pub fn write(&mut self, content: &str) {
        crate::api::get_app().write(content);
    }

    /// Write a header to the app
    pub fn header(&mut self, content: &str) {
        crate::api::get_app().header(content);
    }

    /// Write markdown to the app
    pub fn markdown(&mut self, content: &str) {
        crate::api::get_app().markdown(content);
    }

    /// Create a button widget
    pub fn button(&mut self, label: &str) -> bool {
        crate::api::get_app().button(label, None)
    }

    /// Create a button widget with a custom key
    pub fn button_with_key(&mut self, label: &str, key: &str) -> bool {
        crate::api::get_app().button(label, Some(key))
    }

    /// Create a text input widget
    pub fn text_input(&mut self, label: &str) -> String {
        crate::api::get_app().text_input(label, None, None)
    }

    /// Create a text input widget with default value and key
    pub fn text_input_with_value(&mut self, label: &str, default: &str, key: &str) -> String {
        crate::api::get_app().text_input(label, Some(default), Some(key))
    }

    /// Create a slider widget
    pub fn slider(&mut self, label: &str, min: f64, max: f64) -> f64 {
        crate::api::get_app().slider(label, min, max, None, None)
    }

    /// Create a slider widget with default value and key
    pub fn slider_with_value(&mut self, label: &str, min: f64, max: f64, default: f64, key: &str) -> f64 {
        crate::api::get_app().slider(label, min, max, Some(default), Some(key))
    }

    /// Create a checkbox widget
    pub fn checkbox(&mut self, label: &str) -> bool {
        crate::api::get_app().checkbox(label, None, None)
    }

    /// Create a checkbox widget with default value and key
    pub fn checkbox_with_value(&mut self, label: &str, default: bool, key: &str) -> bool {
        crate::api::get_app().checkbox(label, Some(default), Some(key))
    }

    /// Create a selectbox widget
    pub fn selectbox(&mut self, label: &str, options: Vec<String>) -> String {
        crate::api::get_app().selectbox(label, options, None, None)
    }

    /// Create a selectbox widget with default index and key
    pub fn selectbox_with_index(&mut self, label: &str, options: Vec<String>, index: usize, key: &str) -> String {
        crate::api::get_app().selectbox(label, options, Some(index), Some(key))
    }

    /// Create a number input widget
    pub fn number_input(&mut self, label: &str, min: f64, max: f64) -> f64 {
        crate::api::get_app().number_input(label, min, max, None, None)
    }

    /// Create a number input widget with default value and key
    pub fn number_input_with_value(&mut self, label: &str, min: f64, max: f64, default: f64, key: &str) -> f64 {
        crate::api::get_app().number_input(label, min, max, Some(default), Some(key))
    }

    /// Get all elements (used by the server)
    pub fn get_elements(&self) -> Vec<crate::api::StreamlitElement> {
        crate::api::get_app().get_elements()
    }

    /// Clear all elements
    pub fn clear_elements(&mut self) {
        crate::api::get_app().clear_elements();
    }

    /// Get the run count
    pub fn get_run_count(&self) -> i64 {
        crate::api::get_app().get_run_count()
    }

    /// Increment the run count
    pub fn increment_run_count(&mut self) {
        crate::api::get_app().increment_run_count();
    }
}

impl Default for Streamlit {
    fn default() -> Self {
        Self::new()
    }
}