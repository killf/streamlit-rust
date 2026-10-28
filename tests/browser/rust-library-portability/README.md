# 库路径与本地 release 安装

2026-10-27，Windows/MSVC，已有固定依赖缓存与 protoc 36.2。库目录改名为 `renamed-library`，隔离源码不放置外部 `www`；原构建因固定 proto 路径失败。修复虚拟协议映射及 crate 内版本 index 后，库检查成功；在含空格路径中构建现有 quickstart 的 release 成功。原协议与 6467 字节官方 index 不改，完整前端仍作为 sidecar。

`build-logs/` 是实际红/绿、release 及包文件列表。首次新 consumer 漏写 async 的失败单独保留，纠正后真正的 consumer 失败来自宏直接引用 tokio/env_logger。**2026-10-28 宏支撑方案 A 已实施并复验通过**：库新增 doc-hidden `__macro` 重导出命名空间，宏改用限定路径并显式构建同样的 Tokio 多线程运行时（不用 `#[tokio::main]` 属性——其展开仍引用裸 `::tokio`）；同一改名库目录 + 含空格路径、仅依赖 `streamlit` 一个包的 consumer 应用真实编译（`consumer-macro-green.log`，本机以 crates.io 常规拉取的 vendored protoc 提供 `PROTOC`）、启动 8550、真实 Chrome 点击 **Add** 三次 Count 0→1→2→3、无 stException。历史红记录（`consumer-macro-red.log` 的 E0433×2 + E0752）保留为修复前证据；`build-results.json` 记录的是当时观察，不要求未来仍失败。

已将本次实际 release 可执行文件复制为 `install/portable-quickstart.exe`，确认原构建产物与复制字节相等；从 `runtime/workdir` 启动，子进程移除静态目录 override。真实 Chrome 初始 category/0/true，真实点击复选框后显示 false，同一 WS 完成两轮。`trace.json` 保存 24 PB、原 CDP 操作/事件、DOM 和 HTTP；截图对应两阶段。60 个 HTTP 响应体在 `http/`，含首页及全部 index 引用的启动 JS/CSS，均与实际安装资源一致。

锁定 wheel 的完整 347 文件集与源 www、安装后及交互后均一致；`frontend-files.json` 保存独立复核的每个名称/大小/数据 SHA。它只约束官方资源数据，不约束 Rust 或采集器源码。原事件 Recorder 的 `_target` 沿用 python-componentv2-state，trace 明确为 Rust release，不改写历史标签冒称其他采集器。

UI 进程默认日志为空，原 `server.log` 保留。随后另用同一安装程序/工作目录、RUST_LOG=info 单独启动健康检查，`server-info.log` 才实际记录 executable sidecar；这是第二个 PID，不能把该日志说成 UI 捕获进程输出。该进程与原服务/Chrome/profile 均清理，8503 无监听；两个 Python 工具的采集退出均为 0。最后 PowerShell 因无监听返回 1 是外层观察行为，不伪造为全部工具链统一退出 0。

离线检查复用这些数据，不启动 Python Streamlit 或浏览器：

```powershell
target/pyref-venv/Scripts/python.exe -B -m pytest tests/reference/test_library_portability_reference.py -q -p no:cacheprovider
```

证据仅支持本机缓存 Windows 的库目录修复和现有示例安装。它不是全新机器/系统运行库、MSRV、Linux/macOS、完整 crate archive 验证、crates.io 发布或完整 M6 验收。
