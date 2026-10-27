//! Differential element fields from the eight real Chrome reference captures.
//! Only the opaque ID digest is normalized; its shape and key suffix are checked.
use super::*;
use crate::SessionState;
use crate::elements::common::RenderContext;
use crate::proto::{WidgetState, delta, forward_msg, widget_state};
use prost::Message;
use serde_json::Value as Json;
use std::collections::HashMap;

type TestResult<T = ()> = Result<T, Box<dyn std::error::Error>>;

fn fields(value: &Json, allowed: &[&str]) -> TestResult {
    for key in value.as_object().ok_or("reference element must be a JSON object")?.keys() {
        assert!(allowed.contains(&key.as_str()), "unhandled reference field {key}");
    }
    Ok(())
}
fn string(value: &Json, key: &str) -> String {
    value[key].as_str().unwrap_or_default().into()
}
fn boolean(value: &Json, key: &str) -> bool {
    value[key].as_bool().unwrap_or(false)
}
fn numbers(value: &Json, key: &str) -> TestResult<Vec<f64>> {
    let Some(array) = value[key].as_array() else { return Ok(Vec::new()) };
    Ok(array.iter().map(|number| number.as_f64().ok_or("reference numeric array must contain numbers")).collect::<Result<Vec<_>, _>>()?)
}

fn expected_element(value: &Json) -> TestResult<proto::Element> {
    use proto::streamlit::{WidthConfig, width_config::WidthSpec};
    fields(value, &["selectbox", "slider", "checkbox", "widthConfig", "hasOneShotEffect"])?;
    let width = &value["widthConfig"];
    fields(width, &["useContent", "useStretch"])?;
    let width_spec = if boolean(width, "useContent") {
        WidthSpec::UseContent(true)
    } else {
        assert!(boolean(width, "useStretch"));
        WidthSpec::UseStretch(true)
    };
    let visibility = |v: &Json| {
        assert_eq!(v["labelVisibility"], serde_json::json!({}));
        Some(proto::LabelVisibility { value: 0 })
    };
    let body = if let Some(v) = value.get("selectbox") {
        fields(v, &["id", "label", "default", "options", "setValue", "labelVisibility", "acceptNewOptions", "rawValue", "disabled"])?;
        element::Type::Selectbox(proto::Selectbox {
            id: string(v, "id"),
            label: string(v, "label"),
            default: v.get("default").map(|n| -> TestResult<i32> { Ok(i32::try_from(n.as_i64().ok_or("selectbox default must be an integer")?)?) }).transpose()?,
            options: v["options"]
                .as_array()
                .ok_or("selectbox options must be an array")?
                .iter()
                .map(|v| v.as_str().map(str::to_string).ok_or("selectbox option must be a string"))
                .collect::<Result<Vec<_>, _>>()?,
            set_value: boolean(v, "setValue"),
            disabled: boolean(v, "disabled"),
            label_visibility: visibility(v),
            accept_new_options: v.get("acceptNewOptions").map(|b| b.as_bool().ok_or("acceptNewOptions must be a boolean")).transpose()?,
            raw_value: v.get("rawValue").map(|s| s.as_str().map(str::to_string).ok_or("rawValue must be a string")).transpose()?,
            ..Default::default()
        })
    } else if let Some(v) = value.get("slider") {
        fields(v, &["id", "label", "format", "default", "max", "step", "value", "setValue", "labelVisibility", "type", "disabled"])?;
        assert_eq!(v["type"], "SLIDER");
        element::Type::Slider(proto::Slider {
            id: string(v, "id"),
            label: string(v, "label"),
            format: string(v, "format"),
            default: numbers(v, "default")?,
            max: v["max"].as_f64().ok_or("slider max must be a number")?,
            step: v["step"].as_f64().ok_or("slider step must be a number")?,
            value: numbers(v, "value")?,
            set_value: boolean(v, "setValue"),
            disabled: boolean(v, "disabled"),
            label_visibility: visibility(v),
            r#type: 1,
            ..Default::default()
        })
    } else {
        let v = &value["checkbox"];
        fields(v, &["id", "label", "default", "setValue", "labelVisibility", "disabled"])?;
        element::Type::Checkbox(proto::Checkbox {
            id: string(v, "id"),
            label: string(v, "label"),
            default: boolean(v, "default"),
            set_value: boolean(v, "setValue"),
            disabled: boolean(v, "disabled"),
            label_visibility: visibility(v),
            ..Default::default()
        })
    };
    Ok(proto::Element {
        r#type: Some(body),
        width_config: Some(WidthConfig { width_spec: Some(width_spec) }),
        has_one_shot_effect: value.get("hasOneShotEffect").map(|v| v.as_bool().ok_or("hasOneShotEffect must be a boolean")).transpose()?,
        ..Default::default()
    })
}

