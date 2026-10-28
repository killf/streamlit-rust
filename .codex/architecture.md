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

### Session concurrency and reclamation validation

本轮在既有 M5 内核验两个缺口，不改 SessionStore/WS 接管规则：16 个真实 WS 客户端使用两个 Actix worker 配置，各自建立不同计数，再并行让一半在关闭确认后重连、一半继续点击，最后核对各自 session ID、计数与普通重跑；另用零保留期和每轮 32 个会话做四轮到期清理，通过 Weak 观察应用值、上传容器及缓存资源对象在无外部强引用时释放。零保留期是既有测试参数，16/32/4 是本次负载，不是新产品限额或 SLO。

先补使用说明，再只修改 session.rs 的既有单元模块与 tests/runtime/sessions.rs；复用真实 WS 工具和已有接管暂停回归，无新依赖/公共接口。新增 WS 测试用自有服务器，成功、错误或 panic 后均先停止并等待自有 handle，再报告；清理测试观察对象所有权，不从 Weak 释放推断 RSS 下降、全局媒体回收或长时无泄漏。实际 72 次运行、32 个保留计数以及 128 个到期会话均通过，对运行中接管另复验既有暂停回归；未发现需修改生产逻辑的证据。相关格式/全目标 Clippy 和 13 项单元/真实 WS 检查已过；没有重采 Python 或将上一版本全量结果冒称本批全量验收。

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

必选单行的空协议输入已完成[独立八阶段补证](../tests/reference/reference-browser/dataframe-required-protocol/README.md)及修复。`12f3664` 的真实 WS 红复现表明：非空表空 rows 时返回 `[0]`，keyed/callback 却看到空 rows。现在 codec 携带注册时的 required/行数，在变更判断和回调前补齐协议字段及必选首行，注册更新下一轮元数据；删除 renderer 按本轮行数强补返回值的分支。空→非空恢复当轮仍可为空，非空→空当轮也可保留旧位置，符合固定 Python 实测；程序 partial keyed JSON 保留，不统一裁剪位置。原 34 与新增 8 阶段共用 42 阶段真实 Rust WS 回归，旧 UI 证据不重采；新增探针仅为显式协议注入，没有浏览器可清除的声明，无新公共 API 或依赖。

## CSV application integration — accepted A

状态：用户已于 2026-10-27 选择 A，按当前长期 Goal 执行，尚未验收。现有 `data_app` 表是 `group_key/row_count/total_amount/avg_amount` 聚合结果；其 Row 仅保留四个销售字段，不能把所选聚合位置当成唯一订单，也不能无依据回写原 CSV。使用通用示例验证框架链路，销售统计继续保留自身规则。B/C 不进入本次范围。

| 方案 | 交付与代价 |
| --- | --- |
| A，推荐 | 新增 `csv_workbench` 通用示例，串起上传、筛选、选择、详情编辑、应用、新增行、计数图和 CSV 下载。所有单元格按文本处理，保持原列及顺序；不改已有销售示例或其金额规则。需要一个独立示例及其参考/回归。 |
| B | 将相同的明细编辑流程并入当前 `data_app`；聚合结果仍只读，从应用后的原始明细重新计算。需扩充既有解析模型以保留所有列，并更新原页面、参考应用和整合旅程；耦合与复验范围更大。 |
| C | 暂缓 CSV 应用整合，先推进其他已确认的库内能力。CSV 闭环仍是未完成的 M2 目标，不取消或视为已过。 |

A 的已采纳行为：UTF-8/BOM CSV，列名与内容原样保留；空/重复列名及结构、编码错误明确报错。所有值按文本展示，不猜测数值/日期类型。筛选为指定列的文本精确匹配；计数图按用户选择的列统计当前筛选结果。选择位置映射到原始明细，并先检查有效性。详情使用固定行编辑器，显式 Apply 后才更新本会话工作数据、表和图；原上传 bytes 不变，仅提供修订 CSV 下载，不落盘或写数据库。

共享控件契约：`CSV workbench` 标题；`Upload CSV` 单文件；`Filter column` 与 `Count by` 默认首列；`Filter enabled` 默认 false，启用时 `Exact value` 连空串也按精确文本筛选；`Rows` 单行选择，`Detail draft` 固定单行编辑器配 `Apply`，`New rows draft` 空输入动态编辑器配 `Append`；`Download CSV` 下载 `workbench.csv`，`Ordinary rerun` 普通重跑。示例监听 `127.0.0.1:8545`，使用 `#[main]`。Python 和 Rust 参考使用同一行为契约，传输与运行身份各自记录。

