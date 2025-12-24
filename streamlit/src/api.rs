use crate::elements::alert::{AlertFormat, Error, Info, Success, Warning};
use crate::elements::badge::{Badge, BadgeElement};
use crate::elements::button::ButtonElement;
use crate::elements::checkbox::CheckboxElement;
use crate::elements::code::{Code, CodeElement};
use crate::elements::color_picker::ColorPickerElement;
use crate::elements::columns::{Column, ColumnElement, ColumnsOption};
use crate::elements::common::Element;
use crate::elements::container::{Container, ContainerElement};
use crate::elements::dataframe::{DataFrame, DataFrameElement, Table, TableElement, TableData};
use crate::elements::date_input::DateInputElement;
use crate::elements::download_button::{DownloadButton, DownloadButtonElement};
use crate::elements::file_uploader::{FileUploader, FileUploaderElement};
use crate::elements::form::{Form, FormElement, FormSubmitButtonElement};
use crate::elements::image::ImageElement;
use crate::elements::markdown::{Markdown, MarkdownElement, MarkdownElementType};
use crate::elements::metric::MetricElement;
use crate::elements::multiselect::MultiSelectElement;
use crate::elements::number_input::NumberInputElement;
use crate::elements::plotly_chart::{PlotlyChart, PlotlyChartElement};
use crate::elements::progress::ProgressElement;
use crate::elements::radio::RadioElement;
use crate::elements::selectbox::SelectboxElement;
use crate::elements::slider::SliderElement;
use crate::elements::spinner::SpinnerElement;
use crate::elements::text_input::TextInputElement;
use crate::elements::time_input::TimeInputElement;
use crate::elements::title::{Heading, HeadingElement};
use crate::elements::visual_effects::{BalloonsElement, SnowElement};
use crate::elements::App;
use crate::memory::Allocator;
use crate::proto::WidgetState;
use parking_lot::Mutex;
use std::cell::RefCell;
use std::sync::Arc;

/// Streamlit Rust API - provides a Python-like Streamlit interface
pub struct Streamlit {
    pub(crate) app: Arc<Mutex<App>>,
    allocator: Allocator,
}

impl Streamlit {
    pub(crate) fn new() -> Self {
        Self {
            app: Arc::new(Mutex::new(App::new())),
            allocator: Allocator::new(),
        }
    }

    pub(crate) fn process_widget_states(self, widget_states: Vec<WidgetState>) -> Self {
        self.app.lock().process_widget_states(widget_states);
        self
    }
}

pub(crate) trait AppendChild {
    fn push(&self, element: Arc<RefCell<dyn Element>>);

    fn allocator(&self) -> &Allocator;

    fn app_ref(&self) -> Option<&Arc<Mutex<App>>> {
        None
    }
}

impl AppendChild for Streamlit {
    fn push(&self, element: Arc<RefCell<dyn Element>>) {
        self.app.lock().push(element);
    }

    fn allocator(&self) -> &Allocator {
        &self.allocator
    }

    fn app_ref(&self) -> Option<&Arc<Mutex<App>>> {
        Some(&self.app)
    }
}

/// Internal helper trait for reducing code duplication
trait StreamlitApiInternal {
    fn get_and_clear_widget_state<T, F>(
        &self,
        key: &str,
        default: T,
        getter: F,
    ) -> T
    where
        T: Clone,
        F: FnOnce(&App) -> T;

    fn get_widget_key<T: ToString>(&self, label: T, key: Option<T>) -> (String, String);
}

pub trait StreamlitApi {
    fn write<T: ToString>(&self, content: T) -> &Markdown;

    fn title<T: ToString>(&self, body: T) -> &Heading {
        self.h1(body)
    }

    fn header<T: ToString>(&self, body: T) -> &Heading {
        self.h2(body)
    }

    fn sub_header<T: ToString>(&self, body: T) -> &Heading {
        self.h3(body)
    }

    fn divider(&self) -> &Markdown;

    fn h1<T: ToString>(&self, body: T) -> &Heading;

    fn h2<T: ToString>(&self, body: T) -> &Heading;

    fn h3<T: ToString>(&self, body: T) -> &Heading;

    fn markdown<T: ToString>(&self, body: T) -> &Markdown;

    fn badge<T: ToString>(&self, label: T) -> &Badge;

    fn caption<T: ToString>(&self, body: T) -> &Markdown;

    fn code<T1: ToString, T2: ToString>(&self, code_text: T1, language: T2) -> &Code;

