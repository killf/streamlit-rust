# user/cookies：Rust 对照证据（M4）

2026-10-28，caller-owned `auth` 示例服务器（8592，`HeaderAuthenticator("x-test-user")` + cookies/user-agent 白名单）+ 同一[采集器](../user_cookies_capture.py) --url 模式（不带身份头 → 匿名连接）。

实测对齐 [Python 参考](../../reference/reference-browser/user-cookies/README.md)：`st.user().to_dict()` 匿名为**空映射**（1.66.1 基线），cookies 解析逐字一致（probe-flavor/probe-session 同值）；已认证路径（x-test-user 假凭据 → sub/name/roles/claims 映射）无 Python oracle，由 WS 回归 `header_identity_and_cookies_ride_the_connection` 与 `without_an_authenticator_the_user_mapping_is_the_anonymous_baseline` 证明，单元测试覆盖认证器解析边界（垃圾 JSON、缺 sub → 匿名）与 cookies 解析（无 `=` 段跳过、白名单外不可见）。

边界：认证为假凭据（本地/测试）；OIDC tokens 子视图未实现；cookies 仅在白名单显式放行 Cookie 头后可见（与 Python 全量可见的差异有意识地收窄，凭据安全默认）。
