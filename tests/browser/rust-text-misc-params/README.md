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


## Divider complete layout (2026-10-30)

--scenario dividers / ?case=dividers records nine complete Elements: the
input report, default/explicit stretch and 1/240/i32::MAX-pixel dividers,
plus Markdown, caption and LaTeX controls. Python dividers/trace.json omits
alignment and wrap for DIVIDER. Rust dividers-before retains the five wrong
LEFT configs; fixed dividers matches all nine full Elements and paths.
The controls ensure Native/Caption retain LEFT and LaTeX remains without it.
Four coherent wrong-wire guards reject alignment, explicit-false wrap,
pixel-width and control-alignment corruption after decoding raw protobuf.
Invalid/nonpositive sizes, values outside Rust i32 and browser geometry are
not verified here. Old captures are unchanged; this is not an identity fix.


## Divider error/recovery contract (2026-10-30; decision pending)

--scenario divider-errors drives zero -> negative -> caught -> recovered on
one WS/session. Python divider-errors has 11 Elements: two uncaught errors
with no after output, three caught invalid widths followed by valid width=1,
and a successful width=240 recovery; runs are 1/2/3/4. Rust divider-errors-before
has 16 Elements, emits 0/4294967295/2147483648 widths, returns normally and
continues after the invalid calls. Both have four successful transport finishes;
that does not prove semantic parity. Recovery alone matches in full.

The gate binds all raw frames, requests, stable session ids, paths, ordered
error/continuation/state results and recovery. Four coherent wrong-wire guards
reject message/type/caught-result/recovery-counter corruption. This is retained
failure evidence. Production validation/error handling is unchanged. Options
in .codex/architecture.md cover Result-returning calls versus validated options,
plus the actual fallible entry/macro dependency; user choice is pending.


## Actual Chrome layout follow-up (2026-10-30)

layout-ui/trace.json contains four Browser Use observations per runtime:
dividers, normalization top, real End-to-bottom and Home-to-top. Nine divider
and 85 normalization containers match in text, heading/child structure,
width/height and relative positions. Eight JPEGs across both runtimes retain
full divider context and normalization top/bottom. Plain-text CRLF/CR and
Unicode/empty cases are checked; a standalone CR yields a heading soft break.

Raw viewport heights (1305/1249 at width 2560) and x origins (923/928) are kept.
Only content comparisons subtract the first container x and add bottom scroll;
there is no identical-full-screen-pixel claim. Both render requested 1px at
16px, 240px at 240px, and huge divider width at the 704px parent. End animation
intermediates were observed; final scroll tops equal max and Home restores 0.

Six matching KaTeX Unicode warnings are retained on both runtimes. No app
exception occurred, but the console is not described as clean. Rust's first
top screenshot timed out; only that screenshot was retried on the same tab.
No input or navigation was replayed. Six guards reject wrong width/text/tag,
scroll, console or image observations. This batch changes no production code;
invalid-width/identity/API decisions and other themes/viewports remain open.


## Badge labels/icons and text help (2026-10-30)

--scenario badge-content / ?case=badge-content emits 18 complete Elements:
the input report, 12 badges and five Markdown/caption/heading help controls.
Python badge-content is frozen; Rust badge-content-before retains all 17
content mismatches, while fixed badge-content matches whole Elements/paths.
Labels only escape brackets; original backslashes, blank/padded/multiline
labels and Markdown remain. Valid/blank icons trim Python boundary whitespace,
including U+001C/U+001F. Help dedents but retains leading/trailing LF.

Seven coherent wrong-wire guards reject bracket/backslash mistakes, label
stripping, untrimmed icon, untouched help indent, stripped help boundaries
and heading help errors. Public APIs/hash expressions are unchanged; normalized
label/icon fields naturally affect existing hashes. Help identity omissions,
invalid icon error handling, non-string conversion and new tooltip/UI or
attribute-update verification remain open. Older UI/wire captures are kept.


## Actual badge/tooltips in Chrome (2026-10-30)

badge-content-ui/trace.json retains eight observations and four JPEGs per
runtime. The input report was collapsed once, then seven real mouse-hover
targets were checked: plain badge, Material/backslash Help, markdown, caption,
and h1/h2/h3 help. Read-only DOM observations retain actual tooltip names,
paragraph text and strong formatting; help is rendered as bold in the common
controls. All 12 labels match visible text/colors and bold/code semantics.

Hidden zero-size measurement spans are kept in the raw badge list, while
visible_badges separately filters positive-size visible spans. An empty label
has no visible badge. Directive-like x] :red-badge[other renders x] [other on
both runtimes; this is observed parser behavior, not a general escaping claim.

Four screenshot timeouts returned no bytes; existing files were checked and
only missing screenshots retried. No collapse or hover was replayed during
recovery. Explicitly activating the owned tabs preceded the final successful
captures. Collection notes retain the initial Python hover probe/dismissal.
Nine guards reject wrong label/color/format/empty state, tooltip/action or image
observations. Warn/error buffers were empty in the measured window; task tabs,
services and listeners were cleaned up. No production change or parameter
rerun is included, and dynamic help identity remains a separate open problem.


Image audit: Python markdown-help.jpg is byte-identical to initial.jpg and
contains no tooltip. It is retained and excluded from tooltip image proof.
The separate markdown-help-confirmation.json preserves two unused normal
screenshot attempts, then a visually checked markdown-help-cdp.jpg captured
through supported tab CDP Page.captureScreenshot with visible DOM/opacity=1.
No old image/capture was overwritten. This adds three Python observations and
three JPEGs (19 observations / 11 JPEGs overall); all hashes, decoded dimensions
and evidence-use flags are checked. Extra owned tabs/services were closed.
