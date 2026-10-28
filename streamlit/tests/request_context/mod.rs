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

#[test]
fn header_authenticator_reads_identity_and_ignores_garbage() {
    let authenticator = RequestHeaderAccess::Standard; // placeholder import guard
    let _ = authenticator;
    let auth = crate::HeaderAuthenticator::new("X-Test-User");
    let mut headers = std::collections::BTreeMap::new();
    assert!(auth.authenticate(&headers).is_none(), "no header -> anonymous");
    headers.insert("x-test-user".into(), r#"{"sub":"u1","name":"Ada","roles":["admin"],"team":"core"}"#.into());
    let identity = auth.authenticate(&headers).expect("valid JSON identity authenticates");
    assert_eq!(identity.sub, "u1");
    assert_eq!(identity.name.as_deref(), Some("Ada"));
    assert_eq!(identity.roles, ["admin"]);
    assert_eq!(identity.extra.get("team").map(String::as_str), Some("core"));
    let dict = identity.to_dict();
    assert_eq!(dict.get("sub").map(String::as_str), Some("u1"));
    assert_eq!(dict.get("roles").map(String::as_str), Some("admin"));
    headers.insert("x-test-user".into(), "not-json".into());
    assert!(auth.authenticate(&headers).is_none(), "garbage -> anonymous");
    headers.insert("x-test-user".into(), r#"{"name":"no-sub"}"#.into());
    assert!(auth.authenticate(&headers).is_none(), "missing sub -> anonymous");
}

#[test]
fn cookies_parse_from_the_whitelisted_header_only() {
    let context = crate::RequestContext {
        headers: [("cookie".to_owned(), "probe-flavor=oat; probe-session=42; broken".to_owned())].into_iter().collect(),
        ..Default::default()
    };
    assert_eq!(context.cookies(), [("probe-flavor".to_owned(), "oat".to_owned()), ("probe-session".to_owned(), "42".to_owned())].into_iter().collect());
    // No cookie header passed the whitelist -> empty mapping, like the
    // default Standard surface.
    assert!(crate::RequestContext::default().cookies().is_empty());
}
