# 时间/滑块创建参数：Rust 对照证据（M3 temporal 切片）

2026-10-29，caller-owned `temporal_params` 示例服务器（8600）+ 同一[采集器](../temporal_params_capture.py) --url 模式，与 [Python 参考](../../reference/reference-browser/temporal-params/README.md)同调用集。

实测对齐：**5/5 元素字段一致（零实现改动）**——date_input 显式边界与 ±10 年缺省窗、自定义 format、select_slider 双端点范围默认（SELECT_SLIDER 类型与索引端点）、time_input step 字符串化与 24h 格式均为既有行为经参考确认。边界同参考。
