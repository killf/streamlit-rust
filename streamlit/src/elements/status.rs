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

pub(crate) fn status_content(body: &str, icon: Option<&str>) -> Result<(String, String), crate::api::StatusError> {
    if let Some(icon) = icon {
        if icon.is_empty() || material_icon_len(icon) == Some(icon.len()) || is_single_emoji(icon) {
            return Ok((body.to_string(), icon.to_string()));
        }
        return Err(crate::api::StatusError::InvalidIcon(icon.to_string()));
    }
    if let Some(end) = material_icon_len(body).or_else(|| emoji_len(body)) {
        return Ok((body[end..].trim_start().to_string(), body[..end].to_string()));
    }
    Ok((body.to_string(), String::new()))
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

    // Expected values come from the real Python 1.66.1 browser capture, not
    // generated Rust output. This file deliberately exercises only measured cases.
    fn assert_reference_case(case: &str) {
        let reference: serde_json::Value = serde_json::from_str(include_str!("../../../tests/reference/reference-browser/status/trace-status.json")).unwrap();
        assert_eq!(reference["reference_version"], "1.66.1");
        let alerts = reference["cases"][case]["alerts"].as_array().unwrap();
        let st = Streamlit::new();
        let (sender, mut receiver) = tokio::sync::mpsc::unbounded_channel();
        let mut context = RenderContext::with_sender("status-test".to_string(), sender);
        context.delta_path = vec![0, 0];
        context.active_script_hash = "status-script".to_string();
        st.app.lock().set_render_context(context);

        for (index, observation) in alerts.iter().enumerate() {
            let wire = &observation["wire"];
            let body = wire["body"].as_str().unwrap();
            let format = Format::from_str_name(wire["format"].as_str().unwrap()).unwrap();
            let mut options = StatusOptions::new(body);
            if let Some(icon) = wire["icon"].as_str() {
                options = options.icon(icon);
            } else if body.starts_with("INFO-NOICON-BODY") {
                options = options.icon("");
            }
            if let Some(width) = wire["widthConfig"]["pixelWidth"].as_i64() {
                options = options.width(i32::try_from(width).unwrap());
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
            }
            .unwrap();

            let msg = receiver.try_recv().unwrap();
            let msg = crate::proto::ForwardMsg::decode(msg.encode_to_vec().as_slice()).unwrap();
            let metadata = msg.metadata.as_ref().unwrap();
            assert_eq!(metadata.delta_path, vec![0, u32::try_from(index).unwrap()]);
            assert_eq!(metadata.active_script_hash, "status-script");
            let Some(forward_msg::Type::Delta(delta)) = msg.r#type else { panic!("missing delta") };
            let Some(delta::Type::NewElement(element)) = delta.r#type else { panic!("missing element") };
            assert!(element.width_config.is_none());
            assert!(element.height_config.is_none());
            assert!(element.text_alignment_config.is_none());
            let Some(element::Type::Alert(alert)) = element.r#type else { panic!("missing alert") };
            let width_spec = if let Some(width) = wire["widthConfig"]["pixelWidth"].as_u64() {
                WidthSpec::PixelWidth(u32::try_from(width).unwrap())
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
        assert_eq!(st.app.lock().render_context_mut().unwrap().delta_path, vec![0, u32::try_from(alerts.len()).unwrap()]);
    }

    #[test]
    fn defaults_match_python_browser_oracle() {
        assert_reference_case("defaults");
    }

    #[test]
    fn explicit_icon_width_title_and_middle_emoji_match_python_browser_oracle() {
        assert_reference_case("variants");
    }

    #[test]
    fn leading_icons_and_explicit_empty_icon_match_browser_oracle() {
        let reference: serde_json::Value = serde_json::from_str(include_str!("../../../tests/reference/reference-browser/status/trace-status-leading.json")).unwrap();
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
            st.info(options).unwrap();
            let Some(forward_msg::Type::Delta(delta)) = receiver.try_recv().unwrap().r#type else { panic!("missing delta") };
            let Some(delta::Type::NewElement(element)) = delta.r#type else { panic!("missing element") };
            let Some(element::Type::Alert(alert)) = element.r#type else { panic!("missing alert") };
            let wire = &reference["cases"][case]["alerts"][0];
            assert_eq!(alert.body, wire["body"].as_str().unwrap());
            assert_eq!(alert.icon, wire["icon"].as_str().unwrap_or_default());
            assert_eq!(alert.format, Format::Info as i32);
            assert_eq!(alert.width_config.unwrap().width_spec, Some(WidthSpec::UseStretch(true)));
        }
    }

    #[test]
    fn compound_icons_and_leading_cluster_match_python_browser_oracle() {
        let reference: serde_json::Value = serde_json::from_str(include_str!("../../../tests/reference/reference-browser/status/trace-status-icon-composite.json")).unwrap();
        assert_eq!(reference["reference_version"], "1.66.1");
        for input in reference["icon_rule"]["accepted_multi_code_point_clusters"].as_array().unwrap() {
            let case = input["case"].as_str().unwrap();
            let icon = input["value"].as_str().unwrap();
            let wire = &reference["cases"][case]["alerts"][0];
            assert!(reference["cases"][case]["exceptions"].as_array().unwrap().is_empty());
            assert_compound_alert(StatusOptions::new(wire["body"].as_str().unwrap()).icon(icon), wire);
        }
        let wire = &reference["cases"]["leading_composite"]["alerts"][0];
        assert_compound_alert(StatusOptions::new("👩‍💻 INFO-LEADING-COMPOSITE body starts with a composite emoji"), wire);
    }

    fn assert_compound_alert(options: StatusOptions, wire: &serde_json::Value) {
        let st = Streamlit::new();
        let (sender, mut receiver) = tokio::sync::mpsc::unbounded_channel();
        let mut context = RenderContext::with_sender("compound-test".to_string(), sender);
        context.delta_path = vec![0, 0];
        st.app.lock().set_render_context(context);
        st.info(options).unwrap();
        let msg = receiver.try_recv().unwrap();
        let msg = crate::proto::ForwardMsg::decode(msg.encode_to_vec().as_slice()).unwrap();
        assert_eq!(msg.metadata.as_ref().unwrap().delta_path, vec![0, 0]);
        let Some(forward_msg::Type::Delta(delta)) = msg.r#type else { panic!("missing delta") };
        let Some(delta::Type::NewElement(element)) = delta.r#type else { panic!("missing element") };
        assert!(element.width_config.is_none());
        assert!(element.height_config.is_none());
        let Some(element::Type::Alert(alert)) = element.r#type else { panic!("missing alert") };
        assert_eq!(alert.body, wire["body"].as_str().unwrap());
        assert_eq!(alert.icon, wire["icon"].as_str().unwrap());
        assert_eq!(alert.format, Format::Info as i32);
        assert_eq!(alert.width_config.unwrap().width_spec, Some(WidthSpec::UseStretch(true)));
        assert!(receiver.try_recv().is_err());
    }

    #[test]
    fn two_independent_emoji_return_observed_error_without_emitting_an_alert() {
        let reference: serde_json::Value = serde_json::from_str(include_str!("../../../tests/reference/reference-browser/status/trace-status-icon-composite.json")).unwrap();
        let invalid = reference["icon_rule"]["rejected"]["value"].as_str().unwrap();
        let st = Streamlit::new();
        let (sender, mut receiver) = tokio::sync::mpsc::unbounded_channel();
        let mut context = RenderContext::with_sender("invalid-compound-test".to_string(), sender);
        context.delta_path = vec![0, 0];
        st.app.lock().set_render_context(context);
        let error = st.info(StatusOptions::new("INFO-ICON-TWO body").icon(invalid)).unwrap_err();
        assert_eq!(error.to_string(), reference["cases"]["icon_two_emoji"]["exceptions"][0]["message"].as_str().unwrap());
        assert!(reference["cases"]["icon_two_emoji"]["alerts"].as_array().unwrap().is_empty());
        assert!(receiver.try_recv().is_err());
        let mut app = st.app.lock();
        let context = app.render_context_mut().unwrap();
        assert_eq!(context.delta_path, vec![0, 0]);
        assert!(context.stream.is_empty());
    }

    #[test]
    fn unicode_sequence_validation_uses_data_and_preserves_input() {
        // Rust-side validation regressions, beyond the captured Python cases.
        // These do not establish acceptance parity for the entire Unicode set.
        for icon in ["👨‍👩‍👧‍👦", "🧑🏽‍🏫", "🇺🇳", "1️⃣", "❤️", "❤"] {
            assert!(is_single_emoji(icon), "{icon:?}");
            assert_eq!(status_content("body", Some(icon)).unwrap(), ("body".to_string(), icon.to_string()));
            assert_eq!(status_content(&format!("{icon} body"), None).unwrap(), ("body".to_string(), icon.to_string()));
        }
        for icon in ["a\u{301}", "👩‍x", "🔥💡", "👍🏽💡", "🇨🇳🇺🇳", "\u{200d}"] {
            assert!(!is_single_emoji(icon), "{icon:?}");
            assert!(status_content("body", Some(icon)).is_err());
        }
    }

    #[test]
    fn invalid_width_returns_the_observed_message_without_appending_an_element() {
        let reference: serde_json::Value = serde_json::from_str(include_str!("../../../tests/reference/reference-browser/status/trace-status-leading.json")).unwrap();
        let st = Streamlit::new();
        let (sender, mut receiver) = tokio::sync::mpsc::unbounded_channel();
        let mut context = RenderContext::with_sender("invalid-test".to_string(), sender);
        context.delta_path = vec![0, 0];
        st.app.lock().set_render_context(context);
        st.info("INFO-BODY before the invalid call").unwrap();
        receiver.try_recv().unwrap();
        let error = st.info(StatusOptions::new("invalid width follows").width("bogus")).unwrap_err();
        assert_eq!(error.to_string(), reference["cases"]["invalid_width"]["exceptions"][0]["message"].as_str().unwrap());
        assert!(receiver.try_recv().is_err());
        let mut app = st.app.lock();
        let context = app.render_context_mut().unwrap();
        assert_eq!(context.delta_path, vec![0, 1]);
        assert_eq!(context.stream.len(), 1);
    }

    #[test]
    fn rust_parameter_boundaries_and_markdown_are_explicit() {
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
        st.info(StatusOptions::new(body).icon("").width(1).title("**Title**")).unwrap();
        let Some(forward_msg::Type::Delta(delta)) = receiver.try_recv().unwrap().r#type else { panic!("missing delta") };
        let Some(delta::Type::NewElement(element)) = delta.r#type else { panic!("missing element") };
        let Some(element::Type::Alert(alert)) = element.r#type else { panic!("missing alert") };
        assert_eq!(alert.body, body);
        assert_eq!(alert.title, "**Title**");
        assert_eq!(alert.width_config.unwrap().width_spec, Some(WidthSpec::PixelWidth(1)));
    }
}
