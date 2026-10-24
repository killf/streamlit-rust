use crate::WidgetError;
use crate::api::AppendChild;
use crate::elements::common::{Element, ElementHeight, ElementWidth, RenderContext};
use crate::error::StreamlitError;
use crate::memory::Allocator;
use crate::proto::streamlit::{HeightConfig, WidthConfig};
use crate::proto::{Block, Delta, delta, delta_base_with_path, forward_msg};
use crate::utils::hash::hash;
use parking_lot::Mutex;
use std::cell::RefCell;
use std::rc::Rc;

pub(crate) struct FormElement {
    key: String,
    clear_on_submit: bool,
    border: bool,
    enter_to_submit: bool,
    width: ElementWidth,
    height: ElementHeight,
    pub(crate) children: Vec<Rc<RefCell<dyn Element>>>,
    submit_count: usize,
}

impl FormElement {
    pub(crate) fn new(key: String, clear_on_submit: bool, border: bool, enter_to_submit: bool, width: ElementWidth, height: ElementHeight) -> Self {
        Self {
            key,
            clear_on_submit,
            border,
            enter_to_submit,
            width,
            height,
            children: Vec::new(),
            submit_count: 0,
        }
    }
}

impl Element for FormElement {
    fn render(&self, context: &mut RenderContext) -> Result<(), StreamlitError> {
        let element_hash = hash(format!("form_{}_{}_{}_{}_{:?}_{:?}", self.key, self.clear_on_submit, self.border, self.enter_to_submit, self.width, self.height).as_str());
        let mut msg = delta_base_with_path(context.delta_path.clone(), context.active_script_hash.clone(), element_hash);
        let width_config: Option<WidthConfig> = Some(self.width.clone().into());
        let height_config: Option<HeightConfig> = Some(self.height.clone().into());
        msg.r#type = Some(forward_msg::Type::Delta(Delta {
            fragment_id: String::new(),
            r#type: Some(delta::Type::AddBlock(Block {
                autoscroll: None,
                allow_empty: false,
                id: None,
                height_config,
                width_config,
                r#type: Some(crate::proto::block::Type::Form(crate::proto::block::Form {
                    form_id: self.key.clone(),
                    clear_on_submit: self.clear_on_submit,
                    border: self.border,
                    enter_to_submit: self.enter_to_submit,
                })),
            })),
        }));
        context.push(msg);

        context.delta_path.push(0);
        for child in &self.children {
            child.borrow().render(context)?;
        }
        context.delta_path.pop();
        if let Some(index) = context.delta_path.last_mut() {
            *index += 1;
        }
        Ok(())
    }
}

pub struct Form<'a> {
    element: Rc<RefCell<FormElement>>,
    allocator: &'a Allocator,
    app: Rc<Mutex<crate::elements::App>>,
    key: String,
}

impl<'a> Form<'a> {
    pub(crate) fn new(element: Rc<RefCell<FormElement>>, key: String, allocator: &'a Allocator, app: Rc<Mutex<crate::elements::App>>) -> Self {
        Self { element, key, allocator, app }
    }

    pub(crate) fn record_submit(&self) {
        self.element.borrow_mut().submit_count += 1;
    }

    pub(crate) fn submit_count(&self) -> usize {
        self.element.borrow().submit_count
    }
}

impl AppendChild for Form<'_> {
    fn push(&self, element: Rc<RefCell<dyn Element>>) {
        self.element.borrow_mut().children.push(element);
    }

    fn allocator(&self) -> &Allocator {
        self.allocator
    }

    fn get_app(&self) -> Rc<Mutex<crate::elements::App>> {
        self.app.clone()
    }

    fn parent_form_id(&self) -> Option<String> {
        Some(self.key.clone())
    }
}

pub(crate) fn validate_form_dimensions(width: ElementWidth, height: ElementHeight) -> Result<(), WidgetError> {
    let valid = |value: &ElementWidth| !matches!(value, ElementWidth::Value(v) if *v <= 0);
    let valid_height = |value: &ElementHeight| !matches!(value, ElementHeight::Value(v) if *v <= 0);
    if !valid(&width) || !valid_height(&height) {
        return Err(WidgetError::InvalidValue("form width and height must be positive".into()));
    }
    Ok(())
}
