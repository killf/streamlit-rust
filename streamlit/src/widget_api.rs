//! Typed native inputs. These methods work on Streamlit and its containers.
use crate::api::{AppendChild, ButtonOptions};
use crate::elements::{button::ButtonElement, input::InputElement};
use crate::proto::{self, element};
use crate::widgets::{Codec, WidgetSpec};
use crate::{Streamlit, WidgetCallback, WidgetError};
use serde::{Serialize, de::DeserializeOwned};
use serde_json::Value;
use std::{cell::RefCell, rc::Rc, sync::Arc};

#[derive(Clone, Copy, Debug, Default)]
pub enum LabelVisibility {
    #[default]
    Visible,
    Hidden,
    Collapsed,
}

impl LabelVisibility {
    fn wire(self) -> Option<proto::LabelVisibility> {
        Some(proto::LabelVisibility {
            value: match self {
                Self::Visible => 0,
                Self::Hidden => 1,
                Self::Collapsed => 2,
            },
        })
    }
}

#[derive(Clone)]
struct InputOptions {
    label: String,
    key: Option<String>,
    help: String,
    disabled: bool,
    width: Option<i32>,
    visibility: LabelVisibility,
    ignore_rerun: bool,
    callback: Option<WidgetCallback>,
}

impl InputOptions {
    fn new(label: impl Into<String>) -> Self {
        Self {
            label: label.into(),
            key: None,
            help: String::new(),
            disabled: false,
            width: None,
            visibility: LabelVisibility::Visible,
            ignore_rerun: false,
            callback: None,
        }
    }
    fn identity(&self, extra: &str) -> String {
        if self.key.is_some() {
            extra.to_string()
        } else {
            serde_json::to_string(&(&self.label, &self.help, extra)).expect("string identity serializes")
        }
    }
    fn width(&self, content_default: bool) -> Result<Option<proto::streamlit::WidthConfig>, WidgetError> {
        use proto::streamlit::width_config::WidthSpec;
        let width_spec = match self.width {
            Some(width) if width > 0 => WidthSpec::PixelWidth(width as u32),
            Some(_) => return Err(WidgetError::InvalidValue("width must be positive".into())),
            None if content_default => WidthSpec::UseContent(true),
            None => WidthSpec::UseStretch(true),
        };
        Ok(Some(proto::streamlit::WidthConfig { width_spec: Some(width_spec) }))
    }
}

macro_rules! common_builders {
    () => {
        pub fn key(mut self, key: impl Into<String>) -> Self {
            self.common.key = Some(key.into());
            self
        }
        pub fn help(mut self, help: impl Into<String>) -> Self {
            self.common.help = help.into();
            self
        }
        pub fn disabled(mut self, disabled: bool) -> Self {
            self.common.disabled = disabled;
            self
        }
        /// A positive pixel width. Default: content for checkbox, stretch otherwise.
        pub fn width(mut self, pixels: i32) -> Self {
            self.common.width = Some(pixels);
            self
        }
        pub fn label_visibility(mut self, visibility: LabelVisibility) -> Self {
            self.common.visibility = visibility;
            self
        }
        pub fn on_change(mut self, callback: impl Fn(&Streamlit) + Send + Sync + 'static) -> Self {
            self.common.callback = Some(Arc::new(callback));
            self.common.ignore_rerun = false;
            self
        }
        /// Buffer changes in the frontend until another action causes a rerun.
        pub fn ignore_rerun(mut self, ignore: bool) -> Self {
            self.common.ignore_rerun = ignore;
            if ignore {
                self.common.callback = None;
            }
            self
        }
    };
}

pub struct CheckboxOptions {
    common: InputOptions,
    value: bool,
}
impl CheckboxOptions {
    pub fn new(label: impl Into<String>) -> Self {
        Self { common: InputOptions::new(label), value: false }
    }
    pub fn value(mut self, value: bool) -> Self {
        self.value = value;
        self
    }
    common_builders!();
}
impl From<&str> for CheckboxOptions {
    fn from(label: &str) -> Self {
        Self::new(label)
    }
}
impl From<String> for CheckboxOptions {
    fn from(label: String) -> Self {
        Self::new(label)
    }
}
impl<L: Into<String>> From<(L, bool)> for CheckboxOptions {
    fn from((label, value): (L, bool)) -> Self {
        Self::new(label).value(value)
    }
}

