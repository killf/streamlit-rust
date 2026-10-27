# Rust CSV workbench：已测范围

2026-10-27，真实 `#[main]` 原生示例 `csv_workbench`、官方前端。`main-tab-fixed` 20 阶段与 `filters-first` 13 阶段共 743 个 PB，经独立 Reviewer 与 [冻结 Python 33 阶段](../../reference/reference-browser/csv-workbench/README.md)对照：有序文本行、详情源表、新增草稿、逻辑计数、实际 CSV 下载和双会话隔离相符。未 Apply 不改工作数据；Apply 仅改 rA.region；Append 保留空字段；筛选变化隔离详情，但 pending 新增草稿保留至 Append。

`protocol/` 是另一次 **显式 Rust WS 输入**，不是浏览器可达性或 Python 兼容证明。17 阶段、400 PB、2 PUT 204 与 16 GET 200，核对同批/延迟旧 Apply/Append 不误写；合法 Apply 正对照只修改 X.region。共 18 次运行，其中合法 Apply 有早结束及服务器重跑。探针只关自己的 WS，没有停止主代理服务；没有归档源码或源码指纹门槛。

本批另有真实 HTTP 红绿回归：原 `.csv` 下载地址返回 404；修复后 CSV 200、`text/csv; charset=utf-8`、附件名 `workbench.csv`、原始字节、206 Range、重复下载和未知 id 404 均通过。实现保留注册时的下载元数据、原内容地址和首次写入语义；普通媒体路由范围没有扩大。

保留差异：Python 下载设为 ignore，Rust 下载另触发重跑；Python Arrow nullable 和索引呈现与 Rust 不完全相同；空计数时 Python 发空图而 Rust 不发；Vega spec 不相等。Python 部分截图仍是更新前柱高，Rust 实际截图显示新计数，尚未证明该 Python 呈现差异的原因。只声明逻辑计数和所见的 Rust 图，不声明完整 schema/IPC/像素或默认图表兼容。

来源替换 UI 尚未验收，等待“上传器空状态和清空工作副本”的规则选择；没有把该失败隐藏或改为通过。本证据也不覆盖全部数据类型、所有选择模式/参数、完整错误/安全边界或长期目标其余阶段。

`manifest.json` 只校验数据和图片；Git、旧 PID 与路径只用于追溯。两个 browser raw 保留 caller-owned server 的原始 `None` 清理状态。后来主代理通过托管进程句柄停止两次自有服务，`root-cleanup.json` 独立确认 PID 51376/56352 已不存在、8545 端口关闭；Chrome/profile 已分别由各次采集器回收。

启动查看：仓库根目录执行 `cargo run --example csv_workbench --locked`，访问 `http://127.0.0.1:8545/`。离线回归使用 `cargo test --example csv_workbench --locked` 和参考数据测试；不为一般代码改动重新采集 Python。
