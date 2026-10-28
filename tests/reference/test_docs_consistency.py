"""The M7 documentation-accuracy scan: matrix evidence, guide links, examples.

Three cross-checks so the ledgers cannot drift from the tree: every evidence
path the compatibility matrix cites exists; every repository-relative link in
the user guide resolves; and the example registry in Cargo.toml matches the
examples directory exactly (with the guide indexing the combined example).
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).parents[2]
GUIDE = ROOT / "docs/guide/application-workflows.md"
README = ROOT / "README.md"
MATRIX = ROOT / "compatibility/api-compatibility-matrix.json"
CARGO = ROOT / "streamlit/Cargo.toml"


def matrix_evidence_paths(matrix):
    for entry in matrix["entries"]:
        evidence = entry.get("evidence", {})
        for value in evidence.values():
            items = value if isinstance(value, list) else [value]
            for item in items:
                if isinstance(item, str) and "/" in item and not item.startswith(("http", "#")):
                    yield entry["feature_id"], item


def test_matrix_evidence_paths_exist():
    matrix = json.loads(MATRIX.read_text(encoding="utf-8"))
    missing = []
    for feature, path in matrix_evidence_paths(matrix):
        candidate = ROOT / path.split(":")[0]
        if not candidate.exists():
            missing.append((feature, path))
    assert not missing, f"stale matrix evidence references: {missing[:10]}"


def markdown_repo_links(text):
    for match in re.finditer(r"\]\(([^)#]+?)(#[^)]*)?\)", text):
        target = match.group(1).strip()
        if target.startswith(("http://", "https://", "mailto:")):
            continue
        yield target


def test_guide_and_readme_links_resolve():
    for document in (GUIDE, README):
        text = document.read_text(encoding="utf-8")
        missing = [target for target in markdown_repo_links(text) if not (document.parent / target).resolve().exists()]
        assert not missing, f"{document.name} broken links: {missing[:10]}"


def test_example_registry_matches_the_directory():
    cargo = CARGO.read_text(encoding="utf-8")
    registered = set(re.findall(r'path = "examples/([a-z0-9_]+)\.rs"', cargo))
    on_disk = {path.stem for path in (ROOT / "streamlit/examples").glob("*.rs")}
    # Explicit registrations must point at real files; the rest ride Cargo's
    # auto-discovery, which the build gates already exercise.
    assert registered <= on_disk, sorted(registered - on_disk)
    # The guide is the example index: every shipped example is named there.
    guide = GUIDE.read_text(encoding="utf-8")
    unindexed = sorted(example for example in on_disk if f"**{example}**" not in guide)
    assert not unindexed, f"examples missing from the guide index: {unindexed}"


def test_reference_dirs_carry_readme_and_manifest():
    overview = (ROOT / "tests/reference/reference-browser/README.md").read_text(encoding="utf-8")
    for directory in sorted((ROOT / "tests/reference/reference-browser").iterdir()):
        if not directory.is_dir():
            continue
        manifest = directory / "manifest.json" if (directory / "manifest.json").exists() else directory / "MANIFEST.json"
        if manifest.exists():
            # The curated frozen set: a README states its own scope, and every
            # manifest entry resolves.
            assert (directory / "README.md").exists(), f"{directory.name} lacks README"
            entries = json.loads(manifest.read_text(encoding="utf-8"))
            for item in entries.get("files", []):
                stored = item.get("stored_file", "")
                name = item.get("file") or (stored.split(f"reference-browser/{directory.name}/")[-1] if stored else "")
                if name:
                    # Repo-absolute stored paths resolve at ROOT; in-dir names at the chain.
                    target = (ROOT / name) if name.startswith("tests/") else (directory / name)
                    assert target.exists(), f"{directory.name}/{name} missing"
        elif not (directory / "README.md").exists():
            # Manifest-less AND readme-less: the overview README must index it.
            assert f"`{directory.name}/`:" in overview, f"{directory.name} is neither curated (manifest), self-documented (README), nor indexed by the overview"
