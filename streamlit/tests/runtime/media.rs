//! Media regressions against the measured Python 1.66.1 wire (see
//! .codex/compatibility.md, Media route): the image list carries relative
//! content-addressed URLs with a content width, the audio element stretches
//! inside its message, metrics derive direction/color from the delta sign,
//! progress coalesces to one final-value delta, and /media answers 200/206
//! with the measured headers.
use super::*;
use crate::InputWidgets;
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
        let result: TestResult = async {
            // Mirrors tests/reference/media_app.py.
            st.image((gradient(), "gradient"));
            st.audio((wav_bytes(), "audio/wav"));
            st.metric(MetricOptions::new("Temperature", "72 °F").delta("2 °F"));
            st.metric(MetricOptions::new("Wind", "8 mph").delta("-3 mph").delta_color(DeltaColor::Inverse));
            let progress = st.progress(50)?;
            progress.set(75);
            Ok(())
        }
        .await;
        assert!(result.is_ok(), "media_entry fixture failed: {result:?}");
    })
}

#[derive(Default)]
struct MediaWires {
    elements: Vec<crate::proto::Element>,
}

async fn start_media_server(entry: fn(&Streamlit) -> Pin<Box<dyn Future<Output = ()> + '_>>) -> TestResult<(std::net::SocketAddr, actix_web::dev::ServerHandle, tokio::task::JoinHandle<std::io::Result<()>>, TcpStream)> {
    let listener = std::net::TcpListener::bind("127.0.0.1:0")?;
    let address = listener.local_addr()?;
    let server = HttpServer::new(move || App::new().app_data(web::Data::new(StreamlitServer::new(entry, "127.0.0.1".into(), 0))).configure(configure_routes))
        .workers(1)
        .listen(listener)?
        .run();
    let handle = server.handle();
    let task = actix_web::rt::spawn(server);
    let mut stream = TcpStream::connect(address).await?;
    let request = format!("GET /_stcore/stream HTTP/1.1\r\nHost: {address}\r\nConnection: Upgrade\r\nUpgrade: websocket\r\nSec-WebSocket-Version: 13\r\nSec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==\r\nSec-WebSocket-Protocol: streamlit, test-xsrf\r\n\r\n");
    stream.write_all(request.as_bytes()).await?;
    let headers = tokio::time::timeout(Duration::from_secs(5), async {
        let mut response = Vec::new();
        while !response.ends_with(b"\r\n\r\n") {
            response.push(stream.read_u8().await?);
            assert!(response.len() < 8192);
        }
        Ok::<_, Box<dyn std::error::Error>>(String::from_utf8(response)?.to_ascii_lowercase())
    })
    .await??;
    assert!(headers.starts_with("http/1.1 101"));
    Ok((address, handle, task, stream))
}

async fn run_once(stream: &mut TcpStream, session_id: &mut String) -> TestResult<MediaWires> {
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
    let init = new_session.initialize.ok_or("NewSession must include initialization")?;
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
    Ok(wires)
}

