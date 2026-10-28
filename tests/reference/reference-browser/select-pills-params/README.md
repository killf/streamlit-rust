# selectbox/checkbox/pills 参数：Python 1.66.1 参考（M3 切片）

2026-10-29，锁定 Python 1.66.1 + 原生 WS，[select_pills_params_capture.py](../../../browser/select_pills_params_capture.py) 一次采集冻结；参考应用 [select_pills_params_app.py](../../select_pills_params_app.py)。五元素创建期 wire：

- **selectbox**：`index=None`（无 default 字段）+ `placeholder` + `help` 进消息；`disabled=True` + 默认 index=0。
- **checkbox**：`default true`/`disabled`/`help` 全部进消息。
- **pills multi**：`selection_mode="multi"` → button_group 的 `click_mode MULTI_SELECT`；`default=["x","z"]` → **索引 `[0, 2]`**；选项为 `{content}` 对象数组；`help` 进消息。

Rust 对照（[浏览器证据](../../../browser/rust-select-pills-params/README.md)）：**5/5 字段一致——零实现改动确认**。离线断言 `tests/reference/test_select_pills_params_reference.py`。边界：format_func、option icons、query binding、wrap、交互期选择行为未纳入。
