use crate::WidgetError;
use crate::elements::App;
use crate::elements::badge::BadgeElement;
use crate::elements::code::CodeElement;
use crate::elements::columns::{Column, ColumnElement};
use crate::elements::common::{Anchor, Divider, Element, ElementHeight, ElementWidth, Gap, HorizontalAlignment, TextAlignment, VerticalAlignment};
use crate::elements::container::{Container, ContainerElement};
pub use crate::elements::form::Form;
use crate::elements::form::{FormElement, validate_form_dimensions};
use crate::elements::markdown::{MarkdownElement, MarkdownElementType};
use crate::elements::status::{StatusElement, status_content};
use crate::elements::title::HeadingElement;
use crate::memory::Allocator;
use parking_lot::Mutex;
use std::cell::RefCell;
use std::rc::Rc;

/// Streamlit Rust API - provides a Python-like Streamlit interface
pub struct Streamlit {
    pub(crate) app: Rc<Mutex<App>>,
    allocator: Allocator,
}

impl Streamlit {
    pub(crate) fn new() -> Self {
        Self {
            app: Rc::new(Mutex::new(App::new())),
            allocator: Allocator::new(),
        }
    }
}

pub(crate) trait AppendChild {
    fn push(&self, element: Rc<RefCell<dyn Element>>);

    fn allocator(&self) -> &Allocator;

    fn get_app(&self) -> Rc<Mutex<App>>;

    fn parent_form_id(&self) -> Option<String> {
        None
    }

    fn next_child_path(&self) -> Vec<u32> {
        self.get_app().lock().render_context_mut().map(|context| context.delta_path.clone()).unwrap_or_default()
    }

    /// Register a widget against the session registry, or take over the run
    /// the way upstream does when the key is already live: the framework
    /// renders the `StreamlitDuplicateElementKey` exception element, every
    /// later element and state write of the run is suppressed, and the run
    /// still finishes `FINISHED_SUCCESSFULLY`. The caller receives its
    /// default value, mirroring upstream code that never runs past the raise.
    fn register_widget_parity<T>(&self, spec: crate::widgets::WidgetSpec<'_>, resolve: impl Fn(&serde_json::Value) -> Result<T, WidgetError>) -> Result<(String, T, bool), WidgetError> {
        let state = self.get_app().lock().session_state.clone();
        let default = spec.default.clone();
        let kind = spec.kind.to_owned();
        match state.register_widget(spec, &resolve) {
            Ok(triple) => Ok(triple),
            Err(WidgetError::DuplicateKey(key)) => {
                self.push(Rc::new(RefCell::new(crate::elements::exception::ExceptionElement::duplicate_key(&kind, &key))));
                state.set_run_control(crate::session::RunControl::Stop);
                let value = resolve(&default)?;
                Ok((String::new(), value, false))
            }
            Err(other) => Err(other),
        }
    }
}

impl AppendChild for Streamlit {
    fn push(&self, element: Rc<RefCell<dyn Element>>) {
        self.app.lock().push(element);
    }

    fn allocator(&self) -> &Allocator {
        &self.allocator
    }

    fn get_app(&self) -> Rc<Mutex<App>> {
        self.app.clone()
    }
}

pub struct WriteOptions {
    body: String,
    unsafe_allow_html: bool,
}

/// Options shared by informational, warning, error, and success messages.
pub struct StatusOptions {
    body: String,
    icon: Option<String>,
    width: StatusWidth,
    title: Option<String>,
}

impl StatusOptions {
    pub fn new(body: impl ToString) -> Self {
        Self {
            body: body.to_string(),
            icon: None,
            width: StatusWidth::Keyword("stretch".to_string()),
            title: None,
        }
    }

    /// Set an empty icon, a Material shortcode, or one Unicode emoji sequence.
    /// The sequence is preserved verbatim; the library's Unicode repertoire
    /// is not a claim of complete acceptance parity with Python 1.66.1.
    pub fn icon(mut self, icon: impl Into<String>) -> Self {
        self.icon = Some(icon.into());
        self
    }

    pub fn width(mut self, width: impl Into<StatusWidth>) -> Self {
        self.width = width.into();
        self
    }

    pub fn title(mut self, title: impl Into<String>) -> Self {
        self.title = Some(title.into());
        self
    }
}

/// Status messages accept `"stretch"` or a positive pixel count.
#[derive(Debug, Clone)]
pub enum StatusWidth {
    Pixels(i32),
    Keyword(String),
}

