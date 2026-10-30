//! The `st.components.v2.component` surface against the measured 1.66.1
//! wire (see .codex/compatibility.md, Custom components): one registered
//! definition carries inline HTML/CSS/JS; each mount streams a
//! bidi_component element whose id is the instance's widget id
//! (`$$ID-<digest>-<key>`), with the JSON data payload serialized like the
//! reference's json.dumps defaults, the state carried as one json_value
//! widget (the default object before any component interaction) and the
//! trigger events carried as one internal json_trigger_value aggregator
//! (`$$STREAMLIT_INTERNAL_KEY_<id>__events`) — the frontend accumulates the
//! fired {"event", "value"} payloads there and the mount surfaces the
//! declared events on its result object.
use crate::elements::common::{Element, ElementHeight, ElementWidth, RenderContext};
use crate::error::StreamlitError;
use crate::proto::{Delta, bidi_component, delta, delta_base_with_path, element, forward_msg};
use crate::utils::hash::hash;
use serde_json::Value;

/// One registered component: the trusted inline content every mount
/// instantiates. `st.components.v2.component(name, html=, css=, js=,
/// isolate_styles=)` upstream.
#[derive(Clone)]
pub struct ComponentV2 {
    name: String,
    html: String,
    css: String,
    js: String,
    isolate_styles: bool,
}

impl ComponentV2 {
    pub fn new(name: impl Into<String>) -> Self {
        Self {
            name: name.into(),
            html: String::new(),
            css: String::new(),
            js: String::new(),
            isolate_styles: true,
        }
    }

    /// The component root's inline HTML (without html/head/body wrappers).
    pub fn html(mut self, body: impl Into<String>) -> Self {
        self.html = body.into();
        self
    }

    /// Inline CSS (without a style block).
    pub fn css(mut self, body: impl Into<String>) -> Self {
        self.css = body.into();
        self
    }

    /// Inline JavaScript (without a script block).
    pub fn js(mut self, body: impl Into<String>) -> Self {
        self.js = body.into();
        self
    }

    /// Whether the component's styles live in a shadow root (the default).
    pub fn isolate_styles(mut self, isolate: bool) -> Self {
        self.isolate_styles = isolate;
        self
    }

    pub fn name(&self) -> &str {
        &self.name
    }
}

/// One mount's parameters: `key`, the JSON `data` payload, the `default`
/// state object, the trigger events the app reads and the sizing (stretch
/// width and content height by default, like the reference).
pub struct ComponentMount<'a> {
    key: Option<&'a str>,
    data: Option<Value>,
    default: Value,
    events: Vec<String>,
    width: ElementWidth,
    height: ElementHeight,
}

impl Default for ComponentMount<'_> {
    fn default() -> Self {
        Self {
            key: None,
            data: None,
            default: Value::Null,
            events: Vec::new(),
            width: ElementWidth::Stretch,
            height: ElementHeight::Content,
        }
    }
}

impl<'a> ComponentMount<'a> {
    pub fn new() -> Self {
        Self::default()
    }

    pub fn key(mut self, key: &'a str) -> Self {
        self.key = Some(key);
        self
    }

    /// The JSON payload handed to the component's frontend.
    pub fn data(mut self, data: Value) -> Self {
        self.data = Some(data);
        self
    }

    /// Defaults for missing top-level state keys, including after frontend updates.
    /// Supplied values take precedence, including explicit JSON nulls.
    pub fn default_state(mut self, default: Value) -> Self {
        self.default = default;
        self
    }

    /// The trigger events the app reads from the result, like the reference's
    /// `on_<event>_change` callbacks declaring them: every declared event
    /// surfaces on the returned object (null until it fires), unfired events
    /// of the run included; the component's `setTriggerValue` payloads reach
    /// them through the internal events aggregator widget.
    pub fn events(mut self, events: impl IntoIterator<Item = impl Into<String>>) -> Self {
        self.events = events.into_iter().map(Into::into).collect();
        self
    }

    pub fn width(mut self, width: ElementWidth) -> Self {
        self.width = width;
        self
    }

    pub fn height(mut self, height: ElementHeight) -> Self {
        self.height = height;
        self
    }
}

pub(crate) struct BidiComponentElement {
    component: ComponentV2,
    id: String,
    data_json: Option<String>,
    form_id: String,
    width: ElementWidth,
    height: ElementHeight,
}

