# generic Vega：同形状更新已随内容命名数据集刷新（已采纳 A）

2026-10-28，与[修复前失败基线](../rust-vega-refresh-before/README.md)同一四阶段流程（load → **Change Vega data** 3→8 → **Ordinary rerun** → 切回 3），同一官方前端与采集方法（[vega_refresh_capture.py](../vega_refresh_capture.py) 对 caller-owned `chartlibs` 示例服务器）。实施已采纳的方案 A 后：内联 `data.values` 提取为内容命名的 `ArrowNamedDataSet`（IPC 字节 md5），spec 以 `data: {"name": …}` 引用，同形状值变化即改变数据集身份。

每阶段的 ARIA 可见标记与 wire 数据一致：load `kind: a; count: 3` → change-to-8 **`count: 8`** → 普通重跑保持 8 → 切回 3。修复前同一流程的可视值始终停留在 3（基线保留不删）。`trace.json` 含 76 帧原 PB、每阶段 generic 图的 dataset 名与解码行；`manifest.json` 锁定字节。dataset 名在 3↔8 间变化、普通重跑保持不变，由离线测试与 WS 回归 `generic_vega_same_shape_updates_change_the_dataset_identity` 双向断言。

边界：一次成功采集、一台机器的 headless Chrome；spec 变化会重建 Vega view，缩放/brush/选区等图内交互状态保持未验收；URL、自带 `data.name`、嵌套 spec 与无数据调用不在本流程内（行为不变）。静态七图契约（journey-chartlibs-v1）的 Rust 时间线已按本偏差更新并重采通过，Python oracle 未重采。
