# 录制控件参数：Python 1.66.1 参考（M3 切片）

2026-10-29，锁定 Python 1.66.1 + 原生 WS，[recorder_params_capture.py](../../../browser/recorder_params_capture.py) 一次采集冻结；参考应用 [recorder_params_app.py](../../recorder_params_app.py)。三元素创建期 wire：

- **audio_input**：显式 `sample_rate=44100` 进消息（既有默认 16000 路径此前已测）。
- **camera_input**：默认拍照模式——消息仅 label/label_visibility（无 capture_mode 字段）。

Rust 对照（[浏览器证据](../../../browser/rust-recorder-params/README.md)）：**3/3 字段一致——零实现改动确认**（sample_rate 与 camera 默认形态为既有行为经参考确认）。离线断言 `tests/reference/test_recorder_params_reference.py`。边界：录音/拍照的**提交行为**（真实麦克风/摄像头）headless 不可测——与既有 pickers 链边界一致；disabled/help/回调未纳入。
