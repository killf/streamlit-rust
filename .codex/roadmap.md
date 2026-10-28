# Roadmap

本文记录已确认的长期目标、阶段依赖和当前停止位置。用户于 2026-10-27 确认建立长期 Goal 并从 M0 持续执行，随后更新授权为及时提交、推送已验收批次；允许本地实现、验证和按需组队，不发布或部署。主分支更新仍经 PR/MR；创建 PR/MR 和合并分别核对本轮授权。

功能证据仍由[兼容性矩阵](../compatibility/api-compatibility-matrix.json)维护，原有应用旅程由[journey 清单](../tests/journeys/journeys.json)维护。这里不另建逐项通过记录；验收要求见 [acceptance](acceptance.md)，能力边界见 [compatibility](compatibility.md)。

## Long-term goal

交付功能完整、行为可信、易于开发和分发的原生 Rust Streamlit，以锁定的 Python Streamlit 1.66.1 为首个完整兼容目标。生产运行保持原生 Rust，Python 只用于开发参考与差分验证；复用官方前端和协议。

完整性以官方用户文档中的功能、子能力、配置和使用流程为权威范围，不以 Python 导出符号、已捕获页面数、同名函数数或旧旅程通过数作为完整分母。Rust 的接口和实现可以不同；源码只用于核实行为及实现线索，不定义待实现功能。每项适用能力都需要实现、接通、异常与边界验证、文档和必要的浏览器证据。现有 `not_applicable` 理由须复核：缺少 Rust 实现本身不构成不适用。

最终完成要求覆盖功能、行为、用户体验、架构与资源生命周期、Rust API 易用性、测试可信度、性能报告、文档、工程检查、独立 Review 和本地分发。关键行为、公共接口、依赖、架构取舍或验收变化提交用户决定；普通实现细节自主处理。上游版本升级作为后续独立决定，不移动本目标的基线。

## Current focus

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

峰值最多四个代理，包含主代理。主代理负责关键路径、共享接口、唯一共享文件写入和最终验收；独立能力按需并行，紧密耦合逻辑归同一代理。参考测量先于兼容实现，稳定交付交给只读 Reviewer 审查。

模型池沿用已批准配置：复杂核心和参考协议使用 Sol/high，普通实现 Sol/medium 或 high，界面和文档 Terra/medium，明确检索 Luna/medium，独立 Reviewer Sol/high。主代理模型由客户端控制，无法核验时报告，不宣称配置已生效。不使用固定满编团队，也不允许子代理继续委派。

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
