# data_editor：非法正删除位置与恢复

2026-10-27，固定 Python Streamlit **1.66.1**，仅两行合成 qty/label。包含两类分开的证据，均不绑定当前源码 SHA：

- `inputs.json` 与 `observations.json`：18 个脚本级私有实现实验，先按公开调用路径 `ensure_copy=True` 复制输入，再反序列化并应用编辑。合法删除、重复位置、升降序、越界、极大整数、负位置、混合编辑分别记录返回/异常及 caller/工作副本前后数据。这不是浏览器或协议证据。
- `protocol-first/`：复用既有 `dataeditor_app.py`，一次独立 native WS 的 4 阶段、30 PB。初始两行 → `deleted_rows:[2]` → `[0]` → `[]`。session/editor 身份稳定，错误后同连接恢复；没有浏览器操作声明。

非法正位置在 Python 产生 IndexError，极大位置可能为 OverflowError；Rust 通过已有 DataError 表达失败，不要求语言异常类名一致。原 caller 表始终不变。私有 helper 的工作副本可能已先应用单元格修改再在删除时抛错，不能把它称为整体事务。

协议越界阶段发送真实 IndexError Exception，没有后续 editor/返回表/rows 正文，完成状态仍为 `FINISHED_SUCCESSFULLY`。这个状态不等于应用没有报错。下一轮 `[0]` 返回 b 行，`[]` 恢复 a/b 两行。Rust 自动化真实 WS 复用这四个原字符串，验证 Result 错误、无部分表输出及同连接恢复；Rust fixture 自行显示错误文字，不宣称与 Python Exception 元素逐字段等价。

Rust 修复前 `Vec::remove(2)` 对两行表 panic，红日志在本地 `target/checks/m2-editor-invalid-rows/rust/before.log`。修复先检查整数可表示性与全部删除位置范围，保留合法去重、倒序及编辑→删除→新增顺序。单元测试读取这 18 个记录中的 **13 个非负场景**；空表删除首行另标为 Rust 内部边界。其余 5 个含负索引场景只保留观察：Python 使用 pandas 负索引，Rust 当前拒绝，策略未在本批改变，也不宣称全部输入兼容。

首次采集的即时端口检查未通过，collector 退出 1；原 trace 中 `port_closed:false` 和日志保留。`protocol-first/cleanup-verification.json` 是随后独立核验，`cleanup-final-verification.json` 再明确绑定原 PID 77124，确认进程不存在、61412 无监听。WS close 1000、没有 browser/profile；不重采、不把首次退出改成成功。

日常验证复用数据，不启动 Python server：

```powershell
target/pyref-venv/Scripts/python.exe -B -m pytest tests/reference/test_dataeditor_invalid_rows_reference.py -q -p no:cacheprovider
cargo test --workspace --locked --lib positive_out_of_range_deletions_return_error_without_panicking
cargo test --workspace --locked --lib frozen_invalid_editor_input_recovers_on_the_same_websocket
```

`manifest.json` 只校验这些输入、原 PB、日志及输出的完整性。路径、旧 PID、traceback 源文件位置是捕获来源，不读取旧源码或要求当前源码相同。其他非法 JSON、删除专用模式、所有类型和前端可达性仍未由此完成验收。
