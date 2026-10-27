# generic Vega：真实更新失败，修法待决

2026-10-27，现有公开 `vega_lite_chart` 的同尺寸数据更新失败已复现。`chartlibs` 的 7 图初始数据和路径保持，末尾新增 **Change Vega data**，只改变第二图 a.count，使用现有 SessionState、按钮和 rerun，没有新接口或依赖。

四个真实官方前端阶段：load → 按钮 3→8 → R 普通重跑 → 按钮切回 3。最终消息中的数据为 3→8→8→3，SVG ARIA/PNG 可见 a.count 始终为 3；图位于 viewport 内。全部四个 Arrow IPC 都是 1416 字节，同 schema、同行列尺寸、同 spec、同 ForwardMsg 根 hash。`trace.json` 保留 76 个原 PB、CDP 命令、HTTP、DOM 和截图；`verification.json` 指向对应帧和字段。**这是失败基线，不是当前功能通过。**

锁定官方前端的 Quiver 判定不含单元格值，同形状/同字节长度可能被当作同数据。先前 Python CSV 的消息 hash 已改变，仍有类似漏刷，故只修 Rust 消息 hash 不能充分解决问题。现有内容命名的 CSV/bar 路径已测刷新正确。拟修法、有限 wire 差异和可能重置图内交互状态的代价见 [待决方案](../../../.codex/architecture.md#vega-lite-same-shape-updates--decision-pending)；用户选择前不改生产图表路径、官方资源或旧 oracle。

采集失败的首次驱动记录仍保留于本机 `target/checks/m2-chart-refresh/rust-before/`；此目录只整理已完成红复现的四阶段。`verification.json.only_tracked_file_edited` 是采集代理自己的写入归属，不是全工作区唯一改动：同时还有独立的编辑器越界修复，图表生产模块未改。Git revision、PID、路径和资产校验只追溯来源，不要求当前应用源码等于捕获时版本。

自有 server PID 45068、Chrome PID 42848 和 profile 已清理，8528 无监听；记录中 cleanup_errors 为空。普通开发不重复采旧 Python CSV，只在修法确认后对这个新边界验证修后实际值，并复用已有正确数据。