impl From<i32> for StatusWidth {
    fn from(width: i32) -> Self {
        Self::Pixels(width)
    }
}

impl From<&str> for StatusWidth {
    fn from(width: &str) -> Self {
        Self::Keyword(width.to_string())
    }
}

impl From<String> for StatusWidth {
    fn from(width: String) -> Self {
        Self::Keyword(width)
    }
}

/// Validation fails before an element is appended. Unlike Python, non-string
/// icons are rejected by the Rust type system rather than at runtime.
#[derive(Debug, PartialEq, Eq, thiserror::Error)]
pub enum StatusError {
    #[error("Invalid width value: {0}. Width must be either a positive integer (pixels) or 'stretch'.")]
    InvalidWidth(String),
    #[error("The value \"{0}\" is not a valid emoji. Please use a single emoji.")]
    InvalidIcon(String),
}

impl From<&str> for StatusOptions {
    fn from(body: &str) -> Self {
        Self::new(body)
    }
}

impl From<String> for StatusOptions {
    fn from(body: String) -> Self {
        Self::new(body)
    }
}

impl WriteOptions {
    pub fn new(body: String) -> Self {
        Self { body, unsafe_allow_html: false }
    }

    pub fn unsafe_allow_html(mut self, unsafe_allow_html: bool) -> Self {
        self.unsafe_allow_html = unsafe_allow_html;
        self
    }
}

impl From<String> for WriteOptions {
    fn from(body: String) -> Self {
        Self { body, unsafe_allow_html: false }
    }
}

impl From<&str> for WriteOptions {
    fn from(body: &str) -> Self {
        body.to_string().into()
    }
}

pub struct HeaderOptions {
    body: String,
    anchor: Option<Anchor>,
    help: Option<String>,
    divider: Divider,
    width: ElementWidth,
    text_alignment: TextAlignment,
}

impl HeaderOptions {
    pub fn new<T: ToString>(body: T) -> Self {
        Self {
            body: body.to_string(),
            anchor: None,
            help: None,
            divider: Divider::Bool(false),
            width: ElementWidth::Stretch,
            text_alignment: TextAlignment::Left,
        }
    }

    pub fn anchor<T: Into<Anchor>>(mut self, anchor: T) -> Self {
        self.anchor = Some(anchor.into());
        self
    }

    pub fn help<T: ToString>(mut self, help: T) -> Self {
        self.help = Some(help.to_string());
        self
    }

    pub fn divider<T: Into<Divider>>(mut self, divider: T) -> Self {
        self.divider = divider.into();
        self
    }

    pub fn width<T: Into<ElementWidth>>(mut self, width: T) -> Self {
        self.width = width.into();
        self
    }

    pub fn text_alignment<T: Into<TextAlignment>>(mut self, alignment: T) -> Self {
        self.text_alignment = alignment.into();
        self
    }
}

impl From<String> for HeaderOptions {
    fn from(body: String) -> Self {
        HeaderOptions::new(body)
    }
}

impl From<&str> for HeaderOptions {
    fn from(body: &str) -> Self {
        HeaderOptions::new(body)
    }
}

pub struct MarkdownOptions {
    body: String,
    unsafe_allow_html: bool,
    help: Option<String>,
    width: ElementWidth,
    text_alignment: TextAlignment,
}

impl MarkdownOptions {
    pub fn new(body: String) -> Self {
        Self {
            body,
            unsafe_allow_html: false,
            help: None,
            width: ElementWidth::Stretch,
            text_alignment: TextAlignment::Left,
        }
    }

    pub fn unsafe_allow_html(mut self, unsafe_allow_html: bool) -> Self {
        self.unsafe_allow_html = unsafe_allow_html;
        self
    }

    pub fn help<T: ToString>(mut self, help: T) -> Self {
        self.help = Some(help.to_string());
        self
    }
    pub fn width<T: Into<ElementWidth>>(mut self, width: T) -> Self {
        self.width = width.into();
        self
    }
    pub fn text_alignment<T: Into<TextAlignment>>(mut self, alignment: T) -> Self {
        self.text_alignment = alignment.into();
        self
    }
}

impl From<String> for MarkdownOptions {
    fn from(body: String) -> Self {
        MarkdownOptions::new(body)
    }
}

impl From<&str> for MarkdownOptions {
    fn from(body: &str) -> Self {
        body.to_string().into()
    }
}

