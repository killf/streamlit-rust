#!/usr/bin/env python3
"""Regenerate and verify the single official-docs compatibility matrix."""

from __future__ import annotations

import hashlib
import json
import re
import tarfile
import zipfile
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOCK_PATH = ROOT / "upstream.lock.json"
MATRIX_PATH = ROOT / "compatibility/api-compatibility-matrix.json"
BASELINE_PATH = ROOT / "compatibility/p0-baseline.json"
TRACE_PATH = ROOT / "tests/reference/reference-browser/closed-loop/trace.json"

TRACE_EVIDENCE = {
    "st.button": "closed-loop",
    "st.file_uploader": "closed-loop",
    "st.selectbox": "closed-loop",
    "st.slider": "closed-loop",
    "st.checkbox": "closed-loop",
    "st.dataframe": "closed-loop",
    "st.form": "form",
    "st.form_submit_button": "form",
    "st.tabs": "tabs",
}


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def rust_candidates() -> dict[str, str]:
    result: dict[str, str] = {}
    in_trait = False
    for line_number, line in enumerate((ROOT / "streamlit/src/api.rs").read_text(encoding="utf-8").splitlines(), 1):
        if line.startswith("pub trait StreamlitApi"):
            in_trait = True
        if in_trait and line.startswith("}"):
            break
        match = re.match(r"^\s{4}fn\s+([A-Za-z_][A-Za-z0-9_]*)", line) if in_trait else None
        if match:
            result[match.group(1)] = f"streamlit/src/api.rs:{line_number}"
    return result


def trace_for(feature_id: str, scenarios: set[str]) -> str | None:
    scenario = TRACE_EVIDENCE.get(feature_id)
    if scenario not in scenarios:
        return None
    name = "trace.json" if scenario == "closed-loop" else f"trace-{scenario}.json"
    relative = Path("tests/reference/reference-browser") / scenario / name
    return relative.as_posix() if (ROOT / relative).is_file() else None


def evidence_file(reference: str, root: Path) -> Path:
    """Resolve repository-relative file[:line] evidence, never external paths."""
    if not isinstance(reference, str) or not reference.strip():
        raise ValueError("empty evidence reference")
    match = re.fullmatch(r"(.+?)(?::([1-9][0-9]*))?", reference)
    if match is None:
        raise ValueError("invalid evidence reference")
    relative = Path(match[1])
    path = (root / relative).resolve()
    if relative.is_absolute() or root.resolve() not in path.parents or not path.is_file() or not path.stat().st_size:
        raise ValueError(f"missing or unsafe evidence: {reference}")
    if match[2] and int(match[2]) > len(path.read_text(encoding="utf-8").splitlines()):
        raise ValueError(f"evidence line does not exist: {reference}")
    return path


