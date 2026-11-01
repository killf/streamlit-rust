//! The media and presentation elements measured on the Python 1.66.1
//! reference (see .codex/compatibility.md, Media route): the image list with
//! relative content-addressed URLs, the audio element with its stretch width
//! inside the message, the metric with direction/color derived from the delta
//! sign, and the coalescing progress bar.

use crate::elements::common::{Element, ElementHeight, ElementWidth, RenderContext};
use crate::elements::exception::AppException;
use crate::error::StreamlitError;
use crate::media;
use crate::proto::{Delta, delta, delta_base_with_path, element, forward_msg, metric};
use crate::utils::hash::hash;

fn push_element(context: &mut RenderContext, element_hash: String, inner: element::Type, width: Option<ElementWidth>, height: Option<ElementHeight>) {
    let mut msg = delta_base_with_path(context.delta_path.clone(), context.active_script_hash.clone(), element_hash);
    msg.r#type = Some(forward_msg::Type::Delta(Delta {
        fragment_id: String::new(),
        r#type: Some(delta::Type::NewElement(crate::proto::Element {
            width_config: width.map(Into::into),
            height_config: height.map(Into::into),
            r#type: Some(inner),
            ..Default::default()
        })),
    }));
    context.push(msg);
    if let Some(index) = context.delta_path.pop() {
        context.delta_path.push(index + 1);
    }
}

/// Pushes a one-shot element (balloons): the measured wire marks these
/// `has_one_shot_effect` and carries no width or height config.
fn push_one_shot_element(context: &mut RenderContext, element_hash: String, inner: element::Type) {
    let mut msg = delta_base_with_path(context.delta_path.clone(), context.active_script_hash.clone(), element_hash);
    msg.r#type = Some(forward_msg::Type::Delta(Delta {
        fragment_id: String::new(),
        r#type: Some(delta::Type::NewElement(crate::proto::Element {
            has_one_shot_effect: Some(true),
            r#type: Some(inner),
            ..Default::default()
        })),
    }));
    context.push(msg);
    if let Some(index) = context.delta_path.pop() {
        context.delta_path.push(index + 1);
    }
}

pub(crate) struct ToastElement {
    body: String,
    icon: String,
    duration: Option<i32>,
}

impl ToastElement {
    pub fn new(body: String, icon: String, duration: Option<i32>) -> Self {
        Self { body, icon, duration }
    }
}

impl Element for ToastElement {
    fn render(&self, context: &mut RenderContext) -> Result<(), StreamlitError> {
        // The measured toast routes to the dedicated root path [2, 0], not
        // the calling container, and does not consume a container slot.
        let element_hash = hash(format!("toast_{}_{}_{}", self.body, self.icon, self.duration.unwrap_or(0)).as_str());
        let mut msg = delta_base_with_path(vec![2, 0], context.active_script_hash.clone(), element_hash);
        msg.r#type = Some(forward_msg::Type::Delta(Delta {
            fragment_id: String::new(),
            r#type: Some(delta::Type::NewElement(crate::proto::Element {
                has_one_shot_effect: Some(true),
                r#type: Some(element::Type::Toast(crate::proto::Toast {
                    body: self.body.clone(),
                    icon: self.icon.clone(),
                    duration: self.duration,
                })),
                ..Default::default()
            })),
        }));
        context.push(msg);
        Ok(())
    }
}

pub(crate) struct BalloonsElement;

impl Element for BalloonsElement {
    fn render(&self, context: &mut RenderContext) -> Result<(), StreamlitError> {
        push_one_shot_element(context, hash("balloons"), element::Type::Balloons(crate::proto::Balloons { show: true }));
        Ok(())
    }
}

/// One transient-element delta: the spinner lifecycle rides `new_transient`
/// (one active spinner, then an empty list when the block exits).
pub(crate) struct SpinnerTransientElement {
    text: Option<String>,
}

impl SpinnerTransientElement {
    pub fn active(text: String) -> Self {
        Self { text: Some(text) }
    }

    pub fn cleared() -> Self {
        Self { text: None }
    }
}

