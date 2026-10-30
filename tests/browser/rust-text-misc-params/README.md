# 文本族/杂项参数：Rust 对照证据（M3 切片）

2026-10-29，caller-owned `text_misc_params` 示例服务器（8606）+ 同一[采集器](../text_misc_params_capture.py) --url 模式，与 [Python 参考](../../reference/reference-browser/text-misc-params/README.md)同调用集。

实测对齐：**5/5 字段一致**。本批修复两处真实偏差：`st.latex` 此前发普通 NATIVE markdown（应为 LATEX 类型 + wrap 缺省）；`st.divider` 此前 wrap true（应缺省）——`MarkdownElement::wrap` 因此改为 `Option<bool>` 以区分"显式 false"与"省略"。`st.help` 的 name/type/value 为显式 API 用法对齐（Rust 无 Python 内省，设计如此）。边界同参考。


## Retained multi-element attribute update failures (2026-10-30)

[identity-before/trace.json](identity-before/trace.json) is three native WS
requests on the existing example at `?case=identity`. Five targets send changed
inner fields while retaining the same hash. The Python reference has A/B/A
hashes. Inner field parity excludes runtime widget ids; full Elements still
have eight separately recorded layout-presence differences.

[identity-ui-before/trace.json](identity-ui-before/trace.json) is actual Chrome
Browser Use with three observations and three JPEGs: alternate=true does not
update the anchor/divider or caption style and incorrectly leaves Action
enabled. No Action click or tooltip hover was performed. The capture is marked
successful=false, and the positive semantic gate rejects its stale values.

This batch adds diagnostic evidence and a workflow proposal, not a production
fix. Central full-Element hashing, explicit producer hashing or field-tuple
repair awaits user choice; the shared scope is in .codex/architecture.md.
All owned connections/tabs/services closed and 8606/18606 had no listeners.
The original five-element creation capture remains unchanged. Remaining UI,
layout and identity behavior stays partial.


## Layout presence correction (2026-10-30)

The Python layouts/trace.json retains all 17 cases, including nondefault
alignment. layout-widths/trace.json contains the 13 cases expressible through
the existing external Rust API plus their JSON report (14 full Elements).
Use --scenario layout-widths, or ?case=layouts&only_widths=true. Markdown's
default/auto width is absent; explicit stretch/content/pixels are present.
Caption defaults to stretch; badge defaults to content with no alignment.
The Rust layout-widths-before capture retains seven full-payload differences;
the fixed layout-widths capture matches all 14 full Elements and paths.

Rust identity-layouts matches 24 complete Elements after widget-id normalization,
removing the eight historical layout differences. Four target hashes still
remain A/A/A. No new browser run or general identity fix is claimed. Old failed
wire/UI captures are unchanged. TextAlignment cannot currently be named from
an external crate; full Rust layouts explicitly diagnoses that gap. Root enum
export versus convenience methods awaits user decision in .codex/architecture.md.
The full 17-case reference is not replaced by the supported subset. Raw-frame,
summary, path, layout semantics and coherent wrong-wire guards are checked.
