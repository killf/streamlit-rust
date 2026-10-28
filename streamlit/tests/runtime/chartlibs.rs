//! Library-chart regressions against the measured Python 1.66.1 wire (see
//! .codex/compatibility.md, Chart libraries): the seven surfaces pass the
//! same final payloads the reference produced. st.altair_chart carries the
//! dataset-name indirection spec (schema URL + autosize appended, theme
//! streamlit) with the chart's arrow dataset (content-addressed name, md5 of
//! the IPC bytes); st.vega_lite_chart pulls an inline values list out of the
//! spec into a content-named dataset referenced by spec data.name (accepted
//! A — the measured top-level inline data missed same-shape value changes on
//! the official frontend); st.plotly_chart carries the figure
//! JSON with the config "{}" and the 450px height; st.pydeck_chart carries
//! the deck JSON at 500px; st.graphviz_chart's element id is the reference's
//! calc_hash of the delta-path repr with content sizing; st.mermaid_chart is
//! a fenced markdown block (4-backtick fence, stretch width); st.echarts_chart
//! carries the compact-separator spec at 350px.
use super::*;
use crate::InputWidgets;
use crate::StreamlitApi;
use crate::data::{Field, Int64Array, RecordBatch, Schema, StringArray};
use crate::proto::element;
use crate::proto::forward_msg;
use serde_json::json;
use std::sync::Arc;

fn kind_count_batch() -> TestResult<RecordBatch> {
    let fields = vec![Field::new("kind", crate::data::DataType::Utf8, true), Field::new("count", crate::data::DataType::Int64, true)];
    let kind: Vec<&str> = vec!["a", "b"];
    let arrays = vec![Arc::new(StringArray::from(kind)) as _, Arc::new(Int64Array::from(vec![3, 7])) as _];
    Ok(RecordBatch::try_new(Arc::new(Schema::new(fields)), arrays)?)
}

fn chartlibs_entry(st: &Streamlit) -> Pin<Box<dyn Future<Output = ()> + '_>> {
    Box::pin(async move {
        let result: TestResult = async {
            // Mirrors tests/reference/chartlibs_app.py.
            st.altair_chart(
                json!({"mark": {"type": "bar"}, "encoding": {"x": {"field": "kind", "type": "nominal"}, "y": {"field": "count", "type": "quantitative"}}}),
                &kind_count_batch()?,
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

            Ok(())
        }
        .await;

        assert!(result.is_ok(), "chartlibs fixture must render successfully: {result:?}");
    })
}

#[actix_web::test]
async fn library_charts_match_the_measured_wire() -> TestResult {
    let listener = std::net::TcpListener::bind("127.0.0.1:0")?;
    let address = listener.local_addr()?;
    let server = HttpServer::new(move || App::new().app_data(web::Data::new(StreamlitServer::new(chartlibs_entry, "127.0.0.1".into(), 0))).configure(configure_routes))
        .workers(1)
        .listen(listener)?
        .run();
    let handle = server.handle();
    let task = actix_web::rt::spawn(server);
    let mut stream = TcpStream::connect(address).await?;
    let request = format!("GET /_stcore/stream HTTP/1.1\r\nHost: {address}\r\nConnection: Upgrade\r\nUpgrade: websocket\r\nSec-WebSocket-Version: 13\r\nSec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==\r\nSec-WebSocket-Protocol: streamlit, test-xsrf\r\n\r\n");
    stream.write_all(request.as_bytes()).await?;
    let headers = tokio::time::timeout(Duration::from_secs(5), async {
        let mut response = Vec::new();
        while !response.ends_with(b"\r\n\r\n") {
            response.push(stream.read_u8().await?);
        }
        Ok::<_, Box<dyn std::error::Error>>(String::from_utf8(response)?.to_ascii_lowercase())
    })
    .await??;
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
                        let spec = serde_json::from_str::<serde_json::Value>(&vega.spec)?;
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
    assert!(joined.contains("vega:dataset_named=true:datasets=1:inline_data=false:theme=streamlit:autosize=fit:schema_vega=true"), "altair: {joined}");
    // Accepted A: the generic chart's extracted values ride a content-named
    // dataset like altair's (the top-level inline data missed same-shape
    // value changes on the official frontend); the caller spec carries no
    // $schema, which keeps the two entries distinguishable.
    assert!(joined.contains("vega:dataset_named=true:datasets=1:inline_data=false:theme=streamlit:autosize=fit:schema_vega=false"), "vega_lite: {joined}");
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
    task.await??;

    Ok(())
}

#[test]
fn the_graphviz_element_id_is_the_path_hash() {
    // The reference's calc_hash (BLAKE2b-16) of the Python list repr.
    assert_eq!(crate::utils::hash::blake2b16("[0, 4]"), "342a5ac24f2b29e74222b5f39ab31d99");
    // And the two chart surfaces' content addressing rides md5 like upstream.
    assert_eq!(format!("{:x}", md5::compute(b"abc")), "900150983cd24fb0d6963f7d28e17f72");
}

