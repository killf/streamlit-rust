# 上传并发与断线过期：Python 1.66.1 协议参考（M3 输入收尾）

2026-10-28，锁定 Python 1.66.1 服务器（`--server.disconnectedSessionTTL=3`）+ 原生 WS + 授权 HTTP，[uploads_lifecycle_capture.py](../../../browser/uploads_lifecycle_capture.py) 一次采集冻结；全部 WS 帧与 HTTP 交换逐条记录。

实测语义：

- **并发不互斥**：两个 PUT 并发打不同上传 URL → 双 204，互不干扰；两个 PUT 并发竞争同一 URL → 双 204，最终存储恰为**一次完整写入**（本次冻结为 B 版本 22 字节，无混合/损坏），由控件状态回读证实。
- **断线过期**（配置名 `server.disconnectedSessionTTL`，默认 120 秒，与 Rust `with_disconnected_session_ttl` 同语义同默认）：WS 断开超过 TTL 后，对该会话上传 URL 的 PUT 答 **400**（未知会话），DELETE 仍 **204**（幂等）；未知会话 PUT 控制组同样 400（与官方 8601 观测一致）。

Rust 对照回归 `upload_concurrency_and_expired_sessions_match_the_reference` 以 1 秒 TTL 服务器复现同链：并发不同 URL 双 204、同 URL 竞争幸存内容为完整其一、断线超时后 PUT 400 / DELETE 204。另注：超限 413 与本参考的重置语义共享"RST 可能丢弃在途状态行"的传输现实（超限回归按"送达的 413 或空中止"双形态断言，不存储为更强保证）。边界：单机、单会话、两写者竞争；更高并发度与多写者损坏窗口不冒称已测。离线断言见 `tests/reference/test_uploads_lifecycle_reference.py`。
