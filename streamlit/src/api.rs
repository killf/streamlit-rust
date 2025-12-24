use crate::elements::badge::BadgeElement;
use crate::elements::button::ButtonElement;
use crate::elements::code::CodeElement;
use crate::elements::columns::{Column, ColumnElement};
use crate::elements::common::{Anchor, Divider, Element, ElementHeight, ElementWidth, Gap, HorizontalAlignment, TextAlignment, VerticalAlignment};
use crate::elements::container::{Container, ContainerElement};
use crate::elements::markdown::{MarkdownElement, MarkdownElementType};
use crate::elements::title::HeadingElement;
use crate::elements::{App, WidgetValue};
use crate::memory::Allocator;
use crate::proto::WidgetState;
use crate::utils::hash::hash;
use parking_lot::Mutex;
use std::cell::RefCell;
use std::sync::Arc;

/// Streamlit Rust API - provides a Python-like Streamlit interface
pub struct Streamlit {
    pub(crate) app: Arc<Mutex<App>>,
    allocator: Allocator,
}

impl Streamlit {
    pub(crate) fn new() -> Self {
        Self {
            app: Arc::new(Mutex::new(App::new())),
            allocator: Allocator::new(),
        }
    }

    pub(crate) fn process_widget_states(self, widget_states: Vec<WidgetState>) -> Self {
        self.app.lock().process_widget_states(widget_states);
        self
    }
}

pub(crate) trait AppendChild {
    fn push(&self, element: Arc<RefCell<dyn Element>>);

    fn allocator(&self) -> &Allocator;

    fn get_app(&self) -> Arc<Mutex<App>>;
}

impl AppendChild for Streamlit {
    fn push(&self, element: Arc<RefCell<dyn Element>>) {
        self.app.lock().push(element);
    }

    fn allocator(&self) -> &Allocator {
        &self.allocator
    }

    fn get_app(&self) -> Arc<Mutex<App>> {
        self.app.clone()
    }
}

pub struct WriteOptions {
    body: String,
    unsafe_allow_html: bool,
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
    label: String,
    key: Option<String>,
    help: Option<String>,
    r#type: String,
    icon: Option<String>,
    disabled: bool,
    width: ElementWidth,
    shortcut: Option<String>,
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
        }
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

    fn columns<T: Into<ColumnsOptions>>(&self, spec: T) -> &[Column<'_>];

    fn button<T: Into<ButtonOptions>>(&self, options: T) -> bool;
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

    this.push(Arc::new(RefCell::new(element)));
}

impl<C: AppendChild> StreamlitApi for C {
    fn write<T: Into<WriteOptions>>(&self, body: T) {
        let body = body.into();
        let element = MarkdownElement::new(body.body).unsafe_allow_html(body.unsafe_allow_html);
        self.push(Arc::new(RefCell::new(element)));
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

        self.push(Arc::new(RefCell::new(element)));
    }

    fn badge<T: Into<BadgeOptions>>(&self, body: T) {
        let body = body.into();
        let element = BadgeElement::new(body.label).color(body.color).icon(body.icon.unwrap_or_default()).width(body.width).help(body.help.unwrap_or_default());
        self.push(Arc::new(RefCell::new(element)));
    }

    fn caption<T: Into<CaptionOptions>>(&self, body: T) {
        let body = body.into();
        let element = MarkdownElement::new(body.body)
            .element_type(MarkdownElementType::Caption)
            .unsafe_allow_html(body.unsafe_allow_html)
            .width(body.width)
            .help(body.help.unwrap_or_default())
            .text_alignment(body.text_alignment);
        self.push(Arc::new(RefCell::new(element)));
    }

    fn code_options<T: Into<CodeOptions>>(&self, code_options: T) {
        let body = code_options.into();
        let element = CodeElement::new(body.body, body.language).show_line_numbers(body.line_numbers).wrap_lines(body.wrap_lines).width(body.width).height(body.height);
        self.push(Arc::new(RefCell::new(element)));
    }

    fn divider_options<T: Into<DividerOptions>>(&self, options: T) {
        let body = options.into();
        let element = MarkdownElement::new("---".to_string()).element_type(MarkdownElementType::Divider).width(match body {
            DividerOptions::Stretch => ElementWidth::Stretch,
            DividerOptions::Width(v) => ElementWidth::Value(v),
        });
        self.push(Arc::new(RefCell::new(element)));
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

        let element = Arc::new(RefCell::new(element));
        self.push(element.clone());

        self.allocator().malloc(Container::new(element, self.allocator(), self.get_app()))
    }

    fn columns<T: Into<ColumnsOptions>>(&self, spec: T) -> &[Column<'_>] {
        let options = spec.into();

        let total: f32 = options.spec.iter().sum();
        let weights: Vec<f32> = options.spec.iter().map(|w| w / total).collect();

        if weights.is_empty() {
            return &[];
        }

        let container_element = Arc::new(RefCell::new(ContainerElement::new().horizontal(true).gap(options.gap)));
        self.push(container_element.clone());

        let columns = self.allocator().malloc(vec![]);
        for w in weights {
            let column_element = Arc::new(RefCell::new(ColumnElement::new(w).border(options.border).vertical_alignment(options.vertical_alignment.clone()).width(options.width.clone())));
            container_element.borrow_mut().children.push(column_element.clone());

            columns.push(Column::new(column_element, self.allocator(), self.get_app()));
        }
        columns.as_slice()
    }

    /// Display a button and return whether it was clicked
    fn button<T: Into<ButtonOptions>>(&self, options: T) -> bool {
        let options = options.into();

        let key = if let Some(key) = options.key { hash(key.as_str()) } else { hash(options.label.as_str()) };
        let button_id = format!("$$ID-{}", key);

        // Check if this button was previously clicked
        let app = self.get_app();
        let was_clicked = app
            .lock()
            .get_widget_state(button_id.as_str())
            .and_then(|value| match value {
                WidgetValue::Boolean(b) => Some(b),
                _ => None,
            })
            .unwrap_or(false);

        // Reset button state after checking
        if was_clicked {
            app.lock().set_widget_state(button_id.clone(), WidgetValue::Boolean(false));
        }

        // Create the button element with consistent ID
        let element = ButtonElement::new(button_id, options.label)
            .help(options.help.unwrap_or_default())
            .r#type(options.r#type)
            .icon(options.icon.unwrap_or_default())
            .shortcut(options.shortcut.unwrap_or_default())
            .width(options.width);

        self.push(Arc::new(RefCell::new(element)));

        was_clicked
    }
}
