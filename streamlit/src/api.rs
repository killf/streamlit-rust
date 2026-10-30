use crate::WidgetError;
use crate::elements::App;
use crate::elements::badge::BadgeElement;
use crate::elements::code::CodeElement;
use crate::elements::columns::{Column, ColumnElement};
use crate::elements::common::{Anchor, Divider, Element, ElementHeight, ElementWidth, Gap, HorizontalAlignment, TextAlignment, VerticalAlignment};
use crate::elements::container::{Container, ContainerElement};
use crate::elements::exception::AppException;
pub use crate::elements::form::Form;
use crate::elements::form::{FormElement, validate_form_dimensions};
pub use crate::elements::layouts::{Bottom, ChatMessage, ChatMessageOptions, DialogBody, DialogOptions, EmptyHandle, Expander, ExpanderKind, ExpanderOptions, Popover, PopoverKind, PopoverOptions, Sidebar, Status, StatusState, Tab, TabsOptions};
use crate::elements::layouts::{ChatMessageElement, DialogElement, ExpanderElement, PopoverElement, StatusElement, TabsElement};
use crate::elements::markdown::{MarkdownElement, MarkdownElementType};
use crate::elements::status::{StatusElement as AlertStatusElement, status_content};
use crate::elements::text::{EmptyElement, HtmlElement, IframeElement, JsonElement, SnowElement, SpaceElement, TextElement};
use crate::elements::title::HeadingElement;
use crate::memory::Allocator;
pub use crate::proto::block::dialog::{DialogPosition, DialogWidth};
pub use crate::proto::page_config::{Layout as PageLayout, SidebarState as InitialSidebarState};
use crate::proto::{Delta, ForwardMsg, delta, delta_base_with_path, element, forward_msg};
use parking_lot::Mutex;
use std::cell::RefCell;
use std::rc::Rc;

