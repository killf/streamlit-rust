# Data editor：非 nullable 输入的 Rust 官方前端验证

2026-10-27，一次自有本地 Rust server 与隔离 headless Chrome 155.0.8059.85 完成四步真实交互：加载、将 qty 首格改为 7、新增空行、将新增行 qty 改为 9。四轮原始 `NewSession` 均声明 1.66.1，均以 `FINISHED_SUCCESSFULLY` 结束。未重采 Python，未修改旧 Python/native 轨迹或既有采集器。

使用已构建的 `target/debug/examples/dataeditor.exe`，对应 [dataeditor.rs](../../../streamlit/examples/dataeditor.rs) 的 `RecordBatch::try_from_iter` 输入：qty `[1,2]`、label `["a","b"]`，两字段因没有 null 自动推断为不可空。布局与旧 [Python dataeditor 参考](../../reference/reference-browser/dataeditor/) 相同。此处验证的是用户选定的 Rust 规则：仅在结果列实际出现 null 时放宽该列 nullable，保留其他列的原有约束；**旧 Python 参考的输入字段本来可空，不构成 Python 非空输入行为的测量**。

| 真实阶段 | BackMsg 中的编辑内容 | editor 原表 nullable（qty/label） | 返回表 nullable | 返回 qty |
| --- | --- | --- | --- | --- |
| 01-load | 无 widget state | false / false | false / false | int64 `[1,2]` |
| 02-edit-cell | edited_rows `{"0":{"qty":7}}`，无新增行 | false / false | false / false | int64 `[7,2]` |
| 03-add-row | added_rows `[{}]` | false / false | true / true | double `[7.0,2.0,null]` |
| 04-edit-added-row | added_rows `[{"qty":9}]` | false / false | false / true | int64 `[7,2,9]` |

四轮 editor 下发的原表值均保持 `[1/a,2/b]`。新增行的 label 在后两轮都为 null；第四轮 qty 已填满，所以其返回字段恢复输入的不可空标记。四轮返回表的逻辑类型、行值与既有 Python 冻结 IPC 一致；nullable 差异在独立检查中保留，没有被旧合同的逻辑比较隐藏。页面实际显示 `rows=2,2,3,3`，无 exception。

复用 [dataeditor_capture.py](../dataeditor_capture.py) 与 [dataeditor_contract.py](../dataeditor_contract.py)，实际 `DATAEDITOR_REQUIRED` 为 6 项，本次 6/6 通过。忽略目录中的临时 wrapper 只负责本地进程编排、注入 headless/no-window 参数和保留完整原始 CDP/PB，不改采集器源码；Chrome 的 driver kill 延后到自有进程树清理。捕获与检查命令分别为：

```powershell
target/pyref-venv/Scripts/python.exe -B target/checks/q5-editor-schema/capture_nonnullable.py
target/pyref-venv/Scripts/python.exe -B target/checks/q5-editor-schema/verify_nonnullable.py
target/pyref-venv/Scripts/python.exe -B target/checks/q5-editor-schema/verify_nonnullable.py tests/browser/rust-dataeditor-nonnullable
```

三个命令退出码均为 0；后两个命令只读重放已有采集与 Python fixture，不启动服务。`capture.log`、`verification.log`、`published-verification.log` 保留本次实际输出。旧合同通过原 observation 的绝对 `ipc_dir` 读取截图；第三个命令仅在内存 observation 副本中将此路径定位本发布目录，再校验原 PNG SHA，不修改 raw、动作或预期。这样同时核对了发布目录自己的数据。临时编排脚本不属于长期重放前置条件，后续读取冻结数据时同样以 fixture 所在目录定位相对 PNG；仅有新行为、版本升级或证据失效时才补采。

在新的 checkout 中，可直接重放发布目录的六项既有合同（不依赖临时编排脚本）：

```powershell
@'
import json, pathlib, sys
sys.path.insert(0, "tests/browser")
from dataeditor_contract import dataeditor_result
root = pathlib.Path("tests/browser/rust-dataeditor-nonnullable").resolve()
observation = json.loads((root / "trace-dataeditor.json").read_text(encoding="utf-8"))["observation"]
observation["ipc_dir"] = str(root)
result = dataeditor_result(observation=observation)
assert result["ok"], result["failures"]
print(result["counts"])
'@ | target/pyref-venv/Scripts/python.exe -
```

这六项合同比较逻辑内容；nullable 标记另由 `nullable-checks.json`、原始 IPC 和 Rust 单元/WS 回归核对，不把它当作 Python 非空输入的证明。

文件说明：

- `trace-dataeditor.json` 与 `manifest.json` 是既有 collector 生成的原文件，未改写或替换旧记录；四张 PNG 保存阶段页面。
- `trace.json` 额外保留 807 个原始 CDP 事件、36 条发出命令及响应、32 个完整双向 PB frame 的字节/base64/解码、实际浏览器版本、binary/config/argv 与清理记录。真实 mouse/key actions 和 `added_rows:[{}]` 可追溯至原始事件。
- `nullable-checks.json` 是独立 IPC 解码结果：每轮原表/返回表 schema、行值、原始 edits 与旧 Python 数据身份。检查同时核对 raw PB 与 stage IPC 相同、PNG 哈希和阶段成功结束。
- `evidence-manifest.json` 对本目录数据文件保存大小与 SHA。binary SHA 仅追溯该次实际运行的二进制，Git revision/路径仅追溯捕获环境；没有源码 SHA 或源码归档，也不要求当前源码/二进制与旧捕获一致。

采集后确认自有 server PID 51020、Chrome PID 61896 均退出，端口 8541/49897 均关闭，临时 profile 删除，`cleanup_errors` 为空。仅使用本地假数据；未安装依赖、提交或推送。本链未覆盖行删除、required/default 列配置、其他 Arrow 类型、非法单元格类型或跨会话行为。