pub struct SelectboxOptions<T> {
    common: InputOptions,
    options: Vec<T>,
    labels: Vec<String>,
    index: Option<usize>,
    placeholder: Option<String>,
}
impl<T: ToString> SelectboxOptions<T> {
    pub fn new(label: impl Into<String>, options: impl IntoIterator<Item = T>) -> Self {
        Self::with_format_func(label, options, ToString::to_string)
    }
}
impl<L, I, T> From<(L, I)> for SelectboxOptions<T>
where
    L: Into<String>,
    I: IntoIterator<Item = T>,
    T: ToString,
{
    fn from((label, options): (L, I)) -> Self {
        Self::new(label, options)
    }
}
impl<T> SelectboxOptions<T> {
    /// Construct options whose native type has no Display implementation, such
    /// as `Option<T>` or `()`, without changing the returned native value.
    pub fn with_format_func(label: impl Into<String>, options: impl IntoIterator<Item = T>, format: impl Fn(&T) -> String) -> Self {
        let options: Vec<T> = options.into_iter().collect();
        let labels = options.iter().map(format).collect();
        Self {
            common: InputOptions::new(label),
            options,
            labels,
            index: Some(0),
            placeholder: None,
        }
    }
}
impl<T> SelectboxOptions<T> {
    pub fn index(mut self, index: Option<usize>) -> Self {
        self.index = index;
        self
    }
    /// Formatting changes labels, never the returned original option value.
    pub fn format_func(mut self, format: impl Fn(&T) -> String) -> Self {
        self.labels = self.options.iter().map(format).collect();
        self
    }
    pub fn placeholder(mut self, placeholder: impl Into<String>) -> Self {
        self.placeholder = Some(placeholder.into());
        self
    }
    common_builders!();
}

mod sealed {
    pub trait Scalar {}
    impl Scalar for i64 {}
    impl Scalar for i32 {}
    impl Scalar for f64 {}
    pub trait Numeric {}
    impl Numeric for i64 {}
    impl Numeric for i32 {}
    impl Numeric for f64 {}
    impl<T: Scalar> Numeric for (T, T) {}
    impl<T: Scalar> Numeric for [T; 2] {}
}

/// Numeric scalar or two-endpoint range. Date/time sliders are not implemented yet.
/// Ranges must contain exactly two scalar endpoints, never nested ranges.
/// ```compile_fail
/// use streamlit::SliderOptions;
/// let _ = SliderOptions::new("Nested", ((1_i64, 2_i64), (3_i64, 4_i64)));
/// ```
pub trait SliderValue: sealed::Numeric + Serialize + DeserializeOwned + Clone {
    const INTEGER: bool;
    const COUNT: usize;
    /// Native return-type bounds, additionally constrained by the widget bounds.
    const NATIVE_MIN: f64;
    const NATIVE_MAX: f64;
    fn numbers(&self) -> Vec<f64>;
}
macro_rules! slider_scalar {
    ($t:ty, $int:expr, $min:expr, $max:expr) => {
        impl SliderValue for $t {
            const INTEGER: bool = $int;
            const COUNT: usize = 1;
            const NATIVE_MIN: f64 = $min;
            const NATIVE_MAX: f64 = $max;
            fn numbers(&self) -> Vec<f64> {
                vec![*self as f64]
            }
        }
    };
}
slider_scalar!(i64, true, -9_007_199_254_740_991.0, 9_007_199_254_740_991.0);
slider_scalar!(i32, true, i32::MIN as f64, i32::MAX as f64);
slider_scalar!(f64, false, f64::MIN, f64::MAX);
impl<T: SliderValue + sealed::Scalar> SliderValue for (T, T) {
    const INTEGER: bool = T::INTEGER;
    const COUNT: usize = 2;
    const NATIVE_MIN: f64 = T::NATIVE_MIN;
    const NATIVE_MAX: f64 = T::NATIVE_MAX;
    fn numbers(&self) -> Vec<f64> {
        vec![self.0.numbers()[0], self.1.numbers()[0]]
    }
}
impl<T: SliderValue + sealed::Scalar> SliderValue for [T; 2] {
    const INTEGER: bool = T::INTEGER;
    const COUNT: usize = 2;
    const NATIVE_MIN: f64 = T::NATIVE_MIN;
    const NATIVE_MAX: f64 = T::NATIVE_MAX;
    fn numbers(&self) -> Vec<f64> {
        vec![self[0].numbers()[0], self[1].numbers()[0]]
    }
}

