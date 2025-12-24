use crate::error::StreamlitError;
use crate::proto::streamlit::gap_config::GapSpec;
use crate::proto::streamlit::{text_alignment_config, GapConfig, HeightConfig, TextAlignmentConfig, WidthConfig};
use crate::proto::ForwardMsg;
use std::fmt::Display;

#[derive(Debug, Clone)]
pub enum ElementWidth {
    Stretch,
    Content,
    Value(i32),
}

impl From<&str> for ElementWidth {
    fn from(value: &str) -> Self {
        match value {
            "stretch" => Self::Stretch,
            "content" => Self::Content,
            _ => Self::Stretch,
        }
    }
}

impl From<String> for ElementWidth {
    fn from(value: String) -> Self {
        Self::from(value.as_str())
    }
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

impl From<&str> for ElementHeight {
    fn from(value: &str) -> Self {
        match value {
            "stretch" => Self::Stretch,
            "content" => Self::Content,
            _ => Self::Stretch,
        }
    }
}

impl From<String> for ElementHeight {
    fn from(value: String) -> Self {
        Self::from(value.as_str())
    }
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

impl From<&str> for TextAlignment {
    fn from(value: &str) -> Self {
        match value {
            "left" => Self::Left,
            "center" => Self::Center,
            "right" => Self::Right,
            "justify" => Self::Justify,
            _ => Self::Left,
        }
    }
}

impl From<String> for TextAlignment {
    fn from(value: String) -> Self {
        Self::from(value.as_str())
    }
}

#[derive(Debug, Clone)]
pub enum HorizontalAlignment {
    Left,
    Center,
    Right,
    Distribute,
}

impl From<&str> for HorizontalAlignment {
    fn from(value: &str) -> Self {
        match value {
            "left" => Self::Left,
            "center" => Self::Center,
            "right" => Self::Right,
            "distribute" => Self::Distribute,
            _ => Self::Left,
        }
    }
}

impl From<String> for HorizontalAlignment {
    fn from(value: String) -> Self {
        Self::from(value.as_str())
    }
}

#[derive(Debug, Clone)]
pub enum VerticalAlignment {
    Top,
    Center,
    Bottom,
    Distribute,
}

impl From<&str> for VerticalAlignment {
    fn from(value: &str) -> Self {
        match value {
            "top" => Self::Top,
            "center" => Self::Center,
            "bottom" => Self::Bottom,
            "distribute" => Self::Distribute,
            _ => Self::Top,
        }
    }
}

impl From<String> for VerticalAlignment {
    fn from(value: String) -> Self {
        Self::from(value.as_str())
    }
}

#[derive(Debug, Clone)]
pub enum Gap {
    Small,
    Medium,
    Large,
}

impl From<&str> for Gap {
    fn from(value: &str) -> Self {
        match value {
            "small" => Self::Small,
            "medium" => Self::Medium,
            "large" => Self::Large,
            _ => Self::Small,
        }
    }
}

impl From<String> for Gap {
    fn from(value: String) -> Self {
        Self::from(value.as_str())
    }
}

pub enum Anchor {
    String(String),
    Bool(bool),
}

impl From<&str> for Anchor {
    fn from(value: &str) -> Self {
        Self::String(value.to_string())
    }
}

impl From<String> for Anchor {
    fn from(value: String) -> Self {
        Anchor::String(value)
    }
}

impl From<bool> for Anchor {
    fn from(value: bool) -> Self {
        Anchor::Bool(value)
    }
}

impl Display for Anchor {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        let str = match self {
            Anchor::String(value) => value.to_string(),
            Anchor::Bool(value) => value.to_string(),
        };
        write!(f, "{}", str)
    }
}

pub enum Divider {
    Bool(bool),
    Blue,
    Green,
    Orange,
    Red,
    Violet,
    Yellow,
    Gray,
    Grey,
    Rainbow,
}

impl From<&str> for Divider {
    fn from(value: &str) -> Self {
        match value {
            "blue" => Self::Blue,
            "green" => Self::Green,
            "orange" => Self::Orange,
            "red" => Self::Red,
            "violet" => Self::Violet,
            "yellow" => Self::Yellow,
            "gray" => Self::Gray,
            "grey" => Self::Grey,
            "rainbow" => Self::Rainbow,
            _ => Self::Bool(false),
        }
    }
}

impl From<String> for Divider {
    fn from(value: String) -> Self {
        value.as_str().into()
    }
}

impl From<bool> for Divider {
    fn from(value: bool) -> Self {
        Self::Bool(value)
    }
}

impl Display for Divider {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        let str = match self {
            Divider::Bool(value) => value.to_string(),
            Divider::Blue => "blue".into(),
            Divider::Green => "green".into(),
            Divider::Orange => "orange".into(),
            Divider::Red => "red".into(),
            Divider::Violet => "violet".into(),
            Divider::Yellow => "yellow".into(),
            Divider::Gray => "gray".into(),
            Divider::Grey => "grey".into(),
            Divider::Rainbow => "rainbow".into(),
        };
        write!(f, "{}", str)
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
