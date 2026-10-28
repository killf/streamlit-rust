# request_context：真实前端证据（M4 首切片）

2026-10-28，caller-owned `request_context` 示例服务器（默认白名单）+ 官方前端 + [request_context_capture.py](../request_context_capture.py) 一次采集。两阶段：默认 URL 与 `?st_embed=true`。

实测：渲染的 JSON 反映 Chrome 真实连接的白名单头（小写名：`accept-language`、`host`、`origin`、`user-agent`——Chrome 的 WS 握手不带裸 `accept`，与单元/WS 回归的输入面一致），无凭据/传输头泄漏；`is_embedded` 随 `?st_embed=true` 由 false 变 **true**——官方前端把 `st_embed` 回传到 rerun 查询串，与服务端推导一致。全程无 stException。对照 [冻结 Python 参考](../../../tests/reference/reference-browser/context-headers/README.md)（全部握手头、原名大小写、原生连接空前端字段）；Rust 的白名单与小写规范化是记录在案的刻意差异，`All` 模式经 WS 回归逐头对齐参考集。caption 测试点未在 DOM 抓取（testid 差异），`is_embedded` 由 code 文本直接证明。边界：一次采集、一台机器；cookies/url/locale/timezone 字段未实现（后者待浏览器路径实测）。
