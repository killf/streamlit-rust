//! audio_input/camera_input parameter edges — the frozen recorder-params
//! reference's calls: an explicit sample rate and the default camera mode.
use ::streamlit::*;
use streamlit::StreamlitApi;

fn render(st: &Streamlit) {
    st.title("Recorder parameter edges");
    let _ = st.audio_input(AudioInputOptions::new("Record note").sample_rate(44100).key("a1"));
    let _ = st.camera_input(CameraInputOptions::new("Take a photo").key("c1"));
}

#[main(host = "127.0.0.1", port = 8605)]
async fn main(st: &Streamlit) {
    render(st);
}
