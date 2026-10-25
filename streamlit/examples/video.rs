//! Video demo on the measured 1.66.1 wire. Mirrors
//! tests/reference/video_app.py: both sides serve the same committed sample
//! bytes, so the media address is byte-identical across runtimes.
use ::streamlit::*;

const VIDEO_SAMPLE: &[u8] = include_bytes!("../../tests/reference/video_sample.mp4");

#[tokio::main]
async fn main() -> std::io::Result<()> {
    StreamlitServer::new(
        |st| {
            Box::pin(async move {
                st.video((VIDEO_SAMPLE.to_vec(), "video/mp4"));
            })
        },
        "127.0.0.1".into(),
        8510,
    )
    .start()
    .await
}
