# 大小受限上传：Python 1.66.1 参考（M3 输入切片）

2026-10-28，真实 Python 1.66.1 + 官方前端 + 真实 Chrome（[uploads_limit_capture.py](../../../browser/uploads_limit_capture.py) 一次采集）。参考应用 [uploads_limit_app.py](../../uploads_limit_app.py) 以 `max_upload_size=1`（MiB）回显报告；三阶段：load → 选择 2MiB 文件 → 选择 14B 小文件。

实测语义：

- **前端在 PUT 之前静默拦截超限文件**：选择 2MiB 文件后无任何网络上传、无 alert/notification、无 stException，应用报告保持 `count: 0`（元件 `max_upload_size_mb=1` 已在 wire 上）。
- 小文件正常：一条 PUT、报告 `count: 1`（name/size 一致）。
- 服务端防线另行实测（协议探针）：`--server.maxUploadSize=1` 下直接对上传 URL PUT 2MiB 多部件体 → **413 Content Too Large**，连接随即由服务端重置；探针记录于本地 `target/checks/m3-upload-limit/`。

边界：widget 限与服务端限是两道独立防线（前者前端、后者传输层）；`max_upload_size` 参数名与 Python 一致（Rust 构建器为 `max_upload_size_mb`）；超限提示的 UI 文案（若有）在 headless 下未见出现，不冒称已验证用户可见错误提示。Rust 对照见[浏览器证据](../../../browser/rust-uploads-limit/README.md)。
