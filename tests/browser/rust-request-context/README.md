# request_context：真实前端证据（M4 前两切片）

2026-10-28，caller-owned `request_context` 示例服务器（默认白名单）+ 官方前端 + [request_context_capture.py](../request_context_capture.py)。两阶段：默认 URL 与 `?embed=true`。

实测：白名单头（小写名）反映 Chrome 真实连接，无凭据/传输头泄漏；页面上下文经前端随 rerun 上报的 `context_info` 到达——`url`、`locale=zh-CN`、`timezone=Asia/Shanghai`、`timezone_offset=-480`、`theme=dark` 全部填充；`is_embedded` 随 `?embed=true` 由 false 变 **true**（官方 1.66.1 前端对 `?st_embed=true` 报告 false，实测 Python 亦然，故该旗标只认浏览器报告）。全程无 stException。

对照参考：[原生 WS 协议参考](../../../tests/reference/reference-browser/context-headers/README.md)（全部握手头、原生连接无页面上下文）与[浏览器路径参考](../../../tests/reference/reference-browser/context-browser/README.md)（context_info 携带全部页面字段）。Rust 的默认白名单与小写规范化是刻意安全差异，`All` 模式经 WS 回归逐头对齐。caption DOM 抓取因 testid 差异未纳入断言。边界：一次采集、一台机器；cookies 与 ip 未实现。