def merge_progress(entry: dict, old: dict | None, root: Path) -> dict:
    """Keep authored progress; generated docs authority is never overwritten."""
    if old is not None:
        if old.get("official_url") != entry["official_url"]:
            raise ValueError(f"official URL changed; review retained progress for {entry['feature_id']}")
        for key in ("implementation_status", "compatibility_status", "rust_plan", "compatibility_scope", "limitations", "rust_source_path"):
            if key in old:
                entry[key] = old[key]
        if not isinstance(old.get("evidence", {}), dict):
            raise ValueError("evidence must be an object")
        for key, value in old.get("evidence", {}).items():
            if key != "official_document_sha256":
                entry["evidence"][key] = value
    implementation = entry["implementation_status"]
    compatibility = entry["compatibility_status"]
    if implementation not in ("absent", "candidate", "implemented") or compatibility not in ("unverified", "partial", "supported"):
        raise ValueError(f"invalid status for {entry['feature_id']}")
    for key in ("rust_plan", "compatibility_scope"):
        if key in entry and (not isinstance(entry[key], str) or not entry[key].strip()):
            raise ValueError(f"empty {key}")
    if entry.get("rust_source_path") is not None:
        evidence_file(entry["rust_source_path"], root)
    for key, value in entry["evidence"].items():
        if key == "official_document_sha256" or (key == "python_browser_trace" and value is None and compatibility == "unverified"):
            continue
        evidence_file(value, root)
    if compatibility != "unverified":
        for key in ("python_browser_trace", "rust_wire_observation", "official_frontend_browser_e2e"):
            path = evidence_file(entry["evidence"].get(key), root)
            capture = json.loads(path.read_text(encoding="utf-8"))
            directions = {frame.get("direction") for frame in capture.get("frames", [])}
            if (capture.get("versions", {}).get("streamlit") != "1.66.1"
                    or not capture.get("steps") or capture.get("failures") != []
                    or not {"client->server", "server->client"} <= directions):
                raise ValueError(f"incomplete browser/wire capture: {key}")
    if implementation != "absent" and not entry.get("rust_source_path"):
        raise ValueError("candidate/implemented requires Rust source")
    if compatibility != "unverified":
        if implementation != "implemented" or not entry.get("compatibility_scope") or not entry.get("rust_plan"):
            raise ValueError("verified progress requires implementation, concrete plan and bounded scope")
        required = ["python_browser_trace", "rust_api_test", "rust_wire_observation", "official_frontend_browser_e2e"]
        if compatibility == "supported":
            required += ["rust_api_differential", "rust_wire_differential"]
        for key in required:
            evidence_file(entry["evidence"].get(key), root)
        if compatibility == "supported":
            for key in ("rust_api_differential", "rust_wire_differential"):
                result = json.loads(evidence_file(entry["evidence"][key], root).read_text(encoding="utf-8"))
                if (result.get("feature_id") != entry["feature_id"] or result.get("status") != "pass"
                        or type(result.get("compared_cases")) is not int or result["compared_cases"] < 1
                        or result.get("failures") != []):
                    raise ValueError(f"missing passing feature-specific differential result: {key}")
    return entry


def vendor_status(lock: dict) -> dict:
    """Optional cache audit: vendor equality is independent of API progress."""
    result = {"status": "unverified", "authority": "upstream.lock.json", "scope": "Official frontend/protobuf bytes only; no API compatibility credit."}
    artifacts = lock["artifacts"]
    paths = {key: ROOT / artifacts[key]["cache_path"] for key in ("wheel", "github_archive")}
    if not all(path.is_file() for path in paths.values()):
        result["reason"] = "Locked archives unavailable; optional cache audit not run."
        return result
    for key, path in paths.items():
        if digest(path) != artifacts[key]["sha256"]:
            raise ValueError(f"vendor archive hash mismatch: {key}")
    with zipfile.ZipFile(paths["wheel"]) as archive:
        prefix = "streamlit/static/"
        frontend = {name[len(prefix):]: hashlib.sha256(archive.read(name)).hexdigest()
                    for name in archive.namelist() if name.startswith(prefix) and not name.endswith("/")}
    with tarfile.open(paths["github_archive"], "r:gz") as archive:
        proto = {}
        for member in archive:
            relative = member.name.partition("/")[2]
            if member.isfile() and relative.startswith("proto/streamlit/proto/") and relative.endswith(".proto"):
                proto[relative.removeprefix("proto/streamlit/proto/")] = hashlib.sha256(archive.extractfile(member).read()).hexdigest()
    def equal_tree(folder: Path, expected: dict) -> bool:
        actual = {path.relative_to(folder).as_posix(): digest(path) for path in folder.rglob("*") if path.is_file()}
        return bool(expected) and actual == expected
    # Repository instruction files are not vendor protocol schema.
    actual_proto = {path.relative_to(ROOT / "streamlit/proto").as_posix(): digest(path)
                    for path in (ROOT / "streamlit/proto").rglob("*.proto")}
    result.update(frontend_files=len(frontend), protocol_files=len(proto),
                  frontend_bytes_equal=equal_tree(ROOT / "www", frontend), protocol_bytes_equal=bool(proto) and actual_proto == proto)
    result["status"] = "verified" if result["frontend_bytes_equal"] and result["protocol_bytes_equal"] else "mismatch"
    if result["status"] == "mismatch":
        raise ValueError(f"vendor bytes differ: {result}")
    return result


