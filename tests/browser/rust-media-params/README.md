# 媒体播放参数：Rust 对照证据（M3 媒体切片）

2026-10-28，caller-owned `media_params` 示例服务器（8593）+ 同一[采集器](../media_params_capture.py) --url 模式，与 [Python 参考](../../reference/reference-browser/media-params/README.md)同七调用。

实测对齐：六元素参数字段逐项一致（start/end 整秒、loop/autoplay/muted、autoplay 携带 `$$ID-<32hex>-None`）；**媒体 URL 与 Python 逐哈希一致**（`/media/7a0a…wav`、`/media/4f87…` 裸地址、`/media/160e…mp4`）——内容寻址哈希同构，含 `audio/x-wav` 无后缀实测；字幕轨 label=VTT 文本 → `.vtt` 媒体地址（哈希含坐标，跨端不同，断言掩码）；非法字幕渲染同形 `StreamlitAPIException` 异常元素（消息逐字一致；堆栈为 Rust 真实上下文行）。字幕 URL 哈希与 autoplay id 哈希的跨端差异是记录的运行时身份差异。构建器：`AudioOptions/VideoOptions` 的 `start_time/end_time/loop_/autoplay/muted/subtitle`；SRT 文本按参考规则转换（未实测路径）。
