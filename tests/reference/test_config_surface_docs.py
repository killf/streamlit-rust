"""Documentation-accuracy gate for the runtime configuration surface.

The guide's configuration table names each knob's evidence; this check parses
the table and fails when any referenced file no longer exists or a builder
method documented in code goes unmentioned, so the surface cannot drift.
"""
import re
from pathlib import Path

ROOT = Path(__file__).parents[2]
GUIDE = ROOT / "docs/guide/application-workflows.md"
SERVER = ROOT / "streamlit/src/server.rs"


def test_every_table_evidence_reference_exists():
    text = GUIDE.read_text(encoding="utf-8")
    start = text.index("## 运行配置面")
    end = text.index("## ", start + 1)
    section = text[start:end]
    rows = [line for line in section.splitlines() if line.startswith("|") and "---" not in line and "运行项" not in line]
    assert len(rows) >= 7, f"the configuration table must stay complete: {len(rows)} rows"
    referenced = set()
    for row in rows:
        for token in re.findall(r"[A-Za-z0-9_./-]+", row):
            token = token.strip("`'.")
            # Evidence references are repository paths: a known top-level
            # directory or a code file; prose like "HTTP/WS" never qualifies.
            if token.startswith(("tests/", "streamlit/", "docs/", "compatibility/")) or token.endswith((".rs", ".py")):
                referenced.add(token)
    missing = [token for token in sorted(referenced) if not (ROOT / token).exists() and not token.startswith(("http", "0.0.0.0"))]
    assert not missing, f"stale evidence references in the configuration table: {missing}"


def test_every_server_builder_knob_is_documented():
    text = GUIDE.read_text(encoding="utf-8")
    start = text.index("## 运行配置面")
    end = text.index("## ", start + 1)
    section = text[start:end]
    builders = re.findall(r"pub fn (with_[a-z_]+)", SERVER.read_text(encoding="utf-8"))
    assert builders, "the builder inventory must not be empty"
    missing = [builder for builder in builders if f".{builder}(" not in section]
    assert not missing, f"builder knobs absent from the configuration table: {missing}"


def test_environment_variables_are_documented():
    text = GUIDE.read_text(encoding="utf-8")
    start = text.index("## 运行配置面")
    end = text.index("## ", start + 1)
    section = text[start:end]
    for variable in ("STREAMLIT_STATIC_DIR", "RUST_LOG"):
        assert variable in section, f"{variable} must stay documented"
