# 媒体 Range：原始请求与响应

2026-10-27，固定 Python Streamlit **1.66.1**，以公开 `st.download_button`/`st.video` 发射实际 URL，再对本地媒体路由发送原始 HTTP 请求。没有浏览器，不声明已测拖动播放器定位。

- `first/`：18 字节合成 CSV、空下载及现有 3605 字节有效视频，23 个新请求、9 个原 PB。实际为 1×200、9×206、13×416。
- `integer-forms/`：只补四个此前未测输入，7 PB；没有重跑原 23 条。`bytes=5`、`bytes=1_0-1_7`、超过 u64 的 end 返回 206，存在但为空的 Range header 返回 200。

共 **27 请求：2×200、12×206、13×416**。合法后缀、超长 suffix/end、开放终点、大小写/空白/加号按记录返回单个区间；非法、越界、多范围和空文件的非空 Range 返回 416。所有 416 正文恰为 `Invalid range`（13 字节），带 `Content-Range: bytes */N` 与文本类型，不带成功媒体的附件或 Accept-Ranges。多范围没有 multipart 响应；不为它编造边界规范化。

每组 `inputs.json` 保存原 Range 字符串及公开参数/原数据，`trace.json` 保存原 PB、请求和完整 HTTP 响应字节，`range-cases.json` 是逐响应提取。错误正文或字节核验的附加字段仅存在 compact，原 trace 不改。`range-input-output.json` 仅把这些原响应提取为 Rust 可直接读取的字节数组，避免另加解码依赖；离线检查从 raw 逐项反查它。`manifest.json` 只绑定输入输出和日志的完整性，不绑定或归档源码。

两次采集均退出 0、WS close 1000、cleanup_errors 为空；自有 PID 59884/41568 停止，61428/51437 无监听且核验退出 0，无 browser/profile。第一次 Rust 夹具误用未声明 base64 crate 的编译失败留在本地 `target/checks/m3-media-range/rust/compile-before.log`；改读提取字节后真实红复现 suffix 应为 206 却是 200，见 `before.log`。修复不改公开解析器签名或新增依赖；非空无效 Range 不再偷偷返回整文件。

日常复用全部冻结数据，不启动 Python：

```powershell
target/pyref-venv/Scripts/python.exe -B -m pytest tests/reference/test_media_range_reference.py -q -p no:cacheprovider
cargo test --workspace --locked --lib media_ranges_match_twenty_seven_frozen_public_http_requests
cargo test --workspace --locked --lib byte_range_parser_matches_frozen_response_intervals
```

本批仅覆盖记录的 GET 输入。HEAD、If-Range/CORS、重复 Range header、全部整数字符或超长 header、所有媒体类型及完整资源生命周期仍未完成验收；没有通过这些 HTTP 结果宣称完整视频播放或所有 Range 语法兼容。
