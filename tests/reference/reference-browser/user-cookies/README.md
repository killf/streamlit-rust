# st.user（匿名）与 st.context.cookies：Python 1.66.1 参考（M4）

2026-10-28，锁定 Python 1.66.1 + 原生 WS（探测 Cookie `probe-flavor=oat; probe-session=42`），[user_cookies_capture.py](../../../browser/user_cookies_capture.py) 一次采集冻结；参考应用 [user_cookies_app.py](../../user_cookies_app.py)。

实测语义：

- `st.user` 是**映射代理**（get/items/keys/to_dict/values/tokens），无属性式访问（`st.user.name` 抛 AttributeError）；1.66.1 无本地认证器，真实连接下 `to_dict()` 为**空映射**、键列表空。`tokens` 子代理存在，无提供方下行为未测。
- `st.context.cookies` 为 dict-like：从握手 Cookie 头解析（`{"probe-flavor":"oat","probe-session":"42"}`），缺失键 `get` 返回 None；Python 侧无门控（cookies 随 headers 全量可见）。
- Python 1.66.1 **不存在已认证 oracle**（OIDC 需托管平台提供方），本参考锚定匿名基线与解析语义；Rust 的认证路径（假凭据）无 Python 对照，由 WS 回归证明。

Rust 对照（[协议证据](../../../browser/rust-user-cookies/README.md)）：同一采集器 --url 对 `auth` 示例——匿名映射与 cookies 解析逐字一致。设计按指南推荐实施（trait + 内置假凭据 + cookies 跟随白名单），公共形态待用户追认。
