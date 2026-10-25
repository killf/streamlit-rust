//! Native, server-owned state for one browser session.
use crate::Streamlit;
use parking_lot::Mutex;
use serde::{Serialize, de::DeserializeOwned};
use serde_json::Value;
use std::collections::HashMap;
use std::sync::Arc;
use std::sync::atomic::{AtomicU8, Ordering};
use std::time::{Duration, Instant};

/// Run-control signal raised by [`Streamlit::rerun`] and [`Streamlit::stop`].
///
/// Mirrors the measured Python 1.66.1 wire: after either call, later element
/// pushes and session-state writes of the same run have no effect, and the
/// run's finish status follows the signal — `rerun` finishes early for the
/// next run, `stop` still finishes successfully.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum RunControl {
    Rerun,
    Stop,
}

impl RunControl {
    const RERUN: u8 = 1;
    const STOP: u8 = 2;
}

/// JSON-serializable application values shared across reruns of one session.
/// Cloning this handle shares that session's values, not another user's state.
/// Widget values with explicit keys share this map; button triggers reset each run.
#[derive(Clone, Default)]
pub struct SessionState {
    pub(crate) values: Arc<Mutex<HashMap<String, Value>>>,
    pub(crate) widgets: Arc<Mutex<crate::widgets::WidgetRegistry>>,
    pub(crate) uploads: Arc<Mutex<crate::upload::UploadStore>>,
    pub(crate) run_control: Arc<AtomicU8>,
}

impl SessionState {
    /// Read a typed value. Missing keys return `Ok(None)`; type mismatches return
    /// a serde error and leave the stored value unchanged.
    pub fn get<T: DeserializeOwned>(&self, key: &str) -> serde_json::Result<Option<T>> {
        let value = self.values.lock().get(key).cloned();
        value.map(serde_json::from_value).transpose()
    }

    /// Store a JSON-serializable value, replacing the previous value only when
    /// serialization succeeds. Explicit widget keys share these values; writes
    /// after that widget is instantiated in a run are rejected.
    pub fn set<T: Serialize>(&self, key: impl Into<String>, value: T) -> serde_json::Result<()> {
        // Code after st.rerun()/st.stop() never executes upstream, so its
        // writes must not land here either.
        if self.run_control().is_some() {
            return Ok(());
        }
        let value = serde_json::to_value(value)?;
        let key = key.into();
        let mut registry = self.widgets.lock();
        registry.check_write(&key)?;
        registry.mark_write(&key);
        self.values.lock().insert(key, value);
        Ok(())
    }

    /// Delete an application value and return its previous JSON representation.
    /// Removing a widget key does not reset a still-rendered widget: its current
    /// value recreates the key when that widget is instantiated again.
    pub fn remove(&self, key: &str) -> Option<Value> {
        if self.run_control().is_some() {
            return None;
        }
        self.values.lock().remove(key)
    }

    /// The run-control signal of the current run, if `st.rerun()`/`st.stop()` was called.
    pub fn run_control(&self) -> Option<RunControl> {
        match self.run_control.load(Ordering::Relaxed) {
            RunControl::RERUN => Some(RunControl::Rerun),
            RunControl::STOP => Some(RunControl::Stop),
            _ => None,
        }
    }

    pub(crate) fn set_run_control(&self, control: RunControl) {
        let raw = match control {
            RunControl::Rerun => RunControl::RERUN,
            RunControl::Stop => RunControl::STOP,
        };
        self.run_control.store(raw, Ordering::Relaxed);
    }

    pub(crate) fn reset_run_control(&self) {
        self.run_control.store(0, Ordering::Relaxed);
    }
}

impl Streamlit {
    /// Application state for the current browser session, preserved across reruns.
    pub fn session_state(&self) -> SessionState {
        self.app.lock().session_state.clone()
    }

    /// Rerun the script immediately, mirroring `st.rerun()`.
    ///
    /// The current run aborts at this point — the measured 1.66.1 wire finishes
    /// it with `FINISHED_EARLY_FOR_RERUN` and the server starts the next run
    /// without any browser request. Elements and session-state writes after
    /// this call have no effect in the current run. Guard the call so it fires
    /// exactly once (for example with a session-state flag): an unguarded
    /// `rerun` reruns forever, exactly as upstream does.
    pub fn rerun(&self) {
        self.session_state().set_run_control(RunControl::Rerun);
    }

    /// Stop the current run without an error, mirroring `st.stop()`.
    ///
    /// Elements emitted before this call stay on the page; later elements never
    /// emit, and the run still finishes `FINISHED_SUCCESSFULLY` on the wire.
    pub fn stop(&self) {
        self.session_state().set_run_control(RunControl::Stop);
    }

