//! Audio/video playback parameters: start/end times, loop, autoplay, muted,
//! text subtitles, and the format-driven URL suffix — the frozen
//! media-params reference's six calls plus the invalid-subtitle rejection.
use ::streamlit::*;

fn tone() -> Vec<u8> {
    // A one-second silent mono 16-bit 8 kHz WAV, built like the fixture.
    let mut wav = Vec::new();
    wav.extend_from_slice(b"RIFF");
    let data_len = 1600u32;
    let riff_len = 36 + data_len;
    wav.extend_from_slice(&riff_len.to_le_bytes());
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

fn render(st: &Streamlit) {
    st.title("Media parameters");
    st.audio(AudioOptions::new(tone(), "audio/wav"));
    st.audio(AudioOptions::new(tone(), "audio/wav").autoplay(true).loop_(true).start_time(1.5).end_time(3.0));
    st.audio(AudioOptions::new(tone(), "audio/x-wav"));
    st.video(VideoOptions::new(video(), "video/mp4"));
    st.video(VideoOptions::new(video(), "video/mp4").autoplay(true).muted(true).loop_(true).start_time(2.0).end_time(4.0));
    st.video(VideoOptions::new(video(), "video/mp4").subtitle("en", "WEBVTT\n\n00:00:00.000 --> 00:00:02.000\nHello"));
    st.video(VideoOptions::new(video(), "video/mp4").subtitle("en", "data:application/vtt;base64,ZW4="));
}

#[main(host = "127.0.0.1", port = 8593)]
async fn main(st: &Streamlit) {
    render(st);
}
