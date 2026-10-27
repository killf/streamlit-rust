# 字节下载：默认文件名、特殊字符及 MIME

2026-10-27，Python Streamlit **1.66.1**，10 次公开 `st.download_button` 调用，均使用合成的 18 字节 `id,region\nA,north\n`。一次初始真实 WS 运行记录 16 个 PB，随后对发射的 10 个 URL 实际 GET；全部 200，原字节不变。这是协议/HTTP 证据，没有 Python 浏览器保存行为声明。

| 输入边界 | 实测结果 |
| --- | --- |
| 未给文件名，字节默认 MIME | `streamlit_download.bin`，`application/octet-stream` |
| 未给文件名，显式 text/plain | `streamlit_download.txt`，响应补 UTF-8 charset |
| Unicode、引号、反斜杠文件名 | `filename*=utf-8''...`，UTF-8 百分号编码 |
| 空文件名、text/csv | 回退为 `streamlit_download.csv` |
| text/plain 已含 charset | 不重复 charset；URL 和默认文件名没有扩展名 |
| application/json | `.json`，不追加文本 charset |
| 未知 MIME | 无扩展名的 URL 仍返回 200 |
| hello.txt、text/plain | 普通 quoted filename，响应补 UTF-8 charset |

`cases-input.json` 保留公开参数与原字节；`trace.json` 是原 PB/HTTP 和资源清理记录；`download-cases.json` 仅提取其中的配对数据，供 Rust 真实公开入口/HTTP 回归读取。十个 `.bin` 是实际响应体。`manifest.json` 校验数据、原始日志和响应体的大小与 SHA，不校验或归档当前源码；旧绝对路径仅说明捕获来源。

采集器退出 0，WS close 1000，自有 PID 79104 停止，54244 无监听，cleanup_errors 为空；未启动 browser/profile。日常测试只读这些冻结数据，不重新启动 Python server：

```powershell
target/pyref-venv/Scripts/python.exe -B -m pytest tests/reference/test_download_boundaries_reference.py -q -p no:cacheprovider
cargo test --workspace --locked --lib download_headers_and_bytes_match_ten_frozen_public_cases
```

Rust 修复前真实 HTTP 已复现缺默认名、特殊字符使用普通 filename、text/plain 缺 charset；本地红/绿日志在 `target/checks/m3-download-boundaries/rust/`。既有媒体与 CSV Range/重复 GET 回归继续保留。Rust 浏览器保存行为另见 [原生下载证据](../../../browser/rust-download-boundaries/README.md)。

范围只涵盖这 10 个字节输入；其他标点组合、所有 MIME 映射、字符串/file-like 自动类型推断、动态数据或 callable、下载的完整生命周期尚未在本批验收。Rust 的字节接口丢失输入原始 text/bytes 类型，不据此宣称已兼容 Python 全部输入形式。
