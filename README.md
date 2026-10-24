# streamlit-rust

A Rust reimplementation of the Streamlit server, targeting the public behavior of Streamlit 1.66.1 with the official frontend reused without modification.

This repository is an early baseline. It is **not yet compatible with Streamlit 1.66.1**. Scope and current status are tracked in the [compatibility matrix](/.codex/compatibility.md); no same-name Rust function or passing health check is a compatibility claim.

## Layout

- `streamlit/`, `streamlit-macros/`: Rust workspace.
- `www/`: frontend distribution; do not edit production bundle files by hand.
- `tests/reference/`: Python 1.66.1 oracle, deterministic fixtures, and real browser HTTP/WS/protobuf traces.
- `compatibility/`: generated docs-driven matrix and baseline.
- `docs/`: project usage documentation; start with the [user guide](docs/guide/README.md).
- `tools/`: fixed upstream and matrix verification tools.
- `.codex/`: local agent configuration, development planning, [architecture](.codex/architecture.md), [compatibility policy](.codex/compatibility.md), and [acceptance requirements](.codex/acceptance.md).

Development checks and optional upstream-cache audits are documented in the [acceptance requirements](.codex/acceptance.md). Official artifacts and hashes are locked in [upstream.lock.json](/upstream.lock.json).