async fn http_get(address: std::net::SocketAddr, path: &str, range: Option<&str>) -> TestResult<(u16, Vec<(String, String)>, Vec<u8>)> {
    let mut stream = TcpStream::connect(address).await?;
    let range_header = range.map(|value| format!("Range: {value}\r\n")).unwrap_or_default();
    let request = format!("GET {path} HTTP/1.1\r\nHost: {address}\r\n{range_header}Connection: close\r\n\r\n");
    stream.write_all(request.as_bytes()).await?;
    let mut raw = Vec::new();
    stream.read_to_end(&mut raw).await?;
    let split = raw.windows(4).position(|window| window == b"\r\n\r\n").ok_or("HTTP response must include header terminator")?;
    let head = String::from_utf8_lossy(&raw[..split]).to_string();
    let status: u16 = head.lines().next().ok_or("HTTP response must include a status line")?.split_whitespace().nth(1).ok_or("HTTP status line must include a code")?.parse()?;
    let headers = head.lines().skip(1).filter_map(|line| line.split_once(':')).map(|(name, value)| (name.trim().to_ascii_lowercase(), value.trim().to_string())).collect();
    Ok((status, headers, raw[split + 4..].to_vec()))
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
async fn csv_download_serves_named_attachment_and_repeatable_range_bytes() -> TestResult {
    let bytes = b"id,region\nA,north\n";
    let mime = "text/csv";
    let id = crate::media::put_download(bytes, mime, Some("workbench.csv"));
    let path = format!("/media/{id}{}", crate::media::download_extension(mime));
    let (address, handle, task, stream) = start_media_server(media_entry).await?;

    // 1. 复用真实 HTTP 路由采集完整、范围、重复与未知地址响应。
    let captured = tokio::time::timeout(Duration::from_secs(10), async {
        let full = http_get(address, &path, None).await?;
        let range = http_get(address, &path, Some("bytes=0-1")).await?;
        let repeated = http_get(address, &path, None).await?;
        let unknown = http_get(address, "/media/0123456789abcdef0123456789abcdef.csv", None).await?;
        Ok::<_, Box<dyn std::error::Error>>((full, range, repeated, unknown))
    })
    .await;

    // 2. 任一路径失败也先回收自有连接与 server，再断言下载内容和响应头。
    drop(stream);
    handle.stop(false).await;
    task.await??;
    let (full, range, repeated, unknown) = captured??;
    println!("CSV download path={path}; full={full:?}; range={range:?}; repeated={repeated:?}; unknown_status={}", unknown.0);
    assert_eq!(full.0, 200, "registered CSV download must be reachable through its actual extension");
    assert_eq!(full.1.iter().find(|(name, _)| name == "content-type").map(|(_, value)| value.as_str()), Some("text/csv; charset=utf-8"));
    let disposition = full.1.iter().find(|(name, _)| name == "content-disposition").map(|(_, value)| value.as_str()).ok_or("CSV download must provide Content-Disposition")?;
    assert!(disposition.starts_with("attachment;") && disposition.contains("workbench.csv"), "CSV download must retain its attachment filename: {disposition}");
    assert_eq!(full.2, bytes);
    assert_eq!(range.0, 206);
    let expected_range = format!("bytes 0-1/{}", bytes.len());
    assert_eq!(range.1.iter().find(|(name, _)| name == "content-range").map(|(_, value)| value.as_str()), Some(expected_range.as_str()));
    assert_eq!(range.2, &bytes[..2]);
    assert_eq!(repeated.0, 200);
    assert_eq!(repeated.2, bytes, "downloading must not consume or change the stored CSV");
    assert_eq!(unknown.0, 404);
    Ok(())
}

fn download_boundaries_entry(st: &Streamlit) -> Pin<Box<dyn Future<Output = ()> + '_>> {
    Box::pin(async move {
        let result: TestResult = (|| {
            let reference: serde_json::Value = serde_json::from_str(include_str!("../../../tests/reference/reference-browser/download-boundaries/download-cases.json"))?;
            for case in reference["cases"].as_array().ok_or("download reference cases are missing")? {
                let label = case["label"].as_str().ok_or("download label is missing")?;
                let payload = serde_json::from_value::<Vec<u8>>(case["payload_bytes"].clone())?;
                let mut options = crate::DownloadButtonOptions::new(label, payload).key(label).ignore_rerun(true);
                if let Some(name) = case["file_name_option"].as_str() {
                    options = options.file_name(name);
                }
                if let Some(mime) = case["mime_option"].as_str() {
                    options = options.mime(mime);
                }
                st.download_button(options)?;
            }
            Ok(())
        })();
        assert!(result.is_ok(), "download fixture failed: {result:?}");
    })
}

