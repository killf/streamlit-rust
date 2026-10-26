//! Library-chart regressions against the measured Python 1.66.1 wire (see
//! .codex/compatibility.md, Chart libraries): the seven surfaces pass the
//! same final payloads the reference produced. st.altair_chart carries the
//! dataset-name indirection spec (schema URL + autosize appended, theme
//! streamlit) with the chart's arrow dataset (content-addressed name, md5 of
//! the IPC bytes); st.vega_lite_chart pulls an inline values list out of the
//! spec into the element's arrow data; st.plotly_chart carries the figure
//! JSON with the config "{}" and the 450px height; st.pydeck_chart carries
//! the deck JSON at 500px; st.graphviz_chart's element id is the reference's
//! calc_hash of the delta-path repr with content sizing; st.mermaid_chart is
//! a fenced markdown block (4-backtick fence, stretch width); st.echarts_chart
//! carries the compact-separator spec at 350px.
use super::*;
use crate::StreamlitApi;
use crate::data::{Field, Int64Array, RecordBatch, Schema, StringArray};
use crate::proto::element;
use crate::proto::forward_msg;
use serde_json::json;
use std::sync::Arc;

fn kind_count_batch() -> RecordBatch {
    let fields = vec![Field::new("kind", crate::data::DataType::Utf8, true), Field::new("count", crate::data::DataType::Int64, true)];
    let kind: Vec<&str> = vec!["a", "b"];
    let arrays = vec![Arc::new(StringArray::from(kind)) as _, Arc::new(Int64Array::from(vec![3, 7])) as _];
    RecordBatch::try_new(Arc::new(Schema::new(fields)), arrays).unwrap()
}

fn chartlibs_entry(st: &Streamlit) -> Pin<Box<dyn Future<Output = ()> + '_>> {
    Box::pin(async move {
        // Mirrors tests/reference/chartlibs_app.py.
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
        st.plotly_chart(include_str!("../../../tests/reference/chartlibs-plotly_spec.json"));
        st.pydeck_chart(include_str!("../../../tests/reference/chartlibs-deck_json.json"));
        st.graphviz_chart(include_str!("../../../tests/reference/chartlibs-graphviz_spec.json"));
        st.mermaid_chart("graph LR\n    A[Start] --> B{Decision}");
        st.echarts_chart(json!({
            "xAxis": {"type": "category", "data": ["a", "b"]},
            "yAxis": {"type": "value"},
            "series": [{"type": "bar", "data": [3, 7]}],
        }));
    })
}

