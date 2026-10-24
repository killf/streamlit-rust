# Architecture

The Cargo workspace has two product crates: `streamlit` is the server/API runtime and `streamlit-macros` owns the `#[streamlit::main]` transform. Actix serves the static frontend, terminates WebSocket connections, decodes BackMsg, reruns the user function, and emits ForwardMsg through a per-connection render context.

The runtime assets now come directly from the archives pinned in `upstream.lock.json`: all 347 wheel `streamlit/static/` files are installed under `www/`, and all 91 same-tag protocol text files are under `streamlit/proto/`. Rust generates browser protocol types at build time with the existing paired prost/prost-build 0.14 dependencies; the independent OpenMetrics monitoring schema is retained as official text but is not compiled. Git attributes disable newline conversion for these upstream bytes. No frontend shim or Python runtime is used.

The immediate architecture path is:

1. Keep the official frontend bytes and protocol authority pinned by `upstream.lock.json`; adaptation belongs in Rust, not in frontend rewrites.
2. Give each connection a session runner owning widget state, rerun generation, and the element tree; no application state is global.
3. Execute a user function into an element tree, serialize official ForwardMsg, then apply decoded BackMsg widget states before the next rerun.
4. Compare Rust HTTP/WS/protobuf behavior directly with the captured Python 1.66.1 traces in `tests/reference/reference-browser/`.
5. Verify UI behavior only through the unmodified official frontend in a real browser.

The present module boundaries are appropriate for this stage: `api.rs` defines the public developer surface, `elements/*` builds protocol-neutral element state, `proto.rs` isolates generated protocol types, `server.rs` and `websocket/*` own transport/session orchestration, and `memory.rs` is the remaining low-level storage helper. A larger split should wait until session state and data transfer implementations add real boundaries; no empty layer is justified now.

`session.rs` now owns typed JSON application state and the server-instance session registry shared across Actix workers. A versioned WebSocket lease retains one session's application values across reruns; each rerun still builds a fresh App/render tree and trigger map. A known-ID connection may upgrade immediately, but ownership transfers only after the predecessor's run and outgoing sends finish, using that session's run mutex. The registry mutex is never held across an await, so other sessions remain concurrent. Only the current owner's Drop marks it disconnected, so an older socket cannot expire its replacement. Later connections lazily evict disconnected state past the configurable retention window (local default 120 seconds). No user state is static/global. `SessionState` is exported from `lib.rs`; its Streamlit accessor is an inherent impl in `session.rs`, leaving `api.rs` independent of this batch.

## Dependency and launch audit (2026-10-25)

Base: `590aed547f062b6791689ffe48940ffd6461a603`, Windows x86_64 MSVC. No package declares `rust-version`; edition 2024 alone does not establish the workspace MSRV. Host-filtered Cargo metadata reports a highest dependency declaration of Rust 1.88 (Arrow 60 and actix-multipart 0.8.5). Installed stable is Rust/Cargo 1.95.0; its isolated `check --workspace --all-targets --locked --offline` passed on the original lock. Default Rust remains 1.98.0-nightly (54333ff07). Neither result is a Rust 1.88/MSRV test. Stable logs record a nonfatal Windows incremental-cache finalization warning, not a source-check failure.

