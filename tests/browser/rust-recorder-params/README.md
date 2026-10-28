# 录制控件参数：Rust 对照证据（M3 切片）

2026-10-29，caller-owned `recorder_params` 示例服务器（8605）+ 同一[采集器](../recorder_params_capture.py) --url 模式，与 [Python 参考](../../reference/reference-browser/recorder-params/README.md)同调用集。

实测对齐：**3/3 字段一致（零实现改动）**——audio_input 的显式 sample_rate 与 camera_input 的默认消息形态均为既有行为经参考确认。边界同参考（提交行为 headless 不可测）。