实际 WS/HTTP 探针发现下载前置缺陷：按钮已生成真实 `.csv` 地址，但媒体路由白名单拒绝，GET 404；下载 MIME/文件名参与地址计算后未存储，HTTP 不能提供既有 `file_name` 参数指定的名称。修复归入已采纳的 CSV 下载链路：`media.rs` 内存记录保留下载元数据，`server.rs` 对已注册下载按其 MIME 和 attachment 文件名响应；现有公开存取接口、内容地址、普通媒体路由及 Range 语义保持，未知 id 仍 404，不引入磁盘读取或依赖。先保留红复现，再在 `tests/runtime/media.rs` 检查真实 CSV GET、响应头、字节与 Range；文件名、无后缀及其他 MIME 的完整兼容不从这个 CSV 场景推定。原始诊断和回归日志位于本地 `target/checks/m2-csv-workbench/`。

新增行用独立动态编辑器及显式 Append，保留重复行，空单元格导出为空 CSV 字段；不隐式合并其他文件或去重。保留筛选结果位置到原始行的映射，选择和详情编辑器绑定上传 id、数据版本、筛选视图身份及原始行位置；筛选变化清空旧选择及详情草稿，选行变化清空旧详情草稿。Apply 只接受仍属于同一视图和行版本的草稿；筛选/选行与 Apply 同轮或延迟旧状态不能写入另一行。新增行草稿保留至应用或切换有效源文件；成功 Apply/Append 增加数据版本并重置选择及草稿。成功替换文件以新来源重置工作副本；坏文件显示错误并保留上次有效副本，界面明确标记仍在显示旧来源；清空仅经显式 Clear 按钮。不生成业务主键。

来源切换已定（2026-10-28 用户采纳方案 1，显式清空）：真实 Python 前端在单文件替换时先发空 uploader state 再发新文件；该空状态只清除选择、保留工作副本，移除已选文件同样保留副本，显式 `Clear working copy` 按钮是唯一清空入口。Rust 示例与 Python 参考同轮改为该契约（`Workbench::source` 的 None 分支不再触碰 sheet，新增 `clear()` 与 `wb-clear` 按钮；参考应用 None 分支仅丢弃 attempt、新增同 key 按钮）。`sources-clear` 16 阶段双端真实前端采集一次成功并冻结：坏替换保留旧副本、移除上传保留副本、显式清空生效，四次实际下载双端逐字节相同；旧失败链保留于本地 `target/checks/m2-csv-workbench/python/sources-first/` 未改写，此前 main/filters 33 阶段未重采。方案 2（暂存导入）与 3（移除即清空）未采纳。

A 的拟改范围：`streamlit/examples/csv_workbench.rs` 包含数据与视图的简洁实现及纯函数回归；`tests/reference/csv_workbench_app.py` 与一个复用既有 Recorder/解码工具的采集器仅冻结新组合，旧正确数据不重采；现有使用指南、矩阵证据和必要运行回归同步。只使用现有依赖和公共 API，不另建解析框架、存储服务或 Rust 追加接口。处理与整表传输成本随内存数据量增长，不通过截断结果或新限额获得性能结论。

验收：UTF-8/BOM/引号换行及列顺序往返、空表与无匹配、坏文件不覆盖有效副本；未 Apply 时原数据/图不变，Apply 后详情、过滤、统计和下载同时一致；排序后的选择指向正确原位置，筛选/选择与 Apply 同轮及延迟旧状态均不会误写其他行；新增、替换、清除、普通重跑及两会话隔离有真实流程证据。Python 新流程采一次冻结，Rust 单元/WS 复用；使用官方前端实际验证并核下载字节，最后独立 Review。完成 A 仅关闭这条应用子流程，不替代其余模式/参数、M3–M7 或长期整体验收。

