//! The measured 1.66.1 layout blocks: the expander, the tabs container with
//! its tab blocks, the popover, the dialog (two add_blocks on the event root
//! plus a flex content container) and the fixed sidebar root, which takes no
//! block at all (see .codex/compatibility.md, Layouts).

use crate::api::AppendChild;
use crate::elements::App;
use crate::elements::common::{Element, ElementHeight, ElementWidth, RenderContext};
use crate::error::StreamlitError;
use crate::memory::Allocator;
use crate::proto::block::dialog::{DialogPosition, DialogWidth};
use crate::proto::block::flex_container::{Align, Direction, Justify};
use crate::proto::block::{Dialog, Expandable, FlexContainer, TabContainer};
use crate::proto::block::{Popover as PopoverProto, Tab as TabProto};
use crate::proto::{Block, Delta, delta, delta_base_with_path, forward_msg};
use crate::utils::hash::hash;
use parking_lot::Mutex;
use std::cell::RefCell;
use std::rc::Rc;

/// The expander's visual style (Python `type=`): the bordered default or the
/// minimal compact toggle; STEP stays unmeasured.
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
pub enum ExpanderKind {
    #[default]
    Default,
    Compact,
}

impl ExpanderKind {
    fn wire(self) -> crate::proto::block::expandable::Type {
        match self {
            Self::Default => crate::proto::block::expandable::Type::Default,
            Self::Compact => crate::proto::block::expandable::Type::Compact,
        }
    }
}

/// Expander options: label, expanded, icon, and the visual style.
pub struct ExpanderOptions {
    label: String,
    expanded: bool,
    icon: String,
    pub(crate) kind: ExpanderKind,
}

impl ExpanderOptions {
    pub fn new(label: impl Into<String>) -> Self {
        Self {
            label: label.into(),
            expanded: false,
            icon: String::new(),
            kind: ExpanderKind::Default,
        }
    }
    pub fn expanded(mut self, expanded: bool) -> Self {
        self.expanded = expanded;
        self
    }
    pub fn icon(mut self, icon: impl Into<String>) -> Self {
        self.icon = icon.into();
        self
    }
    /// The visual style: the bordered default or the minimal inline toggle
    /// (Python `type="compact"`).
    pub fn kind(mut self, kind: ExpanderKind) -> Self {
        self.kind = kind;
        self
    }
}

impl From<&str> for ExpanderOptions {
    fn from(label: &str) -> Self {
        Self::new(label)
    }
}

/// The popover's button style (Python `type=`): secondary (default) or
/// primary.
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
pub enum PopoverKind {
    #[default]
    Secondary,
    Primary,
}

impl PopoverKind {
    fn wire(self) -> &'static str {
        match self {
            Self::Secondary => "secondary",
            Self::Primary => "primary",
        }
    }
}

/// Popover options: label, icon, button style, help, disabled, and whether
/// the trigger stretches with the container (the block's width).
pub struct PopoverOptions {
    label: String,
    icon: String,
    pub(crate) kind: PopoverKind,
    pub(crate) help: String,
    pub(crate) disabled: bool,
    pub(crate) use_container_width: bool,
    pub(crate) wrap: bool,
}

impl PopoverOptions {
    pub fn new(label: impl Into<String>) -> Self {
        Self {
            label: label.into(),
            icon: String::new(),
            kind: PopoverKind::Secondary,
            help: String::new(),
            disabled: false,
            use_container_width: false,
            wrap: false,
        }
    }
    pub fn icon(mut self, icon: impl Into<String>) -> Self {
        self.icon = icon.into();
        self
    }
    /// The trigger's button style (Python `type="primary"`).
    pub fn kind(mut self, kind: PopoverKind) -> Self {
        self.kind = kind;
        self
    }
    /// The trigger's help tooltip text.
    pub fn help(mut self, help: impl Into<String>) -> Self {
        self.help = help.into();
        self
    }
    /// Disable the trigger.
    pub fn disabled(mut self, disabled: bool) -> Self {
        self.disabled = disabled;
        self
    }
    /// Stretch the trigger with the container (the block carries a stretch
    /// width instead of content).
    pub fn use_container_width(mut self, value: bool) -> Self {
        self.use_container_width = value;
        self
    }

    /// Wrap the trigger's label text (Python `wrap=True`).
    pub fn wrap(mut self, value: bool) -> Self {
        self.wrap = value;
        self
    }
}

impl From<&str> for PopoverOptions {
    fn from(label: &str) -> Self {
        Self::new(label)
    }
}

/// Tabs options: just the labels, in order.
pub struct TabsOptions<'a> {
    pub(crate) labels: Vec<String>,
    pub(crate) default_tab: Option<String>,
    pub(crate) width: Option<ElementWidth>,
    pub(crate) height: Option<ElementHeight>,
    _marker: std::marker::PhantomData<&'a ()>,
}

impl<'a> TabsOptions<'a> {
    pub fn new(labels: impl IntoIterator<Item = impl Into<String>>) -> Self {
        Self {
            labels: labels.into_iter().map(Into::into).collect(),
            default_tab: None,
            _marker: std::marker::PhantomData,
            width: None,
            height: None,
        }
    }