/// Streamlit Rust API - provides a Python-like Streamlit interface
pub struct Streamlit {
    pub(crate) app: Rc<Mutex<App>>,
    pub(crate) allocator: Allocator,
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
            Err(other) => {
                if let Some(message) = state.take_registration_error() {
                    self.push(Rc::new(RefCell::new(crate::elements::exception::AppException::new("TypeError".into(), message, Vec::new()))));
                    state.set_run_control(crate::session::RunControl::Stop);
                    return Ok((String::new(), resolve(&default)?, false));
                }
                Err(other)
            }
        }
    }

    /// Registration under a derived widget id (the bidi component's trigger
    /// aggregator), with the same duplicate-key takeover as above.
    fn register_widget_with_id_parity<T>(&self, spec: crate::widgets::WidgetSpec<'_>, id: &str, resolve: impl Fn(&serde_json::Value) -> Result<T, WidgetError>) -> Result<(String, T, bool), WidgetError> {
        let state = self.get_app().lock().session_state.clone();
        let default = spec.default.clone();
        let kind = spec.kind.to_owned();
        match state.register_widget_with_id(spec, id, &resolve) {
            Ok(triple) => Ok(triple),
            Err(WidgetError::DuplicateKey(key)) => {
                self.push(Rc::new(RefCell::new(crate::elements::exception::ExceptionElement::duplicate_key(&kind, &key))));
                state.set_run_control(crate::session::RunControl::Stop);
                let value = resolve(&default)?;
                Ok((String::new(), value, false))
            }
            Err(other) => {
                if let Some(message) = state.take_registration_error() {
                    self.push(Rc::new(RefCell::new(crate::elements::exception::AppException::new("TypeError".into(), message, Vec::new()))));
                    state.set_run_control(crate::session::RunControl::Stop);
                    return Ok((String::new(), resolve(&default)?, false));
                }
                Err(other)
            }
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
    width: Option<ElementWidth>,
    text_alignment: TextAlignment,
}

impl MarkdownOptions {
    pub fn new(body: String) -> Self {
        Self {
            body,
            unsafe_allow_html: false,
            help: None,
            width: None,
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
        self.width = Some(width.into());
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

/// Page-config options: the measured 1.66.1 `st.set_page_config` subset.
/// Every call streams one `page_config_changed` message at the call point;
/// fields left unset inherit the previous config (they ride the wire as
/// LAYOUT_UNSET / SIDEBAR_UNSET), matching the reference.
pub struct PageConfigOptions {
    page_title: Option<String>,
    page_icon: Option<String>,
    layout: Option<PageLayout>,
    initial_sidebar_state: Option<InitialSidebarState>,
    menu_items: Option<MenuItems>,
}

impl PageConfigOptions {
    pub fn new() -> Self {
        Self {
            page_title: None,
            page_icon: None,
            layout: None,
            initial_sidebar_state: None,
            menu_items: None,
        }
    }

    pub fn page_title(mut self, title: impl Into<String>) -> Self {
        self.page_title = Some(title.into());
        self
    }

    pub fn page_icon(mut self, icon: impl Into<String>) -> Self {
        self.page_icon = Some(icon.into());
        self
    }

    pub fn layout(mut self, layout: PageLayout) -> Self {
        self.layout = Some(layout);
        self
    }

    pub fn initial_sidebar_state(mut self, state: InitialSidebarState) -> Self {
        self.initial_sidebar_state = Some(state);
        self
    }

    pub fn menu_items(mut self, menu: MenuItems) -> Self {
        self.menu_items = Some(menu);
        self
    }
}

impl Default for PageConfigOptions {
    fn default() -> Self {
        Self::new()
    }
}

impl From<&str> for PageConfigOptions {
    fn from(title: &str) -> Self {
        Self::new().page_title(title)
    }
}

impl From<String> for PageConfigOptions {
    fn from(title: String) -> Self {
        Self::new().page_title(title)
    }
}

/// The main-menu entries: help and bug-report links plus the About dialog
/// markdown.
pub struct MenuItems {
    get_help_url: Option<String>,
    report_a_bug_url: Option<String>,
    about_section_md: Option<String>,
}

impl MenuItems {
    pub fn new() -> Self {
        Self {
            get_help_url: None,
            report_a_bug_url: None,
            about_section_md: None,
        }
    }

    pub fn get_help(mut self, url: impl Into<String>) -> Self {
        self.get_help_url = Some(url.into());
        self
    }

    pub fn report_bug(mut self, url: impl Into<String>) -> Self {
        self.report_a_bug_url = Some(url.into());
        self
    }

    pub fn about(mut self, markdown: impl Into<String>) -> Self {
        self.about_section_md = Some(markdown.into());
        self
    }
}

impl Default for MenuItems {
    fn default() -> Self {
        Self::new()
    }
}

impl From<PageConfigOptions> for crate::proto::PageConfig {
    fn from(options: PageConfigOptions) -> Self {
        crate::proto::PageConfig {
            title: options.page_title.unwrap_or_default(),
            favicon: options.page_icon.unwrap_or_default(),
            // Unset enums ride the wire as the reference's inherit markers.
            layout: options.layout.map(|layout| layout as i32).unwrap_or(crate::proto::page_config::Layout::Unset as i32),
            initial_sidebar_state: options.initial_sidebar_state.map(|state| state as i32).unwrap_or(crate::proto::page_config::SidebarState::SidebarUnset as i32),
            menu_items: options.menu_items.map(|menu| crate::proto::page_config::MenuItems {
                get_help_url: menu.get_help_url.unwrap_or_default(),
                report_a_bug_url: menu.report_a_bug_url.unwrap_or_default(),
                about_section_md: menu.about_section_md.unwrap_or_default(),
                ..Default::default()
            }),
            initial_sidebar_width: None,
        }
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

/// Image options. The plain `RgbaImage` call renders the image with no
/// caption; `(image, "caption")` names it, matching the measured reference.
pub struct ImageOptions {
    image: crate::media::RgbaImage,
    caption: String,
    width: Option<ElementWidth>,
}

/// Multiple images in one element (Python `st.image([a, b], caption=[...])`):
/// one imgs element whose entries share the element-level width.
pub struct ImageListOptions {
    images: Vec<crate::media::RgbaImage>,
    captions: Vec<String>,
    width: Option<ElementWidth>,
}
impl ImageListOptions {
    pub fn new(images: impl IntoIterator<Item = crate::media::RgbaImage>) -> Self {
        Self {
            images: images.into_iter().collect(),
            captions: Vec::new(),
            width: None,
        }
    }
    /// One caption per image, in order.
    pub fn captions(mut self, captions: impl IntoIterator<Item = impl Into<String>>) -> Self {
        self.captions = captions.into_iter().map(Into::into).collect();
        self
    }
    pub fn width(mut self, width: ElementWidth) -> Self {
        self.width = Some(width);
        self
    }
}
impl ImageOptions {
    pub fn new(image: crate::media::RgbaImage) -> Self {
        Self { image, caption: String::new(), width: None }
    }
    pub fn caption(mut self, caption: impl Into<String>) -> Self {
        self.caption = caption.into();
        self
    }
    pub fn width(mut self, width: ElementWidth) -> Self {
        self.width = Some(width);
        self
    }
}
impl From<crate::media::RgbaImage> for ImageOptions {
    fn from(image: crate::media::RgbaImage) -> Self {
        Self::new(image)
    }
}
impl From<(crate::media::RgbaImage, &str)> for ImageOptions {
    fn from((image, caption): (crate::media::RgbaImage, &str)) -> Self {
        Self::new(image).caption(caption)
    }
}
impl From<(crate::media::RgbaImage, String)> for ImageOptions {
    fn from((image, caption): (crate::media::RgbaImage, String)) -> Self {
        Self::new(image).caption(caption)
    }
}

/// Audio options: the measured call passes the bytes and their MIME type;
/// the playback knobs (frozen media-params reference) mirror the Python
/// kwargs. `start_time`/`end_time` accept seconds (truncated like Python's
/// `int()`); `format` is the `mime` positional.
pub struct AudioOptions {
    data: Vec<u8>,
    mime: String,
    start_time: Option<f64>,
    end_time: Option<f64>,
    loop_: bool,
    autoplay: bool,
}
impl AudioOptions {
    pub fn new(data: Vec<u8>, mime: impl Into<String>) -> Self {
        Self {
            data,
            mime: mime.into(),
            start_time: None,
            end_time: None,
            loop_: false,
            autoplay: false,
        }
    }
    /// Where playback starts, in seconds (fractional seconds truncate).
    pub fn start_time(mut self, seconds: f64) -> Self {
        self.start_time = Some(seconds);
        self
    }
    /// Where playback stops, in seconds (fractional seconds truncate).
    pub fn end_time(mut self, seconds: f64) -> Self {
        self.end_time = Some(seconds);
        self
    }
    /// Start over once the media ends.
    pub fn loop_(mut self, value: bool) -> Self {
        self.loop_ = value;
        self
    }
    /// Attempt to play automatically; an autoplaying player carries a stable
    /// element id like the reference's.
    pub fn autoplay(mut self, value: bool) -> Self {
        self.autoplay = value;
        self
    }
}
impl From<(Vec<u8>, &str)> for AudioOptions {
    fn from((data, mime): (Vec<u8>, &str)) -> Self {
        Self::new(data, mime)
    }
}
impl From<(Vec<u8>, String)> for AudioOptions {
    fn from((data, mime): (Vec<u8>, String)) -> Self {
        Self::new(data, mime)
    }
}

/// Video options: the measured bytes+MIME call plus the playback knobs and
/// text subtitles (VTT or SRT text; see `subtitle`).
pub struct VideoOptions {
    data: Vec<u8>,
    mime: String,
    /// A direct URL rides the wire unchanged (no upload): the measured
    /// reference passes it through with type NATIVE and the playback knobs.
    url: Option<String>,
    start_time: Option<f64>,
    end_time: Option<f64>,
    loop_: bool,
    autoplay: bool,
    muted: bool,
    subtitles: Vec<(String, String)>,
}
impl VideoOptions {
    pub fn new(data: Vec<u8>, mime: impl Into<String>) -> Self {
        Self {
            data,
            mime: mime.into(),
            url: None,
            start_time: None,
            end_time: None,
            loop_: false,
            autoplay: false,
            muted: false,
            subtitles: Vec::new(),
        }
    }

    /// A direct URL instead of bytes (Python `st.video("https://…")`).
    pub fn from_url(url: impl Into<String>) -> Self {
        Self::new(Vec::new(), "video/mp4").url(url)
    }

    /// Set the direct URL (builder form of `from_url`).
    pub fn url(mut self, url: impl Into<String>) -> Self {
        self.url = Some(url.into());
        self
    }
    /// Where playback starts, in seconds (fractional seconds truncate).
    pub fn start_time(mut self, seconds: f64) -> Self {
        self.start_time = Some(seconds);
        self
    }
    /// Where playback stops, in seconds (fractional seconds truncate).
    pub fn end_time(mut self, seconds: f64) -> Self {
        self.end_time = Some(seconds);
        self
    }
    /// Start over once the media ends.
    pub fn loop_(mut self, value: bool) -> Self {
        self.loop_ = value;
        self
    }
    /// Attempt to play automatically; an autoplaying player carries a stable
    /// element id like the reference's.
    pub fn autoplay(mut self, value: bool) -> Self {
        self.autoplay = value;
        self
    }
    /// Begin playback muted.
    pub fn muted(mut self, value: bool) -> Self {
        self.muted = value;
        self
    }
    /// One subtitle track: a language/track label and its VTT- or
    /// SRT-formatted text. Invalid text renders the reference's API exception
    /// instead of the player.
    pub fn subtitle(mut self, label: impl Into<String>, text: impl Into<String>) -> Self {
        self.subtitles.push((label.into(), text.into()));
        self
    }
}
impl From<(Vec<u8>, &str)> for VideoOptions {
    fn from((data, mime): (Vec<u8>, &str)) -> Self {
        Self::new(data, mime)
    }
}
impl From<(Vec<u8>, String)> for VideoOptions {
    fn from((data, mime): (Vec<u8>, String)) -> Self {
        Self::new(data, mime)
    }
}

pub use crate::elements::media::DeltaColor;

/// Metric options. The plain `(label, value)` call renders without a delta;
/// `.delta("2 °F")` derives the measured direction and color from the sign.
/// String deltas are dedented, then only the literal `"0"` is neutral:
/// `"0.0"` points up and `"-0"` points down, matching the pinned reference.
pub struct MetricOptions {
    label: String,
    value: String,
    delta: Option<String>,
    delta_color: DeltaColor,
}
impl MetricOptions {
    pub fn new(label: impl Into<String>, value: impl Into<String>) -> Self {
        Self {
            label: label.into(),
            value: value.into(),
            delta: None,
            delta_color: DeltaColor::Normal,
        }
    }
    pub fn delta(mut self, delta: impl Into<String>) -> Self {
        self.delta = Some(delta.into());
        self
    }
    pub fn delta_color(mut self, delta_color: DeltaColor) -> Self {
        self.delta_color = delta_color;
        self
    }
}
impl<L: Into<String>, V: Into<String>> From<(L, V)> for MetricOptions {
    fn from((label, value): (L, V)) -> Self {
        Self::new(label, value)
    }
}

/// Toast options. The plain message call shows the measured four-second
/// toast; `.icon(...)` and `.duration(...)` override.
pub struct ToastOptions {
    body: String,
    icon: String,
    duration: Option<i32>,
}
impl ToastOptions {
    pub fn new(body: impl Into<String>) -> Self {
        Self {
            body: body.into(),
            icon: String::new(),
            duration: Some(4),
        }
    }
    pub fn icon(mut self, icon: impl Into<String>) -> Self {
        self.icon = icon.into();
        self
    }
    pub fn duration(mut self, duration: i32) -> Self {
        self.duration = Some(duration);
        self
    }
}
impl From<&str> for ToastOptions {
    fn from(body: &str) -> Self {
        Self::new(body)
    }
}
impl From<String> for ToastOptions {
    fn from(body: String) -> Self {
        Self::new(body)
    }
}

/// Options for `st.text`: the body plus the measured defaults (wrapped
/// text, content width, left alignment).
pub struct TextOptions {
    pub body: String,
    pub width: Option<ElementWidth>,
    pub text_alignment: Option<TextAlignment>,
}

impl TextOptions {
    pub fn new(body: impl Into<String>) -> Self {
        Self {
            body: body.into(),
            width: None,
            text_alignment: None,
        }
    }

    pub fn width(mut self, width: ElementWidth) -> Self {
        self.width = Some(width);
        self
    }

    pub fn text_alignment(mut self, alignment: TextAlignment) -> Self {
        self.text_alignment = Some(alignment);
        self
    }
}

impl From<&str> for TextOptions {
    fn from(body: &str) -> Self {
        Self::new(body)
    }
}

impl From<String> for TextOptions {
    fn from(body: String) -> Self {
        Self::new(body)
    }
}

/// Options for `st.html`: the body of the embedded document.
pub struct HtmlOptions {
    pub body: String,
}

impl HtmlOptions {
    pub fn new(body: impl Into<String>) -> Self {
        Self { body: body.into() }
    }
}

impl From<&str> for HtmlOptions {
    fn from(body: &str) -> Self {
        Self::new(body)
    }
}

impl From<String> for HtmlOptions {
    fn from(body: String) -> Self {
        Self::new(body)
    }
}

/// What an `st.iframe` embeds: a URL or an inline document.
pub enum IFrameSource {
    Src(String),
    Srcdoc(String),
}

/// Options for `st.iframe`: the source plus the measured defaults
/// (scrolling on, a 400 px height, stretch width).
pub struct IFrameOptions {
    pub source: IFrameSource,
    pub height: Option<ElementHeight>,
}

impl IFrameOptions {
    pub fn new(source: IFrameSource) -> Self {
        Self { source, height: None }
    }

    pub fn height(mut self, height: ElementHeight) -> Self {
        self.height = Some(height);
        self
    }
}

impl From<&str> for IFrameOptions {
    fn from(url: &str) -> Self {
        Self::new(IFrameSource::Src(url.to_owned()))
    }
}

impl From<String> for IFrameOptions {
    fn from(url: String) -> Self {
        Self::new(IFrameSource::Src(url))
    }
}

/// Options for `st.exception`: the exception's type name, its message and
/// the trace lines the box shows (the runtime cannot know the application's
/// source, so the caller supplies them).
pub struct ExceptionOptions {
    pub kind: String,
    pub message: String,
    pub stack_trace: Vec<String>,
}

impl ExceptionOptions {
    pub fn new(kind: impl Into<String>, message: impl Into<String>) -> Self {
        Self {
            kind: kind.into(),
            message: message.into(),
            stack_trace: Vec::new(),
        }
    }

    pub fn trace(mut self, line: impl Into<String>) -> Self {
        self.stack_trace.push(line.into());
        self
    }
}

/// Options for the `st.status` container: the label and its initial
/// expansion.
pub struct StatusContainerOptions {
    pub label: String,
    pub expanded: bool,
}

impl StatusContainerOptions {
    pub fn new(label: impl Into<String>) -> Self {
        Self { label: label.into(), expanded: false }
    }

    pub fn expanded(mut self, expanded: bool) -> Self {
        self.expanded = expanded;
        self
    }
}

impl From<&str> for StatusContainerOptions {
    fn from(label: &str) -> Self {
        Self::new(label)
    }
}

impl From<String> for StatusContainerOptions {
    fn from(label: String) -> Self {
        Self::new(label)
    }
}

/// The handle `st.progress` returns: updates coalesce into the single delta
/// the reference streams at the end of the run.
pub struct Progress {
    element: Rc<RefCell<crate::elements::media::ProgressElement>>,
}

/// Progress options: an integer percent (0..=100) with an optional text
/// label riding the same message (the measured python form); floats are a
/// python-only overload (0.0..=1.0, else a framework exception) the Rust
/// API does not carry — the integer path is the measured parity surface.
pub struct ProgressOptions {
    value: u32,
    text: String,
}
impl ProgressOptions {
    pub fn new(value: u32) -> Self {
        Self { value, text: String::new() }
    }
    pub fn text(mut self, text: impl Into<String>) -> Self {
        self.text = text.into();
        self
    }
}
impl From<u32> for ProgressOptions {
    fn from(value: u32) -> Self {
        Self::new(value)
    }
}
impl Progress {
    pub fn set(&self, value: u32) {
        self.element.borrow_mut().set(value);
    }
    pub fn text(&self, text: impl Into<String>) {
        self.element.borrow_mut().set_text(text.into());
    }
}

pub trait StreamlitApi {
    fn write<T: Into<WriteOptions>>(&self, body: T);

    /// Stream text chunks into one growing markdown element, like
    /// `st.write_stream`: each chunk replaces the placeholder with the
    /// accumulated text (unclosed markdown stays renderable mid-stream) and
    /// the final flush closes the parsing. Returns the accumulated text.
    fn write_stream<S: Into<String>>(&self, chunks: impl IntoIterator<Item = S>) -> String;

    /// The cursor form of `write_stream`: from the second chunk on, the
    /// cursor rides the streamed body until the final flush drops it.
    fn write_stream_with_cursor<S: Into<String>>(&self, cursor: &str, chunks: impl IntoIterator<Item = S>) -> String;

    /// An altair-style chart, like `st.altair_chart`: the final vega-lite
    /// spec (without the dataset indirection, schema or autosize) plus the
    /// chart's data. The chart-building library is Python-only; the Rust
    /// surface takes the transformed payload.
    fn altair_chart(&self, spec: serde_json::Value, data: &crate::data::RecordBatch);

    /// A vega-lite chart, like `st.vega_lite_chart`: the spec dict; an
    /// inline `data.values` list is extracted into the element's arrow data
    /// exactly like the reference does.
    fn vega_lite_chart(&self, spec: serde_json::Value);

    /// A plotly chart, like `st.plotly_chart`: the figure JSON as produced
    /// by plotly's `to_json`.
    fn plotly_chart(&self, spec: impl Into<String>);

    /// A pydeck chart, like `st.pydeck_chart`: the deck JSON as produced by
    /// `Deck.to_json`.
    fn pydeck_chart(&self, json: impl Into<String>);

    /// A graphviz chart, like `st.graphviz_chart`: the DOT source.
    fn graphviz_chart(&self, spec: impl Into<String>);

    /// A mermaid diagram, like `st.mermaid_chart`: the diagram source,
    /// rendered through a fenced markdown block.
    fn mermaid_chart(&self, body: impl Into<String>);

    /// An echarts chart, like `st.echarts_chart`: the option object.
    fn echarts_chart(&self, spec: serde_json::Value);

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

    /// The fixed sidebar root: children stream straight into [1, i],
    /// interleaved with the main flow, with no block of its own.
    fn sidebar(&self) -> &Sidebar<'_>;

    /// The fixed bottom root: children stream straight into [3, i], pinned
    /// to the bottom of the viewport, with no block of its own.
    fn bottom(&self) -> &Bottom<'_>;

    /// An expandable status container, like `with st.status("Working...")`;
    /// `status.update(...)` re-streams the block with the new label, state
    /// and expansion.
    fn status<T: Into<StatusContainerOptions>>(&self, options: T) -> &Status<'_>;

    /// An overwritable placeholder slot, like `st.empty()`: the placeholder
    /// takes the call slot and anything written through the handle replaces
    /// that slot.
    fn empty(&self) -> &EmptyHandle<'_>;

    /// A JSON viewer, like `st.json(body)`, fully expanded by default.
    /// String bodies are already-serialized JSON and pass through unchanged;
    /// other values use the reference's `json.dumps` representation.
    fn json<T: serde::Serialize>(&self, body: T);

    /// Select initial expansion, like `st.json(body, expanded=True/False)`.
    fn json_expanded<T: serde::Serialize>(&self, body: T, expanded: bool);

    /// A square spacer, like `st.space(pixels)`.
    fn space(&self, size: u32);

    /// A chat message container, like `with st.chat_message("user")`: the
    /// avatar follows preset/emoji names; other names use a letter icon.
    fn chat_message<T: Into<ChatMessageOptions>>(&self, options: T) -> &ChatMessage<'_> {
        self.chat_message_options(options.into())
    }

    fn chat_message_options(&self, options: ChatMessageOptions) -> &ChatMessage<'_>;

    fn expander<T: Into<ExpanderOptions>>(&self, options: T) -> &Expander<'_> {
        self.expander_options(options.into())
    }

    fn expander_options(&self, options: ExpanderOptions) -> &Expander<'_>;

    fn tabs<'a, T: Into<TabsOptions<'a>>>(&self, labels: T) -> &[Tab<'_>];

    fn popover<T: Into<PopoverOptions>>(&self, options: T) -> &Popover<'_> {
        self.popover_options(options.into())
    }

    fn popover_options(&self, options: PopoverOptions) -> &Popover<'_>;

    /// Opens a dialog on the event root and streams `body` into it, the way
    /// the reference's `@st.dialog` decorator behaves on call.
    fn dialog<T, F: FnOnce(&DialogBody<'_>) -> T>(&self, options: impl Into<DialogOptions>, body: F) -> T;

    /// Configures the page: title, icon, layout, sidebar state and menu
    /// links. Like the measured 1.66.1 reference, every call streams one
    /// `page_config_changed` message at the call point and consumes no
    /// element path; fields left unset inherit the previous config.
    fn set_page_config(&self, options: impl Into<PageConfigOptions>);

    fn form<T>(&self, options: impl Into<FormOptions>, body: impl FnOnce(&Form<'_>) -> Result<T, WidgetError>) -> Result<T, WidgetError>;

    fn columns<T: Into<ColumnsOptions>>(&self, spec: T) -> &[Column<'_>];

    fn button<T: Into<ButtonOptions>>(&self, options: T) -> bool;

    fn image<T: Into<ImageOptions>>(&self, options: T);

    /// Several images in one element, like `st.image([...])`.
    fn images(&self, options: ImageListOptions);

    fn audio<T: Into<AudioOptions>>(&self, options: T);

    fn video<T: Into<VideoOptions>>(&self, options: T);

    fn metric<T: Into<MetricOptions>>(&self, options: T);

    fn progress(&self, value: u32) -> Result<Progress, WidgetError>;

    /// Progress with a text label riding the creation message
    /// (Python `st.progress(50, text=…)`).
    fn progress_options(&self, options: impl Into<ProgressOptions>) -> Result<Progress, WidgetError>;

    /// Streams a transient spinner around `body`, clearing it on exit the
    /// way the reference's `with st.spinner(...)` does.
    fn spinner<T>(&self, text: impl Into<String>, body: impl FnOnce() -> T) -> T;

    fn toast<T: Into<ToastOptions>>(&self, options: T);

    fn balloons(&self);

    /// Plain pre-formatted text, like `st.text`: wrapped, content width.
    fn text<T: Into<TextOptions>>(&self, body: T);

    /// A LaTeX formula rendered as display math, like `st.latex`.
    fn latex(&self, formula: impl Into<String>);

    /// Embed an html document in the page, like `st.html`.
    fn html<T: Into<HtmlOptions>>(&self, body: T);

    /// Embed an external page in an iframe, like `st.iframe`.
    fn iframe<T: Into<IFrameOptions>>(&self, body: T);

    /// Mount one registered `st.components.v2.component` instance: streams
    /// the bidi_component element carrying the definition's inline
    /// HTML/CSS/JS and the JSON data payload, registers the instance's
    /// state widget, and returns the current state (the default object
    /// before any component interaction).
    fn component_v2<'a>(&self, component: &crate::elements::components::ComponentV2, mount: impl Into<crate::elements::components::ComponentMount<'a>>) -> Result<serde_json::Value, WidgetError>;

    /// The one-shot snowfall, like `st.snow()`.
    fn snow(&self);

    /// Show `code` beside the output of `body`, like `with st.echo():` --
    /// an empty placeholder takes the call slot, `body`'s output streams
    /// after it, and the block exit replaces the placeholder with the code.
    /// Rust cannot read the caller's source, so the code text is supplied.
    fn echo<F: FnOnce(&Self)>(&self, code: impl Into<String>, body: F)
    where
        Self: Sized;

    /// Display an exception, like `st.exception`: the type name, the
    /// message and the caller's trace lines in the framework's box.
    fn exception<T: Into<ExceptionOptions>>(&self, error: T);

    /// A link to another page or an external URL, like `st.page_link`: a
    /// pure navigation element with no widget state. A registered page keeps
    /// its title and icon as the link's label and icon unless overridden;
    /// an external URL needs an explicit label, as in the reference.
    fn page_link<'a>(&self, options: impl Into<crate::navigation::PageLinkOptions<'a>>) -> Result<(), WidgetError>;

    /// The app logo, like `st.logo`: a ForwardMsg-level message (no element
    /// path) carrying the image (an emoji, a material icon or an image URL),
    /// the size and an optional link and collapsed-sidebar icon.
    fn logo(&self, options: impl Into<LogoOptions>);

    /// The help viewer, like `st.help`: the doc string with the object's
    /// type, name and value. Rust cannot introspect a value the way Python
    /// does, so every field is supplied explicitly.
    fn help(&self, options: impl Into<HelpOptions>);

    /// A skeleton loading placeholder, like `st.skeleton`: the returned
    /// handle replaces the placeholder's slot, like `st.empty`.
    fn skeleton(&self, options: impl Into<SkeletonOptions>) -> &EmptyHandle<'_>;

    /// The PDF viewer, like `st.pdf`. The pinned reference lacks the
    /// optional `streamlit-pdf` component, so the measured behavior is the
    /// framework exception; this port mirrors exactly that path.
    fn pdf(&self, data: impl Into<String>);
}

/// The logo image: an emoji, a material icon shortcode, or a URL.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum LogoImage {
    Emoji(String),
    Icon(String),
    Url(String),
}

impl LogoImage {
    fn wire(self) -> (String, i32) {
        match self {
            Self::Emoji(value) => (value, crate::proto::logo::ImageType::Emoji as i32),
            Self::Icon(value) => (value, crate::proto::logo::ImageType::Icon as i32),
            Self::Url(value) => (value, crate::proto::logo::ImageType::Image as i32),
        }
    }
}

/// Logo options: the image (emoji, material icon or URL), the size and an
/// optional external link plus the collapsed-sidebar icon.
pub struct LogoOptions {
    image: LogoImage,
    size: &'static str,
    link: Option<String>,
    icon_image: Option<LogoImage>,
}
impl LogoOptions {
    pub fn new(image: impl Into<LogoImage>) -> Self {
        Self {
            image: image.into(),
            size: "medium",
            link: None,
            icon_image: None,
        }
    }
    pub fn small(mut self) -> Self {
        self.size = "small";
        self
    }
    pub fn large(mut self) -> Self {
        self.size = "large";
        self
    }
    pub fn link(mut self, link: impl Into<String>) -> Self {
        self.link = Some(link.into());
        self
    }
    pub fn icon_image(mut self, icon: impl Into<LogoImage>) -> Self {
        self.icon_image = Some(icon.into());
        self
    }
}
impl From<&str> for LogoImage {
    fn from(value: &str) -> Self {
        if value.starts_with(":material/") && value.ends_with(':') {
            Self::Icon(value.to_string())
        } else if emojis::get(value).is_some() {
            Self::Emoji(value.to_string())
        } else {
            Self::Url(value.to_string())
        }
    }
}
impl From<String> for LogoImage {
    fn from(value: String) -> Self {
        Self::from(value.as_str())
    }
}
impl From<LogoImage> for LogoOptions {
    fn from(image: LogoImage) -> Self {
        Self::new(image)
    }
}
impl From<&str> for LogoOptions {
    fn from(image: &str) -> Self {
        Self::new(LogoImage::from(image))
    }
}
impl From<String> for LogoOptions {
    fn from(image: String) -> Self {
        Self::new(LogoImage::from(image))
    }
}

/// Help options: the doc string and the object's type, name and value.
pub struct HelpOptions {
    doc_string: String,
    type_name: String,
    name: Option<String>,
    value: Option<String>,
}
impl HelpOptions {
    pub fn new(doc_string: impl Into<String>, type_name: impl Into<String>) -> Self {
        Self {
            doc_string: doc_string.into(),
            type_name: type_name.into(),
            name: None,
            value: None,
        }
    }
    pub fn name(mut self, name: impl Into<String>) -> Self {
        self.name = Some(name.into());
        self
    }
    pub fn value(mut self, value: impl Into<String>) -> Self {
        self.value = Some(value.into());
        self
    }
}
impl<D: Into<String>, T: Into<String>> From<(D, T)> for HelpOptions {
    fn from((doc_string, type_name): (D, T)) -> Self {
        Self::new(doc_string, type_name)
    }
}

/// Skeleton options: a pixel height (`None` keeps the standard element
/// height, `"stretch"` fills the parent) with the stretch width default.
pub struct SkeletonOptions {
    width: Option<ElementWidth>,
    height: Option<ElementHeight>,
}
impl SkeletonOptions {
    pub fn new() -> Self {
        Self { width: None, height: None }
    }
    /// A fixed pixel height.
    pub fn height(mut self, pixels: i32) -> Self {
        self.height = Some(ElementHeight::Value(pixels));
        self
    }
    /// A height matching the parent container.
    pub fn stretch_height(mut self) -> Self {
        self.height = Some(ElementHeight::Stretch);
        self
    }
    /// A fixed pixel width; the default stretches.
    pub fn width(mut self, pixels: i32) -> Self {
        self.width = Some(ElementWidth::Value(pixels));
        self
    }
}
impl Default for SkeletonOptions {
    fn default() -> Self {
        Self::new()
    }
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
    let element = AlertStatusElement::new(crate::proto::Alert {
        body,
        format: format as i32,
        icon,
        width_config: Some(crate::proto::streamlit::WidthConfig { width_spec: Some(width_spec) }),
        title: options.title.unwrap_or_default(),
    });
    this.push(Rc::new(RefCell::new(element)));
    Ok(())
}

/// The measured echo shape: an empty placeholder takes the call slot, the
/// body's output streams after it, and the block exit replaces the
/// placeholder with the code (python, content height, stretch width)
/// without touching the cursor.
fn emit_echo<C: AppendChild, F: FnOnce(&C)>(this: &C, code: String, body: F) {
    let app_handle = this.get_app();
    let placeholder_path = {
        let mut app = app_handle.lock();
        app.render_context_mut().map(|context| context.delta_path.clone()).unwrap_or_default()
    };
    this.push(Rc::new(RefCell::new(EmptyElement)));
    body(this);
    let mut app = app_handle.lock();
    if let Some(context) = app.render_context_mut() {
        let element_hash = crate::utils::hash::hash(format!("echo_{code}").as_str());
        let mut msg = delta_base_with_path(placeholder_path, context.active_script_hash.clone(), element_hash);
        msg.r#type = Some(forward_msg::Type::Delta(Delta {
            fragment_id: String::new(),
            r#type: Some(delta::Type::NewElement(crate::proto::Element {
                height_config: Some(ElementHeight::Content.into()),
                width_config: Some(ElementWidth::Stretch.into()),
                r#type: Some(element::Type::Code(crate::proto::Code {
                    code_text: code,
                    language: "python".to_string(),
                    ..Default::default()
                })),
                ..Default::default()
            })),
        }));
        context.push(msg);
    }
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

    fn write_stream<S: Into<String>>(&self, chunks: impl IntoIterator<Item = S>) -> String {
        self.write_stream_with_cursor("", chunks)
    }

    fn write_stream_with_cursor<S: Into<String>>(&self, cursor: &str, chunks: impl IntoIterator<Item = S>) -> String {
        // Mirrors the reference loop: the empty placeholder is created at the
        // first text chunk, each chunk replaces it with the accumulated
        // markdown (parsing left open mid-stream), and a final cursor-less
        // flush closes the parsing. The reference's message queue coalesces
        // the placeholder with the first same-path write, so the placeholder
        // element itself never reaches the wire: the slot is created
        // silently and the parent cursor still advances.
        let mut slot: Option<&EmptyHandle<'_>> = None;
        let mut accumulated = String::new();
        for chunk in chunks {
            let chunk = chunk.into();
            if chunk.is_empty() {
                continue;
            }
            let first = slot.is_none();
            let slot = slot.get_or_insert_with(|| {
                let app_handle = self.get_app();
                let mut app = app_handle.lock();
                let slot_path = app.render_context_mut().map(|context| context.delta_path.clone()).unwrap_or_default();
                if let Some(context) = app.render_context_mut()
                    && let Some(index) = context.delta_path.pop()
                {
                    context.delta_path.push(index + 1);
                }
                drop(app);
                self.allocator().malloc(EmptyHandle::new(self.allocator(), app_handle.clone(), self.parent_form_id(), slot_path))
            });
            accumulated.push_str(&chunk);
            let mut body = accumulated.clone();
            if !first {
                body.push_str(cursor);
            }
            slot.push(Rc::new(RefCell::new(crate::elements::markdown::MarkdownElement::new(body).unterminated())));
        }
        if let Some(slot) = slot {
            slot.push(Rc::new(RefCell::new(crate::elements::markdown::MarkdownElement::new(accumulated.clone()))));
        }
        accumulated
    }

    fn altair_chart(&self, spec: serde_json::Value, data: &crate::data::RecordBatch) {
        let Ok(arrow) = crate::data_api::chart_arrow_data(data) else { return };
        self.push(Rc::new(RefCell::new(crate::elements::charts::altair_chart(spec, arrow))));
    }

    fn vega_lite_chart(&self, spec: serde_json::Value) {
        let Ok(element) = crate::elements::charts::vega_lite_chart(spec, None) else { return };
        self.push(Rc::new(RefCell::new(element)));
    }

    fn plotly_chart(&self, spec: impl Into<String>) {
        self.push(Rc::new(RefCell::new(crate::elements::charts::plotly_chart(spec.into()))));
    }

    fn pydeck_chart(&self, json: impl Into<String>) {
        self.push(Rc::new(RefCell::new(crate::elements::charts::pydeck_chart(json.into()))));
    }

    fn graphviz_chart(&self, spec: impl Into<String>) {
        self.push(Rc::new(RefCell::new(crate::elements::charts::graphviz_chart(spec.into()))));
    }

    fn mermaid_chart(&self, body: impl Into<String>) {
        self.push(Rc::new(RefCell::new(crate::elements::charts::mermaid_element(body.into(), None))));
    }

    fn echarts_chart(&self, spec: serde_json::Value) {
        self.push(Rc::new(RefCell::new(crate::elements::charts::echarts_chart(spec))));
    }

    fn text<T: Into<TextOptions>>(&self, body: T) {
        let options = body.into();
        let mut element = TextElement::new(options.body);
        if let Some(width) = options.width {
            element = element.width(width);
        }
        if let Some(alignment) = options.text_alignment {
            element = element.text_alignment(alignment);
        }
        self.push(Rc::new(RefCell::new(element)));
    }

    fn latex(&self, formula: impl Into<String>) {
        // Measured (text-misc-params): the reference emits the display
        // formula as LATEX-typed markdown with wrap LEFT UNSET.
        let element = MarkdownElement::new(format!("$$\n{}\n$$", crate::utils::clean_text(&formula.into())))
            .element_type(MarkdownElementType::Latex)
            .wrap(None)
            .width(ElementWidth::Stretch);
        self.push(Rc::new(RefCell::new(element)));
    }

    fn html<T: Into<HtmlOptions>>(&self, body: T) {
        let options = body.into();
        self.push(Rc::new(RefCell::new(HtmlElement::new(options.body))));
    }

    fn iframe<T: Into<IFrameOptions>>(&self, body: T) {
        let options = body.into();
        let mut element = match options.source {
            IFrameSource::Src(url) => IframeElement::src(url),
            IFrameSource::Srcdoc(html) => IframeElement::srcdoc(html),
        };
        if let Some(height) = options.height {
            element = element.height(height);
        }
        self.push(Rc::new(RefCell::new(element)));
    }

    fn component_v2<'a>(&self, component: &crate::elements::components::ComponentV2, mount: impl Into<crate::elements::components::ComponentMount<'a>>) -> Result<serde_json::Value, WidgetError> {
        crate::elements::components::mount_component(self, component, mount.into())
    }

    fn snow(&self) {
        self.push(Rc::new(RefCell::new(SnowElement)));
    }

    fn echo<F: FnOnce(&Self)>(&self, code: impl Into<String>, body: F)
    where
        Self: Sized,
    {
        emit_echo(self, code.into(), body);
    }

    fn exception<T: Into<ExceptionOptions>>(&self, error: T) {
        let options = error.into();
        self.push(Rc::new(RefCell::new(AppException::new(options.kind, options.message, options.stack_trace))));
    }

    fn page_link<'a>(&self, options: impl Into<crate::navigation::PageLinkOptions<'a>>) -> Result<(), WidgetError> {
        use crate::elements::input::InputElement;
        use crate::navigation::PageTarget;
        use crate::navigation::page_hash;
        let options = options.into();
        let (page, label, icon, script_hash, external) = match &options.target {
            PageTarget::Page(page) => (
                page.url_path.clone(),
                options.label.clone().unwrap_or_else(|| page.title.clone()),
                options.icon.clone().or_else(|| page.icon.clone()),
                page_hash(&page.url_path),
                false,
            ),
            PageTarget::Url(url) => {
                let label = options.label.clone().ok_or_else(|| WidgetError::InvalidValue("st.page_link cannot infer a label for an external URL".into()))?;
                if label.is_empty() {
                    return Err(WidgetError::InvalidValue("st.page_link cannot infer a label for an external URL".into()));
                }
                (url.clone(), label, options.icon.clone(), String::new(), true)
            }
        };
        let width_spec = match options.width {
            Some(pixels) if pixels > 0 => crate::proto::streamlit::width_config::WidthSpec::PixelWidth(pixels as u32),
            Some(_) => return Err(WidgetError::InvalidValue("width must be positive".into())),
            None => crate::proto::streamlit::width_config::WidthSpec::UseContent(true),
        };
        self.push(Rc::new(RefCell::new(InputElement(crate::proto::Element {
            width_config: Some(crate::proto::streamlit::WidthConfig { width_spec: Some(width_spec) }),
            r#type: Some(element::Type::PageLink(crate::proto::PageLink {
                page,
                label,
                icon: icon.unwrap_or_default(),
                page_script_hash: script_hash,
                help: options.help,
                disabled: options.disabled,
                external,
                ..Default::default()
            })),
            ..Default::default()
        }))));
        Ok(())
    }

    fn logo(&self, options: impl Into<LogoOptions>) {
        let options = options.into();
        let app = self.get_app();
        let mut app = app.lock();
        if app.session_state.run_control().is_some() {
            return;
        }
        let Some(context) = app.render_context_mut() else { return };
        if context.sender.is_none() {
            return;
        }
        let (image, image_type) = options.image.wire();
        let mut logo = crate::proto::Logo {
            image,
            image_type,
            size: options.size.to_string(),
            ..Default::default()
        };
        if let Some(link) = options.link {
            logo.link = link;
        }
        if let Some(icon) = options.icon_image {
            let (icon_image, icon_image_type) = icon.wire();
            logo.icon_image = icon_image;
            logo.icon_image_type = icon_image_type;
        }
        // The reference stamps metadata.active_script_hash on every enqueued
        // ForwardMsg (script_run_context.enqueue); the frontend's logo handler
        // dereferences it unconditionally, so omitting it blanks the page.
        let message = ForwardMsg {
            metadata: Some(crate::proto::ForwardMsgMetadata {
                cacheable: false,
                delta_path: Vec::new(),
                active_script_hash: context.active_script_hash.clone(),
            }),
            r#type: Some(forward_msg::Type::Logo(logo)),
            ..Default::default()
        };
        context.push(message);
    }

    fn help(&self, options: impl Into<HelpOptions>) {
        let options = options.into();
        let mut element = crate::elements::text::HelpElement::new(options.doc_string, options.type_name);
        if let Some(name) = options.name {
            element = element.name(name);
        }
        if let Some(value) = options.value {
            element = element.value(value);
        }
        self.push(Rc::new(RefCell::new(element)));
    }

    fn skeleton(&self, options: impl Into<SkeletonOptions>) -> &EmptyHandle<'_> {
        let options = options.into();
        let app = self.get_app();
        let slot_path = self.next_child_path();
        self.push(Rc::new(RefCell::new(crate::elements::text::SkeletonElement::new(options.width, options.height))));
        self.allocator().malloc(EmptyHandle::new(self.allocator(), app, self.parent_form_id(), slot_path))
    }

    fn pdf(&self, data: impl Into<String>) {
        let _ = data.into();
        // The pinned reference lacks the optional streamlit-pdf component;
        // its st.pdf raises before any viewer element streams. Mirror that
        // measured path: the full error path type, the exact message, the
        // markdown + streamlit-error flags, and an empty trace (the
        // reference's trace lines name the caller's Python file).
        let message = "The PDF viewer requires the `streamlit-pdf` component to be installed.\n\nPlease run `pip install streamlit[pdf]` to install it.\n\nFor more information, see the Streamlit PDF documentation at https://docs.streamlit.io/develop/api-reference/media/st.pdf.";
        let exception = AppException::new("streamlit.errors.StreamlitAPIException".to_string(), message.to_string(), Vec::new()).streamlit_markdown();
        self.push(Rc::new(RefCell::new(exception)));
    }

    fn set_page_config(&self, options: impl Into<PageConfigOptions>) {
        let page_config: crate::proto::PageConfig = options.into().into();
        let app = self.get_app();
        let mut app = app.lock();
        // Like every other output, a run ended by st.rerun/st.stop streams
        // nothing further.
        if app.session_state.run_control().is_some() {
            return;
        }
        if let Some(context) = app.render_context_mut()
            && context.sender.is_some()
        {
            let mut message = ForwardMsg {
                hash: "page_config_changed".to_string(),
                ..Default::default()
            };
            message.r#type = Some(forward_msg::Type::PageConfigChanged(page_config));
            context.push(message);
        }
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

        let mut element = MarkdownElement::new(body.body).unsafe_allow_html(body.unsafe_allow_html).help(body.help.unwrap_or_default()).text_alignment(body.text_alignment);
        if let Some(width) = body.width {
            element = element.width(width);
        }

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
        let element = MarkdownElement::new("---".to_string()).element_type(MarkdownElementType::Divider).wrap(None).width(match body {
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

    fn sidebar(&self) -> &Sidebar<'_> {
        let app = self.get_app();
        let exit_path = self.next_child_path();
        self.allocator().malloc(Sidebar::new(self.allocator(), app, self.parent_form_id(), exit_path))
    }

    fn bottom(&self) -> &Bottom<'_> {
        let app = self.get_app();
        let exit_path = self.next_child_path();
        self.allocator().malloc(Bottom::new(self.allocator(), app, self.parent_form_id(), exit_path))
    }

    fn status<T: Into<StatusContainerOptions>>(&self, options: T) -> &Status<'_> {
        let options = options.into();
        let element = Rc::new(RefCell::new(StatusElement::new(options.label, options.expanded)));
        let app = self.get_app();
        let base_path = self.next_child_path();
        self.push(element.clone());
        let exit_path = app.lock().render_context_mut().map(|context| context.delta_path.clone()).unwrap_or_default();
        self.allocator().malloc(Status::new(element, self.allocator(), app, self.parent_form_id(), base_path, exit_path))
    }

    fn empty(&self) -> &EmptyHandle<'_> {
        let app = self.get_app();
        let slot_path = self.next_child_path();
        self.push(Rc::new(RefCell::new(EmptyElement)));
        self.allocator().malloc(EmptyHandle::new(self.allocator(), app, self.parent_form_id(), slot_path))
    }

    fn json<T: serde::Serialize>(&self, body: T) {
        self.json_expanded(body, true);
    }

    fn json_expanded<T: serde::Serialize>(&self, body: T, expanded: bool) {
        if let Ok(value) = serde_json::to_value(&body) {
            let body = match value {
                serde_json::Value::String(text) => text,
                value => crate::pywire::py_dumps(&value),
            };
            self.push(Rc::new(RefCell::new(JsonElement::new(body, expanded))));
        }
    }

    fn space(&self, size: u32) {
        self.push(Rc::new(RefCell::new(SpaceElement::new(size))));
    }

    fn expander_options(&self, options: ExpanderOptions) -> &Expander<'_> {
        let element = Rc::new(RefCell::new(ExpanderElement::new(options)));
        let app = self.get_app();
        let base_path = self.next_child_path();
        self.push(element.clone());
        let exit_path = app.lock().render_context_mut().map(|context| context.delta_path.clone()).unwrap_or_default();
        self.allocator().malloc(Expander::new(element, self.allocator(), app, self.parent_form_id(), base_path, exit_path))
    }

    fn chat_message_options(&self, options: ChatMessageOptions) -> &ChatMessage<'_> {
        let element = Rc::new(RefCell::new(ChatMessageElement::new(options)));
        let app = self.get_app();
        let base_path = self.next_child_path();
        self.push(element.clone());
        let exit_path = app.lock().render_context_mut().map(|context| context.delta_path.clone()).unwrap_or_default();
        self.allocator().malloc(ChatMessage::new(element, self.allocator(), app, self.parent_form_id(), base_path, exit_path))
    }

    fn tabs<'a, T: Into<TabsOptions<'a>>>(&self, labels: T) -> &[Tab<'_>] {
        let options = labels.into();
        if options.labels.is_empty() {
            return &[];
        }
        let element = Rc::new(RefCell::new(TabsElement::new(options.labels, options.default_tab, options.width, options.height)));
        let app = self.get_app();
        let base_path = self.next_child_path();
        self.push(element.clone());
        let exit_path = app.lock().render_context_mut().map(|context| context.delta_path.clone()).unwrap_or_default();

        let tabs: Vec<Tab<'_>> = (0..element.borrow().tab_count())
            .map(|index| Tab::new(index, element.clone(), self.allocator(), app.clone(), self.parent_form_id(), base_path.clone(), exit_path.clone()))
            .collect();
        self.allocator().malloc(tabs).as_slice()
    }

    fn popover_options(&self, options: PopoverOptions) -> &Popover<'_> {
        let element = Rc::new(RefCell::new(PopoverElement::new(options)));
        let app = self.get_app();
        let base_path = self.next_child_path();
        self.push(element.clone());
        let exit_path = app.lock().render_context_mut().map(|context| context.delta_path.clone()).unwrap_or_default();
        self.allocator().malloc(Popover::new(element, self.allocator(), app, self.parent_form_id(), base_path, exit_path))
    }

    fn dialog<T, F: FnOnce(&DialogBody<'_>) -> T>(&self, options: impl Into<DialogOptions>, body: F) -> T {
        let options = options.into();
        let app = self.get_app();
        let script_hash = app.lock().render_context_mut().map(|context| context.active_script_hash.clone()).unwrap_or_default();
        let element = Rc::new(RefCell::new(DialogElement::new(options, &script_hash)));
        let exit_path = self.next_child_path();
        self.push(element.clone());
        let dialog = self.allocator().malloc(DialogBody::new(element, self.allocator(), app, self.parent_form_id(), exit_path));
        body(dialog)
    }

    fn columns<T: Into<ColumnsOptions>>(&self, spec: T) -> &[Column<'_>] {
        let options = spec.into();

        // The reference computes weights in double precision (measured 1/3
        // stays 0.3333333333333333); the f32 spec values are widened first.
        let total: f64 = options.spec.iter().map(|w| *w as f64).sum();
        let weights: Vec<f64> = options.spec.iter().map(|w| *w as f64 / total).collect();

        if weights.is_empty() {
            return &[];
        }

        let container_element = Rc::new(RefCell::new(ContainerElement::new().columns_flex(options.gap.clone())));
        let app = self.get_app();
        let container_base = self.next_child_path();
        self.push(container_element.clone());
        let container_exit = app.lock().render_context_mut().map(|context| context.delta_path.clone()).unwrap_or_default();

        let mut columns = Vec::with_capacity(weights.len());
        for (index, w) in weights.iter().enumerate() {
            let column_element = Rc::new(RefCell::new(
                ColumnElement::new(*w).border(options.border).vertical_alignment(options.vertical_alignment.clone()).gap(options.gap.clone()).width(options.width.clone()),
            ));
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

    fn image<T: Into<ImageOptions>>(&self, options: T) {
        let options = options.into();
        if !options.image.valid() {
            log::error!("st.image needs width*height*4 RGBA pixels");
            return;
        }
        let png = crate::media::png_encode(&options.image);
        match crate::elements::media::media_url(&png, "image/png") {
            Ok(url) => {
                let element = crate::elements::media::ImgsElement::new(vec![(url, options.caption)], options.width);
                self.push(Rc::new(RefCell::new(element)));
            }
            Err(error) => log::error!("st.image failed to register media: {}", error),
        }
    }

    fn images(&self, options: ImageListOptions) {
        if options.images.len() != options.captions.len() && !options.captions.is_empty() {
            log::error!("st.images needs one caption per image");
            return;
        }
        let mut entries = Vec::with_capacity(options.images.len());
        for image in &options.images {
            if !image.valid() {
                log::error!("st.images needs width*height*4 RGBA pixels");
                return;
            }
            match crate::elements::media::media_url(&crate::media::png_encode(image), "image/png") {
                Ok(url) => entries.push((url, String::new())),
                Err(error) => {
                    log::error!("st.images failed to register media: {}", error);
                    return;
                }
            }
        }
        for (entry, caption) in entries.iter_mut().zip(options.captions) {
            entry.1 = caption;
        }
        let element = crate::elements::media::ImgsElement::new(entries, options.width);
        self.push(Rc::new(RefCell::new(element)));
    }

    fn audio<T: Into<AudioOptions>>(&self, options: T) {
        let options = options.into();
        match crate::elements::media::media_url(&options.data, &options.mime) {
            Ok(url) => {
                let element = crate::elements::media::AudioElement::new(url).with_playback(crate::elements::media::Playback {
                    start_time: options.start_time,
                    end_time: options.end_time,
                    loop_: options.loop_,
                    autoplay: options.autoplay,
                    muted: false,
                });
                self.push(Rc::new(RefCell::new(element)));
            }
            Err(error) => log::error!("st.audio failed to register media: {}", error),
        }
    }

    fn video<T: Into<VideoOptions>>(&self, options: T) {
        let options = options.into();
        if let Some(url) = options.url.clone() {
            // Measured: a direct URL bypasses the media store entirely.
            let element = crate::elements::media::VideoElement::new(url).with_playback(crate::elements::media::Playback {
                start_time: options.start_time,
                end_time: options.end_time,
                loop_: options.loop_,
                autoplay: options.autoplay,
                muted: options.muted,
            });
            self.push(Rc::new(RefCell::new(element)));
            return;
        }
        // Subtitles resolve first: invalid text renders the reference's API
        // exception element instead of the player (measured media-params).
        let mut tracks = Vec::new();
        for (label, text) in &options.subtitles {
            match crate::elements::media::subtitle_track(label, text) {
                Ok(track) => tracks.push(track),
                Err(message) => {
                    let exception = crate::elements::exception::AppException::new(
                        "streamlit.errors.StreamlitAPIException".into(),
                        message,
                        vec![format!("streamlit-rust: the video subtitle track {label:?} was rejected by VTT/SRT validation")],
                    )
                    .streamlit_markdown();
                    self.push(Rc::new(RefCell::new(exception)));
                    return;
                }
            }
        }
        match crate::elements::media::media_url(&options.data, &options.mime) {
            Ok(url) => {
                let element = crate::elements::media::VideoElement::new(url)
                    .with_playback(crate::elements::media::Playback {
                        start_time: options.start_time,
                        end_time: options.end_time,
                        loop_: options.loop_,
                        autoplay: options.autoplay,
                        muted: options.muted,
                    })
                    .with_subtitles(tracks);
                self.push(Rc::new(RefCell::new(element)));
            }
            Err(error) => log::error!("st.video failed to register media: {}", error),
        }
    }

    fn metric<T: Into<MetricOptions>>(&self, options: T) {
        let options = options.into();
        let element = crate::elements::media::MetricElement::new(options.label, options.value, options.delta, options.delta_color);
        self.push(Rc::new(RefCell::new(element)));
    }

    fn progress(&self, value: u32) -> Result<Progress, WidgetError> {
        if value > 100 {
            return Err(WidgetError::InvalidValue("progress value must be within 0..=100".into()));
        }
        let element = Rc::new(RefCell::new(crate::elements::media::ProgressElement::new(value)));
        self.push(element.clone());
        Ok(Progress { element })
    }

    fn progress_options(&self, options: impl Into<ProgressOptions>) -> Result<Progress, WidgetError> {
        let options = options.into();
        if options.value > 100 {
            return Err(WidgetError::InvalidValue("progress value must be within 0..=100".into()));
        }
        let mut element = crate::elements::media::ProgressElement::new(options.value);
        if !options.text.is_empty() {
            element.set_text(options.text);
        }
        let element = Rc::new(RefCell::new(element));
        self.push(element.clone());
        Ok(Progress { element })
    }

    fn toast<T: Into<ToastOptions>>(&self, options: T) {
        let options = options.into();
        let element = crate::elements::media::ToastElement::new(options.body, options.icon, options.duration);
        self.push(Rc::new(RefCell::new(element)));
    }

    fn balloons(&self) {
        self.push(Rc::new(RefCell::new(crate::elements::media::BalloonsElement)));
    }

    fn spinner<T>(&self, text: impl Into<String>, body: impl FnOnce() -> T) -> T {
        self.push(Rc::new(RefCell::new(crate::elements::media::SpinnerTransientElement::active(text.into()))));
        let result = body();
        self.push(Rc::new(RefCell::new(crate::elements::media::SpinnerTransientElement::cleared())));
        result
    }
}

#[cfg(test)]
mod quality_tests {
    use super::*;

    #[test]
    fn logo_string_conversions_recognize_complete_emoji_sequences() {
        for value in ["🧊", "🛠️", "🛠", "👩‍💻", "👨‍👩‍👧‍👦", "🏳️‍🌈", "🇨🇳", "1️⃣", "👍🏽", "👩🏽‍💻"] {
            assert_eq!(LogoImage::from(value), LogoImage::Emoji(value.into()));
            assert_eq!(LogoImage::from(value.to_owned()), LogoImage::Emoji(value.into()));
        }
        assert_eq!(LogoImage::from(":material/home:"), LogoImage::Icon(":material/home:".into()));
        for value in ["https://example.invalid/logo.png", "data:image/png;base64,AA==", "/app/static/logo.png"] {
            assert_eq!(LogoImage::from(value), LogoImage::Url(value.into()));
            assert_eq!(LogoImage::from(value.to_owned()), LogoImage::Url(value.into()));
        }
    }

    #[test]
    fn json_public_calls_preserve_string_bodies_and_serialize_nested_strings() -> anyhow::Result<()> {
        // 1. 通过公共 API 写入三类顶层字符串和嵌套字符串对照。
        let st = Streamlit::new();
        let (sender, mut receiver) = tokio::sync::mpsc::unbounded_channel();
        let mut context = crate::elements::common::RenderContext::with_sender("json-unit".into(), sender);
        context.delta_path = vec![0, 0];
        st.app.lock().set_render_context(context);
        let text = "\n{\"emoji\": \"🤖\"}\t";

        st.json(text);
        st.json_expanded(text.to_owned(), false);
        st.json(serde_json::Value::String(text.into()));
        let nested = serde_json::json!({"nested": text});
        st.json(&nested);

        // 2. 从实际消息通道读取载荷，检查原文、展开标志和嵌套转义。
        let mut observed = Vec::new();
        while let Ok(message) = receiver.try_recv() {
            let Some(crate::proto::forward_msg::Type::Delta(delta)) = message.r#type else { anyhow::bail!("expected JSON delta") };
            let Some(crate::proto::delta::Type::NewElement(element)) = delta.r#type else { anyhow::bail!("expected JSON element") };
            let Some(crate::proto::element::Type::Json(json)) = element.r#type else { anyhow::bail!("expected JSON payload") };
            observed.push(json);
        }
        assert_eq!(observed.len(), 4);
        for (json, expanded) in observed[..3].iter().zip([true, false, true]) {
            assert_eq!(json.body, text);
            assert_eq!(json.expanded, expanded);
            assert_eq!(json.max_expand_depth, None);
        }
        assert_eq!(serde_json::from_str::<serde_json::Value>(&observed[3].body)?, nested);
        assert!(observed[3].expanded);
        Ok(())
    }

    #[test]
    fn public_markdown_width_presence_and_badge_alignment_match_reference() -> anyhow::Result<()> {
        // 1. 公共调用区分默认与显式宽度，caption 和 badge 作为默认值对照。
        let st = Streamlit::new();
        let (sender, mut receiver) = tokio::sync::mpsc::unbounded_channel();
        let mut context = crate::elements::common::RenderContext::with_sender("layout-unit".into(), sender);
        context.delta_path = vec![0, 0];
        st.app.lock().set_render_context(context);

        st.markdown("default");
        st.markdown(MarkdownOptions::new("stretch".into()).width(ElementWidth::Stretch));
        st.markdown(MarkdownOptions::new("content".into()).width(ElementWidth::Content));
        st.markdown(MarkdownOptions::new("pixels".into()).width(240));
        st.caption("caption");
        st.badge("badge");

        // 2. 实际通道载荷验证配置存在性。
        let mut elements = Vec::new();
        while let Ok(message) = receiver.try_recv() {
            let Some(crate::proto::forward_msg::Type::Delta(delta)) = message.r#type else { anyhow::bail!("expected layout delta") };
            let Some(crate::proto::delta::Type::NewElement(element)) = delta.r#type else { anyhow::bail!("expected layout element") };
            elements.push(element);
        }
        assert_eq!(elements.len(), 6);
        use crate::proto::streamlit::width_config::WidthSpec;
        let widths = elements.iter().map(|element| element.width_config.as_ref().and_then(|width| width.width_spec)).collect::<Vec<_>>();
        assert_eq!(
            widths,
            [
                None,
                Some(WidthSpec::UseStretch(true)),
                Some(WidthSpec::UseContent(true)),
                Some(WidthSpec::PixelWidth(240)),
                Some(WidthSpec::UseStretch(true)),
                Some(WidthSpec::UseContent(true))
            ]
        );
        assert!(elements[..5].iter().all(|element| element.text_alignment_config.is_some()));
        assert!(elements[5].text_alignment_config.is_none());
        Ok(())
    }

    #[tokio::test]
    async fn joined_futures_share_one_task_local_streamlit_state() -> anyhow::Result<()> {
        let st = Streamlit::new();
        let initial_count = Rc::strong_count(&st.app);

        let writer = async {
            st.session_state().set("quality", true)?;
            tokio::task::yield_now().await;

            Ok::<_, anyhow::Error>(())
        };
        let reader = async {
            tokio::task::yield_now().await;
            st.session_state().get::<bool>("quality")
        };

        let (written, clicked) = tokio::join!(writer, reader);
        written?;

        assert_eq!(initial_count, 1);
        assert_eq!(clicked?, Some(true));

        Ok(())
    }
}
