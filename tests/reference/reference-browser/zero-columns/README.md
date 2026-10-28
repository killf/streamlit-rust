# 零列公开调用与首次 UI 参考

2026-10-28，本机锁定 Python Streamlit **1.66.1**、pandas 3.1.0、PyArrow 26.0.0。范围由官方 [dataframe](https://docs.streamlit.io/develop/api-reference/data/st.dataframe) 与 [data_editor](https://docs.streamlit.io/develop/api-reference/data/st.data_editor) 说明确定；本轮网页仍标为 1.66.0，零列具体行为由这里的真实 1.66.1 观察证明。

`primary/` 是首次九个公开场景、32 PB；运行中才提出的 table 对照另在 `table/` 采三例、14 PB，没有重采前九例。三个输入为真实 0×0 Arrow、通过 drop 保留两行的 2×0 Arrow、pandas 两行 index-only frame。dataframe、enabled/disabled fixed editor、table(hide_index=False) 均成功，12/12 原输入不变，IPC 无物理列但保留行数。Arrow 直接 dataframe/table 无 pandas metadata；editor 和 pandas 输入的 RangeIndex 位于 metadata，不是实体索引列。编辑器返回保持本次输入的 Python 类型；它转换后的 producer metadata 不是 Rust 返回的同构要求。

**协议成功不代表显示成功。** `ui/` 是独立的首次恢复组合：0 行 → Two rows → Ordinary rerun → 回到 0 行，共四次真实 Chrome 操作、76 PB，以及原 DOM/PNG。两行时直接 Arrow dataframe 的两个可见格均为 **Error during cell creation**；两个 editor 显示索引 0、1，返回行数仍为 2；table 区域只见空框。切回零行恢复 empty。无 stException 不能作为渲染成功判断；`successful:true` 只表示采集步骤完成。独立检查实际截图与 ARIA 数据后仍保留这个上游限制，不改原轨迹让兼容检查变绿。

`ui-first/` 保留更早的采集器滚动表达式返回值错误，只有初始阶段，producer_error 为 `KeyError: 'value'`；修正采集器后才完成上述四阶段，不把失败前缀当完整 UI 记录。静态十二个单元参考没有因此重采。协议两组的 execution/cleanup 与 UI 两次 cleanup 原样保留，另有根代理对原 PID、端口和临时 profile 的只读清理核验。

`manifest.json` 只固定输入、PB、IPC、DOM、PNG、日志及清理记录，不含 app/probe 源码快照或源码 SHA。原捕获命令中的 target/app.py、probe.py 路径是历史来源，不要求它们现在存在或等于维护后的参考工具。正式维护源为 [reference app](../../zero_columns_app.py)、[协议采集器](../../../browser/zero_columns_protocol_capture.py) 和 [UI 采集器](../../../browser/zero_columns_capture.py)。原 9/3 组临时脚本没有复制为仓库源码档案。

日常开发只复用冻结数据：

```powershell
target/pyref-venv/Scripts/python.exe -B -m pytest tests/reference/test_zero_columns_reference.py -q -p no:cacheprovider
```

只有新边界或版本需要新参考时，协议采集器以 `--inputs <本组 inputs.json> --out <新目录>` 运行；UI 采集器以 `--out <新目录>` 启动隔离 Python/Chrome，`--url` 仅用于调用方自有 Rust 服务。两者都不覆盖旧记录；修改 Rust 或工具源码本身不是重采理由。

Rust 目前仍在显示转换返回 Arrow 错误。原始引用已经冻结；选用虚拟 RangeIndex 修正上游直接 Arrow 的可见问题、严格保留上游错误，或暂缓实现，等待用户决定。这里不是 Rust 实现/前端验收通过记录，也不覆盖动态行编辑、选择、任意索引或所有 metadata 组合。
