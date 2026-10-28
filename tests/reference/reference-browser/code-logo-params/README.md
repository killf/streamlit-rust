# code/skeleton/logo 参数：Python 1.66.1 参考（M3 切片）

2026-10-29，锁定 Python 1.66.1 + 原生 WS，[code_logo_params_capture.py](../../../browser/code_logo_params_capture.py) 一次采集冻结；参考应用 [code_logo_params_app.py](../../code_logo_params_app.py)。三元素 + 一个 **logo ForwardMsg**（非 delta，走顶层 `logo` 字段）：

- **st.code**：`language="rust"` 原样上 wire（任意标签不做白名单）、`line_numbers=True` → `show_line_numbers true`。
- **st.skeleton**：默认占位为空消息（无额外字段）。
- **st.logo("🧊")**：emoji 图 → `image_type EMOJI`、**缺省 `size "medium"`**、无 link/icon——元数据仅 active_scriptHash（既有约定）。

Rust 对照（[浏览器证据](../../../browser/rust-code-logo-params/README.md)）：**3/3 元素 + logo 帧逐字一致——零实现改动确认**。离线断言 `tests/reference/test_code_logo_params_reference.py`。边界：code 的 wrap_lines/height、URL/路径 logo 图、icon_image 与 link 未纳入。