fn range_entry(st: &Streamlit) -> Pin<Box<dyn Future<Output = ()> + '_>> {
    Box::pin(async move {
        let result: TestResult = (|| {
            st.download_button(crate::DownloadButtonOptions::new("range-csv", b"id,region\nA,north\n".to_vec()).file_name("range.csv").mime("text/csv").key("range-csv").ignore_rerun(true))?;
            st.download_button(crate::DownloadButtonOptions::new("range-empty", Vec::new()).file_name("empty.bin").mime("application/octet-stream").key("range-empty").ignore_rerun(true))?;
            st.video((VIDEO_SAMPLE.to_vec(), "video/mp4"));
            Ok(())
        })();
        assert!(result.is_ok(), "range fixture failed: {result:?}");
    })
}

#[actix_web::test]
async fn media_ranges_match_twenty_seven_frozen_public_http_requests() -> TestResult {
    let reference: serde_json::Value = serde_json::from_str(include_str!("../../../tests/reference/reference-browser/media-range/range-input-output.json"))?;
    assert_eq!(reference["reference_version"], "1.66.1");
    let cases = reference["cases"].as_array().ok_or("range cases missing")?;
    assert_eq!(cases.len(), 27);
    let (address, handle, task, mut socket) = start_media_server(range_entry).await?;
    let captured = tokio::time::timeout(Duration::from_secs(10), async {
        let wires = run_once(&mut socket, &mut String::new()).await?;
        let urls: std::collections::HashMap<_, _> = wires
            .elements
            .into_iter()
            .filter_map(|element| match element.r#type {
                Some(element::Type::DownloadButton(button)) => Some((button.label.trim_start_matches("range-").to_string(), button.url)),
                Some(element::Type::Video(video)) => Some(("video".into(), video.url)),
                _ => None,
            })
            .collect();
        let mut responses = Vec::new();
        for case in cases {
            let asset = case["asset"].as_str().ok_or("range asset missing")?;
            let url = urls.get(asset).ok_or("public entry did not emit the asset")?;
            responses.push((url.clone(), http_get(address, url, case["range_header"].as_str()).await?));
        }
        Ok::<_, Box<dyn std::error::Error>>(responses)
    })
    .await;
    // 先采完并清理，再逐项比对；红断言不会遗留服务。
    drop(socket);
    handle.stop(false).await;
    task.await??;
    let responses = captured??;
    for ((_, (status, _, _)), case) in responses.iter().zip(cases) {
        println!("range case={} asset={} header={} actual={} expected={}", case["label"], case["asset"], case["range_header"], status, case["status"]);
    }
    assert_eq!(responses.len(), cases.len());
    for ((url, (status, headers, body)), case) in responses.into_iter().zip(cases) {
        assert_eq!(url, case["url"], "{}: actual public URL", case["label"]);
        assert_eq!(Some(u64::from(status)), case["status"].as_u64(), "{}", case["label"]);
        let expected: Vec<(String, String)> = serde_json::from_value(case["headers"].clone())?;
        for name in ["content-range", "content-length", "content-type", "content-disposition", "accept-ranges"] {
            assert_eq!(
                headers.iter().find(|(key, _)| key == name).map(|(_, value)| value),
                expected.iter().find(|(key, _)| key.eq_ignore_ascii_case(name)).map(|(_, value)| value),
                "{}: {name}",
                case["label"]
            );
        }
        assert_eq!(body, serde_json::from_value::<Vec<u8>>(case["body_bytes"].clone())?, "{}: response bytes", case["label"]);
    }
    Ok(())
}

