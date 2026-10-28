# st.columns 参数：Python 1.66.1 参考（M3 列切片）

2026-10-28，锁定 Python 1.66.1 + 原生 WS，[columns_params_capture.py](../../../browser/columns_params_capture.py) 一次采集冻结；参考应用 [columns_params_app.py](../../columns_params_app.py)。七组调用：默认、gap medium/large、border、vertical_alignment center/bottom、加权 spec 全参数。

实测 wire 语义：

- **flex_container**（每组一个）：`gap_config.gap_size`（SMALL/MEDIUM/LARGE）、`scale: 1.0`、`direction: HORIZONTAL`、`wrap: true`、`align: STRETCH`（justify 缺省 = UNDEFINED）、块级 stretch 宽度。
- **column**（每列一个）：`weight` 为 **double 精度**（等分三列 = 0.3333333333333333，[3,1] = 0.75/0.25）；**容器的 gap 同时复制到每个 column 的 `gap_config`**；`show_border`（border=True）；`vertical_alignment`（CENTER/BOTTOM，默认 TOP 缺省）。

Rust 对照（[浏览器证据](../../../browser/rust-columns-params/README.md)）：**22/22 块发射逐字一致**（本切片修复了三处真实偏差，见该 README）。离线断言 `tests/reference/test_columns_params_reference.py`。边界：单行 spec、无嵌套；wrap=False/自定义宽度、列内换行未测。