    fn container(&self) -> &Container<'_>;

    fn columns<T: Into<ColumnsOption>>(&self, spec: T) -> &[Column<'_>];

    fn button<T: ToString>(&self, label: T, key: Option<T>) -> bool;

    fn slider<T: ToString>(&self, label: T, min: f64, max: f64, value: f64, key: Option<T>) -> f64;

    fn checkbox<T: ToString>(&self, label: T, value: bool, key: Option<T>) -> bool;

    fn text_input<T: ToString>(&self, label: T, value: T, key: Option<T>) -> String;

    fn text_area<T: ToString>(&self, label: T, value: T, key: Option<T>) -> String;

    fn selectbox<T: ToString>(&self, label: T, options: Vec<String>, index: usize, key: Option<T>) -> (usize, String);

    fn radio<T: ToString>(&self, label: T, options: Vec<String>, index: usize, key: Option<T>) -> (usize, String);

    fn number_input<T: ToString>(&self, label: T, value: f64, key: Option<T>) -> f64;

    fn metric<T: ToString>(&self, label: T, body: T, delta: T);

    fn progress(&self, value: f64, text: Option<String>);

    fn spinner<T: ToString>(&self, text: T);

    // New elements
    fn dataframe(&self, data: TableData) -> &DataFrame;

    fn table(&self, data: TableData) -> &Table;

    fn form<T: ToString>(&self, key: T) -> &Form<'_>;

    fn form_submit_button<T: ToString>(&self, label: T) -> bool;

    fn file_uploader<T: ToString>(&self, label: T, key: Option<T>) -> &FileUploader;

    fn download_button<T: ToString>(&self, label: T, data: Vec<u8>, file_name: &str, key: Option<T>) -> &DownloadButton;

    fn plotly_chart(&self, spec: &str) -> &PlotlyChart;

    // Alert elements
    fn error<T: ToString>(&self, body: T) -> &Error;

    fn warning<T: ToString>(&self, body: T) -> &Warning;

    fn info<T: ToString>(&self, body: T) -> &Info;

    fn success<T: ToString>(&self, body: T) -> &Success;

    // Image element
    fn image(&self, url: Option<String>, caption: Option<String>);

    // Visual effects
    fn balloons(&self);

    fn snow(&self);

    // New input elements
    fn color_picker<T: ToString>(&self, label: T, default_value: T, key: Option<T>) -> String;

    fn time_input<T: ToString>(&self, label: T, default_value: Option<T>, key: Option<T>) -> Option<String>;

    fn date_input<T: ToString>(&self, label: T, default_value: Vec<T>, key: Option<T>) -> Vec<String>;

    fn multiselect<T: ToString>(&self, label: T, options: Vec<String>, default_indices: Vec<i32>, key: Option<T>) -> (Vec<i32>, Vec<String>);
}

impl<C: AppendChild> StreamlitApiInternal for C {
    fn get_and_clear_widget_state<T, F>(
        &self,
        key: &str,
        default: T,
        getter: F,
    ) -> T
    where
        T: Clone,
        F: FnOnce(&App) -> T,
    {
        let current = if let Some(app) = self.app_ref() {
            getter(&app.lock())
        } else {
            default.clone()
        };

        if let Some(app) = self.app_ref() {
            app.lock().clear_widget_state(key);
        }

        current
    }

    fn get_widget_key<T: ToString>(&self, label: T, key: Option<T>) -> (String, String) {
        let key_str = key.map(|k| k.to_string()).unwrap_or_else(|| label.to_string());
        (label.to_string(), key_str)
    }
}

impl<C: AppendChild> StreamlitApi for C {
    fn write<T: ToString>(&self, content: T) -> &Markdown {
        let element = Arc::new(RefCell::new(MarkdownElement::new(content.to_string())));
        self.push(element.clone());
        self.allocator().malloc(Markdown::new(element))
    }

    fn divider(&self) -> &Markdown {
        let element = Arc::new(RefCell::new(MarkdownElement::new("---".to_string()).element_type(MarkdownElementType::Divider)));
        self.push(element.clone());
        self.allocator().malloc(Markdown::new(element))
    }

    fn h1<T: ToString>(&self, body: T) -> &Heading {
        let element = Arc::new(RefCell::new(HeadingElement::new("h1".to_string(), body.to_string())));
        self.push(element.clone());
        self.allocator().malloc(Heading::new(element))
    }

