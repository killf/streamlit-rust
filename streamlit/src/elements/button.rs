use crate::elements::common::{Element, ElementHeight, ElementWidth, RenderContext, TextAlignment};
use crate::error::StreamlitError;
use crate::proto::streamlit::{HeightConfig, TextAlignmentConfig, WidthConfig};
use crate::proto::{delta, delta_base_with_path, element, forward_msg, Delta};
use crate::utils::hash::hash;

pub(crate) struct ButtonElement {
    id: String,
    label: String,
    r#type: String,
    help: Option<String>,
    width: Option<ElementWidth>,
    height: Option<ElementHeight>,
    text_alignment: Option<TextAlignment>,
    form_id: Option<String>,
    is_form_submitter: bool,
    default: bool,
    disabled: bool,
    shortcut: Option<String>,
    icon: Option<String>,
    icon_position: i32,
}

impl ButtonElement {
    pub fn new(id: String, label: String) -> Self {
        Self {
            id,
            label,
            r#type: "secondary".to_string(),
            help: None,
            width: None,
            height: None,
            text_alignment: None,
            form_id: None,
            is_form_submitter: false,
            default: false,
            disabled: false,
            shortcut: None,
            icon: None,
            icon_position: 0,
        }
    }

    pub fn r#type(mut self, r#type: String) -> Self {
        self.r#type = r#type;
        self
    }

    pub fn width(mut self, width: ElementWidth) -> Self {
        self.width = Some(width);
        self
    }

    pub fn help(mut self, help: String) -> Self {
        self.help = Some(help);
        self
    }

    pub fn icon(mut self, icon: String) -> Self {
        self.icon = Some(icon);
        self
    }

    pub fn shortcut(mut self, shortcut: String) -> Self {
        self.shortcut = Some(shortcut);
        self
    }
}

impl Element for ButtonElement {
    fn render(&self, context: &mut RenderContext) -> Result<(), StreamlitError> {
        let element_hash = hash(format!("button_{}_{}_{}_{:?}", self.id, self.label, self.r#type, self.width).as_str());
        let mut msg = delta_base_with_path(context.delta_path.clone(), context.active_script_hash.clone(), element_hash);

        let width_config: Option<WidthConfig> = if let Some(width) = self.width.clone() { Some(width.into()) } else { None };
        let height_config: Option<HeightConfig> = if let Some(height) = self.height.clone() { Some(height.into()) } else { None };
        let text_alignment_config: Option<TextAlignmentConfig> = if let Some(align) = self.text_alignment.clone() { Some(align.into()) } else { None };

        msg.r#type = Some(forward_msg::Type::Delta(Delta {
            fragment_id: String::new(),
            r#type: Some(delta::Type::NewElement(crate::proto::Element {
                height_config,
                width_config,
                text_alignment_config,
                r#type: Some(element::Type::Button(crate::proto::Button {
                    id: self.id.clone(),
                    label: self.label.clone(),
                    default: self.default,
                    help: self.help.clone().unwrap_or_default(),
                    form_id: self.form_id.clone().unwrap_or_default(),
                    is_form_submitter: self.is_form_submitter,
                    r#type: self.r#type.clone(),
                    disabled: self.disabled,
                    #[allow(deprecated)]
                    use_container_width: false,
                    icon: self.icon.clone().unwrap_or_default(),
                    shortcut: self.shortcut.clone().unwrap_or_default(),
                    icon_position: self.icon_position,
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
