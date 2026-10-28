# chat/metric/progress 参数：Python 1.66.1 参考（M3 切片）

2026-10-29，锁定 Python 1.66.1 + 原生 WS，[chat_metric_params_capture.py](../../../browser/chat_metric_params_capture.py) 一次采集冻结；参考应用 [chat_metric_params_app.py](../../chat_metric_params_app.py)。九元素（8 核心 + 1 Python-only 异常）：

- **chat_message**：emoji 字符串 avatar → `avatar_type: EMOJI`（material 短码为 ICON——既有测量）。
- **metric 全规则**（frozen 实测）：无 delta 与 **delta=0** 均 `NONE + GRAY`；`delta_color="off"` 保留方向（UP）但 GRAY；负 delta normal 为 `DOWN + RED`（proto 零值缺省省略——DOWN=0/RED=0，不打印）。
- **progress**：`text` 标签随消息同行（value 50 + text）；**float overload 为 Python-only**——25.5（>1.0）触发框架异常 `outside [0.0, 1.0]`（int 0..=100 / float 0..1 双区间）。

Rust 对照（[浏览器证据](../../../browser/rust-chat-metric-params/README.md)）：**8/8 核心元素一致**（Python-only float 异常不适用）。本批修复三处真实偏差：① 无 delta 的颜色 RED→GRAY；② delta=0 被当作负数（DOWN+RED）→ NONE+GRAY；③ emoji avatar 被标 ICON → EMOJI；新增 `progress_options(text)`。离线断言 `tests/reference/test_chat_metric_params_reference.py`。边界：image/URL avatar、accept_file、非数值 delta、float progress 的 Rust 等价未纳入。
