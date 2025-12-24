use crate::elements::common::{Element, RenderContext};
use crate::error::StreamlitError;
use crate::proto::{
    delta, delta_base_with_path, element, forward_msg, Arrow, Delta,
};
use crate::utils::hash::hash;
use std::cell::RefCell;
use std::sync::Arc;

/// Represents data for a table/dataframe
#[derive(Debug, Clone)]
pub enum TableData {
    /// Simple 2D string table
    StringTable(Vec<Vec<String>>),
    /// Named columns with string data
    NamedColumns { columns: Vec<String>, data: Vec<Vec<String>> },
}

/// DataFrame element for displaying tabular data
pub(crate) struct DataFrameElement {
    data: TableData,
    use_container_width: bool,
    height: Option<u32>,
}

impl DataFrameElement {
    pub fn new(data: TableData) -> Self {
        Self {
            data,
            use_container_width: false,
            height: None,
        }
    }

    pub fn use_container_width(&mut self, use_container_width: bool) {
        self.use_container_width = use_container_width;
    }

    pub fn height(&mut self, height: u32) {
        self.height = Some(height);
    }

    /// Convert TableData to simple Arrow bytes
    /// This is a simplified implementation - in production you'd use the Arrow crate
    fn to_arrow_bytes(&self) -> Vec<u8> {
        // For now, return an empty Arrow payload
        // A full implementation would use the arrow crate to serialize data
        // This is sufficient for basic display with deprecated format
        vec![]
    }
}

impl Element for DataFrameElement {
    fn render(&self, context: &mut RenderContext) -> Result<(), StreamlitError> {
        let element_hash = hash(format!("dataframe_{:?}", self.data).as_str());
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
                r#type: Some(element::Type::ArrowDataFrame(Arrow {
                    data: self.to_arrow_bytes(),
                    styler: None,
                    id: String::new(),
                    columns: String::new(),
                    editing_mode: 0,
                    disabled: false,
                    form_id: String::new(),
                    column_order: vec![],
                    selection_mode: vec![],
                    row_height: None,
                    border_mode: 0,
                    placeholder: None,
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

/// Table element - similar to DataFrame but static display
pub(crate) struct TableElement {
    data: TableData,
    use_container_width: bool,
}

impl TableElement {
    pub fn new(data: TableData) -> Self {
        Self {
            data,
            use_container_width: false,
        }
    }

    pub fn use_container_width(&mut self, use_container_width: bool) {
        self.use_container_width = use_container_width;
    }

    fn to_arrow_bytes(&self) -> Vec<u8> {
        // For now, return an empty Arrow payload
        vec![]
    }
}

impl Element for TableElement {
    fn render(&self, context: &mut RenderContext) -> Result<(), StreamlitError> {
        let element_hash = hash(format!("table_{:?}", self.data).as_str());
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
                r#type: Some(element::Type::ArrowTable(Arrow {
                    data: self.to_arrow_bytes(),
                    styler: None,
                    id: String::new(),
                    columns: String::new(),
                    editing_mode: 0,
                    disabled: false,
                    form_id: String::new(),
                    column_order: vec![],
                    selection_mode: vec![],
                    row_height: None,
                    border_mode: 0,
                    placeholder: None,
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

pub struct DataFrame {
    element: Arc<RefCell<DataFrameElement>>,
}

impl DataFrame {
    pub(crate) fn new(element: Arc<RefCell<DataFrameElement>>) -> Self {
        Self { element }
    }

    pub fn use_container_width(&self) -> &Self {
        self.element.borrow_mut().use_container_width(true);
        self
    }

    pub fn height(&self, height: u32) -> &Self {
        self.element.borrow_mut().height(height);
        self
    }
}

pub struct Table {
    element: Arc<RefCell<TableElement>>,
}

impl Table {
    pub(crate) fn new(element: Arc<RefCell<TableElement>>) -> Self {
        Self { element }
    }

    pub fn use_container_width(&self) -> &Self {
        self.element.borrow_mut().use_container_width(true);
        self
    }
}
