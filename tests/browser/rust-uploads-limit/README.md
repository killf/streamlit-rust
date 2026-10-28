# 大小受限上传：Rust 浏览器证据（M3 输入切片）

2026-10-28，caller-owned `uploads` 示例（8591）+ 官方前端 + 同一[采集器](../uploads_limit_capture.py)、同一输入，与[Python 参考](../../reference/reference-browser/uploads-limit/README.md)同三阶段。Rust 页在此采集时含单/多/限制三段（directory 段随后续批次加入示例，不在本 trace 内）。

实测对齐：2MiB 文件被同一前端**在 PUT 之前拦截**（限段报告保持 `count: 0`、无上传请求、无异常）；小文件一条 PUT、限段报告 `count: 1`（`small.txt` 14 字节）。wire 元素 `max_upload_size_mb=1` 与 Python 一致，前端行为即由该值驱动。

服务端防线（独立于前端）：`UploadHttpError::TooLarge` 映射为 **413**（实测 Python `server.maxUploadSize` 同状态），`StreamlitServer::with_max_upload_size_mb` 可配置（默认 200MiB 同 Python）；WS/HTTP 回归 `oversized_upload_put_answers_413_without_storage` 断言 2MiB PUT → 413、同 URL 小文件 → 204、存储未写入。离线断言见 `tests/reference/test_uploads_limit_reference.py`。
