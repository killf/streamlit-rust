//! Unit regressions for the request-context header allowlist.
use super::*;

#[test]
fn standard_allows_common_headers_but_not_credentials_or_probes() {
    let access = RequestHeaderAccess::Standard;
    for name in ["user-agent", "accept-language", "accept", "origin", "host"] {
        assert!(access.allows(name), "{name} is standard");
    }
    for name in ["cookie", "authorization", "x-m4-probe", "sec-websocket-key", "x-forwarded-for"] {
        assert!(!access.allows(name), "{name} must not leak by default");
    }
    // Header names are case-insensitive.
    assert!(access.allows("User-Agent") && access.allows("ACCEPT-LANGUAGE"));
}

#[test]
fn selected_matches_case_insensitively_and_all_allows_everything() {
    let selected = RequestHeaderAccess::Selected(vec!["X-M4-Probe".into(), "user-agent".into()]);
    assert!(selected.allows("x-m4-probe") && selected.allows("X-M4-PROBE") && selected.allows("USER-AGENT"));
    assert!(!selected.allows("cookie") && !selected.allows("accept"));
    assert!(RequestHeaderAccess::All.allows("cookie") && RequestHeaderAccess::All.allows("sec-websocket-key"));
}
