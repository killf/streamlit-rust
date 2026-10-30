# 文本族/杂项参数：Python 1.66.1 参考（M3 切片）

2026-10-29，锁定 Python 1.66.1 + 原生 WS，[text_misc_params_capture.py](../../../browser/text_misc_params_capture.py) 一次采集冻结；参考应用 [text_misc_params_app.py](../../text_misc_params_app.py)。五元素创建期 wire：

- **st.text**：`wrap: true` 显式（与 markdown 族不同）。
- **st.latex**：公式为 **LATEX 类型 markdown**（body `$$\n…\n$$`）且 **wrap 缺省**——Rust 此前走普通 markdown（NATIVE+wrap true），实测修复。
- **st.help(st.dataframe)**：`doc_string`（完整 docstring）+ `name "st.dataframe"` + **`type "method"`（Python 可调用种类）** + `value`（完整签名 721 字符）——Rust 显式 API 需全量四字段，示例用法已按参考对齐。
- **st.divider()**：`---` body 的 DIVIDER 类型 markdown，**wrap 缺省**——同样实测修复（原 wrap true）。

Rust 对照（[浏览器证据](../../../browser/rust-text-misc-params/README.md)）：**5/5 字段一致**（修复 latex 类型与 divider wrap 两处偏差；help 为用法对齐而非实现缺陷）。离线断言 `tests/reference/test_text_misc_params_reference.py`。边界：caption/code/markdown 各自 wrap 语义沿用既有链。


## Cross-element identity failure reference (2026-10-30; fix pending)

[identity/trace.json](identity/trace.json) uses the existing fixture/collector's
`--scenario identity`: three requests on one native WS, 24 elements, five
attribute-changing targets. Python changes hashes A/B/A for the h2 properties,
Markdown help, badge help, Markdown-to-caption type, and button attributes.
Rust's identity-before sends the changed inner fields but keeps A/A/A hashes.
Inner projections match after widget id normalization. Full Elements still
have eight layout-presence differences (Markdown default width and badge
alignment); these are retained separately, not accepted or hidden as parity.

[identity-ui/trace.json](identity-ui/trace.json) contains actual Browser Use
Chrome initial/alternate/restored observations and three context JPEGs. Python
updates anchor/divider, caption style and disabled button state. The Rust
identity-ui-before capture keeps the old values despite alternate=true and a
checked control. Action was never clicked. Help changes have raw-frame proof;
no tooltip hover is claimed. This is retained failure evidence, not a fix.

Old default Python/Rust captures are now also bound to decoded protobuf and
finishes; six corruption guards reject summary/frame/length/direction/finish
and missing-element damage. Five UI guards reject stale attributes or image
hash damage. Both correct and failed three-stage images are decoded and checked
against byte lengths, hashes and clip dimensions. This window's warn/error
buffers were empty, tabs/services/connections were closed, and ports 8606/18606
had no listeners afterward. Gates replay saved data rather than launch Chrome.

The reviewable scope/options live in .codex/architecture.md under Pending unified
NewElement identity decision. Recommended central stamping would hash complete
Element protobuf bytes before send/record/stream and remove duplicate manual
hash work, preserving public identifiers, metadata and cacheable=false. A user
choice is required for this shared workflow change; production hashing is still
unchanged. Broader attributes, maps/performance and all other compatibility gaps
remain open, including the separate layout differences noted above.


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


## Text normalization (2026-10-30)

Use --scenario normalization or ?case=normalization. normalization-valid is
correct Python evidence: 12 string inputs across markdown/caption/text/three
heading levels/latex plus the input JSON report, 85 complete Elements. Python
3.14.7 dedent removes common ASCII space/tab prefixes, clears Unicode blank
lines and retains interior CRLF. Rust normalization-before retains 72 differing
payloads; Rust normalization matches all 85 full Elements and delta paths.
LaTeX cleans the formula before display delimiters; width is stretch and its
alignment config is absent. Unit and real WS tests check production behavior.

The first Python normalization trace is retained as fixture-error evidence:
a JSON surrogate pair was mistakenly pasted into a Python literal and caused
UnicodeEncodeError in the last case (79 elements, including the exception).
Its successful flag only records transport completion. The corrected fixture
uses a Unicode scalar, and normalization-valid is a new capture, not an edited
replacement. Five coherent wrong-wire guards reject mixed-indent, CRLF,
Unicode stripping and LaTeX width/alignment damage. No new browser/UI or
non-string conversion claim is made; other compatibility gaps remain open.
