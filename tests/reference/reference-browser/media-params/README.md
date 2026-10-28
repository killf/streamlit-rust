# 媒体播放参数：Python 1.66.1 参考（M3 媒体切片）

2026-10-28，锁定 Python 1.66.1 + 原生 WS，[media_params_capture.py](../../../browser/media_params_capture.py) 一次采集冻结；参考应用 [media_params_app.py](../../media_params_app.py)。六个有效调用 + 一个非法字幕调用：

实测语义（逐元素 wire）：

- **audio 参数**：`start_time`/`end_time` 为整秒（1.5 → 1，`int()` 截断）、`loop`、`autoplay`；autoplay 时携带 `id = $$ID-<32hex>-None`（元素身份，跨运行时哈希不同）；无参数时这些字段全部缺省。
- **video 参数**：上述全部 + `muted`；同样仅 autoplay 带 id。
- **format → 地址后缀**：`audio/wav` → `/media/<hash>.wav`；**`audio/x-wav` → 裸地址无后缀**（实测）；内容寻址使同字节共享同 URL。
- **字幕**：`{"en": "<VTT 文本>"}` → `subtitles: [{label, url: /media/<hash>.vtt}]`（URL 哈希含元素坐标，跨端不同）；SRT 文本被接受并转 VTT（未在本组实测）。**非法值**（非 VTT/SRT 文本，如 data: URL）→ 框架渲染 `streamlit.errors.StreamlitAPIException` 异常元素（markdown 标记、streamlit_error 置位、stretch 宽度、真实 Python 堆栈行），本组实测该调用为最后一条语句且 run 以 `FINISHED_SUCCESSFULLY` 结束。

Rust 对照（[浏览器证据](../../../browser/rust-media-params/README.md)）：六元素字段结构逐项一致、**媒体 URL 逐哈希一致**（内容寻址同算法）；autoplay id 形状一致（哈希如 dialog 属运行时身份）；非法字幕同样渲染异常元素（类型/消息/markdown 标记一致；堆栈行为 Rust 真实上下文行，不冒称 Python 路径）。离线断言 `tests/reference/test_media_params_reference.py`。边界：SRT 转换、多音轨、YouTube/URL 输入、alt 未测。
