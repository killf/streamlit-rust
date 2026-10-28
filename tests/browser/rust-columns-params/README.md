# st.columns 参数：Rust 对照证据（M3 列切片）

2026-10-28，caller-owned `columns_params` 示例服务器（8595）+ 同一[采集器](../columns_params_capture.py) --url 模式，与 [Python 参考](../../reference/reference-browser/columns-params/README.md)同七组调用。

实测对齐：**22/22 块发射字段逐字一致**（容器 gap/scale/wrap/align/justify 与列 weight/gap 复制/show_border/vertical_alignment 全对齐）。本切片修复三处真实偏差：① 容器硬编码 `scale 0.0/wrap false` → 实测 `1.0/true`，且 columns 容器的 justify=UNDEFINED、align=STRETCH 与普通容器的 START 对齐不同（`columns_flex` 构建器分离）；② 权重由 f32 计算改为 **f64**（参考 1/3=0.3333333333333333，f32 会得 0.33333334）；③ 容器 gap 此前未复制到 column 块。另修正共享容器对齐枚举映射（Center/Right 此前映射到 proto 的 END/CENTER 序号——非默认对齐未经测量，按 proto 语义纠正，默认 Left/Top 不受影响）。

边界：同参考（单行 spec、无嵌套、wrap/自定义列宽未测）。
