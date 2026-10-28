# 布局与流式参数：Python 1.66.1 参考（M3 布局/流式切片）

2026-10-28，锁定 Python 1.66.1 + 原生 WS，[layout_params_capture.py](../../../browser/layout_params_capture.py) 一次采集冻结；参考应用 [layout_params_app.py](../../layout_params_app.py)。逐 add_block/new_element 记录（含块级 id/宽度）。

实测语义：

- **expander**：`type="compact"` → `type: COMPACT`（默认 DEFAULT 缺省）；icon 原样；expanded 布尔。
- **popover**：`type="primary"` → 字符串 primary；help/disabled 透传；`use_container_width=True` 由**块级 stretch 宽度**承载（默认 content）；`open: false` 显式置位。
- **tabs**：`default=` 接受**标签**而非索引（传索引实测抛 StreamlitValueError）；命中 → `tab_container.default_tab_index`（Beta=1）。
- **dialog**：width large → `width: LARGE`；块先发 `$$ID-<32hex>-None` 再以 `is_open: true` 重发同路径。
- **status**：即 expandable 块（RUNNING/spinner → COMPLETE/:material/check: 或 ERROR/:material/error:）；`update(label/state)` 重发同路径；**update 未传 expanded 时重发不带该字段**（None 清除），传了才置位。
- **toast duration**：short→4、long→10、毫秒整数按原值（1500）。
- **spinner show_time**：本原生 WS 采集无可观测增量（transient 形态由 elements 链另行测量）。

Rust 对照（[浏览器证据](../../../browser/rust-layout-params/README.md)）：**14/14 块发射逐字一致**。离线断言 `tests/reference/test_layout_params_reference.py`。
