//! Query-params regressions against the measured Python 1.66.1 wire (see
//! .codex/compatibility.md, Query params): the run's parameter store is
//! seeded from the browser-reported query string and server-side writes
//! serialize as alphabetically sorted, percent-encoded k=v pairs like the
//! reference's page_info_changed. The selectbox upgrade round (creation
//! mode, filter mode, queryParamKey) adds the websocket regression once it
//! lands.
#[test]
fn query_param_store_round_trips_and_serializes_like_the_reference() {
    let mut store = crate::query_params::QueryParamStore::default();
    store.load("bound=y&mode=demo");
    assert_eq!(store.serialize(), "bound=y&mode=demo");
    store.set("mode", vec!["demo".into()]);
    assert_eq!(store.serialize(), "bound=y&mode=demo", "an equal write keeps the merged state");
    store.set("alpha", vec!["one".into(), "two".into()]);
    assert_eq!(store.serialize(), "alpha=one&alpha=two&bound=y&mode=demo");
    assert_eq!(store.get("mode"), Some("demo"));
    assert_eq!(store.get_all("alpha"), &["one".to_string(), "two".to_string()]);
    assert!(store.remove("bound"));
    assert_eq!(store.serialize(), "alpha=one&alpha=two&mode=demo");
    store.load("q=%E4%B8%AD%E6%96%87+text");
    assert_eq!(store.get("q"), Some("\u{4e2d}\u{6587} text"));
    assert_eq!(store.serialize(), "q=%E4%B8%AD%E6%96%87+text", "non-ascii round-trips percent-encoded like urlencode");
    store.clear();
    assert_eq!(store.serialize(), "");
}
