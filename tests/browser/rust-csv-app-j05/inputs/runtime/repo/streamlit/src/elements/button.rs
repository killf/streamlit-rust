use crate::elements::common::{Element, ElementHeight, ElementWidth, RenderContext, TextAlignment};
use crate::error::StreamlitError;
use crate::proto::streamlit::{HeightConfig, TextAlignmentConfig, WidthConfig};
use crate::proto::{Delta, delta, delta_base_with_path, element, forward_msg};
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
    wrap: Option<bool>,
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
            wrap: None,
        }
    }

    pub fn r#type(mut self, r#type: String) -> Self {
        self.r#type = r#type;
        self
    }

    pub fn disabled(mut self, disabled: bool) -> Self {
        self.disabled = disabled;
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

    pub fn form_id(mut self, form_id: String) -> Self {
        self.form_id = Some(form_id);
        self
    }

    pub fn form_submitter(mut self, form_submitter: bool) -> Self {
        self.is_form_submitter = form_submitter;
        self
    }

    pub fn icon_position(mut self, icon_position: i32) -> Self {
        self.icon_position = icon_position;
        self
    }

    pub fn wrap(mut self, wrap: Option<bool>) -> Self {
        self.wrap = wrap;
        self
    }
}

impl Element for ButtonElement {
    fn render(&self, context: &mut RenderContext) -> Result<(), StreamlitError> {
        let element_hash = hash(format!("button_{}_{}_{}_{:?}", self.id, self.label, self.r#type, self.width).as_str());
        let mut msg = delta_base_with_path(context.delta_path.clone(), context.active_script_hash.clone(), element_hash);

        let width_config: Option<WidthConfig> = self.width.clone().map(Into::into);
        let height_config: Option<HeightConfig> = self.height.clone().map(Into::into);
        let text_alignment_config: Option<TextAlignmentConfig> = self.text_alignment.clone().map(Into::into);

        msg.r#type = Some(forward_msg::Type::Delta(Delta {
            fragment_id: String::new(),
            r#type: Some(delta::Type::NewElement(crate::proto::Element {
                has_one_shot_effect: None,
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
                    icon: self.icon.clone().unwrap_or_default(),
                    shortcut: self.shortcut.clone().unwrap_or_default(),
                    icon_position: self.icon_position,
                    wrap: self.wrap,
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
