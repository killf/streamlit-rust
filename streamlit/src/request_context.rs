//! The per-connection request context: the measured `st.context` surface of
//! the pinned 1.66.1 reference (tests/reference/reference-browser/
//! context-headers), with a deliberate default header whitelist.

use std::collections::BTreeMap;

/// Which WebSocket handshake headers `request_context()` reflects.
///
/// The measured Python 1.66.1 reference returns every handshake header with
/// no whitelist — including credentials and transport headers. The Rust
/// default deliberately exposes only common non-credential headers; widening
/// it is an explicit server-builder choice, never a silent default.
#[derive(Clone, Debug, Default)]
pub enum RequestHeaderAccess {
    /// `user-agent`, `accept-language`, `accept`, `origin`, `host`.
    #[default]
    Standard,
    /// Every handshake header — the measured Python behavior. Credentials
    /// and transport headers included; only for trusted deployments.
    All,
    /// Exactly the named headers (matched case-insensitively).
    Selected(Vec<String>),
}

impl RequestHeaderAccess {
    pub(crate) fn allows(&self, name: &str) -> bool {
        let lowercase = name.to_ascii_lowercase();
        match self {
            Self::All => true,
            Self::Standard => matches!(lowercase.as_str(), "user-agent" | "accept-language" | "accept" | "origin" | "host"),
            Self::Selected(names) => names.iter().any(|candidate| candidate.eq_ignore_ascii_case(name)),
        }
    }
}

/// A read-only snapshot of the current browser connection, taken per call.
///
/// Header names are normalized to lowercase (HTTP names are case-insensitive;
/// the Python reference passes the received spelling through — a documented
/// divergence). `url`/`locale`/`timezone`/`timezone_offset`/`theme`/`is_embedded`
/// come from the official frontend's per-rerun context report; native clients
/// that send none see `None`/`false`, exactly as the frozen references show.
/// `ip_address` and cookies stay out of this slice.
#[derive(Clone, Debug, Default, PartialEq, Eq)]
pub struct RequestContext {
    /// The whitelisted handshake headers of this connection.
    pub headers: BTreeMap<String, String>,
    /// The page URL the browser reported with the run, if any.
    pub url: Option<String>,
    /// The browser locale, if reported.
    pub locale: Option<String>,
    /// The IANA timezone name, if reported.
    pub timezone: Option<String>,
    /// The timezone offset in minutes, if reported.
    pub timezone_offset: Option<i32>,
    /// The browser color scheme ("light"/"dark"), if reported.
    pub theme: Option<String>,
    /// Whether the browser reported the page as embedded.
    pub is_embedded: bool,
}

#[cfg(test)]
#[path = "../tests/request_context/mod.rs"]
mod tests;

/// The authenticated identity a `RequestAuthenticator` resolves for a
/// connection. `sub` is the stable subject identifier; the remaining fields
/// mirror the pinned reference's `st.user` mapping entries.
#[derive(Clone, Debug, Default, PartialEq, Eq)]
pub struct UserIdentity {
    pub sub: String,
    pub name: Option<String>,
    pub email: Option<String>,
    pub picture: Option<String>,
    pub roles: Vec<String>,
    /// Any additional claims carried into the `st.user()` mapping.
    pub extra: BTreeMap<String, String>,
}

impl UserIdentity {
    /// The `st.user`-equivalent mapping: the standard fields when present,
    /// then every extra claim; an anonymous connection maps to empty.
    pub fn to_dict(&self) -> BTreeMap<String, String> {
        let mut out = BTreeMap::new();
        // The anonymous baseline maps to empty: absent fields and an empty
        // sub never enter the mapping (the frozen reference has no keys).
        for (key, value) in [("sub", (!self.sub.is_empty()).then_some(&self.sub)), ("name", self.name.as_ref()), ("email", self.email.as_ref()), ("picture", self.picture.as_ref())] {
            if let Some(value) = value {
                out.insert(key.to_owned(), value.clone());
            }
        }
        if !self.roles.is_empty() {
            out.insert("roles".to_owned(), self.roles.join(","));
        }
        for (key, value) in &self.extra {
            out.insert(key.clone(), value.clone());
        }
        out
    }
}

/// Decides, per connection, whether the credentials on the WebSocket
/// handshake identify a user. Implementations run at connect time against
/// every handshake header (not the app-visible whitelist — the authenticator
/// is trusted server configuration) and must be cheap and side-effect free.
pub trait RequestAuthenticator: Send + Sync + 'static {
    fn authenticate(&self, headers: &BTreeMap<String, String>) -> Option<UserIdentity>;
}

/// A fake-credential authenticator for local development and tests: reads a
/// JSON identity from one named request header. Never a production identity
/// source — anyone able to set the header becomes that user.
#[derive(Clone, Debug)]
pub struct HeaderAuthenticator {
    header: String,
}

impl HeaderAuthenticator {
    pub fn new(header: impl Into<String>) -> Self {
        Self { header: header.into() }
    }
}

impl RequestAuthenticator for HeaderAuthenticator {
    fn authenticate(&self, headers: &BTreeMap<String, String>) -> Option<UserIdentity> {
        let raw = headers.get(&self.header.to_ascii_lowercase())?;
        let value: serde_json::Value = serde_json::from_str(raw).ok()?;
        let object = value.as_object()?;
        let identity = UserIdentity {
            sub: object.get("sub")?.as_str()?.to_owned(),
            name: object.get("name").and_then(|item| item.as_str()).map(str::to_owned),
            email: object.get("email").and_then(|item| item.as_str()).map(str::to_owned),
            picture: object.get("picture").and_then(|item| item.as_str()).map(str::to_owned),
            roles: object
                .get("roles")
                .and_then(|item| item.as_array())
                .map(|items| items.iter().filter_map(|item| item.as_str().map(str::to_owned)).collect())
                .unwrap_or_default(),
            extra: object
                .iter()
                .filter(|(key, _)| !["sub", "name", "email", "picture", "roles"].contains(&key.as_str()))
                .filter_map(|(key, item)| item.as_str().map(|text| (key.clone(), text.to_owned())))
                .collect(),
        };
        Some(identity)
    }
}

/// Parse `k=v; k2=v2` cookie pairs from one raw Cookie header value. Names
/// and values are taken verbatim (no percent-decoding); a segment without `=`
/// is skipped. Mirrors the frozen reference's observable mapping.
pub(crate) fn parse_cookies(raw: &str) -> BTreeMap<String, String> {
    raw.split(';').filter_map(|pair| pair.split_once('=')).map(|(name, value)| (name.trim().to_owned(), value.trim().to_owned())).collect()
}

impl RequestContext {
    /// The cookies visible to this app: parsed from the Cookie header only
    /// when the server's header whitelist let it through (the default
    /// Standard set does not — cookies are credentials, like the Python
    /// surface made visible only by explicit configuration here).
    pub fn cookies(&self) -> BTreeMap<String, String> {
        self.headers.get("cookie").map(|raw| parse_cookies(raw)).unwrap_or_default()
    }
}

/// The read-only `st.user`-equivalent mapping returned by `st.user()`;
/// `to_dict()` mirrors the reference's dict shape, `is_empty()` the
/// anonymous baseline.
#[derive(Clone, Debug, Default, PartialEq, Eq)]
pub struct UserView {
    pub(crate) mapping: BTreeMap<String, String>,
}

impl UserView {
    pub fn to_dict(&self) -> BTreeMap<String, String> {
        self.mapping.clone()
    }

    pub fn is_empty(&self) -> bool {
        self.mapping.is_empty()
    }
}
