# Local agent configuration

This directory contains the local model/agent registry and current development documents: [architecture](architecture.md), [compatibility policy](compatibility.md), [acceptance requirements](acceptance.md), the goal-oriented [roadmap](roadmap.md), and the distilled process [lessons](lessons.md). Keep `docs/` exclusively for installation, usage, examples, and public API documentation. Development plans, architecture decisions, compatibility explanations, acceptance criteria/evidence indexes, agent contracts, and research progress belong in the existing `.codex/` structure. The machine-readable matrix and baseline under `compatibility/` are tool outputs and retain their generator-bound paths. Actual test fixtures, traces, and screenshots stay under `tests/`; temporary logs and debug outputs belong under ignored `target/`. The root README links to these development documents instead of duplicating their checks. Process history and superseded contracts are ignored under `target/checks/agent-history/`.

Verify the frozen role/model mapping with:

```powershell
python .codex/verify_roles.py
```

## Shared artifacts and completion reports

`compatibility/documentation-scope.json` 是长期 M0 的官方文档范围审读输入，记录用户能力、场景和来源身份；它不是第二份实现进度表，也不是 Python API 导出清单。实现与兼容证据仍归现有矩阵，应用步骤归 journey 清单。本轮动态 Team 的实际配置和并发以最新用户 Goal 授权为准，历史冻结角色表不代表客户端配置已经生效。

Assign exactly one writer to each shared whole-file artifact, including JSON manifests, matrices and generated summaries. Other agents supply proposed fragments or write only their assigned evidence directories; they must not concurrently rewrite the shared file. Transfer ownership explicitly before another writer applies changes.

Match each completion/review report to its task submission, freeze and artifact identity: the agreed scope/base revision, exact paths and reviewed hashes. Preserve results for earlier submissions when a thread proceeds to another task; its latest message does not replace all preceding results. A completion report for one submission cannot approve a different artifact revision. Use the existing submission and freeze records rather than introducing a separate tracking framework.

Current journey status and remaining steps live in [the journey manifest](../tests/journeys/journeys.json). Feature status/evidence and the captured scope live in [the compatibility matrix](../compatibility/api-compatibility-matrix.json) and [baseline](../compatibility/p0-baseline.json); use [acceptance](acceptance.md) for the checks and [architecture](architecture.md) for build/deployment constraints. Do not duplicate changing stage counts here or infer complete P0 acceptance from a subset PASS. Preserve official frontend/protocol bytes and the user's local changes.

## forms-text-input writer boundary

For this isolated branch, the GLM engineer owns the Rust API/render/widget/session changes, Rust tests, example, user guide, and strict forms contract. MiniMax QA owns only the forms fixture/case files, thin collector, and reference raw/PNG evidence under the forms evidence directories; it does not edit Rust or the shared decoder framework.
