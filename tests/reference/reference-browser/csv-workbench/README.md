# CSV workbench：一次冻结的成功子流程

2026-10-27，实际 Python Streamlit **1.66.1**、官方前端和合成文本 CSV。`main-complete` 20 阶段与 `filters-first` 13 阶段由独立 Reviewer 重解核验：615 个原 PB、真实 CDP 操作、Arrow、PNG、上传 HTTP、实际下载字节及会话身份。`csv-input-output.json` 是原记录的紧凑索引，`manifest.json` 只校验数据字节，不绑定当前源码或旧机器绝对路径。

- main：BOM、Unicode、引号换行及空串；浏览器排序后选择输入位置 1/rA；详情未 Apply 时工作数据和下载不变；Apply 只把 rA.region 改为 north；Append 加入 new 及空字段；普通重跑；B 会话独立上传 other，A 下载仍保留自己的编辑和追加。
- filters：新增 pending 草稿跨空筛选、空字符串匹配、无匹配、关闭筛选后保留 Exact value；最后 Append 只加入一次 pending，下载含四行。
- Apply/Append 的早结束与随后成功运行均保留。紧凑状态只取最终成功运行；下载不重跑时沿用同一 target 的最后实际状态，不把零新帧当成空表。

计数的预期来自实际 value/count Arrow 数据。**图形像素没有获得等价结论**：Python Append 后部分截图仍显示之前的柱高，实际 Arrow 和 CSV 已更新；采集当时尚未确定是否与离屏、异步重绘或其他原因有关。Rust 对应截图显示更新后的计数。保留这个差异，不修饰截图，不从逻辑计数推断 Python 图已完成刷新。图表 spec、空图存在性、索引显示和 nullable 标记亦不在本次等价声明内。

后续独立调查已在 generic Vega 的同形状更新上[真实复现漏刷](../../../browser/rust-vega-refresh-before/README.md)，官方前端的数据判断不含值，机制与本组观察一致；修法涉及协议/交互取舍，尚未实施。不改写本组原始数据或据此追加一次旧流程重采。

来源切换已按 2026-10-28 采纳的显式清空方案通过。参考应用与采集器按"上传器空状态仅清选择、坏文件保留旧副本、显式 **Clear working copy** 才清空"同步更新后，`sources-clear` 16 阶段一次成功：五个坏文件逐个替换都保留 `workbench-bom` 旧副本并实际下载原字节，空表头替换为无数据行的工作副本，有效替换与移除上传后副本保留、下载字节不变，显式清空后回到初始空态。Rust 对照的四次实际下载与本组逐字节相同，离线测试双向断言空状态前驱运行仍显示旧副本。旧失败链原样保留于本机 `target/checks/m2-csv-workbench/python/sources-first/`，未改写为成功；此前 main/filters 33 阶段未重采。多文件上传、上传端点安全边界与全部坏输入枚举仍不在等价声明内。

参考应用为 [csv_workbench_app.py](../../csv_workbench_app.py)，采集器为 [csv_workbench_capture.py](../../../browser/csv_workbench_capture.py)。当前 Python 3.14.7/Altair 5.5.0 在初次 `st.bar_chart` 时出错，参考用现有 `st.vega_lite_chart` 展示相同分组计数，没有修改或安装依赖。下载同名覆盖和后台标签页截图的采集器故障修复后才完成成功链；正确 filters 没有重采。

日常开发直接复用冻结数据，不启动 Python 或浏览器：

```powershell
target/pyref-venv/Scripts/python.exe -B -m pytest tests/reference/test_csv_workbench_reference.py -q -p no:cacheprovider
cargo test --example csv_workbench --locked
```

只有新边界、版本变化或失效数据才补采；更新采集器或 Rust 源码本身不是重采理由。原始下载路径是浏览器来源元数据，阶段唯一 `artifacts/*.csv` 保存各次实际下载，避免后一次同名文件覆盖历史证据。所有自有 Python/Chrome、profile 和端口已清理；[Rust 对照](../../../browser/rust-csv-workbench/README.md)另行记录自身进程和协议范围。
