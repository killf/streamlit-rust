# 媒体/布局剩余边界：Rust 对照证据（M3 收窄）

2026-10-28，caller-owned `media_more` 示例服务器（8597）+ 同一[采集器](../media_more_capture.py) --url 模式，与 [Python 参考](../../reference/reference-browser/media-more/README.md)同四调用。

实测对齐：**6/6 元素逐字一致**（URL 视频、SRT→VTT 字幕轨媒体哈希、popover wrap、tabs 块级宽高）。本批修复一处真实缺陷：Rust 的 SRT 时间戳校验器字节偏移写错，把合法 SRT 判为非法（渲染异常元素而非播放器）——冻结参考对照即刻暴露，已按 `dd:dd:dd,ddd` 逐位校验重写。新构建器：`VideoOptions::from_url/url`（URL 输入不经媒体存储）、`PopoverOptions::wrap`、`TabsOptions::width/height`（块级 pixel 配置）。边界同参考。