    /// The label of the tab selected on load (Python's `default` takes a
    /// label, not a position). An unknown label is logged and ignored —
    /// Python raises instead; the divergence is recorded in the guide.
    pub fn default_tab(mut self, label: impl Into<String>) -> Self {
        self.default_tab = Some(label.into());
        self
    }

    /// The tab strip's pixel width (the block's width config).
    pub fn width(mut self, pixels: i32) -> Self {
        self.width = Some(ElementWidth::Value(pixels));
        self
    }

    /// The tab strip's pixel height (the block's height config).
    pub fn height(mut self, pixels: i32) -> Self {
        self.height = Some(ElementHeight::Value(pixels));
        self
    }
}

impl<'a, const N: usize> From<[&'a str; N]> for TabsOptions<'a> {
    fn from(labels: [&'a str; N]) -> Self {
        Self::new(labels.iter().copied())
    }
}

impl<'a> From<&'a [&'a str]> for TabsOptions<'a> {
    fn from(labels: &'a [&'a str]) -> Self {
        Self::new(labels.iter().copied())
    }
}

impl<'a> From<&'a Vec<&'a str>> for TabsOptions<'a> {
    fn from(labels: &'a Vec<&'a str>) -> Self {
        Self::new(labels.iter().copied())
    }
}

impl<'a> From<Vec<String>> for TabsOptions<'a> {
    fn from(labels: Vec<String>) -> Self {
        Self {
            labels,
            default_tab: None,
            width: None,
            height: None,
            _marker: std::marker::PhantomData,
        }
    }
}

/// Dialog options: the measured subset (title, width, position, dismissible,
/// icon). The measured default is small/center/dismissible.
pub struct DialogOptions {
    title: String,
    width: DialogWidth,
    position: DialogPosition,
    dismissible: bool,
    icon: String,
}

impl DialogOptions {
    pub fn new(title: impl Into<String>) -> Self {
        Self {
            title: title.into(),
            width: DialogWidth::Small,
            position: DialogPosition::Center,
            dismissible: true,
            icon: String::new(),
        }
    }
    pub fn width(mut self, width: DialogWidth) -> Self {
        self.width = width;
        self
    }
    pub fn position(mut self, position: DialogPosition) -> Self {
        self.position = position;
        self
    }
    pub fn dismissible(mut self, dismissible: bool) -> Self {
        self.dismissible = dismissible;
        self
    }
    pub fn icon(mut self, icon: impl Into<String>) -> Self {
        self.icon = icon.into();
        self
    }
    /// The Python str() of each id input, in the reference's call order.
    fn id_inputs(&self) -> Vec<(&'static str, String)> {
        vec![
            ("title", self.title.clone()),
            ("dismissible", py_bool(self.dismissible)),
            ("width", self.width.python_value().to_string()),
            ("position", self.position.python_value().to_string()),
            ("icon", py_str_none(&self.icon)),
            ("on_dismiss", "ignore".into()),
        ]
    }
}

impl From<&str> for DialogOptions {
    fn from(title: &str) -> Self {
        Self::new(title)
    }
}

trait PythonValue {
    fn python_value(self) -> &'static str;
}

impl PythonValue for DialogWidth {
    fn python_value(self) -> &'static str {
        match self {
            DialogWidth::Small => "small",
            DialogWidth::Large => "large",
            DialogWidth::Medium => "medium",
        }
    }
}

impl PythonValue for DialogPosition {
    fn python_value(self) -> &'static str {
        match self {
            DialogPosition::Center => "center",
            DialogPosition::Left => "left",
            DialogPosition::Right => "right",
        }
    }
}

fn py_bool(value: bool) -> String {
    if value { "True".into() } else { "False".into() }
}

fn py_str_none(value: &str) -> String {
    if value.is_empty() { "None".into() } else { value.to_string() }
}

/// The reference names a dialog `$$ID-<blake2b16 of the inputs>-<key>`;
/// the hash mixes the runtime's script identity, which has no cross-runtime
/// counterpart, so each side hashes its own identity the same way.
pub(crate) fn dialog_id(options: &DialogOptions, active_script_hash: &str) -> String {
    use blake2::digest::consts::U16;
    use blake2::{Blake2b, Digest};
    let mut hasher = Blake2b::<U16>::new();
    hasher.update(b"dialog");
    for (key, value) in options.id_inputs() {
        hasher.update(key.as_bytes());
        hasher.update(value.as_bytes());
    }
    for (key, value) in [("active_script_hash", active_script_hash.to_string()), ("form_id", String::new()), ("active_dg_root_container", "2".to_string())] {
        hasher.update(key.as_bytes());
        hasher.update(value.as_bytes());
    }
    format!("$$ID-{:x}-None", hasher.finalize())
}

pub(crate) struct ExpanderElement {
    options: ExpanderOptions,
    pub(crate) children: Vec<Rc<RefCell<dyn Element>>>,
}

/// The st.chat_message container: a chat_message block (name, avatar,
/// ICON avatar type, allowEmpty, stretch width) with children at
/// [slot, k] (the measured 1.66.1 shape; the avatar defaults to the name).
pub(crate) struct ChatMessageElement {
    name: String,
    avatar: String,
    avatar_type: crate::proto::block::chat_message::AvatarType,
    pub(crate) children: Vec<Rc<RefCell<dyn Element>>>,
}

