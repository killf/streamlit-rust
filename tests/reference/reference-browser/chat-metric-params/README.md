# chat/metric/progress 参数：Python 1.66.1 参考（M3 切片）

2026-10-29，锁定 Python 1.66.1 + 原生 WS，[chat_metric_params_capture.py](../../../browser/chat_metric_params_capture.py) 一次采集冻结；参考应用 [chat_metric_params_app.py](../../chat_metric_params_app.py)。九元素（8 核心 + 1 Python-only 异常）：

- **chat_message**：emoji 字符串 avatar → `avatar_type: EMOJI`（material 短码为 ICON——既有测量）。
- **metric 已测 delta 情况**（frozen 实测）：无 delta 与 **delta=0** 均 `NONE + GRAY`；`delta_color="off"` 保留方向（UP）但 GRAY；负 delta normal 为 `DOWN + RED`（proto 零值缺省省略——DOWN=0/RED=0，不打印）。
- **progress**：`text` 标签随消息同行（value 50 + text）；**float overload 为 Python-only**——25.5（>1.0）触发框架异常 `outside [0.0, 1.0]`（int 0..=100 / float 0..1 双区间）。

Rust 对照（[原生 WS 证据](../../../browser/rust-chat-metric-params/README.md)）：**8/8 核心元素一致**（Python-only float 异常不适用）。本批修复三处真实偏差：① 无 delta 的颜色 RED→GRAY；② delta=0 被当作负数（DOWN+RED）→ NONE+GRAY；③ emoji avatar 被标 ICON → EMOJI；新增 `progress_options(text)`。离线断言 `tests/reference/test_chat_metric_params_reference.py`。边界：image/URL avatar、accept_file、非数值 delta、float progress 的 Rust 等价未纳入。

## String delta extension (2026-10-29)

`string-delta/trace.json` adds 36 metric cases (12 strings × normal/inverse/off)
captured over a real native WS from Python 1.66.1. The original trace remains
unchanged and describes the earlier, smaller application. The current reference
application includes this extension; source changes do not invalidate frozen data.

Only the literal dedented string `"0"` is neutral; `"0.0"`, `"0%"`, ordinary text
and `"NaN"` point up, while `"-0"` and negative text point down. Common indentation
is removed without stripping surrounding newlines. Whitespace-only lines become
empty lines; a nonempty whitespace input remains an upward delta after dedenting.

The raw protobuf frames and element summaries are cross-checked in the existing
Python regression. The Rust comparison retains both the 30/36 failing baseline
and the fixed 36/36 result; see the linked Rust evidence. This extends the metric
wire evidence only, without claiming browser rendering or all metric options.


## String avatar defaults, aliases and image URI extension (2026-10-30)

[string-avatars/trace.json](string-avatars/trace.json) adds a separate native-WS
capture (`chat_metric_params_capture.py --scenario avatars`). It contains one
JSON input report, 28 chat blocks and 28 nested markdown children. Old reference
captures remain unchanged. Fifteen cases use omitted avatars (preset aliases
and case variants, custom names, Unicode emoji names and the empty name);
thirteen supply presets, emoji, a Material icon, HTTP(S) URLs, PNG/SVG data URIs
or an /app/static/ URI. The empty-name case records runtime behavior rather
than endorsing its use for accessibility.

The fixed 1.66.1 output normalizes human/ai aliases to user/assistant. Custom
non-emoji names use an empty avatar with ICON, leaving the letter to the
frontend; emoji names use EMOJI. The six image URI cases use IMAGE (the proto
zero value, omitted from the JSON rendering) and retain their exact spelling,
including the uppercase HTTPS scheme. This is encoding evidence only; no remote
image was fetched, no static file was served and no browser display was tested.
Official scope: [chat_message](https://docs.streamlit.io/develop/api-reference/chat/st.chat_message),
currently labeled 1.66.0; runtime reference remains pinned to 1.66.1.

The Rust WS regression replays only the input report as case data. Its expected
outputs come independently from the frozen block/element frames. It compares
57 ordered projections: names, avatars/types, allow_empty/stretch width, full
paths, child text and JSON values/default expansion. Before-fix failure is
retained locally in target/chat-avatar-red.log. It also exposed invalid non-BMP
JSON escaping (five-digit escapes instead of UTF-16 pairs) and a collapsed
st.json default. These shared serialization/default defects are fixed and
covered by Unicode scalar-boundary/key/value tests plus the same WS report.
The [JSON documentation](https://docs.streamlit.io/develop/api-reference/data/st.json)
and the frozen report both specify expanded=True by default; explicit False
is preserved. An unsupported depth= keyword is distinct from the documented
integer expanded depth, which remains unimplemented in the Rust bool surface.

No public signatures/dependencies were added. Local image loading, malformed
avatars, full emoji catalogue equivalence, width/depth variants and actual
browser rendering remain open. The owned Python server/socket were closed.