| 工作项 | 交付物 | 依赖 | 主/子代理 | 模型与档位 | 修改范围/只读 | 验收方式 | 启动与停止条件 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 工作台与整合 | 单一工作数据源、视图与操作 | 用户采纳 A | 主代理 | 目标 Sol/high，实际由客户端控制 | 新示例及相关 Rust 回归 | 代码、单元、WS、下载一致性 | 采纳后开始，本子流程验收后停止 |
| 新流程参考 | 正确输入、返回及真实交互 | 先定使用说明和控件契约 | 子代理 | Sol/high | Python 参考及采集/冻结数据 | 原 PB/DOM/Arrow/HTTP 与一次采集 | 契约稳定后开始，冻结交付即停 |
| 指南与界面核验 | 可运行指南、状态提示 | 核心与参考稳定 | 子代理 | Terra/medium | 指南和只读界面验证 | 实际步骤、误导/状态检查 | 可独立部分并行，交付即停 |
| 独立审查 | 问题与最终范围结论 | 当前实现及实际检查 | 子代理 | Sol/high | 只读 | 不改实现，复核原始证据及边界 | 写入者交付后开始，通过后停 |

峰值四个含主代理；参考先行，核心与指南在共享契约稳定后并行，审查复用已释放槽位。主代理统一测试和整合，同一文件不并行写。额外协调仅为控件/数据契约、参考交付和一次独立审查，无加速倍数承诺。

采纳 A 后的可执行子目标：在当前长期 Goal 的 M2 内交付上述文本 CSV 工作台，按已说明的会话编辑、应用、追加与导出语义完成实现、冻结参考、Rust 回归、真实前端和独立 Review，保留旧销售示例与有效证据；不增依赖/库接口，不做外部数据写入、发布或部署。关键偏差另交用户决定，普通细节自主处理，验收后及时提交推送工作分支并继续未完成的长期目标。

## Data editor positive deletion bounds

`ff1290d` 在两行原表回送 `deleted_rows:[2]` 时因 `Vec::remove` 越界 panic，已留本地红复现 `target/checks/m2-editor-invalid-rows/rust/before.log`。锁定 Python 1.66.1 的 18 个脚本级边界中，非法正删除位置产生 IndexError/OverflowError、原 caller 输入不变；脚本实验不冒充协议或 UI 证据。另一次四阶段真实 Python WS 已证明错误后同连接可合法删除并恢复，Rust 直接复用其原始输入回归；[冻结数据及清理说明](../tests/reference/reference-browser/dataeditor-invalid-rows/README.md)明确区分首次采集清理观察失利和最终资源退出。

本批仅修复正删除位置的范围检查：`data_api.rs` 将数值转换为本机索引时检查可表示性，并在删除前核对所有位置；非法值沿用现有 `DataError::InvalidOption`，不忽略、截断或选择其他行。合法删除的倒序/去重、先编辑后删除再新增的顺序、原表不变及公开接口不变。先补使用者错误说明，再修生产逻辑；复用冻结参考、合法/混合非法输入、空表及真实 WS 错误后恢复，最后独立 Review。拟改范围为现有 data_api、编辑器运行测试及相关证据/指南，无新依赖。

Python 私有实现对负位置采用 pandas 索引语义，Rust 目前拒绝负数；该差异另行保留，不在本批悄悄改写为新的索引规则。CSV 来源规则仍待用户决定，与此修复无依赖。

## Vega-Lite same-shape updates — accepted A (content-named dataset)

现有 `vega_lite_chart` 曾真实复现：同一图、同列/行数、同 1416 字节 IPC，实际 a.count 从 3 改为 8，但可见 ARIA/SVG/PNG 仍为 3，普通 rerun 也未恢复；四阶段失败基线已冻结于 `tests/browser/rust-vega-refresh-before/`。官方前端 Quiver 的数据判定不含值；Python 先前的两组记录也有同 shape/length 的漏刷，其 ForwardMsg hash 已改变，证明仅修 Rust 漏含数据的消息 hash 不充分。Rust 现有 CSV/原生 bar 路径使用内容名进入 spec，已测不受该问题影响。

2026-10-28 用户采纳方案 A：generic Vega 的 Arrow 数据路径复用内容命名的 `ArrowNamedDataSet`，spec 以 `data: {"name": <md5(IPC)>}` 引用，官方前端无需改动；B（inline values 留在 spec 内）与 C（暂缓）未采纳。落点：`elements/charts.rs` 的 `split_inline_values` 返回字段映射，`vega_lite_chart` 对提取出的 Arrow 数据按内容命名并加入 `datasets`、spec 以 data.name 引用（与同文件 `altair_chart` 同构），element hash 输入经含名称的 spec 随数据变化。保持用户 API、数据类型及 Arrow 传输；数据 hash 随 IPC 大小线性计算。