pub struct BadgeOptions {
    label: String,
    icon: Option<String>,
    color: String,
    width: ElementWidth,
    help: Option<String>,
}

impl BadgeOptions {
    pub fn new<T: ToString>(label: T) -> Self {
        Self {
            label: label.to_string(),
            icon: None,
            color: "blue".to_string(),
            width: ElementWidth::Content,
            help: None,
        }
    }

    pub fn icon<T: ToString>(mut self, icon: T) -> Self {
        self.icon = Some(icon.to_string());
        self
    }

    pub fn color<T: ToString>(mut self, color: T) -> Self {
        self.color = color.to_string();
        self
    }

    pub fn width<T: Into<ElementWidth>>(mut self, width: T) -> Self {
        self.width = width.into();
        self
    }

    pub fn help<T: ToString>(mut self, help: T) -> Self {
        self.help = Some(help.to_string());
        self
    }
}

impl From<String> for BadgeOptions {
    fn from(body: String) -> Self {
        BadgeOptions::new(body)
    }
}

impl From<&str> for BadgeOptions {
    fn from(body: &str) -> Self {
        BadgeOptions::new(body)
    }
}

pub struct CaptionOptions {
    body: String,
    unsafe_allow_html: bool,
    help: Option<String>,
    width: ElementWidth,
    text_alignment: TextAlignment,
}

impl CaptionOptions {
    pub fn new<T: ToString>(body: T) -> Self {
        Self {
            body: body.to_string(),
            unsafe_allow_html: false,
            help: None,
            width: ElementWidth::Stretch,
            text_alignment: TextAlignment::Left,
        }
    }

    pub fn unsafe_allow_html(mut self, unsafe_allow_html: bool) -> Self {
        self.unsafe_allow_html = unsafe_allow_html;
        self
    }

    pub fn help<T: ToString>(mut self, help: T) -> Self {
        self.help = Some(help.to_string());
        self
    }

    pub fn width<T: Into<ElementWidth>>(mut self, width: T) -> Self {
        self.width = width.into();
        self
    }

    pub fn text_alignment(mut self, alignment: TextAlignment) -> Self {
        self.text_alignment = alignment;
        self
    }
}

impl From<String> for CaptionOptions {
    fn from(body: String) -> Self {
        CaptionOptions::new(body)
    }
}

impl From<&str> for CaptionOptions {
    fn from(body: &str) -> Self {
        body.to_string().into()
    }
}

pub struct CodeOptions {
    body: String,
    language: String,
    line_numbers: bool,
    wrap_lines: bool,
    height: ElementHeight,
    width: ElementWidth,
}

impl CodeOptions {
    pub fn new<T1: ToString, T2: ToString>(body: T1, language: T2) -> Self {
        Self {
            body: body.to_string(),
            language: language.to_string(),
            line_numbers: false,
            wrap_lines: false,
            height: ElementHeight::Content,
            width: ElementWidth::Stretch,
        }
    }

    pub fn line_numbers(mut self, line_numbers: bool) -> Self {
        self.line_numbers = line_numbers;
        self
    }

    pub fn wrap_lines(mut self, wrap_lines: bool) -> Self {
        self.wrap_lines = wrap_lines;
        self
    }

    pub fn height<T: Into<ElementHeight>>(mut self, height: T) -> Self {
        self.height = height.into();
        self
    }

    pub fn width<T: Into<ElementWidth>>(mut self, width: T) -> Self {
        self.width = width.into();
        self
    }
}

pub enum DividerOptions {
    Stretch,
    Width(i32),
}

impl From<i32> for DividerOptions {
    fn from(width: i32) -> Self {
        Self::Width(width)
    }
}

pub struct ContainerOptions {
    border: bool,
    key: Option<String>,
    width: ElementWidth,
    height: ElementHeight,
    horizontal: bool,
    horizontal_alignment: HorizontalAlignment,
    vertical_alignment: VerticalAlignment,
    gap: Gap,
}

impl Default for ContainerOptions {
    fn default() -> Self {
        Self::new()
    }
}

impl ContainerOptions {
    pub fn new() -> Self {
        Self {
            border: false,
            key: None,
            width: ElementWidth::Stretch,
            height: ElementHeight::Content,
            horizontal: false,
            horizontal_alignment: HorizontalAlignment::Left,
            vertical_alignment: VerticalAlignment::Top,
            gap: Gap::Small,
        }
    }

