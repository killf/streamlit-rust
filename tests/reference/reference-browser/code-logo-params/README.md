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
