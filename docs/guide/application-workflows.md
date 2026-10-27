# 使用 Rust 构建数据应用

本指南按使用场景介绍当前可运行的路径和目标体验。项目仍处于早期阶段：示例能运行或某个场景已有验证，并不意味着完整兼容 Streamlit。Python 参考运行锁定在 1.66.1；API 文档页面当前观察到的标签为 1.66.0，概念和部署指南是未版本化实时文档。功能边界和证据以[兼容矩阵](../../compatibility/api-compatibility-matrix.json)各条目的 `compatibility_scope` 和 `limitations` 为准。

| 场景 | 状态 | 依据与边界 |
| --- | --- | --- |
| 输入控件、CSV 上传、筛选、表格和图表 | 当前可用；兼容性部分验证 | [data_app](../../streamlit/examples/data_app.rs)；矩阵 `st.file_uploader`、`st.dataframe`、`st.bar_chart`。只覆盖已测组合。 |
| 表单、会话状态和普通重跑 | 当前可用；部分验证 | 矩阵 `st.form`、`st.form_submit_button`、`st.session_state`。状态在内存中，恢复有边界。 |
| 单独编辑表格 | 部分验证 | 矩阵 `st.data_editor`；[dataeditor 示例](../../streamlit/examples/dataeditor.rs)覆盖单元格编辑和新增行，不能代表所有类型与操作。 |
| 选择行 → 详情 → 编辑 → 追加 | 待实现或待设计 | 当前没有 dataframe 选择公共 API，也没有将独立编辑示例接入 CSV 应用的完整流程。数据追加/更新的方式仍待设计。 |
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

此示例的聚合和舍入是应用自身规则，不是所有 Streamlit 应用的通用行为。上传的替换、删除、多文件、会话过期和安全边界仍未完整验证；不要将当前上传端点视为面向不可信用户的生产认证边界。参见官方[文件上传](https://docs.streamlit.io/develop/api-reference/widgets/st.file_uploader)、[表格](https://docs.streamlit.io/develop/api-reference/data/st.dataframe)、[表单](https://docs.streamlit.io/develop/api-reference/execution-flow/st.form)及矩阵对应条目。

## 选择、查看、编辑和追加：目标体验

目标流程是：在结果表中选择一条记录，查看其详情，修改并确认，再将新数据追加到已有视图；重跑时应明确保留哪些选择和编辑结果。空选择、筛选后所选记录消失、编辑失败、重复提交和数据来源更新等行为仍待设计和验证。

当前 CSV 示例没有行选择或这一整套交互。官方已在 1.58.0 移除 `element.add_rows`，它不是本项目 1.66.1 的兼容缺口；数据追加流程仍保留在目标中，应用数据更新/重新渲染与新增 Rust 扩展需要分开选择。[dataeditor 示例](../../streamlit/examples/dataeditor.rs)是独立演示，可通过 `cargo run --example dataeditor --locked` 在 8541 端口查看编辑与新增行。编辑器每轮发送原始输入表，并返回应用编辑后的 `RecordBatch`；调用方可像示例一样通过 `st.dataframe` 单独显示或继续处理返回值。它不会自动保存或改写上传的 CSV。

已复现不可空字段遇到空行时的 schema 冲突，并选择按编辑结果放宽：仅实际产生 null 的结果列设为 nullable，未产生 null 的列保留输入的可空标记，原始输入表不变。调用方须读取返回表的 schema，不能假定它仍与输入完全相同。整数列遇 null 时已有的 Float64 转换规则继续适用；填齐新增行后，每轮仍基于原始输入重新应用编辑。该规则已有冻结输入回归、真实 WS 和 Rust 官方前端四步交互验证。删除行、其他编辑模式和回调的覆盖仍有限。参考官方[数据编辑器](https://docs.streamlit.io/develop/api-reference/data/st.data_editor)与矩阵 `st.data_editor`、`st.dataframe`。

选择接口的候选用法及返回值兼容影响见[待确认设计](../../.codex/architecture.md#dataframe-selection-and-data-updates--proposal)；它尚未实现，不能将提议示例作为当前可用接口。

## 会话、重跑和错误

交互通常使整个应用函数重新执行。每个浏览器会话有独立的内存状态；普通重跑保留状态，断线后在服务端仍保留该会话时可以恢复。刷新页面或另开标签页创建新会话，服务重启后内存状态消失。当前默认断线保留 120 秒，这是本实现的本地策略，并非对上游默认值的兼容承诺。运行 `cargo run --example counter --locked` 可观察计数与重跑。

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

## 参考数据与验证

参考行为以锁定的 Python Streamlit 1.66.1 一次采集的正确输入、输出及版本信息冻结；之后 Rust 单元测试和协议重放复用这些数据，无需因每次 Rust 修改或路径变化重新运行 Python。只有新行为、版本升级或证据失效时才补采。Rust、Python 和采集工具的源码 SHA 不作为验收条件；改变错误处理或实现方式不会使正确的冻结结果失效，也不需要另存历史源码。当前 Rust 仍需实际通过对应功能、协议和交互验证。

旧 raw 保持原样；其中源码 SHA 与旧绝对路径仅用于追溯来源，当前数据 fixture 应通过受控相对路径、大小和内容 SHA 定位。各矩阵条目的证据链接说明已覆盖的场景，不应把某一项通过推广到完整功能。