impl Element for SpinnerTransientElement {
    fn render(&self, context: &mut RenderContext) -> Result<(), StreamlitError> {
        let elements = match &self.text {
            Some(text) => vec![crate::proto::Element {
                width_config: Some(crate::proto::streamlit::WidthConfig {
                    width_spec: Some(crate::proto::streamlit::width_config::WidthSpec::UseContent(true)),
                }),
                r#type: Some(element::Type::Spinner(crate::proto::Spinner { text: text.clone(), ..Default::default() })),
                ..Default::default()
            }],
            None => vec![],
        };
        let element_hash = hash(format!("spinner_transient_{:?}", self.text).as_str());
        let mut msg = delta_base_with_path(context.delta_path.clone(), context.active_script_hash.clone(), element_hash);
        msg.r#type = Some(forward_msg::Type::Delta(Delta {
            fragment_id: String::new(),
            // The transient spinner does not advance the element path: the
            // with-block's later elements keep their own positions.
            r#type: Some(delta::Type::NewTransient(crate::proto::Transient { elements })),
        }));
        context.push(msg);
        Ok(())
    }
}

pub(crate) struct ImgsElement {
    urls: Vec<(String, String)>, // (url, caption)
    width: Option<ElementWidth>,
}

impl ImgsElement {
    pub fn new(urls: Vec<(String, String)>, width: Option<ElementWidth>) -> Self {
        Self { urls, width }
    }
}

impl Element for ImgsElement {
    fn render(&self, context: &mut RenderContext) -> Result<(), StreamlitError> {
        let element_hash = hash(format!("imgs_{:?}_{:?}", self.urls, self.width).as_str());
        push_element(
            context,
            element_hash,
            element::Type::Imgs(crate::proto::ImageList {
                imgs: self
                    .urls
                    .iter()
                    .map(|(url, caption)| crate::proto::Image {
                        url: url.clone(),
                        caption: caption.clone(),
                        alt: None,
                    })
                    .collect(),
                link: String::new(),
            }),
            Some(self.width.clone().unwrap_or(ElementWidth::Content)),
            None,
        );
        Ok(())
    }
}

pub(crate) struct AudioElement {
    url: String,
    start_time: Option<i32>,
    end_time: Option<i32>,
    loop_: bool,
    autoplay: bool,
}

/// The playback parameters the measured audio/video calls carry (frozen
/// media-params reference): second-precision start/end, loop, autoplay, and
/// (video) muted/subtitles.
#[derive(Clone, Copy, Debug, Default)]
pub(crate) struct Playback {
    pub start_time: Option<f64>,
    pub end_time: Option<f64>,
    pub loop_: bool,
    pub autoplay: bool,
    pub muted: bool,
}

impl Playback {
    pub(crate) fn time_error(start_time: Option<f64>, end_time: Option<f64>, video: bool) -> Option<AppException> {
        let error = |kind: &str, message: String| AppException::new(kind.into(), message, Vec::new());
        let start = start_time.unwrap_or(0.0);

        // 1. Python 先解析 start，再解析 end；非有限数不进入区间/协议校验。
        if start.is_nan() {
            let message = concat!(
                "Failed to convert 'start_time' to a timedelta. Please use a string in a format supported by ",
                "[Pandas Timedelta constructor](https://pandas.pydata.org/docs/reference/api/pandas.Timedelta.html), ",
                "e.g. `\"10s\"`, `\"15 seconds\"`, or `\"1h23s\"`. Got: nan"
            );
            return Some(error("streamlit.errors.StreamlitAPIException", message.into()).streamlit_markdown());
        }
        if start.is_infinite() {
            return Some(error("OverflowError", "cannot convert float infinity to integer".into()));
        }
        if let Some(end) = end_time {
            if end.is_nan() {
                return Some(error("ValueError", "cannot convert float NaN to integer".into()));
            }
            if end.is_infinite() {
                return Some(error("OverflowError", "cannot convert float infinity to integer".into()));
            }
        }

        // 2. 截断后仅视频拒绝负开始值/倒置区间；音频允许这些输入。
        let start = start.trunc();
        let end = end_time.map(f64::trunc);
        if video && (start < 0.0 || end.is_some_and(|end| end <= start)) {
            return Some(error("streamlit.errors.StreamlitAPIException", "Invalid start_time and end_time combination.".into()).streamlit_markdown());
        }

        // 3. 最后按 protobuf 字段顺序验证范围，不能让 Rust 的 as 饱和截断。
        for value in std::iter::once(start).chain(end) {
            if !(i32::MIN as f64..=i32::MAX as f64).contains(&value) {
                return Some(error("ValueError", format!("Value out of range: {value:.0}")));
            }
        }

        None
    }

