# 使用 Rust 构建数据应用

本指南按使用场景介绍当前可运行的路径和目标体验。项目仍处于早期阶段：示例能运行或某个场景已有验证，并不意味着完整兼容 Streamlit。Python 参考运行锁定在 1.66.1；API 文档页面当前观察到的标签为 1.66.0，概念和部署指南是未版本化实时文档。功能边界和证据以[兼容矩阵](../../compatibility/api-compatibility-matrix.json)各条目的 `compatibility_scope` 和 `limitations` 为准。

| 场景 | 状态 | 依据与边界 |
| --- | --- | --- |
| 输入控件、CSV 上传、筛选、表格和图表 | 当前可用；兼容性部分验证 | [data_app](../../streamlit/examples/data_app.rs)；矩阵 `st.file_uploader`、`st.dataframe`、`st.bar_chart`。只覆盖已测组合。 |
| 表单、会话状态和普通重跑 | 当前可用；部分验证 | 矩阵 `st.form`、`st.form_submit_button`、`st.session_state`。状态在内存中，恢复有边界。 |
| 单独编辑表格 | 部分验证 | 矩阵 `st.data_editor`；[dataeditor 示例](../../streamlit/examples/dataeditor.rs)覆盖单元格编辑和新增行，不能代表所有类型与操作。 |
| 选择行 → 详情 → 编辑 → 追加 | 待实现或待设计 | 当前没有 dataframe 选择和 `add_rows` 公共 API，也没有将独立编辑示例接入 CSV 应用的完整流程。 |
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

当前 CSV 示例没有行选择或这一整套交互，也没有公开的 `add_rows` API。[dataeditor 示例](../../streamlit/examples/dataeditor.rs)是独立演示，可通过 `cargo run --example dataeditor --locked` 在 8541 端口查看编辑与新增行。编辑方法返回编辑后的数据，调用方使用返回值继续处理；它不会自动保存或改写上传的 CSV。

源码检查发现不可空字段产生 null 时的 schema 冲突，尚未完成该边界的运行时复现；允许空值还是保持输入 schema 约束需要确认。删除行、其他编辑模式和回调的覆盖仍有限。参考官方[数据编辑器](https://docs.streamlit.io/develop/api-reference/data/st.data_editor)与矩阵 `st.data_editor`、`st.dataframe`。

## 会话、重跑和错误

交互通常使整个应用函数重新执行。每个浏览器会话有独立的内存状态；普通重跑保留状态，断线后在服务端仍保留该会话时可以恢复。刷新页面或另开标签页创建新会话，服务重启后内存状态消失。当前默认断线保留 120 秒，这是本实现的本地策略，并非对上游默认值的兼容承诺。运行 `cargo run --example counter --locked` 可观察计数与重跑。

`rerun` 和 `stop` 的基本场景有验证，但已复现同一次运行中后续信号覆盖首个信号的问题；不要依赖多个信号的优先级。也已复现 `query_params.set` 后服务端重跑丢失该值；不要依赖该路径保存状态。详情参见矩阵 `st.rerun`、`st.stop`、`st.query_params`、`st.session_state` 和官方[会话状态](https://docs.streamlit.io/develop/api-reference/caching-and-state/st.session_state)。

可失败的控件调用应传播错误，并在应用入口统一处理，例如 [quickstart](../../streamlit/examples/quickstart.rs) 中的实际模式：

```rust
use ::streamlit::*;

fn render(st: &Streamlit) -> Result<(), WidgetError> {
    let minimum = st.slider(("Minimum amount", 0_i64, 0..=200))?;
    st.write(format!("Minimum amount: {minimum}"));
    Ok(())
}
```

入口可用 `if let Err(error) = render(st)` 显示或记录错误；完整启动代码见示例。当前宏入口接受返回单元类型的函数，因此可在返回 `Result` 的辅助函数中使用 `?`。重复控件 key 会显示框架异常；其他参数错误应由应用处理。Rust 规范禁止 `.unwrap()`，包括示例和测试，也不能机械换成 `.expect()` 或通用 panic 包装。仓库既有用法尚在整改，不能将早期检查通过记录视为已通过新规范。

## 更多应用入口

以下示例提供已有能力的入口，功能和参数只在各自证据范围内得到验证：

| 需求 | 示例或指南 | 官方文档与矩阵条目 |
| --- | --- | --- |
| 布局、侧栏与容器 | [layouts](../../streamlit/examples/layouts.rs) | [布局](https://docs.streamlit.io/develop/api-reference/layout)；各布局条目 |
| 多页面导航 | [navigation](../../streamlit/examples/navigation.rs) | [导航](https://docs.streamlit.io/develop/api-reference/navigation/st.navigation)；`st.navigation` |
| 输入与表单 | [widgets](../../streamlit/examples/widgets.rs)、[forms](../../streamlit/examples/forms.rs) | [控件](https://docs.streamlit.io/develop/api-reference/widgets)、`st.form` |
| 流式文本 | [writestream](../../streamlit/examples/writestream.rs) | [流式输出](https://docs.streamlit.io/develop/api-reference/write-magic/st.write_stream)；`st.write_stream`，当前证据限文本 |
| 自定义组件 | [componentv2](../../streamlit/examples/componentv2.rs) | [组件](https://docs.streamlit.io/develop/concepts/custom-components)；`st.components.v2.component`。源码检查发现局部 JSON 状态可能丢失默认字段，运行时边界尚待验证。 |
| 缓存 | [cache](../../streamlit/examples/cache.rs) | [缓存](https://docs.streamlit.io/develop/concepts/architecture/caching)；`st.cache_data`。当前缓存按会话隔离；源码检查发现嵌套调用可能覆盖录制上下文，尚未运行复现。 |

页面配置已有部分接口；完整配置体系、秘密管理、身份认证、主题和生产部署的体验仍待盘点、设计和验证。请参考官方[配置](https://docs.streamlit.io/develop/concepts/configuration)、[认证](https://docs.streamlit.io/develop/concepts/connections/authentication)、[主题](https://docs.streamlit.io/develop/concepts/configuration/theming)及[部署](https://docs.streamlit.io/deploy/concepts)。矩阵中历史 `not_applicable` 条目正在重新审视，不能据此推断长期目标排除这些场景。

## 参考数据与验证

参考行为以锁定的 Python Streamlit 1.66.1 一次采集的正确输入、输出及版本信息冻结；之后 Rust 单元测试和协议重放复用这些数据，无需因每次 Rust 修改或路径变化重新运行 Python。只有新行为、版本升级或证据失效时才补采。旧 raw 保持原样；其中旧绝对路径仅用于追溯来源，当前 fixture 应通过受控相对路径、大小和 SHA 定位。各矩阵条目的证据链接说明已覆盖的场景，不应把某一项通过推广到完整功能。本次编写未重新运行服务或浏览器验证。
