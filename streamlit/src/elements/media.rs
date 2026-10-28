//! The media and presentation elements measured on the Python 1.66.1
//! reference (see .codex/compatibility.md, Media route): the image list with
//! relative content-addressed URLs, the audio element with its stretch width
//! inside the message, the metric with direction/color derived from the delta
//! sign, and the coalescing progress bar.

use crate::elements::common::{Element, ElementHeight, ElementWidth, RenderContext};
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

impl MetricElement {
    pub fn new(label: String, body: String, delta: Option<String>, delta_color: DeltaColor) -> Self {
        Self { label, body, delta, delta_color }
    }
}

impl Element for MetricElement {
    fn render(&self, context: &mut RenderContext) -> Result<(), StreamlitError> {
        // The direction follows the delta's numeric sign, read off the first
        // number word: the measured "2 °F" points UP and "-3 mph" DOWN, so
        // trailing unit words do not break the parse. No number word at all
        // has no direction (only the UP/DOWN pair is measured).
        let sign = self
            .delta
            .as_deref()
            .and_then(|delta| delta.split_whitespace().next())
            .and_then(|token| token.replace(',', "").parse::<f64>().ok())
            .map(|number| number > 0.0);
        let (direction, color) = match sign {
            Some(true) => (metric::MetricDirection::Up, self.delta_color.wire(true)),
            Some(false) => (metric::MetricDirection::Down, self.delta_color.wire(false)),
            None => (metric::MetricDirection::None, metric::MetricColor::Red),
        };
        let element_hash = hash(format!("metric_{}_{}_{}_{:?}_{:?}", self.label, self.body, self.delta.as_deref().unwrap_or(""), self.delta_color, direction).as_str());
        push_element(
            context,
            element_hash,
            element::Type::Metric(crate::proto::Metric {
                label: self.label.clone(),
                body: self.body.clone(),
                delta: self.delta.clone().unwrap_or_default(),
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
/// media-params): text starting `WEBVTT` passes as-is; SRT (numeric first
/// line, `hh:mm:ss,mmm --> hh:mm:ss,mmm` second line) is converted; anything
/// else is rejected with the measured message.
pub(crate) fn subtitle_track(label: &str, text: &str) -> Result<crate::proto::SubtitleTrack, String> {
    let invalid = || format!("Failed to process the provided subtitle '{label}': Invalid `subtitles` value. Supported values: VTT-formatted text, SRT-formatted text.");
    let content = if text.trim_start().starts_with("WEBVTT") {
        text.as_bytes().to_vec()
    } else if let Some(converted) = srt_to_vtt(text) {
        converted
    } else {
        return Err(invalid());
    };
    let url = media_url(&content, "text/vtt").map_err(|error| format!("Failed to process the provided subtitle '{label}': {error}"))?;
    Ok(crate::proto::SubtitleTrack { label: label.to_owned(), url })
}

/// The reference's SRT detection and conversion: a numeric first line and an
/// SRT timestamp second line; conversion rewrites `,mmm` to `.mmm` and
/// prepends the WEBVTT header.
fn srt_to_vtt(text: &str) -> Option<Vec<u8>> {
    let mut lines = text.lines();
    let first = lines.next()?.trim();
    let second = lines.next()?.trim();
    if first.is_empty() || !first.chars().all(|c| c.is_ascii_digit()) {
        return None;
    }
    // "dd:dd:dd,ddd --> dd:dd:dd,ddd": each side is 12 chars with ':' at 2/5
    // and ',' at 8; the arrow joins them with single spaces.
    let (start, end) = second.split_once(" --> ")?;
    let stamp = |value: &str| value.len() == 12 && value.as_bytes()[2] == b':' && value.as_bytes()[5] == b':' && value.as_bytes()[8] == b',' && value.as_bytes().iter().enumerate().all(|(index, byte)| matches!(index, 2 | 5 | 8) || byte.is_ascii_digit());
    let valid = stamp(start) && stamp(end);
    if !valid {
        return None;
    }
    let mut out = String::from("WEBVTT\n\n");
    for line in text.lines().skip(1) {
        // Only timestamp lines carry the comma; cue text passes through.
        if let Some((stamp, rest)) = line.split_once(" --> ") {
            let converted = stamp.replace(',', ".");
            let rest = rest.split(',').next().map(|tail| format!(".{tail}")).unwrap_or_default();
            out.push_str(&format!("{converted} --> {rest}\n"));
        } else {
            out.push_str(line);
            out.push('\n');
        }
    }
    Some(out.into_bytes())
}
