#![allow(dead_code)]

use crate::elements::common::{Element, RenderContext};
use crate::error::StreamlitError;
use crate::proto::{delta, delta_base_with_path, element, forward_msg, MultiSelect as ProtoMultiSelect, Delta};
use crate::utils::hash::hash;

pub(crate) struct MultiSelectElement {
    id: String,
    key: String,
    label: String,
    default_indices: Vec<i32>,
    options: Vec<String>,
    help: Option<String>,
    disabled: bool,
    placeholder: Option<String>,
    max_selections: Option<i32>,
}

impl MultiSelectElement {
    pub fn new(label: String, options: Vec<String>, default_indices: Vec<i32>, key: Option<String>) -> Self {
        let select_key = key.unwrap_or_else(|| label.clone());
        let id = format!("multiselect_{}", select_key);

        Self {
            id,
            key: select_key,
            label,
            default_indices,
            options,
            help: None,
            disabled: false,
            placeholder: None,
            max_selections: None,
        }
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

    pub fn max_selections(&mut self, max_selections: i32) {
        self.max_selections = Some(max_selections);
    }

    pub fn get_key(&self) -> &str {
        &self.key
    }
}

impl Element for MultiSelectElement {
    fn render(&self, context: &mut RenderContext) -> Result<(), StreamlitError> {
        let element_hash = hash(format!("multiselect_{}_{}", self.key, self.default_indices.iter().map(|i| i.to_string()).collect::<Vec<_>>().join(",")).as_str());
        let mut msg = delta_base_with_path(context.delta_path.clone(), context.active_script_hash.clone(), element_hash);

        // Get default values from indices
        let default_values: Vec<String> = self.default_indices
            .iter()
            .filter_map(|&i| self.options.get(i as usize).cloned())
            .collect();

        msg.r#type = Some(forward_msg::Type::Delta(Delta {
            fragment_id: String::new(),
            r#type: Some(delta::Type::NewElement(crate::proto::Element {
                height_config: None,
                width_config: None,
                text_alignment_config: None,
                r#type: Some(element::Type::Multiselect(ProtoMultiSelect {
                    id: self.id.clone(),
                    label: self.label.clone(),
                    default: self.default_indices.clone(),
                    options: self.options.clone(),
                    help: self.help.clone().unwrap_or_default(),
                    form_id: String::new(),
                    raw_values: default_values,
                    set_value: false,
                    disabled: self.disabled,
                    label_visibility: None,
                    max_selections: self.max_selections.unwrap_or(0),
                    placeholder: self.placeholder.clone().unwrap_or_default(),
                    accept_new_options: None,
                    ..Default::default()
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

pub struct MultiSelect {
    indices: Vec<i32>,
    values: Vec<String>,
}

impl MultiSelect {
    pub(crate) fn new(indices: Vec<i32>, values: Vec<String>) -> Self {
        Self { indices, values }
    }

    /// Get the selected indices
    pub fn indices(&self) -> &[i32] {
        &self.indices
    }

    /// Get the selected values
    pub fn values(&self) -> &[String] {
        &self.values
    }
}
