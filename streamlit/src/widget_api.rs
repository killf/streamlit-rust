//! Typed native inputs. These methods work on Streamlit and its containers.
use crate::UploadedFiles;
use crate::api::{AppendChild, ButtonOptions};
use crate::elements::form::Form;
use crate::elements::{button::ButtonElement, input::InputElement};
use crate::proto::{self, element};
use crate::widgets::{Codec, WidgetSpec};
use crate::{Streamlit, UploadedFile, WidgetCallback, WidgetError};
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
    /// Accept several files at once; returns `UploadedFiles::Multiple`.
    /// Mirrors `st.file_uploader(accept_multiple_files=True)`.
    pub fn multiple_files(mut self) -> Self {
        self.mode = FileUploadMode::Multiple;
        self
    }
    /// Pick a whole directory; also returns `UploadedFiles::Multiple`.
    pub fn directory(mut self) -> Self {
        self.mode = FileUploadMode::Directory;
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

/// Options for `st.chat_input`: the placeholder (the bare form) plus the
/// measured server-configured defaults.
pub struct ChatInputOptions {
    placeholder: String,
    key: Option<String>,
}

impl ChatInputOptions {
    pub fn new(placeholder: impl Into<String>) -> Self {
        Self { placeholder: placeholder.into(), key: None }
    }

    pub fn key(mut self, key: impl Into<String>) -> Self {
        self.key = Some(key.into());
        self
    }
}

impl From<&str> for ChatInputOptions {
    fn from(placeholder: &str) -> Self {
        Self::new(placeholder)
    }
}

impl From<String> for ChatInputOptions {
    fn from(placeholder: String) -> Self {
        Self::new(placeholder)
    }
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
    filter_mode: Option<SelectFilterMode>,
    bind: TextBind,
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
            filter_mode: None,
            bind: TextBind::None,
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
    /// The option-filter behavior of the dropdown (`filterMode` on the wire).
    /// The measured default is fuzzy; `None` disables filtering and cannot
    /// combine with creation mode.
    pub fn filter_mode(mut self, mode: Option<SelectFilterMode>) -> Self {
        self.filter_mode = mode;
        self
    }
    /// Bind the selection to the URL under this run's query parameters,
    /// carrying `queryParamKey` on the wire (requires `key`).
    pub fn bind(mut self, bind: TextBind) -> Self {
        self.bind = bind;
        self
    }
    common_builders!();
}

/// The select-like filter behaviors of the measured wire.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum SelectFilterMode {
    Fuzzy,
    Contains,
    Prefix,
}

impl SelectFilterMode {
    pub(crate) fn wire(self) -> i32 {
        match self {
            Self::Fuzzy => crate::proto::streamlit::SelectWidgetFilterMode::FilterModeFuzzy as i32,
            Self::Contains => crate::proto::streamlit::SelectWidgetFilterMode::FilterModeContains as i32,
            Self::Prefix => crate::proto::streamlit::SelectWidgetFilterMode::FilterModePrefix as i32,
        }
    }
}

/// Creation-mode selectbox options (`accept_new_options`): any typed value is
/// accepted and returned as its string, like the reference's str overload.
pub struct SelectboxCreationOptions {
    common: InputOptions,
    options: Vec<String>,
    index: Option<usize>,
    placeholder: Option<String>,
    filter_mode: Option<SelectFilterMode>,
    bind: TextBind,
}

impl SelectboxCreationOptions {
    pub fn new(label: impl Into<String>, options: impl IntoIterator<Item = impl Into<String>>) -> Self {
        let options: Vec<String> = options.into_iter().map(Into::into).collect();
        Self {
            common: InputOptions::new(label),
            index: (!options.is_empty()).then_some(0),
            filter_mode: Some(SelectFilterMode::Fuzzy),
            options,
            placeholder: None,
            bind: TextBind::None,
        }
    }

    pub fn index(mut self, index: Option<usize>) -> Self {
        self.index = index;
        self
    }

    pub fn placeholder(mut self, placeholder: impl Into<String>) -> Self {
        self.placeholder = Some(placeholder.into());
        self
    }

    pub fn filter_mode(mut self, mode: SelectFilterMode) -> Self {
        self.filter_mode = Some(mode);
        self
    }

    pub fn bind(mut self, bind: TextBind) -> Self {
        self.bind = bind;
        self
    }

    common_builders!();
}

impl From<SelectboxCreationOptions> for SelectboxOptions<String> {
    fn from(options: SelectboxCreationOptions) -> Self {
        SelectboxOptions {
            common: options.common,
            labels: options.options.clone(),
            options: options.options,
            index: options.index,
            placeholder: options.placeholder,
            filter_mode: options.filter_mode,
            bind: options.bind,
        }
    }
}

/// Radio options. The plain `(label, options)` call selects the first option,
/// matching the measured reference; `.index(None)` starts unselected.
pub struct RadioOptions {
    common: InputOptions,
    options: Vec<String>,
    index: Option<usize>,
    horizontal: bool,
    captions: Vec<String>,
}
impl RadioOptions {
    pub fn new(label: impl Into<String>, options: impl IntoIterator<Item = impl ToString>) -> Self {
        Self {
            common: InputOptions::new(label),
            options: options.into_iter().map(|option| option.to_string()).collect(),
            index: Some(0),
            horizontal: false,
            captions: Vec::new(),
        }
    }
    pub fn index(mut self, index: Option<usize>) -> Self {
        self.index = index;
        self
    }
    /// Lay the options out horizontally (Python `horizontal=True`).
    pub fn horizontal(mut self, value: bool) -> Self {
        self.horizontal = value;
        self
    }
    /// Per-option caption lines shown under the options.
    pub fn captions(mut self, captions: impl IntoIterator<Item = impl Into<String>>) -> Self {
        self.captions = captions.into_iter().map(Into::into).collect();
        self
    }
    common_builders!();
}
impl<L: Into<String>, I: IntoIterator<Item = T>, T: ToString> From<(L, I)> for RadioOptions {
    fn from((label, options): (L, I)) -> Self {
        Self::new(label, options)
    }
}

/// Multiselect options. Selections return in selection order; the plain call
/// starts empty, matching the reference's empty default.
pub struct MultiselectOptions<T> {
    common: InputOptions,
    options: Vec<T>,
    labels: Vec<String>,
    default: Vec<usize>,
    max_selections: Option<usize>,
}
impl<T: ToString> MultiselectOptions<T> {
    pub fn new(label: impl Into<String>, options: impl IntoIterator<Item = T>) -> Self {
        let options: Vec<T> = options.into_iter().collect();
        let labels = options.iter().map(ToString::to_string).collect();
        Self {
            common: InputOptions::new(label),
            options,
            labels,
            default: Vec::new(),
            max_selections: None,
        }
    }
    /// Cap the selectable count (Python `max_selections=`).
    pub fn max_selections(mut self, count: usize) -> Self {
        self.max_selections = Some(count);
        self
    }
}
impl<L, I, T> From<(L, I)> for MultiselectOptions<T>
where
    L: Into<String>,
    I: IntoIterator<Item = T>,
    T: ToString,
{
    fn from((label, options): (L, I)) -> Self {
        Self::new(label, options)
    }
}
impl<T> MultiselectOptions<T> {
    /// Select defaults by option position, like the reference's index list.
    pub fn default_indices(mut self, indices: impl IntoIterator<Item = usize>) -> Self {
        self.default = indices.into_iter().collect();
        self
    }
    /// Formatting changes labels, never the returned original option values.
    pub fn format_func(mut self, format: impl Fn(&T) -> String) -> Self {
        self.labels = self.options.iter().map(format).collect();
        self
    }
    common_builders!();
}

/// Toggle options. The plain `(label, value)` call starts unchecked, like the
/// reference's `value=False` default.
pub struct ToggleOptions {
    common: InputOptions,
    value: bool,
}
impl ToggleOptions {
    pub fn new(label: impl Into<String>) -> Self {
        Self { common: InputOptions::new(label), value: false }
    }
    pub fn value(mut self, value: bool) -> Self {
        self.value = value;
        self
    }
    common_builders!();
}
impl From<&str> for ToggleOptions {
    fn from(label: &str) -> Self {
        Self::new(label)
    }
}
impl From<String> for ToggleOptions {
    fn from(label: String) -> Self {
        Self::new(label)
    }
}
impl<L: Into<String>> From<(L, bool)> for ToggleOptions {
    fn from((label, value): (L, bool)) -> Self {
        Self::new(label).value(value)
    }
}

/// The feedback styles and their icon counts, as the reference renders them.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum FeedbackKind {
    Thumbs,
    Faces,
    Stars,
}
impl FeedbackKind {
    fn count(self) -> usize {
        match self {
            Self::Thumbs => 2,
            Self::Faces | Self::Stars => 5,
        }
    }
    fn wire(self) -> proto::feedback::FeedbackType {
        match self {
            Self::Thumbs => proto::feedback::FeedbackType::Thumbs,
            Self::Faces => proto::feedback::FeedbackType::Faces,
            Self::Stars => proto::feedback::FeedbackType::Stars,
        }
    }
}

/// Feedback options. The plain call is thumbs, unselected; the value is the
/// picked icon's index (0 = most negative) or None once cleared. Feedback
/// has no label or help, like the reference.
pub struct FeedbackOptions {
    common: InputOptions,
    kind: FeedbackKind,
    default: Option<u32>,
}
impl FeedbackOptions {
    pub fn new(kind: FeedbackKind) -> Self {
        Self {
            common: InputOptions::new(String::new()),
            kind,
            default: None,
        }
    }
    pub fn default(mut self, default: u32) -> Self {
        self.default = Some(default);
        self
    }
    pub fn key(mut self, key: impl Into<String>) -> Self {
        self.common.key = Some(key.into());
        self
    }
    pub fn disabled(mut self, disabled: bool) -> Self {
        self.common.disabled = disabled;
        self
    }
    pub fn width(mut self, pixels: i32) -> Self {
        self.common.width = Some(pixels);
        self
    }
    pub fn on_change(mut self, callback: impl Fn(&Streamlit) + Send + Sync + 'static) -> Self {
        self.common.callback = Some(Arc::new(callback));
        self.common.ignore_rerun = false;
        self
    }
    pub fn ignore_rerun(mut self, ignore: bool) -> Self {
        self.common.ignore_rerun = ignore;
        if ignore {
            self.common.callback = None;
        }
        self
    }
}
impl Default for FeedbackOptions {
    fn default() -> Self {
        Self::new(FeedbackKind::Thumbs)
    }
}
impl From<FeedbackKind> for FeedbackOptions {
    fn from(kind: FeedbackKind) -> Self {
        Self::new(kind)
    }
}

/// How a pills or segmented-control group picks: one option at most, or any
/// number in selection order.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum SelectionMode {
    Single,
    Multi,
}

/// Shared options of pills and segmented control: option labels, either
/// selection mode, and the initially selected labels. A leading material or
/// emoji icon on a label travels as its own wire field, like the reference's
/// transformed format function.
pub struct ButtonGroupOptions {
    common: InputOptions,
    options: Vec<String>,
    mode: SelectionMode,
    default: Vec<String>,
    required: bool,
}
impl ButtonGroupOptions {
    pub fn new(label: impl Into<String>, options: impl IntoIterator<Item = impl ToString>) -> Self {
        Self {
            common: InputOptions::new(label),
            options: options.into_iter().map(|option| option.to_string()).collect(),
            mode: SelectionMode::Single,
            default: Vec::new(),
            required: false,
        }
    }
    pub fn selection_mode(mut self, mode: SelectionMode) -> Self {
        self.mode = mode;
        self
    }
    /// The initially selected labels; one entry at most in single mode.
    pub fn default(mut self, default: impl IntoIterator<Item = impl ToString>) -> Self {
        self.default = default.into_iter().map(|option| option.to_string()).collect();
        self
    }
    /// Keep one option always selected in single mode once a pick exists.
    pub fn required(mut self, required: bool) -> Self {
        self.required = required;
        self
    }
    common_builders!();
}
impl<L: Into<String>, I: IntoIterator<Item = T>, T: ToString> From<(L, I)> for ButtonGroupOptions {
    fn from((label, options): (L, I)) -> Self {
        Self::new(label, options)
    }
}

/// Pagination options. Pages are 1-indexed and one page is always selected.
pub struct PaginationOptions {
    common: InputOptions,
    num_pages: u32,
    default: u32,
    max_visible_pages: Option<u32>,
}
impl PaginationOptions {
    pub fn new(num_pages: u32) -> Self {
        Self {
            common: InputOptions::new(String::new()),
            num_pages,
            default: 1,
            max_visible_pages: Some(7),
        }
    }
    pub fn default(mut self, default: u32) -> Self {
        self.default = default;
        self
    }
    /// The target page-button count; None lifts the explicit cap.
    pub fn max_visible_pages(mut self, max_visible_pages: Option<u32>) -> Self {
        self.max_visible_pages = max_visible_pages;
        self
    }
    pub fn key(mut self, key: impl Into<String>) -> Self {
        self.common.key = Some(key.into());
        self
    }
    pub fn disabled(mut self, disabled: bool) -> Self {
        self.common.disabled = disabled;
        self
    }
    pub fn width(mut self, pixels: i32) -> Self {
        self.common.width = Some(pixels);
        self
    }
    pub fn on_change(mut self, callback: impl Fn(&Streamlit) + Send + Sync + 'static) -> Self {
        self.common.callback = Some(Arc::new(callback));
        self.common.ignore_rerun = false;
        self
    }
    pub fn ignore_rerun(mut self, ignore: bool) -> Self {
        self.common.ignore_rerun = ignore;
        if ignore {
            self.common.callback = None;
        }
        self
    }
}
impl From<u32> for PaginationOptions {
    fn from(num_pages: u32) -> Self {
        Self::new(num_pages)
    }
}

/// Menu button options. The trigger returns the picked option's label for
/// one run, then None, like the reference.
pub struct MenuButtonOptions {
    common: InputOptions,
    options: Vec<String>,
    r#type: String,
    icon: Option<String>,
}
impl MenuButtonOptions {
    pub fn new(label: impl Into<String>, options: impl IntoIterator<Item = impl ToString>) -> Self {
        Self {
            common: InputOptions::new(label),
            options: options.into_iter().map(|option| option.to_string()).collect(),
            r#type: "secondary".to_string(),
            icon: None,
        }
    }
    pub fn primary(mut self) -> Self {
        self.r#type = "primary".into();
        self
    }
    pub fn tertiary(mut self) -> Self {
        self.r#type = "tertiary".into();
        self
    }
    pub fn icon(mut self, icon: impl Into<String>) -> Self {
        self.icon = Some(icon.into());
        self
    }
    common_builders!();
}
impl<L: Into<String>, I: IntoIterator<Item = T>, T: ToString> From<(L, I)> for MenuButtonOptions {
    fn from((label, options): (L, I)) -> Self {
        Self::new(label, options)
    }
}

/// Link button options. The plain call is a pure link (the reference's
/// `on_click="ignore"` default: no rerun); `.on_click(...)` turns it into a
/// trigger widget that reports the click for one run.
pub struct LinkButtonOptions {
    common: InputOptions,
    url: String,
    r#type: String,
    icon: Option<String>,
    rerun: bool,
}
impl LinkButtonOptions {
    pub fn new(label: impl Into<String>, url: impl Into<String>) -> Self {
        Self {
            common: InputOptions::new(label),
            url: url.into(),
            r#type: "secondary".to_string(),
            icon: None,
            rerun: false,
        }
    }
    pub fn primary(mut self) -> Self {
        self.r#type = "primary".into();
        self
    }
    pub fn tertiary(mut self) -> Self {
        self.r#type = "tertiary".into();
        self
    }
    pub fn icon(mut self, icon: impl Into<String>) -> Self {
        self.icon = Some(icon.into());
        self
    }
    /// Report clicks as one-shot trigger values instead of pure navigation.
    pub fn on_click(mut self) -> Self {
        self.rerun = true;
        self.common.ignore_rerun = false;
        self
    }
    common_builders!();
}
impl<L: Into<String>, U: Into<String>> From<(L, U)> for LinkButtonOptions {
    fn from((label, url): (L, U)) -> Self {
        Self::new(label, url)
    }
}

/// Download button options. `data` is served from the media store and the
/// trigger reports the click for one run.
pub struct DownloadButtonOptions {
    common: InputOptions,
    data: Vec<u8>,
    file_name: Option<String>,
    mime: Option<String>,
    r#type: String,
    icon: Option<String>,
}
impl DownloadButtonOptions {
    pub fn new(label: impl Into<String>, data: impl Into<Vec<u8>>) -> Self {
        Self {
            common: InputOptions::new(label),
            data: data.into(),
            file_name: None,
            mime: None,
            r#type: "secondary".to_string(),
            icon: None,
        }
    }
    pub fn file_name(mut self, file_name: impl Into<String>) -> Self {
        self.file_name = Some(file_name.into());
        self
    }
    pub fn mime(mut self, mime: impl Into<String>) -> Self {
        self.mime = Some(mime.into());
        self
    }
    pub fn primary(mut self) -> Self {
        self.r#type = "primary".into();
        self
    }
    pub fn tertiary(mut self) -> Self {
        self.r#type = "tertiary".into();
        self
    }
    pub fn icon(mut self, icon: impl Into<String>) -> Self {
        self.icon = Some(icon.into());
        self
    }
    common_builders!();
}
impl<L: Into<String>, D: Into<Vec<u8>>> From<(L, D)> for DownloadButtonOptions {
    fn from((label, data): (L, D)) -> Self {
        Self::new(label, data)
    }
}

/// What a date input returns: one date, or the two endpoints of a range.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum DateSelection {
    Single(chrono::NaiveDate),
    Range(chrono::NaiveDate, chrono::NaiveDate),
}

/// Date input options. The plain call starts at today (the reference's
/// value=None default); `value_range` switches to the two-endpoint range.
pub struct DateInputOptions {
    common: InputOptions,
    single: Option<chrono::NaiveDate>,
    range: Option<(chrono::NaiveDate, chrono::NaiveDate)>,
    min: Option<chrono::NaiveDate>,
    max: Option<chrono::NaiveDate>,
    format: String,
}
impl DateInputOptions {
    pub fn new(label: impl Into<String>) -> Self {
        Self {
            common: InputOptions::new(label),
            single: Some(chrono::Local::now().date_naive()),
            range: None,
            min: None,
            max: None,
            format: "YYYY/MM/DD".to_string(),
        }
    }
    pub fn value(mut self, value: chrono::NaiveDate) -> Self {
        self.single = Some(value);
        self
    }
    /// The two endpoints of a range picker, in order.
    pub fn value_range(mut self, start: chrono::NaiveDate, end: chrono::NaiveDate) -> Self {
        self.range = Some((start, end));
        self
    }
    pub fn min(mut self, min: chrono::NaiveDate) -> Self {
        self.min = Some(min);
        self
    }
    pub fn max(mut self, max: chrono::NaiveDate) -> Self {
        self.max = Some(max);
        self
    }
    /// The frontend's display format (the reference's default is
    /// "YYYY/MM/DD"); the wire always carries ISO dates.
    pub fn format(mut self, format: impl Into<String>) -> Self {
        self.format = format.into();
        self
    }
    common_builders!();
}
impl From<&str> for DateInputOptions {
    fn from(label: &str) -> Self {
        Self::new(label)
    }
}
impl From<String> for DateInputOptions {
    fn from(label: String) -> Self {
        Self::new(label)
    }
}

/// Time input options. The plain call starts at now; the step decides the
/// wire precision (whole minutes carry "HH:MM", finer steps "HH:MM:SS").
pub struct TimeInputOptions {
    common: InputOptions,
    value: Option<chrono::NaiveTime>,
    step: i64,
    format: &'static str,
}
impl TimeInputOptions {
    pub fn new(label: impl Into<String>) -> Self {
        Self {
            common: InputOptions::new(label),
            value: Some(chrono::Local::now().time()),
            step: 900,
            format: "24h",
        }
    }
    pub fn value(mut self, value: chrono::NaiveTime) -> Self {
        self.value = Some(value);
        self
    }
    /// An unset picker: starts empty and may be cleared back to None.
    pub fn value_none(mut self) -> Self {
        self.value = None;
        self
    }
    /// The picker's minute granularity, in seconds (900 = 15 minutes).
    pub fn step(mut self, step: i64) -> Self {
        self.step = step;
        self
    }
    /// The clock presentation: "24h" (default), "12h" or "localized".
    pub fn format(mut self, format: &'static str) -> Self {
        self.format = format;
        self
    }
    common_builders!();
}
impl From<&str> for TimeInputOptions {
    fn from(label: &str) -> Self {
        Self::new(label)
    }
}
impl From<String> for TimeInputOptions {
    fn from(label: String) -> Self {
        Self::new(label)
    }
}

