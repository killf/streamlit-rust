#![allow(dead_code)]

use crate::elements::common::{Element, RenderContext};
use crate::error::StreamlitError;
use crate::proto::{delta, delta_base_with_path, element, forward_msg, Metric as ProtoMetric, Delta};
use crate::utils::hash::hash;

pub enum MetricColor {
    Red,
    Green,
    Gray,
    Orange,
    Yellow,
    Blue,
    Violet,
    Primary,
}

pub enum MetricDirection {
    Down,
    Up,
    None,
}

pub(crate) struct MetricElement {
    label: String,
    body: String,
    delta: String,
    direction: MetricDirection,
    color: MetricColor,
    help: Option<String>,
    show_border: bool,
}

impl MetricElement {
    pub fn new(label: String, body: String, delta: String) -> Self {
        Self {
            label,
            body,
            delta,
            direction: MetricDirection::None,
            color: MetricColor::Gray,
            help: None,
            show_border: false,
        }
    }

    pub fn direction(&mut self, direction: MetricDirection) {
        self.direction = direction;
    }

    pub fn color(&mut self, color: MetricColor) {
        self.color = color;
    }

    pub fn help(&mut self, help: String) {
        self.help = Some(help);
    }

    pub fn show_border(&mut self, show_border: bool) {
        self.show_border = show_border;
    }
}

impl Element for MetricElement {
    fn render(&self, context: &mut RenderContext) -> Result<(), StreamlitError> {
        let element_hash = hash(format!("metric_{}_{}_{}", self.label, self.body, self.delta).as_str());
        let mut msg = delta_base_with_path(context.delta_path.clone(), context.active_script_hash.clone(), element_hash);

        let direction = match self.direction {
            MetricDirection::Down => 0,
            MetricDirection::Up => 1,
            MetricDirection::None => 2,
        };

        let color = match self.color {
            MetricColor::Red => 0,
            MetricColor::Green => 1,
            MetricColor::Gray => 2,
            MetricColor::Orange => 3,
            MetricColor::Yellow => 4,
            MetricColor::Blue => 5,
            MetricColor::Violet => 6,
            MetricColor::Primary => 7,
        };

        msg.r#type = Some(forward_msg::Type::Delta(Delta {
            fragment_id: String::new(),
            r#type: Some(delta::Type::NewElement(crate::proto::Element {
                height_config: None,
                width_config: None,
                text_alignment_config: None,
                r#type: Some(element::Type::Metric(ProtoMetric {
                    label: self.label.clone(),
                    body: self.body.clone(),
                    delta: self.delta.clone(),
                    direction,
                    color,
                    help: self.help.clone().unwrap_or_default(),
                    label_visibility: None,
                    show_border: self.show_border,
                    chart_data: vec![],
                    chart_type: 0, // LINE
                    format: String::new(),
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
