use crate::api::AppendChild;
use crate::elements::App;
use crate::elements::common::{Element, ElementHeight, ElementWidth, Gap, RenderContext, VerticalAlignment};
use crate::error::StreamlitError;
use crate::memory::Allocator;
use crate::proto::streamlit::{HeightConfig, WidthConfig};
use crate::proto::{Block, Delta, delta, delta_base_with_path, forward_msg};
use crate::utils::hash::hash;
use parking_lot::Mutex;
use std::cell::{Cell, RefCell};
use std::rc::Rc;

pub(crate) struct ColumnElement {
    border: bool,
    weight: f32,
    gap: Gap,

    width: Option<ElementWidth>,
    height: Option<ElementHeight>,

    vertical_alignment: VerticalAlignment,

    pub(crate) children: Vec<Rc<RefCell<dyn Element>>>,
}

impl ColumnElement {
    pub fn new(weight: f32) -> Self {
        Self {
            border: false,
            weight,
            gap: Gap::Small,
            children: Vec::new(),
            width: None,
            height: None,
            vertical_alignment: VerticalAlignment::Top,
        }
    }

    pub fn border(mut self, border: bool) -> Self {
        self.border = border;
        self
    }

    pub fn width(mut self, width: ElementWidth) -> Self {
        self.width = Some(width);
        self
    }

    pub fn vertical_alignment(mut self, vertical_alignment: VerticalAlignment) -> Self {
        self.vertical_alignment = vertical_alignment;
        self
    }
}

impl Element for ColumnElement {
    fn render(&self, context: &mut RenderContext) -> Result<(), StreamlitError> {
        // 1. 先渲染容器
        let element_hash = hash(format!("container_{}_{:?}", self.weight, self.gap).as_str());
        let mut msg = delta_base_with_path(context.delta_path.clone(), context.active_script_hash.clone(), element_hash);

        let width_config: Option<WidthConfig> = self.width.clone().map(Into::into);
        let height_config: Option<HeightConfig> = self.height.clone().map(Into::into);

        msg.r#type = Some(forward_msg::Type::Delta(Delta {
            fragment_id: String::new(),
            r#type: Some(delta::Type::AddBlock(Block {
                autoscroll: None,
                allow_empty: true,
                id: None,
                height_config,
                width_config,
                r#type: Some(crate::proto::block::Type::Column(crate::proto::block::Column {
                    weight: self.weight as f64,
                    vertical_alignment: self.vertical_alignment.clone() as i32,
                    show_border: self.border,
                    gap_config: Some(self.gap.clone().into()),
                })),
            })),
        }));

        context.push(msg);

        // 2. 渲染容器中的元素
        context.delta_path.push(0);
        for child in self.children.iter() {
            child.borrow().render(context)?;
        }
        context.delta_path.pop();

        if let Some(index) = context.delta_path.pop() {
            context.delta_path.push(index + 1);
        }

        Ok(())
    }
}

pub struct Column<'a> {
    element: Rc<RefCell<ColumnElement>>,
    allocator: &'a Allocator,
    app: Rc<Mutex<App>>,
    form_id: Option<String>,
    base_path: Vec<u32>,
    exit_path: Vec<u32>,
    block_emitted: Cell<bool>,
}

impl<'a> Column<'a> {
    pub(crate) fn new(element: Rc<RefCell<ColumnElement>>, allocator: &'a Allocator, app: Rc<Mutex<App>>, form_id: Option<String>, base_path: Vec<u32>, exit_path: Vec<u32>) -> Column<'a> {
        let mut block_emitted = false;
        if form_id.is_none() {
            let mut app = app.lock();
            if let Some(context) = app.render_context_mut()
                && context.sender.is_some()
            {
                context.delta_path = base_path.clone();
                if let Err(error) = element.borrow().render(context) {
                    log::error!("Failed to render column immediately: {error}");
                }
                context.delta_path = exit_path.clone();
                block_emitted = true;
            }
        }
        Column {
            element,
            allocator,
            app,
            form_id,
            base_path,
            exit_path,
            block_emitted: Cell::new(block_emitted),
        }
    }
}

impl AppendChild for Column<'_> {
    fn push(&self, element: Rc<RefCell<dyn Element>>) {
        let child_index = u32::try_from(self.element.borrow().children.len()).expect("column child index fits u32");
        let mut render_now = false;
        if self.form_id.is_none() {
            let mut app = self.app.lock();
            if let Some(context) = app.render_context_mut()
                && context.sender.is_some()
            {
                render_now = true;
                if !self.block_emitted.get() {
                    context.delta_path = self.base_path.clone();
                    if let Err(error) = self.element.borrow().render(context) {
                        log::error!("Failed to render column immediately: {error}");
                    }
                    self.block_emitted.set(true);
                }
            }
        }
        self.element.borrow_mut().children.push(element.clone());
        if render_now {
            let mut app = self.app.lock();
            if let Some(context) = app.render_context_mut() {
                context.delta_path = self.base_path.clone();
                context.delta_path.push(child_index);
                if let Err(error) = element.borrow().render(context) {
                    log::error!("Failed to render column child immediately: {error}");
                }
                context.delta_path = self.exit_path.clone();
            }
        }
    }

    fn allocator(&self) -> &Allocator {
        self.allocator
    }

    fn get_app(&self) -> Rc<Mutex<App>> {
        self.app.clone()
    }

    fn parent_form_id(&self) -> Option<String> {
        self.form_id.clone()
    }

    fn next_child_path(&self) -> Vec<u32> {
        let mut path = self.base_path.clone();
        path.push(self.element.borrow().children.len() as u32);
        path
    }
}