/// Datetime input options. The plain call starts at now (minute precision);
/// the default bounds are the ten-year window around the value's date.
pub struct DateTimeInputOptions {
    common: InputOptions,
    value: Option<chrono::NaiveDateTime>,
    min: Option<chrono::NaiveDateTime>,
    max: Option<chrono::NaiveDateTime>,
    step: i64,
    format: String,
}
impl DateTimeInputOptions {
    pub fn new(label: impl Into<String>) -> Self {
        use chrono::Timelike;
        Self {
            common: InputOptions::new(label),
            value: chrono::Local::now().naive_local().with_second(0).and_then(|moment| moment.with_nanosecond(0)),
            min: None,
            max: None,
            step: 900,
            format: "YYYY/MM/DD".to_string(),
        }
    }
    pub fn value(mut self, value: chrono::NaiveDateTime) -> Self {
        use chrono::Timelike;
        self.value = Some(value.with_second(0).and_then(|moment| moment.with_nanosecond(0)).unwrap_or(value));
        self
    }
    /// An unset picker: starts empty and may be cleared back to None.
    pub fn value_none(mut self) -> Self {
        self.value = None;
        self
    }
    pub fn min(mut self, min: chrono::NaiveDateTime) -> Self {
        self.min = Some(min);
        self
    }
    pub fn max(mut self, max: chrono::NaiveDateTime) -> Self {
        self.max = Some(max);
        self
    }
    /// The picker's minute granularity, in seconds (900 = 15 minutes;
    /// the reference bounds it to [60, 82800]).
    pub fn step(mut self, step: i64) -> Self {
        self.step = step;
        self
    }
    /// The frontend's date display format (the reference's default is
    /// "YYYY/MM/DD"); the wire always carries ISO datetimes.
    pub fn format(mut self, format: impl Into<String>) -> Self {
        self.format = format.into();
        self
    }
    common_builders!();
}
impl From<&str> for DateTimeInputOptions {
    fn from(label: &str) -> Self {
        Self::new(label)
    }
}
impl From<String> for DateTimeInputOptions {
    fn from(label: String) -> Self {
        Self::new(label)
    }
}

/// Color picker options. The plain call starts at black; values are
/// "#RRGGBB" strings like the reference.
pub struct ColorPickerOptions {
    common: InputOptions,
    value: String,
}
impl ColorPickerOptions {
    pub fn new(label: impl Into<String>) -> Self {
        Self {
            common: InputOptions::new(label),
            value: "#000000".to_string(),
        }
    }
    pub fn value(mut self, value: impl Into<String>) -> Self {
        self.value = value.into();
        self
    }
    common_builders!();
}
impl From<&str> for ColorPickerOptions {
    fn from(label: &str) -> Self {
        Self::new(label)
    }
}
impl From<String> for ColorPickerOptions {
    fn from(label: String) -> Self {
        Self::new(label)
    }
}

/// What a select slider returns: one option, or both ends of a range.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum SelectSliderValue {
    Single(String),
    Range(String, String),
}

/// Select slider options: option labels with one selected label, or two
/// for a range. The wire is a slider of label indices.
pub struct SelectSliderOptions {
    common: InputOptions,
    options: Vec<String>,
    default: Vec<String>,
}
impl SelectSliderOptions {
    pub fn new(label: impl Into<String>, options: impl IntoIterator<Item = impl ToString>) -> Self {
        Self {
            common: InputOptions::new(label),
            options: options.into_iter().map(|option| option.to_string()).collect(),
            default: Vec::new(),
        }
    }
    /// The selected label(s); two labels make a range picker.
    pub fn default(mut self, default: impl IntoIterator<Item = impl ToString>) -> Self {
        self.default = default.into_iter().map(|option| option.to_string()).collect();
        self
    }
    common_builders!();
}
impl<L: Into<String>, I: IntoIterator<Item = T>, T: ToString> From<(L, I)> for SelectSliderOptions {
    fn from((label, options): (L, I)) -> Self {
        Self::new(label, options)
    }
}

/// Audio input options: a single-file recorder widget.
pub struct AudioInputOptions {
    common: InputOptions,
    sample_rate: Option<i32>,
}
impl AudioInputOptions {
    pub fn new(label: impl Into<String>) -> Self {
        Self {
            common: InputOptions::new(label),
            sample_rate: Some(16000),
        }
    }
    pub fn sample_rate(mut self, sample_rate: i32) -> Self {
        self.sample_rate = Some(sample_rate);
        self
    }
    /// Omit the declared rate from the wire.
    pub fn no_sample_rate(mut self) -> Self {
        self.sample_rate = None;
        self
    }
    common_builders!();
}
impl From<&str> for AudioInputOptions {
    fn from(label: &str) -> Self {
        Self::new(label)
    }
}
impl From<String> for AudioInputOptions {
    fn from(label: String) -> Self {
        Self::new(label)
    }
}

/// Camera input options: a single-file photo widget.
pub struct CameraInputOptions {
    common: InputOptions,
}
impl CameraInputOptions {
    pub fn new(label: impl Into<String>) -> Self {
        Self { common: InputOptions::new(label) }
    }
    common_builders!();
}
impl From<&str> for CameraInputOptions {
    fn from(label: &str) -> Self {
        Self::new(label)
    }
}
impl From<String> for CameraInputOptions {
    fn from(label: String) -> Self {
        Self::new(label)
    }
}

/// The number types a number input returns; the wire's integer/float split
/// follows the value's type, as measured on the reference.
pub trait NumberValue: Copy + Serialize + DeserializeOwned + PartialOrd + 'static {
    const INTEGER: bool;
    fn to_f64(self) -> f64;
    // Session state mirrors the declared type: integer inputs store integer
    // JSON so the default round-trips through from_value.
    fn to_value(self) -> Value;
    fn from_value(value: &Value) -> Option<Self>;
}
impl NumberValue for i64 {
    const INTEGER: bool = true;
    fn to_f64(self) -> f64 {
        self as f64
    }
    fn to_value(self) -> Value {
        Value::from(self)
    }
    fn from_value(value: &Value) -> Option<Self> {
        value.as_i64()
    }
}
impl NumberValue for f64 {
    const INTEGER: bool = false;
    fn to_f64(self) -> f64 {
        self
    }
    fn to_value(self) -> Value {
        Value::from(self)
    }
    fn from_value(value: &Value) -> Option<Self> {
        value.as_f64()
    }
}

/// Number input options. The plain `(label, value)` call starts at the value
/// with the reference's default step (1 for integers, 0.01 for floats).
pub struct NumberInputOptions<T: NumberValue> {
    common: InputOptions,
    value: T,
    min: Option<T>,
    max: Option<T>,

    // 保存调用方是否省略步长，生效默认值在渲染时按数值类型解析。
    step: Option<f64>,
}
impl<T: NumberValue> NumberInputOptions<T> {
    pub fn new(label: impl Into<String>, value: T) -> Self {
        Self {
            common: InputOptions::new(label),
            value,
            min: None,
            max: None,
            step: None,
        }
    }
    pub fn min(mut self, min: impl Into<T>) -> Self {
        self.min = Some(min.into());
        self
    }
    pub fn max(mut self, max: impl Into<T>) -> Self {
        self.max = Some(max.into());
        self
    }
    pub fn step(mut self, step: impl Into<f64>) -> Self {
        self.step = Some(step.into());
        self
    }
    common_builders!();
}
impl<L: Into<String>, T: NumberValue> From<(L, T)> for NumberInputOptions<T> {
    fn from((label, value): (L, T)) -> Self {
        Self::new(label, value)
    }
}
impl<L: Into<String>, T: NumberValue> From<(L, T, std::ops::RangeInclusive<T>)> for NumberInputOptions<T> {
    fn from((label, value, bounds): (L, T, std::ops::RangeInclusive<T>)) -> Self {
        let (min, max) = bounds.into_inner();
        Self::new(label, value).min(min).max(max)
    }
}

/// Text area options. The plain `(label, value)` call starts with the value;
/// `.value_none()` starts empty.
pub struct TextAreaOptions {
    common: InputOptions,
    value: Option<String>,
    max_chars: Option<usize>,
    placeholder: Option<String>,
    height: Option<i32>,
}
impl TextAreaOptions {
    pub fn new(label: impl Into<String>, value: impl Into<String>) -> Self {
        Self {
            common: InputOptions::new(label),
            value: Some(value.into()),
            max_chars: None,
            placeholder: None,
            height: None,
        }
    }
    /// The box's pixel height (the element's height config).
    pub fn height(mut self, pixels: i32) -> Self {
        self.height = Some(pixels);
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
    pub fn placeholder(mut self, placeholder: impl Into<String>) -> Self {
        self.placeholder = Some(placeholder.into());
        self
    }
    common_builders!();
}
impl<L: Into<String>, S: Into<String>> From<(L, S)> for TextAreaOptions {
    fn from((label, value): (L, S)) -> Self {
        Self::new(label, value)
    }
}
impl From<&str> for TextAreaOptions {
    fn from(label: &str) -> Self {
        Self::new(label, "")
    }
}

mod sealed {
    use chrono::{NaiveDate, NaiveDateTime, NaiveTime};
    pub trait Scalar {}
    impl Scalar for i64 {}
    impl Scalar for i32 {}
    impl Scalar for f64 {}
    impl Scalar for NaiveDate {}
    impl Scalar for NaiveTime {}
    impl Scalar for NaiveDateTime {}
    pub trait SliderGate {}
    impl SliderGate for i64 {}
    impl SliderGate for i32 {}
    impl SliderGate for f64 {}
    impl SliderGate for NaiveDate {}
    impl SliderGate for NaiveTime {}
    impl SliderGate for NaiveDateTime {}
    impl<T: Scalar> SliderGate for (T, T) {}
    impl<T: Scalar> SliderGate for [T; 2] {}
}

/// Numeric or date/time scalar, or a two-endpoint range of one scalar type.
/// Ranges must contain exactly two scalar endpoints, never nested ranges.
/// ```compile_fail
/// use streamlit::SliderOptions;
/// let _ = SliderOptions::new("Nested", ((1_i64, 2_i64), (3_i64, 4_i64)));
/// ```
pub trait SliderValue: sealed::SliderGate + Serialize + DeserializeOwned + Clone {
    const COUNT: usize;
    /// Identity discriminator plus wire defaults, all measured on the pinned
    /// 1.66.1 reference. See `.codex/compatibility.md` for the observed table.
    fn slider_identity_kind() -> &'static str;
    /// The `Slider.DataType` enum; the builder derives the wire codec from it.
    fn slider_data_type() -> i32;
    fn slider_wire_integral() -> bool;
    /// The window every user-supplied min/max must lie inside.
    fn slider_domain() -> (f64, f64);
    fn slider_default_format() -> String;
    fn slider_default_step() -> f64;
    /// The wire numbers of this value: raw numbers, or epoch microseconds.
    fn slider_numbers(&self) -> Vec<f64>;
    /// The default (min, max) when the caller supplies none.
    fn slider_default_bounds(&self) -> (f64, f64);
}
macro_rules! slider_scalar {
    ($t:ty, $kind:expr, $data_type:expr, $integer:expr, $domain:expr, $format:expr, $step:expr, $max_default:expr) => {
        impl SliderValue for $t {
            const COUNT: usize = 1;
            fn slider_identity_kind() -> &'static str {
                $kind
            }
            fn slider_data_type() -> i32 {
                $data_type
            }
            fn slider_wire_integral() -> bool {
                $integer
            }
            fn slider_domain() -> (f64, f64) {
                $domain
            }
            fn slider_default_format() -> String {
                $format.into()
            }
            fn slider_default_step() -> f64 {
                $step
            }
            fn slider_numbers(&self) -> Vec<f64> {
                vec![*self as f64]
            }
            fn slider_default_bounds(&self) -> (f64, f64) {
                (0.0, $max_default)
            }
        }
    };
}
slider_scalar!(i64, "int", 0, true, (-9_007_199_254_740_991.0, 9_007_199_254_740_991.0), "%d", 1.0, 100.0);
slider_scalar!(i32, "int", 0, true, (i32::MIN as f64, i32::MAX as f64), "%d", 1.0, 100.0);
slider_scalar!(f64, "float", 1, false, (f64::MIN, f64::MAX), "%0.2f", 0.01, 1.0);
macro_rules! slider_temporal {
    ($t:ty, $kind:expr, $wire_kind:expr, $format:expr, $step:expr, $micros:expr, $bounds:expr) => {
        impl SliderValue for $t {
            const COUNT: usize = 1;
            fn slider_identity_kind() -> &'static str {
                $kind
            }
            fn slider_data_type() -> i32 {
                $wire_kind.data_type()
            }
            fn slider_wire_integral() -> bool {
                true
            }
            fn slider_domain() -> (f64, f64) {
                (-crate::widgets::JS_SAFE_INTEGER, crate::widgets::JS_SAFE_INTEGER)
            }
            fn slider_default_format() -> String {
                $format.into()
            }
            fn slider_default_step() -> f64 {
                $step as f64
            }
            fn slider_numbers(&self) -> Vec<f64> {
                vec![$micros(*self) as f64]
            }
            fn slider_default_bounds(&self) -> (f64, f64) {
                $bounds($micros(*self))
            }
        }
    };
}
/// The value plus/minus 14 days: the measured date and datetime default window.
fn plus_minus_14_days(micros: i64) -> (f64, f64) {
    let span = 14 * crate::widgets::DAY_MICROS;
    ((micros - span) as f64, (micros + span) as f64)
}
/// The full 2000-01-01 day, 00:00:00.000000 through 23:59:59.999999: the
/// measured time-of-day default window.
fn full_day_bounds() -> (f64, f64) {
    let anchor = crate::widgets::TIME_ANCHOR_MICROS;
    (anchor as f64, (anchor + crate::widgets::DAY_MICROS - 1) as f64)
}
slider_temporal!(chrono::NaiveDate, "date", crate::widgets::TemporalKind::Date, "YYYY-MM-DD", crate::widgets::DAY_MICROS, crate::widgets::date_micros, plus_minus_14_days);
slider_temporal!(chrono::NaiveTime, "time", crate::widgets::TemporalKind::Time, "HH:mm", 900_000_000, crate::widgets::time_micros, |_| full_day_bounds());
slider_temporal!(
    chrono::NaiveDateTime,
    "datetime",
    crate::widgets::TemporalKind::Datetime,
    "YYYY-MM-DD",
    crate::widgets::DAY_MICROS,
    crate::widgets::datetime_micros,
    plus_minus_14_days
);

impl<T: SliderValue + sealed::Scalar> SliderValue for (T, T) {
    const COUNT: usize = 2;
    fn slider_identity_kind() -> &'static str {
        T::slider_identity_kind()
    }
    fn slider_data_type() -> i32 {
        T::slider_data_type()
    }
    fn slider_wire_integral() -> bool {
        T::slider_wire_integral()
    }
    fn slider_domain() -> (f64, f64) {
        T::slider_domain()
    }
    fn slider_default_format() -> String {
        T::slider_default_format()
    }
    fn slider_default_step() -> f64 {
        T::slider_default_step()
    }
    fn slider_numbers(&self) -> Vec<f64> {
        vec![self.0.slider_numbers()[0], self.1.slider_numbers()[0]]
    }
    fn slider_default_bounds(&self) -> (f64, f64) {
        // Measured on the reference: a range's default window hangs off the
        // FIRST endpoint alone (for a date pair, value0 ± 14 days).
        self.0.slider_default_bounds()
    }
}
impl<T: SliderValue + sealed::Scalar> SliderValue for [T; 2] {
    const COUNT: usize = 2;
    fn slider_identity_kind() -> &'static str {
        T::slider_identity_kind()
    }
    fn slider_data_type() -> i32 {
        T::slider_data_type()
    }
    fn slider_wire_integral() -> bool {
        T::slider_wire_integral()
    }
    fn slider_domain() -> (f64, f64) {
        T::slider_domain()
    }
    fn slider_default_format() -> String {
        T::slider_default_format()
    }
    fn slider_default_step() -> f64 {
        T::slider_default_step()
    }
    fn slider_numbers(&self) -> Vec<f64> {
        vec![self[0].slider_numbers()[0], self[1].slider_numbers()[0]]
    }
    fn slider_default_bounds(&self) -> (f64, f64) {
        self[0].slider_default_bounds()
    }
}

/// A slider bound: a plain number, or a date/time value carried through the
/// measured epoch-microsecond encoding.
pub trait SliderBound: slider_sealed::Sealed {
    fn slider_bound(self) -> f64;
}
mod slider_sealed {
    pub trait Sealed {}
    impl Sealed for i64 {}
    impl Sealed for i32 {}
    impl Sealed for f64 {}
    impl Sealed for chrono::NaiveDate {}
    impl Sealed for chrono::NaiveTime {}
    impl Sealed for chrono::NaiveDateTime {}
    impl Sealed for chrono::TimeDelta {}
}
impl SliderBound for i64 {
    fn slider_bound(self) -> f64 {
        self as f64
    }
}
impl SliderBound for i32 {
    fn slider_bound(self) -> f64 {
        self as f64
    }
}
impl SliderBound for f64 {
    fn slider_bound(self) -> f64 {
        self
    }
}
impl SliderBound for chrono::NaiveDate {
    fn slider_bound(self) -> f64 {
        crate::widgets::date_micros(self) as f64
    }
}
impl SliderBound for chrono::NaiveTime {
    fn slider_bound(self) -> f64 {
        crate::widgets::time_micros(self) as f64
    }
}
impl SliderBound for chrono::NaiveDateTime {
    fn slider_bound(self) -> f64 {
        crate::widgets::datetime_micros(self) as f64
    }
}

/// A slider step: a plain number of wire units (microseconds for date/time
/// sliders), or a chrono duration converted to microseconds.
pub trait SliderStep: slider_sealed::Sealed {
    fn slider_step(self) -> f64;
}
impl SliderStep for i64 {
    fn slider_step(self) -> f64 {
        self as f64
    }
}
impl SliderStep for f64 {
    fn slider_step(self) -> f64 {
        self
    }
}
impl SliderStep for chrono::TimeDelta {
    fn slider_step(self) -> f64 {
        // The temporal wire carries whole microseconds; a delta outside that
        // grid becomes NaN and fails the finite-step validation below.
        self.num_microseconds().map(|micros| micros as f64).unwrap_or(f64::NAN)
    }
}

