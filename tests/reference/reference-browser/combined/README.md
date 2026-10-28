# combined：跨能力组合差分（M7 启动）

2026-10-28，M7 全量验收的首个组合差分链。Python 1.66.1 组合页 [combined_app.py](../../combined_app.py) 与 Rust 镜像示例 [combined.rs](../../../../streamlit/examples/combined.rs)（8596）逐调用对应，同一[采集器](../../../browser/combined_capture.py)原生 WS 各一次采集冻结：标题/说明、紧凑 expander、加权带边框列（内嵌表与指标）、双标签页（默认 Beta，两张 vega）、primary popover 内自动播放音频、status 容器内自动播放视频并更新为 complete、toast。两侧各 22 元素/26 帧。

离线差分 `tests/reference/test_combined_differential.py`：kind 序列逐项相等；Arrow 按逻辑行列类型比较、generic vega 按 accepted-A 承载差比较（既有两条约定）；其余元素字段逐字相等（含媒体内容哈希——同字节同 URL）。矩阵在 dataframe/vega/expander/popover/tabs/columns/audio/video/toast/metric/code 条目下挂 `m7_combined_differential` 交叉证据。
