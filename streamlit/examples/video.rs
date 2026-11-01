//! Video demo on the measured 1.66.1 wire. Mirrors
//! tests/reference/video_app.py: both sides serve the same committed sample
//! bytes, so the media address is byte-identical across runtimes.
use ::streamlit::*;

const VIDEO_SAMPLE: &[u8] = include_bytes!("data/video_sample.mp4");

#[main(host = "127.0.0.1", port = 8510)]
async fn main(st: &Streamlit) {
    if st.query_params().get("subtitles").as_deref() == Some("1") {
        st.video(
            VideoOptions::new(VIDEO_SAMPLE.to_vec(), "video/mp4")
                .muted(true)
                .loop_(true)
                .subtitle("English", "1\n00:00:00,000 --> 00:00:01,000\nHello SRT")
                .subtitle("中文", "WEBVTT\n\n00:00:00.000 --> 00:00:01.000\n中文字幕"),
        );
    } else {
        st.video((VIDEO_SAMPLE.to_vec(), "video/mp4"));
    }
}
