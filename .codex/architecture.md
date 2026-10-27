# Architecture

The Cargo workspace has two product crates: `streamlit` is the server/API runtime and `streamlit-macros` owns the `#[streamlit::main]` transform. Actix serves the static frontend, terminates WebSocket connections, decodes BackMsg, reruns the user function, and emits ForwardMsg through a per-connection render context.

The runtime assets now come directly from the archives pinned in `upstream.lock.json`: all 347 wheel `streamlit/static/` files are installed under `www/`, and all 91 same-tag protocol text files are under `streamlit/proto/`. Rust generates browser protocol types at build time with the existing paired prost/prost-build 0.14 dependencies; the independent OpenMetrics monitoring schema is retained as official text but is not compiled. Git attributes disable newline conversion for these upstream bytes. No frontend shim or Python runtime is used.

## Long-term architecture boundary

2026-10-27 确认的完整实现目标沿用现有两 crate 和官方前端/协议边界。功能范围以官方用户文档和使用流程为准，不照搬 Python API 导出或对象模型。长期 M0 先盘点文档功能、真实职责和状态生命周期，尚未批准另建执行框架、配置体系或认证集成；这些关键方案在相应阶段具体设计后决定。

应用值和 widget 状态按会话隔离，不等于所有资源必须按会话复制。当前缓存是会话级，与参考的进程级缓存存在已记录差异；是否共享、如何隔离及何时回收需明确设计。上传、媒体、缓存及会话的资源归属和生命周期分别核验，不用“无全局状态”替代资源管理证明。

公开接口、默认值、关键规则、依赖或验收变化交由用户决定。模块调整由真实职责和测试边界驱动，不为长期规划预建空层。每个阶段同时维护实现、协议证据、架构说明和实际运行局限。

The immediate architecture path is:

1. Keep the official frontend bytes and protocol authority pinned by `upstream.lock.json`; adaptation belongs in Rust, not in frontend rewrites.
2. Give each retained session a runner owning its widget state and rerun generation, and each run a fresh element tree; application values remain session-isolated.
3. Execute a user function into an element tree, serialize official ForwardMsg, then apply decoded BackMsg widget states before the next rerun.
4. Compare Rust HTTP/WS/protobuf behavior directly with the captured Python 1.66.1 traces in `tests/reference/reference-browser/`.
5. Verify UI behavior only through the unmodified official frontend in a real browser.

The present module boundaries are appropriate for this stage: `api.rs` defines the public developer surface, `elements/*` builds protocol-neutral element state, `proto.rs` isolates generated protocol types, `server.rs` and `websocket/*` own transport/session orchestration, and `memory.rs` is the remaining low-level storage helper. A larger split should wait until session state and data transfer implementations add real boundaries; no empty layer is justified now.

`session.rs` now owns typed JSON application state and the server-instance session registry shared across Actix workers. A versioned WebSocket lease retains one session's application values across reruns; each rerun still builds a fresh App/render tree and trigger map. A known-ID connection may upgrade immediately, but ownership transfers only after the predecessor's run and outgoing sends finish, using that session's run mutex. The registry mutex is never held across an await, so other sessions remain concurrent. Only the current owner's Drop marks it disconnected, so an older socket cannot expire its replacement. Later connections lazily evict disconnected state past the configurable retention window (local default 120 seconds). No user state is static/global. `SessionState` is exported from `lib.rs`; its Streamlit accessor is an inherent impl in `session.rs`, leaving `api.rs` independent of this batch.

## Dataframe selection and data updates — proposal

执行取舍：用户于 2026-10-27 最新澄清无需保持旧 Rust API 的向后兼容；Python 1.66.1 的功能和行为目标不变。本阶段按此前单入口方案推进 dataframe 选择，随后接通详情与编辑；不增加兼容入口或扩展 trait。数据追加的独立 Rust 扩展尚未批准。

实现沿用现有 `DataApi::dataframe`，新增 typed 返回、key/选择选项和专用 string_value codec；协议已有 `selection_mode`、`selection_state`、`selection_default` 与 widget id，复用 registry 的运行前状态应用、callback 和清理，无需改官方 proto 或引入依赖。既有 Arrow、列配置、编辑参考继续复用，新增选择输入已接入真实 Rust WS 回归及最小官方前端流程，覆盖边界见下述证据。

