//! Media regressions against the measured Python 1.66.1 wire (see
//! .codex/compatibility.md, Media route): the image list carries relative
//! content-addressed URLs with a content width, the audio element stretches
//! inside its message, metrics derive direction/color from the delta sign,
//! progress coalesces to one final-value delta, and /media answers 200/206
//! with the measured headers.
use super::*;
use crate::{DeltaColor, MetricOptions, RgbaImage};

/// The WAV fixture tests/reference/media_app.py synthesizes: half a second
/// of 440 Hz mono PCM16 at 22050 Hz with the Python wave module's RIFF layout.
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
    wav.extend_from_slice(&1u16.to_le_bytes()); // PCM
    wav.extend_from_slice(&1u16.to_le_bytes()); // mono
    wav.extend_from_slice(&22050u32.to_le_bytes());
    wav.extend_from_slice(&44100u32.to_le_bytes());
    wav.extend_from_slice(&2u16.to_le_bytes());
    wav.extend_from_slice(&16u16.to_le_bytes());
    wav.extend_from_slice(b"data");
    wav.extend_from_slice(&(data.len() as u32).to_le_bytes());
    wav.extend_from_slice(&data);
    wav
}

/// The 8x8 RGBA gradient fixture: channel j cycles (4*j) % 256 like the
/// numpy uint8 arange, and the alpha plane is forced to 255.
fn gradient() -> RgbaImage {
    let value = |index: usize| (4 * index % 256) as u8;
    let mut pixels = Vec::with_capacity(256);
    for pixel in 0..64 {
        pixels.extend_from_slice(&[value(4 * pixel), value(4 * pixel + 1), value(4 * pixel + 2), 255]);
    }
    RgbaImage::new(8, 8, pixels)
}

fn media_entry(st: &Streamlit) -> Pin<Box<dyn Future<Output = ()> + '_>> {
    Box::pin(async move {
        // Mirrors tests/reference/media_app.py.
        st.image((gradient(), "gradient"));
        st.audio((wav_bytes(), "audio/wav"));
        st.metric(MetricOptions::new("Temperature", "72 °F").delta("2 °F"));
        st.metric(MetricOptions::new("Wind", "8 mph").delta("-3 mph").delta_color(DeltaColor::Inverse));
        let progress = st.progress(50).unwrap();
        progress.set(75);
    })
}

#[derive(Default)]
struct MediaWires {
    elements: Vec<crate::proto::Element>,
}

async fn start_media_server() -> (std::net::SocketAddr, actix_web::dev::ServerHandle, tokio::task::JoinHandle<std::io::Result<()>>, TcpStream) {
    let listener = std::net::TcpListener::bind("127.0.0.1:0").unwrap();
    let address = listener.local_addr().unwrap();
    let server = HttpServer::new(move || App::new().app_data(web::Data::new(StreamlitServer::new(media_entry, "127.0.0.1".into(), 0))).configure(configure_routes))
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
    (address, handle, task, stream)
}

async fn run_once(stream: &mut TcpStream, session_id: &mut String) -> MediaWires {
    let request = BackMsg {
        r#type: Some(back_msg::Type::RerunScript(ClientState {
            widget_states: Some(WidgetStates { widgets: vec![] }),
            ..Default::default()
        })),
    };
    send_binary(stream, &request.encode_to_vec()).await;
    let first = receive(stream).await;
    let Some(forward_msg::Type::NewSession(new_session)) = first.r#type else {
        panic!("a run must start with NewSession, got {:?}", first.r#type)
    };
    let init = new_session.initialize.unwrap();
    if session_id.is_empty() {
        *session_id = init.session_id;
    } else {
        assert_eq!(init.session_id, *session_id);
    }
    assert!(matches!(receive(stream).await.r#type, Some(forward_msg::Type::SessionStatusChanged(status)) if status.script_is_running));
    let mut wires = MediaWires::default();
    let mut finished = false;
    loop {
        match receive(stream).await.r#type {
            Some(forward_msg::Type::Delta(delta)) => {
                let Some(delta::Type::NewElement(element)) = delta.r#type else { continue };
                wires.elements.push(element);
            }
            Some(forward_msg::Type::ScriptFinished(status)) => {
                assert_eq!(status, 0);
                assert!(!finished);
                finished = true;
            }
            Some(forward_msg::Type::SessionStatusChanged(status)) if !status.script_is_running => break,
            other => panic!("unexpected lifecycle response: {other:?}"),
        }
    }
    assert!(finished);
    wires
}

