# 多文件上传：Rust 浏览器证据（M3 输入切片）

2026-10-28，caller-owned `uploads` 示例服务器（单+多两个上传器，8591）+ 官方前端 + 同一[采集器](../uploads_multi_capture.py)。与[冻结 Python 参考](../../reference/reference-browser/uploads-multi/README.md)同一四阶段与输入：load → 一次选择两文件 → 移除 alpha → 移除 beta。

实测对齐：报告 count 0→2→1→0，name/size/`bytes_head` 与输入逐字节一致；chip DOM 同步；wire 上 `multiple_files=true`、一条批量 `file_urls_request`（2 名）、逐文件 PUT、状态列表 `[alpha, beta]→[beta]→[]`；移除语义保留存活文件。全部无 stException。两侧唯一差异是页面结构（Rust 示例多一个单文件上传器在前，采集器按最后一个 dropzone 定位多文件控件）。

离线断言（`tests/reference/test_uploads_multi_reference.py`）双向核对 Python 与 Rust 冻结数据：语义阶段一致、批量地址请求、状态递减、PUT/DELETE 计数（收尾 DELETE 的竞态只保证首个）。边界同参考：小文本文件、单会话、一台机器；目录模式与超限未测。