/// Options for [`InputWidgets::slider`]. Date/time sliders use the measured
/// 1.66.1 wire encoding: integer epoch microseconds carried as doubles, naive
/// date-times as if UTC, time-of-day anchored at 2000-01-01. Defaults when no
/// bounds are given: a date or datetime spans its value ± 14 days with a daily
/// step; a time spans the full day with a 15-minute step; a range hangs its
/// window off the first endpoint. Values stay inside the exactly-representable
/// double range (roughly 1677..2262); microsecond components round-trip.
pub struct SliderOptions<T> {
    common: InputOptions,
    value: T,
    min: Option<f64>,
    max: Option<f64>,
    step: Option<f64>,
    format: Option<String>,
}
impl<T: SliderValue> SliderOptions<T> {
    pub fn new(label: impl Into<String>, value: T) -> Self {
        Self {
            common: InputOptions::new(label),
            value,
            min: None,
            max: None,
            step: None,
            format: None,
        }
    }
    pub fn min(mut self, min: impl SliderBound) -> Self {
        self.min = Some(min.slider_bound());
        self
    }
    pub fn max(mut self, max: impl SliderBound) -> Self {
        self.max = Some(max.slider_bound());
        self
    }
    pub fn step(mut self, step: impl SliderStep) -> Self {
        self.step = Some(step.slider_step());
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
impl<L: Into<String>, T: SliderValue, B: SliderBound> From<(L, T, std::ops::RangeInclusive<B>)> for SliderOptions<T> {
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
        let (id, value, _) = self.register_widget_parity(
            WidgetSpec {
                disabled: options.disabled,
                query: None,
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

    /// The creation-mode selectbox (`accept_new_options`): accepts typed
    /// values outside its options and returns the selected string, like the
    /// reference's str overload.
    fn selectbox_creation(&self, options: impl Into<SelectboxCreationOptions>) -> Result<Option<String>, WidgetError>;
    /// Accept a builder or `(label, options)`. The plain call selects the
    /// first option; `.index(None)` starts unselected.
    fn radio(&self, options: impl Into<RadioOptions>) -> Result<Option<String>, WidgetError>;
    /// Accept a builder or `(label, options)`. The plain call starts empty.
    fn multiselect<T: Clone + Serialize>(&self, options: impl Into<MultiselectOptions<T>>) -> Result<Vec<T>, WidgetError>;
    /// Accept a builder, `(label, value)` or `(label, value, min..=max)`.
    fn number_input<T: NumberValue>(&self, options: impl Into<NumberInputOptions<T>>) -> Result<T, WidgetError>;
    /// Accept a builder or `(label, value)`; `.value_none()` starts empty.
    fn text_area(&self, options: impl Into<TextAreaOptions>) -> Result<Option<String>, WidgetError>;
    /// Accept a builder, `(label, value)`, or `(label, value, min..=max)`.
    /// A tuple/array value denotes the selected range, not the permitted bounds.
    fn slider<T: SliderValue>(&self, options: impl Into<SliderOptions<T>>) -> Result<T, WidgetError>;
    /// Fallible counterpart to the original boolean-returning `button` method.
    fn try_button(&self, options: impl Into<ButtonOptions>) -> Result<bool, WidgetError>;
    /// Accept a builder or `(label, value)`; the plain call starts unchecked.
    fn toggle(&self, options: impl Into<ToggleOptions>) -> Result<bool, WidgetError>;
    /// Accept a builder or a `FeedbackKind`. Returns the picked icon index.
    fn feedback(&self, options: impl Into<FeedbackOptions>) -> Result<Option<u32>, WidgetError>;
    /// pills: accept a builder or `(label, options)`.
    fn pills(&self, options: impl Into<ButtonGroupOptions>) -> Result<ButtonGroupValue, WidgetError>;
    /// segmented_control: accept a builder or `(label, options)`.
    fn segmented_control(&self, options: impl Into<ButtonGroupOptions>) -> Result<ButtonGroupValue, WidgetError>;
    /// Accept a builder or a page count. Returns the 1-indexed page.
    fn pagination(&self, options: impl Into<PaginationOptions>) -> Result<u32, WidgetError>;
    /// Accept a builder or `(label, options)`. The pick lasts one run.
    fn menu_button(&self, options: impl Into<MenuButtonOptions>) -> Result<Option<String>, WidgetError>;
    /// Accept a builder or `(label, url)`. Pure link unless `.on_click()`.
    fn link_button(&self, options: impl Into<LinkButtonOptions>) -> Result<bool, WidgetError>;
    /// Accept a builder or `(label, data)`. Serves `data` from the media store.
    fn download_button(&self, options: impl Into<DownloadButtonOptions>) -> Result<bool, WidgetError>;
    /// Accept a builder or `(label, options)`; the plain call starts at
    /// today, `value_range` makes a range picker. Returns the date(s).
    fn date_input(&self, options: impl Into<DateInputOptions>) -> Result<DateSelection, WidgetError>;
    /// Accept a builder or a label; the plain call starts at now.
    /// Returns None when the picker is clearable and cleared.
    fn time_input(&self, options: impl Into<TimeInputOptions>) -> Result<Option<chrono::NaiveTime>, WidgetError>;
    /// A combined date-and-time picker, like `st.datetime_input`: ISO
    /// "YYYY-MM-DDTHH:MM" values in a ten-year window around the value's
    /// date, with a minute-granularity step.
    fn datetime_input(&self, options: impl Into<DateTimeInputOptions>) -> Result<Option<chrono::NaiveDateTime>, WidgetError>;
    /// Accept a builder or a label; the plain call starts at black.
    fn color_picker(&self, options: impl Into<ColorPickerOptions>) -> Result<String, WidgetError>;
    /// Accept a builder or `(label, options)`; two default labels make a
    /// range picker.
    fn select_slider(&self, options: impl Into<SelectSliderOptions>) -> Result<SelectSliderValue, WidgetError>;
    /// Accept a builder or a label; a single-file recorder widget.
    fn audio_input(&self, options: impl Into<AudioInputOptions>) -> Result<Option<UploadedFile>, WidgetError>;
    /// Accept a builder or a label; a single-file photo widget.
    fn camera_input(&self, options: impl Into<CameraInputOptions>) -> Result<Option<UploadedFile>, WidgetError>;

    /// The chat input (`st.chat_input`): a trigger widget routed to the
    /// bottom container that returns the submitted prompt on the run it
    /// triggered and `None` afterwards. Accepts a builder or the bare
    /// placeholder string.
    fn chat_input(&self, options: impl Into<ChatInputOptions>) -> Result<Option<String>, WidgetError>;
}

/// What a pills or segmented-control group returns: the selected label in
/// single mode, every selected label in selection order in multi mode.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum ButtonGroupValue {
    Single(Option<String>),
    Multi(Vec<String>),
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
        let uploads = self.get_app().lock().session_state.uploads.clone();
        let (id, files, _) = self.register_widget_parity(
            WidgetSpec {
                disabled: c.disabled,
                query: None,
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
        let (id, value, set_value) = self.register_widget_parity(
            WidgetSpec {
                disabled: c.disabled,
                query: None,
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
        let mut c = options.common;
        let form_id = form_scope(self, c.callback.is_some())?;
        if matches!(options.live, TextLive::Debounce(milliseconds) if milliseconds > 60_000) {
            return Err(WidgetError::InvalidValue("text_input live debounce cannot exceed one minute".into()));
        }
        if options.bind == TextBind::QueryParams && c.key.is_none() {
            return Err(WidgetError::InvalidValue("text_input query binding requires a key".into()));
        }
        if options.bind == TextBind::QueryParams && c.key.as_deref().is_some_and(crate::query_params::is_embed_key) {
            return Err(WidgetError::InvalidValue("cannot bind a reserved embedding query parameter".into()));
        }
        if options.bind == TextBind::QueryParams && options.input_type == TextInputType::Password {
            return Err(WidgetError::InvalidValue("text_input query binding cannot use a password input".into()));
        }

        // 显式空状态覆盖本轮默认值；身份仍使用调用方提供的原始选项。
        let mut wire_default = options.value.clone();
        if let Some(key) = c.key.as_deref()
            && self.get_app().lock().session_state.get::<Value>(key)?.is_some_and(|value| value.is_null())
        {
            wire_default = None;
        }

        // 默认值经反序列化截断；wire 保留有效默认值的原始文本。
        let default = wire_default
            .as_ref()
            .map_or(Value::Null, |value| Value::String(options.max_chars.map_or_else(|| value.clone(), |limit| value.chars().take(limit).collect())));

        // 身份只包含调用方显式正则；类型派生规则仍在下方写入 wire。
        let validation_regex = match &options.validation {
            TextValidation::Inherit => None,
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
                    c.width,
                ))?
            },
        );
        let (id, value, set_value) = self.register_widget_parity(
            WidgetSpec {
                disabled: c.disabled,
                query: (options.bind == TextBind::QueryParams).then_some(crate::widgets::QueryBinding { clearable: true }),
                kind: "text_input",
                key: c.key.as_deref(),
                identity: &identity,
                default,
                codec: Codec::Text { max_chars: options.max_chars },
                callback: c.callback.take(),
            },
            |value| Ok(value.as_str().map(str::to_owned)),
        )?;
        let app = self.get_app();
        let state = app.lock().session_state.clone();
        state.set_query_binding(&id, options.bind == TextBind::QueryParams);
        crate::query_params::flush_query_update(&mut app.lock());
        let (validate_regex, validate_message) = match options.validation {
            TextValidation::Inherit => {
                let (regex, message) = options.input_type.default_validation();
                (regex.map(String::from), message.map(String::from))
            }
            TextValidation::Off => (Some(String::new()), None),
            TextValidation::Pattern { regex, message } => (Some(regex), message),
        };

        // 注册和 URL 修正先完成；布局错误不撤销已发送的查询更新。
        if let Some(width) = c.width
            && width <= 0
        {
            return Err(WidgetError::InvalidValue(format!("Invalid width value: {width}. Width must be either a positive integer (pixels) or 'stretch'.")));
        }
        let width_config = c.width(false)?;

        self.push(Rc::new(RefCell::new(InputElement(proto::Element {
            width_config,
            has_one_shot_effect: set_value.then_some(true),
            r#type: Some(element::Type::TextInput(proto::TextInput {
                id,
                label: c.label,
                default: wire_default,
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
        emit_selectbox(self, options.into(), false, &|_| None)
    }

    /// The creation-mode selectbox (`accept_new_options`): the wire carries
    /// `acceptNewOptions` and a freshly typed value keeps its label string,
    /// so the call returns `Option<String>` like the reference's str overload.
    fn selectbox_creation(&self, options: impl Into<SelectboxCreationOptions>) -> Result<Option<String>, WidgetError> {
        let creation: SelectboxOptions<String> = options.into().into();
        emit_selectbox(self, creation, true, &|label| Some(label.to_string()))
    }

    fn radio(&self, options: impl Into<RadioOptions>) -> Result<Option<String>, WidgetError> {
        let options = options.into();
        let c = options.common;
        let form_id = form_scope(self, c.callback.is_some())?;
        let width_config = c.width(false)?;
        if !options.options.is_empty() && options.index.is_some_and(|index| index >= options.options.len()) {
            return Err(WidgetError::InvalidValue("radio index is outside options".into()));
        }
        let default = options.index.map(Value::from).unwrap_or(Value::Null);
        let identity = c.identity_in_form(&form_id, &if c.key.is_some() { String::new() } else { format!("{:?}:{:?}", options.options, options.index) });
        let (id, selected, set_value) = self.register_widget_parity(
            WidgetSpec {
                disabled: c.disabled,
                query: None,
                kind: "radio",
                key: c.key.as_deref(),
                identity: &identity,
                default: default.clone(),
                codec: Codec::Radio(options.options.clone()),
                callback: c.callback,
            },
            |value| {
                if value.is_null() {
                    return Ok(None);
                }
                value
                    .as_u64()
                    .and_then(|index| usize::try_from(index).ok())
                    .filter(|index| *index < options.options.len())
                    .map(|index| Some(options.options[index].clone()))
                    .ok_or_else(|| WidgetError::InvalidValue("invalid radio selection index".into()))
            },
        )?;
        let result = selected.clone();
        self.push(Rc::new(RefCell::new(InputElement(proto::Element {
            width_config,
            has_one_shot_effect: set_value.then_some(true),
            r#type: Some(element::Type::Radio(proto::Radio {
                id,
                label: c.label,
                form_id,
                default: options.index.map(|index| index as i32),
                options: options.options.clone(),
                horizontal: options.horizontal,
                captions: options.captions.clone(),
                help: c.help,
                disabled: c.disabled || options.options.is_empty(),
                label_visibility: c.visibility.wire(),
                ignore_rerun: c.ignore_rerun,
                ..Default::default()
            })),
            ..Default::default()
        }))));
        Ok(result)
    }

    fn multiselect<T: Clone + Serialize>(&self, options: impl Into<MultiselectOptions<T>>) -> Result<Vec<T>, WidgetError> {
        let options = options.into();
        let c = options.common;
        let form_id = form_scope(self, c.callback.is_some())?;
        let width_config = c.width(false)?;
        if options.default.iter().any(|index| *index >= options.options.len()) || options.default.len() > options.options.len() || options.default.iter().collect::<std::collections::HashSet<_>>().len() != options.default.len() {
            return Err(WidgetError::InvalidValue("multiselect defaults must be distinct indices inside options".into()));
        }
        let native: Vec<Value> = options.options.iter().map(serde_json::to_value).collect::<Result<_, _>>()?;
        let default = Value::Array(options.default.iter().map(|index| Value::from(*index)).collect::<Vec<_>>());
        let identity = c.identity_in_form(&form_id, &if c.key.is_some() { String::new() } else { format!("{:?}:{:?}", options.labels, options.default) });
        let codec = Codec::MultiSelect(options.labels.iter().cloned().zip(native.iter().cloned()).collect());
        let (id, selected, set_value) = self.register_widget_parity(
            WidgetSpec {
                disabled: c.disabled,
                query: None,
                kind: "multiselect",
                key: c.key.as_deref(),
                identity: &identity,
                default,
                codec,
                callback: c.callback,
            },
            // Resolve on indices and clone the native options, matching
            // selectbox: from_value::<Vec<T>> trips the higher-ranked
            // lifetime check and borrowed types like &str cannot be
            // deserialized from owned state at all.
            |value| {
                value
                    .as_array()
                    .ok_or_else(|| WidgetError::InvalidValue("multiselect selection must be an index array".into()))?
                    .iter()
                    .map(|item| {
                        item.as_u64()
                            .and_then(|index| usize::try_from(index).ok())
                            .filter(|index| *index < options.options.len())
                            .map(|index| options.options[index].clone())
                            .ok_or_else(|| WidgetError::InvalidValue("invalid multiselect selection index".into()))
                    })
                    .collect()
            },
        )?;
        let selected: Vec<T> = selected;
        let default_wire: Vec<i32> = options.default.iter().map(|index| *index as i32).collect();
        self.push(Rc::new(RefCell::new(InputElement(proto::Element {
            width_config,
            has_one_shot_effect: set_value.then_some(true),
            r#type: Some(element::Type::Multiselect(proto::MultiSelect {
                id,
                label: c.label,
                form_id,
                default: default_wire,
                options: options.labels.clone(),
                help: c.help,
                disabled: c.disabled || options.options.is_empty(),
                label_visibility: c.visibility.wire(),
                accept_new_options: Some(false),
                select_all: Some(1000),
                max_selections: options.max_selections.map(|count| count as i32).unwrap_or(0),
                ignore_rerun: c.ignore_rerun,
                ..Default::default()
            })),
            ..Default::default()
        }))));
        Ok(selected)
    }

    fn number_input<T: NumberValue>(&self, options: impl Into<NumberInputOptions<T>>) -> Result<T, WidgetError> {
        let options = options.into();
        let c = options.common;
        let form_id = form_scope(self, c.callback.is_some())?;
        let width_config = c.width(false)?;
        let (min, max) = (options.min.map(T::to_f64), options.max.map(T::to_f64));
        let step = options.step.unwrap_or(if T::INTEGER { 1.0 } else { 0.01 });
        // SDK 允许相等边界和有限的零/负步长；仅拒绝倒置边界及无效数值。
        let numbers = [options.value.to_f64(), min.unwrap_or_default(), max.unwrap_or_default(), step];
        if !step.is_finite()
            || min.is_some_and(|low| low > max.unwrap_or(f64::INFINITY))
            || numbers.iter().any(|number| !number.is_finite())
            || (T::INTEGER && numbers.iter().any(|number| number.fract() != 0.0 || number.abs() > crate::widgets::JS_SAFE_INTEGER))
            || min.is_some_and(|low| options.value.to_f64() < low)
            || max.is_some_and(|high| options.value.to_f64() > high)
        {
            return Err(WidgetError::InvalidValue("number input needs a value inside ordered finite bounds (integers must be JS-safe) and a finite step".into()));
        }
        let default = options.value.to_value();
        // 无 key 时保留原始可选参数；省略 step 与显式默认步长的身份不同。
        let identity = c.identity_in_form(
            &form_id,
            &if c.key.is_some() {
                String::new()
            } else {
                serde_json::to_string(&(options.min, options.max, options.value, options.step, c.width))?
            },
        );
        let (id, result, set_value) = self.register_widget_parity(
            WidgetSpec {
                disabled: c.disabled,
                query: None,
                kind: "number_input",
                key: c.key.as_deref(),
                identity: &identity,
                default,
                codec: Codec::NumberInput { min, max, integer: T::INTEGER },
                callback: c.callback,
            },
            |value| T::from_value(value).ok_or_else(|| WidgetError::InvalidValue("number input expects its declared number type".into())),
        )?;
        self.push(Rc::new(RefCell::new(InputElement(proto::Element {
            width_config,
            has_one_shot_effect: set_value.then_some(true),
            r#type: Some(element::Type::NumberInput(proto::NumberInput {
                id,
                label: c.label,
                form_id,
                // The measured formats: %d for integers, %0.2f for floats
                // (frozen widget-params reference).
                format: if T::INTEGER { "%d".into() } else { "%0.2f".into() },
                data_type: i32::from(!T::INTEGER),
                has_min: min.is_some(),
                has_max: max.is_some(),
                default: Some(options.value.to_f64()),
                step,
                // 未指定边界仍发送 SDK 哨兵；has_min/has_max 只标记显式约束。
                min: min.unwrap_or(if T::INTEGER { -crate::widgets::JS_SAFE_INTEGER } else { f64::MIN }),
                max: max.unwrap_or(if T::INTEGER { crate::widgets::JS_SAFE_INTEGER } else { f64::MAX }),
                value: set_value.then(|| result.to_f64()),
                set_value,
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

    fn text_area(&self, options: impl Into<TextAreaOptions>) -> Result<Option<String>, WidgetError> {
        let options = options.into();
        let mut c = options.common;
        let form_id = form_scope(self, c.callback.is_some())?;

        // 显式空状态覆盖本轮默认值；身份仍使用调用方提供的原始选项。
        let mut wire_default = options.value.clone();
        if let Some(key) = c.key.as_deref()
            && self.get_app().lock().session_state.get::<Value>(key)?.is_some_and(|value| value.is_null())
        {
            wire_default = None;
        }

        // 默认值经反序列化截断；wire 保留有效默认值的原始文本。
        let default = wire_default
            .as_ref()
            .map_or(Value::Null, |value| Value::String(options.max_chars.map_or_else(|| value.clone(), |limit| value.chars().take(limit).collect())));

        // 显式 key 仍按上限变化重置；默认值变化不改变 keyed 控件身份。
        let identity = c.identity_in_form(
            &form_id,
            &if c.key.is_some() {
                serde_json::to_string(&options.max_chars)?
            } else {
                serde_json::to_string(&(&options.value, options.max_chars, options.height, &options.placeholder, c.width))?
            },
        );
        let (id, result, set_value) = self.register_widget_parity(
            WidgetSpec {
                disabled: c.disabled,
                query: None,
                kind: "text_area",
                key: c.key.as_deref(),
                identity: &identity,
                default: default.clone(),
                codec: Codec::Text { max_chars: options.max_chars },
                callback: c.callback.take(),
            },
            |value| {
                if value.is_null() {
                    return Ok(None);
                }
                value.as_str().map(|text| Some(text.to_string())).ok_or_else(|| WidgetError::InvalidValue("text area expects text".into()))
            },
        )?;

        // 布局错误在注册后返回；宽度先于高度，已处理的状态与 callback 保留。
        if let Some(width) = c.width
            && width <= 0
        {
            return Err(WidgetError::InvalidValue(format!("Invalid width value: {width}. Width must be either a positive integer (pixels) or 'stretch'.")));
        }
        let width_config = c.width(false)?;

        // 自动高度随标签布局变化，但不代替上面参与身份的原始高度选项。
        let height = options.height.unwrap_or(if matches!(c.visibility, LabelVisibility::Collapsed) { 94 } else { 122 });
        if height <= 0 {
            return Err(WidgetError::InvalidValue(format!("Invalid height value: {height}. Height must be either a positive integer (pixels), 'stretch', or 'content'.")));
        }

        self.push(Rc::new(RefCell::new(InputElement(proto::Element {
            width_config,
            height_config: Some(crate::proto::streamlit::HeightConfig {
                height_spec: Some(crate::proto::streamlit::height_config::HeightSpec::PixelHeight(height as u32)),
            }),
            has_one_shot_effect: set_value.then_some(true),
            r#type: Some(element::Type::TextArea(proto::TextArea {
                id,
                label: c.label,
                form_id,
                default: wire_default,
                max_chars: options.max_chars.unwrap_or_default() as u32,
                value: if set_value { result.clone() } else { None },
                set_value,
                help: c.help,
                disabled: c.disabled,
                label_visibility: c.visibility.wire(),
                placeholder: options.placeholder.unwrap_or_default(),
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
        let (default_min, default_max) = T::slider_default_bounds(&options.value);
        let min = options.min.unwrap_or(default_min);
        let max = options.max.unwrap_or(default_max);
        let step = options.step.unwrap_or_else(T::slider_default_step);
        let (domain_min, domain_max) = T::slider_domain();
        if !min.is_finite()
            || !max.is_finite()
            || !step.is_finite()
            || min >= max
            || step <= 0.0
            || min < domain_min
            || max > domain_max
            || (T::slider_wire_integral() && [min, max, step].iter().any(|v| v.fract() != 0.0 || v.abs() > crate::widgets::JS_SAFE_INTEGER))
        {
            return Err(WidgetError::InvalidValue(
                "slider needs ordered finite bounds representable by its return type and a positive step (integers and date/time values are JS-safe microsecond counts)".into(),
            ));
        }
        let default = serde_json::to_value(&options.value)?;
        // The measured DataType enum selects the codec: INT/FLOAT are raw
        // numeric doubles; DATETIME/DATE/TIME are epoch-microsecond doubles.
        let codec = match T::slider_data_type() {
            0 => Codec::Slider { min, max, count: T::COUNT, integer: true },
            1 => Codec::Slider { min, max, count: T::COUNT, integer: false },
            data_type => Codec::TemporalSlider {
                min,
                max,
                count: T::COUNT,
                kind: match data_type {
                    2 => crate::widgets::TemporalKind::Datetime,
                    3 => crate::widgets::TemporalKind::Date,
                    _ => crate::widgets::TemporalKind::Time,
                },
            },
        };
        if !codec.valid(&default) {
            return Err(WidgetError::InvalidValue("slider default is outside bounds or range is reversed".into()));
        }
        let constraints = format!("{}:{}:{}:{}:{}", min, max, step, T::slider_identity_kind(), T::COUNT);
        let identity = c.identity_in_form(&form_id, &if c.key.is_some() { constraints } else { format!("{constraints}:{default}:{:?}", options.format) });
        let (id, result, set_value) = self.register_widget_parity(
            WidgetSpec {
                disabled: c.disabled,
                query: None,
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
                default: options.value.slider_numbers(),
                value: if set_value { result.slider_numbers() } else { vec![] },
                set_value,
                min,
                max,
                step,
                data_type: T::slider_data_type(),
                r#type: 1,
                format: options.format.unwrap_or_else(T::slider_default_format),
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
        let (id, value, _) = self.register_widget_parity(
            WidgetSpec {
                disabled: options.disabled,
                query: None,
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

    fn toggle(&self, options: impl Into<ToggleOptions>) -> Result<bool, WidgetError> {
        let options = options.into();
        let c = options.common;
        let form_id = form_scope(self, c.callback.is_some())?;
        let width_config = c.width(true)?;
        let identity = c.identity_in_form(&form_id, &if c.key.is_some() { String::new() } else { options.value.to_string() });
        let (id, value, set_value) = self.register_widget_parity(
            WidgetSpec {
                disabled: c.disabled,
                query: None,
                kind: "toggle",
                key: c.key.as_deref(),
                identity: &identity,
                default: options.value.into(),
                codec: Codec::Bool,
                callback: c.callback,
            },
            |value| value.as_bool().ok_or_else(|| WidgetError::InvalidValue("toggle expects bool".into())),
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
                r#type: proto::checkbox::StyleType::Toggle as i32,
                ..Default::default()
            })),
            ..Default::default()
        }))));
        Ok(value)
    }

    fn feedback(&self, options: impl Into<FeedbackOptions>) -> Result<Option<u32>, WidgetError> {
        let options = options.into();
        let c = options.common;
        let form_id = form_scope(self, c.callback.is_some())?;
        let width_config = c.width(true)?;
        let count = options.kind.count();
        if options.default.is_some_and(|default| default as usize >= count) {
            return Err(WidgetError::InvalidValue("feedback default is outside the style's icons".into()));
        }
        let identity = c.identity_in_form(&form_id, &if c.key.is_some() { String::new() } else { format!("{:?}:{}", options.kind, options.default.unwrap_or(0)) });
        let (id, value, set_value) = self.register_widget_parity(
            WidgetSpec {
                disabled: c.disabled,
                query: None,
                kind: "feedback",
                key: c.key.as_deref(),
                identity: &identity,
                default: options.default.map(Value::from).unwrap_or(Value::Null),
                codec: Codec::Feedback { count },
                callback: c.callback,
            },
            |value| {
                if value.is_null() {
                    return Ok(None);
                }
                value.as_u64().map(|index| index as u32).map(Some).ok_or_else(|| WidgetError::InvalidValue("feedback expects an icon index".into()))
            },
        )?;
        self.push(Rc::new(RefCell::new(InputElement(proto::Element {
            width_config,
            has_one_shot_effect: set_value.then_some(true),
            r#type: Some(element::Type::Feedback(proto::Feedback {
                id,
                r#type: options.kind.wire() as i32,
                default: options.default,
                disabled: c.disabled,
                form_id,
                value: set_value.then_some(value).flatten(),
                set_value,
                ignore_rerun: c.ignore_rerun,
            })),
            ..Default::default()
        }))));
        Ok(value)
    }

    fn pills(&self, options: impl Into<ButtonGroupOptions>) -> Result<ButtonGroupValue, WidgetError> {
        emit_button_group(self, options.into(), proto::button_group::Style::Pills)
    }

    fn segmented_control(&self, options: impl Into<ButtonGroupOptions>) -> Result<ButtonGroupValue, WidgetError> {
        emit_button_group(self, options.into(), proto::button_group::Style::SegmentedControl)
    }

    fn pagination(&self, options: impl Into<PaginationOptions>) -> Result<u32, WidgetError> {
        let options = options.into();
        let c = options.common;
        let form_id = form_scope(self, c.callback.is_some())?;
        let width_config = c.width(true)?;
        if options.num_pages < 1 {
            return Err(WidgetError::InvalidValue("pagination needs at least one page".into()));
        }
        if !(1..=options.num_pages).contains(&options.default) {
            return Err(WidgetError::InvalidValue("pagination default is outside the pages".into()));
        }
        let identity = c.identity_in_form(&form_id, &if c.key.is_some() { String::new() } else { format!("{}:{}:{:?}", options.num_pages, options.default, options.max_visible_pages) });
        let (id, value, set_value) = self.register_widget_parity(
            WidgetSpec {
                disabled: c.disabled,
                query: None,
                kind: "pagination",
                key: c.key.as_deref(),
                identity: &identity,
                default: Value::from(options.default as u64),
                codec: Codec::Pagination { num_pages: options.num_pages },
                callback: c.callback,
            },
            |value| value.as_u64().map(|page| page as u32).ok_or_else(|| WidgetError::InvalidValue("pagination expects a page number".into())),
        )?;
        self.push(Rc::new(RefCell::new(InputElement(proto::Element {
            width_config,
            has_one_shot_effect: set_value.then_some(true),
            r#type: Some(element::Type::Pagination(proto::Pagination {
                id,
                num_pages: options.num_pages,
                default: options.default,
                max_visible_pages: options.max_visible_pages,
                disabled: c.disabled,
                form_id,
                // The reference streams value only with set_value; an
                // unchanged page stays at the declared default, which the
                // wire omits.
                value: if set_value { value } else { 0 },
                set_value,
                ignore_rerun: c.ignore_rerun,
                ..Default::default()
            })),
            ..Default::default()
        }))));
        Ok(value)
    }

    fn menu_button(&self, options: impl Into<MenuButtonOptions>) -> Result<Option<String>, WidgetError> {
        let options = options.into();
        let c = options.common;
        if self.parent_form_id().is_some() {
            return Err(WidgetError::InvalidValue("st.menu_button cannot be added to a form".into()));
        }
        if options.options.is_empty() {
            return Err(WidgetError::InvalidValue("menu_button needs at least one option".into()));
        }
        let width_config = c.width(true)?;
        let identity = c.identity_in_form("", &if c.key.is_some() { String::new() } else { format!("{:?}:{}:{:?}", options.options, options.r#type, options.icon) });
        let (id, value, _) = self.register_widget_parity(
            WidgetSpec {
                disabled: c.disabled,
                query: None,
                kind: "menu_button",
                key: c.key.as_deref(),
                identity: &identity,
                default: Value::Null,
                codec: Codec::StringTrigger(options.options.clone()),
                callback: c.callback,
            },
            |value| {
                if value.is_null() {
                    return Ok(None);
                }
                value
                    .as_u64()
                    .and_then(|index| options.options.get(index as usize).cloned())
                    .map(Some)
                    .ok_or_else(|| WidgetError::InvalidValue("invalid menu_button selection index".into()))
            },
        )?;
        self.push(Rc::new(RefCell::new(InputElement(proto::Element {
            width_config,
            r#type: Some(element::Type::MenuButton(proto::MenuButton {
                id,
                label: c.label,
                options: options.options,
                help: c.help,
                r#type: options.r#type,
                disabled: c.disabled,
                icon: options.icon.unwrap_or_default(),
                ..Default::default()
            })),
            ..Default::default()
        }))));
        Ok(value)
    }

    fn link_button(&self, options: impl Into<LinkButtonOptions>) -> Result<bool, WidgetError> {
        let options = options.into();
        let c = options.common;
        let width_config = c.width(true)?;
        // The reference's default is `on_click="ignore"`: a pure element
        // that still registers its id and key when either is given. Only an
        // opted-in click trigger carries widget state.
        let (id, value) = if options.rerun || c.key.is_some() {
            if self.parent_form_id().is_some() {
                return Err(WidgetError::InvalidValue("st.link_button cannot be added to a form".into()));
            }
            let identity = if c.key.is_some() {
                String::new()
            } else {
                serde_json::to_string(&(&c.label, &c.help, &options.url, &options.r#type, &options.icon))?
            };
            let (id, value, _) = self.register_widget_parity(
                WidgetSpec {
                    disabled: c.disabled,
                    query: None,
                    kind: "link_button",
                    key: c.key.as_deref(),
                    identity: &identity,
                    default: false.into(),
                    codec: Codec::Trigger,
                    callback: if options.rerun { c.callback } else { None },
                },
                |value| value.as_bool().ok_or_else(|| WidgetError::InvalidValue("link_button expects bool".into())),
            )?;
            (id, value)
        } else {
            (String::new(), false)
        };
        self.push(Rc::new(RefCell::new(InputElement(proto::Element {
            width_config,
            r#type: Some(element::Type::LinkButton(proto::LinkButton {
                id,
                label: c.label,
                help: c.help,
                url: options.url,
                disabled: c.disabled,
                r#type: options.r#type,
                icon: options.icon.unwrap_or_default(),
                ignore_rerun: !options.rerun,
                ..Default::default()
            })),
            ..Default::default()
        }))));
        Ok(value)
    }

    fn download_button(&self, options: impl Into<DownloadButtonOptions>) -> Result<bool, WidgetError> {
        let options = options.into();
        let c = options.common;
        if self.parent_form_id().is_some() {
            return Err(WidgetError::InvalidValue("st.download_button cannot be added to a form".into()));
        }
        let width_config = c.width(true)?;
        let mime = options.mime.clone().unwrap_or_else(|| "application/octet-stream".to_string());
        let url = format!("/media/{}{}", crate::media::put_download(&options.data, &mime, options.file_name.as_deref()), crate::media::download_extension(&mime));
        let identity = if c.key.is_some() {
            String::new()
        } else {
            serde_json::to_string(&(&c.label, &c.help, &options.file_name, &mime, &options.r#type, &options.icon))?
        };
        let (id, value, _) = self.register_widget_parity(
            WidgetSpec {
                disabled: c.disabled,
                query: None,
                kind: "download_button",
                key: c.key.as_deref(),
                identity: &identity,
                default: false.into(),
                codec: Codec::Trigger,
                callback: c.callback,
            },
            |value| value.as_bool().ok_or_else(|| WidgetError::InvalidValue("download_button expects bool".into())),
        )?;
        self.push(Rc::new(RefCell::new(InputElement(proto::Element {
            width_config,
            r#type: Some(element::Type::DownloadButton(proto::DownloadButton {
                id,
                label: c.label,
                default: false,
                help: c.help,
                url,
                disabled: c.disabled,
                r#type: options.r#type,
                icon: options.icon.unwrap_or_default(),
                ignore_rerun: c.ignore_rerun,
                ..Default::default()
            })),
            ..Default::default()
        }))));
        Ok(value)
    }

    fn date_input(&self, options: impl Into<DateInputOptions>) -> Result<DateSelection, WidgetError> {
        use chrono::{Datelike, NaiveDate};
        let options = options.into();
        let c = options.common;
        let form_id = form_scope(self, c.callback.is_some())?;
        let width_config = c.width(false)?;
        let iso = |date: NaiveDate| date.format("%Y-%m-%d").to_string();
        // The reference's default bounds: a ten-year window around the
        // value (the range's endpoints each anchor their own side).
        let ten_years = |date: NaiveDate, forward: bool| {
            let shift = if forward { 10 } else { -10 };
            NaiveDate::from_ymd_opt(date.year() + shift, date.month(), date.day())
                .or_else(|| NaiveDate::from_ymd_opt(date.year() + shift, date.month(), (date.day() - 1).max(1)))
                .expect("a shifted date always exists")
        };
        let (range, default, default_wire, min, max) = if let Some((start, end)) = options.range {
            if start > end {
                return Err(WidgetError::InvalidValue("date_input range is reversed".into()));
            }
            let min = options.min.unwrap_or_else(|| ten_years(start, false));
            let max = options.max.unwrap_or_else(|| ten_years(end, true));
            if start < min || end > max {
                return Err(WidgetError::InvalidValue("date_input value is outside min/max".into()));
            }
            (true, Value::Array(vec![Value::String(iso(start)), Value::String(iso(end))]), vec![iso(start), iso(end)], min, max)
        } else {
            let date = options.single.ok_or_else(|| WidgetError::InvalidValue("date_input needs a value".into()))?;
            let min = options.min.unwrap_or_else(|| ten_years(date, false));
            let max = options.max.unwrap_or_else(|| ten_years(date, true));
            if date < min || date > max {
                return Err(WidgetError::InvalidValue("date_input value is outside min/max".into()));
            }
            (false, Value::String(iso(date)), vec![iso(date)], min, max)
        };
        let identity = c.identity_in_form(
            &form_id,
            &if c.key.is_some() {
                String::new()
            } else {
                format!(
                    "{:?}:{:?}:{:?}:{}:{}",
                    options.single.map(iso),
                    options.range.map(|(start, end)| (iso(start), iso(end))),
                    (options.min.map(iso), options.max.map(iso)),
                    options.format,
                    range
                )
            },
        );
        let (id, selected, set_value) = self.register_widget_parity(
            WidgetSpec {
                disabled: c.disabled,
                query: None,
                kind: "date_input",
                key: c.key.as_deref(),
                identity: &identity,
                default,
                codec: Codec::DateInput { range },
                callback: c.callback,
            },
            |value| {
                let parse = |text: &str| NaiveDate::parse_from_str(text, "%Y-%m-%d").map_err(|_| WidgetError::InvalidValue("date_input expects ISO dates".into()));
                Ok(if range {
                    let items = value.as_array().ok_or_else(|| WidgetError::InvalidValue("date_input range expects two dates".into()))?;
                    DateSelection::Range(parse(items[0].as_str().unwrap_or_default())?, parse(items[1].as_str().unwrap_or_default())?)
                } else {
                    DateSelection::Single(parse(value.as_str().unwrap_or_default())?)
                })
            },
        )?;
        self.push(Rc::new(RefCell::new(InputElement(proto::Element {
            width_config,
            has_one_shot_effect: set_value.then_some(true),
            r#type: Some(element::Type::DateInput(proto::DateInput {
                id,
                label: c.label,
                default: default_wire,
                min: iso(min),
                max: iso(max),
                is_range: range,
                help: c.help,
                form_id,
                value: if set_value {
                    match &selected {
                        DateSelection::Single(date) => vec![iso(*date)],
                        DateSelection::Range(start, end) => vec![iso(*start), iso(*end)],
                    }
                } else {
                    Vec::new()
                },
                set_value,
                disabled: c.disabled,
                label_visibility: c.visibility.wire(),
                format: options.format,
                ignore_rerun: c.ignore_rerun,
                ..Default::default()
            })),
            ..Default::default()
        }))));
        Ok(selected)
    }

