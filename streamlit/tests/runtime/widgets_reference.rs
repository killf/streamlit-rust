//! Differential element fields from the eight real Chrome reference captures.
//! Only the opaque ID digest is normalized; its shape and key suffix are checked.
use super::*;
use crate::SessionState;
use crate::elements::common::RenderContext;
use crate::proto::{WidgetState, delta, forward_msg, widget_state};
use prost::Message;
use serde_json::Value as Json;
use std::collections::HashMap;

fn fields(value: &Json, allowed: &[&str]) {
    for key in value.as_object().unwrap().keys() {
        assert!(allowed.contains(&key.as_str()), "unhandled reference field {key}");
    }
}
fn string(value: &Json, key: &str) -> String {
    value[key].as_str().unwrap_or_default().into()
}
fn boolean(value: &Json, key: &str) -> bool {
    value[key].as_bool().unwrap_or(false)
}
fn numbers(value: &Json, key: &str) -> Vec<f64> {
    value[key].as_array().map(|array| array.iter().map(|v| v.as_f64().unwrap()).collect()).unwrap_or_default()
}

fn expected_element(value: &Json) -> proto::Element {
    use proto::streamlit::{WidthConfig, width_config::WidthSpec};
    fields(value, &["selectbox", "slider", "checkbox", "widthConfig", "hasOneShotEffect"]);
    let width = &value["widthConfig"];
    fields(width, &["useContent", "useStretch"]);
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
        fields(v, &["id", "label", "default", "options", "setValue", "labelVisibility", "acceptNewOptions", "rawValue", "disabled"]);
        element::Type::Selectbox(proto::Selectbox {
            id: string(v, "id"),
            label: string(v, "label"),
            default: v.get("default").map(|n| i32::try_from(n.as_i64().unwrap()).unwrap()),
            options: v["options"].as_array().unwrap().iter().map(|v| v.as_str().unwrap().into()).collect(),
            set_value: boolean(v, "setValue"),
            disabled: boolean(v, "disabled"),
            label_visibility: visibility(v),
            accept_new_options: v.get("acceptNewOptions").map(|b| b.as_bool().unwrap()),
            raw_value: v.get("rawValue").map(|s| s.as_str().unwrap().into()),
            ..Default::default()
        })
    } else if let Some(v) = value.get("slider") {
        fields(v, &["id", "label", "format", "default", "max", "step", "value", "setValue", "labelVisibility", "type", "disabled"]);
        assert_eq!(v["type"], "SLIDER");
        element::Type::Slider(proto::Slider {
            id: string(v, "id"),
            label: string(v, "label"),
            format: string(v, "format"),
            default: numbers(v, "default"),
            max: v["max"].as_f64().unwrap(),
            step: v["step"].as_f64().unwrap(),
            value: numbers(v, "value"),
            set_value: boolean(v, "setValue"),
            disabled: boolean(v, "disabled"),
            label_visibility: visibility(v),
            r#type: 1,
            ..Default::default()
        })
    } else {
        let v = &value["checkbox"];
        fields(v, &["id", "label", "default", "setValue", "labelVisibility", "disabled"]);
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
    proto::Element {
        r#type: Some(body),
        width_config: Some(WidthConfig { width_spec: Some(width_spec) }),
        has_one_shot_effect: value.get("hasOneShotEffect").map(|v| v.as_bool().unwrap()),
        ..Default::default()
    }
}

fn id_mut(element: &mut proto::Element) -> &mut String {
    match element.r#type.as_mut().unwrap() {
        element::Type::Selectbox(v) => &mut v.id,
        element::Type::Slider(v) => &mut v.id,
        element::Type::Checkbox(v) => &mut v.id,
        _ => panic!("unexpected element"),
    }
}

