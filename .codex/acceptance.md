# Acceptance

Runtime compatibility is accepted only from black-box evidence against the pinned Python Streamlit 1.66.1 browser trace. Source inspection, compilation, health checks, AppTest, or a same-name Rust function can never imply compatibility.

The 1.66.1 runtime migration adds Rust regressions in `streamlit/tests/runtime/mod.rs` (loaded by the server module): health/host-config HTTP responses, unchanged index/JavaScript serving, a fresh two-entry WS handshake, four reruns including two button triggers and a reset, and heartbeat responses after each run. The real official-frontend [Rust button smoke](../tests/browser/rust-smoke/trace-smoke.json) records 36 frames and three clicks, each with a same-connection true trigger followed by `script_finished` status 0. This is retained UI/wire evidence for the minimal button demo, not completion of an upload journey, session restoration, or security-handshake compatibility; see [known compatibility gaps](compatibility.md).

## Long-term acceptance

2026-10-27 确认的长期目标以完整原生 Rust Streamlit 为交付，阶段见 [roadmap](roadmap.md#long-term-milestones)。历史页面矩阵和原有旅程只证明各自已测范围；它们不是完整功能分母，也不证明当前修改后的程序已通过相同验证。

| 层面 | 最终需提供的证据 |
|---|---|
| 功能与适用性 | 官方用户文档的功能、子能力、配置和使用流程盘点，保留文档版本与 1.66.1 运行参考版本；Rust 可使用不同接口和实现，源码仅核实行为；每项适用能力实现并接通，不适用及有意差异经审查或必要用户决策。 |
| 正确性与兼容 | 默认值、返回值、状态、异常、边界及重要组合的回归；涉及界面的能力使用官方前端和参考差分；缺陷有修复前后可定位证据。 |
| 完整应用 | 上传、筛选、选择、编辑、图表、导航、组件和实时更新等应用流程；包含空集、替换、恢复、重连及会话隔离。 |
| 架构与资源 | 会话、运行、widget、缓存、上传和媒体的职责及生命周期；已测场景无未处理的串会话、失控重跑或资源持续累积问题。 |
| 性能 | 固定版本、环境和输入下的延迟、吞吐、CPU、内存、资源回收报告；说明负载与局限，性能与容量目标由证据和用户决定。 |
| 开发与分发 | 清楚且兼容的 Rust API、可运行示例、准确文档、明确支持平台和工具链、干净环境构建/安装/运行记录。 |
| 工程与 Review | 相关代码检查、单元及真实集成验证通过，逐文件 diff 复查，独立只读 Review 无未处理的阻塞发现；被替代代码与说明及时清理。 |

长期 M0 只建立盘点和基线，不要求尚未实现的能力提前通过，也不把环境失败归为产品缺陷。长期 Goal 只有在上述完成条件及确认的停止位置全部满足后才能结束；代码完成、历史记录或局部 PASS 不能代替整体验收。

本地隔离开发环境、现有固定参考依赖和构建缓存用于执行与验证；不读取真实密钥或敏感配置。2026-10-29 本轮停止于本地可审查、可分发成果；提交、推送、PR/MR 创建、合并、发布、部署及生产/数据库外部写入分别核对本轮授权，不沿用历史批次的提交推送授权。完整兼容路线不默认接受未验证能力为限制，环境受阻项保留开放。

对应能力先写面向使用者的用法和行为文档，再实现；文档中的当前能力与规划接口分开标注。关键公共接口或行为规则确认后实施，普通实现细节自主处理。

用户最新澄清无需保持旧 Rust API 的向后兼容；Python Streamlit 1.66.1 的功能和行为目标继续保持。清理无关、过时的文档、图片、测试和代码，持续保持实现整洁；有效冻结数据仍用于回归，不因年代较早而视为无关。

## Current full-compatibility calibration (2026-10-29)

本轮按完整兼容路线接续，M3/M5/M7 保持开放。当前矩阵为 182 条目（130 implemented/partial、52 not_applicable）；生成清单的分桶为 80 项未测参数、12 项外部来源/环境、2 项 Rust 扩展/headless 边界和 47 项无显式缺口描述。同一条目可属于多个桶，分桶不能相加为能力总数，也不构成功能完成率。八项能力的过时或串入其他能力的 limitations 已校正，并同步生成清单；所有实现/兼容状态与原始轨迹保持不变。

chat/metric/progress 证据门真实复现旧检查缺口：在内存中删除 Python/Rust 捕获的全部原始帧，原两项检查仍通过。修复后逐帧解码 protobuf，核对字节长度、已存解码结果、元素字段、块尺寸、路径和成功结束状态；16 个双端篡改案例验证脱离原始帧的摘要会被拒绝。该修复加强冻结证据可信度，不是新增界面操作或当前 Rust 运行证明；同类其他参数链尚待审查。

本轮恢复 `target/pyref-venv` 中既有 requirements 固定的参考环境，实测版本为 Streamlit 1.66.1、pytest 8.4.2、PyArrow 26.0.0，`pip check` 无依赖冲突。Python 语法检查通过；矩阵/清单进度门、文档门及 chat-metric/json-badge/button-image/widget/media-more/layout 参数回归共 80 项通过。首次执行为 78 通过、2 失败，均为已有 colconfig_params 工作的示例/参考目录索引缺失；补齐索引后相关 80 项通过，未改其示例代码或捕获。全参考套件、当前程序真实前端和最终独立 Review 尚未在本轮执行。

### Metric string delta slice

后续字符串切片在原参考 app 与 Rust 示例中各加入 12 种文本 × normal/inverse/off：空串、字面零、0.0/0%、负零、普通/负号文本、NaN、缩进、多行和空白行。Python 1.66.1 实际 WS 参考保存为 `tests/reference/reference-browser/chat-metric-params/string-delta/trace.json`；修前 Rust `string-delta-before/trace.json` 在 36 项中有 30 项方向/颜色或文本不同。旧失败与原较小批次轨迹均保留，未重写冻结结果。

`MetricElement` 不再解析 f64，而对字符串去公共缩进、只将原始空值与字面 `"0"` 视作中性，再按首字符负号决定方向；显示使用同一去缩进文本，换行保留。没有新增公共接口或依赖。修后 Rust `tests/browser/rust-chat-metric-params/string-delta/trace.json` 与参考的 36 项字段全部一致，两个自有 Rust 服务及参考采集服务均已停止。Python 门同时解码三份捕获并断言 30 项旧差异与 36 项修复结果。

本批按代码→单元→集成顺序验证：所改 Rust 文件 rustfmt 检查、工作区全目标 Clippy（`-D warnings`）通过；去缩进单元回归、8 项真实 HTTP/WS 媒体回归通过；重新构建示例并采集真实修后 WS 后，相关 Python 门共 81 项通过。MSVC 保留既有 linker stdout 告警，未禁用 lint。`cargo test --workspace --offline --locked` 最终通过 210 项（库 203、journey ledger 1、宏 2、rustdoc 4），未包含另行运行全部示例测试；本切片不证明浏览器渲染、显式颜色/delta_arrow/数值格式与图表字段，也不关闭 M3。

### Query parameter value and mutation slice

新增固定 Python 1.66.1 参考 app 与一次性原生 WS 采集器，原始请求/响应保存在 `tests/reference/reference-browser/queryparams/values/trace.json`，不覆盖旧浏览器轨迹。合成 URL 含重复键、空值和中文编码；应用依次读取、替换、追加、设置空列表、删除空列表键、删除普通键、清空、恢复。八个 JSON 状态与七次 `page_info_changed` 保留实际交错顺序，参考进程和连接均由采集器关闭。Python 门逐帧核对 base64、长度、protobuf 解码结果及关键状态，不从 Rust 构造期望。

Rust 真实 WS 修前回归已失败（本地 `target/query-values-red.log`）：重复键取首值、URL 字母排序，且空列表键被当作缺失，应用在第四个状态后报错。修复仅改变现有 store 的末值读取、空列表存在性和插入顺序序列化，并同步 `to_vec` 的末值行为；公共签名与依赖不变，既有排序断言按新增实际参考校正。修后八个状态、七次 URL 写入及成功结束全部与参考一致；原重跑、切页及绑定 selectbox 回归仍通过。

按代码→单元→集成验证：所改 Rust 文件 rustfmt、全目标 Clippy（`-D warnings`）通过；store 单元回归后运行查询参数模块 5 项，再执行 `cargo test --workspace --offline --locked` 共 211 项通过（库 204、ledger 1、宏 2、rustdoc 4；日志 `target/query-values-workspace.log`）。查询参数参考门、矩阵/清单及文档门共 78 项通过。MSVC 既有 linker stdout 告警仍保留。全参考套件、全部示例测试和当前浏览器 URL 往返未在本批执行；保留/空键、嵌入参数及 widget-bound mutation 规则尚待后续验证，矩阵仍为 partial，M3/M5/M7 不关闭。

### Query parameter reserved and empty keys

同一固定参考 app/采集器增加 `--scenario reserved`，不重写旧数据；新原始帧位于 `tests/reference/reference-browser/queryparams/reserved/trace.json`。合成输入含大小写混合的 embed/embed_options、普通 st_embed 和空字符串键。九份 JSON 报告及四次 URL 写入记录应用读取隐藏、保留键 set/remove 拒绝且不发 URL、不改变状态，空键正常往返，公开 clear 保留原始保留键名称/值，以及清空后恢复写入。Python 门逐帧解码并检查场景完整性；只比较拒绝状态，不宣称 Python 异常类、文本或错误界面等价。

修前真实 Rust WS 回归失败，日志保留在本地 `target/query-reserved-red.log`：保留值可读、修改/删除被接受并写 URL，空键被拒绝。修复现有 store 的应用可见读取、set_all 保留键校验、to_vec 过滤与公开 clear 保留规则，移除空键限制。内部完整清空方法保持原行为；没有新增公共接口或依赖。两个场景复用同一真实 WS 对照过程，不复制测试服务。

依次完成格式/全目标 Clippy、store 单元、真实 WS 与工作区回归；`cargo test --workspace --offline --locked` 共 213 项通过（库 206、ledger 1、宏 2、rustdoc 4），本地日志 `target/query-reserved-workspace.log`。相关 Python 参数参考、矩阵及文档门 79 项通过。原参考服务已由采集器停止，测试服务在对照前关闭；MSVC 既有 linker stdout 告警保留。最终只补了说明注释，未改变已测行为。当前浏览器嵌入/URL 往返、包含保留键的页面切换、widget 绑定及完整错误 UI 未在本批验收；M3/M5/M7 与长期目标继续开放。

### Query-bound widget registration and cleanup

四轮固定 Python 1.66.1 原生 WS 参考保留于 `tests/reference/reference-browser/queryparams/binding/trace.json`：首轮注册默认控件并验证无绑定 URL 时 clear 可成功；活跃轮同时提供 URL 与真实 widget states；第三轮条件隐藏控件但运行内仍拒绝直接改写，结束时合并删除失效绑定 URL；第四轮允许手工写入。18 份 JSON 与 5 次 URL 写入按完整顺序对照，包含 selectbox、侧栏 text_input、大小写敏感键和拒绝后的状态保持。

Rust 修前真实 WS 失败保留在本地 `target/query-binding-red.log`。实现复用 WidgetRegistry 记录，不新增第二套登记：注册后追踪绑定、公共 set/remove/clear 防止越过控件写入、失效记录结束清理 URL，并在 script_finished 前统一发送。内部单元另验证同身份取消绑定与条件隐藏两种清理时机；保留键绑定有 Rust 参数防御，完整参考错误 UI 不在本批。

采集器最初将单轮默认 `query_string` 头带入了多轮捕获；已按首个原始 BackMsg 修正，旧值保留为 `original_query_string_header` 并记录 correction 说明，frames/时间/观察结果未改。后续 collector 按场景正确记录头部，Rust 与 Python 回归均以全部原始 BackMsg 序列作为四轮输入；未重新采集正确行为或改写期望转绿。

按代码→单元→集成顺序完成：格式与全目标 Clippy（`-D warnings`）通过，绑定清理单元与查询参数模块 8 项通过；`cargo test --workspace --offline --locked` 共 215 项通过（库 208、ledger 1、宏 2、rustdoc 4），日志 `target/query-binding-workspace.log`；相关 Python/矩阵/文档门 80 项通过。测试服务和参考采集服务均关闭；保留既有 MSVC linker stdout 告警。最终仅追加说明和分段空行，行为未变。仅 URL 初始化、动态 bind 切换的参考/界面、重挂载/跨页恢复、表单/缓存组合及真实浏览器同步仍未完成，M3/M5/M7 与长期 Goal 保持开放。

### Query-bound URL initialization and history

新增 `queryparams/seed/trace.json` 八轮固定原生 WS 参考，覆盖普通 selectbox、文本、可清空选择与创建模式选择：URL-only 初始化、前端值优先、再次 URL-only 请求、无效/默认/空值校正、后续代码赋值、历史导航有值/缺值。Rust 对照 32 次控件 value/raw_value 与 set_value 投影、8 份应用状态及 9 次 URL 写入的完整顺序；不把空 URL 的普通重跑（可保留旧值）与历史缺参（恢复默认）合并。修前失败日志在本地 `target/query-seed-red.log`。

实现通过内部 WidgetSpec 的可选 QueryBinding 策略进入已有注册路径；text_input/selectbox 启用，其余登记只机械补 None，公开 API/依赖不变。查询存储保存运行前 URL 快照并承接 ClientState 历史标志，服务端新轮刷新快照并清除历史标志；登记时决定 URL、前端与代码优先级，校正默认/非法参数，同步程序写入及前端 set_value。已有绑定追踪和发送边界继续复用。

逐文件复查又复现一个本批问题：URL 已选定后仍先解析被丢弃的错误类型旧状态。单独 `queryparams/seed-code/trace.json` 两轮参考（8 次控件同步投影、2 份状态）确认首轮与历史 URL 均应覆盖代码写入的整数状态；保留 `target/query-seed-code-red.log`，修复为按选中的来源惰性解析，避免丢弃状态抢先报错，并移除 URL 值的多余克隆。原八轮数据未重采或重写。

代码检查后完成两项 codec/优先级单元、查询参数模块 10 项真实/原生回归；`cargo test --workspace --offline --locked` 最终共 219 项通过（库 212、ledger 1、宏 2、rustdoc 4），日志 `target/query-seed-workspace-final.log`。相关 Python 参考/矩阵/文档门 82 项通过，Clippy 全目标 `-D warnings`、所改 Rust 格式和 diff 检查通过；最终只补字段说明和文档。保留既有 MSVC linker stdout 告警。参考及测试服务关闭，未提交或发布。仅比较已列协议/返回字段；禁用/伪造包组合、callback、绑定服务端重跑、跨页/重挂载、动态组合和真实浏览器历史仍未验收，完整参考套件及所有示例测试未在本批重跑，长期目标保持开放。

## Current M0 baseline (2026-10-27)

代码快照 `b94ac474d541533e36ca278c02838ebffba44db3` 在干净工作区完成本次基线；该 M0 批次随后仅修改文档与能力追溯数据；M2 新代码的验证另记于下文。Git 版本仅用于追溯，不是源码 SHA 门禁。原始命令、退出码、环境及日志索引见本地 `target/checks/m0-current-20261027/baseline.json`。

环境为 Windows 11 / x86_64 MSVC、Rust/Cargo 1.98.1、Python 3.14.7，参考 Streamlit 1.66.1 / PyArrow 26.0.0；使用已有固定依赖和 protoc 缓存。按代码、单元、集成顺序执行，格式、全目标 Clippy 和 quickstart 构建均通过；Rust 测试共 172 项（76 库单元、2 宏单元、11 示例、4 rustdoc、78 运行模块、1 journey ledger）。运行模块包含真实 HTTP/WS，也包含纯单元测试，不将 78 项全称为网络集成。冻结参考回归 1488 项通过，仍有 96 条既有 Pillow 弃用告警；本次没有重采 Python 行为。

同一代码快照下的 debug quickstart 仅做本机顺序冒烟：每个 HTTP 路由和一个持久 WS 连接分别预热 5 次、测量 100 次。health、首页、WS 重跑的 p50/p95 分别为 0.322/0.442、0.579/0.796、0.518/0.744 毫秒。测量窗口约 0.184 秒，服务进程各线程 CPU 时间合计 0.141 秒；工作集从 22,982,656 到 25,026,560 字节，私有内存从 16,527,360 到 16,601,088 字节。完整方法与结果见 `target/checks/m0-current-20261027/benchmark-smoke.json`，自有进程已停止。

该性能快照不证明并发容量、长期资源回收、无泄漏或生产 SLO，也不与不同环境的旧测量直接比较。吞吐、慢连接、大表及长时测量仍属 M5；下面各修复批次的计数和旧环境记录保留为历史证据，不代替本次基线。

## Frozen reference data

2026-10-27 用户确认：以当前项目锁定的 Python Streamlit 1.66.1 收集参考数据，并将输入、预期结果及版本元数据固化为仓库夹具，作为后续 Rust 单元和协议回归依据。已有且身份匹配的冻结数据直接复用，不因 Rust 改动或 checkout 目录变化反复采集 Python。

首次新增行为、参考版本升级或证据确实失效时补充采集，记录参考包身份、输入和配置、输出、原始观察及允许的规范化。后续测试直接重放；不得从待测 Rust 实现生成自己的预期，或为了转绿修改冻结结果。涉及界面的能力保留初始官方前端差分证据，必要时验证当前 Rust 界面；不要求每次重采 Python。

用户进一步明确取消源码 SHA 限制：不计算或校验 Rust、Python 参考应用、采集器及判定器源码的 SHA 作为测试或兼容门禁，不因源码变化强制重采数据，也不为保留此限制增加历史源码归档。版本号和 Git 提交只用于追溯，正确性由冻结输入输出、协议和实际交互证明。旧轨迹中的源码 SHA 保留作历史元数据，不再作为当前判定条件；功能检查数量必须如实反映实际检查，不能保留空检查凑数。

数据夹具、截图、Arrow/HTTP payload 和发行包的完整性校验与源码门禁分开处理；媒体地址及 widget/page 标识的协议哈希属于功能行为，不能在清理源码限制时一并删除。新采集记录参考版本与输入配置，不再增加源码指纹门槛。

历史 J09-S4 的 Python 配置、命令行与有效配置可共同核实 120 秒；Rust 的旧记录只声明该值，移除源码快照门槛后，保留材料不能独立重证精确的有效 TTL。实际断线至少 135 秒后换会话并重置状态仍有冻结行为证据。重放检查据此使用 `recorded_ttl120`，不把旧 Rust 记录当作当前配置证明。

取消源码门槛后的当前冻结数据回归为 1488 项通过（`pytest tests/reference`）；forms 采集/证据映射专项另有 53 项通过。26 个通用合同的必需检查总数由 264 减为 238，删除源码身份检查而非保留空检查。此次没有重新采集 Python 行为或修改原始输入输出；96 条 Pillow 弃用告警仍待后续维护。

旧机器绝对路径属于采集来源。重放必须通过当前仓库的受控相对路径、大小和 SHA 定位数据夹具，继续校验上传动作、HTTP payload 与运行关联，不静默重写原始轨迹。CSV 重放已有受控路径映射与错误目录、错误文件、路径遍历及内容变化的回归；其他历史路径仍按各自证据检查，不能据此宣称全部旧轨迹可跨目录重放。

## Rust error handling

Rust 禁止使用 `.unwrap()`；工作区 Clippy 配置 `unwrap_used = deny`，两个 crate 继承并覆盖全部目标，包括示例和测试。错误按现有返回类型正常传播，测试以明确断言表达预期，不通过批量替换 `.expect()`、增加 lint 豁免或通用 panic 提取器规避要求。需要改变公共错误接口时提交用户决策。

2026-10-27 当前迁移已通过格式检查、全目标 Clippy、工作区测试（151 库测试、1 journey ledger、2 rustdoc）及示例测试（11 项）。独立只读 Review 已复核迁移、查询参数重跑/切页边界与首个运行控制信号规则；这些结果不代替全部功能和浏览器兼容验收。原始日志见本地 `target/checks/m0-baseline/` 中的 `*-integrated.log`。

Q3 默认状态补证后的整合验证按代码检查、单元、集成顺序执行：格式与全目标 Clippy 通过；76 项纯库单元、76 项运行模块测试（含真实 HTTP/WS）、1 项旅程清单、2 项 rustdoc 通过。新回归直接读取冻结的 Python 四轮输入输出，并增加注明为 Rust 内部边界的空输入保留检查。修前失败与修后日志见 `target/checks/q3-componentv2/`；此条不扩展到完整组件兼容。

Q4 嵌套缓存补证后的整合验证同样按代码、单元、集成顺序执行：格式与全目标 Clippy 通过，76 项库单元、2 项宏单元、77 项运行模块测试（含真实 HTTP/WS）、1 项旅程清单、4 项 rustdoc 通过。新回归逐条对照一次 Python 1.66.1 冻结的 22/19 个 delta 和路径，同时独立核对返回值与计算次数；新增 `cache_nested` 示例经真实 HTTP/WS 两轮启动验证。日志见 `target/checks/q4-cache-nested/`，异常、更深递归、容器与跨会话边界仍待单独验证。

Q5/Q6 在用户确认选择性 nullable 规则后完成：76 项库单元、2 项宏单元、78 项运行模块测试（含真实 HTTP/WS）、1 项旅程清单、4 项 rustdoc 通过，格式与全目标 Clippy 通过。旧 Python 四轮 edits 直接复用；另一次 Rust 官方前端实测 6/6 合同通过，并独立解 IPC 验证 editor 原表 FF、返回表 FF/FF/TT/FT。Q6 同步纠正原表 wire 与编辑后返回值的说明。原 Python 输入可空和 Rust 非空输入扩展分开记录，不将后者冒称 Python 行为；日志见 `target/checks/q5-editor-schema/` 与发布证据目录。

## Dataframe selection reference (2026-10-27)

独立参考补证已冻结在 [dataframe-selection](../tests/reference/reference-browser/dataframe-selection/README.md)：五种配置 30 阶段，单独缩行补充 4 阶段，共 512 个原始二进制帧；两批均由独立 Reviewer 核对真实输入、协议/DOM/截图、1.66.1 版本、成功运行及自有资源清理。程序部分 keyed state、返回值补齐、回调实际顺序、排序输入位置、隐藏清理与缩行仍保留旧位置均按观察保留，不从待测 Rust 产生 expected。

参考批次 `31f539f` 新增 `test_dataframe_selection_reference.py` 的 6 项离线核验通过，包含数据字节、原 PB/CDP、compact 输入预期、Arrow 数据、DOM/截图与关键行为；当时只增加参考依据，未改旧数据或 Rust 代码。后续 Rust 选择实现与当前验证见下一节；参考结果本身不提升 Rust 兼容状态。

## Current M2 selection validation (2026-10-27)

当前 required 空协议输入修复通过格式检查、全目标 Clippy、177 项 Rust 测试（80 库单元、2 宏、11 示例、4 rustdoc、79 运行模块、1 journey ledger）及 1496 项冻结参考回归；96 条既有 Pillow 弃用告警保留。运行模块含真实 HTTP/WS 与纯单元，不全称网络测试。结果、范围和日志见本地 `target/checks/m2-required-selection/results.json`；前一单入口实现批的结果与指南原样编译记录仍在 `target/checks/m2-dataframe-selection/rust/`，不混作本次新增行为证明。

`12f3664` 的真实 WS 红复现证明 returned rows[0] 而 keyed/callback 为空；[新增八阶段协议参考](../tests/reference/reference-browser/dataframe-required-protocol/README.md)固定了非空/空表、恢复、程序 partial 与实际 server echo 的生命周期。修复后原 34 前端输入与新 8 显式协议阶段共用 42 阶段真实 Rust WS 回归，原 oneof 来源检查保留；新增两项离线检查直接连接 raw PB、compact、Arrow 和实际 echo。协议反序列化先按旧注册元数据正规化，再比较变更、写 keyed 和安排回调，注册更新下一轮行数；程序 partial keyed 与旧位置不被裁剪。没有新依赖、公共接口或旧数据重采。

先前 [Rust 官方前端六阶段证据](../tests/browser/rust-dataframe-selection/README.md)保留 SingleRow 选择/重跑/排序/详情/键盘编辑的实际范围，不能据此宣称浏览器能清除 required 行。畸形选择和有效 trigger 同批的整体拒绝回归继续通过；这不替代完整恶意输入兼容。未验证的全部模式/参数、非法组合/程序值、多页/会话、lazy 及 CSV 完整闭环、追加仍属后续工作。矩阵保持 partial，M2 和长期 Goal 均未关闭。

## Current M2 CSV subset validation (2026-10-27)

用户采纳 A 后先写使用说明，再新增独立 `csv_workbench`，不改销售示例、不增依赖或公共 API。冻结 [Python 33 阶段](../tests/reference/reference-browser/csv-workbench/README.md)及 [Rust 对照](../tests/browser/rust-csv-workbench/README.md)，独立 Review 核对 1358 个 PB、真实交互、Arrow、下载及两会话；只对照逻辑文本数据/计数，保留 schema、索引、空图和下载重跑差异。部分 Python 截图柱高未刷新而 Arrow 已更新，原因未定，不宣称像素等价。来源替换先空状态的真实失败已于 2026-10-28 由用户决定改为显式清空方案并双端验收（见上文 Current CSV source replacement validation），M2/长期 Goal 仍不因此自动关闭。

本批修复已复现的 CSV 下载 404 及附件元数据丢失，公开接口/内容地址/首次存储不变。代码检查通过；当前 184 项 Rust（161 库/运行模块、2 宏、1 ledger、4 rustdoc、16 示例）及 1498 项冻结参考测试通过，保留 96 条既有 Pillow 告警。新离线测试链接原 PB、Arrow、输入和下载；库内编辑回归直接复用冻结选择、真实编辑输入及下载预期，应用另有 5 项纯模型测试，没有重采旧正确 Python 数据。另 17 阶段显式 Rust WS/18 次运行防旧 Apply/Append 误写已独立通过，不能冒称 UI/Python 证据。全部自有服务/浏览器已清理；日志索引为本地 `target/checks/m2-csv-workbench/`。首次整库收尾因正在运行的示例占用 Windows 链接目标失败，停自有服务后重新完整通过；不隐去失败或把环境错误算为产品缺陷。

上述 1498 项运行先于该子批最终追加的矩阵元数据，未覆盖后来引入的嵌套证据格式错误；本轮已发现、修正并完整复验，见下节，不将旧通过结果当作该元数据有效性的证明。

## Current editor bounds validation (2026-10-27)

已修复两行表删除位置 2 的 panic：全部删除位置先验证整数可表示性及范围，沿用 DataError，不裁剪、不忽略。使用说明先于生产修复；[新冻结参考](../tests/reference/reference-browser/dataeditor-invalid-rows/README.md)保留 18 个脚本级实验及独立四阶段真实协议。Rust 单元复用 13 个非负场景、另验空表，真实 WS 回放错误→合法删除→恢复，原输入与会话/editor 身份保持。负索引另有差异未改，错误文字与 Python Exception 元素不作逐字段等价声明。

当前格式、全目标 Clippy、186 项 Rust（163 库/运行模块、2 宏、1 ledger、4 rustdoc、16 示例）及 1500 项冻结参考检查通过，96 条 Pillow 告警保留；结果和完整命令/日志索引见本地 `target/checks/m2-editor-invalid-rows/results.json`。首次全参考为 1499 通过/1 失败，定位到前批矩阵用了校验器不支持的嵌套 evidence；只改回既有路径列表，未动生成器或断言，相关 49 项及随后完整 1500 项通过，原失败日志保留。Python 新协议首次即时端口关闭观察未通过，原退出 1/port_closed:false 未改，独立补证明确确认原 PID 77124 消失、61412 无监听，不重采。

另已归档 [generic Vega 的真实更新失败](../tests/browser/rust-vega-refresh-before/README.md)：四阶段消息值 3→8→8→3、可见值仍 3，图生产代码与旧 oracle 未改。A/B/C 协议及交互状态取舍仍待用户选择，CSV 来源规则亦待决，M2 与长期 Goal 均未完成。静态、运行回归及数据归档已独立 Review，无本编辑器修复范围内剩余阻塞。

## Current download boundaries validation (2026-10-27)

按使用文档先行、冻结参考复用的约定，补十条新的 Python 1.66.1 公开字节下载输入/真实 WS/HTTP，不重采已有正确场景。Rust 留下缺默认文件名的真实红断言后，修复默认/空名、Unicode/引号/反斜杠扩展参数及文本 charset；原始 MIME 仍决定地址和扩展名，现有媒体、Range、首次写入保持。十条 URL、四项响应头及原字节精确对照通过，没有新增公共 API、依赖或源码 SHA 门槛。

[原生浏览器证据](../tests/browser/rust-download-boundaries/README.md)另记录两次真实点击和落盘文件名/原字节；HTTP 是加载时 Fetch、随后点击保存，不伪称点击后重新请求。三项新离线检查连接冻结 PB、公开参数、HTTP、下载字节及两次 Rust 浏览器保存。所有自有服务、Chrome/profile 已清理，root 复核两 PID 消失、8523 无监听。

格式及全目标 Clippy 通过，既有 MSVC linker_messages 提示保留；该下载批次 187 项 Rust（164 库/运行模块、2 宏、1 ledger、4 rustdoc、16 示例）与 1503 项冻结参考检查通过，96 条既有 Pillow 告警保留。矩阵最终证据只挂下载条目、维持 partial，并额外复核 47 项矩阵检查。完整命令、退出码与本地红/绿日志索引在 `target/checks/m3-download-boundaries/results.json`；生产代码、冻结参考及真实保存证据经独立只读 Review。最终工作分支交付与下节缓存修复一并记录，未发布或部署。

该批仅是 M3 下载子集，不证明所有标点/MIME、文本和文件对象自动类型推断、延迟 callable 或完整媒体生命周期。CSV 来源与 generic Vega 的关键取舍仍待用户选择；M2、M3 与长期 Goal 都未关闭。

## Current cache kind isolation validation (2026-10-27)

真实复现同名同参 data→resource→data 将 `Some(42)` 错返 None；按使用说明先行，内部存储分为 data/resources，保留原会话作用域、Arc、重放和总清空。新[冻结公开参考](../tests/reference/reference-browser/cache-kind-isolation/README.md)包含四组结构值/None、正反顺序，初始计数均 1/2/2/2；它是 bare-script API 实验，真实 MemoryCacheStorageManager 告警保留，不冒称 Python UI/wire。独立分类 clear 的 Python 记录没有变成 Rust 公共接口。

Rust 新增三项回归：原错误值/资源身份、参数变化和清空；直接复用四组初始值/计数；两轮真实 WS 在同会话重放各自 computed=1/2 和连续路径，后轮不重复计算。既有嵌套与基础缓存回归保留，缓存组六项通过，五项新离线检查核对公开计划、原日志、值与计数。数据完整性仅绑定输入输出，不绑源码。

最终格式、全目标 Clippy、190 项 Rust（167 库/运行模块、2 宏、1 ledger、4 rustdoc、16 示例）及 1508 项冻结参考检查通过；96 条既有 Pillow 告警与 MSVC linker_messages 提示保留。独立只读 Review 未发现本修复范围内阻塞。最终完整命令、退出码及红/绿日志索引见本地 `target/checks/m3-cache-kind-isolation/results.json`；本批按 Goal 授权提交、推送工作分支，不创建 PR/MR、合并、发布或部署。

归档阶段先发现原始 JSON 的 CRLF 空白误报和默认忽略的日志未入索引；仅补原换行识别并显式纳入日志，未重写 raw 或改预期。最终暂存空白检查通过，27 个原始证据文件的索引大小/数据 SHA 全部与 manifest 一致，避免将工作区数据通过误当作完整提交归档。

该修复不关闭完整缓存能力：全局/跨会话、分类别或函数清空、TTL、持久化、全部序列化类型、异常与并发仍待后续设计/验证。CSV 来源规则和 generic Vega 方案继续待用户选择，长期 Goal 保持进行中。

## Current media Range validation (2026-10-27)

原 Rust 对 `bytes=-5` 返回整文件 200，而冻结公开参考为 206；许多非法/越界请求同样错返整文件。使用说明先行后，扩展既有单范围解析并在非空无效 Range 时提前返回 416，保留公开 `Option<ByteRange>` 签名、内容地址与依赖。先校验数字再饱和累积，合法超大 suffix/end 仍按文件边界解释，不引入新大小限额；空内容与空 header 分别核验。旧 suffix fallback 的内部断言按新真实参考更新，旧 Python raw 未改。

[冻结参考](../tests/reference/reference-browser/media-range/README.md)包含最初 23 个新请求和仅四个补充整数/空 header 输入，合计 16 PB、27 HTTP；原 23 个未重采。实际 2×200、12×206、13×416，所有 416 均为 13 字节 `Invalid range`、`Content-Range: bytes */N` 且无成功下载头。Rust 公共调用实际发射 URL 后逐个 GET，精确核对状态、五项头的值/有无及原字节；解析器复用同一组记录。派生字节表逐项连接原请求/响应与公开输入，避免加 base64 依赖；首次夹具编译失败单独保留，不充当产品红复现。两次自有进程、WS 和端口都已清理，root 再核对 PID 消失、无监听。

格式与全目标 Clippy、11 项媒体相关 Rust 检查、最终 192 项 Rust（169 库/运行模块、2 宏、1 ledger、4 rustdoc、16 示例）及 1513 项冻结参考检查通过，96 条既有 Pillow 告警和 MSVC linker_messages 提示保留。独立只读 Review 核对数学边界、16 PB、原 HTTP 与派生字节，无范围内阻塞；完整命令/退出码/红绿日志索引见本地 `target/checks/m3-media-range/results.json`。矩阵仅在下载/视频条目补传输子集，状态及 summary 不变。

未据此宣称浏览器拖动定位、HEAD、If-Range/CORS、重复或全部数字/header 语法、所有媒体类型及完整资源生命周期已验收。按当前 Goal 授权提交推送工作分支，不创建 PR/MR、不合并/发布/部署；CSV 来源与 generic Vega 关键取舍仍待用户选择，长期 Goal 继续。

## Current library portability validation (2026-10-27)

真实隔离库目录改名且无外部 www 时，原 protoc 固定路径编译失败；改为现有编译器的虚拟前缀映射，并把原已内嵌的 6467 字节官方 index 原样作为 crate 私有数据，保留协议、依赖、API 与完整 frontend sidecar 规则。改名/no-www 检查及含空格目录的 quickstart release 构建通过，Cargo 包清单实际包含私有 index；清单命令首次因未提交修改拒绝后，仅用 --allow-dirty 做本地列表核对，不发布包。

[原生安装证据](../tests/browser/rust-library-portability/README.md)保存 24 PB、60 实际 HTTP、同 WS 两轮完成、真实复选框 true→false、DOM/截图及进程清理。源/安装后/交互后三次完整 347 文件集和数据 SHA 均与锁定 wheel 一致；root 再次核对全部实际安装字节和复制 exe 字节。UI 首次日志为空，另外的 info 日志属于第二次健康检查 PID，不混称同一进程。全部自有服务/Chrome/profile 清理，8503 无监听。

格式、全目标 Clippy、192 项 Rust 及原有完整 1513 项冻结参考检查通过，96 条既有 Pillow 告警和 MSVC linker_messages 提示保留。新增三项构建/资产/原 PB-CDP-DOM-PNG 证据检查随后单独通过，未把它写成一次 1516 项全量运行；新增 DOM 绑定校验最初误读 JSON 字符串和坐标对象的两种 CDP 返回形态，修正解码后精确比较通过，失败日志保留、raw 未改。普通构建修复与文档经独立只读 Review；完整命令/日志索引见本地 `target/checks/m6-library-portability/results.json`。

本地生成 quickstart Windows x86_64 演示 zip（exe+347 frontend+README），归档内每个可执行/资源字节与已验证安装目录相同；产物在本地 target，不随 Git 分发，也不是公开发布。仍未验证全新机器运行库、无缓存构建、MSRV、其他平台或完整 crate archive。修正本轮新示例漏写 async 后，仅依赖 streamlit 的外部应用仍真实失败于宏的 tokio/env_logger 名称；公共接口 A/B/C 待用户选择，未擅自实现支撑模块或添加调用方依赖，长期 Goal/M6 保持未完成。

## Current crate archive example validation (2026-10-27)

真实执行 workspace package 后默认库/宏验证已通过，但提取出的 chartlibs/video 示例因四个仓库外数据输入编译失败。先补使用说明，再把少量配置/媒体原样放入 examples/data，两个示例只改 include 路径；保留原参考、不改依赖/接口/Vega 逻辑。最终真实库包 227 文件、宏包 6 文件，全部 41 个包内示例及普通 SDK consumer library target 编译检查通过。原/私有数据/最终 tarball/提取目录逐字一致，MP4 换行保护，JSON/DOT 文本保持原 Git 换行策略。

格式、全目标 Clippy、仓库 192 项 Rust 及这次完整 1516 项冻结参考检查通过，96 条 Pillow 告警和既有 MSVC linker_messages 提示保留，无旧 Python 数据重采。独立只读 Review 已核对源改动、实际包及依赖子集，无本示例修复范围内阻塞；[原日志与成员/状态](../tests/build/crate-archives/README.md)不绑定源码指纹，实际 crate 为本地生成，不是发布。

必须保留的失败：最终独立源码包的维护者 lib test --no-run 仍报 31 个仓库级输入读取缺失，并未执行这些测试；不能用普通 SDK/示例通过冒充它通过。PKG-A/B/C 分发与测试边界等待用户选择，宏支撑接口也未采纳，M6/长期 Goal 未关闭。首次 probe 漏 InputWidgets 导入、提取目录误发现祖先 workspace 的设置失败另存，不作产品缺陷。完整命令/退出码与结果索引见本地 `target/checks/m6-crate-archives/results.json`。

## Current media response storage validation (2026-10-27)

媒体完整 GET 原先每次复制整个存储文件，206 又复制片段。先补使用说明和优化前测量，再把 private 存储改为既有 `Bytes`，响应快照及范围共享不可变内容；注册隔离、公开 `get -> Vec<u8>` 的独立返回、内容地址、首次注册元数据及 HTTP 行为保持，没有新接口、依赖或生命周期规则。

[三次前后对照](../tests/performance/media-storage.json)使用同一 8 MiB 合成文件，同时保留 16 个完整及 16 个 64 KiB 范围响应。完整响应独立缓冲数均从 16 降为一份，中位构造耗时从 74.323 降至 3.321 ms，操作系统峰值工作集约从 163 降为 35 MiB。Windows/debug、进程内生产路由构造及整进程内存观测是本次口径；不包含 sockets、CPU、网络吞吐、慢客户端或长期回收，不设性能阈值。5 ms 是请求采样睡眠间隔；调度和观测可能漏掉短峰，操作系统工作集高水位另外保存。前后 executable 路径相同但中途重建，不把当前二进制冒充旧版本；新测量夹具最初误传 &String 的编译错误独立保留，不是产品红复现。

格式、全目标 Clippy、7 项媒体单元及最终 194 项 Rust（171 库/运行模块、2 宏、1 ledger、4 rustdoc、16 示例）通过；全部 1516 项冻结参考检查通过，96 条既有 Pillow 告警和 MSVC linker_messages 提示保留。新增回归检查注册/公开读取隔离、多个完整与范围响应的内容、头和剩余存活期；既有真实 HTTP/WS 精确复用 27 个范围和 10 个下载案例，未重采 Python。各次测量自有 test 进程均退出；原始输出、命令和检查日志索引在本地 `target/checks/m5-media-storage/`。

媒体仍是进程全局存储，没有自动淘汰；此次共享响应不解决生命周期、完整平台或容量验收，M5 和长期 Goal 保持未完成。CSV 来源、Vega、宏支撑和源码包分发的已存待决方案不因本批通过而采纳。

## Current session boundary validation (2026-10-27)

本批没有发现需要修改生产逻辑的证据，只补 session.rs 的 `#[cfg(test)]` 与既有会话运行测试。使用说明先行；不改连接接管、默认 120 秒/测试零保留期、上传/缓存归属，不新增公共接口或依赖。

实际 16 个 WS 客户端在两个 Actix worker 配置下建立不同计数；一半先关闭确认再重连，一半继续点击，逐会话核对 ID、计数、运行次数、单个 finish 及普通重跑不重放按钮。共完成 72 次运行，保留 32 次点击计数；新增测试统一在停止并等待自有服务器后返回或重抛，成功清理已实测，错误/超时/panic 清理按控制流核对而未做故障注入。进行中接管不是该新增流程，而是另一次实际通过的旧运行暂停回归，它确认旧运行/发送先完成，其他会话不被注册表锁阻塞，旧连接不能越过所有权继续运行。

零保留期测试四轮、每轮同时保留 32 个 lease。活跃时各对象仍在，drop lease 后注册表仍保留惰性条目；下一次连接清理旧条目并创建一个新会话，旧应用值、上传容器与缓存资源的 Weak 均不能再升级。最后释放新 lease，再用未知上传会话查询触发清理，每轮注册表为零，共观察 128 个旧会话对象释放。Weak 不持有资源，不将这个结果称为 RSS 下降、所有上传外部句柄已释放、全局媒体回收或长时无泄漏。

格式与全目标 Clippy 通过；会话单元 7 项、真实 WS 会话组 5 项、暂停接管 1 项共 13 项通过，既有 MSVC linker_messages 提示保留。命令依次为 `cargo test -p streamlit --lib session::tests:: --locked --offline -- --nocapture`、`cargo test -p streamlit --lib server::tests::sessions:: --locked --offline -- --nocapture`、`cargo test -p streamlit --lib server::tests::overlap:: --locked --offline -- --nocapture`。原始日志及索引位于本地 `target/checks/m5-session-boundaries/`；最初测试错误类型推断导致的编译失败单独保留，不当作产品红复现。

本批未改 Python/前端/公开行为，不重采参考，也未重复未受影响的全量参考和示例运行；上一媒体批次的 194/1516 仅是对应版本的记录。本次并发客户端正确性不证明应用执行必定重叠、同时处理能力或 SLO；M5、其余未验证组合和长期目标继续保持未完成。

## Current WebSocket logging validation (2026-10-28)

真实红复现使用隔离 test 子进程，将现有 websocket logger 显式设为 Debug（含 Info/Warn/Error），没有把默认过滤等级冒称 Info。两轮真实控件输入/大文本输出、非法 protobuf 后心跳、未支持请求、原始文本及带描述的关闭帧均已完成，服务停止后仅因五种合成标记进入日志而断言失败。原始日志 131,289 字节；修后同配置探针为 3,704 字节、0 个标记，原 wire 文本、控件 ID、关闭 code/description 及心跳恢复保持，错误诊断和 kind/frames/bytes/elapsed_ms 字段仍在。数据与方法见[小型记录](../tests/performance/ws-logging.json)，重复大载荷 raw 仅留本机 target，不做源码快照或源码 SHA 门槛。

生产改动限 handler 的日志与局部计数/计时：ForwardMsg 仍只编码一次，entry/send join、运行控制、会话锁、错误处理及原关闭应答保持。Info 保留运行汇总，Debug 提供逐帧摘要；不再格式化完整 protobuf、原始消息或文本/关闭描述。elapsed 仅为取得运行锁后的执行与发送调度，不是队列等待、客户端收取或端到端延迟。该字节差异是一个固定合成场景的日志体积，没有 CPU/吞吐结论、性能阈值或完整安全/全局脱敏承诺；应用和第三方日志继续由各自负责。

格式、全目标 Clippy、先行 84 项纯单元检查、日志红→绿及最终 197 项 Rust 检查通过；最终总数为 174 库/运行模块、2 宏、1 ledger、4 rustdoc、16 示例，不重复累计先行检查或日志子进程内部同名用例。实际工作区回归覆盖会话、接管、运行控制、缓存重放、流式输出、HTTP/WS 及静态资源，既有 MSVC linker_messages 提示保留。新测试的 single_match 风格失败已正常修正，原日志独立保留，未 suppress；此前纯单元结果不是替代最终版本全量 Rust 的依据。

仅 Rust 内部日志变化，没有 Python/前端/协议或应用用法变更，未重采或重复运行未受影响的全量 Python 参考，不将旧 1516 计为本批新结果。真实 Chrome、认证/权限、外部日志保密及长期容量仍未据此验收。全部自有测试子进程已终止、服务 handle 停止并等待，命令/结果/红绿日志索引见本地 `target/checks/m5-ws-logging/`；M5 与长期 Goal 未关闭，四项旧关键取舍继续待决。

## Current native input boundary validation (2026-10-28)

RGBA 公共 st.image 的微小缓冲/超大尺寸调用已真实复现乘法溢出 panic；改为 checked_mul 后，无效尺寸/缓冲不发出元素，也不占用后续有效 1×1 图片的位置。没有新图片大小阈值、接口或错误策略；底层 png_encode 仍要求通过 valid 的输入，不据此宣称任意无效底层编码调用均安全。

无编辑 data_editor 的公共 disabled 调用已分别复现 metadata 从调用方标记丢为 `{}`、合法零列输入在 clone_batch.expect 中 panic。直接复制已有效 batch 并删除重建 helper 后，普通返回保留完整 schema/data，底层零列复制保留 0/2 行；公开 0/2 行零列输入在后续 chart_arrow_data 显示转换仍返回 Arrow 错误，未完成零列表格呈现。公开调用测试允许正确原样返回或该既有类型的显示错误，不将当前缺口锁成目标；实际编辑后的 schema/index 策略未改。

格式、全目标 Clippy、8 项媒体和 2 项无编辑定向检查、最终 200 项 Rust（177 库/运行模块、2 宏、1 ledger、4 rustdoc、16 示例）通过；定向检查不重复累计。矩阵只更新 st.image/st.data_editor 的原生证据/局限，partial 状态及 summary 不变，并去掉图片条目过时源码指纹/行号说明；47 项矩阵检查通过。未重采 Python 或冒称当前全量参考结果，原图片 HTTP/WS/PNG 和冻结编辑输入由实际 Rust 回归复用，既有 MSVC linker_messages 提示保留。

release RGBA 补验最初因未配置 protoc 在构建阶段失败，未执行测试；改用现有缓存 protoc 后，同一图片边界用例在 optimized profile 实际通过，不再因溢出尺寸接受空缓冲，也未进入巨型分配。这是一个 release 用例复验，不冒称整个 release 测试集或其他平台通过。两次新测试的导入/类型推断/借用编译失误另存，不作产品红复现。原命令、红绿与构建日志位于本地 `target/checks/m3-native-boundaries/`。本批是 Rust 原生算术/所有权与无编辑结果的正确性修复，不证明全部图片类型、全部元数据组合、零列前端兼容或其他平台；M3 和长期 Goal 继续未完成。

## Current zero-column display validation (2026-10-28)

用户于 2026-10-28 采纳零列呈现方案 A（虚拟 RangeIndex）。落点在 `chart_arrow_data` 与 `with_range_index`：重建 batch 时显式携带行数（`RecordBatch::try_new` 在零列时因缺 row count 返回的 Arrow 错误即本批修复的公开缺口），合成的 pandas range 索引描述符保持既有逻辑，零列 wire 因此与实测编辑器同构、官方前端可创建格子；无实体索引列、新公共接口、依赖或前端改动，有列路径行为不变。

WS 回归 `zero_column_views_render_virtual_range_index_over_the_same_flow` 以 0→2→普通重跑→0 驱动同一复选框流，逐阶段断言 dataframe、两个固定编辑器与显示索引 table 四个视图的 IPC 均为（真实行数, 0）列并携带 range 0..行数 描述符；`unedited_zero_column_batches_keep_explicit_row_counts` 不再接受显示错误。真实浏览器用既有 zero_columns 采集器对 `cargo build --example zero_columns` 服务器重放同一契约并冻结于 `tests/browser/rust-zero-columns/`：两行时三个 grid 全部渲染 0/1（Python 参考中 dataframe 为 cell creation 错误、table 空框）、普通重跑保持、归零回空，全程无 stException 与 console 错误；trace 与 PNG 经 manifest sha256 锁定，离线测试双向断言含"不重放上游格错误"。

`cargo fmt --all -- --check`、全目标 Clippy（-D warnings，既有 MSVC linker_messages 提示保留）、`cargo test --workspace --locked`（185 项）与 1521 项冻结参考/矩阵检查通过；Python 9+3 协议参考与首次 UI 错误证据未重采未改写。已知边界：一次成功采集、一台机器的 headless Chrome；动态行编辑、任意 schema/metadata 组合、编辑后元数据策略未验证；Rust run 循环每轮重发同 session id 的 new_session（Python 为每连接一次）是先前批次已有差异且官方前端接受，非本批引入。M3 与长期 Goal 保持未完成。

## Current CSV source replacement validation (2026-10-28)

用户于 2026-10-28 采纳来源切换方案 1（显式清空）。Rust `Workbench::source` 的 None 分支不再清空工作副本（空上传状态只清选择），新增 `clear()` 与 `wb-clear` 按钮；Python 参考应用同轮改为同一契约并加同 key 按钮，采集器 sources 段改为 `remove-upload-keeps-copy`（移除保留副本并下载验证）→ `clear-working-copy` → `empty-rerun` 三段。示例单元测试改为断言空状态保留副本、仅显式清空移除。

双端 sources-clear 16 阶段各一次成功采集并冻结（Python 于 `tests/reference/reference-browser/csv-workbench/sources-clear/`，Rust 于 `tests/browser/rust-csv-workbench/sources-clear/`）：五个坏文件逐个替换保留 `workbench-bom` 旧副本、空表头替换、有效替换、移除上传后副本保留、显式清空回到空态且重跑保持。四次实际下载（坏替换后/空表头/替换后/移除后）双端逐字节相同；离线测试 `test_csv_sources_clear_semantics_match_across_runtimes` 以阶段转移（旧副本→新副本）断言空状态前驱运行仍显示旧副本，双端文案差异（错误前缀、空态提示）按语义断言。此前 main/filters 33 阶段与旧失败链（本地 `sources-first/`）均未重采、未改写。多文件上传、上传端点安全边界与全部坏输入枚举未验证；M2 关闭评估另行执行。

## Current generic Vega refresh validation (2026-10-28)

用户于 2026-10-28 采纳图表漏刷方案 A。落点 `elements/charts.rs`：`split_inline_values` 返回字段映射，`vega_lite_chart` 将提取的 Arrow 数据按 IPC 字节 md5 内容命名、放入 `datasets` 并由 spec `data.name` 引用（与同文件 altair 同构），元素 hash 输入随含名 spec 变化；URL、自带 data.name、嵌套 spec 与无数据调用不改写、行为不变，公共 API 与依赖无变化。

WS 回归 `generic_vega_same_shape_updates_change_the_dataset_identity` 驱动 0→8→普通重跑→回 3：每轮断言单 dataset、md5 名、spec 引用一致、行值正确，且 3↔8 改名、重跑保持。真实浏览器：静态七图页在新 wire 下重采并通过 journey-chartlibs-v1 契约 6/6（契约增加原生时间线变体与名称匹配不变量，Python oracle 与冻结 Python 回放未重采）；新增可复用采集器 `vega_refresh_capture.py` 重放失败基线的四阶段流程并冻结于 `tests/browser/rust-vega-refresh-after/`——可见 ARIA 标记随 wire 同步 3→8→保持→回 3，修复前停留 3 的失败基线保留。修复期间发现并修正本机克隆对 `chartlibs-deck_json.json` 的 CRLF 污染（.gitattributes 补 `-text` 并从索引恢复 LF），该固件经 `include_str!` 直接进入 wire。

`cargo fmt/clippy(-D warnings)/test --workspace --locked` 与冻结参考/矩阵检查通过（数字见最终批记录）。边界：一次采集、一台机器的 headless Chrome；图内交互状态（缩放/brush/选区）在 view 重建时的保持未验收；大数据 hash 成本随 IPC 线性，未做性能声明。M2 关闭评估另行执行。

## M2 milestone close (2026-10-28)

退出条件逐项核对（均含冻结证据与真实前端操作）：完整用户流程——CSV 工作台主流程 20、筛选 13、来源替换 16 阶段双端冻结对照，选择旅程 42 阶段（34 前端 + 8 required 协议）；空集——无匹配/空匹配筛选、空表头工作副本、零列 0/2 行呈现（方案 A）；替换——坏替换保留旧副本、有效替换、空表头替换（sources-clear）；恢复——各流程普通重跑保持状态、会话断线重连接管（M5 批次）；排序映射——浏览器排序后选择映射回原始位置（main-complete + dataframe-selection）；会话隔离——双会话独立上传/编辑/下载（main-complete 与 WS 回归）。上传、筛选、选择、详情、编辑、增量更新（Append 流；官方 1.58.0 已移除 add_rows，按用户决定不新增 Rust 追加扩展）与图表联动（计数图随筛选/编辑联动、generic Vega 同形状刷新修复）均有实现、回归与浏览器证据。

遗留项按范围归档，不阻塞 M2：多文件上传模式归 M3 输入能力；上传端点安全/凭据边界归 M4/M5；图内交互状态（缩放/brush/选区）在 Vega view 重建时的保持继续开放；下载/编辑之外的全部参数组合与完整默认图表兼容不在本里程碑声明内。关闭质量门：`cargo fmt --check`、全目标 Clippy（-D warnings）、`cargo test --workspace --locked`（186 项）、全部示例构建、1525 项冻结参考/矩阵检查通过；lessons.md 增补第 29 条（`include_str!` wire 固件的 `-text` 属性）。当前焦点移至 M3/M6，M4 随后启动。

## Current M6 distribution decisions validation (2026-10-28)

用户于 2026-10-28 采纳 PKG-A 与宏支撑 A。PKG-A 为交付边界定义：SDK crate 的验收即 `cargo package` 的库/宏编译与全部示例构建（既有 crate-archives 日志），全部维护者回归由完整仓库源码交付承载；此前实测的 31 项包内 lib test 输入缺失重新定性为边界记录，断言未删、测试未关、包内不捆绑旧参考，crate-archives README 与指南同步改述。

宏支撑 A 落点：lib.rs 新增 `#[doc(hidden)] pub mod __macro`（重导出 tokio/env_logger）；`#[streamlit::main]` 全部走 `::streamlit::__macro::…` 限定路径，并显式构建同样的 Tokio 多线程运行时——不用 `#[tokio::main]` 属性，因为该属性自身展开仍引用裸 `::tokio`，首次实现曾漏此点。复验：改名库目录 + 含空格路径、仅依赖 `streamlit` 一个包的 consumer 应用真实编译（`consumer-macro-green.log`；本机经 crates.io 常规拉取的 vendored protoc 提供 `PROTOC`）、启动 8550、健康检查 ok、真实 Chrome 点击 **Add** 三次 Count 0→1→2→3、无 stException；历史红 `consumer-macro-red.log` 保留。工作区 fmt/Clippy(-D warnings)/186 项测试与全部示例构建通过；既有宏参数解析单测不受影响。边界：单机 Windows 缓存构建，不含新机器、MSRV、其他平台或完整打包分发声明。

## M6 milestone close (2026-10-28)

PKG-A 与宏支撑 A 实施后逐项对照 M6 退出条件（"干净环境可依文档构建、安装并完成代表性应用；不是公开发布"）：API 一致性（矩阵、易用性规则、rustdoc 与指南一致）、完整示例（42 个全部构建、指南索引）、文档与本地安装产物（含 sidecar 对照、release 安装与单依赖 consumer 交互）均有保留证据；两项分发决策已落地。先前评估的唯一缺口"干净环境"已于同日补齐：全新 `CARGO_HOME`（空 registry、按 lockfile 联网实下全部依赖）+ 全新 `CARGO_TARGET_DIR` + vendored protoc 依文档构建 quickstart 2m17s 成功，产物启动后健康检查 ok、真实 Chrome 页面渲染正确、**Include unknown** 复选框真实翻转、无异常（`clean-env-build.log`/`clean-env-browser-check.log`）。M6 据此关闭。

边界声明（关闭的一部分，不是遗留缺口）：全部证据为同机既有 rustup 工具链 + Windows/MSVC；新机器的 rustup 安装过程、MSRV、Linux/macOS 与系统运行库从未验证也不在本里程碑声明内（长期目标与 M7 范围另行处理）；无任何公开发布，crates.io 不在范围；维护者回归按 PKG-A 由完整源码交付承载。关闭质量门沿用本日已过的 fmt/Clippy(-D warnings)/186 项工作区测试/全部示例构建/1527 项冻结检查。

## Current M4 runtime-integration start (2026-10-28)

M4 运行集成启动，按"文档先行、参考测量先于实现"执行。指南新增设计草案章节（请求上下文/认证与用户信息/配置三块，明确标注未实现、拟议接口待确认）；首个切片选 st.context：参考应用 + 带 固定探测头 的原生 WS 采集器一次成功并冻结于 `tests/reference/reference-browser/context-headers/`（11 帧、两轮 rerun 报告逐字相同、清理干净），离线测试双向断言。实测设计输入：Python 反映全部握手头（无白名单），直连 ip 为 null，url/timezone/locale/theme 来自浏览器会话而非握手（原生连接下为空）——Rust 拟议默认白名单构成刻意安全偏离并已在指南与矩阵标注。矩阵 st.context 的 not_applicable 理由按实测重写（运行时自身终结浏览器连接，请求上下文存在），证据挂参考；实现状态仍为未实现，不冒称任何 Rust 能力。采集器首次运行的头部解码笔误发生在 trace 写出前，属采集器编程失误，修正后一次成功，无失败前缀保留。config.toml 注册表与 secrets 文件存储维持不适用；认证/用户信息切片待设计确认后推进。

## Current M4 request-context slice validation (2026-10-28)

用户确认拟议接口后实施首切片：新增 `request_context.rs` 模块（`RequestContext { headers, is_embedded }`、`RequestHeaderAccess` Standard/Selected/All，名称大小写不敏感匹配、暴露统一小写）；`StreamlitServer::with_request_headers` 构建器选择白名单，WS 入口按白名单捕获握手头、(重)连接时刷新；`SessionState` 持有头快照，`st.request_context()` 按调用即时生成（headers + 由 `st_embed` 查询参数推导的 is_embedded）。示例 `request_context.rs`（8590，默认白名单）演示并说明扩面方式。

验证：单元回归覆盖三模式白名单与大小写；真实 WS 回归以带凭据/探测头的原生握手双向断言——默认面只回 user-agent/accept-language/accept/origin/host（Cookie、X-M4-Probe、Sec-WebSocket-* 不泄漏），`All` 模式与冻结 Python 参考的头集合逐头一致（小写化为记录差异），同一连接第二轮 `st_embed=true` 后 is_embedded 翻转；真实官方前端两阶段采集（默认 URL 与 `?st_embed=true`）冻结于 `tests/browser/rust-request-context/`——Chrome 真实连接白名单头渲染、`is_embedded` false→true、无 stException，离线测试断言 manifest 与语义。矩阵 st.context 升 implemented/partial（129/53）。已知边界：url/locale/timezone/theme/ip 未实现（参考证明来自浏览器会话而非握手）、cookies 未设计、caption DOM 抓取因 testid 差异未纳入断言（is_embedded 由 code 文本直接证明）。M4 后续切片待推进。

第二切片（同日）：冻结的浏览器路径参考证明页面上下文由前端随每轮 rerun 的 `context_info` 上报（url/locale/timezone/timezone_offset/color_scheme/is_embedded），且 `?embed=true` 翻转 embedded 而 `?st_embed=true` 不翻转（三参数探针实测）——首切片从查询串推导 is_embedded 的做法被实测推翻并改为浏览器报告驱动。`RequestContext` 扩为七字段，`SessionState` 持有每轮 context_info；WS 回归以携带 context_info 的 rerun 断言全字段，双端浏览器采集均冻结并通过离线断言（真实前端填充全部页面字段、白名单不泄漏凭据）。采集器本批内两次修正（健康检查双斜杠、embed 参数语义）发生在冻结确立前，属采集器编程修正而非产品发现，无失败前缀保留。

## Current multiple-file upload validation (2026-10-28)

M3 输入切片：`file_uploader` 多文件模式。新增便捷构建器 `multiple_files()`/`directory()`（既有 `mode()` 保留）。双端冻结参考（[Python](../tests/reference/reference-browser/uploads-multi/README.md)/[Rust](../tests/browser/rust-uploads-multi/README.md)，同一采集器与输入，真实 Chrome 四阶段 load→双文件→移除一→清空）：报告 count 0→2→1→0、name/size/字节一致、chip 同步、无异常；wire 上 `multiple_files=true`、一条批量 `file_urls_request`（2 名）、逐文件 PUT、状态列表 `[alpha,beta]→[beta]→[]`、移除即 DELETE（收尾 DELETE 与停采竞态，断言只保证首个）。Rust WS 回归 `multiple_file_uploads_batch_urls_states_and_removal_semantics` 以带 XSRF 凭据的真实 HTTP PUT 复现同链并断言返回值与移除语义；`uploads` 示例（8591）承载单+多上传器。离线测试双向核对两份冻结数据。边界：目录选择器、`max_upload_size_mb` 超限、并发竞争、过期清理未测；采集器两次修正（chip testid、reference_version 字段）发生在冻结确立前，属采集器编程修正。

## Current upload size-limit and directory validation (2026-10-28)

M3 输入切片（续）：上传大小限制与目录模式。协议探针实测锁定 Python 1.66.1 服务端在 `server.maxUploadSize=1` 下对 2MiB PUT 答 **413**；浏览器参考（`uploads_limit_app.py`，`max_upload_size=1`）证明官方前端在 PUT 之前**静默拦截**超限文件（无上传请求、无 alert、报告保持 0），小文件正常。Rust：`UploadHttpError::TooLarge` 修正映射为 413（原落 500 分支，即真实缺口），新增 `StreamlitServer::with_max_upload_size_mb`（默认 200MiB）；WS/HTTP 回归断言 2MiB → 413、同 URL 小文件 → 204、存储未写入；Rust 浏览器采集与 Python 逐项对齐（[双侧冻结](../tests/reference/reference-browser/uploads-limit/README.md) + 离线双向断言，wire `max_upload_size_mb=1` 同值）。

目录模式裁决：锁定 Python 1.66.1 的 `st.file_uploader` 签名**无目录参数**（仅 `max_upload_size` 等），目录模式为 Rust 扩展。探针实测锁定官方前端对 `accept_directory` 正确渲染目录选择器（第三个 dropzone 的 input 带 `webkitdirectory=true`），但 CDP 注入文件经目录控件返回 0——完整目录流需真实 OS 选择器与 `webkitRelativePath`，headless 不可达；渲染已证、返回路径未证，如实不作为可用声明（探针日志在本地 `target/checks/m3-upload-limit/`）。超限 UI 文案（headless 下未见提示）与 Python 413 的响应体内容不作等价声明（仅状态码）。并发竞争与过期清理仍开放。

## Current upload concurrency and expiry validation (2026-10-28)

M3 上传边界收尾。协议参考冻结于 `tests/reference/reference-browser/uploads-lifecycle/`（`--server.disconnectedSessionTTL=3`）：并发不同 URL 双 204；并发同 URL 双 204 且最终恰为一次完整写入（冻结轮为 B 版本 22 字节，无混合）；断线超过 TTL 后 PUT **400**、DELETE **204**、未知会话 PUT 400；配置名与默认值（120 秒）与 Rust 既有 `with_disconnected_session_ttl` 同构。Rust 对照回归 `upload_concurrency_and_expired_sessions_match_the_reference`（1 秒 TTL）逐项复现，8 次连跑稳定。途中发现并修复既有 413 回归的读取竞态：被拒 PUT 的连接重置可能丢弃在途状态行（Windows RST 语义，Python 探针同样观测到中途 reset），客户端断言改为"送达的 413 或空中止"双形态，"不存储"作为更强保证保留。边界：单机、单会话、双写者；更高并发与多写者损坏窗口未测。

## Current fake-credential auth and user validation (2026-10-28)

M4 认证/用户信息切片。参考测量先行：实测 1.66.1 的 `st.user` 为映射代理（无属性访问、无提供方时 `to_dict()` 空、`tokens` 子代理存在）、`st.context.cookies` 无门控解析；冻结于 `tests/reference/reference-browser/user-cookies/`（原生 WS 带探测 Cookie，一次采集）。1.66.1 无本地认证 oracle，认证路径只能以 Rust 回归证明。

实施（按指南推荐，公共形态待用户追认）：`RequestAuthenticator` trait + `UserIdentity`（sub/name/email/picture/roles/extra → to_dict）+ 内置 `HeaderAuthenticator`（指定头读 JSON 假凭据，垃圾/缺 sub → 匿名）；`StreamlitServer::with_authenticator` 在连接建立时以**全部**握手头调用认证器（不受应用可见白名单限制），身份随会话存储、重连刷新；`st.user()` 返回 `UserView`（匿名/空 sub → 空映射，修复过默认空 sub 混入映射的缺陷）；`RequestContext::cookies()` 从白名单放行的 Cookie 头解析（默认不可见，刻意凭据安全差异）。示例 `auth.rs`（8592，假凭据 + cookies 白名单）。

验证：单元测试（认证器边界、cookie 解析、空映射基线）；WS 回归双向——带身份头连接 → sub/name/roles/claims 映射 + cookies 可见，无认证器/未带凭据 → 空映射 + cookies 不可见；同采集器 --url 对照采集冻结于 `tests/browser/rust-user-cookies/`（匿名映射与 cookies 解析与 Python 参考逐字一致），离线测试双向断言。采集器本批内两次修正（--url 分支误启动 Python、runtime 字段未参数化）经 trace 元数据核查发现并在冻结确立前修正。边界：假凭据仅本地/测试；OIDC tokens、真实提供方、令牌校验与权限边界未实现不冒称。M4 配置面整理仍待推进。

## Current runtime configuration surface validation (2026-10-28)

M4 配置面切片：无新旋钮、无行为变更——把 builder/环境变量已覆盖的全部运行项（地址端口、静态目录三级解析、会话 TTL、上传上限、头白名单、认证器、RUST_LOG）整理为指南「运行配置面」表格（默认值、设置方式、证据指针）。每个旋钮的生效证据沿用其切片冻结（uploads-lifecycle/uploads-limit/context-headers/user-cookies/static_assets），本批不制造冗余弱测试（途中撤回了一个绕过真实 start() 的自接线静态目录测试）。新增离线文档门 `test_config_surface_docs.py`：表格证据路径必须存在、`server.rs` 的每个 `with_*` 构建器必须入表、两个环境变量必须在册——配置面不得漂移。表格发现并修复：user-cookies 重采时被抹掉的两份 README 复原，证据列全部改为可验证相对路径。

M4 关闭评估：请求上下文（headers/页面上下文/cookies）、认证与用户信息（假凭据）、配置面均已交付并各有冻结证据；剩余不关闭原因——认证与 request_context 的公共形态**待用户追认**（8890ee1 批注）、`ip_address` 未实现（两条实测路径均为 null，无 oracle，属记录边界而非缺口）、真实 OIDC 提供方集成本远期。追认后 M4 可按退出条件（关键设计获确认、假凭据与隔离依赖验证、权限边界清楚——认证器为受信配置、HeaderAuthenticator 明示非生产身份源）关闭。

## M4 milestone close (2026-10-28)

用户于 2026-10-28 追认认证与 request_context 的公共接口形态，M4 按退出条件关闭。交付对照退出条件：请求上下文——`st.request_context()`（白名单握手头 + 前端每轮 `context_info` 页面上下文 + cookies 白名单访问），双路径冻结参考（context-headers 原生 WS、context-browser 浏览器路径）与 WS/浏览器回归；认证与用户信息——`RequestAuthenticator` trait（连接建立时以全部握手头调用）+ `HeaderAuthenticator` 假凭据 + `st.user()` 映射（匿名空映射基线实测对齐），user-cookies 参考 + 认证回归 + 对照采集；配置面——指南显式表格 + 离线文档门（`test_config_surface_docs.py`）。假凭据与隔离依赖验证：HeaderAuthenticator 明示非生产身份源，权限边界为"认证器是受信服务端配置"（应用侧仅见映射）。边界随关闭入档：`ip_address` 两条实测路径均 null（无 oracle，未实现不冒称）；OIDC tokens/真实提供方集成为远期独立决定；关闭质量门沿用本日已过的全部门。

## Current media playback parameters validation (2026-10-28)

M3 媒体参数切片（用户同日追认 M4 公共形态并关闭 M4，见上文关闭记录）。冻结 Python 参考 `tests/reference/reference-browser/media-params/`（原生 WS 六有效调用 + 非法字幕）：start/end 整秒截断（1.5→1）、loop/autoplay、autoplay 携带 `$$ID-<32hex>-None` 身份、`audio/x-wav` 实测**裸地址**（`audio/wav` 带 `.wav`）、VTT 字幕 → `.vtt` 媒体轨（URL 哈希含坐标）、非法字幕渲染框架 `StreamlitAPIException` 异常元素（消息/标记实测）且 run 以 0 结束。

Rust 实施：`AudioOptions/VideoOptions` 新构建器（start_time/end_time/loop_/autoplay/muted/subtitle）；`AudioElement/VideoElement` 携带参数并在 autoplay 时生成同形 id；`media::extension` 按 实测拆分 x-wav（裸地址）并新增 `text/vtt`；`subtitle_track` 做 VTT/SRT 校验与 SRT→VTT 转换（SRT 路径按参考规则实现、未实测）；非法字幕经既有 `AppException` 渲染同形异常（堆栈为 Rust 真实上下文行）。验证：WS 运行时回归（整秒截断、裸地址、$$ID 形状、字幕轨、异常元素）+ 同采集器 --url 对照（六元素字段逐项一致、**payload URL 逐哈希跨端一致**、异常消息逐字一致；autoplay id 与字幕 URL 哈希为记录的运行时身份差异）+ 离线双向断言。参考 app 两次修正（subtitles 需 VTT 文本而非 data: URL、转义损坏）发生在冻结确立前，属采集 fixture 编程修正。边界：SRT 转换、多音轨、YouTube/URL 输入、alt 未测。

## Current layout/streaming parameters validation (2026-10-28)

M3 布局/流式参数切片。冻结 Python 参考 `tests/reference/reference-browser/layout-params/`（原生 WS，逐 add_block/new_element 含块级字段）：expander `type=compact` → COMPACT、icon 透传；popover primary/help/disabled + use_container_width（块级 stretch）；tabs `default=` **接受标签**（索引实测抛 StreamlitValueError）→ `default_tab_index`；dialog width=LARGE 两段发射（`$$ID` + `is_open`）；status update 的 **None 清除 expanded** 语义；toast duration short=4/long=10/毫秒原值；spinner show_time 原生 WS 无可观测增量。

Rust 实施：`ExpanderKind`/`PopoverKind` 枚举与 `kind()/help()/disabled()/use_container_width()`/`default_tab()` 构建器；status 的 expanded 改 `Option<bool>`（初始置位、update 传则置/不传则清除，对齐实测）；TabContainer 携带 default_tab_index。验证：同一采集器 --url 对照——**14/14 块发射字段逐字一致**；WS 回归断言 COMPACT 类型、popover 全参数与块级 stretch、default_tab_index、status 三态与 None 清除；离线双向断言。记录差异：tabs 未知 default 标签 Python 抛错、Rust 日志忽略；spinner show_time 未提供。采集器三次修正（add_block 字段名/oneof 名/块级字段）发生在冻结确立前。边界：STEP expander、popover wrap、tabs 宽度、toast 容器内发射未测。

## Current columns parameters validation (2026-10-28)

M3 列参数切片。冻结 Python 参考 `tests/reference/reference-browser/columns-params/`（七组调用，逐块含块级字段）：容器 `scale 1.0/wrap true/justify UNDEFINED/align STRETCH`、gap 仅 SM/M/L 变化且**复制到每个列块**、列权重 **double 精度**（1/3=0.3333333333333333）、`show_border`/`vertical_alignment`。Rust 实施修复三处真实偏差：容器硬编码 `scale 0.0/wrap false`（且 columns 容器 justify/align 与普通容器不同——新增 `columns_flex` 形态）；权重 f32→**f64**；列块缺 gap 复制。另修正共享容器非默认对齐的枚举映射（Center/Right 此前错映 proto 序号；该路径未经测量，默认 Left/Top 不变）。验证：同采集器 --url 对照 **22/22 块逐字一致**；WS 回回归断言容器形态、f64 权重与 gap 复制；离线双向断言；`Gap/VerticalAlignment` 自 crate 根导出。边界：wrap=false、自定义列宽、嵌套、horizontal_alignment 未测。

## Current stability scenarios validation (2026-10-28)

2026-11-01 更正：本节历史 `PrivateUsage` 数值来自错位的 Windows 结构，实际读取峰值提交内存，不能视为当前私有内存或据此推断增量/增长趋势；工作集字段不受影响。原始快照与更正后的六相重测保留于 `stability.json`，见[采样器更正](#current-m5-memory-counter-correction-2026-11-01)。下面原记录保留为历史证据。

M5 稳定性批次：三个此前未测场景的可复现回归与测量（`streamlit/tests/runtime/stability.rs` + `tools/measure_stability.py` + [tests/performance/stability.json](../tests/performance/stability.json)，各 3 试次）：

- **大数据/容量**：同一 WS 会话单轮渲染 100k 行 + 50k×4 列两表与 200k 点图表数据集（帧 >1MiB，回归自带 ≤64MiB 大帧读取器），解码行数逐表断言，第二轮 rerun 复现。测量：整测试进程峰值私有内存 52 MiB（含夹具），两轮墙钟 ~2.4s——观测值非阈值。
- **长时运行**：单会话 300 轮 rerun + 11 次按钮触发，会话身份全程不变、计数精确落在 11、全部 FINISHED_SUCCESSFULLY；300 轮总墙钟 ~0.14s，峰值内存 ~2 MiB 增量（无随轮增长迹象，非泄漏证明）。
- **慢连接**：一个客户端读到一半停住（parked reader，未读载荷滞留 socket），同时另一会话全速跑完 20 轮（~12ms/轮），随后慢客户端排空并正常结束——每会话独立发送通道，慢读者不阻塞他人。

边界：单机 debug 构建、每场景单/双会话；吞吐、并发容量上限、真实网络延迟抖动、多小时级长时运行与泄漏证明不在本批；无 SLO。M5 保持未完成（媒体回收、会话容量等既有边界不变）。

## Current M7 kickoff validation (2026-10-28)

M7 全量验收启动批次（组合差分 + 文档核验 + 独立 Review）：

- **跨能力组合差分**：组合页 fixture [combined_app.py](../tests/reference/combined_app.py) 与 Rust 镜像示例 [combined.rs](../streamlit/examples/combined.rs)（8596）逐调用对应，同一采集器原生 WS 双侧各一次冻结（22 元素/26 帧，python `reference-browser/combined/`、rust `browser/rust-combined/`，manifest 哈希锁定）。离线差分 [test_combined_differential.py](../tests/reference/test_combined_differential.py)：kind 序列逐项相等、逐元素字段相等，仅两条既有约定归一化（Arrow 逻辑比较、generic vega accepted-A 承载差）；媒体内容哈希同字节同 URL 逐字一致。矩阵在 11 个被交叉的条目下挂 `m7_combined_differential` 证据。Python 侧 `st.bar_chart` 因锁定的 altair 在 Python 3.14 无法导入（既有记录），组合页两图均用显式 vega spec——与 CSV 参考同款处理。
- **文档核验扫描** [test_docs_consistency.py](../tests/reference/test_docs_consistency.py)（4 项，常驻离线门）：矩阵证据路径存在（生成器边界内）、指南/README 仓库相对链接可解析、示例注册与目录一致且指南「示例索引」覆盖全部 49 个示例（`**名称**` 形式匹配）、reference-browser 各链 README/manifest 一致（repo 绝对 stored_file 在 ROOT 校验）。扫描落地即修复真缺口：25 个有 manifest 无 README 的链补 README（按矩阵引用生成）、指南新增 49 项示例索引、总览 README 补 27 条链索引。
- **独立只读 Review**（Sol/high 档位 Explore 代理）：判定**有保留通过**——证据真实、归一化未放宽、抽查全部属实；两个阻塞项（本台账缺失、矩阵未挂 combined 证据 + 索引行悬空）已按审查意见补齐；建议项（stored_file 分支改在 ROOT 校验、示例索引改精确匹配）已采纳，其余建议（差分比较收窄盲区）记为后续增强。审查原文要点存档于本节。

边界：组合差分为单页单轮原生 WS（无浏览器 UI 层、无交互）；差分盲区（markdown element_type/wrap、vega theme、add_block delta_path 参与断言）经审查人工核对当前无差异，列为后续增强；M7 其余义务（全量差分矩阵扩展、最终文档核验、遗留清理）未完成，M7 保持开放。

## Current media/layout edges and session capacity validation (2026-10-28)

M3 收窄 + M5 边界批次。冻结 Python 参考 `tests/reference/reference-browser/media-more/`（四个此前未测边界）与 Rust 对照 **6/6 逐字一致**：st.video 的**直接 URL 输入**原样上 wire 不经媒体存储；**SRT 字幕**按参考转换为 VTT 轨（本批冻结对照暴露并修复 Rust SRT 校验器字节偏移写错、把合法 SRT 误判为非法的真实缺陷——重写为 `dd:dd:dd,ddd` 逐位校验）；`popover wrap` 进消息可选字段；`tabs width/height` 走块级 pixel 配置。新构建器：`VideoOptions::from_url/url`、`PopoverOptions::wrap`、`TabsOptions::width/height`。矩阵 st.video/st.popover/st.tabs 三条目 limitation 收窄并挂 `media-more` 证据。

M5 会话容量回归 `many_concurrent_sessions_hold_independent_state`：64 个并发 WS 会话全部完成各自 run、重连保持身份、计数互不串扰（0.09s）。媒体回收经查证为**进程全局内容寻址、会话过期不回收**——与 Python MemoryMediaFileStorage 同语义，属记录在案的设计事实而非缺口（roadmap M5 行已有"进程全局媒体无自动淘汰"）；不据此关闭 M5。

## Current M7 second differential and close evaluation (2026-10-28)

M7 第二组合差分链（交互流 + 真实浏览器 UI 层）：Python fixture [combined_interactive_app.py](../tests/reference/combined_interactive_app.py) 与 Rust 镜像 [combined_interactive.rs](../streamlit/examples/combined_interactive.rs)（8598），同一[采集器](../tests/browser/combined_interactive_capture.py)驱动真实 Chrome 六阶段交互（load → 上传两文件 → 勾选 → 选 b → 点表格首行 → Apply+toast）。双侧冻结（各 10 文件含截图/manifest）：**六阶段应用报告 JSON 值逐阶段一致**（代码块文本因双端序列化格式不同而字面不同——独立 Review 指出后如实改述）；DOM chips/checkbox/toast 同步、无异常、双 PUT、末轮 widget 状态集合 [cb,df,go,k,sel] 双端一致（离线对称断言）。审查确认采集器 baseline+变化轮询无静默造假通道。

独立只读 Review（Sol/high）：**有保留通过**——四项建议（措辞精确化、Rust 断言对称、台账补记、总览索引）全部采纳；记录项（Rust 镜像表格显式宽高/`select-row-2` 命名历史、逐帧校验为各端自一致）已入 README。

**M7 关闭评估（采纳审查结论）：现在不可关闭。** M7 退出条件首句"长期验收全部满足"为硬前置；当前 M3 矩阵 130 项 implemented 全 partial、M5 未关闭（吞吐/容量上限/多小时运行未测），无"前置未齐而关闭后续里程碑"的先例。推进排序：**M3 → M5 → M7 终批**；唯一替代路径是用户对剩余限制的显式确认（尚无该记录）。

## Current M3 partial inventory (2026-10-28)

M3 收窄前置：机器导出 130 项 implemented/partial 的精确剩余清单 [compatibility/m3-partial-inventory.json](../compatibility/m3-partial-inventory.json)（生成器 `tools/export_m3_inventory.py`，limitation 原文逐条携带，漂移门 `test_m3_partial_inventory_matches_the_matrix` 与矩阵强同步）。分桶（决策辅助、非状态变更）：**80 项含未测参数**（可本地双端测）、**12 项需外部源/环境**（YouTube/iframe/新机器/发布等）、**2 项 headless 不可达**（目录完整流等 Rust 扩展）、**36 项无未测声明**（纯范围/溯源描述，含 12 项空 limitations）。

范围确认问题已向用户提出（外部 12 + headless 2 定为已确认限制、80 项继续切片的混合路线为推荐），**未获答复**——按既定规则不做默认确认：130 项全部保持 partial 开放；下一步继续 80 项可测面的逐切片双端验收，外部源项与范围定格等待用户显式记录。

## Current widget creation-parameter validation (2026-10-28)

M3 可测面切片（widgets 簇，取自 80 项清单）。冻结 Python 参考 `tests/reference/reference-browser/widget-params/`（8 元素创建期 wire）与 Rust 对照 **8/8 字段一致**：number_input **float 路径**（format %0.2f、默认步长 0.01、无界 f64 哨兵 ∓1.797e308、整型 %d 无旗标）——本批修复两处真实偏差（float format 此前按注释留空、无界 min/max 此前发 0.0）；radio `index=None` 不发 default + `horizontal/captions`；text_area `max_chars/placeholder`（消息内）+ `height`（元素级）；multiselect `max_selections`。新增四组构建器与 WS 回归 `widget_parameter_edges_match_the_frozen_reference`；矩阵 st.number_input/st.radio/st.text_area/st.multiselect 四条目 limitation 收窄并挂 `creation_params_reference`；清单已再生成（漂移门同步）。on_change、format_func 往返与交互期行为留后续切片。

## Current temporal/slider creation-parameter validation (2026-10-29)

M3 可测面切片（temporal 簇）。冻结 Python 参考 `tests/reference/reference-browser/temporal-params/`（5 元素）与 Rust 对照 **5/5 字段一致——零实现改动**：date_input 显式 min/max、**未给边界时 value ±10 年窗**（2014/2034 实测）与自定义 format；select_slider 双端点范围默认（SELECT_SLIDER + 索引端点，min=0 省略）；time_input step 字符串化（"900"）与 24h 格式。既有 Rust 行为全部经参考确认而非修改。矩阵 st.date_input/st.select_slider/st.time_input 三条目收窄挂 `creation_params_reference`；清单再生成。离线断言含 min 省略等 wire 细节。边界：range date_input、交互期日历提交、on_change 未纳入。

## Current button/image creation-parameter validation (2026-10-29)

M3 可测面切片（buttons/images 簇）。冻结 Python 参考 `tests/reference/reference-browser/button-image-params/`（6 元素）与 Rust 对照 **6/6 字段一致**：按钮 `primary/icon/disabled` 透传；`download_button` 的 **URL 扩展名规则**实测——显式 file_name 取其扩展（`.txt`）、均缺省按内容推断（裸字节 `.bin`），消息仅带 url；`st.image` 列表输入合成单 `imgs` 元素、caption 逐条、同像素**共享内容寻址 URL**。Rust 新增 `st.images(ImageListOptions)` API；其余为既有行为经参考确认。矩阵 st.button/st.download_button/st.image 三条目收窄挂 `creation_params_reference`；清单再生成。边界：URL/path 图输入、use_container_width、点击交互流未纳入。

## Current chat/metric/progress parameter validation (2026-10-29)

M3 可测面切片（chat/metric/progress 簇）。冻结 Python 参考 `tests/reference/reference-browser/chat-metric-params/`（9 元素含 1 个 Python-only 异常）与 Rust 对照 **8/8 核心元素一致**。**三处真实偏差由差分暴露并修复**：① metric 无 delta 颜色 RED→GRAY；② delta=0 被当作负（DOWN+RED）→ NONE+GRAY；③ emoji avatar 被标 ICON→EMOJI（按 material 短码前缀判型）。新增 `progress_options(text)`；progress float overload 实测为 Python-only（0..1，25.5 触发框架异常 `[0.0, 1.0]`），Rust 维持整数面不冒称 float 等价——记录差异。proto 零值（DOWN=0/RED=0）在 MessageToDict 中省略，离线断言按此精确锁定。矩阵 st.chat_message/st.metric/st.progress 三条目收窄；清单再生成。边界：image/URL avatar、accept_file、非数值 delta 未纳入。

## Current slider/multiselect parameter validation (2026-10-29)

M3 可测面切片（slider/multiselect 簇）。冻结 Python 参考 `tests/reference/reference-browser/slider-multi-params/`（4 元素）与 Rust 对照 **4/4 字段一致——零实现改动**：datetime 滑杆显式 `timedelta(minutes=30)` 步长以微秒上 wire（1.8e9）、value/min/max 为 epoch 微秒浮点、格式 YYYY-MM-DD（datetime 亦然）；date 滑杆缺省步长一天（8.64e10）；multiselect 默认选择以选项索引 [1,2] 上 wire（与既有 max_selections 证据互补）。既有 Rust 微秒换算与索引默认全部经参考确认。矩阵 st.slider/st.multiselect 两条目收窄挂 `creation_params_reference`；清单再生成。边界：时间值 datetime 滑杆、midnight 缺省步长、搜索过滤交互、format_func 往返未纳入。

## Current json/badge/feedback parameter validation (2026-10-29)

M3 可测面切片（json/badge/feedback 簇）。冻结 Python 参考 `tests/reference/reference-browser/json-badge-params/`（6 元素）与 Rust 对照 **6/6 字段一致**：st.json 的 expanded=True 显式、**collapsed 缺省省略字段**（1.66.1 无 depth 参数，传即 TypeError——首采真实触发）；st.badge 的 icon/color 进 body、**wrap 字段缺省**——本批修复 Rust 误发 `Some(true)` 的偏差，且离线差分连续抓两次：显式 `Some(false)` 仍不等价于省略，终改 `None`；st.feedback 位置参数即 preset（options= 关键字冲突实测 TypeError）、disabled 进消息。矩阵 st.json/st.badge/st.feedback 三条目收窄（st.badge 原无 limitations，首次补测量记录）；清单再生成。边界：badge 宽度/帮助、feedback 交互提交、ignore 模式未纳入。

## Current recorder parameter validation (2026-10-29)

M3 可测面切片（录制控件簇）。冻结 Python 参考 `tests/reference/reference-browser/recorder-params/`（3 元素）与 Rust 对照 **3/3 字段一致——零实现改动**：audio_input 显式 sample_rate=44100 进消息；camera_input 默认拍照模式消息仅 label/label_visibility（无 capture 字段）。提交行为（真实麦克风/摄像头）headless 不可测，维持 pickers 链边界。矩阵 st.audio_input 收窄；st.camera_input 原无 limitations 首次补测量记录；清单再生成。

## Current text-family parameter validation (2026-10-29)

M3 可测面切片（文本族簇）。冻结 Python 参考 `tests/reference/reference-browser/text-misc-params/`（5 元素）与 Rust 对照 **5/5 字段一致**。修复两处真实偏差：`st.latex` 此前发普通 NATIVE markdown + wrap true（应为 **LATEX 类型 + wrap 缺省**）；`st.divider` 此前 wrap true（应缺省）——`MarkdownElement::wrap` 因此改为 `Option<bool>`，与此前 badge 修复共同确立"markdown 族各元素 wrap 语义独立实测"的规则。`st.help` 四字段（doc_string/name/type=callable 种类/value=完整签名）经参考对齐示例用法（Rust 显式 API 设计不变）；`st.text` 的显式 wrap true 为零改动确认。矩阵 st.latex/st.help/st.divider/st.text 四条目收窄（其中三条原无 limitations 首获测量记录）；清单再生成。

## Current code/skeleton/logo parameter validation (2026-10-29)

M3 可测面切片（code/skeleton/logo 簇）。冻结 Python 参考 `tests/reference/reference-browser/code-logo-params/`（3 元素 + logo ForwardMsg）与 Rust 对照 **3/3 元素 + logo 帧逐字一致——零实现改动**：`st.code` 的任意 language 标签透传（无白名单）与 `line_numbers→show_line_numbers`；`st.skeleton` 默认空消息；`st.logo` emoji 判型 EMOJI、**缺省 size "medium"**、顶层 logo 字段承载（非 delta，元数据仅 activeScriptHash）。矩阵 st.code/st.skeleton 两条目原无 limitations 首获测量记录、st.logo 在既有 emoji 链上叠加端到端确认；清单再生成。边界：code wrap_lines/height、URL/路径 logo、icon_image/link 未纳入。

## Current M5 throughput/capacity/sustained validation (2026-10-29)

2026-11-01 更正：本节历史“峰值私有内存”使用了误标的峰值提交内存字段；不能将其作为当前私有内存测量引用。原始数值保留，正确结构与当前六相重测见[采样器更正](#current-m5-memory-counter-correction-2026-11-01)。本次不重解释历史吞吐或正确性结果为当前版本结果。

M5 三场景批次（`tools/measure_stability.py` 扩至六相，[tests/performance/stability.json](../tests/performance/stability.json) 各 3 试次冻结）：

- **吞吐**（`throughput_reruns`）：单会话 200 轮持续 rerun（256 行表），**~509 rerun/s**、每轮 5,256 字节 Arrow 全部逐行解码正确；3 试次峰值私有内存 ~3 MiB。
- **容量上限**（`capacity_ramp`）：64→128 两级并发会话逐级放大，每级**全部会话完成 run**（128 级 3/3 试次全对，~0.56s/级）；峰值 ~8 MiB。未探到失败上限——本机文件描述符内 128 级全部正确，更高级别的真实失败点未测。
- **持续运行**（`sustained_window`）：**5 秒有界持续窗口**内 ~9,500 轮 rerun + 197 次按钮触发，计数精确、会话身份稳定（~1,900 runs/s）。**如实声明：这是有界持续窗口，不是多小时浸泡**——多小时级长时运行仍未测，M5 不据此关闭。

修正一处测试自伤（sustained_window 首轮按钮未注册时 bumps 计数先于交付——测试代码问题，产品零改动）。边界：单机 debug、单 worker；真实网络抖动、跨机分布式与真正多小时运行不在本批。

## M7 terminal-batch preparation status (2026-10-29)

M7 终批前置：范围确认问题已**第四次**向用户提交（M3 53 项含未测参数 + 12 需外部源 + 2 headless 不可达的处理路线；M5 多小时浸泡定格与否），**未获答复**——按既定规则不做默认确认，130 项 partial 与 M5 多小时全部保持开放，等待显式记录。

不依赖确认的终批要件本批完成核验：

- **最终文档核验**：矩阵全量一致性审计通过（182 条目、130 implemented 全部有证据、summary 与条目同步、清单与矩阵强一致）；指南/验收/roadmap 全部仓库相对链接解析；52 项矩阵进度门 + 4 项文档门 + 850 项采集检查全绿。
- **遗留清理扫描**：`streamlit/src`、`streamlit-macros/src`、`tools/*.py` 零 TODO/FIXME/XXX/HACK；`tools/` 五个脚本全部在册使用（inventory/stability 生成器 + 三个历史工具）；无死探针、无过期文档残留。
- **待确认后即可执行的终批剩余**：据用户答复定格或补测（M3 范围/M5 多小时）→ M7 关闭评估复核 → 最终独立 Review → 关闭记录。

## Current select/pills parameter validation (2026-10-29)

M3 可测面切片（selectbox/checkbox/pills 簇，范围确认未获答复后的最佳判断推进，不冻结任何项）。冻结 Python 参考 `tests/reference/reference-browser/select-pills-params/`（5 元素）与 Rust 对照 **5/5 字段一致——零实现改动**：selectbox 的 `index=None`（不发 default）+ `placeholder`/`help`/`disabled`；checkbox 的 `value/disabled/help`；pills multi 的 `MULTI_SELECT` click_mode、默认标签**索引化 [0,2]**、content 对象选项与 help。矩阵 st.selectbox/st.checkbox/st.pills 三条目收窄挂 `creation_params_reference`；清单再生成。边界：format_func、option icons、query binding、wrap、交互期行为未纳入。

## Required fresh-checkout checks

```powershell
python -m pytest tests/reference -q
cargo fmt --all -- --check
cargo clippy --workspace --locked --all-targets -- -D warnings
cargo test --workspace --locked
cargo test --workspace --locked --examples
```

The journey manifest is validated by the Rust `journey_ledger` integration test inside `cargo test`; the former `validate_journeys.py` was removed because repository tests live in Rust unless they must drive the pinned Python reference or a real Chrome.

The official docs cache is an ignored input under `target/upstream/docs`; when present, `tools/fetch_upstream.py` and `tools/verify_p0.py` can audit it and regenerate the two compatibility JSON files. These tools are optional local-cache checks, not fresh-checkout gates. `fetch_upstream.py --download` restores only the three locked archives and cannot reconstruct the captured catalog or HTML cache. If that cache is absent, do not run these two tools or claim that they automatically rebuild it.

## Gates

- Upstream artifacts and the documentation catalog match every hash in `upstream.lock.json`.
- The docs matrix has one row per captured canonical page with official URL, Rust plan, implementation status, compatibility status, and evidence links.
- A `partial` or `supported` compatibility status requires linked differential evidence. `supported` additionally requires API, wire, and official-frontend browser evidence.
- Failed or partial browser attempts retain their real artifacts and a failure reason; an unrun journey remains `not_run` with no attempt artifacts.
- No HTTP/WS differential failure is accepted. AppTest results are script-level oracle evidence and cannot replace wire evidence.

## Remaining first-release journeys

Read current whole-journey status, original assertions, `preparation_contract` actions and linked evidence from [the journey manifest](../tests/journeys/journeys.json); per-feature scope and limitations are in [the compatibility matrix](../compatibility/api-compatibility-matrix.json). `not_run` means unmeasured, not necessarily unimplemented. The original 10 journeys had 42 steps; J04-S4 was added later, making 43. These application journeys are not a complete feature denominator.

Product behavior follows official [widget semantics](https://docs.streamlit.io/develop/concepts/architecture/widget-behavior), [session state](https://docs.streamlit.io/develop/concepts/architecture/session-state), [uploader](https://docs.streamlit.io/develop/api-reference/widgets/st.file_uploader), [dataframe](https://docs.streamlit.io/develop/api-reference/data/st.dataframe), and [forms](https://docs.streamlit.io/develop/concepts/architecture/forms). Execution reference is Python Streamlit 1.66.1; CSV aggregates and literal messages are application contracts in the manifest.

For each whole journey, verify 100% of its original assertions, retain the required step screenshots and allow no unexplained missing artifacts or mismatches. Component tests, a positive raw, a screenshot or a manifest entry alone do not establish the complete journey. Preserve original expected results; do not change them or introduce hidden resets to turn a failing check green. If the reference contradicts a preparation or expectation, retain the failure and review the contract.

Perform the recorded preparations as real UI actions. Record before/after control values, target client state, successful request/completion windows on the same connection and resulting DOM/Arrow data. Each ordinary changed control requires one rerun and a runs delta of one; use the observed ledger for uploads and preparations rather than inventing a fixed total. Dependent recovery and counter steps must remain in the same session and preserve their request/completion evidence. In the two-session journey, verify A remains unchanged during B operations and B retains its session, upload and result when only A reloads.

J04-S4 requires a guarded rerun ending `FINISHED_EARLY_FOR_RERUN`, a server-triggered run on the same session with a fresh run ID, and `stop` ending successfully with later output suppressed. Both runtimes must reach the measured DOM end state. J09 requires recovery of uploaded data and counters in the same session, followed by reload reset; S4 requires a genuine disconnect of at least 135 seconds and the observed new-session/state-reset outcome. The frozen reference and Rust evidence remain linked from the manifest. Earlier component-only observations cannot replace these combined journeys.

## API and wire differential obligations

These 21 obligations replace the removed interface-diff metadata file. They are acceptance requirements, not a claim of Rust compatibility. The Python browser traces under `tests/reference/reference-browser/` are the wire oracle where marked; Rust progress must be assessed per obligation against equivalent black-box evidence and recorded in the current matrix.

| ID | Surface | Rust requirement | Reference evidence |
|---|---|---|---|
| A01 | st.file_uploader | the Rust uploader must return the uploaded bytes unchanged and must not raise on malformed CSV | golden `G01` |
| A02 | st.selectbox | the Rust selector must expose the same option set and initial selection; the returned value must be the selected option, never an index | golden `G01` |
| A03 | st.slider | the Rust slider must clamp and quantise identically, and the filter it drives must use >= on the amount, not > | golden `G07` |
| A04 | st.checkbox | the Rust checkbox defaults to on and its false branch must apply the same unknown-region rule as the oracle | golden `G02` |
| A05 | st.button | the Rust button must return a one-shot trigger value and cause exactly one rerun per click | reference run `REF-15` |
| A06 | st.form + st.form_submit_button | the Rust form must gate its children's values on an explicit submit, and must not clear the field on submit when clear_on_submit is false | reference run `REF-16` |
| A07 | st.dataframe | the Rust dataframe must emit the same column order, the same hidden index and an empty-but-present table for the empty case | golden `G01` |
| A08 | st.altair_chart / st.vega_lite_chart | the Rust chart must be omitted entirely in the empty case, matching the oracle's absent element rather than an empty spec | reference run `REF-03` |
| A09 | st.text / st.markdown | the Rust text element must carry the same literal content so that the browser journeys can assert on it | reference run `REF-01` |
| A10 | st.session_state | the Rust session state must be per-session, survive reruns and reject assignment to a live widget key | reference run `REF-15` |
| W01 | HTTP GET /_stcore/health | the Rust server must expose the same path and body. NOTE: this is an interface probe, not a UI pass. | Python browser trace `tests/reference/reference-browser/closed-loop/trace.json#/http_requests` |
| W02 | HTTP GET /_stcore/host-config | the Rust server must return the same JSON keys with the same defaults. NOTE: interface probe, not a UI pass. | Python browser trace `tests/reference/reference-browser/closed-loop/trace.json#/http_requests` |
| W03 | HTTP GET / and static assets | the Rust server must serve the official frontend unmodified, byte for byte. NOTE: interface probe, not a UI pass. | Python browser trace `tests/reference/reference-browser/closed-loop/trace.json#/http_requests` |
| W04 | HTTP PUT /_stcore/upload_file/{session_id}/{file_id} | the Rust upload route must accept PUT on that path shape, take the single uploaded file regardless of its field name, and answer 204 | Python browser trace `tests/reference/reference-browser/closed-loop/trace.json#/upload_contract` |
| W05 | HTTP GET /media/{file_id} | the Rust media route must mirror the upstream shape. This case is out of the P0 closed loop and is carried forward, not a UI pass. CLOSED 2026-10-25: the route serves the reference's content-addressed store (BLAKE2b-128 over `"{len}:"`+data+mimetype, >1MiB head/middle/tail sampling) with the measured 200/`accept-ranges` and 206/`content-range` shapes; the byte-identical WAV fixture is served under its exact measured address. Evidence: the journey-media-v1 chain (both replays 11/11/11) plus the runtime regression in `streamlit/tests/runtime/media.rs`. | [Python media trace](../tests/reference/reference-browser/media/trace-media.json) and [Rust media trace](../tests/browser/rust-media/trace-media.json) |
| W06 | WebSocket handshake GET /_stcore/stream | the Rust server must accept a two-entry subprotocol header on a fresh load, select 'streamlit', and return the session id in NewSession.initialize.session_id | Python browser trace `tests/reference/reference-browser/closed-loop/trace.json#/websocket_handshake` |
| W07 | WebSocket ForwardMsg lifecycle | the Rust server must emit the same message kinds and the same script_finished status value | Python browser trace `tests/reference/reference-browser/closed-loop/trace.json#/frames` |
| W08 | WebSocket BackMsg rerun_script and WidgetStates | the Rust server must treat one BackMsg as exactly one rerun and must not receive form children before a submit | Python browser trace `tests/reference/reference-browser/closed-loop/trace.json#/button_trace` |
| W09 | protobuf Element oneof names | the Rust proto must use the same oneof member names and numbers so the official frontend renders the elements | Python browser trace `tests/reference/reference-browser/closed-loop/trace.json#/frames` |
| W10 | protobuf WidgetState value encoding | the Rust server must decode each widget kind from the same field and must keep widget ids stable across reruns | Python browser trace `tests/reference/reference-browser/closed-loop/trace.json#/frames` |
| W11 | WebSocket reconnect handshake /_stcore/stream | on a socket-only reconnect, recover the retained session identified by the opaque third subprotocol entry; a page refresh uses a fresh two-entry handshake and new session. Unknown UUID and non-UUID IDs must start a new server-selected session, as measured by the reference probe. Rust two-worker HTTP/WS regressions cover these lookups and stale-owner Drop protection. The session core, controlled-await ownership boundary, and final Rust browser subset have independently passed review: retained same-ID recovery with a subsequent increment, fresh-ID reset, and two-tab isolation. Original-socket fate and upstream expiry policy remain separate gaps; this is partial evidence, not full takeover or security-handshake compatibility. | Python [reconnect handshakes](../tests/reference/reference-browser/reconnect/trace-reconnect.json#/websocket_handshakes) record the first connection closing and the second using a third subprotocol entry with the same session ID; [post-reconnect observations](../tests/reference/reference-browser/reconnect/trace-reconnect.json#/steps) show Pulses 2 retained, then 2→3 with a successful server response on the new connection. Python [refresh handshakes](../tests/reference/reference-browser/refresh/trace-refresh.json#/websocket_handshakes) are the separate fresh-load reference; [Rust S1 observations](../tests/browser/rust-counter-s1/trace-counter.json#/steps) record the measured Rust subset. |


### Disabled widget inputs, callback order and malformed recovery (2026-10-30)

用户明确选择错误类型提交时保留 Python 错误、已发生 callback 和下一轮恢复，不采用整批拒绝或静默忽略。固定 Python 1.66.1 app 与原生 WS collector 新增 `disabled-valid`/`disabled` 两个独立九轮场景，保留原始 base64、protobuf、时间和服务日志；没有覆盖旧参考。正确类型分支覆盖普通/绑定 text_input、selectbox、checkbox、Live 正常输入、代码赋值、无效 URL、条件隐藏/重挂载和双向 disabled 切换。错误分支提交 bool oneof 给禁用 selectbox：Plain 已发出，Live callback 已执行，注册处 TypeError，缺少本轮其余控件和报告，成功结束后同连接恢复。修前正确类型回归已失败，保留本地 `target/query-disabled-red.log`。

Rust 内部 WidgetSpec/Record 记录 disabled 与输入前值，callback 取上一轮策略，当前禁用注册恢复值；已测 bool/select 错误延迟到注册呈现一次 TypeError，错误轮保留未渲染记录及已发生的 callback。普通启用控件的既有整批验证策略未宣称全面 Python 兼容。无新增公共接口或依赖；两个场景分别按顺序比较 58 与 52 个控件/URL/状态/异常事件。异常比较包括类型、消息、顺序和标志，Python 的来源栈帧保留为参考，Rust 不伪造栈路径；完整错误 UI 尚未验收。

最终按代码→单元→集成验证：格式/全目标 Clippy（`-D warnings`）通过；控件单元 12 项、查询参数真实 WS 回归 12 项通过。`cargo test --workspace --offline --locked` 共 223 项通过（库 216、ledger 1、宏 2、rustdoc 4），日志 `target/query-disabled-workspace-final.log`；相关 Python 参数/metric 参考、矩阵与文档门 103 项通过，日志 `target/query-disabled-gates.log`。逐文件复查本批 Rust diff，保留既有 MSVC linker stdout 告警。参考采集器和测试自有服务关闭。最后仅补充字段注释、语义空行与验收文字，未改变通过验证的行为；未重复执行全部 Python 参考套件、全部示例测试或真实浏览器操作。矩阵仍 130 项 partial，其他错误类型/控件、跨页、绑定服务端重跑与浏览器错误界面继续开放，M3/M5/M7 和长期 Goal 不关闭；无提交、推送或发布。


### Bound server rerun evidence and pending queue expansion (2026-10-30)

五个原生 WS 请求各引起一轮早结束与一轮成功结束，`queryparams/rerun/trace.json` 固定 47 个事件（12 URL、15 JSON、10 控件同步投影、10 finish）。修前 `target/query-rerun-red.log` 失败；状态修复后该差分通过，控件单元 14、当时查询集成 13 和执行集成 6 项通过，代码 Clippy 通过，相关 Python/矩阵/文档门当时 104 项通过。修复延续内部重跑的前端/代码优先级、未渲染控件与绑定，并从最近公布 URL 重建状态。新增真实 Rust WS yield 回归确认已发 Delta 保留、后来排队 Delta 丢弃。普通 rerun 仍不重放 callback。

工作区随后发现导航回归失败（库 219 通过、1 失败，日志 `target/query-rerun-workspace.log`），因此本批未达到工作区全绿。独立使用既有导航 fixture 捕获 `navigation-rerun/trace.json`，证实旧轮未发送 Navigation 也被 Python 清理；进一步捕获冷调用 `rerun-messages` 与预热 `rerun-queue`，保留两个真实发送窗口。后者明确保留 toast、URL 和生命周期帧，清理未发 PageConfig/普通 Delta；当前获准的 Delta-only Rust 逻辑会误丢 toast、误留 config，真实差分 red 日志 `target/query-rerun-queue-red.log` 保留。原始数据未改写转绿。三份新增数据与此前查询参考的逐帧 Python 门共 36 项通过（`target/query-rerun-additional-python-final.log`）。

需要用户进一步决定：按锁定版本完整生命周期/toast 保留表扩展（推荐）、仅针对 Navigation/toast 最小扩展，或保留当前已知差异；该问题已通过 async 提出，目前尚未收到此次扩展选择。不是重复询问旧 Delta-only 方案，而是新发现消息类型与例外。推荐实现只需修改 handler 队列判断，测试已经具备具体原始期望，执行后须重新完成 Clippy、单元、相关集成与工作区回归；在决定前不擅自扩大发送规则、不报告本批完成或暂停整个 Goal。已有用户修改保留，无提交/推送/发布，M3/M5/M7 和完整兼容目标开放。


### String avatar aliases/URI typing and Unicode JSON (2026-10-30)

在发送队列扩展尚待用户选择期间，独立处理既有 ChatMessageOptions 字符串接口。官方 chat_message 文档（当前标注 1.66.0）定义默认头像、emoji 和图像输入；锁定 Python 1.66.1 的独立原生 WS 记录 `chat-metric-params/string-avatars/trace.json` 含 28 组输入：15 个无显式头像的名字与 13 个显式字符串。保留一次输入 JSON、28 个聊天 block 和 28 个子文本，旧 trace 均未改。修前真实 Rust WS 失败保留在 `target/chat-avatar-red.log`。

修复默认 name 大小写预设与 human/ai 别名、普通名字空 ICON avatar、emoji 名字 EMOJI，以及 HTTP(S)/PNG-SVG data URI/静态 URI 的 IMAGE 类型与字符串原样保留。现有 emojis 依赖复用，没有新增公共接口、依赖或图片加载流程。Rust 回放固定输入报告作为用例数据，输出期望独立取原始 block/element 帧；57 个有序投影比较 name/avatar/type、allow_empty/stretch、完整路径、子文本、输入 JSON 内容与默认 expanded。URI 仅编码验证，不宣称远程图片已加载、静态文件已提供或浏览器显示通过。

该回归进一步真实复现非 BMP JSON 编码损坏，日志 `target/chat-avatar-integration.log` 保留：pywire 将一个 Unicode 标量写成五位转义，解码后变成其他字符。改用 encode_utf16 逐码元输出，单元覆盖普通/compact/pairs 的 JSON 值、对象键、emoji/ZWJ/VS 及 U+10000、U+10FFFF 边界，并校验 JSON 解析恢复。固定报告还确认默认 expanded=True，现修正 st.json 默认值，显式 json_expanded(false) 不变。原 JSON 深度说明已校正：独立 depth= 关键字不受支持，但官方文档和锁定 runtime 的 expanded=int 确实存在；Rust 整数深度仍未实现，不能据旧关键字报错宣布不适用。

验证顺序为代码/全目标 Clippy（-D warnings）、序列化 4 项与头像 1 项单元，再聊天真实 WS 2 项（包含 57 个投影）通过。`cargo test --workspace --offline --locked -- --skip server::tests::navigation::navigation_pages_switch_and_session_state_match_the_measured_wire --skip server::tests::queryparams::rerun_queue_messages_match_frozen_reference` 通过 229 项（库 222、ledger 1、宏 2、rustdoc 4），日志 `target/chat-avatar-workspace-remaining.log`。仅显式排除两个发送规则待决的已知 red 回归，不是完整工作区全绿，也不接受这两项差异为最终目标；相关 Python/参数/矩阵/文档门 110 项通过（`target/chat-avatar-gates.log`）。逐文件复查本批 Rust diff，rustfmt/diff 检查通过，既有 MSVC linker stdout 告警保留。

最终仅更新说明与字段断言，无行为再改。参考及测试自有进程/连接均已关闭，没有重新执行完整 Python 参考套件、全部示例测试或浏览器显示。图片字节/本地文件与异常、完整 emoji catalogue、头像宽度、JSON 整数深度/宽度/字符串输入和浏览器交互继续开放；矩阵 130 项 partial 不变，队列扩展待决、M3/M5/M7 和完整兼容 Goal 保持开放。无提交、推送或发布。


### JSON top-level strings and raw evidence guards (2026-10-30)

`json-badge-params/strings/trace.json` 是复用既有 app/collector 的独立固定 1.66.1 原生 WS 捕获：一次输入报告、15 种字符串各默认/显式折叠两次，以及对象、数组、null、布尔与整数五种结构化对照，共 36 个 Json 元素。字符串覆盖对象/数组/标量文本、实际空白换行、引号、空串、Unicode、错误/多文档文本，以及字符串 NaN/Infinity（不是原生 float）。即使已测文本不能解析成单一 JSON，服务端仍原样发送并成功结束；不把此结果当作前端解析或错误 UI 通过。旧参考未修改。

真实 Rust WS 修前失败保留于 `target/json-string-red.log`。现有 json_expanded 只在 serde Value::String 分支直接传递文本，非字符串仍 py_dumps，嵌套字符串仍转义；json 直接复用 json_expanded(body, true)，没有新增公共签名、依赖或预解析流程。公共 API 单元经真实消息通道覆盖 &str、String、Value::String 和嵌套对象；WS 对照完整 Json 载荷（body/expanded/max_expand_depth）、完整路径及 stretch 标志，36 项一致。旧公开 rustdoc 的 collapsed 默认描述一并校正。

同时加强 JSON 原始证据门：原 test_json_badge_params_reference 定义解码生成器但主比较未绑定原始帧，现在原 Python/Rust 与新记录均核对方向、base64 长度、protobuf 解码消息、元素摘要及结束状态；七个摘要/原始消息损坏 guard 均拒绝异常输入，正确历史数据继续通过。README 仅纠正显式 False 被误写成默认和 depth= 与 expanded=int 的混淆，并记录说明；没有修改正确原始帧或源 SHA 验收口径。

按代码→单元→集成验证：全目标 Clippy（-D warnings）通过；公共接口单元 1 项、文本真实 WS 2 项通过。工作区命令沿用精确排除两个待决队列回归的范围，`cargo test --workspace --offline --locked -- --skip server::tests::navigation::navigation_pages_switch_and_session_state_match_the_measured_wire --skip server::tests::queryparams::rerun_queue_messages_match_frozen_reference` 共 231 项通过（库 224、ledger 1、宏 2、rustdoc 4；`target/json-string-workspace-remaining.log`）。这不是完整工作区全绿，已知 Navigation/toast/config 队列差异未擅自接受或修复。相关 Python 参数/矩阵/文档门 118 项通过（`target/json-string-gates.log`）。逐文件检查 Rust diff；最终仅补步骤注释、整理 Python import 与验收说明，行为未变，格式/diff 检查通过；保留既有 MSVC linker stdout 告警。

参考与测试自有进程/连接关闭，已有用户修改保留，无提交/推送/发布。本批未运行全 Python 参考套件、全部示例测试或实际浏览器。JSON 前端解析/展开/错误 UI、整数展开深度、宽度、自定义序列化失败和特殊原生数值等继续开放，矩阵仍 130 项 partial，M3/M5/M7 与完整兼容 Goal 不关闭。


### Live Chrome JSON string rendering and disclosure (2026-10-30)

本批独立于仍待决的发送队列流程。复用既有 json_badge_params 示例和 Python fixture：增加 `?case=strings&sample=0..14` 单例路径，`collapsed=true` 选择初始折叠；没有 sample 的完整字符串场景和普通默认六元素场景保留。示例经 `cargo clippy -p streamlit --example json_badge_params --offline --locked -- -D warnings` 与构建通过（`target/json-ui-clippy.log`、`target/json-ui-build.log`）；再以原采集器 --scenario strings --url 模式保留 `tests/browser/rust-json-badge-params/strings/trace.json`，全部 36 个原生 WS Element 载荷与路径和固定 Python 参考一致。

随后通过 Browser Use 的真实 Chrome 扩展标签页操作官方前端，未用 native WS 冒充浏览器：两端各留 22 个有序观察（15 个字符串默认显示、对象/数组各 initial-collapse→实际点击 expand→实际点击 collapse 三阶段、最终 Unicode 复核）。主内容文本、解析警告、JSON 文本、展开图标、键与子行数全部一致。空串、错误和多文档文本在已测窗口显示 Json Parse Error；合法标量及字符串 NaN/Infinity 在上游组件中显示 ERROR 对象，这一真实行为原样保留。每端九张 JPEG 及字节数/SHA256、完整 DOM/组件 HTML、URL 与阶段信息分存于 `tests/reference/reference-browser/json-badge-params/ui` 和 `tests/browser/rust-json-badge-params/ui`。`collapsed` 字段是初始请求选项，点击后的实际状态由图标/文本/行数证明。

最终观察时读取的 console buffer 各保留八条同文 `react-json-view error: src property must be a valid json object`；不能报告零 console 错误，也不按每个导航窗口强行归因。两个任务创建标签页关闭后，经受控 Ctrl-C 终止自有服务；Python 在关闭阶段出现 Windows Proactor pipe ConnectionResetError，已单独记入 cleanup，不作为观察过程的应用错误。工具确认两个服务 session 终止，8604/18604 无监听。未读取其他用户标签页或改变浏览器设置。

离线门核对两个 22 阶段序列、精确本地 URL、可见 JSON/警告/图标/键/行数、全部 JPEG 的真实解码/尺寸/长度/哈希、两端语义差分和示例 36 个完整原生载荷；七项损坏 guard 拒绝缺阶段、错 URL、伪造文本/图标、图片哈希、警告及 Unicode 破坏。相关 Python 参数/矩阵/文档门 129 项通过（`target/json-ui-gates.log`）。这些门复核保存的浏览器数据，本身不会重新启动 Chrome；采集是本次实际 Browser Use 编排，未新增独立 CI 浏览器驱动。当前库代码未改，未无故重复已通过的库单元/工作区回归；该既有回归的两个待决队列排除项仍明确开放。本批逐文件复查示例 Rust diff，格式/diff 检查通过，既有 MSVC linker stdout 告警保留。

只补齐所列字符串和两个根级 disclosure 往返；整数展开深度、更深嵌套、其他宽度/主题/响应布局、更广输入/序列化失败及全量自动浏览器验证仍未完成。矩阵仍 130 项 partial，M3/M5/M7 与完整兼容 Goal 保持开放，队列扩展未越过用户决策；无提交、推送、合并或发布。


### Logo strings, JSON depth references, and branch checkpoint (2026-10-30)

Logo 自动字符串分类使用现有 emoji 数据表识别完整序列，覆盖 ZWJ、旗帜、肤色、键帽与 variation selector，保留 Material 与 URI 分类。固定 Python 参考的 18 组 Logo 六字段和元数据经生产 WebSocket 对照；修复前 9 组不一致，修复后通过。JSON expanded/width 新参考覆盖 18 组输入，9 接受、9 拒绝；保留 False 与整数 0 的深度字段差异、int32 边界和宽度错误。这部分仅为参考，未擅自新增公共接口，JsonOptions 设计仍待用户选择。

当前验证：Logo 单元 1 项、display2 生产 WS 2 项通过；workspace/all-targets clippy -D warnings 通过，保留既有 MSVC linker stdout 告警。工作区测试在明确排除 navigation_pages_switch_and_session_state_match_the_measured_wire 与 rerun_queue_messages_match_frozen_reference 两项已知队列差异后共 233 项通过（库 226、ledger 1、宏 2、rustdoc 4），日志 target/logo-strings-workspace-remaining.log。相关 Python 原始帧、损坏 guard、矩阵与文档门共 139 项通过（target/logo-depth-gates.log）。这不是完整工作区全绿；Navigation/config/toast 的更广队列策略仍待用户决定，当前仅实施已批准的未发送 Delta 丢弃。

用户已授权定期提交并推送。显示行为与证据单独提交，查询状态和两项已知差异以明确 WIP 的工作分支检查点保存；不视为合并或发布验收。独立 colconfig_params 示例、采集器、捕获目录以及 Cargo/索引改动保留在工作区，不纳入本次提交。矩阵仍 130 项 partial，完整兼容目标继续开放。


### Finite JSON numeric notation and nonfinite evidence (2026-10-30)

在现有 JSON 示例、fixture 和采集器加入 numbers 场景。固定 Python Streamlit 1.66.1 原生 WS 记录位于 json-badge-params/numbers/trace.json（19 个文本输入，每个标量/数组输出，加报告共 39 个元素）；Rust numbers-before 保留修复前 8 组有限值和 3 组非有限值差异。共享 pywire 的普通、compact、pairs 数字写入修正指数符号、两位补零和 1e-5 的记法，整数不变。Rust numbers 新记录的前 33 个报告/有限值完整载荷、路径、伸展宽度与参考一致；NaN、Infinity、-Infinity 的六个 null 差异仍保留，不视为完整兼容。

按代码、单元、集成顺序验证：workspace/all-targets clippy -D warnings 通过（target/json-numbers-clippy.log）；pywire 单元 5 项通过（target/json-numbers-unit.log）；文本/JSON 生产 WS 集成 3 项通过（target/json-numbers-integration.log）。现有运行共享编码的工作区回归在明确排除两项已知队列差异后 235 项通过（库 228、ledger 1、宏 2、rustdoc 4；target/json-numbers-workspace-remaining.log），并非完整工作区全绿。相关 Python 原始帧/字段/路径/宽度/矩阵/文档门 140 项通过（target/json-numbers-gates.log）。保留既有 MSVC linker stdout 告警；本轮 rustfmt 已按项目 edition 2024 运行，并逐文件检查改动。

采集器停止自有 Python 服务，两次自有 Rust 服务 session 均终止，8604 无监听。没有浏览器数值渲染验收、公共接口或依赖变更；非有限值在 to_value 前的信息保留方案需另行确定，自定义序列化失败、任意精度/舍入、更广数字和其他未测能力仍开放。矩阵仍 130 项 partial；用户已有 colconfig_params 改动保持独立，不纳入本批提交。此批将按已授权工作分支提交并推送，不合并或发布。


### JSON mapping keys, serialization warnings and failure recovery references (2026-10-30)

扩展现有 JSON fixture/collector，未修改生产序列化流程。Python serialization/trace.json 固定 17 组输入：13 成功、4 捕获异常、5 条 warning，加报告与 repr 次数共 37 个元素。门逐帧解码绑定摘要，核对完整有序 body、JSON/alert 宽度、路径、结束标志和 cleanup。重复文本键必须逐字保留，不经普通 dict 合并；七项损坏 guard 同时修改原始 protobuf 和相应摘要，通用帧校验仍通过后，语义门拒绝重复键折叠、非有限键改变、warning 格式、递归 skipkeys、错误类型、恢复值和重试次数错误。保留正确原始记录不改写。

现有 Rust JSON 示例增加独立 serialization 诊断，必然错误的自定义 Serialize 和 None-key BTreeMap 前后均发标记。生产原生 WS serialization-before/trace.json 仅五个报告/标记元素、finish=0，没有两份失败输入的 JSON，也无 alert/exception。它证明当前静默丢弃并继续，不是与 17 个 Python 输入同场景比较，不接受该差异。固定失败证据门不会要求将来的运行实现保留错误行为。未把 Python 专用 repr、集合一般顺序或循环引用映射伪称为 Rust 已支持。

示例代码检查 cargo clippy -p streamlit --example json_badge_params --offline --locked -- -D warnings、构建及 rustfmt edition 2024 检查通过，保留既有 MSVC linker stdout 告警；日志 target/json-serialization-example-clippy.log 与 target/json-serialization-example-build.log。JSON 门 32 项通过，最终相关 Python 参数/原始证据/矩阵/文档门 149 项通过（target/json-serialization-final-gates.log）。本批无库代码修改，未重复上一批已验证单元/工作区回归；上一批 235 项通过仍带两个已知队列排除项，不能报告本次全工作区全绿。

Python 采集器关闭 WS 并停止自有服务，Rust 自有服务 session 终止，8604 无监听；未运行本批浏览器 UI。内部文本序列化器/值树/暂缓三项流程取舍已请求用户决定，并在 architecture 中写清拟改文件、影响和验证；尚未收到答复，未实施新序列化流程、公共接口或依赖。JsonOptions 与发送队列两项既有取舍仍待决。矩阵 130 项 partial 和完整目标继续开放，colconfig_params 独立工作区改动不进入本批阶段提交。


### Code string boundaries, language and valid dimensions (2026-10-30)

既有 code_logo_params fixture/example/collector 新增 code-text 场景，Python 1.66.1 参考为 27 个代码调用及一份输入报告（28 元素）。13 类字符串覆盖空/单/多 LF、缩进、空格、CRLF/CR、制表符、Unicode 空白和中文/emoji；轮换任意/大小写/空/单空格语言、行号与自动换行，覆盖 stretch/content/正像素宽高的全部九种组合。Python language=None 的最终调用在 Rust 中用现有空字符串入口表达纯文本效果，不新增 Option 接口。

修前 code-text-before 原始记录保留 23 个代码元素载荷差异；宽高、其他字段和路径经原始帧对照原本已一致。CodeElement 现直接修改现有 String，各去掉一次开头/结尾 LF，保留其他字符，并把空语言规范化为 plaintext。没有改变公共接口、依赖或布局映射。修后 code-text 捕获的全部 28 个完整 Element、路径与尺寸配置匹配参考；生产 WS 测试独立读取固定输入与原始消息投影作全载荷比较。八项 guard 同时修改原始 protobuf 与摘要，通用帧检查通过后，语义门仍拒绝 LF/CR、语言、尺寸与开关破坏。正确和失败捕获均未覆盖或改写；证据目录沿用 -text 并为 Rust 该目录允许 CR-at-eol，保留采集字节。

按代码、单元、集成顺序检查：全工作区/全目标 Clippy -D warnings、Rustfmt edition 2024 通过；代码元素单元 2 项、文本/JSON 生产 WS 集成 4 项通过（target/code-text-clippy.log、target/code-text-unit.log、target/code-text-integration.log）。工作区明确排除既有 navigation_pages_switch_and_session_state_match_the_measured_wire 与 rerun_queue_messages_match_frozen_reference 后 238 项通过（库 231、ledger 1、宏 2、rustdoc 4；target/code-text-workspace-remaining.log），不是完整工作区全绿。相关 Python 参数/原始帧/矩阵/文档门 159 项通过（target/code-text-final-gates.log）。既有 MSVC linker stdout 告警保留；已逐文件检查 Rust 和脚本 diff。

采集器停止自有 Python 服务，两个自有 Rust 服务 session 均终止，8607 无监听。未执行本批浏览器语法高亮、滚动或响应式布局验收；非字符串 body 转换和无效尺寸错误等仍开放，st.code 与总矩阵仍 partial（共 130 项）。inventory 仅如实补出原缺少明确差距的一项，未通过改分母关闭能力。序列化、JsonOptions 和发送队列待决流程均未扩大实施。已有 colconfig_params 文件、Cargo 与索引改动保留，不纳入本批阶段提交和推送。


### Actual code-height reruns and frontend identity fix (2026-10-30)

既有 code_logo_params fixture/example 添加 code-live 场景：三个 checkbox 控制固定 360 像素宽的 20 行 Python 代码的 120/240 高度、自动换行及行号。实际 Browser Use Chrome 复现 Rust Tall/all-enabled caption 已为 240、代码区域仍为 120；修前十个控件观察及三张 JPEG 保留在 rust-code-logo-params/ui-before。原生三请求参考与修前记录均证明高度载荷为 120→240→120（18 元素、三次成功 finish），但 Rust hash 为 A/A/A，Python 为 A/B/A。捆绑前端 applyDelta 按 elementHash 复用旧 Element，与 cacheable=false 独立，故不能用完整帧已发送推断布局已更新。

最小改动只把 height 加入 CodeElement 既有 hash。单位测试和同连接生产 WS 验证 A/B/A，修后原生完整 code 载荷和所有元素摘要（排除运行时 widget id）匹配参考；没有启用消息缓存、改发送流程或新增公共接口/依赖。修后新建真实浏览器 tab 重新完整操作：十次有序控件观察与 Python 的 caption、checkbox、几何、滚动区尺寸、文本/高亮 token、行号及 white-space 一致，真实滚轮可在代码区下滚并回到零。Python 留 13、Rust 留 14 个观察（后者下滚第一次尚为零，多留一份稳定观察），不把动画中间偏移声称逐帧一致；正确两端各六/七张 JPEG，加修前三张共 16 张，均验证字节/哈希/真实解码/裁剪尺寸。九项损坏观察 guard 被拒绝，正向 UI 门也明确拒绝原高度失败；这些门只重放保存材料，不伪装为自动启动 Chrome 的 CI 驱动。

一次采集方式错误保留在 height-rerun-metadata-before：我误用约定为 Rust 的 --url 模式连接自有 Python 服务，导致 runtime 元数据误标。正确原始包与错误字段未覆盖修改，门会拒绝将其当 Python 参考；随后使用采集器自有 Python 模式生成正确新参考。独立失败记录不计入已通过跨运行时证据。两个成功标签页本次读取的 warn/error 缓冲为空，非全时段零错误断言。全部三个任务 tab 和自有 WS 关闭，先后两个 Rust server session 与 Python session 均终止，8607/18607 无监听；本轮关闭未观察到上一 JSON 批的 Proactor 异常。

按代码→单元→集成顺序：全目标 Clippy -D warnings、格式检查通过；代码元素单元 3 项、文本/JSON 生产 WS 集成 5 项通过（target/code-height-clippy.log、target/code-height-unit.log、target/code-height-integration.log）。工作区仍明确排除 navigation_pages_switch_and_session_state_match_the_measured_wire 与 rerun_queue_messages_match_frozen_reference，240 项通过（库 233、ledger 1、宏 2、rustdoc 4；target/code-height-workspace-remaining.log），不能称全工作区全绿。最终相关 Python 门 174 项通过（target/code-height-final-gates.log），已有 MSVC linker stdout 告警保留。逐文件复查 Rust/采集器/fixture diff，最后仅补语义空行和说明。

范围只覆盖当前视口/主题、固定宽度和这段 Python 代码；其他语言、尺寸/主题/响应布局、复制按钮、非字符串和无效尺寸继续开放，矩阵仍 130 项 partial，完整目标不关闭。三个既有流程选择未越过用户决定；用户已有 colconfig_params 文件/Cargo/索引改动保持独立，阶段提交仅含本批实现与证据。


### Code body/language field-boundary identity fix (2026-10-30)

同一代码元素的 left_right/python 与 left/right_python 在旧下划线拼接下得到相同身份。新三轮原生参考、修前和修后记录各 12 元素、三次成功 finish，载荷均正确，hash 从修前 A/A/A 改为 A/B/A。真实 Chrome checkbox 操作复现修前 caption 已改而代码正文/语言仍为旧值；三个失败状态及 JPEG 保留。修后新 tab 的 initial→alternate→restored 三状态与 Python 正文、语言 class、caption、checkbox 和尺寸一致，固定布局 360×120；未知标签只证明该样本的原样传递/纯文本回退，不证明一般语法支持。

最小修正只把 code.rs 七个现有身份字段编码为带字符串边界/转义的 Debug 元组，继续用原 MD5 算法、既有字段和传输；无新文件模块、依赖、公共接口或缓存流程。单元覆盖下划线、引号、Unicode 反例；真实同连接 WS 覆盖切换与恢复，原高度往返回归仍通过。Python/修前/修后共九张 JPEG 的字节/哈希/解码/裁剪尺寸和原始 protobuf 均检查；七项损坏观察 guard 被拒绝，正确 UI 规则会拒绝保留的旧正文失败。Python 初次截图请求超时发生于任何控件输入之前，仅重新观察同一 tab 并重取截图，未重放按钮/任务，collection_notes 保留这一过程。

代码→单元→集成顺序检查：全目标 Clippy -D warnings、格式检查通过；代码元素单元 4 项、文本/JSON 生产 WS 6 项通过（target/code-identity-clippy.log、target/code-identity-unit.log、target/code-identity-integration.log）。工作区明确排除两项既有队列差异后共 242 项通过（库 235、ledger 1、宏 2、rustdoc 4；target/code-identity-workspace-remaining.log）；不是全工作区全绿。相关 Python 门 185 项通过（target/code-identity-final-gates.log），保留已有 MSVC linker stdout 告警；逐文件复查 Rust、fixture 和采集器 diff。

两个成功浏览器 tab 在已测窗口读到的 warn/error 缓冲为空。全部三个任务 tab、两个 Rust server session、自有 Python server 和采集器连接已关闭，8607/18607 无监听。其他元素的身份逻辑、更多代码输入/布局/高亮/错误条件仍开放，矩阵仍 130 项 partial，三个待决流程未扩大实施。colconfig_params 独立改动保持未提交；本批按现有授权做工作分支提交/推送，不合并或发布。


### Cross-element identity investigation and pending workflow (2026-10-30)

本批仅修改既有 text_misc_params 示例/fixture/采集器和证据门，不改生产身份计算。三轮原生 Python 参考与 Rust identity-before 各 24 元素/三次成功 finish：h2 属性、Markdown help、badge help、Markdown→caption 类型、显式 key 按钮 disabled/help/icon 五个变化目标在 Python 为 A/B/A，在 Rust 均为 A/A/A。内部业务字段投影匹配，但完整 Element 仍有八个另行记录的布局存在性差异（Markdown 默认 width、badge alignment）；这些差异不当作已通过或被接受。

真实 Browser Use Chrome 各保留 initial→alternate→restored 三个观察、三张 context JPEG。Rust 切换后标题 anchor/divider、caption 样式和 Action 按钮启用状态均滞留，状态 caption 与 checkbox 已切换；Python 同步更新。Rust UI capture 标记 successful=false，正向语义门拒绝旧值；没有点击本应禁用的按钮或声称做过 help hover。两个标签页在所测窗口读到的 warn/error 缓冲为空；两个任务 tab、WS 与自有服务已关闭，8606/18606 无监听。正确/失败截图字节、哈希、解码和裁剪尺寸均验证，五项 UI 损坏 guard 被拒绝。

原来 text/misc 门只读摘要、未执行已有原始帧解码生成器，现补实际逐帧 base64/方向/长度/协议/摘要/结束标志绑定，旧正确五元素数据未修改，六项线/摘要损坏 guard 被拒绝。相关新增参考门及矩阵/文档共 67 项通过（target/element-identity-final-gates.log）；示例 Clippy -D warnings、构建与 Rustfmt 检查通过（target/element-identity-example-clippy.log、target/element-identity-example-build.log），保留既有 MSVC linker stdout 告警。无库代码修改，本批未无故重复库单元/工作区；旧 242 项记录带两项队列排除，不能称本批库全绿或本批故障已修复。

architecture 的 Pending unified NewElement identity decision 写出静态/原生/可见故障分层、三种实际选项、推荐唯一终结点、15 个拟改生产文件、现有 map 与编码成本、sender/recording/stream 一致性、cache replay 与真实 UI 验收范围。按用户 AGENTS.md 第 2 条等待流程选择，尚未实施新阶段；公开 proto 的 HashMap 类型、widget/图表 ID、URL、缓存键和另三个待决流程保持未动。矩阵仍 130 项 partial；inventory 如实补出五项先前未明示的缺口，不调整功能分母。用户 colconfig_params 文件/Cargo/索引改动未纳入本批阶段提交。


### Text layout defaults and presence correction (2026-10-30)

修正 MarkdownOptions 私有宽度默认值：默认/auto 省略 width_config，显式 stretch/content/像素保持；caption 默认 stretch 不变。badge 默认不发送 text_alignment_config。没有公共签名、依赖、发送或身份流程变更。完整 Python layouts 17 场景参考保留；非默认 TextAlignment 位于私有模块，外部示例无法命名该类型，公共导出/便利方法取舍等待用户选择。Rust 完整 layouts 明确诊断此缺口，only_widths=true 单独验证现有接口可表达的 13 场景，不缩减完整分母。

新原始 Python/Rust layout-widths 各 14 个完整 Element（含输入报告），修前七处宽度/对齐存在性偏差保留，修后路径和完整 Element 一致。新 identity-layouts 24 个完整 Element 与既有 Python identity 一致（仅归一化运行时 widget id），此前八处布局偏差消除；四个目标仍 A/A/A hash，统一身份选择未实施。本批没有新的浏览器/UI 验证，旧失败记录未修改，不能声称标题或按钮的可见滞留已修复。

按代码→单元→集成验证：全目标 Clippy -D warnings、Rustfmt 检查通过；公共 API 单元 1 项、文本/JSON WS 集成 7 项通过（target/text-layout-clippy.log、text-layout-unit.log、text-layout-integration.log）。工作区 244 项通过（库 237、ledger 1、宏 2、rustdoc 4），明确排除既有 navigation_pages_switch_and_session_state_match_the_measured_wire、rerun_queue_messages_match_frozen_reference 两项队列差异（target/text-layout-workspace-remaining.log），不称全工作区全绿。原始协议/摘要绑定、完整载荷语义与四项一致错误线 guard、矩阵和文档共 73 项通过（target/text-layout-final-gates.log）。已有 MSVC linker stdout 告警保留。

逐文件复查 diff，示例构建通过；采集连接/自有服务已关闭，结束时 8606/18606 均无监听。矩阵仍 130 partial，完整目标继续；用户 colconfig_params 文件、Cargo 与索引修改保持独立，未纳入阶段提交。按现有授权只提交推送工作分支，不合并或发布。


### Text normalization and LaTeX layout validation (2026-10-30)

真实修前/修后原生 WS 以 12 个字符串输入分别调用 markdown、caption、text、title、header、subheader、latex，加输入报告共 85 Element。修前 72 个完整载荷不同；修后全部完整 Element/路径与 Streamlit 1.66.1 / Python 3.14.7 参考一致。覆盖空格/Tab 共同前缀（不能按最小缩进长度裁切）、Unicode 全空白行、Python strip 的 U+001C–001F、内部 CRLF/CR、空输入及中文/emoji。LaTeX 在加 $$ 前清理公式，默认 width stretch 且 alignment 缺省，均以完整载荷验收。

只在现有 utils/mod.rs 放置 crate 私有清理函数并由既有生产者共用，未新增模块、依赖或公共接口。保留原始 Python normalization 的 fixture 错误：JSON surrogate 转义直接写成 Python 字面量导致最后 Unicode 案例 UnicodeEncodeError（79 元素，含异常）；successful 只是采集器传输标志，证据门明确检查异常而不当成正确语义。修正输入后另存 normalization-valid；没有编辑、删除或覆盖首份失败。Rust before 与 fixed 各 85 元素保留。

按代码→单元→集成顺序，全目标 Clippy -D warnings 与 Rustfmt 检查通过；12 输入语义边界的清理单元 1 项、文本/JSON WS 集成 8 项通过（target/text-normalization-clippy.log、text-normalization-unit.log、text-normalization-integration.log）。工作区共 246 项通过（库 239、ledger 1、宏 2、rustdoc 4；target/text-normalization-workspace.log），仍明确排除 navigation_pages_switch_and_session_state_match_the_measured_wire、rerun_queue_messages_match_frozen_reference 两项既有队列差异，不称完整工作区全绿。协议/摘要绑定、完整语义、五项一致错误线 guard 加矩阵/文档门共 79 项通过（target/text-normalization-final-gates.log）。已有 MSVC linker stdout 告警保留。

逐文件复查 diff，示例构建通过；两个 Rust server session 均终止，采集器拥有的 Python 服务/连接关闭，8606/18606 无监听。没有新的浏览器渲染/非字符串转换证明，未关闭未测参数或等待选择的统一身份、TextAlignment、JSON、队列策略；矩阵仍 130 partial，完整目标继续。colconfig_params 独立改动保留，按授权只提交推送工作分支，不合并或发布。


### Divider alignment presence validation (2026-10-30)

固定 Python 1.66.1 与 Rust 原生 WS 的 dividers 场景各九个完整 Element：输入报告、默认/显式 stretch、1/240/i32::MAX 像素 divider，及普通 Markdown/caption/LaTeX 对照。修前五个 divider 多发 LEFT alignment，修后所有 Element/路径匹配参考，保留 DIVIDER 类型与 wrap 缺省。生产只在既有对齐判断加入 Divider，不改公共签名、依赖、hash 或队列；Native/Caption 保留 LEFT，LaTeX 继续省略。

公共 API 单元扩入 divider，并按实际覆盖更名为 public_text_width_and_alignment_presence_match_reference；一项通过。按代码→单元→集成顺序，全目标 Clippy -D warnings、Rustfmt 检查与文本/JSON WS 九项通过（target/divider-layout-clippy.log、divider-layout-unit.log、divider-layout-integration.log）。工作区 247 项通过（库 240、ledger 1、宏 2、rustdoc 4；target/divider-layout-workspace.log），明确排除已有 navigation_pages_switch_and_session_state_match_the_measured_wire、rerun_queue_messages_match_frozen_reference 两项队列差异，不称完整工作区全绿。原始帧/摘要/完整布局语义、四项一致错误线 guard 与矩阵/文档门 84 项通过（target/divider-layout-final-gates.log），已有 MSVC linker stdout 告警保留。

修前原始帧未改，逐文件检查 Rust、fixture、采集器与 gate diff。两个 Rust server session 均终止，Python collector 拥有的服务/连接关闭，8606/18606 无监听。未新增浏览器几何验证；静态 Width(i32) 到 u32 未校验风险已记录，但异常/恢复行为尚待动态参考及错误流程决定，不能用有效值关闭该缺口。统一身份和其他接口/流程选择保持待决，矩阵仍 130 partial，完整目标继续。colconfig_params 独立改动不纳入本批；只按授权提交推送工作分支，不合并或发布。


### Divider invalid-width diagnosis and pending error API (2026-10-30)

本批未改库/宏/生产错误流程。复用现有 text_misc_params fixture、示例和采集器，以同一 WS/session 四轮 zero→negative→caught→recovered 采集双端。Python 11 元素：0/-1 的未捕获 StreamlitInvalidWidthError 阻止 after 输出，显式捕获 0/-1/i32::MIN 后可渲染 1 并输出三条精确错误消息，下一轮 240 正常。Rust 16 元素：所有调用返回 () 并继续 after，原始宽度为 0/4294967295/2147483648/1；四轮 session id 恒定、runs=1/2/3/4、finish 均 0，最后恢复轮三个完整 Element 与 Python 一致。仅恢复一致不代表错误语义通过；调用后的状态写入没有单独探针，不据此声称已完成该项验收。

原始帧逐条绑定 base64/长度/解码/摘要，另绑定四个请求 query、同会话、分轮 delta_path、异常类型/完整消息/flags、捕获结果、后续输出和恢复计数；四项一致错误线 guard 被正确拒绝。相关 Python/矩阵/文档门 89 项通过（target/divider-errors-final-gates.log）。示例 Clippy -D warnings、构建、Rustfmt 检查通过（target/divider-errors-example-clippy.log、divider-errors-example-build.log）；保留已有 MSVC linker stdout 告警。因没有生产库修改，本批未重复库/工作区测试，上一批 247 项记录仍带两项已知队列排除，不能称本批新跑全库或错误修复完成。

源码调查确认只返回 render Err 会被 App::push 日志吞掉，而仅阻止后续输出不能保证用户代码中止；Entry Future<Output=()> 和 main 宏丢弃返回类型也是落地可捕获错误的真实依赖。architecture 的 Divider invalid-width error contract awaiting decision 提供 Result-returning calls（推荐）、受校验配置构造、暂缓三个选项，列出公共接口、Entry/宏、WS 异常边界、迁移文件及后续状态写入/真实 UI 验收。按 AGENTS.md 第 2 条等待用户选择，未实施这些生产变更；完整目标与 130 partial 不变，其他待决流程未推进。

逐文件复查诊断 diff，两份正确/失败原始记录未修改；Rust server session 终止、采集器自有 Python 服务与连接关闭，8606/18606 无监听。本批未运行浏览器；colconfig_params 独立改动保留，只按已授权工作分支提交推送，不合并或发布。


### Real Chrome text layout and scrolling validation (2026-10-30)

使用 computer-use/Browser Use Chrome extension 操作既有 dividers、normalization 双端页面，每端四个实际观察：divider、规范化页首、End 到底部、Home 回页首。九个 divider/对照和 85 个规范化元素逐项比较内容、Markdown/caption/text 子组件、36 个标题 tag/id、元素宽高及相对位置；均匹配。12 个普通 text innerText 精确符合规范化参考（含 CRLF、CR、Unicode 与空输入），末尾中文/emoji 实际可见，LaTeX 呈现的文字保留原值。请求 1px 的 divider 两端均被前端限制为 16px，240 保持，超大宽度限制为父容器 704，未为符合参数名伪造像素。

每端视口宽 2560、DPR=1，高度分别 1305/1249；main clientWidth 2550/2560 导致 x 原点 923/928 的变化。全部原值保留，内容比较只减首元素 x、给底部 y 加实际 scrollTop，不称全屏像素一致。End 最初读数仍在动画中（1111/158），后续最终分别为 max=6216/6272；Home 均恢复 0，宽高/内容/相对位置不变。没有重发滚动输入。保留八张 JPEG（每端 divider 全视口/上下文、规范化首/末屏），字节、SHA-256、解码格式和剪裁尺寸逐张检查。

两端规范化页各六条相同 KaTeX Unicode warning，原始 message/timestamp/URL 保留；没有 stException，但不称控制台干净或一般 Unicode 数学支持通过。Rust 首屏截图第一次超时，已核对 Python 图成功写入而 Rust 图缺失，只重取同 tab 的 Rust 图，未重放导航/按键。初版证据门错误假定标题都取正文首行，实测单独 CR 产生 alpha\nbeta 的标题软换行；已按保留 DOM 修正规则，未改原始观察。

本批只新增浏览器证据、强化现有 gate 并更新矩阵/文档，没有修改生产代码或示例。六项损坏观察 guard 拒绝错误宽度、纯文本、标题 tag、滚动、告警和图像哈希；相关 Python/矩阵/文档共 96 项通过（target/text-layout-ui-final-gates.log），其中 text/misc 门 44 项。未重复 Rust 库/工作区；此前 247 项属于上一生产批次且带两项队列排除，不作为本轮新结果。所有原始 WS 和旧失败材料保持，矩阵仍 130 partial。

两个任务 tab 明确关闭，Python/Rust 自有 server session 均收到 Ctrl-C 并终止，结束时 8606/18606 无监听。其他视口/主题、一般渲染组合、未捕获错误 UI、统一身份和其余接口/流程决定继续开放。用户 colconfig_params 改动不纳入阶段提交；按既有授权提交推送工作分支，不合并或发布，完整目标继续。


### Badge content and text-help creation validation (2026-10-30)

新增既有 text_misc_params 的 badge-content 场景：12 个 badge 字符串输入、五种文本 help 对照与输入报告，原始 Python/修前/修后各 18 Element/一次成功 finish。修前 17 个内容 Element 不同；修后完整 Element 与 delta_path 全部匹配 Python。badge 只转义 [ 和 ]，不 strip 标签或删除既有反斜杠/换行/Markdown；有效/空白 icon 按 Python whitespace trim（含 U+001C/U+001F）。badge、Markdown/caption、三级标题的 help 仅 dedent，保留首尾 LF。content/stretch/240 宽度、wrap 与 alignment 存在性同时校验。

在现有 utils/mod.rs 提取 dedent_text 和共用空白判定，原 clean_text 继续 dedent 后 strip，既有正文回归保持。无新模块/依赖/外部公共接口，手工 hash 表达式和统一流程未改；标签/icon 储存值的规范化自然影响现有输入，但 help 仍遗漏于相关手工 hash，本批不能称动态帮助刷新已修复。无效 icon、非字符串、tooltip/浏览器显示尚未验收，完整目标继续。

按代码→单元→集成顺序，全目标 Clippy -D warnings、Rustfmt 检查通过；utils 两项（新 help 边界与旧正文）、公共 badge 单元一项、文本/JSON WS 十项通过（target/badge-content-clippy.log、badge-content-dedent-unit.log、badge-content-unit.log、badge-content-integration.log）。工作区 250 项通过（库 243、ledger 1、宏 2、rustdoc 4；target/badge-content-workspace.log），明确排除已有 navigation_pages_switch_and_session_state_match_the_measured_wire、rerun_queue_messages_match_frozen_reference 两项，不称完整工作区全绿。完整协议绑定、七项一致错误线 guard 与相关矩阵/文档门 104 项通过（target/badge-content-final-gates.log）。已有 MSVC linker stdout 告警保留。

原始修前与正确记录未改，逐文件复查 Rust、fixture、采集器和 gate diff；示例构建通过。两个 Rust server session 均终止，参考采集器自有 Python 服务/连接关闭，8606/18606 无监听。本批没有新浏览器操作，上一批 layout-ui 不作为本场景证据。矩阵仍 130 partial，未推进待决错误契约/身份/公开对齐/JSON/队列策略，colconfig_params 独立改动保持；按授权只提交推送工作分支，不合并或发布。


### Actual Chrome badge content and tooltip validation (2026-10-30)

复用已提交的 badge-content 双端示例，真实 Chrome 每端各折叠一次输入报告，核对 12 标签的可见文本、颜色、粗体/code、18 容器及相对几何；结果一致。保留隐藏零尺寸测量副本，另以 positive-size visible_badges 区分实际显示；空标签没有可见 badge。类似指令标签的 x] [other 显示、零尺寸嵌套 span 和 Material/已有反斜杠标签旁的 Help 按钮按实测保留，不编造一般转义安全保证。

随后每端真实悬停七个入口：普通 badge、Material/反斜杠 badge Help、Markdown、caption、title/header/subheader。通过受支持的 tab CDP Input.dispatchMouseEvent mouseMoved 在刚读取的 DOM 坐标中心移动指针，等待实际 tooltip 可见，保存 role/name、DOM、paragraph textContent 和 strong。Tip [0]/Tip [3] detail 及 Common help detail 两端相同，common help 中 help 实际加粗；七入口均通过，每端共八观察和四张 JPEG。除首次页面加载外未请求参数切换或额外 rerun；本批没有完整 WS 请求计数账本，不能据此宣称任意环境都只运行一次。

四次截图在返回字节前超时（Python initial/Markdown/subheader，Rust Markdown），逐次核对已保存文件，只补缺图，没有重放折叠或悬停；最终对准确任务 tab 调用 Page.bringToFront 后重新观察并成功截图。Python 初步 hover 探针在保留 initial 前已移出，collection_notes 记录过程。八张 JPEG 的字节数、SHA-256、解码与 800×1000 剪裁尺寸验证；所测 warn/error 缓冲为空，不能推广到未观察窗口。

九项错误观察 guard 覆盖标签、颜色、粗体/code、空标签、tooltip、帮助格式、实际动作目标及图片；相关 Python/矩阵/文档门共 114 项通过（target/badge-content-ui-final-gates.log），其中 text/misc 62 项。逐文件复查证据门与文档 diff。本批未改生产/示例/宏/Entry，未重复 Rust 库/工作区；上一生产批次的 250 项记录仍带两项队列排除，不冒称本轮新结果。两任务 tab 明确关闭，两个自有 server session 均终止，8606/18606 无监听。

本批只证明固定输入初次创建后的 badge/tooltip 显示；没有帮助 A/B 参数切换，旧 help hash 遗漏与统一身份仍未修复，错误契约等其他选择保持待决。原始 WS、旧失败和上一 UI 记录未改，矩阵仍 130 partial，完整目标继续。colconfig_params 独立改动不纳入本批，按授权仅提交推送工作分支，不合并或发布。


截图逐图复核补充：原 Python markdown-help.jpg 与 initial.jpg 字节相同、没有 tooltip，明确排除为 tooltip 图像证据，原文件不改。另开独立 Python 会话补证，普通 screenshot 的两张尝试图也不作 tooltip 证明；DOM 观察保留。第二个独立 tab 在确认 role/name/opacity=1 后，通过受支持的 tab CDP Page.captureScreenshot 直接取得并目视确认正确 tooltip 图 markdown-help-cdp.jpg。markdown-help-confirmation.json 记录这三个观察、三张图的用途/哈希/尺寸和独立清理。原序列每端八观察/四 JPEG 不变，新增 Python 补证后合计 19 个观察、11 张 JPEG；不把缺失或过渡图伪称正确。追加两个 Python task tab 与服务均清理，结束无监听。


### Alert normalization and separator rules validation (2026-10-30)

在既有 status_app.py/status.rs 添加 normalization 诊断场景，现有 text_misc_params_capture.py 的 alert-normalization 路由选择该 app，其他场景不变。12 组输入乘 info/success/warning/error 共 48 调用，加输入/返回报告共 50 Element；修后完整 Element/路径与 Python 1.66.1 逐项一致。正文先 clean_text 再提取图标，title 单独 clean_text；显式图标按 Python whitespace strip，空白变空串仍抑制自动提取。Alert 宽度仍放在 Alert 内，外层 Element 不新增布局字段。

修前错误基线共 34 元素：16 个带边界空白的有效图标被误拒绝，其余正文/title 未规范化。第一次实现把 emoji 后分隔当普通空白，四个格式的 U+001C 被多删；50 元素的 normalization-attempt 和 target/alert-normalization-integration-attempt.log 保留，Python 参考未改。真实结果与固定源码确认 emoji 仅吞空格/下划线/连字符，而 Material 吞 Python whitespace；最终分成两个清楚分支。另保存 16 输入的直接 Python helper oracle，对 Tab/LF/CR/NBSP/Unicode 空白/C0 和两类分隔符做单位验证；该文件明确不属于公共 WS/浏览器证据。

按代码→单元→集成顺序，全目标 Clippy -D warnings、Rustfmt 检查通过，status 单元十项和文本/JSON/Alert WS 集成十一项通过（target/alert-normalization-clippy.log、alert-normalization-unit.log、alert-normalization-integration.log）。工作区共 253 项通过（库 246、ledger 1、宏 2、rustdoc 4；target/alert-normalization-workspace.log），明确排除已有 navigation_pages_switch_and_session_state_match_the_measured_wire、rerun_queue_messages_match_frozen_reference 两项，不称完整工作区全绿。原始帧/报告绑定、七项一致错误线 guard、helper oracle 边界及矩阵/文档门 123 项通过（target/alert-normalization-final-gates.log）。已有 MSVC linker stdout 告警保留。

没有新模块/依赖/公共签名/错误类型，未改宏/Entry、StatusContainer 或统一 hash；使用既有正文清理函数。逐文件复查生产、示例、fixture、采集器、gate diff；示例构建通过，四个定点 .gitattributes 规则保留新原始记录行尾。三个 Rust server session 均终止，Python collector 自有服务/连接关闭，结束无相关监听。新浏览器/UI、图标全集、非法参数组合与非字符串仍开放；矩阵保持 130 partial，其他待决选择及完整 Goal 不缩减。用户 colconfig_params 修改不纳入阶段提交，只按授权提交推送工作分支，不合并或发布。


### Actual Chrome alert normalization UI validation (2026-10-30)

复用已提交 status normalization 场景，真实 Chrome 两端各折叠输入/返回 JSON 报告一次，再做 PageDown、End、Home。每端四个完整 DOM/几何/console 观察和三张 JPEG；48 条提示逐项核对正文/paragraph（含 CRLF 与 U+001C）、title/strong、emoji/Material 图标与字体、前景/背景色、ARIA role 和几何，均匹配。info/success 为 status，warning/error 为 alert；宽度为 240 或默认父容器 704，空正文/title 不变，显式空图标不自动提取。截图保留首/中/末视口，目视确认四种颜色、标题、图标、Markdown、空内容；不称每条提示都有独立图片。

真实滚动的中段 top=1092，底部 top=max=2900，Home 回到 0；全程内容/尺寸和文档相对位置保持。Python 初始视口 2560×1305，随后 2560×1249，Rust 为 2560×1249；初始 Python max=2844 变为 2900，原值保留，未强设视口或改浏览器设置。比较只加实际 scrollTop 并以首提示 x 为原点，不宣称全屏像素一致。emoji 后 U+001C 按参考保留，屏幕可出现控制/缺字方块，不把兼容输出描述为控制字符清洗。

截图采用已支持的 tab CDP Page.captureScreenshot，激活准确任务 tab、把指针移离控件后直接保存，六图无超时；逐张校验字节数、SHA-256、JPEG 解码及 800×1000 剪裁尺寸。九项错误观察 guard 覆盖正文、标题、图标、ARIA role、颜色、宽度、空标题、滚动及图片。相关 Python/矩阵/文档共 133 项通过（target/alert-normalization-ui-final-gates.log），text/misc 门 81 项；逐文件复查 diff。

本批未改生产、示例或 API，未重复 Rust 库/工作区；上批 253 项仍带两项既有队列排除，不称本轮新结果。所测 warn/error 缓冲为空；两个任务 tab 明确关闭、两个自有 server session 终止，8502/18502 无监听。除首次加载外未请求参数切换或额外 rerun，但本批没有完整 WS 请求账本，不能推断任意环境的总运行次数。其他主题/视口、非法参数、callback/参数更新身份仍开放，矩阵保持 130 partial，完整目标继续。colconfig_params 独立改动保留，按授权仅提交推送工作分支，不合并或发布。


### Alert validation boundary, partial corpus (2026-10-30)

二十组参数乘四格式的原生 WS 保留输入报告及每次真实调用后的 receipt。Python 97 Elements/16 Alert；Rust 修前 93/12、修后 101/20，原始三份均未覆盖改写。分类错误文字、icon-before-width 和 strip 后 spinner 修正，使完整调用匹配从 20/80 变为 68/80。十二处剩余差异明确为 case 3/15 未知 Material 成员判断/首错与 case 19 带引号宽度 repr，各四格式；不硬编码拒绝测试字符串，不把已知失败排除出语料。拒绝调用无 Alert/路径消耗，显式捕获后的后续有效调用恢复；不宣称未捕获异常、callback、Python 异常类/error_id 或新 UI 已兼容。

源码逐文件复查，Rustfmt 与全目标 Clippy -Dwarnings 通过；Clippy 保留工具链已有 MSVC 链接器提示。status 单元 12 项通过，既有 text-elements/Alert 真 WS 集成 11 项通过，工作区总计 255 项通过、两项既有更广队列差异测试排除（target/alert-errors-unit.log、alert-errors-integration.log、alert-errors-clippy.log、alert-errors-workspace.log）。新冻结数据门按原始 protobuf 解码绑定 summary，校验八十调用的顺序、完整 Alert/receipt 和连续路径；五项一致改写的错误 wire guard 覆盖首错类别、错误文字、spinner、宽度位置和回执顺序。相关 text/misc、矩阵、文档共 139 项通过（target/alert-errors-final-gates.log）；没有为文档修改重复整套 Rust 测试。

Python 原 PID 51364 已不存在，原端口 51056 与 Rust 8502 无监听，Rust 采集进程已终止。本批无浏览器 task。新增目录接入三案位于 architecture.md，生产目录/生成器尚未添加；带引号 repr 可独立继续。四个条目的证据/限制和生成清单已同步，130 partial 与完整目标保持；colconfig_params 独立改动保留，提交/推送只到当前工作分支。


### Width error repr follow-up (2026-10-30)

现有 Alert width 错误改用 status.rs 内部 width_error_value，按 Python 选择引号、转义定界符/反斜杠、LF/CR/Tab 与其他 ASCII 控制字符。公开方法和 StatusError 形状未变，未新增生产数据/依赖/模块。原二十输入前缀现在 72/80 对齐，原始捕获不重写。扩展十八个输入后完整公共 WS 为 38 输入/152 调用：Python 169 Elements/16 Alert；Rust 修前和修后 173/20；完整匹配由 84/152 增至 112/152。剩余 Material cases 3/15 与 Unicode cases 30..37 共 40 处差异明确保留。中文、emoji 和组合重音匹配；Unicode 空白/格式/私用/未分配的 printability 尚未完成，不用 Rust Debug 伪装通用 Python repr。

源码逐文件复查，Rustfmt、全目标 Clippy -Dwarnings 通过（已有 MSVC linker 提示保留）。status 单元 13 项通过，其中新测试对照十条 Python 公共错误；工作区 256 项通过、两项既有更广队列测试排除。target/alert-width-unit.log、alert-width-clippy.log、alert-width-workspace.log 保留结果；未重复同一批通过的集成。完整冻结协议门解码 protobuf 并检查全部调用/路径/receipt，新六项 coherent wrong-wire guards 对旧引号/反斜杠/控制字符输出拒绝。相关 text/misc、矩阵、文档共 146 项通过（target/alert-width-final-gates.log）。

Python 原 PID 67700 不存在，54437/8502 无监听；两次自有 Rust 服务均已终止，本轮没有浏览器 task。只读字符探针在 target，Python Unicode 16.0.0 的非 ASCII 不可打印 scalar 数据统计为 737 闭区间，接入生产表/导出流程的三案记录于 architecture.md，尚未创建；与 Material 目录选择独立。四条矩阵证据/限制和生成清单同步，130 partial 和完整目标保持。colconfig_params 独立改动未修改、未纳入提交；仅提交推送工作分支。


### Bytes repr and dataset-name boundary (2026-10-30)

锁定 Streamlit 1.66.1 util.calc_hash(str(value)) / Python 3.14.7 对照证明 bytes 含单引号、不含双引号时使用双引号。旧 pywire.rs 的固定单引号和一条既有单元预期均错误；独立提取 HEAD 原函数的 Rust 探针对单引号字节真实失败（target/bytes-repr-before.log，退出 101），未改生产源码来制造失败。新实现选择定界符后只转义该定界符，保留字节转义与既有哈希算法；纠正旧预期，并以五个短字节串及 bytes(range(256)) 的实测 Python 哈希覆盖边界。三份冻结 chart IPC 均含双引号，本批没有新公共 UI 故障/修复证明，也未重新采集或修改它们。

Rustfmt、全目标 Clippy -Dwarnings 通过（已有 MSVC 链接器提示保留）；pywire 单元 6 项、图表集成/几何回归 5 项、原生 bar/data-view 集成 3 项通过，分别记录于 target/bytes-repr-unit.log、bytes-repr-integration.log、bytes-repr-native-bar.log。后两组包含真实 WS，同时保留纯序列化/几何测试的证据层级；不能把全部八项称为独立 WS 测试。Python charts/chartlibs 合同 30 项通过（target/bytes-repr-python.log）。按本次相关范围验证，未重复整个工作区或浏览器流程。

未新增生产文件/依赖/公共接口，未修改 Material/Unicode 数据、JSON/统一身份和更广 rerun 等待决项。矩阵状态未改变，130 partial 和完整目标仍开放；colconfig_params 独立改动保留，提交推送仅到既有工作分支。


### Disabled malformed numeric types (2026-10-30)

按用户已选 Python 错误/callback/恢复方案继续：在既有注册错误路径补 int/double，bool/int 用 integer TypeError，double 用 real-number TypeError。Live callback 已发生，异常后保留未渲染控件，下一轮恢复。无新公共接口/依赖/模块；数组的早期错误与会话持续状态尚未实现，不将所有错误输入一律忽略或整批拒绝。

参考首次单会话 disabled-types 原始记录保留 17 轮、13 异常、4 状态；数组污染后续输入，不能据此评判后半段其他类型。disabled-types-isolated 用八个独立 WS 会话各 load→malformed→同会话 recovery，合计 24 轮、19 状态、5 异常；原始请求/回复逐帧解码绑定 summary。明确验证 JSON select/Plain/Text/Check 的所测错误输入在 Python 被忽略、数组当轮及恢复轮仍异常。真实来源栈长度不同，门禁原先沿用旧的固定两帧假设而失败，已纠正为保留实际栈并校验非空，未改参考来转绿。三个 coherent wrong-wire guards 验证 double 错误文字、异常位置、恢复 callback 账本。

Rust 新回归仅重放完整参考前三种标量用例的九轮/42 个控件-异常-状态投影，先真实红（target/disabled-numeric-before.log），生产修正后绿；不声称完整八类或 protobuf 所有字段已对齐。复用单元按 bool/int/double 参数化，14 个 widgets 单元通过；queryparams 相关检查 14 项通过，既有队列差异未计入通过。全工作区 258 项通过、仅两项既有更广队列测试排除；全目标 Clippy -Dwarnings 与 Rustfmt 通过。日志为 target/disabled-numeric-unit.log、disabled-numeric-integration.log、disabled-numeric-workspace.log、disabled-numeric-clippy.log。相关 Python/query/矩阵/文档 93 项通过（target/disabled-types-final-gates.log）。

collector 重连通过 ExitStack 持有全部 WS；改动后另在 target/disabled-types-confirmation 实际复采并用完整门禁核验八组语义/清理，未替换冻结数据。自有端口 53202/64563/58706 均无监听，采集进程已 wait 终止，无浏览器 task。数组早期异常/持续失败、JSON/其他控件 Rust 差分和真实 UI 继续开放，四条矩阵限制/证据和清单同步，130 partial 与完整目标保持。colconfig_params 独立改动保留，提交推送只到工作分支。


### Disabled array errors before entry and across requests (2026-10-30)

复用既有两份 Python 原始参考，未重采/改写。完整回归不再截取标量前缀：八个独立会话合计 24 轮/130 个控件、URL、异常与状态投影，原单会话合计 17 轮/40 投影；两份均由 Rust 真实 WS 严格对照。数组错误在应用入口/所有 callback 前输出，后续新输入未应用且再次失败；独立新会话正常。JSON selectbox、Plain/Text bool 和 Check string 的所测忽略行为也已完成 Rust 差分。新 helper 比较异常 delta_path、类型、文字、两个标志；不伪造 Python 来源栈，也不把投影相同说成完整 protobuf/UI 验收。

WidgetRegistry 私有 input_error 区分持续的输入解码失败与可恢复的注册失败；handler 提前呈现异常并跳过 callback/entry，正常结束帧保留。输入类型、持久状态均按已确认 Python 方案，不新增公共接口、依赖或队列策略。新单元验证正常包在数组前/后两种顺序、首轮正常输入已接收而 callback 未分派、后续新输入被阻止和新状态无错误。

原完整回归先因事件计数常量写成 126 而失败；核对原始参考为 130（含八次 URL 写入）后重新运行，确认在旧生产代码上真实差分失败，保留 target/disabled-array-before-confirmed.log。一次误在旧编译会话仍运行时尝试重复启动，因日志占用未启动第二进程；随后继续等待原会话完成，未据观察超时重启。修后 widgets 单元 15 项、queryparams 相关检查 15 项通过。加入异常位置严格比较后，全目标 Clippy -Dwarnings、Rustfmt 及工作区 260 项通过，另排除原有两项更广队列测试，没有新增排除。日志为 target/disabled-array-unit.log、disabled-array-integration.log、disabled-array-clippy.log、disabled-array-workspace.log。相关 Python/query/矩阵/文档 93 项通过（target/disabled-array-final-gates.log）。

本轮未启动独立采集服务/浏览器；回归使用自有临时监听并自行关闭。现有参考 README 只改目标段落，保留其他行尾字节。四条矩阵当前限制与清单已同步，130 partial 和完整目标保持；真实错误 UI、启用/creation select 及其他 JSON/oneof 组合继续开放。colconfig_params 独立修改未纳入提交，只提交推送工作分支。


### Additional JSON/repeated/scalar disabled inputs (2026-10-30)

在旧八例后增加 JSON list/dict/null/string、整数/浮点数组、空 bytes 和 trigger，使用既有 collector 与参考 app；新 disabled-types-more 原始记录为十六个独立 WS 会话/48 轮、33 状态、15 TypeError、230 个控件-URL-异常-状态投影。旧两份捕获不重写。JSON list/dict 与三类 repeated 数组产生各自 unhashable TypeError，入口前失败且后续持续；JSON null/string 所测输入被忽略。空 bytes/trigger 在 Plain 后注册失败，保留 Live callback 并恢复。新完整原生 Rust WS 回归先在旧实现真实失败（target/disabled-types-more-before.log），修后全 48 轮/230 投影对齐，异常 path/类型/文字/标志严格比较。

widgets.rs 只扩展既有 input_error/scalar_error 分类，JSON 使用已有 serde_json，不新增生产文件、依赖或公开接口。单元将容器覆盖扩大为五类×两种输入顺序，标量增加 bytes/trigger；widgets 单元 15 项、queryparams 相关检查 16 项、全目标 Clippy -Dwarnings 与格式检查通过。工作区 261 项通过，另排除原有两项更广队列差异，没有新增排除。结果在 target/disabled-types-more-unit.log、disabled-types-more-integration.log、disabled-types-more-clippy.log、disabled-types-more-workspace.log。

Python 门扩展检查 16 个会话/48 轮的原始 protobuf 与 summary、输入 oneof、全部状态/callback、精确异常阶段与三项新增一致改写的 list/dict/bytes 错误 guard。相关 query/矩阵/文档 97 项通过（target/disabled-types-more-final-gates.log）。实际采集已退出并 wait，自有端口 55321 无监听，本批无浏览器 task。四条矩阵证据/限制和生成清单同步，130 partial 与完整目标保持。

Rust 重放明确只接受本例的空 bytes；不为测试引入 base64 依赖或把非空 bytes 写成已测。JSON 语法错误映射、更多形状/参数、启用/creation 控件和真实错误 UI 仍开放。Material/Unicode 等待选项保持，colconfig_params 独立修改未纳入提交，仅提交推送既有工作分支。


### Complete frozen-reference audit and media warning maintenance (2026-10-30)

当前工作区（保留已有 colconfig_params 改动）完整运行 tests/reference：首次 1781 项通过、96 条 Pillow getdata 弃用告警，日志 target/full-reference-current.log，原运行会话 43948 已确认正常结束。告警集中在既有 media_contract.py 的逐行全图 getdata 列表构造。只改成一次 Image.load 获取 PixelAccess，再按原行列顺序读取 RGBA；MEDIA_PNG_SIZE、MEDIA_PNG_PIXELS、十个合同判据和既有篡改检查保持不变。复用现有像素 API，没有修改依赖/最低版本声明，也没有屏蔽告警。

媒体合同在 -W error::DeprecationWarning 下 25 项通过，含无法解码的 PNG、错误像素、尺寸/字节/状态/截图等拒绝用例（target/media-pixel-access-gates.log）。修正后完整 pytest tests/reference -q -W error::DeprecationWarning 为 1781 项全部通过、没有告警（target/full-reference-final.log），运行会话 57855 正常退出。未改 Rust 生产代码，没有为本次 Python/文档维护重复 Rust 或浏览器验证；不把前批 Rust 261 项记成本轮新结果，也不以本次约两分钟时长作性能收益结论。

应用指南纠正 URL 初始化仍未完成的过时说法，并将禁用控件的异常分成已执行 callback 后可恢复的注册错误、callback/入口前持续失败的输入错误。保留框架停止标志不自动中断普通 Rust 计算/副作用的限制，不声称完整原生控制流传播已等价。只改已有说明并链接现有真实证据，没有新增接口或行为规则。guide 中已有 colconfig_params 索引段落保持原样，并从本批暂存中排除；其他 colconfig 文件也不纳入。

完整冻结检查证明当前既有合同回归通过，不代替新真实 UI、外部环境或全 API 验收。130 partial、M3/M5/M7 与所有待决项保持，完整 Goal 继续；仅按授权提交推送当前工作分支。


### Nonempty bytes and exact-octet replay (2026-10-30)

不改 Rust 生产逻辑或错误策略，只补参考与维护者重放。新 disabled-types-bytes 原始参考保留原十六例后追加 x、单引号/NUL/反斜杠/CR/LF 与 bytes(range(256))，十九独立会话各三轮，共 57 轮、39 状态、18 TypeError、272 控件-URL-异常-状态投影。三组非空 bytes 都在 Plain 后报 expected bytes, str found，保留 Live callback，下一轮同 WS 恢复；原三份捕获保留。新完整真实 WS 差分逐轮匹配异常位置/类型/消息/标志、URL、控件与状态回执。

既有重放器的“仅空 bytes”限制改为私有测试 Base64 解码，不新增生产文件、依赖或公共接口。标准向量、非法字符/padding/尾位及固定参考中全部 0..255 字节的单元通过；全目标 Clippy -Dwarnings 与 Rustfmt 通过。queryparams 相关 18 项通过，具体为 15 项真实 WS 与 3 项纯单元，不把整组都称为集成；此前 14/15/16 项的记录标签已校正为相关检查，通过总数不变。工作区总计 263 项通过，另排除原有两项更广队列测试，没有新排除。日志为 target/disabled-bytes-unit.log、disabled-bytes-integration.log、disabled-bytes-clippy.log、disabled-bytes-workspace.log。

Python 从原始 PB 检查四份 bytes 载荷的精确内容，并一致改写 0..255 为反向序列，要求门禁拒绝，即使错误文字相同。初版篡改循环误匹配较早异常帧，已修正只修改目标客户端请求，未改真实参考。相关 query/矩阵/文档在弃用告警视为错误下共 99 项通过（target/disabled-bytes-final-gates.log）。上轮完整 1781 项是保留结果，本轮按改动范围验证，没有把其记作含新增用例的当前完整计数。

采集进程已 terminate/wait，自有端口 60865 无监听，本轮无浏览器 task。用户指南和参考说明已同步十九例及非空字节范围；四条矩阵证据/限制和生成清单同步，130 partial 与完整目标保持。JSON 语法错误、其他组合和真实错误 UI 仍开放，Material/Unicode 等待选事项不变；只提交推送工作分支，colconfig_params 文件及已有指南索引段落不纳入。


### JSON syntax reference and private parser choice (2026-10-31)

复用既有参考 app/collector 新增 disabled-json 场景，没有修改生产 Rust。新原始捕获为 24 个独立 WS 会话各三轮，共 72 轮、34 状态、38 异常、252 个控件-URL-异常-状态投影。17 个语法错误各在入口/callback 前产生两次 json.decoder.JSONDecodeError；五个特殊标量接受并忽略、Live callback/恢复正常；[NaN] 和含 Infinity 对象经过 JSON 解码后各产生两次 list/dict TypeError。NewSession 原始环境字段逐轮核对 Streamlit 1.66.1/Python 3.14.7.final.0，runtime.json 只补采集后的构建信息，不修改原 trace。

冻结输入词法、完整类型/消息、codepoint 位置（多行 emoji 例 char 7）、全部请求/结束帧、会话隔离、callback 和持续错误。三个一致改写 guard 覆盖 TypeError 替换 JSONDecodeError、错用 byte offset 10、NaN 换成标准 null，均应拒绝。相关 Python/query/矩阵/文档在弃用告警视为错误下 103 项通过（target/disabled-json-final-gates.log），其中 query 51 项。没有新增 Rust 排除或调整已有原始记录。

独立直接解析探针使用当前缓存的 serde_json 1.0.145（对应 .d 编译输入已核对版本）和 Python json：七个输入被 Python 解码接受，Value 解码拒绝本次全部 24 个；补测已有 IgnoredAny 接受其中孤立 surrogate/溢出指数两例，另外五例仍不接受，已纳入选案。探针/结果位于 target/disabled-json-syntax-probe.rs、disabled-json-rust-parser.jsonl、disabled-json-decoder-comparison.json。此结果不能冒充 Rust 服务端差分，也未在本轮重新跑 Rust 工作区；前批 263 项只是保留结果。代码检查显示现有 serde 失败分支为 None 且输入错误只有固定 TypeError，新的 JSONDecodeError 路径尚未实现。

按 engineering-change-design 整理既有 architecture.md 三案：根类型语法扫描（推荐）、现有 IgnoredAny 词法/错误适配、暂缓。涉及新增 python_json.rs 和私有错误 kind/message 传递，依用户提供的 AGENTS.md 第 2 条先待选择，生产文件/流程未实施，行为方向仍沿用此前选定的 Python 完整兼容。四条矩阵仅补参考/限制、未升级状态，清单保持 130 partial；M3/M5/M7 与完整 Goal 继续开放。

采集进程已 terminate/wait，原端口 64996 清理另核验，本轮无浏览器 task。colconfig_params 独立改动保留，仅提交推送当前工作分支的参考、门禁和方案，不合并或发布。


### 2026-10-31 query binding: real browser history evidence

Python 1.66.1/3.14.7 reference and current Rust example were operated through the
computer-use Chrome tab API, using actual Back/Forward. No injected history or
synthetic client flags. Both same-document journeys have five runs/50 raw frames,
one session ID, no eviction or console warnings: URL y wins over submitted old
widget x on Back; absent bound restores default x over old y on Forward; Pick=c
persists. Flags false/false/false/true/true and explicit set_value/raw_value were
verified from original PB. Visible URL and markdown match each run's DOM cursor.

The first, distinct journey intentionally remains in evidence: binding edits
replaced the current entry, Back reached about:blank, Forward reloaded Pick=a,
and direct URL document history restored x/y. Python Connecting/disabled UI and
one/two Python/Rust WebSocket onerror messages are preserved. CDP eviction flags
mean its 70/60 retained frames (seven/six complete executions) do not prove all
navigation/reconnection requests were observed. An unavailable history-inspection
command and a rejected CDP read on blank were not bypassed. The second journey
created its entry through the existing server-side mode write and had no such
eviction. Original records were not rewritten to make the first assumption pass.

Eight JPEGs and both raw/DOM/log records are in
`tests/reference/reference-browser/queryparams/history-ui/` and
`tests/browser/rust-queryparams/history-ui/`. Current reference versions are
checked in raw NewSession frames; separate interpreter readback is post-capture.
109 related query/matrix/docs checks passed with DeprecationWarning as error
(`target/query-history-ui-final-gates.log`), including five wrong-evidence guards.
No production code changed, so no new broad Rust/full-reference claim is made;
the existing example built offline/locked before actual browser verification.
All four owned tabs across the two batches and both batches of servers were
closed; ports 8515/18515 and owned PIDs were read back absent. General history,
callback, multipage and other bound-widget behavior remain unverified; existing
queue/API/parser decisions and the 130 partial denominator remain unchanged.


### 2026-10-31 query percent encoding correction

The existing private decoder accepted Rust integer-parser leading plus syntax:
%+1 read as U+0001, including in parameter names. Python 1.66.1 preserves the
invalid percent sequence and applies ordinary plus-to-space handling (% 1).
The fix in query_params.rs only requires both escape characters to be ASCII
hex digits. Public interfaces/dependencies and later UTF-8 handling are unchanged.
Semantic match-arm spacing and the complete Rust diff were reviewed.

Reused the values reference app/collector, adding only an encoding scenario.
Sixteen requests on one native WS produce 128 JSON snapshots and 112 URL writes,
all 240 interleaved Rust events match. Cases include malformed and short escapes,
valid upper/lower hex, literal/encoded plus and space, nonrecursive decode,
control/Unicode/invalid UTF-8, separator literals and repeated/empty/equivalent
keys through all eight mutation stages. Static initial literals and raw-PB to
summary binding preserve reference meaning; four coherent wrong-wire guards
reject changed value/key/UTF-8 replacement count/request lexeme. Every raw Python
NewSession version is checked. Reference: queryparams/encoding/trace.json.
The producer closed its socket/server and port 49353 was read back free.

Pre-fix unit and full WS differential both failed on real current production
code (target/query-encoding-unit-before.log and query-encoding-ws-before.log).
After the minimal fix, code/all-targets Clippy -D warnings and Rustfmt check passed;
the focused unit passed; queryparams related checks passed 20 (16 real WS and
four pure units), with the existing queue test excluded. Full workspace passed
265 (library 258, ledger 1, macros 2, rustdoc 4), explicitly excluding only the
two pre-existing navigation_pages_switch_and_session_state_match_the_measured_wire
and rerun_queue_messages_match_frozen_reference differences. This is not full
workspace green. Logs: query-encoding-clippy.log, query-encoding-unit.log,
query-encoding-integration.log and query-encoding-workspace.log under target/.
The existing MSVC linker stdout warning remains; no new warning was introduced.
114 related Python/query/matrix/docs checks passed with DeprecationWarning as
error (target/query-encoding-final-gates.log).

No new browser DOM/navigation proof is claimed for this codec correction;
existing real-history captures were retained rather than recaptured. Arbitrary
query grammar, other bound controls and full compatibility remain open, as do
the pending JSON parser/public-interface/broader queue decisions. Matrix evidence
was expanded without status upgrade; inventory remains 130 partial. Existing
colconfig_params work remains outside this batch's commit.


### 2026-10-31 text-limit deserialization correction

Fixed Codec::Text rejecting overlong submitted strings/defaults instead of the
locked Python truncation. Incoming/default text now slices by Unicode code
points, while explicit native assignments remain intact. The original wire
default/max_chars are preserved. No public API/dependency/module additions;
other codecs and existing broader batch/queue policies were not changed.

The opt-in probe in the existing forms reference produces eight fresh sessions,
72 runs, 928 original frames and 144 ordered widget/state projections. text_input
and text_area each cover limit 5, zero, no limit and a None default; nine phases
include ASCII, CJK/astral/combining/ZWJ, retained-prefix equality, empty input,
code assignment, no-input retention and later recovery. All 144 Rust projections
match. Callback logs use truncated values, suppress discarded-suffix changes,
and preserve untruncated code state until another frontend submission.
Kind/default/max_chars/set_value/value are checked alongside native snapshots.
Python gates bind raw PB to summaries, versions/IDs/exact input and static
literal values; four coherent wrong-wire guards are rejected. The producer
closed all sockets/server; port 54262 was read back free. Reference is
queryparams/text-length/trace.json; old records were retained unchanged.

The revised form unit first failed with zero callbacks against the old production
code (target/text-length-unit-before.log). The pre-fix WS replay could not obtain
the first widget ID after its overlong default failed, so the second request
stopped with missing live widget id (target/text-length-ws-before.log); this is
not a completed 72-run pre-fix differential. An interim revised-unit assertion
rebuilt the same key outside its original form and changed identity; that mixed
path was removed. The final unit checks the applied batch, then executes the
submit callback and verifies its observed truncated text.

Code/all-targets Clippy -D warnings and Rustfmt passed. Codec Unicode/source
unit and corrected form-submit unit passed (target/text-length-codec-unit.log,
text-length-form-unit.log). Full workspace passed 267: library 260, ledger 1,
macros 2, rustdoc 4, explicitly excluding only the existing
navigation_pages_switch_and_session_state_match_the_measured_wire and
rerun_queue_messages_match_frozen_reference. This is not full workspace green
(target/text-length-workspace.log). After strengthening raw widget-field
comparison, 21 query-related checks passed: 17 real WS, four pure units
(target/text-length-query-regressions.log). No semantic production change was
made after the workspace run. The existing MSVC linker stdout warning remains.

Full frozen reference: 1803 passed with DeprecationWarning as error
(target/text-length-full-reference.log). The subsequent related query/matrix/docs
check passed 119, including final documentation/evidence paths
(target/text-length-final-gates.log). No new browser UI/IME/UTF-16,
query-bound length, changing-limit identity or invalid-limit definition claim.
M3/M5/M7, all 130 partial entries and the full goal remain open; pending JSON/API/
queue choices are unchanged. Existing colconfig_params work is kept out of this
batch's commit and push.


### 2026-10-31 keyed text limit reset correction

Keyed text_area previously ignored max_chars in its identity. The existing
keyed text_input is the control; only text_area's keyed identity extra now
serializes max_chars. No new API, dependency/module, default handling, unkeyed
identity or general element hashing change. Source diff and semantic spacing
were reviewed.

Reused the existing forms probe without modifying it. New text-reset native
reference has two sessions/24 runs/310 raw frames and 48 ordered widget/state
projections. The limit sequence covers shrink/grow/zero/unlimited/return,
actual typed strings and default-only None changes. Four IDs per kind are
required even when zero/None share max_chars=0 wire encoding. Returning to an
old ID yields its default, not the earlier input; no callback is dispatched
solely by the reset. All native values/state/callbacks and widget fields match,
and every pairwise identity equality relation matches the frozen reference.
Opaque Python/Rust digest literals are not compared across runtimes.

The new public-API unit first failed on unchanged identity; the complete 48-event
WS replay also failed against current old production code before the fix.
Both logs are retained as target/text-reset-unit-before.log and
text-reset-ws-before.log. After correction, code/all-targets Clippy -D warnings,
Rustfmt, focused unit and WS differential passed (text-reset-clippy.log,
text-reset-unit.log, text-reset-integration.log under target/). Existing MSVC
linker stdout warning remains. Full workspace passed 269: library 262, ledger 1,
macros 2, rustdoc 4. Only the original
navigation_pages_switch_and_session_state_match_the_measured_wire and
rerun_queue_messages_match_frozen_reference were excluded; this is not full
workspace green (target/text-reset-workspace.log).

124 related query/matrix/docs checks passed with DeprecationWarning as error
(target/text-reset-final-gates.log). Raw PB/summary, exact requests/input,
versions/session grouping, static native state/callback/default/limit/sync fields
and identity relations are checked. Four coherent mutations reject collapsed
area IDs with matching client references, resurrected state, reset callbacks
and default-only reset. The previous full 1803-reference run was not repeated;
this batch claims its actual related checks only. Native capture sockets/server
were closed and port 62136 read back free. Original reference files remain
unchanged; new data is queryparams/text-reset/trace.json.

Guide/matrix/inventory now distinguish measured native reset from unverified
browser remount/IME, simultaneous code/limit changes, stale-ID submissions,
unkeyed and arbitrary parameter combinations. No status upgrade: 130 partial,
M3/M5/M7 and the full goal stay open. Generic element identity, JSON/public API
and broader queue decisions remain pending. Existing colconfig_params work
is preserved outside this batch's commit/push.


### 2026-10-31 simultaneous old input, new limit and code assignment

Fixed the existing registration branch choosing a changed identity's default
over an explicit native write. changed_identity now falls back to default only
when !code_assigned. Existing native type/constraint validation and other source
branches remain. No new API/module/dependency, generic element hash or queue
policy was introduced. Guide now makes the explicit-write exception precise.

The existing forms app probe is unchanged. New text-source native capture has
two sessions, 20 runs, 258 original frames and 40 ordered kind/default/limit/
sync/state projections. Every incoming string uses the prior active ID. Source
values decode before callbacks using the previous run's limit; then the main
run resets on an identity change or preserves its explicit code assignment.
For example old limit five yields callback ABCDE before new limit three returns
abc; old limit zero yields an empty callback before new limit five returns
abcde. Three same-run assignments to code長🧊extra survive new zero/three/five
limits, synchronize their full value and retain it on later no-input runs.
All 40 projections and every within-runtime identity equality relation match.
Opaque cross-runtime ID digest strings are not required to be identical.

Public unit (both text widgets) and complete WS comparison first failed against
old production code (target/text-source-unit-before.log, text-source-ws-before.log).
After the guard correction, code/all-targets Clippy -D warnings, Rustfmt, focused
unit and WS differential passed (text-source-clippy.log, text-source-unit.log,
text-source-integration.log under target/). Full workspace passed 271: library
264, ledger 1, macros 2, rustdoc 4, excluding only the original
navigation_pages_switch_and_session_state_match_the_measured_wire and
rerun_queue_messages_match_frozen_reference. This is not full workspace green
(target/text-source-workspace.log). Existing MSVC linker stdout warning remains.

129 related query/matrix/docs checks passed with DeprecationWarning as error
(target/text-source-final-gates.log). Gates bind raw PB to summaries, exact
request/input/active IDs, versions/session groups, literal native and callback
values and widget sync/identity relations. Four coherent mutations reject new-
limit callback decoding, lost code value in both wire/report, lost later
retention and missing synchronization. Original captures were not changed.
The prior full-reference run was not repeated and is not presented as current
full-suite validation. All sockets/server closed; port 57186 read back free.
New data is queryparams/text-source/trace.json.

This shared registration correction has new reference proof for text_input and
text_area, not every other widget/native type, orphan historical-ID submission,
callback-side writes, query binding/fragment/rerun or current browser remount/IME.
Three matrix entries gain evidence without status upgrade; inventory remains
130 partial. M3/M5/M7 and the full goal stay open, pending architecture choices
are unchanged. Existing colconfig_params work is kept outside this commit/push.


### 2026-10-31 text-input URL truncation and bound history callbacks

Corrected selected query-seed serialization through the existing pending URL
update, plus omission of prior registered query-bound widget states before
history input application/callback collection. Existing private widget metadata
is used; unbound and unknown inputs retain their original order. No URL-loading
or normal callback reorder, public API, module/dependency or queue change.
TextAreaOptions.bind is a separate proposal, not an implemented method.

The existing forms probe gains opt-in binding/peer parameters without changing
old cases. Single-control text-bound reference has 12 runs/162 original frames/
31 ordered projections; text-bound-peer has 12 runs/174 frames/43 projections.
All 74 projections and identity relations match Rust. Each capture records seven
URL writes; URL-only and history truncation, default-equivalent clearing with
ordinary retained state, frontend/native/history priority, missing/empty values,
repeated truncated values and recovery match. History-bound string submissions
do not produce callbacks, while all three unbound peer callbacks remain.
The unchanged-repeat guarantee also has a focused Rust unit; the follow-up
native capture below now verifies that precise case independently.

Pre-fix public unit read abc but kept bound=abcdef in the store; pre-fix real WS
comparison failed. Logs target/text-bound-unit-before.log and text-bound-before.log
retain those failures. The latter used the original combined test name before
splitting single/peer tests. After correction, code/all-targets Clippy -D warnings,
Rustfmt, URL/store unit, history-admission unit and both real-WS comparisons passed
(text-bound-clippy.log, text-bound-url-unit.log, text-bound-history-unit.log,
text-bound-integration.log under target/). Full workspace passed 275: library
268, ledger 1, macros 2, rustdoc 4. Only the two existing
navigation_pages_switch_and_session_state_match_the_measured_wire and
rerun_queue_messages_match_frozen_reference were excluded. This is not full
workspace green (target/text-bound-workspace.log); existing MSVC linker stdout
warning remains.

134 related query/matrix/docs checks passed with DeprecationWarning as error
(target/text-bound-final-gates.log). Raw PB/summary, SDK versions/session groups,
requests/IDs/history flags, exact ordered URLs, original binding/default/limit/
sync fields, state/peer values and callbacks are checked. Four coherent mutations
reject wrong URL correction, an old bound callback/value and lost peer state.
Old captures were not rewritten; new references are queryparams/text-bound and
text-bound-peer. Servers/sockets closed and ports 58105/51632 were read back free.
The prior full reference suite result is not presented as current full validation.

The TextAreaOptions.bind public-method proposal was prepared with the engineering
change design skill in architecture.md. User confirmation is required by the
user's AGENTS.md 2, not an extra skill approval rule; the async question remains
pending and no method was implemented. Native text_input work continued under
the existing full-compatibility scope. Matrix adds scoped evidence/gap notes;
130 partial, M3/M5/M7 and the full goal remain open. No browser navigation/IME,
all malformed history types, multiple binding removal or generic JSON/queue/
identity completion is claimed. Existing colconfig_params changes stay outside
this batch's commit/push.


### Unchanged repeated bound text native follow-up (2026-10-31)

The independently retained text-repeat/trace.json has three runs, 39 raw frames
and seven ordered widget/state/URL projections in one session. first,ok and
again,ok select ok without any URL write; first,LONGEST selects LONGE and emits
one correction to a single value. No frontend widget input or callback occurs;
identity, default abcdef🧊, limit 5 and query key cjk_note stay fixed.
Existing production code already matches; only the collector, frozen evidence,
contract checks and real-WS regression were extended. Earlier captures remain.

The focused public URL/store unit passed, then 26 related query-module checks
passed, excluding only the existing rerun_queue_messages_match_frozen_reference
in that module (target/text-repeat-integration.log). This includes the new
seven-event comparison. All-targets Clippy -D warnings and Rustfmt passed;
the existing MSVC linker stdout warning remains (target/text-repeat-clippy.log).
137 query/matrix/docs Python checks passed with DeprecationWarning as error
(target/text-repeat-final-gates.log). Two coherent wrong-wire mutations reject
rewriting unchanged pairs and selecting the first value in both report and wire.
The full workspace/reference suites were not rerun for this test-only change;
the prior 275/1803 results are not represented as current full-suite validation.

Socket/server cleanup is recorded and port 62304 was read back free. This is
native API/WS evidence, not internal get_all state, arbitrary query syntax or
browser navigation/IME. Matrix evidence and derived inventory preserve all 130
partial entries; M3/M5/M7 and the complete goal remain open. Public TextArea
binding and the other pending decisions are unchanged. Existing colconfig_params
changes are excluded from this batch's commit/push.


### Null text state effective-default correction (2026-10-31)

Ten native bound-input runs on one session retain 132 original frames and all
23 ordered widget/state/URL projections in text-empty/trace.json. Three explicit
None assignments remove the parameter; a following missing-parameter history
request restores None in this sequence. The literal URL None is a string, and
an empty URL is an empty string. Frontend Unicode input truncates to abcde and
produces the only callback; stale history inputs and a later unchanged empty
input do not add callbacks. Optional default/value fields, original raw default,
limit, binding key, history flags, IDs and identity equality relations are gated.

The pinned SDK changes the effective default when current keyed native state
is None, after computing identity from the original options. This disproved the
initial serializer-only inference. Rust's text_input/text_area now follow that
existing-source behavior; no query serializer/registry/history flow changed.
The public unit covers both controls' null preseed, retained null, explicit
full string restore and stable ID. The new native binding comparison is only
text_input; TextAreaOptions.bind remains pending. No public API/module/dependency
was added. Existing normal forms behavior and earlier frozen captures remain.

The public unit and complete native comparison both failed before correction
(target/text-empty-unit-before.log, text-empty-before.log). The first draft
integration count was corrected from 22 to the measured 23 before recording the
production mismatch; no reference was changed to hide a discrepancy. Code/all-
targets Clippy -D warnings and Rustfmt passed, then the public unit and all 27
related query-module checks passed, excluding the existing queue comparison
(target/text-empty-clippy.log, text-empty-unit.log, text-empty-integration.log).
Full Rust workspace passed 278: library 271, ledger 1, macros 2, rustdoc 4.
Only the two existing navigation_pages_switch_and_session_state_match_the_measured_wire
and rerun_queue_messages_match_frozen_reference were skipped; this is not full
workspace green (target/text-empty-workspace.log). MSVC linker stdout warning
remains. Related query/matrix/docs Python gates passed 142 with deprecations as
errors (target/text-empty-final-gates.log); four coherent mutations reject wrong
default presence, missing URL clearing, literal-None coercion and history value.

Full frozen-reference Python suite passed 1826 with DeprecationWarning as error
(target/text-empty-reference.log).

Owned socket/server cleanup is recorded; port 50499 was read back free. Matrix
and derived inventory retain 130 partial entries, M3/M5/M7 and the complete goal.
This is native API/WS evidence, not fresh browser/IME, native area binding or all
null/default/identity/source combinations. Existing colconfig_params changes
are excluded from this batch's commit/push.


### Keyed text raw-validation identity correction (2026-10-31)

The independent text-validation capture retains fourteen native runs, 181 raw
frames and 42 ordered widget/validation/state projections. Six types with
inherited validation share identity and preserve the frontend's KEEP🧊. Explicit
^A+$ changes identity and resets; changing its message and type together retains
AAAAA. Disabling validation with an explicit empty regex resets; changing type
with that same empty regex retains identity. Restoring inherited validation
returns to the original ID without resurrecting old input. Only the two
frontend edits invoke callbacks. No URL message occurs.

Rust's prior identity branch used derived email/url validation, producing an
incorrect reset. Complete WS comparison failed before the one-branch correction
(target/text-validation-before.log). Identity now uses the raw optional regex;
actual emitted regex/message resolution remains unchanged. The new public unit
covers all six types, retained native values, identity and derived wire rules.
No public API/dependency/module or generic hash change was introduced.

Code/all-targets Clippy -D warnings and Rustfmt passed, followed by the public
unit, then all 28 related query-module checks, excluding its existing queue
comparison (text-validation-clippy.log, text-validation-unit.log and
text-validation-integration.log under target/). Full workspace passed 280:
library 273, ledger 1, macros 2, rustdoc 4. Only the two existing
navigation_pages_switch_and_session_state_match_the_measured_wire and
rerun_queue_messages_match_frozen_reference were skipped; this is not complete
workspace green (target/text-validation-workspace.log). Existing MSVC linker
stdout warning remains. 146 related query/matrix/docs Python checks passed with
DeprecationWarning as error (target/text-validation-final-gates.log). This batch
did not rerun the full reference suite; the prior 1826 result is historical.

Raw PB/summary, exact requests/input IDs/history, versions/session, snapshots,
callbacks and optional type/regex/message/default/limit/sync fields are guarded.
All pairwise ID equality relations are compared. Three coherent mutations reject
type reset, message reset and a lost derived regex. Socket/server closed and
port 63974 was read back free. Matrix and derived inventory retain 130 partial
entries and M3/M5/M7/full goal remain open. Native protocol/API proof does not
claim browser enforcement/remount, unkeyed identity equivalence, generic hash
repair or every query/callback/source combination. Existing colconfig_params
changes are excluded from this batch's commit/push; pending choices stay pending.


### Unkeyed text policy identity correction (2026-10-31)

Twelve native runs/155 raw frames/36 ordered widget-policy-return projections
in text-unkeyed prove KEEP🧊 survives disabled, callback removal, hidden label,
ignore-rerun and collapsed label changes under the same identity. Width/help
controls reset to abcde; restoring an old ID does not resurrect its old input.
Only the two frontend edits add callback markers. The opt-in probe has no user
key: state=null is deliberate, has_key=false is checked, and the report does
not pretend to expose unkeyed internal state through a key lookup.

Rust excludes disabled/callback/ignore/visibility from only its unkeyed text
identity tuple. Width/help and content/constraints remain; keyed identity,
emitted policy fields and generic Element hashing do not change. The public
unit applies frontend input then exercises policy transitions and stable IDs.
No new public API/module/dependency was added. Existing keyed probes retain
their prior behavior; old raw captures remain intact.

The first replay hit the adapter's explicit-key-only mapping, not a production
comparison (target/text-unkeyed-adapter-before.log). The helper now maps the
unkeyed -None suffix only in this scenario. Replaying the prior four identity
terms then produced a genuine observed/expected mismatch; the corrected tuple
was restored and the same comparison passed (target/text-unkeyed-before.log).
No reference was altered to hide either failure. Code/all-targets Clippy
-D warnings and Rustfmt passed, followed by the public unit and all 29 related
query-module checks, excluding its existing queue comparison (text-unkeyed-
clippy.log, text-unkeyed-unit.log, text-unkeyed-integration.log under target/).
151 related query/matrix/docs Python gates passed with DeprecationWarning as
error (target/text-unkeyed-final-gates.log). Four coherent wrong-wire mutations
reject disabled/callback resets, a lost ignore flag and wrong width retention.
Exact input IDs/history, versions/session, raw PB/summary, defaults/limits/sync,
policy/visibility/width/help, callbacks/returns and all pairwise ID equality
relations are checked. This batch did not rerun the full Python reference suite.

Full Rust workspace passed 282: library 275, ledger 1, macros 2, rustdoc 4.
Only the two existing navigation_pages_switch_and_session_state_match_the_measured_wire
and rerun_queue_messages_match_frozen_reference were skipped; this is not full
workspace green (target/text-unkeyed-workspace.log). The existing MSVC linker
stdout warning remains.

Owned socket/server closed; port 49687 was read back free. Matrix/inventory retain
130 partial entries and M3/M5/M7/full goal remain open. This is native API/WS
proof, not browser disabled/visibility/buffering/remount, every omitted-versus-
empty option distinction, unkeyed form/sidebar identity or forged-input proof.
Pending API/hash/queue/parser choices stay pending; existing colconfig_params
changes are excluded from this batch's commit/push.


### Unkeyed area layout and default-height correction (2026-10-31)

text-unkeyed-area retains 21 native runs/272 raw frames/63 ordered widget-policy-
return projections in one session. The original input reference remains intact.
Policy changes retain KEEP🧊, while width/help/raw-height/placeholder changes
reset to abcde. Explicit native heights are 120/240; hint/next placeholders,
four frontend edits/callback markers and restoration are measured. All pairwise
ID equivalence relations match; previous IDs do not resurrect earlier input.
The unkeyed probe deliberately reports state=null with has_key=false and actual
return values, rather than claiming a keyed read of internal unkeyed state.

The pinned SDK also emits automatic height 122, or 94 with a collapsed label.
Rust's existing area emitter now sends this effective height; unkeyed identity
includes raw height/width/placeholder, leaving the keyed max_chars branch and
original supplied options intact. A public unit separately proves automatic
None versus explicit 122 have different IDs despite equal pixel payload, same-ID
collapsed 94 retains input, and returning to the old identity resets. No new
public API/module/dependency, shared hash or queue policy is introduced.

The complete real-WS comparison failed before correction on actual values and
layout (target/text-unkeyed-area-before.log), then passed all 63 projections.
Code/all-targets Clippy -D warnings and Rustfmt passed, then the public unit and
all 30 related query-module checks passed, excluding the existing queue test
(text-unkeyed-area-clippy.log, text-unkeyed-area-unit.log and text-unkeyed-area-
integration.log under target/). Raw PB/summary, exact requests/input IDs/history,
runtime/session, defaults/limits/sync, policy/visibility/width/height/placeholder/
help, callbacks/returns and ID relations are gated. Shared mutation checks reject
missing layout as well as wrong resets/retention or lost ignore flags; original
trace files are not rewritten.

Full Rust workspace passed 284: library 277, ledger 1, macros 2, rustdoc 4.
Only the existing navigation_pages_switch_and_session_state_match_the_measured_wire
and rerun_queue_messages_match_frozen_reference were skipped; this is not full
workspace green (target/text-unkeyed-area-workspace.log). Existing MSVC linker
stdout warning remains.

Complete frozen-reference Python suite passed 1842 with DeprecationWarning as
error (target/text-unkeyed-area-reference.log); 158 related query/matrix/docs
checks also passed (target/text-unkeyed-area-final-gates.log).

Owned socket/server closed and port 56722 was read back free. Matrix/inventory
retain 130 partial entries and M3/M5/M7/full goal remain open. Browser pixels,
remount/buffering, invalid/content heights, area binding, context and all
omitted/empty option distinctions are not proven by this native batch. Pending
API/hash/queue/parser choices stay pending; existing colconfig_params changes
are excluded from this batch's commit/push.


### Nonpositive area height, caller-visible error and registration stage (2026-10-31)

Nine independent native sessions/27 runs/339 raw frames retain all 51 ordered
widget/report projections in text-area-height. Inputs truncate to EDITE and
callbacks run before height validation. -2147483648/-1/0 raise the exact SDK
StreamlitInvalidHeightError after registration without an area emission; caught
state writes/retries have exact frozen Python errors, and next-run recovery
retains EDITE. Positive 1/67/68/94/96/i32::MAX controls emit accepted pixel heights.
This is not a browser minimum-height/clamping result.

Rust now checks height after registration and before push, returning its existing
WidgetError::InvalidValue with exact SDK height payload. No public enum/method/
module/dependency or generic Entry conversion was introduced. The actual Rust
Display prefix is retained. Public unit and real-WS comparison failed before
correction (target/text-area-height-before.log). All-targets Clippy -D warnings
and Rustfmt, then the public unit and all 31 related query-module checks passed,
excluding its existing queue comparison (text-area-height-clippy.log,
text-area-height-unit.log and text-area-height-integration.log under target/).
The public unit checks the existing Rust variant/payload, no failed emission,
updated state, write lock and later recovery. Native API comparison projects
Python height errors to payload text and lock errors to a rejection boolean;
raw source exceptions are not relabeled as Rust classes. All input/session/ID/
flag/field and within-runtime identity relations are checked.

Verification exposed a separate existing duplicate-key difference: the wrapper
register_widget_parity emits an exception, sets Stop and returns a default,
whereas Python can catch the duplicate and continue. The first post-fix unit
asserting a returned DuplicateKey failed (target/text-area-height-duplicate-gap.log).
The height correction does not change that shared takeover. Public duplicate
retry is excluded from Rust parity, explicitly removed from only the expected
API projection; the untouched Python capture and its gate still require exact
duplicate type/message and same-run registration occupancy. This difference
remains open in the existing error-entry design; passing height checks do not
close caught-duplicate or unhandled exception UI compatibility.

Full Rust workspace passed 286: library 279, ledger 1, macros 2, rustdoc 4.
Only the two existing navigation_pages_switch_and_session_state_match_the_measured_wire
and rerun_queue_messages_match_frozen_reference were skipped; this is not full
workspace green (target/text-area-height-workspace.log). Existing MSVC linker
stdout warning remains. 165 related query/matrix/docs Python checks passed with
DeprecationWarning as error (target/text-area-height-final-gates.log).

The reference gate rejects six coherent wrong-wire mutations: early state/
callback loss, released registration, wrong error type/message, lost recovery
and rejection of positive height. Original PB/summary and all 51 source event
positions are bound. Socket/server closed and port 60687 was read back free.
No full Python reference suite was rerun in this batch. Content/stretch builders,
mixed-invalid parameters, all lock/duplicate error text parity, browser behavior
and pending API/hash/queue/parser choices stay open. Matrix/inventory retain
130 partial entries and M3/M5/M7/full goal. Existing colconfig_params changes
remain outside this batch's commit/push.


### Area width registration stage and width-before-height priority (2026-10-31)

text-area-size adds eight native sessions/24 runs/298 original frames/42 ordered
widget/report API projections, retaining the earlier height-only capture. Width/
height pairs include negative/minimal/zero width with invalid height, valid
width with zero/negative height, and 1x1/max-i32 positive controls. SDK errors
follow registration, width before height; EDITE input/callback, write locks and
next-run state are retained. Source raw classes/text, including caught duplicate
errors, remain exact. Rust parity continues the documented narrow projection:
height/width payload text and write-lock rejection, not fabricated SDK exception
classes/lock text or caught-duplicate parity.

The prior Rust width helper ran before registration, produced 'width must be
positive', and allowed the caught write to change state. Public unit and native
comparison both failed before correction (target/text-area-size-before.log).
Only text_area now checks width after registration ahead of height, returning
its existing InvalidValue payload. The shared width helper and other widget
producers remain unchanged; callback ownership uses take rather than cloning.
No public enum/method/module/dependency or generic Entry change was introduced.

All-targets Clippy -D warnings and Rustfmt passed, then the public unit and all
32 related query-module checks passed, excluding its existing queue test
(text-area-size-clippy.log, text-area-size-unit.log, text-area-size-integration.log
under target/). The unit checks actual Rust variant/payload and width-first
priority, no invalid element, state/write locks and next-run recovery. Native
comparison checks all 42 API projections and within-runtime identity relations.
172 related query/matrix/docs Python checks passed with DeprecationWarning as
error (target/text-area-size-final-gates.log). Shared height/size gates reject
six coherent mutations per capture, including height-preempts-width type,
early registration/state loss, wrong message, lost recovery and positive-height
control rejection. Original PB/summary, exact requests/inputs/IDs/history,
version/session groups, emission absence/order and complete dimensions are bound.
No full Python reference suite was rerun in this batch.

Full Rust workspace passed 288: library 281, ledger 1, macros 2, rustdoc 4.
Only the two existing navigation_pages_switch_and_session_state_match_the_measured_wire
and rerun_queue_messages_match_frozen_reference were skipped; this is not full
workspace green (target/text-area-size-workspace.log). Existing MSVC linker
stdout warning remains.

Owned socket/server closed; port 63502 was read back free. Caught duplicate-key
and unhandled exception UI remain in the existing pending error-entry design;
no passing width check closes those differences. Browser dimensions, all mixed
invalid parameters, content/string sizes and other widget producers remain open.
Matrix/inventory retain 130 partial entries and M3/M5/M7/full goal. Existing
colconfig_params modifications are excluded from this batch's commit/push.


### Bound input width errors preserve earlier URL correction (2026-10-31)

text-input-width retains five native sessions/20 runs/254 raw frames and all
39 ordered API projections: five URLs, fourteen widgets and twenty reports.
Each width (i32::MIN,-1,0,1,i32::MAX) gets load, submitted input, URL-only update
and valid recovery. Submitted EDITEDtail truncates to EDITE and calls back once.
URL-only LONGURL becomes LONGU with no callback and emits its corrected URL
before the report, including failed nonpositive-width calls. State/write locks
and final LONGU recovery persist; exact positive widths remain accepted.

The previous Rust width check preceded registration/binding/flush. Public unit
and complete native comparison both failed before correction (target/text-input-
width-before.log). Only text_input now validates width after register, binding
metadata and flush_query_update, before push; existing InvalidValue carries the
SDK width payload. No public enum/method/module/dependency, shared width helper
or queue policy changed. Callback ownership uses take without an extra clone.
The public cold-binding unit checks the actual Rust variant/payload, LONGU state,
state/query locks, one corrected URL, no widget and valid next-run recovery.
API comparison uses the existing explicit error projection; caught duplicate-
key, SDK exception-class/lock-text and unhandled error UI parity remain open.

All-targets Clippy -D warnings and Rustfmt, then the public unit and all 33
related query-module checks passed, excluding its existing queue test
(text-input-width-clippy.log, text-input-width-unit.log and text-input-width-
integration.log under target/). 179 related query/matrix/docs Python checks
passed with DeprecationWarning as error (target/text-input-width-final-gates.log).
Shared raw SDK lock/duplicate constants retain exact source messages. Six
coherent mutations reject missing/delayed URL, spurious callback on URL seeding,
wrong state/write lock and lost recovery. PB/summary, exact requests/input IDs/
history, runtime/session groups, original defaults/limits/query key/sync/width
and all 39 event positions plus identity relations are checked. Earlier raw
captures are unchanged; the full Python reference suite was not rerun here.

Full Rust workspace passed 290: library 283, ledger 1, macros 2, rustdoc 4.
Only the two existing navigation_pages_switch_and_session_state_match_the_measured_wire
and rerun_queue_messages_match_frozen_reference were skipped; this is not full
workspace green (target/text-input-width-workspace.log). Existing MSVC linker
stdout warning remains.

Owned socket/server closed; port 61372 was read back free. Matrix/inventory
retain 130 partial entries and M3/M5/M7/full goal. Browser URL/size behavior,
other invalid parameter combinations and producers, caught duplicate and
unhandled error UI remain open. Existing colconfig_params modifications are
excluded from this batch's commit/push.


### Real text-area UI comparison (2026-10-31)

Existing inputs examples were exercised through the actual Chrome UI against
SDK 1.66.1 and a fresh Rust inputs build at 3219f3e. Each side retained five
runs/65 raw WebSocket events: controlled warm reload, multiline Unicode edit
committed on blur, sms peer rerun retaining text, empty submission, restoration.
Frozen evidence: tests/reference/reference-browser/inputs/text-area-ui/settled
and tests/browser/rust-inputs/text-area-ui/settled. Their manifests retain source,
binary and collector hashes, runtime provenance, visual review and cleanup.
At the same 1463x724/DPR 1.75 viewport both render a 92px textarea inside a
121.14286px stTextArea, with nominal wire height 122. All ten actual screenshots
were inspected with matching before/after DOM and echoes. The returned image
bytes are JPEG despite inherited .png filenames; preserve bytes and gate decoded
format/dimensions plus SHA256. The earlier background SDK attempt is explicitly
unsuccessful and retained separately; it does not count as accepted evidence.
Existing test_inputs_contract.py checks raw protobuf types, input values,
identity/session continuity, five successful completions, cursor coverage,
rendered values/geometry and screenshots; seven evidence-damage cases fail.
No production/API/dependency changes. Browser remount/history/IME, collapsed or
dynamic options and invalid-size/error UI remain open. This scoped result does
not erase the older capture's 9px boundary or establish all frontend parity.
Owned tab/servers closed; ports 8508/8618 read back free. All 130 partial rows,
M3/M5/M7 and the full goal remain open; unrelated colconfig_params work excluded.

Validation for this batch: fresh offline/locked inputs example build passed; 83 focused Python input/matrix/documentation checks passed with deprecation warnings as errors. No production Rust changes and no repeat full Rust workspace run.


### Text-area binding oracle prepared; interface still pending (2026-10-31)

The existing forms fixture already accepts SDK text_area bind="query-params".
Add only text-bound-area to the existing native collector, reusing the twelve
bound-text steps with kind=area. The frozen reference retains 162 raw frames,
12 same-WS runs, 12 widget/state pairs and seven ordered URL corrections.
The existing bound-text gate now selects the widget kind explicitly and checks
all input/history flags, exact URL order, state/callbacks/default/value/set_value,
identity stability and area layout (nominal 122px/stretch). Four coherent raw
protobuf/summary mutations reject wrong URL, history value/report, callback and
height. Source SDK results agree with text_input for these twelve steps; this
is no Rust implementation or browser proof. Existing fixture and old captures
are unchanged; TextAreaOptions.bind(TextBind) remains a proposal awaiting the
user's public-interface choice. No production Rust/API/dependency changes.

Before this reference addition, full Python reference regression at c02ac89
passed 1872 tests with deprecations as errors (target/reference-current-full.log).
After addition, 184 focused query/matrix/documentation tests passed. The full
suite was not rerun after this five-test addition. The owned SDK server/socket
closed and port 54510 was read back free. Matrix stays 130 partial and the full
goal stays open. Unrelated colconfig_params changes remain excluded.


### Integer number-input unset wire bounds (2026-10-31)

Pinned SDK 1.66.1 fills each omitted integer min/max with the JavaScript safe
integer sentinel (-/+9007199254740991) while has_min/has_max record explicit
constraints only. Rust emitted 0/f64::MAX, affecting the frontend boundary.
Correct only those two protocol fallback values in widget_api.rs; float and
explicit bounds, public API, identity and submitted-state handling are unchanged.
The misleading old integer-default comment is replaced with the measured rule.

Reuse existing widget_params examples/collector behind probe=integer-bounds;
the original default eight elements and historical captures remain unchanged.
Each new native capture retains one complete run, 19 raw frames/15 elements:
original eight plus seven integer cases (free, min-only, max-only, explicit zero
min/max and both safe endpoints). Existing reference tests now bind raw PB to
summaries/elements, pin all seven values/bounds/flags/step/type/format, preserve
the eight-element baseline and reject coherent wrong-min/max/explicit-flag data.
Public Rust unit failed before correction with (0,f64::MAX), then passed the
same seven configurations and returned values. Native SDK/Rust wire gates pass.

Check/all-target Clippy and formatting passed; the existing MSVC linker stdout
warning remains (its lint ignores -D warnings). Workspace passed 291 tests:
library 284, ledger 1, macros 2 and rustdoc 4. Only the two existing
navigation_pages_switch_and_session_state_match_the_measured_wire and
rerun_queue_messages_match_frozen_reference were excluded, so this is not a
claim of complete workspace green. Logs: target/number-integer-{red,green,check,
clippy,build,workspace}.log. SDK collector cleaned its owned server/socket;
Rust owned process 3596 was verified by path then stopped; ports 57650/8599
were read back free. Native wire evidence does not prove browser stepper,
client validation UI, empty-number options, submitted out-of-range behavior,
callbacks or dynamic-bound state correction. These remain open with the full
goal and all 130 partial rows. Pending area binding/API/queue/parser decisions
and unrelated colconfig_params changes are unchanged and excluded from staging.

This batch also passed 59 focused Python widget-reference/matrix/documentation checks with deprecations treated as errors; the complete Python suite was not repeated after the existing 1872-test snapshot.


### Keyed number dynamic-bound reference (2026-10-31)

Existing widget_params fixtures/collector add opt-in number-sequence. Both SDK
and Rust native traces retain 12 same-WS runs/83 raw frames/24 ordered elements:
load, submit 7, explicit min zero, narrow max, grow, changed default, submit 1,
raise min, step, disabled, recover, native assignment. Exact input IDs/types,
phase/query/history, bounds/default/flags/step, state/callbacks, identity/session
continuity, successful finishes and reset value/set_value are gated from raw PB,
summary and element equality. Four coherent mutations reject wrong identity,
sync, callback and reset value/report. A public Rust unit failed before the
change (valid retained 7 became 4), then passed identity/state/locks/recovery.
A separate Rust-only unit checks float reset and noncoercion of wrong types;
it is not additional native SDK float-sequence evidence.

Clippy/all-target and formatting passed; workspace passed 293 tests (library
286, ledger 1, macros 2, rustdoc 4), excluding only the existing navigation_pages_switch_and_session_state_match_the_measured_wire and rerun_queue_messages_match_frozen_reference.
Thus full workspace green is not claimed. Existing MSVC linker stdout warning
remains; logs are target/number-sequence-{red,green,clippy,build,workspace}.log.
Owned SDK socket/server closed; Rust PID 20008 verified by executable path then
stopped; ports 59513/8599 read back free. No production browser evidence, full
float differential, key type changes, malformed input or all dynamic options
claim. Pending NewElement hash/API/queue/parser decisions, 130 partial entries
and M3/M5/M7/full goal remain open; colconfig_params work remains excluded.

Focused widget-reference/matrix/documentation validation passed 65 Python tests with deprecations as errors; the full Python suite was not repeated in this batch.


### Unkeyed number identity differential (2026-10-31)

Each SDK/Rust normal capture retains 21 same-WS runs/146 raw frames/42 ordered
widget/report elements under widget-params/number-unkeyed/normal. Policies
(disabled, hidden, ignore, absent callback) preserve edited input; raw omitted
versus explicit step 1, optional zero min/max, width/help/default and step 2
identity relations are checked pairwise across all stages. Five actual inputs
and cumulative callbacks, exact values/defaults/bounds/flags/step/type/width,
policy fields, session/run continuity and successful completions are gated from
raw PB/summary/elements. Returning cleaned old IDs starts at the default.
Four coherent mutations reject wrong identity, revived value, width or step.
Two public Rust units failed before the fix, then passed raw-step, optional-zero,
width identity and normal restoration. Effective float/integer wire defaults
and existing keyed behavior retain their prior checks.

The first SDK 21-run capture used st.stop(), so its revived values cannot prove
normal cleanup; original bytes plus attempt.json remain and a negative gate
rejects it as the normal oracle. New natural-completion keyed SDK/Rust captures
also reproduce all twelve prior results; historical keyed st.stop bytes stay
unchanged. No native unkeyed-state read is fabricated, only return/callback/wire.
All-target Clippy and formatting passed (existing MSVC linker stdout warning
remains). Workspace passed 295 (library 288, ledger 1, macros 2, rustdoc 4),
excluding only the existing navigation_pages_switch_and_session_state_match_the_measured_wire and rerun_queue_messages_match_frozen_reference.
Logs: target/number-unkeyed-{red,green,clippy,build,workspace}.log. Owned SDK
servers/sockets and Rust PID 60880 were stopped, with executable verification
for Rust and ports 62590/54346/54987/8599 read back free. No browser dynamic
props/IME/remount, full float/type/error or stop-cleanup parity claim; 130 partial
and M3/M5/M7/full goal stay open. Unrelated colconfig_params work is excluded.

Focused widget-reference/matrix/documentation checks passed 74 Python tests with deprecation warnings treated as errors. Full Python suite was not repeated; inventory remains 130 partial with the newly explicit stop boundary moving one entry from no-explicit-gap to unmeasured parameters.


### Stop widget cleanup correction (2026-10-31)

Fresh SDK/Rust explicit-stop captures each retain 21 runs/146 frames/42 ordered
widget-report elements. Three restored IDs retain 7 through stopped finishes;
pre-fix Rust stopped-before/trace.json lost them as 4 and is permanently gated
as an expected failed comparison. Both runtimes' additional stopped-resume
captures retain 23 runs/160 frames/46 elements: after 21 stops, normal-resume
still sees 7, normal completion removes stale identities, and explicit-step
restores its default 4. Exact request stop flags, IDs/identity relations,
inputs/returns/callbacks, fields/layout, sessions/completions and raw PB/summary/
element equality are checked. Three coherent mutations reject lost stopped
values, extra callbacks and revived state after a normal completion.

A Rust lifecycle unit first failed lost state, then passed preservation of
unseen keyed/unkeyed records and URL binding plus trigger=true at stopped finish;
next begin resets trigger=false, and normal finish removes stale records/URL.
The bound native-key preservation rule is corrected by the later lifecycle
reference below. The
unit setup explicitly calls the same post-registration binding marker as public
controls. This is a Rust guard, not a fresh native/browser bound-URL or button
stop journey. Existing stopped/normal references remain unchanged.

All-target Clippy and formatting passed. Workspace rerun passed 296 (library
289, ledger 1, macros 2, rustdoc 4), excluding only the two existing navigation_pages_switch_and_session_state_match_the_measured_wire and rerun_queue_messages_match_frozen_reference.
The first workspace build overlapped the owned running example, causing Windows
LNK1104; stop-cleanup-workspace-locked.log preserves that failure, and retry
succeeded after process shutdown. Existing MSVC linker stdout warning remains.
Other logs: target/stop-cleanup-{red,green,clippy,before-build,build,workspace}.log.
Owned Rust PIDs 24284/47392 were path-verified then stopped; SDK collector closed
its servers/sockets; ports 8599/54872/65442 were read back free. Broader stop,
error/fragment/navigation and browser lifecycle remain open. No public API,
dependency or queue policy change; full goal/130 partial and pending decisions
remain open, and unrelated colconfig_params edits are excluded.

Focused widget-reference/matrix/documentation checks passed 82 Python tests with deprecations as errors; full Python suite was not repeated in this batch.


### Stop, trigger and hidden query-bound lifecycle (2026-10-31)

Existing widget_params fixtures/collector add opt-in stop-lifecycle. Each SDK
and corrected Rust capture retains eight same-WS runs/62 raw frames/20 elements
(11 reports, nine widgets) plus three URL messages. Load creates a button,
ordinary text and bound text; submitted trigger/plain/bound states dispatch
three callbacks before early stop; the next stopped run resets the button but
retains text states. Re-registration resolves the URL, normal hide deletes the
URL and ordinary keys but retains bound native=url, and restoration emits URL
before the bound widget with value/set_value. Final normal hide clears URL again.

Pre-fix Rust lost bound native state and restored base instead; its raw capture
remains gated as expected failure. Python tests bind raw PB/summary/elements,
all exact requests/typed inputs, callback values/order, IDs, widget fields/layout/
one-shot effects, sessions/completions and ordered reports/URL/widget emissions.
Five coherent mutations reject lost native state, stuck trigger, lost callback,
wrong URL and URL sent after its widget. A new real-WS Rust integration replays
the SDK requests and checks all fourteen ordered report/URL projections; the
existing helper only gains button-ID mapping and fire-key admission.

A Rust unit failed before the fix then passed hidden/restored bound state,
identity, default/nondefault synchronization and URL repair. The default branch
is a Rust guard, not a separately captured SDK default-remount journey. The
prior stop lifecycle unit is corrected to preserve bound native keys while still
removing stale records/URL and resetting the trigger on the next real input.
No browser, history/remount, alternate binding producers, explicit persist API,
all native assignment/type/invalid-URL or error-lifecycle parity is claimed.

All-target Clippy and formatting passed after removing a needless return in
the new test fixture. Workspace passed 298 (library 291, ledger 1, macros 2,
rustdoc 4), excluding only the existing navigation_pages_switch_and_session_state_match_the_measured_wire and rerun_queue_messages_match_frozen_reference.
Existing MSVC linker stdout warning remains. Logs: target/stop-lifecycle-{red,
green,stop-unit,integration,clippy,build,workspace}.log. Owned Rust PIDs 40940/72148
were path-verified and stopped; SDK collector closed its socket/server; ports
8599/57333 were read back free. 130 partial and M3/M5/M7/full goal remain open;
public API/hash/queue/parser decisions and unrelated colconfig_params edits
are unchanged and excluded from staging.

Focused widget-reference/query-parameter/matrix/documentation validation passed 222 Python tests with deprecations as errors; full Python suite was not repeated in this batch.


### Cold bound-text assignment reference (2026-10-31)

text-cold/trace.json retains 12 independent sessions, each assignment then
observation: 24 runs/312 raw frames/60 ordered projections (24 widgets, 24 state
reports, twelve URLs). The three code inputs are full Unicode text, effective
default abcde and None; each meets missing, valid-long, default-folding or empty
URL. Inputs contain no widget state and callbacks remain empty. Native code
text stays untruncated; selected URL text is truncated; empty and None differ.
Fresh assignment without URL has no backend URL message. Default-folding URL
is removed even when a nondefault code value remains. None changes the effective
wire default until a non-null value wins; raw options still give stable identity.

Python gates bind exact request/history flags, sessions/version, raw PB/summary,
full widget/default/value/set_value/query-key/max_chars fields, layout/one-shot,
ordered URL/widget/report events and callback/state values. Six coherent cases
reject cold extra publication, native truncation, wrong precedence, None loss,
wrong fold and late URL. Real Rust WS replay checks all sixty projections and
pairwise identity relations. Initial replay lacked cold opt-ins in two widget
projection branches; target/text-cold-adapter-before.log preserves that adapter
failure, and final replay passes after the scoped test-helper correction.

No production Rust changes: the suspected guard removal would have broken the
frozen SDK behavior and was not made. The existing forms fixture's old bytes,
including CRLF, are unchanged outside two opt-in assign-default lines. SDK
collector closed its server/socket; port 57333 read back free. All-target Clippy
and formatting passed (existing MSVC linker stdout warning remains). Native
query module passed 35 tests, retaining only its existing rerun_queue_messages_match_frozen_reference exclusion. Navigation and the rest of the workspace were
not rerun; the previous full Rust result remains a prior snapshot. Logs:
target/text-cold-{replay,clippy,query-regression}.log. Browser URL/IME/remount,
alternate bindings and broader source/error combinations remain open with 130
partial and M3/M5/M7/full goal. Existing pending choices and colconfig_params
work are unchanged and excluded from staging.

Related query/widget-reference/matrix/documentation validation passed 229 Python tests with deprecations as errors; after comment/control-flow cleanup, the focused cold guards also passed. The full Python suite was not repeated.


### Hidden/remounted binding investigation — known mismatch (2026-10-31)

text-restore/trace.json retains twelve independent sessions, 48 runs/584 raw
SDK frames and 116 ordered projections: 36 widgets, 48 reports and 32 URLs.
Each session loads SEED, hides normally, restores/assigns/uses history, then
observes again. Four URL sources (missing, long, default-folding, empty) combine
with three actions. History carries the old ID's valid string and invokes no
callback. Raw PB/summary/version/session, exact inputs/flags, values/defaults/
sync/layout/one-shot, identity and all URL transitions are gated; six coherent
origin/assignment/history/coalescing/hidden-state/callback mutations fail.

Actual Rust WS replay at production base 0a803a9 failed: 109 projections, 25 URLs;
assignment after hide chose URLTO or empty where SDK chose code長🧊extra, and
intermediate/repeated URL writes were missing. Derived projections are retained
under tests/browser/rust-queryparams/text-restore/observed-before.json; no raw
Rust PB or browser capture is claimed. The exploratory test and diagnostic
printing were removed after the run; no new ignore or passing-native assertion
was introduced. The architecture proposal gives the exact test snippet/command
to reproduce 116-vs-109, and target/text-restore-before.log retains the failure.
This new scenario is not part of a claimed passing Rust compatibility suite.

Production remains unchanged. The shared-state representation and URL snapshot
queue are pending the user's architecture choice; SDK gates passing means the
oracle is protected, not that Rust matches. Existing source/callback/history,
public API/queue/parser decisions and 130 partial/full goal remain open. SDK
server/socket closed and port 54687 read back free. Other checks and their exact
scope are recorded after final verification; unrelated colconfig_params work
remains excluded from this batch.

Final evidence checks: 237 related Python reference/widget/matrix/documentation
tests passed with deprecations as errors; all-target Clippy/format checks passed
with the existing MSVC linker stdout warning. The existing Rust query group
passed 35, retaining its pre-existing queue exclusion; full workspace/Python
suites were not repeated. These results do not include a passing text-restore
replay: that new live comparison remains the confirmed 109-vs-116 failure.


### 浮点动态 number_input 原生差分（2026-10-31）

number-float 的 SDK/Rust 冻结采集各十二轮、83 原始帧、24 有序控件/状态元素。
7.25/1.25 的 double_value 提交只触发两次 callback；动态收缩上下界回到默认
4.25 并发送 value/set_value，默认值/步长/禁用变化保留当前值，代码赋值同步
8.25 且不触发 callback。现有门禁复用整数流程并明确选择 FLOAT、%0.2f、f64
哨兵、分数值和精确输入类型；七类一致 raw PB/summary 篡改必须拒绝。
证据位于 tests/reference/reference-browser/widget-params/number-float/trace.json
和 tests/browser/rust-widget-params/number-float/trace.json。两侧服务/WS 均已关闭，
端口 62000/8599 已读回无监听。本批只补探针和回归，不修改生产行为。此证据
不证明浮点浏览器提交、stepper、非有限/非法/越界输入或可空接口的完整兼容。
共享状态选型、116 对 109 的已知失败、130 partial 与完整目标保持开放。

本批验证：示例构建、定向 Clippy 和 rustfmt 检查通过（仍有既有 MSVC linker
stdout warning）。相关 Python 首轮 248 通过、1 项派生清单不一致；运行既有
export_m3_inventory.py 同步后，仅重跑该失败项并通过。日志保留在
target/number-float-{build,clippy,reference}.log。未重复全工作区或全 Python
套件。派生清单仍为 130 partial；提交排除用户 colconfig_params 修改。


### number_input 相等边界及非正步长（2026-10-31）

SDK 与修后 Rust 的 number-permissive/trace.json 各一轮、22 原始帧、18 有序
元素，包含整数/浮点各三组可接受参数（相等边界、零步长、负步长）及各三组
拒绝对照（倒置范围、过小/过大默认值）。修前原生 before/trace.json 一轮/
16 帧/12 报告，六组 SDK 合法调用全被拒绝；作为明确失败证据保留并设负向门。
公开接口单元先红后绿；门禁还核对 raw PB/summary/elements、一轮完成、精确
值/原生状态、类型/格式/范围/标志/step 及控件和报告顺序，六类一致篡改会失败。
Rust 修改仅为两处校验条件及对应错误说明，无公共 API、身份、状态或 slider
改动。拒绝报告只衡量 accepted=false 后继续运行，不证明异常类型/文案/UI
等价；真实浏览器非正 step 行为和非有限/协议输入仍开放。服务/WS 已关闭，
58653/8599 端口读回无监听。完整目标、130 partial、状态待选和 109/116 差异保持开放。

本批格式/全目标 Clippy 通过（既有 MSVC linker stdout warning 保留）；工作区
共 300 项通过：library 293、ledger 1、macros 2、rustdoc 4。仅保留原两项排除：
server::tests::navigation::navigation_pages_switch_and_session_state_match_the_measured_wire
及 server::tests::queryparams::rerun_queue_messages_match_frozen_reference。
258 项相关 Python 参考/矩阵/文档检查通过，未重复完整 Python 套件。日志为
target/number-permissive-{red,green,clippy,build,workspace,reference}.log；首次
编辑保护断言中止后保留的再次失败记录另见 target/number-permissive-edit-not-applied.log，没有修改
slider 校验。用户 colconfig_params 改动不纳入本次提交。


### number_input 非正步长真实浏览器验证（2026-10-31）

SDK 1.66.1 与生产 head 639e2bf 的 Rust 各八个 settled 阶段、七轮/161 原始
WS 帧，126 有序控件/JSON 元素，八张原始图；Chrome 视口 1463×724/DPR1.75。
证据为两侧 number-permissive/ui/settled/trace.json，同目录保存截图。相等
int/float 边界的两个按钮禁用；wire step=0 对应 DOM step=1/0.01；加号分别
得到 4→5、1.50→1.51；负 step 的加号分别得到 4→2、1.50→1.25。真实键盘
输入 Int equal=3 后 blur 显示相同范围错误，不发 WS，后端仍为 2；改回 2 后
正常重跑，再用键盘输入 Float negative step=2.75，blur 后状态和报告均为 2.75。

第一次同调用截图有滞后：DOM 已更新但报告图仍旧，错误图甚至仍显示选中的
旧值 2。原 ui 根目录的 trace/图保留并标记 rejected，负向门禁止其冒充通过。
重采分开动作/AX 确认与下一次调用的截图，十六张 settled 实图均逐张目视检查，
对应输入、报告和错误外观一致；不声称像素差分相等。返回原始字节为 JPEG，
继承 .png 文件名但不转码；门禁核对实际格式、尺寸和 SHA256。

采集仅通过 CUA Chrome 控制和获准的 tab-scoped CDP 事件；普通点击/真实按键，
DOM evaluate 只读。进入页后启用 Network，受控 warm reload 后按游标逐阶段
保留事件；settled 窗口均无 truncated/hasMore。最初跨 origin 的缓冲覆盖和
离开 HTTP origin 后关闭事件读取被拒绝，均保留为诊断限制，未绕过权限。
settled 在跨 origin/关页前停止网络观察，明确不声称保留了 WS close 事件。
两批均核对进程身份后停止自有服务，8599/8619 读回无监听，专用标签页关闭。
首批 SDK 进程停止时出现 WinError10054 的管道清理输出；采集的七轮均已正常
完成且没有应用 exception，不据此推断服务整体健康。第二批停止无新增输出。

离线门禁逐条解码 PB、核对输入类型/ID/值、七轮完成和会话/控件身份、全部
number_input 字段、报告/路径/顺序、DOM 值/边界/step/按钮/错误、事件覆盖和原图字节。
六类破坏反例覆盖 DOM step、同步修改 raw/DOM step、输入类型、图哈希、游标
覆盖和缺阶段。此批没有修改生产代码或接口；回调/异常文案/其他类型及历史/
页面组合仍未证明完整兼容。共享状态选型、109/116、130 partial 和完整目标开放。

本批最终 268 项相关 query/widget/matrix/docs 检查通过，弃用警告作为错误；
日志 target/number-permissive-ui-reference.log。没有重复 Rust 构建/Clippy/
工作区测试，因本批生产与 Rust 源码未变；上一批 300 项及两项排除仍是上一批
结果，不当作这批新增验证。用户 colconfig_params 修改保持隔离、不提交。


### 有 key 输入及提交按钮跨表单（2026-10-31）

form-identity 原生参考：SDK/Rust 各七轮、70 原始帧、36 有序条目（含四个 form
block）。root 提交 7/EDIT，迁入 alpha/beta 保留 keyed 数值/文本；beta 批量提交
8/NEXT/无 key=6 和 trigger 后，回 root/alpha 保留 8/NEXT，但清理后的无 key 值
回到 4。number/note/apply 三个 key 的 ID 分别稳定，无 key 按 root/alpha/beta
分为三个 ID，协议 form_id 跟随当前上下文。各轮自然结束，未用 stop 保留旧值。

修前 before/trace.json 七轮/65 帧/31 条目：迁入 alpha 回到 4/base，换 beta 时
submit ID 变化触发已有 preseed 拒绝，表单回滚并输出错误 markdown。负向门按
真实 PB 和这些错误/状态固定失败；首次误用成功解析器被 markdown 拒绝，已
定向校正并通过，没有放宽成功场景白名单。公共接口单元先红后绿。

生产只改 InputOptions.identity_in_form 和 form_submit_button 两处私有拼接；
保留无 key form 区分和 extra 约束，不改公开 API、共享状态、rollback、输入
类型错误策略。门禁核对 raw PB/summary/elements、精确输入/类型/ID/trigger、
会话/完成、字段/form block 布局/路径/报告及身份关系，五类一致篡改会失败。
证据为两侧 widget-params/form-identity/trace.json，修前另存 Rust 同目录 before。
SDK collector 已关闭服务/WS；原生服务按路径确认后停止；52191/8599 读回无
监听。本批没有浏览器验证，不证明前端 label/help/form、sidebar/页面身份、
其他控件及回调/错误提交的完整兼容。130 partial、109/116 和状态待选保持开放。

本批格式和全目标 Clippy 通过（既有 MSVC linker stdout warning 保留）；工作区
301 项通过：library 294、ledger 1、macros 2、rustdoc 4。仍只排除既有
server::tests::navigation::navigation_pages_switch_and_session_state_match_the_measured_wire
和 server::tests::queryparams::rerun_queue_messages_match_frozen_reference。
276 项相关 Python query/widget/matrix/docs 检查通过，未重复完整 Python 套件。
日志 target/form-identity-{red,green,clippy,build,workspace,reference}.log；定向
负向门校正结果见本轮工具输出。补充原先空 limitations 的两条表单记录后，
派生清单仍为 130 partial，未测参数桶 94、未明确缺口桶 33，其余桶不变。
用户 colconfig_params 修改不纳入本次提交。


### 跨表单真实浏览器提交——已知 hash 失败（2026-10-31）

现有 form-identity 探针加 ui=on 时渲染 Location 选择器，未开启时仍运行原七轮
协议场景。SDK/Rust 各八阶段、九轮/98 原始 WS 帧和八张图；实际 Chrome 同一
标签页先后验证，视口 1463×780/DPR1.75，普通点击与真实键盘。每次动作/AX
确认后下一调用采集 DOM、原图和原连接事件，全部窗口无 truncated/hasMore。
十六张图逐张目视核对其实际控件/报告，不声称两侧行为全部匹配或像素相等。
返回原图字节为 JPEG，继承 .png 名称并保持不转码，核对格式/尺寸/SHA256。

SDK root 分别编辑到 7/EDIT/9，迁入 alpha/beta 后 keyed 保留 7/EDIT、无 key
变 4。beta 中草稿 8/NEXT/6 不发任何 WS，报告仍旧；Apply 后一次提交五个状态
（Location、三个输入和 trigger），报告为 8/NEXT/6、submitted=true。回 root/
alpha 保留 8/NEXT，无 key 恢复 4。源参考门固定全部九轮和八个 DOM 阶段。

Rust 在 beta 草稿阶段与 SDK 一致，但 Apply 实际发旧 7/EDIT/4 和 trigger，
报告 submitted=true 且 native 仍是旧值；返回 root/alpha 仍旧 7/EDIT。等待
NEXT 超时后，检查同一连接确认该轮已完成，再保留失败现场，未因观察超时
重启或重复点击。Rust capture 显式 successful=false、semantic_match=false，
collection_complete=true；负向门固定原始请求、输出和图片，要求完整 SDK
判定失败，没有把测试绿解释为 Rust 功能通过，没有增加 ignore。

两端原始按钮 form_id 都依次 alpha/beta/beta/alpha，widget ID 各自稳定；SDK
消息 hash 为 A/B/B/A，Rust 始终 4aebfc5b0fdec90a6e1fdf37d79410c3。当前
ButtonElement::render 的 hash 只拼 id/label/type/width；已复核捆绑前端
index.Dlja0TUX.js 的 to()/applyDelta，hash/type 相同且没有 one-shot 时复用
旧 Element。此链解释前端缓存旧表单按钮、没有 flush beta 草稿的实际结果。
本次未修改任何生产 hash；继续等待 architecture 的三选方案，不能用改变
widget ID 来掩盖此前已修正并验证的 key 身份规则。

门禁复用既有表单原始解析器，UI 分支显式允许 Location selectbox，原协议
默认白名单不扩张。核对九轮完成/会话、所有精确输入（位置切换携带上一上下文
无 key ID）、稳定 key/三类无 key ID、路径、DOM 表单归属/标签/草稿/报告和
hash 等价关系；四类篡改为按钮 hash、提交值、草稿 DOM、图哈希。证据为两侧
widget-params/form-identity/ui/trace.json，原七轮直接协议参考仍通过且单独保留。
网络观察在离开 origin/关页前停止，未保留 WS close 帧；专用标签页已关闭，
自有服务按进程身份核对后停止，8599/8619 读回无监听。

本批仅示例/SDK fixture、参考门和文档变更，生产实现、共享状态和公开接口
不变。hash 选型及 109/116 状态差异分别开放，完整目标和 130 partial 不关闭。

本批示例构建、定向 Clippy 和 rustfmt 检查通过（既有 MSVC linker stdout
warning 保留）；282 项相关 query/widget/matrix/docs 门通过，日志为
target/form-identity-ui-{build,clippy,reference}.log。这里测试通过表示 SDK
参考和 Rust 失败被正确保护，不能报告 Rust 浏览器兼容通过。未重复工作区/
完整 Python 套件；上一批 301 项与两项排除仍是上一批快照。用户 colconfig_params
改动保持隔离。已向用户重发 hash 三选问题，尚无答复；不视此前错误恢复或
rerun Delta-only 的“1”为本次 hash 选型。


### 有 key 时间控件的 step/format 重置（2026-10-31）

temporal-params/keyed-identity 的 SDK/Rust 原生参考各十一轮、98 原始帧、44
有序控件/JSON 元素。初始 clock/moment/date 为 12:30、2024-03-15T12:30、
2024-03-15，随后三次 typed edits，穿插策略、step、format、默认值、宽边界、
参数恢复和观察。修改 time step 或 datetime step/format、date format 会重建
并回当前默认；time 24h→12h 格式、disabled/hidden/width/help、默认值与仍容纳
有效选择的边界保留状态。三个 ID 等价类数为 2/3/2，恢复旧参数不复活旧选择。

修前 native before/trace.json 同十一轮完整记录，但三个 kind 各只有一个 ID，
step 改变后还返回 13:45、六月 1 日，SDK 已回初始默认。公开接口单元先失败
13:45 对 12:30，修后三控件重建及 time 仅显示格式变化的保留断言通过。生产
只改三处 keyed identity extra，不改公开 API、无 key 身份、codec、共享状态、
hash 或队列。现有 temporal 例子/fixture/collector 加 --identity 探针，旧五元素
场景保持独立；采集自然完成，没有使用 stop 保留已清理值。

门禁绑定 raw PB/summary/elements、全部输入类型/ID/值/history、ID 关系、返回值/
原生状态、默认值/step/format/min/max/策略/宽度/sync、一次性标记及完成/会话；
五类一致反例保护三种约束 ID、被默认值覆盖的保留值和布局。SDK collector 已
关闭服务/WS，Rust 服务按路径核对后停止，64453/8600 读回无监听。日期范围/
空值/旧值越新界限、callback/type/error、timedelta、无 key 和浏览器验证仍开放，
不能把本次原生差分解释成完整 temporal 兼容。完整目标、130 partial、hash
选型与共享状态 109/116 差异继续开放。

最终工作区 302 项通过，保留 navigation_pages_switch_and_session_state_match_the_measured_wire
和 rerun_queue_messages_match_frozen_reference 两项既有排除；相关 query/widget/
temporal/matrix/docs 参考门 292 项通过。工作区/all-target Clippy 通过，既有
MSVC linker stdout warning 保留。日志为 target/temporal-keyed-{workspace,
reference,clippy,build}.log，定向公开接口红绿日志为 temporal-keyed-{red,green}.log。
采集后仅为 Rust 示例两处语义单元补空行；trace 内 producer source 与 binary SHA
保留采集时原值，不代表这一排版后的源码或重新构建产物。

### 无 key 时间控件的显示与边界身份（2026-10-31）

tests/reference/test_temporal_params_reference.py 新增锁定 1.66.1 的公开 AppTest
八轮断言，覆盖 load/edit/format/width/restore/edit-bounds/bounds/observe。
time 仅换 12h 保留 13:45；三个无 key 控件从 stretch 改为 360 都回初始默认；
恢复后重新编辑，再改 datetime 的有效边界，仅该控件回默认。逐轮实际返回值
和任意两轮 ID 的相同/不同关系均检查，三个 ID 等价类为 2/3/2。它是运行 SDK
的后端参考检查，不是新增原生 WS 或浏览器证据；没有删除或重采旧冻结参考。

Rust 同样八轮通过公开 API 注册、真实 typed WidgetState 输入和普通轮末清理，
逐轮检查返回值及 ID 关系；修前在 format 轮 12:30 对 SDK 13:45 失败，修后
通过。生产仅改三个无 key identity extra，原带 key 分支不变。红绿日志为
target/temporal-unkeyed-{red,green}.log，定向 temporal 门先通过 11 项。
指南先说明使用规则，再调整实现；没有新增公共接口、依赖或仓库文件，未改 UI 实现。

此切片不证明日历/时间选择器真实交互，也不覆盖 None/范围、秒或亚秒变化、
原始参数类型、全部 identity 字段、callback/error/URL/跨页组合。格式错误及
失败前身份占用顺序已调查但未实现；hash/共享状态选型与 109/116 差异仍开放，
完整目标和 130 partial 不关闭。

最终工作区 303 项通过（296 库 + 1 ledger + 2 宏 + 4 rustdoc），保留原
navigation_pages_switch_and_session_state_match_the_measured_wire 与
rerun_queue_messages_match_frozen_reference 两项排除；相关 query/widget/
temporal/matrix/docs 参考门 293 项通过。工作区/all-target Clippy、单文件
rustfmt 与 diff --check 通过，既有 MSVC linker stdout warning 保留。日志为
target/temporal-unkeyed-{workspace,reference,clippy}.log。用户 colconfig_params
改动保持独立，没有启动服务或浏览器，没有合并/发布/部署。

### 无 key 时间控件的同连接原生补证（2026-10-31）

新增 reference-browser/temporal-params/unkeyed-identity/trace.json 与对应
rust-temporal-params/unkeyed-identity/trace.json；每端普通完成八轮、71 原始帧、
32 有序 Element。原 WS 请求携带上一轮实际 ID，两个编辑批次分别提交 string
clock 与 string_array datetime/date；load/edit/format/width/restore/edit-bounds/
bounds/observe 的返回值、ID 等价类 2/3/2 与此前公开后端参考一致。无 key 时
native=[] 只说明本探针没有公开 key 投影，不能视作控件会话值读取验证。

门禁验证原始 PB 长度/summary、全部帧种类与 running 状态顺序、八次唯一
run/同一 session、完成和请求历史标记、全部输入类型/值/上一轮 ID、元素次序/
路径、ID 关系、返回值、默认值/format/step/min/max/width/策略/value 同步标志。
另规范化两端运行时 ID 和 JSON 正文，完整 Element 逐字段一致。六类反例同步
修改 raw/summary/元素，分别保护 time-format 身份、date-width 身份、datetime
边界身份、保留值、过期输入 ID 和布局。这里不把 hash 字节视为已经统一。

producer_sources_sha256 保留采集时三份源文件哈希；Rust 生产基线为 797936c，
生产源码无变更，另保留 widget_api 与实际二进制哈希及核对过的进程路径。
collector 自行关闭 SDK 服务/WS；Rust 按 71356 的完整路径停止，原 exec 会话
已终止，51098/8600 读回无监听。随后为共享 fixture 重新检查 SDK/Rust 的
keyed 十一轮及默认五元素模式，输出位于 target/temporal-unkeyed-wire-recheck/；
53796 同路径 Rust 服务也已停止，第二 exec 会话终止、8600 无监听。参考旧
trace 没有覆盖。SDK 临时服务由 collector 正常退出，不把缺少 close 帧当完成证据。

本批不改生产 API/身份/状态/hash/队列，仅增加采集、示例探针和回归证据；
未执行浏览器，亚秒/None/范围/错误/回调/URL/跨页组合继续开放，不能关闭
完整 temporal 能力、M3/M5/M7 或 130 partial。

最终相关 query/widget/temporal/matrix/docs 参考门 302 项通过（temporal 单模块
20 项）；示例构建、定向 Clippy、rustfmt 和 diff --check 通过，既有 MSVC linker
stdout warning 保留。日志为 target/temporal-unkeyed-wire-{build,clippy,reference}.log。
本批未改库生产代码或 Rust 单元，未重复工作区回归；上一批 303 项与两项排除
仍为上一批快照，不作为本批新跑的结果。用户 colconfig_params 文件保持独立。

### datetime 边界精度的接受性修复（2026-10-31）

SDK 公共 AppTest 十一组调查后，冻结 temporal-params/precision 原生参考及
Rust 修前 before/trace.json、修后 trace.json。SDK/修后 Rust 同一轮各 13 帧/
9 元素：八个成功 datetime 控件及十一案报告；修前 Rust 8 帧/4 元素只接受三组。
五个额外拒绝分别为秒/微秒边界归一化后相等、同分钟反序、空默认同分钟反序
及 min-only；全部修后接受。另三组跨分钟的默认值上下越界、min>max 仍拒绝，
后续调用继续成功。所有案例采用独立 key，没有借此验证同 key 错误后重试。

公开 Rust 单元先在第一组错误拒绝，修后覆盖四组成功（含 None）及三组拒绝。
生产仅在 datetime_input 内将显式 min/max 去掉秒/亚秒后比较；默认值原有分钟
精度、默认十年窗口、step、身份规则、codec/注册/状态/hash/队列均不变。
指南先补分钟精度规则，相关红绿/构建日志为 target/datetime-precision-{red,
green,before-build,build}.log；collector save 显式使用 LF，避免新 JSON 的 CRLF
被仓库 -text 规则保留后触发 whitespace 检查。

门禁绑定 raw PB/summary/elements、唯一请求/完成/running/SDK 版本、全部案名/
接受性/返回值与具体错误、八个独立 ID、默认值/空默认/分钟边界/step/format/
布局/策略与同步标志。八个成功控件的完整 Element 仅规范化 ID 后一致；JSON
报告中的错误类型/文案不相等，分别按 SDK 与 Rust 原值保护。修后 Rust 明确
semantic_match=false、precision_acceptance_match=true，这些差异继续开放，
不能报告整份协议或错误行为已经完全匹配。五类同步改动 raw/summary/元素的
反例覆盖默认精度、错误边界、空默认、误拒绝合法值和放过真实非法值。

三份源文件采集时 SHA 保留；修前生产基线 62c8837，修后源码 dirty，另保留
各自 widget_api 与二进制 SHA。SDK collector 退出；Rust 修前 29992、修后
67072 均核对完整路径后停止，原 exec 会话终止，50510/8600 读回无监听。
没有浏览器操作，动态边界/URL/页面/回调/错误恢复/全部时间精度仍未完成，
M3/M5/M7、130 partial、统一 hash 与共享状态选型继续开放。

最终工作区 304 项通过（297 库 + 1 ledger + 2 宏 + 4 rustdoc），保留原
navigation_pages_switch_and_session_state_match_the_measured_wire 与
rerun_queue_messages_match_frozen_reference 两项排除；相关 query/widget/
temporal/matrix/docs 参考门 311 项通过（temporal 29 项）。工作区/all-target
Clippy、编辑 Rust 的 rustfmt、diff --check 通过，既有 MSVC linker stdout
warning 保留。日志为 target/datetime-precision-{workspace,reference,clippy}.log。
用户 colconfig_params 改动保持隔离，未合并、发布或部署。

### 颜色创建值、前端解码与 callback（2026-11-01）

冻结 widget-params/color 的 SDK 与 Rust 修前 before、修后 trace：各完整十六轮
同连接，SDK/修后 122 原始帧/43 有序元素，修前 106/27。首轮 16 个默认值案
（6 接受、10 拒绝）及 -5/0/1/39/40/41 六宽度案；SDK 三/六位 hex 必须带 #，
ASCII 大小写和单个尾随 LF 原样保留，其余非法格式拒绝。六种整数宽度全部
接受且小于 40 提升到 40。无默认的普通调用返回 #000000，不据此验证无 key 身份。

随后十五轮依次 load/short/short-hash/long/invalid/empty/lower/invalid-after-edit/
default-change/changed-invalid/width/assign/native-invalid/observe/recover。输入省略
`#` 被补前缀，非法/空串恢复注册默认并按实际值变化回调，默认更改不覆盖当前
选择但影响下一批非法输入。代码赋值 #135/nothex 分别同步前端，未触发 callback；
无前端输入观察保持 nothex，恢复输入变 #123abc。八个 callback 值完整有序，
修前第一条为错误的 abc，修后为 #abc；返回值、native 和事件日志均实际比对。

公开 Rust 两项单元先失败（拒绝 #ABC、callback 读 abc），修后覆盖默认校验/
宽度、前端解码与默认变更/回调、代码字符串同步及后续保持。生产只改颜色
codec/入口校验和最小宽度；不改通用注册、其他 Text、身份/hash/queue/共享状态。
指南先说明使用规则，再实现。相关日志为 target/color-{red,green,before-build,build}.log。

门禁绑定 PB 原始长度/summary/元素、完整帧/running 次序、16 次唯一 run 和同一
session/成功结束、全部输入字符串/ID、22 案结果和实际拒绝消息、所有默认值/
宽度/布局/策略/同步标志、稳定的 accent ID、十五轮返回/native/八次 callback。
27 个成功 ColorPicker Element 只规范化 ID 后逐字段一致；创建错误类型/文案
分别保护，修后明确 semantic_match=false、color_flow_match=true，不将此当完整
错误兼容。五类同步修改 raw/summary/元素的反例保护 # 归一化、默认回退、回调、
最小宽度及代码赋值的同步/一次性标志。

首个 SDK collector 因 ID 记录误放 block 分支而在第三请求前中断，已修正；
失败 trace/server.log 原样移动至 target/color-collector-incomplete.json 和
target/color-collector-incomplete-server.log，不属于本次冻结正参考。SDK 完整重新采集一次，未覆盖旧成功
参考。三份采集源码 SHA 保留；Rust 基线 6fa5203，另有生产文件与二进制 SHA。
SDK 服务由 collector 退出；Rust 修前 68980、修后 58888 按完整路径核对后停止，
原 exec 会话终止，54320/8599 读回无监听。未操作浏览器；错误身份预占、其他
oneof/禁用/URL/表单/跨页/无 key/非字符串代码态继续开放，完整目标及 130 partial 不关闭。

最终工作区 306 项通过（299 库 + 1 ledger + 2 宏 + 4 rustdoc），保留原
navigation_pages_switch_and_session_state_match_the_measured_wire 与
rerun_queue_messages_match_frozen_reference 两项排除；相关 query/widget/
temporal/pickers/matrix/docs 参考门 343 项通过（widget 参数模块 92 项）。
工作区/all-target Clippy、编辑 Rust 的 rustfmt、diff --check 通过，既有 MSVC
linker stdout warning 保留。日志为 target/color-{workspace,reference,clippy}.log。
用户 colconfig_params 改动保持独立，未合并、发布或部署。

### 颜色弹窗的真实 Chrome 提交与恢复（2026-11-01）

复用 ?probe=color&phase=load，SDK 8624、Rust 8599；开启 Network 后受控 reload
建立正式采集起点。两侧各九阶段 load/short-draft/short-commit/invalid-draft/
invalid-close/recover-draft/recover-commit/restore-draft/restore-commit，五次完整
后端运行、35 原始 WS 帧和一个 created 事件。冻结在 widget-params/color/ui/，
原生十六轮参考未覆盖或改写。两侧 18 张 1463x724 JPEG 原始字节逐张核对，
视口 1463x724/DPR 1.75；动作+AX 与后续截图/DOM 在不同 CUA 调用，避免错位旧图。

弹窗 abc 草稿只更新可见色块，无 WS 帧；Escape 后前端扩展为小写 #aabbcc
提交，返回/native 和 callback 一致。zzzzzz 草稿被前端过滤，Escape 仍重发
#aabbcc 并完成新一轮，值相同不回调；不能写成“不发送/不重跑”。六位 00ffAA
通过色块点击提交成 #00ffaa，123456 通过外部 Accent 标签点击提交成 #123456，
最终有序 callback 为 #aabbcc/#00ffaa/#123456。前端过滤无效草稿与直接协议
注入非法字符串回默认是两条不同路径，不能互相替代。

新增门禁绑定全部 CDP 原始帧/序号/WS ID/页签、各阶段事件边界与无草稿发送、
5 次输入/运行/完成/running 顺序、唯一 session/5 run/稳定控件 ID、实际提交的
六位字符串、返回/native/回调、控件字段/布局/同步标志及可见 DOM。完整 Color
和 JSON Element 仅规范化控件 ID 与 JSON 对象顺序后一致；fixture 的 JSON 属性
插入顺序不同，不宣称整页逐像素相同。JPEG 的格式/尺寸/长度/SHA 和固定色块
采样点均检查；采样以实际 SDK 截图 RGB 为参考，不假定它与 CSS RGB 数值相同。
六类反例覆盖草稿提前发送、非法提交字符串、重复回调、预览色、SHA 和同步
更新 SHA 后复用旧阶段图片。图片和 DOM/原始协议共同构成证据，非人工标志替代。

代码基线 c36f646，采集前二进制及两生产源文件 SHA 与上一批实际原生捕获一致；
本批生产源码干净。两侧采集源 SHA 保留。页签 1754832033/1754832037 已关闭，
先禁用 Network 再关闭页签；没有 close 事件，所以只声明动作完成，不称已观察
WS close 帧。SDK 58436 按已知 fixture/端口命令核对、Rust 62268 按完整路径核对
后停止，原 exec 会话均终止，8624/8599 读回无监听。本批只改门禁/文档/证据，
未操作权限/外部服务，创建错误/禁用/绑定/表单/页面/IME/拖动等组合继续开放。
M3/M5/M7、130 partial、统一 hash 和共享状态选型不关闭。

最终 query/widget/temporal/pickers/matrix/docs 相关参考门 352 项通过（widget 参数
模块 101 项），diff --check 通过，日志为 target/color-ui-reference.log。本批没有
生产/示例/采集器修改，没有重新运行 Rust 工作区或 Clippy；上批 306 项与两项
排除及 Clippy 结果仍为上批快照。用户 colconfig_params 改动保持独立，未合并、
发布或部署。

### 无 key 颜色控件的原始默认值与宽度身份（2026-11-01）

冻结 widget-params/color-unkeyed SDK、Rust before/trace.json 与修后 trace.json，
均十五次普通结束、104 原始帧、30 有序元素。SDK ID 等价类为 0/0/1/1/2/2/2/
2/2/2/3/3/2/0/0：省略默认值与显式 #000000 分开；默认 content 与 40px 分开；
0/-5/1/39/40 的原始宽度归一化后相同；41px 新身份。四批输入依次 #a1b2c3、
#112233、#445566、#778899，恢复被正常清理的 40px/省略配置后返回 #000000，
不复活旧颜色。修前同帧数/同默认字段但全部一个 ID，explicit 仍 #a1b2c3、
最后错误保持 #778899，失败证据保留。没有用帧数或省略字节差异替代值/ID 验证。

公开 Rust 十五轮单元先在 explicit 轮 #a1b2c3 对 #000000 失败，修后全部返回值
和任意两轮 ID 相同/不同关系通过。仅 ColorPickerOptions 私有 value 保留 Option
及无 key extra 加原始 value/有效 width；实际默认仍黑色，有 key 分支、codec、
输入接收/回调/清理、hash、队列和共享状态不变。指南先说明参数身份，再实现。
红绿和构建日志为 target/color-unkeyed-{red,green,before-build,build}.log。

门禁检查 raw PB/summary/元素、所有帧和 running 顺序、15 个唯一 run/单一
session/完成、原始 query/history/四批字符串及上一轮 ID、全部 ID 等价关系、
返回值、黑色默认和真实布局/策略/同步标志。30 个完整 Color/JSON Element
仅规范化控件 ID 与 JSON 正文后逐字段一致。五类反例保护省略/显式身份、
错误使用原始宽度重建、旧值复活、未提升的宽度、过期输入 ID。无 key 不构造
虚假 native key 投影；正常结束路径与 stop/错误保留状态不能混用。

当前二进制另重跑既有带 key 颜色十六轮（122 帧/43 元素），接受性、默认回退、
八条 callback、代码字符串赋值和观察契约通过，输出在 target/color-unkeyed-keyed-recheck/。
未改写旧成功参考，也未重新采集浏览器；旧 UI 证据仍绑定 c36f646 的原快照。
三份采集源 SHA 保留，基线 340b9df，另有生产源及二进制 SHA。采集后仅增加
ColorPickerOptions 私有字段的一行职责注释；修后 trace 保留采集时源码 SHA，
并保存去掉该注释即可重建原 SHA 的说明和补注释后的 SHA，不冒充同一字节源码。
SDK collector 已退出；Rust 57480/44424 按完整路径核对后停止，原 exec 会话终止，
51969/8599 读回无监听。动态浏览器、错误/stop/回调/绑定/表单/跨页等组合及
M3/M5/M7、130 partial、统一 hash 和共享状态选型继续开放。

最终工作区 307 项通过（300 库 + 1 ledger + 2 宏 + 4 rustdoc），保留原
navigation_pages_switch_and_session_state_match_the_measured_wire 与
rerun_queue_messages_match_frozen_reference 两项排除；相关 query/widget/
temporal/pickers/matrix/docs 参考门 361 项通过（widget 参数模块 110 项）。
工作区/all-target Clippy、编辑 Rust 的 rustfmt、diff --check 通过，既有 MSVC
linker stdout warning 保留。日志为 target/color-unkeyed-{workspace,reference,clippy}.log。
用户 colconfig_params 改动保持独立，未合并、发布或部署。

## Current M5 memory counter correction (2026-11-01)

`tools/measure_stability.py` 的 Windows 结构重复了 `QuotaPeakPagedPoolUsage`，漏掉一个 SIZE_T 槽位；本机声明大小为 72 字节，`PrivateUsage` 偏移为 64，实际对应 `PeakPagefileUsage`。依据 [Microsoft PROCESS_MEMORY_COUNTERS_EX](https://learn.microsoft.com/en-us/windows/win32/api/psapi/ns-psapi-process_memory_counters_ex) 补全字段后为 80 字节、偏移 72。`tools/measure_media_storage.py` 的声明原本正确，本批未改。

红→绿验证在自有 Python 进程内调用真实 Windows API：提交并释放 64 MiB。旧字段在释放后仍为 77,828,096 字节，而当时正确的 PrivateUsage 已回落至 10,588,160；修正后的采样器读数为 12,869,632 → 80,113,664 → 12,869,632，峰值提交仍停在 80,113,664。结构大小、偏移、字段唯一性和分配/释放变化均已断言；它验证采样字段，不是 Rust 泄漏测试。

当前生产源码的库测试二进制构建确认通过；Python 语法检查与上述 Windows API 验证通过后，运行现有六个真实 WS 场景，各三次，共 18 次全部通过：大载荷两轮、300 次 rerun/11 次触发、慢读者隔离、200 轮 256 行表吞吐、64→128 会话容量，以及五秒有界持续窗口。重测大载荷观测私有内存峰值为 42.66–46.12 MiB；吞吐约 1,269–1,305 rerun/s；五秒窗口 19,131–19,783 轮，触发计数均精确。这些是单机 debug 测试观测，不与旧版本或不同环境比较，不宣称性能改进或 SLO。

[stability.json](../tests/performance/stability.json) 当前结果记录测试二进制、采样器与夹具 SHA256，以及生产源码提交 `37ce42200a46b7dd35e104cd5362d8bb194da8ee`；`sampler_validation` 保存红/绿实测，`superseded_snapshot.snapshot` 完整保留旧 JSON。旧 `max_observed_private_bytes` 必须按误标的峰值提交内存解释，不能反推出旧当前私有内存；原 WorkingSetSize 的偏移未变。本次不修改生产 Rust、公共接口、依赖或场景负载。

相关 docs/matrix 门 52 项通过。日志位于 `target/stability-counters-{red,green,build,measure,reference}.log`，18 份原始试次日志位于 `target/stability-counters-measurement/`；冻结 JSON 保存测量值和红/绿结果，未提交这些本地日志。本批未重复不受影响的全工作区测试或浏览器采集；多小时浸泡、真实网络抖动与长期回收仍未验收，M3/M5/M7 与长期 Goal 保持开放。`select_slider` 三项行为修复、队列扩展、统一 hash 与共享状态方案继续等待各自决定。

## Current checkbox/toggle width identity validation (2026-11-01)

锁定 SDK 1.66.1 的公开 AppTest 与七轮原生 WS 均确认：无 key 的 checkbox/toggle 从默认内容宽度改为 320 像素时重建身份并恢复 false；普通结束清理后恢复原宽度，原身份虽再次出现，旧 true 不能复活。有 key 的两个对照控件在所有轮次保持身份和值。Rust 修前在 width 轮返回四个 true，新增公开 API 单元回归真实失败；修后返回 false/false/true/true。

生产改动仅为 widget_api.rs 的 checkbox/toggle 两处私有身份 extra：无 key 使用布尔默认值与宽度的结构化序列化，有 key 仍为空。未修改共享 InputOptions、callback/禁用/URL/表单/注册清理或发送队列规则，无新增公共接口或依赖。现有 widget_params Rust/Python 示例增加显式 probe=bool-width 分支，采集器增加互斥 --bool-width；旧入口保持。

不可覆盖参考位于 [Python trace](../tests/reference/reference-browser/widget-params/bool-width/trace.json)、[Rust 修前](../tests/browser/rust-widget-params/bool-width/before/trace.json)与[Rust 修后](../tests/browser/rust-widget-params/bool-width/trace.json)。每端七轮、69 份原始 WS 帧、35 个 Element；四个控件每轮均渲染，无 key 身份各两类，有 key 各一类。修后完整 Element 仅归一化不透明 ID 与 JSON 文本格式后逐字段一致；源码 SHA256 绑定两份示例和采集器。SDK 服务由采集器关闭；自有 Rust 修前 PID 29788、修后 63596 均按精确可执行路径核验后停止；50612/8599 无监听。

参考门同时验证原始 protobuf 与汇总、输入 bool oneof/上一轮 ID、身份等价类、协议宽度与类型、正常完成/会话身份、返回值及清理；五类同步篡改原始帧与汇总的负例必须失败：错误无 key 身份、错误有 key 身份、复活旧值、错协议宽度与过期输入 ID。widget 参数模块 119 项通过；相关 query/widget/temporal/pickers/matrix/docs 门 370 项通过。两项矩阵条目及机器清单已更新，130 partial 保持，桶计数仍为外部 12、Rust/headless 2、未测参数 94、未声明缺口 33。

按代码检查→单元→原生 WS→工作区顺序验证，编辑 Rust 的 rustfmt 与全工作区/all-target Clippy 通过；工作区共 308 项通过（301 库、1 ledger、2 宏、4 rustdoc），仍明确排除原 navigation_pages_switch_and_session_state_match_the_measured_wire 和 rerun_queue_messages_match_frozen_reference 两项待决回归，不能称完整工作区全绿。既有 MSVC linker stdout warning 保留。日志索引 target/bool-width-{red,green,clippy,build,workspace,reference}.log。

本批没有重采真实浏览器；默认/固定宽度以外的表示、无效宽度错误顺序、callback/禁用/表单/跨页等组合继续开放。select_slider、统一 hash、共享状态和发送队列扩展选择未被本批代替；M3/M5/M7 与长期 Goal 仍未完成。用户 colconfig_params 修改保持独立，未合并、发布或部署。

## Current selection policy identity validation (2026-11-01)

锁定 SDK 1.66.1 的原生 WS 九轮参考确认：有 key 的 selectbox 切换 accept_new_options 会重建身份并恢复默认 Alpha；有 key 的 multiselect 切换 max_selections None/2/3 也会重建。相同模式下的 320 像素宽度保持两控件身份和值；创建模式接受并返回列表外字符串 Novel。正常结束清理后恢复原模式/上限，不复活旧 Beta/Charlie。Rust 修前两控件各只有一种身份，mode 轮均返回旧 Beta；公开 API 单元回归真实失败。修后身份分别两类/三类，值与参考一致。

生产修正限于私有身份参数：emit_selectbox 的 keyed extra 包含 creation；multiselect 的 keyed extra 包含 max_selections，unkeyed extra 也将上限与标签/默认索引结构化编码。无新增公共接口或依赖，未改 codec、注册/回调/URL/清理、共享状态、发送队列或选择上限校验。本批动态参考直接验证有 key 的路径，无 key 上限切换和无效/超限输入仍待验证。

现有 Rust/Python widget_params 示例增加显式 probe=select-policy 分支，采集器增加互斥 --select-policy。固定证据为 [Python](../tests/reference/reference-browser/widget-params/select-policy/trace.json)、[Rust 修前](../tests/browser/rust-widget-params/select-policy/before/trace.json)、[Rust 修后](../tests/browser/rust-widget-params/select-policy/trace.json)。每端九轮/71 原始帧/27 完整 Element；仅归一化不透明 ID 和 JSON 文本格式后字段一致。采集器绑定两份示例与自身 SHA256，Rust 另存 widget_api 与二进制 SHA256。原始输入使用前轮实际 ID，单选 string_value、多选 string_array_value，后者保持选择顺序。

公开 AppTest 在尝试提交 Novel 时，于自身测试树序列化阶段抛出 list.index ValueError；这不是应用错误或已验收的失败规则。该失败日志只留在 target/select-policy-sdk.log，未混入成功证据；原生 WS 随后独立完成全部九轮。SDK 自有服务由采集器关闭；Rust 修前 PID 68520、修后 30112 均校验可执行路径后停止，51319/8599 无监听。

参考门核对原始 protobuf/汇总、宽度、创建模式/上限、默认值、输入 ID/oneof、会话/轮次与返回值；五类同步篡改原始帧和汇总的负例必须失败：模式身份、上限身份、旧值复活、协议上限、过期输入 ID。widget 参数模块 128 项、相关 query/widget/temporal/pickers/matrix/docs 门 379 项通过。矩阵仅更新 st.selectbox/st.multiselect 并重导清单；130 partial 与各桶计数保持，未扩大为完整参数、错误或浏览器兼容。

编辑 Rust 的 rustfmt、全工作区/all-target Clippy 通过；按代码检查、单元、原生 WS、工作区顺序验证。工作区共 309 项通过（302 库、1 ledger、2 宏、4 rustdoc），仍精确排除原 navigation_pages_switch_and_session_state_match_the_measured_wire 与 rerun_queue_messages_match_frozen_reference 两项待决回归，不能称完整工作区全绿。既有 MSVC linker stdout warning 保留；日志索引 target/select-policy-{red,green,clippy,build,workspace,reference}.log。

本批未重采真实浏览器，未验证全部回调/绑定/表单/跨页组合；select_slider、统一 hash、共享状态、发送队列扩展与多小时浸泡的待决定状态保持。用户 colconfig_params 修改独立保留；未合并、发布或部署，M3/M5/M7 与长期 Goal 继续开放。

## Current unkeyed selection identity validation (2026-11-01)

本节补充上一批有 key 验收，关闭其“无 key 动态上限待测”的已列场景，不扩大为全部参数兼容。锁定 SDK 1.66.1 的公开 API 经一条原生 WS 完成 17 轮：创建模式、max_selections None/2/3、默认/320 像素宽度、占位文字与 fuzzy/prefix 过滤模式变化；每轮正常结束清理。selectbox 身份六类、multiselect 四类；恢复旧参数不能复活旧选择，空串占位和单空格共享身份，empty-edit 后从空串切为单空格仍返回 Beta。

Rust 修前忽略无 key 的宽度、占位文字和过滤模式，width 轮错误保留 Novel 与 Beta/Charlie；单元回归真实失败。另有显式空占位被错误编码为默认空串。生产改动仅为 multiselect 的 unkeyed extra 补宽度，selectbox 的 unkeyed extra 结构化编码标签、默认索引、创建模式、有效占位、过滤模式及宽度；显式空占位先归一化为单空格再用于身份和协议。keyed 身份白名单、codec、callback/禁用/绑定/清理/发送流程不变，无新公共 API 或依赖。

复用已有示例的 probe=select-policy-unkeyed 分支，以及采集器 --select-policy --select-unkeyed；旧 keyed 分支仍保留。固定原始证据为 [Python](../tests/reference/reference-browser/widget-params/select-policy-unkeyed/trace.json)、[Rust 修前](../tests/browser/rust-widget-params/select-policy-unkeyed/before/trace.json)、[Rust 修后](../tests/browser/rust-widget-params/select-policy-unkeyed/trace.json)，每端 17 轮、135 原始 WS 帧、51 完整 Element；仅归一化不透明 ID 和 JSON 文本格式后逐字段一致。示例/采集器 SHA256 双端相同，Rust 另保存 widget_api 与二进制 SHA256。旧失败保留各两类/三类身份及空占位错误，未覆盖为成功。

参考门复用严格原始 protobuf/汇总解析，验证身份等价类、输入标签/oneof/前轮 ID、宽度、占位、过滤枚举、选择上限、返回值和会话/完成状态。七类同步篡改原始帧与汇总的负例必须失败：宽度身份、占位身份、过滤身份、空格身份、旧值复活、协议占位和过期输入。widget 参数模块 139 项、相关 query/widget/temporal/pickers/matrix/docs 门 390 项通过。两项矩阵证据/边界及机器清单已同步，130 partial 与桶计数保持。

同一修后 Rust 二进制另执行原九个 keyed 场景（71 帧/27 Element），继续与原冻结 SDK 逐字段一致，本地证据 target/select-unkeyed-keyed-recheck/trace.json；未重写旧参考。SDK 服务由采集器关闭，Rust 修前 PID 62280、修后 8988 均核验精确可执行路径后停止，55660/8599 无监听。按代码检查→单元→原生 WS→工作区验证：编辑 Rust 的 rustfmt、全工作区/all-target Clippy 通过，工作区 310 项通过（303 库、1 ledger、2 宏、4 rustdoc），仍精确排除原 navigation_pages_switch_and_session_state_match_the_measured_wire 与 rerun_queue_messages_match_frozen_reference 两项待决回归，不能称完整工作区全绿。既有 MSVC linker stdout warning 保留；日志索引 target/select-unkeyed-{red,green,clippy,build,workspace,reference}.log。

真实浏览器的过滤/占位显示、本批以外的默认/空值/无效参数、错误顺序、回调/绑定/表单/跨页组合仍未验收；select_slider、统一 hash、共享状态、队列扩展与多小时浸泡的决定继续等待。用户 colconfig_params 修改保持独立，未合并、发布或部署；M3/M5/M7 和长期 Goal 仍开放。

## Current selection browser filtering and placeholder validation (2026-11-01)

本批仅补真实 Chrome 证据、离线门与文档，不改生产 Rust 或示例。源版本为 9da119b014a0b94e1081cf8cf194bb58d9e2d880。使用 computer-use 的浏览器接口，经真实 combobox/option 定位操作，不注入控件状态；只读 DOM 与 CDP Network 原始 WS 事件一并保存。

两端各四个独立加载的文档、15 个画面、九轮完整运行、四个 WS 连接和 72 个二进制帧。prefix 输入 ha 只显示 Add: ha，输入 Be 显示 Add: Be/Beta；点击 Beta 和 Add: Novel 后实际返回 Beta/Novel。fuzzy 输入 ha 显示 Add: ha、Alpha、Charlie，点击 Charlie 后返回 Charlie。空串与单空格占位的两个文档在清空编辑文本后均显示空白、保留 Alpha 后端选择，之后点击 Beta 返回 Beta。六个草稿画面均无 WS 提交；清空编辑文本不等于提交 None。

原始证据：[Python UI](../tests/reference/reference-browser/widget-params/select-policy-unkeyed/ui/trace.json)、[Rust UI](../tests/browser/rust-widget-params/select-policy-unkeyed/ui/trace.json)。30 份 JPEG 均实际检查并保留原字节，逐图绑定 SHA256、尺寸及字节数；SDK 可视高度 780、Rust 724、宽度均 1463、DPR 1.75，保留实际差异，不宣称整页像素一致。源码 SHA256 绑定 widget_api 与两份示例，Rust 另记录二进制 SHA256。四个文档分别加载，不能替代前批同连接动态身份验证。

证据门验证 76 个事件（含四个连接事件）的顺序、tab/requestId、Base64/protobuf、九次运行及四组独立会话；每轮完整 Element 仅归一化不透明 ID 与 JSON 文本后逐字段一致。逐画面检查 DOM 过滤列表、编辑值/占位、后端可见报告、事件区间和图片完整性；空白编辑区另查文本亮像素范围，防止旧的有字画面即使同步更新 SHA256 仍冒充空白。七类负例覆盖草稿多发、错误过滤列表、错误占位、错误输入、协议与 DOM 同时错误返回、图片 SHA256 和同步更新 SHA256 的旧图替换，均必须被拒绝。

widget 参数模块 149 项、相关 query/widget/temporal/pickers/matrix/docs 门 400 项通过，日志 target/select-ui-{widget-reference,reference}.log。生产 Rust/示例未变，因此本批未重复工作区 Rust、Clippy 或构建；前批 310 项只保留为对应版本证据。st.selectbox 矩阵边界与机器清单同步，仍为 130 partial。SDK PID 60536（venv launcher 68544）、Rust PID 9344 已按自有命令/可执行路径核验后停止，8624/8599 无监听。自有标签页 1754832072/1754832076 已关闭；先禁用 CDP Network 观测再关页，没有观测到 close 帧，不宣称已捕获 WS 关闭事件。采集时返回的 warn/error 日志为空。

本批只覆盖创建模式的 prefix/fuzzy 列表、选项提交和有既定选择时的空白编辑框。初始无选择占位、默认上下文提示、其他过滤/语言/设备/浏览器、真实多选变更、动态参数的同文档 UI、回调/表单/错误与其余组合继续开放。统一 hash、共享状态、发送队列扩展、select_slider 与多小时浸泡决定不变；用户 colconfig_params 修改保持独立，未合并、发布或部署，M3/M5/M7 与长期 Goal 未关闭。

## Current radio display identity validation (2026-11-01)

锁定 SDK 1.66.1 的公开 AppTest 与原生 WS 十二轮均确认：无 key 的 radio 在默认/320 像素宽度、横排和说明文字变化时重建身份；省略 captions 与显式空列表也分别成类。有 key 的对照组保持身份和值；正常结束清理后恢复原参数不复活旧选择。另确认默认 Element 宽度应为 content，修前错误为 stretch。旧创建参考只比较 Radio 内部字段，不能据此推断外层宽度一致；矩阵已校正此证据边界。

生产修正限于 widget_api.rs：radio 默认使用内容宽度；私有 captions 保存 Option 以区分省略/显式空列表，协议写入时转为空列表；unkeyed extra 结构化编码选项、默认索引、横排、原始 captions 和宽度，keyed extra 仍为空。公共构造器、captions/width builder 形态不变，公共宽度说明改为使用各控件默认值；无新公共 API/依赖，未改 codec、回调/禁用/绑定/表单/清理或发送规则。文本输入/文本域审查确认已有宽度身份参数，本批未改。

修前单元回归真实在 load 轮断言 UseStretch/UseContent 失败；新增例还验证无 key 五类身份、有 key 一类、返回值和恢复清理。固定证据为 [Python](../tests/reference/reference-browser/widget-params/radio-identity/trace.json)、[Rust 修前](../tests/browser/rust-widget-params/radio-identity/before/trace.json)、[Rust 修后](../tests/browser/rust-widget-params/radio-identity/trace.json)，每端 12 轮/95 原始 WS 帧/36 完整 Element。修前两控件各只有一类身份，width 轮保留旧 Beta；修后完整 Element（含外层宽度）仅归一化不透明 ID 和 JSON 文本后逐字段一致。采集器绑定示例/自身源码 SHA256，Rust 另存 widget_api 与二进制 SHA256。

严格原始 protobuf/汇总门检查参数、身份等价类、上一轮输入 ID/string_value、返回值、会话/轮次、完成和清理。七类同步改写原始帧及汇总的负例必须失败：默认 stretch、错误横排身份、错误非空 captions 身份、混淆空/省略 captions、复活旧值、错误 keyed 身份与过期输入。widget 参数模块 160 项、相关 query/widget/temporal/pickers/matrix/docs 门 411 项通过。

按代码检查→单元→原生 WS→工作区验证；编辑 Rust 的 rustfmt 与全工作区/all-target Clippy 通过，工作区 311 项通过（304 库、1 ledger、2 宏、4 rustdoc）。仍精确排除原 navigation_pages_switch_and_session_state_match_the_measured_wire 与 rerun_queue_messages_match_frozen_reference 两项待决回归，不能称完整工作区全绿。既有 MSVC linker stdout warning 保留；日志索引 target/radio-identity-{red,green,clippy,build,workspace,reference}.log。SDK 服务由采集器停止，Rust 修前 PID 68324、修后 47668 按精确可执行路径核验后停止，57917/8599 无监听。

本批未重采真实浏览器；动态 index=None、caption 实际显示与格式、空选项/无效类型/错误顺序、回调/绑定/表单/跨页及其他组合继续开放。仅更新 st.radio 矩阵和机器清单，仍为 130 partial；统一 hash、共享状态、队列扩展、select_slider 与多小时浸泡的待决定状态保持。用户 colconfig_params 修改独立保留，未合并、发布或部署；M3/M5/M7 与长期 Goal 未关闭。

## Current radio empty and None state validation (2026-11-01)

锁定 SDK 1.66.1 的公开 AppTest 初探后，十四轮原生 WS 确认：空选项返回 None，不强制写 disabled；有 key 的旧标签失效时清空并同步，后续恢复选项仍保留 None。index=None 与前端选择可以往返；代码赋 None 时省略协议 default，身份仍取原始 index；代码赋列表外字符串 Missing 时恢复有效默认 Alpha，并将原生状态和前端同步。普通结束清理后恢复无 key 的旧身份从默认值开始。

Rust 修前在空选项轮出现错误，另遗漏显式空状态的协议 default 处理，以及 Radio 的 set_value/raw_value；修前原始证据为 14 个成功完成的脚本轮次、106 帧/37 Element，其中 empty/empty-observe 显示应用外层捕获的错误消息，不能视为功能成功。新增公开 API 单元回归真实报 value does not match radio；中间修复又由回归发现只有外层一次性标志、没有 Radio.set_value 的遗漏，均已修复。

widget_api.rs 的 radio 现在区分原始 index 与本轮 wire_index；空选项使用 Null 作为注册默认，已有 keyed None 省略线上的 default；发送 Radio.set_value/raw_value，并保留无选项时原 disabled。widgets.rs 仅在 Codec::Radio 的原生字符串不在新选项时，恢复本轮有效默认并标记同步；其他原生类型继续原错误路径，原有优先级、回调分派与状态来源结构未改。无公共 API/依赖变动，不选择待决的共享状态来源或发送队列方案。

固定证据为 [Python](../tests/reference/reference-browser/widget-params/radio-empty/trace.json)、[Rust 修前](../tests/browser/rust-widget-params/radio-empty/before/trace.json)、[Rust 修后](../tests/browser/rust-widget-params/radio-empty/trace.json)。修后每端 14 轮/111 原始 WS 帧/42 完整 Element，仅归一化不透明 ID 和 JSON 文本后逐字段一致，包括可选 default 的有无、disabled、set_value、raw_value 与 has_one_shot_effect。无 key 身份四类，有 key 一类；输入均使用前轮实际 ID/string_value。源码 SHA256 绑定两份示例与采集器，Rust 另存 widget_api、widgets 及二进制 SHA256。

参考门验证返回值、身份、同步和完成/清理，七类同步改写原始帧与汇总的负例必须失败：空选项强制禁用、错误 wire default、缺失同步标志、错误同步标签、恢复旧值、过期输入 ID 与错误无 key 身份。参数模块 171 项、相关 query/widget/temporal/pickers/matrix/docs 门 422 项通过。同一二进制另重放原十二个展示参数场景，95 帧/36 Element 继续与冻结参考一致，本地结果 target/radio-empty-identity-recheck/trace.json；未重写旧成功参考。

代码检查→单元→原生 WS→工作区顺序验证；编辑 Rust 的 rustfmt、全工作区/all-target Clippy 通过，工作区 312 项通过（305 库、1 ledger、2 宏、4 rustdoc）。仍精确排除原 navigation_pages_switch_and_session_state_match_the_measured_wire 与 rerun_queue_messages_match_frozen_reference 两项待决回归，不能称完整工作区全绿。既有 MSVC linker stdout warning 保留；日志索引 target/radio-empty-{red,green,clippy,build,workspace,reference}.log。SDK 服务由采集器停止，Rust 修前 PID 57192、修后 54516 按精确可执行路径核验后停止，50880/8599 无监听。

本批未采真实浏览器空状态/清空界面，非字符串原生状态、晚到输入与代码赋值竞争、回调/URL/表单/跨页、其他默认和错误类型仍待测。st.radio 矩阵和机器清单同步，仍为 130 partial；其他待决方案保持，用户 colconfig_params 改动独立保留，未合并、发布或部署。M3/M5/M7 与长期 Goal 继续开放。

## Current selectbox empty and typed native state validation (2026-11-01)

锁定 SDK 1.66.1 的十四轮原生 WS 参考覆盖三个普通 selectbox：无 key 字符串、有 key 字符串和有 key 整数。空选项返回 None，协议不强制 disabled、原始 index=0 仍保留 default=0；已有 keyed None 省略协议默认索引，恢复选项后保持 None。index=None 与前端标签提交可往返；代码赋 None 同步清空，失效 Missing/99 恢复 Alpha/1 并同步标签。整数返回保持 JSON integer，不允许布尔、浮点或字符串代替。

Rust 修前在空选项轮报 session value is absent from selectbox options，且强制 disabled、删去默认索引；原始修前为 14 个完成轮次、121 帧/52 Element，存在外层捕获的错误 Markdown，不能视为功能成功。公开 API 单元回归真实失败；修后 14 轮/125 原始帧/56 完整 Element 仅归一化不透明 ID 与 JSON 文本后逐字段一致，包括 default 有无、set_value/raw_value、外层一次性标志与原生数值类型。

widget_api.rs 区分原始 index 与有效 wire_index；已有原生 None 只影响默认值/clearable，不进入身份；空列表保留原始默认索引和显式 disabled，创建模式构造器默认也保留 Some(0)。widgets.rs 将已有 radio 重置分支扩至普通 Codec::Select，失效原生值恢复有效默认；已匹配展示标签的字符串不被静默改成默认值，创建模式不进入该重置分支。公共接口、原有数据类型与 URL/输入优先级结构不变；原生 None 与绑定等新组合尚未专门验收。

固定证据：[Python](../tests/reference/reference-browser/widget-params/select-empty/trace.json)、[Rust 修前](../tests/browser/rust-widget-params/select-empty/before/trace.json)、[Rust 修后](../tests/browser/rust-widget-params/select-empty/trace.json)。严格门验证前轮 ID/string_value、可选默认、返回值与类型、同步字段、身份和会话/完成状态；八类同步改写原始帧与汇总的负例必须失败：空列表禁用、错误默认、缺失同步、错误标签、恢复旧值、过期输入、错误身份，以及数值相等但类型为 float 的 1.0。另有 SDK AppTest 和 Rust 单元分别验证正常/创建模式空构造器省略 index 时的默认零值。

同一修后 Rust 二进制重放旧九轮创建策略与十四轮 radio-empty，分别 71 帧/27 Element、111 帧/42 Element，继续与冻结参考逐字段一致；本地结果 target/select-empty-{policy,radio}-recheck/trace.json，旧参考未改。SDK 服务由采集器停止；Rust 修前 PID 52160、修后 61796 经精确可执行路径核验后停止，50182/8599 无监听。

完整回归最初发现旧 numeric_ranges_empty_selection_and_constraint_reset 仍要求 empty.disabled=true、default=None，与新 SDK 原生参考和构造器实测相反；已据此更新为 false/Some(0)，未移除断言或新增排除。该两条测试断言在采集后修改，原 widget_api_sha256 保留，widget_api_sha256_after_test_update 与 post_capture_source_note 明确新哈希及精确反向重建方法，已验证能还原原哈希；生产源码未因此改变；随后完整测试重新构建的本地二进制哈希不同，原 binary_sha256 仍标识采集二进制，另以 binary_sha256_after_test_rebuild 记录重建产物，不宣称两者字节相同。代码检查/单元/集成验证完成：编辑 Rust 的 rustfmt、全工作区/all-target Clippy、empty_ 筛选 18 项单元通过，工作区 314 项通过（307 库、1 ledger、2 宏、4 rustdoc），保留原两项队列待决排除，不能称完整工作区全绿。相关 query/widget/temporal/pickers/matrix/docs 门 436 项通过，参数模块 185 项；其中包含 SDK-only 观察，不等于 436 项全部跨运行时验收。既有 MSVC linker stdout warning 保留，日志索引 target/select-empty-{red,green,clippy,build,workspace,reference}.log。

新发现的公共类型边界已以 SDK-only AppTest 用例保留：整数选项 key 被代码赋展示标签字符串 "2" 时，SDK 暂时返回字符串 "2" 并同步 raw_value，AppTest 下一次序列化提交后又返回整数 2。该用例用数组报告保留类型，避免 st.json 直接解析数字字符串掩盖真实返回值；最初观测用例已据此修正。现有 Rust Option<T> 在 T=i64 时无法表达临时字符串返回，需要另行公共 API 建模/决策；本批未改变返回类型，也没有该边界的原生 WS、Rust 或浏览器兼容结论。

本批未重采真实浏览器；动态异类型返回、任意原生类型、原生空状态与绑定/回调/表单/跨页/晚到输入组合继续开放。仅 st.selectbox 矩阵和机器清单更新，仍为 130 partial；其他待决方案及用户 colconfig_params 修改保持，未合并、发布或部署。M3/M5/M7 与长期 Goal 未关闭。

## Current multiselect filtered native state validation (2026-11-01)

锁定 SDK 1.66.1 的公开 AppTest 初探及十二轮原生 WS 参考覆盖无 key 字符串、有 key 字符串和有 key 整数 multiselect。删除部分选项时逐项过滤失效值，保留有效选择的顺序与重复项；重排选项不按旧索引取错值，空列表返回空列表且不强制 disabled。代码赋混合有效/失效数组与重复有效项时，返回原生字符串/整数并同步标签，正常结束后不重放同步。

Rust 修前在 subset、assign-partial、empty 轮出现 session value is absent from multiselect options，且空控件被强制禁用；[修前捕获](../tests/browser/rust-widget-params/multi-empty/before/trace.json)为 12 个完成轮次、101 帧/42 Element，包含外层捕获的错误 Markdown，不代表功能成功。新增公开 API 十二轮单元先真实失败，修后通过；另有公共 API 边界测试确认 None 和无法表达的动态标签类型继续报错，不产生部分控件。

生产修改仅涉及 widgets.rs 的 MultiSelect 原生数组读取与过滤同步标志，以及 widget_api.rs 的 multiselect.set_value/raw_values 和 disabled。过滤保留有效项、顺序及重复项，非数组继续原错误；匹配展示标签但与原生选项类型不同的字符串保留原错误，避免静默丢弃。发送同步标签复用本轮已序列化选项，不新增公共接口、依赖、状态层或队列流程。既有优先级、前端输入解析和 max_selections 规则未改。

[Python](../tests/reference/reference-browser/widget-params/multi-empty/trace.json)与[最终 Rust](../tests/browser/rust-widget-params/multi-empty/trace.json)各 12 轮/107 原始帧/48 完整 Element，仅归一化不透明 ID 和 JSON 文本后逐字段一致。前端提交使用前轮实际 ID/string_array_value；严格门验证返回类型、有效项过滤、顺序/重复项、set_value/raw_values、一次性标志、disabled、会话/轮次与四类无 key/单类 keyed 身份。八类同步改写原始帧和汇总的负例必须失败：空列表禁用、缺失同步、同步顺序、同步去重、返回去重、错误输入 ID、错误无 key 身份、整数变成数值相等的浮点。测试模块共 199 项通过。

同一最终二进制另重放旧十四轮 selectbox-empty 与九轮选择策略，125 帧/56 Element、71 帧/27 Element 继续与旧参考逐字段一致，本地结果 target/multi-empty-{select,policy}-recheck/trace.json。原生捕获绑定两端示例、采集器，以及 Rust widget_api/widgets/二进制 SHA256，均核实与当前文件相同。早期未加异类型标签保护的成功捕获保留于 target/multi-empty-pre-label-guard/trace.json，随后重新采集最终代码，未将旧产物冒充最终证据。

SDK-only AppTest 另记录两项公共边界：原生 None 报 non-iterable 错误，下一轮仍错误，显式赋空数组后恢复；整数选项被代码赋 ["2", 2, 99] 时暂时返回 ["2", 2]，同步标签 ["2", "2"]，AppTest 下一次提交后返回 [2, 2]。现有 Rust Vec<T> 在 T=i64 时不能表达异类型字符串；公共返回建模仍须单独决策。本批没有该动态返回或错误界面的原生 WS/Rust/浏览器兼容结论，不通过静默过滤有效标签缩小目标。

编辑 Rust 的 rustfmt、全工作区/all-target Clippy、两项相关公共 API 单元通过；最终工作区 316 项通过（309 库、1 ledger、2 宏、4 rustdoc），仍仅排除原 navigation_pages_switch_and_session_state_match_the_measured_wire 与 rerun_queue_messages_match_frozen_reference，不能称完整工作区全绿。相关 query/widget/temporal/pickers/matrix/docs 门 450 项通过，其中包含 SDK-only 观察，并非全部跨运行时验收。既有 MSVC linker stdout warning 保留；日志 target/multi-empty-{red,green,clippy,build,workspace,reference}.log。

SDK 服务由采集器停止，Rust 服务通过持有的自建进程句柄 terminate/wait 结束；62455/8599 无监听。本批未采真实浏览器；非空默认、动态异类型返回、任意原生类型、上限/错误/回调/绑定/表单/跨页/晚到输入组合继续开放。仅 st.multiselect 矩阵与机器清单更新，仍为 130 partial；用户 colconfig_params 修改独立保留，未合并、发布或部署，M3/M5/M7 与长期 Goal 未关闭。

## Current multiselect duplicate defaults and zero limit validation (2026-11-01)

SDK 1.66.1 的公开 AppTest 和八轮原生 WS 确认：重复默认值合法，三个选项可默认四次同一选项；max_selections=0 拒绝，越界默认拒绝；默认/前端/代码状态的数量超限在过滤失效项前检查，错误后保留登记状态，后续仍错误，显式合法数组恢复。应用在探针内捕获错误并报告 JSON，因此这里不验收默认异常 UI。

[Python 参考](../tests/reference/reference-browser/widget-params/multi-limits/trace.json)为 8 轮/61 帧/22 Element；[Rust 修前](../tests/browser/rust-widget-params/multi-limits/before/trace.json)为 63 帧/24 Element，错误拒绝三个重复默认案例，却接受零上限。公开 API 回归先真实报 defaults must be distinct indices inside options。独立修正仅在 widget_api.rs：允许重复默认索引、保留越界拒绝，注册前拒绝零上限；无公共 API、codec 或登记/清理流程变动。

[当前 Rust 捕获](../tests/browser/rust-widget-params/multi-limits/trace.json)为 65 帧/26 Element，semantic_match=false 明确保留，不是整批兼容成功。三项重复默认的完整 Element 和返回值已与 SDK 对照；零上限、越界默认均不发送控件，运行时各自的错误类型/文字分别严格验证。默认超限及三个状态超限轮仍错误接受，数量错误/持续登记/过滤前计数继续开放。测试不将这些现有差异改写为已兼容，SDK 参考门仍要求真正的错误与恢复。

严格门验证八轮顺序、实际输入 ID/string_array_value、重复默认/返回、最大值、同步标签/一次性标志、轮次/会话和路径；七类同步改写原始帧及汇总的负例必须失败：默认去重、返回去重、零上限接受、错误输入 ID、缺失修复同步、过滤后才计数、丢失持续错误。参数参考模块 209 项、相关 query/widget/temporal/pickers/matrix/docs 门 460 项通过；其中包含 SDK-only 和差异保留观察，不等于 460 项全部 Rust/SDK 一致。

当前二进制另重放原十二轮 multi-empty 与九轮选择策略，107 帧/48 Element、71 帧/27 Element 仍逐字段一致，本地结果 target/multi-limits-{empty,policy}-recheck/trace.json。源文件、采集器、widget_api/widgets 和二进制 SHA256 均核对当前文件；未改旧成功参考。SDK 服务由采集器停止，Rust 子进程通过自持句柄 terminate/wait 结束，59558/8599 无监听。

编辑 Rust 的 rustfmt、全工作区/all-target Clippy、三项相关 multiselect 单元通过，最终工作区 317 项通过（310 库、1 ledger、2 宏、4 rustdoc），仍仅排除原 navigation_pages_switch_and_session_state_match_the_measured_wire 与 rerun_queue_messages_match_frozen_reference；不能称完整工作区全绿。既有 MSVC linker stdout warning 保留。日志 target/multi-limits-{red,green,clippy,build,workspace,reference}.log。

数量错误后仍保留控件登记，会改变现有 fallible conversion 完成后才登记的流程；已在 [architecture](architecture.md#multiselect-count-validation-and-failed-registration-retention--proposal-2026-11-01) 写明胜出状态原始计数、保留原值、仅此错误的登记例外与验证计划，并依据用户 AGENTS.md 第 2 条提问。该流程尚未获批，未用通用 registration_error 阻断后续控件，未调整既有共享状态、队列、hash 或公共返回类型决策。

真实浏览器、默认异常界面、数量错误 callback 顺序、动态异类型返回、任意默认/上限范围和其他组合仍未完成。仅 st.multiselect 矩阵与机器清单更新，仍为 130 partial；用户 colconfig_params 修改独立保留。未合并、发布或部署，M3/M5/M7 与长期 Goal 保持开放。

## Current selectbox empty browser and ID-only input validation (2026-11-01)

本批使用现有 select-empty/phase=none 示例，三个普通控件均 index=None：无 key 字符串、有 key 字符串、有 key 整数。真实 Chrome 依次记录初始空选择、三个选项菜单、选择 Beta/2/Alpha 和逐个点击 Clear value；每端十画面、七次正常完成运行，打开菜单不发输入，提交/清空各触发一次重跑。后端依次返回 [None,None,None]、[None,Beta,None]、[None,Beta,2]、[Alpha,Beta,2]、[None,Beta,2]、[None,None,2]、[None,None,None]，整数保持原生 integer。

浏览器真实暴露原生脚本未覆盖的问题：前端提交所有控件，空选择是仅含 ID、没有 value oneof 的 WidgetState；Rust 的旧整批校验将该有效载荷视为错误。修前前两次选择后端仍全空，三项全部选中后才接受；随后三次清空均错误保留 [Alpha,Beta,2]。修前十张原始图片及完整帧保存在 [before](../tests/browser/rust-widget-params/select-empty/ui/before/trace.json)，不能把前端已显示选择视为后端生效。

widgets.rs 新增私有完整状态解码，Record 仅为普通/创建 selectbox 保存本次注册有效默认值；下一轮 ID-only 包用上轮缓存值，晚到首次注册包用本轮默认值。整批校验、实际应用、已有 pending 路径共用该解释；其他 codec 的缺失载荷继续拒绝，原显式 value 解码规则不变。不是一律将 ID-only 变 Null：公开 SDK AppTest 与 Rust API 单元分别确认普通/创建模式 index=None 清空为 None、index=0 清空回 Alpha。两项新公开 API 单元先真实失败后通过；生产无公共接口、依赖、队列、状态来源优先级或失败登记流程变更。

[Python](../tests/reference/reference-browser/widget-params/select-empty/ui/trace.json)与[修后 Rust](../tests/browser/rust-widget-params/select-empty/ui/trace.json)各记录一个 WS 连接、七个稳定同会话运行、63 原始二进制帧和 28 完整 Element；仅归一化不透明 ID/JSON 文本后逐字段一致。每份 64 个 CDP 事件，三个菜单阶段无事件，首次 10 事件、其余提交/清空阶段各 9 事件。输入逐控件核对真实 ID 及 value oneof 有无，返回类型、default 省略、同步标志、路径、完成与 running 状态均核对。

三份采集共 30 张原始 JPEG 已逐张查看；SDK 和修后为 1463×780、修前为 1463×724，DPR=1.75，实际尺寸均保留，不宣称整页像素相同。输入框/占位、菜单项、清空按钮数、后端 DOM 与截图 SHA256/尺寸校验；数值输入框文字区域的亮像素门区分数字 2 与空占位，可拒绝换入旧图后同步更新 SHA 的伪造。八类负例必须失败：菜单阶段有发送、错误空载荷 oneof、整数变成 2.0、清空恢复旧值、错误协议 default、图片哈希、旧图片替换、错误选项列表。

原始页面先打开，启用 Network 采集后有意 reload，证据从这次记录连接开始；初始监测前流量和 Network.disable 后的关闭帧不在覆盖内，不宣称观察到了 WS close 帧。三个自建 tab 均已关闭，SDK/修前 Rust 子进程 PID 47984/59116、修后 Rust PID 10736 通过持有句柄 terminate/wait 结束；53858/8599 核实无监听。console error/warn 均为空。捕获保存基线 8240b19、两端示例源 SHA、Rust 核心源 SHA 与二进制 SHA；修后注明基于该提交的已修改工作区，并已核对实际产物哈希，未把基线提交冒充包含新修复。

编辑 Rust 的 rustfmt、全工作区/all-target Clippy、两项 ID-only 单元通过；最终工作区 319 项通过（312 库、1 ledger、2 宏、4 rustdoc），仍仅排除原 navigation_pages_switch_and_session_state_match_the_measured_wire 与 rerun_queue_messages_match_frozen_reference，不能称完整工作区全绿。参数参考模块 225 项、相关 query/widget/temporal/pickers/matrix/docs 门 476 项通过，包含 SDK-only 默认反序列化观察，不等于全部跨运行时 UI 验收。既有 MSVC linker stdout warning 保留；日志 target/select-empty-ui-{red,green,clippy,build,workspace,reference}.log。

本批只验证非空选项列表下的初始 None/选择/明确清空；空选项列表 UI、创建模式浏览器、radio 等其他控件、动态参数、callback/绑定/表单/跨页/晚到输入和动态异类型返回继续开放。仅 st.selectbox 矩阵和机器清单更新，仍为 130 partial；待决的 multiselect 数量错误登记例外及其他方案未获本批代替。用户 colconfig_params 修改独立保留，未合并、发布或部署，M3/M5/M7 与长期 Goal 未关闭。

## Current radio empty browser and ID-only input validation (2026-11-01)

复用既有 radio-empty/phase=none 示例，以无 key 和有 key 的两个字符串 radio 验证初始空选择共存。真实 Chrome 五阶段为初始全空、有 key Alpha、有 key Beta、无 key Alpha、有 key Alpha；对应后端 [None,None]、[None,Alpha]、[None,Beta]、[Alpha,Beta]、[Alpha,Alpha]。SDK 首次直接点击隐藏 Beta 输入实际选中了 Alpha，已经记录原结果及说明，后续改用观察到的可见标签；Rust 两次旅程重放相同实际选择序列。

[SDK](../tests/reference/reference-browser/widget-params/radio-empty/ui/trace.json)的前端空 radio 是仅有 ID、没有 value oneof 的 WidgetState；[修前 Rust](../tests/browser/rust-widget-params/radio-empty/ui/before/trace.json)将前两次聚合输入整批拒绝，后端仍 [None,None]，两组均选择后才生效。修前五图及原始帧保留，界面勾选和后端返回分别验证。

生产仅在 widgets.rs 将 Codec::Radio 纳入已实现的 empty_input 有效默认缓存，并修正字段说明；不改变完整状态解码、批量校验、优先级、错误登记和发送流程。新增两个 Rust 公共 API 回归先真实失败，修后通过：空同伴不阻断正常选择、callback 收集数及执行后读取值为 Alpha/Beta/Alpha；ID-only 包在 index=None 时返回 None，在默认索引 0 时回 Alpha。SDK-only AppTest 另验证默认回退发生在 callback 读取前，回调序列为 Beta/None 或 Beta/Alpha。浏览器示例无 callback，不据此宣称已测浏览器 callback 全链。

[最终 Rust](../tests/browser/rust-widget-params/radio-empty/ui/trace.json)与 SDK 各五画面/五运行、40 原始二进制帧/15 完整 Element，单记录连接、同会话五个独立 run ID。仅归一化不透明 ID 和 JSON 文本后逐字段一致；每轮校验真实输入 ID、string_value 与空 oneof、协议 default 省略、set_value/raw_value/一次性标志、content 宽度、顺序/路径、返回值和运行完成状态。三份证据各 41 个 CDP 事件，首阶段 9 个、后续各 8 个。

15 张原始 JPEG 均已逐张查看；SDK/修后 1463×780、修前 1463×724，DPR=1.75，实际尺寸保留，不宣称整页像素一致。DOM 分组/标签/checked/disabled、后端 JSON、图片格式/尺寸/字节/SHA 均严格核验；六个 radio 圆点的红色像素门检查真正选中位置，可拒绝将 Alpha 旧图替换 Beta 图后同步修改哈希。八类负例必须失败：错误空载荷 oneof、错误返回、错误 checked、过期 ID、协议默认值、额外同步、图片哈希、旧图替换。参数参考模块 239 项、相关 query/widget/temporal/pickers/matrix/docs 门 490 项通过，包含 SDK-only 观察，不等于全部跨运行时验收。

编辑 Rust 的 rustfmt、全工作区/all-target Clippy、四项 ID-only 单元通过（含原 selectbox 两项）；最终工作区 321 项通过（314 库、1 ledger、2 宏、4 rustdoc），仍仅排除原 navigation_pages_switch_and_session_state_match_the_measured_wire 与 rerun_queue_messages_match_frozen_reference，不能称完整工作区全绿。既有 MSVC linker stdout warning 保留；日志 target/radio-none-ui-{red,green,clippy,build,workspace,reference}.log。

采集从启用 Network 后的有意 reload 开始，初始监测前流量与停用采集后的关闭帧不在范围内；不宣称观察到 WS close 帧。三个自建 tab 已关闭；SDK/修前 Rust 子进程 PID 12304/54304、修后 PID 43856 经自持句柄 terminate/wait 结束，53391/8599 核实无监听；console error/warn 均为空。两端 fixture、Rust 源码与二进制 SHA 已核对，基线为 2d05dc6，修后注明已修改工作区，基线提交不冒充含新修复。

本批不验证空选项 UI、代码引起的界面清空、动态参数、非字符串选项、表单/绑定/跨页/晚到输入及其余 callback 组合。仅 st.radio 矩阵与机器清单更新，仍为 130 partial；待决的 multiselect 超限登记、共享状态、hash 和其他公共接口方案保持。用户 colconfig_params 修改独立保留，未合并、发布或部署，M3/M5/M7 与长期 Goal 未关闭。

## Current formatted selection collision validation (2026-11-01)

锁定 SDK 1.66.1 的公开 AppTest 初探后，十轮原生 WS 同时覆盖无 key/keyed 整数 selectbox 与 keyed 整数 multiselect。选项 [1,2,3] 显示为 Same/Same/Other 时，前端提交 Same，selectbox 返回末个匹配值 2，multiselect 返回首个匹配值 1 并保留重复。选项重排为 [2,1,3]、标签与身份不变时，旧原生值保持；新 Same 提交改为单选 1、多选 2。代码赋原生 2 与 [2] 保留值并同步 Same 标签，恢复顺序后再提交按恢复后的规则解析。

[SDK](../tests/reference/reference-browser/widget-params/format-collisions/trace.json)、[Rust 修前](../tests/browser/rust-widget-params/format-collisions/before/trace.json)、[Rust 最终](../tests/browser/rust-widget-params/format-collisions/trace.json)每份均 10 轮/89 原始帧/40 Element。修前正常结束仍错误返回 [1,1,[1]]，不能把脚本结束视为兼容成功。公开 API 回归首先发现 edit 的 callback 未收集；只修标签查找后又真实发现 reorder 的无 key 返回值 1 而非 2，两次失败分别保留在 red/remap-red 日志，均已修复。

widgets.rs 普通 Codec::Select 的前端标签查找改取末项，创建模式和 multiselect 原有查找不改；无 key 且身份相同时，旧原生值仍存在于当前 options 的场景复用现有 read_session_value 重映射，未改变状态来源或优先级。旧原生值已不在当前选项中的保留问题继续开放，未把现有索引回退当成完整保留方案。无新增公共 API、依赖或状态层。

收尾另测重复原生选项 [1,1,3]：SDK 原生值不变时不触发 callback，Rust 原来仅比较索引，回归真实复现多触发两次。已仅对普通 selectbox/multiselect 按序列化原生返回值比较，并在没有 callback 时跳过该比较；其他 codec 保留原比较规则，输入应用与 callback 执行顺序不变。Rust 公共 API 单元核对重复索引不触发、改为 3/返回 1 才触发，以及回调读取整批已更新的两个选择；SDK-only AppTest 保留同一原生值序列。十轮主回归另核对 callback 读取 2/3/2/1；WS 示例无 callback，不据此宣称真实浏览器 callback 全链。

最终完整 Element 仅归一化不透明 ID/JSON 文本后逐字段一致。严格门验证三个控件的 oneof/实际 ID、三控件身份各一类、单选与多选相反的同名规则、重排与代码原生值、default、set_value/raw_value(s)、一次性标志、返回值的 integer 类型、会话/轮次/路径。八类同步改写原始帧与汇总的负例必须失败：单选取首项、多选取末项、无 key 重排错值、同步标签、缺失同步、过期输入、错误身份、数值相等但变成 1.0。

增加 callback 保护后重新构建并重新采集最终代码；先前成功捕获保留于 target/format-collisions-before-callback-guard/trace.json，未用中间产物冒充最终证据。同一最终二进制另重放旧十四轮 select-empty、十七轮 select-policy-unkeyed，125 帧/56 Element、135 帧/51 Element 继续与冻结参考完整字段一致；结果 target/format-collisions-final-{empty,unkeyed}-recheck/trace.json，旧参考未改。三份 producer 源文件、widget_api/widgets 和二进制 SHA 已核对当前产物；修前核心源哈希另与本批前 HEAD 核对。

SDK-only AppTest 新保留一项边界：旧标签重新序列化提交、options 从 [1,2,3] 换成 [4,5,3] 而展示标签不变时，SDK 的 keyed/unkeyed 调用可返回已不在新列表中的整数 2。Option<T> 本身可以表达该 i64 值，但当前 Rust 实现只克隆当前选项，缺少旧泛型值保留机制，需单独的状态/API 设计；该替换场景没有 Rust/原生 WS 兼容结论。不能将旧值保留问题混同为已完成的“旧值仍存在时重排”。

代码 rustfmt、全工作区/all-target Clippy、两项新增公开 API 单元通过；最终工作区 323 项通过（316 库、1 ledger、2 宏、4 rustdoc），仍仅排除原 navigation_pages_switch_and_session_state_match_the_measured_wire 与 rerun_queue_messages_match_frozen_reference，不能称完整工作区全绿。参数参考模块 255 项、相关 query/widget/temporal/pickers/matrix/docs 门 506 项通过，含 SDK-only 观察，并非全部跨运行时验收。既有 MSVC linker stdout warning 保留；日志 target/format-collisions-{red,remap-red,callback-red,green,callback-green,clippy,build,workspace,reference}.log。SDK 服务由采集器停止，Rust 最终进程 PID 55048 通过自持句柄 terminate/wait 结束，59339/8599 核实无监听。

本批无真实浏览器新采集；同名菜单交互、任意 formatter/比较语义、列表外旧泛型值、URL/表单/跨页/晚到输入和其余 callback 组合继续开放。仅 st.selectbox/st.multiselect 矩阵及机器清单更新，仍为 130 partial；其他待决方案、用户 colconfig_params 修改独立保留。未合并、发布或部署，M3/M5/M7 与长期 Goal 未关闭。

## Current radio duplicate-native callback validation (2026-11-01)

锁定 Python Streamlit 1.66.1 后，真实原生 WS 七轮覆盖 Choice=[Same,Same,Other]（声明 index=1）及 Peer=[Idle,Ready]。初始 Same 再提交 Same 时内部索引可从 1 到 0，原生字符串不变，不应触发 callback。随后 Other、返回 Same、单独 Peer、同时改变两个控件及无输入观察，累计回调次数为 0/0/1/2/3/5/5；同批两次回调均读取 Other/Idle，按 choice→peer 顺序执行，观察轮不重放。

[SDK](../tests/reference/reference-browser/widget-params/radio-duplicates/trace.json)、[Rust 修前](../tests/browser/rust-widget-params/radio-duplicates/before/trace.json)、[Rust 最终](../tests/browser/rust-widget-params/radio-duplicates/trace.json)各 7 轮、55 原始帧、21 Element。修前正常结束但 same 轮多出 [choice,Same,Idle]，semantic_match=false；公开 API 单元先真实失败（run 1 回调 1 次而非 0），修后通过。生产仅将现有 callback 原生值比较扩展到 Codec::Radio；无 callback 时仍跳过比较，输入应用和回调执行顺序不变，无新增公共 API、模块或依赖。

完整 Element 仅归一化不透明 ID 与 JSON 文本后逐字段匹配。严格门核对实际旧 ID/string_value、两控件稳定身份、声明默认值 1/0、无额外 set_value/raw_value/one-shot、会话/轮次/路径、逐轮返回与完整有序回调列表。八类同步修改原始帧和汇总的负例必须失败：相同值误回调、错误回调值、同批读取旧 Peer、回调颠倒、观察轮重放、过期输入 ID、错误协议默认值、额外同步。Python/Rust fixture 仅用于回调记录的初始化方式不同，不据此宣称全部原生 session_state 映射一致。

同一最终二进制重放既有十四轮 radio-empty（111 帧/42 Element）和十轮格式化选择（89 帧/40 Element），继续与各自冻结参考完整字段一致，结果在 target/radio-duplicates-{empty,format}-recheck/trace.json。producer 三份源码、widget_api/widgets、二进制 SHA 均已核对；修前核心源码 SHA 与前一 HEAD 9fba22c 匹配。SDK 自建服务和 Rust 自持 Popen 句柄均已停止，61874/8599 无监听。无新浏览器采集。

编辑 Rust 的 rustfmt、全工作区/all-target Clippy、新增 API 单元通过。最终工作区 324 项通过（317 库、1 ledger、2 宏、4 rustdoc），仍仅排除原 navigation_pages_switch_and_session_state_match_the_measured_wire 与 rerun_queue_messages_match_frozen_reference，不称完整工作区全绿。参数参考模块现为 267 项，相关 query/widget/temporal/pickers/matrix/docs 共 518 项通过；既有 MSVC linker stdout warning 保留。日志 target/radio-duplicates-{red,green,clippy,build,workspace,python}.log。

仅 st.radio 矩阵与生成清单更新，仍 130 partial；浏览器重复选项交互、任意原生类型、绑定/表单/跨页/晚到输入及其他 callback 组合继续开放。用户再次确认 rerun 仅丢弃未发送旧轮 Delta，保留 URL/已发送帧，既有已选方案不扩展到其他队列、hash 或共享状态取舍。用户 colconfig_params 修改独立保留；M3/M5/M7 与长期目标未关闭，未创建 PR、合并、发布或部署。

## Current button-group width identity validation (2026-11-01)

锁定 Python Streamlit 1.66.1 的公开 AppTest 初探确认无 key pills/segmented_control 宽度参与身份；随后七轮同连接原生 WS 同时驱动无 key/keyed 单选 pills 与无 key/keyed 多选 segmented_control。初始空选择→提交 Beta→content 改 300px→再次 Beta→恢复 content→再次 Beta→无输入观察。两次宽度转换均只重置无 key 控件；有 key 始终保留 Beta。恢复已被清理的原身份不会复活旧值。

[SDK](../tests/reference/reference-browser/widget-params/group-width/trace.json)、[Rust 修前](../tests/browser/rust-widget-params/group-width/before/trace.json)、[Rust 最终](../tests/browser/rust-widget-params/group-width/trace.json)各 7 轮、69 原始帧、35 完整 Element。修前正常结束但 width/restore 仍返回全部 Beta，semantic_match=false；公开 API 单元真实失败于 width: Plain pills（Some(Beta) 而非 None）。生产只在 emit_button_group 的无 key 私有身份 extra 补入 c.width，其他参数、状态来源、输入解码、回调和清理流程未改，无新公共接口、依赖或模块。

完整 Element 仅归一化不透明 ID/JSON 文本后逐字段一致。严格门验证四控件实际旧 ID/string_array_value、两类无 key 身份与各一类 keyed 身份、300px/content、single/multi click_mode、PILLS/SEGMENTED_CONTROL style、default/required/help/disabled/ignore_rerun、无额外同步及 session/run/path。八类同步改写原始帧与汇总的负例必须失败：无 key 未变身份、有 key 错变身份、宽度保留旧值、恢复复活旧值、错误像素宽度、过期输入 ID、错误输入 oneof、额外 set_value/raw_values/one-shot。

同一最终二进制重放旧 radio-duplicates（7 轮/55 帧/21 Element）与 format-collisions（10 轮/89 帧/40 Element），完整规范化字段继续匹配，结果 target/group-width-{radio,format}-recheck/trace.json。producer 三份源码、widget_api/widgets 和二进制 SHA 已核对当前产物；修前核心源码 SHA 与前一 HEAD cc39b7a 相同。SDK 自建服务已停止，Rust 自持 Popen 句柄 terminate/wait 已结束，52352/8599 无监听。

无新浏览器采集；相反 style/mode 配对、default/required/mode 变化、错误、callback、绑定/表单/跨页/晚到输入继续开放。只更新 st.pills/st.segmented_control 两行矩阵，生成清单仍 130 partial；清单分类从 no-explicit-gap-stated 转为 unmeasured-parameters 是明确记录尚未验证组合，并未关闭能力。用户 colconfig_params 修改独立保留，未创建 PR、合并、发布或部署；M3/M5/M7 与长期 Goal 继续开放。

编辑 Rust 的 rustfmt、全工作区/all-target Clippy、新增公开 API 单元通过；最终工作区 325 项通过（318 库、1 ledger、2 宏、4 rustdoc），仍仅排除原 navigation_pages_switch_and_session_state_match_the_measured_wire 与 rerun_queue_messages_match_frozen_reference，不称完整工作区全绿。参数参考模块 279 项、相关 query/widget/temporal/pickers/matrix/docs 共 530 项通过；文档/矩阵收尾门 52 项通过。既有 MSVC linker stdout warning 保留；日志 target/group-width-{red,green,clippy,build,workspace,python}.log。

## Current button-group required and mode identity validation (2026-11-01)

锁定 SDK 1.66.1 的公开 AppTest 观察后，十轮同连接原生 WS 覆盖 pills/segmented_control 两个样式，各含 keyed/无 key 对照。流程：初始单选空值→四控件 Beta→required=true 保留→改 Alpha→required=false 保留→改多选全部空数组→输入 [Beta,Alpha] 保序→恢复单选全部 None→输入 Beta→无输入观察。required 不参与身份，selection_mode 参与所有控件身份；恢复已清理模式不复活旧选择。

[SDK](../tests/reference/reference-browser/widget-params/group-policy/trace.json)与[Rust 最终](../tests/browser/rust-widget-params/group-policy/trace.json)各 10 轮、99 原始帧、50 完整 Element；[Rust 修前](../tests/browser/rust-widget-params/group-policy/before/trace.json)10 轮、93 帧、44 Element，semantic_match=false。修前 required/optional 轮丢失无 key 选择，multi 轮 keyed 单值被当数组读取报错，restore 轮又因旧数组被当单值读取报错；应用捕获成 Markdown，script_finished=0 并不表示兼容成功，后续不完整恢复也原样保留。单元红复现失败于 required: Plain pills（None 而非 Beta）。

生产只修 emit_button_group 身份 extra：有 key 时包含 multi，拒绝沿用旧模式身份；无 key 时移除 required，保留 options/default/multi/width。注册、状态来源、解码、回调、清理和公共返回类型不改，无新增公共接口、模块或依赖。这里的“模式变化重建”复用现有身份与清理机制，不引入新的错误保留流程或共享状态层。

完整 Element 仅归一化不透明 ID/JSON 文本后逐字段一致。严格门核对四控件各两类身份、required 不变身份、单多选 click_mode、两种 style、四控件实际前轮 ID/string_array_value、多选顺序、content 宽度、声明默认/策略、无额外同步、session/run/path 和逐轮返回。八类同步改写 raw 与汇总的负例必须失败：required 错变身份、keyed 模式未变身份、策略变更丢值、模式变更留旧值、恢复复活旧值、错误 click_mode、输入逆序、额外同步。

同一最终二进制重放旧 group-width 七轮（69 帧/35 Element），与冻结 SDK 完整规范化字段继续匹配，结果 target/group-policy-width-recheck/trace.json。producer 三份源码、widget_api/widgets 与二进制 SHA 已核对当前产物；修前核心源码 SHA 与前一 HEAD 5ee995b 相同。SDK 自建服务与 Rust 自持 Popen 句柄均已停止，52668/8599 无监听。

无新浏览器采集；required 的真实不可取消选择交互、default/代码状态变化、错误、callback、绑定/表单/跨页/晚到输入继续开放。只更新 st.pills/st.segmented_control 两行矩阵，生成清单仍 130 partial；不据此关闭 M3/M5/M7 或长期 Goal。用户 colconfig_params 修改独立保留，未创建 PR、合并、发布或部署。

编辑 Rust 的 rustfmt、全工作区/all-target Clippy、新增公开 API 单元通过；最终工作区 326 项通过（319 库、1 ledger、2 宏、4 rustdoc），仍仅排除原 navigation_pages_switch_and_session_state_match_the_measured_wire 与 rerun_queue_messages_match_frozen_reference，不称完整工作区全绿。参数参考模块 291 项，相关 query/widget/temporal/pickers/matrix/docs 共 542 项通过；文档/矩阵收尾门 52 项通过。既有 MSVC linker stdout warning 保留；日志 target/group-policy-{red,green,clippy,build,workspace,python}.log。

## Current button-group filtered native-state validation (2026-11-01)

锁定 Python Streamlit 1.66.1 公开 AppTest 初探后，十轮同连接原生 WS 覆盖 keyed pills/segmented_control 各单选/多选：默认 Beta→前端 Alpha/[Beta,Alpha,Beta]→选项缩为 [Beta]→空列表→恢复选项→代码赋失效字符串/混合有效失效字符串列表→观察→代码清空→输入恢复→最终观察。单选失效字符串回到当前默认，多选逐项移除 Gone/失效项并保留顺序和重复；空选项同步清空，恢复列表不自动选择默认，后续原生状态与返回值一致，观察轮不重放同步。

[SDK](../tests/reference/reference-browser/widget-params/group-state/trace.json)与[Rust 最终](../tests/browser/rust-widget-params/group-state/trace.json)各 10 轮、99 原始帧、50 完整 Element；[Rust 修前](../tests/browser/rust-widget-params/group-state/before/trace.json)10 轮、91 帧、42 Element。修前 subset/assign 两轮报 session value is absent from options，应用捕获为 Markdown，下一观察轮默认 [Beta] 取代了应保留的 [Beta,Beta,Alpha]；semantic_match=false，不能把 script_finished=0 当作兼容成功。新增公开 API 单元先因相同错误真实失败。

widgets.rs 复用原有 selection_default/selection_reset：ButtonGroup 单选失效字符串恢复默认并同步，多选 read_session_value 过滤失效字符串，比较修正后的原生数组决定同步。codec 新私有 filter_invalid 标志区分 pills/segmented_control 与同样复用该 codec 的 select_slider：后者仍严格拒绝失效区间端点，新增公开 API 回归证明不渲染半个区间。ButtonGroup 非字符串失效项及非数组多选仍保留现有错误，不把不同返回类型问题悄悄过滤掉。无新公共 API、模块、依赖或来源/回调/登记失败保留流程。

完整 Element 仅归一化不透明 ID/JSON 文本后逐字段一致。严格门核对四个稳定 keyed 身份、真实前轮 ID/string_array_value、动态 options/default、四轮 set_value/raw_values/one-shot、单多选/style、disabled/help/required/width、session/run/path，以及逐轮 values/native。八类同时改写原始帧与汇总的负例必须失败：错误返回、丢重复项、未修正原生状态、错误同步顺序、缺失 subset 同步、缺失空选项同步、过期输入 ID、错误声明默认。

同一最终二进制重放 group-policy 十轮（99 帧/50 Element）与 group-width 七轮（69 帧/35 Element），完整规范化字段继续匹配，结果 target/group-state-{policy,width}-recheck/trace.json。producer 三份源码、widget_api/widgets 与二进制 SHA 均已核对；修前核心源码 SHA 与前一 HEAD d4c0a4c 一致。SDK 自建服务与 Rust 自持 Popen 句柄均已停止，50578/8599 无监听。

首次 all-target 编译指出旧 buttons codec 单元两处初始化缺少新字段，已补齐；随后 Clippy 拒绝新增单元的三处 unwrap，已改为有上下文的 expect，失败日志 target/group-state-clippy-before-expect.log 保留。其他编辑 Rust 已逐文件检查语义空行和 diff。

无新浏览器采集；异类型原生状态、错误输入、callback、真实清空 UI、绑定/表单/跨页/晚到输入等继续开放。仅 st.pills/st.segmented_control 两行矩阵及生成清单更新，仍 130 partial；select_slider 的其他已知差异及待决方案保持。用户 colconfig_params 修改独立保留，未创建 PR、合并、发布或部署，M3/M5/M7 与长期 Goal 未关闭。

编辑 Rust 的 rustfmt、全工作区/all-target Clippy、新增公开 API 单元通过；最终工作区 327 项通过（320 库、1 ledger、2 宏、4 rustdoc），仍仅排除原 navigation_pages_switch_and_session_state_match_the_measured_wire 与 rerun_queue_messages_match_frozen_reference，不称完整工作区全绿。参数参考模块 303 项，相关 query/widget/temporal/pickers/matrix/docs/buttons/inputs 八模块共 609 项通过；文档/矩阵收尾门 52 项通过。既有 MSVC linker stdout warning 保留；日志 target/group-state-{red,green,clippy,build,workspace,python}.log。

## Current button-group duplicate-default validation (2026-11-01)

锁定 SDK 1.66.1 的公开 AppTest 验证 pills/segmented_control 多选允许重复默认值，四项默认可以超过两项选项数，单选项上三个相同默认也合法。逐项必须属于选项；单选仍至多一个默认。Rust emit_button_group 原先以 default.len()>options.len() 统一拒绝；本次仅移除该数量条件，保留单选数量与逐项存在性检查，无新公共 API、模块或依赖。

[SDK](../tests/reference/reference-browser/widget-params/group-defaults/trace.json)与[Rust 最终](../tests/browser/rust-widget-params/group-defaults/trace.json)各八轮、79 原始帧、40 完整 Element；两样式各含 keyed/无 key 多选对照。初始 [Beta,Beta,Alpha,Beta] 原样返回，默认索引 [1,1,0,1]；输入 [Alpha,Beta,Alpha] 后，将默认换成 [Alpha,Alpha,Alpha] 仅重建无 key 控件，有 key 保留输入；接着输入重复 Beta，空选项清空所有值（仅 keyed 旧值过滤需同步）；恢复旧默认时无 key 从默认开始，有 key 保持空数组；最后输入 Alpha 并观察保持。

[Rust 修前](../tests/browser/rust-widget-params/group-defaults/before/trace.json)保留首轮五帧/一个 Markdown/一次 script_finished=0 的真实失败前缀，错误 button-group defaults must fit the selection mode。首轮未产生任何控件 ID，采集器准备第二轮提交时 KeyError: Plain pills 中断，trace 无 successful；不得称为八轮修前运行。原始帧未重采或替换，异常路径未记录 websocket_closed，因此不作该字段成功声明；Rust 自持服务句柄已停止。补充 metadata 时收尾脚本也因 cleanup 缺省抛 KeyError，已改用 setdefault，只补实际已验证的 caller_server_stopped。新增公开 API 单元先因同一生产拒绝真实失败，修后通过。

完整 Element 仅归一化不透明 ID/JSON 文本后逐字段一致。严格门核对 default 的顺序与重复数、四控件真实前轮 ID/string_array_value、三类无 key 身份与各一类 keyed 身份、动态默认/空选项/清理恢复、set_value/raw_values/one-shot、style/mode/策略、session/run/path。八类同时改写 raw 与汇总的负例必须失败：默认重排、默认去重、有 key 错变身份、无 key 未变身份、有 key 随默认重置、空恢复复活旧值、缺失空同步、输入顺序变化。

公开 API 单元另覆盖两样式的单选项重复默认、空默认、原生 state/返回值及声明 default/no-sync，以及单选多个默认和多选列表外默认仍拒绝且不发送 Delta。后两项仅证明拒绝边界，未宣称 Python 错误类型、文案或默认错误 UI 完整一致。

同一最终二进制重放 group-state/group-policy 各十轮、99 帧/50 Element，完整规范化字段继续匹配，结果 target/group-defaults-{state,policy}-recheck/trace.json。producer 三份源码、widget_api/widgets 与二进制 SHA 已核对；修前核心源码 SHA 与前一 HEAD 8e74b3e 一致。SDK 自建服务和 Rust 自持 Popen 句柄均已停止，58814/8599 无监听。

无新浏览器采集；重复项可见高亮、callback、任意格式化、错误 UI、绑定/表单/跨页/晚到输入等继续开放。仅 st.pills/st.segmented_control 两行矩阵与生成清单更新，仍 130 partial；未改变完整目标和待决方案。用户 colconfig_params 修改独立保留，未创建 PR、合并、发布或部署，M3/M5/M7 与长期 Goal 未关闭。

编辑 Rust 的 rustfmt、全工作区/all-target Clippy、新增公开 API 单元通过；最终工作区 328 项通过（321 库、1 ledger、2 宏、4 rustdoc），仍仅排除原 navigation_pages_switch_and_session_state_match_the_measured_wire 与 rerun_queue_messages_match_frozen_reference，不称完整工作区全绿。参数参考模块 315 项，相关 query/widget/temporal/pickers/matrix/docs/buttons/inputs 八模块共 621 项通过；文档/矩阵收尾门 52 项通过。既有 MSVC linker stdout warning 保留；日志 target/group-defaults-{red,green,clippy,build,workspace,python}.log。

## Current feedback dynamic identity validation (2026-11-01)

锁定 SDK 1.66.1 公开 AppTest 后，十二轮同连接原生 WS 驱动无 key/keyed feedback：初始 stars/default=None→输入 4→default=0→输入 3→width=300→输入 2→faces→输入 4→thumbs→输入 1→恢复初始 stars→观察。无 key 的原始默认 None/0 与宽度分别决定身份；有 key 忽略默认和宽度但保留图标类型；两端恢复已清理旧 stars 身份均返回 None，不复活旧评分。

[SDK](../tests/reference/reference-browser/widget-params/feedback-identity/trace.json)与[Rust 最终](../tests/browser/rust-widget-params/feedback-identity/trace.json)各 12 轮、95 原始帧、36 完整 Element；[Rust 修前](../tests/browser/rust-widget-params/feedback-identity/before/trace.json)12 轮、94 帧、35 Element。修前 zero 轮返回 [4,4] 而非 [0,4]，width 轮返回 [3,3] 而非 [0,3]，faces keyed 错留 2，thumbs 又因旧 4 越界报 value does not match feedback，恢复 stars 仍错留 1。应用捕获成 Markdown，script_finished=0 不能作为兼容成功。公开 API 单元真实失败于 zero: 0（Some(4) 而非 Some(0)）。

生产仅修 widget_api.rs 的 feedback 身份 extra：无 key 序列化 kind/原始 Option default/width，有 key 保留 kind。Codec、输入验证/回调/状态来源/清理及协议发送不改；无新公共 API、依赖或模块。公开 API 回归核对原生 keyed state、返回评分、声明 default 存在性、type、无额外 set_value/value、身份类别与清理恢复。

完整 Element 仅归一化不透明 ID/JSON 文本后逐字段一致。严格门检查实际前轮 ID/string_value、五类无 key/三类 keyed 身份、None 与数值 0 的区别、content/300px、三种 type、default 存在性、set_value/value/one-shot、禁用/表单/ignore 字段、session/run/path、值与原生 state 的 integer/None 类型。八类同时改写 raw 与汇总的负例必须失败：省略默认误设 0、宽度不重建、keyed 图标不重建、错误返回、恢复复活旧值、额外同步、过期输入 ID、数值相等却变浮点。

producer 三份源码、widget_api/widgets 与二进制 SHA 已核对当前产物；修前核心源码 SHA 与前一 HEAD e694a46 一致。SDK 自建服务和 Rust 自持 Popen 句柄均已停止，57743/8599 无监听。无新浏览器采集；feedback 的真实清空交互、callback、禁用/错误输入、代码赋值、表单/跨页等继续开放。矩阵仅更新 st.feedback，将已取得原生 default/faces 证据与仍未测浏览器范围区分；生成清单仍 130 partial，分类变化不表示关闭能力。

编辑 Rust 的 rustfmt、全工作区/all-target Clippy、新增公开 API 单元通过；最终工作区 329 项通过（322 库、1 ledger、2 宏、4 rustdoc），仍仅排除原 navigation_pages_switch_and_session_state_match_the_measured_wire 与 rerun_queue_messages_match_frozen_reference，不称完整工作区全绿。参数参考模块 327 项，相关 query/widget/temporal/pickers/matrix/docs/buttons/inputs 八模块共 633 项通过。既有 MSVC linker stdout warning 保留；日志 target/feedback-identity-{red,green,clippy,build,workspace,python}.log。

用户 colconfig_params 修改独立保留；未创建 PR、合并、发布或部署；待决共享状态/hash/公共接口方案不变，M3/M5/M7 与长期 Goal 未关闭。

## Current feedback ID-only clear and callback validation (2026-11-01)

锁定 SDK 1.66.1 的 FeedbackSerde 区分三态：没有 value oneof 使用注册默认，string_value="" 显式清空，非空字符串表示评分。Rust 原有 Codec::Feedback 已支持后两者，但没有接入 ID-only 默认缓存，空同伴会使整批输入被丢弃。本次仅把 Feedback 加入现有 selectbox/radio 的 empty_input 缓存集合，更新 Record 注释；默认随登记更新，begin_widgets 用上轮缓存解码。其他 codec 的默认解码、输入校验、来源、回调与注册清理流程不改，无新公共 API、模块或依赖。

[SDK](../tests/reference/reference-browser/widget-params/feedback-empty/trace.json)、[Rust 修前](../tests/browser/rust-widget-params/feedback-empty/before/trace.json)、[Rust 最终](../tests/browser/rust-widget-params/feedback-empty/trace.json)各十轮、79 原始帧、30 完整 Element。主控件 stars 默认 2、同伴 faces 默认 None；评分 4→显式清空→主 ID-only/同伴 3→默认改 0 但无输入→主 ID-only/同伴清空→代码赋 None/4→观察→同时清空→评分 1/同伴 ID-only。修前 edit/clear/peer/fallback 均错保留 [2,None] 且无 callback，recover 又丢失 1；帧数和正常 script_finished 相同不证明兼容成功。新增 API 单元真实失败于 run 1 回调数 0 而非 1。

修后返回值逐轮 [2,None]/[4,None]/[None,None]/[2,3]/[2,3]/[0,None]/[None,4]/[None,4]/[None,None]/[1,None]；累计八条 callback 与 SDK 相同。同批主控件恢复默认和同伴更新时，两回调按 primary→peer 顺序读取整批新值；仅改声明默认不改当前值，下一输入才用新默认；代码赋值不触发 callback，仅发送一次 set_value/value/one-shot，观察不重放；重复清空主控件 None 不误回调。Python/Rust callback 日志初始化方式不同仅属探针记录，不据此宣称整个 session_state 初始化映射一致。

完整 Element 仅归一化不透明 ID/JSON 文本后逐字段一致。严格门核对实际旧 ID、缺省 oneof 与显式空字符串区别、两控件稳定身份、默认 2/0/None 存在性、两种 type、content 宽度、代码同步 value 存在性、session/run/path、返回 integer/None、完整有序回调前缀。八类同时改写 raw 与汇总的负例必须失败：缺省误改空字符串、使用过期默认、回调读旧同伴值、回调顺序颠倒、观察轮重放、清空仍回默认、缺失代码同步值、过期输入 ID。

同一最终二进制重放旧 feedback-identity 十二轮（95 帧/36 Element），完整规范化字段继续匹配，结果 target/feedback-empty-identity-recheck/trace.json。producer 三份源码、widget_api/widgets 与二进制 SHA 已核对；修前核心源码 SHA 与前一 HEAD 377fd2a 相同。SDK 自建服务和 Rust 自持 Popen 句柄均已停止，52076/8599 无监听。无新浏览器采集，ID-only 是原生协议注入，不据此宣称实际浏览器一定生成同一种包。

仅更新 st.feedback 矩阵和生成清单，仍 130 partial；真实清空 UI、禁用/错误输入、ignore、表单/跨页及其他 callback 组合继续开放。用户 colconfig_params 修改独立保留；待决共享状态/hash/公共接口方案不变，未创建 PR、合并、发布或部署，M3/M5/M7 与长期 Goal 未关闭。

编辑 Rust 的 rustfmt、全工作区/all-target Clippy、新增公开 API 单元通过；最终工作区 330 项通过（323 库、1 ledger、2 宏、4 rustdoc），仍仅排除原 navigation_pages_switch_and_session_state_match_the_measured_wire 与 rerun_queue_messages_match_frozen_reference，不称完整工作区全绿。参数参考模块 339 项，相关 query/widget/temporal/pickers/matrix/docs/buttons/inputs 八模块共 645 项通过；文档/矩阵收尾门 52 项通过。既有 MSVC linker stdout warning 保留；日志 target/feedback-empty-{red,green,clippy,build,workspace,python}.log。

## Current feedback browser clearing and callback validation (2026-11-01)

使用 computer-use 技能，在真实 Chrome 依次驱动锁定 SDK 1.66.1 与当前 Rust：初始 stars 默认三颗（原生 2）/faces 未选→点第五颗星→再点第五颗清空→同伴 Satisfied→再点 Satisfied 清空→主控件两颗星。两端各六画面/六运行、48 覆盖二进制帧、18 完整 Element；值依次 [2,None]/[4,None]/[None,None]/[None,3]/[None,None]/[1,None]，五条 callback 依次 primary 4/None、primary None/None、peer None/3、peer None/None、primary 1/None，DOM checked/active、可见 JSON 与完整规范化协议一致。

[SDK 浏览器记录](../tests/reference/reference-browser/widget-params/feedback-empty/ui/trace.json)、[Rust 浏览器记录](../tests/browser/rust-widget-params/feedback-empty/ui/trace.json)包含十二张原始 JPEG，均已逐张查看；实际 1463×780、DPR=1.75，文件未编辑。星级填充、重复点击后清空、faces 满意/清空、评分和回调显示一致；后几轮 JSON 回调列表超出视口，完整列表由 DOM 和原始协议核对，不宣称截图展示全部回调或整页像素一致。

实际浏览器每次交互均携带两个当前 widget ID 和显式 string_value，未选/清空为 ""；本次未产生 ID-only 包，因此不能将上轮原生 ID-only 失败宣称为这段真实浏览器交互的修前失败。原生十轮协议边界证据独立保留。本批无生产 Rust/fixture 修改，仅补真实用户交互及证据门。

采集从启用 Network 后有意 reload 开始；SDK 保存 49 事件（1 created+48 帧）。Rust 保存 51 事件：开头旧连接的 rerun_script/new_session 两帧因初次导航与刷新交叠而被捕获，原样保留并单列为覆盖外前缀；其后的新连接同为 49 事件/48 帧。两条旧帧不能并入新连接计数或直接删去。两端采集均在关闭 tab 前 disable Network，未声明观察到 close 帧。

严格门重解码全部原始事件，检查序列/来源 tab/连接/两条旧前缀、逐阶段事件边界与八帧顺序、session/run/path、实际 ID/oneof/空字符串、声明默认 2/None、type/width/无额外同步、完整有序 callback，以及 DOM 十按钮语义和选中/激活样式。图片 SHA/字节/格式/尺寸严格核对，五个星位的黄色像素门区分 3/5/0/0/0/2 颗填充，可拒绝旧清空图替换五星图后同步改哈希。faces 像素未单独建立选择门，不将 hover 变白当作选择证据。

两份正例、完整字段比较及八类负例共十一项新增测试通过；负例包括清空 oneof 被省略、错误回调、错误声明默认、过期输入、错误 checked、图片哈希、旧图/新哈希、错误覆盖计数。参数参考模块 350 项，相关 query/widget/temporal/pickers/matrix/docs/buttons/inputs 八模块共 656 项通过；日志 target/feedback-ui-python.log。无生产修改，本批未重跑 Rust 工作区或 Clippy，不将上一轮 330 项结果冒充本批运行。

源码与二进制 SHA 已核对 a7f4fe0 当前已提交内容；SDK/Rust 自建服务 PID 53600/33816 经自持 Popen 句柄 terminate/wait 结束，协调进程真实退出 0，56480/8599 无监听；两个自建标签均已关闭，console warn/error 均为空。截图与采集动作分开执行，避免动作后旧帧被当作新画面。指南 README 原 CRLF 字节前缀保持，仅追加说明。

仅 st.feedback 矩阵与生成清单更新，仍 130 partial；动态默认/图标/宽度 UI、代码赋值 UI、禁用/ignore、表单/跨页及其他 callback 组合继续开放。用户 colconfig_params 修改独立保留，未创建 PR、合并、发布或部署；M3/M5/M7 与长期 Goal 未关闭。

## Current text ID-only default and callback validation (2026-11-01)

检查 text_area 动态身份时先确认该项已有历史修复，没有重复修改。新缺口来自锁定 SDK 1.66.1 的 TextInputSerde/TextAreaSerde：缺少 value oneof 回到有效默认，显式空串保留空串，二者均按 max_chars 截断。Rust Text codec 已处理显式字符串，却未接入已有 ID-only 默认缓存，导致同批 checkbox 也被丢弃。本次只对 kind=text_input/text_area 且 Codec::Text 的登记缓存默认；data_editor 复用 Text codec，但不在本次扩展范围，无新公共接口、模块或依赖。

[SDK](../tests/reference/reference-browser/widget-params/text-empty/trace.json)、[Rust 修前](../tests/browser/rust-widget-params/text-empty/before/trace.json)、[Rust 最终](../tests/browser/rust-widget-params/text-empty/trace.json)均八轮、71 原始帧、32 完整 Element。text_input 原始默认 Base🙂X 限五字符，text_area 初始 None 限六字符，同伴 checkbox 初始 false；输入 EDIT🙂X→主 ID-only/多行中文 emoji→全空串/false→声明默认改 Next 无输入→两个 ID-only/true→观察→恢复字符串/false。修前 edit/area 两轮仍 [Base🙂,None,false] 且无 callback，最终只累计四回调；原始失败记录保持 semantic_match=false，不能把相同帧数和正常 script_finished 当作兼容成功。

修后有效返回依次 [Base🙂,None,false]/[EDIT🙂,None,true]/[Base🙂,第一\n行🙂X,true]/[空串,空串,false]/[空串,空串,false]/[Next,None,true]/[Next,None,true]/[OK,恢复\n🙂,false]；这里的 \n 表示实际换行，分别按 Unicode scalar 截为五/六字符，不按 UTF-8 字节或 UTF-16 单元截断。声明 default 仍保留未截断 Base🙂X；缺省包使用上轮已归一化默认。仅改变声明默认不覆盖当前空串，下一轮缺省解码才采用 Next。

累计十三次 callback 与 SDK 完整顺序一致；回调读取整批解码后的文本、area 与 checkbox 新值。input/area/peer 同时变化时按注册顺序执行，观察不重放。两端 callback 日志初始化方式不同仅属探针记录，不宣称整个 session_state 初始化映射一致。新增公开 API 单元先因局部 input 变量遮蔽 input() 辅助函数编译失败，已重命名；编译错误保留 target/text-empty-test-compile.log，再以未修生产逻辑真实复现 run 1 回调 0 而非 2，修后通过。

完整 Element 仅归一化不透明 ID/JSON 文本后逐字段一致。严格门核对三控件稳定 ID、实际前轮 ID、缺省/string_value/bool_value、Unicode/换行/None/空串、声明 default/上限、text area 122px、width/策略/无额外同步、session/run/path、逐轮返回及有序 callback 前缀。八类同时修改 raw 与汇总的负例必须失败：缺省误改空串、Unicode 未截断、回调倒序、回调读取旧 area、旧默认回退、空串误变 None、wire 默认被提前截断、过期 peer ID。

同一最终二进制重放旧 feedback-empty 十轮（79 帧/30 Element），完整规范化字段仍匹配，结果 target/text-empty-feedback-recheck/trace.json。producer 三份源码、widget_api/widgets 与二进制 SHA 已核对；修前核心源码 SHA 与前一 HEAD a20f8ed 相同。SDK 自建服务和 Rust 自持 Popen 句柄均已停止，52867/8599 无监听。无本批浏览器采集，ID-only 为原生协议注入，不推定浏览器生成该包。

编辑 Rust 的 rustfmt、全工作区/all-target Clippy、新增公开 API 单元通过；最终工作区 331 项通过（324 库、1 ledger、2 宏、4 rustdoc），仍仅排除原 navigation_pages_switch_and_session_state_match_the_measured_wire 与 rerun_queue_messages_match_frozen_reference，不称完整工作区全绿。参数参考模块 362 项，相关 query/widget/temporal/pickers/matrix/docs/buttons/inputs 八模块共 668 项通过；既有 MSVC linker stdout warning 保留，日志 target/text-empty-{red,green,clippy,build,workspace,python}.log。

仅 st.text_input/st.text_area 矩阵和生成清单更新，仍 130 partial；真实浏览器、禁用/错误输入、查询绑定/表单/跨页及其他 callback 组合继续开放。用户 colconfig_params 修改独立保留；待决共享状态/hash/公共接口方案不变，未创建 PR、合并、发布或部署，M3/M5/M7 与长期 Goal 未关闭。

## Current numeric missing range and callback validation (2026-11-01)

锁定 Python Streamlit 1.66.1 的 NumberInputSerde 将缺省值、显式边界外数值、非有限浮点和隐式边界外整数回退到其注册默认，再比较状态并调用 callback。Rust 原有 ID-only 未解码，且越界/非有限值在整批有效性门被拒绝，导致同伴 checkbox 输入丢失。本次 widgets.rs 给 NumberInput 缓存有效默认，在 decode_state 先按上轮显式边界或隐式整数 JS-safe/有限浮点边界回默认；错误 oneof 仍不解码，代码赋值及注册时范围重置流程未改。无新公共 API、模块或依赖。

[SDK](../tests/reference/reference-browser/widget-params/number-empty/trace.json)、[Rust 修前](../tests/browser/rust-widget-params/number-empty/before/trace.json)、[Rust 最终](../tests/browser/rust-widget-params/number-empty/trace.json)均十一轮、98 原始帧、44 完整 Element。整数默认 4、浮点 2.5，各有显式边界，后改默认 6/1.25；交错有效输入/ID-only、99/-99 越界、NaN、移除显式边界、int64 最大值与 Infinity、边界值 0/-5 和无输入观察。SDK/Rust 修后累计回调数 0/2/4/6/6/9/10/10/11/14/14；修前前八个后续阶段仍 [4,2.5,false] 且无回调，最终仅两条回调。相同帧数和正常 script_finished 不能替代行为一致。

缺省/非法数值回默认后继续接受 checkbox，callback 读取整批归一化后的 integer/float/bool；整数前端极大值按隐式安全上界回默认，不截断溢出转换。仅改变声明默认不覆盖当前值，下一轮输入才采用新默认。前端回默认不额外发送 set_value/value/one-shot，与 SDK 一致，不虚构捕获到前端界面回正。程序原生赋值、None 返回建模和跨 oneof 数值转换不由本批推定。新增公开 API 单元先真实失败于 run 1 回调 0 而非 2，修后完整十一轮通过。

完整 Element 仅归一化不透明 ID/JSON 文本后逐字段一致。严格门验证三控件稳定身份、实际旧 ID/int_value/double_value/bool_value/缺省 oneof、真实 NaN/Infinity 和 int64 最大值的二进制负载、显式/隐式 min/max 与 has 标志、default/format/step/data_type、width/策略、无额外同步、session/run/path、integer/float/bool 返回类型与十四条有序回调。八类同时改写 raw 与汇总的负例必须失败：缺省变显式零、NaN 被替成有限零、隐式越界未回默认、使用旧默认、回调读旧 peer、回调倒序、错误隐式边界、额外同步。

同一最终二进制另重放旧 keyed number-sequence/number-float 各十二轮（每份 83 帧/24 Element）和 text-empty 八轮（71 帧/32 Element），所有完整规范化 Element 继续匹配 SDK，结果 target/number-empty-{integer,float,text}-recheck/trace.json。未更改旧冻结参考，数字代码范围重置和文本缺省行为未回归。

producer 三份源码、widget_api/widgets 与二进制 SHA 均已核对当前产物；修前核心源码 SHA 与前一 HEAD 4783f72 一致。SDK 自建服务与 Rust 自持 Popen 句柄均已停止，54073/8599 无监听。无本批浏览器采集；ID-only、NaN/Infinity、越界值是原生协议注入，不宣称正常 UI 一定生成这些包。

编辑 Rust 的 rustfmt、全工作区/all-target Clippy、新增公开 API 单元通过；最终工作区 332 项通过（325 库、1 ledger、2 宏、4 rustdoc），仍仅排除原 navigation_pages_switch_and_session_state_match_the_measured_wire 与 rerun_queue_messages_match_frozen_reference，不称完整工作区全绿。参数参考模块 374 项，相关 query/widget/temporal/pickers/matrix/docs/buttons/inputs 八模块共 680 项通过；既有 MSVC linker stdout warning 保留，日志 target/number-empty-{red,green,clippy,build,workspace,python}.log。

仅 st.number_input 矩阵及生成清单更新，仍 130 partial；错误 oneof、nullable Rust 返回、代码赋值边界、禁用输入、浏览器、表单/跨页及其他组合继续开放。用户 colconfig_params 修改独立保留；待决共享状态/hash/公共接口方案不变，未创建 PR、合并、发布或部署，M3/M5/M7 与长期 Goal 未关闭。

## Current time missing invalid and callback validation (2026-11-01)

初查 date_input/time_input 后，先推进已有公开接口能表达且取得完整参考的 time_input 行为。锁定 SDK 1.66.1 的 TimeInputSerde：缺省、空串和无效时间回有效默认；同时接受 HH:MM/HH:MM:SS，分钟 step 去秒，秒级 step 补齐或保留秒，不强制对齐 step 网格。已有 keyed 原生 None 会覆盖后来声明的默认；恢复有效值后，新声明默认才重新登记。Rust 原来缺省/另一格式/无效串整批拒绝，空串反而直接清空，且原生 None 时错误发送声明默认。

[SDK](../tests/reference/reference-browser/widget-params/time-empty/trace.json)、[Rust 修前](../tests/browser/rust-widget-params/time-empty/before/trace.json)、[Rust 最终](../tests/browser/rust-widget-params/time-empty/trace.json)各十二轮、107 原始帧、48 完整 Element。Minute 默认 12:30/step=900、Seconds 默认 None/step=1，同伴 checkbox；交错有效输入、双格式、无效/空串、声明默认改 16:20/06:07:08、ID-only、闰秒、恢复 01:02:03/04:05:06、观察、再次 ID-only。修后累计 callback 为 0/2/4/7/10/11/11/13/14/17/17/20；修前最终仅一次 callback，后半段均错误保留 [None,None,false]。相同帧数和正常 script_finished 不能证明兼容。

widgets.rs 接入 TimeInput 有效默认缓存；私有 decode 接受两种时间格式并按 step 规范字符串，无效/空串产生回默认标记，由 decode_state 使用上轮有效默认。chrono 可解析 23:59:60 为闰秒，而 Python 不允许该时间，因此拒绝 nanosecond>=1_000_000_000 的解析结果再回默认。错误 oneof 未扩展，数字/文本/其他 codec 的解码规则不改。widget_api.rs 仅在 TimeInput 构造有效默认与 wire default 时尊重 keyed 原生 None，原始调用参数仍参与既有身份规则，无新公共接口、模块或依赖。

公开 API 单元先真实失败于 run 1 回调 0 而非 2，修后完整十二轮通过；callback 读取整批归一化后时间与 checkbox，None/空串不制造错误回调，观察不重放，普通前端回默认不额外同步。01:02:03 在分钟 step=900 下得到 01:02，而非被强制吸附到十五分钟。既有 pickers 单元错误断言 whole-minute 只能收 HH:MM，已依据 SDK 双格式参考改为正常接受后去秒；其空串说明也修正为默认回退标记，不再将私有中间 Null 等同实际清空。

完整 Element 仅归一化不透明 ID/JSON 文本后逐字段一致。严格门核对三稳定 ID、实际旧 ID/缺省/string/bool oneof、原始无效与闰秒负载、有效默认存在性、step/format/width/策略/无额外同步、session/run/path、string/None/bool 返回类型与二十条有序回调。八类同时改写 raw 与汇总的负例必须失败：缺省变字符串、分钟未去秒、秒格式未补零、闰秒误接受、None 时发送新声明默认、回调读旧 peer、回调倒序、缺省使用旧默认。

同批重建 temporal_params 示例，重放旧 keyed-identity 十一轮（98 帧/44 Element）与 unkeyed-identity 八轮（71 帧/32 Element），完整规范化 Element 均继续匹配 SDK，结果 target/time-empty-{keyed,unkeyed}-recheck/trace.json；旧冻结参考不改。主 widget_params 与 temporal_params 两个二进制 SHA、producer 三份源码及 widget_api/widgets SHA 已核对当前产物；修前核心源码 SHA 与前一 HEAD 27fc671 一致。

SDK 自建服务与两组 Rust 自持 Popen 句柄均已停止，53394/8599/8600 无监听。无本批浏览器采集，ID-only/无效时间/闰秒均为原生协议注入，不推定正常 UI 生成同样包。日期范围的部分值、date/datetime 的缺省和无效解析并未在本批修复或关闭。

编辑 Rust 的 rustfmt、全工作区/all-target Clippy、新增公开 API 单元通过；最终工作区 333 项通过（326 库、1 ledger、2 宏、4 rustdoc），仍仅排除原 navigation_pages_switch_and_session_state_match_the_measured_wire 与 rerun_queue_messages_match_frozen_reference，不称完整工作区全绿。参数参考模块 386 项，相关 query/widget/temporal/pickers/matrix/docs/buttons/inputs 八模块共 692 项通过；既有 MSVC linker stdout warning 保留，日志 target/time-empty-{red,green,clippy,build,temporal-build,workspace,python}.log。

仅 st.time_input 矩阵与生成清单更新，仍 130 partial；错误 oneof、禁用/ignore、真实浏览器、查询绑定、表单/跨页和其他组合继续开放。用户 colconfig_params 修改独立保留；待决共享状态/hash/公共接口方案不变，未创建 PR、合并、发布或部署，M3/M5/M7 与长期 Goal 未关闭。

## Current datetime frontend fallback validation (2026-11-01)

继续已有正确类型输入工作。锁定 SDK 1.66.1 的 DateTimeInputSerde：缺省、空数组、首项无法解析及前端越界输入回上轮有效默认；只读取数组首项，接受 ISO/legacy 分钟格式，包含边界，不强制吸附 step。已有 keyed 原生 None 压过后来声明的默认。此行为可由现有 Option<NaiveDateTime> 表达，不涉及新增公共接口、依赖、模块或文件。

widgets.rs 的私有 DateTimeInput codec 增加上轮有效 min/max，在前端 decode 时归一化并产生默认回退标记；接入已有 empty_input 缓存及 decode_state 回退。代码赋值的 valid 检查保持原有解析规则，未把新的前端边界检查套用到原生代码赋值。widget_api.rs 使用 keyed 原生 None 构造有效 serde/default，原始 options.value 仍参与既有身份规则。修正既有 runtime 单元将空数组等同清空、将无效字符串直接拒绝的错误断言；错误 oneof 继续拒绝。

公开 API 单元先失败于 ID-only 整批回调为 0 而非 3（target/datetime-fallback-red.log），修后覆盖十二案：缺省、空数组、无效、无效首项加有效尾项、下越界、上越界、含秒、两端边界、ISO、legacy、有效首项加无效尾项。每案先把 populated/None 默认的两个 datetime 都改成非默认值，随后与 checkbox 同批提交；三个 callback 均读到归一化后的完整新值。再将声明默认改成 16:20，核对当前返回值不被覆盖、None 的 proto default 为空、无额外 set_value；下一轮 ID-only 使用新登记的有效默认。Rust 四项相关 datetime 单元/原有运行时协议测试通过。

tests/reference/test_temporal_params_reference.py 新增 SDK serde 24 案和 AppTest 12 案。AppTest 使用真实公开 st.datetime_input 调用与 WidgetStates protobuf 注入，检查相同的三回调值、新旧有效默认、稳定 ID 及无额外同步；直接使用 SDK 的 _run 入口，不称公开测试接口。SDK 36 案通过，相关八模块共 728 项通过。此批未新增冻结捕获文件，AppTest/直接 serde 证据不等于原生 WS 或真实浏览器差分，既有冻结捕获未被改写。

用户再次选定错误类型提交复现 Python 错误、已发生的 callback 和后续恢复，以及 rerun 仅丢弃未发送旧轮 Delta、保留 URL/已发送帧。本批不改发送流程，也不把这两项已选取舍扩展到其他共享状态/hash 架构；当前计划保留其实施和验证边界。

新增 Rust 测试中的两处 unwrap 首次被 Clippy 拒绝，已改成说明固定 fixture 的 expect 后通过全工作区/all-target Clippy，日志保留 target/datetime-fallback-clippy.log 和 -clippy-final.log；既有 MSVC linker stdout warning 保留。编辑 Rust 格式检查及逐文件 diff 复查完成。生产代码只改 datetime 前端回退；用户 colconfig_params 修改独立保留。

最终工作区 334 项通过（327 库、1 ledger、2 宏、4 rustdoc），仍仅排除原 server::tests::navigation::navigation_pages_switch_and_session_state_match_the_measured_wire 与 server::tests::queryparams::rerun_queue_messages_match_frozen_reference，不称完整工作区全绿。文档/矩阵收尾门 52 项通过。日志 target/datetime-fallback-{red,green,sdk,clippy,clippy-final,workspace,python,docs}.log；本批没有启动额外采集服务。

新增边界的原生 WS/浏览器、代码赋值后的动态边界重置、错误类型/文案、禁用/ignore、查询绑定、表单/跨页及其他状态组合仍未验收；矩阵和生成清单不提升状态，130 partial、M3/M5/M7 与完整 Goal 保持开放。未创建 PR、合并、发布或部署。

## Current datetime native fallback evidence (2026-11-01)

为前一批 datetime 修复补原生 WebSocket 验收。复用 widget_params 两端示例与参数校验模块，新增 --datetime-empty 采集模式；生产 widgets/widget_api 未改。两项冻结结果为 [SDK](../tests/reference/reference-browser/widget-params/datetime-empty/trace.json) 与 [Rust](../tests/browser/rust-widget-params/datetime-empty/trace.json)，各十八轮、161 原始帧、72 完整 Element，首次采集直接匹配，无失败捕获被覆盖。

同连接顺序为 load/edit/missing/legacy/invalid/below/above/minimum/maximum/surplus/empty/defaults/fallback/bad-first/seconds/recover/observe/reset。Moment 初始默认 12:30、Optional 默认 None，固定 2025-03-15 08:00..18:00，另有 checkbox 同伴。分别验证 ID-only、空数组、无法解析首项、越界和含秒字符串回有效默认，合法首项忽略无效尾项、非法首项不看合法尾项，legacy 规范为 ISO、包含边界且不吸附 900 秒步长。声明默认改为 16:20 时当前值保留；已有原生 None 的 wire default 继续为空，恢复合法值后才重新登记声明默认。

累计 callback 计数为 0/3/6/9/12/13/14/17/20/23/26/26/28/29/30/33/33/36，按 moment/optional/peer 注册顺序逐条比对；每条均看到整批归一化新值。观察轮不重放，常规前端回退无额外 set_value/one-shot。完整 Element 仅规范化不透明控件 ID 和 JSON 文本后逐字段匹配，semantic_match 只在严格门成功后写为 true。

严格门从原始 base64 重解析 protobuf，核对原始字节数/message JSON/元素汇总、18 个 run/同一 session、三稳定旧 ID、string_array/bool/缺省 oneof、实际输入列表（包含空数组存在性）、min/max/default/step/format/布局/策略/sync、路径及全部返回值类型/36 条有序回调。八类负例同时改写原始包、字节数、message 与元素汇总后必须被拒绝：错误 oneof、空数组改 ID-only、越界误接受、legacy 未归一化、None 错发新默认、callback 读旧 peer、callback 逆序、缺省回旧默认。

参数参考模块增加 11 项至 397；相关八模块 739 项通过。编辑 Rust 示例已按语义留空、逐 diff 检查，格式、cargo build 示例与全工作区/all-target Clippy 通过；既有 MSVC linker stdout warning 保留。本批未改生产/库测试，不重复完整工作区测试；上批 334 项及两项排除是上一批证据，不称本批重跑。日志 target/datetime-ws-{build,sdk,rust,server,gate,python,clippy,docs}.log。

采集器三份 producer、Rust widgets/widget_api 及实际示例二进制 SHA 与当前产物逐一核实。SDK 自有服务和 Rust 自持 Popen 均 terminate/wait 完成，SDK 动态端口与 8599 无监听；本批无浏览器采集。矩阵仅补 st.datetime_input 证据与边界，生成 inventory 仍 130 partial；修正旧兼容记录把空数组等同强制清空的文字。真实浏览器、代码赋值后的动态边界重置、错误 oneof/类型/文案、禁用/ignore、查询绑定、表单/跨页及其他组合仍开放，M3/M5/M7 和完整目标未关闭。用户既有 colconfig 修改独立保留，无 PR、合并、发布或部署。

## Current datetime native bound reset implementation (2026-11-01)

对照锁定 SDK 1.66.1 _validate_datetime_value 与 datetime_input 的登记后处理：只在显式提供 min/max 时检查当前非空原生值；越界回本轮原始声明默认（可 None），更新 keyed session state，发送 value/set_value/one-shot。重置不生成额外 callback。省略显式边界时不因计算出的十年窗口重置代码赋值；原生 None 也不触发范围重置。

Rust 私有 DateTimeInput codec 增加 reset_default: Option<Value>，仅显式边界时保存本轮原始声明默认。它与上一轮前端 serde 的有效默认有不同职责：前者用于登记后的原生范围重置，后者继续用于前端无效/缺省反序列化。沿用既有注册阶段 range_reset，返回值和 keyed state 在同次提交中修正，并复用现有同步标记。没有增加公共接口、依赖、模块或文件，不改变错误原生类型、其他 codec、hash/发送策略或待决架构。runtime datetime 的 codec 构造补齐新私有字段。

公开 API 单元先真实失败于 narrow 仍返回 17:00 而非 12:30，target/datetime-bounds-red.log 保留。修后八阶段 load/edit/narrow/observe/assign/implicit/none/null-observe 对照 SDK AppTest：旧 08:00..18:00 下提交 17:00，然后无输入收窄 max=16:00 回 12:30；观察不再同步；代码赋 19:00 仍回 12:30；省略边界时代码赋 2050-03-15T19:00 保留；恢复显式边界并声明 None 后清空，后续观察保持 None 且不重发。三次 reset 加 implicit 代码同步均核对 set_value、value 与一次性标记；仅 edit 的一个 callback 读到 17:00，后续重置不增加 callback，ID 全程稳定。SDK AppTest 使用 _run(WidgetStates()) 进行无输入轮，避免普通 app.run 序列化旧值后被上一轮 serde 回退，掩盖新边界行为；不是公开 AppTest 入口或真实 WS 证明。

另有 Rust 公开 API 单元与四组 SDK AppTest 测量单侧边界：min-only 的 07:59 回 12:30，08:00 保留；max-only 的 16:01 回 12:30，16:00 保留。新增五项 SDK 参考与两项 Rust 单元，六项相关 datetime 测试通过（含原有运行时协议测试），相关八模块共 744 项通过。指南补充显式/隐式边界语义，原 CRLF 字节前缀验证保留；矩阵及生成 inventory 仍 130 partial。

同批重建 widget_params 当前二进制，在 target/datetime-bounds-fallback-recheck/trace.json 重放旧十八轮同连接原生参考：161 帧、72 完整 Element 和 36 条有序 callback 继续与冻结 SDK 一致，完整字段仅归一化 ID/JSON。旧冻结结果不改；本批生产变动的当前源码/二进制 SHA 保存在重放结果。自持 Rust Popen 已 terminate/wait，8599 无监听，没有启动新的 SDK 采集服务。本次新动态重置场景本身尚无原生 WS 或浏览器捕获，不把旧回退重放算成新场景全覆盖。

最终工作区 336 项通过（329 库、1 ledger、2 宏、4 rustdoc），仍仅排除原 server::tests::navigation::navigation_pages_switch_and_session_state_match_the_measured_wire 与 server::tests::queryparams::rerun_queue_messages_match_frozen_reference，不称完整工作区全绿。文档/矩阵收尾门 52 项通过。

Rust 格式检查、逐文件 diff 复查及全工作区/all-target Clippy 通过，既有 MSVC linker stdout warning 保留；日志 target/datetime-bounds-{red,green,final-green,sdk,python,clippy,build,native,server,workspace,docs}.log。仅做相关实现和验证，用户 colconfig 及其他现有修改独立保留，无 PR、合并、发布或部署。新重置的原生 WS/浏览器、同轮前端输入伴随新边界、错误原生类型/文案、禁用/ignore、URL、表单/跨页和其他状态组合继续开放，M3/M5/M7 与完整 Goal 未关闭。

## Current datetime native bound reset evidence (2026-11-01)

为前批显式边界重置补原生 WebSocket 验收。复用 widget_params 两端 datetime 分支、采集器和参数校验模块，新增 --datetime-bounds 模式，不改生产 widgets/widget_api。冻结 [SDK](../tests/reference/reference-browser/widget-params/datetime-bounds/trace.json) 与 [Rust](../tests/browser/rust-widget-params/datetime-bounds/trace.json) 各十四轮、125 原始帧、56 完整 Element；首次捕获直接一致，没有覆盖失败结果。旧 --datetime-empty 输出保持原样。

顺序为 load/edit/narrow/observe/widen/joint/assign/implicit/implicit-observe/explicit-none/none-observe/recover/reset/final。Moment 默认 12:30、Optional 默认 None，同伴 checkbox。先在 08:00..18:00 下输入两个 17:00，再无输入收窄 max=16:00，分别回 12:30/None 并发送一次同步；观察不再同步，放宽也不复活旧值。joint 轮提交同样的 17:00 和 peer=false，同时脚本把 max 收窄到 16:00：三个 callback 先依注册顺序读到整批 [17:00,17:00,false]，登记后返回和 keyed state 才变为 [12:30,None,false]，带 value/set_value/one-shot。不能把回调值错误改成已经重置的值。

代码为两个 key 赋 19:00 同样重置；省略边界后代码赋 2050-03-15T19:00，虽超出推导的 2015..2035 窗口仍保留并同步，无输入观察继续保留且不重发。随后恢复显式边界且两个声明默认均为 None，两个 key 一起重置为空，value 数组虽空也必须 set_value/one-shot=true；新声明 12:30 的观察轮仍尊重原生 None、default 空且无同步。恢复有效 15:47 后重新登记 12:30 默认；再收窄 max=15:00 时两个控件均回 12:30 并同步，下一轮不重复。

累计 callback 计数 0/3/3/3/3/6/6/6/6/6/6/9/9/9，全部九条的来源、顺序、完整同伴新值严格匹配，范围重置本身不产生 callback。报告同时记录返回值和 keyed native state，逐轮一致。严格门从 base64 重解析 protobuf，核对长度/message/元素汇总、实际旧 ID 和 string_array/bool 输入、14 个 run/同一 session、稳定三 ID、min/max/default/value/set_value/one-shot 存在性、format/step/宽度/策略、路径、finish 和原生类型。完整 Element 仅规范化不透明 ID 和 JSON 文本后逐字段相等，semantic_match 只在此门成功后写 true。

十类同步改写原始字节、message 和元素汇总的负例必须失败：joint callback 错读重置值、native 未重置、缺同步、观察重复同步、隐式边界错误重置、空 value 缺同步、原生 None 错发声明默认、过期输入 ID、回调倒序、错误边界。新增十三项至参数模块 410 项，相关八模块 757 项通过。编辑 Rust 示例格式检查、逐文件 diff 与全工作区/all-target Clippy 通过；既有 MSVC linker stdout warning 保留。无生产/库测试变动，不重复完整工作区测试，上批 336 项和两项既有排除仍是上批证据。

同批用当前 SDK fixture 与同一 Rust 二进制各重跑旧十八轮 --datetime-empty，target/datetime-reset-ws-old-{sdk,rust}/trace.json 保留各 161 帧/72 Element，规范化完整字段同时匹配旧冻结 SDK，避免共享 fixture 分支回归。三份 producer、生产 widgets/widget_api 和二进制 SHA 已核对当前产物；SDK 自有服务与两次 Rust 自持 Popen 均 terminate/wait，50179/51806/8599 核实无监听。日志 target/datetime-reset-ws-{build,sdk,rust,server,gate,python,clippy,old-sdk,old-rust,old-server,docs}.log。

仅 st.datetime_input 矩阵及生成 inventory 增补证据，仍 130 partial。本批无浏览器证据；单侧边界的原生 WS、错误类型/文案、禁用/ignore、URL、表单/跨页和其他状态组合继续开放，不把双侧/当前组合推广为全部行为已验收。用户 colconfig 及其他现有修改独立保留，无 PR、合并、发布或部署；M3/M5/M7 与完整 Goal 未关闭。

## Current single date frontend normalization (2026-11-01)

先复验已排除 rerun_queue_messages_match_frozen_reference，target/rerun-queue-current-red.log 仍真实失败：旧轮 Rust 保留 config、丢弃 toast，SDK 则保留 toast、丢弃 config，其他 URL/finish 等投影一致。已选的未发送 Delta 丢弃/已发送 Delta 与 URL 保留已实现且有既有回归；这次失败属于 2026-10-30 已提出、尚待用户选择的消息类型扩展。未擅自扩大 handler 规则，也未将该 red 删除或改绿。

继续独立的 date_input 单日期行为。锁定 SDK 1.66.1 DateInputSerde 与 AppTest 确认：ID-only、非法字符串和任一越界条目回默认；ISO/legacy 全列表先解析并检查 min/max，再返回首项。非法或越界尾项也会使整组回默认，全部合法的额外日期则只返回首项。空数组不同于缺省，SDK 返回 None；现有 DateSelection 不能表达，依 AGENTS.md 第 2 条向用户提供 Single(Option)/Range(Vec)、保留旧变体另补变体、另增单值/范围接口三个实际选项，尚未收到选择，不实施公开模型变更。

widgets.rs 现有 DateInput codec 保存 min/max/声明默认，仅单日期分支接受 legacy、规范成 ISO 并整组解析/范围验证后回默认；将单日期纳入已有 ID-only 默认缓存。范围分支保留原来 ISO/恰好两项的解码规则，wrong oneof 继续拒绝；空数组仍解为 Null，不伪装成回默认。widget_api.rs 仅把已有默认/边界传给私有 codec，公开 API 未改。既有 pickers codec 单元的非法日期 fail-closed 断言按 SDK 证据修正为回默认，并继续保护空数组与错误 oneof、范围部分值的现状。

公开 API 单元先真实失败于缺省提交两个 callback 为 0，修后十案覆盖缺省、非法、legacy、ISO、合法尾项、非法尾项、首项越界、尾项越界、包含两端边界。每案先编辑到非默认值，再同批输入日期和 checkbox，两个 callback 依登记顺序读到整批新值。声明默认改为 06-10 时当前值保留、wire default 更新且无额外 set_value；下一轮 ID-only 才使用新登记默认。对应 SDK AppTest 十案从原始 WidgetStates 注入得到相同状态/回调/默认，明确使用内部 _run，不称正常浏览器输入。

[SDK](../tests/reference/reference-browser/widget-params/date-single/trace.json) 与 [Rust](../tests/browser/rust-widget-params/date-single/trace.json) 各十六轮、127 原始帧、48 完整 Element，首次采集直接匹配，未覆盖失败捕获。顺序 load/edit/missing/legacy/surplus/bad-tail/bad-first/below/above-tail/minimum/maximum/defaults/fallback/observe/recover/invalid；固定 2025-01-01..12-31、默认 03-15，后改 06-10。累计 callback 0/2/4/6/7/9/10/11/12/14/16/16/18/18/20/22，完整二十二条来源/顺序/同伴新值与原生状态逐轮匹配。观察轮不重放，回默认不额外同步。

严格门从原始 base64 重解析 protobuf，核对原始长度/message/元素汇总、16 个 run/同一 session、两个稳定 ID、实际旧 ID/缺省/string_array/bool oneof、全部原始列表、路径及 default/min/max/format/布局/策略/value/set_value/one-shot 与完整返回值和 keyed state。完整 Element 只规范化不透明 ID/JSON 文本后逐字段相等；semantic_match 在严格门成功后才写 true。八类同步破坏原始字节和汇总的负例均拒绝：错误 oneof、legacy 未归一化、忽略非法尾项、忽略越界尾项、回旧默认、callback 读旧 peer、callback 倒序、错变 range 模式。

编辑 Rust 已按语义留空并逐文件复查 diff；格式、全工作区/all-target Clippy、新增公共单元及既有 pickers 两项通过。最终工作区 337 项通过（330 库、1 ledger、2 宏、4 rustdoc），仍只排除原 navigation_pages_switch_and_session_state_match_the_measured_wire 与 rerun_queue_messages_match_frozen_reference，不称全绿。参数参考模块现 421 项，相关八模块共 778 项通过；既有 MSVC linker stdout warning 保留。日志 target/date-single-{red,green,final-unit,pickers,sdk,clippy,build,sdk-ws,rust-ws,server,gate,workspace,python,docs}.log。

采集器三份 producer、生产 widgets/widget_api 与二进制 SHA 均已核对当前产物；SDK 自建服务和 Rust 自持 Popen 均 terminate/wait，58258/8599 无监听。指南仅追加单日期语义，保留原 CRLF 字节前缀。矩阵仅补 st.date_input 证据及 limitation，生成 inventory 仍 130 partial。没有本批浏览器证明；None/空及部分范围模型待选，范围解码、隐式 today 默认/状态、代码赋值/动态边界、错误类型/文案、禁用/ignore、URL、表单/跨页等仍开放。用户 colconfig 与其他现有修改独立保留，无 PR、合并、发布或部署；M3/M5/M7 与完整 Goal 未关闭。

## Current single date actual Chrome validation (2026-11-01)

使用 computer-use 技能和真实 Chrome 复用现有 --date-single 示例，不改生产或 fixture 源码。保存 [SDK](../tests/reference/reference-browser/widget-params/date-single/ui/trace.json) 与 [Rust](../tests/browser/rust-widget-params/date-single/ui/trace.json) 各十一阶段、五轮真实 rerun、40 覆盖二进制帧、15 完整 Element 和四条 callback。Network 观察在首次 HTTP 页面之后启用，有意 reload 开始覆盖；两端均无旧连接前缀，41 个事件为一次 created 加 40 帧。没有原生注入，没有将旧 malformed/ID-only 捕获冒充正常 UI。

步骤：01-load 显示 2025/03/15、Peer=false；02-calendar-open 打开三月；03-calendar-next 翻四月，无请求；04-calendar-commit 选择 4/20 触发 day callback；05-peer 点击标签改 true，触发 peer callback；06-keyboard-draft 在 day 分段按 ArrowUp，分段与 hidden date 都显示 4/21，但 JSON/后端仍为 4/20 且无请求；07-keyboard-tab 与 08-keyboard-enter 均未提交；09-calendar-reopen 打开日历，无请求；10-draft-calendar-commit 点击已选择的 4/21 才产生 day callback；11-peer-restore 再改 false，触发 peer callback。四条来源、值和同伴状态依次 [day,4/20,false]、[peer,4/20,true]、[day,4/21,true]、[peer,4/21,false]。

SDK 一次 checkbox.check() 自动化动作报告失败；随即用新 AX 和 checked 属性确认仍 false、没有发送请求，再点击可见 Peer 标签成功。此尝试记录在 SDK trace.attempts，不当作产品失败或悄悄重试为成功。Rust 直接使用已验证的标签操作。22 张原始 JPEG 均逐张查看，包括 SDK 04 在混合动作工具报错后从保存文件单独查看；不裁剪、不重绘证明图。截图保留键盘焦点/浮层绘制，部分分段草稿截图显示日历绘制，而同一阶段的 DOM dialog 快照为空，原样保留，不据此宣称弹层动画稳定或逐帧等价。关键输入草稿/后端旧值均可直接核对。

SDK 原始视口 1463x780、Rust 1463x724，DPR 均 1.75，未设置 viewport override；高度差和随 JSON 变长出现的滚动条保留，不宣称全屏像素相同。每张图片校验原始字节数、SHA256、JPEG 类型和真实尺寸；日期字段区域变化另阻止把初始 03/15 图片重算哈希后当作最终 04/21。此像素门是初始图复用检测，不等于通用日期文字 OCR。

严格门从每阶段 CDP 原始 events 重解析 protobuf，确认 pages/events 双份投影一致、cursor/sequence/真实 tab 和单连接 requestId、五组完整 message/status/path 次序、同一 session/五 run、实际旧 ID/string_array/bool oneof、context 中的 zh/Asia-Shanghai/dark/当前 origin、日期 default/min/max/format/布局/策略/sync、全部返回及 keyed state 和回调。DOM 同时核对年月日分段、hidden date、checkbox 与可见 JSON，明确区分草稿和已提交值。完整 Element 只规范化控件 ID 与 JSON body，逐字段相等后才将 Rust semantic_match 写 true。

新增十一项至参数模块 432 项。八类负例拒绝草稿 DOM 复用后端旧值、把 peer 请求挪到键盘阶段、发送旧日期、callback 旧值、额外 set_value/one-shot、过期输入 ID、损坏截图哈希、初始图重算哈希后复用为最终图；涉及协议的负例同步改写 raw payload 和 pages/events，避免只测汇总不一致。相关八模块共 789 项通过，日志 target/date-single-ui-{gate,python,docs}.log；本批没有 Rust 源码变动，不重复 Clippy 或完整 Cargo 测试，上批 337 项及两项既有排除是上批证据，不称本批重跑。

生产 widgets/widget_api、两端 fixture 与运行二进制 SHA 均和采集 metadata/当前文件一致；原始 source_commit=40b0b37 标识启动时基线。两标签已关；Network 在关 tab 前关闭，不宣称捕获 close 帧。自持 Python/Rust Popen 在 coordinator 的 finally 中 terminate/wait，执行句柄正常退出，57820/8599 无监听。目标日志 target/date-single-ui-{sdk,rust}-server.log；target/date-single-ui-stop 是本次唯一停止标记，未复用旧服务。

仅 st.date_input 矩阵及生成 inventory 补真实 UI 证据，仍 130 partial；指南追加草稿与日历提交的区别并保留原 CRLF 前缀。None/空及部分范围公开模型仍待用户选择，日历边界/错误、动态边界 UI、禁用/ignore、URL/表单/跨页、其他主题/语言/视口和更广组合仍开放。用户 colconfig 与其他现有修改独立保留，无 PR、合并、发布或部署；M3/M5/M7 与完整 Goal 未关闭。

## Current date native bound reset validation (2026-11-01)

对照锁定 SDK 1.66.1 _validate_date_value，推进当前 DateSelection 已能表达的单日期和完整双端点范围：仅显式给出 min/max 时，单日期越界或范围首项低于 min/末项高于 max，才回本轮声明默认。返回值与 keyed state 一起更新并发送 value/set_value/one-shot，重置本身不产生 callback；默认推导的十年窗口不重置代码赋值。None/空及部分范围返回模型尚待用户选择，本批未扩大公共接口。

widgets.rs 的 DateInput codec 增加 reset_native 标志，由 widget_api.rs 用原始显式 min/max 是否存在设置。沿用既有登记阶段 range_reset：单日期解析当前原生字符串后检查边界，范围按 SDK 的首/尾规则检查已支持的两个原生端点，再统一提交 corrected value/state 和现有同步标记。已有 frontend decode/缺省缓存、范围 ISO/恰好两项规则、错误类型和 native valid 检查保持原状；不是把新边界直接放入 valid 而提前阻止回退。runtime pickers codec 构造补新私有字段。没有新增依赖、模块或公共 API。

公开 API 单元分别对 single/range 执行十三阶段，先真实失败于 single:narrow 保留 4/20 而非默认 3/15（target/date-bounds-red.log）；修后两种模式均通过。SDK AppTest 两模式的相同十三阶段经原始 WidgetStates 注入确认，观察轮只注入空 WidgetStates，避免旧前端 serde 掩盖新边界重置；SDK 入口 _run 是内部测试接口，不称正常浏览器操作。

[SDK](../tests/reference/reference-browser/widget-params/date-bounds/trace.json) 与 [Rust](../tests/browser/rust-widget-params/date-bounds/trace.json) 首次原生采集各十三轮、116 帧、52 完整 Element，无失败捕获覆盖。Single 默认 2025-03-15，Range 默认 03-15..03-20，同伴 checkbox。顺序 load/edit/narrow/observe/widen/joint/assign/implicit/implicit-observe/minimum/maximum/lower/final。先在宽范围输入单值 4/20、范围 4/20..5/20、peer=true；收窄 max 到 4/10 后回各自默认并同步一次，无输入观察不重复，放宽也不复活旧值。

joint 轮在旧宽边界下提交单值 4/25、范围 4/25..5/25、peer=false，本轮又收窄 max=4/10：三个 callback 先按 single/range/peer 的登记顺序读到整批新输入，随后登记才将返回和原生值重置为默认。assign 轮代码赋 2026 年日期同样回默认且无额外 callback；implicit 轮省略边界后代码赋 2050 年日期，虽然超出计算的 2015..2035 窗口仍保留并同步；implicit-observe 无输入继续保留且不重发。minimum 轮值恰好在 min 保留；maximum 轮 single 恰好 4/20、range 末端恰好 5/20 保留；lower 轮首日期 2/28 低于新 min=3/1，单值和完整范围都回默认，final 不重发。全部只有 edit 与 joint 产生六条 callback，范围重置不合成 callback。

严格门从原始 base64 重解析 protobuf，核对原始 bytes/message 与元素汇总、三稳定旧 ID 和 single 一项/range 两项/bool oneof、13 run/同一 session、全部路径及 single/range default/min/max/is_range/format/布局/策略/value/set_value/one-shot、返回值/原生值类型与六条有序回调。完整 Element 仅规范化控件 ID 与 JSON body 后逐字段相等；semantic_match 在此门成功后才写 true。八类 raw/汇总同时修改的负例均拒绝：缺单值同步、range 原生未重置、观察重复同步、隐式边界错误重置、joint callback 读到重置后值、过期 range 输入 ID、恰好最大值错误回默认、重置额外 callback。

同批用当前二进制重放旧单日期十六轮 --date-single，target/date-bounds-old-single/trace.json 的 127 帧/48 完整 Element 和 22 条 callback 继续匹配冻结 SDK；不覆盖旧原始参考，也未重采上一批浏览器图。生产 widgets/widget_api、三份 producer 及实际二进制 SHA 已与本批原生捕获逐一核对。SDK 自建服务和两次 Rust 自持 Popen 均 terminate/wait，49696/8599 无监听。

按代码检查、公开单元、相关运行时协议与原生采集顺序完成验证；编辑 Rust 格式和逐文件 diff、全工作区/all-target Clippy 通过，既有 MSVC linker stdout warning 保留。最终工作区 338 项通过（331 库、1 ledger、2 宏、4 rustdoc），仍仅排除原 server::tests::navigation::navigation_pages_switch_and_session_state_match_the_measured_wire 与 server::tests::queryparams::rerun_queue_messages_match_frozen_reference，不称全绿。参数参考模块 443 项，相关八模块共 802 项通过；日志 target/date-bounds-{red,green,sdk,clippy,build,final-unit,pickers,sdk-ws,rust-ws,server,gate,recheck,recheck-server,workspace,python,docs}.log。

指南仅追加显式边界重置/回调顺序，保留原 CRLF 字节前缀。矩阵仅补 st.date_input 证据和 limitation，生成 inventory 仍 130 partial。本批无浏览器证据；None/空/部分范围模型待选，范围前端 malformed/legacy/越界、模式或原生类型不匹配、浏览器动态边界、禁用/ignore、URL/表单/跨页和其他组合继续开放，不把正常完整值推广为全部日期行为已兼容。用户 colconfig 与其他现有修改独立保留，无 PR、合并、发布或部署；M3/M5/M7 与完整 Goal 未关闭。

## Current complete date range frontend normalization (2026-11-01)

继续现有返回模型能表达的范围输入，对照锁定 SDK 1.66.1 DateInputSerde 及真实 st.date_input AppTest。范围 ID-only 使用上轮登记默认；ISO/legacy 可混合，先解析整个列表并检查全部边界，任一非法/越界条目恢复完整默认。全部合法的双端点保留输入顺序，允许相等和反向提交值，不擅自排序。这里指前端提交，构造默认范围的既有起点<=终点校验仍保留。

widgets.rs 删除单值/范围重复解析，共用现有单日期 ISO/legacy 与整组回退逻辑；范围分支在解析成功且全部在边界内后仍要求两项，将范围纳入既有缺省默认缓存。默认字段注释同步说明前端回退和原生重置职责。无新公开接口、依赖、模块或文件，登记后的显式边界重置规则不变，wrong oneof 仍拒绝。

公开 API 单元先真实失败于范围 ID-only 使日期和 peer 的两个 callback 均为 0，target/date-range-red.log 保留；修后十二案通过：缺省、legacy、非法首项/末项、首项低于 min/末项高于 max、包含两端边界、相等/反向端点、ISO/legacy 混合、单项非法列表和含非法项的三项列表。后两类 SDK 会返回完整默认双端点，现有模型能表达，所以一并修复。每案先把范围改成非默认 4/10..4/20，再提交原始数组/缺省和 peer=false，两个 callback 均看到整批归一化值且顺序为 range/peer；将声明默认改为 6/10..6/20 后当前值不覆盖，wire default 更新且无额外 set_value，下一轮 ID-only 才使用新默认。

十二组 SDK AppTest 从原始 WidgetStates 经内部 _run 验证相同的返回/原生范围、callback 完整同伴值、稳定 ID/default/no-sync 与下一轮默认更新；不是原生 WS 或浏览器捕获。另三组 SDK-only direct serde 原样证明合法 0/1/3 日期输入可产生对应长度 tuple，序列化后仍为原列表。Rust runtime codec guards 继续明确拒绝合法空/单项/三项范围，防止当前模型偷偷截断或回默认。该边界仍等待此前公开模型三个选项的决定，不宣称已兼容。

按代码检查→新公开单元→既有 pickers 两项→真实原生复验顺序完成验证。当前重建 widget_params 二进制分别重跑旧 date-bounds 十三轮（116 帧/52 Element）和 date-single 十六轮（127 帧/48 Element），结果 target/date-range-{date-bounds,date-single}-recheck/trace.json 与冻结 SDK 的完整 Element 仅规范化 ID/JSON 后一致，既有六条/二十二条 callback 仍匹配。它们不覆盖本批新增 legacy/非法范围路径，不当作新增边界的原生差分。旧参考和上批浏览器截图不改，本批没有新 WS 冻结文件或浏览器采集。

编辑 Rust 的格式、逐文件 diff 和全工作区/all-target Clippy 通过，既有 MSVC linker stdout warning 保留。最终工作区 339 项通过（332 库、1 ledger、2 宏、4 rustdoc），仍只排除原 server::tests::navigation::navigation_pages_switch_and_session_state_match_the_measured_wire 与 server::tests::queryparams::rerun_queue_messages_match_frozen_reference，不称全绿。相关八模块共 817 项通过，包含 SDK-only 未实现形状证据；参数参考模块 443 项未增加，temporal 参考模块新增十五项至 97 项。日志 target/date-range-{red,green,sdk,clippy,pickers,build,server,date-bounds,date-single,workspace,python,docs}.log。

当前源码/二进制 SHA 与两份重放 metadata 一致；自持 Rust Popen 在 finally terminate/wait，8599 已核实无监听，未启动新的 SDK 服务。指南仅追加完整范围默认回退，原 CRLF 字节前缀保留；矩阵与生成 inventory 仍 130 partial。新增范围 malformed/legacy 的原生 WS/浏览器、合法空/部分/多端点公开模型、模式与类型不匹配、禁用/ignore、URL/表单/跨页及其他组合仍开放。用户 colconfig 与其他现有修改独立保留，无 PR、合并、发布或部署；M3/M5/M7 与完整 Goal 未关闭。

## Current date range native frontend validation (2026-11-01)

补上一批范围归一化的原生 WebSocket 证据；没有生产实现改动。复用 widget_params 两端示例和采集器的 opt-in date-range 模式，新增两份首次冻结记录：[SDK](../tests/reference/reference-browser/widget-params/date-range/trace.json)、[Rust](../tests/browser/rust-widget-params/date-range/trace.json)。各十九轮、170 原始帧、76 完整 Element、33 条有序 callback，同一连接/session、十九个不同 run、三个稳定控件 ID。

每轮保留 Single、Range、Peer 和完整返回/原生值/回调 JSON。先改值，再提交 ID-only；覆盖 legacy/ISO 混合、非法首/末项、首项低于 min/末项高于 max、恰好 min/max、相等/反向端点保序、非法单项/三项数组。非法列表回完整已登记默认，不裁剪、排序或截断；这里不包含全合法的空/部分/多端点范围。默认由 3/15..3/20 改为 6/10..6/20 时保留当前值，不额外 callback 或同步；下一轮缺省恢复新默认，观察不重复，恢复正常输入后再以非法输入回新默认。全部 callback 先读到整批归一化后的日期和 Peer 值。

严格门重解析原始 base64/protobuf、bytes/message 双投影和元素汇总，核对全部消息/status 次序、旧 ID、输入 oneof/原始非法或 legacy 数组、history 标志、session/run、路径，以及 default/min/max/format/is_range/布局/策略/no-value/no-set_value/no-one-shot。完整 Element 仅规范化 opaque widget ID 和 JSON body，逐字段相等后才设置 Rust semantic_match=true。两份原始成功捕获没有覆盖；metadata 的三份 producer、两份生产源码及实际二进制 SHA 与当前文件逐一匹配。

参数模块增加十一项至 454 项。八类同时改写 raw bytes/message/元素投影的负例分别拒绝：把 ID-only 改成空数组 oneof、legacy 原生值不归一化、非法末项直接返回、超过 max 仍接受、反向端点排序、三项非法请求被改为合法双项、callback 读到旧 Peer、默认更新后仍回旧默认。每个负例先确认确实改动一帧，避免空操作导致误通过。

同一当前二进制重放旧 date-bounds 十三轮 116 帧/52 Element 和 date-single 十六轮 127 帧/48 Element，与冻结 SDK 的完整 Element 继续一致；target/date-range-ws-old-{date-bounds,date-single}/trace.json 保留，不覆盖原始参考。SDK 自持服务与所有 Rust Popen 均 finally terminate/wait，51944/8599 已核实无监听；collector 的 caller-owned 清理信息只在进程退出后确认。

编辑 Rust 示例格式和逐文件 diff、全工作区/all-target Clippy、示例构建均通过，既有 MSVC linker stdout warning 保留。没有生产代码变化，本批未重复完整 Cargo 测试；上批 339 项及两个既有排除仍属上批证据。日志 target/date-range-ws-{clippy,build,sdk,rust,server,replay-server,old-date-bounds,old-date-single,python,docs}.log。

仅 st.date_input 矩阵新增原生证据键和本批 limitation，生成 inventory 仍 130 partial。合法空/部分/多端点公开返回模型仍待用户选择；本批没有新浏览器证据，模式/类型不匹配、禁用/ignore、query binding、表单/跨页及更广组合仍开放。用户 colconfig 及其他已有修改独立保留，无 PR、合并、发布或部署；M3/M5/M7 和完整 Goal 保持开放。
本批相关八模块实测 1541 项通过：test_widget_params_reference、test_temporal_params_reference、test_pickers_contract、test_temporal_contract、test_datetime_contract、test_inputs_contract、test_refcore、test_capture_checks。文档/配置/矩阵三模块 55 项通过。增加完整消息次序断言后另重跑日期范围十一项；不将不同选择的八模块计数与上一批 817 项直接作增量比较。

## Current date explicit-bound mode reset validation (2026-11-01)

锁定 SDK 1.66.1 的 _validate_date_value 及当前 AppTest 显示：有 key 的 date_input 在单日期与完整范围模式间切换时 ID 保持；只要本轮显式声明 min 或 max，旧原生状态与新模式不匹配就恢复本轮默认。原 Rust 在既有 codec.valid 阶段直接报 value does not match date_input，未到返回转换或发出 Element。本批没有更改公开 DateSelection 或新增依赖。

生产改动仅 widgets.rs 登记重置匹配中的一个分支：显式边界且非 Null 时，范围模式的非数组/空数组，或单日期模式的非字符串，回本轮默认并进入现有 range_reset 提交。沿用返回/keyed state/value/set_value/one-shot 一次同步，重置不额外 callback；其余日期解析、前端 oneof/列表长度校验、默认缓存和现有边界规则保持。Null、合法部分/多端点范围与无显式边界的跨模式返回仍有公开模型/转换边界，未据本切片扩大兼容声明。

公开 API 单元真实先红于单值编辑后切换范围：target/date-mode-red.log 的 InvalidValue(value does not match date_input)；修后双边界、仅 min、仅 max 各十二阶段通过。阶段 load/edit/range/range-edit/single/single-edit/range-narrow/range-observe/range-recover/single-narrow/single-recover/single-observe。模式切换重置为单值 3/15 或范围 3/15..3/20；上轮模式解析输入，callback 先读整批日期和 Peer，登记后重置，不增加 callback。观察不重复同步，恢复正常输入仍可继续。另公开 API 验证两种模式各布尔 false、整数 7、空数组原生赋值，用显式 min 回默认并同步；这些是代码赋值，不称前端错 oneof。

对应 SDK AppTest 三组十二阶段和六个原生形状赋值共九项通过。调用内部 _run 注入实际 WidgetStates，观察轮用空 WidgetStates，避免 AppTest 旧前端 serde 掩盖状态变化；不是正常浏览器输入。

[SDK](../tests/reference/reference-browser/widget-params/date-mode/trace.json) 与 [Rust](../tests/browser/rust-widget-params/date-mode/trace.json) 首次原生采集各十二轮、95 帧、36 完整 Element、十条有序 callback，一条连接/session、十二个 run、两个稳定 ID。Single-edit 发送两个合法日期并验证上轮单值 serde 只返回首项；四次切换时 default/value/set_value/one-shot 和本轮模式一致，其他轮没有同步。完整 Element 只规范化 opaque ID 和 JSON body 后逐字段相等，严格门通过后才设 Rust semantic_match=true。原始首次成功记录未覆盖。

严格门从 raw base64 重解析 protobuf，核对 bytes/message/元素投影、全部消息和 running 状态顺序、旧输入 ID/string_array/bool oneof/原始日期列表/history、session/run/路径、模式/default/min/max/format/布局/策略/同步与返回/原生/callback 类型和值。新增十一项至 widget 参数模块 465 项；八类 coherent 负例各确认实际改动一帧，并同步 raw/message/元素投影，拒绝缺同步、返回旧类型、观察重复同步、callback 旧日期、错误模式、过期提交 ID、截短 surplus 请求、更换输出 ID。

当前二进制同一自持服务重放 date-single 十六轮（127 帧/48 Element）、date-bounds 十三轮（116/52）、date-range 十九轮（170/76），完整 Element 继续匹配冻结 SDK，结果保留在 target/date-mode-old-*/trace.json。当前 Python fixture 另重采旧 date-single 十六轮至 target/date-mode-sdk-old-single/trace.json，也与冻结 SDK 逐字段一致；既有原始参考和浏览器图不改。本批三份 producer、两份生产源文件及实际二进制 SHA 与新原生 capture metadata 匹配。所有自持服务 finally terminate/wait，58863/55169/8599 无监听。

格式、三个编辑 Rust 文件的逐文件 diff、全工作区/all-target Clippy、示例构建通过；既有 MSVC linker stdout warning 保留。公开单元两项、真实 pickers 集成两项通过；最初定向命令 server::tests::runtime::pickers 未命中（0 项），已改为 server::tests::pickers:: 并确认两项实际通过，日志分开保留。最终工作区 341 项通过（334 库、1 ledger、2 宏、4 rustdoc），仍仅排除 server::tests::navigation::navigation_pages_switch_and_session_state_match_the_measured_wire 与 server::tests::queryparams::rerun_queue_messages_match_frozen_reference，不称全绿。日志 target/date-mode-{red,green,shapes,sdk,clippy-final,build,pickers,pickers-corrected,workspace,gate,python,server,sdk-ws,date-mode-ws,date-single-ws,date-bounds-ws,date-range-ws,sdk-old-single,docs}.log。

矩阵只更新 st.date_input 的本批证据和 limitation，生成 inventory 仍 130 partial；指南追加显式边界模式切换语义并保留原 CRLF 字节前缀。本批无新浏览器采集；隐式边界跨模式、None/部分/多端点公开模型、前端错 oneof、禁用/ignore、query binding、表单/跨页及其他组合继续开放。用户 colconfig 及其他已有修改保留，无 PR、合并、发布或部署；M3/M5/M7 和完整 Goal 保持开放。
本批相关八模块 1561 项通过（widget 参数 465、temporal 参数 106），文档/配置/矩阵三模块 55 项通过；命令范围与上一批 1541 项一致，新增十一项原生门和九项 SDK 验证。

推送后来源审计补充：采集器工作区为 CRLF，Git 文本规范化提交为 LF，因此原始 producer_sources_sha256 与对应提交 blob 的 SHA 不同。保留全部原始文件字节 SHA 与原始帧，另在两端 date-mode metadata 增加 source_git_blob_commit=1d2f5c2、producer_git_blob_sha256，Rust 同时记录 rust_git_blob_sha256；逐文件验证仅 CRLF→LF 存在差异。生产源文件和二进制实际 SHA 仍与首次采集相符，不将规范化后的 SHA 冒称当时文件字节，不重采或覆盖帧。

## Current date implicit-bound mode retention validation (2026-11-01)

锁定 SDK 1.66.1 AppTest 证明：没有显式 min/max 时，有 key 的日期控件改变单值/范围声明仍保留旧原生值的实际类型，直到新输入按当前已登记模式解码。旧 Rust codec.valid 把原生类型绑在本轮声明模式，单值切换范围时报 value does not match date_input；返回转换也按本轮模式强制解析。现有 DateSelection::Single/Range 已能表达这两类值，本批无需新公共模型。

生产改动限现有两个位置：DateInput 的原生 valid 同时接受合法日期字符串或完整两项 ISO 日期数组；date_input 的公开结果转换按实际值是数组还是标量选择已有变体。前端 decode 仍按已登记 range 标志解码和检查全部日期/列表长度，wrong oneof、合法空/部分/多端点返回等未借此放宽。上一批显式边界的模式不匹配重置仍先于 valid，保持回本轮默认及 value/set_value/one-shot 一次同步的行为；本批隐式边界切换不产生同步或额外 callback。

复用公开 API 十二阶段单元，扩展为 both/minimum/maximum/implicit 四种策略。先真实红于 implicit 单值编辑后切换范围，日志 target/date-implicit-red.log 保留；修后四组共四十八阶段均通过。隐式 range 轮保留单值 4/20，single 轮保留范围 5/1..5/10；后续范围声明继续保留单值 6/1，切回单值继续保留范围 3/10..3/20。正常新输入分别产生完整范围或取第一日期的单值，十条 callback 读取整批日期/Peer，身份始终保留，观察无重复同步。

另公开 API 单元对声明单值/范围 × 原生单值/完整范围四组合验证代码赋值和观察：2050-02-01 或 2050-02-01..2051-03-01 超出推导的 2015..2035 窗口仍保留实际类型，返回/keyed state 相同，代码赋值按实际一项或两项同步一次，下一轮无输入保留且不重发。对应 SDK AppTest 新增隐式策略一项及原生赋值四项，原有三种显式策略继续通过，合计八项定向 SDK 验证。AppTest 内部 _run 使用实际 WidgetStates，观察传空 WidgetStates，不称正常浏览器操作。

[SDK](../tests/reference/reference-browser/widget-params/date-implicit/trace.json) 与 [Rust](../tests/browser/rust-widget-params/date-implicit/trace.json) 首次原生采集各十二轮、95 帧、36 完整 Element、十条有序 callback，同一连接/session、十二 run、两个稳定 ID。复用已有 date-mode 的十二步，新增 opt-in date-implicit 仅省略边界；min/max wire 按本轮声明默认推导，返回/原生状态可为上轮类型，所有日期同步标记均为空。完整 Element 仅规范化 opaque ID 和 JSON body 后逐字段一致，严格门通过后才设置 Rust semantic_match=true，首次成功参考未覆盖。

同一原始帧校验器参数化显式/隐式两种策略，重解析 base64/protobuf/bytes/message 与元素汇总，核对完整 message/status 次序、实际旧输入 ID/string_array/bool oneof/原始列表/history、session/run/path、模式/default/计算或显式边界/format/布局/策略/同步、所有返回/原生/十条有序 callback 的类型和值。参数模块增加十一项至 476。隐式八类 coherent 负例实际改动一帧并同时更新 raw/message/元素投影，拒绝错误重置同步、原生范围被改回单值默认、观察重复同步、旧日期 callback、错误模式、过期输入 ID、截短 surplus 请求、改变输出 ID；显式原有八类继续验证。

当前同一 Rust 二进制重放原 date-mode 十二轮（95 帧/36 Element）、date-single 十六轮（127/48）、date-bounds 十三轮（116/52）、date-range 十九轮（170/76），完整 Element 均继续匹配冻结 SDK；target/date-implicit-old-*/trace.json 保留。当前 Python fixture 的 date-mode 另重采到 target/date-implicit-sdk-old-mode/trace.json，与原冻结参考相同。没有覆盖旧参考或浏览器图，也不将这些原生结果当成真实 UI 证明。

三个 producer 文件、两个生产源文件的实际 SHA 与新捕获 metadata 逐一一致，当前这些源码使用 LF，提交前另检查 index/blob 口径，避免上一批 CRLF 文件字节与 Git 文本规范化 SHA 混淆；Rust 二进制 SHA 也已核对。source_commit=7ab18fe 是启动基线，未提交工作区的具体文件由所记 SHA 标识。SDK/Rust 自持服务均 finally terminate/wait，61149/55854/8599 无监听。

代码格式、三个编辑 Rust 文件逐文件 diff、全工作区/all-target Clippy、公开单元与真实 pickers 两项、示例构建通过；既有 MSVC linker stdout warning 保留。完整工作区 342 项通过（335 库、1 ledger、2 宏、4 rustdoc），仍仅排除 server::tests::navigation::navigation_pages_switch_and_session_state_match_the_measured_wire 与 server::tests::queryparams::rerun_queue_messages_match_frozen_reference，不称全绿。定向原生门显式/隐式共 22 项通过。日志 target/date-implicit-{red,green,native-unit,sdk-final,clippy-final,pickers,build,workspace,gate,python,server,sdk-ws,date-implicit-ws,date-mode-ws,date-single-ws,date-bounds-ws,date-range-ws,sdk-old-mode,docs}.log。

矩阵只补 st.date_input 本批证据和 limitation，生成 inventory 仍 130 partial；指南仅替换上一批尚未完成的隐式跨模式说明，其他原始字节保持。None/空/部分/多端点公开模型、任意原生类型、错 oneof、禁用/ignore、query binding、表单/跨页和更广组合继续开放，本批没有新浏览器采集。用户 colconfig 及其他已有修改保持，无 PR、合并、发布或部署；M3/M5/M7 与完整 Goal 保持开放。
本批相同八模块共 1577 项通过（widget 参数 476、temporal 参数 111），新增十一项原生策略门和五项 SDK 验证；文档/配置/矩阵三模块 55 项通过。

## Current date range actual Chrome failure evidence (2026-11-01)

正常范围日历操作暴露当前公共返回模型的直接影响：点击新的起点便提交单日期数组，SDK 立即返回并保存部分范围并执行 on_change，Rust codec 因范围只支持两项而使本轮输入未应用，后端继续保留旧完整范围且漏掉该次 callback。输入框由官方前端更新成新起点/空终点，造成可见字段和后端状态不一致。选择终点后 Rust 恢复完整范围提交和后续 Peer 回调，但历史中缺失的起点 callback 不会补回。本批只记录实证，不将已知差异标为修复。

使用 computer-use 技能及已绑定 Chrome 3，直接操作现有 widget_params 的 probe=date-range&phase=load 页面；没有改两端示例、采集器、生产源码或公共接口。两端各九阶段：load/calendar-open/calendar-next/start/dismiss/reopen/complete/peer/peer-restore。先展开三月并翻四月，点击 4/10，仅选择起点；Escape 关闭再重新打开日历，补选 4/20，然后 Peer true/false。所有浏览器输入经语义控件，不注入前端状态、协议包或脚本事件。

[SDK](../tests/reference/reference-browser/widget-params/date-range/ui/trace.json) 与 [Rust](../tests/browser/rust-widget-params/date-range/ui/trace.json) 各五次真实运行、45 个二进制 WS 帧、20 完整 Element，均由当前真实 tab 的 CDP 原始 events/pages 重解析。两端实际提交的 Single 是 3/15，Range 首次只含 4/10，Peer false；SDK 返回/native 为 [4/10] 且新增一条 range callback，Rust 返回/native 仍为 [3/15,3/20] 且没有 callback。部分范围在关闭/重开日历期间保留在前端，四个日历开关/翻月动作无 WS 请求。补齐终点后两端返回/native 都为 [4/10,4/20]，随后 Peer 正常切换；SDK 历史共四条 callback，Rust 只有完整范围和两个 Peer 的三条。

全部控件 Element 仅规范化 opaque ID 后逐字段一致，初始完整 JSON 也一致；从起点轮开始的真实报告差异完整保留，没有通过删除 callback 或只比较最终值制造全量匹配。SDK 严格参考行为门通过才设 successful/semantic_match=true；Rust 保留 collection_complete=true、successful=false、semantic_match=false 和明确 known_failure。相同参考行为门对 Rust 的实际 DOM/返回值失败，另按已知失败形状核查其完整原始证据；不只因 false 标记而失败，也不把测试能准确识别失败当成产品兼容通过。

十八张原始 JPEG 随每阶段直接保存并逐张查看，未重编码、裁切、拼接或生成。SDK DOM/截图为 1463x780，Rust DOM 为 1463x724；Rust 05-dismiss 原始截图实际宽 1462，其余 Rust 图片宽 1463，DPR 均 1.75，无 viewport override。截图宽度差异原样保留，不宣称完整屏幕像素或动画一致。截图 05-dismiss 清楚显示起点 4/10、终点占位，而 Rust JSON 仍为 3/15..3/20；SDK 同阶段 JSON 已为单端点。图片逐一校验原始 bytes/SHA/JPEG/真实尺寸，范围字段区域另拒绝把初始完整值图片重算哈希后当作部分范围。

严格门同时检查九阶段与五次运行分组、DOM 年月日分段/hidden date/checkbox/可见 JSON/日历月份/无异常，原始 CDP events/pages 投影和 cursor/sequence、实际 tab/requestId/单连接、protobuf 完整消息和 running 状态次序、三个稳定 ID 和实际 oneof/原始数组、query/history、zh/Asia-Shanghai/-480/dark/当前 origin context、同一 session 的五个 run 成功结束、全部路径和 widget default/min/max/is_range/format/width/策略/no-sync、返回/native/有序 callback。新增十一项至 widget 参数模块 487 项，其中八类 negative 保留 raw/events/pages 双份一致，拒绝错误部分 DOM、把单端点请求改成完整值、丢 callback、错误模式、额外同步、过期输入 ID、损坏截图 hash、重算 hash 的初始图复用。

源码、fixture、采集器三个 producer 和 widgets/widget_api 两份实际文件 SHA 均与 metadata 和当前 HEAD=18561a9 的 blob 匹配，实际 widget_params 二进制 SHA 也相同。Network 在关闭 owned tab 前禁用，不宣称捕获 close 帧；标签 1754832120/1754832123 均关闭。唯一 stop marker target/date-range-ui-stop-20261101 通知 coordinator 后，SDK/Rust 两个自持 Popen 在 finally terminate/wait，exec session 85135 正常退出，PID 72104/36484 已由句柄确认结束，52875/8599 无监听。日志 target/date-range-ui-{sdk,rust}-server.log 和 server-meta.json 保留。

本批没有 Rust 源码变更，不重复 Clippy、构建或完整 Cargo 测试；上批 342 项与导航/rerun 两项排除属于上批证据。定向完整 UI 门十一项通过；最初 -k date_range_ui 只选中九项，最终以 date_range_ui or date_range_actual_calendar 实测十一项，不以 deselected 当通过。日志 target/date-range-ui-{gate,gate-final,python,docs}.log。

仅 st.date_input 矩阵补真实 UI 参考与明确失败项，生成 inventory 仍 130 partial；指南追加当前正常交互局限并保留旧字节前缀。已结合实证再次请用户选择日期公共返回模型：1 推荐统一 Single(Option<NaiveDate>)/Range(Vec<NaiveDate>) 并迁移调用方；2 保留旧变体另增空/可变范围变体；3 保留旧 API 另增可空/可变范围 API。依用户 AGENTS.md 第 2 条，破坏性公开接口待明确选择后实施，不把推荐或等待当同意。用户已有修改保持，无 PR、合并、发布或部署；空/部分/多端点、其他日期 UI 和更广组合仍未完成，M3/M5/M7 与完整 Goal 保持开放。
本批相同八模块共 1588 项通过（widget 参数 487、temporal 参数 111），文档/配置/矩阵三模块 55 项通过；产品部分范围不兼容仍作为明确失败保留。

## Current disabled date callback exposure validation (2026-11-01)

在日期公共返回模型仍待选择时，检查已能表达的单日期/完整范围禁用策略。锁定 SDK 1.66.1 会先反序列化禁用日期的前端提交，供同批其他控件 callback 读取；日期自身 callback 按上轮 disabled 抑制，随后登记仍禁用的控件才恢复旧值并同步。旧 Rust 将所有禁用日期延迟到登记，Peer callback 因而读到旧值。本批修复这一时序，不改变公开接口、依赖或错误 oneof 策略。

widgets.rs 的 begin_widgets 在既有禁用分支前，仅对已登记且原先 disabled 的 DateInput、能通过现有 decode/valid 的值，设置 before_input 旧快照、记录和 keyed state 的解码新值，然后直接跳过自己的 callback 收集。沿用登记阶段恢复旧值/代码赋值优先机制；不再把已解码的包放回 pending，用新参数二次解码。其他 codec、不可表达的部分范围和错 oneof 路径保持。没有新增 registry 字段、生产文件、依赖或公共 API。

公开 API 十二阶段单元先真实红于 disabled-forged：Peer 读到 March 默认，而不是提交的单值 4/1 和范围 4/10..4/20；target/date-disabled-red.log 保留，修后全部通过。load 初始禁用；forged 只运行 Peer callback，读取提交值，登记后返回/default state 仍为旧 March 日期且两日期同步；observe 不重复。enabled-joint 同轮启用并接受 May 提交，仍按上轮禁用仅调用 Peer；enabled-edit 正常执行 single/range/peer 三回调。disabled-joint 在原启用状态下先让三回调读 July 提交，再恢复 June 旧值。disabled-invalid 在 callback 前回声明 March 默认，登记仍恢复 June；legacy 转为 ISO 供 Peer 读取。disabled-assign 的 Peer 先读 September 输入，应用随后代码赋 October 日期，覆盖旧值与提交并同步；观察不重复，启用保留，November 正常提交恢复三回调。

[SDK](../tests/reference/reference-browser/widget-params/date-disabled/trace.json) 与 [Rust](../tests/browser/rust-widget-params/date-disabled/trace.json) 首次原生捕获各十二轮、107 原始帧、48 完整 Element、十四条有序 callback，同一 session、十二个 run、三个稳定 ID。两个现有 widget_params 示例与采集器增加 opt-in date-disabled，旧分支保留；不把这些手工协议提交当成浏览器会发送禁用控件变化。完整 Element 只规范化 opaque ID 和 JSON body 后逐字段一致，严格门通过才设置 Rust semantic_match=true，首次捕获没有覆盖。

复用日期边界门并参数化新策略，重解析 raw base64/protobuf/bytes/message/元素汇总，检查完整 message/status 次序、旧 ID/oneof/原始 bad 或 legacy 数组/history、session/run/path、disabled/default/min/max/is_range/format/布局/策略/value/set_value/one-shot、返回/native 和全部 callback 类型和值。新增十一项至 widget 参数模块 498。八类 coherent 负例各确认实际改动一帧并同步 raw/message/元素，拒绝 Peer 读旧值、禁用提交直接成为返回值、禁用日期额外 callback、启用轮错误同步、禁用同轮 callback 读恢复后旧值、非法字符串未回默认、代码赋值被提交覆盖、过期 range 输入 ID。原 date-bounds callback 类型检查也补严格 bool/list/string，旧门仍通过。

同一当前 Rust 二进制重放旧 date-bounds 十三轮（116/52）、date-range 十九轮（170/76）、date-mode 十二轮（95/36）、date-implicit 十二轮（95/36）、date-single 十六轮（127/48），全部完整 Element 匹配冻结 SDK，target/date-disabled-old-*/trace.json 保留。当前 Python fixture 另重采旧十三轮边界到 target/date-disabled-sdk-old-bounds/trace.json，也与冻结 SDK 相同。旧参考及上一批已知范围日历失败的原始截图/帧不改，本批没有新浏览器采集，也未修复部分范围的丢 callback。

起初 SDK-only AppTest 调查记录在 target/date-disabled-sdk-probe.log，显示一些非迭代 oneof 或非字符串数组会在变化判断期报错并持续到恢复轮；字符串类还可能在登记序列化时报错，具体取决于值和原生访问。它不是本批已修复/已对齐的错误类型清单，也不是原生 WS 冻结证据。该路径仍须继续按用户已选方案 1 复现 Python 错误、已发生 callback 和恢复，不能因本批正确类型结果而忽略这些差异。None/空/部分/多端点公开模型仍待选择。

编辑 Rust 格式、三个 Rust 文件逐文件 diff、全工作区/all-target Clippy、公开单元、真实 pickers 两项和示例构建通过；既有 MSVC linker stdout warning 保留。完整工作区 343 项通过（336 库、1 ledger、2 宏、4 rustdoc），仍仅排除 server::tests::navigation::navigation_pages_switch_and_session_state_match_the_measured_wire 与 server::tests::queryparams::rerun_queue_messages_match_frozen_reference，不称全绿。新禁用与旧日期边界定向门共 22 项通过；相同八个 Python 模块共 1599 项通过，其中 temporal 111 项未增加。日志 target/date-disabled-{red,green,clippy-final,pickers,build,workspace,gate,python,sdk-ws,date-disabled-ws,date-bounds-ws,date-range-ws,date-mode-ws,date-implicit-ws,date-single-ws,sdk-old-bounds,server,docs}.log。

三个 producer 与 widgets/widget_api 源文件实际 SHA 和二进制 SHA 已与新捕获核对；source_commit=06e4ed3 为启动基线，具体工作区文件由 SHA 标识。SDK 采集服务与自持 Rust Popen 均 finally terminate/wait；50595/51312/8599 无监听。指南追加已测禁用回调时序并保留原字节前缀，矩阵只补 st.date_input 的本批证据与 limitation，生成 inventory 仍 130 partial。用户 colconfig 及其他已有修改保持，无 PR、合并、发布或部署；错误 oneof、空/部分/多端点、unkeyed/ignore、query binding、表单/跨页与更广组合仍开放，M3/M5/M7 和完整 Goal 保持开放。
文档/配置/矩阵三模块 55 项通过。提交前另核对原始捕获来源 SHA 与暂存 blob 一致，原指南字节前缀和全部受保护用户文件 SHA 保持。

## Current disabled date early type-error validation (2026-11-01)

按用户已选方案 1 继续禁用日期的错误路径：本批覆盖 bool/trigger（true/false）、int、double、非空 int_array/double_array 和非空 bytes='x'。SDK 1.66.1 会在变化判断期反序列化失败，尚未分派任何 callback，随后同一会话即使收到正确日期与 Peer=false，也会因原错误在状态压缩期再次失败。正常 Peer=true 的值已接收，但其 callback 不能提前执行。JSON、字符串和空容器有不同规则，仍单列未完成，不通过整批忽略或改变恢复策略接受差异。

生产仅 widgets.rs 既有禁用分支增加 DateInput 类型错误分类：非迭代标量报对应 bool/int/float not iterable，非空数字数组和 bytes 的首项报 strptime() argument 1 must be str, not int/float；写入已有 input_error，沿用 callback 清空、handler 提前呈现 TypeError、保留未见记录与后续输入被阻止的机制。没有新增字段、生产文件、依赖、公开 API 或消息队列策略。已有正常类型的 callback 可见值/登记恢复分支先运行，正常日期不受本分类影响。

Rust registry 单元九种 payload × 单值/范围 × 两种输入顺序共 36 组合，先真实红于 bool 输入仍收集 Peer callback（target/date-errors-red.log），修后通过。单元核对零 callback、具体错误文字、Peer=true 已接收；下一轮正确日期/Peer=false 仍零 callback、原错误不变、Peer 仍 true；新 SessionState 没有污染。对应 36 个锁定 SDK AppTest 实测相同结果，callback 自身只记入口标记，不读日期，避免把 callback 内部访问错误误当成未分派；使用内部 _run/原始 WidgetStates，不称普通浏览器输入。

[SDK](../tests/reference/reference-browser/widget-params/date-errors/trace.json) 与 [Rust](../tests/browser/rust-widget-params/date-errors/trace.json) 首次原生捕获各 36 独立 WS 会话、108 轮、720 原始帧、216 Element，其中 72 个预期 TypeError。复用现有日期示例的 disabled-load，采集器增加 opt-in date-errors：每例 load→malformed→recovery，先关闭上一 WS 再建立新连接，避免持续错误污染后面的类型。每个初始运行正常展示两个禁用日期、Peer 和空 callback 报告；错误轮和恢复轮只发异常，无应用控件/报告，框架仍发送 FINISHED_SUCCESSFULLY。两种顺序都验证，即使 Peer 包在错误包之前也不能分派 callback。

严格门从 raw base64 重解析 protobuf/bytes/message/元素投影，校验完整三轮消息和 running 状态顺序、每例同一 session/不同例 session 隔离、108 个 run、原 query/case/attempt/history、三个初始 ID/默认/范围/disabled/format/bounds/布局/no-sync、准确目标/oneof/顺序/payload（包括显式 false 和 bytes base64）、所有异常 TypeError/文字/位置/标志、恢复包正确但仍失败。SDK 原始栈全部非空、恢复栈包含 _compact_state；Rust 沿用框架空栈。初始控件/报告和异常除 stack_trace 外的完整字段均一致；Python 的实际栈未删，Rust 未伪造 Python 路径，比较时仅单列 stack_trace。Rust 标记 error_semantics_match=true、semantic_match=false，不宣称完整异常 Element/字节或错误 UI 全兼容。

新增十一项原生门至 widget 参数模块 509 项，其中八种 coherent 负例同步改写 raw/message/元素投影并确认一帧实际变更，拒绝错误文字、错误地恢复成功、错误轮呈现 callback 标记、异常位置错误、过期日期 ID、把错误 oneof 换成合法日期、跨例复用 session、将 false payload 改为 true。SDK 模块新增三十六项至 temporal 147；Rust metadata/输入次序与回调持续状态均有公开状态读值证明，不只比较异常数量。

同一当前二进制另重放原禁用日期正常输入十二轮，target/date-errors-old-disabled/trace.json 的 107 帧/48 完整 Element 仍逐字段匹配冻结 SDK；已知部分范围日历失败和既有参考/截图不改。本批无浏览器操作。所有新捕获的三个 producer、widgets/widget_api 源文件 SHA 与当前工作区一致，二进制 SHA 已核对；source_commit=ab4a4c9 是启动基线。采集器和自持 Popen 均 terminate/wait，52701/8599 无监听。

Rust 编辑文件逐段 diff、格式检查、全工作区/all-target Clippy 通过，既有 MSVC linker stdout warning 保留。widgets 单元 19 项、真实 pickers 两项通过；最终工作区 344 项通过（337 库、1 ledger、2 宏、4 rustdoc），仍仅排除 server::tests::navigation::navigation_pages_switch_and_session_state_match_the_measured_wire 与 server::tests::queryparams::rerun_queue_messages_match_frozen_reference，不称全绿。新错误门与旧正确禁用门共 22 项通过，相同八个 Python 模块共 1646 项通过。日志 target/date-errors-{red,green,sdk,widgets,pickers,clippy,build,sdk-ws,rust-ws,server,gate,workspace,python,old-disabled,old-disabled-server,docs}.log。

矩阵只补 st.date_input 的本批错误证据与 limitation，生成 inventory 仍 130 partial；指南追加已测错误类型与持续状态，并明确尚无完整 Rust 异常栈。JSON/字符串/空容器及其他 message 类型、多个坏控件混合、启用控件错误、None/空/部分/多端点公开模型、真实错误 UI、绑定/表单/跨页与其他组合继续开放。用户现有 colconfig 等修改保留，无 PR、合并、发布或部署；M3/M5/M7 与完整 Goal 保持开放。
文档/配置/矩阵三模块 55 项通过；提交前确认原指南字节前缀、受保护用户文件 SHA 和新捕获来源/index blob 口径一致。


## Current disabled date string error recovery validation (2026-11-01)

继续用户已选的 Python 错误/callback/恢复兼容方案，生产仅修改 widgets.rs：禁用日期的非空普通 string_value 逐字符解析失败后，先通过已有 empty_input/before_input 暴露声明默认给 Peer callback，再将原错误包留待日期登记时报 TypeError: bad argument type for built-in operation。复用原 registration_error/Stop 呈现与保留机制，没有新增字段、依赖、公开 API 或发送流程。正常 string_array/ID-only 和提前 persistent input_error 分支保持。恢复后保存默认，不复活错误前 October 原生值；重新启用接受新值但日期 callback 仍按上轮禁用策略抑制，下一次正常编辑恢复日期再 Peer 的回调顺序。

新增 Rust registry 单元覆盖单值/范围、bad/ISO/中文 emoji 三个非空字符串、两种输入顺序共十二组合，真实先红于原生值仍为 October 而非声明 March 默认，修后通过；十二个锁定 SDK AppTest 核对同伴 callback 的实际读值、错误文字和 recovery/enable/edit 的完整状态历史。普通字符串不能与 string_trigger_value 合并：SDK 后者首次 Peer 也看到默认，随后 trigger 清理将状态重置为 None，恢复时 fixture 回调访问 None 再失败；这依赖尚待选择的公开日期模型。本批不处理空串、trigger/None、JSON 或空容器。

[SDK](../tests/reference/reference-browser/widget-params/date-strings/trace.json) 与 [Rust](../tests/browser/rust-widget-params/date-strings/trace.json) 各保留十二个独立原生 WS 会话、60 轮、498 帧、210 完整 Element、十二个预期 TypeError。采集器新增 date-strings 选项，复用现有 date-disabled fixture/example，不改其源码。每例 seed(代码赋值 October)→malformed→recovery(只提交 Peer)→enable→edit。Single 错误时仅异常；Range 错误前已呈现 Single，不因后续异常撤销该元素。异常路径分别 [0,0]/[0,1]，全部脚本 finish=0。

十一项严格原生门核对 raw base64/长度/MessageToDict/Element 投影、完整帧和 running 顺序、query/case/attempt/history、每例同一 session/跨例隔离、60 个 run、输入目标/顺序/oneof/payload、稳定 ID、默认/边界/format/布局/disabled/value/set_value/one-shot、原生和返回值及全部 callback。八种 coherent 负例同步改 raw/message/元素投影并确认一帧实际变化，拒绝错误文案、恢复错误、Peer 读旧 October、Range 异常位置错、过期输入 ID、合法日期冒充错误字符串、跨例 session 泄漏和漏掉初始同步。

SDK 原始异常栈非空，Rust 框架仍空栈；只在语义比较时排除 exception.stack_trace，完整成功 Element 和其余异常字段匹配，不删除实际 Python 栈也不伪造 Rust 栈。Rust error_semantics_match=true、semantic_match=false，不宣称异常 Element/字节或真实错误 UI 完整兼容。本批无浏览器操作。

同一当前二进制重放早期错误 36 会话/108 轮/720 帧与旧正常禁用十二轮/107 帧：前者去栈后的语义和后者完整 Element 均匹配冻结 SDK。新捕获三个 producer、widgets/widget_api 实际 SHA 与二进制 SHA 均已核对；source_commit=8254d52 为启动基线，工作区内容由 SHA 标识。SDK 服务与自持 Rust Popen 均 terminate/wait，动态 SDK 端口及 8599 无监听。

编辑 Rust 格式和逐段 diff、全工作区/all-target Clippy、widgets 二十项、真实 pickers 两项及示例构建通过，既有 MSVC linker stdout warning 保留。工作区 345 项通过（338 库、1 ledger、2 宏、4 rustdoc），仍仅排除 server::tests::navigation::navigation_pages_switch_and_session_state_match_the_measured_wire 与 server::tests::queryparams::rerun_queue_messages_match_frozen_reference，不称全绿。日志 target/date-string-{red,green,sdk,clippy,clippy-final,widgets,pickers,build,sdk-ws,server,gate,workspace,python,docs}.log。

矩阵仅补 st.date_input 本批证据与 limitation，生成 inventory 仍 130 partial；指南只追加兼容边界，原字节前缀和受保护用户 colconfig 等文件 SHA 保持。空串、trigger/None、JSON/容器、空/部分/多端点公开返回模型、真实错误 UI、表单/绑定/跨页和其他组合继续开放；M3/M5/M7 与完整 Goal 未关闭。用户再次选定 rerun 仅丢弃未发 Delta、保留已发帧和 URL，已实现边界不变；config/toast 队列差异仍待独立决定。本批未创建 PR、合并、部署或发布。

相关八个 Python 模块共 1669 项通过，其中 widget 参数模块 520 项、temporal 159 项；文档/配置/矩阵三模块 55 项通过。提交前再次核对完整受保护用户文件 SHA、指南原字节前缀及两个新捕获的实际 producer/Rust 来源与暂存 blob 一致。


## Current disabled date JSON type-error validation (2026-11-01)

按已选 Python 错误/callback/恢复方案推进，生产仅在 widgets.rs 现有禁用 DateInput 分类中解码 json_value。布尔、整数/浮点标量分别报 not iterable；数组逐项检查，非字符串项按 int/float/bool/None/list/dict 报 strptime() TypeError。先出现无法解析的日期字符串时立即停止类型检查，符合 SDK 先捕获 ValueError 回默认、不继续检查后项的次序；边界检查仍在全体解析之后，不把越界项误当解析失败。复用现有 persistent input_error、callback 清空和 handler TypeError 流程，没有新增生产字段、依赖、公开 API 或队列规则。

十二种 JSON payload：true、false、7、1.5、[7]、[1.5]、[true]、[null]、[[]]、[{}]、["2025-04-10",7]、["2025-04-10",true]，各覆盖单值/完整范围和两种输入顺序，新增 48 个 SDK/registry 组合。注册单元真实先红于错误 JSON 仍收集 Peer callback，修后通过。锁定 SDK AppTest 的全部提前错误组合现 84 项通过：无 callback 入口，Peer=true 已接收；后续正确日期和 Peer=false 仍受原错误阻止，Peer 保持 true。另新增四种非法日期前缀控制，各含后续数字/布尔/对象/列表，16 个 SDK 用例与八个 Rust 分类组合验证不会误报提前 TypeError。此控制只证明分类边界，不宣称 Rust 成功 JSON 输入的完整临时值/恢复语义已实现。

[SDK](../tests/reference/reference-browser/widget-params/date-json-errors/trace.json) 和 [Rust](../tests/browser/rust-widget-params/date-json-errors/trace.json) 各首次冻结 48 独立 WS 会话、144 轮、960 原始帧、288 完整 Element，其中 96 个预期 TypeError。复用当前示例、Python fixture 及原错误三阶段 load→malformed→recovery；采集器只增加 date-json-errors 选项与十二个 payload。每例初始四个元素正常，之后两轮只显示异常，框架仍 finish=0；同伴包在错误包之前也不分派 callback。

复用严格原生校验器，旧非 JSON 36 例仍按原完整输入集合和数量验证，不因增加 JSON 变宽。新十一项门检查 raw base64/长度/message/元素投影、完整 running/消息次序、query/case/attempt/history、同例 session 保持/跨例隔离、144 个 run、稳定日期和 Peer ID、实际 JSON 字符串/oneof/目标/输入顺序、初始默认/边界/format/布局/disabled/no-sync、准确异常 TypeError/文案/[0,0] 路径/标志与失败恢复。八类 coherent 负例共用原实现，对两个 cohort 分别验证错误文案、错误地恢复成功、callback 标记、异常位置、过期输入 ID、错误 oneof、session 泄漏与 false→true。SDK 保留实际非空栈，恢复栈含 _compact_state；Rust 框架仍空栈，比较仅单列 exception.stack_trace，error_semantics_match=true、semantic_match=false，无完整错误 Element/字节或真实错误 UI 宣称。

同一当前二进制另重放普通字符串错误恢复 12 会话/60 轮/498 帧、旧提前错误 36 会话/108 轮/720 帧、正常禁用日期十二轮/107 帧。前两者去栈语义及后者完整 Element 均匹配冻结 SDK。三个 producer、widgets/widget_api 源码和实际示例二进制 SHA 核对通过；source_commit=67260f0 为启动基线，具体未提交工作区由 SHA 标识。SDK 59421 与 Rust 8599 服务均 terminate/wait，确认无监听。本批无浏览器操作，旧实际部分范围失败证据保持。

编辑 Rust 按语义留空并逐段 diff 复查，格式、全工作区/all-target Clippy、widgets 21 项、真实 pickers 两项、示例构建通过；既有 MSVC linker stdout warning 保留。完整工作区 346 项通过（339 库、1 ledger、2 宏、4 rustdoc），仍仅排除 server::tests::navigation::navigation_pages_switch_and_session_state_match_the_measured_wire 与 server::tests::queryparams::rerun_queue_messages_match_frozen_reference，不称完整全绿。新旧提前错误原生门共 19 项通过。日志 target/date-json-{red,green,sdk,sdk-prefix,widgets,pickers,clippy,build,sdk-ws,server,gate,workspace,python,docs}.log。

矩阵仅补 st.date_input 证据与边界，生成 inventory 仍 130 partial；指南只追加本批行为，原字节前缀及全部受保护用户文件 SHA 保持。成功 JSON 字符串/null/日期数组/对象及空容器状态、JSONDecodeError 异常类型/文案、任意精度整数、None/空/部分/多端点返回模型、真实错误 UI、多个坏控件和表单/URL/跨页等继续开放。没有把探针观察到的成功 JSON 行为误算实现；新生产分支不依赖用户 Cargo.toml 的 preserve_order 修改。M3/M5/M7 与完整 Goal 保持开放；无 PR、合并、部署或发布。

相关八个 Python 模块 1744 项通过（widget 参数模块 531 项、temporal 223 项），文档/配置/矩阵三模块 55 项通过。提交前核对全部受保护用户文件 SHA、指南原始字节前缀以及新捕获来源 SHA 与暂存 blob 一致。


## Current disabled date normal JSON validation (2026-11-01)

继续完整 Python 1.66.1 状态兼容，生产仅 widgets.rs 既有禁用 DateInput 分支增加可表示 JSON 输入归一化。复用 before_input：Peer callback 先读临时解码值，禁用登记恢复旧 October 原生值并只同步有提交的目标控件一次；观察轮不重复同步。本轮代码赋值和已有禁用/启用策略不改，未扩大到启用控件直接收到 JSON 的路径。

私有 decode_date_json 处理 JSON null→已登记声明默认、字符串按字符迭代→非法日期回默认、日期数组规范化 ISO/legacy/越界回默认与反向范围原序保留；先遇非法日期则忽略后续类型错误，前期 TypeError 分类保持。JSON 对象仅迭代键，现有 serde 访问器读取原始键顺序并去重，重复键保留首次位置，值由 IgnoredAny 消费；不依赖用户 Cargo.toml 尚未提交的 preserve_order，不改 manifest/依赖。三个既有日期解析位置复用同一私有 ISO/legacy helper；空/部分/多端点及 None 公开返回模型仍未扩展，没有新增公开接口、字段、生产文件或队列规则。

十二个 JSON payload 覆盖 null、两个字符串、非法字符串后接数字、有效/非法日期后接对象、ISO/legacy 完整数组、越界日期、反向范围、反序对象键、非法对象键及重复对象键；各组合单值/完整范围、两种输入顺序共 48 组合。Rust registry 单元真实先红于 null 时 Peer 仍看到 October 而非 March 默认（target/date-json-normal-red.log），修后通过并逐例验证 callback 数量、临时值、旧值恢复、sync/no-sync 与无登记错误。对应 48 个锁定 SDK AppTest 覆盖完整返回/native/callback 历史、目标同步、观察、重新启用和后续正常日期/Peer 编辑。

[SDK](../tests/reference/reference-browser/widget-params/date-json-normal/trace.json) 与 [Rust](../tests/browser/rust-widget-params/date-json-normal/trace.json) 各首次保留 48 独立原生 WS 会话、240 轮、2112 原始帧、960 完整 Element。采集器新增 date-json-normal，复用现有日期示例/fixture和五阶段 seed→submitted→observe→enable→edit；没有改示例或 Python 应用源码。每例 seed 为两个日期代码赋值 October；submitted 只提交目标 JSON 与 Peer=true，Peer 读到临时日期值但报告保存旧 October；observe 仅提交 Peer=false并读到旧值；enable 的 StringArray 提交生效且仍抑制日期 callback，下一次 edit 恢复日期再 Peer 回调。所有阶段四个正常 Element，finish=0，无异常或栈归一化。

复用原五阶段字符串错误校验器，但保留原十二例/错误字段/异常栈和错误恢复规则的严格分支。新增十一项原生门，校验 raw base64/长度/MessageToDict/元素投影、完整消息/running 顺序、query/case/attempt/history、同例 session/跨例隔离、240 个 run、准确 JSON 文本和对象键原序、目标/输入顺序/oneof/稳定 ID、默认/边界/format/布局/disabled/value/set_value/one-shot、临时 callback 值/旧保存值/全部有序回调。八类 coherent 负例扩展到两组独立运行，JSON 组拒绝保存值错误、观察期异常、Peer 读旧值、路径、过期输入 ID、合法数组冒充原 JSON、跨例 session 泄漏与初始同步缺失。新旧两组门共十九项通过。完整 Element 比较仅规范化不透明 ID 与 JSON 文本，Rust semantic_match=true，不宣称字节或真实浏览器 UI 兼容。

同一当前二进制另重放普通字符串错误恢复、早期 raw 错误、早期 JSON 错误和正常禁用日期四组，分别 60/108/144/12 轮，均匹配旧冻结 SDK 的完整或去栈错误语义；旧异常栈差异和实际部分范围 Chrome 失败证据保持。新捕获三个 producer、widgets/widget_api 和示例二进制 SHA 核对通过；source_commit=0960042 为启动基线，工作区由实际 SHA 标识。SDK 63383 与 Rust 8599 服务均 terminate/wait，确认无监听；本批无浏览器操作。

编辑 Rust 格式、逐段 diff、全工作区/all-target Clippy、widgets 22 项、真实 pickers 两项、示例构建通过，既有 MSVC linker stdout warning 保留。完整工作区 347 项通过（340 库、1 ledger、2 宏、4 rustdoc），仍仅排除 server::tests::navigation::navigation_pages_switch_and_session_state_match_the_measured_wire 与 server::tests::queryparams::rerun_queue_messages_match_frozen_reference，不称完整全绿。日志 target/date-json-normal-{red,sdk,widgets,clippy,pickers,build,sdk-ws,server,gate,workspace,python,docs}.log。

矩阵仅追加 st.date_input 本批证据及边界，生成 inventory 仍 130 partial；指南追加实测正常 JSON 行为，保留原字节前缀。空/部分/多端点和原生 None 公开模型、启用 JSON、JSONDecodeError、任意精度/特殊数字、多个坏控件、绑定/表单/跨页与真实错误 UI 等继续开放，M3/M5/M7 与完整 Goal 保持开放。用户 colconfig 等现有修改保留，无 PR、合并、部署或发布。

相关八个 Python 模块 1803 项通过（widget 参数模块 542 项、temporal 271 项）；文档/配置/矩阵三模块 55 项通过。提交前核对完整受保护用户文件 SHA、指南原始字节前缀和新捕获 producer/Rust 来源与暂存 blob 一致。


## Current enabled date input admission validation (2026-11-01)

按已选 Python 错误/callback/恢复完整兼容方案，本批生产仅 widgets.rs：将已有 DateInput 提前 TypeError 分类移为私有 codec 方法，在整批验证时允许这些已知错误进入输入处理；接收其他正常输入后保留 input_error，最后清空全部 callback。启用日期不再静默整批拒绝 bool/trigger、int/double、非空数字数组/bytes 与已测 JSON 类型错误，禁用分支复用同一机制；未知类型/其他 codec 仍沿用原规则，没有借此接受差异或扩大公共日期模型。

正常 JSON 的私有解码接入既有 decode_state，启用日期更新 keyed/native 值，所有输入先应用，再按变化和提交顺序执行日期及 Peer callback；登记保留新值、不额外同步，观察轮不回旧值。禁用日期继续使用 before_input 暴露临时值、登记恢复旧值并同步目标。十二个 JSON payload 的 null/字符串/ISO/legacy 数组/非法前缀/越界/反向/有序及重复对象键规则沿用上批实现，没有新增依赖、字段、生产文件、公开 API 或队列规则。

两条既有 Rust registry 序列扩为两种 prior-disabled 策略。提前错误共 21 payload×单值/范围×两种输入顺序×两种策略=168 组合；正常 JSON 共 12×2×2×2=96 组合。真实红分别为启用 bool 错包没有 input_error（target/date-enabled-errors-red.log）和 JSON 正常提交零 callback 而 SDK 有两个（target/date-enabled-normal-red.log）；修后 widgets 22 项通过。SDK 对应 264 个 AppTest 实测通过，提前错误 callback 从未进入、Peer=true 已接收、后续正确输入/Peer=false仍被原错误阻止；正常 JSON 的日期自身 callback 与 Peer 按提交顺序看到相同新值，登记/观察/后续编辑保留正确值，无额外 sync。

三组首次补充原生采集：[raw SDK](../tests/reference/reference-browser/widget-params/date-enabled-errors/trace.json)/[Rust](../tests/browser/rust-widget-params/date-enabled-errors/trace.json) 为 36 会话、144 轮、1044 帧、360 Element、72 TypeError；[JSON 错误 SDK](../tests/reference/reference-browser/widget-params/date-enabled-json-errors/trace.json)/[Rust](../tests/browser/rust-widget-params/date-enabled-json-errors/trace.json) 为 48 会话、192 轮、1392 帧、480 Element、96 TypeError；[正常 JSON SDK](../tests/reference/reference-browser/widget-params/date-enabled-json-normal/trace.json)/[Rust](../tests/browser/rust-widget-params/date-enabled-json-normal/trace.json) 为 48 会话、288 轮、2544 帧、1152 Element。每端合计 132 独立会话、624 轮、4980 帧、1992 Element、168 个预期异常。

采集器在现有错误/正常 JSON 模式增加 date-enabled 变体，每例初始运行后插入 enable-idle 无输入阶段，实际呈现两个 disabled=false 日期，再执行原提交/观察/恢复等阶段；不把“当前轮才启用”误当“上轮已经启用”。复用现有示例与 Python fixture，无应用源码改动。提前错误两轮只有 TypeError；正常 JSON 阶段保留完整四元素报告，总 callback 七条，含输入顺序相反时 Peer 先于日期的两条初次 callback；禁用原例仍五条。所有 finish=0。

严格校验器增加 enabled 分支但保留原禁用 cohort 的精确 case/数量/输入/错误/恢复约束。新增 33 项门，原有与新门共 65 项定向检查通过；校验 raw base64/长度/MessageToDict/元素投影、全部 running/消息顺序、query/attempt/case/history、同例 session/跨例隔离、run 唯一、实际 enable-idle 无输入及 enabled 控件字段、稳定 ID、oneof/原始 JSON/输入顺序/default/bounds/format/布局/策略/sync、所有返回/native/有序 callback 和错误 TypeError/文字/[0,0]/标志/持续性。两类既有 coherent 负例分别扩展到启用 cohort，拒绝错误文案/保存值、错误恢复、错误 callback、路径、过期 ID、oneof、session 泄漏和 false/初始同步破坏。正常 JSON 完整 Element 仅规范化不透明 ID/JSON 文本后匹配，semantic_match=true；错误仍保留 SDK 非空栈、Rust 空栈，只单列 stack_trace 做语义比较，error_semantics_match=true、semantic_match=false，不宣称完整错误 Element/字节或真实 UI 兼容。

同一当前二进制重放禁用 raw 提前错误、JSON 提前错误、正常 JSON、普通字符串错误恢复和正常禁用日期五组，分别 108/144/240/60/12 轮；全部匹配旧冻结 SDK 的完整正常 Element 或除栈外错误语义。新捕获三个 producer、widgets/widget_api 实际 SHA 与示例二进制 SHA 核对通过；source_commit=a4170a0 为启动基线，未提交工作区由 SHA 标识。SDK 51116/61880/60751 和 Rust 8599 服务均 terminate/wait，确认无监听。本批无浏览器操作，旧真实部分范围失败证据和截图保持。

Rust 编辑文件按语义留空、逐段 diff，格式、全工作区/all-target Clippy、widgets 22 项、真实 pickers 两项、示例构建通过，既有 MSVC linker stdout warning 保留。完整工作区仍 347 项通过（340 库、1 ledger、2 宏、4 rustdoc；扩展已有两项测试，不通过拆分参数提高计数），仍仅排除 server::tests::navigation::navigation_pages_switch_and_session_state_match_the_measured_wire 与 server::tests::queryparams::rerun_queue_messages_match_frozen_reference，不称完整全绿。日志 target/date-enabled-{errors-red,normal-red,sdk,widgets,clippy,pickers,build,server,gate,workspace,python,docs}.log。

矩阵仅补 st.date_input 本批证据与边界，生成 inventory 仍 130 partial；指南追加启用策略，不改原字节前缀。启用普通 string_value/string_trigger_value 的登记错误、JSONDecodeError 类型/文案、任意精度/特殊数字、None/空/部分/多端点返回模型、多坏控件混合、绑定/表单/跨页、真实错误 UI 及其他组合继续开放。用户 colconfig 等现有修改保持；M3/M5/M7 与完整 Goal 不关闭，无 PR、合并、部署或发布。

相关八个 Python 模块共 1968 项通过（widget 参数模块 575 项、temporal 403 项），文档/配置/矩阵三模块 55 项通过。提交前再次核对全部受保护用户文件 SHA、指南原始字节前缀及六份新捕获来源与暂存 blob 一致。


## Current enabled date string registration error validation (2026-11-01)

按已选 Python 错误/callback/恢复方案补齐非空普通 string_value 的启用日期路径，生产仅 widgets.rs。先用已登记 empty_input 将错误字符串归一化为声明默认；启用日期和 Peer callback 按输入顺序读取全部新值。正常输入分支将原字符串包保留在既有 pending，日期登记时复用原 registration_error/Stop 报 TypeError: bad argument type for built-in operation。禁用字符串改用相同 decode_state 默认逻辑，仍只分派同伴 callback。日期登记错误不再限于 prior-disabled，选择控件的原禁用规则不变；未新增字段、依赖、生产文件、公开 API 或发送队列策略。

原 registry 字符串序列扩为 prior-disabled 两种策略，共单值/完整范围×bad/ISO 文本/中文 emoji×两种输入顺序×两种策略=24 组合。真实先红于启用错误包零 callback，而 SDK 应有日期及 Peer 两个（target/date-enabled-string-red.log），修后通过。24 个锁定 SDK AppTest 实测错误前 callback 的完整读值/顺序、准确错误、恢复、后续两次正常编辑、稳定 ID 与 no-sync。恢复轮只提交 Peer=false，不注入日期来掩盖坏状态；无异常且保存声明默认，不复活原生 October。后续保持启用时两个日期编辑均执行日期再 Peer，累计七条 callback；原禁用序列仍五条。

首次[SDK](../tests/reference/reference-browser/widget-params/date-enabled-strings/trace.json) 与 [Rust](../tests/browser/rust-widget-params/date-enabled-strings/trace.json) 各十二独立 WS 会话、72 轮、606 原始帧、258 完整 Element、十二个预期 TypeError。复用现有 date-strings 采集模式及 date-enabled 变体，允许该已有变体驱动普通字符串；示例/fixture 均未改。六阶段 seed→enable-idle→malformed→recovery→enable→edit，每例先真实无输入启用两个日期，再提交原字符串/Peer；相反输入顺序时 Peer callback 先于日期。Single 错误只发异常 [0,0]，Range 错误保留先前 Single 控件并在 [0,1] 报错；后续轮四个正常元素，finish=0。

严格校验器为既有启用分支补齐普通字符串，原禁用及正常 JSON 分支精确约束保持。新增十一项至参数模块，原有和新定向门共 35 项通过；检查 raw base64/长度/message/元素投影、全部 running/消息次序、原始 query/case/attempt/history、同例 session/跨例隔离、72 个 run、真实 enable-idle 及 disabled=false、原 StringValue/目标/顺序/稳定 ID、default/bounds/format/布局/sync/one-shot、全部返回/native/有序 callback、准确 TypeError/文案/路径/标志及恢复。八类 coherent 负例同步改 raw/message/元素汇总，拒绝错文案、恢复期错误、callback 读旧值、路径、过期 ID、合法数组冒充字符串、session 泄漏和初始同步缺失。成功 Element 与除 exception.stack_trace 外的异常字段完整匹配；SDK 非空真实栈与 Rust 框架空栈均保留，error_semantics_match=true、semantic_match=false，不宣称完整错误 Element/字节或真实错误 UI 兼容。

同一当前二进制重放八组旧冻结 SDK：启用 raw/JSON 提前错误与正常 JSON，以及禁用 raw/JSON 提前错误、正常 JSON、普通字符串错误恢复、正常禁用日期，完整正常 Element 或除栈外错误语义均匹配。新捕获三个 producer、widgets/widget_api 实际 SHA 与示例二进制 SHA 一致；source_commit=0df6175 为启动基线，工作区由实际 SHA 标识。SDK 63423 与 Rust 8599 服务均 terminate/wait，确认无监听；本批无浏览器操作，旧部分范围 Chrome 失败证据保持。

Rust 按语义单元留空并逐段 diff 复查，格式、全工作区/all-target Clippy、widgets 22 项、真实 pickers 两项和最终示例构建通过；逐段复查补一处语义空行后重新构建，不重复无关测试。既有 MSVC linker stdout warning 保留。完整工作区仍 347 项通过（340 库、1 ledger、2 宏、4 rustdoc；扩展已有注册测试），仍仅排除 server::tests::navigation::navigation_pages_switch_and_session_state_match_the_measured_wire 与 server::tests::queryparams::rerun_queue_messages_match_frozen_reference，不称完整全绿。日志 target/date-enabled-string-{red,sdk,widgets,clippy,pickers,build,build-final,sdk-ws,server,gate,workspace,python,docs}.log。

矩阵仅追加 st.date_input 本批证据与边界，生成 inventory 仍 130 partial；指南追加启用字符串规则，保留原字节前缀。空字符串/string_trigger_value 的 None/空/部分/多端点返回模型、JSONDecodeError、任意精度/特殊数字、callback 内赋值/混合坏输入、绑定/表单/跨页和真实错误 UI 等仍开放，M3/M5/M7 与完整 Goal 不关闭。受保护用户 colconfig 等现有修改保持；无 PR、合并、部署或发布。

相关八个 Python 模块共 1991 项通过（widget 参数模块 586 项、temporal 415 项）。文档初检因矩阵措辞补充后漏重新生成 inventory 而失败一项，原日志 target/date-enabled-string-docs-initial.log 保留；重新生成后文档/配置/矩阵三模块 55 项通过。提交前核对全部受保护用户文件 SHA、指南原始字节前缀及新捕获来源与暂存 blob 一致。


## Current media HEAD and subtitle resource validation (2026-11-01)

从当前矩阵复核媒体正常请求缺口，而非继续只扩大日期错误输入切片。锁定 SDK 1.66.1 实测同一音频 URL 的 HEAD 返回 200、范围 HEAD 返回 206/416，原 Rust 均 404；进一步实测无扩展名 audio/x-wav GET 与 VTT 字幕 GET 也为 404。新增真实网络回归先失败于 audio HEAD: 404 != 200（target/media-http-red.log），修复后全部 48 请求通过。

生产仅 server.rs、media.rs 和 elements/media.rs：已有 /media 路由接受 GET/HEAD，响应 MIME 直接沿用已存媒体，修复无后缀音频、字幕和 HEAD；既有 Range/错误/附件处理复用，HEAD 由真实服务器发送时抑制正文并保留对应长度。新增仅 crate 内部可用的 named-media 存储，普通字幕保持非附件响应；字幕用已有 blake2b16(label)+.vtt 作为参与内容地址的文件名。SDK 的 en 文件名为 746709ed353fc6dedfc50665c7cf7098.vtt，43 字节 VTT 的完整 URL 为 /media/62f7893d6edeae028776bf39f25b93f2.vtt；原 Rust 漏文件名生成 cfc3c7c1ccd55d7da88a2f34d361b2cd，旧的“坐标/每运行时字幕 hash”归因不成立。Rust 公开接口、依赖、示例与 Python fixture 均未改。

复用 media_params_capture.py 加 opt-in http-head：从真实公开音视频发射的 protobuf 取得音频、裸地址音频、视频及字幕四个资源 URL，在 WS 保持期间逐一发起 GET/HEAD 的六组请求：完整、0-3、suffix -4、越界、带不匹配 If-Range、带 1970 日期 If-Range。原始 TCP 写 Connection: close，读取响应直到 EOF，不能只依赖 HTTP 客户端 HEAD.read() 的自动隐藏正文。两端首次捕获各 12 个原始 PB、六个音视频 Element 和 48 个原始 HTTP 响应，严格匹配 8×200、32×206、8×416；这两种 If-Range 在 SDK 中仍返回范围响应，不擅自改为 RFC 假设的整文件。

[SDK](../tests/reference/reference-browser/media-params/http/trace.json)、[当前 Rust](../tests/browser/rust-media-params/http/trace.json) 保留请求/响应完整 base64、长度、状态/头、原始正文、发射 URL/元素关系和采集清理。[修前 Rust](../tests/browser/rust-media-params/http-before/trace.json) 原样保留 36 个 404（全部 HEAD、裸音频 GET、字幕 GET）、实际错误字幕 URL及其余 GET 结果，参考策略检查拒绝它，而不是仅检查 semantic_match 标志。SDK 的 [cases.json](../tests/reference/reference-browser/media-params/http/cases.json) 仅派生原始响应和资源输入供 Rust 离线读取，Python 门逐项回查 raw，并用独立 wave 构造/固定视频/VTT 输入核对原始字节与内容地址。

新增 Rust 公开接口网络回归通过 audio/video 调用生成 URL，再发 48 个真实请求；复用同一 raw TCP helper 支持方法和头，其余已有 GET 回归机械迁移。采集和服务清理先完成再断言，真实 red 也不遗留监听。八个媒体单元、九个媒体运行集成测试通过，包含旧 27 个 Range/下载和特殊下载名、不可变大资源范围检查。Clippy --workspace --all-targets、编辑四个 Rust 文件格式与逐段 diff、示例构建通过，既有 MSVC linker stdout warning 保留；完整工作区 348 项通过（341 库、1 ledger、2 宏、4 rustdoc），仍仅排除 server::tests::navigation::navigation_pages_switch_and_session_state_match_the_measured_wire 与 server::tests::queryparams::rerun_queue_messages_match_frozen_reference，不称完整全绿。

媒体参数 Python 模块新增十三项，共十五项。严格门从 raw PB 反解析长度/message/六元素投影、版本/session/run/完成和 URL来源；从原始 HTTP 反解析请求方法、完整路径、Host/Range/If-Range、响应状态、全部语义头与正文，严格比较完整内容地址，不归一化字幕 URL。每个 HEAD 的实际线缆正文恰为空，仍断言其完整/范围/错误 Content-Length。八种 coherent 负例同步改写 raw 与投影，拒绝状态、泄漏 HEAD 正文、HEAD 长度、MIME、字幕地址、正文位翻转、错误 If-Range 行为及方法。旧媒体参数捕获更名注释为“历史字幕地址缺口”，保留原始失败数据。正常 HTTP 字段完整匹配，http_semantics_match=true；完整 wire semantic_match=false，autoplay 身份、已有非法字幕异常栈/错误 UI 不在本批比较内；未通过 URL 规范化假称完整字幕行为一致。

来源复核发现 Python fixture 为 CRLF，修前 elements/media.rs 也是 CRLF；原始采集 SHA 全部保留，新增各来源的 Git LF blob SHA，对修前文件从 source_commit=49b4c9a 精确重建 CRLF 后验证原始 SHA。当前三个 Rust 来源及最终二进制实际 SHA 与捕获一致，producer 的实际/Git 表示分别验证；source_commit 是启动基线，当前工作区由各 SHA 标识。SDK/修前/修后自有 Popen 均 terminate/wait，记录的 SDK 动态端口及 Rust 8593 无监听。本批无浏览器、播放/定位/字幕显示证据；fixture 视频仅 32 字节格式载荷，不能当成可播放视频验收。

相关七个 Python 模块共 961 项通过。日志 target/media-http-{before,red,green,unit,runtime,clippy,build-final,after,gate,workspace,python,docs}.log；早期只读探针 target/media-head-{sdk-probe.json,rust-before.json,subtitle-probe.json} 保留。矩阵仅补 st.audio/st.video 的本批证据和限制，inventory 仍 130 partial；一行从“未明确缺口”转为“未测参数”，是新增明确边界而非完成状态变化。指南追加已测 HTTP 规则并保留原字节前缀。完整浏览器播放/seek/字幕叠加、下载 HEAD、CORS/缓存验证器、其他 MIME/路径/头组合、更广字幕解析和资源生命周期仍开放；日期模型/JSONDecodeError 与其他原待决项不变，M3/M5/M7 与完整 Goal 不关闭。用户 colconfig 等现有修改保持，无 PR、合并、部署或发布。

文档/配置/矩阵三模块 55 项通过。提交前核对受保护用户文件 SHA、指南原字节前缀、实际源码 SHA 与 Git LF blob SHA 的对应关系；修前源文件按基线 commit 重建，修后源码与暂存 blob 及当前二进制匹配。


## Current subtitle text conversion validation (2026-11-01)

继续字幕正常工作流，发现原 SRT 私有转换器丢首个 cue 编号、将结束时间错误写为 .00:00:02，并额外追加末尾换行。锁定 SDK helper 加公开 st.video AppTest 的 22 个原始字符串用例，17 接受、5 拒绝；每例保存输入、完整内容字节/base64、错误文字或完整内容地址。AppTest 的 /mock/media 前缀与实际 /media 地址分别记录并校验相同摘要；首轮按真实路由断言 mock URL 的错误已纠正，未将 mock URL 当作网络捕获。

生产仅 elements/media.rs：原始字符串使用 Python 空白等价规则去首尾空白（包含 0x1c..0x1f），空/VTT 文本直接保存；SRT 原始文本沿用 SDK 前 33 字节 UTF-8 解码和首行编号/次行时间码检测，转换全局、不重叠的 ASCII 时间戳逗号，保留所有 cue 编号、caption、内部换行，不追加末尾换行。时间码和编号暂仍 ASCII 分类，没有引入 Unicode 数字表、依赖、公开接口、文件读取或其他隐含行为。

[SDK oracle](../tests/reference/reference-browser/media-more/subtitle-text/cases.json) 覆盖 VTT 普通/首尾空白/空串/全空白/header-only/prefix/CRLF/Unicode 控制空白，SRT 单/多 cue、caption 内时间码、重叠候选、三/四位编号、时间码前缀、编号尾空白、CRLF、UTF-8 截断/合法 Unicode caption 及不校验钟表范围。原始 SRT 字符串的 CRLF、过长编号或前缀截断拒绝与 SDK 一致，不将文件输入的处理规则混入原始字符串。Unicode 数字、文件/bytes/Path 等更广分类不在本批完成范围。

新增 Rust 精确字节/地址/拒绝单元，先真实 red：srt-one 实际为 WEBVTT 后直接接首时间码、坏结束时间和末尾换行，参考包含编号 1、正确毫秒和无额外换行（target/subtitle-text-red.log），修后 22 例全匹配；存储 MIME=text/vtt 且非附件，完整地址沿用上批标签摘要文件名。源码逐段 diff、格式、全工作区/all-target Clippy、八个媒体单元、九个媒体运行集成和两个示例构建通过，既有 MSVC linker stdout warning 保留。

独立真实网络捕获 [SDK](../tests/reference/reference-browser/media-more/subtitle-text/trace.json)/[当前 Rust](../tests/browser/rust-media-more/subtitle-text/trace.json) 各 14 原始 PB、六个既有视频/布局投影、一个实际字幕 GET；实际 49 字节正文、完整 URL、状态和全部语义头匹配，不归一化摘要。[修前 Rust](../tests/browser/rust-media-more/subtitle-before/trace.json) 保留 HTTP 200 但正文损坏的 45 字节、实际错误内容地址及同一链路，参考策略拒绝。旧 digest 归一化媒体/layout 捕获保留为历史未测内容缺口，不能再据此声称 SRT 字节等价。采集器只加 subtitle-http opt-in，示例和 Python fixture 均未改；远程 example.com 视频 URI 仅发射、不访问，视频格式载荷不是浏览器播放证据。

媒体/layout Python 模块从两项扩至 36 项：22 个 oracle 持续重放 SDK helper/public AppTest；两端原始 PB 重解析长度/message、session/run/version/完成及实际 [0,2] track 来源，绑定摘要/label/HTTP 内容、SHA、长度/MIME/非附件头；比较完整 VTT 和 URL。八类 coherent 负例对 cue 编号、结束时间、末尾换行、caption、MIME、状态、URL、label 做破坏；内容类重算 SHA、长度、文件地址并同步 raw PB/message/元素投影，仍被参考字节拒绝。subtitle_semantics_match=true、semantic_match=false：本批字幕字节/地址/HTTP 一致，布局、播放器、错误栈等没有据此变为全兼容。

当前二进制另重放上批 48 个媒体 GET/HEAD/Range/If-Range 请求，完整 HTTP 语义保持。新捕获来源实际 SHA 与 Git LF SHA 分别保留；修前 elements/media.rs 的 CRLF 从基线 c9c0efc 精确重建验证，当前三个库来源与最终二进制匹配；source_commit 是启动基线，当前工作区由 SHA 标识。SDK 62867 与 Rust 8597/8593 自有服务均 finally terminate/wait，确认无监听；本批无浏览器。

完整工作区 349 项通过（342 库、1 ledger、2 宏、4 rustdoc），仍仅排除 server::tests::navigation::navigation_pages_switch_and_session_state_match_the_measured_wire 与 server::tests::queryparams::rerun_queue_messages_match_frozen_reference，不称完整全绿。相关七个 Python 模块共 995 项通过。日志 target/subtitle-{sdk-oracle,http-sdk,before-build,before,text-red,text-green,media-unit,media-runtime,text-clippy,text-build,text-gate,text-workspace,text-python,text-docs}.log。

矩阵只追加 st.video 本批证据与限制，inventory 仍 130 partial；指南追加原始字幕字符串规则并保留原字节前缀。非 ASCII 数字、文件/字节/路径与更广输入错误、标签 repr、真实浏览器字幕呈现/选择/播放和资源生命周期等继续开放；日期模型/JSONDecodeError 等其他待决项不变，M3/M5/M7 与完整 Goal 保持开放。用户 colconfig 等已有修改保留，无 PR、合并、部署或发布。

文档/配置/矩阵三模块 55 项通过；提交前再次核对受保护用户文件 SHA、指南原字节前缀，以及 producer 实际/Git 来源、修前基线与修后源码/二进制 SHA 的对应关系。

## Current subtitle Unicode reference validation (2026-11-01)

在已有 subtitle-text/cases.json 追加独立 unicode_cases，原 22 个 cases 保持不变。锁定 SDK 1.66.1 / Python 3.14.7 / Unicode 16.0.0 的 helper 与公开 st.video AppTest 各复验 12 案，八项接受、四项拒绝，保留完整输入、转换字节、摘要 URL 或公开错误；AppTest 地址仍为 /mock/media，不冒充 HTTP 或浏览器证据。原始生成日志 target/subtitle-unicode-oracle.log。

参考将 cue 编号 str.isdigit 与时间码正则 \d 分开：阿拉伯数字和上标 ² 编号接受，分数/罗马数字编号拒绝；四字节数学数字编号因 33 字节前缀截断时间行而拒绝。首个时间码的阿拉伯/全角数字接受，上标拒绝。已识别 SRT 的后续阿拉伯/数学十进制时间码转换逗号，而上标和分数正文保持。Unicode 16.0.0 全 scalar 分类统计：isdigit 888 点、90 区间；isdecimal 760 点、71 区间。区间按紧凑 JSON 序列化的 SHA256 分别为 3891476f1c3608026cb9f4269344e1e09ded3dd40d150efc6d4cef4602f23178 与 813b0301dd8366f257ac91252999b0ed2d9034d032176113fcacadc3c2b7f87c；尚未将分类表接入 Rust。

临时把这 12 案加入现有 Rust 私有字幕测试并去掉 22 案计数断言，实际 cargo test --offline --locked -p streamlit --lib subtitle_strings_match_frozen_sdk_bytes_addresses_and_rejections 退出 101：首个 counter-arabic 被 Rust 拒绝，SDK 接受。日志 target/subtitle-unicode-rust-red.log 保留。初次 --exact 短名过滤命中零项，不计作验证；随后去掉 --exact 确实执行一项并失败。临时源码由 finally 按原始字节恢复，生产实现不变；未把新 Unicode 用例接入默认 Rust 门掩盖或改写既有 22 案结果。

现有 Python 媒体模块扩至 48 项并全部通过（target/subtitle-unicode-python.log）；它证明冻结参考可重放，不代表 Rust Unicode 已修复。完整 Unicode 分类来源涉及数据/依赖选择，方案记录在 architecture，待用户决定；其他已授权工作可继续。未重跑与本参考增补无关的全工作区/真实浏览器，130 partial、M3/M5/M7 与完整目标保持开放。

提交前恢复后的原 22 案 Rust 字节/地址/拒绝回归一项通过（target/subtitle-unicode-existing-rust.log）；文档/配置/矩阵 55 项通过（target/subtitle-unicode-docs.log）。逐文件 diff 复查和 git diff --check 通过，原 oracle 全部既有字段保持；九个受保护用户文件与本批快照 SHA 一致，生产 media.rs 无 diff。本批仅提交参考、重放测试及计划/方案/验收记录。

## Current subtitle label error quoting validation (2026-11-01)

在已有 subtitle-text/cases.json 增补 label_cases 十二项：空/普通标签、单引号、双引号、两类引号、反斜杠、换行、Tab/CR、NUL/全部 ASCII 控制字符、可打印中文和 emoji。每案从锁定 SDK 1.66.1 的公开 st.video AppTest 记录真实异常类型和完整文字，均无 video；不将 AppTest 当作浏览器或 SDK 网络捕获。原 22 个文本案和 12 个待决 Unicode 数字案保持，日志 target/subtitle-label-sdk.log。Python 重放现已使用冻结 label，而非硬编码 en。

修前新增 Rust helper 单元和真实公共 API WebSocket 两项均执行并失败在 label-apostrophe：原输出 'O'Brien'，参考要求双引号定界。target/subtitle-label-red.log 保留真实 red。修复将原 status.rs 的 width_error_value 按职责移到既有 utils/mod.rs，改名为私有 python_error_value，算法未变；api.rs 的状态宽度和 media.rs 的字幕标签复用同一逻辑，不复制字符串转义实现。无新增文件、依赖、公共接口或运行时 Python。Unicode 非打印字符的数据方案未接入；不把该局部修复称作完整 Python repr。

修后两项均通过（target/subtitle-label-green.log）。公共 WS 回归在本机临时端口启动一 worker、逐个以公开 VideoOptions.subtitle 发射十二个错误、解析完整 Exception type/message/Markdown 标记并确认无 video；先关闭连接和自有服务器、等待任务退出再断言。Rust 本来将错误渲染为元素，SDK AppTest 每案独立抛错，不能据本测试声称脚本错误中止/恢复或 stack/UI 完整兼容。

相关 Python 媒体模块 60 项通过（target/subtitle-label-python.log），状态 width_repr 七项通过（target/subtitle-label-width-python.log）。workspace/all-targets Clippy -D warnings 通过，保留原有 MSVC linker_messages 告警（target/subtitle-label-clippy.log）。Rust 按 max_width=256 格式化并逐文件复查语义空行/diff。

检查 SDK 源码时另发现当前 Rust native URL 分支提前返回，忽略字幕验证/附加；这是独立已知差异，本轮未改该流程，也未请求/访问远程视频。Unicode 数字分类方案和 rerun 非 Delta 消息策略仍待独立决定；完整目标、M3/M5/M7 保持开放。

最终工作区回归 351 项通过（344 库、1 ledger、2 宏、4 rustdoc），仍仅排除 server::tests::navigation::navigation_pages_switch_and_session_state_match_the_measured_wire 与 server::tests::queryparams::rerun_queue_messages_match_frozen_reference；日志 target/subtitle-label-workspace.log，不称完整全绿。文档/配置/矩阵三模块 55 项及媒体契约 25 项共 80 项通过（target/subtitle-label-docs.log），inventory 再生成后仍 130 partial。Python 参考重放额外核对 SDK Exception 的 Markdown/Streamlit 标记。

提交前逐文件 diff 与 git diff --check 通过；移动后的 helper 函数体与 HEAD 原函数体仅名称改变，原始 oracle 的全部既有字段保持，九个受保护用户文件与本批 SHA 快照一致。本批没有新文件、真实浏览器操作或远程视频获取，真实 WS 自有服务器已停止；未创建 PR、合并、发布或部署。

## Current native URL subtitle attachment validation (2026-11-01)

修复 be49d6c 中实际发现的 native URL 分支提前返回：api.rs 的 video 函数先复用字幕校验/注册，再选择原 URL 或字节媒体地址，最后统一附加 tracks/播放参数。原 URL（含 query/fragment）原样传递，URL 视频不上传字节；无新文件、接口、依赖或远程获取。生产只改该函数，语义单元编号/空行逐段复查。YouTube 类型/重写/字幕拒绝未在本批实现，不声称所有 URL 来源兼容。

既有字幕 cases.json 追加 url_cases 八案，锁定 SDK 1.66.1 公开 st.video AppTest 实际生成五个完整 Video 和三个错误：无字幕、VTT、SRT、空首轨加多轨、引号/中文标签，以及首轨/后续轨/引号标签的非法字幕。输入使用 https://example.invalid/clip.mp4?take=2#chapter、start=1.5/end=4.8/loop/muted；只发射 URL，从不获取远程视频。保留原 AppTest 完整 protobuf/Base64/字段，与显式转换 mock 前缀后的 canonical protobuf/字节数组；字幕存储原标签、SDK helper 正文/SHA/完整内容地址，不归一化摘要。此前 22 文本、12 Unicode 数字、12 标签错误案全部既有字段保持。生成日志 target/subtitle-url-sdk.log。

真实公共 API WS 回归先 red：url-vtt 缺少参考的 en 字幕轨（target/subtitle-url-red.log）。新增测试最初误用非直接依赖 Base64 和 HTTP helper 返回类型而编译失败，已改用冻结字节数组和现有 header Vec，不将编译错误算产品 red。编辑脚本曾定位到 trait 声明，断言阻止写入；后精确定位实现。未改源码的首次 Clippy 不计修后检查，最终日志已刷新。

修后先字幕单元两项通过（target/subtitle-url-unit.log），再媒体真实网络集成十一项通过（target/subtitle-url-green.log）。新测试逐项比较完整 canonical Video（URL、截断秒数、loop/muted、宽度和轨道顺序）或 Exception type/message/Markdown 标记；从真实 WS track URL 请求七次本机 GET，核对完整正文、200、VTT MIME、长度及无附件头，包含空首轨。十五秒超时；成功/失败均先关闭 socket、停止自有服务并等待退出再比对。SDK 新组合只有 AppTest/helper 参考，没有新 SDK HTTP 或浏览器捕获，不扩大为播放器显示/播放证据。

相关 Python 三模块 108 项通过（68 media-more、15 media-params、25 media-contract，target/subtitle-url-python.log）；八项新增重放完整 SDK protobuf、所有轨道 bytes/SHA/地址和错误标记。workspace/all-targets Clippy -D warnings 通过，保留既有 MSVC linker_messages 告警（target/subtitle-url-clippy.log）。Unicode 分类数据、完整 repr 字符表和 rerun 非 Delta 待决规则未实施；完整目标保持开放。

最终工作区 352 项通过（345 库、1 ledger、2 宏、4 rustdoc），仍仅排除 server::tests::navigation::navigation_pages_switch_and_session_state_match_the_measured_wire 与 server::tests::queryparams::rerun_queue_messages_match_frozen_reference；target/subtitle-url-workspace.log 保留，不称完整全绿。文档/配置/矩阵 55 项通过（target/subtitle-url-docs.log）；生成 inventory 仍 130 partial，M3/M5/M7 和完整目标未关闭。

提交前逐文件 diff 与 git diff --check 通过；原 oracle 字段和九个受保护用户文件 SHA 保持。仅暂存本批九个已存在文件，不纳入用户 colconfig、Cargo 或指南/README 修改；未创建 PR、合并、发布、部署或使用浏览器。

## Current numeric media time validation (2026-11-01)

SDK 源码及公开 AppTest 实测显示音频允许负开始时间和倒置区间，视频才拒绝；两者先把时间截断到整数。Rust 原先对 NaN/无穷/超界静默使用 as 饱和转换，没有 SDK 错误。现有 media.rs Playback 增加私有 time_error，api.rs audio/video 在媒体注册/字幕处理前调用：start 非有限转换→end 非有限转换→向零截断→视频区间→start/end int32 范围，保留音频的真实参考行为。NaN start 为 StreamlitAPIException，NaN end 为 ValueError，无穷为 OverflowError，字段超界为 ValueError；对应 Markdown/Streamlit 标记也匹配，不把所有错误改为单一 API 类型。

既有 media-params/trace.json 只追加独立 playback_time_cases/scope，原 WS capture 全部既有字段/raw PB 保持。锁定 SDK 1.66.1 公开 AppTest 共 52 案，14 接受、38 报错；覆盖默认、负数/负小数、普通小数、同秒/倒置/end=0、int32 上下界/超界、NaN/正负无穷、1e100/最大 f64 和混合错误优先级。非有限输入用字符串 token 标识，重放时转换为 float，不声称支持字符串时间 API。保留完整原 AppTest mock protobuf、canonical 原字节地址 protobuf、或实际错误类型/完整文字/标记；普通构建和运行不需要 Python。生成日志 target/media-time-sdk.log。原 trace 使用 CRLF 且 Git 不归一化，新增 oracle 块以 LF 保存，修复 diff check 的 CR 空白告警；旧帧/字段未改。

新增公共 WS 回归先 red，在 audio-overflow-start 收到播放器而非错误（target/media-time-red.log）；修后三个媒体单元先通过（target/media-time-unit.log），再十二项真实媒体集成通过（target/media-time-green.log）。新测试用公开 AudioOptions/VideoOptions 发出 52 个调用，逐项比较全部 Audio/Video protobuf（地址只显式移除 SDK mock 前缀，不归一化内容摘要），或 Exception type/message/Markdown/Streamlit 标记。测试结束/失败均先关闭 socket、自有服务并等待退出，再断言。最大 f64 的完整十进制整数错误文字也匹配，未用 i32 饱和值伪造。

SDK 参考重放 media-params 模块 67 项通过（target/media-time-python.log），新增 52 项每次实际调用公开 AppTest，不只验证冻结 JSON。workspace/all-targets Clippy -D warnings 通过，保留原有 MSVC linker_messages 告警（target/media-time-clippy.log）。生产只改 api.rs 和 elements/media.rs，按语义单元留空并逐文件 diff 复查；无新文件、依赖、公共接口、重启或外部写操作。

SDK 每个 AppTest 独立报错，Rust 沿用已有错误元素模式，因此不能据一次 WS 批次称整个脚本的抛错/中止/恢复兼容；SDK/native stack/调用位置、显式 None/字符串/timedelta API、浏览器播放/定位和媒体生命周期继续开放。未实施待决 Unicode/repr 数据或 rerun 扩展规则，M3/M5/M7 和完整目标保持开放。

最终工作区 353 项通过（346 库、1 ledger、2 宏、4 rustdoc），仍仅排除 server::tests::navigation::navigation_pages_switch_and_session_state_match_the_measured_wire 与 server::tests::queryparams::rerun_queue_messages_match_frozen_reference；日志 target/media-time-workspace.log，不称完整全绿。六个相关 Python/文档模块共 215 项通过（target/media-time-gates.log），包含 67 media-params、68 media-more、25 media-contract、55 文档/配置/矩阵。生成 inventory 仍 130 partial。

最终逐文件 diff、git diff --check 通过，九个受保护用户文件 SHA 与本批快照一致，旧参考对象所有字段/raw PB 保持；仅暂存本批十个已存在文件，不纳入用户 Cargo、colconfig、指南/README 修改。无浏览器、PR、合并、发布或部署。

## Current real video playback UI validation (2026-11-01)

本批从协议/HTTP 推进到实际浏览器播放，不改生产代码和既有 fixture。当前 8e37530 的 video example 以 offline/locked 重建成功（target/video-playback-build.log），与 SDK 1.66.1 / Python 3.14.7 的 video_app 使用同一真实 MP4：SHA256 dcda48c8cec73a32406a184d635c41a324107f0f51a0cb0fe1124cc0791a19a6、一秒、64x48。本机 Chrome 两个新任务标签，常规 viewport 1463x780/DPR1.75，无覆盖设置；生产/fixture/source/exe SHA 与启动基线分别记录，目标二进制不提交。用户原有标签未操作。

使用 computer-use 技能和 cua_repl：只读 DOM 观察，实际 video 焦点 Space 播放/暂停/恢复，按最新截图里的真实进度条中点点击定位；没有 evaluate/CDP 写 DOM 或设置媒体属性，也未调用程序化 play/pause/seek。两端各七阶段 loaded/play-command/paused/pause-held/resumed/ended/seek-middle，四张未经编辑的原始 JPEG（加载/暂停/末帧/中点）及 trace 分别保存到 tests/reference/reference-browser/video/playback-ui 与 tests/browser/rust-video/playback-ui。所有原始图均实际查看：动态测试图案在播放末帧/定位后变化。没有新 WS/HTTP 捕获，不能冒充逐帧协议新证据。

SDK 播放 0.0298、暂停 0.0527、约 38.768 秒后保持同值、恢复 0.0773、自然结束 1.0；Rust 对应 0.0335/0.0654、约 13.984 秒后同值、恢复 0.1815、结束 1.0。均 paused/ended 状态正确、played 范围达 0..1，之后暂停定位到 0.499134、ended=false，readyState=4、error=null。实际调度时间不同，完整保留，不强改为相等。两个来源完整 media 地址一致（端口除外）。quality/networkState/navigator 不在只读范围中暴露，Browser.getVersion 不受支持；这些辅助读取失败没有改页面，不推断浏览器版本/解码计数，也不把它们列为已验证。

两任务标签已显式关闭，自有服务 proc.terminate 后 wait。SDK 即时端口检查仍可连接（port_closed=false）如实保留；再次核查无 listener，最终两端 connect_ex=10061（连接拒绝），单独记录 port_closed_final/time，未覆写第一次结果。Windows terminate 的退出码 1 来自采集器主动停止，不冒充应用崩溃或自然退出。84041 自有父任务最终退出 0，metadata 在 target/video-playback-ui-meta.json；无残留服务。

既有 test_video_contract.py 增补 27 项真实记录回放/损坏门，合计 48 项通过（target/video-playback-gates.log）。检查阶段完整顺序、真实开始进展、暂停跨一秒保持、恢复/结束/played 范围、真实中点、来源完整地址/分辨率/时长/flags、坐标依据、原 JPEG 完整解码/尺寸/字节 SHA、实际最终关闭；十二种损坏各作用于两端：仍加载、未播放、零时间、暂停漂移、未结束、不完整 played、定位无效、媒体错误、错误源、未清理、缺图、图 SHA 错。不是用 HTTP 200 或静态 DOM 判定成功，也不将生产源码指纹设为功能兼容门。

字幕呈现/选择、非默认 start/end/autoplay/loop/muted 参数、音频、其他视频/编码/时长/设备/浏览器、全屏和完整资源生命周期/长稳态仍开放。仅新增本批证据和相关检查/计划/矩阵，不关闭 st.video 行或 M3/M5/M7；完整目标继续。

最终视频/文档/配置/矩阵四模块 103 项通过（48 视频、55 文档，target/video-playback-final-gates.log）；最终回放逻辑不以临时 browser id 作为兼容门，视频模块复验 48 项通过。生产未变，未无故重跑全 Cargo；当前 example 实际离线构建与浏览器交互已完成。矩阵仅追加 st.video 证据/边界，inventory 仍 130 partial，完整目标未关闭。

提交前逐文件 diff/git diff --check 通过；九个受保护用户文件、全部捕获源码/fixture/sample/exe SHA 与启动快照一致，生产和 fixture 无 diff。仅暂存六个既有测试/计划/矩阵文件及十个本批原始证据文件（两 trace、八 JPEG），不纳入用户 Cargo、colconfig 或指南/README 修改；未创建 PR、合并、发布或部署。

## Current real subtitle UI validation (2026-11-01)

只在既有 streamlit/examples/video.rs 与 tests/reference/video_app.py 增加 ?subtitles=1 测试分支：同一真实一秒/64x48 MP4、English SRT（Hello SRT）和中文 VTT（中文字幕），请求 muted/loop；无开关仍保留原默认调用。库、公共 API、依赖和用户 colconfig/Cargo/指南/README 均未改。先离线锁定构建 example 成功，再 SDK AppTest 核对默认/双轨完整 Video，最后实际 Chrome 原生菜单交互；日志 target/video-subtitle-build.log、video-subtitle-sdk-apptest.log。

SDK/Rust 各六阶段：english-default、track-menu、chinese-selected、off-menu、captions-off、default-restored；各六张原始 JPEG 与独立 trace 保存至 tests/reference/reference-browser/video/subtitle-ui 和 tests/browser/rust-video/subtitle-ui。全部原图均实际检查，首轨显示 Hello SRT，原生字幕菜单 English 有勾；点击中文后显示 中文字幕，菜单中文有勾；点击已关闭后不显示字幕；移除 query 后无 track 且 muted=false。全程暂停于 t=0，readyState=4/error=null，不能据此声称运动中的 cue 定时/切换已验证。

使用现有 computer-use/cua_repl，只读 DOM 和实际原生菜单指针动作；未改 DOM/TextTrack 或进入“字幕设置”系统页面。mode/activeCues 不在只读代理中暴露，保留 null 并明确其仅表示观测限制，不等同关闭字幕。原生菜单 AX 的三个选项值分别为 0/1/0（English）与 0/0/1（中文），配合原截图确认选择。原图 RGB 字节区域 [650,510,805,556]（相同常规 viewport 1463x780/DPR1.75）在两端六阶段逐字节一致，且英文/中文/关闭三个区域摘要不同；区域只读分析，不生成/编辑裁图，不做 OCR。英文/中文含义由人工查看原图确认，自动回放只检验原图/区域和状态证据，不能冒充通用字幕文字识别。

从每端真实 DOM track.src 在字幕分支仍存活时实际 GET 两个字幕，共四次；均为 200，Content-Type=text/vtt; charset=utf-8、正确长度且非附件，英文完整 49 字节、中文完整 50 字节和内容地址一致。地址由 SDK 标签摘要文件名及实际正文重算，JSON 保留下载原文/Base64/SHA/头及公开 AppTest mock 地址；不归一化内容摘要。默认场景也在两端浏览器实际导航恢复，不只靠分支源码推断。两标签关闭后自有服务 terminate/wait，SDK 首次端口检查仍连接成功、第二次 10061，Rust 首次 10061；全部关闭过程原样保存，62102 父任务退出 0。

既有 test_video_contract.py 增加 27 项，视频模块合计 75 项通过（target/video-subtitle-gates.log）：两端回放、原图区域跨端对照、两个 SDK fixture 模式实际重放、十一种损坏各两端（缺轨、默认轨错、菜单状态错、源错、正文错、404、MIME、默认残留轨、区域 SHA、缺图、未清理）。检查原 JPEG 解码/尺寸/字节 SHA、轨道顺序/default/kind、实际字幕地址/HTTP 原文、菜单值、区域变化及恢复默认；不是只检查 HTTP 200。

example Clippy -D warnings 通过（target/video-subtitle-clippy.log），保留既有 MSVC linker_messages 告警。实际源码/fixture/exe SHA 与启动快照保持；source_commit=9ee1a21 为启动基线，producer_worktree_changes 明确两份新增分支文件，另存 Git LF SHA，避免将未提交 fixture 当成原 HEAD 内容。库未改，无故重跑全 Cargo 无收益；旧默认播放证据不重写，新增默认恢复/AppTest 证明当前分支仍适用。

请求 loop=true 但两端 DOM loop 属性均 false，本批没有实际播放循环验证，不从属性推断实现原因或兼容结论。运动 cue、更多格式/输入/样式/动态更新、全屏、其他浏览器/设备、完整资源生命周期和待决 Unicode/repr 等继续开放；st.video、M3/M5/M7 和完整 Goal 不关闭。

最终视频/文档/配置/矩阵四模块 130 项通过（75 视频、55 文档，target/video-subtitle-final-gates.log），inventory 仍 130 partial。逐文件 diff 与 git diff --check 通过，九个用户保护文件及捕获 source/exe SHA 与启动快照一致；production library 无 diff。当前两份测试示例已实际编译/SDK AppTest 与浏览器验证，未无故扩大重跑全 Cargo。

仅暂存本批八个既有示例/测试/计划/矩阵文件及十四个新原始证据文件（十二 JPEG、两 trace），不纳入用户 Cargo、colconfig、指南/README 改动。两标签和自有服务已清理，无 PR、合并、部署或发布，完整 Goal 保持开放。

## Current timed caption and loop UI validation (2026-11-01)

现有 video.rs/video_app.py 增加仅测试的 ?subtitles=timed，沿用真实一秒 MP4、muted/loop 和中文对照轨；英文 SRT 改为 0..0.4 的 First cue、0.6..0.9 的 Second cue，保留中间与末尾空档。原默认/双语模式不变。先 offline/locked 构建，再 SDK 1.66.1 AppTest 核对三模式与转换后 93 字节 VTT；example Clippy -D warnings 通过，保留既有 MSVC linker_messages 告警。日志 target/video-timed-build.log、video-timed-sdk-apptest.log、video-timed-clippy.log。库、公开 API、依赖未改。

真实 Chrome 原生进度条在两端均定位至 0.194588、0.499134、0.753679、0.956709，暂停图像依次为 First cue、无字幕、Second cue、无字幕；每个相同时间点的字幕 RGB 区域跨端一致。完整原图不编辑，区域只读 RGB 分析、不做 OCR；文字由实际查看原图确认。不同时间的背景图像会变化，不能把两处空档强制为相同像素。SDK 原始样本有 780/724 高度变化，Rust 为 724，高度/尺寸分别保留；字幕区域同坐标可直接比较，未覆盖视口或归一化原图。

SDK 首次尾部 Space 后记录 paused/ended=true，后来又读到播放状态；两个时刻均保留，不据早期读数判最终停止或推断原因。原任务标签失效后，清单确认它不存在，仅创建新 SDK 标签，未重启服务。新标签首帧明确启动与后续观察相隔 224.676 秒，Rust 对应为 80.512 秒；观察时两端均 paused=false/ended=false/currentTime 在一秒片长内部、played 覆盖 0..1。之后真实暂停/保持：SDK t=0.7817 显示 Second cue，Rust t=0.1377 显示 First cue；两者区域像素与各自静态定位的对应 cue 一致。该证据支持本样例循环及播放后 cue 选择，不提供精确循环次数、全程无停顿、掉帧或逐帧边界指标。只读 loop/loop_attribute 均 false，原值保留，不从属性推断运行机制。

DOM 读取与截图不是原子操作：SDK fresh-loop-paused 的 DOM 是 0.7817/paused=true，而即时原图仍显示 First cue/播放图标；原图和数据保留并标记，不纳入字幕时间一致性门。后续 fresh-loop-held 时间保持同值、原图已显示正确 Second cue，作为稳定样本。最终 SDK 12 阶段/9 张 JPEG、Rust 9 阶段/6 张 JPEG，共十五张原图均已查看；独立 trace 位于 reference-browser/video/timed-ui 和 rust-video/timed-ui，不改此前捕获。原标签丢失、SDK 首次瞬态、视口变化及非原子图均由专门门检查仍存在，不能改写为整齐统一成功。

四次 DOM track.src 实际 GET（两端各 English/中文）均 200/VTT MIME/正确长度，英文 93、中文 50 字节；完整原文、Base64、SHA 和内容地址与 SDK AppTest/helper 对应，字幕标签文件名参与摘要。自有 79075 父任务约 1205 秒，含二十分钟上限及关闭确认；任务标签显式关闭，旧 SDK 标签缺失状态另记。服务 terminate/wait 后 SDK 首次连接检查成功、后续 10061，Rust 10061，最终父任务退出 0；没有因为一次失效/观察时间长而重启服务。

视频模块新增 29 项，合计 104 项通过（target/video-timed-gates.log）：两端回放、同时间像素对照、timed SDK 实际 AppTest、原始瞬态保留，以及十二种损坏各两端（四个定位时间错、区域 SHA、循环停止/ended、观察时长不足、played 不完整、暂停漂移、VTT 字节、未清理）。初版回放门错误地要求不同时间的两个无字幕背景像素相同，导致两端及对照三项失败；这是测试假设错误，不是产品差异。原失败保留 target/video-timed-gates-first-red.log；删除该错误假设，按同一时间跨端比较，全部正例与负例重新通过，原数据未改。

更精确 cue 边界/连续逐帧切换、更多媒体/参数/编码/设备、全屏、完整资源生命周期和多小时稳态继续开放；不把二十分钟采集器寿命或端点观察当作 M5 完成。未实施待决 Unicode/repr/rerun 扩展，st.video、M3/M5/M7 和完整 Goal 保持开放。

最终视频/文档/配置/矩阵四模块 159 项通过（104 视频、55 文档，target/video-timed-final-gates.log），inventory 仍 130 partial。逐文件 diff/git diff --check 通过，九个受保护用户文件及全部捕获 source/exe SHA 与启动快照一致，库无 diff；只对修改的 example 做实际构建/Clippy，不无故重复全 Cargo。

仅暂存本批八个既有示例/测试/计划/矩阵文件和十七个新证据文件（十五 JPEG、两 trace），不纳入用户 Cargo、colconfig、指南/README 修改。两个现存任务标签已关闭，原 SDK 标签缺失状态保留；自有服务已清理。无 PR、合并、部署或发布，完整目标继续。