    fn time_input(&self, options: impl Into<TimeInputOptions>) -> Result<Option<chrono::NaiveTime>, WidgetError> {
        use chrono::NaiveTime;
        let options = options.into();
        let c = options.common;
        let form_id = form_scope(self, c.callback.is_some())?;
        let width_config = c.width(false)?;
        if !(1..=82_800).contains(&options.step) {
            return Err(WidgetError::InvalidValue("time_input step must be between one second and 23 hours".into()));
        }
        let wire_format = if options.step % 60 != 0 { "%H:%M:%S" } else { "%H:%M" };
        let wire = |time: NaiveTime| time.format(wire_format).to_string();
        let default = options.value.map(|time| Value::String(wire(time))).unwrap_or(Value::Null);
        let identity = c.identity_in_form(&form_id, &if c.key.is_some() { String::new() } else { format!("{:?}:{}:{}", options.value.map(wire), options.step, options.format) });
        let (id, value, set_value) = self.register_widget_parity(
            WidgetSpec {
                disabled: c.disabled,
                query: None,
                kind: "time_input",
                key: c.key.as_deref(),
                identity: &identity,
                default,
                codec: Codec::TimeInput { step: options.step },
                callback: c.callback,
            },
            |value| {
                if value.is_null() {
                    return Ok(None);
                }
                NaiveTime::parse_from_str(value.as_str().unwrap_or_default(), wire_format)
                    .map(Some)
                    .map_err(|_| WidgetError::InvalidValue("time_input expects a clock time".into()))
            },
        )?;
        self.push(Rc::new(RefCell::new(InputElement(proto::Element {
            width_config,
            has_one_shot_effect: set_value.then_some(true),
            r#type: Some(element::Type::TimeInput(proto::TimeInput {
                id,
                label: c.label,
                default: options.value.map(wire),
                help: c.help,
                form_id,
                value: set_value.then_some(value.map(wire)).flatten(),
                set_value,
                disabled: c.disabled,
                label_visibility: c.visibility.wire(),
                step: options.step,
                format: Some(options.format.to_string()),
                ignore_rerun: c.ignore_rerun,
                ..Default::default()
            })),
            ..Default::default()
        }))));
        Ok(value)
    }

    fn datetime_input(&self, options: impl Into<DateTimeInputOptions>) -> Result<Option<chrono::NaiveDateTime>, WidgetError> {
        use chrono::{Datelike, NaiveDate, NaiveDateTime};
        let options = options.into();
        let c = options.common;
        let form_id = form_scope(self, c.callback.is_some())?;
        let width_config = c.width(false)?;
        if !(60..=82_800).contains(&options.step) {
            return Err(WidgetError::InvalidValue("datetime_input step must be between 60 seconds and 23 hours".into()));
        }
        let wire = |moment: NaiveDateTime| moment.format("%Y-%m-%dT%H:%M").to_string();
        // The reference's default bounds: ten years either side of the
        // value's date, min at 00:00 and max at 23:59.
        let ten_years = |date: NaiveDate, forward: bool| {
            let shift = if forward { 10 } else { -10 };
            NaiveDate::from_ymd_opt(date.year() + shift, date.month(), date.day())
                .or_else(|| NaiveDate::from_ymd_opt(date.year() + shift, date.month(), (date.day() - 1).max(1)))
                .expect("a shifted date always exists")
        };
        let base_date = options.value.map(|moment| moment.date()).unwrap_or_else(|| chrono::Local::now().date_naive());
        let midnight = chrono::NaiveTime::from_hms_opt(0, 0, 0).expect("midnight");
        let end_of_day = chrono::NaiveTime::from_hms_opt(23, 59, 0).expect("23:59");
        let min = options.min.unwrap_or_else(|| ten_years(base_date, false).and_time(midnight));
        let max = options.max.unwrap_or_else(|| ten_years(base_date, true).and_time(end_of_day));
        if min > max {
            return Err(WidgetError::InvalidValue("datetime_input min is after max".into()));
        }
        if let Some(value) = options.value
            && (value < min || value > max)
        {
            return Err(WidgetError::InvalidValue("datetime_input value is outside min/max".into()));
        }
        let default = options.value.map(|moment| Value::String(wire(moment))).unwrap_or(Value::Null);
        let identity = c.identity_in_form(&form_id, &if c.key.is_some() { String::new() } else { format!("{:?}:{}:{}", options.value.map(wire), options.step, options.format) });
        let (id, value, set_value) = self.register_widget_parity(
            WidgetSpec {
                disabled: c.disabled,
                query: None,
                kind: "datetime_input",
                key: c.key.as_deref(),
                identity: &identity,
                default,
                codec: Codec::DateTimeInput,
                callback: c.callback,
            },
            |value| {
                if value.is_null() {
                    return Ok(None);
                }
                NaiveDateTime::parse_from_str(value.as_str().unwrap_or_default(), "%Y-%m-%dT%H:%M")
                    .map(Some)
                    .map_err(|_| WidgetError::InvalidValue("datetime_input expects an ISO datetime".into()))
            },
        )?;
        self.push(Rc::new(RefCell::new(InputElement(proto::Element {
            width_config,
            has_one_shot_effect: set_value.then_some(true),
            r#type: Some(element::Type::DateTimeInput(proto::DateTimeInput {
                id,
                label: c.label,
                default: options.value.map(|moment| vec![wire(moment)]).unwrap_or_default(),
                min: wire(min),
                max: wire(max),
                help: c.help,
                form_id,
                value: set_value.then_some(value.map(wire)).flatten().into_iter().collect(),
                set_value,
                disabled: c.disabled,
                label_visibility: c.visibility.wire(),
                format: options.format,
                step: options.step,
                is_range: false,
                ignore_rerun: c.ignore_rerun,
                ..Default::default()
            })),
            ..Default::default()
        }))));
        Ok(value)
    }

    fn color_picker(&self, options: impl Into<ColorPickerOptions>) -> Result<String, WidgetError> {
        let options = options.into();
        let c = options.common;
        let form_id = form_scope(self, c.callback.is_some())?;
        let width_config = c.width(true)?;
        let valid_hex = |value: &str| {
            let digits = value.strip_prefix('#').unwrap_or(value);
            digits.len() == 6 && digits.bytes().all(|byte| byte.is_ascii_hexdigit())
        };
        if !valid_hex(&options.value) {
            return Err(WidgetError::InvalidValue("color_picker expects a #RRGGBB value".into()));
        }
        let identity = c.identity_in_form(&form_id, &if c.key.is_some() { String::new() } else { options.value.clone() });
        let (id, value, set_value) = self.register_widget_parity(
            WidgetSpec {
                disabled: c.disabled,
                query: None,
                kind: "color_picker",
                key: c.key.as_deref(),
                identity: &identity,
                default: Value::String(options.value.clone()),
                codec: Codec::Text { max_chars: None },
                callback: c.callback,
            },
            |value| {
                let text = value.as_str().ok_or_else(|| WidgetError::InvalidValue("color_picker expects a string".into()))?;
                valid_hex(text).then(|| text.to_string()).ok_or_else(|| WidgetError::InvalidValue("color_picker expects a #RRGGBB value".into()))
            },
        )?;
        self.push(Rc::new(RefCell::new(InputElement(proto::Element {
            width_config,
            has_one_shot_effect: set_value.then_some(true),
            r#type: Some(element::Type::ColorPicker(proto::ColorPicker {
                id,
                label: c.label,
                default: options.value,
                help: c.help,
                form_id,
                value: if set_value { value.clone() } else { String::new() },
                set_value,
                disabled: c.disabled,
                label_visibility: c.visibility.wire(),
                ignore_rerun: c.ignore_rerun,
                ..Default::default()
            })),
            ..Default::default()
        }))));
        Ok(value)
    }

    fn select_slider(&self, options: impl Into<SelectSliderOptions>) -> Result<SelectSliderValue, WidgetError> {
        let options = options.into();
        let c = options.common;
        let form_id = form_scope(self, c.callback.is_some())?;
        let width_config = c.width(false)?;
        if options.options.len() < 2 {
            return Err(WidgetError::InvalidValue("select_slider needs at least two options".into()));
        }
        if options.default.len() > 2 || options.default.iter().collect::<std::collections::HashSet<_>>().len() != options.default.len() {
            return Err(WidgetError::InvalidValue("select_slider defaults must be one or two distinct labels".into()));
        }
        let mut default_indices: Vec<f64> = Vec::with_capacity(options.default.len());
        for label in &options.default {
            let index = options.options.iter().position(|option| option == label).ok_or_else(|| WidgetError::InvalidValue("select_slider default is absent from options".into()))?;
            default_indices.push(index as f64);
        }
        if default_indices.len() == 2 && default_indices[0] > default_indices[1] {
            return Err(WidgetError::InvalidValue("select_slider range is reversed".into()));
        }
        let range = default_indices.len() == 2;
        let native: Vec<Value> = options.options.iter().map(|label| Value::String(label.clone())).collect();
        let default = if range {
            Value::Array(vec![Value::from(default_indices[0] as u64), Value::from(default_indices[1] as u64)])
        } else {
            default_indices.first().map(|index| Value::from(*index as u64)).unwrap_or(Value::from(0_u64))
        };
        let identity = c.identity_in_form(&form_id, &if c.key.is_some() { String::new() } else { format!("{:?}:{:?}", options.options, options.default) });
        let (id, selected, set_value) = self.register_widget_parity(
            WidgetSpec {
                disabled: c.disabled,
                query: None,
                kind: "select_slider",
                key: c.key.as_deref(),
                identity: &identity,
                default,
                codec: Codec::ButtonGroup {
                    options: options.options.iter().cloned().zip(native).collect(),
                    multi: range,
                },
                callback: c.callback,
            },
            |value| {
                let label_at = |index: &Value| {
                    index
                        .as_u64()
                        .and_then(|index| usize::try_from(index).ok())
                        .and_then(|index| options.options.get(index).cloned())
                        .ok_or_else(|| WidgetError::InvalidValue("invalid select_slider index".into()))
                };
                Ok(if range {
                    let items = value.as_array().ok_or_else(|| WidgetError::InvalidValue("a select-slider range expects two labels".into()))?;
                    SelectSliderValue::Range(label_at(&items[0])?, label_at(&items[1])?)
                } else {
                    SelectSliderValue::Single(label_at(value)?)
                })
            },
        )?;
        let raw_values = match &selected {
            SelectSliderValue::Single(label) => vec![label.clone()],
            SelectSliderValue::Range(start, end) => vec![start.clone(), end.clone()],
        };
        self.push(Rc::new(RefCell::new(InputElement(proto::Element {
            width_config,
            has_one_shot_effect: set_value.then_some(true),
            r#type: Some(element::Type::Slider(proto::Slider {
                id,
                label: c.label,
                form_id,
                format: "%s".to_string(),
                data_type: 0,
                default: if default_indices.is_empty() { vec![0.0] } else { default_indices },
                min: 0.0,
                max: (options.options.len() - 1) as f64,
                step: 1.0,
                value: Vec::new(),
                set_value,
                options: options.options.clone(),
                help: c.help,
                disabled: c.disabled,
                label_visibility: c.visibility.wire(),
                r#type: 2,
                raw_value: if set_value { raw_values } else { Vec::new() },
                ignore_rerun: c.ignore_rerun,
                ..Default::default()
            })),
            ..Default::default()
        }))));
        Ok(selected)
    }

    fn audio_input(&self, options: impl Into<AudioInputOptions>) -> Result<Option<UploadedFile>, WidgetError> {
        let options = options.into();
        let c = options.common;
        let form_id = form_scope(self, c.callback.is_some())?;
        let width_config = c.width(false)?;
        let identity = c.identity_in_form(&form_id, &if c.key.is_some() { String::new() } else { format!("{:?}", options.sample_rate) });
        let uploads = self.get_app().lock().session_state.uploads.clone();
        let resolve_store = uploads.clone();
        let (id, file, _) = self.register_widget_parity(
            WidgetSpec {
                disabled: c.disabled,
                query: None,
                kind: "audio_input",
                key: c.key.as_deref(),
                identity: &identity,
                default: Value::Array(Vec::new()),
                codec: Codec::Files { store: uploads, multiple: false },
                callback: c.callback,
            },
            move |value| {
                let ids: Vec<String> = serde_json::from_value(value.clone())?;
                let store = resolve_store.lock();
                Ok(ids.first().and_then(|id| store.get(id)))
            },
        )?;
        self.push(Rc::new(RefCell::new(InputElement(proto::Element {
            width_config,
            r#type: Some(element::Type::AudioInput(proto::AudioInput {
                id,
                label: c.label,
                help: c.help,
                form_id,
                disabled: c.disabled,
                label_visibility: c.visibility.wire(),
                sample_rate: options.sample_rate,
                ignore_rerun: c.ignore_rerun,
            })),
            ..Default::default()
        }))));
        Ok(file)
    }

    fn camera_input(&self, options: impl Into<CameraInputOptions>) -> Result<Option<UploadedFile>, WidgetError> {
        let options = options.into();
        let c = options.common;
        let form_id = form_scope(self, c.callback.is_some())?;
        let width_config = c.width(false)?;
        let identity = c.identity_in_form(&form_id, "");
        let uploads = self.get_app().lock().session_state.uploads.clone();
        let resolve_store = uploads.clone();
        let (id, file, _) = self.register_widget_parity(
            WidgetSpec {
                disabled: c.disabled,
                query: None,
                kind: "camera_input",
                key: c.key.as_deref(),
                identity: &identity,
                default: Value::Array(Vec::new()),
                codec: Codec::Files { store: uploads, multiple: false },
                callback: c.callback,
            },
            move |value| {
                let ids: Vec<String> = serde_json::from_value(value.clone())?;
                let store = resolve_store.lock();
                Ok(ids.first().and_then(|id| store.get(id)))
            },
        )?;
        self.push(Rc::new(RefCell::new(InputElement(proto::Element {
            width_config,
            r#type: Some(element::Type::CameraInput(proto::CameraInput {
                id,
                label: c.label,
                help: c.help,
                form_id,
                disabled: c.disabled,
                label_visibility: c.visibility.wire(),
                ignore_rerun: c.ignore_rerun,
                ..Default::default()
            })),
            ..Default::default()
        }))));
        Ok(file)
    }

    fn chat_input(&self, options: impl Into<ChatInputOptions>) -> Result<Option<String>, WidgetError> {
        let options = options.into();
        if self.parent_form_id().is_some() {
            return Err(WidgetError::InvalidValue("st.chat_input cannot be added to a form".into()));
        }
        let identity = if options.key.is_some() { String::new() } else { options.placeholder.clone() };
        let (id, value, _) = self.register_widget_parity(
            WidgetSpec {
                disabled: false,
                query: None,
                kind: "chat_input",
                key: options.key.as_deref(),
                identity: &identity,
                default: Value::Null,
                codec: Codec::ChatInput,
                callback: None,
            },
            |value| Ok(value.as_str().map(str::to_owned)),
        )?;
        // The measured shape: the widget routes to the bottom root [3, 0]
        // without consuming a main-flow slot, carrying the placeholder, the
        // 200 MB server upload cap, the 16000 Hz audio sample rate and the
        // auto-position marker.
        self.push(Rc::new(RefCell::new(crate::elements::input::BottomRoutedElement(proto::Element {
            r#type: Some(element::Type::ChatInput(proto::ChatInput {
                id,
                placeholder: options.placeholder,
                max_upload_size_mb: 200,
                audio_sample_rate: Some(16000),
                is_auto_positioned_at_bottom: true,
                ..Default::default()
            })),
            ..Default::default()
        }))));
        Ok(value)
    }
}

