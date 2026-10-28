# 按钮/图片创建参数：Rust 对照证据（M3 buttons/images 切片）

2026-10-29，caller-owned `button_image_params` 示例服务器（8601）+ 同一[采集器](../button_image_params_capture.py) --url 模式，与 [Python 参考](../../reference/reference-browser/button-image-params/README.md)同调用集。

实测对齐：**6/6 元素字段一致**（URL 哈希掩码；download URL 的 `.txt`/`.bin` 扩展名规则、双图共享内容寻址 URL 逐字一致）。新增 `st.images(ImageListOptions)`（captions/width、逐图校验）；按钮 primary/icon/disabled 与 download 默认命名路径为既有行为经参考确认。边界同参考。
