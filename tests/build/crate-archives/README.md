# 本地 crate：库、示例与维护者测试的实际边界

2026-10-27，Windows/MSVC、Cargo/Rust 1.98.1、protoc 36.2，既有锁文件与缓存，全部命令离线。Rust 包版本是 0.1.1，行为目标仍为 Python Streamlit 1.66.1；没有 Python 行为重采，没有 registry 发布。

`cargo package --workspace --offline --locked` 真正生成并编译验证两个 crate，借助 target/package/tmp-registry 连接同 workspace 的本地依赖。它没有证明 crates.io 上存在这些版本；源码包仍是本地产物。初始库包 223 文件；提取后，chartlibs 三份配置和 video 样本的包外路径使 examples 检查失败。

修复仅让两个示例从 examples/data 读取四份原数据，原参考位置保留。最终库包 227 文件、宏包 6 文件；tarball、提取目录和原输入逐字一致。当前 Windows deck 文本为 CRLF，原/新文件都沿用普通 Git 文本规则，canonical 内容一致；MP4 明确保留原字节。没有改变图表、Vega 待决逻辑或视频行为。

实际结果：

- 最终两个 crate 的 Cargo 默认编译验证通过；全部 41 个包内 examples 经 `cargo check --examples --offline --locked` 通过。
- 独立 consumer 的 library target 直接使用提取出的 SDK，并局部 patch 到同样提取出的配套宏包；公开 trait/API 编译通过。它不调用启动宏，不能冒称仅依赖 streamlit 的可运行应用已成功，也没有加 tokio/env_logger 绕行。consumer 270 个、提取 workspace 286 个第三方依赖均为现有根锁版本/校验子集。
- 最终源码包维护者 lib test 的 `--no-run` 编译仍失败：31 个读取缺失均指向仓库级参考或 fixture。2026-10-28 采纳 PKG-A 后这不再是待决缺陷而是已定义的交付边界：SDK crate 的验收就是库/宏编译与全部示例构建（本目录日志），全部维护者回归由完整仓库源码交付承载（需仓库级参考数据，见 `archive-maintainer-tests-after.log` 的真实失败清单）；失败记录保留、不重定义为通过，也不在包内捆绑旧参考。

`observations.json` 保存实际包成员名称/大小、数据一致性与结果；不保存源码内容或源码包哈希门槛。`manifest.json` 仅核对数据/日志原字节。实际 crate 留在本地 target/package，不纳入 Git 快照或要求未来源码保持原指纹。

`sdk-consumer-import-error.log` 是首次 probe 忘导入 InputWidgets；`archive-maintainer-layout-error.log` 是提取目录发现祖先 workspace。修正 fixture 后才获得 SDK 通过与维护者输入缺失的真实结果；这两次设置错误不是产品缺陷。

可重复的打包入口：

```powershell
cargo package --workspace --offline --locked
```

验证未提交的本地改动时另用 `--allow-dirty`，仅用于本地 package。提取目录需要独立 parent workspace，以免归入祖先 checkout；本地尚未发布的宏通过该 workspace 的 `[patch.crates-io]` 指向配套目录。不要用缺少这些隔离条件的失败判断 SDK 不可消费。源码包检查不替代完整仓库回归、单依赖宏、所有平台/MSRV或生产发布验证。