/// Options for `st.chat_message`: the speaker name and an optional avatar
/// (a material shortcode or emoji; defaults to the name).
pub struct ChatMessageOptions {
    pub(crate) name: String,
    pub(crate) avatar: Option<String>,
}

impl ChatMessageOptions {
    pub fn new(name: impl Into<String>) -> Self {
        Self { name: name.into(), avatar: None }
    }

    pub fn avatar(mut self, avatar: impl Into<String>) -> Self {
        self.avatar = Some(avatar.into());
        self
    }
}

impl From<&str> for ChatMessageOptions {
    fn from(name: &str) -> Self {
        Self::new(name)
    }
}

impl From<String> for ChatMessageOptions {
    fn from(name: String) -> Self {
        Self::new(name)
    }
}

impl ChatMessageElement {
    pub fn new(options: ChatMessageOptions) -> Self {
        // Measured typing (chat.py + frozen chat-metric-params): the name
        // default and material shortcodes are ICON; a bare emoji string is
        // EMOJI. Image/URL avatars stay unimplemented.
        let avatar_type = match &options.avatar {
            None => crate::proto::block::chat_message::AvatarType::Icon,
            Some(avatar) if avatar.starts_with(":material/") => crate::proto::block::chat_message::AvatarType::Icon,
            Some(_) => crate::proto::block::chat_message::AvatarType::Emoji,
        };
        let avatar = options.avatar.unwrap_or_else(|| options.name.clone());
        Self {
            name: options.name,
            avatar,
            avatar_type,
            children: Vec::new(),
        }
    }
}

impl Element for ChatMessageElement {
    fn render(&self, context: &mut RenderContext) -> Result<(), StreamlitError> {
        let element_hash = hash(format!("chat_message_{}_{}", self.name, self.avatar).as_str());
        let mut msg = delta_base_with_path(context.delta_path.clone(), context.active_script_hash.clone(), element_hash);
        msg.r#type = Some(forward_msg::Type::Delta(Delta {
            fragment_id: String::new(),
            r#type: Some(delta::Type::AddBlock(Block {
                autoscroll: None,
                allow_empty: true,
                id: None,
                height_config: None,
                width_config: Some(ElementWidth::Stretch.into()),
                r#type: Some(crate::proto::block::Type::ChatMessage(crate::proto::block::ChatMessage {
                    name: self.name.clone(),
                    avatar: self.avatar.clone(),
                    avatar_type: self.avatar_type as i32,
                })),
            })),
        }));
        context.push(msg);
        context.delta_path.push(0);
        for child in self.children.iter() {
            child.borrow().render(context)?;
        }
        context.delta_path.pop();
        if let Some(index) = context.delta_path.pop() {
            context.delta_path.push(index + 1);
        }
        Ok(())
    }
}

impl ExpanderElement {
    pub fn new(options: ExpanderOptions) -> Self {
        Self { options, children: Vec::new() }
    }
}

impl Element for ExpanderElement {
    fn render(&self, context: &mut RenderContext) -> Result<(), StreamlitError> {
        let element_hash = hash(format!("expander_{}_{}_{}", self.options.label, self.options.expanded, self.options.icon).as_str());
        let mut msg = delta_base_with_path(context.delta_path.clone(), context.active_script_hash.clone(), element_hash);
        msg.r#type = Some(forward_msg::Type::Delta(Delta {
            fragment_id: String::new(),
            r#type: Some(delta::Type::AddBlock(Block {
                autoscroll: None,
                allow_empty: true,
                id: None,
                height_config: None,
                width_config: Some(ElementWidth::Stretch.into()),
                r#type: Some(crate::proto::block::Type::Expandable(Expandable {
                    label: self.options.label.clone(),
                    expanded: Some(self.options.expanded),
                    icon: self.options.icon.clone(),
                    r#type: self.options.kind.wire() as i32,
                    ..Default::default()
                })),
            })),
        }));
        context.push(msg);

        context.delta_path.push(0);
        for child in self.children.iter() {
            child.borrow().render(context)?;
        }
        context.delta_path.pop();
        if let Some(index) = context.delta_path.pop() {
            context.delta_path.push(index + 1);
        }
        Ok(())
    }
}

pub(crate) struct PopoverElement {
    options: PopoverOptions,
    pub(crate) children: Vec<Rc<RefCell<dyn Element>>>,
}

impl PopoverElement {
    pub fn new(options: PopoverOptions) -> Self {
        Self { options, children: Vec::new() }
    }
}

