# 使用 Rust 构建数据应用

本指南按使用场景介绍当前可运行的路径和目标体验。项目仍处于早期阶段：示例能运行或某个场景已有验证，并不意味着完整兼容 Streamlit。Python 参考运行锁定在 1.66.1；API 文档页面当前观察到的标签为 1.66.0，概念和部署指南是未版本化实时文档。功能边界和证据以[兼容矩阵](../../compatibility/api-compatibility-matrix.json)各条目的 `compatibility_scope` 和 `limitations` 为准。

| 场景 | 状态 | 依据与边界 |
| --- | --- | --- |
| 输入控件、CSV 上传、筛选、表格和图表 | 当前可用；兼容性部分验证 | [data_app](../../streamlit/examples/data_app.rs)；矩阵 `st.file_uploader`、`st.dataframe`、`st.bar_chart`。只覆盖已测组合。 |
| 表单、会话状态和普通重跑 | 当前可用；部分验证 | 矩阵 `st.form`、`st.form_submit_button`、`st.session_state`。状态在内存中，恢复有边界。 |
| 单独编辑表格 | 部分验证 | 矩阵 `st.data_editor`；[dataeditor 示例](../../streamlit/examples/dataeditor.rs)覆盖单元格编辑和新增行，不能代表所有类型与操作。 |
| 选择行 → 详情 → 编辑 → 追加 | 主流程与筛选部分验证 | csv_workbench 已测编辑、应用、追加及下载；来源替换已按显式清空方案验证，未完成整体验收。 |
| 布局、导航、组件、流式文本 | 部分验证 | 矩阵 `st.navigation`、`st.components.v2.component`、`st.write_stream` 等；具体入口见下文。 |
| 配置、认证、主题与部署 | 待完成或待设计 | 存在启动配置和前端资源部署路径；完整配置、认证和主题能力尚无足够证据。 |

## 构建并启动

