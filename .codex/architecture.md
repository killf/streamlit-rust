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

## Query-bound widget tracking — current implementation

查询绑定复用现有 `WidgetRegistry::Record` 生命周期，不另建第二套控件登记：text_input/selectbox 注册后更新内部绑定标记，参数名沿用显式 widget key。公共查询参数 set/remove 依据登记拒绝手动写入；clear 只在 URL 中实际存在绑定参数时拒绝。参数名大小写敏感，保留嵌入键不能用作绑定目标。

同身份取消绑定时移除对应 URL；条件隐藏则保留保护到 `finish_widgets`。结束清理先计算仍存活的绑定，避免旧身份清理同名新控件，再释放控件/值锁后移除失效参数。查询存储仅保留待发送标记，注册边界或 WS 结束路径汇总发一次 `page_info_changed`，位于结束帧之前。普通手工写入仍立即发送。没有新增公共接口或依赖。

四轮真实原生 WS 参考保留于 `tests/reference/reference-browser/queryparams/binding/trace.json`，Rust 比较 18 份 JSON 与 5 次 URL 的完整顺序；活跃轮同时提供 URL 和 widget states。内部单元另验证显式取消绑定。仅 URL 初始化、重挂载/跨页恢复、动态绑定组合、表单/缓存交互和真实浏览器同步继续开放，不能据此关闭完整绑定能力。

后续 URL 初始化切片将可选策略放入现有内部 `WidgetSpec`（clearable/disabled），只有已支持绑定的 text_input/selectbox 启用，其余登记显式为 None；公共 API 与依赖不变。查询存储保留用户代码执行前的 URL 快照，历史导航标志随 ClientState 输入；服务端自发重跑刷新快照并撤销历史标志。注册时结合本轮前端输入、代码写入和旧记录决定是否采用 URL，校正无效/默认参数，复用已有发送边界发 URL。程序赋值与默认折叠同步查询存储，结果同时驱动返回值与前端 set_value。

八轮固定原生 WS 参考 `queryparams/seed/trace.json` 已覆盖 URL-only 初值、前端/代码优先级及历史导航存在/缺失参数，连同控件同步标志逐项比较；此前四轮捕获本身仍不证明这些能力。禁用控件与伪造输入组合、callback、绑定控件的服务端重跑、重挂载/跨页及浏览器操作继续开放。

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

### Maintainer source distribution — accepted PKG-A

2026-10-28 用户采纳 PKG-A：分开定义两种交付——SDK crate 只保证库和包内示例可构建（`cargo package` 的库/宏编译验证与示例构建即包形态验收）；完整仓库源码交付承载全部维护者测试，原全部断言保留，完整源码仍必须通过现有全量回归。此前实测的 31 项包内 lib test 缺失（均指向仓库级参考/fixture，冻结日志 `archive-maintainer-tests-after.log`）重新定性为该交付边界的记录而非缺陷：维护者需要完整源码目录运行这套回归，SDK crate 的独立维护者测试限制在指南与包验证 README 中明示。PKG-B（重组测试资源使单包自足，包体积与迁移代价）与 PKG-C（暂缓）未采纳；测试布局与断言未改动，不添加关闭测试的 cfg 或捆绑旧参考。

## Consumer macro support — accepted A (doc-hidden support namespace)

2026-10-28 用户采纳方案 A：库在 lib.rs 提供 `#[doc(hidden)] pub mod __macro`，重导出现有 tokio 与 env_logger 依赖；`#[streamlit::main]` 全部改用 `::streamlit::__macro::…` 限定路径建立同样的 Tokio 运行时与日志初始化。调用方只直接依赖 streamlit 一个包，无新依赖包；新增公共符号仅限宏支撑用途并 doc-hidden，库与宏的支撑契约随两 crate 同仓库同步维护。B（用户可见的同步启动方法）与 C（调用方自备 tokio/env_logger 依赖）未采纳；此前的独立应用红记录（`consumer-macro-red.log` 的 E0433×2 + E0752）保留为修复前证据，复验以改名库目录、含空格路径、单依赖外部应用的真实编译/启动/WS/页面交互为准，不以仓库自身示例通过冒充独立应用通过。

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

