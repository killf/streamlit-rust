use crate::api::AppendChild;
use crate::elements::common::{Element, ElementHeight, ElementWidth, Gap, RenderContext, VerticalAlignment};
use crate::error::StreamlitError;
use crate::memory::Allocator;
use crate::proto::streamlit::{HeightConfig, WidthConfig};
use crate::proto::{delta, delta_base_with_path, forward_msg, Block, Delta};
use crate::utils::hash::hash;
use std::cell::RefCell;
use std::sync::Arc;

pub(crate) struct ColumnElement {
    border: bool,
    weight: f32,
    gap: Gap,

    width: Option<ElementWidth>,
    height: Option<ElementHeight>,

    vertical_alignment: VerticalAlignment,

    pub(crate) children: Vec<Arc<RefCell<dyn Element>>>,
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

        let width_config: Option<WidthConfig> = if let Some(width) = self.width.clone() { Some(width.into()) } else { None };
        let height_config: Option<HeightConfig> = if let Some(height) = self.height.clone() { Some(height.into()) } else { None };

        msg.r#type = Some(forward_msg::Type::Delta(Delta {
            fragment_id: String::new(),
            r#type: Some(delta::Type::AddBlock(Block {
                allow_empty: true,
                id: None,
                height_config,
                width_config,
                r#type: Some(crate::proto::block::Type::Column(crate::proto::block::Column {
                    weight: self.weight as f64,
                    #[allow(deprecated)]
                    gap: "".to_string(),
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
    element: Arc<RefCell<ColumnElement>>,
    allocator: &'a Allocator,
}

impl Column<'_> {
    pub(crate) fn new(element: Arc<RefCell<ColumnElement>>, allocator: &'_ Allocator) -> Column<'_> {
        Column { element, allocator }
    }

    pub fn border(&self, value: bool) -> &Self {
        self.element.borrow_mut().border = value;
        self
    }

    pub fn gap(&self, value: Gap) -> &Self {
        self.element.borrow_mut().gap = value;
        self
    }
}

impl AppendChild for Column<'_> {
    fn push(&self, element: Arc<RefCell<dyn Element>>) {
        self.element.borrow_mut().children.push(element);
    }

    fn allocator(&self) -> &Allocator {
        self.allocator
    }
}
