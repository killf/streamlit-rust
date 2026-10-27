# Dataframe 选择 — Python 参考

2026-10-27，固定 Python Streamlit **1.66.1** 与官方前端，使用合成的三行 `rC/30`、`rA/10`、`rB/20`。首次成功采集五种配置共 30 阶段，另一次只补缩行边界 4 阶段；没有重采已成功场景。两批已独立核验 512 个原始二进制帧、DOM、截图、真实鼠标操作与运行关联。它们是 Python 行为依据，不证明尚未实现的 Rust 选择接口已兼容。

应用：[dataframe_selection_app.py](../../dataframe_selection_app.py)。采集器：[dataframe_selection_capture.py](../../../browser/dataframe_selection_capture.py)。功能依据为官方 [dataframe 文档](https://docs.streamlit.io/develop/api-reference/data/st.dataframe)（页面标签 1.66.0）；实际运行版本由各个 NewSession 核实为 1.66.1。

| 已测配置 | 实际观察 |
| --- | --- |
| 默认 ignore | 返回 DeltaGenerator、无 keyed 选择状态。真实点击后有界窗口无重跑，后续 Probe 正常完成。 |
| 默认 multi-row | 首轮空选择；选第 0、2 行后普通重跑保留 `[0,2]`。浏览器 qty 排序显示 `rA/10,rB/20,rC/30`；点击视觉首行新增原输入位置 1，返回 `[0,1,2]`。 |
| single-row/column/cell 组合 | 首轮同时给定三类默认值；真实单元格选择覆盖默认，普通重跑不恢复默认。三个按钮分别在调用前程序设置 rows、columns、cells。 |
| multi-row/column/cell 组合 | 真实多行、多列和矩形拖动；矩形包含前两列、三行的六个 cell，其他选择保留。 |
| single-row-required | 首轮自动 `[0]`，用户改选 `[2]`；清除尝试约 2.176 秒无重跑，后续 Probe 仍为 `[2]`。只证明此次有界观察。 |
| 同 key 缩行补充 | 先选 `[2]`，将输入从三行换成一行后，返回及 keyed state 仍为 `[2]`，再 Probe 也保留；不支持“换表自动清越界”规则。 |

程序只写 `{"selection":{"rows":[0]}}` 等部分结构时，**keyed state 原样保留部分结构，返回值补齐其他空字段**。不能将两者互相替代。真实用户 callback 在下一轮 main 前执行；程序设置后的部分 callback 来自随后浏览器回送上轮状态，不能概括为赋值当轮立即触发。完整事件顺序在数据中保留。

隐藏表格的当轮输出仍能读取旧 key；隐藏时再 Probe 已无 key；恢复后选择为空。普通数值替换保持行数时也保留旧选择。它们是本次固定布局、同 key 场景，未证明所有参数变化、多页或跨会话恢复。

`selection-input-output.json` 是供后续 Rust 单元/真实 WS 回归直接读取的紧凑输入与预期：保留原 widget ID、原始 value oneof 与 JSON 字符串、完整非 Arrow dataframe 字段、delta path、返回与 keyed state、callback/main 事件和截图身份。规范化 Rust widget ID 时只能映射身份，不能改选择内容。两个子目录的 `trace.json` 保留原始 CDP 命令/事件、PB 字节及解码、阶段 DOM 与截图；不另存重复的 progress 快照。

`manifest.json` 仅校验数据文件字节；Git revision、机器路径和 PID 只是采集来源，不要求当前源码一致、旧绝对路径存在或旧进程身份有效。两个自有 server/Chrome 均已退出、端口关闭、临时 profile 删除，清理无错误。旧轨迹不因采集器追加缩行场景而失效，没有源码 SHA 或源码归档。

首次采集及单独补充的命令为：

```powershell
target/pyref-venv/Scripts/python.exe -B tests/browser/dataframe_selection_capture.py --out target/checks/m2-dataframe-selection/first-attempt
target/pyref-venv/Scripts/python.exe -B tests/browser/dataframe_selection_capture.py --out target/checks/m2-dataframe-selection/shrink-supplement --cases multi-shrink
```

目录必须不存在，避免覆盖正确证据。以后直接运行 `target/pyref-venv/Scripts/python.exe -B -m pytest tests/reference/test_dataframe_selection_reference.py -q -p no:cacheprovider` 离线核验，不启动浏览器或重采 Python。非法模式组合、重复/非法/负位置、程序 multi-cell、lazy 大表、跨页/会话与所有配置参数仍待验证。
