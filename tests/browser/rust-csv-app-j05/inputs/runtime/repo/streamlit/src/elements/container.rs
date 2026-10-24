use crate::api::AppendChild;
use crate::elements::App;
use crate::elements::common::{Element, ElementHeight, ElementWidth, Gap, HorizontalAlignment, RenderContext, VerticalAlignment};
use crate::error::StreamlitError;
use crate::memory::Allocator;
use crate::proto::block::FlexContainer;
use crate::proto::streamlit::{HeightConfig, WidthConfig};
use crate::proto::{Block, Delta, delta, delta_base_with_path, forward_msg};
use crate::utils::hash::hash;
use parking_lot::Mutex;
use std::cell::RefCell;
use std::rc::Rc;

pub(crate) struct ContainerElement {
    border: bool,
    key: String,

    width: Option<ElementWidth>,
    height: Option<ElementHeight>,

    horizontal: bool,
    horizontal_alignment: HorizontalAlignment,
    vertical_alignment: VerticalAlignment,
    gap: Gap,

    pub(crate) children: Vec<Rc<RefCell<dyn Element>>>,
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

    pub fn border(mut self, value: bool) -> Self {
        self.border = value;
        self
    }

    pub fn key(mut self, key: String) -> Self {
        self.key = key;
        self
    }

    pub fn width(mut self, width: ElementWidth) -> Self {
        self.width = Some(width);
        self
    }

    pub fn height(mut self, height: ElementHeight) -> Self {
        self.height = Some(height);
        self
    }

    pub fn horizontal(mut self, value: bool) -> Self {
        self.horizontal = value;
        self
    }

    pub fn horizontal_alignment(mut self, alignment: HorizontalAlignment) -> Self {
        self.horizontal_alignment = alignment;
        self
    }

    pub fn vertical_alignment(mut self, alignment: VerticalAlignment) -> Self {
        self.vertical_alignment = alignment;
        self
    }

    pub fn gap(mut self, gap: Gap) -> Self {
        self.gap = gap;
        self
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

        let width_config: Option<WidthConfig> = self.width.clone().map(Into::into);
        let height_config: Option<HeightConfig> = self.height.clone().map(Into::into);

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
                autoscroll: None,
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
    element: Rc<RefCell<ContainerElement>>,
    allocator: &'a Allocator,
    app: Rc<Mutex<App>>,
    form_id: Option<String>,
    base_path: Vec<u32>,
    exit_path: Vec<u32>,
}

impl<'a> Container<'a> {
    pub(crate) fn new(element: Rc<RefCell<ContainerElement>>, allocator: &'a Allocator, app: Rc<Mutex<App>>, form_id: Option<String>, base_path: Vec<u32>, exit_path: Vec<u32>) -> Container<'a> {
        Container {
            element,
            allocator,
            app,
            form_id,
            base_path,
            exit_path,
        }
    }
}

impl AppendChild for Container<'_> {
    fn push(&self, element: Rc<RefCell<dyn Element>>) {
        let child_index = u32::try_from(self.element.borrow().children.len()).expect("container child index fits u32");
        self.element.borrow_mut().children.push(element.clone());
        // A top-level container is emitted immediately, so its later children
        // must be emitted at their block-local indices too. A container inside
        // a form is part of that form's not-yet-rendered subtree and is
        // rendered wholesale by FormElement::render.
        if self.form_id.is_none() {
            let mut app = self.app.lock();
            if let Some(context) = app.render_context_mut()
                && context.sender.is_some()
            {
                context.delta_path = self.base_path.clone();
                context.delta_path.push(child_index);
                if let Err(error) = element.borrow().render(context) {
                    log::error!("Failed to render container child immediately: {error}");
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
