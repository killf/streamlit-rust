#![allow(dead_code)]

use crate::elements::common::{Element, RenderContext};
use crate::error::StreamlitError;
use crate::proto::{delta, delta_base_with_path, element, forward_msg, NumberInput as ProtoNumberInput, Delta};
use crate::utils::hash::hash;

pub(crate) struct NumberInputElement {
    id: String,
    key: String,
    label: String,
    value: f64,
    min: Option<f64>,
    max: Option<f64>,
    step: f64,
    data_type: NumberDataType,
    format: String,
    help: Option<String>,
    disabled: bool,
    placeholder: Option<String>,
}

#[derive(Clone, Copy)]
pub enum NumberDataType {
    Int,
    Float,
}

impl NumberInputElement {
    pub fn new(label: String, value: f64, key: Option<String>) -> Self {
        let number_key = key.unwrap_or_else(|| label.clone());
        let id = format!("number_input_{}", number_key);

        Self {
            id,
            key: number_key,
            label,
            value,
            min: None,
            max: None,
            step: 1.0,
            data_type: NumberDataType::Float,
            format: String::new(),
            help: None,
            disabled: false,
            placeholder: None,
        }
    }

    pub fn set_value(&mut self, value: f64) {
        self.value = value;
    }

    pub fn get_key(&self) -> &str {
        &self.key
    }

    pub fn min(&mut self, min: f64) {
        self.min = Some(min);
    }

    pub fn max(&mut self, max: f64) {
        self.max = Some(max);
    }

    pub fn step(&mut self, step: f64) {
        self.step = step;
    }

    pub fn data_type(&mut self, data_type: NumberDataType) {
        self.data_type = data_type;
    }

    pub fn format(&mut self, format: String) {
        self.format = format;
    }

    pub fn help(&mut self, help: String) {
        self.help = Some(help);
    }

    pub fn disabled(&mut self, disabled: bool) {
        self.disabled = disabled;
    }

    pub fn placeholder(&mut self, placeholder: String) {
        self.placeholder = Some(placeholder);
    }
}

impl Element for NumberInputElement {
    fn render(&self, context: &mut RenderContext) -> Result<(), StreamlitError> {
        let element_hash = hash(format!("number_input_{}_{}", self.key, self.value).as_str());
        let mut msg = delta_base_with_path(context.delta_path.clone(), context.active_script_hash.clone(), element_hash);

        let data_type = match self.data_type {
            NumberDataType::Int => 0,
            NumberDataType::Float => 1,
        };

        msg.r#type = Some(forward_msg::Type::Delta(Delta {
            fragment_id: String::new(),
            r#type: Some(delta::Type::NewElement(crate::proto::Element {
                height_config: None,
                width_config: None,
                text_alignment_config: None,
                r#type: Some(element::Type::NumberInput(ProtoNumberInput {
                    id: self.id.clone(),
                    label: self.label.clone(),
                    form_id: String::new(),
                    format: self.format.clone(),
                    has_min: self.min.is_some(),
                    has_max: self.max.is_some(),
                    data_type,
                    default: Some(self.value),
                    step: self.step,
                    min: self.min.unwrap_or(0.0),
                    max: self.max.unwrap_or(0.0),
                    help: self.help.clone().unwrap_or_default(),
                    value: Some(self.value),
                    set_value: true,
                    disabled: self.disabled,
                    label_visibility: None,
                    placeholder: self.placeholder.clone().unwrap_or_default(),
                    icon: String::new(),
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
