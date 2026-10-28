# 媒体/布局剩余边界：Python 1.66.1 参考（M3 收窄）

2026-10-28，锁定 Python 1.66.1 + 原生 WS，[media_more_capture.py](../../../browser/media_more_capture.py) 一次采集冻结；参考应用 [media_more_app.py](../../media_more_app.py)。四个此前未测的参数边界：

- **st.video 的 URL 输入**：直接 URL 原样上 wire（`url: "https://…"`、type NATIVE、播放参数同行），不经媒体存储/上传。
- **SRT 字幕**：合法 SRT 文本（数字首行 + `dd:dd:dd,ddd --> dd:dd:dd,ddd` 时间戳行）被参考**转换为 VTT** 后存为 `.vtt` 媒体轨——冻结轮的 SRT 与此前 VTT 文本不同但转换后媒体哈希独立（`7065bd9c…`）。
- **popover wrap**：`wrap: true` 直接进入 Popover 消息（可选字段）。
- **tabs 宽度/高度**：`width=500/height=200` 走**块级** pixel 配置（容器块带 pixel_width/pixel_height，tab 块本身不带）。

Rust 对照（[浏览器证据](../../../browser/rust-media-more/README.md)）：**6/6 元素逐字一致**。离线断言 `tests/reference/test_media_more_reference.py`。边界：多音轨字幕、YouTube/iframe 输入（需真实外部源）未测。