版本更正：官方 [2026 发布说明](https://docs.streamlit.io/develop/quick-reference/release-notes/2026)记录 1.58.0 已移除 `element.add_rows`，当前 Delta 也没有 eager 追加消息。数据追加的用户流程保留；旧接口不是 1.66.1 的兼容义务，新增 Rust 追加 API 则属于独立扩展，不能用整表发送冒称协议增量追加。

### 单入口与状态

`dataframe(options) -> Result<Option<DataframeState>, DataError>` 同时显示并读取选择。默认未开启选择返回 None；开启后返回 Some 状态（其中可以为空），SingleRowRequired 的实测首次状态包含首行。旧 Result<()> 尾表达式及测试回调按新返回类型迁移，不为保留旧签名增加第二入口。

- `DataframeState { selection: DataframeSelection }`；后者含 `rows: Vec<usize>`、`columns: Vec<String>`、`cells: Vec<(usize, String)>`，支持 serde 和默认空集合，与 wire 的 selection 外层对应。
- `DataframeOptions::key`、`on_select(OnSelect)`、`selection_mode(DataframeSelectionMode)`、`selection_default(DataframeSelection)`。`OnSelect` 为 Ignore/Rerun/Callback，callback 构造接受与现有 widget 相同的 `Fn(&Streamlit) + Send + Sync + 'static`。不让调用方管理内部 Arc。
- 默认 Ignore 保持纯显示；显式启用后默认选择模式按参考的 MultiRow，模式类型包含官方 single/multi row、column、cell 及 SingleRowRequired。组合、默认值、程序写入限制和异常先由固定 1.66.1 参考补证，再实现，不从 proto 字段存在推断兼容通过。
- 选择进入专用 codec，使用现有运行前状态应用/callback 和未渲染 widget 清理；不复用组件的宽松 JSON 解析。keyed SessionState 使用同一个 DataframeState，避免返回值与状态出现两套格式。

已实现的基本用法（完整模式和组合仍受已测范围限制）：

```rust
if let Some(event) = st.dataframe(
    DataframeOptions::new(&batch)
        .key("orders")
        .on_select(OnSelect::Rerun)
        .selection_mode(DataframeSelectionMode::SingleRow),
)? {
    for row in &event.selection.rows {
        // row 是当前输入 batch 的位置，应用在此读取详情。
    }
}
```

官方 [dataframe 选择说明](https://docs.streamlit.io/develop/api-reference/data/st.dataframe)标注 1.66.0：浏览器排序后的行选择仍指向输入位置，不承诺跨过滤/换表的业务记录身份。应用的稳定记录键与恢复策略不能由 runtime 静默生成。基本数据替换、程序设置、callback 和隐藏恢复已有下述 1.66.1 参考；多页、其他参数变化及所有模式边界仍待验证，需要额外 Rust 规则时再确认。

### 数据更新的范围取舍

1. 推荐按当前参考的应用数据更新与重新渲染完成追加流程，不增旧 add_rows 同名接口；当前协议是整表 NewElement，成本随结果表大小增长。
2. 若需要可复用的 Rust 追加扩展，先单独设计句柄或按 key 的接口、schema 合并、会话/运行身份与资源回收，再批准实现；不能只保存会被下一轮复用的 delta path。
3. 可先交付选择/详情/编辑，再推进数据追加；追加目标继续留在 M2，不将暂缓写成取消或完成。

### 实现范围与验收

本批修改 `data_api.rs`、`widgets.rs`，复用 registry/传输和已有导出；同步使用指南、最小选择/详情/编辑示例及 Rust runtime/data 回归。旧测试显示 helper 泛化返回值，不为旧 unit 签名增加兼容层。参考应用仅采已有数据缺失处并冻结，旧数据不重写；全部参数、非法组合、跨页/会话及 CSV 完整闭环仍需继续验证。

验收覆盖：默认纯显示、空选择、行/列/单元格及组合、真实选择输入到 typed 返回和 keyed state、callback 顺序、排序输入位置映射、程序默认/更新、数据替换与隐藏/恢复边界；超出当前可测范围明确待核，不宣称全部模式完成。原有数据显示、配置、编辑、chart、形式及会话测试不回归。真实官方前端验证选择→详情→编辑，错误能定位 session/widget/phase/reason，避免逐帧打印数据。

当前 Team 按选择能力的独立验收边界执行，峰值不超过四个（含主代理）；核心类型先稳定，再整合协议回归，Review 在写入者交付后开始。同一文件仅一个写入者，不继续委派。

| 工作项 | 交付物 | 依赖 | 主/子代理、模型与档位 | 修改范围/只读 | 验收方式 | 启动与停止条件 |
| --- | --- | --- | --- | --- | --- | --- |
| 单入口与渲染 | typed state、Options、协议字段及错误传播 | 已冻结输入/输出 | 主代理，目标 Sol/high，实际由客户端控制 | data_api.rs、必要调用迁移和使用指南 | 默认渲染不回归，选择返回对照参考 | 立即开始，整合及最终验收后停止 |
| 选择 codec | string_value 解码与部分 keyed JSON 保留 | DataframeState 类型约定 | 子代理 Sol/high | widgets.rs | 复用冻结输入；不按新表行数清理旧位置 | 类型约定后开始，单元交付后停止 |
| 冻结协议回归 | 单元及真实 WS 的选择/run/callback/清理检查 | 核心 API 与 codec | 子代理 Sol/high | tests/data/mod.rs、tests/runtime/dataframe_selection.rs 及模块声明 | 直接重放冻结数据，验证返回与 keyed state、缩行观察 | 先写回归，核心可编译后整合运行 |
| 文档清理 | 压缩重复历史说明，保留验收边界和证据入口 | 当前清单与链接核对 | 子代理 Terra/medium | roadmap.md、acceptance.md | 无失效规则或断链，不删有效冻结证据 | 可并行，限定候选完成后停止 |
| 独立 Review | 缺陷与验收范围结论 | 最终实现与实际检查 | 子代理 Sol/high | 只读 | 当前 diff、单元/WS/官方前端与冻结参考对照 | 写入者交付释放并发后开始 |

主代理串行整合共享类型与 codec，集中执行代码检查、单元、集成及官方前端验证；没有额外协调框架或新增依赖，成本是三处边界交接与一次独立审查。

参考采证独立于返回接口取舍：使用固定三行、可区分视觉排序与输入位置的合成表，Python 1.66.1 采集五种配置：默认 Ignore；默认 MultiRow；官方示例的 single-row/column/cell 组合；multi-row/column/cell 组合；SingleRowRequired。覆盖真实选择、排序、首次默认与程序设置、callback/main 顺序、普通重跑、换表及隐藏后再探测/恢复；不预设换表或清理结果，不以注入 JSON 冒充浏览器操作。`tests/reference/dataframe_selection_app.py` 与 `tests/browser/dataframe_selection_capture.py` 复用既有 Recorder、协议解码和自有进程清理，独立核验后冻结结果供后续 Rust 回归使用。原 Arrow/editor 参考保持原样，无新增依赖或源码指纹门槛。

该参考采证已完成并独立核验：[冻结数据说明](../tests/reference/reference-browser/dataframe-selection/README.md)。五配置首次成功 30 阶段，仅另补三行缩成一行的 4 阶段。程序写入部分 keyed JSON 时，返回值补齐空字段而 keyed 原结构保持部分；同 key 缩行后仍保留可能已超出新表范围的旧行位置，不自动清理。隐藏当轮仍读到 key，下一隐藏探测才无 key，恢复为空选择。callback 包含浏览器回送上轮程序状态导致的后续触发，需复用真实 run 顺序。后续 typed state 可以通过 serde 默认读取缺失字段，但不能把此处部分 keyed JSON 冒称已经被参考补全。Rust 选择实现按本节单入口推进，兼容通过仍需实际验收。

## Dependency and launch audit (2026-10-25)

这是基于 `590aed547f062b6791689ffe48940ffd6461a603`、Windows MSVC 的历史依赖审计，不是当前安全检测或 MSRV 认证。当前依赖以 Cargo.toml/Cargo.lock 为准，当前工具链和检查见 [acceptance](acceptance.md#current-m0-baseline-2026-10-27)；不再把当时的“最新版本”、测试计数或升级范围写成现行约束。历史 stable 1.95 / nightly 1.98 的编译不能证明最低 Rust 版本可用。

已独立审查的修补提交 `bae7d199f7d7be692fbd960a5eb0d8b926fe74fd` 处理 bytes、time、anyhow、rand、tokio 的锁定版本。对应依据分别为 [0007](https://rustsec.org/advisories/RUSTSEC-2026-0007.html)、[0009](https://rustsec.org/advisories/RUSTSEC-2026-0009.html)、[0190](https://rustsec.org/advisories/RUSTSEC-2026-0190.html)、[0097](https://rustsec.org/advisories/RUSTSEC-2026-0097.html)、[0386](https://rustsec.org/advisories/RUSTSEC-2026-0386.html)。其中 rand 的受影响 log 配置未启用、Tokio 的 Unix AsyncFd 问题不适用于当时的 Windows 检查；这些适用性边界不等于没有其他风险。RustSec 库快照为 `21d909e4c8bd4e14c7aea58bf980c881a0053ab1`，原诊断日志在本地 `target/checks/dependency-audit-590aed5/`，没有把该比较冒称 cargo-audit 或攻击复现。

第二批 `1f2a852` 移除未使用的 Actix HTTP2/h2 默认依赖，保留其他原有功能，依据为 [h2 advisory](https://rustsec.org/advisories/RUSTSEC-2026-0258.html)。当时服务仅使用明文 HTTP1，没有通过强行跨代替换 h2 来声称支持 HTTP2。下游 Cargo feature 合并可能重新启用它，未来 TLS/HTTP2 设计必须重新核实；移除依赖不构成完整传输安全结论。原二进制与冻结轨迹仍保留其捕获时的依赖/配置来源，不冒称已由后来的补丁重建。

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