/// Accepted A regression: same-shape value changes must change the effective
/// update identity. The generic chart's dataset name (md5 of the IPC bytes)
/// and its spec reference change with the values 3 -> 8, stay put across an
/// ordinary rerun, and change back — the four stages the official frontend
/// missed before the fix (see tests/browser/rust-vega-refresh-before).
fn vega_refresh_entry(st: &Streamlit) -> Pin<Box<dyn Future<Output = ()> + '_>> {
    Box::pin(async move {
        let result: TestResult = async {
            let state = st.session_state();
            let count = state.get::<i64>("vega-count")?.unwrap_or(3);
            let count = if st.try_button(crate::ButtonOptions::new("Change Vega data").key("vega-change"))? {
                let toggled = if count == 3 { 8 } else { 3 };
                state.set("vega-count", toggled)?;
                toggled
            } else {
                count
            };
            st.vega_lite_chart(json!({
                "mark": "bar",
                "encoding": {
                    "x": {"field": "kind", "type": "nominal"},
                    "y": {"field": "count", "type": "quantitative"},
                },
                "data": {"values": [{"kind": "a", "count": count}, {"kind": "b", "count": 7}]},
            }));
            Ok(())
        }
        .await;
        assert!(result.is_ok(), "vega refresh fixture failed: {result:?}");
    })
}

#[actix_web::test]
async fn generic_vega_same_shape_updates_change_the_dataset_identity() -> TestResult {
    let listener = std::net::TcpListener::bind("127.0.0.1:0")?;
    let address = listener.local_addr()?;
    let server = HttpServer::new(move || App::new().app_data(web::Data::new(StreamlitServer::new(vega_refresh_entry, "127.0.0.1".into(), 0))).configure(configure_routes))
        .workers(1)
        .listen(listener)?
        .run();
    let handle = server.handle();
    let task = actix_web::rt::spawn(server);
    let mut stream = sessions::connect(address, None).await;
    let mut button_id: Option<String> = None;
    let mut identities = Vec::new();
    for (click, expected) in [(false, 3_i64), (true, 8), (false, 8), (true, 3)] {
        let widgets = match (&button_id, click) {
            (Some(id), true) => vec![WidgetState {
                id: id.clone(),
                value: Some(widget_state::Value::TriggerValue(true)),
            }],
            _ => vec![],
        };
        send_binary(
            &mut stream,
            &(BackMsg {
                r#type: Some(back_msg::Type::RerunScript(ClientState {
                    widget_states: Some(WidgetStates { widgets }),
                    ..Default::default()
                })),
            })
            .encode_to_vec(),
        )
        .await;
        let mut chart = None;
        loop {
            let message = receive(&mut stream).await;
            match message.r#type {
                Some(forward_msg::Type::Delta(delta)) => {
                    if let Some(delta::Type::NewElement(element)) = delta.r#type {
                        match element.r#type {
                            Some(element::Type::Button(button)) => button_id = Some(button.id),
                            Some(element::Type::VegaLiteChart(vega)) => chart = Some(vega),
                            _ => {}
                        }
                    }
                }
                Some(forward_msg::Type::ScriptFinished(status)) => {
                    assert_eq!(status, 0);
                    break;
                }
                _ => {}
            }
        }
        let vega = chart.ok_or("the generic chart must render every run")?;
        assert!(button_id.as_deref().is_some_and(|id| id.ends_with("-vega-change")));
        assert!(vega.data.is_none() && vega.datasets.len() == 1, "the values ride one named dataset");
        let dataset = &vega.datasets[0];
        assert!(dataset.has_name);
        let spec: serde_json::Value = serde_json::from_str(&vega.spec)?;
        assert_eq!(spec["data"]["name"].as_str(), Some(dataset.name.as_str()), "the spec references the dataset by name");
        let batch = crate::data::from_ipc_stream(&dataset.data.as_ref().ok_or("dataset must carry arrow data")?.data)?.remove(0);
        let column = batch.column(1).as_any().downcast_ref::<Int64Array>().ok_or("count column must stay int64")?;
        let counts: Vec<i64> = (0..batch.num_rows()).map(|row| column.value(row)).collect();
        assert_eq!(counts, vec![expected, 7]);
        identities.push((expected, dataset.name.clone()));
    }
    drop(stream);
    handle.stop(false).await;
    task.await??;
    let name = |value: i64| identities.iter().find(|(expected, _)| *expected == value).map(|(_, name)| name.clone()).ok_or("missing identity");
    assert_ne!(name(3)?, name(8)?, "same-shape value changes must change the dataset identity");
    assert_eq!(identities[0].1, name(3)?);
    assert_eq!(identities[2].1, name(8)?, "an ordinary rerun keeps the identity");
    Ok(())
}
