//! Typed native inputs. These methods work on Streamlit and its containers.
use crate::UploadedFiles;
use crate::api::{AppendChild, ButtonOptions};
use crate::elements::form::Form;
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
    fn identity_in_form(&self, form_id: &str, extra: &str) -> String {
        let identity = self.identity(extra);
        if form_id.is_empty() { identity } else { serde_json::to_string(&(form_id, identity)).expect("string identity serializes") }
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

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum FileUploadMode {
    Single,
    Multiple,
    Directory,
}

/// File selection uses the same key/callback/render lifecycle as other inputs.
pub struct FileUploaderOptions {
    common: InputOptions,
    accepted_types: Vec<String>,
    max_upload_size_mb: i32,
    mode: FileUploadMode,
}
impl FileUploaderOptions {
    pub fn new(label: impl Into<String>) -> Self {
        Self {
            common: InputOptions::new(label),
            accepted_types: Vec::new(),
            max_upload_size_mb: 200,
            mode: FileUploadMode::Single,
        }
    }
    pub fn accepted_types(mut self, types: impl IntoIterator<Item = impl Into<String>>) -> Self {
        self.accepted_types = types
            .into_iter()
            .map(Into::into)
            .map(|kind: String| {
                if kind.starts_with('.') || kind.contains('/') {
                    kind
                } else if matches!(kind.as_str(), "image" | "audio" | "video" | "text") {
                    format!("{kind}/*")
                } else {
                    format!(".{kind}")
                }
            })
            .collect();
        self
    }
    pub fn max_upload_size_mb(mut self, mb: i32) -> Self {
        self.max_upload_size_mb = mb;
        self
    }
    pub fn mode(mut self, mode: FileUploadMode) -> Self {
        self.mode = mode;
        self
    }
    common_builders!();
}
impl From<&str> for FileUploaderOptions {
    fn from(label: &str) -> Self {
        Self::new(label)
    }
}
impl From<String> for FileUploaderOptions {
    fn from(label: String) -> Self {
        Self::new(label)
    }
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

#[derive(Clone, Copy, Debug, PartialEq, Eq, serde::Serialize)]
pub enum TextInputType {
    Default,
    Password,
    Email,
    Url,
    Phone,
    Search,
}

impl TextInputType {
    fn wire(self) -> proto::text_input::Type {
        match self {
            Self::Default => proto::text_input::Type::Default,
            Self::Password => proto::text_input::Type::Password,
            Self::Email => proto::text_input::Type::Email,
            Self::Url => proto::text_input::Type::Url,
            Self::Phone => proto::text_input::Type::Phone,
            Self::Search => proto::text_input::Type::Search,
        }
    }

    fn default_autocomplete(self) -> &'static str {
        match self {
            Self::Default => "",
            Self::Password => "new-password",
            Self::Email => "email",
            Self::Url => "url",
            Self::Phone => "tel",
            Self::Search => "off",
        }
    }

    fn default_icon(self) -> &'static str {
        match self {
            Self::Email => ":material/mail:",
            Self::Url => ":material/link:",
            Self::Phone => ":material/call:",
            Self::Search => ":material/search:",
            Self::Default | Self::Password => "",
        }
    }

    fn default_placeholder(self) -> &'static str {
        match self {
            Self::Email => "you@example.com",
            Self::Url => "https://example.com",
            Self::Phone => "+1 234 567 8900",
            Self::Search => "Search",
            Self::Default | Self::Password => "",
        }
    }

    fn default_validation(self) -> (Option<&'static str>, Option<&'static str>) {
        match self {
            Self::Email => (Some(r"^[^\s@]+@[^\s@]+\.[^\s@]+$"), Some("Enter a valid email address.")),
            Self::Url => (Some(r"^([Hh][Tt][Tt][Pp][Ss]?://)?[^\s/.]+\.[^\s]+$"), Some("Enter a valid URL.")),
            Self::Default | Self::Password | Self::Phone | Self::Search => (None, None),
        }
    }
}

#[derive(Clone, Debug, Default, PartialEq, Eq)]
pub enum TextValidation {
    /// Use the input type's built-in rule; default/password have no rule.
    #[default]
    Inherit,
    /// Turn a specialized type's built-in rule off.
    Off,
    Pattern {
        regex: String,
        message: Option<String>,
    },
}

#[derive(Clone, Debug, Default, PartialEq, Eq, serde::Serialize)]
pub enum TextLive {
    #[default]
    CommitOnEnterBlur,
    Debounce(u32),
    Invalid(String),
}

impl TextLive {
    fn parse_duration(value: &str) -> Result<Self, WidgetError> {
        let error = WidgetError::InvalidValue(format!("live duration must be 0, milliseconds, or seconds no greater than one minute: {value}"));
        let (number, unit, explicit_unit): (&str, f64, bool) = value
            .strip_suffix("ms")
            .map(|number| (number, 1.0, true))
            .or_else(|| value.strip_suffix('s').map(|number| (number, 1000.0, true)))
            .unwrap_or((value, 1.0, false));
        let Ok(number) = number.parse::<f64>() else { return Err(error) };
        let milliseconds = number * unit;
        if !milliseconds.is_finite() || !(0.0..=60_000.0).contains(&milliseconds) {
            return Err(error);
        }
        if !explicit_unit && milliseconds != 0.0 {
            return Err(error);
        }
        let milliseconds = milliseconds.round();
        u32::try_from(milliseconds as i64).map(TextLive::Debounce).map_err(|_| error)
    }
}

#[derive(Clone, Copy, Debug, Default, PartialEq, Eq, serde::Serialize)]
pub enum TextBind {
    #[default]
    None,
    QueryParams,
}

pub struct TextInputOptions {
    common: InputOptions,
    value: Option<String>,
    max_chars: Option<usize>,
    input_type: TextInputType,
    autocomplete: Option<String>,
    placeholder: Option<String>,
    required: bool,
    icon: Option<String>,
    validation: TextValidation,
    live: TextLive,
    bind: TextBind,
}

impl TextInputOptions {
    pub fn new(label: impl Into<String>) -> Self {
        Self {
            common: InputOptions::new(label),
            value: Some(String::new()),
            max_chars: None,
            input_type: TextInputType::Default,
            autocomplete: None,
            placeholder: None,
            required: false,
            icon: None,
            validation: TextValidation::Inherit,
            live: TextLive::CommitOnEnterBlur,
            bind: TextBind::None,
        }
    }