pub struct SliderOptions<T> {
    common: InputOptions,
    value: T,
    min: f64,
    max: f64,
    step: f64,
    format: Option<String>,
}
impl<T: SliderValue> SliderOptions<T> {
    pub fn new(label: impl Into<String>, value: T) -> Self {
        Self {
            common: InputOptions::new(label),
            value,
            min: 0.0,
            max: if T::INTEGER { 100.0 } else { 1.0 },
            step: if T::INTEGER { 1.0 } else { 0.01 },
            format: None,
        }
    }
    pub fn min(mut self, min: impl Into<f64>) -> Self {
        self.min = min.into();
        self
    }
    pub fn max(mut self, max: impl Into<f64>) -> Self {
        self.max = max.into();
        self
    }
    pub fn step(mut self, step: impl Into<f64>) -> Self {
        self.step = step.into();
        self
    }
    pub fn format(mut self, format: impl Into<String>) -> Self {
        self.format = Some(format.into());
        self
    }
    common_builders!();
}
impl<L: Into<String>, T: SliderValue> From<(L, T)> for SliderOptions<T> {
    fn from((label, value): (L, T)) -> Self {
        Self::new(label, value)
    }
}
impl<L: Into<String>, T: SliderValue, B: Into<f64>> From<(L, T, std::ops::RangeInclusive<B>)> for SliderOptions<T> {
    fn from((label, value, bounds): (L, T, std::ops::RangeInclusive<B>)) -> Self {
        let (min, max) = bounds.into_inner();
        Self::new(label, value).min(min).max(max)
    }
}

pub trait InputWidgets {
    fn checkbox(&self, options: impl Into<CheckboxOptions>) -> Result<bool, WidgetError>;
    /// Accept a builder or `(label, options)`; both retain the same defaults.
    fn selectbox<T: Clone + Serialize>(&self, options: impl Into<SelectboxOptions<T>>) -> Result<Option<T>, WidgetError>;
    /// Accept a builder, `(label, value)`, or `(label, value, min..=max)`.
    /// A tuple/array value denotes the selected range, not the permitted bounds.
    fn slider<T: SliderValue>(&self, options: impl Into<SliderOptions<T>>) -> Result<T, WidgetError>;
    /// Fallible counterpart to the original boolean-returning `button` method.
    fn try_button(&self, options: impl Into<ButtonOptions>) -> Result<bool, WidgetError>;
}