在仓库根目录使用 Rust 工具链和 `protoc` 构建。项目尚未声明或验证最低支持 Rust 版本（MSRV）。先用 `rustc --version`、`cargo --version` 和 `protoc --version` 检查本机工具；如果 `protoc` 不在 PATH，可从 [Protocol Buffers 官方发布页](https://github.com/protocolbuffers/protobuf/releases)获取适合本机平台的编译器并解压到本地目录。

当前 Windows 工作区已经校验并解压了 `protoc-36.2-win64.zip`，路径为 `target/tools/protoc-36.2/bin/protoc.exe`。下面的命令仅在当前 PowerShell 会话指定它；其他机器使用自己实际解压得到的路径。`target/` 是本地缓存，不随仓库分发：

```powershell
$env:PROTOC = (Resolve-Path 'target/tools/protoc-36.2/bin/protoc.exe').Path
cargo run --example quickstart --locked
```

打开 <http://127.0.0.1:8503/>，修改选择框、滑块和复选框，页面显示对应值。运行不需要 Python。另一个示例使用 8501 端口：

```powershell
cargo run --example data_app --locked
```

打开 <http://127.0.0.1:8501/>；若端口已被占用，先确认是否是自己启动的另一个示例。开发命令从仓库根目录运行，以便找到官方前端资源。分发程序时，构建后的可执行文件需要完整 `www/` 目录或显式资源目录；具体步骤见[现有指南](README.md#run-an-installed-executable-from-any-directory)。这条路径不等于生产部署、认证或安全配置已经完成。

## 上传、筛选和提交

1. 在 `data_app` 上传[示例 CSV](../../tests/fixtures/csv/sales_basic.csv)。文件应为 UTF-8，包含小写 `amount` 和 `region` 列；`category`、`channel` 可提供更多分组选择。
2. 调整 **Group by**、**Include unknown region** 和 **Minimum amount**，页面重新计算并展示分组表格及柱状图。将最低金额设为 200 可看到无匹配行；恢复为 0 可再次显示结果。
3. 在 **Interaction** 输入 **Note**，点击 **Apply note** 后才提交；单独输入不会触发提交。改变筛选条件或点击 **Pulse** 后，上次提交的 Note 和上传数据在当前会话中保留。要清空 Note，清空输入后再次提交。
4. 无法解析的金额会被排除并产生警告；格式错误或非 UTF-8 文件显示错误。选择有效文件可继续使用。只有表头的文件会提示没有数据行。

此示例的聚合和舍入是应用自身规则，不是所有 Streamlit 应用的通用行为。单文件的替换与删除已随 CSV 工作台与上传回归验证；多文件模式见下节。会话过期和安全边界仍未完整验证；不要将当前上传端点视为面向不可信用户的生产认证边界。参见官方[文件上传](https://docs.streamlit.io/develop/api-reference/widgets/st.file_uploader)、[表格](https://docs.streamlit.io/develop/api-reference/data/st.dataframe)、[表单](https://docs.streamlit.io/develop/api-reference/execution-flow/st.form)及矩阵对应条目。

## 多文件上传（Multiple 模式）

`FileUploaderOptions::new("标签").multiple_files()` 开启多选（返回 `UploadedFiles::Multiple(Vec<UploadedFile>)`，未选时为空 vec）；`directory()` 为目录选择（同样返回多个文件）。真实前端一次会话内可为同一控件追加多个文件：前端为整批文件一次性请求上传地址并逐个 PUT，控件状态携带全部文件的 `uploaded_file_info` 列表；移除某个文件只从列表中去掉对应项，其余保留——[uploads 示例](../../streamlit/examples/uploads.rs)演示单/多两个上传器与返回的名称/大小/字节预览。

多选上传已按双端冻结参考验收（真实 Chrome 上传两个文件、移除其一、清空的完整流程，见[参考](../../tests/reference/reference-browser/uploads-multi/README.md)与 Rust 对照证据）：wire 元素 `multiple_files=true`、批量地址请求、逐文件状态与返回值、移除语义在 Python 1.66.1 与 Rust 一致。

**大小限制是两道防线**（均实测对齐）：`max_upload_size_mb(1)` 走 wire 元素由官方前端在上传前静默拦截超限文件（无 PUT、无提示、报告不变，见[限制参考](../../tests/reference/reference-browser/uploads-limit/README.md)与 Rust 对照）；服务端另有独立字节上限 `StreamlitServer::with_max_upload_size_mb`（默认 200 MiB，同 `server.maxUploadSize`），超限 PUT 答 **413** 且不存储。**目录模式**是 Python 1.66.1 之外的 Rust 扩展（其 API 无目录参数）：实测锁定前端对 `accept_directory` 正确渲染目录选择器（input 带 `webkitdirectory`），但完整目录流需真实 OS 选择器与 `webkitRelativePath`，headless 采集无法完成，返回值路径未验证、不作为可用声明。断线过期（`server.disconnectedSessionTTL`，默认 120 秒，同 Rust `with_disconnected_session_ttl`）与并发上传竞争已按[协议参考](../../tests/reference/reference-browser/uploads-lifecycle/README.md)验收：并发 PUT 互不互斥、同 URL 竞争恰存一次完整写入、断线超过 TTL 后 PUT 400 / DELETE 204；更高并发度与多写者损坏窗口不冒称已测。

## CSV workbench：编辑会话工作副本

**主流程、筛选与来源替换已验证。** [csv_workbench 示例](../../streamlit/examples/csv_workbench.rs)与现有销售统计 `data_app` 分开。从仓库根目录运行 `cargo run --example csv_workbench --locked`，打开 `http://127.0.0.1:8545/`。已测 20 阶段主流程、13 阶段筛选流程和来源替换流程（坏文件、空表头、有效替换、移除上传与显式清空），含实际下载与双会话；[证据和局限](../../tests/browser/rust-csv-workbench/README.md)不代表全部模式、数据类型或完整 CSV 验收。

例如，将以下内容保存为 UTF-8 CSV 后上传：

```csv
item,region,quantity
book,north,10
game,south,20
```

1. 在 **CSV workbench** 的 **Upload CSV**（key `wb-upload`）上传一个 CSV。工作台按文本处理每个单元格，不推断数字或日期类型；保留原列及顺序，支持 UTF-8、BOM 和 CSV 引号内容。空列名、重复列名、结构或编码错误会显示错误。上传器的空状态（真实前端替换单文件时会先出现）只清除选择、保留工作副本；移除已选文件同样保留副本。显式 **Clear working copy** 按钮才清空工作副本并重置会话。
2. **Filter column** 默认选择首列；**Filter enabled** 默认关闭。启用后，**Exact value** 按文本精确匹配，空字符串也是有效的匹配值。**Count by** 默认首列，计数图统计当前筛选结果。**Rows** 展示完整筛选结果，初始无选择；排序或筛选后的行选择映射回对应的原始明细位置。
3. 在 **Rows** 选一行，修改单行 **Detail draft**。只有点击 **Apply** 才将草稿应用到当前会话的工作副本，并更新表格和图表；单独编辑草稿不会改动工作数据。筛选变化清除旧选择和详情草稿，选行变化清除旧详情草稿；来源、工作数据版本和视图变化后，过期草稿不能写入其他行。
4. 在独立的 **New rows draft** 动态表中填写新行，点击 **Append** 后才追加。重复行保留，空单元格导出为空 CSV 字段；新增草稿在应用或切换有效来源前保留。成功 **Apply** 或 **Append** 后更新数据版本并重置选择与草稿。
5. **Download CSV** 下载修订后的 `workbench.csv`；原上传内容不变，示例不写文件或数据库。**Ordinary rerun** 可观察当前会话状态。每个浏览器会话有独立工作副本，普通重跑不应混入其他会话的数据。

来源替换规则已定（2026-10-28 采纳显式清空方案）：上传器空状态仅清选择、保留工作副本，坏文件显示错误并保留上次有效副本（界面标记仍在显示旧来源），显式 **Clear working copy** 按钮清空副本并重置。Rust 与 Python 参考按同一契约实现，来源替换全流程（五个坏文件逐个替换、空表头、有效替换、移除上传保留副本、显式清空、清空后重跑）已冻结为双端真实前端证据。多文件上传、上传端点安全边界与全部坏输入枚举仍未验证；无匹配、排序映射、下载字节及会话隔离的证据见上述子流程。

## 选择、查看、编辑和追加：目标体验

目标流程是：在结果表中选择一条记录，查看其详情，修改并确认，再将新数据追加到已有视图；重跑时应明确保留哪些选择和编辑结果。空选择、筛选后所选记录消失、编辑失败、重复提交和数据来源更新等行为仍待设计和验证。

现有销售 `data_app` 没有行选择或这一整套交互；独立 `csv_workbench` 按上节实现和验证，来源替换规则已定（显式清空）。官方已在 1.58.0 移除 `element.add_rows`，它不是本项目 1.66.1 的兼容缺口；工作台采用应用更新数据再渲染，没有新增 Rust 追加扩展。[dataeditor 示例](../../streamlit/examples/dataeditor.rs)是独立演示，可通过 `cargo run --example dataeditor --locked` 在 8541 端口查看编辑与新增行。编辑器每轮发送原始输入表，并返回应用编辑后的 `RecordBatch`；调用方可像示例一样通过 `st.dataframe` 单独显示或继续处理返回值。它不会自动保存或改写上传的 CSV。

已复现不可空字段遇到空行时的 schema 冲突，并选择按编辑结果放宽：仅实际产生 null 的结果列设为 nullable，未产生 null 的列保留输入的可空标记，原始输入表不变。调用方须读取返回表的 schema，不能假定它仍与输入完全相同。整数列遇 null 时已有的 Float64 转换规则继续适用；填齐新增行后，每轮仍基于原始输入重新应用编辑。该规则已有冻结输入回归、真实 WS 和 Rust 官方前端四步交互验证。删除行、其他编辑模式和回调的覆盖仍有限。参考官方[数据编辑器](https://docs.streamlit.io/develop/api-reference/data/st.data_editor)与矩阵 `st.data_editor`、`st.dataframe`。

编辑器对非法正删除位置通过既有 `DataError` 返回，调用方可显示错误并接收后续有效编辑，原输入表不被修改。已用冻结非负输入及真实 WS 错误后恢复核验，不对异常位置做裁剪或自动改选；负位置及完整恶意编辑输入尚未获得兼容结论，范围见[错误与恢复证据](../../tests/reference/reference-browser/dataeditor-invalid-rows/README.md)。

选择接口正按[单入口设计](../../.codex/architecture.md#dataframe-selection-and-data-updates--proposal)实现与验证。用户已澄清无需保留旧 Rust 返回类型，因此使用同一个 `dataframe` 显示并返回选择，不另增兼容入口。下列基本用法已编译验证；完整参数和组合仍限于已测范围：

```rust
use streamlit::{DataApi, DataframeOptions, DataframeSelectionMode, OnSelect, Streamlit, StreamlitApi};
use streamlit::data::{DataError, RecordBatch};

fn show_selection(st: &Streamlit, batch: &RecordBatch) -> Result<(), DataError> {
    if let Some(event) = st.dataframe(
        DataframeOptions::new(batch)
            .key("orders")
            .on_select(OnSelect::Rerun)
            .selection_mode(DataframeSelectionMode::SingleRow),
    )? {
        for row in event.selection.rows {
            if row < batch.num_rows() {
                st.dataframe(&batch.slice(row, 1))?;
            } else {
                st.write("所选位置已不在当前数据中");
            }
        }
    }
    Ok(())
}
```

默认忽略选择时返回 `None`；启用选择后返回 `Some(DataframeState)`，其中选择可以为空。行位置对应本轮输入表，不是浏览器排序后的视觉位置或业务记录 ID。换表后位置可能越界，读取详情前需要检查；框架不会静默替应用选择其他记录。编辑结果的保存、记录身份及追加策略属于应用后续流程，不会自动改写上传的 CSV。

`SingleRowRequired` 的首次非空表默认首行，真实前端的清除尝试不触发重跑。空协议输入现已在回调前按已注册的行数正规化，返回与 keyed state 保持一致。动态换表时输入先于本轮应用代码执行，因此从空表恢复当轮仍可能返回空选择，下一次输入才使用新行数；同样，切成空表当轮也可能保留旧位置。应用仍须检查位置有效性。程序赋值的 partial keyed 原值另行保留；[八阶段协议证据](../../tests/reference/reference-browser/dataframe-required-protocol/README.md)不代表浏览器允许清除必选行。

最小流程见 [dataframe_selection 示例](../../streamlit/examples/dataframe_selection.rs)：在仓库根目录运行 `cargo run --example dataframe_selection --locked`，打开 `http://127.0.0.1:8544/`。选择一行后查看详情、编辑并在下方查看返回结果；**Ordinary rerun** 用于观察选择是否保留，**Selection state** 显示返回状态。示例使用固定的三行数据，所选位置只在此固定输入内作为编辑器 key 的一部分；编辑结果仅展示或供应用处理，不写文件或数据库，也不会自动持久化源数据。该示例已通过构建、单元/WS 回归及[六阶段 Rust 官方前端验证](../../tests/browser/rust-dataframe-selection/README.md)，不代表 CSV 应用已经接通选择、编辑和追加。

这条流程所需的 [Python 选择参考](../../tests/reference/reference-browser/dataframe-selection/README.md)已单独冻结，Rust 回归直接复用。参考中，排序选择指向输入位置；同 key 换成更短的表时旧行位置可能仍保留；程序赋值的部分 keyed state 与补齐后的返回值也可能不同。这些边界需结合本批 Rust 验证结果判断，不能仅凭参考证明完整兼容。

## 会话、重跑和错误

交互通常使整个应用函数重新执行。每个浏览器会话有独立的内存状态；普通重跑保留状态，断线后在服务端仍保留该会话时可以恢复。刷新页面或另开标签页创建新会话，服务重启后内存状态消失。当前默认断线保留 120 秒，这是本实现的本地策略，并非对上游默认值的兼容承诺。运行 `cargo run --example counter --locked` 可观察计数与重跑。

重连已有会话会接管其连接；接管等待旧运行及其输出发送结束，其他会话仍可运行。旧连接退出不能使新连接的会话过期。断线到期清理由后续连接或上传会话查询触发，没有后台定时清理；如果应用自行保留 `SessionState`、上传或缓存资源的克隆句柄，这些句柄也会延长相关对象的存活期。

已用 16 个真实 WS 会话在两个 worker 配置下完成并发重跑和关闭确认后的部分重连，共 72 次运行；正在运行时的接管仍由独立的旧运行暂停回归检查。另有四轮、每轮 32 个会话的到期测试，观察无外部强引用时应用值、上传容器及缓存资源对象释放。这些检查不证明应用函数必定同时执行、进程 RSS 下降、长时无泄漏或并发容量；[当前验收范围](../../.codex/acceptance.md#current-session-boundary-validation-2026-10-27)保留这些局限，运行时保留策略未改。

普通服务端重跑应保留本轮查询参数写入；`switch_page` 切换页面时清空普通查询参数，目标页面后续的新写入再随普通重跑保留。两条路径使用不同的状态边界，不能用旧浏览器请求覆盖目标页的新状态。

同一次运行的首个 `rerun` 或 `stop` 信号决定该轮结束方式，后续信号不会覆盖它；普通服务端重跑保留本轮 `query_params.set` 写入。两条边界均有真实 WebSocket 回归，切页清空与目标页重跑的组合也有验证。详情参见矩阵 `st.rerun`、`st.stop`、`st.query_params`、`st.session_state` 和官方[会话状态](https://docs.streamlit.io/develop/api-reference/caching-and-state/st.session_state)。

当前 Rust 调用发出运行控制信号，并抑制后续 Streamlit 元素和状态写入；它不会自动跳出任意 Rust 辅助函数或取消普通 Rust 计算。调用后应显式返回，例如在下文的 `Result` 辅助函数中使用 `st.stop(); return Ok(());`；`st.rerun()` 同样处理。多层调用的自动控制流传播仍需单独接口设计。

可失败的控件调用应传播错误，并在应用入口统一处理，例如 [quickstart](../../streamlit/examples/quickstart.rs) 中的实际模式：

```rust
use ::streamlit::*;

fn render(st: &Streamlit) -> Result<(), WidgetError> {
    let minimum = st.slider(("Minimum amount", 0_i64, 0..=200))?;
    st.write(format!("Minimum amount: {minimum}"));
    Ok(())
}
```

入口可用 `if let Err(error) = render(st)` 显示或记录错误；完整启动代码见示例。当前宏入口接受返回单元类型的函数，因此可在返回 `Result` 的辅助函数中使用 `?`。重复控件 key 会显示框架异常；其他参数错误应由应用处理。Rust 规范禁止 `.unwrap()`，包括示例和测试，也不能机械换成 `.expect()` 或通用 panic 包装。当前既有用法迁移已通过全目标 Clippy、工作区与示例测试；以后改动仍需按新规范检查。

## 更多应用入口

以下示例提供已有能力的入口，功能和参数只在各自证据范围内得到验证：

| 需求 | 示例或指南 | 官方文档与矩阵条目 |
| --- | --- | --- |
| 布局、侧栏与容器 | [layouts](../../streamlit/examples/layouts.rs) | [布局](https://docs.streamlit.io/develop/api-reference/layout)；各布局条目 |
| 多页面导航 | [navigation](../../streamlit/examples/navigation.rs) | [导航](https://docs.streamlit.io/develop/api-reference/navigation/st.navigation)；`st.navigation` |
| 输入与表单 | [widgets](../../streamlit/examples/widgets.rs)、[forms](../../streamlit/examples/forms.rs) | [控件](https://docs.streamlit.io/develop/api-reference/widgets)、`st.form` |
| 流式文本 | [writestream](../../streamlit/examples/writestream.rs) | [流式输出](https://docs.streamlit.io/develop/api-reference/write-magic/st.write_stream)；`st.write_stream`，当前证据限文本 |
| 自定义组件 | [componentv2](../../streamlit/examples/componentv2.rs) | [组件](https://docs.streamlit.io/develop/concepts/custom-components)；`st.components.v2.component`。局部 JSON 状态的默认字段补齐已有冻结参考数据与真实 WebSocket 回归。 |
| 缓存 | [cache](../../streamlit/examples/cache.rs) | [缓存](https://docs.streamlit.io/develop/concepts/architecture/caching)；`st.cache_data`。当前缓存按会话隔离；两层数据/资源缓存的嵌套输出已有冻结参考与 WebSocket 回归。 |

页面配置已有部分接口；完整配置体系、秘密管理、身份认证、主题和生产部署的体验仍待盘点、设计和验证。请参考官方[配置](https://docs.streamlit.io/develop/concepts/configuration)、[认证](https://docs.streamlit.io/develop/concepts/connections/authentication)、[主题](https://docs.streamlit.io/develop/concepts/configuration/theming)及[部署](https://docs.streamlit.io/deploy/concepts)。矩阵中历史 `not_applicable` 条目正在重新审视，不能据此推断长期目标排除这些场景。

## 组件的默认状态与局部更新

组件先通过 `ComponentV2` 注册内容，再通过 `component_v2` 挂载；使用固定 `.key("greeter")` 区分实例。`ComponentMount::default_state` 提供默认状态对象，挂载返回 JSON 状态；有 key 时，还可用 `session_state().get::<serde_json::Value>("greeter")` 读取组件状态。

在已经注册的 `greeting` 组件上，可这样挂载并读取状态：

```rust
let state = st.component_v2(
    &greeting,
    ComponentMount::new()
        .key("greeter")
        .default_state(serde_json::json!({"value": "hi", "untouched": 7})),
)?;
let stored = st.session_state().get::<serde_json::Value>("greeter")?;
```

局部更新时，默认 `{"value":"hi","untouched":7}` 收到前端 `{"value":"bye"}` 后，返回值和 session state 都应为 `{"value":"bye","untouched":7}`，后续普通重跑继续保留该状态。缺失字段补默认值，前端提供的字段优先；该规则在对象顶层逐键应用。显式 `null` 是前端提供的值，也会保留。

Python 1.66.1 的[冻结输入输出](../../tests/reference/reference-browser/componentv2-state/state-cases.json)覆盖首次加载、局部更新、普通重跑与显式 null，Rust 通过真实 WebSocket 对照返回值和 keyed session state。额外的 Rust 空输入重跑也保留该状态；嵌套对象、多个实例和回调副作用尚未由这组数据验证。

这一使用场景来自官方 [ComponentRenderer](https://docs.streamlit.io/develop/api-reference/custom-components/st.components.v2.types.componentrenderer) 的默认状态与 keyed session state 约定；页面标注 1.66.0，实际参考运行固定为 1.66.1。Rust 使用上文的挂载与状态读取接口。

## 嵌套缓存中的界面输出

运行 `cargo run --example cache_nested --locked` 并打开 `http://127.0.0.1:8543/`。点击 Again 后，数据缓存和资源缓存的内外输出应完整保留，返回值均为 43。

缓存闭包可以调用另一个缓存，并使用现有 `st.write` 等方法输出界面：

```rust
let value = st.cache_data("outer").call(21, |n: i64| {
    st.write("outer-before");
    let doubled = st.cache_data("inner").call(n, |value: i64| {
        st.write("inner");
        value * 2
    });
    st.write("outer-after");
    doubled + 1
});
```

外层命中时，仍按原顺序显示 outer-before、inner、outer-after，返回缓存结果，并跳过计算闭包。外层未命中而内层命中时，内层输出也应包含在外层后续的重放中；调用位置变化后，输出与后续元素应落在正确的页面位置。`cache_resource` 的界面重放也遵守这一规则，返回值仍为共享 `Arc`。

两层嵌套已对照 Python 1.66.1 的[冻结输入输出](../../tests/reference/reference-browser/cache-nested/cache-cases.json)验证：同时覆盖内外未命中、外层未命中而内层命中、外层命中及位置平移。只有最外层未命中发送临时 spinner 清除消息；缓存命中只重放持久输出。该组数据未验证异常、更多递归层或容器组合。当前 Rust 缓存仍按会话保存，使用不同名称标识不同缓存函数。

依据官方 [缓存静态元素](https://docs.streamlit.io/develop/api-reference/caching-and-state/st.cache_data#static-elements) 的重放约定；该页标注 1.66.0，与本项目的 1.66.1 参考运行版本分别记录。

## 同形状数据的图表更新（已采纳内容命名方案 A）

运行 `cargo run --example chartlibs --locked`，打开 `http://127.0.0.1:8528/`。示例的 **Change Vega data** 仅将 generic Vega-Lite 图的 a 从 3 切换到 8、b 保持 7，再切回；其他图保持原数据。曾用真实按钮复现官方 1.66.1 前端的漏刷：数据变为 8、可见柱高仍为 3，普通重跑也不恢复（[失败基线](../../tests/browser/rust-vega-refresh-before/README.md)保留，Python 参考同样漏刷）。

已采纳方案 A（2026-10-28）：`st.vega_lite_chart` 的内联 `data.values` 现与 `altair_chart` 一致——Arrow 数据以内容命名（IPC 字节的 md5）放入 `datasets`，spec 以 `data: {"name": …}` 引用该名称。同形状值变化改变数据内容即改变 dataset 名与 spec，官方前端的值无关判定也能看到新数据集；真实按钮 3→8→重跑→切回 的可见柱高已随数据刷新（[修复后证据](../../tests/browser/rust-vega-refresh-after/README.md)）。这是相对 Python 1.66.1 顶层 `data` 承载的有限 wire 差异：逻辑字段、metadata、行序和值仍严格一致，spec 其余字段不变；URL、自带 `data.name` 或嵌套 spec 不自动改写、无数据时行为不变。代价：spec 变化会重建 Vega view，图内缩放/选区等交互状态可能重置；大数据 hash 随 IPC 线性计算。

## 下载文件名和类型

下载字节数据时，用 `DownloadButtonOptions` 指定文件名及 MIME，例如 `.file_name("数据 é.csv").mime("text/csv")`。缺省或空文件名按类型生成 `streamlit_download` 加后缀，已测特殊文件名采用 UTF-8 扩展参数编码；文本类型补 charset，已有 charset 不重复。十个冻结公开输入已通过 Rust 真实 WS/HTTP 精确对照，见[参考范围](../../tests/reference/reference-browser/download-boundaries/README.md)。显式带 charset 或未知 MIME 的 URL/默认名没有后缀，这沿用原始 MIME 映射；响应头补 charset 不改变文件内容地址。当前字节接口不代表已实现 Python 字符串/文件对象自动推断 MIME 或延迟生成文件。

运行 `cargo run --example buttons --locked`，打开 `http://127.0.0.1:8523/`。**Save default bytes** 和 **Save Unicode CSV** 已通过[真实浏览器保存验证](../../tests/browser/rust-download-boundaries/README.md)，分别落盘为 `streamlit_download.bin` 与 `数据 é.csv`，内容均为合成 CSV 字节。这两个按钮配置 `ignore_rerun(true)`；前端加载时 Fetch 文件，点击后保存，不将它描述为点击后重新取文件。其他标点组合、所有 MIME 映射和下载生命周期仍未完整验收。

## 原生输入与未编辑结果

`RgbaImage` 的尺寸必须为正，像素缓冲必须恰好容纳 `width × height × 4` 字节。`st.image` 对无效输入记录错误并跳过该元素；现在用 checked 运算拒绝无法表示的长度，避免在这之前 panic 或把溢出长度绕回零，没有新增图片大小限额、接口或错误策略。无效图片不占用元素位置，后续有效图片仍正常输出。底层 `media::png_encode` 仍要求通过 `RgbaImage::valid` 的输入，这次不改变它的返回接口或无效输入契约。

`data_editor` 没有实际编辑时，直接复制有效 batch，保留行数、字段及 schema 元数据，并共享 Arrow 不可变缓冲；不再重建 schema 或用 expect 把错误变成 panic。零列 batch 的内部无编辑复制保留 0/2 行，公开显示转换现按下节虚拟 RangeIndex 方案输出零列 IPC。实际编辑后的 schema/index 元数据策略也不据此声明完成。验证使用 Rust 原生输入，不为这些 Rust 所有权/算术边界重采旧 Python 数据。

## 零列表格：虚拟 RangeIndex 呈现（已采纳 A）

零列不等于零行：Arrow batch 可以没有物理列，却有显式 0/2 行。冻结的 Python 1.66.1 参考确认 dataframe、固定行编辑器（含 disabled）和显示索引的 table 接受这些输入；但首次真实前端中，直接 Arrow 两行零列的 dataframe 显示 `Error during cell creation`、table 只剩空框——wire 缺少索引描述符时前端格子创建失败，而携带 RangeIndex 元数据的编辑器正常显示索引 0/1。

Rust 已采纳方案 A：显示转换保留真实行数并合成虚拟 RangeIndex 元数据，零列 dataframe、`table(hide_index=false)` 与编辑器一样显示行号 0/1。这是对直接 Arrow 上游可见错误/空框的明确修正，不冒称与 Python 1.66.1 wire 逐字段等价；原错误参考仍保留在[冻结证据和局限](../../tests/reference/reference-browser/zero-columns/README.md)。默认 `table`（隐藏索引）没有可见列，保持空框呈现。

运行 `cargo run --example zero_columns --locked`（默认 `http://127.0.0.1:8580/`）：**Two rows**（key `zero-two`）在 0↔2 行间切换，**Ordinary rerun** 触发普通重跑；dataframe、enabled/disabled 两个固定行编辑器和显示索引的 table 走同一 0→2→重跑→0 流程，Rust 真实前端对照见[rust 采集证据](../../tests/browser/rust-zero-columns/README.md)。Python 9＋3 静态单元参考没有重采，也没有把原错误轨迹改成成功；动态行编辑、任意 schema/metadata 组合仍未验证。

## 布局与流式参数

冻结参考实测的参数面（[参考](../../tests/reference/reference-browser/layout-params/README.md)，Rust 侧 14/14 块发射逐字一致）：`ExpanderOptions::kind(ExpanderKind::Compact)`（Python `type="compact"`，默认带边框）；`PopoverOptions` 的 `kind(PopoverKind::Primary)`、`help`、`disabled`、`use_container_width(true)`（由块级 stretch 宽度承载）；`TabsOptions::default_tab("Beta")`——**接受标签而非索引**（Python 传索引抛错；Rust 未知标签记日志忽略，为记录差异）；`DialogOptions::width(DialogWidth::Large)`（`width: LARGE`，两段发射含 `is_open`）；status 的 `update(label, state, expanded)`——**未传 expanded 时重发不带该字段**（None 清除，实测语义）；`ToastOptions::duration`（秒：short=4、long=10、毫秒整数按原值）。spinner `show_time` 在原生 WS 无可观测增量，Rust 未提供该参数不冒称等价。

**列**（[columns 参考](../../tests/reference/reference-browser/columns-params/README.md)，22/22 块逐字一致）：`ColumnsOptions` 的 `gap(Gap::Small/Medium/Large)`、`border(true)`、`vertical_alignment(Top/Center/Bottom)` 与加权 spec（`vec![3.0, 1.0]` → 权重 0.75/0.25，**f64 精度**：三等分 = 0.3333333333333333）。实测 wire：容器的 gap 同时复制到每个列块；容器固定 scale 1.0 / wrap / justify UNDEFINED / align STRETCH。`Gap`/`VerticalAlignment` 自 crate 根导出。

## 运行配置面（显式旋钮）

Rust 不解析 `config.toml`（矩阵既有边界：Python 的 TOML 注册表不是兼容目标）；运行项全部是**显式**的服务器构建器与宏参数，无隐藏配置文件。完整清单：

| 运行项 | 设置方式 | 默认 | 证据 |
| --- | --- | --- | --- |
| 监听地址与端口 | `StreamlitServer::new(entry, host, port)` 或 `#[main(host = …, port = …)]`（宏默认 `0.0.0.0:8501`） | — | 全部真实 WS 回归（每项均以配置地址直连）；宏参数见 `main-macro` 检查 |
| 静态前端目录 | `.with_static_dir(path)`；解析顺序 **builder > `STREAMLIT_STATIC_DIR` 环境变量 > 可执行文件旁的 `www/`**，取第一个有效项，无效即启动失败不回落 | 旁置 `www/` | `static_assets`（builder/env/exe 三级优先级与失败边界 + 真实进程 HTTP/WS 迁移） |
| 断线会话保留 | `.with_disconnected_session_ttl(Duration)`，同 `server.disconnectedSessionTTL`（默认 120 秒实测同值） | 120s | tests/reference/reference-browser/uploads-lifecycle/README.md + streamlit/tests/runtime/uploads.rs |
| 上传大小上限 | `.with_max_upload_size_mb(mb)`，同 `server.maxUploadSize`（默认 200MiB；超限 PUT 413 不落存储） | 200 | tests/reference/reference-browser/uploads-limit/README.md + streamlit/tests/runtime/uploads.rs |
| 请求头白名单 | `.with_request_headers(RequestHeaderAccess)`（Standard/Selected/All；`st.request_context()` 可见面） | Standard | tests/reference/reference-browser/context-headers/README.md + streamlit/tests/runtime/request_context.rs |
| 认证器 | `.with_authenticator(Arc<dyn RequestAuthenticator>)`（连接建立时以全部握手头调用；`HeaderAuthenticator` 为假凭据） | 无（匿名） | tests/reference/reference-browser/user-cookies/README.md + streamlit/tests/runtime/request_context.rs |
| 日志 | `RUST_LOG` 环境变量（宏与手动入口的 env_logger；默认过滤等级不变） | info | 运行日志章节（本文件）+ .codex/acceptance.md 的 WS 日志验收 |

配置在构建时一次确定：`with_disconnected_session_ttl` 重建会话存储，不作热重载；各旋钮互不隐藏——改其一不影响其余默认。环境变量仅 `STREAMLIT_STATIC_DIR` 与 `RUST_LOG` 两项，均为开发便利而非必需。上表证据链接由离线检查 `test_config_surface_docs.py` 守护（表格随代码演进，失效即红）。

## 运行日志

`#[main]` 沿用现有 `env_logger` 初始化和 `RUST_LOG` 配置，例如 `RUST_LOG=streamlit=info` 或 `streamlit=debug`；本批不改变默认过滤等级。WS 日志现只记录传输阶段、消息种类标记/序号、字节数、运行耗时与错误原因，不再展开完整输入/输出 protobuf、原始文本帧或关闭描述。Info 保留每轮汇总，逐帧摘要位于 Debug；`elapsed_ms` 是本轮执行与发送调度耗时，不包含运行锁排队、客户端收取或页面呈现。

独立 test 子进程的真实 WS 合成回归已验证两轮控件交互、非法消息后的心跳恢复及关闭应答原样保留，五类合成载荷标记不进入日志；仍有错误诊断和摘要字段，未靠关闭全部日志通过。应用自行记录的内容、第三方日志和完整认证/安全范围不在这项保证内。命令为 `cargo test -p streamlit --lib websocket_diagnostics_do_not_expand_application_payloads --locked -- --nocapture`；全局 logger 仅在自有子进程初始化，不影响其他测试。

## 音视频播放参数与字幕

`AudioOptions`/`VideoOptions` 支持 `start_time`/`end_time`（秒，小数按 Python `int()` 截断到整秒）、`loop_(true)`、`autoplay(true)`（自动播放的播放器携带 `$$ID-<32hex>-None` 元素身份）、`muted`（仅视频）与 `subtitle("en", "<VTT/SRT 文本>")`（文本经校验存为 `.vtt` 媒体轨；SRT 按参考规则转换）。`format` 即 mime 参数：实测 `audio/wav` 地址带 `.wav` 后缀、`audio/x-wav` 为**裸地址**；同字节内容双端共享同一 URL（内容寻址）。非法字幕文本（非 VTT/SRT）按参考渲染 `StreamlitAPIException` 异常元素而非播放器。见[冻结参考](../../tests/reference/reference-browser/media-params/README.md)与 WS/离线回归；YouTube/URL 输入、多音轨、alt 未实现未测。

## 媒体范围读取

音视频与下载文件共用 `/media/` 路由。有效单范围（包括 `bytes=-N` 后缀）返回 206 和对应字节，非法、越界、多范围或空文件的非空 Range 返回 416、`Content-Range: bytes */N` 与 `Invalid range`；无 Range 或空 header 仍返回完整 200。已用 [27 个冻结公开请求](../../tests/reference/reference-browser/media-range/README.md)精确核对 Rust 的状态、头与字节，修复了原先许多情况直接返回整文件的问题。后缀或终点大于文件长度时按有效区间返回；已测的大小写、空白、加号、下划线数字和无连字符形式按参考解释，没有新增应用选项。

调用方无需新增选项；文件名、MIME 和内容地址沿用原下载/视频配置。这里验证 HTTP 范围响应，不将它描述为已完成浏览器拖动定位或完整播放器兼容。

媒体注册后保存在进程内存中，当前没有自动淘汰。同一内容的完整响应和范围响应现在共享不可变字节，调用方式和响应内容保持；注册时仍复制调用方的输入，公开 `media::get` 仍返回独立的 `Vec<u8>`。同一 8 MiB 文件的 16 个完整及 16 个范围响应构造测量中，完整响应的独立缓冲从 16 份降为一份；[本机三次对照数据](../../tests/performance/media-storage.json)只衡量进程内路由构造与持有成本，不证明网络零复制、慢连接容量或长期资源回收，也不改变媒体存活时间。

复测先执行 `cargo test -p streamlit --lib large_media_responses_keep_full_and_range_bytes_alive_independently --locked -- --nocapture`，测试输出实际 test executable 路径和构造测量。Windows 上可用 Python 标准库执行 `python tools/measure_media_storage.py <该 executable 路径> after target/checks/media-storage-local`，单独运行三次并保存进程内存观测和原始输出；路径取当次 Cargo 输出，不固定文件后缀。采样请求间隔为 5 ms，调度可延长它，观测最大值可能漏掉短峰；操作系统峰值工作集另行保留。旧基线对应优化前产品代码与同一新增测试，不能用当前已重建的 executable 冒充旧版本重测。

## 在仓库外创建应用（单依赖宏，已采纳方案 A）

宏支撑方案 A 已实施（2026-10-28）：`#[streamlit::main]` 经库的 doc-hidden 支撑命名空间建立 Tokio 运行时与 env_logger 初始化，调用方**只依赖 `streamlit` 一个包**，不再需要直接依赖 tokio 或 env_logger。`#[streamlit::main]` 接收 async 函数并创建运行时和服务入口。以下目录假设 `my-app/` 与本项目 checkout `streamlit-rust/` 并列；这里使用本地源码，不声称已发布 crates.io 包：

```toml
# my-app/Cargo.toml
[package]
name = "my-app"
version = "0.1.0"
edition = "2024"

[dependencies]
streamlit = { path = "../streamlit-rust/streamlit" }
```

```rust
// my-app/src/main.rs
use streamlit::{Streamlit, StreamlitApi};

#[streamlit::main(host = "127.0.0.1", port = 8550)]
async fn main(st: &Streamlit) {
    st.title("My Rust app");
    st.write("Ready");
}
```

构建前按[入门环境](#构建并启动)配置 Rust 与 protoc，确保 `PROTOC` 指向本机实际编译器；旧记录中的本机 target 路径不是新机器的安装目录。在 `my-app` 执行 `cargo build`；先由 Cargo 生成该应用自己的 Cargo.lock，后续用 `cargo build --locked` 固定已选依赖。运行前，将本 checkout 完整且未修改的 `www/` 放在应用可执行文件旁边，或用 `STREAMLIT_STATIC_DIR` 指向它，再启动并打开 `http://127.0.0.1:8550/`。[既有 sidecar 规则](README.md#run-an-installed-executable-from-any-directory)继续适用；运行时不需要 Python。

库目录改名、不带外部 www 的独立构建、含空格目录的既有 quickstart release 安装，以及**仅依赖 streamlit 的最小外部应用**（改名库目录 + 含空格路径，宏单依赖编译、启动、真实 WS/页面交互）均已通过[本机验证](../../tests/browser/rust-library-portability/README.md)，包括完整 sidecar 对照。无缓存机器、MSRV、Linux/macOS、系统运行库和完整 crate 打包测试均需要各自证据，不能从本机 Windows 缓存构建推断。

## 检查本地 crate 源码包（维护者）

在干净工作区且已配置 protoc/固定依赖缓存时，可从仓库根目录执行 `cargo package --workspace --offline --locked`。这会实际生成并编译验证库与宏两个源码包，输出在 `target/package/`；不会发布到 registry。Cargo 为同 workspace 的尚未发布依赖使用临时本地 registry，因此成功不能证明 crates.io 已存在这些版本。只运行 `--list` 仅能检查文件清单。

本机两个 0.1.1 包已完成此验证，库内协议和 index 可独立编译，普通 SDK consumer 的 library target 也已通过。图表配置和视频样本现随源码包的 examples/data 提供；从实际包提取后，全部示例已通过编译检查，无需另找这些样本。宏包有 6 个文件，修复后的库包有 227 个文件；这些是本次产物计数，不是未来文件数量限制。

维护者测试的交付边界已按采纳的 PKG-A 定义（2026-10-28）：**SDK crate 只保证库与包内示例可构建**——`cargo package` 的库/宏编译验证与示例构建就是包形态的验收；**全部维护者回归由完整仓库源码交付承载**，其 lib test 引用仓库级参考数据（冻结 trace、fixture CSV 等），不能也不需要在独立 crate 包内编译，实测的 31 项包内缺失是该边界的记录而非缺陷。维护者需要完整源码目录运行这套回归；SDK consumer 的 library 检查不冒称单依赖应用或维护者回归通过。Python 参考环境或维护者回归不是应用运行时依赖。

## 运行集成：请求上下文、认证与用户信息（M4 启动，设计中）

本节是 2026-10-28 启动的 M4 里程碑的设计草案；**除已冻结的 Python 参考外，以下 Rust 接口均未实现**，拟新增公共接口按项目规则先供确认，不将规划写成已可用。

**请求上下文**（前两切片已实施）：`st.request_context()` 返回当前浏览器连接的只读快照 `RequestContext { headers, url, locale, timezone, timezone_offset, theme, is_embedded }`——headers 为本连接 WS 握手请求头经服务器白名单过滤后的映射（名称统一小写；HTTP 头名本就大小写不敏感，Python 参考原样保留收到的拼写是记录在案的刻意差异）；`url/locale/timezone/timezone_offset/theme/is_embedded` 来自官方前端随每轮 rerun 上报的 `context_info`（原生客户端不上报则为 None/false，与冻结参考一致；实测前端对 `?embed=true` 报 embedded、对 `?st_embed=true` 不报）。白名单由服务器构建器选择：`RequestHeaderAccess::Standard`（默认：user-agent、accept-language、accept、origin、host）、`Selected([...])`（显式枚举）或 `All`（全部握手头，即冻结参考实测的 Python 行为，含凭据与传输头，仅限可信部署）。锁定的 Python 1.66.1 实测参考见[冻结证据](../../tests/reference/reference-browser/context-headers/README.md)；`ip_address` 与 cookie 读取仍未实现（两种参考路径下 ip 均为 null；cookie 属凭据）。快照按调用即时生成；标头在连接建立时捕获、重连时刷新，页面上下文随每轮 rerun 替换。

**认证与用户信息**：目标是本地可验证的凭据边界——一个可插拔的认证接口（HTTP 头/伪造 OIDC 等价物，测试用假凭据），认证后 `st.user` 等价只读视图暴露身份字段；未配置认证器时应用照常运行。按 M4 退出条件以假凭据与隔离依赖验证，权限边界在设计中明确；真实 OIDC 提供方不在本里程碑范围。

**配置**：Python 的 `config.toml` 注册表不是 Rust 的兼容目标（矩阵既有边界）；Rust 侧的目标是把当前命令行/builder 已覆盖的运行项（地址、端口、静态目录、头部安全开关等）整理为文档化的显式配置面，并为 M4 新能力（认证器、头转发白名单）扩展同风格的显式选项。`st.secrets` 的文件存储暂维持不适用，若用户需要本地 secrets 加载再立项。

**认证与用户信息（公共形态已经用户追认，2026-10-28）**：`StreamlitServer::with_authenticator(Arc<dyn RequestAuthenticator>)`——trait 在连接建立时依据**全部**握手头（不受应用可见白名单限制；认证器是受信服务端配置）返回 `UserIdentity { sub, name, email, picture, roles, extra }` 或匿名；内置 `HeaderAuthenticator::new("x-test-user")`（假凭据：从指定请求头读 JSON 身份，本地/测试用，见 [auth 示例](../../streamlit/examples/auth.rs)），生产部署自行实现 trait。应用侧 `st.user()` 返回等价 `st.user` 的只读映射（`to_dict()`/`is_empty()`；实测无认证的 1.66.1 为**空映射**且无属性式访问，Rust 对齐：未配置认证器、未认证、或空 sub → 空映射）；OIDC `tokens` 子视图未实现（无提供方下参考行为未测）。`st.context.cookies` 等价为 `RequestContext::cookies()`——从**已白名单放行**的 Cookie 头解析键值（[参考](../../tests/reference/reference-browser/user-cookies/README.md)：原生连接 `probe-flavor=oat` → 同值 dict、缺失键 None；默认 Standard 不含 Cookie → 空 dict，显式 Selected/All 才可见）。

已交付：st.context 的 Python 行为参考（协议级）、矩阵条目重开与 `request_context()` v1/v2（示例 `request_context.rs`、WS 回归与浏览器证据见各证据目录）。

## 参考数据与验证

参考行为以锁定的 Python Streamlit 1.66.1 一次采集的正确输入、输出及版本信息冻结；之后 Rust 单元测试和协议重放复用这些数据，无需因每次 Rust 修改或路径变化重新运行 Python。只有新行为、版本升级或证据失效时才补采。Rust、Python 和采集工具的源码 SHA 不作为验收条件；改变错误处理或实现方式不会使正确的冻结结果失效，也不需要另存历史源码。当前 Rust 仍需实际通过对应功能、协议和交互验证。

旧 raw 保持原样；其中源码 SHA 与旧绝对路径仅用于追溯来源，当前数据 fixture 应通过受控相对路径、大小和内容 SHA 定位。各矩阵条目的证据链接说明已覆盖的场景，不应把某一项通过推广到完整功能。

## 示例索引

每个示例 `cargo run --example <名称> --locked` 后打开对应地址：

- **auth**（`http://127.0.0.1:见源码/`）：fake-credential authentication。
- **basic**（`http://127.0.0.1:见源码/`）：markdown/text basics。
- **button**（`http://127.0.0.1:见源码/`）：见源码顶部注释。
- **buttons**（`http://127.0.0.1:8523/`）：every button flavor。
- **cache**（`http://127.0.0.1:8516/`）：cache_data/resource。
- **cache_nested**（`http://127.0.0.1:8543/`）：nested caching。
- **chartlibs**（`http://127.0.0.1:8528/`）：library charts。
- **charts**（`http://127.0.0.1:8512/`）：native charts。
- **chat**（`http://127.0.0.1:8522/`）：chat message and input。
- **colconfig**（`http://127.0.0.1:8529/`）：column configs。
- **columns_params**（`http://127.0.0.1:8595/`）：st.columns parameters。
- **combined**（`http://127.0.0.1:8596/`）：the M7 cross-capability differential page。
- **componenttrigger**（`http://127.0.0.1:8542/`）：component triggers。
- **componentv2**（`http://127.0.0.1:8539/`）：components v2。
- **container**（`http://127.0.0.1:见源码/`）：container basics。
- **counter**（`http://127.0.0.1:见源码/`）：session-state counter。
- **csv_workbench**（`http://127.0.0.1:8545/`）：the full CSV workbench (M2)。
- **data_app**（`http://127.0.0.1:8501/`）：CSV upload to table and chart。
- **dataeditor**（`http://127.0.0.1:8541/`）：the dynamic editor。
- **dataframe_selection**（`http://127.0.0.1:8544/`）：typed row selection。
- **datetime**（`http://127.0.0.1:8526/`）：date/time inputs。
- **display**（`http://127.0.0.1:8521/`）：display elements。
- **display2**（`http://127.0.0.1:8525/`）：display leftovers。
- **elements**（`http://127.0.0.1:8507/`）：element chain page。
- **execution**（`http://127.0.0.1:见源码/`）：rerun/stop control。
- **forms**（`http://127.0.0.1:8504/`）：form flows。
- **hello**（`http://127.0.0.1:见源码/`）：the minimal starter page。
- **inputs**（`http://127.0.0.1:8508/`）：core input widgets。
- **layout_params**（`http://127.0.0.1:8594/`）：layout and streaming parameters。
- **layouts**（`http://127.0.0.1:8513/`）：layout containers。
- **media**（`http://127.0.0.1:8509/`）：media elements。
- **media_params**（`http://127.0.0.1:8593/`）：audio/video playback parameters。
- **navigation**（`http://127.0.0.1:8517/`）：multipage navigation。
- **pageconfig**（`http://127.0.0.1:8514/`）：page config。
- **pickers**（`http://127.0.0.1:8524/`）：picker widgets。
- **presentation**（`http://127.0.0.1:8511/`）：presentation elements。
- **queryparams**（`http://127.0.0.1:8515/`）：query params。
- **quickstart**（`http://127.0.0.1:8503/`）：the guided quickstart widgets。
- **request_context**（`http://127.0.0.1:8590/`）：request context and cookies。
- **status**（`http://127.0.0.1:8502/`）：status elements。
- **tables**（`http://127.0.0.1:见源码/`）：tables and native bar charts。
- **temporal**（`http://127.0.0.1:8506/`）：temporal inputs。
- **textelements**（`http://127.0.0.1:8520/`）：text elements。
- **timer**（`http://127.0.0.1:见源码/`）：auto-rerun timer。
- **uploads**（`http://127.0.0.1:8591/`）：single and multiple uploaders。
- **video**（`http://127.0.0.1:8510/`）：video and ranges。
- **widgets**（`http://127.0.0.1:见源码/`）：the widget parity page。
- **writestream**（`http://127.0.0.1:8527/`）：write_stream。
- **zero_columns**（`http://127.0.0.1:8580/`）：zero-column tables。
