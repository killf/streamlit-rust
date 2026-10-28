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
