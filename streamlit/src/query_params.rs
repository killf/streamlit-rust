//! st.query_params: the URL-synced parameter store on the measured 1.66.1
//! wire. The browser reports its URL state with every rerun
//! (ClientState.query_string); server-side writes stream one
//! `page_info_changed{query_string}` at the call point, merged with the
//! browser-reported state and serialized as alphabetically sorted `k=v`
//! pairs.
use crate::WidgetError;
use crate::elements::App;
use crate::proto::{ForwardMsg, PageInfo, forward_msg};
use parking_lot::Mutex;
use std::rc::Rc;

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
            b'%' if index + 2 < bytes.len() => {
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
}

impl QueryParamStore {
    /// Seed the run's state from the browser-reported query string,
    /// replacing the previous run's view.
    pub(crate) fn load(&mut self, query_string: &str) {
        self.entries.clear();
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
    }

    /// Replace a key's values, like the reference's `__setitem__`.
    pub(crate) fn set(&mut self, key: &str, values: Vec<String>) {
        match self.entries.iter_mut().find(|(existing, _)| existing == key) {
            Some((_, stored)) => *stored = values,
            None => self.entries.push((key.to_string(), values)),
        }
    }

    pub(crate) fn get(&self, key: &str) -> Option<&str> {
        self.entries.iter().find(|(existing, _)| existing == key).and_then(|(_, values)| values.first()).map(String::as_str)
    }

    pub(crate) fn get_all(&self, key: &str) -> &[String] {
        self.entries.iter().find(|(existing, _)| existing == key).map(|(_, values)| values.as_slice()).unwrap_or(&[])
    }

    pub(crate) fn remove(&mut self, key: &str) -> bool {
        let before = self.entries.len();
        self.entries.retain(|(existing, _)| existing != key);
        before != self.entries.len()
    }

    pub(crate) fn clear(&mut self) {
        self.entries.clear();
    }

    /// The current parameters as `(key, values)` pairs.
    pub(crate) fn pairs(&self) -> &[(String, Vec<String>)] {
        &self.entries
    }

    /// The reference's serialization: alphabetically sorted repeated `k=v`
    /// pairs joined by `&`.
    pub(crate) fn serialize(&self) -> String {
        let mut keys: Vec<&(String, Vec<String>)> = self.entries.iter().collect();
        keys.sort_by(|left, right| left.0.cmp(&right.0));
        keys.iter().flat_map(|(key, values)| values.iter().map(move |value| format!("{}={}", encode(key), encode(value)))).collect::<Vec<_>>().join("&")
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

    /// The first value of a parameter, like the reference's `__getitem__`
    /// without raising.
    pub fn get(&self, key: &str) -> Option<String> {
        self.state.query_params.lock().get(key).map(str::to_string)
    }

    /// Every value of a parameter, in URL order.
    pub fn get_all(&self, key: &str) -> Vec<String> {
        self.state.query_params.lock().get_all(key).to_vec()
    }

    /// Replace a parameter's values and stream the merged URL state, the
    /// way the reference streams `page_info_changed` at the write point.
    pub fn set(&self, key: impl Into<String>, value: impl Into<String>) -> Result<(), WidgetError> {
        self.set_all(key, [value])
    }

    pub fn set_all<I: IntoIterator<Item = S>, S: Into<String>>(&self, key: impl Into<String>, values: I) -> Result<(), WidgetError> {
        let key = key.into();
        let values: Vec<String> = values.into_iter().map(Into::into).collect();
        if key.is_empty() {
            return Err(WidgetError::InvalidValue("query parameter keys cannot be empty".into()));
        }
        self.mutate(|store| store.set(&key, values));
        Ok(())
    }

    /// Remove a parameter; a missing key is an error, like the reference.
    pub fn remove(&self, key: &str) -> Result<(), WidgetError> {
        if self.get(key).is_none() {
            return Err(WidgetError::InvalidValue(format!("query parameter '{key}' is not set")));
        }
        self.mutate(|store| {
            store.remove(key);
        });
        Ok(())
    }

    /// Drop every parameter and stream the emptied URL state.
    pub fn clear(&self) -> Result<(), WidgetError> {
        self.mutate(|store| store.clear());
        Ok(())
    }

    /// The current parameters as single-value pairs.
    pub fn to_vec(&self) -> Vec<(String, String)> {
        self.state.query_params.lock().pairs().iter().map(|(key, values)| (key.clone(), values.first().cloned().unwrap_or_default())).collect()
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
        if let Some(context) = app.render_context_mut()
            && context.sender.is_some()
        {
            let mut message = ForwardMsg {
                hash: "page_info_changed".to_string(),
                ..Default::default()
            };
            message.r#type = Some(forward_msg::Type::PageInfoChanged(PageInfo { query_string }));
            context.push(message);
        }
    }
}
