//! st.query_params: the URL-synced parameter store on the measured 1.66.1
//! wire. The browser reports its URL state with every rerun
//! (ClientState.query_string); server-side writes stream one
//! `page_info_changed{query_string}` at the call point, merged with the
//! browser-reported state and serialized as repeated `k=v` pairs in key
//! insertion order, preserving each key's value order.
use crate::WidgetError;
use crate::elements::App;
use crate::proto::{ForwardMsg, PageInfo, forward_msg};
use parking_lot::Mutex;
use std::rc::Rc;

pub(crate) fn is_embed_key(key: &str) -> bool {
    key.eq_ignore_ascii_case("embed") || key.eq_ignore_ascii_case("embed_options")
}

/// Percent-encodes one query component the way the reference's urlencode
/// does: unreserved characters pass through, spaces become `+`.
fn encode(value: &str) -> String {
    let mut out = String::with_capacity(value.len());
    for byte in value.as_bytes() {
        match byte {
            b'A'..=b'Z' | b'a'..=b'z' | b'0'..=b'9' | b'-' | b'_' | b'.' | b'~' => out.push(*byte as char),
            b' ' => out.push('+'),
            other => out.push_str(&format!("%{other:02X}")),
        }
    }
    out
}

fn decode(value: &str) -> String {
    let bytes = value.as_bytes();
    let mut out = Vec::with_capacity(bytes.len());
    let mut index = 0;
    while index < bytes.len() {
        match bytes[index] {
            b'+' => {
                out.push(b' ');
                index += 1;
            }

            // 整数解析允许前导 +，但 URL 转义必须严格包含两位十六进制字符。
            b'%' if index + 2 < bytes.len() && bytes[index + 1].is_ascii_hexdigit() && bytes[index + 2].is_ascii_hexdigit() => {
                let hex = std::str::from_utf8(&bytes[index + 1..index + 3]).unwrap_or("");
                match u8::from_str_radix(hex, 16) {
                    Ok(byte) => {
                        out.push(byte);
                        index += 3;
                    }
                    Err(_) => {
                        out.push(bytes[index]);
                        index += 1;
                    }
                }
            }

            other => {
                out.push(other);
                index += 1;
            }
        }
    }
    String::from_utf8_lossy(&out).into_owned()
}

/// The ordered parameter multimap of one run, seeded from the browser's URL.
#[derive(Clone, Default)]
pub(crate) struct QueryParamStore {
    entries: Vec<(String, Vec<String>)>,

    /// URL snapshot before application code mutates this run's parameters.
    initial: Vec<(String, Vec<String>)>,

    /// The current browser request is restoring a history entry.
    pub(crate) history_navigation: bool,

    /// Internal widget cleanup is sent once at the registration/run boundary.
    pending_update: bool,

    /// Last browser/announced URL; silent default collapse does not replace it.
    rerun_query_string: String,
}

impl QueryParamStore {
    /// Seed the run's state from the browser-reported query string,
    /// replacing the previous run's view.
    pub(crate) fn load(&mut self, query_string: &str) {
        self.entries.clear();
        self.rerun_query_string = query_string.to_owned();
        self.pending_update = false;
        self.history_navigation = false;
        for pair in query_string.split('&').filter(|pair| !pair.is_empty()) {
            let (key, value) = match pair.split_once('=') {
                Some((key, value)) => (decode(key), decode(value)),
                None => (decode(pair), String::new()),
            };
            match self.entries.iter_mut().find(|(existing, _)| *existing == key) {
                Some((_, values)) => values.push(value),
                None => self.entries.push((key, vec![value])),
            }
        }
        self.initial = self.entries.clone();
    }

    pub(crate) fn begin_internal_run(&mut self) {
        let query_string = self.rerun_query_string.clone();
        self.load(&query_string);
    }

    pub(crate) fn initial_value(&self, key: &str) -> Option<&str> {
        self.initial.iter().find(|(existing, _)| existing == key).and_then(|(_, values)| values.last()).map(String::as_str)
    }

    /// Replace a key's values, like the reference's `__setitem__`.
    pub(crate) fn set(&mut self, key: &str, values: Vec<String>) {
        match self.entries.iter_mut().find(|(existing, _)| existing == key) {
            Some((_, stored)) => *stored = values,
            None => self.entries.push((key.to_string(), values)),
        }
    }

    pub(crate) fn get(&self, key: &str) -> Option<&str> {
        self.entries.iter().find(|(existing, _)| existing == key && !is_embed_key(key)).map(|(_, values)| values.last().map(String::as_str).unwrap_or(""))
    }

    pub(crate) fn get_all(&self, key: &str) -> &[String] {
        self.entries.iter().find(|(existing, _)| existing == key && !is_embed_key(key)).map(|(_, values)| values.as_slice()).unwrap_or(&[])
    }

    pub(crate) fn remove(&mut self, key: &str) -> bool {
        let before = self.entries.len();
        self.entries.retain(|(existing, _)| existing != key);
        before != self.entries.len()
    }

    pub(crate) fn clear(&mut self) {
        self.entries.clear();
        self.initial.clear();
        self.rerun_query_string.clear();
        self.history_navigation = false;
        self.pending_update = false;
    }

    pub(crate) fn remove_binding(&mut self, key: &str) {
        self.pending_update |= self.remove(key);
    }

