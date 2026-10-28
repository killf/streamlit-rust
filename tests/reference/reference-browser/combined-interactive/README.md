# 交互组合差分：Python 1.66.1 参考（M7 第二差分链）

2026-10-28，锁定 Python 1.66.1 + 官方前端 + 真实 Chrome（[combined_interactive_capture.py](../../../browser/combined_interactive_capture.py) 一次采集），参考应用 [combined_interactive_app.py](../../combined_interactive_app.py)。六阶段真实 UI 交互流：load → 一次上传两文件（CDP 注入）→ 勾选 Check → 选 Pick=b → 点击表格首行（阶段名 select-row-2 为历史命名，实际点击落在首行——两侧行为一致） → 点击 Apply（toast）。

实测：每阶段应用报告（st.code 的 JSON）与 DOM 同步演进——files 空→[alpha,beta]（排序后）、checked false→true、picked a→b、row null→0、applied false→true + toast "applied"；全程无 stException。widget 状态经 BackMsg 逐轮回传，上传为批量地址请求 + 逐文件 PUT。

Rust 对照（[浏览器证据](../../../browser/rust-combined-interactive/README.md)）：**六阶段报告 JSON 值逐阶段一致**（代码块文本因双端序列化格式不同而字面不同：Python 排序键+带空格，Rust 插入序+紧凑）。Rust 镜像对表格显式 hide_index/固定宽高以稳定行点击坐标（Python 用默认布局），报告不受影响。离线断言 `tests/reference/test_combined_interactive_reference.py`。边界：单会话、六阶段、每控件一种取值；滑动条/键盘输入/多行选择未纳入本流。