    /// Defaults to an empty string, distinct from `value_none`.
    pub fn value(mut self, value: impl ToString) -> Self {
        self.value = Some(value.to_string());
        self
    }

    pub fn value_none(mut self) -> Self {
        self.value = None;
        self
    }

    pub fn max_chars(mut self, max_chars: usize) -> Self {
        self.max_chars = Some(max_chars);
        self
    }

    pub fn no_max_chars(mut self) -> Self {
        self.max_chars = None;
        self
    }

    pub fn input_type(mut self, input_type: TextInputType) -> Self {
        self.input_type = input_type;
        self
    }

    pub fn autocomplete(mut self, autocomplete: impl Into<String>) -> Self {
        self.autocomplete = Some(autocomplete.into());
        self
    }

    pub fn derived_autocomplete(mut self) -> Self {
        self.autocomplete = None;
        self
    }

    pub fn placeholder(mut self, placeholder: impl Into<String>) -> Self {
        self.placeholder = Some(placeholder.into());
        self
    }

    pub fn no_placeholder(mut self) -> Self {
        self.placeholder = Some(String::new());
        self
    }

    pub fn required(mut self, required: bool) -> Self {
        self.required = required;
        self
    }

    pub fn icon(mut self, icon: impl Into<String>) -> Self {
        self.icon = Some(icon.into());
        self
    }

    pub fn validate(mut self, regex: impl Into<String>) -> Self {
        self.validation = TextValidation::Pattern { regex: regex.into(), message: None };
        self
    }

    pub fn validate_with_message(mut self, regex: impl Into<String>, message: impl Into<String>) -> Self {
        self.validation = TextValidation::Pattern {
            regex: regex.into(),
            message: Some(message.into()),
        };
        self
    }

    pub fn validation(mut self, validation: TextValidation) -> Self {
        self.validation = validation;
        self
    }

    pub fn live(mut self, live: bool) -> Self {
        self.live = if live { TextLive::Debounce(250) } else { TextLive::CommitOnEnterBlur };
        self
    }

    pub fn live_debounce_ms(mut self, milliseconds: u32) -> Self {
        self.live = TextLive::Debounce(milliseconds);
        self
    }

    pub fn commit_on_every_change(mut self) -> Self {
        self.live = TextLive::Debounce(0);
        self
    }

    /// Accept the documented duration-string subset: zero without a unit,
    /// milliseconds, or seconds. Invalid input is rejected when the widget is
    /// instantiated, never silently coerced to another debounce.
    pub fn live_duration(mut self, duration: impl Into<String>) -> Self {
        self.live = TextLive::Invalid(duration.into());
        self
    }

    pub fn bind(mut self, bind: TextBind) -> Self {
        self.bind = bind;
        self
    }

    common_builders!();
}

impl From<&str> for TextInputOptions {
    fn from(label: &str) -> Self {
        Self::new(label)
    }
}

impl From<String> for TextInputOptions {
    fn from(label: String) -> Self {
        Self::new(label)
    }
}

impl<L: Into<String>> From<(L, Option<String>)> for TextInputOptions {
    fn from((label, value): (L, Option<String>)) -> Self {
        let options = Self::new(label);
        match value {
            Some(value) => options.value(value),
            None => options.value_none(),
        }
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

#[derive(Clone, Copy, Debug, Default, PartialEq, Eq, serde::Serialize)]
pub enum FormSubmitButtonType {
    Primary,
    #[default]
    Secondary,
    Tertiary,
}

impl FormSubmitButtonType {
    fn wire(self) -> &'static str {
        match self {
            Self::Primary => "primary",
            Self::Secondary => "secondary",
            Self::Tertiary => "tertiary",
        }
    }
}

#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
pub enum ButtonIconPosition {
    #[default]
    Left,
    Right,
}

pub struct FormSubmitButtonOptions {
    label: String,
    key: Option<String>,
    help: Option<String>,
    button_type: FormSubmitButtonType,
    icon: Option<String>,
    icon_position: ButtonIconPosition,
    disabled: bool,
    width: crate::elements::common::ElementWidth,
    shortcut: Option<String>,
    wrap: Option<bool>,
    callback: Option<WidgetCallback>,
}

impl Default for FormSubmitButtonOptions {
    fn default() -> Self {
        Self::new("Submit")
    }
}

impl FormSubmitButtonOptions {
    pub fn new(label: impl Into<String>) -> Self {
        Self {
            label: label.into(),
            key: None,
            help: None,
            button_type: FormSubmitButtonType::default(),
            icon: None,
            icon_position: ButtonIconPosition::default(),
            disabled: false,
            width: crate::elements::common::ElementWidth::Content,
            shortcut: None,
            wrap: None,
            callback: None,
        }
    }

    pub fn key(mut self, key: impl Into<String>) -> Self {
        self.key = Some(key.into());
        self
    }

    pub fn help(mut self, help: impl Into<String>) -> Self {
        self.help = Some(help.into());
        self
    }

    pub fn button_type(mut self, button_type: FormSubmitButtonType) -> Self {
        self.button_type = button_type;
        self
    }

    pub fn icon(mut self, icon: impl Into<String>) -> Self {
        self.icon = Some(icon.into());
        self
    }

    pub fn icon_position(mut self, icon_position: ButtonIconPosition) -> Self {
        self.icon_position = icon_position;
        self
    }

    pub fn disabled(mut self, disabled: bool) -> Self {
        self.disabled = disabled;
        self
    }

    pub fn width(mut self, width: impl Into<crate::elements::common::ElementWidth>) -> Self {
        self.width = width.into();
        self
    }

    pub fn shortcut(mut self, shortcut: impl Into<String>) -> Self {
        self.shortcut = Some(shortcut.into());
        self
    }

    pub fn wrap(mut self, wrap: Option<bool>) -> Self {
        self.wrap = wrap;
        self
    }