    pub fn border(mut self, border: bool) -> Self {
        self.border = border;
        self
    }

    pub fn key<T: ToString>(mut self, key: T) -> Self {
        self.key = Some(key.to_string());
        self
    }

    pub fn width<T: Into<ElementWidth>>(mut self, width: T) -> Self {
        self.width = width.into();
        self
    }

    pub fn height<T: Into<ElementHeight>>(mut self, height: T) -> Self {
        self.height = height.into();
        self
    }

    pub fn horizontal(mut self, horizontal: bool) -> Self {
        self.horizontal = horizontal;
        self
    }

    pub fn horizontal_alignment(mut self, alignment: HorizontalAlignment) -> Self {
        self.horizontal_alignment = alignment;
        self
    }

    pub fn vertical_alignment(mut self, alignment: VerticalAlignment) -> Self {
        self.vertical_alignment = alignment;
        self
    }

    pub fn gap(mut self, gap: Gap) -> Self {
        self.gap = gap;
        self
    }
}

pub struct FormOptions {
    key: String,
    clear_on_submit: bool,
    border: bool,
    enter_to_submit: bool,
    width: ElementWidth,
    height: ElementHeight,
}

impl FormOptions {
    pub fn new(key: impl Into<String>) -> Self {
        Self {
            key: key.into(),
            clear_on_submit: false,
            border: true,
            enter_to_submit: true,
            width: ElementWidth::Stretch,
            height: ElementHeight::Content,
        }
    }

    pub fn clear_on_submit(mut self, clear: bool) -> Self {
        self.clear_on_submit = clear;
        self
    }

    pub fn border(mut self, border: bool) -> Self {
        self.border = border;
        self
    }

    pub fn enter_to_submit(mut self, enter_to_submit: bool) -> Self {
        self.enter_to_submit = enter_to_submit;
        self
    }

    pub fn width<T: Into<ElementWidth>>(mut self, width: T) -> Self {
        self.width = width.into();
        self
    }

    pub fn height<T: Into<ElementHeight>>(mut self, height: T) -> Self {
        self.height = height.into();
        self
    }
}

impl From<&str> for FormOptions {
    fn from(key: &str) -> Self {
        Self::new(key)
    }
}

impl From<String> for FormOptions {
    fn from(key: String) -> Self {
        Self::new(key)
    }
}

pub struct ColumnsOptions {
    spec: Vec<f32>,
    gap: Gap,
    vertical_alignment: VerticalAlignment,
    border: bool,
    width: ElementWidth,
}

impl ColumnsOptions {
    pub fn new(spec: Vec<f32>) -> Self {
        Self {
            spec,
            gap: Gap::Small,
            vertical_alignment: VerticalAlignment::Top,
            border: false,
            width: ElementWidth::Stretch,
        }
    }

    pub fn gap(mut self, gap: Gap) -> Self {
        self.gap = gap;
        self
    }

    pub fn vertical_alignment(mut self, alignment: VerticalAlignment) -> Self {
        self.vertical_alignment = alignment;
        self
    }

    pub fn border(mut self, border: bool) -> Self {
        self.border = border;
        self
    }

    pub fn width<T: Into<ElementWidth>>(mut self, width: T) -> Self {
        self.width = width.into();
        self
    }
}

impl From<i32> for ColumnsOptions {
    fn from(spec: i32) -> Self {
        Self::new(vec![1.0; spec as usize])
    }
}

impl<T: Into<f32> + Copy> From<Vec<T>> for ColumnsOptions {
    fn from(spec: Vec<T>) -> Self {
        Self::new(spec.iter().map(|&i| i.into()).collect())
    }
}

impl<T: Into<f32> + Copy, const N: usize> From<[T; N]> for ColumnsOptions {
    fn from(spec: [T; N]) -> Self {
        Self::new(spec.iter().map(|&i| i.into()).collect())
    }
}

pub struct ButtonOptions {
    pub(crate) label: String,
    pub(crate) key: Option<String>,
    pub(crate) help: Option<String>,
    pub(crate) r#type: String,
    pub(crate) icon: Option<String>,
    pub(crate) disabled: bool,
    pub(crate) width: ElementWidth,
    pub(crate) shortcut: Option<String>,
    pub(crate) callback: Option<crate::WidgetCallback>,
}

