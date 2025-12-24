use crate::elements::common::{Element, RenderContext};
use crate::error::StreamlitError;
use crate::proto::{
    delta, delta_base_with_path, element, forward_msg, PlotlyChart as ProtoPlotlyChart, Delta,
};
use crate::utils::hash::hash;
use std::cell::RefCell;
use std::sync::Arc;

/// Plotly chart element
pub(crate) struct PlotlyChartElement {
    spec: String,
    config: String,
    theme: String,
    use_container_width: bool,
}

impl PlotlyChartElement {
    pub fn new(spec: String) -> Self {
        Self {
            spec,
            config: String::new(),
            theme: String::new(),
            use_container_width: false,
        }
    }

    pub fn config(&mut self, config: String) {
        self.config = config;
    }

    pub fn theme(&mut self, theme: String) {
        self.theme = theme;
    }

    pub fn use_container_width(&mut self, use_container_width: bool) {
        self.use_container_width = use_container_width;
    }
}

impl Element for PlotlyChartElement {
    fn render(&self, context: &mut RenderContext) -> Result<(), StreamlitError> {
        let element_hash = hash(format!("plotly_chart_{}", self.spec).as_str());
        let mut msg = delta_base_with_path(
            context.delta_path.clone(),
            context.active_script_hash.clone(),
            element_hash,
        );

        msg.r#type = Some(forward_msg::Type::Delta(Delta {
            fragment_id: String::new(),
            r#type: Some(delta::Type::NewElement(crate::proto::Element {
                height_config: None,
                width_config: None,
                text_alignment_config: None,
                r#type: Some(element::Type::PlotlyChart(ProtoPlotlyChart {
                    theme: self.theme.clone(),
                    id: String::new(),
                    selection_mode: vec![],
                    form_id: String::new(),
                    spec: self.spec.clone(),
                    config: self.config.clone(),
                    ..Default::default()
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

pub struct PlotlyChart {
    element: Arc<RefCell<PlotlyChartElement>>,
}

impl PlotlyChart {
    pub(crate) fn new(element: Arc<RefCell<PlotlyChartElement>>) -> Self {
        Self { element }
    }

    pub fn use_container_width(&self) -> &Self {
        self.element.borrow_mut().use_container_width(true);
        self
    }

    pub fn theme(&self, theme: &str) -> &Self {
        self.element.borrow_mut().theme(theme.to_string());
        self
    }

    pub fn config(&self, config: &str) -> &Self {
        self.element.borrow_mut().config(config.to_string());
        self
    }
}