def main() -> int:
    lock = json.loads(LOCK_PATH.read_text(encoding="utf-8"))
    docs_meta = lock["documentation"]
    docs_root = (ROOT / docs_meta["cache_path"]).resolve()
    catalog_path = ROOT / docs_meta["catalog_path"]
    if ROOT.resolve() not in docs_root.parents:
        raise SystemExit("unsafe documentation cache path")
    if not catalog_path.is_file():
        raise SystemExit("official docs catalog is missing")
    catalog_hash = digest(catalog_path)
    if catalog_hash != docs_meta["catalog_sha256"]:
        raise SystemExit("official docs catalog hash mismatch")
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    items = catalog.get("items") or []
    if not items:
        raise SystemExit("official docs catalog has no items")

    sources: dict[str, dict] = {}
    for source in catalog.get("sources", []):
        if source.get("http_status") != 200:
            continue
        cache = (ROOT / source["cache_path"]).resolve()
        if docs_root not in cache.parents or not cache.is_file():
            continue
        if digest(cache) == source["sha256"] and cache.stat().st_size == source["bytes"]:
            sources[source["canonicalurl"]] = source
    valid_sources = len(sources)
    expected_sources = len(catalog.get("sources", []))

    candidates = rust_candidates()
    trace = json.loads(TRACE_PATH.read_text(encoding="utf-8")) if TRACE_PATH.is_file() else {}
    scenarios = {"closed-loop"}
    for path in (ROOT / "tests/reference/reference-browser").glob("*/trace-*.json"):
        scenarios.add(path.parent.name)
    if trace:
        scenarios.add(trace.get("scenario") or "closed-loop")

    previous = {}
    old_catalog_hash = None
    if MATRIX_PATH.is_file():
        old = json.loads(MATRIX_PATH.read_text(encoding="utf-8"))
        old_catalog_hash = old.get("scope", {}).get("catalog_sha256")
        for old_entry in old.get("entries", []):
            if old_entry["feature_id"] in previous:
                raise ValueError("duplicate previous feature_id")
            previous[old_entry["feature_id"]] = old_entry
    entries = []
    for item in items:
        url = item["canonicalurl"]
        source = sources.get(url)
        if source is None:
            raise SystemExit(f"documented feature lacks captured source: {url}")
        candidate = candidates.get(item["id"].removeprefix("st."))
        evidence = {
            "official_document_sha256": source["sha256"],
            "python_browser_trace": trace_for(item["id"], scenarios),
        }
        if candidate:
            evidence["rust_source"] = candidate
        entries.append({
            "feature_id": item["id"],
            "category": item["category"],
            "scope_type": "concept" if item["category"].startswith("CONCEPTS/") else "api-reference",
            "official_url": url,
            "rust_source_path": candidate,
            "implementation_status": "candidate" if candidate else "absent",
            "compatibility_status": "unverified",
            "evidence": evidence,
        })

    current_ids = {entry["feature_id"] for entry in entries}
    unmatched_ids = previous.keys() - current_ids
    if unmatched_ids:
        raise ValueError(f"unmatched previous feature IDs: {sorted(unmatched_ids)}")
    missing_ids = current_ids - previous.keys()
    if old_catalog_hash == catalog_hash and missing_ids:
        raise ValueError(f"previous matrix missing feature IDs under unchanged catalog: {sorted(missing_ids)}")
    entries = [merge_progress(entry, previous.get(entry["feature_id"]), ROOT) for entry in entries]
    vendor = vendor_status(lock)
    implementation_counts = dict(Counter(entry["implementation_status"] for entry in entries))
    compatibility_counts = dict(Counter(entry["compatibility_status"] for entry in entries))
    expected_count = catalog["counts"]["total_catalog_entries"]
    checks = {
        "catalog_hash_matches_lock": True,
        "catalog_completed": bool(catalog.get("completed_at_utc")),
        "catalog_fetch_errors_empty": not catalog.get("fetch_errors"),
        "catalog_count_matches": len(entries) == expected_count,
        "feature_ids_unique": len({entry["feature_id"] for entry in entries}) == len(entries),
        "official_urls_unique": len({entry["official_url"] for entry in entries}) == len(entries),
        "captured_sources_valid": valid_sources == expected_sources,
        "compatibility_status_rules_valid": True,  # merge_progress rejects invalid evidence/status before writing.
    }
    if not all(checks.values()):
        raise SystemExit(f"matrix checks failed: {checks}")

    matrix = {
        "schema_version": 2,
        "baseline_head": lock["rust_baseline_head"],
        "scope": {
            "authority": "official Streamlit docs catalog",
            "docs_version_label": catalog["docs_latest_version_label"],
            "runtime_version": catalog["target_server_frontend_version"],
            "catalog_sha256": catalog_hash,
            "counting_policy": catalog["counting_policy"],
            "not_available_in_current_docs": catalog.get("not_available_in_current_docs", []),
            "redirect_aliases_not_counted": catalog.get("redirect_aliases", []),
        },
        "defaults": {
            "rust_plan": "Implement documented behavior in the Rust backend; never modify the official frontend bundle.",
            "backend_only": True,
            "official_frontend_bundle_unmodified": True,
            "status_vocabulary": {
                "implementation_status": ["absent", "candidate", "implemented"],
                "compatibility_status": ["unverified", "partial", "supported"],
            },
            "evidence_rule": "partial requires bounded scope, Python oracle, Rust API test and wire/UI observations; supported additionally requires API and wire JSON differentials with feature_id, status=pass, compared_cases>0 and failures=[]. Evidence files must exist and be nonempty; independent review establishes semantic sufficiency.",
        },
        "summary": {
            "captured_catalog_entries": len(entries),
            "is_complete_official_denominator": False,
            "unavailable_requested_pages": len(catalog.get("not_available_in_current_docs", [])),
            "redirect_aliases_not_counted": len(catalog.get("redirect_aliases", [])),
            "implementation_status_counts": implementation_counts,
            "compatibility_status_counts": compatibility_counts,
            "unique_feature_ids": len({entry["feature_id"] for entry in entries}),
            "unique_official_urls": len({entry["official_url"] for entry in entries}),
            "captured_sources_valid": valid_sources,
            "captured_sources_total": expected_sources,
            "python_browser_trace_links": sum(entry["evidence"].get("python_browser_trace") is not None for entry in entries),
        },
        "vendor_migration": vendor,
        "entries": entries,
    }
    MATRIX_PATH.write_text(json.dumps(matrix, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")

    baseline = {
        "schema_version": 4,
        "baseline_head": lock["rust_baseline_head"],
        "scope": "Official docs catalog is the captured product-scope input, not a completeness denominator; runtime remains Streamlit 1.66.1.",
        "docs": {
            "version_label": catalog["docs_latest_version_label"],
            "runtime_version": catalog["target_server_frontend_version"],
            "catalog_sha256": catalog_hash,
            "captured_catalog_entries": len(entries),
            "is_complete_official_denominator": False,
            "unavailable_requested_pages": len(catalog.get("not_available_in_current_docs", [])),
            "redirect_aliases_not_counted": len(catalog.get("redirect_aliases", [])),
            "captured_sources": valid_sources,
            "not_available_in_current_docs": catalog.get("not_available_in_current_docs", []),
            "redirect_aliases_not_counted": catalog.get("redirect_aliases", []),
        },
        "matrix_summary": matrix["summary"],
        "vendor_migration": vendor,
        "checks": checks,
        "conclusion": "Captured docs hashes and retained progress evidence paths validated; page inventory is not exhaustive. Compatibility claims are limited to each row scope and require independent review. Vendor equality gives no API credit.",
    }
    BASELINE_PATH.write_text(json.dumps(baseline, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"matrix": MATRIX_PATH.as_posix(), "baseline": BASELINE_PATH.as_posix(), "summary": matrix["summary"], "checks": checks}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())