### Disabled input and callback compatibility slice

2026-10-30 用户选择保留 Python 错误、已执行 callback 和后续恢复。两份不可覆盖的 1.66.1 原生 WS 记录位于 `tests/reference/reference-browser/queryparams/disabled-valid/trace.json` 与 `disabled/trace.json`，各九轮。前者 58 个交错事件（44 个控件同步投影、9 份状态、5 次 URL）；后者 52 个（40 个投影、8 份状态、3 次 URL、1 个 TypeError）。错误轮只有 Plain 发出后 selectbox 报错，同批 Live callback 已发生，下一轮仍能回调并恢复。

WidgetSpec/Record 内部保存 disabled，callback 按上一轮元数据处理，当前禁用注册恢复输入前值；代码赋值和 URL 优先级保留。已测 bool oneof 提交给禁用普通 selectbox 时延迟到注册呈现 TypeError，并保留未渲染控件，避免错误轮清理破坏下一轮恢复。无新增公共接口或依赖。错误比较覆盖类型、消息、出现位置与标志；Python 来源栈帧单独保留，Rust 不伪造。其他错误类型/控件、跨页、绑定服务端重跑和真实浏览器错误界面继续开放，M3/M5/M7 未关闭。


### Bound controls across server-started reruns

2026-10-30 `queryparams/rerun/trace.json` 以五次原生 WS 客户端请求产生十轮执行，固定 47 个 URL/控件同步/JSON/finish 事件。新前端请求才调用 begin_widgets，内部重跑用 continue_widgets 延续 received、pending 和本交互代码赋值，且不再次安排 callback；记录和绑定在 rerun 边界不作为 stale 删除，正常结束仍清理。代码赋值的同步标记保留到交互正常结束，不在首次注册时提前移除。内部 URL 从最近收到/公布的 query string 重建，区别于 store 中未广播的默认值折叠；history 标志在内部重跑复位。

用户确认发送流程方案 1：发送任务遇到已触发 rerun 的旧轮 Delta 时丢弃仍在队列中的消息，已经发送的帧与 PageInfoChanged 保留；继续流式发送，不整轮缓存。旧自写同步 prefix 断言按新原始参考纠正，不改冻结参考；另外用真实 WS + executor yield 验证已发送 prefix 保留、随后排队 Delta 丢弃。旧浏览器记录保留其实际调度窗口，不因本批协议对照宣称当前 UI 全部通过。callback 内 rerun、fragment、跨页和其他发送时序仍开放。


### Additional queue evidence awaiting policy decision

新增三份独立原始记录，旧参考未改：`queryparams/navigation-rerun/trace.json` 使用既有 navigation_app（两请求三轮），显示旧轮未发送 Navigation 也被清理；`rerun-messages/trace.json` 保留冷调用中已经发出的 PageConfig/普通 Delta 前缀，不能用于断言所有前缀必然丢弃；`rerun-queue/trace.json` 先预热，再验证未发送 PageConfig、Markdown、balloons 被清理，但 toast、PageInfoChanged 和结束帧保留。三份均逐帧解码通过，生产发送流程仍仅实现已确认的 Delta-only 方案，因此尚有已知 Navigation/toast/config 差异，不能报告本批完整通过。

待用户决定的推荐扩展只改 `streamlit/src/websocket/handler.rs` 队列保留判断：保留 NewSession、ScriptFinished、SessionStatusChanged、ParentMessage、PageInfoChanged，以及 NewElement Toast；其他未发送消息在完整 rerun 时清理。此保留表与锁定版本 forward_msg_queue.py 的生命周期清理规则一致。已发送帧和继续流式发送保持已确认行为，fragment 不在此完整 rerun 规则的验证范围。将以新原始记录、已发送帧回归、全目标 Clippy、控件单元、查询/执行/导航集成及工作区回归验证。AGENTS.md 第 2 条要求流程取舍由用户决定，已提出三个有区别的选项，尚未收到本次扩展答复；不把此前 Delta-only 选择当作扩大消息类型的授权。


