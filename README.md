# streamlit-rust

A Rust reimplementation of the Streamlit server, targeting the public behavior of Streamlit 1.66.1 with the official frontend reused without modification.

This repository is an early baseline. It is **not yet compatible with Streamlit 1.66.1**. Scope and current status are tracked in the [compatibility matrix](/docs/compatibility.md); no same-name Rust function or passing health check is a compatibility claim.

## Layout

- `streamlit/`, `streamlit-macros/`: Rust workspace.
- `www/`: frontend distribution; do not edit production bundle files by hand.
- `tests/reference/`: Python 1.66.1 oracle, deterministic fixtures, and real browser HTTP/WS/protobuf traces.
- `compatibility/`: generated docs-driven matrix and baseline.
- `docs/`: short user, architecture, compatibility, and acceptance documentation.
- `tools/`: fixed upstream and matrix verification tools.
- `.codex/`: local agent configuration and task-contract notes.

## Fresh-checkout checks

```powershell
python -m pytest tests/reference -q
python tests/journeys/validate_journeys.py
cargo fmt --all -- --check
cargo clippy --workspace --locked --all-targets -- -D warnings
cargo test --workspace --locked
```

Official artifacts and hashes are locked in [upstream.lock.json](/upstream.lock.json). `tools/fetch_upstream.py` and `tools/verify_p0.py` are optional local-cache auditors, not fresh-checkout gates. `fetch_upstream.py --download` restores only the three locked archives; it cannot reconstruct the captured docs catalog and HTML under `target/upstream/docs`.