impl Element for PopoverElement {
    fn render(&self, context: &mut RenderContext) -> Result<(), StreamlitError> {
        let element_hash = hash(
            format!(
                "popover_{}_{}_{:?}_{}_{}_{}",
                self.options.label, self.options.icon, self.options.kind, self.options.help, self.options.disabled, self.options.use_container_width
            )
            .as_str(),
        );
        let mut msg = delta_base_with_path(context.delta_path.clone(), context.active_script_hash.clone(), element_hash);
        let width = if self.options.use_container_width { ElementWidth::Stretch } else { ElementWidth::Content };
        msg.r#type = Some(forward_msg::Type::Delta(Delta {
            fragment_id: String::new(),
            r#type: Some(delta::Type::AddBlock(Block {
                autoscroll: None,
                allow_empty: true,
                id: None,
                height_config: None,
                width_config: Some(width.into()),
                r#type: Some(crate::proto::block::Type::Popover(PopoverProto {
                    label: self.options.label.clone(),
                    help: self.options.help.clone(),
                    disabled: self.options.disabled,
                    icon: self.options.icon.clone(),
                    r#type: self.options.kind.wire().into(),
                    open: Some(false),
                    wrap: Some(self.options.wrap),
                    ..Default::default()
                })),
            })),
        }));
        context.push(msg);

        context.delta_path.push(0);
        for child in self.children.iter() {
            child.borrow().render(context)?;
        }
        context.delta_path.pop();
        if let Some(index) = context.delta_path.pop() {
            context.delta_path.push(index + 1);
        }
        Ok(())
    }
}

/// One tab: its block (label only) and the elements written inside it.
pub(crate) struct TabsElement {
    labels: Vec<String>,
    default_tab_index: Option<usize>,
    width: Option<ElementWidth>,
    height: Option<ElementHeight>,
    pub(crate) tabs: Vec<Vec<Rc<RefCell<dyn Element>>>>,
}

impl TabsElement {
    pub fn new(labels: Vec<String>, default_tab: Option<String>, width: Option<ElementWidth>, height: Option<ElementHeight>) -> Self {
        let default_tab_index = match default_tab {
            Some(label) => match labels.iter().position(|candidate| candidate == &label) {
                Some(index) => Some(index),
                None => {
                    log::error!("st.tabs default_tab {label:?} matches no tab label; Python raises here");
                    None
                }
            },
            None => None,
        };
        Self {
            tabs: labels.iter().map(|_| Vec::new()).collect(),
            labels,
            default_tab_index,
            width,
            height,
        }
    }

    pub(crate) fn tab_count(&self) -> usize {
        self.labels.len()
    }
}

impl Element for TabsElement {
    fn render(&self, context: &mut RenderContext) -> Result<(), StreamlitError> {
        let element_hash = hash(format!("tabs_{}_{:?}", self.labels.join("|"), self.default_tab_index).as_str());
        let mut msg = delta_base_with_path(context.delta_path.clone(), context.active_script_hash.clone(), element_hash);
        msg.r#type = Some(forward_msg::Type::Delta(Delta {
            fragment_id: String::new(),
            r#type: Some(delta::Type::AddBlock(Block {
                autoscroll: None,
                allow_empty: false,
                id: None,
                height_config: Some(self.height.clone().unwrap_or(ElementHeight::Content).into()),
                width_config: Some(self.width.clone().unwrap_or(ElementWidth::Stretch).into()),
                r#type: Some(crate::proto::block::Type::TabContainer(TabContainer {
                    default_tab_index: self.default_tab_index.map(|index| index as i32).unwrap_or(0),
                    ..Default::default()
                })),
            })),
        }));
        context.push(msg);

        for (index, label) in self.labels.iter().enumerate() {
            context.delta_path.push(index as u32);
            let tab_hash = hash(format!("tab_{}_{}", index, label).as_str());
            let mut tab_msg = delta_base_with_path(context.delta_path.clone(), context.active_script_hash.clone(), tab_hash);
            tab_msg.r#type = Some(forward_msg::Type::Delta(Delta {
                fragment_id: String::new(),
                r#type: Some(delta::Type::AddBlock(Block {
                    autoscroll: None,
                    allow_empty: true,
                    id: None,
                    height_config: None,
                    width_config: None,
                    r#type: Some(crate::proto::block::Type::Tab(TabProto { label: label.clone() })),
                })),
            }));
            context.push(tab_msg);

            context.delta_path.push(0);
            for child in self.tabs[index].iter() {
                child.borrow().render(context)?;
            }
            context.delta_path.pop();
            context.delta_path.pop();
        }
        if let Some(index) = context.delta_path.pop() {
            context.delta_path.push(index + 1);
        }
        Ok(())
    }
}

/// The dialog: two add_blocks on the event root (the block itself, then the
/// same block reopened with isOpen), then the flex content container and its
/// children.
pub(crate) struct DialogElement {
    options: DialogOptions,
    id: String,
    pub(crate) children: Vec<Rc<RefCell<dyn Element>>>,
}

impl DialogElement {
    pub fn new(options: DialogOptions, active_script_hash: &str) -> Self {
        Self {
            id: dialog_id(&options, active_script_hash),
            options,
            children: Vec::new(),
        }
    }

    fn block(&self, is_open: Option<bool>) -> Block {
        Block {
            autoscroll: None,
            allow_empty: false,
            id: Some(self.id.clone()),
            height_config: None,
            width_config: None,
            r#type: Some(crate::proto::block::Type::Dialog(Dialog {
                title: self.options.title.clone(),
                dismissible: self.options.dismissible,
                width: self.options.width as i32,
                is_open,
                id: String::new(),
                icon: self.options.icon.clone(),
                position: self.options.position as i32,
            })),
        }
    }
}

