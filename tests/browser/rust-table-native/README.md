# Rust table / native bar browser evidence

Only the independently reviewed `rust-native-final` two-run capture is archived
here. [archive.json](archive.json) gives exact source-to-archive SHA256 mappings,
deduplicated IPC references, frozen source hashes and the binary fingerprint.
[capture-metadata.json](capture-metadata.json) is an unchanged copy of the final
measurement metadata, including gate commands, spec fingerprints and partial
boundaries. Historical target-relative references inside copied JSON resolve
through archive.json; raw bytes and CDP events have not been rewritten.

Each run has four views in order: default table, explicit table, default native
bar and horizontal native bar. Both raw records, eight unique IPC streams and
one final full-page screenshot are retained. All rows/types/nulls, table cells,
mark labels and normalized full chart specs were compared with the
[Python reference](../../reference/reference-browser/table-native/README.md).
The independent review also checked SVG positive/negative/zero geometry and
same-connection trigger/completion. Dataset names change with actual values.
Nullable declarations and optional pandas metadata may differ between native
Arrow and pandas-produced Arrow; the archived comparisons state that boundary.

The first, failing explicit-index experiment, build executables, profiles,
process logs and redundant screenshots remain under ignored target and are not
part of this archive. Explicit row-number display was corrected before this
final capture: metadata-free native tables receive truthful Arrow RangeIndex
and column descriptors only when visible row numbers are requested. Arrays and
existing index metadata remain unchanged. No pandas producer/version is claimed.
The official frontend reads these descriptors, and PyArrow stream decoding plus
to_pandas confirmed the RangeIndex and values. See the public
[Arrow index documentation](https://arrow.apache.org/docs/python/pandas.html#handling-pandas-indexes)
and the metadata provenance in capture-metadata.json.

The captured command sequence was:

```powershell
cargo test -p streamlit --lib --locked data_api::tests
cargo test -p streamlit --lib --locked server::tests::data_views
cargo fmt --all -- --check
cargo clippy --workspace --locked --all-targets -- -D warnings
cargo test --workspace --locked
cargo build -p streamlit --example tables --locked
target/checks/table-reference/rust-tables-final.exe --native --port 8503
agent-browser --session table-native open about:blank
agent-browser --session table-native get cdp-url
```

The executable was a byte-identical copy of the built tables example. Its SHA256
is `4814e44f4ec0b7fbd3dd00efc61b1922f0716262bcc9b857c1d3229f06819383`.
Capture attached the existing CDP recorder before navigation to port8503 and
used the existing Page input wrapper for the real Update data button. It used
the unmodified official frontend. No new capture framework is included.
To run a newly built equivalent demo, use:

```powershell
cargo run -p streamlit --example tables --locked -- --native --port 8503
```

Observed gates: 16 data tests, two actual WebSocket tests, fmt, strict clippy and
workspace tests (63 unit tests plus two doctests) exited zero. The independent
review reran the 16 data tests, two WS tests and example check, and redecoded raw
protobuf/IPC rather than trusting stored comparison booleans. It found no
blocking issue within this scope. No claim of all API options is made.

Frozen data_api.rs SHA256:
`8876c12bb8ce69733f677332066046585ebd08bbf2b0d813ba1ebeb5c10be601`.
All other frozen source fingerprints are in archive.json. TableOptions,
TableBorder and DataApi already use the existing data_api public export; no
Cargo/lib export change is required. Rust returns Result<(), DataError> rather
than a Python DeltaGenerator handle; updates use normal session reruns.

This proves the bounded module candidate on 8503 against Python8605, not the
future unified8501/XSRF candidate. That build needs fresh merged source/config/
binary fingerprints and its own QA capture. The measured large-integer mixed
series error-versus-rounding difference and other unimplemented options remain
explicit partial boundaries.