    fn h2<T: ToString>(&self, body: T) -> &Heading {
        let element = Arc::new(RefCell::new(HeadingElement::new("h2".to_string(), body.to_string())));
        self.push(element.clone());
        self.allocator().malloc(Heading::new(element))
    }

    fn h3<T: ToString>(&self, body: T) -> &Heading {
        let element = Arc::new(RefCell::new(HeadingElement::new("h3".to_string(), body.to_string())));
        self.push(element.clone());
        self.allocator().malloc(Heading::new(element))
    }

    fn markdown<T: ToString>(&self, body: T) -> &Markdown {
        let element = Arc::new(RefCell::new(MarkdownElement::new(body.to_string())));
        self.push(element.clone());
        self.allocator().malloc(Markdown::new(element))
    }

    fn badge<T: ToString>(&self, label: T) -> &Badge {
        let element = Arc::new(RefCell::new(BadgeElement::new(label.to_string())));
        self.push(element.clone());
        self.allocator().malloc(Badge::new(element))
    }

    fn caption<T: ToString>(&self, body: T) -> &Markdown {
        let element = Arc::new(RefCell::new(MarkdownElement::new(body.to_string()).element_type(MarkdownElementType::Caption)));
        self.push(element.clone());
        self.allocator().malloc(Markdown::new(element))
    }

    fn code<T1: ToString, T2: ToString>(&self, code_text: T1, language: T2) -> &Code {
        let element = Arc::new(RefCell::new(CodeElement::new(code_text.to_string(), language.to_string())));
        self.push(element.clone());
        self.allocator().malloc(Code::new(element))
    }

    fn container(&self) -> &Container<'_> {
        let element = Arc::new(RefCell::new(ContainerElement::new()));
        self.push(element.clone());
        self.allocator().malloc(Container::new(element, self.allocator()))
    }

    fn columns<T: Into<ColumnsOption>>(&self, spec: T) -> &[Column<'_>] {
        let weights = match spec.into() {
            ColumnsOption::Count(count) => {
                let weight = 1.0 / count as f32;
                vec![weight; count]
            }
            ColumnsOption::Weights(weights) => {
                let total: f32 = weights.iter().sum();
                weights.iter().map(|w| w / total).collect()
            }
        };

        if weights.is_empty() {
            return &[];
        }

        let container_element = Arc::new(RefCell::new(ContainerElement::new().horizontal(true)));
        self.push(container_element.clone());

        let columns = self.allocator().malloc(vec![]);
        for w in weights {
            let column_element = Arc::new(RefCell::new(ColumnElement::new(w)));
            container_element.borrow_mut().children.push(column_element.clone());

            columns.push(Column::new(column_element, self.allocator()));
        }
        columns.as_slice()
    }

    fn button<T: ToString>(&self, label: T, key: Option<T>) -> bool {
        let button_key = key.map(|k| k.to_string()).unwrap_or_else(|| label.to_string());

        // Check if this button was clicked
        let was_clicked = if let Some(app) = self.app_ref() {
            app.lock().get_boolean_state(&button_key)
        } else {
            false
        };

        // Create the button element
        let element = Arc::new(RefCell::new(ButtonElement::new(label.to_string(), Some(button_key.clone()))));
        self.push(element.clone());

        // Clear the button state after checking so it only triggers once per click
        if let Some(app) = self.app_ref() {
            app.lock().clear_widget_state(&button_key);
        }

        was_clicked
    }

    fn slider<T: ToString>(&self, label: T, min: f64, max: f64, value: f64, key: Option<T>) -> f64 {
        let slider_key = key.map(|k| k.to_string()).unwrap_or_else(|| label.to_string());

        // Check if this slider has a value from user input
        let current_value = if let Some(app) = self.app_ref() {
            let float_val = app.lock().get_float_state(&slider_key);
            if float_val != 0.0 {
                float_val
            } else {
                // Try integer value
                let int_val = app.lock().get_integer_state(&slider_key);
                if int_val != 0 {
                    int_val as f64
                } else {
                    value
                }
            }
        } else {
            value
        };

        // Create the slider element
        let element = Arc::new(RefCell::new({
            let mut el = SliderElement::new(label.to_string(), Some(slider_key.clone()));
            el.min(min);
            el.max(max);
            el.value(current_value);
            el
        }));
        self.push(element.clone());

        // Clear the slider state after reading
        if let Some(app) = self.app_ref() {
            app.lock().clear_widget_state(&slider_key);
        }

        current_value
    }