impl Element for DialogElement {
    fn render(&self, context: &mut RenderContext) -> Result<(), StreamlitError> {
        // The dialog lives on the event root at slot 0, outside the normal
        // flow, whatever container it was opened from.
        let saved_path = context.delta_path.clone();
        context.delta_path = vec![2, 0];
        let element_hash = hash(format!("dialog_{}", self.id).as_str());
        let mut block = delta_base_with_path(context.delta_path.clone(), context.active_script_hash.clone(), element_hash.clone());
        block.r#type = Some(forward_msg::Type::Delta(Delta {
            fragment_id: String::new(),
            r#type: Some(delta::Type::AddBlock(self.block(None))),
        }));
        context.push(block);
        let mut open = delta_base_with_path(context.delta_path.clone(), context.active_script_hash.clone(), element_hash);
        open.r#type = Some(forward_msg::Type::Delta(Delta {
            fragment_id: String::new(),
            r#type: Some(delta::Type::AddBlock(self.block(Some(true)))),
        }));
        context.push(open);

        context.delta_path.push(0);
        let mut content = delta_base_with_path(context.delta_path.clone(), context.active_script_hash.clone(), hash(format!("dialog_content_{}", self.id).as_str()));
        content.r#type = Some(forward_msg::Type::Delta(Delta {
            fragment_id: String::new(),
            r#type: Some(delta::Type::AddBlock(Block {
                autoscroll: None,
                allow_empty: false,
                id: None,
                height_config: Some(ElementHeight::Content.into()),
                width_config: Some(ElementWidth::Stretch.into()),
                r#type: Some(crate::proto::block::Type::FlexContainer(FlexContainer {
                    border: false,
                    gap_config: Some(crate::elements::common::Gap::Small.into()),
                    scale: 0.0,
                    direction: Direction::Vertical as i32,
                    wrap: false,
                    justify: Justify::Start as i32,
                    align: Align::Start as i32,
                })),
            })),
        }));
        context.push(content);

        context.delta_path.push(0);
        for child in self.children.iter() {
            child.borrow().render(context)?;
        }
        context.delta_path.pop();
        context.delta_path.pop();
        context.delta_path = saved_path;
        Ok(())
    }
}

/// Renders children into a fixed block path and restores the exit path —
/// the shared push shape of every layout handle below.
pub(crate) fn push_at(element: Rc<RefCell<dyn Element>>, app: &Rc<Mutex<App>>, form_id: &Option<String>, base_path: &[u32], child_index: u32, exit_path: &[u32]) {
    if form_id.is_some() {
        return;
    }
    let mut app = app.lock();
    if let Some(context) = app.render_context_mut()
        && context.sender.is_some()
    {
        context.delta_path = base_path.to_vec();
        context.delta_path.push(child_index);
        if let Err(error) = element.borrow().render(context) {
            log::error!("Failed to render layout child immediately: {error}");
        }
        context.delta_path = exit_path.to_vec();
    }
}

pub struct Expander<'a> {
    element: Rc<RefCell<ExpanderElement>>,
    allocator: &'a Allocator,
    app: Rc<Mutex<App>>,
    form_id: Option<String>,
    base_path: Vec<u32>,
    exit_path: Vec<u32>,
}

/// The st.chat_message handle: children stream into the chat block.
pub struct ChatMessage<'a> {
    element: Rc<RefCell<ChatMessageElement>>,
    allocator: &'a Allocator,
    app: Rc<Mutex<App>>,
    form_id: Option<String>,
    base_path: Vec<u32>,
    exit_path: Vec<u32>,
}

impl<'a> ChatMessage<'a> {
    pub(crate) fn new(element: Rc<RefCell<ChatMessageElement>>, allocator: &'a Allocator, app: Rc<Mutex<App>>, form_id: Option<String>, base_path: Vec<u32>, exit_path: Vec<u32>) -> Self {
        Self {
            element,
            allocator,
            app,
            form_id,
            base_path,
            exit_path,
        }
    }
}

impl AppendChild for ChatMessage<'_> {
    fn push(&self, element: Rc<RefCell<dyn Element>>) {
        let child_index = self.element.borrow().children.len() as u32;
        self.element.borrow_mut().children.push(element.clone());
        push_at(element, &self.app, &self.form_id, &self.base_path, child_index, &self.exit_path);
    }

    fn allocator(&self) -> &Allocator {
        self.allocator
    }

    fn get_app(&self) -> Rc<Mutex<App>> {
        self.app.clone()
    }

    fn parent_form_id(&self) -> Option<String> {
        self.form_id.clone()
    }

    fn next_child_path(&self) -> Vec<u32> {
        let mut path = self.base_path.clone();
        path.push(self.element.borrow().children.len() as u32);
        path
    }
}

impl<'a> Expander<'a> {
    pub(crate) fn new(element: Rc<RefCell<ExpanderElement>>, allocator: &'a Allocator, app: Rc<Mutex<App>>, form_id: Option<String>, base_path: Vec<u32>, exit_path: Vec<u32>) -> Self {
        Self {
            element,
            allocator,
            app,
            form_id,
            base_path,
            exit_path,
        }
    }
}