    /// Python coerces the times to whole seconds (`int(...)` truncation).
    fn seconds(value: Option<f64>) -> Option<i32> {
        value.map(|time| time.trunc() as i32)
    }
}

impl AudioElement {
    pub fn new(url: String) -> Self {
        Self {
            url,
            start_time: None,
            end_time: None,
            loop_: false,
            autoplay: false,
        }
    }

    pub fn with_playback(mut self, playback: Playback) -> Self {
        self.start_time = Playback::seconds(playback.start_time);
        self.end_time = Playback::seconds(playback.end_time);
        self.loop_ = playback.loop_;
        self.autoplay = playback.autoplay;
        self
    }
}

impl Element for AudioElement {
    fn render(&self, context: &mut RenderContext) -> Result<(), StreamlitError> {
        // The measured audio width sits inside the Audio message as a
        // stretch config; the element level carries none.
        let id = self.autoplay.then(|| {
            playback_id(
                "audio",
                &self.url,
                &Playback {
                    start_time: self.start_time.map(|v| v as f64),
                    end_time: self.end_time.map(|v| v as f64),
                    loop_: self.loop_,
                    autoplay: self.autoplay,
                    muted: false,
                },
                None,
            )
        });
        let element_hash = hash(format!("audio_{}_{}_{:?}_{:?}_{}_{}", self.url, id.as_deref().unwrap_or(""), self.start_time, self.end_time, self.loop_, self.autoplay).as_str());
        push_element(
            context,
            element_hash,
            element::Type::Audio(crate::proto::Audio {
                url: self.url.clone(),
                start_time: self.start_time.unwrap_or(0),
                end_time: self.end_time.unwrap_or(0),
                r#loop: self.loop_,
                autoplay: self.autoplay,
                id: id.unwrap_or_default(),
                width_config: Some(crate::proto::streamlit::WidthConfig {
                    width_spec: Some(crate::proto::streamlit::width_config::WidthSpec::UseStretch(true)),
                }),
                ..Default::default()
            }),
            None,
            None,
        );
        Ok(())
    }
}

/// The element id an autoplaying player carries (measured): the runtime's own
/// identity inputs hashed into the `$$ID-<32hex>-None` shape. Like the
/// dialog id, the digest legitimately differs cross-runtime; only the shape
/// is contractual.
fn playback_id(kind: &str, url: &str, playback: &Playback, subtitles: Option<&str>) -> String {
    let _ = subtitles;
    format!("$$ID-{}-None", hash(&format!("{kind}_{url}_{:?}_{:?}_{}_{}_{}", playback.start_time, playback.end_time, playback.loop_, playback.autoplay, playback.muted)))
}

pub(crate) struct VideoElement {
    url: String,
    playback: Playback,
    subtitles: Vec<crate::proto::SubtitleTrack>,
}

impl VideoElement {
    pub fn new(url: String) -> Self {
        Self {
            url,
            playback: Playback::default(),
            subtitles: Vec::new(),
        }
    }

    pub fn with_playback(mut self, playback: Playback) -> Self {
        self.playback = playback;
        self
    }

    pub fn with_subtitles(mut self, subtitles: Vec<crate::proto::SubtitleTrack>) -> Self {
        self.subtitles = subtitles;
        self
    }
}

