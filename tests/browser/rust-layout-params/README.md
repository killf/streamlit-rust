# 布局与流式参数：Rust 对照证据（M3 布局/流式切片）

2026-10-28，caller-owned `layout_params` 示例服务器（8594）+ 同一[采集器](../layout_params_capture.py) --url 模式，与 [Python 参考](../../reference/reference-browser/layout-params/README.md)同调用集。

实测对齐：**14/14 add_block 发射字段逐字一致**（expander COMPACT/icon、popover primary/help/disabled/stretch、tabs default_tab_index=1、dialog LARGE 两段发射、status RUNNING→COMPLETE/ERROR 及 expanded 的 None 清除语义）。Rust 构建器：`ExpanderOptions::kind(ExpanderKind::Compact)`、`PopoverOptions::kind/help/disabled/use_container_width`、`TabsOptions::default_tab("Beta")`、既有 `StatusOptions/Status::update` 与 `DialogOptions::width`。记录差异：tabs 未知 default 标签 Python 抛错中止、Rust 记日志忽略（指南标注）；块级 `$$ID` 哈希为运行时身份。spinner show_time 双端均无 wire 增量（Rust API 亦无该参数，不冒称等价）。