impl AppendChild for Expander<'_> {
    fn push(&self, element: Rc<RefCell<dyn Element>>) {
        let child_index = self.element.borrow().children.len() as u32;
        self.element.borrow_mut().children.push(element.clone());
        push_at(element, &self.app, &self.form_id, &self.base_path, child_index, &self.exit_path);
    }

    fn allocator(&self) -> &Allocator {
        self.allocator
    }

    fn get_app(&self) -> Rc<Mutex<App>> {
        self.app.clone()
    }

    fn parent_form_id(&self) -> Option<String> {
        self.form_id.clone()
    }

    fn next_child_path(&self) -> Vec<u32> {
        let mut path = self.base_path.clone();
        path.push(self.element.borrow().children.len() as u32);
        path
    }
}

pub struct Popover<'a> {
    element: Rc<RefCell<PopoverElement>>,
    allocator: &'a Allocator,
    app: Rc<Mutex<App>>,
    form_id: Option<String>,
    base_path: Vec<u32>,
    exit_path: Vec<u32>,
}

impl<'a> Popover<'a> {
    pub(crate) fn new(element: Rc<RefCell<PopoverElement>>, allocator: &'a Allocator, app: Rc<Mutex<App>>, form_id: Option<String>, base_path: Vec<u32>, exit_path: Vec<u32>) -> Self {
        Self {
            element,
            allocator,
            app,
            form_id,
            base_path,
            exit_path,
        }
    }
}

impl AppendChild for Popover<'_> {
    fn push(&self, element: Rc<RefCell<dyn Element>>) {
        let child_index = self.element.borrow().children.len() as u32;
        self.element.borrow_mut().children.push(element.clone());
        push_at(element, &self.app, &self.form_id, &self.base_path, child_index, &self.exit_path);
    }

    fn allocator(&self) -> &Allocator {
        self.allocator
    }

    fn get_app(&self) -> Rc<Mutex<App>> {
        self.app.clone()
    }

    fn parent_form_id(&self) -> Option<String> {
        self.form_id.clone()
    }

    fn next_child_path(&self) -> Vec<u32> {
        let mut path = self.base_path.clone();
        path.push(self.element.borrow().children.len() as u32);
        path
    }
}

pub struct Tab<'a> {
    index: usize,
    tabs: Rc<RefCell<TabsElement>>,
    allocator: &'a Allocator,
    app: Rc<Mutex<App>>,
    form_id: Option<String>,
    base_path: Vec<u32>,
    exit_path: Vec<u32>,
}

impl<'a> Tab<'a> {
    pub(crate) fn new(index: usize, tabs: Rc<RefCell<TabsElement>>, allocator: &'a Allocator, app: Rc<Mutex<App>>, form_id: Option<String>, base_path: Vec<u32>, exit_path: Vec<u32>) -> Self {
        Self {
            index,
            tabs,
            allocator,
            app,
            form_id,
            base_path,
            exit_path,
        }
    }
}

impl AppendChild for Tab<'_> {
    fn push(&self, element: Rc<RefCell<dyn Element>>) {
        let child_index = self.tabs.borrow().tabs[self.index].len() as u32;
        self.tabs.borrow_mut().tabs[self.index].push(element.clone());
        let mut base = self.base_path.clone();
        base.push(self.index as u32);
        push_at(element, &self.app, &self.form_id, &base, child_index, &self.exit_path);
    }

    fn allocator(&self) -> &Allocator {
        self.allocator
    }

    fn get_app(&self) -> Rc<Mutex<App>> {
        self.app.clone()
    }

    fn parent_form_id(&self) -> Option<String> {
        self.form_id.clone()
    }

    fn next_child_path(&self) -> Vec<u32> {
        let mut path = self.base_path.clone();
        path.push(self.index as u32);
        path.push(self.tabs.borrow().tabs[self.index].len() as u32);
        path
    }
}

/// The dialog body handle: writes stream into the dialog's content
/// container on the event root.
pub struct DialogBody<'a> {
    element: Rc<RefCell<DialogElement>>,
    allocator: &'a Allocator,
    app: Rc<Mutex<App>>,
    form_id: Option<String>,
    exit_path: Vec<u32>,
}

impl<'a> DialogBody<'a> {
    pub(crate) fn new(element: Rc<RefCell<DialogElement>>, allocator: &'a Allocator, app: Rc<Mutex<App>>, form_id: Option<String>, exit_path: Vec<u32>) -> Self {
        Self { element, allocator, app, form_id, exit_path }
    }
}

impl AppendChild for DialogBody<'_> {
    fn push(&self, element: Rc<RefCell<dyn Element>>) {
        let child_index = self.element.borrow().children.len() as u32;
        self.element.borrow_mut().children.push(element.clone());
        push_at(element, &self.app, &self.form_id, &[2, 0, 0], child_index, &self.exit_path);
    }

    fn allocator(&self) -> &Allocator {
        self.allocator
    }

    fn get_app(&self) -> Rc<Mutex<App>> {
        self.app.clone()
    }

    fn parent_form_id(&self) -> Option<String> {
        self.form_id.clone()
    }

    fn next_child_path(&self) -> Vec<u32> {
        let mut path = vec![2, 0, 0];
        path.push(self.element.borrow().children.len() as u32);
        path
    }
}

