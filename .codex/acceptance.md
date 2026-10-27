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

本地隔离开发环境、现有固定参考依赖和构建缓存已经获执行授权；不读取真实密钥或敏感配置。用户已进一步授权及时提交、推送验收后的批次；主分支更新经 PR/MR 门禁。PR/MR 创建、合并、发布、部署及生产/数据库外部写入分别核对授权，不从提交推送授权推断。

对应能力先写面向使用者的用法和行为文档，再实现；文档中的当前能力与规划接口分开标注。关键公共接口或行为规则确认后实施，普通实现细节自主处理。

用户最新澄清无需保持旧 Rust API 的向后兼容；Python Streamlit 1.66.1 的功能和行为目标继续保持。清理无关、过时的文档、图片、测试和代码，持续保持实现整洁；有效冻结数据仍用于回归，不因年代较早而视为无关。

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

用户采纳 A 后先写使用说明，再新增独立 `csv_workbench`，不改销售示例、不增依赖或公共 API。冻结 [Python 33 阶段](../tests/reference/reference-browser/csv-workbench/README.md)及 [Rust 对照](../tests/browser/rust-csv-workbench/README.md)，独立 Review 核对 1358 个 PB、真实交互、Arrow、下载及两会话；只对照逻辑文本数据/计数，保留 schema、索引、空图和下载重跑差异。部分 Python 截图柱高未刷新而 Arrow 已更新，原因未定，不宣称像素等价。来源替换先空状态的真实失败尚待用户决定，M2/长期 Goal 不关闭。

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