    pub fn on_click(mut self, callback: impl Fn(&Streamlit) + Send + Sync + 'static) -> Self {
        self.callback = Some(Arc::new(callback));
        self
    }
}

impl From<&str> for FormSubmitButtonOptions {
    fn from(label: &str) -> Self {
        Self::new(label)
    }
}

impl From<String> for FormSubmitButtonOptions {
    fn from(label: String) -> Self {
        Self::new(label)
    }
}

impl Form<'_> {
    /// Register and append the form's submit trigger.
    pub fn form_submit_button(&self, options: impl Into<FormSubmitButtonOptions>) -> Result<bool, WidgetError> {
        let options = options.into();
        if matches!(options.width, crate::elements::common::ElementWidth::Value(width) if width <= 0) {
            return Err(WidgetError::InvalidValue("form submit button width must be positive".into()));
        }
        let identity = if options.key.is_some() {
            String::new()
        } else {
            serde_json::to_string(&(
                &options.label,
                &options.help,
                &options.button_type,
                &options.icon,
                format!("{:?}", options.icon_position),
                options.disabled,
                format!("{:?}", options.width),
                &options.shortcut,
                options.wrap,
                options.callback.is_some(),
            ))?
        };
        let identity = serde_json::to_string(&(self.parent_form_id(), identity))?;
        let state = self.get_app().lock().session_state.clone();
        let (id, value, _) = state.register_widget(
            WidgetSpec {
                kind: "form_submit_button",
                key: options.key.as_deref(),
                identity: &identity,
                default: false.into(),
                codec: Codec::Trigger,
                callback: options.callback,
            },
            |value| value.as_bool().ok_or_else(|| WidgetError::InvalidValue("form submit button expects bool".into())),
        )?;
        let icon_position = match options.icon_position {
            ButtonIconPosition::Left => 0,
            ButtonIconPosition::Right => 1,
        };
        let element = ButtonElement::new(id, options.label)
            .help(options.help.unwrap_or_default())
            .r#type(options.button_type.wire().to_owned())
            .icon(options.icon.unwrap_or_default())
            .shortcut(options.shortcut.unwrap_or_default())
            .width(options.width)
            .disabled(options.disabled)
            .icon_position(icon_position)
            .wrap(options.wrap)
            .form_id(self.parent_form_id().unwrap_or_default())
            .form_submitter(true);
        self.push(Rc::new(RefCell::new(element)));
        self.record_submit();
        Ok(value)
    }
}

fn form_scope<C: AppendChild>(this: &C, has_callback: bool) -> Result<String, WidgetError> {
    let form_id = this.parent_form_id();
    if form_id.is_some() && has_callback {
        return Err(WidgetError::InvalidValue("only form_submit_button can have a callback inside a form".into()));
    }
    Ok(form_id.unwrap_or_default())
}

pub trait InputWidgets {
    fn file_uploader(&self, options: impl Into<FileUploaderOptions>) -> Result<UploadedFiles, WidgetError>;
    fn checkbox(&self, options: impl Into<CheckboxOptions>) -> Result<bool, WidgetError>;
    fn text_input(&self, options: impl Into<TextInputOptions>) -> Result<Option<String>, WidgetError>;
    /// Accept a builder or `(label, options)`; both retain the same defaults.
    fn selectbox<T: Clone + Serialize>(&self, options: impl Into<SelectboxOptions<T>>) -> Result<Option<T>, WidgetError>;
    /// Accept a builder, `(label, value)`, or `(label, value, min..=max)`.
    /// A tuple/array value denotes the selected range, not the permitted bounds.
    fn slider<T: SliderValue>(&self, options: impl Into<SliderOptions<T>>) -> Result<T, WidgetError>;
    /// Fallible counterpart to the original boolean-returning `button` method.
    fn try_button(&self, options: impl Into<ButtonOptions>) -> Result<bool, WidgetError>;
}

