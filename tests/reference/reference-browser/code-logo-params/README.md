# code/skeleton/logo 参数：Python 1.66.1 参考（M3 切片）

2026-10-29，锁定 Python 1.66.1 + 原生 WS，[code_logo_params_capture.py](../../../browser/code_logo_params_capture.py) 一次采集冻结；参考应用 [code_logo_params_app.py](../../code_logo_params_app.py)。三元素 + 一个 **logo ForwardMsg**（非 delta，走顶层 `logo` 字段）：

- **st.code**：`language="rust"` 原样上 wire（任意标签不做白名单）、`line_numbers=True` → `show_line_numbers true`。
- **st.skeleton**：默认占位为空消息（无额外字段）。
- **st.logo("🧊")**：emoji 图 → `image_type EMOJI`、**缺省 `size "medium"`**、无 link/icon——元数据仅 active_scriptHash（既有约定）。

Rust 对照（[原生 WS 证据](../../../browser/rust-code-logo-params/README.md)）：原批次 **3/3 元素和 logo 字段一致——该原始调用集零实现改动确认**。离线断言 `tests/reference/test_code_logo_params_reference.py`。边界：code 的 wrap_lines/height、URL/路径 logo 图、icon_image 与 link 未纳入。


## Logo string sequences and icon_image extension (2026-10-30)

[logo-strings/trace.json](logo-strings/trace.json) adds 18 complete Logo
ForwardMsgs from the pinned 1.66.1 server (`--scenario logo-strings`). A JSON
report supplies the original inputs. Twelve emoji sequences cover variation
selectors, ZWJ professions/family/rainbow, flags, keycaps and skin tones; two
Material icons plus four HTTP(S)/data/static URIs exercise the other types.
The cases rotate both image and icon_image, all three sizes and optional links.

The Rust production WS test replays input data and compares all six Logo
fields in order, plus nonempty active-script metadata and absent delta paths.
Before-fix failure is retained locally in target/logo-strings-red.log: 9/18
payloads differ because character-count detection treated complex sequences
as image URLs. The fix reuses the existing emojis dependency in automatic
borrowed/owned string conversion; both image fields now classify correctly.
The original capture remains unchanged. URI and link values are protocol
observations only: no image fetch, click, sidebar interaction or browser
rendering is claimed by this extension.

The old element comparisons are now also bound to decoded raw frame data;
six corruption guards cover summaries, paths, finishes, Logo message typing,
length and direction. New Logo cases compare the entire payload, rather than
the original four-field logo tuple. Source hashes are not acceptance gates.
Owned reference processes/sockets were closed. Local/byte images, invalid
strings/links, full emoji-catalogue equality and browser behavior remain open.


## Code text, languages and valid layout parameters (2026-10-30)

[code-text/trace.json](code-text/trace.json) uses `--scenario code-text` in the
existing fixture/collector: 27 code calls and a JSON input report (28 elements).
Thirteen text inputs cover empty/single/multiple LFs, indentation and spaces,
CRLF/CR, tabs, non-ASCII whitespace and Unicode. The cases rotate arbitrary,
case-sensitive, empty and single-space language tags, line_numbers, wrap_lines
and all nine stretch/content/positive-pixel width/height pairs. The final case
uses language=None, which the Rust replay represents with an empty string;
this is an existing API equivalent for plaintext, not a new Option parameter.

The pinned runtime removes exactly one leading LF and one trailing LF, without
dedent/strip or CR normalization. Empty/None language becomes plaintext;
nonempty strings including a space pass through unchanged. Original Rust
code-text-before records 23 differing code payloads; the fixed code-text run
matches complete Elements, paths and dimension configurations. Both artifacts
remain. Eight semantic guards keep raw protobuf and summaries consistent but
reject incorrect LF/CR removal, language normalization, layouts and flags.

This is native WS evidence. Invalid dimensions, non-string body conversion,
full highlighting language support, syntax rendering, scrolling and responsive
browser layouts remain open. Correct captures were not rewritten. Collector-
owned Python and caller-owned Rust services/connections were closed afterward.