impl<C: AppendChild> InputWidgets for C {
    fn checkbox(&self, options: impl Into<CheckboxOptions>) -> Result<bool, WidgetError> {
        let options = options.into();
        let c = options.common;
        let width_config = c.width(true)?;
        let identity = c.identity(&if c.key.is_some() { String::new() } else { options.value.to_string() });
        let state = self.get_app().lock().session_state.clone();
        let (id, value, set_value) = state.register_widget(
            WidgetSpec {
                kind: "checkbox",
                key: c.key.as_deref(),
                identity: &identity,
                default: options.value.into(),
                codec: Codec::Bool,
                callback: c.callback,
            },
            |value| value.as_bool().ok_or_else(|| WidgetError::InvalidValue("checkbox expects bool".into())),
        )?;
        self.push(Rc::new(RefCell::new(InputElement(proto::Element {
            width_config,
            has_one_shot_effect: set_value.then_some(true),
            r#type: Some(element::Type::Checkbox(proto::Checkbox {
                id,
                label: c.label,
                default: options.value,
                value: set_value && value,
                set_value,
                help: c.help,
                disabled: c.disabled,
                label_visibility: c.visibility.wire(),
                ignore_rerun: c.ignore_rerun,
                ..Default::default()
            })),
            ..Default::default()
        }))));
        Ok(value)
    }

    fn selectbox<T: Clone + Serialize>(&self, options: impl Into<SelectboxOptions<T>>) -> Result<Option<T>, WidgetError> {
        let options = options.into();
        let c = options.common;
        let width_config = c.width(false)?;
        if !options.options.is_empty() && options.index.is_some_and(|i| i >= options.options.len()) {
            return Err(WidgetError::InvalidValue("selectbox index is outside options".into()));
        }
        let native: Vec<Value> = options.options.iter().map(serde_json::to_value).collect::<Result<_, _>>()?;
        let default = options.index.filter(|index| *index < native.len()).map(Value::from).unwrap_or(Value::Null);
        let identity = c.identity(&if c.key.is_some() { String::new() } else { format!("{:?}:{:?}", options.labels, options.index) });
        let codec = Codec::Select(options.labels.iter().cloned().zip(native.iter().cloned()).collect());
        let state = self.get_app().lock().session_state.clone();
        let (id, selected, set_value) = state.register_widget(
            WidgetSpec {
                kind: "selectbox",
                key: c.key.as_deref(),
                identity: &identity,
                default: default.clone(),
                codec,
                callback: c.callback,
            },
            |value| {
                if value.is_null() {
                    Ok(None)
                } else {
                    value
                        .as_u64()
                        .and_then(|index| usize::try_from(index).ok())
                        .filter(|index| *index < options.options.len())
                        .map(Some)
                        .ok_or_else(|| WidgetError::InvalidValue("invalid selection index".into()))
                }
            },
        )?;
        let result = selected.map(|index| options.options[index].clone());
        let empty = options.options.is_empty();
        self.push(Rc::new(RefCell::new(InputElement(proto::Element {
            width_config,
            has_one_shot_effect: set_value.then_some(true),
            r#type: Some(element::Type::Selectbox(proto::Selectbox {
                id,
                label: c.label,
                default: if empty { None } else { options.index.map(|i| i as i32) },
                options: options.labels.clone(),
                help: c.help,
                raw_value: if set_value { selected.map(|i| options.labels[i].clone()) } else { None },
                set_value,
                disabled: c.disabled || empty,
                label_visibility: c.visibility.wire(),
                placeholder: options.placeholder.unwrap_or_default(),
                accept_new_options: Some(false),
                ignore_rerun: c.ignore_rerun,
                ..Default::default()
            })),
            ..Default::default()
        }))));
        Ok(result)
    }

    fn slider<T: SliderValue>(&self, options: impl Into<SliderOptions<T>>) -> Result<T, WidgetError> {
        let options = options.into();
        let c = options.common;
        let width_config = c.width(false)?;
        if !options.min.is_finite()
            || !options.max.is_finite()
            || !options.step.is_finite()
            || options.min >= options.max
            || options.step <= 0.0
            || options.min < T::NATIVE_MIN
            || options.max > T::NATIVE_MAX
            || (T::INTEGER && [options.min, options.max, options.step].iter().any(|v| v.fract() != 0.0 || v.abs() > 9_007_199_254_740_991.0))
        {
            return Err(WidgetError::InvalidValue("slider needs ordered finite bounds representable by its return type and a positive step (integers must be JS-safe)".into()));
        }
        let default = serde_json::to_value(&options.value)?;
        let codec = Codec::Slider {
            min: options.min,
            max: options.max,
            count: T::COUNT,
            integer: T::INTEGER,
        };
        if !codec.valid(&default) {
            return Err(WidgetError::InvalidValue("slider default is outside bounds or range is reversed".into()));
        }
        let constraints = format!("{}:{}:{}:{}:{}", options.min, options.max, options.step, T::INTEGER, T::COUNT);
        let identity = c.identity(&if c.key.is_some() { constraints } else { format!("{constraints}:{default}:{:?}", options.format) });
        let state = self.get_app().lock().session_state.clone();
        let (id, result, set_value) = state.register_widget(
            WidgetSpec {
                kind: "slider",
                key: c.key.as_deref(),
                identity: &identity,
                default: default.clone(),
                codec,
                callback: c.callback,
            },
            |value| Ok(serde_json::from_value::<T>(value.clone())?),
        )?;
        self.push(Rc::new(RefCell::new(InputElement(proto::Element {
            width_config,
            has_one_shot_effect: set_value.then_some(true),
            r#type: Some(element::Type::Slider(proto::Slider {
                id,
                label: c.label,
                default: options.value.numbers(),
                value: if set_value { result.numbers() } else { vec![] },
                set_value,
                min: options.min,
                max: options.max,
                step: options.step,
                data_type: if T::INTEGER { 0 } else { 1 },
                r#type: 1,
                format: options.format.unwrap_or_else(|| if T::INTEGER { "%d" } else { "%0.2f" }.into()),
                help: c.help,
                disabled: c.disabled,
                label_visibility: c.visibility.wire(),
                ignore_rerun: c.ignore_rerun,
                ..Default::default()
            })),
            ..Default::default()
        }))));
        Ok(result)
    }

    fn try_button(&self, options: impl Into<ButtonOptions>) -> Result<bool, WidgetError> {
        let options = options.into();
        let identity = if options.key.is_some() {
            String::new()
        } else {
            serde_json::to_string(&(&options.label, &options.help, &options.r#type, &options.icon))?
        };
        let state = self.get_app().lock().session_state.clone();
        let (id, value, _) = state.register_widget(
            WidgetSpec {
                kind: "button",
                key: options.key.as_deref(),
                identity: &identity,
                default: false.into(),
                codec: Codec::Trigger,
                callback: options.callback,
            },
            |value| value.as_bool().ok_or_else(|| WidgetError::InvalidValue("button expects bool".into())),
        )?;
        let element = ButtonElement::new(id, options.label)
            .help(options.help.unwrap_or_default())
            .r#type(options.r#type)
            .icon(options.icon.unwrap_or_default())
            .shortcut(options.shortcut.unwrap_or_default())
            .width(options.width)
            .disabled(options.disabled);
        self.push(Rc::new(RefCell::new(element)));
        Ok(value)
    }
}

#[cfg(test)]
#[path = "../tests/runtime/widgets_reference.rs"]
mod reference_tests;

#[cfg(test)]
mod tests {
    use super::*;
    use crate::elements::common::RenderContext;
    use crate::proto::{ForwardMsg, WidgetState, delta, forward_msg, widget_state};
    use crate::{SessionState, StreamlitApi};

    fn app(state: &SessionState) -> (Streamlit, tokio::sync::mpsc::UnboundedReceiver<ForwardMsg>) {
        let st = Streamlit::with_session_state(state.clone());
        let (sender, receiver) = tokio::sync::mpsc::unbounded_channel();
        st.app.lock().set_render_context(RenderContext::with_sender("unit".into(), sender));
        (st, receiver)
    }
    fn input(receiver: &mut tokio::sync::mpsc::UnboundedReceiver<ForwardMsg>) -> element::Type {
        match receiver.try_recv().unwrap().r#type {
            Some(forward_msg::Type::Delta(proto::Delta {
                r#type: Some(delta::Type::NewElement(element)), ..
            })) => element.r#type.unwrap(),
            other => panic!("expected input, got {other:?}"),
        }
    }

    #[test]
    fn typed_values_and_all_inputs_update_before_callback() {
        let state = SessionState::default();
        state.begin_widgets(vec![]);
        let (st, mut wire) = app(&state);
        assert_eq!(st.selectbox(SelectboxOptions::new("Group by", ["category", "region"]).key("group_by")).unwrap(), Some("category"));
        let element::Type::Selectbox(select) = input(&mut wire) else { panic!() };
        assert!(select.id.ends_with("-group_by"));
        assert_eq!(select.default, Some(0));
        let changed = |st: &Streamlit| {
            let state = st.session_state();
            assert_eq!(state.get::<String>("group_by").unwrap().as_deref(), Some("region"));
            assert_eq!(state.get::<i64>("amount").unwrap(), Some(10));
            assert_eq!(state.get::<bool>("include").unwrap(), Some(false));
            state.set("callback_ran", true).unwrap();
        };
        assert_eq!(st.slider(SliderOptions::new("Amount", 0_i64).max(200).step(10).key("amount").on_change(changed)).unwrap(), 0);
        let element::Type::Slider(slider) = input(&mut wire) else { panic!() };
        assert_eq!(slider.default, vec![0.0]);
        assert_eq!((slider.data_type, slider.step), (0, 10.0));
        assert!(st.checkbox(CheckboxOptions::new("Include").value(true).key("include")).unwrap());
        let element::Type::Checkbox(check) = input(&mut wire) else { panic!() };
        assert!(check.default);
        state.finish_widgets();

        // Exactly the three value types observed in the real closed-loop oracle.
        let callbacks = state.begin_widgets(vec![
            WidgetState {
                id: slider.id,
                value: Some(widget_state::Value::DoubleArrayValue(proto::DoubleArray { data: vec![10.0] })),
            },
            WidgetState {
                id: check.id,
                value: Some(widget_state::Value::BoolValue(false)),
            },
            WidgetState {
                id: select.id,
                value: Some(widget_state::Value::StringValue("region".into())),
            },
        ]);
        assert_eq!(callbacks.len(), 1);
        let (st, _) = app(&state);
        for callback in callbacks {
            callback(&st);
        }
        assert_eq!(state.get::<bool>("callback_ran").unwrap(), Some(true));
        assert_eq!(st.slider(SliderOptions::new("Renamed", 50_i64).max(200).step(10).key("amount")).unwrap(), 10);
        state.finish_widgets();
        assert_eq!(state.get::<String>("group_by").unwrap(), None, "unrendered widget key is cleaned");
        assert_eq!(state.get::<bool>("callback_ran").unwrap(), Some(true), "manual application keys survive");
    }

    #[test]
    fn preseed_key_guards_duplicates_and_trigger_reset() {
        let state = SessionState::default();
        state.set("chosen", 20_i32).unwrap();
        state.begin_widgets(vec![]);
        let (st, mut wire) = app(&state);
        assert_eq!(st.selectbox(SelectboxOptions::new("Numbers", [10, 20]).format_func(|n| format!("option-{n}")).key("chosen")).unwrap(), Some(20));
        let element::Type::Selectbox(select) = input(&mut wire) else { panic!() };
        assert_eq!(select.raw_value.as_deref(), Some("option-20"));
        assert!(select.set_value);
        assert!(state.set("chosen", 10).is_err());
        assert!(matches!(st.checkbox(CheckboxOptions::new("Other").key("chosen")), Err(WidgetError::DuplicateKey(_))));
        assert!(!st.try_button(ButtonOptions::new("Pulse").key("pulse").disabled(true)).unwrap());
        let element::Type::Button(button) = input(&mut wire) else { panic!() };
        assert!(button.disabled);
        assert!(state.set("pulse", true).is_err());
        state.finish_widgets();
        let callbacks = state.begin_widgets(vec![WidgetState {
            id: button.id.clone(),
            value: Some(widget_state::Value::TriggerValue(true)),
        }]);
        assert!(callbacks.is_empty());
        let (st, _) = app(&state);
        assert!(st.button(ButtonOptions::new("Pulse").key("pulse")));
        state.finish_widgets();
        state.begin_widgets(vec![]);
        let (st, _) = app(&state);
        assert!(!st.button(ButtonOptions::new("Pulse").key("pulse")));
        assert_eq!(SessionState::default().get::<i32>("chosen").unwrap(), None);
    }

    #[test]
    fn numeric_ranges_empty_selection_and_constraint_reset() {
        let state = SessionState::default();
        state.begin_widgets(vec![]);
        let (st, mut wire) = app(&state);
        assert_eq!(st.slider(SliderOptions::new("Range", (0.2, 0.8)).key("range")).unwrap(), (0.2, 0.8));
        let element::Type::Slider(slider) = input(&mut wire) else { panic!() };
        assert_eq!((slider.data_type, slider.default), (1, vec![0.2, 0.8]));
        assert_eq!(st.selectbox(SelectboxOptions::new("Empty", Vec::<String>::new())).unwrap(), None);
        let element::Type::Selectbox(empty) = input(&mut wire) else { panic!() };
        assert!(empty.disabled);
        assert_eq!(empty.default, None);
        assert!(matches!(st.selectbox(SelectboxOptions::new("Empty", Vec::<String>::new())), Err(WidgetError::DuplicateId(_))));
        assert!(st.slider(SliderOptions::new("Reversed", (8_i32, 2))).is_err());
        assert!(st.slider(SliderOptions::new("Infinite", 0.0).max(f64::INFINITY)).is_err());
        assert!(st.slider(SliderOptions::new("Unsafe int", 0_i64).max(9_007_199_254_740_992.0)).is_err());
        state.finish_widgets();
        state.begin_widgets(vec![]);
        let (st, _) = app(&state);
        assert_eq!(st.slider(SliderOptions::new("Range", (0.1, 0.9)).max(2.0).key("range")).unwrap(), (0.1, 0.9));
    }

    #[test]
    fn float_array_range_and_native_integer_limits() {
        let state = SessionState::default();
        state.begin_widgets(vec![]);
        let (st, mut wire) = app(&state);
        assert_eq!(st.slider(SliderOptions::new("Rate", 0.25).format("percent").key("rate")).unwrap(), 0.25);
        let element::Type::Slider(rate) = input(&mut wire) else { panic!() };
        assert_eq!((rate.min, rate.max, rate.step), (0.0, 1.0, 0.01));
        assert_eq!(rate.format, "percent");
        assert_eq!(st.slider(SliderOptions::new("Array", [2_i32, 8_i32]).key("array")).unwrap(), [2, 8]);
        let element::Type::Slider(array) = input(&mut wire) else { panic!() };
        // Returning an i32 cannot represent these bounds; reject before registration.
        assert!(st.slider(SliderOptions::new("Too wide", 0_i32).max(3_000_000_000.0).key("wide")).is_err());
        assert_eq!(state.get::<i32>("wide").unwrap(), None);
        state.finish_widgets();
        state.begin_widgets(vec![
            WidgetState {
                id: rate.id,
                value: Some(widget_state::Value::DoubleArrayValue(proto::DoubleArray { data: vec![0.75] })),
            },
            WidgetState {
                id: array.id,
                value: Some(widget_state::Value::DoubleArrayValue(proto::DoubleArray { data: vec![4.0, 10.0] })),
            },
        ]);
        let (st, _) = app(&state);
        assert_eq!(st.slider(SliderOptions::new("Rate", 0.25).format("percent").key("rate")).unwrap(), 0.75, "format does not scale the returned value");
        assert_eq!(st.slider(SliderOptions::new("Array", [2_i32, 8_i32]).key("array")).unwrap(), [4, 10]);
    }

    #[test]
    fn deleted_keys_rebind_and_unrendered_widgets_expire() {
        let state = SessionState::default();
        state.set("manual", "keep").unwrap();
        state.begin_widgets(vec![]);
        let (st, _) = app(&state);
        assert!(st.checkbox(CheckboxOptions::new("Checked").value(true).key("checked")).unwrap());
        state.finish_widgets();
        assert_eq!(state.remove("checked"), Some(Value::Bool(true)));
        state.begin_widgets(vec![]);
        let (st, _) = app(&state);
        assert!(st.checkbox(CheckboxOptions::new("Renamed").value(false).key("checked")).unwrap(), "deleting a key does not reset an existing widget");
        assert_eq!(state.get::<bool>("checked").unwrap(), Some(true));
        state.finish_widgets();
        state.begin_widgets(vec![]);
        state.finish_widgets(); // A run that does not render the checkbox.
        assert_eq!(state.get::<bool>("checked").unwrap(), None);
        assert_eq!(state.get::<String>("manual").unwrap().as_deref(), Some("keep"));
        state.begin_widgets(vec![]);
        let (st, _) = app(&state);
        assert!(!st.checkbox(CheckboxOptions::new("Checked").key("checked")).unwrap());
    }

    #[test]
    fn identity_fields_cannot_alias_through_delimiters() {
        let state = SessionState::default();
        state.begin_widgets(vec![]);
        let (st, mut wire) = app(&state);
        assert!(!st.checkbox(CheckboxOptions::new("a:b").help("c")).unwrap());
        assert!(!st.checkbox(CheckboxOptions::new("a").help("b:c")).unwrap());
        let element::Type::Checkbox(a) = input(&mut wire) else { panic!() };
        let element::Type::Checkbox(b) = input(&mut wire) else { panic!() };
        assert_ne!(a.id, b.id, "distinct parameter tuples must not share an automatic ID");
    }

    #[test]
    fn shorthand_and_advanced_builders_preserve_types_defaults_errors_and_proto() {
        use prost::Message;
        let (short, mut short_wire) = app(&SessionState::default());
        let (advanced, mut advanced_wire) = app(&SessionState::default());

        let checked: bool = short.checkbox(("Include", true)).unwrap();
        assert_eq!(checked, advanced.checkbox(CheckboxOptions::new("Include").value(true)).unwrap());
        assert_eq!(short.checkbox("Default checkbox").unwrap(), advanced.checkbox(CheckboxOptions::new("Default checkbox")).unwrap());
        let selected: Option<&str> = short.selectbox(("Group", ["category", "region"])).unwrap();
        assert_eq!(selected, advanced.selectbox(SelectboxOptions::new("Group", ["category", "region"])).unwrap());
        let selected: Option<i32> = short.selectbox((String::from("Numbers"), vec![1_i32, 2])).unwrap();
        assert_eq!(selected, advanced.selectbox::<i32>(SelectboxOptions::new("Numbers", [1_i32, 2])).unwrap());
        let count: i64 = short.slider(("Count", 0_i64)).unwrap();
        assert_eq!(count, advanced.slider::<i64>(SliderOptions::new("Count", 0_i64)).unwrap());
        let bounded: i64 = short.slider(("Amount", 20_i64, 10..=200)).unwrap();
        assert_eq!(bounded, advanced.slider(SliderOptions::new("Amount", 20_i64).min(10).max(200)).unwrap());
        let ratio: f64 = short.slider(("Ratio", 0.25_f64)).unwrap();
        assert_eq!(ratio, advanced.slider(SliderOptions::new("Ratio", 0.25_f64)).unwrap());
        let range: (i64, i64) = short.slider(("Range", (20_i64, 80_i64))).unwrap();
        assert_eq!(range, advanced.slider(SliderOptions::new("Range", (20_i64, 80_i64))).unwrap());
        let array: [f64; 2] = short.slider(("Array", [0.2_f64, 0.8_f64], 0.0..=1.0)).unwrap();
        assert_eq!(array, advanced.slider(SliderOptions::new("Array", [0.2_f64, 0.8_f64]).min(0.0).max(1.0)).unwrap());
        let bad_short: Result<i64, WidgetError> = short.slider(("Invalid", 0_i64, std::ops::RangeInclusive::new(10, 0)));
        let bad_advanced = advanced.slider(SliderOptions::new("Invalid", 0_i64).min(10).max(0));
        assert!(matches!(bad_short, Err(WidgetError::InvalidValue(_))));
        assert!(matches!(bad_advanced, Err(WidgetError::InvalidValue(_))));
        let mut compared = 0;
        loop {
            match (short_wire.try_recv(), advanced_wire.try_recv()) {
                (Ok(short), Ok(advanced)) => {
                    assert_eq!(short.encode_to_vec(), advanced.encode_to_vec());
                    compared += 1;
                }
                (Err(_), Err(_)) => break,
                _ => panic!("different number of emitted elements"),
            }
        }
        assert_eq!(compared, 9, "failed calls must not emit an element");
    }
}
