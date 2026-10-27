//! Column-config and data-editor demo: one dataframe carrying all 21
//! column-config helpers plus a data_editor. Mirrors
//! tests/reference/colconfig_app.py, including the typed frame columns.
use ::streamlit::*;
use std::sync::Arc;

use arrow_array::{BooleanArray, Date32Array, Int64Array, ListArray, StringArray, StructArray, Time64MicrosecondArray, TimestampMicrosecondArray};
use arrow_buffer::{OffsetBuffer, ScalarBuffer};
use serde_json::json;
use streamlit::column_config as cc;
use streamlit::data::{DataType, Field, RecordBatch, Schema};
use streamlit::{ColumnBase, ColumnConfigs, DataApi, DataEditorOptions, DataframeOptions, EditorRows, StreamlitApi};

fn wide_batch() -> anyhow::Result<RecordBatch> {
    // The 21 configured columns typed like the python fixture's frame:
    // utf8 text, int64 counters, bool, date32, timestamp[us], time64[us],
    // list<string> and one struct column.
    let text = |values: [&str; 2]| Arc::new(StringArray::from(values.to_vec())) as arrow_array::ArrayRef;
    let int = |values: [i64; 2]| Arc::new(Int64Array::from(values.to_vec())) as arrow_array::ArrayRef;
    let item = Arc::new(Field::new("item", DataType::Utf8, true));
    let fields = vec![
        Field::new("name", DataType::Utf8, true),
        Field::new("title", DataType::Utf8, true),
        Field::new("score", DataType::Int64, true),
        Field::new("done", DataType::Boolean, true),
        Field::new("kind", DataType::Utf8, true),
        Field::new("tags", DataType::List(item.clone()), true),
        Field::new("day", DataType::Date32, true),
        Field::new("moment", DataType::Timestamp(arrow_schema::TimeUnit::Microsecond, None), true),
        Field::new("clock", DataType::Time64(arrow_schema::TimeUnit::Microsecond), true),
        Field::new("items", DataType::List(item.clone()), true),
        Field::new("payload", DataType::Struct(vec![Field::new("k", DataType::Int64, true)].into()), true),
        Field::new("notes", DataType::Utf8, true),
        Field::new("site", DataType::Utf8, true),
        Field::new("pic", DataType::Utf8, true),
        Field::new("trend", DataType::Int64, true),
        Field::new("count", DataType::Int64, true),
        Field::new("signal", DataType::Int64, true),
        Field::new("fill", DataType::Int64, true),
        Field::new("clip", DataType::Utf8, true),
        Field::new("reel", DataType::Utf8, true),
        Field::new("act", DataType::Utf8, true),
    ];
    let list = |offsets: Vec<i32>, items: Vec<&str>| {
        let values = Arc::new(StringArray::from(items)) as arrow_array::ArrayRef;
        Arc::new(ListArray::new(item.clone(), OffsetBuffer::new(ScalarBuffer::from(offsets)), values, None)) as arrow_array::ArrayRef
    };
    let payload = {
        // struct<k: int64> column: each row one struct.
        let inner: Vec<arrow_array::ArrayRef> = vec![Arc::new(Int64Array::from(vec![1, 2]))];
        let array = StructArray::new(vec![Field::new("k", DataType::Int64, true)].into(), inner, None);
        Arc::new(array) as arrow_array::ArrayRef
    };
    let arrays = vec![
        text(["alpha", "beta"]),
        text(["Chief", "Deputy"]),
        int([1, 2]),
        Arc::new(BooleanArray::from(vec![true, false])) as _,
        text(["a", "b"]),
        list(vec![0, 1, 2], vec!["x", "y"]),
        Arc::new(Date32Array::from(vec![20090, 20122])) as _,
        Arc::new(TimestampMicrosecondArray::from(vec![1735787040000000, 1738555500000000])) as _,
        Arc::new(Time64MicrosecondArray::from(vec![11040000000, 14700000000])) as _,
        list(vec![0, 2, 3], vec!["a", "b", "c"]),
        payload,
        text(["**bold**", "plain"]),
        text(["https://example.com", "https://example.org"]),
        text(["a", "b"]),
        int([1, 2]),
        int([3, 4]),
        int([5, 6]),
        int([50, 60]),
        text(["c1", "c2"]),
        text(["r1", "r2"]),
        text(["go", "stop"]),
    ];
    Ok(RecordBatch::try_new(Arc::new(Schema::new(fields)), arrays)?)
}