    pub(crate) fn with_session_state(state: SessionState) -> Self {
        let st = Self::new();
        st.app.lock().session_state = state;
        st
    }
}

struct StoredSession {
    state: SessionState,
    owner: uuid::Uuid,
    run: Arc<tokio::sync::Mutex<()>>,
    // None means the session currently has a WebSocket owner.
    disconnected_at: Option<Instant>,
}

pub(crate) struct SessionStore {
    sessions: Mutex<HashMap<String, StoredSession>>,
    disconnected_ttl: Duration,
}

impl SessionStore {
    /// Lookup an existing retained session without creating or transferring it.
    /// Upload HTTP requests must not implicitly create a client-chosen session.
    pub(crate) fn state_for_upload(&self, id: &str) -> Option<SessionState> {
        let mut sessions = self.sessions.lock();
        let now = Instant::now();
        sessions.retain(|_, session| session.disconnected_at.is_none_or(|at| now.duration_since(at) < self.disconnected_ttl));
        sessions.get(id).map(|session| session.state.clone())
    }
    #[cfg(test)]
    pub(crate) fn owner_for_test(&self, id: &str) -> Option<uuid::Uuid> {
        self.sessions.lock().get(id).map(|session| session.owner)
    }

    pub(crate) fn new(disconnected_ttl: Duration) -> Self {
        Self {
            sessions: Mutex::new(HashMap::new()),
            disconnected_ttl,
        }
    }

    pub(crate) async fn connect(self: &Arc<Self>, requested_id: Option<&str>) -> SessionLease {
        let previous_run = {
            let mut sessions = self.sessions.lock();
            let now = Instant::now();
            sessions.retain(|_, session| session.disconnected_at.is_none_or(|at| now.duration_since(at) < self.disconnected_ttl));
            requested_id.and_then(|id| sessions.get(id)).map(|session| session.run.clone())
        };
        // A replacement may upgrade its HTTP connection immediately, but cannot
        // acquire ownership until the previous run and all its sends finish.
        // Only this session's run mutex is awaited, never the registry mutex.
        let _boundary = match previous_run {
            Some(run) => Some(run.lock_owned().await),
            None => None,
        };
        self.connect_at(requested_id, Instant::now())
    }

    fn connect_at(self: &Arc<Self>, requested_id: Option<&str>, now: Instant) -> SessionLease {
        let mut sessions = self.sessions.lock();
        // Lazy expiry at each connection; connected sessions never expire.
        sessions.retain(|_, session| session.disconnected_at.is_none_or(|at| now.duration_since(at) < self.disconnected_ttl));
        if let Some(id) = requested_id
            && let Some(session) = sessions.get_mut(id)
        {
            session.owner = uuid::Uuid::new_v4();
            session.disconnected_at = None;
            return SessionLease {
                id: id.to_owned(),
                state: session.state.clone(),
                owner: session.owner,
                run: session.run.clone(),
                store: self.clone(),
            };
        }
        // Unknown/expired IDs never resurrect data or become a client-chosen ID.
        let id = uuid::Uuid::new_v4().to_string();
        let state = SessionState::default();
        let owner = uuid::Uuid::new_v4();
        let run = Arc::new(tokio::sync::Mutex::new(()));
        sessions.insert(
            id.clone(),
            StoredSession {
                state: state.clone(),
                owner,
                run: run.clone(),
                disconnected_at: None,
            },
        );
        SessionLease { id, state, owner, run, store: self.clone() }
    }
}

/// Versioned WebSocket ownership. Dropping the current lease starts retention;
/// a superseded connection's exit cannot disconnect its replacement.
pub(crate) struct SessionLease {
    pub(crate) id: String,
    pub(crate) state: SessionState,
    pub(crate) run: Arc<tokio::sync::Mutex<()>>,
    owner: uuid::Uuid,
    store: Arc<SessionStore>,
}

impl SessionLease {
    pub(crate) fn is_current(&self) -> bool {
        self.store.sessions.lock().get(&self.id).is_some_and(|session| session.owner == self.owner)
    }
}