    fn checkbox<T: ToString>(&self, label: T, value: bool, key: Option<T>) -> bool {
        let (_label, checkbox_key) = self.get_widget_key(label, key);

        // Check if this checkbox has a value from user input
        let current_value = self.get_and_clear_widget_state(
            &checkbox_key,
            value,
            |app| app.get_boolean_state(&checkbox_key)
        );

        // Create the checkbox element
        let element = Arc::new(RefCell::new({
            let mut el = CheckboxElement::new(_label, Some(checkbox_key.clone()));
            el.set_value(current_value);
            el
        }));
        self.push(element);

        current_value
    }

    fn text_input<T: ToString>(&self, label: T, value: T, key: Option<T>) -> String {
        let (label_str, text_key) = self.get_widget_key(label, key);
        let default_value = value.to_string();

        // Check if this text input has a value from user input
        let current_value = self.get_and_clear_widget_state(
            &text_key,
            default_value.clone(),
            |app| {
                let state = app.get_string_state(&text_key);
                if !state.is_empty() {
                    state
                } else {
                    default_value
                }
            }
        );

        // Create the text input element
        let element = Arc::new(RefCell::new({
            let mut el = TextInputElement::new(label_str, Some(text_key));
            el.set_value(current_value.clone());
            el
        }));
        self.push(element);

        current_value
    }

    fn text_area<T: ToString>(&self, label: T, value: T, key: Option<T>) -> String {
        // For now, text_area is the same as text_input
        // In a full implementation, you might want to add a height property
        self.text_input(label, value, key)
    }

    fn selectbox<T: ToString>(&self, label: T, options: Vec<String>, index: usize, key: Option<T>) -> (usize, String) {
        let selectbox_key = key.map(|k| k.to_string()).unwrap_or_else(|| label.to_string());
        let options_count = options.len();

        // Check if this selectbox has a value from user input
        let current_index = if let Some(app) = self.app_ref() {
            let int_val = app.lock().get_integer_state(&selectbox_key);
            if int_val != 0 {
                (int_val as usize).min(options_count.saturating_sub(1))
            } else {
                // Also check for string value (option text)
                let str_val = app.lock().get_string_state(&selectbox_key);
                if !str_val.is_empty() {
                    // Find the index of the string in options
                    options.iter().position(|o| o == &str_val).unwrap_or(index)
                } else {
                    index
                }
            }
        } else {
            index
        };

        // Ensure index is within bounds
        let current_index = current_index.min(options_count.saturating_sub(1));
        let current_value = options.get(current_index).cloned().unwrap_or_default();

        // Create the selectbox element
        let element = Arc::new(RefCell::new(SelectboxElement::new(
            label.to_string(),
            options,
            current_index,
            Some(selectbox_key.clone()),
        )));
        self.push(element.clone());

        // Clear the selectbox state after reading
        if let Some(app) = self.app_ref() {
            app.lock().clear_widget_state(&selectbox_key);
        }

        (current_index, current_value)
    }

    fn radio<T: ToString>(&self, label: T, options: Vec<String>, index: usize, key: Option<T>) -> (usize, String) {
        let radio_key = key.map(|k| k.to_string()).unwrap_or_else(|| label.to_string());
        let options_count = options.len();

        // Check if this radio has a value from user input
        let current_index = if let Some(app) = self.app_ref() {
            let int_val = app.lock().get_integer_state(&radio_key);
            if int_val != 0 {
                (int_val as usize).min(options_count.saturating_sub(1))
            } else {
                index
            }
        } else {
            index
        };

        // Ensure index is within bounds
        let current_index = current_index.min(options_count.saturating_sub(1));
        let current_value = options.get(current_index).cloned().unwrap_or_default();

        // Create the radio element
        let element = Arc::new(RefCell::new(RadioElement::new(
            label.to_string(),
            options,
            current_index,
            Some(radio_key.clone()),
        )));
        self.push(element.clone());

        // Clear the radio state after reading
        if let Some(app) = self.app_ref() {
            app.lock().clear_widget_state(&radio_key);
        }

        (current_index, current_value)
    }