fn id_mut(element: &mut proto::Element) -> TestResult<&mut String> {
    match element.r#type.as_mut() {
        Some(element::Type::Selectbox(v)) => Ok(&mut v.id),
        Some(element::Type::Slider(v)) => Ok(&mut v.id),
        Some(element::Type::Checkbox(v)) => Ok(&mut v.id),
        _ => Err("expected a selectbox, slider or checkbox element with widget id".into()),
    }
}

fn render_case(case: &str, st: &Streamlit) -> TestResult {
    if case == "keys" {
        let state = st.session_state();
        state.set("group_by", "channel")?;
        state.set("min_amount", 50_i64)?;
        state.set("include_unknown", false)?;
    }
    if case.starts_with("none_") {
        let options = SelectboxOptions::with_format_func("Group by", [None, Some("red")], |v| v.unwrap_or("None").into()).index(if case == "none_option" { Some(0) } else { None });
        let returned = st.selectbox(options)?;
        assert_eq!(returned, if case == "none_option" { Some(None) } else { None });
        return Ok(());
    }
    if case == "dup_key" {
        st.selectbox(SelectboxOptions::new("Group by", ["category", "region"]).key("the_same_key"))?;
        // Upstream raises StreamlitDuplicateElementKey and the framework
        // renders the exception element; the Rust takeover mirrors that wire
        // instead of surfacing a typed error, returning the requested
        // default (the first option) to the caller.
        let second = st.selectbox(SelectboxOptions::new("Other group by", ["category", "region"]).key("the_same_key"))?;
        assert_eq!(second, Some("category"));
        assert_eq!(st.session_state().run_control(), Some(crate::RunControl::Stop));
        return Ok(());
    }
    let mut select = SelectboxOptions::new("Group by", ["category", "region", "channel"]);
    let mut slider = SliderOptions::new("Minimum amount", if matches!(case, "options" | "disabled") { 50_i64 } else { 0_i64 }).max(200).step(10);
    let mut checkbox = CheckboxOptions::new("Include unknown region").value(case != "options");
    if case == "options" {
        select = select.index(Some(1));
    }
    if case == "keys" {
        select = select.key("group_by");
        slider = slider.key("min_amount");
        checkbox = checkbox.key("include_unknown");
    }
    if case == "disabled" {
        select = select.disabled(true);
        slider = slider.disabled(true);
        checkbox = checkbox.disabled(true);
    }
    if case == "on_change" {
        select = select.on_change(|st| note(st, "callback:selectbox"));
        slider = slider.on_change(|st| note(st, "callback:slider"));
        checkbox = checkbox.on_change(|st| note(st, "callback:checkbox"));
    }
    let group = st.selectbox(select)?;
    let amount = st.slider(slider)?;
    let include = st.checkbox(checkbox)?;
    if case == "keys" {
        assert_eq!((group, amount, include), (Some("channel"), 50, false));
    }
    if case == "on_change" {
        note(st, "script");
    }
    Ok(())
}

fn note(st: &Streamlit, value: &str) {
    let result = (|| -> TestResult {
        let state = st.session_state();
        let mut order = state.get::<Vec<String>>("order")?.unwrap_or_default();
        order.push(value.into());
        state.set("order", order)?;
        Ok(())
    })();
    assert!(result.is_ok(), "callback order update failed: {result:?}");
}

