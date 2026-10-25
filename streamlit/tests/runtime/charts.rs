//! Chart regressions against the measured Python 1.66.1 wire: the line,
//! area and scatter charts serialize byte-identical spec strings, dataset
//! names and Arrow IPC bytes, and the map serializes the measured deck.gl
//! JSON (see .codex/compatibility.md, Charts).
use super::*;
use crate::data_api::DataApi;
use crate::{MapOptions, ScatterChartOptions, data::Float64Array};

#[path = "charts_expected.rs"]
mod charts_expected;

fn int64_batch(columns: &[(&str, Vec<i64>)]) -> crate::data::RecordBatch {
    let fields: Vec<_> = columns.iter().map(|(name, _)| crate::data::Field::new(*name, crate::data::DataType::Int64, false)).collect();
    let arrays: Vec<_> = columns.iter().map(|(_, values)| std::sync::Arc::new(crate::data::Int64Array::from(values.clone())) as crate::data::ArrayRef).collect();
    crate::data::RecordBatch::try_new(std::sync::Arc::new(crate::data::Schema::new(fields)), arrays).unwrap()
}

fn float64_batch(columns: &[(&str, Vec<f64>)]) -> crate::data::RecordBatch {
    let fields: Vec<_> = columns.iter().map(|(name, _)| crate::data::Field::new(*name, crate::data::DataType::Float64, false)).collect();
    let arrays: Vec<_> = columns.iter().map(|(_, values)| std::sync::Arc::new(Float64Array::from(values.clone())) as crate::data::ArrayRef).collect();
    crate::data::RecordBatch::try_new(std::sync::Arc::new(crate::data::Schema::new(fields)), arrays).unwrap()
}

fn charts_entry(st: &Streamlit) -> Pin<Box<dyn Future<Output = ()> + '_>> {
    Box::pin(async move {
        // Mirrors tests/reference/charts_app.py.
        st.line_chart(&int64_batch(&[("value", vec![2, 1, 3])])).unwrap();
        st.area_chart(&int64_batch(&[("alpha", vec![1, 2, 3]), ("beta", vec![3, 2, 1])])).unwrap();
        st.scatter_chart(ScatterChartOptions::new(&int64_batch(&[("x", vec![1, 2, 3]), ("y", vec![3, 1, 2])]), "x", "y")).unwrap();
        st.map(MapOptions::new(&float64_batch(&[("lat", vec![40.7, 41.0]), ("lon", vec![-74.0, -73.9])]))).unwrap();
    })
}

