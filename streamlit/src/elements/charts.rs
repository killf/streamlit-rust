//! Library-chart elements against the measured 1.66.1 wire (see
//! .codex/compatibility.md, Chart libraries): the chart-building libraries
//! (altair, plotly, pydeck) are Python-only, so every Rust surface takes the
//! FINAL chart payload — the vega-lite spec, the plotly figure JSON, the deck
//! JSON — and streams it through the element the reference produces. The
//! measured wires were frozen on 2026-10-26 against the real reference.
use crate::elements::common::{Element as ElementTrait, ElementWidth, RenderContext};
use crate::elements::markdown::MarkdownElement;
use crate::error::StreamlitError;
use crate::proto::streamlit::{HeightConfig, WidthConfig, height_config, width_config};
use crate::proto::{Delta, Element, delta, delta_base_with_path, element, forward_msg};
use crate::utils::hash::hash;
use serde_json::{Map, Value};

/// The schema URL altair stamps on its vega-lite output.
const VEGA_SCHEMA_URL: &str = "https://vega.github.io/schema/vega-lite/v5.20.1.json";

fn stretch() -> Option<WidthConfig> {
    Some(WidthConfig {
        width_spec: Some(width_config::WidthSpec::UseStretch(true)),
    })
}

fn content_height() -> Option<HeightConfig> {
    Some(HeightConfig {
        height_spec: Some(height_config::HeightSpec::UseContent(true)),
    })
}

fn pixel_height(pixels: u32) -> Option<HeightConfig> {
    Some(HeightConfig {
        height_spec: Some(height_config::HeightSpec::PixelHeight(pixels)),
    })
}

/// A generic element wrapper: one proto element plus its width/height. The
/// graphviz variant derives its element id from the delta path (the
/// reference's calc_hash of the path repr), so it is filled at render time.
pub(crate) struct ChartElement {
    hash_input: String,
    width: Option<WidthConfig>,
    height: Option<HeightConfig>,
    inner: element::Type,
    path_hashed_id: bool,
}

impl ChartElement {
    pub(crate) fn new(hash_input: String, width: Option<WidthConfig>, height: Option<HeightConfig>, inner: element::Type) -> Self {
        Self {
            hash_input,
            width,
            height,
            inner,
            path_hashed_id: false,
        }
    }

    fn with_path_hashed_id(mut self) -> Self {
        self.path_hashed_id = true;
        self
    }
}

impl ElementTrait for ChartElement {
    fn render(&self, context: &mut RenderContext) -> Result<(), StreamlitError> {
        let element_hash = hash(&self.hash_input);
        let mut msg = delta_base_with_path(context.delta_path.clone(), context.active_script_hash.clone(), element_hash);
        let mut inner = self.inner.clone();
        if self.path_hashed_id
            && let element::Type::GraphvizChart(graphviz) = &mut inner
        {
            // The reference hashes the Python list repr of the delta path,
            // e.g. "[0, 4]".
            let path_repr = format!("[{}]", context.delta_path.iter().map(u32::to_string).collect::<Vec<_>>().join(", "));
            graphviz.element_id = crate::utils::hash::blake2b16(&path_repr);
        }
        msg.r#type = Some(forward_msg::Type::Delta(Delta {
            fragment_id: String::new(),
            r#type: Some(delta::Type::NewElement(Element {
                width_config: self.width,
                height_config: self.height,
                r#type: Some(inner),
                ..Default::default()
            })),
        }));
        context.push(msg);
        if let Some(index) = context.delta_path.pop() {
            context.delta_path.push(index + 1);
        }
        Ok(())
    }
}

/// Assemble the altair chart's vega-lite spec the way the reference emits it:
/// the dataset-name indirection first, then the caller's keys, then the
/// schema URL and autosize (insertion order preserved).
pub(crate) fn altair_spec(spec: &Value, dataset_name: &str) -> String {
    let mut out = Map::new();
    out.insert("data".into(), serde_json::json!({"name": dataset_name}));
    if let Value::Object(fields) = spec {
        for (key, value) in fields {
            out.insert(key.clone(), value.clone());
        }
    }
    out.insert("$schema".into(), Value::String(VEGA_SCHEMA_URL.to_string()));
    out.insert("autosize".into(), serde_json::json!({"type": "fit", "contains": "padding"}));
    crate::pywire::py_dumps(&Value::Object(out))
}

/// The vega_lite_chart transformation: pull an inline `data.values` list out
/// of the spec (it becomes the element's arrow data) and append autosize.
pub(crate) fn split_inline_values(spec: &Value) -> Result<(String, Option<Value>), StreamlitError> {
    let mut out = Map::new();
    let mut values = None;
    if let Value::Object(fields) = spec {
        for (key, value) in fields {
            if key == "data"
                && let Value::Object(data) = value
                && data.get("values").is_some()
            {
                values = data.get("values").cloned();
                continue;
            }
            out.insert(key.clone(), value.clone());
        }
    }
    if !out.contains_key("autosize") {
        out.insert("autosize".into(), serde_json::json!({"type": "fit", "contains": "padding"}));
    }
    Ok((crate::pywire::py_dumps(&Value::Object(out)), values))
}

