# json/badge/feedback 参数：Python 1.66.1 参考（M3 切片）

2026-10-29，锁定 Python 1.66.1 + 原生 WS，[json_badge_params_capture.py](../../../browser/json_badge_params_capture.py) 一次采集冻结；参考应用 [json_badge_params_app.py](../../json_badge_params_app.py)。六元素创建期 wire：

- **st.json**：`expanded=True` 显式置位；**缺省（collapsed）时 expanded 省略**；body 为 json.dumps 格式（", "/": " 分隔、构造序）。**1.66.1 的 st.json 无 depth 参数**（传 depth 实测抛 TypeError——首采真实触发改写 fixture）。
- **st.badge**：`icon`/`color` 进 markdown body（`:green-badge[:material/rocket_launch: New]`；无 icon 无分隔符）；**badge markdown 的 wrap 字段缺省（省略 = None）**——Rust 此前发 `Some(true)`，实测修正为 None。
- **st.feedback**：`disabled=True` 进消息；**feedback 位置参数即选项 preset**（`options=` 关键字实测与位置参数冲突抛 TypeError）。

Rust 对照（[浏览器证据](../../../browser/rust-json-badge-params/README.md)）：**6/6 字段一致**（修复 badge wrap 一处真实偏差；json/feedback 为既有行为确认）。离线断言 `tests/reference/test_json_badge_params_reference.py`。边界：badge 宽度/帮助、feedback 交互提交与 ignore 模式未纳入。
