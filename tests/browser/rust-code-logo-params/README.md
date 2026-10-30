# code/skeleton/logo 参数：Rust 对照证据（M3 切片）

2026-10-29，caller-owned `code_logo_params` 示例服务器（8607）+ 同一[采集器](../code_logo_params_capture.py) --url 模式，与 [Python 参考](../../reference/reference-browser/code-logo-params/README.md)同调用集。

实测对齐：**3/3 元素 + logo 帧逐字一致（零实现改动）**——code 的语言标签透传与行号开关、skeleton 空消息、logo 的 emoji 判型/medium 缺省尺寸/顶层 ForwardMsg 承载均为既有行为经参考确认。边界同参考。


## Code text and layout before/after (2026-10-30)

[code-text-before/trace.json](code-text-before/trace.json) preserves 23/27 code
payload mismatches against the pinned Python reference; layouts and display
flags already match. [code-text/trace.json](code-text/trace.json) retains the
fixed run: all 28 Elements (input report + 27 code blocks), payload fields,
width/height configurations and paths match the
[Python reference](../../reference/reference-browser/code-logo-params/code-text/trace.json).
Use the existing example's `?case=code-text` query and the collector's matching
scenario. The original default code/skeleton/logo scene remains unchanged.

The correction removes one LF at each boundary and sends empty languages as
plaintext, preserving spaces, tabs, CR and Unicode whitespace. Python None
language is expressed as the existing empty-string Rust argument, without
adding Option support. CodeOptions already handles the measured line-number,
wrapping and nine dimension combinations. Both owned Rust service sessions
were stopped after collection; captures remain native WS observations, not
browser screenshots or proof of highlighting/scrolling behavior.
Invalid dimensions, non-string conversion and remaining code UI stay open.


## Real height-update bug and Chrome verification (2026-10-30)

[height-rerun-before/trace.json](height-rerun-before/trace.json) preserves three
correct-height frames (120→240→120) sharing one hash. [ui-before/trace.json](ui-before/trace.json)
retains ten actual Chrome control observations and three JPEGs, including Tall
and all-enabled stuck at visible 120 while the caption says 240. Equal hash
causes the bundled frontend to reuse the old Element even with cacheable=false.

The minimal fix adds height to the existing CodeElement hash. The fixed
[height-rerun/trace.json](height-rerun/trace.json) now has A/B/A hashes and the same
full code payloads as Python. Unit and same-connection production WS regression
cover that relationship. [ui/trace.json](ui/trace.json) records a fresh actual
Chrome tab, with ten matching height/wrap/line-number states and inner scrolling.
There are 14 observations and seven context JPEGs, including the initial zero
scroll observation, later successful movement, and settled restoration to zero.
Python has 13 observations/six JPEGs; the animation observations are retained
rather than normalized into false exact scroll parity. Positive UI semantics,
all saved images, the original failure and nine corruption guards are checked.

Use `?case=code-live` in the existing example. This window's captured console
warn/error buffer was empty; task tabs, sockets and owned servers were closed,
and 8607/18607 had no listeners afterward. No general cache, public interface
or dependency changed. Other languages, dimensions/themes/responsive layouts,
clipboard actions, non-string conversion and invalid sizes stay open. A separate
metadata-error capture is documented in the Python README and excluded from
accepted cross-runtime evidence.
