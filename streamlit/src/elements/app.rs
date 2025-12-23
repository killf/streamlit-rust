use crate::elements::common::{Element, RenderContext};
use crate::error::StreamlitError;
use crate::proto::widget_state::Value;
use crate::proto::{block, delta, forward_msg, Block, Delta, ForwardMsg, ForwardMsgMetadata, WidgetState};
use serde::{Deserialize, Serialize};
use std::cell::RefCell;
use std::collections::HashMap;
use std::sync::Arc;

pub(crate) struct App {
    elements: Vec<Arc<RefCell<dyn Element>>>,
    widget_states: HashMap<String, WidgetValue>,
}

impl App {
    pub fn new() -> Self {
        Self {
            elements: Default::default(),
            widget_states: Default::default(),
        }
    }

    pub fn set_widget_state(&mut self, key: &str, value: WidgetValue) {
        self.widget_states.insert(key.to_string(), value);
    }

    pub fn process_widget_states(&mut self, widget_states: Option<Vec<WidgetState>>) {
        if let Some(states) = widget_states {
            log::info!("Processing {} widget states", states.len());
            for widget_state in states {
                if let Some(value) = widget_state.value {
                    match value {
                        Value::TriggerValue(clicked) => {
                            log::info!("Button '{}' clicked: {}", widget_state.id, clicked);
                            self.set_widget_state(&widget_state.id, WidgetValue::Boolean(clicked));
                        }
                        _ => {
                            log::info!("Received other widget type: {} - {:?}", widget_state.id, value);
                        }
                    }
                }
            }
        }
    }

    pub fn push(&mut self, element: Arc<RefCell<dyn Element>>) {
        self.elements.push(element);
    }
}

impl Element for App {
    fn render(&self, context: &mut RenderContext) -> Result<(), StreamlitError> {
        // 1. 先遍历main
        context.delta_path.push(0);
        context.push(ForwardMsg {
            hash: "main_block".to_string(),
            metadata: Some(ForwardMsgMetadata {
                cacheable: false,
                delta_path: context.delta_path.clone(),
                element_dimension_spec: None,
                active_script_hash: String::new(),
            }),
            debug_last_backmsg_id: String::new(),
            r#type: Some(forward_msg::Type::Delta(Delta {
                fragment_id: String::new(),
                r#type: Option::from(delta::Type::AddBlock(Block {
                    r#type: Some(block::Type::Vertical(block::Vertical {
                        border: false,
                        #[allow(deprecated)]
                        height: 0,
                    })),
                    allow_empty: false,
                    id: Some("main_container".to_string()), // This is the crucial ID!
                    height_config: None,
                    width_config: None,
                })),
            })),
        });

        context.delta_path.push(0);
        for element in self.elements.iter() {
            element.borrow().render(context)?;
        }
        Ok(())
    }
}

/// Widget value types
#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum WidgetValue {
    String(String),
    Float(f64),
    Integer(i64),
    Boolean(bool),
}

impl From<String> for WidgetValue {
    fn from(s: String) -> Self {
        WidgetValue::String(s)
    }
}

impl From<f64> for WidgetValue {
    fn from(f: f64) -> Self {
        WidgetValue::Float(f)
    }
}

impl From<i64> for WidgetValue {
    fn from(i: i64) -> Self {
        WidgetValue::Integer(i)
    }
}

impl From<bool> for WidgetValue {
    fn from(b: bool) -> Self {
        WidgetValue::Boolean(b)
    }
}
