//! Column-config regressions against the measured Python 1.66.1 wire (see
//! .codex/compatibility.md, Column config): the 21-helper mapping serializes
//! byte-for-byte as the reference's single columns JSON string, each button
//! column registers one click widget (`$$ID-<digest>-<key>`, masked in the
//! browser traces) on the dataframe proto's button_click_widgets, and the
//! data_editor rides the hidden `_index`, the dynamic editing mode and its
//! own edits widget id.
use super::*;
use crate::DataApi;
use crate::column_config as cc;
use crate::data::{Field, Int64Array, RecordBatch, Schema, StringArray};
use serde_json::json;
use std::sync::Arc;

fn text_batch(names: &[&str]) -> RecordBatch {
    let fields: Vec<_> = names.iter().map(|name| Field::new(*name, crate::data::DataType::Utf8, true)).collect();
    let arrays: Vec<_> = names.iter().map(|name| Arc::new(StringArray::from(vec![format!("{name}-1"), format!("{name}-2")])) as _).collect();
    RecordBatch::try_new(Arc::new(Schema::new(fields)), arrays).unwrap()
}

fn qty_batch() -> RecordBatch {
    let fields = vec![Field::new("qty", crate::data::DataType::Int64, true)];
    let arrays = vec![Arc::new(Int64Array::from(vec![1, 2])) as _];
    RecordBatch::try_new(Arc::new(Schema::new(fields)), arrays).unwrap()
}

fn colconfig_entry(st: &Streamlit) -> Pin<Box<dyn Future<Output = ()> + '_>> {
    Box::pin(async move {
        // Mirrors tests/reference/colconfig_app.py and examples/colconfig.rs.
        let configs = crate::ColumnConfigs::new()
            .add("name", cc::column(crate::ColumnBase::new(Some("Name")).width("medium").help("the name").pinned(true).alignment("center")))
            .add("title", cc::text_column(crate::ColumnBase::new(Some("Title")), Some("hi"), Some(10), Some(r"^h")))
            .add("score", cc::number_column(crate::ColumnBase::new(Some("Score")), Some(json!(1)), Some("%d"), Some(json!(0)), Some(json!(10)), Some(json!(1))))
            .add("done", cc::checkbox_column(crate::ColumnBase::new(Some("Done"))).default_value(json!(true)))
            .add("kind", cc::selectbox_column(crate::ColumnBase::new(Some("Kind")), Some("a"), &["a", "b"]))
            .add("tags", cc::multiselect_column(crate::ColumnBase::new(Some("Tags")), Some(vec!["x"]), &["x", "y"], Some(true)))
            .add("day", cc::date_column(crate::ColumnBase::new(Some("Day")), Some("2025-01-02"), Some("YYYY/MM/DD"), Some("2024-01-01"), Some("2026-01-01"), Some(1)))
            .add(
                "moment",
                cc::datetime_column(
                    crate::ColumnBase::new(Some("Moment")),
                    Some("2025-01-02T03:04:00"),
                    Some("YYYY/MM/DD HH:mm"),
                    Some("2024-01-01T00:00:00"),
                    Some("2026-01-01T00:00:00"),
                    Some(json!(60)),
                    Some("UTC"),
                ),
            )
            .add("clock", cc::time_column(crate::ColumnBase::new(Some("Clock")), Some("03:04:00"), Some("HH:mm"), Some("01:00:00"), Some("23:00:00"), Some(json!(60))))
            .add("items", cc::list_column(crate::ColumnBase::new(Some("Items"))).default_value(json!(["a"])))
            .add("payload", cc::json_column(crate::ColumnBase::new(Some("Payload"))))
            .add("notes", cc::markdown_column(crate::ColumnBase::new(Some("Notes"))).default_value(json!("**bold**")))
            .add("site", cc::link_column(crate::ColumnBase::new(Some("Site")), Some("https://example.com"), Some(40), Some(r"^https"), Some("open")))
            .add("pic", cc::image_column(crate::ColumnBase::new(Some("Pic"))))
            .add("trend", cc::area_chart_column(crate::ColumnBase::new(Some("Trend")), Some(json!(0)), Some(json!(10)), Some("#ff0000")))
            .add("count", cc::bar_chart_column(crate::ColumnBase::new(Some("Count")), Some(json!(0)), Some(json!(10)), Some("#00ff00")))
            .add("signal", cc::line_chart_column(crate::ColumnBase::new(Some("Signal")), Some(json!(0)), Some(json!(10)), Some("#0000ff")))
            .add("fill", cc::progress_column(crate::ColumnBase::new(Some("Fill")), Some("%d"), Some(json!(0)), Some(json!(100)), Some(json!(1)), Some("green")))
            .add("clip", cc::audio_column(crate::ColumnBase::new(Some("Clip"))))
            .add("reel", cc::video_column(crate::ColumnBase::new(Some("Reel"))))
            .add("act", cc::button_column(crate::ColumnBase::new(Some("Act")), Some("primary"), Some("act")));
        st.dataframe(
            crate::DataframeOptions::new(&text_batch(&[
                "name", "title", "score", "done", "kind", "tags", "day", "moment", "clock", "items", "payload", "notes", "site", "pic", "trend", "count", "signal", "fill", "clip", "reel", "act",
            ]))
            .column_config(configs),
        )
        .unwrap();
        st.data_editor(crate::DataEditorOptions::new(&qty_batch()).num_rows(crate::EditorRows::Dynamic).key("editor")).unwrap();
        st.write("edits=(2, 1)");
    })
}