impl Element for VideoElement {
    fn render(&self, context: &mut RenderContext) -> Result<(), StreamlitError> {
        let id = self.playback.autoplay.then(|| playback_id("video", &self.url, &self.playback, Some(&format!("{:?}", self.subtitles))));
        let element_hash = hash(
            format!(
                "video_{}_{}_{:?}_{:?}_{}_{}_{}_{:?}",
                self.url,
                id.as_deref().unwrap_or(""),
                self.playback.start_time,
                self.playback.end_time,
                self.playback.loop_,
                self.playback.autoplay,
                self.playback.muted,
                self.subtitles
            )
            .as_str(),
        );
        // The measured video element: the NATIVE type, the relative URL and
        // the stretch width inside the message; element level carries none.
        push_element(
            context,
            element_hash,
            element::Type::Video(crate::proto::Video {
                url: self.url.clone(),
                r#type: crate::proto::video::Type::Native as i32,
                start_time: Playback::seconds(self.playback.start_time).unwrap_or(0),
                end_time: Playback::seconds(self.playback.end_time).unwrap_or(0),
                r#loop: self.playback.loop_,
                autoplay: self.playback.autoplay,
                muted: self.playback.muted,
                id: id.unwrap_or_default(),
                subtitles: self.subtitles.clone(),
                width_config: Some(crate::proto::streamlit::WidthConfig {
                    width_spec: Some(crate::proto::streamlit::width_config::WidthSpec::UseStretch(true)),
                }),
                ..Default::default()
            }),
            None,
            None,
        );
        Ok(())
    }
}

/// How a metric colors its delta. The measured normal/inverse pair derives
/// the proto color from the delta sign; "off" grays it out.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum DeltaColor {
    Normal,
    Inverse,
    Off,
}

impl DeltaColor {
    fn wire(self, positive: bool) -> metric::MetricColor {
        match (self, positive) {
            (Self::Off, _) => metric::MetricColor::Gray,
            (Self::Normal, true) | (Self::Inverse, false) => metric::MetricColor::Green,
            (Self::Normal, false) | (Self::Inverse, true) => metric::MetricColor::Red,
        }
    }
}

pub(crate) struct MetricElement {
    label: String,
    body: String,
    delta: Option<String>,
    delta_color: DeltaColor,
}

/// Python textwrap.dedent preserves trailing/newline text and treats tabs
/// and spaces as distinct indentation; whitespace-only lines become empty.
fn metric_delta_text(delta: &str) -> String {
    let lines: Vec<&str> = delta.split('\n').map(|line| if line.bytes().all(|byte| matches!(byte, b' ' | b'\t')) { "" } else { line }).collect();
    let mut margin: Option<&str> = None;
    for line in lines.iter().filter(|line| !line.is_empty()) {
        let indent = &line[..line.len() - line.trim_start_matches([' ', '\t']).len()];
        margin = Some(match margin {
            None => indent,
            Some(previous) => {
                let common = previous.bytes().zip(indent.bytes()).take_while(|(left, right)| left == right).count();
                &previous[..common]
            }
        });
    }
    let margin = margin.unwrap_or("");
    lines.iter().map(|line| line.strip_prefix(margin).unwrap_or(line)).collect::<Vec<_>>().join("\n")
}

impl MetricElement {
    pub fn new(label: String, body: String, delta: Option<String>, delta_color: DeltaColor) -> Self {
        Self { label, body, delta, delta_color }
    }
}

impl Element for MetricElement {
    fn render(&self, context: &mut RenderContext) -> Result<(), StreamlitError> {
        // 1. 字符串先去公共缩进；只有原始空值或字面 "0" 是中性。
        let delta = self.delta.as_deref().map(metric_delta_text).unwrap_or_default();
        let (direction, color) = match self.delta.as_deref() {
            None | Some("") => (metric::MetricDirection::None, metric::MetricColor::Gray),
            Some(_) if delta == "0" => (metric::MetricDirection::None, metric::MetricColor::Gray),
            Some(_) => {
                let positive = !delta.starts_with('-');
                (if positive { metric::MetricDirection::Up } else { metric::MetricDirection::Down }, self.delta_color.wire(positive))
            }
        };

        // 2. 显示文本与方向使用同一去缩进结果，保留普通文本和单位。
        let element_hash = hash(format!("metric_{}_{}_{}_{:?}_{:?}", self.label, self.body, delta, self.delta_color, direction).as_str());
        push_element(
            context,
            element_hash,
            element::Type::Metric(crate::proto::Metric {
                label: self.label.clone(),
                body: self.body.clone(),
                delta,
                direction: direction as i32,
                color: color as i32,
                label_visibility: Some(crate::proto::LabelVisibility::default()),
                ..Default::default()
            }),
            Some(ElementWidth::Stretch),
            Some(ElementHeight::Content),
        );
        Ok(())
    }
}