#[test]
fn eight_chrome_cases_match_full_elements_optional_presence_and_callback_order() -> TestResult {
    for case in ["defaults", "options", "keys", "on_change", "disabled", "dup_key", "none_option", "none_unset"] {
        let path = std::path::Path::new(env!("CARGO_MANIFEST_DIR")).join(format!("../tests/reference/reference-browser/widgets/{case}/trace-widgets-{case}.json"));
        let raw: Json = serde_json::from_str(&std::fs::read_to_string(path)?)?;
        assert_eq!(raw["failures"], serde_json::json!([]));
        let full: Vec<_> = raw["frames"].as_array().ok_or("reference frames must be an array")?.iter().filter_map(|frame| frame.pointer("/decoded/delta/element_full")).collect();
        let runs = raw["client_widget_states"].as_array().ok_or("reference widget runs must be an array")?;
        assert_eq!(full.len() % runs.len(), 0);
        let per_run = full.len() / runs.len();
        let state = SessionState::default();
        let mut ids: HashMap<String, String> = HashMap::new();
        // The run loop clears the run-control signal before every run; the
        // duplicate-key takeover sets it, so the simulation must too.
        let mut exceptions: Vec<_> = raw["frames"].as_array().ok_or("reference frames must be an array")?.iter().filter_map(|frame| frame.pointer("/decoded/delta/exception")).cloned().collect();
        for (run, incoming) in runs.iter().enumerate() {
            let widgets = incoming
                .as_array()
                .ok_or("reference run widget states must be an array")?
                .iter()
                .map(|widget| -> TestResult<WidgetState> {
                    let value = match widget["value_field"].as_str().ok_or("reference widget must name its value field")? {
                        "string_value" => widget_state::Value::StringValue(widget["value"].as_str().ok_or("string widget state must be a string")?.into()),
                        "bool_value" => widget_state::Value::BoolValue(widget["value"].as_bool().ok_or("boolean widget state must be a boolean")?),
                        "double_array_value" => widget_state::Value::DoubleArrayValue(proto::DoubleArray { data: numbers(&widget["value_full"], "data")? }),
                        other => return Err(format!("unhandled reference input {other}").into()),
                    };
                    Ok(WidgetState {
                        id: ids[widget["id"].as_str().ok_or("reference widget id must be a string")?].clone(),
                        value: Some(value),
                    })
                })
                .collect::<TestResult<Vec<_>>>()?;
            let callbacks = state.begin_widgets(widgets);
            state.reset_run_control();
            let st = Streamlit::with_session_state(state.clone());
            let (sender, mut receiver) = tokio::sync::mpsc::unbounded_channel();
            st.app.lock().set_render_context(RenderContext::with_sender("reference".into(), sender));
            for callback in callbacks {
                callback(&st);
            }
            render_case(case, &st)?;
            for observed in &full[run * per_run..(run + 1) * per_run] {
                let mut expected = expected_element(observed)?;
                let Some(forward_msg::Type::Delta(proto::Delta {
                    r#type: Some(delta::Type::NewElement(mut actual)),
                    ..
                })) = receiver.try_recv()?.r#type
                else {
                    panic!("expected input")
                };
                let expected_id = id_mut(&mut expected)?.clone();
                let actual_id = id_mut(&mut actual)?.clone();
                let suffix = expected_id.strip_prefix("$$ID-").ok_or("reference widget id must start with $$ID-")?.get(32..).ok_or("reference widget id must include a 32-byte digest")?;
                let digest = actual_id.strip_prefix("$$ID-").ok_or("native widget id must start with $$ID-")?;
                assert!(digest[..32].bytes().all(|b| b.is_ascii_hexdigit()));
                assert_eq!(&digest[32..], suffix);
                if let Some(previous) = ids.insert(expected_id, actual_id.clone()) {
                    assert_eq!(previous, actual_id);
                }
                *id_mut(&mut expected)? = actual_id;
                assert_eq!(actual.encode_to_vec(), expected.encode_to_vec(), "case={case} run={run}: {actual:?} vs {expected:?}");
            }
            // The duplicate-key takeover renders the framework exception
            // element after the widgets. Its type/message/flags match the
            // reference exactly; only the stack trace line differs, because
            // Rust cannot know the caller's source line.
            while let Some(expected_exception) = exceptions.first() {
                let Some(forward_msg::Type::Delta(proto::Delta {
                    r#type: Some(delta::Type::NewElement(element)), ..
                })) = receiver.try_recv()?.r#type
                else {
                    panic!("expected the duplicate-key exception element in {case} run={run}")
                };
                let Some(element::Type::Exception(exception)) = element.r#type else {
                    panic!("expected an exception element in {case} run={run}")
                };
                assert_eq!(exception.r#type, expected_exception["type"].as_str().ok_or("reference exception type must be a string")?, "case={case} run={run}");
                assert_eq!(exception.message, expected_exception["message"].as_str().ok_or("reference exception message must be a string")?, "case={case} run={run}");
                assert_eq!(exception.message_is_markdown, expected_exception["messageIsMarkdown"].as_bool().ok_or("reference exception markdown flag must be a boolean")?);
                assert_eq!(exception.is_streamlit_exception, expected_exception["isStreamlitException"].as_bool().ok_or("reference exception framework flag must be a boolean")?);
                assert!(matches!(
                    exception.width_config,
                    Some(proto::streamlit::WidthConfig {
                        width_spec: Some(proto::streamlit::width_config::WidthSpec::UseStretch(true))
                    })
                ));
                assert_eq!(exception.stack_trace.len(), 1, "one honest context line, not the unknowable app source line");
                exceptions.remove(0);
            }
            assert!(receiver.try_recv().is_err(), "extra elements in {case}");
            state.finish_widgets();
        }
        if case == "on_change" {
            assert_eq!(raw["dom_after"]["markdown"][0], "order: ['script', 'callback:selectbox', 'script']");
            assert_eq!(state.get::<Vec<String>>("order")?.ok_or("callback order must be recorded")?, ["script", "callback:selectbox", "script"]);
        }
        if case == "disabled" {
            assert_eq!(raw["disabled_attempt"]["frames_after_attempt"], 0);
        }
    }
    Ok(())
}
