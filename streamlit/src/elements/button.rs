#![allow(dead_code)]

use crate::elements::common::{Element, ElementWidth, RenderContext};
use crate::error::StreamlitError;
use crate::proto::streamlit::WidthConfig;
use crate::proto::{delta, delta_base_with_path, element, forward_msg, Button as ProtoButton, Delta};
use crate::utils::hash::hash;
use std::cell::RefCell;
use std::sync::Arc;

pub(crate) struct ButtonElement {
    id: String,
    label: String,
    key: String,
    help: Option<String>,
    disabled: bool,
    width: Option<ElementWidth>,
    icon: Option<String>,
    shortcut: Option<String>,
}

impl ButtonElement {
    pub fn new(label: String, key: Option<String>) -> Self {
        // Use provided key or generate one from label
        let button_key = key.unwrap_or_else(|| label.clone());
        let id = format!("button_{}", button_key);

        Self {
            id,
            label,
            key: button_key,
            help: None,
            disabled: false,
            width: None,
            icon: None,
            shortcut: None,
        }
    }

    pub fn set_key(&mut self, key: String) {
        self.id = format!("button_{}", key);
        self.key = key;
    }

    #[allow(dead_code)]
    pub fn get_key(&self) -> &str {
        &self.key
    }

    pub fn help(&mut self, help: String) {
        self.help = Some(help);
    }

    pub fn disabled(&mut self, disabled: bool) {
        self.disabled = disabled;
    }

    pub fn width(&mut self, width: ElementWidth) {
        self.width = Some(width);
    }

    pub fn icon(&mut self, icon: String) {
        self.icon = Some(icon);
    }

    pub fn shortcut(&mut self, shortcut: String) {
        self.shortcut = Some(shortcut);
    }
}

impl Element for ButtonElement {
    fn render(&self, context: &mut RenderContext) -> Result<(), StreamlitError> {
        let element_hash = hash(format!("button_{}_{}", self.key, self.label).as_str());
        let mut msg = delta_base_with_path(context.delta_path.clone(), context.active_script_hash.clone(), element_hash);

        let width_config: Option<WidthConfig> = self.width.clone().map(|w| w.into());

        msg.r#type = Some(forward_msg::Type::Delta(Delta {
            fragment_id: String::new(),
            r#type: Some(delta::Type::NewElement(crate::proto::Element {
                height_config: None,
                width_config,
                text_alignment_config: None,
                r#type: Some(element::Type::Button(ProtoButton {
                    id: self.id.clone(),
                    label: self.label.clone(),
                    default: false,
                    help: self.help.clone().unwrap_or_default(),
                    form_id: String::new(),
                    is_form_submitter: false,
                    r#type: "primary".to_string(),
                    disabled: self.disabled,
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

pub struct Button {
    element: Arc<RefCell<ButtonElement>>,
    clicked: bool,
}

impl Button {
    pub(crate) fn new(element: Arc<RefCell<ButtonElement>>, clicked: bool) -> Self {
        Self { element, clicked }
    }

    /// Returns true if the button was clicked
    pub fn is_clicked(&self) -> bool {
        self.clicked
    }

    /// Returns true if the button was clicked (alias for is_clicked)
    pub fn was_clicked(&self) -> bool {
        self.clicked
    }

    pub fn label<T: ToString>(&self, value: T) -> &Self {
        self.element.borrow_mut().label = value.to_string();
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

    pub fn width(&self, width: ElementWidth) -> &Self {
        self.element.borrow_mut().width(width);
        self
    }

    pub fn icon<T: ToString>(&self, value: T) -> &Self {
        self.element.borrow_mut().icon(value.to_string());
        self
    }

    pub fn shortcut<T: ToString>(&self, value: T) -> &Self {
        self.element.borrow_mut().shortcut(value.to_string());
        self
    }

    pub fn key<T: ToString>(&self, value: T) -> &Self {
        self.element.borrow_mut().set_key(value.to_string());
        self
    }
}
