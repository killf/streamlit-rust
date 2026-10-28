# combined：Rust 组合差分证据（M7 启动）

2026-10-28，caller-owned `combined` 示例服务器（8596，最终构建源码）+ 同一[采集器](../combined_capture.py) --url 模式，与 [Python 参考](../../reference/reference-browser/combined/README.md)逐调用对照。22 元素 kind 序列与 Python 完全一致；离线差分断言逐元素相等（Arrow 逻辑比较与 generic vega accepted-A 承载差为既有两条约定，其余字段逐字一致，媒体内容哈希同字节同 URL）。caller-owned 服务器不归档；进程经端口核验清理。