## Height reruns and actual Chrome code controls (2026-10-30)

The existing fixture/example add `?case=code-live`: three checkboxes control
120/240-pixel height, wrapping and line numbers around one fixed 20-line Python
code sample (360-pixel width). `--scenario code-live` in the existing native WS
collector sends three requests on one connection, with height 120→240→120.
[height-rerun/trace.json](height-rerun/trace.json) retains the correct Python
reference (18 elements, three successful finishes). The matching before/fixed
Rust payloads already have the right heights; only their hash relationship
changes from A/A/A to A/B/A. Hash strings need not equal across runtimes.

The actual Chrome Browser Use capture [ui/trace.json](ui/trace.json) has 13
observations and six context JPEGs. Ten control states exercise both directions
of height, wrap and line-number changes, then an actual wheel scroll moves the
inner code area down and back up. An intermediate upward-scroll observation
is retained before settled zero. The fixed Rust capture has 14 observations
and seven JPEGs because its first downward-wheel observation was still zero;
a later observation proves movement. These animation snapshots are not claimed
as exact cross-runtime offsets. Ten settled control states match in geometry,
text/tokens, numbers and wrapping, and both sequences restore scrollTop=0.

The initial Rust browser failure remains in ui-before (ten control observations,
three JPEGs): Tall and all-enabled claim 240 in the state caption but measure
120 in the code area. The bundled frontend's applyDelta/elementHash helper
reuses the previous Element for equal hashes independently of cacheable.
Including height in the existing code hash fixes the visible update; no cache
feature, public API or dependency was introduced. Positive UI gates reject the
saved failed height, verify image bytes/hash/decoding/dimensions, and exercise
nine observation-corruption guards. Gates replay retained artifacts; collection
was a real Browser Use session, not a new browser CI driver.

A collection mistake is retained in
[height-rerun-metadata-before/trace.json](height-rerun-metadata-before/trace.json):
I used the collector's Rust-only `--url` mode against the caller-owned Python
port, so runtime metadata says rust even though those frames came from Python.
It is rejected by the Python-reference gate and is not Rust or accepted Python
evidence. The correct reference was collected anew using its owned Python mode;
no packet bytes or incorrect runtime fields were edited to conceal the mistake.

Successful-tab captured warn/error buffers are empty for this observation
window. All task-created tabs and owned services/connections were closed;
8607/18607 had no listener afterward. This does not close full highlighting
language support, other sizes/themes/responsive layouts, clipboard interaction,
non-string body conversion, invalid dimensions or the complete code capability.


## Code body/language identity boundaries (2026-10-30)

The existing `?case=code-identity` scene alternates body/language pairs
`left_right`/`python` and `left`/`right_python` with a real checkbox. The old
underscore-joined identity string was equal for those distinct pairs. The
[identity-rerun reference](identity-rerun/trace.json), using the collector's
matching scenario, retains three requests, 12 element projections and A/B/A
code hashes. Rust before/fixed packets both carry the correct fields, but the
hash relationship changes from A/A/A to A/B/A after escaping field boundaries.
The MD5 algorithm and existing public CodeOptions API remain unchanged.

[identity-ui/trace.json](identity-ui/trace.json) is actual Chrome Browser Use,
with initial→alternate→restored states and three context JPEGs. Rust's original
three-stage failure and three JPEGs remain in identity-ui-before: alternate
caption changed, but the code text/language stayed old. A new fixed tab matches
all three Python visible text, language classes, checkbox states and geometry.
The nine images, raw protobuf, retained failure and seven observation-corruption
guards are checked. The unfamiliar right_python label demonstrates accepted
pass-through/plain-text fallback in this sample, not a supported language
catalogue. Python's initial screenshot request timed out before any control
action; the same tab was re-observed unchanged and only the screenshot retried,
as retained in collection_notes. No control operation or task was replayed.

The two successful tabs' captured warn/error buffers were empty. All task tabs
and owned services were closed; 8607/18607 had no listeners after cleanup.
This does not close invalid dimensions, other elements' identity logic,
non-string conversion, clipboard actions or wider code UI/configurations.
