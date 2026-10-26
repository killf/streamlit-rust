//! Library-chart demo: the seven measured chart surfaces. Mirrors
//! tests/reference/chartlibs_app.py — the chart-building libraries are
//! Python-only, so the Rust side passes the same final payloads the
//! reference produced.
use ::streamlit::*;
use std::sync::Arc;

use serde_json::json;
use streamlit::StreamlitApi;
use streamlit::data::{Field, Int64Array, RecordBatch, Schema, StringArray};

fn kind_count_batch() -> RecordBatch {
    let fields = vec![Field::new("kind", streamlit::data::DataType::Utf8, true), Field::new("count", streamlit::data::DataType::Int64, true)];
    let kind: Vec<String> = ["a", "b"].iter().map(|s| (*s).to_string()).collect();
    let arrays = vec![Arc::new(StringArray::from(kind)) as _, Arc::new(Int64Array::from(vec![3, 7])) as _];
    RecordBatch::try_new(Arc::new(Schema::new(fields)), arrays).unwrap()
}

fn render(st: &Streamlit) {
    st.altair_chart(
        json!({"mark": {"type": "bar"}, "encoding": {"x": {"field": "kind", "type": "nominal"}, "y": {"field": "count", "type": "quantitative"}}}),
        &kind_count_batch(),
    );

    st.vega_lite_chart(json!({
        "mark": "bar",
        "encoding": {
            "x": {"field": "kind", "type": "nominal"},
            "y": {"field": "count", "type": "quantitative"},
        },
        "data": {"values": [{"kind": "a", "count": 3}, {"kind": "b", "count": 7}]},
    }));

    st.plotly_chart(include_str!("../../tests/reference/chartlibs-plotly_spec.json"));

    st.pydeck_chart(include_str!("../../tests/reference/chartlibs-deck_json.json"));

    st.graphviz_chart(include_str!("../../tests/reference/chartlibs-graphviz_spec.json"));

    st.mermaid_chart("graph LR\n    A[Start] --> B{Decision}");

    st.echarts_chart(json!({
        "xAxis": {"type": "category", "data": ["a", "b"]},
        "yAxis": {"type": "value"},
        "series": [{"type": "bar", "data": [3, 7]}],
    }));
}

#[tokio::main]
async fn main() -> std::io::Result<()> {
    StreamlitServer::new(
        |st| {
            Box::pin(async move {
                render(st);
            })
        },
        "127.0.0.1".into(),
        8528,
    )
    .start()
    .await
}