#[actix_web::test]
async fn download_headers_and_bytes_match_ten_frozen_public_cases() -> TestResult {
    let reference: serde_json::Value = serde_json::from_str(include_str!("../../../tests/reference/reference-browser/download-boundaries/download-cases.json"))?;
    assert_eq!(reference["reference_version"], "1.66.1");
    let cases = reference["cases"].as_array().ok_or("download cases are missing")?;
    assert_eq!(cases.len(), 10);
    let (address, handle, task, mut stream) = start_media_server(download_boundaries_entry).await?;
    let captured = tokio::time::timeout(Duration::from_secs(10), async {
        let wires = run_once(&mut stream, &mut String::new()).await?;
        let mut actual = Vec::new();
        for element in wires.elements {
            let Some(element::Type::DownloadButton(button)) = element.r#type else {
                return Err("unexpected element in download fixture".into());
            };
            let response = http_get(address, &button.url, None).await?;
            actual.push((button.label, button.url, response));
        }
        Ok::<_, Box<dyn std::error::Error>>(actual)
    })
    .await;
    // 先完整取回十个真实响应并回收自有连接，再比较，失败不会遗留 server。
    drop(stream);
    handle.stop(false).await;
    task.await??;
    let actual = captured??;
    assert_eq!(actual.len(), cases.len());
    for (label, url, (status, headers, _)) in &actual {
        println!(
            "download case={label} url={url} status={status} content_type={:?} disposition={:?}",
            headers.iter().find(|(name, _)| name == "content-type"),
            headers.iter().find(|(name, _)| name == "content-disposition")
        );
    }
    for ((label, url, (status, headers, body)), expected) in actual.into_iter().zip(cases) {
        assert_eq!(label, expected["label"]);
        assert_eq!(url, expected["url"], "content address and extension must match at {label}");
        assert_eq!(status, expected["status"].as_u64().ok_or("expected status is missing")? as u16);
        let expected_headers: Vec<(String, String)> = serde_json::from_value(expected["headers"].clone())?;
        for name in ["content-type", "content-disposition", "content-length", "accept-ranges"] {
            assert_eq!(
                headers.iter().find(|(key, _)| key == name).map(|(_, value)| value),
                expected_headers.iter().find(|(key, _)| key.eq_ignore_ascii_case(name)).map(|(_, value)| value),
                "{label}: {name}"
            );
        }
        assert_eq!(body, serde_json::from_value::<Vec<u8>>(expected["body_bytes"].clone())?, "{label}");
    }
    Ok(())
}