wire 规范化仅限此 generic Vega 的顶层 Arrow data 与单个 named dataset 之间的承载差别；内容名须匹配数据，逻辑 Arrow 字段/metadata/行序/值及 spec 其他字段仍严格校验。URL、调用方已有 data.name、嵌套 spec 与无数据调用不自动改写、行为不变。这是有意修正已观察到的 1.66.1 漏刷，不是声称与其错误像素一致；spec 变化会重建 Vega view，缩放/brush/selection/params 等图内交互状态可能重置，该项保持完整目标的未验收部分。验收按原计划执行：7 图初始语义保留（chartlibs 契约的 generic vega 预期更新为 named dataset 形态），真实按钮 3→8→普通 rerun→3 可见条值与实际 Arrow 一致（`tests/browser/rust-vega-refresh-after/`），同形状变化改变 dataset 名与元素身份；旧正确 Python 记录复用不重采。

## Download filename and MIME boundaries

本批补齐现有 `DownloadButtonOptions` 的响应头边界，不增加公共接口或依赖。一次锁定 Python 1.66.1 的真实公开调用/WS/HTTP 已收 10 个合成字节案例：默认/空文件名、ASCII、Unicode、引号、反斜杠、显式 charset、JSON 及未知 MIME。默认名为 `streamlit_download` 加原 MIME 对应后缀；Unicode 和特殊字符使用扩展 filename 参数。该参考不是浏览器保存对话框证据。

先用这些冻结输入通过 Rust 公共 download_button 发射 URL，再真实 GET 比较状态、内容类型、附件名和原字节，留红后修。`server.rs` 复用已有 typed ContentDisposition/FilenameExt 和原始 UTF-8 字节，不手拼未转义文件名；默认/空名回退、文本响应补 charset 只发生在响应头，不能反改 StoredFile MIME、内容地址或 URL 后缀。显式含 charset 的 MIME、未知 MIME 仍遵从原后缀映射，普通媒体、Range、首次写入语义不变。

已完成红→绿：默认下载原为只有 attachment 而无文件名；修后十条真实 WS/HTTP 精确比较通过，既有媒体/Range/重复下载不变。`buttons` 新增两控件经真实 Chrome 保存默认名及 Unicode 名，原字节一致；前端先 Fetch 后点击保存的顺序原样记录。[冻结参考](../tests/reference/reference-browser/download-boundaries/README.md)及[原生保存证据](../tests/browser/rust-download-boundaries/README.md)均仅绑定数据完整性，不绑定源码。该批是 M3 子集，其他符号/MIME、文本与文件对象自动推断和完整资源生命周期仍未验收；无新 API 或依赖。

拟改既有媒体运行测试、server 响应头、buttons 示例和指南，冻结新参考供后续回归；原 ASCII CSV/图片/音频与新默认/Unicode 的真实保存按受影响范围验收。只承诺实际测过的 10 种组合，标准扩展参数编码与 Python quote 在其他符号上的差别不隐藏，也不放宽这 10 项预期。字符串或文件对象的自动 MIME 推断、延迟 callable、其他 HTTP 边界仍不据此宣称完成。CSV 来源和 Vega 取舍与此无依赖，继续待决。

## Cache kind isolation

静态调用链显示 `cache_data` 与 `cache_resource` 以同一个 name + JSON 参数访问同一张 entries 表；resource 写入的 JSON 占位是 null。当同名同参数的数据结果类型能反序列化 null（如 `Option<i64>`），先 data→resource→data 可能返回 None，而非原有 Some(42)；其他类型可能重复计算或混用录制输出。先用现有公共调用复现，再一次性记录 Python 1.66.1 对同一函数双包装的公开行为；脚本实验与真实 WS 证据分别标注，不推定全量缓存兼容。

若复现和参考确认，两种缓存的现有 name/参数键分开存放，`cache_clear` 仍清当前会话的两种缓存，数据反序列化、共享 Arc、嵌套录制与调用点重放逻辑保持。拟改 `cache.rs` 内部存储及现有缓存运行回归、指南和证据映射；不加文件层抽象、依赖或公共接口，不改变已声明的会话作用域，也不在此引入 TTL/持久化/并发策略。使用说明先行，验收覆盖调用次序、合法 null、参数变化、清空、共享身份和输出重放；既有正确 Python 参考继续复用，最后独立只读 Review。

