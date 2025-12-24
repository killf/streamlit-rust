#![allow(dead_code)]

use crate::elements::common::{Element, RenderContext};
use crate::elements::container::ContainerElement;
use crate::error::StreamlitError;
use crate::memory::Allocator;
use crate::proto::block;
use crate::proto::{delta, delta_base_with_path, forward_msg, Block, Delta};
use crate::utils::hash::hash;
use parking_lot::Mutex;
use std::cell::RefCell;
use std::sync::Arc;

/// Form element for grouping widgets
pub(crate) struct FormElement {
    container: ContainerElement,
    form_id: String,
    clear_on_submit: bool,
    border: bool,
    enter_to_submit: bool,
}

impl FormElement {
    pub fn new(form_id: String) -> Self {
        Self {
            container: ContainerElement::new(),
            form_id,
            clear_on_submit: false,
            border: false,
            enter_to_submit: true,
        }
    }

    pub fn clear_on_submit(&mut self, clear_on_submit: bool) {
        self.clear_on_submit = clear_on_submit;
    }

    pub fn border(&mut self, border: bool) {
        self.border = border;
    }

    pub fn enter_to_submit(&mut self, enter_to_submit: bool) {
        self.enter_to_submit = enter_to_submit;
    }

    pub fn form_id(&self) -> &str {
        &self.form_id
    }

    pub(crate) fn children(&self) -> &Vec<Arc<RefCell<dyn Element>>> {
        &self.container.children
    }

    pub(crate) fn children_mut(&mut self) -> &mut Vec<Arc<RefCell<dyn Element>>> {
        &mut self.container.children
    }
}

impl Element for FormElement {
    fn render(&self, context: &mut RenderContext) -> Result<(), StreamlitError> {
        // 1. Render the form block
        let element_hash = hash(format!("form_{}", self.form_id).as_str());
        let mut msg = delta_base_with_path(
            context.delta_path.clone(),
            context.active_script_hash.clone(),
            element_hash,
        );

        msg.r#type = Some(forward_msg::Type::Delta(Delta {
            fragment_id: String::new(),
            r#type: Some(delta::Type::AddBlock(Block {
                allow_empty: false,
                id: Some(self.form_id.clone()),
                height_config: None,
                width_config: None,
                r#type: Some(block::Type::Form(block::Form {
                    form_id: self.form_id.clone(),
                    clear_on_submit: self.clear_on_submit,
                    border: self.border,
                    enter_to_submit: self.enter_to_submit,
                })),
            })),
        }));

        context.push(msg);

        // 2. Render child elements
        context.delta_path.push(0);
        for child in self.container.children.iter() {
            child.borrow().render(context)?;
        }
        context.delta_path.pop();

        if let Some(index) = context.delta_path.pop() {
            context.delta_path.push(index + 1);
        }

        Ok(())
    }
}

/// Form submit button element
pub(crate) struct FormSubmitButtonElement {
    label: String,
    disabled: bool,
    use_container_width: bool,
}

impl FormSubmitButtonElement {
    pub fn new(label: String) -> Self {
        Self {
            label,
            disabled: false,
            use_container_width: false,
        }
    }

    pub fn disabled(&mut self, disabled: bool) {
        self.disabled = disabled;
    }

    pub fn use_container_width(&mut self, use_container_width: bool) {
        self.use_container_width = use_container_width;
    }
}

impl Element for FormSubmitButtonElement {
    fn render(&self, context: &mut RenderContext) -> Result<(), StreamlitError> {
        // Form submit button is rendered as a special button within the form
        let element_hash = hash(format!("form_submit_{}", self.label).as_str());
        let mut msg = delta_base_with_path(
            context.delta_path.clone(),
            context.active_script_hash.clone(),
            element_hash,
        );

        msg.r#type = Some(forward_msg::Type::Delta(Delta {
            fragment_id: String::new(),
            r#type: Some(delta::Type::NewElement(crate::proto::Element {
                height_config: None,
                width_config: None,
                text_alignment_config: None,
                r#type: Some(crate::proto::element::Type::Button(
                    crate::proto::Button {
                        id: String::new(),
                        label: self.label.clone(),
                        r#type: "form_submit".to_string(),
                        help: String::new(),
                        form_id: String::new(),
                        disabled: self.disabled,
                        default: false,
                        is_form_submitter: true,
                        ..Default::default()
                    },
                )),
            })),
        }));

        context.push(msg);

        if let Some(index) = context.delta_path.pop() {
            context.delta_path.push(index + 1);
        }

        Ok(())
    }
}

/// Form container for adding child elements
pub struct Form<'a> {
    element: Arc<RefCell<FormElement>>,
    allocator: &'a Allocator,
    app: Option<Arc<Mutex<crate::elements::App>>>,
}

impl<'a> Form<'a> {
    pub(crate) fn new(
        element: Arc<RefCell<FormElement>>,
        allocator: &'a Allocator,
        app: Option<Arc<Mutex<crate::elements::App>>>,
    ) -> Self {
        Self {
            element,
            allocator,
            app,
        }
    }

    pub fn form_id(&self) -> String {
        self.element.borrow().form_id().to_string()
    }
}

// Implement AppendChild-like trait for Form
impl<'a> crate::api::AppendChild for Form<'a> {
    fn push(&self, element: Arc<RefCell<dyn crate::elements::common::Element>>) {
        self.element.borrow_mut().children_mut().push(element);
    }

    fn allocator(&self) -> &crate::memory::Allocator {
        self.allocator
    }

    fn app_ref(&self) -> Option<&Arc<Mutex<crate::elements::App>>> {
        self.app.as_ref()
    }
}

/// Form submit button
pub struct FormSubmitButton {
    element: Arc<RefCell<FormSubmitButtonElement>>,
}

impl FormSubmitButton {
    pub(crate) fn new(element: Arc<RefCell<FormSubmitButtonElement>>) -> Self {
        Self { element }
    }
}
