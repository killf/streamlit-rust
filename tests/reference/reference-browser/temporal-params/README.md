# 时间/滑块创建参数：Python 1.66.1 参考（M3 temporal 切片）

2026-10-29，锁定 Python 1.66.1 + 原生 WS，[temporal_params_capture.py](../../../browser/temporal_params_capture.py) 一次采集冻结；参考应用 [temporal_params_app.py](../../temporal_params_app.py)。五元素创建期 wire：

- **date_input**：显式 value → `default ["YYYY-MM-DD"]`；显式 min/max 透传 ISO；**未给 min/max 时为 value 日期 ±10 年窗口**（Formatted 组实测 2014-06-01/2034-06-01）；自定义 `format`（如 DD/MM/YYYY）原样上 wire。
- **select_slider 范围模式**：双端点 value → `default [0.0, 2.0]`（选项索引）、`type SELECT_SLIDER`、`options` 标签数组、`step 1.0`、`format "%s"`、min 0 max N-1。
- **time_input**：`step` 以**字符串**上 wire（"900"）、`format "24h"`、default "HH:MM"。

Rust 对照（[浏览器证据](../../../browser/rust-temporal-params/README.md)）：**5/5 元素字段一致，零实现改动**——既有 date 十年窗/format、select_slider 范围默认与 time step 已符合参考。离线断言 `tests/reference/test_temporal_params_reference.py`。边界：range date_input、交互期提交（日历/输入行为）、on_change 未纳入。