    fn number_input<T: ToString>(&self, label: T, value: f64, key: Option<T>) -> f64 {
        let number_key = key.map(|k| k.to_string()).unwrap_or_else(|| label.to_string());

        // Check if this number input has a value from user input
        let current_value = if let Some(app) = self.app_ref() {
            let float_val = app.lock().get_float_state(&number_key);
            if float_val != 0.0 {
                float_val
            } else {
                // Try integer value
                let int_val = app.lock().get_integer_state(&number_key);
                if int_val != 0 {
                    int_val as f64
                } else {
                    value
                }
            }
        } else {
            value
        };

        // Create the number input element
        let element = Arc::new(RefCell::new(NumberInputElement::new(label.to_string(), current_value, Some(number_key.clone()))));
        self.push(element.clone());

        // Clear the number input state after reading
        if let Some(app) = self.app_ref() {
            app.lock().clear_widget_state(&number_key);
        }

        current_value
    }

    fn metric<T: ToString>(&self, label: T, body: T, delta: T) {
        // Create the metric element
        let element = Arc::new(RefCell::new(MetricElement::new(
            label.to_string(),
            body.to_string(),
            delta.to_string(),
        )));
        self.push(element);
    }

    fn progress(&self, value: f64, text: Option<String>) {
        // Create the progress element
        let element = Arc::new(RefCell::new(ProgressElement::new(
            (value * 100.0) as u32,
            text.unwrap_or_default(),
        )));
        self.push(element);
    }

    fn spinner<T: ToString>(&self, text: T) {
        // Create the spinner element
        let element = Arc::new(RefCell::new(SpinnerElement::new(text.to_string())));
        self.push(element);
    }

    // New element implementations

    fn dataframe(&self, data: TableData) -> &DataFrame {
        let element = Arc::new(RefCell::new(DataFrameElement::new(data)));
        self.push(element.clone());
        self.allocator().malloc(DataFrame::new(element))
    }

    fn table(&self, data: TableData) -> &Table {
        let element = Arc::new(RefCell::new(TableElement::new(data)));
        self.push(element.clone());
        self.allocator().malloc(Table::new(element))
    }

    fn form<T: ToString>(&self, key: T) -> &Form<'_> {
        let form_id = key.to_string();
        let element = Arc::new(RefCell::new(FormElement::new(form_id.clone())));
        self.push(element.clone());

        // Check if form was submitted
        if let Some(app) = self.app_ref() {
            let form_key = format!("_form_submit_{}", form_id);
            let was_submitted = app.lock().get_boolean_state(&form_key);
            if was_submitted {
                app.lock().clear_widget_state(&form_key);
            }
        }