/// The mermaid fence: at least four backticks, always one more than the
/// longest backtick run inside the body.
fn mermaid_fence(body: &str) -> usize {
    let mut longest = 0;
    let mut current = 0;
    for character in body.chars() {
        if character == '`' {
            current += 1;
            longest = longest.max(current);
        } else {
            current = 0;
        }
    }
    longest.max(3) + 1
}

pub(crate) fn mermaid_element(body: String, width: Option<ElementWidth>) -> MarkdownElement {
    let fence = "`".repeat(mermaid_fence(&body));
    let mut element = MarkdownElement::new(format!("{fence}mermaid\n{body}\n{fence}"));
    // The reference's mermaid width default is stretch.
    element = element.width(width.unwrap_or(ElementWidth::Stretch));
    element
}

/// st.altair_chart: the vega-lite chart with the caller's spec and the arrow
/// dataset (name = md5 of the IPC bytes, exactly like the reference).
pub fn altair_chart(spec: Value, dataset: crate::proto::ArrowData) -> ChartElement {
    let name = format!("{:x}", md5::compute(&dataset.data));
    let spec_json = altair_spec(&spec, &name);
    ChartElement::new(
        format!("altair_{spec_json}"),
        stretch(),
        content_height(),
        element::Type::VegaLiteChart(crate::proto::VegaLiteChart {
            spec: spec_json,
            datasets: vec![crate::proto::ArrowNamedDataSet { name, has_name: true, data: Some(dataset) }],
            theme: "streamlit".into(),
            ..Default::default()
        }),
    )
}

/// st.vega_lite_chart: the caller's spec with an optional inline values list
/// extracted into the element's arrow data.
pub fn vega_lite_chart(spec: Value, data: Option<crate::proto::ArrowData>) -> Result<ChartElement, StreamlitError> {
    let (spec_json, values) = split_inline_values(&spec)?;
    let arrow = match (data, values) {
        (Some(arrow), _) => Some(arrow),
        (None, Some(values)) => {
            let values = values.as_array().cloned().unwrap_or_default();
            let batch = crate::data::values_to_batch(&values).map_err(|error| StreamlitError::Component(error.to_string()))?;
            Some(crate::data_api::chart_arrow_data(&batch).map_err(|error| StreamlitError::Component(error.to_string()))?)
        }
        (None, None) => None,
    };
    Ok(ChartElement::new(
        format!("vega_lite_{spec_json}"),
        stretch(),
        content_height(),
        element::Type::VegaLiteChart(crate::proto::VegaLiteChart {
            spec: spec_json,
            data: arrow,
            theme: "streamlit".into(),
            ..Default::default()
        }),
    ))
}

/// st.plotly_chart: the figure JSON as produced by plotly's to_json.
pub fn plotly_chart(spec: String) -> ChartElement {
    let id = format!("$$ID-{}-None", hash(&spec));
    ChartElement::new(
        format!("plotly_{spec}"),
        stretch(),
        pixel_height(450),
        element::Type::PlotlyChart(crate::proto::PlotlyChart {
            theme: "streamlit".into(),
            id,
            spec,
            config: "{}".into(),
            ..Default::default()
        }),
    )
}

/// st.pydeck_chart: the deck JSON as produced by Deck.to_json.
pub fn pydeck_chart(json: String) -> ChartElement {
    ChartElement::new(format!("pydeck_{json}"), stretch(), pixel_height(500), element::Type::DeckGlJsonChart(crate::proto::DeckGlJsonChart { json, ..Default::default() }))
}

/// st.graphviz_chart: the DOT source. The element id is the reference's
/// calc_hash of the delta-path repr, filled at render time.
pub fn graphviz_chart(spec: String) -> ChartElement {
    ChartElement::new(
        format!("graphviz_{spec}"),
        Some(WidthConfig {
            width_spec: Some(width_config::WidthSpec::UseContent(true)),
        }),
        content_height(),
        element::Type::GraphvizChart(crate::proto::GraphVizChart {
            spec,
            engine: "dot".into(),
            ..Default::default()
        }),
    )
    .with_path_hashed_id()
}

/// st.echarts_chart: the option object, serialized with the reference's
/// compact separators.
pub fn echarts_chart(spec: Value) -> ChartElement {
    let spec_json = crate::pywire::py_dumps_compact(&spec);
    ChartElement::new(
        format!("echarts_{spec_json}"),
        stretch(),
        pixel_height(350),
        element::Type::EchartsChart(crate::proto::EChartsChart {
            spec: spec_json,
            theme: "streamlit".into(),
            ..Default::default()
        }),
    )
}
