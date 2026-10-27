# Rust dataframe 选择、详情与编辑

2026-10-27，当前开发工作区编译的 [dataframe_selection 示例](../../../streamlit/examples/dataframe_selection.rs)，通过自有 Chrome 及未修改的官方前端完成 6 阶段。示例入口为 `#[main(host = "127.0.0.1", port = 8544)]`，生产服务仅为 Rust；Python 只用于开发期浏览器驱动和协议解码，没有重采 Python 参考。

| 实际步骤 | 原始协议与页面结果 |
| --- | --- |
| 加载 | 已启用 SingleRow，返回空选择；原表按 `rC/30,rA/10,rB/20` 展示。 |
| 选择输入第 0 行 | 返回 `rows:[0]`，详情及编辑器原表为 `rC/30`。 |
| Ordinary rerun | 同一会话保留 `rows:[0]` 和对应详情。 |
| qty 升序 | 真实点击表头，DOM 顺序变为 `rA/10,rB/20,rC/30`；此阶段没有新增 WS 帧或重跑。 |
| 选择视觉首行 | 原始 string_value 与页面返回 `rows:[1]`，详情为原输入的 `rA/10`。 |
| 编辑 qty 为 15 并 Enter | 原始 editor edits 为第 0 行 qty 15。编辑器仍接收 `rA/10` 原表，返回结果及页面显示 `rA/15`；orders 原表和选择 `[1]` 保持。 |

独立 Review 已重解全部 75 个二进制帧，并核对 895 个 CDP 事件、39 条命令、HTTP 200、WS 101、同一会话的 5 个不同 run ID 和成功完成。原始 Arrow、DOM、selection JSON、delta path 与截图关联，排序和编辑截图已实际查看。原数据与编辑后的返回表分开核验，不把改写后的表冒充 editor 输入。

`first-attempt/trace.json`、六张 PNG 及两个进程日志保持采集原字节；`native-input-output.json` 为其紧凑数据投影，截图名相对于 raw 所在的 `first-attempt/` 目录。`manifest.json` 校验数据大小及 SHA；Git revision、机器路径与二进制身份只描述捕获来源，不绑定当前源码或要求旧进程存在。Rust/Chrome、自有端口及临时 profile 已清理，`cleanup_errors` 为空。

本例由固定三行数据演示交互，不保存回源 CSV、文件或数据库；切换详情也不意味着跨隐藏保留编辑。它只证明这条 SingleRow 流程，没有证明所有模式、参数组合、多页/会话、lazy、错误输入或 CSV 完整闭环。

运行示例后可按上表真实操作复验：

```powershell
cargo run --example dataframe_selection --locked
```

自动回归使用已冻结的 [Python 34 阶段输入](../../reference/reference-browser/dataframe-selection/README.md)，直接验证真实 Rust WS 的 typed 返回、原始 keyed state、callback 顺序、程序设置、缩行及隐藏/恢复。它覆盖的模式比本次 Rust 浏览器链更广，但不能替代浏览器几何交互：

```powershell
cargo test --workspace --locked --lib server::tests::dataframe_selection
```
