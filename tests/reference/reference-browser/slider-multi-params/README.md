# slider/multiselect 参数：Python 1.66.1 参考（M3 切片）

2026-10-29，锁定 Python 1.66.1 + 原生 WS，[slider_multi_params_capture.py](../../../browser/slider_multi_params_capture.py) 一次采集冻结；参考应用 [slider_multi_params_app.py](../../slider_multi_params_app.py)。四元素创建期 wire：

- **datetime slider 显式步长**：`timedelta(minutes=30)` → `step 1800000000.0`（微秒）；value/min/max 为 epoch 微秒浮点；`data_type DATETIME`、**format "YYYY-MM-DD"**（datetime 亦为日期格式）。
- **date slider 窗口**：`data_type DATE`、缺省步长为一天 `86400000000.0`。
- **multiselect 默认选择**：`default=["q","r"]` → **选项索引 `[1, 2]`** 上 wire。

Rust 对照（[浏览器证据](../../../browser/rust-slider-multi-params/README.md)）：**4/4 字段一致——零实现改动确认**（既有 datetime/date slider 步长与微秒换算、multiselect 索引默认已符合参考）。离线断言 `tests/reference/test_slider_multi_params_reference.py`。边界：时间值 datetime 滑杆、midnight 缺省步长、搜索过滤交互、format_func 往返未纳入。