已按上述最小设计修复：原真实公开调用的 `Some(42)`→None 红断言转绿。Python 四组 bare-script 公开调用证明同函数双包装独立，真实 MemoryCacheStorageManager 告警原样保留，数据已冻结；Rust 复用初始四次调用和合法 null，另验证参数变化、两类清空和 Arc 身份。新两轮真实 Rust WS 证明各自的 computed=1/2 输出在原会话重放，后轮不重复计算、不带 miss transient，路径连续；不是 Python UI/wire 对照。缓存组六项和新五项离线检查通过，独立 Review 无阻塞；跨会话/全局/TTL/分类别清空仍未据此完成。

## Media Range boundary correction

原 `ByteRange::parse` 只接受 bytes=a-b/a-；后缀、非法、越界、多范围均回退为整文件 200。新一次公开 download_button/video 的真实 WS→HTTP 参考包含 23 请求，证明后缀等为 206，非法/越界/多范围及空文件上的非空 Range 为 416、正文 `Invalid range` 与 `Content-Range: bytes */N`。仅另补四个此前未测数字语法/空 header 请求，原 23 条不重采；无连字符、下划线、超 u64 的 end 均有实际响应依据。不存在 multipart 设计选择，目标 1.66.1 实际拒绝多范围。

先补使用说明，再让真实 Rust 公共调用发射同一内容地址，以原 Range 字符串逐个 GET 留红。修复范围仅 `media.rs` 的既有解析器、`server.rs` 的 416 分支、现有媒体运行回归与冻结证据/指南/矩阵：保留公开 `Option<ByteRange>` 签名，不增接口或依赖。数字语法保留已测的空白、大小写、可选加号/下划线；用校验十进制字符后饱和累积避免固定整数溢出导致合法后缀/end 被误拒，最终范围始终受文件长度约束。非空但无效 Range 提前返回精确 416，不带成功下载的附件/Accept-Ranges；空 header 与无 header 保持整文件响应。

验收按冻结 27 请求精确对照状态、Content-Range/Length/Type、附件/Accept-Ranges 有无及原字节；解析器同时读取相同参考，覆盖 0 长度和超 u64 数字。保留已有普通媒体、200/206/404、下载文件名与重复读取回归，不改旧正确 raw 或标准。新参考是协议/HTTP，不能冒称浏览器定位动作已测；HTTP HEAD、If-Range/CORS、全部数字字符或超长 header 与完整生命周期不在本批已测范围，长期媒体目标不因此关闭。

已完成真实红→绿：`bytes=-5` 原为 200，而目标为 206；修后全部 27 个请求逐字匹配，11 项媒体相关 Rust 检查及五项新离线检查通过。首次夹具误用未声明 base64 crate 的编译失败另存，纠正为从原 HTTP 提取受核验字节数组后才构成产品红复现，无新依赖。旧 suffix=未知时返回 None 的内部断言已按新公开参考改为有效后缀区间，不更改旧 Python raw；原有效 200/206/404、重复下载和文件名边界继续检查。

## Zero-column display — accepted A (virtual RangeIndex)

在修复 no-op 克隆 panic 后，真实 Python 1.66.1 新参考证明 Arrow 零列 0/2 行及 pandas index-only 输入可由 dataframe、固定编辑器（enabled/disabled）和 table(hide_index=False) 接受；首次主组 9 场景、独立 table 补充 3 场景，各自一个成功运行，原 caller 输入不变。物理字段为空，行数与 RangeIndex 分开保存。官方目录此次仍显示 1.66.0 标签，运行基线仍锁定 1.66.1；功能范围来自官方 data_editor/dataframe 文档，具体空形状语义来自本次实测，不能由 wheel 符号或实现推定。

首次独立 UI 恢复流程又证明：直接 Arrow 两行零列的 dataframe 出现两个 `Error during cell creation`，table 只剩空框；两个 editor 显示 0/1，普通 rerun 保持这些表现，恢复零行后回到 empty。无 stException 不等于显示正确。原 9＋3 公开调用和四阶段 UI 已分别冻结，第一次 collector 返回值错误的失败前缀也保留。已交付候选为一个协议/UI 双模式参考 app、两个复用现有工具的采集器、原始输入/PB/IPC/DOM/PNG/日志及四项离线检查；数据 manifest 不绑定源码，原 PID、端口和 profile 另作只读清理核验。