async fn http_get(address: std::net::SocketAddr, path: &str, range: Option<&str>) -> (u16, Vec<(String, String)>, Vec<u8>) {
    let mut stream = TcpStream::connect(address).await.unwrap();
    let range_header = range.map(|value| format!("Range: {value}\r\n")).unwrap_or_default();
    let request = format!("GET {path} HTTP/1.1\r\nHost: {address}\r\n{range_header}Connection: close\r\n\r\n");
    stream.write_all(request.as_bytes()).await.unwrap();
    let mut raw = Vec::new();
    stream.read_to_end(&mut raw).await.unwrap();
    let split = raw.windows(4).position(|window| window == b"\r\n\r\n").expect("http header terminator");
    let head = String::from_utf8_lossy(&raw[..split]).to_string();
    let status: u16 = head.lines().next().unwrap().split_whitespace().nth(1).unwrap().parse().unwrap();
    let headers = head.lines().skip(1).filter_map(|line| line.split_once(':')).map(|(name, value)| (name.trim().to_ascii_lowercase(), value.trim().to_string())).collect();
    (status, headers, raw[split + 4..].to_vec())
}

fn width_kind(config: &Option<crate::proto::streamlit::WidthConfig>) -> String {
    config
        .as_ref()
        .and_then(|config| config.width_spec.as_ref())
        .map(|spec| match spec {
            crate::proto::streamlit::width_config::WidthSpec::UseStretch(_) => "stretch".into(),
            crate::proto::streamlit::width_config::WidthSpec::UseContent(_) => "content".into(),
            crate::proto::streamlit::width_config::WidthSpec::PixelWidth(pixels) => format!("pixels:{pixels}"),
            crate::proto::streamlit::width_config::WidthSpec::RemWidth(_) => "rem".into(),
        })
        .unwrap_or_default()
}