impl Drop for SessionLease {
    fn drop(&mut self) {
        if let Some(session) = self.store.sessions.lock().get_mut(&self.id)
            && session.owner == self.owner
        {
            session.disconnected_at = Some(Instant::now());
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn typed_values_removal_and_independent_maps() {
        let state = SessionState::default();
        assert_eq!(state.get::<u64>("count").unwrap(), None);
        state.set("count", 3_u64).unwrap();
        assert_eq!(state.clone().get::<u64>("count").unwrap(), Some(3));
        assert!(state.get::<Vec<u8>>("count").is_err());
        assert_eq!(state.get::<u64>("count").unwrap(), Some(3));
        assert_eq!(SessionState::default().get::<u64>("count").unwrap(), None);
        assert_eq!(state.remove("count"), Some(Value::from(3)));
        assert_eq!(state.remove("count"), None);
    }

    #[test]
    fn failed_serialization_keeps_previous_value() {
        struct Invalid;
        impl Serialize for Invalid {
            fn serialize<S: serde::Serializer>(&self, _: S) -> Result<S::Ok, S::Error> {
                Err(serde::ser::Error::custom("test failure"))
            }
        }
        let state = SessionState::default();
        state.set("value", 7).unwrap();
        assert!(state.set("value", Invalid).is_err());
        assert_eq!(state.get::<i32>("value").unwrap(), Some(7));
    }

    #[tokio::test]
    async fn retained_uploads_are_session_local_and_fresh_sessions_start_empty() {
        let store = Arc::new(SessionStore::new(Duration::from_secs(5)));
        let lease = store.connect(None).await;
        let id = lease.id.clone();
        lease.state.uploads.lock().insert("file".into(), "sales.csv".into(), Some("text/csv".into()), vec![1, 2, 3]);
        let other = store.connect(None).await;
        assert!(store.state_for_upload(&other.id).unwrap().uploads.lock().get("file").is_none());
        assert!(store.state_for_upload("unknown").is_none());
        drop(lease);
        let restored = store.connect(Some(&id)).await;
        assert_eq!(restored.id, id);
        assert_eq!(store.state_for_upload(&id).unwrap().uploads.lock().get("file").unwrap().as_bytes(), &[1, 2, 3]);
        let fresh = store.connect(None).await;
        assert_ne!(fresh.id, id);
        assert!(store.state_for_upload(&fresh.id).unwrap().uploads.lock().get("file").is_none());
    }

    #[tokio::test]
    async fn upload_lookup_obeys_local_retention_and_does_not_renew_expiry() {
        let store = Arc::new(SessionStore::new(Duration::ZERO));
        let lease = store.connect(None).await;
        let id = lease.id.clone();
        assert!(store.state_for_upload(&id).is_some(), "connected sessions do not expire");
        drop(lease);
        assert!(store.state_for_upload(&id).is_none());
        let fresh = store.connect(Some(&id)).await;
        assert_ne!(fresh.id, id);
        assert!(fresh.state.uploads.lock().get("file").is_none());
    }

    #[tokio::test]
    async fn leases_restore_expire_and_ignore_superseded_drop() {
        let store = Arc::new(SessionStore::new(Duration::from_secs(5)));
        let lease = store.connect(None).await;
        let id = lease.id.clone();
        lease.state.set("count", 2).unwrap();
        let replacement = store.connect(Some(&id)).await;
        assert!(!lease.is_current());
        drop(lease);
        assert!(replacement.is_current());
        assert!(store.sessions.lock()[&id].disconnected_at.is_none());
        drop(replacement);
        let disconnected = store.sessions.lock()[&id].disconnected_at.unwrap();
        let restored = store.connect_at(Some(&id), disconnected + Duration::from_secs(4));
        assert_eq!(restored.id, id);
        assert_eq!(restored.state.get::<i32>("count").unwrap(), Some(2));
        drop(restored);
        let disconnected = store.sessions.lock()[&id].disconnected_at.unwrap();
        let expired = store.connect_at(Some(&id), disconnected + Duration::from_secs(5));
        assert_ne!(expired.id, id);
        assert_eq!(expired.state.get::<i32>("count").unwrap(), None);
        assert!(!store.sessions.lock().contains_key(&id));
        let unknown = store.connect(Some(&uuid::Uuid::new_v4().to_string())).await;
        assert_ne!(unknown.id, expired.id);
        assert_eq!(unknown.state.get::<i32>("count").unwrap(), None);
    }

    #[tokio::test]
    async fn server_stores_do_not_share_sessions_and_active_sessions_do_not_expire() {
        let a = Arc::new(SessionStore::new(Duration::ZERO));
        let b = Arc::new(SessionStore::new(Duration::ZERO));
        let lease = a.connect(None).await;
        lease.state.set("private", "a").unwrap();
        let latest = a.connect_at(Some(&lease.id), Instant::now() + Duration::from_secs(999));
        assert_eq!(latest.id, lease.id);
        assert!(!lease.is_current());
        assert!(latest.is_current());
        let other = b.connect(Some(&lease.id)).await;
        assert_ne!(other.id, lease.id);
        assert_eq!(other.state.get::<String>("private").unwrap(), None);
    }
}
