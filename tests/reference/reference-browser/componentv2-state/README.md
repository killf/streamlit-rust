# Component defaults and partial state — Python reference

2026-10-27，一次隔离的 Python Streamlit **1.66.1** 官方前端采集。四轮实际 `NewSession` 都报告 1.66.1，并各有一个成功的 `script_finished`。只使用假数据；本地 server、headless Chrome 和临时 profile 均已清理。

应用：[componentv2_state_app.py](../../componentv2_state_app.py)。采集器：[componentv2_state_capture.py](../../../browser/componentv2_state_capture.py)。默认值为 `{"value":"hi","untouched":7}`，两个字段都声明空回调。组件按钮分别只调用 `setStateValue("value", "bye")` 和 `setStateValue("value", null)`；普通重跑来自页面的 `Ordinary rerun` 按钮。

| 实际操作 | BackMsg 中 greeter 的原始 `json_value` | 返回值与 keyed Session State |
| --- | --- | --- |
| 初始加载 | 无该 widget state | `{"untouched":7,"value":"hi"}` |
| Set bye | `{"value":"bye"}` | `{"untouched":7,"value":"bye"}` |
| Ordinary rerun | `{"value":"bye"}` | `{"untouched":7,"value":"bye"}` |
| Set null | `{"value":null}` | `{"untouched":7,"value":null}` |

这是实际观察：浏览器确实发送局部对象，未携带 `untouched`。Python 在顶层补缺失默认字段；已有值（包括显式 null）优先。普通重跑保留先前的局部值。此捕获没有进一步测试 null 后的第二次普通重跑、嵌套对象、多个实例或回调副作用。

`state-cases.json` 是从原始 BackMsg 与页面 JSON 输出提取的紧凑输入/预期，可供 Rust `include_str!` 回归使用；其中 widget ID 保留原值，没有规范化为 Rust ID。返回值和 `st.session_state["greeter"]` 分开保留，不能用其中之一替代另一项。

`trace.json` 保存完整原始 CDP 事件、发送命令及响应、32 个原始 PB frame、逐阶段范围、DOM JSON、版本、启动配置与进程清理结果；四张 PNG 保留操作后的实际页面。`manifest.json` 只校验数据文件的大小与 SHA，不包含源码 SHA。Git revision 与机器路径仅用于采集追溯，不构成源码一致性门槛。

后续直接重放冻结数据；不要因 Rust 或采集器实现修改重新运行 Python。首次采集命令为：

```powershell
target/pyref-venv/Scripts/python.exe -B tests/browser/componentv2_state_capture.py --out target/checks/componentv2-state-reference-once
```

采集器要求输出目录不存在，避免覆盖既有正确证据。这里发布的文件与该次成功采集的原字节相同。
