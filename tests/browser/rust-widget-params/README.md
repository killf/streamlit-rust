# 控件创建参数边界：Rust 对照证据（M3 widgets 切片）

2026-10-28，caller-owned `widget_params` 示例服务器（8599）+ 同一[采集器](../widget_params_capture.py) --url 模式，与 [Python 参考](../../reference/reference-browser/widget-params/README.md)同调用集。

实测对齐：**8/8 元素字段一致**（heading + 3×number_input + 2×radio + text_area + multiselect；widget id 掩码）。WS 回归 `widget_parameter_edges_match_the_frozen_reference` 断言 float format/步长/哨兵、整型 %d 与无旗标、radio index=None 无 default、horizontal/captions、text_area max_chars/placeholder 与元素级 height、multiselect max_selections。边界同参考。
