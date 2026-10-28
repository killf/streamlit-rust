# 文本族/杂项参数：Python 1.66.1 参考（M3 切片）

2026-10-29，锁定 Python 1.66.1 + 原生 WS，[text_misc_params_capture.py](../../../browser/text_misc_params_capture.py) 一次采集冻结；参考应用 [text_misc_params_app.py](../../text_misc_params_app.py)。五元素创建期 wire：

- **st.text**：`wrap: true` 显式（与 markdown 族不同）。
- **st.latex**：公式为 **LATEX 类型 markdown**（body `$$\n…\n$$`）且 **wrap 缺省**——Rust 此前走普通 markdown（NATIVE+wrap true），实测修复。
- **st.help(st.dataframe)**：`doc_string`（完整 docstring）+ `name "st.dataframe"` + **`type "method"`（Python 可调用种类）** + `value`（完整签名 721 字符）——Rust 显式 API 需全量四字段，示例用法已按参考对齐。
- **st.divider()**：`---` body 的 DIVIDER 类型 markdown，**wrap 缺省**——同样实测修复（原 wrap true）。

Rust 对照（[浏览器证据](../../../browser/rust-text-misc-params/README.md)）：**5/5 字段一致**（修复 latex 类型与 divider wrap 两处偏差；help 为用法对齐而非实现缺陷）。离线断言 `tests/reference/test_text_misc_params_reference.py`。边界：caption/code/markdown 各自 wrap 语义沿用既有链。
