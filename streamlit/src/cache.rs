//! st.cache_data / st.cache_resource on the measured 1.66.1 wire: results
//! are memoized per session and cache kind keyed by name and serialized arguments; an outermost miss
//! streams an empty-element transient (the cleared-spinner shape) at the
//! call site and records every element the function emitted, and a hit
//! replays those elements at their original paths with no transient
//! (see .codex/compatibility.md, Caching, frozen 2026-10-26).
use serde::Serialize;
use serde::de::DeserializeOwned;
use std::any::Any;
use std::cell::RefCell;
use std::collections::HashMap;
use std::marker::PhantomData;
use std::rc::Rc;

use crate::Streamlit;

pub(crate) struct CacheRecord {
    pub value: serde_json::Value,
    pub resource: Option<std::sync::Arc<dyn Any + Send + Sync>>,
    pub recorded: Vec<crate::proto::ForwardMsg>,
    /// The call site's path when the recording was made, so a hit can
    /// re-anchor the recorded paths to its own cursor.
    pub entry_path: Vec<u32>,
}

#[derive(Default)]
pub(crate) struct CacheStore {
    // 数据结果和资源引用分别存放，允许两类缓存使用相同名称和参数。
    data: HashMap<String, CacheRecord>,

    resources: HashMap<String, CacheRecord>,
}

impl CacheStore {
    pub(crate) fn clear(&mut self) {
        self.data.clear();
        self.resources.clear();
    }
}

/// `st.cache_data(name).call(arg, f)`: memoizes `f(arg)`'s value and side
/// effects per session. Hits replay the recorded elements and skip the
/// transient; misses compute, stream and record. The plain call is
/// `let v = st.cache_data("double").call(21, |n: i64| n * 2);`.
pub fn cache_data<T: Serialize, R: Clone + Serialize + DeserializeOwned>(st: &Streamlit, name: impl Into<String>, arg: T, f: impl FnOnce(T) -> R) -> R {
    let state = st.session_state();
    let key = match serde_json::to_string(&arg) {
        Ok(text) => format!("{}::{}", name.into(), text),
        Err(_) => return f(arg),
    };
    let caches = state.caches.lock();
    if let Some(record) = caches.data.get(&key) {
        let value = record.value.clone();
        let recorded = record.recorded.clone();
        let entry_path = record.entry_path.clone();
        drop(caches);
        replay(st, &recorded, &entry_path);
        return serde_json::from_value(value).unwrap_or_else(|_| f(arg));
    }
    drop(caches);
    let (value, recorded, entry_path) = execute_with_recording(st, || f(arg));
    if let Ok(serialized) = serde_json::to_value(&value) {
        state.caches.lock().data.insert(
            key,
            CacheRecord {
                value: serialized,
                resource: None,
                recorded,
                entry_path,
            },
        );
    }
    value
}

/// `st.cache_resource(name).call(arg, f)`: the same memoization, but the
/// stored value is shared (`Arc`) rather than cloned on every hit, matching
/// the reference's resource semantics for models, clients and connections.
pub fn cache_resource<T: Serialize, R: Send + Sync + 'static>(st: &Streamlit, name: impl Into<String>, arg: T, f: impl FnOnce(T) -> R) -> std::sync::Arc<R> {
    let state = st.session_state();
    let key = match serde_json::to_string(&arg) {
        Ok(text) => format!("{}::{}", name.into(), text),
        Err(_) => return std::sync::Arc::new(f(arg)),
    };
    let caches = state.caches.lock();
    if let Some(record) = caches.resources.get(&key)
        && let Some(shared) = record.resource.clone()
        && let Ok(typed) = shared.downcast::<R>()
    {
        let recorded = record.recorded.clone();
        let entry_path = record.entry_path.clone();
        drop(caches);
        replay(st, &recorded, &entry_path);
        return typed;
    }
    drop(caches);
    let (value, recorded, entry_path) = execute_with_recording(st, || f(arg));
    let shared = std::sync::Arc::new(value);
    st.session_state().caches.lock().resources.insert(
        key,
        CacheRecord {
            value: serde_json::Value::Null,
            resource: Some(shared.clone()),
            recorded,
            entry_path,
        },
    );
    shared
}