async fn collect_chart_elements() -> Vec<crate::proto::Element> {
    let listener = std::net::TcpListener::bind("127.0.0.1:0").unwrap();
    let address = listener.local_addr().unwrap();
    let server = HttpServer::new(move || App::new().app_data(web::Data::new(StreamlitServer::new(charts_entry, "127.0.0.1".into(), 0))).configure(configure_routes))
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
            assert!(response.len() < 8192);
        }
        String::from_utf8(response).unwrap().to_ascii_lowercase()
    })
    .await
    .unwrap();
    assert!(headers.starts_with("http/1.1 101"));
    let request = BackMsg {
        r#type: Some(back_msg::Type::RerunScript(ClientState {
            widget_states: Some(WidgetStates { widgets: vec![] }),
            ..Default::default()
        })),
    };
    send_binary(&mut stream, &request.encode_to_vec()).await;
    assert!(matches!(receive(&mut stream).await.r#type, Some(forward_msg::Type::NewSession(_))));
    assert!(matches!(receive(&mut stream).await.r#type, Some(forward_msg::Type::SessionStatusChanged(_))));
    let mut elements = Vec::new();
    loop {
        match receive(&mut stream).await.r#type {
            Some(forward_msg::Type::Delta(delta)) => {
                if let Some(delta::Type::NewElement(element)) = delta.r#type {
                    elements.push(element);
                }
            }
            Some(forward_msg::Type::ScriptFinished(status)) => assert_eq!(status, 0),
            Some(forward_msg::Type::SessionStatusChanged(status)) if !status.script_is_running => break,
            other => panic!("unexpected lifecycle response: {other:?}"),
        }
    }
    drop(stream);
    handle.stop(false).await;
    task.await.unwrap().unwrap();
    elements
}

fn oracle(name: &str) -> Vec<u8> {
    std::fs::read(std::path::Path::new(env!("CARGO_MANIFEST_DIR")).join("../tests/reference").join(name)).unwrap()
}

fn stretch_width(element: &crate::proto::Element) -> bool {
    matches!(element.width_config.as_ref().and_then(|config| config.width_spec.as_ref()), Some(crate::proto::streamlit::width_config::WidthSpec::UseStretch(_)))
}

#[actix_web::test]
async fn charts_match_the_measured_wire_byte_for_byte() {
    let elements = collect_chart_elements().await;
    assert_eq!(elements.len(), 4, "three vega charts then the map");

    let expected_specs = [
        (charts_expected::LINE_SPEC, charts_expected::LINE_DATASET, "chart-line.arrow"),
        (charts_expected::AREA_SPEC, charts_expected::AREA_DATASET, "chart-area.arrow"),
        (charts_expected::SCATTER_SPEC, charts_expected::SCATTER_DATASET, "chart-scatter.arrow"),
    ];
    for (index, (expected_spec, expected_name, oracle_file)) in expected_specs.iter().enumerate() {
        let Some(element::Type::VegaLiteChart(chart)) = elements[index].r#type.as_ref() else {
            panic!("element {index} is not a vega chart: {:?}", elements[index].r#type);
        };
        let served = &chart.datasets[0].data.as_ref().expect("dataset data").data;
        // The reference names each dataset calc_hash(str(arrow_bytes)); the
        // Rust writer's IPC bytes differ from pyarrow's at the flatbuffer
        // layout level, so byte identity stops at the naming formula: the
        // served name must be the formula over the served bytes, and the
        // spec must be the measured string under that name.
        assert_eq!(chart.datasets[0].name, crate::pywire::dataset_name(served));
        assert_eq!(chart.datasets[0].name.len(), 32);
        assert_eq!(
            chart.spec.replace(&chart.datasets[0].name, expected_name),
            *expected_spec,
            "the {} spec differs from the measured wire beyond the dataset name",
            oracle_file
        );
        let served_batches = crate::data::from_ipc_stream(served).expect("the served dataset decodes");
        let oracle_batches = crate::data::from_ipc_stream(&oracle(oracle_file)).expect("the oracle dataset decodes");
        assert_eq!(served_batches, oracle_batches, "the {} dataset differs from the reference frame", oracle_file);
        assert!(chart.datasets[0].has_name);
        assert_eq!(chart.theme, "streamlit");
        assert!(stretch_width(&elements[index]));
        assert!(matches!(
            elements[index].height_config.as_ref().and_then(|config| config.height_spec.as_ref()),
            Some(crate::proto::streamlit::height_config::HeightSpec::UseContent(_))
        ));
    }

    let Some(element::Type::DeckGlJsonChart(deck)) = elements[3].r#type.as_ref() else {
        panic!("element 3 is not a deck chart: {:?}", elements[3].r#type);
    };
    assert_eq!(deck.json, charts_expected::DECK_JSON);
    assert_eq!(deck.id, "");
    assert_eq!(deck.mapbox_token, "");
    assert!(stretch_width(&elements[3]));
    assert!(matches!(
        elements[3].height_config.as_ref().and_then(|config| config.height_spec.as_ref()),
        Some(crate::proto::streamlit::height_config::HeightSpec::PixelHeight(height)) if *height == 500
    ));
}

/// Render one map through the element pipeline and return the deck json
/// string (no server round trip needed for a pure serialization check).
fn map_deck_json(columns: &[(&'static str, Vec<f64>)]) -> String {
    let st = Streamlit::new();
    let (sender, mut receiver) = tokio::sync::mpsc::unbounded_channel();
    let mut context = crate::elements::common::RenderContext::with_sender("charts-test".into(), sender);
    context.delta_path = vec![0, 0];
    st.app.lock().set_render_context(context);
    st.map(&float64_batch(columns)).unwrap();
    let message = receiver.try_recv().unwrap();
    let decoded = ForwardMsg::decode(message.encode_to_vec().as_slice()).unwrap();
    let Some(forward_msg::Type::Delta(delta)) = decoded.r#type else { panic!("missing delta") };
    let Some(delta::Type::NewElement(element)) = delta.r#type else { panic!("missing element") };
    let Some(element::Type::DeckGlJsonChart(chart)) = element.r#type else { panic!("missing deck chart") };
    chart.json
}

fn zoom_of(deck_json: &str) -> i64 {
    serde_json::from_str::<serde_json::Value>(deck_json)
        .expect("deck json parses")
        .pointer("/initialViewState/zoom")
        .and_then(|value| value.as_i64())
        .expect("zoom")
}

#[test]
fn map_zoom_ladder_and_empty_frame_match_the_pinned_reference() {
    // The measured page only exercises distance 0.3 (zoom 10); the ladder
    // tail below 0.003 degrees diverged from the reference before it was
    // pinned, so the tail is frozen here against map.py's own bisect.
    let street = map_deck_json(&[("lat", vec![40.7000, 40.7004]), ("lon", vec![-74.0, -74.0])]);
    assert_eq!(zoom_of(&street), 19, "distance 0.0004 must bisect to street level");
    let block = map_deck_json(&[("lat", vec![40.7000, 40.7027]), ("lon", vec![-74.0, -74.0])]);
    assert_eq!(zoom_of(&block), 17, "distance 0.0027 must bisect to 17");
    let tight = map_deck_json(&[("lat", vec![40.7000, 40.7012]), ("lon", vec![-74.0, -74.0])]);
    assert_eq!(zoom_of(&tight), 17, "distance 0.0012 must bisect to 17");
    let cluster = map_deck_json(&[("lat", vec![40.7000, 40.7001]), ("lon", vec![-74.0, -74.0])]);
    assert_eq!(zoom_of(&cluster), 12, "a distance off the ladder tail falls back to the default zoom");
    // An empty frame serializes the reference's fixed EMPTY_MAP verbatim.
    let empty = map_deck_json(&[("lat", vec![]), ("lon", vec![])]);
    assert_eq!(empty, "{\"initialViewState\": {\"latitude\": 0, \"longitude\": 0, \"pitch\": 0, \"zoom\": 1}}");
}