fn render_case(case: &str, st: &Streamlit) {
    if case == "keys" {
        let state = st.session_state();
        state.set("group_by", "channel").unwrap();
        state.set("min_amount", 50_i64).unwrap();
        state.set("include_unknown", false).unwrap();
    }
    if case.starts_with("none_") {
        let options = SelectboxOptions::with_format_func("Group by", [None, Some("red")], |v| v.unwrap_or("None").into()).index(if case == "none_option" { Some(0) } else { None });
        let returned = st.selectbox(options).unwrap();
        assert_eq!(returned, if case == "none_option" { Some(None) } else { None });
        return;
    }
    if case == "dup_key" {
        st.selectbox(SelectboxOptions::new("Group by", ["category", "region"]).key("the_same_key")).unwrap();
        assert!(matches!(st.selectbox(SelectboxOptions::new("Other group by", ["category", "region"]).key("the_same_key")), Err(WidgetError::DuplicateKey(_))));
        // Rust exposes a typed Result. This does not claim the Python exception UI.
        return;
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
    let group = st.selectbox(select).unwrap();
    let amount = st.slider(slider).unwrap();
    let include = st.checkbox(checkbox).unwrap();
    if case == "keys" {
        assert_eq!((group, amount, include), (Some("channel"), 50, false));
    }
    if case == "on_change" {
        note(st, "script");
    }
}
fn note(st: &Streamlit, value: &str) {
    let state = st.session_state();
    let mut order = state.get::<Vec<String>>("order").unwrap().unwrap_or_default();
    order.push(value.into());
    state.set("order", order).unwrap();
}

#[test]
fn eight_chrome_cases_match_full_elements_optional_presence_and_callback_order() {
    for case in ["defaults", "options", "keys", "on_change", "disabled", "dup_key", "none_option", "none_unset"] {
        let path = std::path::Path::new(env!("CARGO_MANIFEST_DIR")).join(format!("../tests/reference/reference-browser/widgets/{case}/trace-widgets-{case}.json"));
        let raw: Json = serde_json::from_str(&std::fs::read_to_string(path).unwrap()).unwrap();
        assert_eq!(raw["failures"], serde_json::json!([]));
        let full: Vec<_> = raw["frames"].as_array().unwrap().iter().filter_map(|frame| frame.pointer("/decoded/delta/element_full")).collect();
        let runs = raw["client_widget_states"].as_array().unwrap();
        assert_eq!(full.len() % runs.len(), 0);
        let per_run = full.len() / runs.len();
        let state = SessionState::default();
        let mut ids: HashMap<String, String> = HashMap::new();
        for (run, incoming) in runs.iter().enumerate() {
            let widgets = incoming
                .as_array()
                .unwrap()
                .iter()
                .map(|widget| {
                    let value = match widget["value_field"].as_str().unwrap() {
                        "string_value" => widget_state::Value::StringValue(widget["value"].as_str().unwrap().into()),
                        "bool_value" => widget_state::Value::BoolValue(widget["value"].as_bool().unwrap()),
                        "double_array_value" => widget_state::Value::DoubleArrayValue(proto::DoubleArray { data: numbers(&widget["value_full"], "data") }),
                        other => panic!("unhandled reference input {other}"),
                    };
                    WidgetState {
                        id: ids[widget["id"].as_str().unwrap()].clone(),
                        value: Some(value),
                    }
                })
                .collect();
            let callbacks = state.begin_widgets(widgets);
            let st = Streamlit::with_session_state(state.clone());
            let (sender, mut receiver) = tokio::sync::mpsc::unbounded_channel();
            st.app.lock().set_render_context(RenderContext::with_sender("reference".into(), sender));
            for callback in callbacks {
                callback(&st);
            }
            render_case(case, &st);
            for observed in &full[run * per_run..(run + 1) * per_run] {
                let mut expected = expected_element(observed);
                let Some(forward_msg::Type::Delta(proto::Delta {
                    r#type: Some(delta::Type::NewElement(mut actual)),
                    ..
                })) = receiver.try_recv().unwrap().r#type
                else {
                    panic!("expected input")
                };
                let expected_id = id_mut(&mut expected).clone();
                let actual_id = id_mut(&mut actual).clone();
                let suffix = expected_id.strip_prefix("$$ID-").unwrap().get(32..).unwrap();
                let digest = actual_id.strip_prefix("$$ID-").unwrap();
                assert!(digest[..32].bytes().all(|b| b.is_ascii_hexdigit()));
                assert_eq!(&digest[32..], suffix);
                if let Some(previous) = ids.insert(expected_id, actual_id.clone()) {
                    assert_eq!(previous, actual_id);
                }
                *id_mut(&mut expected) = actual_id;
                assert_eq!(actual.encode_to_vec(), expected.encode_to_vec(), "case={case} run={run}: {actual:?} vs {expected:?}");
            }
            assert!(receiver.try_recv().is_err(), "extra elements in {case}");
            state.finish_widgets();
        }
        if case == "on_change" {
            assert_eq!(raw["dom_after"]["markdown"][0], "order: ['script', 'callback:selectbox', 'script']");
            assert_eq!(state.get::<Vec<String>>("order").unwrap().unwrap(), ["script", "callback:selectbox", "script"]);
        }
        if case == "disabled" {
            assert_eq!(raw["disabled_attempt"]["frames_after_attempt"], 0);
        }
    }
}