/// A hit replays the recorded elements at the call site like the reference
/// does: recorded paths are re-anchored to the hit run's cursor (the call
/// site may sit on a different index when earlier layout changed between
/// runs), and every element or block slot at the call site's level advances
/// that cursor exactly like a live render, so following writes land after
/// the replayed elements. Blocks the function opened get their own anchor
/// so nested children follow their block.
fn replay(st: &Streamlit, recorded: &[crate::proto::ForwardMsg], entry_path: &[u32]) {
    use crate::proto::delta::Type as DeltaType;
    use crate::proto::forward_msg::Type as MsgType;

    let mut app = st.app.lock();
    if app.session_state.run_control().is_some() {
        return;
    }
    if let Some(context) = app.render_context_mut()
        && context.sender.is_some()
    {
        let depth = entry_path.len();
        let hit_path = context.delta_path.clone();
        // Without a same-depth call site there is nothing to re-anchor
        // against; replay verbatim without touching the cursor.
        if depth == 0 || hit_path.len() != depth || hit_path[..depth - 1] != entry_path[..depth - 1] {
            for message in recorded {
                context.push(message.clone());
            }
            return;
        }
        let entry_last = entry_path[depth - 1];
        let hit_last = hit_path[depth - 1];
        let mut anchors: Vec<(Vec<u32>, Vec<u32>)> = Vec::new();
        for message in recorded {
            let (takes_slot, is_block, path) = match message.r#type.as_ref() {
                Some(MsgType::Delta(delta)) => match delta.r#type.as_ref() {
                    Some(DeltaType::NewElement(_)) => (true, false, delta_path_of(message)),
                    Some(DeltaType::AddBlock(_)) => (true, true, delta_path_of(message)),
                    _ => (false, false, delta_path_of(message)),
                },
                _ => (false, false, None),
            };
            let Some(recorded_path) = path else {
                context.push(message.clone());
                continue;
            };
            // Nested blocks re-anchor through the anchor their parent block
            // registered; everything else sits at the call site's own level.
            let anchor = anchors.iter().filter(|(recorded, _)| recorded.len() >= depth && recorded_path.starts_with(recorded.as_slice())).max_by_key(|(recorded, _)| recorded.len());
            let mut replayed = message.clone();
            let mut advances = false;
            if let Some((recorded_base, new_base)) = anchor {
                if let Some(metadata) = replayed.metadata.as_mut() {
                    metadata.delta_path = [new_base.as_slice(), &recorded_path[recorded_base.len()..]].concat();
                }
            } else if recorded_path.len() >= depth && recorded_path[..depth - 1] == entry_path[..depth - 1] {
                let offset = (recorded_path[depth - 1] as i64 - entry_last as i64).max(0) as u32;
                if let Some(metadata) = replayed.metadata.as_mut() {
                    metadata.delta_path = [&hit_path[..depth - 1], &[hit_last + offset], &recorded_path[depth..]].concat();
                }
                advances = takes_slot && recorded_path.len() == depth;
            }
            if is_block && let Some(metadata) = replayed.metadata.as_ref() {
                anchors.push((recorded_path, metadata.delta_path.clone()));
            }
            context.push(replayed);
            if advances && let Some(last) = context.delta_path.last_mut() {
                *last += 1;
            }
        }
    }
}

fn delta_path_of(message: &crate::proto::ForwardMsg) -> Option<Vec<u32>> {
    message.metadata.as_ref().map(|metadata| metadata.delta_path.clone())
}