### Independent string avatar and JSON serialization slice

2026-10-30 队列扩展决策仍待回复，独立处理聊天头像现有字符串接口。`chat-metric-params/string-avatars/trace.json` 固定 28 组输入、57 个输出投影，修复默认 name 的预设大小写与 human/ai 别名、普通名字空 avatar、emoji 名字 EMOJI、六组图片 URI 的 IMAGE 分类；URI 原样透传，不请求图片。复用既有 emojis 依赖，无新增公共接口或文件加载流程。完整本地图片/异常/emoji catalogue/宽度与浏览器行为仍开放。

同一 WS 输入报告揭示 pywire 非 BMP 字符被错误输出为五位 \u 转义，现改用 char.encode_utf16 逐码元生成 JSON 转义，覆盖普通/compact/pairs 的键和值及 U+10000/U+10FFFF 边界。还按固定报告和官方文档把 st.json 默认 expanded 改为 true，显式 json_expanded(false) 保留。旧 JSON 说明的“depth 参数不存在”只针对 depth= 关键字，不能排除 expanded=int 支持；已校正文案，Rust 整数展开深度仍是未完成能力。队列保留规则未在本批扩展，两个已知队列差异继续留存。


### JSON string passthrough and evidence binding

2026-10-30 独立 `json-badge-params/strings/trace.json` 固定 15 个字符串的展开/折叠输出与五种结构化对照，加输入报告共 36 个 JSON 元素。锁定 runtime 原样保留顶层字符串，包括空串、实际空白/换行、Unicode、错误文本与多文档文本，不在服务端补引号或校验。Rust 既有 json_expanded 在 serde Value::String 分支直接传递，其他值继续 py_dumps；json 复用 json_expanded(body, true)，无新增接口、依赖或格式化流程。公共调用单元覆盖 &str/String/Value::String 与嵌套对象；真实 WS 比较完整 Json 载荷、路径和 stretch 标志。前端解析错误 UI、整数展开深度与自定义序列化失败仍开放。

同时修复参考证据门的真实缺口：test_json_badge_params_reference 原先虽然定义了 protobuf 解码生成器，主比较却只读取未绑定摘要；现在原 Python/Rust 与新字符串参考都逐帧验证 base64/长度/方向/解码消息，并核对元素摘要与 finish。七项损坏输入 guard 与原正确参考并存；没有修改旧行为期望或添加源 SHA 门。README 对 collapsed default 与 depth= 的旧表述已明确校正，不改原始帧。


### Real Chrome JSON string UI evidence

2026-10-30 复用 JSON 示例/参考 fixture，新增可选 sample=0..14 的单例场景与 collapsed=true 初始折叠；无 sample 的 36 元素场景及默认六元素场景保留。Rust 示例的完整 36 元素原生 WS 预检通过后，使用 Browser Use 的实际 Chrome 标签页读取 DOM/HTML、截图并真实点击根展开箭头。每端 22 个状态（15 显示＋两个三阶段折叠往返＋Unicode 复核）的主文本、警告、JSON 文本/图标/键/行数全部一致。数据和九张 JPEG/端分别留在 json-badge-params/ui，不伪装成 headless/native WS 浏览器证据。

console buffer 各有八条同文 react-json-view scalar 错误日志，属于实际保留观察；不得报告零 console 错误或精确归因到每个导航窗口。Python 在已完成观察并关闭标签页后的 Ctrl-C 阶段出现 Windows Proactor ConnectionResetError，单独记录为关闭过程现象；两服务 session 均终止且本轮端口无监听。离线门验证阶段/URL/可见内容/图片字节与差分，七项损坏 guard 失败；门本身不启动浏览器。整数深度、嵌套/宽度/主题等仍开放，发送规则未越过待决选择。


### Pending JSON depth/width public interface decision