/// The one selectbox emitter behind both the plain and the creation-mode
/// calls: the measured 1.66.1 wire (acceptNewOptions, filterMode,
/// queryParamKey, the string state of a freshly typed creation value).
#[allow(clippy::type_complexity)]
fn emit_selectbox<C: AppendChild, T: Clone + Serialize>(this: &C, options: SelectboxOptions<T>, creation: bool, creation_build: &dyn Fn(&str) -> Option<T>) -> Result<Option<T>, WidgetError> {
    let c = options.common;
    let form_id = form_scope(this, c.callback.is_some())?;
    let width_config = c.width(false)?;
    if !options.options.is_empty() && options.index.is_some_and(|i| i >= options.options.len()) {
        return Err(WidgetError::InvalidValue("selectbox index is outside options".into()));
    }
    if creation && options.filter_mode.is_none() {
        return Err(WidgetError::InvalidValue("selectbox filter_mode cannot be disabled with accept_new_options".into()));
    }
    if options.bind == TextBind::QueryParams && c.key.is_none() {
        return Err(WidgetError::InvalidValue("selectbox query binding requires a key".into()));
    }
    if options.bind == TextBind::QueryParams && c.key.as_deref().is_some_and(crate::query_params::is_embed_key) {
        return Err(WidgetError::InvalidValue("cannot bind a reserved embedding query parameter".into()));
    }
    let native: Vec<Value> = options.options.iter().map(serde_json::to_value).collect::<Result<_, _>>()?;
    let default = options.index.filter(|index| *index < native.len()).map(Value::from).unwrap_or(Value::Null);
    // Creation mode joins the widget identity, like the reference's
    // key_as_main_identity("accept_new_options").
    let identity = c.identity_in_form(&form_id, &if c.key.is_some() { String::new() } else { format!("{:?}:{:?}:{}", options.labels, options.index, creation) });
    let pairs = options.labels.iter().cloned().zip(native.iter().cloned()).collect();
    let codec = if creation { Codec::SelectCreation(pairs) } else { Codec::Select(pairs) };
    let labels = options.labels.clone();
    let values = options.options.clone();
    let (id, selected, set_value) = this.register_widget_parity(
        WidgetSpec {
            disabled: c.disabled,
            query: (options.bind == TextBind::QueryParams).then_some(crate::widgets::QueryBinding { clearable: options.index.is_none() }),
            kind: "selectbox",
            key: c.key.as_deref(),
            identity: &identity,
            default: default.clone(),
            codec,
            callback: c.callback,
        },
        |value| {
            if value.is_null() {
                return Ok(None);
            }
            let index = value.as_u64().and_then(|index| usize::try_from(index).ok()).filter(|index| *index < labels.len());
            match index {
                Some(index) => Ok(Some(values[index].clone())),
                // Creation mode: a freshly typed value arrives as its
                // label string outside the options list.
                None if creation => value.as_str().and_then(creation_build).map(Some).ok_or_else(|| WidgetError::InvalidValue("invalid selection value".into())),
                None => Err(WidgetError::InvalidValue("invalid selection index".into())),
            }
        },
    )?;
    let app = this.get_app();
    let state = app.lock().session_state.clone();
    state.set_query_binding(&id, options.bind == TextBind::QueryParams);
    crate::query_params::flush_query_update(&mut app.lock());
    let result = selected.clone();
    let empty = options.options.is_empty();
    let raw_label = |selected: &Option<T>| -> Option<String> {
        let value = selected.as_ref()?;
        let json = serde_json::to_value(value).ok()?;
        native
            .iter()
            .position(|candidate| *candidate == json)
            .map(|index| labels[index].clone())
            .or_else(|| json.as_str().map(str::to_string))
            .or_else(|| labels.first().cloned())
    };
    this.push(Rc::new(RefCell::new(InputElement(proto::Element {
        width_config,
        has_one_shot_effect: set_value.then_some(true),
        r#type: Some(element::Type::Selectbox(proto::Selectbox {
            id,
            label: c.label,
            form_id,
            default: if empty { None } else { options.index.map(|i| i as i32) },
            options: options.labels.clone(),
            help: c.help,
            raw_value: if set_value { raw_label(&selected) } else { None },
            set_value,
            disabled: c.disabled || (empty && !creation),
            label_visibility: c.visibility.wire(),
            placeholder: options.placeholder.unwrap_or_default(),
            accept_new_options: Some(creation),
            query_param_key: (options.bind == TextBind::QueryParams).then(|| c.key.clone()).flatten(),
            filter_mode: options.filter_mode.map(|mode| mode.wire()).unwrap_or(crate::proto::streamlit::SelectWidgetFilterMode::FilterModeFuzzy as i32),
            ignore_rerun: c.ignore_rerun,
        })),
        ..Default::default()
    }))));
    Ok(result)
}

/// The one emitter behind pills and segmented_control: both are the same
/// button-group element with a different style, the measured 1.66.1 wire.
fn emit_button_group<C: AppendChild>(this: &C, options: ButtonGroupOptions, style: proto::button_group::Style) -> Result<ButtonGroupValue, WidgetError> {
    let c = options.common;
    let multi = options.mode == SelectionMode::Multi;
    let form_id = form_scope(this, c.callback.is_some())?;
    let width_config = c.width(true)?;
    if options.required && multi {
        return Err(WidgetError::InvalidValue("required is only supported for single-select mode".into()));
    }
    if options.default.len() > options.options.len() || (!multi && options.default.len() > 1) {
        return Err(WidgetError::InvalidValue("button-group defaults must fit the selection mode".into()));
    }
    let mut default_indices: Vec<u32> = Vec::with_capacity(options.default.len());
    for label in &options.default {
        let index = options.options.iter().position(|option| option == label).ok_or_else(|| WidgetError::InvalidValue("button-group default is absent from options".into()))?;
        default_indices.push(index as u32);
    }
    let native: Vec<Value> = options.options.iter().map(|label| Value::String(label.clone())).collect();
    let default = if multi {
        Value::Array(default_indices.iter().map(|index| Value::from(*index as u64)).collect())
    } else {
        default_indices.first().map(|index| Value::from(*index as u64)).unwrap_or(Value::Null)
    };
    let identity = c.identity_in_form(
        &form_id,
        &if c.key.is_some() {
            String::new()
        } else {
            format!("{:?}:{:?}:{}:{:?}", options.options, default_indices, multi, options.required)
        },
    );
    let (id, selected, set_value) = this.register_widget_parity(
        WidgetSpec {
            disabled: c.disabled,
            query: None,
            kind: if style == proto::button_group::Style::Pills { "pills" } else { "segmented_control" },
            key: c.key.as_deref(),
            identity: &identity,
            default,
            codec: Codec::ButtonGroup {
                options: options.options.iter().cloned().zip(native).collect(),
                multi,
            },
            callback: c.callback,
        },
        |value| {
            let labels = if multi {
                value
                    .as_array()
                    .ok_or_else(|| WidgetError::InvalidValue("multi-select expects an index array".into()))?
                    .iter()
                    .map(|item| {
                        item.as_u64()
                            .and_then(|index| usize::try_from(index).ok())
                            .and_then(|index| options.options.get(index).cloned())
                            .ok_or_else(|| WidgetError::InvalidValue("invalid button-group selection index".into()))
                    })
                    .collect::<Result<Vec<_>, _>>()?
            } else if value.is_null() {
                Vec::new()
            } else {
                vec![
                    value
                        .as_u64()
                        .and_then(|index| usize::try_from(index).ok())
                        .and_then(|index| options.options.get(index).cloned())
                        .ok_or_else(|| WidgetError::InvalidValue("invalid button-group selection index".into()))?,
                ]
            };
            Ok(if multi { ButtonGroupValue::Multi(labels) } else { ButtonGroupValue::Single(labels.into_iter().next()) })
        },
    )?;
    // The selection labels re-serialize in selection order, like the
    // reference's serializer, so the frontend's set_value stays faithful.
    let raw_values = match &selected {
        ButtonGroupValue::Single(Some(label)) => vec![label.clone()],
        ButtonGroupValue::Single(None) => Vec::new(),
        ButtonGroupValue::Multi(labels) => labels.clone(),
    };
    this.push(Rc::new(RefCell::new(InputElement(proto::Element {
        width_config,
        has_one_shot_effect: set_value.then_some(true),
        r#type: Some(element::Type::ButtonGroup(proto::ButtonGroup {
            id,
            options: options.options.iter().map(|label| button_group_option(label)).collect(),
            default: default_indices,
            disabled: c.disabled,
            click_mode: if multi { proto::button_group::ClickMode::MultiSelect as i32 } else { proto::button_group::ClickMode::SingleSelect as i32 },
            form_id,
            set_value,
            style: style as i32,
            label: c.label,
            label_visibility: c.visibility.wire(),
            help: if c.help.is_empty() { None } else { Some(c.help) },
            raw_values: if set_value { raw_values } else { Default::default() },
            required: options.required,
            ignore_rerun: c.ignore_rerun,
            ..Default::default()
        })),
        ..Default::default()
    }))));
    Ok(selected)
}

