#![allow(dead_code)]

use crate::elements::common::{Element, RenderContext};
use crate::error::StreamlitError;
use crate::proto::{delta, delta_base_with_path, element, forward_msg, Slider as ProtoSlider, Delta};
use crate::utils::hash::hash;
use std::cell::RefCell;
use std::sync::Arc;

pub enum SliderValue {
    Int(i64),
    Float(f64),
}

impl From<i64> for SliderValue {
    fn from(v: i64) -> Self {
        SliderValue::Int(v)
    }
}

impl From<f64> for SliderValue {
    fn from(v: f64) -> Self {
        SliderValue::Float(v)
    }
}

pub(crate) struct SliderElement {
    id: String,
    key: String,
    label: String,
    min: f64,
    max: f64,
    value: f64,
    step: f64,
    data_type: SliderDataType,
    help: Option<String>,
    disabled: bool,
}

#[derive(Clone, Copy)]
pub enum SliderDataType {
    Int,
    Float,
}

impl SliderElement {
    pub fn new(label: String, key: Option<String>) -> Self {
        let slider_key = key.unwrap_or_else(|| label.clone());
        let id = format!("slider_{}", slider_key);

        Self {
            id,
            key: slider_key,
            label,
            min: 0.0,
            max: 100.0,
            value: 50.0,
            step: 1.0,
            data_type: SliderDataType::Float,
            help: None,
            disabled: false,
        }
    }

    pub fn min(&mut self, min: f64) {
        self.min = min;
    }

    pub fn max(&mut self, max: f64) {
        self.max = max;
    }

    pub fn value(&mut self, value: f64) {
        self.value = value;
    }

    pub fn step(&mut self, step: f64) {
        self.step = step;
    }

    pub fn data_type(&mut self, data_type: SliderDataType) {
        self.data_type = data_type;
    }

    pub fn help(&mut self, help: String) {
        self.help = Some(help);
    }

    pub fn disabled(&mut self, disabled: bool) {
        self.disabled = disabled;
    }

    pub fn get_key(&self) -> &str {
        &self.key
    }

    pub fn get_value(&self) -> SliderValue {
        match self.data_type {
            SliderDataType::Int => SliderValue::Int(self.value as i64),
            SliderDataType::Float => SliderValue::Float(self.value),
        }
    }
}

impl Element for SliderElement {
    fn render(&self, context: &mut RenderContext) -> Result<(), StreamlitError> {
        let element_hash = hash(format!("slider_{}_{}", self.key, self.value).as_str());
        let mut msg = delta_base_with_path(context.delta_path.clone(), context.active_script_hash.clone(), element_hash);

        let data_type = match self.data_type {
            SliderDataType::Int => 0,
            SliderDataType::Float => 1,
        };

        msg.r#type = Some(forward_msg::Type::Delta(Delta {
            fragment_id: String::new(),
            r#type: Some(delta::Type::NewElement(crate::proto::Element {
                height_config: None,
                width_config: None,
                text_alignment_config: None,
                r#type: Some(element::Type::Slider(ProtoSlider {
                    id: self.id.clone(),
                    form_id: String::new(),
                    label: self.label.clone(),
                    format: String::new(),
                    data_type,
                    default: vec![],
                    min: self.min,
                    max: self.max,
                    step: self.step,
                    value: vec![self.value],
                    set_value: true,
                    options: vec![],
                    help: self.help.clone().unwrap_or_default(),
                    disabled: self.disabled,
                    label_visibility: None,
                    r#type: 1, // SLIDER
                })),
            })),
        }));

        context.push(msg);

        if let Some(index) = context.delta_path.pop() {
            context.delta_path.push(index + 1);
        }

        Ok(())
    }
}

pub struct Slider {
    element: Arc<RefCell<SliderElement>>,
    value: SliderValue,
}

impl Slider {
    pub(crate) fn new(element: Arc<RefCell<SliderElement>>, value: SliderValue) -> Self {
        Self { element, value }
    }

    /// Returns the current value of the slider
    pub fn get_value(&self) -> &SliderValue {
        &self.value
    }

    /// Returns the integer value (returns 0 if not an int slider)
    pub fn as_int(&self) -> i64 {
        match self.value {
            SliderValue::Int(v) => v,
            _ => 0,
        }
    }

    /// Returns the float value (returns 0.0 if not a float slider)
    pub fn as_float(&self) -> f64 {
        match self.value {
            SliderValue::Float(v) => v,
            _ => 0.0,
        }
    }

    pub fn label<T: ToString>(&self, value: T) -> &Self {
        self.element.borrow_mut().label = value.to_string();
        self
    }

    pub fn min(&self, min: f64) -> &Self {
        self.element.borrow_mut().min(min);
        self
    }

    pub fn max(&self, max: f64) -> &Self {
        self.element.borrow_mut().max(max);
        self
    }

    pub fn step(&self, step: f64) -> &Self {
        self.element.borrow_mut().step(step);
        self
    }

    pub fn help<T: ToString>(&self, value: T) -> &Self {
        self.element.borrow_mut().help(value.to_string());
        self
    }

    pub fn disabled(&self, disabled: bool) -> &Self {
        self.element.borrow_mut().disabled(disabled);
        self
    }

    pub fn key<T: ToString>(&self, value: T) -> &Self {
        self.element.borrow_mut().key = value.to_string();
        self
    }
}