#[actix_web::test]
async fn media_elements_match_the_measured_wire_and_serve_the_measured_http() {
    let (address, handle, task, mut stream) = start_media_server().await;
    let mut session_id = String::new();

    let wires = run_once(&mut stream, &mut session_id).await;
    let kinds: Vec<&str> = wires
        .elements
        .iter()
        .map(|element| match element.r#type.as_ref().unwrap() {
            element::Type::Imgs(_) => "imgs",
            element::Type::Audio(_) => "audio",
            element::Type::Metric(_) => "metric",
            element::Type::Progress(_) => "progress",
            other => panic!("unexpected element: {other:?}"),
        })
        .collect();
    assert_eq!(kinds, ["imgs", "audio", "metric", "metric", "progress"], "the progress 50/75 pair coalesces into one final-value delta");

    let imgs = match wires.elements[0].r#type.as_ref().unwrap() {
        element::Type::Imgs(imgs) => imgs,
        other => panic!("expected imgs, got {other:?}"),
    };
    assert_eq!(imgs.imgs.len(), 1);
    assert_eq!(imgs.imgs[0].caption, "gradient");
    assert_eq!(imgs.imgs[0].alt, None);
    assert_eq!(imgs.link, "");
    let image_url = imgs.imgs[0].url.clone();
    assert!(image_url.starts_with("/media/") && image_url.ends_with(".png"), "the URL is relative and typed: {image_url}");
    assert_eq!(width_kind(&wires.elements[0].width_config), "content");

    let audio = match wires.elements[1].r#type.as_ref().unwrap() {
        element::Type::Audio(audio) => audio,
        other => panic!("expected audio, got {other:?}"),
    };
    let audio_url = audio.url.clone();
    assert!(audio_url.starts_with("/media/") && audio_url.ends_with(".wav"), "the URL is relative and typed: {audio_url}");
    // The measured audio stretch width sits inside the Audio message.
    assert_eq!(width_kind(&audio.width_config), "stretch");
    assert_eq!((audio.start_time, audio.end_time, audio.r#loop, audio.autoplay, audio.id.as_str()), (0, 0, false, false, ""));
    assert_eq!(width_kind(&wires.elements[1].width_config), "");

    let metrics: Vec<&crate::proto::Metric> = wires.elements[2..4]
        .iter()
        .map(|element| match element.r#type.as_ref().unwrap() {
            element::Type::Metric(metric) => metric,
            other => panic!("expected metric, got {other:?}"),
        })
        .collect();
    assert_eq!((metrics[0].label.as_str(), metrics[0].body.as_str(), metrics[0].delta.as_str()), ("Temperature", "72 °F", "2 °F"));
    assert_eq!((metrics[0].direction, metrics[0].color), (1, 1), "a positive delta points UP colored GREEN");
    assert_eq!((metrics[1].label.as_str(), metrics[1].body.as_str(), metrics[1].delta.as_str()), ("Wind", "8 mph", "-3 mph"));
    assert_eq!((metrics[1].direction, metrics[1].color), (0, 1), "an inverse negative delta points DOWN colored GREEN");
    assert!(metrics.iter().all(|metric| metric.label_visibility.is_some()));
    for element in &wires.elements[2..4] {
        assert_eq!(width_kind(&element.width_config), "stretch");
        assert_eq!(
            element
                .height_config
                .as_ref()
                .and_then(|config| config.height_spec.as_ref())
                .map(|spec| matches!(spec, crate::proto::streamlit::height_config::HeightSpec::UseContent(_))),
            Some(true),
            "metrics carry the measured content height"
        );
    }

    let progress = match wires.elements[4].r#type.as_ref().unwrap() {
        element::Type::Progress(progress) => progress,
        other => panic!("expected progress, got {other:?}"),
    };
    assert_eq!(progress.value, 75, "the streamed value is the final one, never the intermediate 50");
    assert_eq!(progress.text, "");
    assert_eq!(width_kind(&wires.elements[4].width_config), "stretch");

    // The measured /media round trips: 200 with accept-ranges for a full
    // GET, 206 with content-range for the browser's open-ended Range.
    let (status, headers, body) = http_get(address, &image_url, None).await;
    assert_eq!(status, 200);
    assert_eq!(headers.iter().find(|(name, _)| name == "content-type").map(|(_, value)| value.as_str()), Some("image/png"));
    assert_eq!(headers.iter().find(|(name, _)| name == "accept-ranges").map(|(_, value)| value.as_str()), Some("bytes"));
    assert!(body.starts_with(b"\x89PNG\r\n\x1a\n"));
    let image_id = image_url.trim_start_matches("/media/").trim_end_matches(".png");
    assert_eq!(crate::media::file_id(&body, "image/png", None), image_id, "the served bytes are the addressed content");

    let wav = wav_bytes();
    // The fixture WAV is byte-identical to the reference's, so the address
    // is the exact measured one.
    assert_eq!(audio_url, "/media/431dec53348c010fe7c4e0be3ac78ede.wav");
    let (status, headers, body) = http_get(address, &audio_url, Some("bytes=0-")).await;
    assert_eq!(status, 206);
    assert_eq!(headers.iter().find(|(name, _)| name == "content-type").map(|(_, value)| value.as_str()), Some("audio/wav"));
    let expected_range = format!("bytes 0-{}/{}", wav.len() - 1, wav.len());
    assert_eq!(headers.iter().find(|(name, _)| name == "content-range").map(|(_, value)| value.as_str()), Some(expected_range.as_str()));
    assert_eq!(body, wav);

    let (status, _, _) = http_get(address, "/media/0123456789abcdef0123456789abcdef.png", None).await;
    assert_eq!(status, 404);
    let (status, _, partial) = http_get(address, &audio_url, Some("bytes=10-99")).await;
    assert_eq!(status, 206);
    assert_eq!(partial, wav[10..=99]);
    let (status, _, full) = http_get(address, &audio_url, None).await;
    assert_eq!(status, 200);
    assert_eq!(full, wav);

    drop(stream);
    handle.stop(false).await;
    task.await.unwrap().unwrap();
}

