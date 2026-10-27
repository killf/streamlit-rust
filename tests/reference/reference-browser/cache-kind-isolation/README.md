# 缓存种类隔离

2026-10-27，固定 Python Streamlit **1.66.1**。同一个 `compute` 函数对象分别由公开 `st.cache_data(show_spinner=False)`、`st.cache_resource(show_spinner=False)` 包装；合成参数返回 `{"value":42}` 或 None。四组覆盖 data/resource 正反调用顺序，初始四次调用均只计算两次，计数 `[1,2,2,2]`，值始终正确。单独 clear data 不影响 resource 命中，反向亦然。

这是 **bare script 公开 API** 实验。真实 stderr 的 `No runtime found, using MemoryCacheStorageManager` 告警保留；没有 AppTest、HTTP、WS 或浏览器，不能据此推断会话作用域和界面重放。`inputs.json` 是调用计划；`observations.json` 逐次记录值/计数；stdout 是原始逐次输出；`execution.json` 保留实际命令、版本环境时间和退出 0。finally 清理自有两 wrapper 缓存，没有服务或浏览器资源。

`manifest.json` 仅校验这些数据与日志，不校验/归档源码。日常离线检查复用数据，不重跑 Python 缓存：

```powershell
target/pyref-venv/Scripts/python.exe -B -m pytest tests/reference/test_cache_kind_isolation_reference.py -q -p no:cacheprovider
cargo test --workspace --locked --lib cache
```

Rust 复用四组初始调用及预期值/计数；合法 null 是正常缓存值。原实现共用 entries，resource 的内部 null 覆盖 data，`Some(42)` 在后一次 data 命中变为 None，红复现在本地 `target/checks/m3-cache-kind-isolation/rust/before.log`。修复分开内部两张表，无新依赖或公共接口。另有 Rust 真实 WS 回归观察同名缓存的输出重放，不将它冒称 Python wire 对照。

Rust `cache_clear` 继续清当前会话的两类缓存；本批不增加 Python 分类别/函数清空入口。Python 参考后半段的独立 clear 记录保留为行为资料，**不宣称 Rust 已提供这些接口**。跨会话/全局缓存、TTL、持久化、完整异常及并发仍未在本批验收。

功能语义依据官方 [cache_data](https://docs.streamlit.io/develop/api-reference/caching-and-state/st.cache_data) 与 [cache_resource](https://docs.streamlit.io/develop/api-reference/caching-and-state/st.cache_resource) 的数据副本、共享资源和各自清空说明；2026-10-27 实时页面标注 1.66.0，与本实验的运行版本 1.66.1 分开记录，不将实时页面当作逐字锁定的旧文档。
