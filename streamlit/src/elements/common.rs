use crate::error::StreamlitError;
use crate::proto::ForwardMsg;
use crate::proto::streamlit::gap_config::GapSpec;
use crate::proto::streamlit::{GapConfig, HeightConfig, TextAlignmentConfig, WidthConfig, text_alignment_config};

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
    pub sender: Option<tokio::sync::mpsc::UnboundedSender<ForwardMsg>>,
    /// While a cached function executes (miss), every streamed message is
    /// copied here so a later hit can replay the side effects at their
    /// original paths.
    pub recording: Option<Vec<ForwardMsg>>,
}

impl RenderContext {
    pub fn with_sender(session_id: String, sender: tokio::sync::mpsc::UnboundedSender<ForwardMsg>) -> Self {
        Self {
            session_id,
            stream: vec![],
            delta_path: vec![],
            active_script_hash: "".to_string(),
            sender: Some(sender),
            recording: None,
        }
    }

    pub fn push(&mut self, msg: ForwardMsg) {
        // 如果有 sender，立即发送到 channel
        if let Some(ref sender) = self.sender {
            let _ = sender.send(msg.clone());
        }
        if let Some(recording) = &mut self.recording {
            recording.push(msg.clone());
        }
        // 同时保存到 Vec，保持兼容性
        self.stream.push(msg);
    }
}

pub(crate) trait Element {
    fn render(&self, context: &mut RenderContext) -> Result<(), StreamlitError>;

    /// A deferred element streams once at the end of the run with its final
    /// value, mirroring the reference's same-tick element coalescing (the
    /// measured st.progress page streams one delta holding the last value).
    fn deferred(&self) -> bool {
        false
    }
}

impl From<ElementWidth> for WidthConfig {
    fn from(value: ElementWidth) -> Self {
        match value {
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

impl From<ElementHeight> for HeightConfig {
    fn from(value: ElementHeight) -> Self {
        match value {
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

impl From<TextAlignment> for TextAlignmentConfig {
    fn from(value: TextAlignment) -> Self {
        match value {
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

impl From<Gap> for GapConfig {
    fn from(value: Gap) -> Self {
        match value {
            Gap::Small => GapConfig { gap_spec: Some(GapSpec::GapSize(1)) },
            Gap::Medium => GapConfig { gap_spec: Some(GapSpec::GapSize(2)) },
            Gap::Large => GapConfig { gap_spec: Some(GapSpec::GapSize(3)) },
        }
    }
}