/// The status container state, mirroring the reference's block states and
/// their icons ("spinner" / ":material/check:" / ":material/error:").
#[derive(Clone, Copy, Debug)]
pub enum StatusState {
    Running,
    Complete,
    Error,
}

impl StatusState {
    fn wire(self) -> crate::proto::block::expandable::State {
        match self {
            Self::Running => crate::proto::block::expandable::State::Running,
            Self::Complete => crate::proto::block::expandable::State::Complete,
            Self::Error => crate::proto::block::expandable::State::Error,
        }
    }

    fn icon(self) -> &'static str {
        match self {
            Self::Running => "spinner",
            Self::Complete => ":material/check:",
            Self::Error => ":material/error:",
        }
    }
}

/// The st.status container: an expandable block whose label/icon/state can
/// be updated mid-run -- `status.update(...)` re-streams the same block
/// path with the new payload (the measured 1.66.1 shape).
pub(crate) struct StatusElement {
    label: String,
    expanded: Option<bool>,
    icon: String,
    state: crate::proto::block::expandable::State,
    pub(crate) children: Vec<Rc<RefCell<dyn Element>>>,
}

impl StatusElement {
    pub fn new(label: String, expanded: bool) -> Self {
        Self {
            label,
            expanded: Some(expanded),
            icon: StatusState::Running.icon().to_string(),
            state: StatusState::Running.wire(),
            children: Vec::new(),
        }
    }

    pub fn update(&mut self, label: Option<String>, state: Option<StatusState>, expanded: Option<bool>) {
        if let Some(label) = label {
            self.label = label;
        }
        if let Some(state) = state {
            self.state = state.wire();
            self.icon = state.icon().to_string();
        }
        // Measured: an update without `expanded` re-streams the block with
        // the field unset (None clears it); only passing it re-arms the value.
        self.expanded = expanded;
    }
}

impl Element for StatusElement {
    fn render(&self, context: &mut RenderContext) -> Result<(), StreamlitError> {
        self.render_block(context, self.label.clone(), self.icon.clone(), self.state, self.expanded)?;
        context.delta_path.push(0);
        for child in self.children.iter() {
            child.borrow().render(context)?;
        }
        context.delta_path.pop();
        if let Some(index) = context.delta_path.pop() {
            context.delta_path.push(index + 1);
        }
        Ok(())
    }
}

impl StatusElement {
    fn render_block(&self, context: &mut RenderContext, label: String, icon: String, state: crate::proto::block::expandable::State, expanded: Option<bool>) -> Result<(), StreamlitError> {
        let element_hash = hash(format!("status_{label}_{icon}_{expanded:?}_{}", state.as_str_name()).as_str());
        let mut msg = delta_base_with_path(context.delta_path.clone(), context.active_script_hash.clone(), element_hash);
        msg.r#type = Some(forward_msg::Type::Delta(Delta {
            fragment_id: String::new(),
            r#type: Some(delta::Type::AddBlock(Block {
                autoscroll: None,
                allow_empty: true,
                id: None,
                height_config: None,
                width_config: Some(ElementWidth::Stretch.into()),
                r#type: Some(crate::proto::block::Type::Expandable(Expandable {
                    label,
                    expanded,
                    icon,
                    state: state as i32,
                    ..Default::default()
                })),
            })),
        }));
        context.push(msg);
        Ok(())
    }
}

/// The status handle: children stream into the block; `update` re-streams
/// the block with the new label/state/expanded after the children.
pub struct Status<'a> {
    element: Rc<RefCell<StatusElement>>,
    allocator: &'a Allocator,
    app: Rc<Mutex<App>>,
    form_id: Option<String>,
    base_path: Vec<u32>,
    exit_path: Vec<u32>,
}

impl<'a> Status<'a> {
    pub(crate) fn new(element: Rc<RefCell<StatusElement>>, allocator: &'a Allocator, app: Rc<Mutex<App>>, form_id: Option<String>, base_path: Vec<u32>, exit_path: Vec<u32>) -> Self {
        Self {
            element,
            allocator,
            app,
            form_id,
            base_path,
            exit_path,
        }
    }

    /// Update the container mid-run, like `status.update(label=...,
    /// state=..., expanded=...)`: the same block path re-streams with the
    /// new payload (the state drives the icon like the reference).
    pub fn update(&self, label: Option<String>, state: Option<StatusState>, expanded: Option<bool>) {
        let mut app = self.app.lock();
        if app.session_state.run_control().is_some() {
            return;
        }
        self.element.borrow_mut().update(label, state, expanded);
        let Some(context) = app.render_context_mut() else { return };
        // The update re-streams at the block's own path; the container
        // cursor does not move.
        let saved = context.delta_path.clone();
        context.delta_path = self.base_path.clone();
        let updated = self.element.borrow();
        let _ = updated.render_block(context, updated.label.clone(), updated.icon.clone(), updated.state, updated.expanded);
        context.delta_path = saved;
    }
}

