# Rust 原生下载保存

2026-10-27，构建当前 `buttons` 示例，自有 127.0.0.1:8523 服务、隔离 headless Chrome/profile，未修改官方前端。真实点击 **Save default bytes** 与 **Save Unicode CSV**，磁盘分别保存 `streamlit_download.bin` 和 `数据 é.csv`，均为原始 18 字节 `id,region\nA,north\n`。

`trace.json` 包含原始 PB/解码、CDP 请求/事件、DOM、两阶段和资源清理。每阶段下载事件的 suggestedFilename、完成事件和实际落盘文件互相核对；PNG 是各阶段页面截图。`manifest.json` 校验数据、截图、日志和下载字节，不绑定源码 SHA。采集脚本不是冻结证据门槛。

两个媒体 HTTP 响应均为 200；默认 `application/octet-stream` 配普通 filename，Unicode CSV 为 `text/csv; charset=utf-8` 配扩展 UTF-8 filename。浏览器在加载前端按钮时已经 Fetch 文件，之后真实点击保存；不能将这些记录描述为点击后重新发起 HTTP 请求。两按钮使用 `ignore_rerun(true)`，本次不验证触发重跑的下载。

Recorder 复用组件采集工具，原 CDP events 的 `_target` 标签沿用 `python-componentv2-state`，标签不表示本次运行时。trace 的 runtime、实际 URL/PID、PB 和网络响应均来自 Rust；不改写原事件消除这一历史命名。

自有服务 PID 77600、Chrome PID 66616 均停止，8523 无监听，临时 profile 已移除，cleanup_errors 为空。只有两条 Rust 浏览器保存场景；[十条 Python 公开输入/协议/HTTP 参考](../../reference/reference-browser/download-boundaries/README.md)未使用浏览器，不据此声称十条均经 Python 浏览器保存或完整下载能力已验收。
