# json/badge/feedback 参数：Rust 对照证据（M3 切片）

2026-10-29，caller-owned `json_badge_params` 示例服务器（8604）+ 同一[采集器](../json_badge_params_capture.py) --url 模式，与 [Python 参考](../../reference/reference-browser/json-badge-params/README.md)同调用集。

实测对齐：**6/6 元素字段一致**。本批修复一处真实偏差：badge markdown 的 `wrap` 此前发 `Some(true)`，实测参考**缺省该字段**——先误改为 `Some(false)`（离线差分再次抓到显式 false 仍不等价于省略），终改 `None`；json 的 expanded 语义与 feedback 的 disabled 为既有行为经参考确认。边界同参考。


## JSON string example and live Chrome extension (2026-10-30)

The example now mirrors the fixed string fixture when called with
`?case=strings`; [strings/trace.json](strings/trace.json) retains the full 36
JSON elements and exact payload/path parity with the original Python wire.
The original six-element default example and its old trace remain unchanged.

[ui/trace.json](ui/trace.json) is a separate live Chrome capture with 22 states,
matching the [Python browser capture](../../reference/reference-browser/json-badge-params/ui/trace.json).
It covers all 15 string renderings, real object/array collapse-expand-collapse
cycles, parse alerts, upstream scalar ERROR objects and Unicode preservation.
Nine JPEGs with hashes are retained; [Unicode context](ui/unicode-context.jpg)
is a cropped browser screenshot including the page heading and JSON output.
DOM/HTML and console-buffer observations are retained without hiding the
upstream react-json-view error logs. See the reference README for scope and
capture details. Offline gates validate artifacts; they do not replace a
fresh browser run or claim all JSON inputs/UI configurations are complete.

Run the existing example and open `http://127.0.0.1:8604/?case=strings&sample=11`
for the Unicode scene; sample values 0..14 select the retained input strings,
and `&collapsed=true` chooses initial collapse. The runtime/schema APIs did
not change. Both owned servers and both task-created tabs were closed after
collection. The queue-policy decision remains separate and pending.


## Numeric wire before and after (2026-10-30)

[numbers-before/trace.json](numbers-before/trace.json) retains the original
8/16 finite input mismatches plus three nonfinite mismatches against the
[Python numeric reference](../../reference/reference-browser/json-badge-params/numbers/trace.json).
[numbers/trace.json](numbers/trace.json) retains the fresh fixed run: all 16
finite scalar/array pairs and the input report match (33 elements), while
NaN and both infinities still become null in six elements. Both full captures
have 39 elements; neither capture was overwritten to hide the differences.
Use `?case=numbers` in the existing example to reproduce the input set.

The collector used caller-owned Rust services, each stopped after collection.
These are native WS observations; no numeric browser rendering or complete
serialization compatibility claim. Shared py_dumps/compact/pairs unit tests,
finite production WS tests and raw-frame evidence gates cover the correction.
Nonfinite preservation requires a separate internal serialization decision;
public JSON expansion/width and rerun policy choices remain pending.


## Existing serialization failures (2026-10-30; diagnostic evidence)

[serialization-before/trace.json](serialization-before/trace.json) uses the
existing example at `?case=serialization`: an input report plus before/after
markers around a BTreeMap with a None key and a custom Serialize implementation
that returns a synthetic error. Only those five JSON elements appear; there
is no JSON for the rejected inputs and no alert or exception, with finish=0.
This records current silent omission and continuation; it does not accept that
behavior or gate the future runtime to retain it. The test checks the frozen
failure artifact rather than requiring the running implementation to fail.

This Rust diagnostic intentionally has different inputs from the 17-case
[Python serialization reference](../../reference/reference-browser/json-badge-params/serialization/trace.json).
There is no field-for-field compatibility claim for the two sequences. The
collector closed its owned WS connection, and the caller stopped the Rust
service afterward. No browser observation is claimed. Internal serialization
flow and public error propagation remain explicit open decisions.
