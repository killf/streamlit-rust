# json/badge/feedback 参数：Python 1.66.1 参考（M3 切片）

2026-10-29，锁定 Python 1.66.1 + 原生 WS，[json_badge_params_capture.py](../../../browser/json_badge_params_capture.py) 一次采集冻结；参考应用 [json_badge_params_app.py](../../json_badge_params_app.py)。六元素创建期 wire：

- **st.json**：`expanded=True` 显式置位；显式 `expanded=False` 时 expanded 省略（默认值其实为 True）；body 为 json.dumps 格式（", "/": " 分隔、构造序）。独立 `depth=` 关键字实测不受支持；这不排除 `expanded=int` 深度能力（该路径未在原批次测量）。
- **st.badge**：`icon`/`color` 进 markdown body（`:green-badge[:material/rocket_launch: New]`；无 icon 无分隔符）；**badge markdown 的 wrap 字段缺省（省略 = None）**——Rust 此前发 `Some(true)`，实测修正为 None。
- **st.feedback**：`disabled=True` 进消息；**feedback 位置参数即选项 preset**（`options=` 关键字实测与位置参数冲突抛 TypeError）。

Rust 对照（[原生 WS 证据](../../../browser/rust-json-badge-params/README.md)）：**6/6 字段一致**（修复 badge wrap 一处真实偏差；json/feedback 为既有行为确认）。离线断言 `tests/reference/test_json_badge_params_reference.py`。边界：badge 宽度/帮助、feedback 交互提交与 ignore 模式未纳入。


## String passthrough extension (2026-10-30)

[strings/trace.json](strings/trace.json) uses the existing app and collector
with `--scenario strings`. The capture contains 36 JSON elements: one input
report, 15 strings each emitted with default and explicit collapsed expansion,
and five structured controls (object, list, null, boolean and integer).
Strings include serialized objects/arrays/scalars, actual whitespace and
newlines, quotes, empty text, Unicode, malformed JSON and multi-document text.
NaN/Infinity here are raw strings, not native floating-point inputs.

The pinned 1.66.1 server forwards every string unchanged, without validating
or serializing it again. Even the measured invalid/empty strings finish
successfully on the server. Structured controls still use json.dumps,
including escaping their nested strings and Unicode. Frontend parsing,
error presentation and browser expansion are not tested by this native WS.
The original parameter capture and all new raw frames remain unchanged.

The Rust production API now serializes only non-string values; json delegates
to json_expanded(..., true), with no new public signature or dependency.
The true-WS test replays the input report but derives all 36 expected Json
payloads independently from the original frames: exact body, expanded,
max_expand_depth omission, complete path and stretch-width flag. Before-fix
failure is retained locally in target/json-string-red.log. A public-call unit
covers borrowed/owned strings, Value::String and a nested string control.

The Python gate now also binds the original Python/Rust element summaries and
finishes to decoded base64 protobuf bytes. Seven corruption guards check body,
path, finish, decoded-message summary, length, direction and missing elements;
all original valid captures still pass. Documentation corrections above fix
the earlier mistaken collapsed-default claim and distinguish an unsupported
depth= keyword from integer expanded; no recorded behavior was rewritten.
Owned reference processes and sockets were closed after capture.

Integer expansion depth, width options, frontend invalid-JSON handling,
custom serialization failures and exotic numeric values remain open. Current
workspace verification separately excludes the two pending rerun-queue policy
regressions; this is not a complete-workspace or browser compatibility pass.


## Real Chrome JSON rendering and disclosure (2026-10-30)

[ui/trace.json](ui/trace.json) and the [Rust trace](../../../browser/rust-json-badge-params/ui/trace.json)
retain a new live Chrome Browser Use comparison, not a native-WS-only claim.
The existing app/example now accept `?case=strings&sample=0` through sample 14;
`&collapsed=true` selects initial collapse. The original full `case=strings`
scene remains unchanged, verified by the Rust example's separate 36-element
[native preflight](../../../browser/rust-json-badge-params/strings/trace.json).
The ordinary six-element demo remains the default route.

