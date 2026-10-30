use crate::elements::common::{Element, RenderContext};
use crate::error::StreamlitError;
use crate::proto::{Alert, Delta, delta, delta_base_with_path, element, forward_msg};
use crate::utils::hash::hash;
use unicode_segmentation::UnicodeSegmentation;

fn material_icon_len(value: &str) -> Option<usize> {
    let rest = value.strip_prefix(":material/")?;
    let end = rest.find(':')?;
    let name = &rest[..end];
    (!name.is_empty() && name.bytes().all(|byte| byte.is_ascii_lowercase() || byte.is_ascii_digit() || byte == b'_')).then_some(":material/".len() + end + 1)
}

fn is_single_emoji(value: &str) -> bool {
    // A grapheme boundary alone does not establish emoji validity. Check the
    // complete cluster against the library's Unicode emoji sequence data too.
    value.graphemes(true).next() == Some(value) && emojis::get(value).is_some()
}

fn emoji_len(value: &str) -> Option<usize> {
    let cluster = value.graphemes(true).next()?;
    is_single_emoji(cluster).then_some(cluster.len())
}

/// Width error values follow Python quoting and ASCII escapes. Unicode
/// printability still needs the pinned Python character data; keep those
/// characters unchanged rather than using Rust's different debug repertoire.
pub(crate) fn width_error_value(value: &str) -> String {
    let quote = if value.contains('\'') && !value.contains('"') { '"' } else { '\'' };
    let mut output = String::new();
    output.push(quote);

    for character in value.chars() {
        match character {
            '\\' => output.push_str("\\\\"),
            '\n' => output.push_str("\\n"),
            '\r' => output.push_str("\\r"),
            '\t' => output.push_str("\\t"),
            character if character == quote => {
                output.push('\\');
                output.push(character);
            }
            '\0'..='\u{1f}' | '\u{7f}' => output.push_str(&format!("\\x{:02x}", character as u32)),
            character => output.push(character),
        }
    }

    output.push(quote);
    output
}

pub(crate) fn invalid_icon_message(value: &str) -> String {
    const HINT: &str = "Please use a single emoji or a Material icon shortcode like `:material\u{200b}/thumb_up:`.";
    let shortcode = value.strip_prefix(':').and_then(|rest| rest.strip_suffix(':'));

    // 1. Material 错误优先于普通 shortcode；保留参考的零宽空格与标点差别。
    if value.to_ascii_lowercase().starts_with(":material") {
        let parsed = !value.contains('\n') && shortcode.and_then(|rest| rest.rsplit_once('/')).is_some_and(|(pack, name)| !pack.is_empty() && !name.is_empty());
        let shown = value.replace('/', "\u{200b}/");
        let punctuation = if parsed { "." } else { "" };
        return format!("The value `\"{shown}\"` is not a valid Material icon. Please use a Material icon shortcode like **`:material\u{200b}/thumb_up:`**{punctuation}");
    }
    if shortcode.is_some_and(|name| !name.is_empty() && name.bytes().all(|byte| byte.is_ascii_alphanumeric() || matches!(byte, b'_' | b'+' | b'-'))) {
        return format!("The value \"{value}\" is not a valid icon. Emoji shortcodes are not supported. {HINT}");
    }

    // 2. URL 形状只生成错误，不读取图片；长度按 Unicode 码点截取。
    if value.contains("://") || value.get(..5).is_some_and(|prefix| prefix.eq_ignore_ascii_case("data:")) || value.starts_with("//") {
        let shown = if value.chars().count() > 60 { format!("{}…", value.chars().take(60).collect::<String>()) } else { value.to_owned() };
        return format!("The value \"{shown}\" looks like a URL. Images are not supported for `icon`. {HINT} To follow support for image icons, see https://github.com/streamlit/streamlit/issues/9770.");
    }

    // 3. ASCII 普通名称与非 ASCII emoji 使用各自的既有错误文字。
    if value.is_ascii() {
        return format!("The value \"{value}\" is not a valid icon. {HINT}");
    }
    format!("The value \"{value}\" is not a valid emoji. Please use a single emoji.")
}