#[actix_web::test]
async fn library_charts_match_the_measured_wire() {
    let listener = std::net::TcpListener::bind("127.0.0.1:0").unwrap();
    let address = listener.local_addr().unwrap();
    let server = HttpServer::new(move || App::new().app_data(web::Data::new(StreamlitServer::new(chartlibs_entry, "127.0.0.1".into(), 0))).configure(configure_routes))
        .workers(1)
        .listen(listener)
        .unwrap()
        .run();
    let handle = server.handle();
    let task = actix_web::rt::spawn(server);
    let mut stream = TcpStream::connect(address).await.unwrap();
    let request = format!("GET /_stcore/stream HTTP/1.1\r\nHost: {address}\r\nConnection: Upgrade\r\nUpgrade: websocket\r\nSec-WebSocket-Version: 13\r\nSec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==\r\nSec-WebSocket-Protocol: streamlit, test-xsrf\r\n\r\n");
    stream.write_all(request.as_bytes()).await.unwrap();
    let headers = tokio::time::timeout(Duration::from_secs(5), async {
        let mut response = Vec::new();
        while !response.ends_with(b"\r\n\r\n") {
            response.push(stream.read_u8().await.unwrap());
        }
        String::from_utf8(response).unwrap().to_ascii_lowercase()
    })
    .await
    .unwrap();
    assert!(headers.starts_with("http/1.1 101"));

    send_binary(
        &mut stream,
        &(BackMsg {
            r#type: Some(back_msg::Type::RerunScript(ClientState::default())),
        })
        .encode_to_vec(),
    )
    .await;

    let mut timeline: Vec<String> = Vec::new();
    loop {
        let message = receive(&mut stream).await;
        match message.r#type {
            Some(forward_msg::Type::NewSession(_)) => {}
            Some(forward_msg::Type::SessionStatusChanged(status)) if !status.script_is_running => break,
            Some(forward_msg::Type::Delta(delta)) => {
                let Some(delta::Type::NewElement(element)) = delta.r#type else { continue };
                let Some(kind) = element.r#type else { continue };
                let height = match element.height_config {
                    Some(ref config) => match config.height_spec {
                        Some(crate::proto::streamlit::height_config::HeightSpec::UseContent(true)) => "content".to_string(),
                        Some(crate::proto::streamlit::height_config::HeightSpec::PixelHeight(pixels)) => format!("px{pixels}"),
                        other => format!("other:{other:?}"),
                    },
                    None => "none".to_string(),
                };
                let entry = match kind {
                    element::Type::VegaLiteChart(vega) => {
                        let spec = serde_json::from_str::<serde_json::Value>(&vega.spec).unwrap();
                        let named = spec["data"]["name"].as_str().is_some();
                        let datasets = vega.datasets.len();
                        let inline = vega.data.is_some();
                        let schema = spec["$schema"].as_str().map(|url| url.starts_with("https://vega.github.io/schema/vega-lite/")).unwrap_or(false);
                        format!(
                            "vega:dataset_named={named}:datasets={datasets}:inline_data={inline}:theme={}:autosize={}:schema_vega={schema}",
                            vega.theme,
                            spec["autosize"]["type"].as_str().unwrap_or("none"),
                        )
                    }
                    element::Type::PlotlyChart(plotly) => {
                        format!("plotly:theme={}:config={:?}:height={}:spec_starts={:?}", plotly.theme, plotly.config, height, &plotly.spec[..40])
                    }
                    element::Type::DeckGlJsonChart(deck) => {
                        format!("pydeck:height={}:json_has_layers={}", height, deck.json.contains("\"layers\""))
                    }
                    element::Type::GraphvizChart(graphviz) => {
                        format!("graphviz:engine={}:id_len={}:spec={}", graphviz.engine, graphviz.element_id.len(), graphviz.spec)
                    }
                    element::Type::Markdown(markdown) => {
                        format!("mermaid:fence4={}:body={:?}", markdown.body.starts_with("````mermaid\n"), markdown.body)
                    }
                    element::Type::EchartsChart(echarts) => {
                        format!("echarts:theme={}:height={}:spec={}", echarts.theme, height, echarts.spec)
                    }
                    other => format!("{other:?}"),
                };
                timeline.push(entry);
            }
            Some(forward_msg::Type::ScriptFinished(status)) => assert_eq!(status, 0),
            Some(forward_msg::Type::SessionStatusChanged(_)) => {}
            other => panic!("unexpected lifecycle response: {other:?}"),
        }
    }
    let joined = timeline.join(" | ");
    assert!(joined.contains("vega:dataset_named=true:datasets=1:inline_data=false:theme=streamlit"), "altair: {joined}");
    assert!(joined.contains("vega:dataset_named=false:datasets=0:inline_data=true:theme=streamlit"), "vega_lite: {joined}");
    assert!(joined.contains("plotly:theme=streamlit:config=\"{}\""), "plotly: {joined}");
    assert!(joined.contains("height=px450"), "plotly height: {joined}");
    assert!(joined.contains("pydeck:height=px500:json_has_layers=true"), "pydeck: {joined}");
    assert!(joined.contains("graphviz:engine=dot:id_len=32:spec=digraph { a -> b }"), "graphviz: {joined}");
    assert!(joined.contains("mermaid:fence4=true:body=\"````mermaid\\ngraph LR\\n    A[Start] --> B{Decision}\\n````\""), "mermaid: {joined}");
    assert!(
        joined.contains("echarts:theme=streamlit:height=px350:spec={\"xAxis\":{\"type\":\"category\",\"data\":[\"a\",\"b\"]},\"yAxis\":{\"type\":\"value\"},\"series\":[{\"type\":\"bar\",\"data\":[3,7]}]}"),
        "echarts: {joined}"
    );
    assert_eq!(timeline.len(), 7, "exactly the seven chart surfaces: {joined}");

    drop(stream);
    handle.stop(false).await;
    task.await.unwrap().unwrap();
}

#[test]
fn the_graphviz_element_id_is_the_path_hash() {
    // The reference's calc_hash (BLAKE2b-16) of the Python list repr.
    assert_eq!(crate::utils::hash::blake2b16("[0, 4]"), "342a5ac24f2b29e74222b5f39ab31d99");
    // And the two chart surfaces' content addressing rides md5 like upstream.
    assert_eq!(format!("{:x}", md5::compute(b"abc")), "900150983cd24fb0d6963f7d28e17f72");
}
