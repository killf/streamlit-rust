# sources-clear：来源替换的 Rust 对照（显式清空方案）

2026-10-28，caller-owned `csv_workbench` 示例服务器（`#[main]`，8545）+ 官方前端，与 [Python 参考](../../../reference/reference-browser/csv-workbench/sources-clear/README.md)同一 16 阶段契约：坏替换保留旧副本、空表头替换、有效替换、移除上传保留副本、显式 **Clear working copy** 清空、空态重跑。四次实际下载与 Python 逐字节相同；`Workbench::source` 的空状态仅清选择，`clear()` + `wb-clear` 按钮唯一清空。

两侧文案差异（错误前缀 Could not read/ parse CSV、空态提示）按语义断言，不逐字对比。`trace.json` 为原始 PB/DOM/下载；服务进程为调用方所有，未归档。上一级 [README](../README.md) 记录 Rust 侧整体范围与进程清理。