固定参考 `json-badge-params/expansion/trace.json` 包含 18 组参数、9 成功/9 拒绝（28 个 JSON 元素含输入/结果报告）。bool False 的 expanded 缺省且无 max_expand_depth；int 0 的 expanded=true 且 max_expand_depth=0，不能合并两种状态。1/2/3、-1 和 int32 最大值都按整数原样发出；超 int32、float/string expanded 拒绝。宽度 stretch 和正像素成功，0/负数/content/其他字符串/float/None 拒绝；上游 bool True 宽度被编码成 1 像素。异常报告仅证明捕获的服务器行为，不证明完整错误 UI。

2026-10-30 已请求用户从三种公共接口方案选择，尚未收到此项答复；未增加以下公共代码：

1. 推荐新增 `JsonOptions<T>` 与 `json_options(options) -> Result<(), WidgetError>`，保留现有 json/json_expanded 签名。示例：`st.json_options(JsonOptions::new(body).expanded(2).width(ElementWidth::Value(240)))?`。新增 `JsonExpansion::{Expanded, Collapsed, Depth(i32)}`，From<bool>/From<i32> 供 builder 接收布尔和深度；一字段表达互斥状态。默认 Expanded/Stretch，整数沿用捕获的 int32 语义（含 -1），宽度只允许 Stretch 或正 Value，Content/非正值返回既有 InvalidValue，复用现有错误与宽度类型。
2. 新增 `json_with(body, expansion, width)` 三参数方法与扩展状态枚举，保留旧方法，不引入 Options builder；调用短，但可选参数后续扩展需调整参数列表。
3. 先泛化 json_expanded 第二参数为 bool/深度枚举，保留旧布尔调用；宽度入口后续再决定。此方案只分阶段实现，不缩小长期范围。

方案 1 的拟改文件为 api.rs（类型/方法/兼容入口）、elements/text.rs（已有 JsonElement 的深度与宽度字段）以及既有 JSON 示例/单元/WS/参考/浏览器证据和说明。验证需覆盖原 bool/字符串 API 不回归、9 种已测成功配置和 Rust 可表达的无效宽度、None 与 Some(0) 的字段差异、深度/宽度真实前端展示；Rust 静态类型不能传入的 float/string expanded 不伪造为已测运行时异常。序列化失败等既有缺口继续单列，不因该接口选择自动关闭。没有新文件/依赖或生产发布计划。

### Logo automatic emoji-sequence typing slice

`code-logo-params/logo-strings/trace.json` 固定 18 个双图 Logo：12 个普通/VS/ZWJ/家庭/国旗/keycap/肤色序列、两个 Material 图标和四个 URL/data/static URI，轮换 small/medium/large 及 link。修前 9/18 完整载荷不同，原因是自动 From<&str> 用非 ASCII 且字符数<=2 的启发式；改为复用已锁定 emojis::get，From<String> 仍复用该转换。主图与 icon_image 的全部六字段和 Logo 元数据形态通过真实 WS 对照，无新增公共接口或依赖。无效图片/Material 字符串、本地/bytes 加载、完整 emoji catalogue、侧栏显示与链接操作等继续开放。


### JSON numeric encoding and remaining nonfinite data loss

2026-10-30 同一 JSON fixture/example/collector 增加 numbers 场景：19 个 f64 文本输入分别调用 st.json(value) 与 st.json([value])，连输入报告共 39 个输出。旧 Rust 的八组有限值在指数正号、两位补零和 1e-5 记法上不同；pywire 现有数字写入统一处理普通/compact/pairs 路径，整数保持原样，无新公共接口或依赖。固定原始参考与修复前、后记录分别保留；16 个有限值的 33 个报告/输出载荷已匹配。

三组非有限值（NaN、Infinity、-Infinity）在 Python JSON body 中原样发出，Rust 的 serde_json::to_value 在 pywire 之前已把它们变成 null，现有 Value 编码无法还原。两种调用形态的六个差异继续记录为未完成。处理需要在转 Value 前保留浮点信息的内部序列化设计；不得使用特殊字符串哨兵或把 null 当作兼容结果。该设计与已待决的 JsonOptions 深度/宽度接口相互独立，当前未擅自引入自定义 Serializer、类型模型或依赖。自定义序列化失败、任意精度/舍入与更广数值/浏览器组合仍开放。


