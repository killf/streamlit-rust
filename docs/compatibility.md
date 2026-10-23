# Compatibility

Streamlit runtime compatibility is pinned to 1.66.1. Product scope follows the official documentation catalog captured in the ignored cache `target/upstream/docs`; its observed docs label is 1.66.0 and its runtime target is 1.66.1. Version labels are recorded separately and no inaccessible versioned URL is synthesized.

The only feature matrix is [compatibility/api-compatibility-matrix.json](../compatibility/api-compatibility-matrix.json). It currently records 182 captured canonical pages, not a claim of completeness: 7 requested legacy pages are unavailable in the current docs and 2 redirects are recorded as aliases rather than extra rows. Missing and redirected pages stay explicit in the matrix and [p0-baseline.json](../compatibility/p0-baseline.json).

Each row has an official URL, Rust plan, `implementation_status`, `compatibility_status`, and evidence links. The current baseline has 11 source candidates and 171 absent implementations; every compatibility status is `unverified`. Candidates are not compatibility claims. Future verification must compare Rust API behavior, HTTP/WS/protobuf traces, and the unmodified official frontend against the pinned Python reference.

`python tools/verify_p0.py` regenerates the matrix while preserving prior evidence-backed non-unverified statuses when a row remains the same. New catalog rows and rows without sufficient evidence remain unverified.
