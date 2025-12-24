use crate::error::StreamlitError;
use crate::proto::streamlit::gap_config::GapSpec;
use crate::proto::streamlit::{text_alignment_config, GapConfig, HeightConfig, TextAlignmentConfig, WidthConfig};
use crate::proto::ForwardMsg;

#[derive(Debug, Clone)]
pub enum ElementWidth {
    Stretch,
    Content,
    Value(i32),
}

impl From<i32> for ElementWidth {
    fn from(value: i32) -> Self {
        Self::Value(value)
    }
}

#[derive(Debug, Clone)]
pub enum ElementHeight {
    Stretch,
    Content,
    Value(i32),
}

impl From<i32> for ElementHeight {
    fn from(value: i32) -> Self {
        Self::Value(value)
    }
}

#[derive(Debug, Clone)]
pub enum TextAlignment {
    Left,
    Center,
    Right,
    Justify,
}

#[derive(Debug, Clone)]
pub enum HorizontalAlignment {
    Left,
    Center,
    Right,
    Distribute,
}

#[derive(Debug, Clone)]
pub enum VerticalAlignment {
    Top = 0,
    Center = 1,
    Bottom = 2,
    Distribute = 3,
}

#[derive(Debug, Clone)]
pub enum Gap {
    Small,
    Medium,
    Large,
}

#[derive(Debug, Clone)]
pub enum Anchor {
    String(String),
    Bool(bool),
}

impl From<String> for Anchor {
    fn from(s: String) -> Self {
        Anchor::String(s)
    }
}

impl From<bool> for Anchor {
    fn from(b: bool) -> Self {
        Anchor::Bool(b)
    }
}

#[derive(Debug, Clone)]
pub enum Divider {
    String(String),
    Bool(bool),
}

impl From<String> for Divider {
    fn from(s: String) -> Self {
        Divider::String(s)
    }
}

impl From<bool> for Divider {
    fn from(b: bool) -> Self {
        Divider::Bool(b)
    }
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

impl Into<HeightConfig> for ElementHeight {
    fn into(self) -> HeightConfig {
        match self {
            ElementHeight::Stretch => HeightConfig {
                height_spec: Some(crate::proto::streamlit::height_config::HeightSpec::UseStretch(true)),
            },
            ElementHeight::Content => HeightConfig {
                height_spec: Some(crate::proto::streamlit::height_config::HeightSpec::UseContent(true)),
            },
            ElementHeight::Value(value) => HeightConfig {
                height_spec: Some(crate::proto::streamlit::height_config::HeightSpec::PixelHeight(value as u32)),
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

impl Into<GapConfig> for Gap {
    fn into(self) -> GapConfig {
        match self {
            Gap::Small => GapConfig { gap_spec: Some(GapSpec::GapSize(1)) },
            Gap::Medium => GapConfig { gap_spec: Some(GapSpec::GapSize(2)) },
            Gap::Large => GapConfig { gap_spec: Some(GapSpec::GapSize(3)) },
        }
    }
}