pub(crate) struct ProgressElement {
    value: u32,
    text: String,
}

impl ProgressElement {
    pub fn new(value: u32) -> Self {
        Self { value, text: String::new() }
    }

    pub fn set(&mut self, value: u32) {
        self.value = value;
    }

    pub fn set_text(&mut self, text: String) {
        self.text = text;
    }
}

impl Element for ProgressElement {
    fn deferred(&self) -> bool {
        true
    }

    fn render(&self, context: &mut RenderContext) -> Result<(), StreamlitError> {
        let element_hash = hash(format!("progress_{}_{}", self.value, self.text).as_str());
        push_element(context, element_hash, element::Type::Progress(crate::proto::Progress { value: self.value, text: self.text.clone() }), Some(ElementWidth::Stretch), None);
        Ok(())
    }
}

/// Registers image or audio bytes and returns the relative measured URL. A
/// known mime measured to carry no extension (audio/x-wav) addresses bare.
pub(crate) fn media_url(bytes: &[u8], mime: &str) -> Result<String, StreamlitError> {
    let extension = media::extension(mime).ok_or_else(|| StreamlitError::InvalidMessage(format!("unsupported media type '{mime}'")))?;
    let id = media::put(bytes, mime);
    Ok(if extension.is_empty() { format!("/media/{id}") } else { format!("/media/{id}.{extension}") })
}

/// One validated subtitle track: the label plus the media URL of its
/// VTT-formatted text. Mirrors the reference's acceptance rules (frozen
/// media-params): raw text is stripped; empty/VTT text is stored, and
/// detected SRT retains cue identifiers while converting timestamp commas.
pub(crate) fn subtitle_track(label: &str, text: &str) -> Result<crate::proto::SubtitleTrack, String> {
    let invalid = || {
        format!(
            "Failed to process the provided subtitle {}: Invalid `subtitles` value. Supported values: VTT-formatted text, SRT-formatted text.",
            crate::utils::python_error_value(label)
        )
    };
    let text = subtitle_trim(text);
    let content = if text.is_empty() || text.starts_with("WEBVTT") {
        text.as_bytes().to_vec()
    } else if let Some(converted) = srt_to_vtt(text) {
        converted
    } else {
        return Err(invalid());
    };
    let file_name = format!("{}.vtt", crate::utils::hash::blake2b16(label));
    let id = media::put_named_media(&content, "text/vtt", &file_name);
    let url = format!("/media/{id}.vtt");
    Ok(crate::proto::SubtitleTrack { label: label.to_owned(), url })
}

fn subtitle_trim(text: &str) -> &str {
    text.trim_matches(|ch: char| ch.is_whitespace() || matches!(ch, '\u{1c}'..='\u{1f}'))
}

fn srt_timestamp(bytes: &[u8]) -> bool {
    bytes.len() >= 12
        && bytes[..12].iter().enumerate().all(|(index, byte)| match index {
            2 | 5 => *byte == b':',
            8 => *byte == b',',
            _ => byte.is_ascii_digit(),
        })
}