Each runtime has 22 ordered observations: 15 default string displays; object
and array initial-collapse / real arrow-click expand / real arrow-click
collapse; then final Unicode verification. Visible main text, parse alerts,
JSON text, icons, keys and child-row counts match across all 22 pairs. Empty,
malformed and multi-document inputs show Json Parse Error alerts in the
measured cases. Valid scalar JSON and the NaN/Infinity strings instead show
the upstream react-json-view ERROR object; this observed upstream behavior
was retained. Two live disclosure cycles restore the collapsed state.

There are nine original JPEGs per runtime, with byte lengths and SHA256 in
each trace, including [Rust Unicode context](../../../browser/rust-json-badge-params/ui/unicode-context.jpg).
Full DOM snapshots and JSON component HTML remain available with the semantic
projections. The trace's collapsed flag records the initial URL option, not
the client state after an arrow click; actual icon/row/text data captures that
state. Console buffers, read at the final observation, each retain eight
identical react-json-view error messages. They are not zero-error health
claims or exact per-navigation counts.

Browser tabs and both owned local servers were closed; listeners 8604/18604
were absent afterwards. The Python process reported a Windows Proactor pipe
ConnectionResetError during the controlled shutdown after observations,
recorded separately from rendering results. No production service was used.

The Python gate validates stage coverage, local URLs, JSON/alert/arrow state,
all JPEG bytes/hashes/decodability, semantic pair equality and the native
preflight. Seven UI corruption guards cover missing states, wrong URLs,
fabricated visible text/icons, screenshot hashes, alerts and Unicode. These
are offline integrity/differential checks on retained browser observations;
they do not themselves launch a fresh browser. Collection used Browser Use
against real local pages, rather than a new standalone CI driver.

This closes only the measured string rendering and two single-level
object/array disclosure cycles. Integer expansion depth, nested disclosure
combinations, other widths/themes/responsive cases, serialization failures
and broader JSON inputs remain open. The two pending rerun-queue policy
regressions and the complete long-term target are unchanged.


## Integer expansion and width reference (2026-10-30; Rust API pending)

[expansion/trace.json](expansion/trace.json) uses `--scenario expansion` in the
same fixture/collector. It retains 18 requests to st.json inside one run,
with one input report, nine successful JSON outputs and 18 result reports
(28 elements total). Caught failure reports preserve exception names/messages;
this does not compare framework exception UI.

Integer expanded values set expanded=True and max_expand_depth, including
0, 1, 2, 3, -1 and int32 max. False instead omits expanded/depth; int32 overflow
raises ValueError and float/string expanded is rejected. Width stretch,
240/480 pixels and bool True (encoded as one pixel) succeed; 0, negatives,
content, invalid text, float and None fail. The undocumented negative/bool
cases are observations of the pinned runtime, not a recommendation to use them.

The raw gate verifies all fields, width configurations and failure reports.
Rust's current bool-only API cannot express integer depth or width here.
Three concrete interface choices have been submitted to the user, with the
recommended JsonOptions/json_options described in .codex/architecture.md.
No new JSON public interface has been implemented before that decision.


## Numeric serialization (2026-10-30; partial)

[numbers/trace.json](numbers/trace.json) is the existing collector's new
`--scenario numbers`, with 19 f64 input texts, each rendered as a scalar and
one-element array, plus an input report (39 JSON elements). It measures signed
zero, notation thresholds, mantissas, smallest subnormal, minimum positive
normal, largest finite double, NaN and both infinities over native WebSocket.
The collector stopped its owned Python process. No browser claim is made.

The retained Rust numbers-before capture differs on eight finite inputs
(16 element bodies) and three nonfinite inputs (six bodies). After the shared
encoder correction, all 16 finite inputs match Python, including `1e-05`,
`1e+16` and `1.7976931348623157e+308`, while integer formatting stays unchanged.
Production WS tests compare 33 finite/report elements with paths, full JSON
fields and stretch width; the offline gate decodes every raw protobuf frame.

NaN/Infinity/-Infinity still produce null in Rust's current to_value pipeline;
both scalar and array differences remain visible in the fixed capture. This
is recorded failure evidence, not accepted compatibility. A different internal
serialization flow needs a separate design decision; custom serialization
failures, arbitrary precision/rounding, wider numeric input sets, numeric UI,
integer expansion/width and the wider JSON scope remain open.
