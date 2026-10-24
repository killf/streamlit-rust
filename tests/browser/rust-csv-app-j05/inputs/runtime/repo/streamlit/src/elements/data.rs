use crate::elements::common::{Element, RenderContext};
use crate::error::StreamlitError;
use crate::proto::{Delta, Element as WireElement, delta, delta_base_with_path, forward_msg};

pub(crate) struct DataElement(pub(crate) WireElement);

impl Element for DataElement {
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