fn qty_batch() -> anyhow::Result<RecordBatch> {
    let fields = vec![Field::new("qty", DataType::Int64, true)];
    let arrays = vec![Arc::new(Int64Array::from(vec![1, 2])) as _];
    Ok(RecordBatch::try_new(Arc::new(Schema::new(fields)), arrays)?)
}

fn render(st: &Streamlit) -> anyhow::Result<()> {
    let configs = ColumnConfigs::new()
        .add("name", cc::column(ColumnBase::new(Some("Name")).width("medium").help("the name").pinned(true).alignment("center")))
        .add("title", cc::text_column(ColumnBase::new(Some("Title")), Some("hi"), Some(10), Some(r"^h")))
        .add("score", cc::number_column(ColumnBase::new(Some("Score")), Some(json!(1)), Some("%d"), Some(json!(0)), Some(json!(10)), Some(json!(1))))
        .add("done", cc::checkbox_column(ColumnBase::new(Some("Done"))).default_value(json!(true)))
        .add("kind", cc::selectbox_column(ColumnBase::new(Some("Kind")), Some("a"), &["a", "b"]))
        .add("tags", cc::multiselect_column(ColumnBase::new(Some("Tags")), Some(vec!["x"]), &["x", "y"], Some(true)))
        .add("day", cc::date_column(ColumnBase::new(Some("Day")), Some("2025-01-02"), Some("YYYY/MM/DD"), Some("2024-01-01"), Some("2026-01-01"), Some(1)))
        .add(
            "moment",
            cc::datetime_column(
                ColumnBase::new(Some("Moment")),
                Some("2025-01-02T03:04:00"),
                Some("YYYY/MM/DD HH:mm"),
                Some("2024-01-01T00:00:00"),
                Some("2026-01-01T00:00:00"),
                Some(json!(60)),
                Some("UTC"),
            ),
        )
        .add("clock", cc::time_column(ColumnBase::new(Some("Clock")), Some("03:04:00"), Some("HH:mm"), Some("01:00:00"), Some("23:00:00"), Some(json!(60))))
        .add("items", cc::list_column(ColumnBase::new(Some("Items"))).default_value(json!(["a"])))
        .add("payload", cc::json_column(ColumnBase::new(Some("Payload"))))
        .add("notes", cc::markdown_column(ColumnBase::new(Some("Notes"))).default_value(json!("**bold**")))
        .add("site", cc::link_column(ColumnBase::new(Some("Site")), Some("https://example.com"), Some(40), Some(r"^https"), Some("open")))
        .add("pic", cc::image_column(ColumnBase::new(Some("Pic"))))
        .add("trend", cc::area_chart_column(ColumnBase::new(Some("Trend")), Some(json!(0)), Some(json!(10)), Some("#ff0000")))
        .add("count", cc::bar_chart_column(ColumnBase::new(Some("Count")), Some(json!(0)), Some(json!(10)), Some("#00ff00")))
        .add("signal", cc::line_chart_column(ColumnBase::new(Some("Signal")), Some(json!(0)), Some(json!(10)), Some("#0000ff")))
        .add("fill", cc::progress_column(ColumnBase::new(Some("Fill")), Some("%d"), Some(json!(0)), Some(json!(100)), Some(json!(1)), Some("green")))
        .add("clip", cc::audio_column(ColumnBase::new(Some("Clip"))))
        .add("reel", cc::video_column(ColumnBase::new(Some("Reel"))))
        .add("act", cc::button_column(ColumnBase::new(Some("Act")), Some("primary"), Some("act")));

    st.dataframe(DataframeOptions::new(&wide_batch()?).column_config(configs))?;

    let _edits = st.data_editor(DataEditorOptions::new(&qty_batch()?).num_rows(EditorRows::Dynamic).key("editor"))?;
    st.write(format!("edits=({}, {})", qty_batch()?.num_rows(), qty_batch()?.num_columns()));
    Ok(())
}

#[tokio::main]
async fn main() -> std::io::Result<()> {
    StreamlitServer::new(
        |st| {
            Box::pin(async move {
                if let Err(error) = render(st) {
                    st.write(format!("Example error: {error}"));
                }
            })
        },
        "127.0.0.1".into(),
        8529,
    )
    .start()
    .await
}