### Pending lossless JSON serialization flow decision (2026-10-30)

原生证据已扩展：Python serialization/trace.json 有 17 组输入、13 成功/4 捕获异常、5 条 warning，共 37 个元素。None/bool/float/非有限映射键转为文本，规范化后相同的键仍按原始顺序重复保留，不能经普通字符串键 Map 合并。tuple/complex 键先 warning 再递归 skipkeys；自定义 repr 的 TypeError 导致 warning 和第二次调用，ValueError 不重试；循环引用为 ValueError，调用方捕获后可恢复。sets、bytes 和稳定自定义 repr 只证明这一组 Python 输入，不宣称一般集合顺序或 Rust 类型映射。

Rust serialization-before/trace.json 是另一组原生诊断，不是同输入跨语言比较：BTreeMap<Option<i32>, &str> 中 None 键和必然返回错误的自定义 Serialize 均没有输出，也没有 alert/exception；前后四个 JSON 标记和输入报告全部出现，finish=0。这证明当前 API 静默丢弃错误输出并继续；不把五元素诊断当作兼容通过。生产流程未在此批修改。

已提交用户选择（AGENTS.md 第 2 条的流程取舍），尚待回复：

1. 推荐在既有 pywire.rs 中实现内部 Serde 文本序列化器，在 api.rs 的 JSON 路径调用；直接生成文本并复用 ASCII 字符串与有限数字写入，保留 f64 非有限值、整数、映射原始次序/重复文本键，避免先转 serde_json::Value 的损失。无新文件、依赖或公共接口。不能以字符串哨兵编码 NaN。
2. 在相同文件中使用内部值树，保存浮点、映射原始键和序列，再生成 Python 风格文本；阶段与调试直观，但多一层类型与分配，映射必须使用条目序列保留重复键。
3. 暂缓内部流程，继续其他兼容项；这些差异仍属未完成，不接受为长期兼容限制。

此选择只决定保留可表达输入的内部流程，不自动改变自定义 Serialize 失败的公共传播策略，也不自动实现 Python 专用类型 repr、循环检测或 invalid-key fallback。新参考明确这些仍需处理，不缩减完整目标。此前 JsonOptions 返回 Result 的公共接口以及发送队列保留表仍分别待决。预计修改 pywire.rs/api.rs、既有 JSON 示例与单元/生产 WS/证据门；验证先代码、单元、集成，再检查字符串原样传递、16 个有限值、三种非有限值、嵌套与映射顺序/重复键。Rust 无法表达的 Python 类型不伪造通过。


### Independent existing code element correction

2026-10-30 在三个待决流程之外核对既有 st.code/CodeOptions：Python 只各去掉一次边界 LF，空语言改为 plaintext；Rust 原实现两处均不同。27 场景原始参考与修前/修后记录保留，修正只在 elements/code.rs 的构造中直接调整现有 String 和空语言；没有公共签名/依赖变化，不复用 markdown 的 dedent/strip。宽高/开关既有映射在九种有效组合保持原样，None 语言用 Rust 空字符串表达已有纯文本效果。完整元素/路径/尺寸的生产 WS 差分和八项一致原始帧语义 guard 通过；无效尺寸、非字符串转换、语法高亮和浏览器布局继续待验。


### Code height participates in frontend element identity

2026-10-30 实际 Chrome 控件操作复现：Rust 状态 caption 已为 240，但代码区域仍为 120；Python 同操作立即为 240。新三请求原生 WS 参考证明两边高度载荷均为 120→240→120，Rust 修前三个 hash 相同、Python 为 A→B→A。虽然 delta_base_with_path 仍设置 cacheable=false，捆绑前端 www/static/js/index.Dlja0TUX.js 的 applyDelta 在 function to(e,t,n) 判断 e.elementHash===t 时选择旧 s.element，而不是新 o。该树复用与消息缓存标记独立，故完整帧仍会保留旧高度。

