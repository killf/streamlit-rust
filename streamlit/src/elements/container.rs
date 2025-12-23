use crate::api::AppendChild;
use crate::elements::common::{Element, ElementHeight, ElementWidth, Gap, HorizontalAlignment, RenderContext, VerticalAlignment};
use crate::error::StreamlitError;
use crate::memory::Allocator;
use crate::proto::block::FlexContainer;
use crate::proto::streamlit::{HeightConfig, WidthConfig};
use crate::proto::{delta, delta_base_with_path, forward_msg, Block, Delta};
use crate::utils::hash::hash;
use std::cell::RefCell;
use std::sync::Arc;

pub(crate) struct ContainerElement {
    border: bool,
    key: String,

    width: Option<ElementWidth>,
    height: Option<ElementHeight>,

    horizontal: bool,
    horizontal_alignment: HorizontalAlignment,
    vertical_alignment: VerticalAlignment,
    gap: Gap,

    children: Vec<Arc<RefCell<dyn Element>>>,
}

impl ContainerElement {
    pub fn new() -> ContainerElement {
        Self {
            border: false,
            key: String::new(),
            width: None,
            height: None,
            horizontal: false,
            horizontal_alignment: HorizontalAlignment::Left,
            vertical_alignment: VerticalAlignment::Top,
            gap: Gap::Small,

            children: Vec::new(),
        }
    }
}

impl Element for ContainerElement {
    fn render(&self, context: &mut RenderContext) -> Result<(), StreamlitError> {
        // 1. 先渲染容器
        let element_hash = hash(
            format!(
                "container_{}_{:?}_{:?}_{:?}_{:?}_{:?}_{:?}_{:?}",
                self.border, self.key, self.width, self.height, self.horizontal, self.horizontal_alignment, self.vertical_alignment, self.gap
            )
                .as_str(),
        );
        let mut msg = delta_base_with_path(context.delta_path.clone(), context.active_script_hash.clone(), element_hash);

        let width_config: Option<WidthConfig> = if let Some(width) = self.width.clone() { Some(width.into()) } else { None };
        let height_config: Option<HeightConfig> = if let Some(height) = self.height.clone() { Some(height.into()) } else { None };

        let (direction, justify, align) = if self.horizontal {
            (
                2,
                match self.horizontal_alignment {
                    HorizontalAlignment::Left => 1,
                    HorizontalAlignment::Center => 2,
                    HorizontalAlignment::Right => 3,
                    HorizontalAlignment::Distribute => 4,
                },
                match self.vertical_alignment {
                    VerticalAlignment::Top => 1,
                    VerticalAlignment::Center => 2,
                    VerticalAlignment::Bottom => 3,
                    VerticalAlignment::Distribute => 4,
                },
            )
        } else {
            (
                1,
                match self.vertical_alignment {
                    VerticalAlignment::Top => 1,
                    VerticalAlignment::Center => 2,
                    VerticalAlignment::Bottom => 3,
                    VerticalAlignment::Distribute => 4,
                },
                match self.horizontal_alignment {
                    HorizontalAlignment::Left => 1,
                    HorizontalAlignment::Center => 2,
                    HorizontalAlignment::Right => 3,
                    HorizontalAlignment::Distribute => 4,
                },
            )
        };

        msg.r#type = Some(forward_msg::Type::Delta(Delta {
            fragment_id: String::new(),
            r#type: Some(delta::Type::AddBlock(Block {
                allow_empty: true,
                id: None,
                height_config,
                width_config,
                r#type: Some(crate::proto::block::Type::FlexContainer(FlexContainer {
                    border: self.border,
                    gap_config: Some(self.gap.clone().into()),
                    wrap: false,
                    scale: 0.0,
                    direction,
                    justify,
                    align,
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

pub struct Container<'a> {
    element: Arc<RefCell<ContainerElement>>,
    allocator: &'a Allocator,
}

impl Container<'_> {
    pub(crate) fn new(element: Arc<RefCell<ContainerElement>>, allocator: &'_ Allocator) -> Container<'_> {
        Container { element, allocator }
    }

    pub fn border(&self, value: bool) -> &Self {
        self.element.borrow_mut().border = value;
        self
    }

    pub fn key<T: ToString>(&self, key: T) -> &Self {
        self.element.borrow_mut().key = key.to_string();
        self
    }

    pub fn width(&self, width: ElementWidth) -> &Self {
        self.element.borrow_mut().width = Some(width);
        self
    }

    pub fn height(&self, height: ElementHeight) -> &Self {
        self.element.borrow_mut().height = Some(height);
        self
    }

    pub fn horizontal(&self, horizontal: bool) -> &Self {
        self.element.borrow_mut().horizontal = horizontal;
        self
    }

    pub fn horizontal_alignment(&self, horizontal_alignment: HorizontalAlignment) -> &Self {
        self.element.borrow_mut().horizontal_alignment = horizontal_alignment;
        self
    }

    pub fn vertical_alignment(&self, vertical_alignment: VerticalAlignment) -> &Self {
        self.element.borrow_mut().vertical_alignment = vertical_alignment;
        self
    }

    pub fn gap(&self, gap: Gap) -> &Self {
        self.element.borrow_mut().gap = gap;
        self
    }
}

impl AppendChild for Container<'_> {
    fn push(&self, element: Arc<RefCell<dyn Element>>) {
        self.element.borrow_mut().children.push(element);
    }

    fn allocator(&self) -> &Allocator {
        &self.allocator
    }
}
