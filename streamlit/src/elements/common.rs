use crate::error::StreamlitError;
use crate::proto::streamlit::{text_alignment_config, TextAlignmentConfig, WidthConfig};
use crate::proto::ForwardMsg;

#[derive(Debug, Clone)]
pub enum ElementWidth {
    Stretch,
    Content,
    Value(i32),
}

#[derive(Debug, Clone)]
pub enum TextAlignment {
    Left,
    Center,
    Right,
    Justify,
}

pub(crate) struct RenderContext {
    pub stream: Vec<ForwardMsg>,
    pub delta_path: Vec<u32>,
    pub active_script_hash: String,
    pub session_id: String,
}

impl RenderContext {
    pub fn new(session_id: String) -> Self {
        Self {
            session_id,
            stream: vec![],
            delta_path: vec![],
            active_script_hash: "".to_string(),
        }
    }

    pub fn push(&mut self, msg: ForwardMsg) {
        self.stream.push(msg);
    }
}

pub(crate) trait Element {
    fn render(&self, context: &mut RenderContext) -> Result<(), StreamlitError>;
}

impl Into<WidthConfig> for ElementWidth {
    fn into(self) -> WidthConfig {
        match self {
            ElementWidth::Stretch => WidthConfig {
                width_spec: Some(crate::proto::streamlit::width_config::WidthSpec::UseStretch(true)),
            },
            ElementWidth::Content => WidthConfig {
                width_spec: Some(crate::proto::streamlit::width_config::WidthSpec::UseContent(true)),
            },
            ElementWidth::Value(value) => WidthConfig {
                width_spec: Some(crate::proto::streamlit::width_config::WidthSpec::PixelWidth(value as u32)),
            },
        }
    }
}

impl Into<TextAlignmentConfig> for TextAlignment {
    fn into(self) -> TextAlignmentConfig {
        match self {
            TextAlignment::Left => TextAlignmentConfig {
                alignment: text_alignment_config::Alignment::Left.into(),
            },
            TextAlignment::Center => TextAlignmentConfig {
                alignment: text_alignment_config::Alignment::Center.into(),
            },
            TextAlignment::Right => TextAlignmentConfig {
                alignment: text_alignment_config::Alignment::Right.into(),
            },
            TextAlignment::Justify => TextAlignmentConfig {
                alignment: text_alignment_config::Alignment::Justify.into(),
            },
        }
    }
}
