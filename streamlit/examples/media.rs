//! Media demo: image, audio, metric and progress on the measured 1.66.1
//! wire. Mirrors tests/reference/media_app.py so the browser differential
//! compares identical pages; the gradient and the WAV are synthesized the
//! way the fixture synthesizes them.
use ::streamlit::*;

fn wav_bytes() -> Vec<u8> {
    let samples: Vec<i16> = (0..11025).map(|index| (20000.0 * (2.0 * std::f64::consts::PI * 440.0 * index as f64 / 22050.0).sin()) as i16).collect();
    let mut data = Vec::with_capacity(samples.len() * 2);
    for sample in samples {
        data.extend_from_slice(&sample.to_le_bytes());
    }
    let mut wav = Vec::with_capacity(44 + data.len());
    wav.extend_from_slice(b"RIFF");
    wav.extend_from_slice(&(36 + data.len() as u32).to_le_bytes());
    wav.extend_from_slice(b"WAVEfmt ");
    wav.extend_from_slice(&16u32.to_le_bytes());
    wav.extend_from_slice(&1u16.to_le_bytes());
    wav.extend_from_slice(&1u16.to_le_bytes());
    wav.extend_from_slice(&22050u32.to_le_bytes());
    wav.extend_from_slice(&44100u32.to_le_bytes());
    wav.extend_from_slice(&2u16.to_le_bytes());
    wav.extend_from_slice(&16u16.to_le_bytes());
    wav.extend_from_slice(b"data");
    wav.extend_from_slice(&(data.len() as u32).to_le_bytes());
    wav.extend_from_slice(&data);
    wav
}

fn gradient() -> RgbaImage {
    let value = |index: usize| (4 * index % 256) as u8;
    let mut pixels = Vec::with_capacity(256);
    for pixel in 0..64 {
        pixels.extend_from_slice(&[value(4 * pixel), value(4 * pixel + 1), value(4 * pixel + 2), 255]);
    }
    RgbaImage::new(8, 8, pixels)
}

fn render(st: &Streamlit) {
    st.image((gradient(), "gradient"));
    st.audio((wav_bytes(), "audio/wav"));
    st.metric(MetricOptions::new("Temperature", "72 °F").delta("2 °F"));
    st.metric(MetricOptions::new("Wind", "8 mph").delta("-3 mph").delta_color(DeltaColor::Inverse));
    match st.progress(50) {
        Ok(progress) => progress.set(75),
        Err(error) => st.write(format!("Progress error: {error}")),
    }
}

#[tokio::main]
async fn main() -> std::io::Result<()> {
    StreamlitServer::new(
        |st| {
            Box::pin(async move {
                render(st);
            })
        },
        "127.0.0.1".into(),
        8509,
    )
    .start()
    .await
}
