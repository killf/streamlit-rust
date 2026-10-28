# sources-clear：来源替换的 Python 参考（显式清空方案）

2026-10-28，真实 Python Streamlit 1.66.1、官方前端与合成坏/好 CSV，16 阶段一次成功：五个坏文件逐个替换均保留 `workbench-bom` 旧副本（错误 + "Showing previous valid source" 警告 + 旧数据/下载不变）、空表头替换为无数据行副本、有效替换、移除上传后副本保留并可下载、显式 **Clear working copy** 清空、清空后普通重跑保持空态。参考应用与采集器已按该契约更新（`csv_workbench_app.py` 的 None 分支仅丢 attempt、新增 `wb-clear` 按钮；采集器 sources 段见 `remove-upload-keeps-copy`/`clear-working-copy`）。

`trace.json` 保留全部原 PB、DOM、下载字节与清理审计；`artifacts/*.csv` 为各次实际下载；`inputs/` 为本组输入。此前的来源失败链（移除即清空语义）保留于本地 `target/checks/m2-csv-workbench/python/sources-first/`，未改写。离线断言见 `tests/reference/test_csv_workbench_reference.py::test_csv_sources_clear_semantics_match_across_runtimes`（与 Rust 对照逐字节比对下载）。上一级 [README](../README.md) 记录 main/filters 与总体边界。
