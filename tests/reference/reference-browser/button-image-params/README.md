# 按钮/图片创建参数：Python 1.66.1 参考（M3 buttons/images 切片）

2026-10-29，锁定 Python 1.66.1 + 原生 WS，[button_image_params_capture.py](../../../browser/button_image_params_capture.py) 一次采集冻结；参考应用 [button_image_params_app.py](../../button_image_params_app.py)。六元素创建期 wire：

- **st.button**：`type="primary"` → `type: primary`；`icon`（material 短码）透传；`disabled=True` + 默认 secondary 同行。
- **st.download_button**：body 存媒体库——**显式 file_name/mime 时 URL 扩展名取自文件名（`.txt`）**；**均缺省时按内容推断（未知 → `.bin` 裸字节）**，消息内不带 file_name/mime（仅 url）。
- **st.image 列表输入**：两图（同像素 → **同内容寻址 URL**）合成一个 `imgs` 元素，caption 逐条对应，width 120 元素级。

Rust 对照（[浏览器证据](../../../browser/rust-button-image-params/README.md)）：**6/6 字段一致**（URL 哈希掩码；download URL 扩展名规则与双图共享 URL 逐字一致）。新增 `st.images(ImageListOptions)` 列表 API；按钮 type/icon/disabled 与 download 命名规则为既有行为经参考确认。离线断言 `tests/reference/test_button_image_params_reference.py`。边界：URL/path 图输入、use_container_width、点击交互流未纳入。
