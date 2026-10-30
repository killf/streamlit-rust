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