2026-10-28 用户采纳方案 A：保留真实行数，提供虚拟 RangeIndex，让零列 dataframe/table 显示 0/1，编辑器沿实测正常行为完成；B（严格保留直接 Arrow 的格错误/空框）与 C（暂缓）未采纳。落点：`chart_arrow_data` 与 `with_range_index` 重建 batch 时显式携带行数（`RecordBatch::try_new` 在零列时要求 row count，此前在显示路径返回 Arrow 错误），合成的 pandas 元数据本就含 range 索引描述符，故零列 wire 与编辑器同构、官方前端可创建格子。无实体索引列、新接口、依赖或官方前端修改；这是对直接 Arrow 上游错误/空框的明确修正，不冒称逐字段等价或任意索引均支持，原错误参考仍保留。默认隐藏索引的 table 没有可见列，保持空框呈现。新增 `zero_columns` 示例与 Rust 0→2→重跑→0 真实前端对照；有列路径行为不变，Rust 无编辑返回保留原 batch。动态行编辑、任意 schema/metadata 组合继续未完成，M3/Goal 不因此自动关闭。

## Native input arithmetic and no-op editor ownership

原 RGBA 校验直接相乘 usize，超出可表示字节数的尺寸在 debug 的公开 st.image 调用中已真实复现 panic；release 算术可能绕回零。微小缓冲公共调用留红后，valid 改为 checked_mul，只有尺寸为正、长度可表示且等于现有缓冲时通过。既有无效 image 的日志/跳过行为和有效 PNG 编码保持，不增加产品大小阈值；底层 png_encode 的有效输入前提与签名不改。

data_editor 原无编辑分支用 Schema::new 和 try_new 重建已有效 RecordBatch，丢弃顶层 metadata，合法零列 batch 则触发 expect panic，两项均已由公共 disabled 编辑器调用留红。删除只用于无编辑的 clone_batch 重建辅助，直接返回 data.clone()，保留不可变 Arrow 缓冲共享、schema metadata 和显式 row count，无新依赖、公开接口或编辑规则。实际编辑后 schema/index 策略不在本批变更；chart_arrow_data 对零列的后续错误也不冒称已支持其前端呈现。

修改仅现有 media.rs 的校验及其单元模块、data_api.rs 的无编辑分支、既有 dataeditor 运行回归、指南与两项矩阵证据。有效 1×1 图片、无效长度/尺寸不占元素位置以及无编辑 metadata/显式行数的定向回归已转绿；公开 0/2 行零列输入现在都由后续显示转换返回 Arrow 错误，不再 panic，底层无编辑返回严格等于原 batch。矩阵仅补 Rust 原生边界证据、保留 partial，并清除图片条目过时源码指纹/行号说明，不改分母、历史数据完整性或接受标准。完整检查及独立 Review 后交付，M3/长期 Goal 不关闭。

## WebSocket diagnostic payloads

原 handler 的 Info 级 ForwardMsg/BackMsg Debug 展开、Debug 级原始 Message、文本及关闭原因日志会输出应用载荷；大字符串/Arrow 还会放大格式化和写出成本。宏只使用 env_logger 默认环境配置，不把这个缺陷描述成默认已开启 Info。真实红探针在完成 wire、错误后心跳、关闭应答和服务清理后，仅因五类合成标记全部进入日志而失败。

在既有 M5 可观测性范围内，先写使用说明并用合成数据真实复现，再只改 websocket/handler.rs 的日志：输出种类标记/序号、帧长度、汇总数量/字节、运行耗时与错误原因，移除输入/输出内容展开、任意文本及关闭描述。未知 BackMsg 仍保留现有错误处理，只记录其种类；不改协议行为、关闭原应答、过滤级别、宏公共支撑、接口或依赖。ForwardMsg 仍只编码一次，原 payload 交给 binary；计时从已取得运行锁后的本轮开始，到执行与发送调度完成，不是端到端延迟。不是新遥测框架、认证策略或全局脱敏保证。

新增 tests/runtime/logging.rs 并接入既有 mod.rs，复用 WS 工具；通过精确 test 名称启动独立自有 test 子进程，在子进程内初始化捕获 logger。用真实控件输入、较大输出、未支持请求、文本帧、关闭原因各自的合成标记验证原样 wire 与无载荷日志；非法 protobuf 后仍能 heartbeat，错误诊断不被整体禁用。子进程捕获的成功/失败结果在自有服务停止后报告，原失败日志只含合成数据，保留在 target/checks/m5-ws-logging/。同一 Debug 配置下，日志从 131,289 降为 3,704 字节、标记从 5 降为 0；小型记录存入 tests/performance/ws-logging.json，重复的大载荷原日志不复制进 Git。该结果不是吞吐/CPU 或完整安全测量，冻结 Python 不重采；最终相关回归和独立 Review 后交付。

## Media response storage