/// Mount one instance: register the state widget (its id lands on the
/// element) and the internal trigger aggregator under the frontend-derived
/// id, serialize the JSON payload with the reference's json.dumps defaults,
/// enqueue the bidi_component element, and return the ComponentResult
/// object — {**trigger values, **state}, state winning on collision like
/// the reference.
pub(crate) fn mount_component(host: &impl crate::api::AppendChild, component: &ComponentV2, mount: ComponentMount<'_>) -> Result<Value, crate::widgets::WidgetError> {
    let ComponentMount { key, data, default, events, width, height } = mount;
    let default = match default {
        Value::Null => Value::Object(Default::default()),
        other => other,
    };

    let (id, state, _set) = host.register_widget_parity(
        crate::widgets::WidgetSpec {
            disabled: false,
            query: None,
            kind: "bidi_component",
            key,
            identity: "",
            codec: crate::widgets::Codec::JsonValue { defaults: default.clone() },
            default,
            callback: None,
        },
        |value| Ok::<_, crate::widgets::WidgetError>(value.clone()),
    )?;
    // The reference registers the aggregator on every mount, its id derived
    // from the state widget's id (the frontend recomputes the same shape).
    let aggregator_id = format!("$$STREAMLIT_INTERNAL_KEY_{id}__events");
    let (_, fired, _aggregator_set) = host.register_widget_with_id_parity(
        crate::widgets::WidgetSpec {
            disabled: false,
            query: None,
            kind: "bidi_component_trigger",
            key: None,
            identity: "",
            default: Value::Null,
            codec: crate::widgets::Codec::JsonTrigger,
            callback: None,
        },
        &aggregator_id,
        |value| Ok::<_, crate::widgets::WidgetError>(value.clone()),
    )?;
    let data_json = data.map(|data| crate::pywire::py_dumps(&data));
    host.push(std::rc::Rc::new(std::cell::RefCell::new(BidiComponentElement::new(
        component.clone(),
        id,
        data_json,
        host.parent_form_id().unwrap_or_default(),
        width,
        height,
    ))));
    // ComponentResult: every declared event surfaces (null until it fires),
    // the last payload per event wins, and state keys overwrite collisions.
    if events.is_empty() {
        return Ok(state);
    }
    let mut result = serde_json::Map::new();
    if let Value::Array(payloads) = &fired {
        for payload in payloads {
            if let (Some(event), Some(value)) = (payload.get("event").and_then(Value::as_str), payload.get("value")) {
                result.insert(event.to_owned(), value.clone());
            }
        }
    }
    for event in &events {
        result.entry(event.clone()).or_insert(Value::Null);
    }
    if let Value::Object(object) = state {
        for (name, value) in object {
            result.insert(name, value);
        }
    }
    Ok(Value::Object(result))
}

impl BidiComponentElement {
    pub(crate) fn new(component: ComponentV2, id: String, data_json: Option<String>, form_id: String, width: ElementWidth, height: ElementHeight) -> Self {
        Self {
            component,
            id,
            data_json,
            form_id,
            width,
            height,
        }
    }
}

impl Element for BidiComponentElement {
    fn render(&self, context: &mut RenderContext) -> Result<(), StreamlitError> {
        let element_hash = hash(format!("bidi_component_{}_{}", self.component.name, self.id).as_str());
        let mut msg = delta_base_with_path(context.delta_path.clone(), context.active_script_hash.clone(), element_hash);
        msg.r#type = Some(forward_msg::Type::Delta(Delta {
            fragment_id: String::new(),
            r#type: Some(delta::Type::NewElement(element(self.component.clone(), self.id.clone(), self.data_json.clone(), self.form_id.clone(), &self.width, &self.height))),
        }));
        context.push(msg);
        if let Some(index) = context.delta_path.last_mut() {
            *index += 1;
        }
        Ok(())
    }
}

fn element(component: ComponentV2, id: String, data_json: Option<String>, form_id: String, width: &ElementWidth, height: &ElementHeight) -> crate::proto::Element {
    crate::proto::Element {
        width_config: Some(width.clone().into()),
        height_config: Some(height.clone().into()),
        r#type: Some(element::Type::BidiComponent(crate::proto::BidiComponent {
            id,
            component_name: component.name().to_owned(),
            // The reference assigns every content field (empty strings
            // included), so the optional source paths ride the wire as "".
            js_content: Some(component.js),
            js_source_path: Some(String::new()),
            form_id,
            html_content: Some(component.html),
            css_content: Some(component.css),
            css_source_path: Some(String::new()),
            isolate_styles: component.isolate_styles,
            data: data_json.map(bidi_component::Data::Json),
        })),
        ..Default::default()
    }
}