pub(crate) fn status_content(body: &str, icon: Option<&str>) -> Result<(String, String), crate::api::StatusError> {
    // 1. 先清理正文；显式图标即使清理后为空，也抑制自动提取。
    let body = crate::utils::clean_text(body);
    if let Some(icon) = icon {
        let icon = icon.trim_matches(crate::utils::python_whitespace);
        if icon.is_empty() || icon == "spinner" || material_icon_len(icon) == Some(icon.len()) || is_single_emoji(icon) {
            return Ok((body, icon.to_string()));
        }
        return Err(crate::api::StatusError::InvalidIcon(icon.to_string()));
    }
    // 2. Material 图标后按 Python 空白规则移除分隔符。
    if let Some(end) = material_icon_len(&body) {
        return Ok((body[end..].trim_start_matches(crate::utils::python_whitespace).to_string(), body[..end].to_string()));
    }

    // 3. Emoji 只吞掉空格、下划线和连字符，不吞 Tab/LF 或 Unicode 空白。
    if let Some(end) = emoji_len(&body) {
        return Ok((body[end..].trim_start_matches([' ', '_', '-']).to_string(), body[..end].to_string()));
    }
    Ok((body, String::new()))
}

pub(crate) struct StatusElement {
    alert: Alert,
}

impl StatusElement {
    pub(crate) fn new(alert: Alert) -> Self {
        Self { alert }
    }
}