#[actix_web::test]
async fn media_elements_match_the_measured_wire_and_serve_the_measured_http() -> TestResult {
    let (address, handle, task, mut stream) = start_media_server(media_entry).await?;
    let mut session_id = String::new();

    let wires = run_once(&mut stream, &mut session_id).await?;
    let kinds: Vec<&str> = wires
        .elements
        .iter()
        .map(|element| match element.r#type.as_ref() {
            Some(element::Type::Imgs(_)) => "imgs",
            Some(element::Type::Audio(_)) => "audio",
            Some(element::Type::Metric(_)) => "metric",
            Some(element::Type::Progress(_)) => "progress",
            other => panic!("unexpected element: {other:?}"),
        })
        .collect();
    assert_eq!(kinds, ["imgs", "audio", "metric", "metric", "progress"], "the progress 50/75 pair coalesces into one final-value delta");

    let imgs = match wires.elements[0].r#type.as_ref() {
        Some(element::Type::Imgs(imgs)) => imgs,
        other => panic!("expected imgs, got {other:?}"),
    };
    assert_eq!(imgs.imgs.len(), 1);
    assert_eq!(imgs.imgs[0].caption, "gradient");
    assert_eq!(imgs.imgs[0].alt, None);
    assert_eq!(imgs.link, "");
    let image_url = imgs.imgs[0].url.clone();
    assert!(image_url.starts_with("/media/") && image_url.ends_with(".png"), "the URL is relative and typed: {image_url}");
    assert_eq!(width_kind(&wires.elements[0].width_config), "content");

    let audio = match wires.elements[1].r#type.as_ref() {
        Some(element::Type::Audio(audio)) => audio,
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
        .map(|element| match element.r#type.as_ref() {
            Some(element::Type::Metric(metric)) => metric,
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

    let progress = match wires.elements[4].r#type.as_ref() {
        Some(element::Type::Progress(progress)) => progress,
        other => panic!("expected progress, got {other:?}"),
    };
    assert_eq!(progress.value, 75, "the streamed value is the final one, never the intermediate 50");
    assert_eq!(progress.text, "");
    assert_eq!(width_kind(&wires.elements[4].width_config), "stretch");

    // The measured /media round trips: 200 with accept-ranges for a full
    // GET, 206 with content-range for the browser's open-ended Range.
    let (status, headers, body) = http_get(address, &image_url, None).await?;
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
    let (status, headers, body) = http_get(address, &audio_url, Some("bytes=0-")).await?;
    assert_eq!(status, 206);
    assert_eq!(headers.iter().find(|(name, _)| name == "content-type").map(|(_, value)| value.as_str()), Some("audio/wav"));
    let expected_range = format!("bytes 0-{}/{}", wav.len() - 1, wav.len());
    assert_eq!(headers.iter().find(|(name, _)| name == "content-range").map(|(_, value)| value.as_str()), Some(expected_range.as_str()));
    assert_eq!(body, wav);

    let (status, _, _) = http_get(address, "/media/0123456789abcdef0123456789abcdef.png", None).await?;
    assert_eq!(status, 404);
    let (status, _, partial) = http_get(address, &audio_url, Some("bytes=10-99")).await?;
    assert_eq!(status, 206);
    assert_eq!(partial, wav[10..=99]);
    let (status, _, full) = http_get(address, &audio_url, None).await?;
    assert_eq!(status, 200);
    assert_eq!(full, wav);

    drop(stream);
    handle.stop(false).await;
    task.await??;
    Ok(())
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
async fn video_matches_the_measured_wire_and_serves_the_sample_unchanged() -> TestResult {
    let listener = std::net::TcpListener::bind("127.0.0.1:0")?;
    let address = listener.local_addr()?;
    let server = HttpServer::new(move || App::new().app_data(web::Data::new(StreamlitServer::new(video_entry, "127.0.0.1".into(), 0))).configure(configure_routes))
        .workers(1)
        .listen(listener)?
        .run();
    let handle = server.handle();
    let task = actix_web::rt::spawn(server);
    let mut stream = TcpStream::connect(address).await?;
    let request = format!("GET /_stcore/stream HTTP/1.1\r\nHost: {address}\r\nConnection: Upgrade\r\nUpgrade: websocket\r\nSec-WebSocket-Version: 13\r\nSec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==\r\nSec-WebSocket-Protocol: streamlit, test-xsrf\r\n\r\n");
    stream.write_all(request.as_bytes()).await?;
    let headers = tokio::time::timeout(Duration::from_secs(5), async {
        let mut response = Vec::new();
        while !response.ends_with(b"\r\n\r\n") {
            response.push(stream.read_u8().await?);
            assert!(response.len() < 8192);
        }
        Ok::<_, Box<dyn std::error::Error>>(String::from_utf8(response)?.to_ascii_lowercase())
    })
    .await??;
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
    let video = video.ok_or("video widget must be rendered")?;
    assert_eq!(video.url, "/media/89d6baf253834c013e2bc52aab2354d4.mp4");
    assert_eq!(video.r#type, crate::proto::video::Type::Native as i32);
    assert_eq!((video.start_time, video.end_time, video.r#loop, video.autoplay, video.muted, video.id.as_str()), (0, 0, false, false, false, ""));
    assert!(video.subtitles.is_empty());
    assert_eq!(width_kind_local(&video.width_config), "stretch");

    let (status, headers, body) = http_get(address, &video.url, Some("bytes=0-")).await?;
    assert_eq!(status, 206);
    assert_eq!(headers.iter().find(|(name, _)| name == "content-type").map(|(_, value)| value.as_str()), Some("video/mp4"));
    let expected_range = format!("bytes 0-{}/{}", VIDEO_SAMPLE.len() - 1, VIDEO_SAMPLE.len());
    assert_eq!(headers.iter().find(|(name, _)| name == "content-range").map(|(_, value)| value.as_str()), Some(expected_range.as_str()));
    assert_eq!(body, VIDEO_SAMPLE);

    drop(stream);
    handle.stop(false).await;
    task.await??;
    Ok(())
}

fn width_kind_local(config: &Option<crate::proto::streamlit::WidthConfig>) -> &'static str {
    match config.as_ref().and_then(|config| config.width_spec.as_ref()) {
        Some(crate::proto::streamlit::width_config::WidthSpec::UseStretch(_)) => "stretch",
        _ => "",
    }
}