最小修复只把 self.height 加入 code.rs 的既有 hash 输入，不启用缓存、不改变发送流程、公共接口或依赖。单元和真实同连接 WS 验证高度往返的内容身份关系；修后实际浏览器十个控件状态与 Python 几何/文本/高亮/行号/自动换行一致，真实内层滚动可移动并恢复到顶。保存 Python 13 与 Rust 14 个观察及修前三个失败截图，保留滚动动画的中间值，不伪造逐帧偏移一致。特殊语言、其他宽高/主题/响应式、clipboard、非字符串和无效尺寸继续开放；此前三个待决流程不变。


### Unambiguous code identity field boundaries

2026-10-30 后续实际复现正文 left_right / language python 与正文 left / language right_python 的手工下划线拼接相同。Python 原始三轮为 A/B/A，Rust 修前三轮为 A/A/A；真实 Chrome 勾选 Alternate code 后 caption 已显示新正文，但代码区仍显示 left_right 和旧语言，证明高度字段补齐不等于字段编码已无歧义。

只在 code.rs 的既有 hash 调用中把七个现有字段放入 Debug 元组，保留字符串边界与转义、类型/字段顺序、height 和原 MD5 算法；没有新模块、公共接口、依赖或缓存流程。单元反例含下划线、引号、Unicode；同连接生产 WS 与三阶段真实 Chrome 均验证正文/语言切换与恢复，原始载荷保持原样。没有据此推断其他元素的手工 hash 完整或宣称任意语言标签都有语法高亮。九张正确/失败 JPEG 和原始帧保留，首次截图超时只重取同页截图，未重放控件操作。


### Pending unified NewElement identity decision (2026-10-30)

现状已超出代码元素：`text-misc-params/identity/trace.json` 固定三次请求、24 元素，五个目标的载荷变化均为 A→B→A 身份；Rust `identity-before/trace.json` 的元素内部业务字段投影匹配，但五个 hash 全为 A/A/A。完整 Element 另有八个未完成的布局字段差异（Markdown 默认 width 存在性、badge text_alignment_config），原始帧保留，不把它们归为已修复或已接受；该差距与身份统一分别验收。真实 Chrome 进一步证明标题 anchor/divider、Markdown→caption 样式和按钮 disabled 保留旧值；没有点击本应禁用的 Action。两端三观察及六张 JPEG 保留，Rust capture 明确 successful=false。help 字段变化有原始帧证据，本批未操作 tooltip，不把它伪称为已完成 hover 验证。

| 生产者 | 未进入当前手工 hash 的字段 | 当前证据强度 |
| --- | --- | --- |
| markdown.rs | help、element_type | 原始载荷变化与 hash 不变；caption 样式实际滞留 |
| title.rs | anchor、help、divider、hide_anchor | 前三字段原始帧；anchor/divider 实际滞留，hide_anchor 仅静态 |
| badge.rs | help | 原始帧与 hash 不变，未做 tooltip 交互 |
| button.rs | disabled、help、icon 等 | 显式 key 下 id 不变；原始字段变化且可见按钮仍启用 |
| text.rs HelpElement | type_name、name、value | 静态遗漏，尚无本批动态 UI 证明 |
| components.rs | data_json、width、height、组件内容 | 静态遗漏，尚无本批动态 UI 证明 |

AddBlock 的 chat/expander 等虽也有手工 hash，不因静态字段遗漏就称为本批 UI 故障：已检查捆绑前端 applyDelta，旧 Element 复用判断只在 newElement 分支。新方案限定 Delta::NewElement，AddBlock/newTransient 与生命周期消息不变。

供用户决定的三项方案（均以完整行为修复为目标）：