impl ButtonOptions {
    pub fn new<T: ToString>(label: T) -> Self {
        Self {
            label: label.to_string(),
            key: None,
            help: None,
            r#type: "secondary".to_string(),
            icon: None,
            disabled: false,
            width: ElementWidth::Content,
            shortcut: None,
            callback: None,
        }
    }

    pub fn on_click(mut self, callback: impl Fn(&Streamlit) + Send + Sync + 'static) -> Self {
        self.callback = Some(std::sync::Arc::new(callback));
        self
    }

    pub fn key<T: ToString>(mut self, key: T) -> Self {
        self.key = Some(key.to_string());
        self
    }

    pub fn help<T: ToString>(mut self, help: T) -> Self {
        self.help = Some(help.to_string());
        self
    }

    pub fn r#type<T: ToString>(mut self, r#type: T) -> Self {
        self.r#type = r#type.to_string();
        self
    }

    pub fn icon<T: ToString>(mut self, icon: T) -> Self {
        self.icon = Some(icon.to_string());
        self
    }

    pub fn disabled(mut self, disabled: bool) -> Self {
        self.disabled = disabled;
        self
    }

    pub fn width<T: Into<ElementWidth>>(mut self, width: T) -> Self {
        self.width = width.into();
        self
    }

    pub fn shortcut<T: ToString>(mut self, shortcut: T) -> Self {
        self.shortcut = Some(shortcut.to_string());
        self
    }
}

impl From<String> for ButtonOptions {
    fn from(label: String) -> Self {
        Self::new(label)
    }
}

impl From<&str> for ButtonOptions {
    fn from(value: &str) -> Self {
        value.to_string().into()
    }
}

pub trait StreamlitApi {
    fn write<T: Into<WriteOptions>>(&self, body: T);

    fn info<T: Into<StatusOptions>>(&self, options: T) -> Result<(), StatusError>;

    fn warning<T: Into<StatusOptions>>(&self, options: T) -> Result<(), StatusError>;

    fn error<T: Into<StatusOptions>>(&self, options: T) -> Result<(), StatusError>;

    fn success<T: Into<StatusOptions>>(&self, options: T) -> Result<(), StatusError>;

    fn title<T: Into<HeaderOptions>>(&self, body: T) {
        self.h1(body)
    }

    fn header<T: Into<HeaderOptions>>(&self, body: T) {
        self.h2(body)
    }

    fn sub_header<T: Into<HeaderOptions>>(&self, body: T) {
        self.h3(body)
    }

    fn h1<T: Into<HeaderOptions>>(&self, body: T);

    fn h2<T: Into<HeaderOptions>>(&self, body: T);

    fn h3<T: Into<HeaderOptions>>(&self, body: T);

    fn markdown<T: Into<MarkdownOptions>>(&self, body: T);

    fn badge<T: Into<BadgeOptions>>(&self, body: T);

    fn caption<T: Into<CaptionOptions>>(&self, body: T);

    fn code<T1: ToString, T2: ToString>(&self, code_text: T1, language: T2) {
        self.code_options(CodeOptions::new(code_text, language));
    }

    fn code_options<T: Into<CodeOptions>>(&self, code_options: T);

    fn divider(&self) {
        self.divider_options(DividerOptions::Stretch);
    }

    fn divider_options<T: Into<DividerOptions>>(&self, options: T);