/// The reference's transformed format function: a leading material icon or
/// emoji travels as its own wire field instead of label text.
fn button_group_option(label: &str) -> proto::button_group::Option {
    let mut parts = label.splitn(2, ' ');
    let first = parts.next().unwrap_or_default();
    let rest = parts.next().unwrap_or_default();
    let is_material = first.starts_with(":material/") && first.ends_with(':') && first.len() > ":material/:".len();
    let is_emoji = !is_material && first.chars().count() == 1 && !first.is_ascii();
    if (is_material || is_emoji) && rest.chars().any(|character| !character.is_whitespace()) {
        let content = rest.trim_start().to_string();
        let content = if content.is_empty() { String::new() } else { content };
        return proto::button_group::Option { content, content_icon: Some(first.to_string()) };
    }
    proto::button_group::Option { content: label.to_string(), content_icon: None }
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
    fn input(receiver: &mut tokio::sync::mpsc::UnboundedReceiver<ForwardMsg>) -> anyhow::Result<element::Type> {
        match receiver.try_recv()?.r#type {
            Some(forward_msg::Type::Delta(proto::Delta {
                r#type: Some(delta::Type::NewElement(element)), ..
            })) => element.r#type.ok_or_else(|| anyhow::anyhow!("new widget element must contain its type")),
            other => panic!("expected input, got {other:?}"),
        }
    }

    fn form_block(receiver: &mut tokio::sync::mpsc::UnboundedReceiver<ForwardMsg>) -> anyhow::Result<proto::Block> {
        match receiver.try_recv()?.r#type {
            Some(forward_msg::Type::Delta(proto::Delta { r#type: Some(delta::Type::AddBlock(block)), .. })) => Ok(block),
            other => panic!("expected form block, got {other:?}"),
        }
    }

    #[test]
    fn form_text_core_matches_reference_and_callbacks_see_batch_first() -> anyhow::Result<()> {
        let state = SessionState::default();
        state.begin_widgets(vec![]);
        let (st, mut wire) = app(&state);
        let callback = |st: &Streamlit| {
            let state = st.session_state();
            assert!(matches!(state.get::<String>("default_note"), Ok(Some(value)) if value == "hello"));
            assert!(matches!(state.get::<bool>("default_agree"), Ok(Some(true))));
            assert!(state.set("callback_ran", true).is_ok());
        };
        let (note, agree, submitted) = st.form(FormOptions::new("default_form"), |form| {
            let note = form.text_input(TextInputOptions::new("Note").key("default_note"))?;
            let agree = form.checkbox(CheckboxOptions::new("Agree").key("default_agree"))?;
            let submitted = form.form_submit_button(FormSubmitButtonOptions::new("Apply").key("default_apply").on_click(callback))?;
            Ok((note, agree, submitted))
        })?;
        assert_eq!((note.as_deref(), agree, submitted), (Some(""), false, false));
        let block = form_block(&mut wire)?;
        let Some(proto::block::Type::Form(form)) = block.r#type else { panic!() };
        assert_eq!((form.form_id.as_str(), form.clear_on_submit, form.border, form.enter_to_submit), ("default_form", false, true, true));
        assert_eq!(block.width_config.map(|width| width.width_spec), Some(Some(proto::streamlit::width_config::WidthSpec::UseStretch(true))));
        assert_eq!(block.height_config.map(|height| height.height_spec), Some(Some(proto::streamlit::height_config::HeightSpec::UseContent(true))));
        let element::Type::TextInput(text) = input(&mut wire)? else { panic!() };
        assert!(text.id.ends_with("-default_note"));
        assert_eq!((text.label.as_str(), text.default.as_deref(), text.form_id.as_str(), text.r#type), ("Note", Some(""), "default_form", 0));
        let element::Type::Checkbox(check) = input(&mut wire)? else { panic!() };
        assert_eq!((check.form_id.as_str(), check.default, check.disabled), ("default_form", false, false));
        let element::Type::Button(button) = input(&mut wire)? else { panic!() };
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
        assert_eq!(state.get::<bool>("callback_ran")?, Some(true));
        let (note, agree, submitted) = st.form(FormOptions::new("default_form"), |form| {
            let note = form.text_input(TextInputOptions::new("Note").key("default_note"))?;
            let agree = form.checkbox(CheckboxOptions::new("Agree").key("default_agree"))?;
            let submitted = form.form_submit_button(FormSubmitButtonOptions::new("Apply").key("default_apply"))?;
            Ok((note, agree, submitted))
        })?;
        let block = form_block(&mut wire)?;
        let Some(proto::block::Type::Form(form)) = block.r#type else { panic!() };
        assert_eq!(form.form_id, "default_form");
        let element::Type::TextInput(_) = input(&mut wire)? else { panic!() };
        let element::Type::Checkbox(_) = input(&mut wire)? else { panic!() };
        let element::Type::Button(_) = input(&mut wire)? else { panic!() };
        assert_eq!((note.as_deref(), agree, submitted), (Some("hello"), true, true));
        state.finish_widgets();
        state.begin_widgets(vec![]);
        let (st, _) = app(&state);
        let submitted = st.form(FormOptions::new("default_form"), |form| form.form_submit_button(FormSubmitButtonOptions::new("Apply").key("default_apply")))?;
        assert!(!submitted, "submit triggers reset after a completed run");

        Ok(())
    }

    #[test]
    fn forms_render_in_containers_and_containers_render_in_forms() -> anyhow::Result<()> {
        let state = SessionState::default();
        state.begin_widgets(vec![]);
        let (st, mut wire) = app(&state);
        let container = st.container();
        container.form(FormOptions::new("outside_form"), |form| {
            form.text_input(TextInputOptions::new("Note").key("outside_note"))?;
            form.form_submit_button(FormSubmitButtonOptions::new("Apply").key("outside_apply"))
        })?;
        assert!(matches!(form_block(&mut wire)?.r#type, Some(proto::block::Type::FlexContainer(_))));
        assert!(matches!(form_block(&mut wire)?.r#type, Some(proto::block::Type::Form(_))));
        let element::Type::TextInput(text) = input(&mut wire)? else { panic!() };
        assert_eq!(text.form_id, "outside_form");
        let element::Type::Button(button) = input(&mut wire)? else { panic!() };
        assert!(button.is_form_submitter);

        let columns = st.columns(2);
        columns[0].form(FormOptions::new("column_form"), |form| {
            form.text_input(TextInputOptions::new("Note").key("column_note"))?;
            form.form_submit_button(FormSubmitButtonOptions::new("Apply").key("column_apply"))
        })?;
        assert!(matches!(form_block(&mut wire)?.r#type, Some(proto::block::Type::FlexContainer(_))));
        assert!(matches!(form_block(&mut wire)?.r#type, Some(proto::block::Type::Column(_))));
        assert!(matches!(form_block(&mut wire)?.r#type, Some(proto::block::Type::Column(_))));
        assert!(matches!(form_block(&mut wire)?.r#type, Some(proto::block::Type::Form(_))));
        let element::Type::TextInput(column_text) = input(&mut wire)? else { panic!() };
        assert_eq!(column_text.form_id, "column_form");
        let element::Type::Button(column_button) = input(&mut wire)? else { panic!() };
        assert!(column_button.is_form_submitter);

        st.form(FormOptions::new("inside_form"), |form| {
            let container = form.container();
            container.text_input(TextInputOptions::new("Note").key("inside_note"))?;
            form.form_submit_button(FormSubmitButtonOptions::new("Apply").key("inside_apply"))
        })?;
        assert!(matches!(form_block(&mut wire)?.r#type, Some(proto::block::Type::Form(_))));
        assert!(matches!(form_block(&mut wire)?.r#type, Some(proto::block::Type::FlexContainer(_))));
        let element::Type::TextInput(text) = input(&mut wire)? else { panic!() };
        assert_eq!(text.form_id, "inside_form");
        let element::Type::Button(button) = input(&mut wire)? else { panic!() };
        assert!(button.is_form_submitter);

        Ok(())
    }

    #[test]
    fn forms_need_submits_and_form_keys_share_widget_spelling() -> anyhow::Result<()> {
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
        assert_eq!(st.text_input(TextInputOptions::new("Shared").key("shared"))?, Some(String::new()));
        st.form(FormOptions::new("shared"), |form| form.form_submit_button("Submit"))?;
        assert!(wire.try_recv().is_ok());

        Ok(())
    }

    #[test]
    fn forms_anonymous_identity_is_scoped_but_explicit_widget_keys_are_global() -> anyhow::Result<()> {
        let state = SessionState::default();
        state.begin_widgets(vec![]);
        let (st, mut wire) = app(&state);
        for key in ["a", "b"] {
            st.form(key, |form| {
                form.text_input("Note")?;
                form.form_submit_button("Apply")
            })?;
        }
        let mut ids = std::collections::HashSet::new();
        for _ in 0..2 {
            form_block(&mut wire)?;
            let element::Type::TextInput(text) = input(&mut wire)? else { panic!() };
            assert!(ids.insert(text.id));
            let element::Type::Button(button) = input(&mut wire)? else { panic!() };
            assert!(ids.insert(button.id));
        }
        assert!(wire.try_recv().is_err());
        st.form("same", |form| {
            form.text_input(TextInputOptions::new("Note").key("same"))?;
            form.form_submit_button("Submit")
        })?;
        // The duplicate key takes over the run like upstream: the exception
        // element renders, later output is suppressed and the caller receives
        // the default it requested instead of an error (measured dup_key
        // reference wire; text_input's default is the empty string).
        assert_eq!(st.text_input(TextInputOptions::new("Root").key("same"))?, Some(String::new()));
        assert_eq!(state.run_control(), Some(crate::session::RunControl::Stop));
        let _ = form_block(&mut wire)?;
        match input(&mut wire)? {
            element::Type::TextInput(text) => assert_eq!(text.label, "Note"),
            other => panic!("expected the form text input before the exception, got {other:?}"),
        }
        let _ = input(&mut wire)?; // the form submit button
        match input(&mut wire)? {
            element::Type::Exception(exception) => {
                assert_eq!(exception.r#type, "streamlit.errors.StreamlitDuplicateElementKey");
                assert!(exception.message.contains("key='same'"));
                assert!(exception.is_streamlit_exception && exception.message_is_markdown);
                assert_eq!(exception.stack_trace.len(), 1);
            }
            other => panic!("expected the duplicate-key exception element, got {other:?}"),
        }
        assert!(wire.try_recv().is_err());

        Ok(())
    }

    #[test]
    fn forms_abort_rolls_back_registration_and_widget_values() -> anyhow::Result<()> {
        let state = SessionState::default();
        state.begin_widgets(vec![]);
        state.set("shared", "seed")?;
        let (st, mut wire) = app(&state);
        let result = st.form("retry", |form| {
            form.text_input(TextInputOptions::new("Hidden").key("shared"))?;
            form.form_submit_button(FormSubmitButtonOptions::new("Discard").key("discard"))?;
            Err::<(), _>(WidgetError::InvalidValue("abort".into()))
        });
        assert!(result.is_err());
        assert!(wire.try_recv().is_err());
        assert_eq!(state.get::<String>("shared")?.as_deref(), Some("seed"));
        assert_eq!(state.get::<bool>("discard")?, None);
        st.form("retry", |form| {
            form.text_input(TextInputOptions::new("Visible").key("shared"))?;
            form.form_submit_button(FormSubmitButtonOptions::new("Keep").key("discard"))
        })?;
        assert_eq!(state.get::<bool>("discard")?, Some(false));

        Ok(())
    }

    #[test]
    fn forms_live_duration_milliseconds_and_seconds_share_limits() -> anyhow::Result<()> {
        for (duration, milliseconds) in [("250ms", 250), ("0.25s", 250), ("1ms", 1), ("0", 0), ("60s", 60_000)] {
            assert_eq!(TextLive::parse_duration(duration)?, TextLive::Debounce(milliseconds));
        }
        for duration in ["60001ms", "60.001s", "-1ms", "NaNms", "infms", "250"] {
            assert!(TextLive::parse_duration(duration).is_err(), "{duration}");
        }

        Ok(())
    }

    #[test]
    fn forms_overlong_text_is_truncated_before_submit_callback() -> anyhow::Result<()> {
        let state = SessionState::default();
        state.begin_widgets(vec![]);
        let (st, mut wire) = app(&state);
        st.form("bounded", |form| {
            form.text_input(TextInputOptions::new("Bounded").key("bounded").max_chars(5))?;
            form.checkbox(CheckboxOptions::new("Agree").key("agree"))?;
            form.form_submit_button(FormSubmitButtonOptions::new("Apply").key("apply").on_click(|st| {
                assert!(matches!(st.session_state().get::<String>("bounded"), Ok(Some(value)) if value == "TOOLO"));
                st.write("submit callback");
            }))
        })?;
        form_block(&mut wire)?;
        let element::Type::TextInput(text) = input(&mut wire)? else { panic!() };
        let element::Type::Checkbox(check) = input(&mut wire)? else { panic!() };
        let element::Type::Button(button) = input(&mut wire)? else { panic!() };
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
        assert_eq!(callbacks.len(), 1);
        assert_eq!(state.get::<String>("bounded")?.as_deref(), Some("TOOLO"));
        assert_eq!(state.get::<bool>("agree")?, Some(true));
        assert_eq!(state.get::<bool>("apply")?, Some(true));
        let (st, mut wire) = app(&state);
        for callback in callbacks {
            callback(&st);
        }
        assert!(matches!(input(&mut wire)?, element::Type::Markdown(markdown) if markdown.body == "submit callback"));

        Ok(())
    }

    #[test]
    fn keyed_text_area_resets_for_limit_changes_but_keeps_default_only_edits() -> anyhow::Result<()> {
        let state = SessionState::default();
        let render = |limit, none| -> anyhow::Result<(String, Option<String>)> {
            let (st, mut wire) = app(&state);
            let mut options = TextAreaOptions::new("Area", "abcdef").key("area").max_chars(limit);
            if none {
                options = options.value_none();
            }
            let value = st.text_area(options)?;
            let element::Type::TextArea(widget) = input(&mut wire)? else { anyhow::bail!("expected text area") };
            Ok((widget.id, value))
        };

        // 1. 同一上限保留前端值和身份。
        state.begin_widgets(vec![]);
        let (first, value) = render(5, false)?;
        assert_eq!(value.as_deref(), Some("abcde"));
        state.finish_widgets();
        state.begin_widgets(vec![WidgetState {
            id: first.clone(),
            value: Some(widget_state::Value::StringValue("edit!".into())),
        }]);
        let (same, value) = render(5, false)?;
        assert_eq!(same, first);
        assert_eq!(value.as_deref(), Some("edit!"));
        state.finish_widgets();

        // 2. 上限变化回到新默认值，仅改默认值不重置；回到旧上限也不复活旧输入。
        state.begin_widgets(vec![]);
        let (short, value) = render(3, false)?;
        assert_ne!(short, first);
        assert_eq!(value.as_deref(), Some("abc"));
        state.finish_widgets();
        state.begin_widgets(vec![]);
        let (same, value) = render(3, true)?;
        assert_eq!(same, short);
        assert_eq!(value.as_deref(), Some("abc"));
        state.finish_widgets();
        state.begin_widgets(vec![]);
        let (restored, value) = render(5, false)?;
        assert_eq!(restored, first);
        assert_eq!(value.as_deref(), Some("abcde"));
        state.finish_widgets();
        Ok(())
    }

    #[test]
    fn code_assigned_text_survives_same_run_limit_identity_change() -> anyhow::Result<()> {
        for area in [false, true] {
            let state = SessionState::default();
            let render = |limit| -> anyhow::Result<(String, Option<String>, bool, Option<String>)> {
                let (st, mut wire) = app(&state);
                let value = if area {
                    st.text_area(TextAreaOptions::new("Text", "abcdef").key("text").max_chars(limit))?
                } else {
                    st.text_input(TextInputOptions::new("Text").value("abcdef").key("text").max_chars(limit))?
                };
                match input(&mut wire)? {
                    element::Type::TextInput(widget) => Ok((widget.id, value, widget.set_value, widget.value)),
                    element::Type::TextArea(widget) => Ok((widget.id, value, widget.set_value, widget.value)),
                    _ => anyhow::bail!("expected text widget"),
                }
            };

            // 1. 新输入先按原上限应用，再由代码赋值并切换到新上限。
            state.begin_widgets(vec![]);
            let (first, value, _, _) = render(5)?;
            assert_eq!(value.as_deref(), Some("abcde"));
            state.finish_widgets();
            state.begin_widgets(vec![WidgetState {
                id: first.clone(),
                value: Some(widget_state::Value::StringValue("ABCDEF".into())),
            }]);
            assert_eq!(state.get::<String>("text")?.as_deref(), Some("ABCDE"));
            state.set("text", "code長🧊extra")?;
            let (second, value, set, wire_value) = render(0)?;
            assert_ne!(first, second);
            assert_eq!(value.as_deref(), Some("code長🧊extra"));
            assert!(set);
            assert_eq!(wire_value, value);
            state.finish_widgets();

            // 2. 无新输入时保留代码值，不再发送一次性同步标记。
            state.begin_widgets(vec![]);
            let (same, value, set, wire_value) = render(0)?;
            assert_eq!(same, second);
            assert_eq!(value.as_deref(), Some("code長🧊extra"));
            assert!(!set);
            assert!(wire_value.is_none());
            state.finish_widgets();
        }
        Ok(())
    }

    #[test]
    fn input_width_error_preserves_registered_binding_and_published_url() -> anyhow::Result<()> {
        for width in [i32::MIN, -1, 0] {
            let state = SessionState::default();
            state.query_params.lock().load("bound=LONGURL&marker=kept");
            state.begin_widgets(vec![]);
            let (st, mut wire) = app(&state);
            let error = st
                .text_input(TextInputOptions::new("Bound").value("base").key("bound").max_chars(5).bind(TextBind::QueryParams).width(width))
                .err()
                .ok_or_else(|| anyhow::anyhow!("nonpositive width must fail"))?;
            let WidgetError::InvalidValue(message) = error else { anyhow::bail!("expected existing invalid-value variant") };
            assert_eq!(message, format!("Invalid width value: {width}. Width must be either a positive integer (pixels) or 'stretch'."));
            assert_eq!(state.get::<String>("bound")?.as_deref(), Some("LONGU"));
            assert!(state.set("bound", "blocked").is_err());
            assert!(st.query_params().set("bound", "blocked").is_err());
            let Some(forward_msg::Type::PageInfoChanged(info)) = wire.try_recv()?.r#type else {
                anyhow::bail!("expected URL correction before failed widget")
            };
            assert_eq!(info.query_string, "bound=LONGU&marker=kept");
            assert!(wire.try_recv().is_err(), "width error must not emit the widget");
            state.finish_widgets();

            state.query_params.lock().load("bound=LONGU&marker=kept");
            state.begin_widgets(vec![]);
            let (st, mut wire) = app(&state);
            assert_eq!(st.text_input(TextInputOptions::new("Bound").value("base").key("bound").max_chars(5).bind(TextBind::QueryParams).width(320))?.as_deref(), Some("LONGU"));
            assert!(matches!(input(&mut wire)?, element::Type::TextInput(_)));
            state.finish_widgets();
        }
        Ok(())
    }

    #[test]
    fn area_width_error_keeps_registration_and_precedes_height() -> anyhow::Result<()> {
        for width in [i32::MIN, -1, 0] {
            let state = SessionState::default();
            state.begin_widgets(vec![]);
            let (st, mut wire) = app(&state);
            st.text_area(TextAreaOptions::new("Area", "base").key("area").max_chars(5).width(320).height(122))?;
            let element::Type::TextArea(widget) = input(&mut wire)? else { anyhow::bail!("expected text area") };
            state.finish_widgets();

            state.begin_widgets(vec![WidgetState {
                id: widget.id,
                value: Some(widget_state::Value::StringValue("EDITEDtail".into())),
            }]);
            let (st, mut wire) = app(&state);
            let error = st
                .text_area(TextAreaOptions::new("Area", "base").key("area").max_chars(5).width(width).height(0))
                .err()
                .ok_or_else(|| anyhow::anyhow!("nonpositive width must fail"))?;
            let WidgetError::InvalidValue(message) = error else { anyhow::bail!("expected existing invalid-value variant") };
            assert_eq!(message, format!("Invalid width value: {width}. Width must be either a positive integer (pixels) or 'stretch'."));
            assert!(wire.try_recv().is_err());
            assert_eq!(state.get::<String>("area")?.as_deref(), Some("EDITE"));
            assert!(state.set("area", "blocked").is_err());
            state.finish_widgets();

            state.begin_widgets(vec![]);
            let (st, mut wire) = app(&state);
            assert_eq!(st.text_area(TextAreaOptions::new("Area", "base").key("area").max_chars(5).width(320).height(122))?.as_deref(), Some("EDITE"));
            assert!(matches!(input(&mut wire)?, element::Type::TextArea(_)));
            state.finish_widgets();
        }
        Ok(())
    }

    #[test]
    fn area_height_error_keeps_registration_and_caller_recovery() -> anyhow::Result<()> {
        for height in [i32::MIN, -1, 0] {
            let state = SessionState::default();
            state.begin_widgets(vec![]);
            let (st, mut wire) = app(&state);
            st.text_area(TextAreaOptions::new("Area", "base").key("area").max_chars(5).height(122))?;
            let element::Type::TextArea(widget) = input(&mut wire)? else { anyhow::bail!("expected text area") };
            state.finish_widgets();

            state.begin_widgets(vec![WidgetState {
                id: widget.id,
                value: Some(widget_state::Value::StringValue("EDITEDtail".into())),
            }]);
            let (st, mut wire) = app(&state);
            let error = st
                .text_area(TextAreaOptions::new("Area", "base").key("area").max_chars(5).height(height))
                .err()
                .ok_or_else(|| anyhow::anyhow!("nonpositive height must fail"))?;
            let WidgetError::InvalidValue(message) = error else { anyhow::bail!("expected existing invalid-value variant") };
            assert_eq!(message, format!("Invalid height value: {height}. Height must be either a positive integer (pixels), 'stretch', or 'content'."));
            assert!(wire.try_recv().is_err(), "failed height must not emit an element");
            assert_eq!(state.get::<String>("area")?.as_deref(), Some("EDITE"));
            assert!(state.set("area", "blocked").is_err());
            state.finish_widgets();

            state.begin_widgets(vec![]);
            let (st, mut wire) = app(&state);
            assert_eq!(st.text_area(TextAreaOptions::new("Area", "base").key("area").max_chars(5).height(122))?.as_deref(), Some("EDITE"));
            assert!(matches!(input(&mut wire)?, element::Type::TextArea(_)));
            state.finish_widgets();
        }
        Ok(())
    }

    #[test]
    fn unkeyed_text_area_identity_uses_raw_height_and_emits_effective_height() -> anyhow::Result<()> {
        let state = SessionState::default();
        let mut identities: Vec<String> = Vec::new();
        for phase in 0..6 {
            let incoming = if matches!(phase, 1 | 4) {
                vec![WidgetState {
                    id: identities[phase - 1].clone(),
                    value: Some(widget_state::Value::StringValue("kept".into())),
                }]
            } else {
                Vec::new()
            };
            state.begin_widgets(incoming);
            let mut options = TextAreaOptions::new("Area", "base");
            if phase == 2 {
                options = options.label_visibility(LabelVisibility::Collapsed);
            } else if matches!(phase, 3 | 4) {
                options = options.height(122);
            }

            let (st, mut wire) = app(&state);
            assert_eq!(st.text_area(options)?.as_deref(), Some(if matches!(phase, 1 | 2 | 4) { "kept" } else { "base" }));
            let Some(forward_msg::Type::Delta(proto::Delta {
                r#type: Some(delta::Type::NewElement(element)), ..
            })) = wire.try_recv()?.r#type
            else {
                anyhow::bail!("expected area element")
            };
            let height = element.height_config.and_then(|config| config.height_spec);
            assert!(matches!(height, Some(proto::streamlit::height_config::HeightSpec::PixelHeight(pixels)) if pixels == if phase == 2 { 94 } else { 122 }));
            let Some(element::Type::TextArea(widget)) = element.r#type else { anyhow::bail!("expected text area") };
            identities.push(widget.id);
            state.finish_widgets();
        }
        assert_eq!(identities[0], identities[1]);
        assert_eq!(identities[0], identities[2]);
        assert_ne!(identities[0], identities[3]);
        assert_eq!(identities[3], identities[4]);
        assert_eq!(identities[0], identities[5]);
        Ok(())
    }

    #[test]
    fn unkeyed_text_policy_changes_preserve_frontend_input_and_identity() -> anyhow::Result<()> {
        let state = SessionState::default();
        let mut identities: Vec<String> = Vec::new();
        for phase in 0..6 {
            let incoming = if phase == 1 {
                vec![WidgetState {
                    id: identities[0].clone(),
                    value: Some(widget_state::Value::StringValue("preserved".into())),
                }]
            } else {
                Vec::new()
            };
            state.begin_widgets(incoming);
            let mut options = TextInputOptions::new("Plain").value("base").disabled(phase == 2);
            if phase == 3 {
                options = options.on_change(|_| panic!("no new input"));
            } else if phase == 4 {
                options = options.ignore_rerun(true);
            } else if phase == 5 {
                options = options.label_visibility(LabelVisibility::Hidden);
            }

            let (st, mut wire) = app(&state);
            assert_eq!(st.text_input(options)?.as_deref(), Some(if phase == 0 { "base" } else { "preserved" }));
            let element::Type::TextInput(widget) = input(&mut wire)? else { anyhow::bail!("expected text input") };
            identities.push(widget.id);
            state.finish_widgets();
        }
        assert!(identities.iter().all(|id| id == &identities[0]));
        Ok(())
    }

    #[test]
    fn keyed_text_type_defaults_do_not_change_identity_or_reset_native_value() -> anyhow::Result<()> {
        let state = SessionState::default();
        let mut identities = Vec::new();
        for kind in [TextInputType::Default, TextInputType::Email, TextInputType::Url, TextInputType::Phone, TextInputType::Search, TextInputType::Password] {
            state.begin_widgets(vec![]);
            if identities.is_empty() {
                state.set("bound", "preserved")?;
            }
            let (st, mut wire) = app(&state);
            assert_eq!(st.text_input(TextInputOptions::new("Bound").value("base").key("bound").input_type(kind))?.as_deref(), Some("preserved"));
            let element::Type::TextInput(widget) = input(&mut wire)? else { anyhow::bail!("expected text input") };
            identities.push(widget.id);
            let (regex, message) = kind.default_validation();
            assert_eq!(widget.validate_regex.as_deref(), regex);
            assert_eq!(widget.validate_message.as_deref(), message);
            state.finish_widgets();
        }
        assert!(identities.iter().all(|id| id == &identities[0]));
        Ok(())
    }

    #[test]
    fn null_text_state_changes_effective_default_without_changing_identity() -> anyhow::Result<()> {
        for area in [false, true] {
            let state = SessionState::default();
            let mut identities = Vec::new();
            for phase in 0..3 {
                state.begin_widgets(vec![]);
                if phase == 0 {
                    state.set("bound", Option::<String>::None)?;
                } else if phase == 2 {
                    state.set("bound", "restored")?;
                }

                let (st, mut wire) = app(&state);
                let value = if area {
                    st.text_area(TextAreaOptions::new("Bound", "abcdef🧊").key("bound").max_chars(5))?
                } else {
                    st.text_input(TextInputOptions::new("Bound").value("abcdef🧊").key("bound").max_chars(5))?
                };
                assert_eq!(value.as_deref(), (phase == 2).then_some("restored"));
                let (id, default, synchronized) = match input(&mut wire)? {
                    element::Type::TextInput(widget) => (widget.id, widget.default, widget.set_value),
                    element::Type::TextArea(widget) => (widget.id, widget.default, widget.set_value),
                    other => anyhow::bail!("expected text widget, got {other:?}"),
                };
                identities.push(id);
                assert_eq!(default.as_deref(), (phase == 2).then_some("abcdef🧊"));
                assert_eq!(synchronized, phase != 1);
                state.finish_widgets();
            }
            assert!(identities.iter().all(|id| id == &identities[0]));
        }
        Ok(())
    }

    #[test]
    fn bound_text_limit_corrects_changed_urls_without_collapsing_unchanged_repeats() -> anyhow::Result<()> {
        let state = SessionState::default();
        state.query_params.lock().load("bound=abcdef&other=kept");
        state.begin_widgets(vec![]);
        let (st, _) = app(&state);
        assert_eq!(st.text_input(TextInputOptions::new("Bound").value("base").key("bound").max_chars(3).bind(TextBind::QueryParams))?.as_deref(), Some("abc"));
        assert_eq!(state.query_params.lock().serialize(), "bound=abc&other=kept");
        state.finish_widgets();

        // 已经规范化的末值不需要重写，重复键及其顺序继续保留。
        state.query_params.lock().load("bound=abc&bound=abc&other=kept");
        state.begin_widgets(vec![]);
        let (st, _) = app(&state);
        assert_eq!(st.text_input(TextInputOptions::new("Bound").value("base").key("bound").max_chars(3).bind(TextBind::QueryParams))?.as_deref(), Some("abc"));
        assert_eq!(state.query_params.lock().serialize(), "bound=abc&bound=abc&other=kept");
        state.finish_widgets();
        Ok(())
    }

    #[test]
    fn history_input_omission_keeps_unbound_and_unknown_inputs() -> anyhow::Result<()> {
        let state = SessionState::default();
        state.begin_widgets(vec![]);
        let (st, mut wire) = app(&state);
        st.text_input(TextInputOptions::new("Bound").value("base").key("bound").bind(TextBind::QueryParams).on_change(|_| panic!("history bound callback")))?;
        st.text_input(TextInputOptions::new("Live").value("ready").key("live").on_change(|st| st.write("live callback")))?;
        let element::Type::TextInput(bound) = input(&mut wire)? else { anyhow::bail!("expected bound input") };
        let element::Type::TextInput(live) = input(&mut wire)? else { anyhow::bail!("expected live input") };
        state.finish_widgets();

        let mut incoming = vec![
            WidgetState {
                id: bound.id,
                value: Some(widget_state::Value::StringValue("old history value".into())),
            },
            WidgetState {
                id: live.id.clone(),
                value: Some(widget_state::Value::StringValue("next".into())),
            },
            WidgetState {
                id: "unknown".into(),
                value: Some(widget_state::Value::StringValue("pending".into())),
            },
        ];
        state.omit_query_bound_inputs(&mut incoming);
        assert_eq!(incoming.iter().map(|widget| widget.id.as_str()).collect::<Vec<_>>(), [live.id.as_str(), "unknown"]);
        let callbacks = state.begin_widgets(incoming);
        assert_eq!(state.get::<String>("bound")?.as_deref(), Some("base"));
        assert_eq!(state.get::<String>("live")?.as_deref(), Some("next"));
        assert_eq!(callbacks.len(), 1);
        let (st, mut wire) = app(&state);
        for callback in callbacks {
            callback(&st);
        }
        assert!(matches!(input(&mut wire)?, element::Type::Markdown(markdown) if markdown.body == "live callback"));
        Ok(())
    }

    #[test]
    fn unkeyed_number_distinguishes_omitted_and_explicit_default_step() -> anyhow::Result<()> {
        let state = SessionState::default();
        state.begin_widgets(vec![]);
        let (st, mut wire) = app(&state);
        st.number_input(NumberInputOptions::new("Number", 4_i64))?;
        let element::Type::NumberInput(initial) = input(&mut wire)? else { panic!() };
        state.finish_widgets();

        state.begin_widgets(vec![WidgetState {
            id: initial.id.clone(),
            value: Some(widget_state::Value::IntValue(7)),
        }]);
        let (st, mut wire) = app(&state);
        assert_eq!(st.number_input(NumberInputOptions::new("Number", 4_i64))?, 7);
        let _ = input(&mut wire)?;
        state.finish_widgets();

        state.begin_widgets(vec![]);
        let (st, mut wire) = app(&state);
        assert_eq!(st.number_input(NumberInputOptions::new("Number", 4_i64).step(1.0))?, 4);
        let element::Type::NumberInput(explicit) = input(&mut wire)? else { panic!() };
        assert_ne!(explicit.id, initial.id);
        assert_eq!(explicit.step, initial.step);
        state.finish_widgets();

        state.begin_widgets(vec![]);
        let (st, mut wire) = app(&state);
        assert_eq!(st.number_input(NumberInputOptions::new("Number", 4_i64))?, 4);
        let element::Type::NumberInput(restored) = input(&mut wire)? else { panic!() };
        assert_eq!(restored.id, initial.id);
        Ok(())
    }

    #[test]
    fn unkeyed_number_preserves_optional_zero_bounds_and_width_identity() -> anyhow::Result<()> {
        let state = SessionState::default();
        state.begin_widgets(vec![]);
        let (st, mut wire) = app(&state);
        let mut ids = Vec::new();

        for options in [
            NumberInputOptions::new("Number", 4_i64),
            NumberInputOptions::new("Number", 4_i64).min(0),
            NumberInputOptions::new("Number", -4_i64),
            NumberInputOptions::new("Number", -4_i64).max(0),
            NumberInputOptions::new("Number", 4_i64).width(360),
        ] {
            st.number_input(options)?;
            let element::Type::NumberInput(number) = input(&mut wire)? else { panic!() };
            assert!(!ids.contains(&number.id));
            ids.push(number.id);
        }

        Ok(())
    }

    #[test]
    fn number_range_reset_preserves_float_values_and_type_errors() -> anyhow::Result<()> {
        let state = SessionState::default();
        state.begin_widgets(vec![]);
        let (st, mut wire) = app(&state);
        st.number_input(NumberInputOptions::new("Float", 9.5_f64).key("float"))?;
        let element::Type::NumberInput(initial) = input(&mut wire)? else { panic!() };
        state.finish_widgets();

        state.begin_widgets(vec![]);
        let (st, mut wire) = app(&state);
        assert_eq!(st.number_input(NumberInputOptions::new("Float", 4.25_f64).key("float").max(6.0))?, 4.25);
        let element::Type::NumberInput(reset) = input(&mut wire)? else { panic!() };
        assert_eq!(reset.id, initial.id);
        assert!(reset.set_value);
        assert_eq!(reset.value, Some(4.25));
        assert_eq!(state.get::<f64>("float")?, Some(4.25));
        state.finish_widgets();

        state.begin_widgets(vec![]);
        state.set("float", "wrong type")?;
        let (st, _) = app(&state);
        assert!(st.number_input(NumberInputOptions::new("Float", 4.25_f64).key("float").max(6.0)).is_err());
        state.set("integer", 1.5_f64)?;
        assert!(st.number_input(NumberInputOptions::new("Integer", 0_i64).key("integer").max(1)).is_err());
        Ok(())
    }

    #[test]
    fn keyed_number_keeps_identity_and_resets_only_outside_new_bounds() -> anyhow::Result<()> {
        let state = SessionState::default();
        state.begin_widgets(vec![]);
        let (st, mut wire) = app(&state);
        st.number_input(NumberInputOptions::new("Number", 4_i64).key("number"))?;
        let element::Type::NumberInput(initial) = input(&mut wire)? else { panic!() };
        state.finish_widgets();

        state.begin_widgets(vec![WidgetState {
            id: initial.id.clone(),
            value: Some(widget_state::Value::IntValue(7)),
        }]);
        let (st, mut wire) = app(&state);
        assert_eq!(st.number_input(NumberInputOptions::new("Number", 4_i64).key("number").max(10))?, 7);
        let element::Type::NumberInput(grown) = input(&mut wire)? else { panic!() };
        assert_eq!(grown.id, initial.id);
        assert!(!grown.set_value);
        state.finish_widgets();

        state.begin_widgets(vec![]);
        let (st, mut wire) = app(&state);
        assert_eq!(st.number_input(NumberInputOptions::new("Number", 4_i64).key("number").max(6))?, 4);
        let element::Type::NumberInput(narrow) = input(&mut wire)? else { panic!() };
        assert_eq!(narrow.id, initial.id);
        assert_eq!(narrow.value, Some(4.0));
        assert!(narrow.set_value);
        assert_eq!(state.get::<i64>("number")?, Some(4));
        assert!(state.set("number", 5_i64).is_err());
        state.finish_widgets();

        state.begin_widgets(vec![]);
        let (st, mut wire) = app(&state);
        assert_eq!(st.number_input(NumberInputOptions::new("Number", 5_i64).key("number").step(2.0))?, 4);
        let element::Type::NumberInput(restored) = input(&mut wire)? else { panic!() };
        assert_eq!(restored.id, initial.id);
        assert!(!restored.set_value);
        Ok(())
    }

    #[test]
    fn number_input_equal_bounds_and_nonpositive_steps_match_reference() -> anyhow::Result<()> {
        fn check<T: NumberValue>(label: &str, value: T, low: Option<T>, high: Option<T>, step: f64) -> anyhow::Result<()> {
            let state = SessionState::default();
            state.begin_widgets(vec![]);
            let (st, mut wire) = app(&state);
            let mut options = NumberInputOptions::new(label, value).key("number").step(step);
            if let Some(low) = low {
                options = options.min(low);
            }
            if let Some(high) = high {
                options = options.max(high);
            }

            assert_eq!(st.number_input(options)?.to_value(), value.to_value(), "{label}");
            assert_eq!(state.get::<T>("number")?.map(T::to_value), Some(value.to_value()));
            let element::Type::NumberInput(number) = input(&mut wire)? else { panic!() };
            assert_eq!(number.default, Some(value.to_f64()));
            assert_eq!(number.step, step);
            assert_eq!(number.data_type, i32::from(!T::INTEGER));
            assert_eq!((number.has_min, number.has_max), (low.is_some(), high.is_some()));
            if let (Some(low), Some(high)) = (low, high) {
                assert_eq!((number.min, number.max), (low.to_f64(), high.to_f64()));
            }
            assert!(!number.set_value);
            Ok(())
        }

        for (label, value, low, high, step) in [("Int equal", 2_i64, Some(2), Some(2), 1.0), ("Int zero step", 4, None, None, 0.0), ("Int negative step", 4, None, None, -2.0)] {
            check(label, value, low, high, step)?;
        }

        for (label, value, low, high, step) in [("Float equal", 2.5_f64, Some(2.5), Some(2.5), 0.25), ("Float zero step", 1.5, None, None, 0.0), ("Float negative step", 1.5, None, None, -0.25)] {
            check(label, value, low, high, step)?;
        }
        Ok(())
    }

    #[test]
    fn number_input_integer_unset_bounds_match_sdk_sentinels() -> anyhow::Result<()> {
        let state = SessionState::default();
        state.begin_widgets(vec![]);
        let (st, mut wire) = app(&state);
        let safe = 9_007_199_254_740_991_i64;

        for (label, low, high, value) in [
            ("free", None, None, 4),
            ("min", Some(2), None, 4),
            ("max", None, Some(8), 4),
            ("zero min", Some(0), None, 4),
            ("zero max", None, Some(0), -4),
            ("safe high", None, None, safe),
            ("safe low", None, None, -safe),
        ] {
            let mut options = NumberInputOptions::new(label, value);
            if let Some(low) = low {
                options = options.min(low);
            }
            if let Some(high) = high {
                options = options.max(high);
            }

            assert_eq!(st.number_input(options)?, value);
            let element::Type::NumberInput(number) = input(&mut wire)? else { panic!() };
            assert_eq!((number.min, number.max), (low.unwrap_or(-safe) as f64, high.unwrap_or(safe) as f64), "{label}");
            assert_eq!((number.has_min, number.has_max), (low.is_some(), high.is_some()));
            assert_eq!(number.default, Some(value as f64));
            assert_eq!(number.data_type, 0);
            assert_eq!(number.step, 1.0);
        }

        Ok(())
    }

    #[test]
    fn text_input_none_and_empty_are_distinct_wire_and_native_values() -> anyhow::Result<()> {
        let state = SessionState::default();
        state.begin_widgets(vec![]);
        let (st, mut wire) = app(&state);
        assert_eq!(st.text_input(TextInputOptions::new("None value").value_none().key("none_value"))?, None);
        let element::Type::TextInput(none) = input(&mut wire)? else { panic!() };
        assert_eq!(none.default, None);
        assert_eq!(st.text_input(TextInputOptions::new("Empty value").key("empty_value"))?, Some(String::new()));
        let element::Type::TextInput(empty) = input(&mut wire)? else { panic!() };
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
        assert_eq!(st.text_input(TextInputOptions::new("None value").value_none().key("none_value"))?, Some("x".into()));
        assert_eq!(st.text_input(TextInputOptions::new("Empty value").key("empty_value"))?, Some(String::new()));

        Ok(())
    }

    #[test]
    fn text_input_advanced_fields_match_the_pinned_reference() -> anyhow::Result<()> {
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
            assert_eq!(st.text_input(options)?, Some(String::new()));
            let element::Type::TextInput(text) = input(&mut wire)? else { panic!() };
            assert_eq!(text.r#type, wire_type as i32);
        }
        // Rewind one frame at a time is awkward; use independent receivers below
        // only when a field assertion needs the whole Element. The five IDs and
        // scalar fields above establish that every specialized type registered.
        state.finish_widgets();

        Ok(())
    }

    #[test]
    fn text_input_advanced_defaults_and_overrides_match_wire_fields() -> anyhow::Result<()> {
        let field = |st: &Streamlit, options: TextInputOptions| -> anyhow::Result<proto::TextInput> {
            let (sender, mut receiver) = tokio::sync::mpsc::unbounded_channel();
            st.app.lock().set_render_context(RenderContext::with_sender("field".into(), sender));
            st.text_input(options)?;
            let element::Type::TextInput(text) = input(&mut receiver)? else { panic!() };
            Ok(text)
        };
        let st = Streamlit::new();
        let email = field(&st, TextInputOptions::new("Email").input_type(TextInputType::Email).key("email"))?;
        assert_eq!(email.autocomplete, "email");
        assert_eq!(email.icon, ":material/mail:");
        assert_eq!(email.placeholder, "you@example.com");
        assert_eq!(email.validate_regex.as_deref(), Some(r"^[^\s@]+@[^\s@]+\.[^\s@]+$"));
        assert_eq!(email.validate_message.as_deref(), Some("Enter a valid email address."));
        let url = field(&st, TextInputOptions::new("URL").input_type(TextInputType::Url).key("url"))?;
        assert_eq!((url.autocomplete.as_str(), url.icon.as_str(), url.placeholder.as_str()), ("url", ":material/link:", "https://example.com"));
        assert_eq!(url.validate_regex.as_deref(), Some(r"^([Hh][Tt][Tt][Pp][Ss]?://)?[^\s/.]+\.[^\s]+$"));
        assert_eq!(url.validate_message.as_deref(), Some("Enter a valid URL."));
        let phone = field(&st, TextInputOptions::new("Phone").input_type(TextInputType::Phone).key("phone"))?;
        assert_eq!((phone.autocomplete.as_str(), phone.icon.as_str(), phone.placeholder.as_str()), ("tel", ":material/call:", "+1 234 567 8900"));
        assert!(phone.validate_regex.is_none() && phone.validate_message.is_none());
        let search = field(&st, TextInputOptions::new("Search").input_type(TextInputType::Search).key("search"))?;
        assert_eq!((search.autocomplete.as_str(), search.icon.as_str(), search.placeholder.as_str()), ("off", ":material/search:", "Search"));
        let password = field(&st, TextInputOptions::new("Secret").input_type(TextInputType::Password).key("password"))?;
        assert_eq!(password.autocomplete, "new-password");
        assert!(password.icon.is_empty() && password.placeholder.is_empty());

        let live = field(&st, TextInputOptions::new("Digits").key("digits").validate_with_message(r"^\d+$", "digits only").live(true))?;
        assert_eq!(live.live_debounce_ms, Some(250));
        assert_eq!(live.validate_regex.as_deref(), Some(r"^\d+$"));
        assert_eq!(live.validate_message.as_deref(), Some("digits only"));
        let required = field(&st, TextInputOptions::new("Required").key("required").required(true).placeholder("type here"))?;
        assert!(required.required && required.placeholder == "type here");
        let disabled = field(&st, TextInputOptions::new("Disabled").key("disabled").disabled(true).value("fixed"))?;
        assert!(disabled.disabled && disabled.default.as_deref() == Some("fixed"));
        let cjk = field(&st, TextInputOptions::new("中文").key("cjk").max_chars(5))?;
        assert_eq!(cjk.max_chars, 5);
        let half_second = field(&st, TextInputOptions::new("Search").key("half_second").live_duration("0.5s"))?;
        assert_eq!(half_second.live_debounce_ms, Some(500));
        let zero = field(&st, TextInputOptions::new("Zero").key("zero").live_duration("0"))?;
        assert_eq!(zero.live_debounce_ms, Some(0));
        assert!(st.text_input(TextInputOptions::new("Bad live").key("bad_live").live_duration("300")).is_err(), "a nonzero bare number is not a documented duration");
        assert!(st.text_input(TextInputOptions::new("Too slow").key("too_slow").live_debounce_ms(60_001)).is_err());
        assert!(st.text_input(TextInputOptions::new("Bound").key("bound").bind(TextBind::QueryParams).input_type(TextInputType::Password)).is_err());

        Ok(())
    }

    #[test]
    fn form_flags_and_multiple_or_disabled_submits_match_reference() -> anyhow::Result<()> {
        let state = SessionState::default();
        state.begin_widgets(vec![]);
        let (st, mut wire) = app(&state);
        st.form(FormOptions::new("clear_true_form").clear_on_submit(true), |form| {
            form.text_input(TextInputOptions::new("Note").key("note"))?;
            form.form_submit_button(FormSubmitButtonOptions::new("Apply").key("clear_apply"))
        })?;
        let block = form_block(&mut wire)?;
        let Some(proto::block::Type::Form(form)) = block.r#type else { panic!() };
        assert!(form.clear_on_submit && form.border && form.enter_to_submit);
        let _ = input(&mut wire)?;
        let _ = input(&mut wire)?;

        st.form(FormOptions::new("enter_off_form").enter_to_submit(false), |form| {
            form.text_input(TextInputOptions::new("Note").key("enter_note"))?;
            form.form_submit_button(FormSubmitButtonOptions::new("Apply").key("enter_apply"))
        })?;
        let block = form_block(&mut wire)?;
        let Some(proto::block::Type::Form(form)) = block.r#type else { panic!() };
        assert!(!form.clear_on_submit && form.border && !form.enter_to_submit);
        let _ = input(&mut wire)?;
        let _ = input(&mut wire)?;

        st.form(FormOptions::new("first_disabled_form"), |form| {
            form.text_input(TextInputOptions::new("Note").key("disabled_note"))?;
            form.form_submit_button(FormSubmitButtonOptions::new("Disabled").key("disabled").disabled(true))?;
            form.form_submit_button(FormSubmitButtonOptions::new("Apply").key("apply"))
        })?;
        let _ = form_block(&mut wire)?;
        let _ = input(&mut wire)?;
        let element::Type::Button(disabled) = input(&mut wire)? else { panic!() };
        assert!(disabled.disabled && disabled.is_form_submitter);
        let element::Type::Button(enabled) = input(&mut wire)? else { panic!() };
        assert!(!enabled.disabled && enabled.is_form_submitter);

        Ok(())
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
    fn typed_values_and_all_inputs_update_before_callback() -> anyhow::Result<()> {
        let state = SessionState::default();
        state.begin_widgets(vec![]);
        let (st, mut wire) = app(&state);
        assert_eq!(st.selectbox(SelectboxOptions::new("Group by", ["category", "region"]).key("group_by"))?, Some("category"));
        let element::Type::Selectbox(select) = input(&mut wire)? else { panic!() };
        assert!(select.id.ends_with("-group_by"));
        assert_eq!(select.default, Some(0));
        let changed = |st: &Streamlit| {
            let state = st.session_state();
            assert!(matches!(state.get::<String>("group_by"), Ok(Some(value)) if value == "region"));
            assert!(matches!(state.get::<i64>("amount"), Ok(Some(10))));
            assert!(matches!(state.get::<bool>("include"), Ok(Some(false))));
            assert!(state.set("callback_ran", true).is_ok());
        };
        assert_eq!(st.slider(SliderOptions::new("Amount", 0_i64).max(200).step(10).key("amount").on_change(changed))?, 0);
        let element::Type::Slider(slider) = input(&mut wire)? else { panic!() };
        assert_eq!(slider.default, vec![0.0]);
        assert_eq!((slider.data_type, slider.step), (0, 10.0));
        assert!(st.checkbox(CheckboxOptions::new("Include").value(true).key("include"))?);
        let element::Type::Checkbox(check) = input(&mut wire)? else { panic!() };
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
        assert_eq!(state.get::<bool>("callback_ran")?, Some(true));
        assert_eq!(st.slider(SliderOptions::new("Renamed", 50_i64).max(200).step(10).key("amount"))?, 10);
        state.finish_widgets();
        assert_eq!(state.get::<String>("group_by")?, None, "unrendered widget key is cleaned");
        assert_eq!(state.get::<bool>("callback_ran")?, Some(true), "manual application keys survive");

        Ok(())
    }

    #[test]
    fn preseed_key_guards_duplicates_and_trigger_reset() -> anyhow::Result<()> {
        let state = SessionState::default();
        state.set("chosen", 20_i32)?;
        state.begin_widgets(vec![]);
        let (st, mut wire) = app(&state);
        assert_eq!(st.selectbox(SelectboxOptions::new("Numbers", [10, 20]).format_func(|n| format!("option-{n}")).key("chosen"))?, Some(20));
        let element::Type::Selectbox(select) = input(&mut wire)? else { panic!() };
        assert_eq!(select.raw_value.as_deref(), Some("option-20"));
        assert!(select.set_value);
        assert!(state.set("chosen", 10).is_err());
        assert!(!st.try_button(ButtonOptions::new("Pulse").key("pulse").disabled(true))?);
        let element::Type::Button(button) = input(&mut wire)? else { panic!() };
        assert!(button.disabled);
        assert!(state.set("pulse", true).is_err());
        // A duplicated widget key takes over the run the way upstream does:
        // the exception element renders, later output is suppressed and the
        // caller receives the default (measured dup_key reference wire).
        assert!(!st.checkbox(CheckboxOptions::new("Other").key("chosen"))?);
        assert_eq!(state.run_control(), Some(crate::session::RunControl::Stop));
        match input(&mut wire)? {
            element::Type::Exception(exception) => {
                assert_eq!(exception.r#type, "streamlit.errors.StreamlitDuplicateElementKey");
                assert!(exception.message.contains("key='chosen'"));
            }
            other => panic!("expected the duplicate-key exception element, got {other:?}"),
        }
        assert!(wire.try_recv().is_err(), "output after the takeover is suppressed");
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
        assert_eq!(SessionState::default().get::<i32>("chosen")?, None);

        Ok(())
    }

    #[test]
    fn numeric_ranges_empty_selection_and_constraint_reset() -> anyhow::Result<()> {
        let state = SessionState::default();
        state.begin_widgets(vec![]);
        let (st, mut wire) = app(&state);
        assert_eq!(st.slider(SliderOptions::new("Range", (0.2, 0.8)).key("range"))?, (0.2, 0.8));
        let element::Type::Slider(slider) = input(&mut wire)? else { panic!() };
        assert_eq!((slider.data_type, slider.default), (1, vec![0.2, 0.8]));
        assert_eq!(st.selectbox(SelectboxOptions::new("Empty", Vec::<String>::new()))?, None);
        let element::Type::Selectbox(empty) = input(&mut wire)? else { panic!() };
        assert!(empty.disabled);
        assert_eq!(empty.default, None);
        assert!(matches!(st.selectbox(SelectboxOptions::new("Empty", Vec::<String>::new())), Err(WidgetError::DuplicateId(_))));
        assert!(st.slider(SliderOptions::new("Reversed", (8_i32, 2))).is_err());
        assert!(st.slider(SliderOptions::new("Infinite", 0.0).max(f64::INFINITY)).is_err());
        assert!(st.slider(SliderOptions::new("Unsafe int", 0_i64).max(9_007_199_254_740_992.0)).is_err());
        state.finish_widgets();
        state.begin_widgets(vec![]);
        let (st, _) = app(&state);
        assert_eq!(st.slider(SliderOptions::new("Range", (0.1, 0.9)).max(2.0).key("range"))?, (0.1, 0.9));

        Ok(())
    }

    #[test]
    fn float_array_range_and_native_integer_limits() -> anyhow::Result<()> {
        let state = SessionState::default();
        state.begin_widgets(vec![]);
        let (st, mut wire) = app(&state);
        assert_eq!(st.slider(SliderOptions::new("Rate", 0.25).format("percent").key("rate"))?, 0.25);
        let element::Type::Slider(rate) = input(&mut wire)? else { panic!() };
        assert_eq!((rate.min, rate.max, rate.step), (0.0, 1.0, 0.01));
        assert_eq!(rate.format, "percent");
        assert_eq!(st.slider(SliderOptions::new("Array", [2_i32, 8_i32]).key("array"))?, [2, 8]);
        let element::Type::Slider(array) = input(&mut wire)? else { panic!() };
        // Returning an i32 cannot represent these bounds; reject before registration.
        assert!(st.slider(SliderOptions::new("Too wide", 0_i32).max(3_000_000_000.0).key("wide")).is_err());
        assert_eq!(state.get::<i32>("wide")?, None);
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
        assert_eq!(st.slider(SliderOptions::new("Rate", 0.25).format("percent").key("rate"))?, 0.75, "format does not scale the returned value");
        assert_eq!(st.slider(SliderOptions::new("Array", [2_i32, 8_i32]).key("array"))?, [4, 10]);

        Ok(())
    }

    #[test]
    fn deleted_keys_rebind_and_unrendered_widgets_expire() -> anyhow::Result<()> {
        let state = SessionState::default();
        state.set("manual", "keep")?;
        state.begin_widgets(vec![]);
        let (st, _) = app(&state);
        assert!(st.checkbox(CheckboxOptions::new("Checked").value(true).key("checked"))?);
        state.finish_widgets();
        assert_eq!(state.remove("checked"), Some(Value::Bool(true)));
        state.begin_widgets(vec![]);
        let (st, _) = app(&state);
        assert!(st.checkbox(CheckboxOptions::new("Renamed").value(false).key("checked"))?, "deleting a key does not reset an existing widget");
        assert_eq!(state.get::<bool>("checked")?, Some(true));
        state.finish_widgets();
        state.begin_widgets(vec![]);
        state.finish_widgets(); // A run that does not render the checkbox.
        assert_eq!(state.get::<bool>("checked")?, None);
        assert_eq!(state.get::<String>("manual")?.as_deref(), Some("keep"));
        state.begin_widgets(vec![]);
        let (st, _) = app(&state);
        assert!(!st.checkbox(CheckboxOptions::new("Checked").key("checked"))?);

        Ok(())
    }

    #[test]
    fn identity_fields_cannot_alias_through_delimiters() -> anyhow::Result<()> {
        let state = SessionState::default();
        state.begin_widgets(vec![]);
        let (st, mut wire) = app(&state);
        assert!(!st.checkbox(CheckboxOptions::new("a:b").help("c"))?);
        assert!(!st.checkbox(CheckboxOptions::new("a").help("b:c"))?);
        let element::Type::Checkbox(a) = input(&mut wire)? else { panic!() };
        let element::Type::Checkbox(b) = input(&mut wire)? else { panic!() };
        assert_ne!(a.id, b.id, "distinct parameter tuples must not share an automatic ID");

        Ok(())
    }

    #[test]
    fn shorthand_and_advanced_builders_preserve_types_defaults_errors_and_proto() -> anyhow::Result<()> {
        use prost::Message;
        let (short, mut short_wire) = app(&SessionState::default());
        let (advanced, mut advanced_wire) = app(&SessionState::default());

        let checked: bool = short.checkbox(("Include", true))?;
        assert_eq!(checked, advanced.checkbox(CheckboxOptions::new("Include").value(true))?);
        assert_eq!(short.checkbox("Default checkbox")?, advanced.checkbox(CheckboxOptions::new("Default checkbox"))?);
        let selected: Option<&str> = short.selectbox(("Group", ["category", "region"]))?;
        assert_eq!(selected, advanced.selectbox(SelectboxOptions::new("Group", ["category", "region"]))?);
        let selected: Option<i32> = short.selectbox((String::from("Numbers"), vec![1_i32, 2]))?;
        assert_eq!(selected, advanced.selectbox::<i32>(SelectboxOptions::new("Numbers", [1_i32, 2]))?);
        let count: i64 = short.slider(("Count", 0_i64))?;
        assert_eq!(count, advanced.slider::<i64>(SliderOptions::new("Count", 0_i64))?);
        let bounded: i64 = short.slider(("Amount", 20_i64, 10..=200))?;
        assert_eq!(bounded, advanced.slider(SliderOptions::new("Amount", 20_i64).min(10).max(200))?);
        let ratio: f64 = short.slider(("Ratio", 0.25_f64))?;
        assert_eq!(ratio, advanced.slider(SliderOptions::new("Ratio", 0.25_f64))?);
        let range: (i64, i64) = short.slider(("Range", (20_i64, 80_i64)))?;
        assert_eq!(range, advanced.slider(SliderOptions::new("Range", (20_i64, 80_i64)))?);
        let array: [f64; 2] = short.slider(("Array", [0.2_f64, 0.8_f64], 0.0..=1.0))?;
        assert_eq!(array, advanced.slider(SliderOptions::new("Array", [0.2_f64, 0.8_f64]).min(0.0).max(1.0))?);
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

        Ok(())
    }

    #[test]
    fn uploader_matches_csv_reference_and_resolves_native_files_before_callback() -> anyhow::Result<()> {
        use std::io::Read;
        let state = SessionState::default();
        state.begin_widgets(vec![]);
        let (st, mut wire) = app(&state);
        let options = || {
            FileUploaderOptions::new("Upload sales CSV").accepted_types(["csv"]).key("upload").on_change(|st| {
                let Ok(files) = st.session_state().uploaded_files("upload") else { panic!("upload callback must resolve its registered files") };
                assert_eq!(files.len(), 1);
                assert_eq!(files[0].name(), "sales_basic.csv");
                assert!(st.session_state().set("upload_callback", files[0].size()).is_ok());
            })
        };
        assert!(matches!(st.file_uploader(options())?, UploadedFiles::Single(None)));
        let element::Type::FileUploader(uploader) = input(&mut wire)? else { panic!() };
        let reference: Value = serde_json::from_str(include_str!("../../tests/reference/reference-browser/data-loop/upload/trace-data-loop.json"))?;
        let observed = reference["frames"]
            .as_array()
            .ok_or_else(|| anyhow::anyhow!("upload reference must contain a frames array"))?
            .iter()
            .find_map(|frame| frame.pointer("/decoded/delta/element_full/fileUploader"))
            .ok_or_else(|| anyhow::anyhow!("upload reference must contain a fileUploader element"))?;
        assert_eq!(uploader.label, observed["label"]);
        assert_eq!(uploader.r#type, vec![observed["type"][0].as_str().ok_or_else(|| anyhow::anyhow!("reference uploader must declare an accepted file type"))?.to_owned()]);
        assert_eq!(uploader.max_upload_size_mb, observed["maxUploadSizeMb"].as_i64().ok_or_else(|| anyhow::anyhow!("reference uploader must declare maxUploadSizeMb"))? as i32);
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
        assert_eq!(state.get::<u64>("upload_callback")?, Some(bytes.len() as u64));
        let UploadedFiles::Single(Some(mut file)) = st.file_uploader(options())? else { panic!() };
        assert_eq!(file.content_type(), Some("text/csv"));
        let mut received = Vec::new();
        file.read_to_end(&mut received)?;
        assert_eq!(received, bytes);
        state.finish_widgets();
        state.begin_widgets(vec![]);
        let (st, _) = app(&state);
        assert_eq!(st.file_uploader(options())?.as_slice()[0].position(), 0);
        let other = SessionState::default();
        let (st, _) = app(&other);
        assert!(st.file_uploader(options())?.as_slice().is_empty());

        Ok(())
    }

    #[test]
    fn uploader_mode_constraints_and_foreign_file_ids_remain_isolated() -> anyhow::Result<()> {
        let state = SessionState::default();
        let (st, mut wire) = app(&state);
        let options = || FileUploaderOptions::new("Folder").mode(FileUploadMode::Directory).key("folder");
        assert!(matches!(st.file_uploader(options())?, UploadedFiles::Multiple(files) if files.is_empty()));
        let element::Type::FileUploader(uploader) = input(&mut wire)? else { panic!() };
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
        assert!(st.file_uploader(options())?.as_slice().is_empty());
        assert!(st.file_uploader(FileUploaderOptions::new("Bad").max_upload_size_mb(0)).is_err());
        // Directory flags are docs/native coverage; no directory browser PASS.

        Ok(())
    }

    #[test]
    fn temporal_sliders_emit_the_measured_wire_and_keep_microseconds() -> anyhow::Result<()> {
        let state = SessionState::default();
        state.begin_widgets(vec![]);
        let (st, mut wire) = app(&state);
        let date = chrono::NaiveDate::from_ymd_opt(2024, 3, 15).ok_or_else(|| anyhow::anyhow!("invalid temporal slider fixture: chrono::NaiveDate::from_ymd_opt(2024, 3, 15)"))?;
        let time = chrono::NaiveTime::from_hms_micro_opt(12, 30, 7, 123456).ok_or_else(|| anyhow::anyhow!("invalid temporal slider fixture: chrono::NaiveTime::from_hms_micro_opt(12, 30, 7, 123456)"))?;
        let datetime = date.and_hms_micro_opt(12, 30, 7, 123456).ok_or_else(|| anyhow::anyhow!("invalid temporal slider fixture: date.and_hms_micro_opt(12, 30, 7, 123456)"))?;
        assert_eq!(st.slider(SliderOptions::new("date", date).key("date"))?, date);
        let element::Type::Slider(slider) = input(&mut wire)? else { panic!() };
        // Numbers captured from the pinned 1.66.1 reference: value ± 14 days,
        // daily step, DATE enum, and the date-only default format.
        assert_eq!((slider.min, slider.max, slider.step, slider.data_type, slider.format.as_str()), (1709251200000000.0, 1711670400000000.0, 86400000000.0, 3, "YYYY-MM-DD"));
        assert_eq!(slider.default, vec![1710460800000000.0]);
        assert_eq!(st.slider(SliderOptions::new("time", time).key("time"))?, time);
        let element::Type::Slider(slider) = input(&mut wire)? else { panic!() };
        // The full 2000-01-01 day with an off-grid max and a 15-minute step.
        assert_eq!((slider.min, slider.max, slider.step, slider.data_type, slider.format.as_str()), (946684800000000.0, 946771199999999.0, 900000000.0, 4, "HH:mm"));
        assert_eq!(slider.default, vec![946729807123456.0]);
        assert_eq!(st.slider(SliderOptions::new("datetime", datetime).key("datetime"))?, datetime);
        let element::Type::Slider(slider) = input(&mut wire)? else { panic!() };
        // Bounds keep the value's time-of-day and microseconds; DATETIME enum.
        assert_eq!((slider.min, slider.max, slider.step, slider.data_type, slider.format.as_str()), (1709296207123456.0, 1711715407123456.0, 86400000000.0, 2, "YYYY-MM-DD"));
        assert_eq!(slider.default, vec![1710505807123456.0]);
        let pair = (
            chrono::NaiveDate::from_ymd_opt(2024, 3, 10).ok_or_else(|| anyhow::anyhow!("invalid temporal slider fixture: chrono::NaiveDate::from_ymd_opt(2024, 3, 10)"))?,
            chrono::NaiveDate::from_ymd_opt(2024, 3, 20).ok_or_else(|| anyhow::anyhow!("invalid temporal slider fixture: chrono::NaiveDate::from_ymd_opt(2024, 3, 20)"))?,
        );
        assert_eq!(st.slider(SliderOptions::new("date-range", pair).key("date-range"))?, pair);
        let element::Type::Slider(slider) = input(&mut wire)? else { panic!() };
        // A range's default window hangs off the FIRST endpoint alone.
        assert_eq!((slider.min, slider.max), (1708819200000000.0, 1711238400000000.0));
        assert_eq!(slider.default, vec![1710028800000000.0, 1710892800000000.0]);
        state.finish_widgets();

        Ok(())
    }

    #[test]
    fn temporal_slider_states_round_trip_and_out_of_domain_bounds_are_rejected() -> anyhow::Result<()> {
        use chrono::Datelike;
        let state = SessionState::default();
        state.begin_widgets(vec![]);
        let (st, mut wire) = app(&state);
        let time = chrono::NaiveTime::from_hms_micro_opt(12, 30, 7, 123456).ok_or_else(|| anyhow::anyhow!("invalid temporal slider fixture: chrono::NaiveTime::from_hms_micro_opt(12, 30, 7, 123456)"))?;
        let _ = st.slider(SliderOptions::new("time", time).key("time"))?;
        let element::Type::Slider(slider) = input(&mut wire)? else { panic!() };
        state.finish_widgets();
        // The reference's End key lands on the 15-minute grid at 23:45; the
        // returned native value keeps the typed form, not the wire double.
        state.begin_widgets(vec![WidgetState {
            id: slider.id,
            value: Some(widget_state::Value::DoubleArrayValue(proto::DoubleArray { data: vec![946770300000000.0] })),
        }]);
        let (st, _) = app(&state);
        assert_eq!(
            st.slider(SliderOptions::new("time", time).key("time"))?,
            chrono::NaiveTime::from_hms_opt(23, 45, 0).ok_or_else(|| anyhow::anyhow!("invalid temporal slider fixture: chrono::NaiveTime::from_hms_opt(23, 45, 0)"))?
        );
        state.finish_widgets();
        // Dates outside the exactly-representable double range are refused
        // instead of silently losing microseconds.
        let far = chrono::NaiveDate::from_ymd_opt(1500, 1, 1).ok_or_else(|| anyhow::anyhow!("invalid temporal slider fixture: chrono::NaiveDate::from_ymd_opt(1500, 1, 1)"))?;
        assert!(st.slider(SliderOptions::new("past", far)).is_err());
        // Explicit temporal bounds and a chrono step land on the wire unconverted.
        let bounded = st.slider(
            SliderOptions::new("window", far.with_year(2024).ok_or_else(|| anyhow::anyhow!("invalid temporal slider fixture: far.with_year(2024)"))?)
                .min(chrono::NaiveDate::from_ymd_opt(2024, 1, 1).ok_or_else(|| anyhow::anyhow!("invalid temporal slider fixture: chrono::NaiveDate::from_ymd_opt(2024, 1, 1)"))?)
                .max(chrono::NaiveDate::from_ymd_opt(2024, 12, 31).ok_or_else(|| anyhow::anyhow!("invalid temporal slider fixture: chrono::NaiveDate::from_ymd_opt(2024, 12, 31)"))?)
                .step(chrono::TimeDelta::days(7)),
        )?;
        assert_eq!(
            bounded,
            chrono::NaiveDate::from_ymd_opt(2024, 1, 1).ok_or_else(|| anyhow::anyhow!("invalid temporal slider fixture: chrono::NaiveDate::from_ymd_opt(2024, 1, 1)"))?
        );

        Ok(())
    }
}
