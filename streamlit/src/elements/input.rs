use crate::elements::common::{Element, RenderContext};
use crate::error::StreamlitError;
use crate::proto::{Delta, Element as WireElement, delta, delta_base_with_path, forward_msg};

pub(crate) struct InputElement(pub(crate) WireElement);

impl Element for InputElement {
    fn render(&self, context: &mut RenderContext) -> Result<(), StreamlitError> {
        let mut message = delta_base_with_path(context.delta_path.clone(), context.active_script_hash.clone(), crate::utils::hash::hash(&format!("{:?}", self.0)));
        message.r#type = Some(forward_msg::Type::Delta(Delta {
            fragment_id: String::new(),
            r#type: Some(delta::Type::NewElement(self.0.clone())),
        }));
        context.push(message);
        if let Some(index) = context.delta_path.last_mut() {
            *index += 1;
        }
        Ok(())
    }
}

/// A widget element the runtime routes to the bottom container ([3, 0])
/// without consuming a main-flow slot: the measured st.chat_input shape
/// (auto-positioned at the bottom).
pub(crate) struct BottomRoutedElement(pub(crate) WireElement);

impl Element for BottomRoutedElement {
    fn render(&self, context: &mut RenderContext) -> Result<(), StreamlitError> {
        let mut message = delta_base_with_path(vec![3, 0], context.active_script_hash.clone(), crate::utils::hash::hash(&format!("{:?}", self.0)));
        message.r#type = Some(forward_msg::Type::Delta(Delta {
            fragment_id: String::new(),
            r#type: Some(delta::Type::NewElement(self.0.clone())),
        }));
        context.push(message);
        Ok(())
    }
}