impl AppendChild for Status<'_> {
    fn push(&self, element: Rc<RefCell<dyn Element>>) {
        let child_index = self.element.borrow().children.len() as u32;
        self.element.borrow_mut().children.push(element.clone());
        push_at(element, &self.app, &self.form_id, &self.base_path, child_index, &self.exit_path);
    }

    fn allocator(&self) -> &Allocator {
        self.allocator
    }

    fn get_app(&self) -> Rc<Mutex<App>> {
        self.app.clone()
    }

    fn parent_form_id(&self) -> Option<String> {
        self.form_id.clone()
    }

    fn next_child_path(&self) -> Vec<u32> {
        let mut path = self.base_path.clone();
        path.push(self.element.borrow().children.len() as u32);
        path
    }
}

/// The st.empty handle: the placeholder consumed its slot at creation;
/// `write` streams any element at that same slot, replacing what it held
/// without advancing the container cursor.
pub struct EmptyHandle<'a> {
    allocator: &'a Allocator,
    app: Rc<Mutex<App>>,
    form_id: Option<String>,
    slot_path: Vec<u32>,
}

impl<'a> EmptyHandle<'a> {
    pub(crate) fn new(allocator: &'a Allocator, app: Rc<Mutex<App>>, form_id: Option<String>, slot_path: Vec<u32>) -> Self {
        Self { allocator, app, form_id, slot_path }
    }
}

impl AppendChild for EmptyHandle<'_> {
    fn push(&self, element: Rc<RefCell<dyn Element>>) {
        let mut app = self.app.lock();
        if app.session_state.run_control().is_some() {
            return;
        }
        // The replacement writes at the stored slot path; the container
        // cursor does not move (a later sibling still takes the next slot).
        if let Some(context) = app.render_context_mut() {
            let saved = context.delta_path.clone();
            context.delta_path = self.slot_path.clone();
            if let Err(error) = element.borrow().render(context) {
                log::error!("failed to render into the empty slot: {error}");
            }
            context.delta_path = saved;
        }
    }

    fn allocator(&self) -> &Allocator {
        self.allocator
    }

    fn get_app(&self) -> Rc<Mutex<App>> {
        self.app.clone()
    }

    fn parent_form_id(&self) -> Option<String> {
        self.form_id.clone()
    }

    fn next_child_path(&self) -> Vec<u32> {
        self.slot_path.clone()
    }
}

/// The bottom container is a fixed root ([3]) that takes no block: children
/// stream straight into it, interleaved with the main flow, like the
/// sidebar's [1].
pub struct Bottom<'a> {
    allocator: &'a Allocator,
    app: Rc<Mutex<App>>,
    form_id: Option<String>,
    exit_path: Vec<u32>,
    children: std::cell::Cell<u32>,
}

impl<'a> Bottom<'a> {
    pub(crate) fn new(allocator: &'a Allocator, app: Rc<Mutex<App>>, form_id: Option<String>, exit_path: Vec<u32>) -> Self {
        Self {
            allocator,
            app,
            form_id,
            exit_path,
            children: std::cell::Cell::new(0),
        }
    }
}

impl AppendChild for Bottom<'_> {
    fn push(&self, element: Rc<RefCell<dyn Element>>) {
        let child_index = self.children.get();
        self.children.set(child_index + 1);
        push_at(element, &self.app, &self.form_id, &[3], child_index, &self.exit_path);
    }

    fn allocator(&self) -> &Allocator {
        self.allocator
    }

    fn get_app(&self) -> Rc<Mutex<App>> {
        self.app.clone()
    }

    fn parent_form_id(&self) -> Option<String> {
        self.form_id.clone()
    }

    fn next_child_path(&self) -> Vec<u32> {
        vec![3, self.children.get()]
    }
}

/// The sidebar is a fixed root ([1]) that takes no block: children stream
/// straight into it, interleaved with the main flow.
pub struct Sidebar<'a> {
    allocator: &'a Allocator,
    app: Rc<Mutex<App>>,
    form_id: Option<String>,
    exit_path: Vec<u32>,
    children: std::cell::Cell<u32>,
}

impl<'a> Sidebar<'a> {
    pub(crate) fn new(allocator: &'a Allocator, app: Rc<Mutex<App>>, form_id: Option<String>, exit_path: Vec<u32>) -> Self {
        Self {
            allocator,
            app,
            form_id,
            exit_path,
            children: std::cell::Cell::new(0),
        }
    }
}

impl AppendChild for Sidebar<'_> {
    fn push(&self, element: Rc<RefCell<dyn Element>>) {
        let child_index = self.children.get();
        self.children.set(child_index + 1);
        push_at(element, &self.app, &self.form_id, &[1], child_index, &self.exit_path);
    }

    fn allocator(&self) -> &Allocator {
        self.allocator
    }

    fn get_app(&self) -> Rc<Mutex<App>> {
        self.app.clone()
    }

    fn parent_form_id(&self) -> Option<String> {
        self.form_id.clone()
    }

    fn next_child_path(&self) -> Vec<u32> {
        vec![1, self.children.get()]
    }
}