impl Element for StatusElement {
    fn render(&self, context: &mut RenderContext) -> Result<(), StreamlitError> {
        let mut msg = delta_base_with_path(context.delta_path.clone(), context.active_script_hash.clone(), hash(&format!("status_{:?}", self.alert)));
        msg.r#type = Some(forward_msg::Type::Delta(Delta {
            fragment_id: String::new(),
            r#type: Some(delta::Type::NewElement(crate::proto::Element {
                r#type: Some(element::Type::Alert(self.alert.clone())),
                ..Default::default()
            })),
        }));
        context.push(msg);
        if let Some(index) = context.delta_path.last_mut() {
            *index += 1;
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::api::{StatusOptions, Streamlit, StreamlitApi};
    use crate::proto::alert::Format;
    use crate::proto::streamlit::{WidthConfig, width_config::WidthSpec};
    use prost::Message;

    #[test]
    fn width_error_quoting_and_ascii_escapes_match_python_reference() -> anyhow::Result<()> {
        let reference: serde_json::Value = serde_json::from_str(include_str!("../../../tests/reference/reference-browser/status/normalization/width-repr/trace.json"))?;
        let elements = reference["elements"].as_array().ok_or_else(|| anyhow::anyhow!("missing width reference"))?;
        let inputs: serde_json::Value = serde_json::from_str(elements[0]["fields"]["body"].as_str().ok_or_else(|| anyhow::anyhow!("missing inputs"))?)?;
        let mut checked = 0;
        for element in &elements[1..] {
            if element["kind"] != "json" {
                continue;
            }
            let report: serde_json::Value = serde_json::from_str(element["fields"]["body"].as_str().ok_or_else(|| anyhow::anyhow!("missing receipt"))?)?;
            let index = report["index"].as_u64().ok_or_else(|| anyhow::anyhow!("missing index"))? as usize;
            if !(20..30).contains(&index) || report["kind"] != "info" {
                continue;
            }
            let value = inputs["error_cases"][index]["width"].as_str().ok_or_else(|| anyhow::anyhow!("missing width"))?;
            let error = crate::StatusError::InvalidWidth(super::width_error_value(value));
            assert_eq!(error.to_string(), report["message"].as_str().ok_or_else(|| anyhow::anyhow!("missing error message"))?);
            checked += 1;
        }
        assert_eq!(checked, 10);
        Ok(())
    }

    #[test]
    fn icon_error_display_matches_reference_without_changing_variant_payload() -> anyhow::Result<()> {
        let reference: serde_json::Value = serde_json::from_str(include_str!("../../../tests/reference/reference-browser/status/normalization/errors/trace.json"))?;
        let elements = reference["elements"].as_array().ok_or_else(|| anyhow::anyhow!("missing error reference elements"))?;
        let inputs: serde_json::Value = serde_json::from_str(elements[0]["fields"]["body"].as_str().ok_or_else(|| anyhow::anyhow!("missing error inputs"))?)?;
        let mut checked = 0;
        for element in &elements[1..] {
            if element["kind"] != "json" {
                continue;
            }
            let report: serde_json::Value = serde_json::from_str(element["fields"]["body"].as_str().ok_or_else(|| anyhow::anyhow!("missing error report"))?)?;
            if report["category"] != "icon" || report["kind"] != "info" {
                continue;
            }
            let index = report["index"].as_u64().ok_or_else(|| anyhow::anyhow!("missing report index"))? as usize;
            let value = inputs["error_cases"][index]["icon"].as_str().ok_or_else(|| anyhow::anyhow!("missing icon input"))?.trim_matches(crate::utils::python_whitespace);
            let error = crate::StatusError::InvalidIcon(value.to_owned());
            assert_eq!(error.to_string(), report["message"].as_str().ok_or_else(|| anyhow::anyhow!("missing icon error message"))?);
            assert!(matches!(error, crate::StatusError::InvalidIcon(payload) if payload == value));
            checked += 1;
        }
        assert_eq!(checked, 12);
        Ok(())
    }

    #[test]
    fn icon_validation_precedes_width_and_spinner_recovers_at_the_same_path() -> anyhow::Result<()> {
        let st = Streamlit::new();
        let (sender, mut receiver) = tokio::sync::mpsc::unbounded_channel();
        let mut context = RenderContext::with_sender("alert-error-priority".into(), sender);
        context.delta_path = vec![0, 0];
        st.app.lock().set_render_context(context);

        for format in [Format::Info, Format::Success, Format::Warning, Format::Error] {
            let options = StatusOptions::new("both invalid").icon("🔥💡").width(0);
            let result = match format {
                Format::Info => st.info(options),
                Format::Success => st.success(options),
                Format::Warning => st.warning(options),
                Format::Error => st.error(options),
                Format::Unused => unreachable!(),
            };
            assert!(matches!(result, Err(crate::StatusError::InvalidIcon(value)) if value == "🔥💡"));
        }
        assert!(matches!(st.info(StatusOptions::new("bad width").icon(" ").width(0)), Err(crate::StatusError::InvalidWidth(value)) if value == "0"));
        assert!(receiver.try_recv().is_err(), "rejected calls do not consume a delta slot");
        st.success(StatusOptions::new("recovered").icon(" spinner ").width(240))?;
        let message = receiver.try_recv()?;
        assert_eq!(message.metadata.as_ref().ok_or_else(|| anyhow::anyhow!("missing recovery path"))?.delta_path, [0, 0]);
        let Some(forward_msg::Type::Delta(delta)) = message.r#type else { anyhow::bail!("missing recovery delta") };
        let Some(delta::Type::NewElement(element)) = delta.r#type else { anyhow::bail!("missing recovery element") };
        let Some(element::Type::Alert(alert)) = element.r#type else { anyhow::bail!("missing recovery alert") };
        assert_eq!(alert.icon, "spinner");
        assert_eq!(alert.format, Format::Success as i32);
        assert!(receiver.try_recv().is_err());
        Ok(())
    }

    #[test]
    fn normalization_precedes_icon_detection_and_keeps_explicit_empty_icon() -> anyhow::Result<()> {
        for (body, icon, expected_body, expected_icon) in [
            ("\n    💡 alpha\n      beta\n", None, "alpha\n  beta", "💡"),
            ("\n    :material/thumb_up: alpha\n      beta\n", None, "alpha\n  beta", ":material/thumb_up:"),
            (" \t💡 keep \n", Some(" \t\n"), "💡 keep", ""),
            ("  body\r\n    next  ", Some(" 🧊 "), "body\r\n  next", "🧊"),
            (" \u{1c}body\u{1f} ", Some("\u{1c}👩‍💻\u{1f}"), "body", "👩‍💻"),
            ("💡\u{1c}after", None, "\u{1c}after", "💡"),
            ("💡_ -__ after", None, "after", "💡"),
            ("💡\tafter", None, "\tafter", "💡"),
            ("💡\nafter", None, "\nafter", "💡"),
            ("💡\u{a0}after", None, "\u{a0}after", "💡"),
            (":material/thumb_up:\u{1c}after", None, "after", ":material/thumb_up:"),
            (":material/thumb_up:__-after", None, "__-after", ":material/thumb_up:"),
        ] {
            assert_eq!(status_content(body, icon)?, (expected_body.into(), expected_icon.into()));
        }
        Ok(())
    }

    #[test]
    fn leading_separator_rules_match_direct_python_oracle() -> anyhow::Result<()> {
        let reference: serde_json::Value = serde_json::from_str(include_str!("../../../tests/reference/reference-browser/status/normalization/icon-separators.json"))?;
        let cases = reference["cases"].as_array().ok_or_else(|| anyhow::anyhow!("missing separator cases"))?;
        assert_eq!(cases.len(), 16);
        for case in cases {
            assert_eq!(
                status_content(case["input"].as_str().ok_or_else(|| anyhow::anyhow!("missing separator input"))?, None)?,
                (
                    case["body"].as_str().ok_or_else(|| anyhow::anyhow!("missing separator body"))?.into(),
                    case["icon"].as_str().ok_or_else(|| anyhow::anyhow!("missing separator icon"))?.into()
                )
            );
        }
        Ok(())
    }

    // Expected values come from the real Python 1.66.1 browser capture, not
    // generated Rust output. This file deliberately exercises only measured cases.
    fn assert_reference_case(case: &str) -> anyhow::Result<()> {
        let reference: serde_json::Value = serde_json::from_str(include_str!("../../../tests/reference/reference-browser/status/trace-status.json"))?;
        assert_eq!(reference["reference_version"], "1.66.1");
        let alerts = reference["cases"][case]["alerts"]
            .as_array()
            .ok_or_else(|| anyhow::anyhow!("status reference requires reference[\"cases\"][case][\"alerts\"].as_array()"))?;
        let st = Streamlit::new();
        let (sender, mut receiver) = tokio::sync::mpsc::unbounded_channel();
        let mut context = RenderContext::with_sender("status-test".to_string(), sender);
        context.delta_path = vec![0, 0];
        context.active_script_hash = "status-script".to_string();
        st.app.lock().set_render_context(context);

        for (index, observation) in alerts.iter().enumerate() {
            let wire = &observation["wire"];
            let body = wire["body"].as_str().ok_or_else(|| anyhow::anyhow!("status reference requires wire[\"body\"].as_str()"))?;
            let format = Format::from_str_name(wire["format"].as_str().ok_or_else(|| anyhow::anyhow!("status reference requires wire format"))?).ok_or_else(|| anyhow::anyhow!("reference status format must be recognized"))?;
            let mut options = StatusOptions::new(body);
            if let Some(icon) = wire["icon"].as_str() {
                options = options.icon(icon);
            } else if body.starts_with("INFO-NOICON-BODY") {
                options = options.icon("");
            }
            if let Some(width) = wire["widthConfig"]["pixelWidth"].as_i64() {
                options = options.width(i32::try_from(width)?);
            }
            if let Some(title) = wire["title"].as_str() {
                options = options.title(title);
            }
            match format {
                Format::Info => st.info(options),
                Format::Success => st.success(options),
                Format::Warning => st.warning(options),
                Format::Error => st.error(options),
                Format::Unused => panic!("not a measured status format"),
            }?;

            let msg = receiver.try_recv()?;
            let msg = crate::proto::ForwardMsg::decode(msg.encode_to_vec().as_slice())?;
            let metadata = msg.metadata.as_ref().ok_or_else(|| anyhow::anyhow!("status message must contain delta metadata"))?;
            assert_eq!(metadata.delta_path, vec![0, u32::try_from(index)?]);
            assert_eq!(metadata.active_script_hash, "status-script");
            let Some(forward_msg::Type::Delta(delta)) = msg.r#type else { panic!("missing delta") };
            let Some(delta::Type::NewElement(element)) = delta.r#type else { panic!("missing element") };
            assert!(element.width_config.is_none());
            assert!(element.height_config.is_none());
            assert!(element.text_alignment_config.is_none());
            let Some(element::Type::Alert(alert)) = element.r#type else { panic!("missing alert") };
            let width_spec = if let Some(width) = wire["widthConfig"]["pixelWidth"].as_u64() {
                WidthSpec::PixelWidth(u32::try_from(width)?)
            } else {
                assert_eq!(wire["widthConfig"]["useStretch"], true);
                WidthSpec::UseStretch(true)
            };
            assert_eq!(
                alert,
                Alert {
                    body: body.to_string(),
                    format: format as i32,
                    icon: wire["icon"].as_str().unwrap_or_default().to_string(),
                    width_config: Some(WidthConfig { width_spec: Some(width_spec) }),
                    title: wire["title"].as_str().unwrap_or_default().to_string(),
                }
            );
        }
        assert!(receiver.try_recv().is_err());
        assert_eq!(
            st.app.lock().render_context_mut().ok_or_else(|| anyhow::anyhow!("status test must retain its render context"))?.delta_path,
            vec![0, u32::try_from(alerts.len())?]
        );

        Ok(())
    }

    #[test]
    fn defaults_match_python_browser_oracle() -> anyhow::Result<()> {
        assert_reference_case("defaults")?;

        Ok(())
    }

    #[test]
    fn explicit_icon_width_title_and_middle_emoji_match_python_browser_oracle() -> anyhow::Result<()> {
        assert_reference_case("variants")?;

        Ok(())
    }

    #[test]
    fn leading_icons_and_explicit_empty_icon_match_browser_oracle() -> anyhow::Result<()> {
        let reference: serde_json::Value = serde_json::from_str(include_str!("../../../tests/reference/reference-browser/status/trace-status-leading.json"))?;
        let inputs = [
            ("leading_emoji", "💡 INFO-LEADING-EMOJI this body starts with an emoji", None),
            ("leading_emoji_noicon", "💡 INFO-LEADING-NOICON body keeps its emoji", Some("")),
            ("leading_material", ":material/thumb_up: INFO-LEADING-MATERIAL body starts with a shortcode", None),
        ];
        for (case, body, icon) in inputs {
            let st = Streamlit::new();
            let (sender, mut receiver) = tokio::sync::mpsc::unbounded_channel();
            st.app.lock().set_render_context(RenderContext::with_sender("leading-test".to_string(), sender));
            let mut options = StatusOptions::new(body);
            if let Some(icon) = icon {
                options = options.icon(icon);
            }
            st.info(options)?;
            let Some(forward_msg::Type::Delta(delta)) = receiver.try_recv()?.r#type else { panic!("missing delta") };
            let Some(delta::Type::NewElement(element)) = delta.r#type else { panic!("missing element") };
            let Some(element::Type::Alert(alert)) = element.r#type else { panic!("missing alert") };
            let wire = &reference["cases"][case]["alerts"][0];
            assert_eq!(alert.body, wire["body"].as_str().ok_or_else(|| anyhow::anyhow!("status reference requires wire[\"body\"].as_str()"))?);
            assert_eq!(alert.icon, wire["icon"].as_str().unwrap_or_default());
            assert_eq!(alert.format, Format::Info as i32);
            assert_eq!(alert.width_config.ok_or_else(|| anyhow::anyhow!("status alert must contain width configuration"))?.width_spec, Some(WidthSpec::UseStretch(true)));
        }

        Ok(())
    }

    #[test]
    fn compound_icons_and_leading_cluster_match_python_browser_oracle() -> anyhow::Result<()> {
        let reference: serde_json::Value = serde_json::from_str(include_str!("../../../tests/reference/reference-browser/status/trace-status-icon-composite.json"))?;
        assert_eq!(reference["reference_version"], "1.66.1");
        for input in reference["icon_rule"]["accepted_multi_code_point_clusters"]
            .as_array()
            .ok_or_else(|| anyhow::anyhow!("status reference requires reference[\"icon_rule\"][\"accepted_multi_code_point_clusters\"].as_array()"))?
        {
            let case = input["case"].as_str().ok_or_else(|| anyhow::anyhow!("status reference requires input[\"case\"].as_str()"))?;
            let icon = input["value"].as_str().ok_or_else(|| anyhow::anyhow!("status reference requires input[\"value\"].as_str()"))?;
            let wire = &reference["cases"][case]["alerts"][0];
            assert!(
                reference["cases"][case]["exceptions"]
                    .as_array()
                    .ok_or_else(|| anyhow::anyhow!("status reference requires reference[\"cases\"][case][\"exceptions\"].as_array()"))?
                    .is_empty()
            );
            assert_compound_alert(StatusOptions::new(wire["body"].as_str().ok_or_else(|| anyhow::anyhow!("status reference requires wire[\"body\"].as_str()"))?).icon(icon), wire)?;
        }
        let wire = &reference["cases"]["leading_composite"]["alerts"][0];
        assert_compound_alert(StatusOptions::new("👩‍💻 INFO-LEADING-COMPOSITE body starts with a composite emoji"), wire)?;

        Ok(())
    }

    fn assert_compound_alert(options: StatusOptions, wire: &serde_json::Value) -> anyhow::Result<()> {
        let st = Streamlit::new();
        let (sender, mut receiver) = tokio::sync::mpsc::unbounded_channel();
        let mut context = RenderContext::with_sender("compound-test".to_string(), sender);
        context.delta_path = vec![0, 0];
        st.app.lock().set_render_context(context);
        st.info(options)?;
        let msg = receiver.try_recv()?;
        let msg = crate::proto::ForwardMsg::decode(msg.encode_to_vec().as_slice())?;
        assert_eq!(msg.metadata.as_ref().ok_or_else(|| anyhow::anyhow!("status message must contain delta metadata"))?.delta_path, vec![0, 0]);
        let Some(forward_msg::Type::Delta(delta)) = msg.r#type else { panic!("missing delta") };
        let Some(delta::Type::NewElement(element)) = delta.r#type else { panic!("missing element") };
        assert!(element.width_config.is_none());
        assert!(element.height_config.is_none());
        let Some(element::Type::Alert(alert)) = element.r#type else { panic!("missing alert") };
        assert_eq!(alert.body, wire["body"].as_str().ok_or_else(|| anyhow::anyhow!("status reference requires wire[\"body\"].as_str()"))?);
        assert_eq!(alert.icon, wire["icon"].as_str().ok_or_else(|| anyhow::anyhow!("status reference requires wire[\"icon\"].as_str()"))?);
        assert_eq!(alert.format, Format::Info as i32);
        assert_eq!(alert.width_config.ok_or_else(|| anyhow::anyhow!("status alert must contain width configuration"))?.width_spec, Some(WidthSpec::UseStretch(true)));
        assert!(receiver.try_recv().is_err());

        Ok(())
    }

    #[test]
    fn two_independent_emoji_return_observed_error_without_emitting_an_alert() -> anyhow::Result<()> {
        let reference: serde_json::Value = serde_json::from_str(include_str!("../../../tests/reference/reference-browser/status/trace-status-icon-composite.json"))?;
        let invalid = reference["icon_rule"]["rejected"]["value"]
            .as_str()
            .ok_or_else(|| anyhow::anyhow!("status reference requires reference[\"icon_rule\"][\"rejected\"][\"value\"].as_str()"))?;
        let st = Streamlit::new();
        let (sender, mut receiver) = tokio::sync::mpsc::unbounded_channel();
        let mut context = RenderContext::with_sender("invalid-compound-test".to_string(), sender);
        context.delta_path = vec![0, 0];
        st.app.lock().set_render_context(context);
        let error = st.info(StatusOptions::new("INFO-ICON-TWO body").icon(invalid)).err().ok_or_else(|| anyhow::anyhow!("compound icon must be rejected"))?;
        assert_eq!(
            error.to_string(),
            reference["cases"]["icon_two_emoji"]["exceptions"][0]["message"]
                .as_str()
                .ok_or_else(|| anyhow::anyhow!("status reference requires reference[\"cases\"][\"icon_two_emoji\"][\"exceptions\"][0][\"message\"].as_str()"))?
        );
        assert!(
            reference["cases"]["icon_two_emoji"]["alerts"]
                .as_array()
                .ok_or_else(|| anyhow::anyhow!("status reference requires reference[\"cases\"][\"icon_two_emoji\"][\"alerts\"].as_array()"))?
                .is_empty()
        );
        assert!(receiver.try_recv().is_err());
        let mut app = st.app.lock();
        let context = app.render_context_mut().ok_or_else(|| anyhow::anyhow!("status test must retain its render context"))?;
        assert_eq!(context.delta_path, vec![0, 0]);
        assert!(context.stream.is_empty());

        Ok(())
    }

    #[test]
    fn unicode_sequence_validation_uses_data_and_preserves_input() -> anyhow::Result<()> {
        // Rust-side validation regressions, beyond the captured Python cases.
        // These do not establish acceptance parity for the entire Unicode set.
        for icon in ["👨‍👩‍👧‍👦", "🧑🏽‍🏫", "🇺🇳", "1️⃣", "❤️", "❤"] {
            assert!(is_single_emoji(icon), "{icon:?}");
            assert_eq!(status_content("body", Some(icon))?, ("body".to_string(), icon.to_string()));
            assert_eq!(status_content(&format!("{icon} body"), None)?, ("body".to_string(), icon.to_string()));
        }
        for icon in ["a\u{301}", "👩‍x", "🔥💡", "👍🏽💡", "🇨🇳🇺🇳", "\u{200d}"] {
            assert!(!is_single_emoji(icon), "{icon:?}");
            assert!(status_content("body", Some(icon)).is_err());
        }

        Ok(())
    }

    #[test]
    fn invalid_width_returns_the_observed_message_without_appending_an_element() -> anyhow::Result<()> {
        let reference: serde_json::Value = serde_json::from_str(include_str!("../../../tests/reference/reference-browser/status/trace-status-leading.json"))?;
        let st = Streamlit::new();
        let (sender, mut receiver) = tokio::sync::mpsc::unbounded_channel();
        let mut context = RenderContext::with_sender("invalid-test".to_string(), sender);
        context.delta_path = vec![0, 0];
        st.app.lock().set_render_context(context);
        st.info("INFO-BODY before the invalid call")?;
        receiver.try_recv()?;
        let error = st.info(StatusOptions::new("invalid width follows").width("bogus")).err().ok_or_else(|| anyhow::anyhow!("invalid width must be rejected"))?;
        assert_eq!(
            error.to_string(),
            reference["cases"]["invalid_width"]["exceptions"][0]["message"]
                .as_str()
                .ok_or_else(|| anyhow::anyhow!("status reference requires reference[\"cases\"][\"invalid_width\"][\"exceptions\"][0][\"message\"].as_str()"))?
        );
        assert!(receiver.try_recv().is_err());
        let mut app = st.app.lock();
        let context = app.render_context_mut().ok_or_else(|| anyhow::anyhow!("status test must retain its render context"))?;
        assert_eq!(context.delta_path, vec![0, 1]);
        assert_eq!(context.stream.len(), 1);

        Ok(())
    }

    #[test]
    fn rust_parameter_boundaries_and_markdown_are_explicit() -> anyhow::Result<()> {
        use crate::api::StatusError;
        let st = Streamlit::new();
        let (sender, mut receiver) = tokio::sync::mpsc::unbounded_channel();
        st.app.lock().set_render_context(RenderContext::with_sender("boundary-test".to_string(), sender));
        for width in [0, -1, i32::MIN] {
            assert!(matches!(st.warning(StatusOptions::new("bad width").width(width)), Err(StatusError::InvalidWidth(_))));
        }
        assert!(matches!(st.error(StatusOptions::new("bad width").width("content")), Err(StatusError::InvalidWidth(_))));
        for icon in ["hello", "图", ":smile:", ":material/:", ":material/thumb_up:trailing"] {
            assert!(matches!(st.success(StatusOptions::new("bad icon").icon(icon)), Err(StatusError::InvalidIcon(_))));
        }
        assert!(matches!(st.info(StatusOptions::new("not an emoji sequence").icon("👩‍x")), Err(StatusError::InvalidIcon(_))));
        assert!(receiver.try_recv().is_err());
        let body = "**bold** _italic_ `code` [link](https://streamlit.io)\n\n<script>literal</script>";
        st.info(StatusOptions::new(body).icon("").width(1).title("**Title**"))?;
        let Some(forward_msg::Type::Delta(delta)) = receiver.try_recv()?.r#type else { panic!("missing delta") };
        let Some(delta::Type::NewElement(element)) = delta.r#type else { panic!("missing element") };
        let Some(element::Type::Alert(alert)) = element.r#type else { panic!("missing alert") };
        assert_eq!(alert.body, body);
        assert_eq!(alert.title, "**Title**");
        assert_eq!(alert.width_config.ok_or_else(|| anyhow::anyhow!("status alert must contain width configuration"))?.width_spec, Some(WidthSpec::PixelWidth(1)));

        Ok(())
    }
}