impl<C: AppendChild> InputWidgets for C {
    fn file_uploader(&self, options: impl Into<FileUploaderOptions>) -> Result<UploadedFiles, WidgetError> {
        let options = options.into();
        let c = options.common;
        let form_id = form_scope(self, c.callback.is_some())?;
        let width_config = c.width(false)?;
        if options.max_upload_size_mb <= 0 {
            return Err(WidgetError::InvalidValue("max_upload_size_mb must be positive".into()));
        }
        let multiple = options.mode != FileUploadMode::Single;
        let constraints = serde_json::to_string(&(&options.accepted_types, options.max_upload_size_mb, format!("{:?}", options.mode)))?;
        let identity = c.identity_in_form(&form_id, &constraints);
        let state = self.get_app().lock().session_state.clone();
        let uploads = state.uploads.clone();
        let (id, files, _) = state.register_widget(
            WidgetSpec {
                kind: "file_uploader",
                key: c.key.as_deref(),
                identity: &identity,
                default: Value::Array(Vec::new()),
                codec: Codec::Files { store: uploads.clone(), multiple },
                callback: c.callback,
            },
            |value| {
                let ids: Vec<String> = serde_json::from_value(value.clone())?;
                let store = uploads.lock();
                let files: Vec<_> = ids.iter().filter_map(|id| store.get(id)).collect();
                Ok(if multiple { UploadedFiles::Multiple(files) } else { UploadedFiles::Single(files.into_iter().next()) })
            },
        )?;
        self.push(Rc::new(RefCell::new(InputElement(proto::Element {
            width_config,
            r#type: Some(element::Type::FileUploader(proto::FileUploader {
                id,
                label: c.label,
                form_id,
                r#type: options.accepted_types,
                max_upload_size_mb: options.max_upload_size_mb,
                multiple_files: multiple,
                accept_directory: options.mode == FileUploadMode::Directory,
                help: c.help,
                disabled: c.disabled,
                label_visibility: c.visibility.wire(),
                ignore_rerun: c.ignore_rerun,
            })),
            ..Default::default()
        }))));
        Ok(files)
    }
    fn checkbox(&self, options: impl Into<CheckboxOptions>) -> Result<bool, WidgetError> {
        let options = options.into();
        let c = options.common;
        let form_id = form_scope(self, c.callback.is_some())?;
        let width_config = c.width(true)?;
        let identity = c.identity_in_form(&form_id, &if c.key.is_some() { String::new() } else { options.value.to_string() });
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
                form_id,
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

    fn text_input(&self, options: impl Into<TextInputOptions>) -> Result<Option<String>, WidgetError> {
        let options = options.into();
        let options = if let TextLive::Invalid(duration) = &options.live {
            let duration = duration.clone();
            let mut normalized = options;
            normalized.live = TextLive::parse_duration(&duration)?;
            normalized
        } else {
            options
        };
        let c = options.common;
        let form_id = form_scope(self, c.callback.is_some())?;
        if matches!(options.live, TextLive::Debounce(milliseconds) if milliseconds > 60_000) {
            return Err(WidgetError::InvalidValue("text_input live debounce cannot exceed one minute".into()));
        }
        if options.bind == TextBind::QueryParams && c.key.is_none() {
            return Err(WidgetError::InvalidValue("text_input query binding requires a key".into()));
        }
        if options.bind == TextBind::QueryParams && options.input_type == TextInputType::Password {
            return Err(WidgetError::InvalidValue("text_input query binding cannot use a password input".into()));
        }
        let width_config = c.width(false)?;
        let default = options.value.clone().map_or_else(|| Value::Null, Value::String);
        let validation_regex = match &options.validation {
            TextValidation::Inherit => options.input_type.default_validation().0.map(String::from),
            TextValidation::Off => Some(String::new()),
            TextValidation::Pattern { regex, .. } => Some(regex.clone()),
        };
        let identity = c.identity_in_form(
            &form_id,
            &if c.key.is_some() {
                serde_json::to_string(&(&options.max_chars, &validation_regex))?
            } else {
                serde_json::to_string(&(
                    &options.value,
                    &options.max_chars,
                    &options.input_type,
                    &options.autocomplete,
                    &options.placeholder,
                    options.required,
                    &options.icon,
                    &validation_regex,
                    &options.live,
                    &options.bind,
                    c.disabled,
                    c.width,
                    c.ignore_rerun,
                    format!("{:?}", c.visibility),
                    c.callback.is_some(),
                ))?
            },
        );
        let state = self.get_app().lock().session_state.clone();
        let (id, value, set_value) = state.register_widget(
            WidgetSpec {
                kind: "text_input",
                key: c.key.as_deref(),
                identity: &identity,
                default,
                codec: Codec::Text { max_chars: options.max_chars },
                callback: c.callback,
            },
            |value| Ok(value.as_str().map(str::to_owned)),
        )?;
        let (validate_regex, validate_message) = match options.validation {
            TextValidation::Inherit => {
                let (regex, message) = options.input_type.default_validation();
                (regex.map(String::from), message.map(String::from))
            }
            TextValidation::Off => (Some(String::new()), None),
            TextValidation::Pattern { regex, message } => (Some(regex), message),
        };
        self.push(Rc::new(RefCell::new(InputElement(proto::Element {
            width_config,
            has_one_shot_effect: set_value.then_some(true),
            r#type: Some(element::Type::TextInput(proto::TextInput {
                id,
                label: c.label,
                default: options.value,
                r#type: options.input_type.wire() as i32,
                max_chars: options.max_chars.unwrap_or_default() as u32,
                help: c.help,
                form_id,
                value: if set_value { value.clone() } else { None },
                set_value,
                autocomplete: options.autocomplete.unwrap_or_else(|| options.input_type.default_autocomplete().to_owned()),
                placeholder: options.placeholder.unwrap_or_else(|| options.input_type.default_placeholder().to_owned()),
                disabled: c.disabled,
                label_visibility: c.visibility.wire(),
                icon: options.icon.unwrap_or_else(|| options.input_type.default_icon().to_owned()),
                query_param_key: (options.bind == TextBind::QueryParams).then(|| c.key.clone()).flatten(),
                validate_regex,
                validate_message,
                ignore_rerun: c.ignore_rerun,
                live_debounce_ms: match options.live {
                    TextLive::CommitOnEnterBlur | TextLive::Invalid(_) => None,
                    TextLive::Debounce(milliseconds) => Some(milliseconds),
                },
                required: options.required,
            })),
            ..Default::default()
        }))));
        Ok(value)
    }

    fn selectbox<T: Clone + Serialize>(&self, options: impl Into<SelectboxOptions<T>>) -> Result<Option<T>, WidgetError> {
        let options = options.into();
        let c = options.common;
        let form_id = form_scope(self, c.callback.is_some())?;
        let width_config = c.width(false)?;
        if !options.options.is_empty() && options.index.is_some_and(|i| i >= options.options.len()) {
            return Err(WidgetError::InvalidValue("selectbox index is outside options".into()));
        }
        let native: Vec<Value> = options.options.iter().map(serde_json::to_value).collect::<Result<_, _>>()?;
        let default = options.index.filter(|index| *index < native.len()).map(Value::from).unwrap_or(Value::Null);
        let identity = c.identity_in_form(&form_id, &if c.key.is_some() { String::new() } else { format!("{:?}:{:?}", options.labels, options.index) });
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
                form_id,
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
        let form_id = form_scope(self, c.callback.is_some())?;
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
        let identity = c.identity_in_form(&form_id, &if c.key.is_some() { constraints } else { format!("{constraints}:{default}:{:?}", options.format) });
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
                form_id,
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
        if self.parent_form_id().is_some() {
            return Err(WidgetError::InvalidValue("st.button cannot be added to a form".into()));
        }
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
    use crate::{FormOptions, SessionState, StreamlitApi};

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

    fn form_block(receiver: &mut tokio::sync::mpsc::UnboundedReceiver<ForwardMsg>) -> proto::Block {
        match receiver.try_recv().unwrap().r#type {
            Some(forward_msg::Type::Delta(proto::Delta { r#type: Some(delta::Type::AddBlock(block)), .. })) => block,
            other => panic!("expected form block, got {other:?}"),
        }
    }

    #[test]
    fn form_text_core_matches_reference_and_callbacks_see_batch_first() {
        let state = SessionState::default();
        state.begin_widgets(vec![]);
        let (st, mut wire) = app(&state);
        let callback = |st: &Streamlit| {
            let state = st.session_state();
            assert_eq!(state.get::<String>("default_note").unwrap().as_deref(), Some("hello"));
            assert_eq!(state.get::<bool>("default_agree").unwrap(), Some(true));
            state.set("callback_ran", true).unwrap();
        };
        let (note, agree, submitted) = st
            .form(FormOptions::new("default_form"), |form| {
                let note = form.text_input(TextInputOptions::new("Note").key("default_note"))?;
                let agree = form.checkbox(CheckboxOptions::new("Agree").key("default_agree"))?;
                let submitted = form.form_submit_button(FormSubmitButtonOptions::new("Apply").key("default_apply").on_click(callback))?;
                Ok((note, agree, submitted))
            })
            .unwrap();
        assert_eq!((note.as_deref(), agree, submitted), (Some(""), false, false));
        let block = form_block(&mut wire);
        let Some(proto::block::Type::Form(form)) = block.r#type else { panic!() };
        assert_eq!((form.form_id.as_str(), form.clear_on_submit, form.border, form.enter_to_submit), ("default_form", false, true, true));
        assert_eq!(block.width_config.map(|width| width.width_spec), Some(Some(proto::streamlit::width_config::WidthSpec::UseStretch(true))));
        assert_eq!(block.height_config.map(|height| height.height_spec), Some(Some(proto::streamlit::height_config::HeightSpec::UseContent(true))));
        let element::Type::TextInput(text) = input(&mut wire) else { panic!() };
        assert!(text.id.ends_with("-default_note"));
        assert_eq!((text.label.as_str(), text.default.as_deref(), text.form_id.as_str(), text.r#type), ("Note", Some(""), "default_form", 0));
        let element::Type::Checkbox(check) = input(&mut wire) else { panic!() };
        assert_eq!((check.form_id.as_str(), check.default, check.disabled), ("default_form", false, false));
        let element::Type::Button(button) = input(&mut wire) else { panic!() };
        assert_eq!((button.form_id.as_str(), button.is_form_submitter, button.r#type.as_str(), button.disabled), ("default_form", true, "secondary", false));
        state.finish_widgets();

        let callbacks = state.begin_widgets(vec![
            WidgetState {
                id: text.id,
                value: Some(widget_state::Value::StringValue("hello".into())),
            },
            WidgetState {
                id: check.id,
                value: Some(widget_state::Value::BoolValue(true)),
            },
            WidgetState {
                id: button.id,
                value: Some(widget_state::Value::TriggerValue(true)),
            },
        ]);
        assert_eq!(callbacks.len(), 1);
        let (st, mut wire) = app(&state);
        for callback in callbacks {
            callback(&st);
        }
        assert_eq!(state.get::<bool>("callback_ran").unwrap(), Some(true));
        let (note, agree, submitted) = st
            .form(FormOptions::new("default_form"), |form| {
                let note = form.text_input(TextInputOptions::new("Note").key("default_note"))?;
                let agree = form.checkbox(CheckboxOptions::new("Agree").key("default_agree"))?;
                let submitted = form.form_submit_button(FormSubmitButtonOptions::new("Apply").key("default_apply"))?;
                Ok((note, agree, submitted))
            })
            .unwrap();
        let block = form_block(&mut wire);
        let Some(proto::block::Type::Form(form)) = block.r#type else { panic!() };
        assert_eq!(form.form_id, "default_form");
        let element::Type::TextInput(_) = input(&mut wire) else { panic!() };
        let element::Type::Checkbox(_) = input(&mut wire) else { panic!() };
        let element::Type::Button(_) = input(&mut wire) else { panic!() };
        assert_eq!((note.as_deref(), agree, submitted), (Some("hello"), true, true));
        state.finish_widgets();
        state.begin_widgets(vec![]);
        let (st, _) = app(&state);
        let submitted = st.form(FormOptions::new("default_form"), |form| form.form_submit_button(FormSubmitButtonOptions::new("Apply").key("default_apply"))).unwrap();
        assert!(!submitted, "submit triggers reset after a completed run");
    }

    #[test]
    fn forms_render_in_containers_and_containers_render_in_forms() {
        let state = SessionState::default();
        state.begin_widgets(vec![]);
        let (st, mut wire) = app(&state);
        let container = st.container();
        container
            .form(FormOptions::new("outside_form"), |form| {
                form.text_input(TextInputOptions::new("Note").key("outside_note"))?;
                form.form_submit_button(FormSubmitButtonOptions::new("Apply").key("outside_apply"))
            })
            .unwrap();
        assert!(matches!(form_block(&mut wire).r#type, Some(proto::block::Type::FlexContainer(_))));
        assert!(matches!(form_block(&mut wire).r#type, Some(proto::block::Type::Form(_))));
        let element::Type::TextInput(text) = input(&mut wire) else { panic!() };
        assert_eq!(text.form_id, "outside_form");
        let element::Type::Button(button) = input(&mut wire) else { panic!() };
        assert!(button.is_form_submitter);

        let columns = st.columns(2);
        columns[0]
            .form(FormOptions::new("column_form"), |form| {
                form.text_input(TextInputOptions::new("Note").key("column_note"))?;
                form.form_submit_button(FormSubmitButtonOptions::new("Apply").key("column_apply"))
            })
            .unwrap();
        assert!(matches!(form_block(&mut wire).r#type, Some(proto::block::Type::FlexContainer(_))));
        assert!(matches!(form_block(&mut wire).r#type, Some(proto::block::Type::Column(_))));
        assert!(matches!(form_block(&mut wire).r#type, Some(proto::block::Type::Column(_))));
        assert!(matches!(form_block(&mut wire).r#type, Some(proto::block::Type::Form(_))));
        let element::Type::TextInput(column_text) = input(&mut wire) else { panic!() };
        assert_eq!(column_text.form_id, "column_form");
        let element::Type::Button(column_button) = input(&mut wire) else { panic!() };
        assert!(column_button.is_form_submitter);

        st.form(FormOptions::new("inside_form"), |form| {
            let container = form.container();
            container.text_input(TextInputOptions::new("Note").key("inside_note"))?;
            form.form_submit_button(FormSubmitButtonOptions::new("Apply").key("inside_apply"))
        })
        .unwrap();
        assert!(matches!(form_block(&mut wire).r#type, Some(proto::block::Type::Form(_))));
        assert!(matches!(form_block(&mut wire).r#type, Some(proto::block::Type::FlexContainer(_))));
        let element::Type::TextInput(text) = input(&mut wire) else { panic!() };
        assert_eq!(text.form_id, "inside_form");
        let element::Type::Button(button) = input(&mut wire) else { panic!() };
        assert!(button.is_form_submitter);
    }

    #[test]
    fn forms_need_submits_and_form_keys_share_widget_spelling() {
        let state = SessionState::default();
        state.begin_widgets(vec![]);
        let (st, mut wire) = app(&state);
        assert!(matches!(
            st.form(FormOptions::new("no_submit"), |form| {
                form.text_input(TextInputOptions::new("Note").key("missing_note"))
            }),
            Err(WidgetError::InvalidValue(message)) if message.contains("form_submit_button")
        ));
        assert!(wire.try_recv().is_err(), "an incomplete form must not append its children");

        let state = SessionState::default();
        state.begin_widgets(vec![]);
        let (st, mut wire) = app(&state);
        assert_eq!(st.text_input(TextInputOptions::new("Shared").key("shared")).unwrap(), Some(String::new()));
        st.form(FormOptions::new("shared"), |form| form.form_submit_button("Submit")).unwrap();
        assert!(wire.try_recv().is_ok());
    }

    #[test]
    fn forms_anonymous_identity_is_scoped_but_explicit_widget_keys_are_global() {
        let state = SessionState::default();
        state.begin_widgets(vec![]);
        let (st, mut wire) = app(&state);
        for key in ["a", "b"] {
            st.form(key, |form| {
                form.text_input("Note")?;
                form.form_submit_button("Apply")
            })
            .unwrap();
        }
        let mut ids = std::collections::HashSet::new();
        for _ in 0..2 {
            form_block(&mut wire);
            let element::Type::TextInput(text) = input(&mut wire) else { panic!() };
            assert!(ids.insert(text.id));
            let element::Type::Button(button) = input(&mut wire) else { panic!() };
            assert!(ids.insert(button.id));
        }
        assert!(wire.try_recv().is_err());
        st.form("same", |form| {
            form.text_input(TextInputOptions::new("Note").key("same"))?;
            form.form_submit_button("Submit")
        })
        .unwrap();
        assert!(matches!(st.text_input(TextInputOptions::new("Root").key("same")), Err(WidgetError::DuplicateKey(_))));
    }

    #[test]
    fn forms_abort_rolls_back_registration_and_widget_values() {
        let state = SessionState::default();
        state.begin_widgets(vec![]);
        state.set("shared", "seed").unwrap();
        let (st, mut wire) = app(&state);
        let result = st.form("retry", |form| {
            form.text_input(TextInputOptions::new("Hidden").key("shared"))?;
            form.form_submit_button(FormSubmitButtonOptions::new("Discard").key("discard"))?;
            Err::<(), _>(WidgetError::InvalidValue("abort".into()))
        });
        assert!(result.is_err());
        assert!(wire.try_recv().is_err());
        assert_eq!(state.get::<String>("shared").unwrap().as_deref(), Some("seed"));
        assert_eq!(state.get::<bool>("discard").unwrap(), None);
        st.form("retry", |form| {
            form.text_input(TextInputOptions::new("Visible").key("shared"))?;
            form.form_submit_button(FormSubmitButtonOptions::new("Keep").key("discard"))
        })
        .unwrap();
        assert_eq!(state.get::<bool>("discard").unwrap(), Some(false));
    }

    #[test]
    fn forms_live_duration_milliseconds_and_seconds_share_limits() {
        for (duration, milliseconds) in [("250ms", 250), ("0.25s", 250), ("1ms", 1), ("0", 0), ("60s", 60_000)] {
            assert_eq!(TextLive::parse_duration(duration).unwrap(), TextLive::Debounce(milliseconds));
        }
        for duration in ["60001ms", "60.001s", "-1ms", "NaNms", "infms", "250"] {
            assert!(TextLive::parse_duration(duration).is_err(), "{duration}");
        }
    }

    #[test]
    fn forms_invalid_batch_is_rejected_before_values_and_submit_callback() {
        let state = SessionState::default();
        state.begin_widgets(vec![]);
        let (st, mut wire) = app(&state);
        st.form("bounded", |form| {
            form.text_input(TextInputOptions::new("Bounded").key("bounded").max_chars(5))?;
            form.checkbox(CheckboxOptions::new("Agree").key("agree"))?;
            form.form_submit_button(FormSubmitButtonOptions::new("Apply").key("apply").on_click(|_| panic!("invalid batch reached callback")))
        })
        .unwrap();
        form_block(&mut wire);
        let element::Type::TextInput(text) = input(&mut wire) else { panic!() };
        let element::Type::Checkbox(check) = input(&mut wire) else { panic!() };
        let element::Type::Button(button) = input(&mut wire) else { panic!() };
        state.finish_widgets();
        let callbacks = state.begin_widgets(vec![
            WidgetState {
                id: button.id,
                value: Some(widget_state::Value::TriggerValue(true)),
            },
            WidgetState {
                id: check.id,
                value: Some(widget_state::Value::BoolValue(true)),
            },
            WidgetState {
                id: text.id,
                value: Some(widget_state::Value::StringValue("TOOLONG".into())),
            },
        ]);
        assert!(callbacks.is_empty());
        assert_eq!(state.get::<String>("bounded").unwrap().as_deref(), Some(""));
        assert_eq!(state.get::<bool>("agree").unwrap(), Some(false));
        assert_eq!(state.get::<bool>("apply").unwrap(), Some(false));
        let (st, _) = app(&state);
        assert_eq!(st.text_input(TextInputOptions::new("Bounded").key("bounded").max_chars(5)).unwrap(), Some(String::new()));
    }

    #[test]
    fn text_input_none_and_empty_are_distinct_wire_and_native_values() {
        let state = SessionState::default();
        state.begin_widgets(vec![]);
        let (st, mut wire) = app(&state);
        assert_eq!(st.text_input(TextInputOptions::new("None value").value_none().key("none_value")).unwrap(), None);
        let element::Type::TextInput(none) = input(&mut wire) else { panic!() };
        assert_eq!(none.default, None);
        assert_eq!(st.text_input(TextInputOptions::new("Empty value").key("empty_value")).unwrap(), Some(String::new()));
        let element::Type::TextInput(empty) = input(&mut wire) else { panic!() };
        assert_eq!(empty.default.as_deref(), Some(""));
        state.finish_widgets();
        let callbacks = state.begin_widgets(vec![
            WidgetState {
                id: none.id,
                value: Some(widget_state::Value::StringValue("x".into())),
            },
            WidgetState {
                id: empty.id,
                value: Some(widget_state::Value::StringValue(String::new())),
            },
        ]);
        assert!(callbacks.is_empty());
        let (st, _) = app(&state);
        assert_eq!(st.text_input(TextInputOptions::new("None value").value_none().key("none_value")).unwrap(), Some("x".into()));
        assert_eq!(st.text_input(TextInputOptions::new("Empty value").key("empty_value")).unwrap(), Some(String::new()));
    }

    #[test]
    fn text_input_advanced_fields_match_the_pinned_reference() {
        let state = SessionState::default();
        state.begin_widgets(vec![]);
        let (st, mut wire) = app(&state);

        let cases = [
            (TextInputOptions::new("Email").input_type(TextInputType::Email).key("type_email"), proto::text_input::Type::Email),
            (TextInputOptions::new("URL").input_type(TextInputType::Url).key("type_url"), proto::text_input::Type::Url),
            (TextInputOptions::new("Phone").input_type(TextInputType::Phone).key("type_phone"), proto::text_input::Type::Phone),
            (TextInputOptions::new("Search").input_type(TextInputType::Search).key("type_search"), proto::text_input::Type::Search),
            (TextInputOptions::new("Secret").input_type(TextInputType::Password).key("type_password"), proto::text_input::Type::Password),
        ];
        for (options, wire_type) in cases {
            assert_eq!(st.text_input(options).unwrap(), Some(String::new()));
            let element::Type::TextInput(text) = input(&mut wire) else { panic!() };
            assert_eq!(text.r#type, wire_type as i32);
        }
        // Rewind one frame at a time is awkward; use independent receivers below
        // only when a field assertion needs the whole Element. The five IDs and
        // scalar fields above establish that every specialized type registered.
        state.finish_widgets();
    }

    #[test]
    fn text_input_advanced_defaults_and_overrides_match_wire_fields() {
        let field = |st: &Streamlit, options: TextInputOptions| -> proto::TextInput {
            let (sender, mut receiver) = tokio::sync::mpsc::unbounded_channel();
            st.app.lock().set_render_context(RenderContext::with_sender("field".into(), sender));
            st.text_input(options).unwrap();
            let element::Type::TextInput(text) = input(&mut receiver) else { panic!() };
            text
        };
        let st = Streamlit::new();
        let email = field(&st, TextInputOptions::new("Email").input_type(TextInputType::Email).key("email"));
        assert_eq!(email.autocomplete, "email");
        assert_eq!(email.icon, ":material/mail:");
        assert_eq!(email.placeholder, "you@example.com");
        assert_eq!(email.validate_regex.as_deref(), Some(r"^[^\s@]+@[^\s@]+\.[^\s@]+$"));
        assert_eq!(email.validate_message.as_deref(), Some("Enter a valid email address."));
        let url = field(&st, TextInputOptions::new("URL").input_type(TextInputType::Url).key("url"));
        assert_eq!((url.autocomplete.as_str(), url.icon.as_str(), url.placeholder.as_str()), ("url", ":material/link:", "https://example.com"));
        assert_eq!(url.validate_regex.as_deref(), Some(r"^([Hh][Tt][Tt][Pp][Ss]?://)?[^\s/.]+\.[^\s]+$"));
        assert_eq!(url.validate_message.as_deref(), Some("Enter a valid URL."));
        let phone = field(&st, TextInputOptions::new("Phone").input_type(TextInputType::Phone).key("phone"));
        assert_eq!((phone.autocomplete.as_str(), phone.icon.as_str(), phone.placeholder.as_str()), ("tel", ":material/call:", "+1 234 567 8900"));
        assert!(phone.validate_regex.is_none() && phone.validate_message.is_none());
        let search = field(&st, TextInputOptions::new("Search").input_type(TextInputType::Search).key("search"));
        assert_eq!((search.autocomplete.as_str(), search.icon.as_str(), search.placeholder.as_str()), ("off", ":material/search:", "Search"));
        let password = field(&st, TextInputOptions::new("Secret").input_type(TextInputType::Password).key("password"));
        assert_eq!(password.autocomplete, "new-password");
        assert!(password.icon.is_empty() && password.placeholder.is_empty());

        let live = field(&st, TextInputOptions::new("Digits").key("digits").validate_with_message(r"^\d+$", "digits only").live(true));
        assert_eq!(live.live_debounce_ms, Some(250));
        assert_eq!(live.validate_regex.as_deref(), Some(r"^\d+$"));
        assert_eq!(live.validate_message.as_deref(), Some("digits only"));
        let required = field(&st, TextInputOptions::new("Required").key("required").required(true).placeholder("type here"));
        assert!(required.required && required.placeholder == "type here");
        let disabled = field(&st, TextInputOptions::new("Disabled").key("disabled").disabled(true).value("fixed"));
        assert!(disabled.disabled && disabled.default.as_deref() == Some("fixed"));
        let cjk = field(&st, TextInputOptions::new("中文").key("cjk").max_chars(5));
        assert_eq!(cjk.max_chars, 5);
        let half_second = field(&st, TextInputOptions::new("Search").key("half_second").live_duration("0.5s"));
        assert_eq!(half_second.live_debounce_ms, Some(500));
        let zero = field(&st, TextInputOptions::new("Zero").key("zero").live_duration("0"));
        assert_eq!(zero.live_debounce_ms, Some(0));
        assert!(st.text_input(TextInputOptions::new("Bad live").key("bad_live").live_duration("300")).is_err(), "a nonzero bare number is not a documented duration");
        assert!(st.text_input(TextInputOptions::new("Too slow").key("too_slow").live_debounce_ms(60_001)).is_err());
        assert!(st.text_input(TextInputOptions::new("Bound").key("bound").bind(TextBind::QueryParams).input_type(TextInputType::Password)).is_err());
    }

    #[test]
    fn form_flags_and_multiple_or_disabled_submits_match_reference() {
        let state = SessionState::default();
        state.begin_widgets(vec![]);
        let (st, mut wire) = app(&state);
        st.form(FormOptions::new("clear_true_form").clear_on_submit(true), |form| {
            form.text_input(TextInputOptions::new("Note").key("note"))?;
            form.form_submit_button(FormSubmitButtonOptions::new("Apply").key("clear_apply"))
        })
        .unwrap();
        let block = form_block(&mut wire);
        let Some(proto::block::Type::Form(form)) = block.r#type else { panic!() };
        assert!(form.clear_on_submit && form.border && form.enter_to_submit);
        let _ = input(&mut wire);
        let _ = input(&mut wire);

        st.form(FormOptions::new("enter_off_form").enter_to_submit(false), |form| {
            form.text_input(TextInputOptions::new("Note").key("enter_note"))?;
            form.form_submit_button(FormSubmitButtonOptions::new("Apply").key("enter_apply"))
        })
        .unwrap();
        let block = form_block(&mut wire);
        let Some(proto::block::Type::Form(form)) = block.r#type else { panic!() };
        assert!(!form.clear_on_submit && form.border && !form.enter_to_submit);
        let _ = input(&mut wire);
        let _ = input(&mut wire);

        st.form(FormOptions::new("first_disabled_form"), |form| {
            form.text_input(TextInputOptions::new("Note").key("disabled_note"))?;
            form.form_submit_button(FormSubmitButtonOptions::new("Disabled").key("disabled").disabled(true))?;
            form.form_submit_button(FormSubmitButtonOptions::new("Apply").key("apply"))
        })
        .unwrap();
        let _ = form_block(&mut wire);
        let _ = input(&mut wire);
        let element::Type::Button(disabled) = input(&mut wire) else { panic!() };
        assert!(disabled.disabled && disabled.is_form_submitter);
        let element::Type::Button(enabled) = input(&mut wire) else { panic!() };
        assert!(!enabled.disabled && enabled.is_form_submitter);
    }

    #[test]
    fn form_constraints_reject_before_appending_nested_or_callback_elements() {
        let state = SessionState::default();
        state.begin_widgets(vec![]);
        let (st, mut wire) = app(&state);
        assert!(
            st.form(FormOptions::new("duplicate_form"), |form| {
                form.text_input(TextInputOptions::new("First").key("first"))?;
                form.form_submit_button(FormSubmitButtonOptions::new("First apply").key("first_apply"))
            })
            .is_ok()
        );
        assert!(matches!(
            st.form(FormOptions::new("duplicate_form"), |form| {
                form.text_input(TextInputOptions::new("Second").key("second"))?;
                form.form_submit_button(FormSubmitButtonOptions::new("Second apply").key("second_apply"))
            }),
            Err(WidgetError::DuplicateKey(_))
        ));
        assert!(matches!(
            st.form(FormOptions::new("outer_form"), |form| {
                InputWidgets::try_button(form, ButtonOptions::new("Ordinary"))
            }),
            Err(WidgetError::InvalidValue(message)) if message.contains("st.button")
        ));
        assert!(matches!(
            st.form(FormOptions::new("callback_form"), |form| {
                form.text_input(TextInputOptions::new("Bad callback").key("bad_callback").on_change(|_| {}))
            }),
            Err(WidgetError::InvalidValue(message)) if message.contains("only form_submit_button")
        ));
        assert!(matches!(
            st.form(FormOptions::new("nested_form"), |form| {
                form.form(FormOptions::new("inner_form"), |inner| inner.form_submit_button("Inner apply"))
            }),
            Err(WidgetError::InvalidValue(message)) if message.contains("nested")
        ));
        for _ in 0..3 {
            assert!(wire.try_recv().is_ok(), "the first valid form is still rendered");
        }
        assert!(wire.try_recv().is_err(), "failed form calls must not append their partial children");
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

    #[test]
    fn uploader_matches_csv_reference_and_resolves_native_files_before_callback() {
        use std::io::Read;
        let state = SessionState::default();
        state.begin_widgets(vec![]);
        let (st, mut wire) = app(&state);
        let options = || {
            FileUploaderOptions::new("Upload sales CSV").accepted_types(["csv"]).key("upload").on_change(|st| {
                let files = st.session_state().uploaded_files("upload").unwrap();
                assert_eq!(files.len(), 1);
                assert_eq!(files[0].name(), "sales_basic.csv");
                st.session_state().set("upload_callback", files[0].size()).unwrap();
            })
        };
        assert!(matches!(st.file_uploader(options()).unwrap(), UploadedFiles::Single(None)));
        let element::Type::FileUploader(uploader) = input(&mut wire) else { panic!() };
        let reference: Value = serde_json::from_str(include_str!("../../tests/reference/reference-browser/data-loop/upload/trace-data-loop.json")).unwrap();
        let observed = reference["frames"].as_array().unwrap().iter().find_map(|frame| frame.pointer("/decoded/delta/element_full/fileUploader")).unwrap();
        assert_eq!(uploader.label, observed["label"]);
        assert_eq!(uploader.r#type, vec![observed["type"][0].as_str().unwrap().to_owned()]);
        assert_eq!(uploader.max_upload_size_mb, observed["maxUploadSizeMb"].as_i64().unwrap() as i32);
        assert!(!uploader.multiple_files && !uploader.disabled && !uploader.accept_directory);
        assert_eq!(uploader.label_visibility, Some(proto::LabelVisibility { value: 0 }));
        assert!(uploader.id.ends_with("-upload"));
        assert!(state.set("upload", Vec::<String>::new()).is_err(), "uploader keys are read-only");
        state.finish_widgets();
        let bytes = include_bytes!("../../tests/fixtures/csv/sales_basic.csv");
        state.uploads.lock().insert("file".into(), "sales_basic.csv".into(), Some("text/csv".into()), bytes.to_vec());
        let callbacks = state.begin_widgets(vec![WidgetState {
            id: uploader.id.clone(),
            value: Some(widget_state::Value::FileUploaderStateValue(proto::FileUploaderState {
                uploaded_file_info: vec![proto::UploadedFileInfo {
                    file_id: "file".into(),
                    name: "client metadata is not authoritative".into(),
                    size: 1,
                    file_urls: None,
                }],
            })),
        }]);
        let (st, _) = app(&state);
        assert_eq!(callbacks.len(), 1);
        for callback in callbacks {
            callback(&st);
        }
        assert_eq!(state.get::<u64>("upload_callback").unwrap(), Some(bytes.len() as u64));
        let UploadedFiles::Single(Some(mut file)) = st.file_uploader(options()).unwrap() else { panic!() };
        assert_eq!(file.content_type(), Some("text/csv"));
        let mut received = Vec::new();
        file.read_to_end(&mut received).unwrap();
        assert_eq!(received, bytes);
        state.finish_widgets();
        state.begin_widgets(vec![]);
        let (st, _) = app(&state);
        assert_eq!(st.file_uploader(options()).unwrap().as_slice()[0].position(), 0);
        let other = SessionState::default();
        let (st, _) = app(&other);
        assert!(st.file_uploader(options()).unwrap().as_slice().is_empty());
    }

    #[test]
    fn uploader_mode_constraints_and_foreign_file_ids_remain_isolated() {
        let state = SessionState::default();
        let (st, mut wire) = app(&state);
        let options = || FileUploaderOptions::new("Folder").mode(FileUploadMode::Directory).key("folder");
        assert!(matches!(st.file_uploader(options()).unwrap(), UploadedFiles::Multiple(files) if files.is_empty()));
        let element::Type::FileUploader(uploader) = input(&mut wire) else { panic!() };
        assert!(uploader.multiple_files && uploader.accept_directory);
        state.finish_widgets();
        state.begin_widgets(vec![WidgetState {
            id: uploader.id,
            value: Some(widget_state::Value::FileUploaderStateValue(proto::FileUploaderState {
                uploaded_file_info: vec![proto::UploadedFileInfo {
                    file_id: "other-session-only".into(),
                    ..Default::default()
                }],
            })),
        }]);
        let (st, _) = app(&state);
        assert!(st.file_uploader(options()).unwrap().as_slice().is_empty());
        assert!(st.file_uploader(FileUploaderOptions::new("Bad").max_upload_size_mb(0)).is_err());
        // Directory flags are docs/native coverage; no directory browser PASS.
    }
}