原 `StoredFile` 持有 `Vec<u8>`，`stored_file` 每次克隆整个文件；206 分支随后再对片段执行 `to_vec`。同一大文件的待发送响应按请求数重复持有整文件，小范围请求也会先复制全文件。优化前产品代码配合同一新增回归已实测：16 个 8 MiB 完整响应持有 16 份独立缓冲。

在既有 M5 范围内先写使用说明并测量，再将 private 字节存储换成已有依赖的 `Bytes`，注册时 `copy_from_slice` 保持输入所有权隔离，快照克隆和范围 `slice` 共享不可变存储。公开 `get -> Option<Vec<u8>>` 在返回时复制，公开签名、内容地址、首次注册元数据及 HTTP 行为保持。没有新依赖、公共接口、限额、淘汰或会话归属规则；进程全局媒体存储的生命周期问题继续留在长期目标。

修改仅 media.rs 的 private 存储/既有 get、server.rs 的范围响应与既有媒体运行回归，指南、测量脚本及数据同步。用同一 8 MiB 合成文件保留 16 个完整及 16 个 64 KiB 范围响应，优化前三次构造耗时为 70,653/74,323/81,656 μs，优化后为 5,737/3,195/3,321 μs；完整响应独立缓冲降为一份，操作系统峰值工作集约从 163 MiB 降为 35 MiB。[原始数据和方法](../tests/performance/media-storage.json)是 debug 进程内路由响应构造测量，不代表网络吞吐/慢客户端容量或性能门槛。回归校验每个响应内容、头与丢弃部分响应后的剩余有效性，并复用冻结 27 个范围和 10 个下载案例及真实 HTTP/WS 测试，不重采 Python；公开注册和读取的输入隔离另有单元回归。不以局部性能结果关闭 M5。

## Library build portability

M6 新实测在隔离 workspace 中将库目录改名为 renamed-library、保留宏和锁文件但不放置外部 www，`cargo check --offline --locked -p streamlit --lib` 真实失败：protoc 找不到固定的 `streamlit/proto/Alert.proto`。源码另有 `include_str!("../../www/index.html")`，Cargo 包清单不含该外部文件；当前启动校验需要的版本身份因此也依赖仓库相邻目录。不是新依赖或客户端环境故障。

修复维持既有“启动时完整官方 frontend sidecar、编译时只含小版本身份”的设计：build.rs 用已实测可用的 protoc 虚拟目录映射，将官方 streamlit/proto 前缀指向当前 crate 的 proto 目录，协议原文件/导入名保持逐字不变；将启动校验原先已编译进程序的官方 index 原字节放入 `streamlit/assets/frontend-index.html`，服务端只调整 include 路径。完整 347 文件前端仍按既有 sidecar/显式目录规则运行，不改公共 API、依赖或启动优先级。

已通过改名/no-www 库检查及含空格目录的现有 quickstart release 构建；实际安装程序从独立工作目录完成复选框重跑。源/安装/交互后三次 347 文件对照均通过，60 个 HTTP 响应、24 PB、两阶段 DOM/截图归档在[安装证据](../tests/browser/rust-library-portability/README.md)。默认 UI 进程日志为空，另一次启动的 info 日志才确认 sidecar，两个 PID 分开记录。独立 consumer 发现的公共宏支撑缺陷另见下节，未用增加依赖绕过；M6 不因此关闭。

拟改 build.rs、server.rs 的单个 include、上述 private 数据文件与字节属性，以及现有使用指南/验收记录。先写独立应用完整 Cargo.toml/入口、工具链与 sidecar 用法，再实现。验收使用无外部 www 且库目录改名的隔离源码和已有固定缓存编译，另构建仓库外应用、从无仓库工作目录启动，核对真实首页/boot资源/WS及交互、完整 sidecar 字节；已有协议/静态/宏与库回归保持。缓存依赖的 Windows 实验不冒称无缓存机器、MSRV、全部平台或 crates.io 发布已通过；源码包的完整维护者测试/外部 fixtures 仍需另核实，M6 不因本批构建可用而关闭。

## Local crate archive verification

M6 继续核实真实源码包而非仅文件清单。当前 Cargo 1.98.1 的 `cargo package --workspace --offline --locked` 实际生成并验证两个 0.1.1 crate：宏包 6 文件、库包 223 文件；Cargo 用 target 下临时本地 registry 连接同 workspace 的未发布依赖，没有发布或外部写入。库包已含私有 index，版本/proto 数据与仓库输入相同，目录版本后缀不再阻断库编译。