/// Raw string detection follows the SDK's 33-byte UTF-8 prefix. The current
/// numeric classification covers ASCII counters/timestamps, not all Unicode Nd.
fn srt_to_vtt(text: &str) -> Option<Vec<u8>> {
    // 1. 只检查 SDK 实际读取的前缀；换行、空白和 UTF-8 截断影响识别。
    let header = subtitle_trim(std::str::from_utf8(&text.as_bytes()[..text.len().min(33)]).ok()?);
    let mut lines = header.split('\n');
    let counter = lines.next()?;
    if counter.is_empty() || !counter.bytes().all(|byte| byte.is_ascii_digit()) {
        return None;
    }
    let timing = lines.next()?;
    if !timing.as_bytes().windows(29).any(|span| srt_timestamp(&span[..12]) && &span[12..17] == b" --> " && srt_timestamp(&span[17..])) {
        return None;
    }

    // 2. 全局、不重叠地替换时间戳逗号，保留编号、正文和内部换行。
    let mut converted = text.as_bytes().to_vec();
    let mut offset = 0;
    while offset + 12 <= converted.len() {
        if srt_timestamp(&converted[offset..]) {
            converted[offset + 8] = b'.';
            offset += 12;
        } else {
            offset += 1;
        }
    }
    let mut out = b"WEBVTT\n\n".to_vec();
    out.extend_from_slice(&converted);
    Some(out)
}

#[cfg(test)]
mod metric_tests {
    use super::metric_delta_text;

    #[test]
    fn delta_text_matches_frozen_whitespace_cases() -> Result<(), Box<dyn std::error::Error>> {
        let reference: serde_json::Value = serde_json::from_str(include_str!("../../../tests/reference/reference-browser/chat-metric-params/string-delta/trace.json"))?;
        let elements = reference["elements"].as_array().ok_or("missing reference elements")?;
        for (label, input) in [("normal:8", " 0"), ("normal:9", "  -down"), ("normal:10", "\n  up\n  next\n"), ("normal:11", " \t\n")] {
            let expected = elements.iter().find(|element| element["fields"]["label"] == label).ok_or("missing reference case")?;
            assert_eq!(metric_delta_text(input), expected["fields"]["delta"].as_str().ok_or("missing reference delta")?, "{label}");
        }
        Ok(())
    }
}

#[cfg(test)]
mod subtitle_tests {
    use super::*;

    #[test]
    fn subtitle_label_errors_match_frozen_public_sdk_messages() -> Result<(), Box<dyn std::error::Error>> {
        let reference: serde_json::Value = serde_json::from_str(include_str!("../../../tests/reference/reference-browser/media-more/subtitle-text/cases.json"))?;
        let cases = reference["label_cases"].as_array().ok_or("missing subtitle label cases")?;
        assert_eq!(cases.len(), 12);

        for case in cases {
            let result = subtitle_track(case["label"].as_str().ok_or("missing label")?, case["input"].as_str().ok_or("missing input")?);
            assert_eq!(result.err().as_deref(), case["error"].as_str(), "{}", case["name"]);
        }

        Ok(())
    }

    #[test]
    fn subtitle_strings_match_frozen_sdk_bytes_addresses_and_rejections() -> Result<(), Box<dyn std::error::Error>> {
        let reference: serde_json::Value = serde_json::from_str(include_str!("../../../tests/reference/reference-browser/media-more/subtitle-text/cases.json"))?;
        let cases = reference["cases"].as_array().ok_or("missing subtitle cases")?;
        assert_eq!(cases.len(), 22);
        for case in cases.iter().filter(|case| case["name"] == "srt-one").chain(cases.iter().filter(|case| case["name"] != "srt-one")) {
            let result = subtitle_track(case["label"].as_str().ok_or("missing label")?, case["input"].as_str().ok_or("missing input")?);
            if case["accepted"] == true {
                let track = result?;
                let id = track.url.strip_prefix("/media/").and_then(|url| url.strip_suffix(".vtt")).ok_or("subtitle address")?;
                let file = crate::media::stored_file(id).ok_or("stored subtitle")?;
                let expected = serde_json::from_value::<Vec<u8>>(case["content_bytes"].clone())?;
                assert_eq!(String::from_utf8_lossy(&file.bytes), String::from_utf8_lossy(&expected), "{}: complete VTT bytes", case["name"]);
                assert_eq!(file.bytes.as_ref(), expected.as_slice());
                assert_eq!(track.url, case["url"], "{}: complete content URL", case["name"]);
                assert_eq!(file.mime, "text/vtt");
                assert!(!file.download);
            } else {
                assert_eq!(result.err().as_deref(), case["error"].as_str(), "{}: expected SDK rejection", case["name"]);
            }
        }
        Ok(())
    }
}
