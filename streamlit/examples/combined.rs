//! Cross-capability combination page — the M7 combined differential's Rust
//! side, mirroring tests/reference/combined_app.py call for call.
use ::streamlit::*;
use std::sync::Arc;

use streamlit::StreamlitApi;
use streamlit::data::{ArrayRef, Int64Array, LargeStringArray, RecordBatch};

fn tone() -> Vec<u8> {
    let mut wav = Vec::new();
    wav.extend_from_slice(b"RIFF");
    let data_len = 1600u32;
    wav.extend_from_slice(&(36 + data_len).to_le_bytes());
    wav.extend_from_slice(b"WAVEfmt ");
    wav.extend_from_slice(&16u32.to_le_bytes());
    wav.extend_from_slice(&1u16.to_le_bytes());
    wav.extend_from_slice(&1u16.to_le_bytes());
    wav.extend_from_slice(&8000u32.to_le_bytes());
    wav.extend_from_slice(&16000u32.to_le_bytes());
    wav.extend_from_slice(&2u16.to_le_bytes());
    wav.extend_from_slice(&16u16.to_le_bytes());
    wav.extend_from_slice(b"data");
    wav.extend_from_slice(&data_len.to_le_bytes());
    wav.extend(std::iter::repeat_n(0u8, 1600));
    wav
}

fn video() -> Vec<u8> {
    b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp42isom\x00\x00\x00\x08free".to_vec()
}

fn frame() -> Result<RecordBatch, arrow_schema::ArrowError> {
    RecordBatch::try_from_iter(vec![("kind", Arc::new(LargeStringArray::from(vec!["a", "b"])) as ArrayRef), ("count", Arc::new(Int64Array::from(vec![3, 7])) as ArrayRef)])
}

fn render(st: &Streamlit) -> Result<(), Box<dyn std::error::Error>> {
    st.title("Combined page");
    st.caption("cross-capability differential");
    let expander = st.expander_options(ExpanderOptions::new("Compact").icon(":material/add:").kind(ExpanderKind::Compact));
    expander.write("expander body");
    expander.code("print('combined')", "python");
    let columns = st.columns(ColumnsOptions::new(vec![3.0, 1.0]).gap(Gap::Large).border(true).vertical_alignment(VerticalAlignment::Center));
    {
        let left = &columns[0];
        left.markdown("left column");
        left.dataframe(&frame()?)?;
        let right = &columns[1];
        right.metric(MetricOptions::new("Temperature", "72 °F").delta("2 °F"));
    }
    let tabs = st.tabs(TabsOptions::new(["Alpha", "Beta"]).default_tab("Beta"));
    tabs[0].vega_lite_chart(serde_json::json!({
        "mark": "bar",
        "encoding": {"x": {"field": "g", "type": "nominal"}, "y": {"field": "c", "type": "quantitative"}},
        "data": {"values": [{"g": "x", "c": 2}, {"g": "y", "c": 5}]},
    }));
    tabs[1].vega_lite_chart(serde_json::json!({
        "mark": "bar",
        "encoding": {"x": {"field": "k", "type": "nominal"}, "y": {"field": "v", "type": "quantitative"}},
        "data": {"values": [{"k": "m", "v": 4}, {"k": "n", "v": 9}]},
    }));
    let popover = st.popover_options(PopoverOptions::new("Primary").kind(PopoverKind::Primary).use_container_width(true));
    popover.audio(AudioOptions::new(tone(), "audio/wav").autoplay(true).loop_(true).start_time(1.5).end_time(3.0));
    let status = st.status(StatusContainerOptions::new("Working").expanded(false));
    status.video(VideoOptions::new(video(), "video/mp4").autoplay(true).muted(true).start_time(2.0).end_time(4.0));
    status.update(Some("Done".into()), Some(StatusState::Complete), Some(false));
    st.toast(ToastOptions::new("combined done").duration(10));
    Ok(())
}

#[main(host = "127.0.0.1", port = 8596)]
async fn main(st: &Streamlit) {
    if let Err(error) = render(st) {
        st.write(format!("Combined example error: {error}"));
    }
}
