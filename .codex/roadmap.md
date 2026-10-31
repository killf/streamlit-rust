# Roadmap

本文记录已确认的长期目标、阶段依赖和当前停止位置。2026-10-29 用户选择完整兼容优先路线并要求执行：先校准剩余范围，再完成 M3、M5 与 M7，停止于本地可审查、可分发成果。本轮执行包括本地代码、文档和相关验证；2026-10-30 用户追加“实现这个目标，记得定期提交并推送代码”，已授权当前工作分支的阶段提交和推送。PR/MR、合并、发布和部署仍需另行授权。默认单代理，新增并行或独立审查安排先确认。

功能证据仍由[兼容性矩阵](../compatibility/api-compatibility-matrix.json)维护，原有应用旅程由[journey 清单](../tests/journeys/journeys.json)维护。这里不另建逐项通过记录；验收要求见 [acceptance](acceptance.md)，能力边界见 [compatibility](compatibility.md)。

## Long-term goal

交付功能完整、行为可信、易于开发和分发的原生 Rust Streamlit，以锁定的 Python Streamlit 1.66.1 为首个完整兼容目标。生产运行保持原生 Rust，Python 只用于开发参考与差分验证；复用官方前端和协议。

完整性以官方用户文档中的功能、子能力、配置和使用流程为权威范围，不以 Python 导出符号、已捕获页面数、同名函数数或旧旅程通过数作为完整分母。Rust 的接口和实现可以不同；源码只用于核实行为及实现线索，不定义待实现功能。每项适用能力都需要实现、接通、异常与边界验证、文档和必要的浏览器证据。现有 `not_applicable` 理由须复核：缺少 Rust 实现本身不构成不适用。

最终完成要求覆盖功能、行为、用户体验、架构与资源生命周期、Rust API 易用性、测试可信度、性能报告、文档、工程检查、独立 Review 和本地分发。关键行为、公共接口、依赖、架构取舍或验收变化提交用户决定；普通实现细节自主处理。上游版本升级作为后续独立决定，不移动本目标的基线。

## Current focus

2026-10-29 本轮首先校准剩余能力和证据。未验证参数、外部来源、真实提供方及系统选择器等条件受限项继续开放，不通过接受已知限制、修改统计口径或缩小适用范围关闭长期目标。先前等待的“将外部/headless 项定为已确认限制”不再是推荐执行路径。历史已验收批次继续保留；本轮验证以当前环境与实际输出为准，历史 `target/` 日志不视为当前可用证据。

本轮已校正八项能力的过时描述并加强原始帧证据门；metric 字符串 delta 切片真实复现 30/36 差异，修复后 36/36 原生 WS 字段一致，旧失败与固定参考均保留。M3/M5/M7 继续开放；下一步继续参数链证据核对和剩余功能，不能把本切片的 WS 结果当成全前端或全部 metric 选项验收。

查询参数值与写入顺序切片已补真实 WS 参考：八阶段状态与七次 URL 写入验证重复键末值、全部值顺序、空列表存在性、替换/追加、删除/清空/恢复。修复取首值、字母排序及空列表删除失败；原浏览器链继续保留，保留键/绑定规则及当前浏览器 URL 往返仍开放。

查询参数保留键切片进一步补齐大小写无关的 embed/embed_options 隐藏、拒绝修改/删除且不发 URL、公开 clear 保留原值，以及空键/st_embed 普通键行为（九份 JSON、四次 URL 写入）。原始运行重置逻辑未改；绑定规则、错误 UI 和当前浏览器行为继续开放。

绑定生命周期切片已通过四轮真实 WS 对照（18 份 JSON、5 次 URL）：selectbox 与侧栏 text_input 注册后拒绝直接修改，条件隐藏仍保护到运行结束，统一清理失效 URL，下一轮解除保护。追踪复用 WidgetRegistry，无新公共接口；活跃轮显式同时提供 URL 与 widget states，不证明仅 URL 初始化、重挂载/跨页恢复或浏览器往返，M3 继续开放。

URL 初始化后续切片补八轮原生 WS：四类控件的 URL-only 值、前端/代码优先级、无效/默认/空值校正与历史导航恢复；32 次 value/set_value、8 份状态和 9 次 URL 顺序对照通过。重挂载/跨页、禁用/伪造输入、callback、绑定服务端重跑及真实浏览器操作继续待验，M3/M5/M7 不关闭。

同批补两轮独立 seed-code 参考，确认有效 URL 初始化/历史值覆盖错误类型代码状态；修复不应解析的旧值抢先报错。最终工作区 219 项与相关 Python 门 82 项通过；此结果只关闭已列输入边界，不把 130 项 partial 或长期目标改为完成。

**长期 M2、M6、M4 均已于 2026-10-28 关闭（各有保留证据与关闭记录）；M5 已交付稳定性三场景批次（保持开放），M3 参数面多切片收敛中；M7 全量验收已启动（首个跨能力组合差分 + 文档核验门 + 独立 Review 有保留通过并补齐阻塞项）。** M0 起点为 `99b1ed8e4b35737c9495764fb70269271a10bada`，开始时工作区干净。已建立官方文档能力与缺口清单、复核不适用项并刷新 Rust/Python 验证及性能基线；这不代表全功能或所有参数、教程 FAQ 的验收结束。已校验的 wheel 仅固定参考环境，不能代替官方用户文档的功能范围。