/// The committed one-second sample the video fixture serves; the same bytes
/// feed the Python reference, so the media address is the exact measured one.
const VIDEO_SAMPLE: &[u8] = include_bytes!("../../../tests/reference/video_sample.mp4");

fn video_entry(st: &Streamlit) -> Pin<Box<dyn Future<Output = ()> + '_>> {
    Box::pin(async move {
        // Mirrors tests/reference/video_app.py.
        st.video((VIDEO_SAMPLE.to_vec(), "video/mp4"));
    })
}

#[actix_web::test]
async fn video_matches_the_measured_wire_and_serves_the_sample_unchanged() {
    let listener = std::net::TcpListener::bind("127.0.0.1:0").unwrap();
    let address = listener.local_addr().unwrap();
    let server = HttpServer::new(move || App::new().app_data(web::Data::new(StreamlitServer::new(video_entry, "127.0.0.1".into(), 0))).configure(configure_routes))
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
    let mut video: Option<crate::proto::Video> = None;
    let mut finished = false;
    let first = receive(&mut stream).await;
    assert!(matches!(first.r#type, Some(forward_msg::Type::NewSession(_))));
    assert!(matches!(receive(&mut stream).await.r#type, Some(forward_msg::Type::SessionStatusChanged(status)) if status.script_is_running));
    loop {
        match receive(&mut stream).await.r#type {
            Some(forward_msg::Type::Delta(delta)) => {
                let Some(delta::Type::NewElement(element)) = delta.r#type else { continue };
                match element.r#type {
                    Some(element::Type::Video(wire)) => video = Some(wire),
                    Some(other) => panic!("unexpected element: {other:?}"),
                    None => {}
                }
            }
            Some(forward_msg::Type::ScriptFinished(status)) => {
                assert_eq!(status, 0);
                assert!(!finished);
                finished = true;
            }
            Some(forward_msg::Type::SessionStatusChanged(status)) if !status.script_is_running => break,
            other => panic!("unexpected lifecycle response: {other:?}"),
        }
    }
    assert!(finished);

    // The measured video wire: NATIVE type, the exact byte-derived address,
    // and the stretch width inside the message with nothing at element level.
    let video = video.expect("video wire");
    assert_eq!(video.url, "/media/89d6baf253834c013e2bc52aab2354d4.mp4");
    assert_eq!(video.r#type, crate::proto::video::Type::Native as i32);
    assert_eq!((video.start_time, video.end_time, video.r#loop, video.autoplay, video.muted, video.id.as_str()), (0, 0, false, false, false, ""));
    assert!(video.subtitles.is_empty());
    assert_eq!(width_kind_local(&video.width_config), "stretch");

    let (status, headers, body) = http_get(address, &video.url, Some("bytes=0-")).await;
    assert_eq!(status, 206);
    assert_eq!(headers.iter().find(|(name, _)| name == "content-type").map(|(_, value)| value.as_str()), Some("video/mp4"));
    let expected_range = format!("bytes 0-{}/{}", VIDEO_SAMPLE.len() - 1, VIDEO_SAMPLE.len());
    assert_eq!(headers.iter().find(|(name, _)| name == "content-range").map(|(_, value)| value.as_str()), Some(expected_range.as_str()));
    assert_eq!(body, VIDEO_SAMPLE);

    drop(stream);
    handle.stop(false).await;
    task.await.unwrap().unwrap();
}

fn width_kind_local(config: &Option<crate::proto::streamlit::WidthConfig>) -> &'static str {
    match config.as_ref().and_then(|config| config.width_spec.as_ref()) {
        Some(crate::proto::streamlit::width_config::WidthSpec::UseStretch(_)) => "stretch",
        _ => "",
    }
}