#[actix_web::test]
async fn column_config_and_editor_match_the_measured_wire() {
    let listener = std::net::TcpListener::bind("127.0.0.1:0").unwrap();
    let address = listener.local_addr().unwrap();
    let server = HttpServer::new(move || App::new().app_data(web::Data::new(StreamlitServer::new(colconfig_entry, "127.0.0.1".into(), 0))).configure(configure_routes))
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

    let mut dataframes = Vec::new();
    let mut trailing = String::new();
    loop {
        let message = receive(&mut stream).await;
        match message.r#type {
            Some(forward_msg::Type::NewSession(_)) => {}
            Some(forward_msg::Type::SessionStatusChanged(status)) if !status.script_is_running => break,
            Some(forward_msg::Type::Delta(delta)) => {
                let Some(delta::Type::NewElement(element)) = delta.r#type else { continue };
                match element.r#type {
                    Some(element::Type::Dataframe(frame)) => dataframes.push(frame),
                    Some(element::Type::Markdown(markdown)) => trailing = markdown.body,
                    _ => {}
                }
            }
            Some(forward_msg::Type::ScriptFinished(status)) => assert_eq!(status, 0),
            Some(forward_msg::Type::SessionStatusChanged(_)) => {}
            other => panic!("unexpected lifecycle response: {other:?}"),
        }
    }
    assert_eq!(dataframes.len(), 2, "the configured dataframe and the editor");
    assert_eq!(trailing, "edits=(2, 1)");

    let configured = &dataframes[0];
    assert_eq!(configured.columns, include_str!("../../../tests/reference/colconfig-columns.json"), "the 21-helper columns JSON, byte for byte");
    assert_eq!(configured.button_click_widgets.len(), 1, "one click widget for the act column");
    let button_id = &configured.button_click_widgets["act"];
    let digest = button_id.strip_prefix("$$ID-").and_then(|rest| rest.strip_suffix("-act")).unwrap_or_default();
    assert_eq!(digest.len(), 32, "the reference's fast-hash digest length: {button_id}");
    assert!(digest.chars().all(|c| c.is_ascii_hexdigit()), "hex digest: {button_id}");
    assert!(configured.id.is_empty(), "a plain dataframe carries no edits widget id");

    let editor = &dataframes[1];
    assert_eq!(editor.columns, r#"{"_index": {"hidden": true}}"#, "the editor hides the index by default");
    assert_eq!(editor.editing_mode, 2, "num_rows=dynamic");
    assert!(!editor.disabled);
    assert!(editor.button_click_widgets.is_empty(), "no button columns configured");
    let editor_id = editor.id.strip_prefix("$$ID-").and_then(|rest| rest.strip_suffix("-editor")).unwrap_or_default();
    assert_eq!(editor_id.len(), 32, "the edits widget id: {}", editor.id);

    drop(stream);
    handle.stop(false).await;
    task.await.unwrap().unwrap();
}
