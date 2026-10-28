# 多文件上传：Python 1.66.1 参考（M3 输入切片）

2026-10-28，真实 Python Streamlit 1.66.1 + 官方前端 + 真实 Chrome（[uploads_multi_capture.py](../../../browser/uploads_multi_capture.py) 一次采集）。参考应用 [uploads_multi_app.py](../../uploads_multi_app.py) 以 `accept_multiple_files=True` 回显文件报告；四阶段：load → 一次选择 `alpha.txt`+`beta.csv`（CDP 双文件注入）→ 移除 alpha → 移除 beta。

实测 wire 与语义：

- 上传器元素 `multiple_files=true`；文件选择后前端**一次性批量请求**两个文件的地址（一条 `file_urls_request` 带 2 名 → 一条 response 带 2 url），随后逐个 PUT `/upload_file/{session}/{file_id}`。
- 每轮 rerun 的控件状态携带完整 `uploaded_file_info` 列表：`[alpha, beta] → [beta] → []`；移除 alpha 时前端对该文件发 **DELETE**；清空最后一个文件时的收尾 DELETE 与采集器停采存在竞态（一次采到、一次未采到），断言只保证首个。
- 应用侧返回值：count 0→2→1→0，name/size/type/`getvalue()` 字节与输入一致；chip DOM 同步（0→2→1→0）。上传、移除均触发整页 rerun；无 stException。

边界：两个小文本文件、一台机器、单会话；目录选择、超大文件、`max_upload_size_mb` 超限、并发竞争与过期清理未测。Rust 对照见[浏览器证据](../../../browser/rust-uploads-multi/README.md)，离线断言见 `tests/reference/test_uploads_multi_reference.py`。
