# 控件创建参数边界：Python 1.66.1 参考（M3 widgets 切片）

2026-10-28，锁定 Python 1.66.1 + 原生 WS，[widget_params_capture.py](../../../browser/widget_params_capture.py) 一次采集冻结；参考应用 [widget_params_app.py](../../widget_params_app.py)。四个控件、八个元素的创建期 wire 参数（无需 UI 交互）：

- **number_input float 路径**：`format "%0.2f"`、`data_type FLOAT`、默认步长 **0.01**、无界时 min/max 携带 **f64 哨兵**（∓1.797e308）且不带 has_min/has_max；整型为 `"%d"`、无界时不发边界。有界 float（0.25/9.75/步 0.25）与有界整型（2/8/步 2，default/step/min/max 均为浮点标量）逐字段实测。
- **radio**：`index=None` **不发 default 字段**；`horizontal=True` + `captions` 逐项透传，default=0。
- **text_area**：`max_chars`/`placeholder` 在消息内。
- **multiselect**：`max_selections` 在消息内（select_all 1000、accept_new_options false 同既有）。

Rust 对照（[浏览器证据](../../../browser/rust-widget-params/README.md)）：**8/8 元素字段一致**（widget id 为运行时身份已掩码）。本批修复 Rust 两处真实偏差：float format 此前留空待测（现为 %0.2f）、无界 float 的 min/max 此前发 0.0（现按参考发哨兵）；新增 radio horizontal/captions、text_area height、multiselect max_selections 构建器。on_change、format_func 往返与交互期行为未纳入。离线断言 `tests/reference/test_widget_params_reference.py`。
