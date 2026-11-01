//! Video demo on the measured 1.66.1 wire. Mirrors
//! tests/reference/video_app.py: both sides serve the same committed sample
//! bytes, so the media address is byte-identical across runtimes.
use ::streamlit::*;

const VIDEO_SAMPLE: &[u8] = include_bytes!("data/video_sample.mp4");

#[main(host = "127.0.0.1", port = 8510)]
async fn main(st: &Streamlit) {
    // 1. 查询开关只选择字幕测试数据，默认视频调用保持独立。
    let mode = st.query_params().get("subtitles");
    if matches!(mode.as_deref(), Some("1" | "timed")) {
        let english = if mode.as_deref() == Some("timed") {
            "1\n00:00:00,000 --> 00:00:00,400\nFirst cue\n\n2\n00:00:00,600 --> 00:00:00,900\nSecond cue"
        } else {
            "1\n00:00:00,000 --> 00:00:01,000\nHello SRT"
        };

        // 2. 两个场景复用同一视频和播放参数。
        st.video(
            VideoOptions::new(VIDEO_SAMPLE.to_vec(), "video/mp4")
                .muted(true)
                .loop_(true)
                .subtitle("English", english)
                .subtitle("中文", "WEBVTT\n\n00:00:00.000 --> 00:00:01.000\n中文字幕"),
        );
    } else {
        st.video((VIDEO_SAMPLE.to_vec(), "video/mp4"));
    }
}
