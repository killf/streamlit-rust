# st.context：浏览器路径参考（页面上下文的到达方式）

2026-10-28，真实 Python Streamlit 1.66.1 + 官方前端 + 真实 Chrome（`?embed=true&m4=browser`），一次采集冻结。与[原生 WS 参考](../context-headers/README.md)互补：本组证明页面上下文字段**全部由前端随每轮 rerun 的 `context_info` 上报**——`url`（无查询串）、`locale`、`timezone`、`timezone_offset`、`color_scheme` 与 `is_embedded`；headers 仍为全部握手头（真实前端连接含 XSRF Cookie，佐证 Rust 默认白名单的安全动机）。

实测要点：`?embed=true` 时前端报告 `is_embedded=true`；`?st_embed=true` 报告 **false**（同日探针三次对照 plain/embed/st_embed）。原生连接（无 context_info）下这些字段为空/缺省。采集器 [context_browser_capture.py](../../../browser/context_browser_capture.py) 记录 CDP 捕获的原 PB 双向帧与渲染报告；`ip_address` 在两种路径下均为 null。离线断言见 `tests/reference/test_context_reference.py`。