独立 consumer 的 library target 已从实际 tarball 提取的两个包通过检查；局部 path/patch 仅连接本地宏包，第三方 270 个包的版本/校验与既有锁文件一致，没有调用未采纳的启动宏。该检查不能替代单依赖宏应用或真实运行验证。

继续实测揭示两种包内缺口：维护者 lib test 编译产生 31 个包外 include 缺失；普通 examples 检查则因 chartlibs 的三个配置与 video 的样本共四个包外文件失败。先为普通示例补使用说明，然后将这四份小型配置/媒体输入作为 `streamlit/examples/data/` 私有示例资源提供，两个示例只调整 include 路径；参考数据原位置保留，配置/视频内容不变，无新依赖或公共接口。JSON 沿用原普通文本换行规则，MP4 保持原字节。

重新执行真实 workspace package verify、从最终 tarball 提取检查全部 examples、普通 SDK consumer，以及现有代码/协议回归；私有示例资源逐项与旧输入核对。维护者测试的仓库级 fixtures 布局不在此偷改，不添加关闭测试的 cfg 或捆绑全部旧参考；对应失败和完整维护者源码分发边界继续明确保留，M6 不关闭。

### Maintainer source distribution — decision pending

最终库包的 lib test 仍实际编译失败，31 个缺失均指向仓库级参考/fixture；这不是普通 SDK consumer 或已修复的示例失败。分发形态与维护者测试归属需要确认，不在本批关闭测试或改写通过标准。

| 方案 | 交付及取舍 |
| --- | --- |
| PKG-A，推荐 | 分开定义两种交付：SDK crate 保证库和包内示例可构建；完整仓库源码交付承载全部维护者测试。原全部断言保留，完整源码仍必须通过现有全量回归；SDK crate 的独立维护者测试限制继续明示。维护者需要完整源码目录，不能只下载单个 crate 运行这套回归。 |
| PKG-B | 重组测试资源布局，使单个 SDK crate 的维护者测试也自足。完整保留原断言，迁移必要 fixture/前端测试输入并调整消费路径，增加包体积和迁移/复验范围；实施前收敛具体依赖集合与文件计划，不把所有历史资料直接捆入。 |
| PKG-C | 暂缓源码分发策略，只保留当前库/示例已验证的实验包及明确失败，不关闭 M6；继续其他独立能力。 |

该选择独立于上游/现有接口行为和下节宏方案。推荐不等于采纳；当前只交付已证实的私有示例资源修复及本地包验证，测试布局没有改动。

## Consumer macro support — decision pending

修正隔离应用示例漏写 async 后，仅依赖 streamlit 的真实调用仍不能编译：宏当前直接展开 `#[tokio::main]` 与 `env_logger::Builder`，但二者不是调用方直接依赖。库内部已有这两种依赖，不能据此认为外部 crate 也能按这些名字解析。失败记录为 `target/checks/m6-library-portability/consumer-macro-red.log`，不以仓库自身示例通过冒充独立应用通过。

| 方案 | 改动、收益与代价 |
| --- | --- |
| A，推荐 | 库提供 doc-hidden 的公共宏支撑命名空间，重导出现有运行时/日志依赖；宏全部使用该限定路径，可显式建立同样的 Tokio 运行时。调用方只直接依赖 streamlit。新增的公共符号限宏支撑用途，无新依赖包；要维护库与宏的支撑契约，需用户采纳后实施。 |
| B | 新增用户可见的同步服务启动方法，由库管理 Tokio/日志，宏调用该方法。也支持手工服务入口，接口更正式；新增公共方法与启动职责更广，需设计返回错误、调用限制和日志归属。 |
| C | 保留现有宏展开方式，独立应用 Cargo.toml 明确加入现有固定 Tokio 与 env_logger。库公共面不变、实现成本低；调用方需了解并维护运行时/日志直接依赖，最小应用仍需三个依赖。 |

A 拟改 lib.rs 的支撑导出、streamlit-macros/src/lib.rs 的限定调用、既有宏检查和独立应用指南。验收只直接依赖 streamlit 的外部项目、host/port、实际启动/WS/页面交互、现有示例和全部静态资源边界，无源码 SHA 门槛。B/C 仅在采纳后展开相应设计。选择前不新增公共支撑接口，也不将三依赖绕行冒称单依赖已成功；当前仅继续独立的库目录修复及现有示例分发验证。

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
