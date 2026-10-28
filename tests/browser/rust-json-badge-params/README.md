# json/badge/feedback 参数：Rust 对照证据（M3 切片）

2026-10-29，caller-owned `json_badge_params` 示例服务器（8604）+ 同一[采集器](../json_badge_params_capture.py) --url 模式，与 [Python 参考](../../reference/reference-browser/json-badge-params/README.md)同调用集。

实测对齐：**6/6 元素字段一致**。本批修复一处真实偏差：badge markdown 的 `wrap` 此前发 `Some(true)`，实测参考**缺省该字段**——先误改为 `Some(false)`（离线差分再次抓到显式 false 仍不等价于省略），终改 `None`；json 的 expanded 语义与 feedback 的 disabled 为既有行为经参考确认。边界同参考。