1. **推荐：RenderContext::push 统一完成 NewElement 身份。** 在发送/recording/stream 三份拷贝之前，对完整 `proto::Element` 实际 protobuf 编码字节计算现有 MD5；不含 ForwardMsg metadata、delta_path、active_script_hash。统一入口保证新增字段自然参与身份。只改消息 `.hash`，widget id、图表 dataset/element id、URL、缓存键及数据 payload 不变，cacheable 继续 false，流式逐消息发送不整轮缓冲。同步删除各生产者重复的手工 hash 拼接/计算，避免双重开销；保留 AddBlock/newTransient 等既有处理。
2. **生产者显式使用完整 Element hash。** 各 render 在 Element 构造后调用同一个内部计算函数；避免自动发送前修改消息，但需每个生产者主动接通，今后新入口漏接仍可能复发。完成范围同样包括全部已接通 NewElement 生产者，不只修当前样本。
3. **逐项补齐现有字段元组。** 在各生产者穷核所有当前可变载荷字段，补全并保留转义/边界测试；不新增统一阶段，局部流程变化小，但需要持续维护两份字段清单。源码静态缺口和实际 UI 回归仍须验收，不接受已知差异作为结束条件。

方案 1 拟改生产文件共 15 个：`streamlit/src/elements/common.rs`（唯一身份终结点）；`streamlit/src/api.rs`（echo 直接生产的 NewElement 去掉重复 hash）；`streamlit/src/elements/` 下 `badge.rs`、`button.rs`、`charts.rs`、`code.rs`、`components.rs`、`data.rs`、`exception.rs`、`input.rs`、`markdown.rs`、`media.rs`、`status.rs`、`text.rs`、`title.rs`（只清理 NewElement 的手工身份；ChartElement 的私有 hash_input 和仅服务于该字段的工厂参数一并清理）。`proto.rs` 的 metadata/构造签名保持原样，不新增业务模块、依赖或公共接口。cache replay 当前也经过 context.push，需在 metadata 改锚后保持同 Element 编码的身份；录制与发送必须拿到同一个最终 hash。

稳定性与成本边界：这里以实际 Element 编码字节定义内容身份，不承诺跨运行时摘要字面值相等。已查到两类 map 字段（MixedData.arrow_blobs、Dataframe.button_click_widgets），Rust 公开 proto 类型仍保留 HashMap，不偷偷改成 BTreeMap。map 编码顺序可能带来冗余身份变化，需要在多列按钮映射/组件与缓存回放中验证状态、选择和滚动保持，并报告哈希/编码开销；若出现实际状态回退，解决后再验收，不能用接受差异关闭。大 Arrow 载荷需实测额外编码/分配，移除旧 hash 重复计算并保留逐消息 streaming。没有先假定性能阈值或引入全局 canonicalizer/新依赖。

验证顺序与停止位置：先全目标 Clippy/格式；单位覆盖完整 Element 的已测字段变化、相同字节/恢复输入、仅 metadata/路径变化、非 NewElement 不变、sender/recording/stream 一致与 one-shot；再真实同连接 WS、cache replay、组件/数据/控件集成，重跑代码高度/字段边界及当前五元素参考。实际 Chrome 必须把标题属性、caption 样式和按钮 disabled 修到 Python 行为，并补本批未做的 help 交互；旧失败材料继续保留，不能靠改冻结参考通过。最后相关 Python/矩阵/文档门、工作区回归与代表性大载荷测量，现有两个队列差异仍单独标明；其他三个待决流程不在此授权内。保持单代理，已授权的工作分支阶段提交/推送继续，合并/发布不包含。

按用户提供的 AGENTS.md 第 2 条，本项是影响所有 NewElement 的发送前流程取舍，等待用户明确选择；尚未修改任何生产身份计算，当前只完成调查、参考、诊断场景和证据门。


### Text layout defaults and pending alignment export (2026-10-30)

MarkdownOptions 的私有 width 改为 Option，默认省略 width_config，显式 stretch/content/像素保持既有 builder；caption 默认 stretch 不变。badge 默认省略 text_alignment_config，wrap 仍未设置。公共方法签名、依赖和身份流程未改。完整 Python 17 场景参考保留；当前外部 Rust API 可表达的 13 场景单独记录为 layout-widths（含报告共 14 Element），修前七处不同，修后完整载荷和路径匹配。identity-layouts 的 24 个 Element 也匹配 Python（仅归一化运行时控件 id），纠正历史记录的八处布局差异；四个目标仍为 A/A/A 身份。旧失败帧与 UI 记录未改，本批没有重新运行浏览器。

