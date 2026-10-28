# 文本族/杂项参数：Rust 对照证据（M3 切片）

2026-10-29，caller-owned `text_misc_params` 示例服务器（8606）+ 同一[采集器](../text_misc_params_capture.py) --url 模式，与 [Python 参考](../../reference/reference-browser/text-misc-params/README.md)同调用集。

实测对齐：**5/5 字段一致**。本批修复两处真实偏差：`st.latex` 此前发普通 NATIVE markdown（应为 LATEX 类型 + wrap 缺省）；`st.divider` 此前 wrap true（应缺省）——`MarkdownElement::wrap` 因此改为 `Option<bool>` 以区分"显式 false"与"省略"。`st.help` 的 name/type/value 为显式 API 用法对齐（Rust 无 Python 内省，设计如此）。边界同参考。