        self.allocator().malloc(Form::new(element, self.allocator(), self.app_ref().cloned()))
    }

    fn form_submit_button<T: ToString>(&self, label: T) -> bool {
        let label_str = label.to_string();
        // The form submit button is handled by the parent form
        // For now, just return a placeholder
        let element = Arc::new(RefCell::new(FormSubmitButtonElement::new(label_str.clone())));
        self.push(element);
        false
    }

    fn file_uploader<T: ToString>(&self, label: T, key: Option<T>) -> &FileUploader {
        let uploader_key = key.map(|k| k.to_string()).unwrap_or_else(|| label.to_string());
        let element = Arc::new(RefCell::new(FileUploaderElement::new(label.to_string(), Some(uploader_key.clone()))));
        self.push(element.clone());
        self.allocator().malloc(FileUploader::new(element))
    }

    fn download_button<T: ToString>(&self, label: T, data: Vec<u8>, file_name: &str, key: Option<T>) -> &DownloadButton {
        let button_key = key.map(|k| k.to_string()).unwrap_or_else(|| label.to_string());
        let mut element = DownloadButtonElement::new(label.to_string(), Some(button_key));
        element.data(data);
        element.file_name(file_name.to_string());
        let element = Arc::new(RefCell::new(element));
        self.push(element.clone());
        self.allocator().malloc(DownloadButton::new(element))
    }

    fn plotly_chart(&self, spec: &str) -> &PlotlyChart {
        let element = Arc::new(RefCell::new(PlotlyChartElement::new(spec.to_string())));
        self.push(element.clone());
        self.allocator().malloc(PlotlyChart::new(element))
    }

    // New element implementations

    fn error<T: ToString>(&self, body: T) -> &Error {
        let element = Arc::new(RefCell::new(crate::elements::alert::AlertElement::new(body.to_string(), AlertFormat::Error)));
        self.push(element.clone());
        self.allocator().malloc(Error::new(element))
    }

    fn warning<T: ToString>(&self, body: T) -> &Warning {
        let element = Arc::new(RefCell::new(crate::elements::alert::AlertElement::new(body.to_string(), AlertFormat::Warning)));
        self.push(element.clone());
        self.allocator().malloc(Warning::new(element))
    }

    fn info<T: ToString>(&self, body: T) -> &Info {
        let element = Arc::new(RefCell::new(crate::elements::alert::AlertElement::new(body.to_string(), AlertFormat::Info)));
        self.push(element.clone());
        self.allocator().malloc(Info::new(element))
    }

    fn success<T: ToString>(&self, body: T) -> &Success {
        let element = Arc::new(RefCell::new(crate::elements::alert::AlertElement::new(body.to_string(), AlertFormat::Success)));
        self.push(element.clone());
        self.allocator().malloc(Success::new(element))
    }

    fn image(&self, url: Option<String>, caption: Option<String>) {
        let mut element = ImageElement::new();
        if let Some(u) = url {
            element = element.url(u);
        }
        if let Some(c) = caption {
            element = element.caption(c);
        }
        let element = Arc::new(RefCell::new(element));
        self.push(element);
    }

    fn balloons(&self) {
        let element = Arc::new(RefCell::new(BalloonsElement::new()));
        self.push(element);
    }

    fn snow(&self) {
        let element = Arc::new(RefCell::new(SnowElement::new()));
        self.push(element);
    }

    // New element implementations

    fn color_picker<T: ToString>(&self, label: T, default_value: T, key: Option<T>) -> String {
        let (label_str, picker_key) = self.get_widget_key(label, key);
        let default_str = default_value.to_string();

        // Check if this color picker has a value from user input
        let current_value = self.get_and_clear_widget_state(
            &picker_key,
            default_str.clone(),
            |app| {
                let state = app.get_string_state(&picker_key);
                if !state.is_empty() {
                    state
                } else {
                    default_str
                }
            }
        );

        // Create the color picker element
        let element = Arc::new(RefCell::new(ColorPickerElement::new(
            label_str,
            current_value.clone(),
            Some(picker_key),
        )));
        self.push(element);

        current_value
    }

    fn time_input<T: ToString>(&self, label: T, default_value: Option<T>, key: Option<T>) -> Option<String> {
        let (label_str, input_key) = self.get_widget_key(label, key);
        let default_str = default_value.map(|v| v.to_string());

        // Check if this time input has a value from user input
        let current_value = self.get_and_clear_widget_state(
            &input_key,
            default_str.clone(),
            |app| {
                let state = app.get_string_state(&input_key);
                if !state.is_empty() {
                    Some(state)
                } else {
                    default_str
                }
            }
        );

        // Create the time input element
        let element = Arc::new(RefCell::new(TimeInputElement::new(
            label_str,
            current_value.clone(),
            Some(input_key),
        )));
        self.push(element);

        current_value
    }

    fn date_input<T: ToString>(&self, label: T, default_value: Vec<T>, key: Option<T>) -> Vec<String> {
        let (label_str, input_key) = self.get_widget_key(label, key);
        let default_vec: Vec<String> = default_value.iter().map(|v| v.to_string()).collect();

        // For simplicity, return the default values
        // In a full implementation, you'd parse the date strings from widget state
        let element = Arc::new(RefCell::new(DateInputElement::new(
            label_str,
            default_vec.clone(),
            Some(input_key.clone()),
        )));
        self.push(element);

        // Clear the date input state after reading
        if let Some(app) = self.app_ref() {
            app.lock().clear_widget_state(&input_key);
        }

        default_vec
    }

    fn multiselect<T: ToString>(&self, label: T, options: Vec<String>, default_indices: Vec<i32>, key: Option<T>) -> (Vec<i32>, Vec<String>) {
        let (label_str, select_key) = self.get_widget_key(label, key);
        let options_count = options.len();

        // For simplicity, use the default indices
        // In a full implementation, you'd check the widget state for user selections
        let current_indices = default_indices.clone();
        let current_values: Vec<String> = current_indices
            .iter()
            .filter_map(|&i| {
                let idx = i as usize;
                if idx < options_count {
                    Some(options[idx].clone())
                } else {
                    None
                }
            })
            .collect();

        // Create the multiselect element
        let element = Arc::new(RefCell::new(MultiSelectElement::new(
            label_str,
            options,
            current_indices.clone(),
            Some(select_key.clone()),
        )));
        self.push(element);

        // Clear the multiselect state after reading
        if let Some(app) = self.app_ref() {
            app.lock().clear_widget_state(&select_key);
        }

        (current_indices, current_values)
    }
}
