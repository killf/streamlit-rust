# 嵌套缓存输出 — Python 参考

2026-10-27，在一个隔离的 Python Streamlit **1.66.1** 会话中，一次完成官方前端的初始加载和真实 `Again` 按钮点击。两轮 `NewSession` 的实际 wire 版本均为 1.66.1，均以 `FINISHED_SUCCESSFULLY` 结束。Chrome 为 155.0.8059.85。

应用：[cache_nested_app.py](../../cache_nested_app.py)。采集器：[cache_nested_capture.py](../../../browser/cache_nested_capture.py)。分别定义独立的 `cache_data` 和 `cache_resource` outer/inner 函数。每轮依次调用 data outer A、B，再调用 resource outer A、B；两个 family 的 inner 都固定输入 7、返回 14，outer 返回 15。每个 outer 写 `family-before-{arg}`、调用 inner 写 `family-inner`、再写 `family-after-{arg}`；调用外写 `family-return-{arg}=15`。第二轮在所有调用之前增加 `leading`。

| 实际观察 | 首轮 load | 第二轮 again |
| --- | --- | --- |
| data outer / inner 执行累计次数 | 2 / 1 | 2 / 1 |
| resource outer / inner 执行累计次数 | 2 / 1 | 2 / 1 |
| 四个 outer 返回值 | 全部 15 | 全部 15 |
| `new_element` 数量 | 18 | 19（增加 leading） |
| `new_transient` 数量 | 4 | 0 |

首轮每个 family 的 A 是 outer/inner 双 miss，B 是 outer miss、inner hit；第二轮 A/B 都是 outer hit。计数来自应用真实 `st.session_state`，在页面末尾的 JSON 与 PB code 元素中保留；它们说明第二轮闭包没有再次执行，而内层输出仍按 before、inner、after 的顺序重放。

首轮四个 transient 分别位于 data A、data B、resource A、resource B 的 outer after 与外部 return 输出之间，路径依次为 `[0,0]`、`[0,4]`、`[0,8]`、`[0,12]`，实际内容均为 `{"new_transient":{}}`。没有额外的可见 inner transient。第二轮只产生持久元素：`leading` 位于 `[0,0]`，原有 18 个元素路径全部后移一位，code 从 `[0,16]` 变为 `[0,17]`，Again 从 `[0,17]` 变为 `[0,18]`。这是本次真实数量与顺序，没有按单层缓存的 transient 假设补造或删减。

`cache-cases.json` 从本次真实 PB 与页面 JSON 提取，每轮保留完整 `timeline`（全局 frame 索引、原始 delta path 和原始 delta 对象）、`returned`、`counters`、`round`。可直接供 Rust `include_str!` 回归使用；按钮 ID、code JSON 和 transient 均保留原值。`trace.json` 保留完整 51 个双向 PB frame 的原字节/base64/解码、557 个原始 CDP 事件、11 个发出命令及响应、每阶段范围、DOM、版本、启动配置和清理状态。

`load.png` 与 `again.png` 是实际页面截图，显示完整输出顺序；末尾单行 JSON 的右侧因浏览器横向滚动而被截断，完整内容仍在 DOM、原始 PB 和紧凑 JSON 中。`manifest.json` 仅校验数据文件大小与 SHA；Git revision 和机器路径只追溯采集来源，不作为源码一致性条件。没有源码 SHA 或源码归档。

只使用本地假数据。采集结束确认自有 server/Chrome PID 均已退出、两个端口均已关闭、临时 profile 已删除；trace 中 `cleanup_errors` 为空。冻结文件与成功采集目录中的原字节一致。采集命令为：

```powershell
target/pyref-venv/Scripts/python.exe -B tests/browser/cache_nested_capture.py --out target/checks/cache-nested-reference-once
```

输出目录必须不存在，以防覆盖正确证据。此后直接复用冻结数据，无需因 Rust 或采集器源码变化重新采集。覆盖仅限这两轮单会话场景；未验证 cache clear、TTL、并发、跨会话 resource 共享、异常、容器嵌套或更多层递归。