已完成 54 项历史 `not_applicable` 的用户文档适用性复核，结论见 [compatibility](compatibility.md#historical-not-applicable-closures-and-m0-review)；没有将缺少 Rust 实现视为永久排除，也没有自动改写旧状态。M1 列明的 Q1–Q6 已确认修复、回归、必要前端证据和独立 Review 已分批完成，覆盖范围见 acceptance；未验证的运行组合及资源边界继续留在后续里程碑，不把六项修复当成运行时完整兼容。

M0 批次基线在干净代码快照 `b94ac474` 上完成，172 项 Rust 与 1488 项冻结参考回归通过，debug 顺序性能冒烟已测 CPU、延迟和内存；方法和局限见 [acceptance](acceptance.md#current-m0-baseline-2026-10-27)，本地原始日志位于 `target/checks/m0-current-20261027/`。旧 `m0-baseline` 测量继续保留为历史记录。

[官方文档范围](../compatibility/documentation-scope.json)按 17 组、59 条子能力建立矩阵关联和证据缺口说明；关联不是完成状态，也不以这些条数宣称覆盖了所有参数、教程或 FAQ。尚未逐项核实的模式、组合和文档入口继续作为长期范围内的待核项。缺失的旧 docs HTML/catalog 不由下载归档冒充恢复；新抓取保留实际日期和文档版本。独立 Reviewer 已核对清单、当前日志与性能边界，确认符合 M0 退出条件。

选择接口按用户最新无需旧 Rust API 向后兼容的取舍，采用单入口返回 typed state，实施与验收见[当前设计](architecture.md#dataframe-selection-and-data-updates--proposal)。官方 1.58.0 已移除旧 add_rows；数据追加流程仍在 M2，是否另增 Rust 扩展由用户选择，不自动增加追加扩展。

选择参考保留[原 34 阶段前端输入](../tests/reference/reference-browser/dataframe-selection/README.md)，另补[八阶段 required 协议输入](../tests/reference/reference-browser/dataframe-required-protocol/README.md)，真实 Rust WS 共用 42 阶段回放。已修复空协议选择在返回、keyed 与 callback 间分裂的问题，包含空表/恢复时使用前轮行数上下文；此前选择批次的 177 项 Rust 和 1496 项冻结参考回归通过。新协议探针不宣称浏览器能清除 required 行，旧正确数据未重采。CSV 应用已由用户采纳[独立工作台方案 A](architecture.md#csv-application-integration--accepted-a)，先补使用说明，再实现与验证；其余方案不纳入本次范围。

M4 运行集成已启动（2026-10-28）：st.context 首切片已按用户确认实施——`st.request_context()` 返回白名单握手头（小写名）+ `st_embed` 标志，`RequestHeaderAccess` Standard/Selected/All 选择面（All 对齐冻结参考的全部头行为，含凭据，仅限可信部署）；WS 回归双向断言默认白名单不泄漏凭据/传输头、All 与参考集逐头一致，真实前端两阶段采集中 `is_embedded` 随 `?st_embed=true` 翻转。第二切片已按浏览器路径参考实施：url/locale/timezone/timezone_offset/theme/is_embedded 经前端每轮 rerun 的 context_info 上报（`?embed=true` 翻转、`?st_embed=true` 不翻转，双端实测一致）；ip 与 cookies 未实现。认证/用户信息切片已按指南推荐实施（trait 认证器 + HeaderAuthenticator 假凭据 + `st.user()` 空映射基线 + cookies 白名单访问；[验收](acceptance.md#current-fake-credential-auth-and-user-validation-2026-10-28)，公共形态待用户追认）；OIDC tokens 与真实提供方待 oracle。配置面已整理为指南显式表格并由离线文档门守护（[验收](acceptance.md#current-runtime-configuration-surface-validation-2026-10-28)）；用户已于 2026-10-28 追认公共形态，M4 关闭（[关闭记录](acceptance.md#m4-milestone-close-2026-10-28)）；ip_address 维持记录边界（两路径实测 null），OIDC tokens 与真实提供方为远期独立决定；config.toml 注册表与 secrets 文件存储维持既有不适用边界。见[启动验收](acceptance.md#current-m4-runtime-integration-start-2026-10-28)与[首切片验收](acceptance.md#current-m4-request-context-slice-validation-2026-10-28)。

## Long-term milestones

CSV 工作台 A 已交付主流程 20 阶段、筛选 13 阶段与来源替换 16 阶段的实现、冻结参考及真实前端对照。来源切换已按 2026-10-28 采纳的显式清空方案落地：空上传状态仅清选择、坏替换保留旧副本、显式 Clear working copy 唯一清空，双端下载逐字节一致（[验收](acceptance.md#current-csv-source-replacement-validation-2026-10-28)）。图表漏刷已按 2026-10-28 采纳的内容命名方案 A 修复：generic Vega 的内联值走内容命名 dataset 并由 spec 引用，四阶段真实前端可见值随 wire 刷新，失败基线保留（[验收](acceptance.md#current-generic-vega-refresh-validation-2026-10-28)）。多文件上传模式归入 M3 输入能力、上传端点安全边界归入 M4/M5，图内交互状态保持继续开放，均不在 M2 退出条件内。

下列 M0–M7 属于 2026-10-27 确认的长期目标，与文末已经关闭的历史 P0 里程碑区分。

独立 M3 下载边界已补默认/空文件名、Unicode/引号/反斜杠编码及文本 charset；十条冻结 Python 公开输入由 Rust 真实 HTTP 精确对照，另有两条实际浏览器保存证据，见[范围与局限](../tests/reference/reference-browser/download-boundaries/README.md)。它不关闭 M3，也不替代 M2 待决的来源/图表工作；完整类型推断、媒体生命周期及其余能力继续按官方文档范围推进。

缓存种类共用键表导致的实际返回值错误已独立修复：data/resource 同名同参各自保留结果、资源引用和录制输出；四组公开参考只采一次并冻结，Rust 真实 WS 复验各自重放。仍维持会话级缓存与现有总清空接口，未扩大为完整 Python 全局/会话选项、TTL 或分类别清空兼容；详见[参考及局限](../tests/reference/reference-browser/cache-kind-isolation/README.md)。

M5 三场景批次（2026-10-29）：吞吐（~509 rerun/s、字节/行数逐轮正确）、容量上限（128 并发两级全对）、5 秒有界持续窗口（~9.5k 轮精确状态）冻结于 stability.json 六相测量（[验收](acceptance.md#current-m5-throughput/capacity/sustained-validation-2026-10-29)）；**多小时浸泡仍未测，M5 保持未完成**。

M5 稳定性批次（2026-10-28）：大数据（100k/50k 行 + 200k 点图表）、长时运行（300 轮 rerun 精确状态）与慢连接（parked reader 不阻塞他 会话）三场景落地可复现回归与 3 试次测量（[验收](acceptance.md#current-stability-scenarios-validation-2026-10-28)）；吞吐/容量上限/多小时运行未测，M5 保持未完成。

M3 select/pills 切片（2026-10-29）：selectbox placeholder/help/disabled、checkbox 参数、pills multi 索引默认双端冻结 5/5（零实现改动确认；[验收](acceptance.md#current-select/pills-parameter-validation-2026-10-29)）。

M3 code/skeleton/logo 切片（2026-10-29）：code 语言/行号、skeleton、logo emoji 端到端双端冻结 3/3 + logo 帧（零实现改动确认；[验收](acceptance.md#current-code/skeleton/logo-parameter-validation-2026-10-29)）。

M3 文本族切片（2026-10-29）：latex LATEX 类型与 divider/help/text 字段形态双端冻结 5/5（修两处 markdown wrap/typing 偏差；[验收](acceptance.md#current-text-family-parameter-validation-2026-10-29)）。

M3 录制控件切片（2026-10-29）：audio_input 显式采样率、camera_input 默认形态双端冻结 3/3（零实现改动确认；[验收](acceptance.md#current-recorder-parameter-validation-2026-10-29)）。

M3 json/badge/feedback 切片（2026-10-29）：json expanded 语义（无 depth 参数实测裁决）、badge wrap 缺省修复、feedback 位置 preset 双端冻结 6/6（[验收](acceptance.md#current-json/badge/feedback-parameter-validation-2026-10-29)）。

M3 slider/multiselect 切片（2026-10-29）：datetime 微秒步长、date 一天缺省步长、multiselect 索引默认双端冻结 4/4（零实现改动确认；[验收](acceptance.md#current-slider/multiselect-parameter-validation-2026-10-29)）。

M3 chat/metric/progress 切片（2026-10-29）：emoji avatar、metric 全 delta 规则（三处偏差修复）、progress text 双端冻结 8/8 一致；progress float overload 裁决为 Python-only 记录差异（[验收](acceptance.md#current-chat/metric/progress-parameter-validation-2026-10-29)）。

M3 buttons/images 切片（2026-10-29）：按钮 primary/icon/disabled、download URL 命名规则（.txt/.bin）、st.images 多图列表 API 双端冻结 6/6 一致（[验收](acceptance.md#current-button/image-creation-parameter-validation-2026-10-29)）。

M3 temporal 切片（2026-10-29）：date_input 边界/十年窗/自定义 format、select_slider 范围默认、time_input step 双端冻结 5/5 一致（零实现改动确认；[验收](acceptance.md#current-temporal/slider-creation-parameter-validation-2026-10-29)）。

M3 widgets 参数切片（2026-10-28）：number_input float 路径（修复 format 留空与无界哨兵两处偏差）、radio index=None/horizontal/captions、text_area max_chars/placeholder/height、multiselect max_selections 双端冻结 8/8 一致（[验收](acceptance.md#current-widget-creation-parameter-validation-2026-10-28)）。

M3 收窄前置（2026-10-28）：130 项 partial 已机器导出精确清单（80 可测/12 需外部源/2 headless 不可达/36 无未测声明，带漂移门）；范围确认问题已提出未获答复，全部保持开放，继续 80 项可测面切片（[清单](acceptance.md#current-m3-partial-inventory-2026-10-28)）。

M7 终批前置（2026-10-29）：范围确认第四次提交未获答复（不默认确认，全部保持开放）；不依赖确认的文档核验（矩阵全量审计/全链接解析/全部离线门）与遗留清理扫描（零 TODO、无死探针）已完成并通过（[状态](acceptance.md#m7-terminal-batch-preparation-status-2026-10-29)）；终批剩余定格/复核/最终 Review 待用户答复后一次执行。

M7 第二差分链（2026-10-28）：六阶段真实 UI 交互组合差分双端冻结、报告逐阶段一致、独立 Review 有保留通过（建议项已采纳）；**关闭评估采纳审查结论——M7 现在不可关闭**，须先完成 M3（130 项 partial）与 M5（吞吐/容量/多小时），排序 M3 → M5 → M7 终批（[评估](acceptance.md#current-m7-second-differential-and-close-evaluation-2026-10-28)）。

M3 收窄 + M5 边界批次（2026-10-28）：video URL 输入、SRT 字幕、popover wrap、tabs 宽高双端冻结 6/6 一致（暴露并修复 Rust SRT 校验缺陷）；64 并发会话容量回归落地；媒体回收确认为进程全局设计事实（[验收](acceptance.md#current-media/layout-edges-and-session-capacity-validation-2026-10-28)）。

M7 启动批次（2026-10-28）：跨能力组合差分（22 元素双端冻结、仅两条既有约定归一化）、常驻文档核验门（矩阵证据/指南链接/示例索引/链 README-manifest）与独立只读 Review（有保留通过，两阻塞项已补齐，[验收](acceptance.md#current-m7-kickoff-validation-2026-10-28)）；全量差分扩展与遗留清理未完成，M7 保持开放。

M3 列参数切片（2026-10-28）：st.columns 的 gap/border/vertical_alignment/加权 spec 已双端冻结验收（22/22 块逐字一致，修复容器 scale/wrap、f64 权重与列 gap 复制三处偏差；[验收](acceptance.md#current-columns-parameters-validation-2026-10-28)）；wrap/自定义列宽/嵌套未测。

M3 布局/流式参数切片（2026-10-28）：expander 类型、popover 参数、tabs 默认标签、status 更新语义与 toast 时长已双端冻结验收，14/14 块发射逐字一致（[验收](acceptance.md#current-layout-streaming-parameters-validation-2026-10-28)）；STEP/wrap/容器内 toast 未测。

M3 媒体参数切片（2026-10-28）：audio/video 播放参数（start/end/loop/autoplay/muted）与文本字幕已双端冻结验收，`audio/x-wav` 裸地址与非法字幕异常元素均实测对齐（[验收](acceptance.md#current-media-playback-parameters-validation-2026-10-28)）；YouTube/URL 输入、多音轨、SRT 实测仍开放。

M3 输入切片推进（2026-10-28）：`file_uploader` 多文件模式已双端验收——批量地址请求、逐文件 PUT、整表状态与逐文件移除语义、返回值逐字节一致（[验收](acceptance.md#current-multiple-file-upload-validation-2026-10-28)）；大小限制双防线（前端 wire 拦截 + 服务端 413）与目录选择器渲染已实测对齐（[验收](acceptance.md#current-upload-size-limit-and-directory-validation-2026-10-28)）；目录完整流（OS 选择器/webkitRelativePath）headless 不可达；并发竞争与断线过期清理已按协议参考验收（[验收](acceptance.md#current-upload-concurrency-and-expiry-validation-2026-10-28)），更高并发度不冒称已测，M3 保持未完成。

媒体 Range 已按[27 个冻结公开 HTTP 请求](../tests/reference/reference-browser/media-range/README.md)修复后缀、非法/越界/多范围、空文件及超 u64 数字的处理；状态、响应头与字节由实际 Rust GET 精确对照，公开解析器签名不变。它是 M3 传输子集，不代表已测播放器拖动、HEAD/If-Range/CORS、所有输入语法或完整媒体生命周期，M2/M3 继续保持未关闭。

M5 的独立媒体响应优化已改用共享不可变字节，消除每次 GET 的全文件克隆及 Range 片段复制；[同负载三次测量](../tests/performance/media-storage.json)证明进程内响应构造与持有成本下降。194 项 Rust 和 1516 项冻结参考检查通过，公共行为无变更，未重采 Python；未声明网络吞吐、慢连接容量或长期回收通过，进程全局媒体仍无自动淘汰，M5 不关闭。

后续会话验证批次只补测试与文档：16 个真实 WS 客户端、两个 worker 配置下的部分重连与独立计数，以及四轮共 128 个会话的惰性到期对象释放通过。13 项相关检查及全目标 Clippy 通过；[具体验收](acceptance.md#current-session-boundary-validation-2026-10-27)区分客户端并发、运行中接管、Weak 对象释放和未测容量/长期内存，不用此前全量结果代替本批验证，M5 保持未完成。

WS 日志已在真实红→绿后移除完整 protobuf/文本/关闭描述展开，保留种类、长度、数量、运行耗时和错误摘要。隔离合成场景的日志从 131,289 降为 3,704 字节、五类载荷标记降为零，原 WS 行为保持；格式、Clippy 和当前 197 项 Rust 检查通过。[验收边界](acceptance.md#current-websocket-logging-validation-2026-10-28)不含 CPU/网络吞吐或完整安全/第三方日志保证，未重采 Python，也不关闭 M5。

M3 原生输入边界已修复 RGBA 尺寸计算 panic，以及无编辑编辑器复制中的 metadata 丢失/零列 panic；200 项当前 Rust 和 47 项矩阵检查通过，release 补验另见[实际验收状态](acceptance.md#current-native-input-boundary-validation-2026-10-28)。零列呈现已按 2026-10-28 用户采纳的方案 A（虚拟 RangeIndex）落地：显示转换保留真实行数并合成 range 索引描述符，dataframe、table(hide_index=false) 与固定编辑器在官方前端渲染 0/1，Rust 四阶段真实前端对照与 WS 回归已冻结，原 Python 错误参考保留不重采；这是对直接 Arrow 上游格错误/空框的明确修正而非逐字段等价，动态行编辑与任意 schema/metadata 组合仍未验证，M3 保持未完成，验收见[零列呈现状态](acceptance.md#current-zero-column-display-validation-2026-10-28)。

| 阶段 | 交付 | 退出条件 |
|---|---|---|
| M0 完整基线 | 公开能力和子能力盘点、不适用复核、当前测试与性能基线、依赖及待决策项 | 盘点来源可追踪，未验证和未实现明确，范围取舍可审阅；不将静态盘点当兼容证明。 |
| M1 运行基础 | 复现并处理 Q1–Q6：查询参数重跑、运行控制覆盖、组件默认状态、嵌套缓存录制、编辑空值与文档矛盾 | 修复前后证据、相关 Rust/协议回归及必要浏览器差分；空值 schema 等关键规则先确认。 |
| M2 数据应用 | 上传、筛选、选择、详情、编辑、增量更新和图表联动 | 完整用户流程及空集、替换、恢复、排序映射、会话隔离有实际操作证据。 |
| M3 适用公开能力 | 补齐输入、布局、媒体、导航、缓存、流式输出与组件的适用能力 | 经确认的适用能力无未实现或未接通项，参数、返回值、状态和失败边界均有覆盖。 |
| M4 运行集成 | 配置、请求上下文、认证、用户信息及必要 Rust 等价集成 | 关键设计获确认，使用假凭据和隔离依赖验证，权限边界清楚。 |
| M5 稳定性与性能 | 并发、慢连接、重连、长时运行、大数据、资源回收和测量驱动优化 | 已确认测试负载下无未处理的正确性或稳定性阻塞，性能资源报告可复现；不自定产品 SLO。 |
| M6 开发与分发 | API 一致性、完整示例、文档、支持工具链及平台、本地安装产物 | 干净环境可依文档构建、安装并完成代表性应用；不是公开发布。 |
| M7 完整验收 | 全量回归、关键组合差分、独立 Review、文档核验和遗留清理 | 长期验收全部满足，剩余限制经用户明确确认，停止于本地可审查、可分发成果。 |

文档、测试、架构一致性和代码规范随每项能力同步验收；性能自 M0 起保留测量。阶段通过后推进已确认范围，不以进入下一阶段为由自动批准新的公共接口、依赖或关键规则。

M6 独立构建子集已修复协议目录及前端版本身份的仓库路径依赖，完成改名/含空格目录的检查、release 示例构建和本机安装真实交互，完整 sidecar 与锁定 wheel 一致；[证据与边界](../tests/browser/rust-library-portability/README.md)不等于新机器、所有平台或完整源码包验收。宏支撑已按 2026-10-28 采纳的方案 A 实施：doc-hidden `__macro` 重导出 + 限定路径显式建运行时，仅依赖 streamlit 的外部应用（改名/含空格库目录）真实编译、启动并完成浏览器交互，历史红保留（[决策](architecture.md#consumer-macro-support--accepted-a-doc-hidden-support-namespace)）。

后续[真实 crate 检查](../tests/build/crate-archives/README.md)已通过两个包的默认编译验证、全部 41 个示例及普通 SDK consumer。修复了示例对四份包外数据的依赖，数据仍与原参考一致；最终 SDK 227 文件、宏 6 文件。维护者测试归属已按 2026-10-28 采纳的 PKG-A 定义：SDK crate 以库/宏编译与示例构建为验收，全部维护者回归由完整仓库源码交付承载，31 个包内输入缺失是边界记录而非缺陷（[决策](architecture.md#maintainer-source-distribution--accepted-pkg-a)）；断言未删、测试未关。

M6 已于 2026-10-28 关闭：除包验证外，退出条件『干净环境可依文档构建、安装并完成代表性应用』以全新 CARGO_HOME/TARGET（空 registry 按 lockfile 联网实下依赖）+ vendored protoc 构建 quickstart、启动并真实浏览器交互（复选框翻转、无异常）补齐（[关闭记录](acceptance.md#m6-milestone-close-2026-10-28)）。边界：全部证据为同机 Windows/MSVC 与既有 rustup 工具链，新机器安装、MSRV、其他平台不在声明内；无公开发布。

用户进一步明确开发顺序：先写面向使用者的功能流程、Rust 用法、返回值、错误及状态说明，再开发对应能力。使用文档清楚区分当前可用、部分验证与待实现；拟新增公共接口和关键规则先供确认，不能将规划接口写成已可用。已完成的代码和证据保留，顺序调整不用于回退他人工作。

## Team and integration

本轮默认单代理，负责关键路径、接口和最终验收。需要并行或独立只读 Reviewer 时，先确认具体分工；最终 M7 的独立审查要求仍保留。参考测量先于兼容实现，紧密耦合逻辑由同一执行者负责。

主代理模型由客户端控制，不宣称历史模型池或并发配置在本轮生效。后续团队安排只使用届时明确批准且实际可用的配置。

## Historical P0 terminal goal

以下为长期 Goal 建立前的 P0 退出条件和历史记录，只证明当时已捕获范围的完成，不构成长期目标的完整兼容结论：

1. The journey manifest shows all 10 journeys / 43 steps `passed`, including J09-S4 measured by a real slow disconnect (not by policy or inference).
2. Every captured matrix row (182 documentation entries) has left `absent`/`unverified` through linked black-box differential evidence, or carries an explicit recorded reason it does not apply.
3. All 21 API/wire obligations (A01–A10, W01–W11 in [acceptance](acceptance.md)) are closed with measured evidence; no obligation remains "carried forward".
4. The required fresh-checkout checks (pytest reference suite, `cargo fmt --check`, `cargo clippy -D warnings`, `cargo test` — which includes the Rust journey-ledger validation) all pass.
5. The repository itself stays worth reading and trusting: the code carries no dead or superseded paths, every document is concise and readable for its human audience, the examples run against the current API, and obsolete code, tests and docs are removed promptly rather than archived in place.

Compatibility is only established by black-box evidence against the pinned reference; a milestone never advances a status without it.

## Cross-cutting quality acceptance

下列既有质量约定继续适用于长期里程碑；仅历史阶段名称和关闭记录不代表当前验证已运行。

**Code quality.** `cargo clippy --workspace --locked --all-targets -- -D warnings` and `cargo fmt --all -- --check` stay green (already fresh-checkout gates). Beyond the tools: no dead code, no superseded duplicate paths, no speculative abstraction — the simplest implementation that passes its evidence chain wins, and public user-facing API carries rustdoc that agrees with the guide.

2026-10-27 用户明确要求 Rust 禁止使用 `.unwrap()`。工作区通过 `clippy::unwrap_used = deny` 执行，两 crate 继承，检查包含生产代码、构建工具、示例和测试。既有用法按错误语义整改：可恢复错误正常传播，测试用明确断言表达预期，不能机械替换为 `.expect()` 或通用 panic 包装来绕过规则。当前迁移已通过全目标 Clippy、工作区及示例测试，证据范围见 [acceptance](acceptance.md#rust-error-handling)；新增 lint 前的旧通过记录保留其原始配置身份。

**Rust-first tests.** Repository tests default to Rust under `cargo test`: runtime regressions, protocol contracts and ledger validation live in the workspace. Python is reserved for the reference side of the evidence chain — fixtures executed by the pinned Python server and the Chrome CDP capture tooling — and when a Python test no longer needs that side, it migrates to Rust in the same change that retires the reason.

**Documentation readability and conciseness.** Every document states and serves a human audience: `README` and `docs/guide` for users, `.codex/` for process and contracts. Prefer rewriting a section over appending to it; when a sentence has grown into a paragraph, split it or cut it. Documentation follows the code it describes: a milestone that changes behavior updates or deletes the affected doc lines in the same change, and a doc that no longer describes anything real is deleted, not left to drift. Duplication of the live ledgers stays forbidden (see maintenance rules).

**Human-facing examples.** `streamlit/examples/` is product surface, not scratch space: every user-facing API added by a milestone appears in a minimal, runnable example; examples are edited or removed in the same milestone that changes their API; `docs/guide` stays an accurate index of what each example shows and how to run it. The usability bar: a human with only the Rust toolchain goes from fresh clone to a running app of their own using `README`, `docs/guide` and the examples, without reading server internals.

**Usability.** Full parity never excuses a heavier call. Builders are value-first with `Into`/tuple conversions so the plain call is the common call; defaults equal the measured reference, so zero configuration renders the reference page; knobs beyond what evidence requires are not added; the hot path stays allocation-light and never blocks the render loop. Every new API documents a one-line shorthand next to its full-options form, and a milestone whose API reads worse than the reference's Python call is not closed.

**Hygiene and cleanup.** Superseded code, tests that no longer exercise live behavior, spent probe scripts and stale doc sections are deleted in the milestone that retires them. Cleanup explicitly does not delete retained failure evidence or frozen capture artifacts: [acceptance](acceptance.md) requires failed and partial attempts to keep their real artifacts, and those are records, not clutter. Ignored `target/` rounds never migrate into the repository.

## Historical P0 milestones

历史 P0 于 2026-10-25 至 2026-10-27 分阶段关闭：当时的记录覆盖 10 个旅程、43 个步骤和 182 条历史文档矩阵条目。此结果仅描述当时捕获与验证的范围，不代表长期 Goal 已完成，也不证明后续修改已通过相同检查。

具体旅程、准备动作和证据见 [journey 清单](../tests/journeys/journeys.json)，各功能的测量范围和限制见 [兼容性矩阵](../compatibility/api-compatibility-matrix.json)与 [compatibility](compatibility.md)；验收边界见 [acceptance](acceptance.md)。冻结参考和历史证据继续保留。

## Maintenance rules

- The current-focus pointer moves only when the active milestone's exit criteria are met with retained evidence, never by plan or estimate.
- Milestone work items are ordered within the milestone but do not skip the reference-first rule; a measured contradiction with the reference stops the item and records the failure.
- journeys.json remains the only live step ledger and the matrix the only per-API ledger; roadmap updates at milestone close record only structure, ordering, and focus movement.
- A feature is done when it works, is evidence-verified, reads like the rest of the codebase, is documented concisely for its audience, is shown in an example (when user-facing), and leaves nothing superseded behind. Any missing subset is an open task, not a finished feature.
- Milestone close runs the quality pass: the clippy/fmt gates, an example build, a documentation accuracy check of everything the milestone touched, and a cleanup sweep for retired code, tests and docs.
- Milestone close distills process lessons into [lessons](lessons.md) and prunes entries that no longer change how we work; recurring friction is promoted to a lesson the moment it is paid for twice.
- Each milestone close updates this file's focus pointer and commits together with its evidence.

### Disabled input and callback compatibility slice

2026-10-30 用户选择保留 Python 错误、已执行 callback 和后续恢复。两份不可覆盖的 1.66.1 原生 WS 记录位于 `tests/reference/reference-browser/queryparams/disabled-valid/trace.json` 与 `disabled/trace.json`，各九轮。前者 58 个交错事件（44 个控件同步投影、9 份状态、5 次 URL）；后者 52 个（40 个投影、8 份状态、3 次 URL、1 个 TypeError）。错误轮只有 Plain 发出后 selectbox 报错，同批 Live callback 已发生，下一轮仍能回调并恢复。

WidgetSpec/Record 内部保存 disabled，callback 按上一轮元数据处理，当前禁用注册恢复输入前值；代码赋值和 URL 优先级保留。已测 bool oneof 提交给禁用普通 selectbox 时延迟到注册呈现 TypeError，并保留未渲染控件，避免错误轮清理破坏下一轮恢复。无新增公共接口或依赖。错误比较覆盖类型、消息、出现位置与标志；Python 来源栈帧单独保留，Rust 不伪造。其他错误类型/控件、跨页、绑定服务端重跑和真实浏览器错误界面继续开放，M3/M5/M7 未关闭。

本切片最终工作区 223 项、相关 Python/矩阵/文档门 103 项通过；详细验收与局限见 acceptance 的 Disabled widget inputs 条目。下一步继续补齐绑定控件服务端重跑、跨页与真实浏览器行为，不将 native WS 等同于完整 UI 验收。


绑定控件服务端重跑切片新增五请求十轮的固定原生 WS 参考（47 个交错事件），复现旧轮多发 Delta、未渲染控件过早清理、前端优先级丢失、代码同步标志丢失及静默 URL 折叠影响内层初值。用户已选仅丢弃未发送 Delta 的发送流程；修复继续保持流式和已发送帧。真实浏览器、callback 内 rerun、fragment 和跨页组合仍待补证，长期目标不缩减。


发送队列扩展发现未发送 Navigation/PageConfig 也需清理、toast Delta 必须保留。新增原生参考和 red 回归保留；完整保留表的流程选择已请求用户决定，当前仅获准的 Delta-only 实现未擅自扩展。工作区首次本批回归为库 219 通过、1 导航失败，不能报告全绿；控件单元 14、查询核心差分及执行测试已有通过。后续消息参考与测试加入后需重新完成代码/单元/集成/工作区验证。长期目标继续开放。


队列扩展待选择期间，独立头像/JSON 切片补 28 组固定字符串输入与 57 个 WS 投影：默认名字、预设别名、emoji、图片 URI 编码已对照；并修复非 BMP JSON 转义与 JSON 默认展开。无新增接口/依赖。完整浏览器图片显示、图片加载与异常、JSON 整数展开深度等继续开放；“没有 depth= 参数”不代表没有 expanded=int 能力，旧说明已校正。整体目标和队列待决项未缩减。

头像/JSON 切片：57 个 WS 投影一致；相关单元/集成和 Python 门通过。工作区其余 229 项通过，明确排除两个待选择队列规则的 red 回归，不能称完整工作区全绿；详见 acceptance。队列流程未在本批越过用户待决项。


JSON 字符串切片补 36 个固定原生 WS 元素，修复顶层字符串重复编码，保留非字符串序列化；JSON 旧参考比较也补原始 protobuf 绑定与七项损坏 guard。字段、路径与展开标志已对照；前端错误 UI、整数展开深度、自定义序列化失败及队列待决项仍未关闭。

JSON 字符串切片最终 36 个 WS 元素一致；工作区其余 231 项通过（精确排除两个队列待决回归），相关 Python/矩阵/文档门 118 项通过。完整浏览器/整数深度/错误与剩余参数仍开放，队列扩展选择未被后续独立工作替代。


JSON 已补真实 Chrome 证据：每端 22 个状态覆盖 15 种字符串显示和两个实际折叠/展开/折叠往返，语义投影全部一致，截图/DOM/console 原样保留。示例先做完整 36 元素原生 WS 预检。该结果只补已测 UI 子能力，不等于全部 JSON、所有浏览器或长期目标完成；队列待决与 M3/M5/M7 保持开放。

本次 JSON Chrome 补证：示例 Clippy/构建、36 原生 Element 预检与 22 对浏览器状态通过；相关 Python/矩阵/文档门 129 项通过，服务与标签页已关闭。控制台真实上游错误日志保留，不宣称零错误或完整 JSON/全部旅程通过。


JSON 深度/宽度已补 18 组固定原生参考（9 成功、9 拒绝）；JsonOptions/json_options 等三种公共接口方案等待用户决定，尚未实施。独立 logo 切片复现并修复 9/18 双图载荷差异，字符数启发式改为复用现有 Unicode emoji 数据。两项不改变队列待决状态，也不关闭完整 JSON/logo 或长期目标。


2026-10-30 独立数值切片修正共享 JSON 编码的有限浮点数指数格式，16 组有限输入的标量/数组输出通过真实 WS 对照；保留 19 输入的 Python、修前和修后原始记录。NaN 与正负 Infinity 的三组输入在当前 to_value 流程仍变成 null，六个差异继续开放，不能用字符串场景已匹配代替数值兼容。235 项工作区测试通过但明确排除既有两项队列差异，140 项相关 Python 门通过；完整范围和待决接口/发送流程保持原样，后续内部序列化设计需先说明取舍。


2026-10-30 已补齐 JSON 映射键、warning、序列化错误和恢复的原始参考：Python 17 输入/37 元素，Rust 独立五元素诊断证明 None 键与自定义 Serialize 错误的静默丢弃。七项可通过通用原始帧检查的语义损坏 guard 被拒绝；最终相关 Python 门 149 项通过。新内部直接 Serde 文本写入与值树方案已交用户选择，不把继续其他能力等同接受差异；尚未修改生产流程，也未缩减自定义错误与更广输入范围。


2026-10-30 独立 st.code 切片消除 27 场景中的 23 个元素差异：只移除各一次边界 LF，空语言发 plaintext，保留 CR、缩进及其他空白。固定修前/修后数据、全 Element/路径生产 WS 差分与九种有效宽高组合已验证；八项语义损坏 guard 通过。238 项工作区测试通过但仍明确排除既有两项队列差异，相关 Python 门 159 项通过。非字符串、无效尺寸与真实高亮/滚动/响应布局未关闭，完整 Goal 与三项待决流程不变；保持阶段提交与推送。


2026-10-30 实际 Chrome 验证代码动态高度时复现 hash 遗漏 height 导致旧 Element 被复用，已最小修复并保留原生/浏览器失败材料。修后高度往返、自动换行、行号与实际内层滚动对齐固定 Python 场景；两端 13/14 个观察及全部 16 张正确/失败 JPEG 有门验证，动画中间状态和一次 runtime 误标采集均如实保留。240 项工作区测试通过但仍排除既有两项队列差异，相关 Python 门 174 项通过；其余代码输入/布局、三个待决流程及完整 Goal 继续开放，照常阶段提交和推送。


2026-10-30 代码元素身份继续消除字段拼接歧义：不同正文/语言组合旧 hash 相同并在真实 Chrome 留旧正文，现用既有字段 Debug 元组保留边界/转义。原生和浏览器 before/fixed 证据、九张 JPEG 与七项损坏 guard 保留，正文/语言切换和恢复对照通过。242 项工作区通过但仍排除既有两项队列差异，185 项相关 Python 门通过；原高度修复不回退，其他元素及更广兼容范围、三个待决流程继续开放，按阶段提交推送。


2026-10-30 跨元素身份调查证实同类缺口不仅在 code：三轮 24 元素参考的五个变化目标在 Rust 仍为 A/A/A，真实 Chrome 保留旧标题锚点/分隔线、caption 样式和按钮启用状态。六张 JPEG、正确/失败原始记录与更强证据门已保留。另发现八个完整 Element 布局存在性差异，保持未完成。architecture 中已形成统一 NewElement 身份、生产者完整 hash、逐项元组三种实际流程选项及文件/验收范围；生产 hash 尚未改变，待用户决定后实施。其余三个既有待决流程和完整 Goal 不变。


2026-10-30 文本布局默认值：Markdown 默认/auto 省略 width_config，badge 默认省略 alignment；caption stretch 保持。完整 Python 17 场景与 Rust 可表达 13 场景分别保留，后者 14 个完整 Element/路径对齐；既有 identity 场景八处布局偏差消除。非默认 TextAlignment 外部导出等待选择，四个目标 hash 仍不变，未声称 UI 修复；全部兼容目标及 130 partial 分母保持。


2026-10-30 文本规范化切片：七类公共调用的 12 输入共 85 个完整 Element/路径与固定 Python 3.14.7 参考匹配，修复混合缩进、Unicode 空白、CRLF 及 LaTeX 先清理后包裹；LaTeX 默认宽度/对齐存在性同步纠正。72 个修前偏差与首次 fixture UnicodeEncodeError 保留，UI/非字符串和其他参数未据此关闭，130 partial 及完整目标不变。


2026-10-30 divider 完整布局切片：只省略 Divider 错发的 LEFT alignment，五种有效宽度及 Markdown/caption/LaTeX 对照共九个完整 Element/路径匹配 Python。保留修前五处偏差；无效宽度、浏览器几何和统一身份继续开放，130 partial 与长期目标不变。


2026-10-30 divider 无效宽度已从静态风险转为真实四轮失败：Python 未捕获/显式捕获/同连接恢复共 11 元素，Rust 16 元素、负数转大 u32 且继续 after。正确和错误原始记录/语义门保留。architecture 提出 Result 返回与验证配置两种完整错误契约，以及暂缓选项，包含 Entry/宏的实际依赖与验收；等待用户选择，生产代码未改，完整目标及 130 partial 保持。


2026-10-30 已补真实 Chrome 文本布局：九个 divider/对照与 85 个规范化元素的语义、尺寸和相对位置匹配，真实 End/Home 验证底部 Unicode/空输入与恢复。八张 JPEG、原始视口/坐标、滚动动画窗口和两端相同的六条 KaTeX 告警保留；不声称全屏像素或一般 Unicode 数学支持。未改生产代码，待决接口/错误流程及完整 Goal 保持，矩阵仍 130 partial。


2026-10-30 badge/文本帮助创建切片：标签仅转义方括号、有效/空白图标 trim，帮助 dedent 保留边界 LF；18 个完整 Element/路径匹配 Python，17 个修前偏差保留。共用内部去缩进逻辑，正文 clean_text 回归保持，无公共接口/统一身份改动；无效 icon 错误、tooltip/动态帮助刷新及完整目标继续开放，130 partial 不变。


2026-10-30 badge/帮助已补真实 Chrome：12 标签可见语义及七个帮助入口的实际悬停结果匹配 Python，每端八观察/四 JPEG。隐藏测量副本、空标签、指令式标签实际显示及截图超时恢复原样记录；本批未改生产代码、未做参数切换，动态帮助 hash 缺口及其他待决接口保持，完整 Goal 与 130 partial 不变。


2026-10-30 四种 Alert 规范化切片：正文/title clean_text、显式图标 strip/空串语义及两类开头图标分隔规则修正。48 次公共调用与双 JSON 报告共 50 完整 Element/路径匹配，修前 16 误拒绝和首次 U+001C 过度清理记录保留；16 分隔符 helper oracle 明确区别于 WS。无公共接口/错误类型变化，UI、图标全集和错误组合仍开放，130 partial 与完整目标不变。


2026-10-30 四类 Alert 已补真实 Chrome：48 个提示的文字/标题格式、图标、颜色、ARIA role 与 240/704px 布局匹配。真实 PageDown/End/Home 验证滚动和恢复，六张 JPEG 与八个原始观察保留实际视口变化、坐标和控制字符显示。未改生产代码，其他视口/主题、非法参数、callback 和参数更新身份仍开放，完整 Goal 与 130 partial 不变。


2026-10-30 Alert 错误边界推进：保留公开 Result/错误变体，修正 icon-before-width、分类错误文字及 spinner。二十输入乘四格式的完整 WS 语料修前有 60 处不同，修后剩 12 处（未知 Material 的两类行为、带引号宽度 repr），68/80 对齐；未缩小语料或完整兼容分母。Material 冻结目录的三案已写 architecture.md，新增生产文件/生成流程待选；宽度 repr 可独立推进。130 partial、M3/M5/M7 与完整 Goal 保持开放。


2026-10-30 Width repr 继续推进：引号选择、反斜杠和 ASCII 控制字符转义已修正，原二十输入达到 72/80 对齐。扩展后完整 38 输入/152 调用匹配 112 次，仍有 Material 8 次及 Unicode 不可打印字符 32 次差异；全部保留。直接套 Rust Debug 经实测不等价，冻结 Python Unicode 16 数据的方案已列入 architecture.md，新增数据/生成流程待选。完整 Goal 和 130 partial 保持开放。


2026-10-30 修正已有 Python bytes repr 的定界符选择，并纠正原错误单元预期；对应数据集哈希已按固定 Python oracle 验证，覆盖引号组合和 256 字节序列。三份既有 chart IPC 本来含双引号，本批未证明新的公共 UI 故障。相关图表/原生 bar 回归通过，未改接口、依赖或待选数据方案；130 partial 和完整目标保持。


2026-10-30 禁用控件错误类型继续推进：selectbox 的 int/double 已补与 bool 一致的延迟校验机制，各自复现准确 TypeError、保留 Live callback 并在下一轮恢复。Rust 真 WS 对照前三类完整九轮/42 事件；八种类型参考另保留独立会话和持续失败两份原始记录。数组导致早期异常且后续仍失败，JSON/普通控件的 Rust 差分和真实 UI 仍开放；继续遵循用户已选 Python 行为方案 1。130 partial 和完整目标保持。


2026-10-30 数组错误阶段已补：注册器保留输入解码错误，执行入口在 callback/用户代码之前呈现 TypeError；后续请求继续失败，新会话独立。Rust 差分已从九轮标量前缀扩展到完整八组 24 轮/130 投影，并复现单会话 17 轮/40 投影的持续错误；JSON/其他控件所测忽略行为也匹配。异常位置严格检查，原始参考复用不改。真实 UI、其他参数/oneof/JSON 形状仍开放，130 partial 与完整目标保持。


2026-10-30 错误类型扩大到十六例：JSON list/dict、三种 repeated 数组均复现入口前持续错误，JSON null/string 所测忽略行为匹配；空 bytes/trigger 复现注册阶段错误、已发生 callback 和恢复。完整 48 轮/230 交错投影真 WS 对齐，旧八例/单会话原始记录保留。无新公共接口/依赖，JSON 语法错误、非空 bytes 及其他参数/真实 UI 未验收，130 partial 与完整目标保持。


2026-10-30 完整冻结参考回归为 1781 项通过。媒体 PNG 校验改用 Image.load 的像素访问，保留逐像素判据与既有篡改拒绝，96 条弃用告警消除；完整参考在弃用告警视为错误下仍全通过。用户指南同步已测 URL 初始化、错误阶段/callback/恢复与 Rust 控制流限制，已有 colconfig 索引改动不纳入提交。没有新增生产接口或真实 UI 结论，130 partial 与 M3/M5/M7/完整 Goal 均保持开放。


2026-10-30 非空 bytes 验证补齐：原有后端逻辑不变，测试重放解除仅空字节限制；十九例/57 轮、272 个交错投影对照普通字节、控制字符及 0..255 序列，均保留既有 callback 和同会话恢复。精确字节内容另有单元和反向序列篡改门验证，没有新增生产依赖/API。JSON 语法错误及其他未测行为继续开放，130 partial 与完整目标保持。


2026-10-31 JSON 语法与接受边界参考已冻结：24 会话/72 轮、34 状态、38 异常、252 交错投影。17 个语法错误输入表现为入口前且持续的 json.decoder.JSONDecodeError；五种特殊标量被接受，另外两种含非有限数的容器转为 TypeError。库层对比显示 serde_json 1.0.145 拒绝 Python 接受的七种解码输入，不能直接拿其错误替代 Python。私有扫描/现有 IgnoredAny 适配/暂缓三案见 architecture.md，新增生产模块待用户选择；本轮未实施 Rust 解析或声称服务端差分通过，完整目标保持。


2026-10-31 查询绑定新增真实 Chrome 同页历史证据：复用既有示例，无生产改动；每端五轮/50 原始帧，实际 Back/Forward 标志为 true，URL 优先于旧控件值、缺省键恢复 x，普通 Pick=c 与会话身份保留。另保留最初 replaceState/跨文档流程及其 about:blank、重连告警、Connecting UI 和 CDP 淘汰限制，不据其 70/60 帧宣称请求全覆盖。八张 JPEG、原始帧/DOM 绑定及五项错误证据拒绝门已验证，相关 Python/矩阵/文档 109 项通过。通用历史、callback、跨页及其他绑定仍开放，130 partial、M3/M5/M7 与完整 Goal 不变，继续阶段提交推送。


2026-10-31 查询百分号解码真实红→绿：%+1 不再经整数解析误变成 U+0001，参数名和值均按固定 Python 参考保留无效转义并处理普通加号。复用既有 app/采集器，16 请求/128 快照/112 URL 写入的全部 240 交错事件对齐，包含 Unicode、无效 UTF-8、重复/空键及完整写回阶段。全目标 Clippy、单元与相关 20 项 Rust 检查通过，工作区 265 项通过但仍明确排除原有两项队列差异；114 项相关 Python/矩阵/文档通过。无新接口/依赖，不据协议结果宣称本次真实 UI 或任意 URL 语法通过；130 partial、M3/M5/M7 与待决方案继续保持，按授权阶段提交推送。


2026-10-31 文本长度反序列化已修正：两类文本控件不再因超长字符串整批拒绝，而按 Python 对默认值/前端输入做码点截断；代码赋值保持原长。八会话/72 轮的全部 144 控件字段/状态投影匹配，涵盖 5/0/无上限/None、组合字符/ZWJ、callback 去重、代码保留及恢复。表单单元验证同批 checkbox/submit 和 callback 看到截断值。全目标 Clippy/格式、相关 21 项检查通过；工作区 267 项通过但仍排除既有两项队列差异，完整冻结参考 1803 项通过且弃用告警为错误。未据原生参考宣称浏览器输入/IME、查询绑定长度或动态上限身份通过；无新增接口/依赖，130 partial 与完整 Goal 保持，继续阶段提交推送。


2026-10-31 keyed text_area 动态上限身份已修正：max_chars 纳入现有身份 extra，text_input 作控制；24 轮/48 控件状态投影和全部 ID 相等关系对齐。覆盖 5→3→5→0→无上限→5，改上限重置、不触发 callback，回到旧 ID 不复活旧输入，同上限仅改默认值仍保留。单元及完整原生差分均先红后绿，全目标 Clippy/格式通过；工作区 269 项通过但仍排除原有两项队列差异，相关 Python/矩阵/文档 124 项通过。未扩大浏览器重挂载、同时代码赋值/改上限、旧 ID 提交或无 key 的验收；通用元素身份方案未改，130 partial 与完整 Goal 保持，继续阶段提交推送。


2026-10-31 同轮输入/上限/代码赋值的来源优先级已修正：身份变化只有在未显式赋值时采用新默认值。两类文本控件的 20 轮/40 投影和 ID 相等关系匹配，callback 先用旧上限解析输入，随后主程序代码赋值可跨新 0/3/5 上限保留并同步。单元与完整原生差分先红后绿，Clippy/格式通过；工作区 271 项通过但仍排除既有两项队列差异，相关 Python/矩阵/文档 129 项通过。共享注册器仅改一处既有回退条件，其他 widget/native 类型、孤立旧 ID、callback 写值、query/fragment/browser 组合仍未据本批关闭；130 partial 与完整 Goal 保持，按授权阶段提交推送。


2026-10-31 文本查询绑定修正：被截断的 URL 值通过现有 pending 更新规范化；历史请求先忽略已注册绑定输入，保留未绑定/未知输入，普通 callback 与 URL 载入顺序不重排。单控件及 Live 对照共 24 轮/74 投影、14 URL 写入匹配，历史绑定 callback 被跳过但 Live 三次 callback 保留。相关单元、两组真 WS、Clippy/格式通过；工作区 275 项通过但仍排除原有两项队列差异，相关 Python/矩阵/文档 134 项通过。另识别 text_area 缺公开绑定入口，已在 architecture.md 准备复用 TextBind 的最小方案并依 AGENTS.md 2 待确认，未实施新方法；浏览器与完整目标/130 partial 继续开放，按授权阶段提交推送。


2026-10-31 重复查询绑定补充原生证据：独立三轮/39 原始帧/七个有序投影确认末值保持 ok 时没有 URL 写入，末值 LONGEST 截断为 LONGE 时才折叠为单值并写回。无前端输入、无 callback，身份保持；现有生产实现匹配，本批仅补采集/冻结/回归。代码检查、一个聚焦单元和 26 项相关查询检查通过（该模块原有队列差异仍排除），137 项相关 Python/矩阵/文档通过；未重跑完整工作区/参考套件。原始 PB 和两种一致篡改拒绝均验证，端口清理回读完成。无新增公共接口，不扩展为任意查询语法或浏览器结论，130 partial、M3/M5/M7 和完整目标保持开放，按授权阶段提交推送。


2026-10-31 文本 None 状态默认值已修正：锁定 SDK 先用原始选项计算身份，再按当前 keyed 空状态将有效默认值设为 None。原生十轮/132 原始帧/23 有序投影先红后绿，三次代码赋空清除绑定参数，后续缺参数 history 恢复 None；空串与字面字符串 None 保持区分。两类现有文本控件按同一 SDK 源码规则修正，单元覆盖空预设/保留/恢复字符串与身份稳定；新增绑定原生差分仅覆盖 text_input，area 公开绑定入口仍待确认。Clippy/格式、聚焦单元、27 项相关查询检查通过；工作区 278 项通过但仍排除原有两项队列差异，142 项相关 Python/矩阵/文档及完整冻结参考 1826 项通过（弃用告警视为错误）。无新接口/模块/依赖，未扩大为真实浏览器或任意空值/身份组合验收，130 partial 与完整目标保持开放，按授权阶段提交推送。


2026-10-31 keyed text_input 校验身份已修正：身份使用调用方原始可选正则，不再使用 email/url 类型自动派生规则。十四轮/181 原始帧/42 有序投影先红后绿；六类类型切换保留输入，显式正则变化重置，同正则仅换提示/类型保留，回到旧 ID 不复活旧值。实际发送的校验正则与提示未改，两个前端 callback 和全部身份相等关系匹配。Clippy/格式、聚焦单元、28 项查询回归通过；工作区 280 项通过但仍排除既有两项队列差异，146 项相关 Python/矩阵/文档通过，未重跑完整冻结参考。无新公共接口/依赖/模块，不扩展为浏览器或无 key 身份验收；130 partial、M3/M5/M7 和完整目标保持开放，按授权阶段提交推送。


2026-10-31 无 key text_input 身份已修正：从现有元组移除 disabled、callback 存在性、ignore_rerun 和标签可见性四类策略字段，宽度/help 继续参与身份。十二轮/155 原始帧/36 有序投影确认策略变化保留输入，宽度/help 变化重置，旧 ID 不复活旧值。首轮重放因适配器未支持 -None 后缀而中断；补齐限于本场景的映射后，修前生产逻辑真实失败、修后全部对齐。Clippy/格式、聚焦单元、29 项查询回归通过；工作区 282 项通过但仍排除原有两项队列差异，151 项相关 Python/矩阵/文档通过，未重跑完整冻结参考。探针不虚构无 key 的原生状态读取，只验返回值、callback、has_key=false 和协议/身份。无新公共接口/模块/依赖，不扩展浏览器或所有身份组合结论；130 partial 与完整目标保持开放，按授权阶段提交推送。


2026-10-31 无 key text_area 布局身份及自动高度已修正：现有身份补入原始宽度/高度/placeholder，显式 key 分支保持 max_chars；未给高度发送 122，collapsed 自动高度 94，但身份仍区分原始 None 与显式 122。二十一轮/272 原始帧/63 有序投影先红后绿，策略变化保留输入、布局/placeholder变化重置，旧 ID 不复活旧值；单元另验证同载荷的自动/显式 122 身份不同。Clippy/格式、聚焦单元、30 项查询回归通过；工作区 284 项通过但仍排除既有两项队列差异，完整 Python 冻结参考 1842 项及相关矩阵/文档 158 项通过（弃用告警视为错误）。无新公共接口/模块/依赖，不扩展为浏览器像素、无效/content 高度、area binding 或所有空选项组合验收；130 partial 与完整目标保持开放，按授权阶段提交推送。