    pub(crate) fn set_binding_value(&mut self, key: &str, value: String) {
        if self.get_all(key) != [value.as_str()] {
            self.set(key, vec![value]);
            self.pending_update = true;
        }
    }

    /// The current parameters as `(key, values)` pairs.
    pub(crate) fn pairs(&self) -> &[(String, Vec<String>)] {
        &self.entries
    }

    /// The reference's serialization preserves key insertion order and
    /// repeated values. Empty lists remain stored but emit no URL pair.
    pub(crate) fn serialize(&self) -> String {
        self.entries.iter().flat_map(|(key, values)| values.iter().map(move |value| format!("{}={}", encode(key), encode(value)))).collect::<Vec<_>>().join("&")
    }
}

pub(crate) fn flush_query_update(app: &mut App) {
    let query_string = {
        let mut query = app.session_state.query_params.lock();
        std::mem::take(&mut query.pending_update).then(|| query.serialize())
    };
    if let Some(query_string) = query_string {
        send_query_update(app, query_string);
    }
}

fn send_query_update(app: &mut App, query_string: String) {
    app.session_state.query_params.lock().rerun_query_string = query_string.clone();
    if let Some(context) = app.render_context_mut()
        && context.sender.is_some()
    {
        context.push(ForwardMsg {
            hash: "page_info_changed".into(),
            r#type: Some(forward_msg::Type::PageInfoChanged(PageInfo { query_string })),
            ..Default::default()
        });
    }
}

/// The application-facing query-parameter handle.
pub struct QueryParams<'a> {
    app: Rc<Mutex<App>>,
    state: crate::SessionState,
    #[allow(dead_code)]
    allocator: &'a crate::memory::Allocator,
}

impl<'a> QueryParams<'a> {
    pub(crate) fn new(app: Rc<Mutex<App>>, state: crate::SessionState, allocator: &'a crate::memory::Allocator) -> Self {
        Self { app, state, allocator }
    }

    /// The last value of a parameter, like the reference's `__getitem__`
    /// without raising. An existing empty list returns an empty string.
    /// Reserved embedding parameters are hidden from application reads.
    pub fn get(&self, key: &str) -> Option<String> {
        self.state.query_params.lock().get(key).map(str::to_string)
    }

    /// Every value of an ordinary parameter, in URL order. Reserved
    /// embedding parameters return an empty list.
    pub fn get_all(&self, key: &str) -> Vec<String> {
        self.state.query_params.lock().get_all(key).to_vec()
    }

    /// Replace a parameter's values and stream the merged URL state, the
    /// way the reference streams `page_info_changed` at the write point.
    /// Registered query-bound widget keys cannot be changed directly.
    pub fn set(&self, key: impl Into<String>, value: impl Into<String>) -> Result<(), WidgetError> {
        self.set_all(key, [value])
    }

    pub fn set_all<I: IntoIterator<Item = S>, S: Into<String>>(&self, key: impl Into<String>, values: I) -> Result<(), WidgetError> {
        let key = key.into();
        if self.state.widgets.lock().query_bound(&key) {
            return Err(WidgetError::InvalidValue(format!("cannot directly set query parameter '{key}' bound to a widget")));
        }
        if is_embed_key(&key) {
            return Err(WidgetError::InvalidValue("Query param embed and embed_options (case-insensitive) cannot be set programmatically.".into()));
        }
        let values: Vec<String> = values.into_iter().map(Into::into).collect();
        self.mutate(|store| store.set(&key, values));
        Ok(())
    }

    /// Remove an unbound parameter; a missing or bound key is an error.
    pub fn remove(&self, key: &str) -> Result<(), WidgetError> {
        if self.state.widgets.lock().query_bound(key) {
            return Err(WidgetError::InvalidValue(format!("cannot directly delete query parameter '{key}' bound to a widget")));
        }
        if self.get(key).is_none() {
            return Err(WidgetError::InvalidValue(format!("query parameter '{key}' is not set")));
        }
        self.mutate(|store| {
            store.remove(key);
        });
        Ok(())
    }

    /// Drop ordinary parameters, preserve reserved embedding parameters,
    /// and stream the remaining URL state. Existing bound parameters must
    /// be changed through their widgets instead.
    pub fn clear(&self) -> Result<(), WidgetError> {
        let bound = self.state.widgets.lock().bound_query_keys();
        if bound.iter().any(|key| self.state.query_params.lock().get(key).is_some()) {
            return Err(WidgetError::InvalidValue("cannot clear query parameters bound to widgets".into()));
        }
        self.mutate(|store| store.entries.retain(|(key, _)| is_embed_key(key)));
        Ok(())
    }

    /// The ordinary parameters in key insertion order, taking the last
    /// value per key (or an empty string for an existing empty list).
    pub fn to_vec(&self) -> Vec<(String, String)> {
        self.state
            .query_params
            .lock()
            .pairs()
            .iter()
            .filter(|(key, _)| !is_embed_key(key))
            .map(|(key, values)| (key.clone(), values.last().cloned().unwrap_or_default()))
            .collect()
    }

    fn mutate(&self, change: impl FnOnce(&mut QueryParamStore)) {
        let mut app = self.app.lock();
        if app.session_state.run_control().is_some() {
            return;
        }
        let query_string = {
            let mut store = self.state.query_params.lock();
            change(&mut store);
            store.serialize()
        };
        send_query_update(&mut app, query_string);
    }
}