/// Record one miss independently and merge its output back into an enclosing
/// miss. Only the outermost call emits the measured cleared-spinner transient.
fn execute_with_recording<R>(st: &Streamlit, f: impl FnOnce() -> R) -> (R, Vec<crate::proto::ForwardMsg>, Vec<u32>) {
    use crate::elements::common::Element;

    // 1. 独立录制本次调用，暂存父层已经收集的输出。
    let recording = {
        let mut app = st.app.lock();
        let suppressed = app.session_state.run_control().is_some();
        match app.render_context_mut() {
            Some(context) if !suppressed && context.sender.is_some() => Some((context.delta_path.clone(), context.recording.replace(Vec::new()))),
            _ => None,
        }
    };
    let value = f();
    let Some((entry_path, mut parent_recording)) = recording else {
        return (value, Vec::new(), Vec::new());
    };

    // 2. 子层持久输出并回父层，外层后续写入继续进入原来的录制。
    let mut app = st.app.lock();
    let suppressed = app.session_state.run_control().is_some();
    let Some(context) = app.render_context_mut() else {
        return (value, Vec::new(), Vec::new());
    };
    let recorded = context.recording.take().unwrap_or_default();
    let outermost = parent_recording.is_none();
    if let Some(parent) = &mut parent_recording {
        parent.extend(recorded.iter().cloned());
    }
    context.recording = parent_recording;

    if suppressed || context.sender.is_none() {
        return (value, recorded, Vec::new());
    }

    // 3. 仅最外层未命中发送临时 spinner 清除消息，不把它缓存到父层。
    if outermost {
        let mut snapshot = crate::elements::common::RenderContext {
            stream: Vec::new(),
            delta_path: entry_path.clone(),
            active_script_hash: context.active_script_hash.clone(),
            session_id: context.session_id.clone(),
            sender: None,
            recording: None,
        };
        let cleared = Rc::new(RefCell::new(crate::elements::media::SpinnerTransientElement::cleared()));
        if let Err(error) = cleared.borrow().render(&mut snapshot) {
            log::error!("cache transient failed to render: {error}");
        }
        for message in snapshot.stream {
            context.push(message);
        }
    }
    (value, recorded, entry_path)
}

impl Streamlit {
    /// Memoize a pure computation per session, like `@st.cache_data`:
    /// `st.cache_data(|n| ...)`. The builder form below keeps argument and
    /// closure together: `st.cache_data("double").call(21, |n: i64| n * 2)`.
    pub fn cache_data<T: Serialize, R: Clone + Serialize + DeserializeOwned>(&self, name: impl Into<String>) -> CachedData<'_, T, R> {
        CachedData {
            st: self,
            name: name.into(),
            _types: PhantomData,
        }
    }

    /// Memoize a shared resource per session, like `@st.cache_resource`.
    pub fn cache_resource<T: Serialize, R: Send + Sync + 'static>(&self, name: impl Into<String>) -> CachedResource<'_, T, R> {
        CachedResource {
            st: self,
            name: name.into(),
            _types: PhantomData,
        }
    }

    /// Drop every cached entry of this session, like `st.cache_data.clear()`.
    pub fn cache_clear(&self) {
        self.session_state().caches.lock().clear();
    }
}

pub struct CachedData<'a, T, R> {
    st: &'a Streamlit,
    name: String,
    _types: PhantomData<fn(T) -> R>,
}

impl<T: Serialize, R: Clone + Serialize + DeserializeOwned> CachedData<'_, T, R> {
    pub fn call(self, arg: T, f: impl FnOnce(T) -> R) -> R {
        cache_data(self.st, self.name, arg, f)
    }
}

pub struct CachedResource<'a, T, R> {
    st: &'a Streamlit,
    name: String,
    _types: PhantomData<fn(T) -> R>,
}

impl<T: Serialize, R: Send + Sync + 'static> CachedResource<'_, T, R> {
    pub fn call(self, arg: T, f: impl FnOnce(T) -> R) -> std::sync::Arc<R> {
        cache_resource(self.st, self.name, arg, f)
    }
}
