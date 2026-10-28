# st.context：锁定 1.66.1 的请求上下文参考（M4 首个切片）

2026-10-28，真实 Python Streamlit 1.66.1 服务器 + 原生 WebSocket 客户端（固定探测头 `User-Agent: M4ContextProbe/1.0`、`X-M4-Probe: alpha`、`Accept-Language: zh-CN,zh;q=0.9`），一次采集冻结。参考应用 [context_app.py](../../context_app.py) 把 `st.context` 的公开字段原样 `st.code` 到 wire；采集器 [context_protocol_capture.py](../../../browser/context_protocol_capture.py) 记录握手、全部 ForwardMsg 与两轮 rerun。

实测事实（Rust 设计的直接输入）：

- `headers` 返回**全部 WS 握手请求头**（含探测头与 Host/Origin/Sec-Websocket-* 传输头），Python 侧没有白名单；Rust 拟议的默认白名单是刻意的安全偏离，已在指南标注。
- `ip_address` 为 `null`：无 `X-Forwarded-For` 的直连下 Python 不回填地址。
- `url`、`timezone`、`timezone_offset`、`locale`、`theme` 在原生 WS 连接下为空/0：这些字段来自**浏览器前端会话**（页面 URL/Intl/主题协商），不是握手请求头；`is_embedded` 为 false。
- 两轮普通 rerun 的报告逐字相同，上下文不随 rerun 变化。

首次采集因采集器头部解码笔误失败于 trace 写出前，属采集器编程失误而非产品发现，已修正后一次成功；无失败前缀保留。离线断言见 `tests/reference/test_context_reference.py`。浏览器前端路径下的 cookies/theme/url 行为是后续切片，不在本参考内。
