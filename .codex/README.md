# Local agent configuration

This directory contains the local model/agent registry and current development documents: [architecture](architecture.md), [compatibility policy](compatibility.md), and [acceptance requirements](acceptance.md). Keep `docs/` exclusively for project usage documentation; development planning, architecture, and acceptance belong in `.codex/`. Process history and superseded contracts are ignored under `target/checks/agent-history/`.

Verify the frozen role/model mapping with:

```powershell
python .codex/verify_roles.py
```