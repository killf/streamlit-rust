# 交互组合差分：Rust 对照证据（M7 第二差分链）

2026-10-28，caller-owned `combined_interactive` 示例服务器（8598）+ 同一[采集器](../combined_interactive_capture.py) --url 模式，与 [Python 参考](../../reference/reference-browser/combined-interactive/README.md)同六阶段交互流。

实测对齐：**六阶段应用报告 JSON 值逐阶段一致**（files/checked/picked/row/applied 的每一步演进；代码块文本因序列化格式不同而字面不同）；DOM 侧 chips/checkbox/toast 同步；无 stException。上传链（批量地址 + 逐文件 PUT）与多文件切片一致。边界同参考（单会话、六阶段、单选行）。