外部示例编译暴露 TextAlignment 位于私有 elements 模块，根模块未导出，调用方无法命名 Center/Right/Justify。完整 layouts 示例明确报错，only_widths=true 执行不含 text_alignment 参数的 13 场景，不把子集当成完整布局验收。已提出以下选项，尚未收到用户选择：

1. 推荐：在 streamlit/src/lib.rs 根部重新导出既有 TextAlignment，保留四个枚举变体和现有 builder；外部示例使用该类型，验证全部 17 场景。
2. 增加 left/center/right/justify 便利 builder，外部不直接命名类型；涉及 api.rs 公共方法扩展，并验证外部编译与 17 场景。
3. 暂缓外部非默认对齐，保留完整 Python 参考和未完成缺口。

按 AGENTS.md 第 2 条，新增公共导出/方法需要用户决定。本批未修改 lib.rs；统一身份、JSON 与更广队列策略继续分别等待决定。


### Shared text normalization on the pinned reference (2026-10-30)

固定环境 Streamlit 1.66.1 / Python 3.14.7 的 clean_text 调用 textwrap.dedent(str(body)).strip()。该版本 dedent 按 LF 分行，将 Unicode 全空白行清为空行，只从非空白行计算空格/Tab 的共同前缀，保留正文 CR。Rust 旧 Markdown 按最小字节数去缩进并用 lines() 改写 CRLF；text 和标题未清理，LaTeX 未在添加 $$ 前清理公式。

复用现有 utils/mod.rs 的 crate 私有 clean_text，Markdown/caption、text、三级标题与 LaTeX 共用。Unicode strip 补 U+001C–001F 与 Rust White_Space 的差别，缩进仅识别 ASCII 空格/Tab。未新增模块/依赖或公共接口，未改生产身份或队列策略。完整载荷比较另确认 LaTeX 宽度应 stretch、alignment 应省略，按该类型修正；未借此修改其他 Markdown 类型的默认配置。

12 输入乘七类调用，加输入报告共 85 Element；修前 72 个完整载荷不同，修后完整 Element 和路径匹配。原始首份 Python normalization 因 fixture 把 surrogate JSON 转义当成 Python 字面量，在最后 Unicode 场景抛 UnicodeEncodeError；保留 79 元素/异常/正常 finish 原记录。采集器 successful 表示传输完成，不能代替语义验收。修正 fixture 后另存 normalization-valid，不覆盖失败；Rust before 和 fixed 各 85 元素。浏览器排版、非字符串转换和未测参数仍开放。


### Divider alignment presence correction (2026-10-30)

Python 1.66.1 divider 直接生成 MarkdownProto，只有 body 与 DIVIDER 类型，布局带宽度但不带 alignment。Rust 复用 MarkdownElement 时仍填 LEFT；本批仅把 Divider 加入既有 LaTeX 的 alignment 省略分支，不修改 Native/Caption 或生产 hash。公共 API 单元扩入 divider 对照；真实 WS 测默认/显式 stretch、1/240/i32::MAX，另有 Markdown/caption/LaTeX 对照，九个完整 Element/路径与参考一致，修前五个 alignment 偏差保留。

无新公共接口、模块或依赖。非正宽度和超出 i32 参数范围不在本批验收中，不能将有效值对照当成输入错误兼容；浏览器几何与完整元素身份仍未完成。其余待决接口/流程不变。


本批还见到静态输入校验风险：divider_options 的 Width(i32) 直接进入 ElementWidth::Value，common.rs 将它 as u32；零/负值没有在该路径检查。尚未做异常/恢复的双端动态对照，不将其当作有效宽度验收的一部分，也不把“未验证”写成没有问题。错误传播形态需要结合既有调用契约另行确认。