The official crates.io API was queried for all 34 workspace dependencies rather than treating every newer version as necessary. Arrow 60.0.0, actix-multipart 0.8.5, emojis 0.9.1, subtle 2.6.1, CSV 1.4.0 and rust_decimal 1.43.0 remain current there. Examples of newer optional upgrades are paired prost/prost-build 0.14.4, actix-web 4.18.1, actix-ws 0.4.0 and actix-files 0.7.2; these are outside this minimal security patch. The two previously reviewed actix-files advisories affect <=0.6.9 and are fixed by the already locked 0.6.10: [path fallback](https://github.com/actix/actix-web/security/advisories/GHSA-8v2v-wjwg-vx6r), [empty Range](https://github.com/actix/actix-web/security/advisories/GHSA-gcqf-3g44-vc9p).

The RustSec database was read at revision `21d909e4c8bd4e14c7aea58bf980c881a0053ab1`; registry responses, package/feature graphs and check logs are rebuildable local diagnostics under ignored `target/checks/dependency-audit-590aed5/`. This is a lock/advisory comparison, not a cargo-audit run or proof of exploitability.

| Package | Locked before -> minimal repair | Official advisory and applicability |
|---|---|---|
| bytes | 1.11.0 -> 1.11.1 | [RUSTSEC-2026-0007](https://rustsec.org/advisories/RUSTSEC-2026-0007.html): `BytesMut::reserve` overflow with wrapping arithmetic; no application exploit reproduced. |
| time | 0.3.44 -> 0.3.47 | [RUSTSEC-2026-0009](https://rustsec.org/advisories/RUSTSEC-2026-0009.html): RFC2822 parsing stack exhaustion; linked through Actix/cookies/logging, no public attack path established here. |
| anyhow | 1.0.100 -> 1.0.103 | [RUSTSEC-2026-0190](https://rustsec.org/advisories/RUSTSEC-2026-0190.html): unsound contextual `downcast_mut`; no call in workspace production source. |
| rand | 0.9.2 -> 0.9.3 | [RUSTSEC-2026-0097](https://rustsec.org/advisories/RUSTSEC-2026-0097.html): custom reentrant logger/ThreadRng conditions; resolved `log` feature is absent, so no affected current configuration claimed. |
| tokio | 1.48.0 -> 1.51.6 | [RUSTSEC-2026-0386](https://rustsec.org/advisories/RUSTSEC-2026-0386.html): Unix AsyncFd safety; does not affect the checked Windows target. 1.51.6 is a patched branch; latest 1.54.1 is unnecessary here. |

The three existing direct requirements now exclude their vulnerable lower versions; rand/time remain transitive, with no artificial direct dependency added. Necessary lock companions: time-core 0.1.8, time-macros 0.2.27, num-conv 0.2.0; Tokio requires mio >=1.2.0, socket2 >=0.6.3 and tokio-macros ~2.7.0, locked at those minima, plus libc 0.2.183 required by mio. Tokio's windows-sys ^0.61 requirement reuses the existing 0.61.2 and removes the otherwise unused 0.60.2/0.53 target packages. Unrelated errno/rustix/tempfile Windows dependency selections retain their original 0.61.2 edges. No unrelated package upgrades, frontend/protocol changes or old proof fingerprints are permitted.

On this repaired lock, installed stable 1.95.0 and default nightly 1.98.0 both passed all-targets workspace checks, 66 workspace unit tests, 2 doctests and 8 data-app tests (`--locked --offline` after downloading the selected crates). Stable used isolated `target/checks/stable-audit-590aed5`; the two toolchains' logs are under the diagnostic directory above. These are compilation/native regression results, not a new official-browser capture, MSRV validation or complete security clearance. The already captured 943 binary keeps its original lock/config provenance; this patch does not rewrite old raw or advertise that old process as a rebuilt candidate.

The five-item repair was independently reviewed and committed separately as `bae7d199f7d7be692fbd960a5eb0d8b926fe74fd`. The separately reviewed second stage was committed as `1f2a852` and removes unused HTTP2: [h2 0.3.27](https://rustsec.org/advisories/RUSTSEC-2026-0258.html) was in the default Actix graph; the advisory fixes only >=0.4.16. Even current actix-http 3.19.0 requires h2 ^0.3.27, so a broad Actix update or forcing h2 0.4 is not justified. Current `HttpServer::bind` uses the plain HTTP1 path; HTTP2 was not an exposed/accepted product capability, and no live exploit is claimed. actix-web defaults are now disabled with every other original default explicitly retained: `macros`, `compress-brotli`, `compress-gzip`, `compress-zstd`, `cookies`, `unicode`, `compat`, `ws`. The only lock change is removal of the h2 package and actix-http's h2 edge; no package version changes. Locked workspace feature-tree inspection finds neither h2 nor http2; inverse `cargo tree -i h2` reports package not found (expected exit 101). Stable 1.95.0 isolated all-targets check passed, and default-nightly real HTTP/static/WS/upload/session/data/ownership regressions passed 15/15. Logs are `no-http2-*` under the same ignored diagnostic directory. Independent review passed before that separate commit. Downstream Cargo feature unification can re-enable HTTP2; reassess if TLS/HTTP2 features are introduced. Removing this unused dependency does not prove complete transport security.

## Static directory launch contract (frozen for Raman / Hooke)

Implemented in isolated commit `b2c2013`, independently reviewed by Hooke and integrated on mainline in `f2a3a78`. The contract below remains the behavior/acceptance boundary; existing captures retain their original binary/source/config provenance and are not relabeled as the integrated build.

Public API: retain `StreamlitServer::new(...)` and `start() -> std::io::Result<()>`; add only `with_static_dir(self, path: impl Into<PathBuf>) -> Self`. The macro continues using the existing constructor; `STREAMLIT_STATIC_DIR` provides configuration without rewriting an app. No new deployment/config framework, dependency, embedding of the complete frontend, or production Python.

Resolve once before binding and share the canonical absolute result across Actix workers, in this exact order:

1. Explicit builder path, when supplied.
2. `STREAMLIT_STATIC_DIR`, when present (read as an OS path; empty is an error, not absence).
3. `current_exe()?.parent()/www`, independent of CWD.
4. Development fallback only in a debug build: CWD's `www`, and only when CWD contains the existing root `Cargo.toml`, `streamlit/Cargo.toml` and `streamlit-macros/Cargo.toml`. This preserves the published repository-root `cargo run --example ...` workflow. Release builds never use this fallback.

Builder/environment relative paths are explicitly relative to startup CWD, resolved once; absolute overrides work from any CWD. No ancestor/disk search, global CWD mutation, or `CARGO_MANIFEST_DIR`/absolute build-machine path as a runtime default. A supplied invalid override must fail without trying lower priorities. An existing but invalid executable-side `www` must also fail; only its absence permits the debug fallback. Log selected source and canonical path once, making precedence observable.

Validate before opening the listening socket: selected path is a readable directory; `index.html` is a readable regular file with the exact pinned official index bytes; each local JS/CSS boot/preload asset referenced by that index is present, readable and nonempty inside the canonical root. Reject an unrelated/old index or incomplete boot assets with an actionable `io::Error` containing selection source, path and cause. A small compiled identity of the existing official index may be used; it is not a runtime build-path fallback or permission to modify the bundle. Do not add markers/shims to `www`. Startup identity/availability checks are not a claim of runtime integrity checking of all chunks.

Distribution layout is `<install>/app.exe` plus `<install>/www/**`, copied from the full locked 1.66.1 wheel static tree, or the same tree at an explicitly configured directory. Keep every official file unchanged. Package/review gates compare the complete 347-file set and every hash against the locked wheel, before and after relocation; startup merely rejecting malformed directories does not replace that check. Keep existing Actix HTTP1, API-route precedence, MIME/cache/range behavior and WebSocket/upload routes unchanged. Missing assets must not leave a health-only server listening.

Required acceptance matrix: **12/12 scenarios**, all named invalid-path variants below, **347/347 packaged files/hash matches**, and **0 affected HTTP/static/WS regression failures**. These are requirements, not results. Use temporary directories and subprocess-specific environment/CWD or explicit private resolver inputs; do not mutate the test process's global environment/CWD while parallel tests run.

| ID | Required observation |
|---|---|
| S01 | Valid builder wins over valid environment and executable sidecar; selected canonical root is the builder directory. |
| S02 | With no builder, valid environment wins over sidecar, including an explicit relative path resolved from startup CWD. |
| S03 | From an unrelated CWD containing a decoy `www`, a relocated executable selects its adjacent official sidecar; real GET index/boot JS/CSS bodies match the packaged bytes. |
| S04 | Debug repository-root quickstart with no override/sidecar still starts via the narrowly allowed CWD fallback. |
| S05 | Release mode with the same repository CWD but no override/sidecar fails; no implicit CWD fallback. |
| S06 | Invalid explicit builder (nonexistent, ordinary file, or unreadable path) fails before bind despite valid lower-priority roots. |
| S07 | Invalid environment directory fails before bind despite a valid sidecar. |
| S08 | Empty environment value and empty builder path each fail explicitly; neither means absence. |
| S09 | Selected directory with missing/unreadable index fails before bind. |
| S10 | Selected directory containing an unrelated or old index fails; an invalid existing sidecar cannot fall back to a valid developer CWD. |
| S11 | Missing/unreadable/empty referenced JS or CSS asset fails before bind. |
| S12 | No candidate (including debug CWD without the repository markers) fails clearly; no health/WS endpoint is reachable from that failed startup. |

Implementation uses `streamlit/src/server.rs` and the existing-runtime static-assets test module, with existing crates and official bytes as read-only inputs. The [user guide](../docs/guide/README.md#run-an-installed-executable-from-any-directory) documents sidecar/configuration and precedence; the root README remains a short usage/contribution entry. Any new browser observation records its own binary/source/config and selected static-root provenance; it cannot relabel an earlier captured binary as this build.
