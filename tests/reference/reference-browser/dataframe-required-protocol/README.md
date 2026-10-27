# Required row：空协议值及行数上下文

2026-10-27，固定 Python Streamlit **1.66.1** 的独立本机 WS 协议探针。只使用合成三行数据，8 阶段与 176 个 PB 已由独立 Reviewer 重解核验。**这是显式协议注入，不证明浏览器允许清除必选行**；没有 Chrome、CDP、DOM 或 PNG。原来真实 UI 清除尝试不触发重跑的证据继续保留，没有重采。

参考应用：[dataframe_selection_app.py](../../dataframe_selection_app.py) 的 `required-protocol` case。采集器：[dataframe_required_protocol_capture.py](../../../browser/dataframe_required_protocol_capture.py)。每轮完整 BackMsg、真实 button trigger、ForwardMsg、Code JSON、Arrow、run/session/widget 身份及清理结果在 `first-attempt/trace.json`；紧凑输入/预期在 `required-protocol-input-output.json`。以下均为实际观察：

| 阶段 | 输入/动作 | returned rows / 原始 keyed rows | callback |
| --- | --- | --- | --- |
| 1 | 三行首次加载 | `[0]` / `[0]` | 无 |
| 2 | 显式 full 空选择 | `[0]` / `[0]` | 无 |
| 3 | 同空输入及 Probe | `[0]` / `[0]` | 无 |
| 4 | 同空输入及 Empty table，变零行 | `[0]` / `[0]` | 无 |
| 5 | 零行时再输入空选择 | `[]` / `[]` | main5 前，看到空 rows，run_seen4 |
| 6 | 空输入及 Restore table，恢复三行 | `[]` / `[]` | 无 |
| 7 | 空输入及程序写 partial 空 rows | `[0]` / `{"selection":{"rows":[]}}` | main7 前，看到 `[0]`，run_seen6 |
| 8 | 逐字回送第 7 轮实际 selection_state，附 Probe | `[0]` / `[0]` | main8 前，看到 `[0]`，run_seen7 |

解码发生在 main 前，使用前一轮注册的行数元数据；本轮注册更新后，下一轮才使用新行数。不能在返回值末尾按当前表行数强制补首行：这样会使恢复当轮的返回与 keyed/callback 分裂。协议反序列化需补齐字段并处理 required 首行；程序赋值仍保留 partial keyed 原值，只把正规化结果用于返回和 selection_state。普通保留的旧位置也不能因缩表而统一裁剪。

所有连接均为本次自有 Python 进程，HTTP 200、WS 101、同一会话和 widget，八轮成功完成；保留默认安全参数，没有关闭 XSRF/CORS，也不据此声称安全握手兼容。WS 已关闭、server PID 已退出、端口已关闭，清理无错误。没有启动浏览器或 profile。首次采集的 websockets direct-connect 弃用告警原样保留；采后明确 direct 模式和加强清理的源码改动不会使正确数据失效。

`manifest.json` 仅校验数据字节；Git revision、路径和 PID 是来源元数据，不要求当前源码、旧根目录或进程相同。只在首次新边界执行过以下采集命令；以后直接复用冻结输入，不因 Rust 或采集器改动重采：

```powershell
target/pyref-venv/Scripts/python.exe -B tests/browser/dataframe_required_protocol_capture.py --out target/checks/m2-required-selection/python/first-attempt
```

离线核验不会启动服务或重新采集：

```powershell
target/pyref-venv/Scripts/python.exe -B -m pytest tests/reference/test_dataframe_required_protocol_reference.py -q -p no:cacheprovider
cargo test --workspace --locked --lib server::tests::dataframe_selection
```

Rust 回归将原 34 个前端输入和新增 8 个协议阶段共用一条回放路径，保留两者来源差异；不重复创建一套探针服务器或另存历史源码。

尚未覆盖其他非法模式/字段、多页/会话、lazy、动态默认以及所有浏览器行数切换组合；本组协议证据不能扩大为这些能力已通过。