    fn container(&self) -> &Container<'_> {
        self.container_options(ContainerOptions::new())
    }

    fn container_options<T: Into<ContainerOptions>>(&self, options: T) -> &Container<'_>;

    fn form<T>(&self, options: impl Into<FormOptions>, body: impl FnOnce(&Form<'_>) -> Result<T, WidgetError>) -> Result<T, WidgetError>;

    fn columns<T: Into<ColumnsOptions>>(&self, spec: T) -> &[Column<'_>];

    fn button<T: Into<ButtonOptions>>(&self, options: T) -> bool;
}

fn create_status<C: AppendChild>(this: &C, options: StatusOptions, format: crate::proto::alert::Format) -> Result<(), StatusError> {
    use crate::proto::streamlit::width_config::WidthSpec;
    let width_spec = match options.width {
        StatusWidth::Keyword(value) if value == "stretch" => WidthSpec::UseStretch(true),
        StatusWidth::Pixels(value) if value > 0 => WidthSpec::PixelWidth(value as u32),
        StatusWidth::Keyword(value) => return Err(StatusError::InvalidWidth(format!("'{value}'"))),
        StatusWidth::Pixels(value) => return Err(StatusError::InvalidWidth(value.to_string())),
    };
    let (body, icon) = status_content(&options.body, options.icon.as_deref())?;
    let element = StatusElement::new(crate::proto::Alert {
        body,
        format: format as i32,
        icon,
        width_config: Some(crate::proto::streamlit::WidthConfig { width_spec: Some(width_spec) }),
        title: options.title.unwrap_or_default(),
    });
    this.push(Rc::new(RefCell::new(element)));
    Ok(())
}

fn create_header<C: AppendChild, T: Into<HeaderOptions>>(this: &C, data: T, tag: &str) {
    let option = data.into();

    let element = HeadingElement::new(tag.to_string(), option.body).help(option.help.unwrap_or_default()).width(option.width).text_alignment(option.text_alignment);

    let element = match option.divider {
        Divider::String(v) => element.divider(v),
        Divider::Bool(v) => {
            if v {
                element.divider("blue".into())
            } else {
                element
            }
        }
    };

    let element = if let Some(anchor) = option.anchor {
        match anchor {
            Anchor::String(s) => element.hide_anchor(false).anchor(s),
            Anchor::Bool(b) => element.hide_anchor(!b),
        }
    } else {
        element
    };

    this.push(Rc::new(RefCell::new(element)));
}

impl<C: AppendChild> StreamlitApi for C {
    fn info<T: Into<StatusOptions>>(&self, options: T) -> Result<(), StatusError> {
        create_status(self, options.into(), crate::proto::alert::Format::Info)
    }

    fn warning<T: Into<StatusOptions>>(&self, options: T) -> Result<(), StatusError> {
        create_status(self, options.into(), crate::proto::alert::Format::Warning)
    }

    fn error<T: Into<StatusOptions>>(&self, options: T) -> Result<(), StatusError> {
        create_status(self, options.into(), crate::proto::alert::Format::Error)
    }

    fn success<T: Into<StatusOptions>>(&self, options: T) -> Result<(), StatusError> {
        create_status(self, options.into(), crate::proto::alert::Format::Success)
    }

    fn write<T: Into<WriteOptions>>(&self, body: T) {
        let body = body.into();
        let element = MarkdownElement::new(body.body).unsafe_allow_html(body.unsafe_allow_html);
        self.push(Rc::new(RefCell::new(element)));
    }

    fn h1<T: Into<HeaderOptions>>(&self, body: T) {
        create_header(self, body, "h1");
    }

    fn h2<T: Into<HeaderOptions>>(&self, body: T) {
        create_header(self, body, "h2");
    }

    fn h3<T: Into<HeaderOptions>>(&self, body: T) {
        create_header(self, body, "h3");
    }

    fn markdown<T: Into<MarkdownOptions>>(&self, body: T) {
        let body = body.into();

        let element = MarkdownElement::new(body.body)
            .unsafe_allow_html(body.unsafe_allow_html)
            .help(body.help.unwrap_or_default())
            .width(body.width)
            .text_alignment(body.text_alignment);

        self.push(Rc::new(RefCell::new(element)));
    }

    fn badge<T: Into<BadgeOptions>>(&self, body: T) {
        let body = body.into();
        let element = BadgeElement::new(body.label).color(body.color).icon(body.icon.unwrap_or_default()).width(body.width).help(body.help.unwrap_or_default());
        self.push(Rc::new(RefCell::new(element)));
    }

    fn caption<T: Into<CaptionOptions>>(&self, body: T) {
        let body = body.into();
        let element = MarkdownElement::new(body.body)
            .element_type(MarkdownElementType::Caption)
            .unsafe_allow_html(body.unsafe_allow_html)
            .width(body.width)
            .help(body.help.unwrap_or_default())
            .text_alignment(body.text_alignment);
        self.push(Rc::new(RefCell::new(element)));
    }

    fn code_options<T: Into<CodeOptions>>(&self, code_options: T) {
        let body = code_options.into();
        let element = CodeElement::new(body.body, body.language).show_line_numbers(body.line_numbers).wrap_lines(body.wrap_lines).width(body.width).height(body.height);
        self.push(Rc::new(RefCell::new(element)));
    }

    fn divider_options<T: Into<DividerOptions>>(&self, options: T) {
        let body = options.into();
        let element = MarkdownElement::new("---".to_string()).element_type(MarkdownElementType::Divider).width(match body {
            DividerOptions::Stretch => ElementWidth::Stretch,
            DividerOptions::Width(v) => ElementWidth::Value(v),
        });
        self.push(Rc::new(RefCell::new(element)));
    }

    fn form<T>(&self, options: impl Into<FormOptions>, body: impl FnOnce(&Form<'_>) -> Result<T, WidgetError>) -> Result<T, WidgetError> {
        let options = options.into();
        if self.parent_form_id().is_some() {
            return Err(WidgetError::InvalidValue("forms cannot be nested in other forms".into()));
        }
        validate_form_dimensions(options.width.clone(), options.height.clone())?;
        let app = self.get_app();
        if !app.lock().claim_form_key(&options.key) {
            return Err(WidgetError::DuplicateKey(options.key));
        }
        let state = app.lock().session_state.clone();
        let checkpoint = state.form_checkpoint();

        let element = Rc::new(RefCell::new(FormElement::new(options.key.clone(), options.clear_on_submit, options.border, options.enter_to_submit, options.width, options.height)));
        let form = self.allocator().malloc(Form::new(element.clone(), options.key.clone(), self.allocator(), app.clone()));
        let result = match body(form).and_then(|value| if form.submit_count() == 0 { Err(WidgetError::InvalidValue("every form needs a form_submit_button".into())) } else { Ok(value) }) {
            Ok(value) => value,
            Err(error) => {
                state.rollback_form(checkpoint);
                app.lock().release_form_key(&options.key);
                return Err(error);
            }
        };
        self.push(element);
        Ok(result)
    }

    fn container_options<T: Into<ContainerOptions>>(&self, options: T) -> &Container<'_> {
        let options = options.into();

        let element = ContainerElement::new()
            .border(options.border)
            .key(options.key.unwrap_or_default())
            .width(options.width)
            .height(options.height)
            .horizontal(options.horizontal)
            .horizontal_alignment(options.horizontal_alignment)
            .vertical_alignment(options.vertical_alignment)
            .gap(options.gap);

        let element = Rc::new(RefCell::new(element));
        let app = self.get_app();
        let base_path = self.next_child_path();
        self.push(element.clone());
        let exit_path = app.lock().render_context_mut().map(|context| context.delta_path.clone()).unwrap_or_default();

        self.allocator().malloc(Container::new(element, self.allocator(), app, self.parent_form_id(), base_path, exit_path))
    }

    fn columns<T: Into<ColumnsOptions>>(&self, spec: T) -> &[Column<'_>] {
        let options = spec.into();

        let total: f32 = options.spec.iter().sum();
        let weights: Vec<f32> = options.spec.iter().map(|w| w / total).collect();

        if weights.is_empty() {
            return &[];
        }

        let container_element = Rc::new(RefCell::new(ContainerElement::new().horizontal(true).gap(options.gap)));
        let app = self.get_app();
        let container_base = self.next_child_path();
        self.push(container_element.clone());
        let container_exit = app.lock().render_context_mut().map(|context| context.delta_path.clone()).unwrap_or_default();

        let mut columns = Vec::with_capacity(weights.len());
        for (index, w) in weights.iter().enumerate() {
            let column_element = Rc::new(RefCell::new(ColumnElement::new(*w).border(options.border).vertical_alignment(options.vertical_alignment.clone()).width(options.width.clone())));
            container_element.borrow_mut().children.push(column_element.clone());

            let mut column_base = container_base.clone();
            column_base.push(index as u32);
            columns.push(Column::new(column_element, self.allocator(), app.clone(), self.parent_form_id(), column_base, container_exit.clone()));
        }
        self.allocator().malloc(columns).as_slice()
    }

    /// Display a button. Use `try_button` to handle duplicate key/ID errors.
    fn button<T: Into<ButtonOptions>>(&self, options: T) -> bool {
        crate::InputWidgets::try_button(self, options).expect("button registration failed")
    }
}

#[cfg(test)]
mod quality_tests {
    use super::*;

    #[tokio::test]
    async fn joined_futures_share_one_task_local_streamlit_state() {
        let st = Streamlit::new();
        let initial_count = Rc::strong_count(&st.app);

        let writer = async {
            st.session_state().set("quality", true).unwrap();
            tokio::task::yield_now().await;
        };
        let reader = async {
            tokio::task::yield_now().await;
            st.session_state().get::<bool>("quality").unwrap()
        };

        let (_, clicked) = tokio::join!(writer, reader);

        assert_eq!(initial_count, 1);
        assert_eq!(clicked, Some(true));
    }
}
