# slider/multiselect 参数：Rust 对照证据（M3 切片）

2026-10-29，caller-owned `slider_multi_params` 示例服务器（8603）+ 同一[采集器](../slider_multi_params_capture.py) --url 模式，与 [Python 参考](../../reference/reference-browser/slider-multi-params/README.md)同调用集。

实测对齐：**4/4 字段一致（零实现改动）**——datetime 显式 30 分钟步长的微秒换算（1.8e9）、date 窗口的一天缺省步长（8.64e10）、epoch 微秒标量与 YYYY-MM-DD 格式、multiselect 默认选择的索引化（[1,2]）均为既有行为经参考确认。边界同参考。
