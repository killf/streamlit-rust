#!/usr/bin/env python3
"""Regenerate and verify the single official-docs compatibility matrix."""

from __future__ import annotations

import hashlib
import json
import re
import sys
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
    if MATRIX_PATH.is_file():
        old = json.loads(MATRIX_PATH.read_text(encoding="utf-8"))
        for old_entry in old.get("entries", []):
            url = old_entry.get("official_url") or old_entry.get("official_doc", {}).get("url")
            previous[(old_entry["feature_id"], url)] = old_entry
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

    for entry in entries:
        old = previous.get((entry["feature_id"], entry["official_url"]))
        if not old:
            continue
        if old.get("implementation_status") == "implemented" and entry["implementation_status"] == "candidate":
            entry["implementation_status"] = "implemented"
        old_evidence = old.get("evidence", {})
        for key in ("rust_api_differential", "rust_wire_differential", "official_frontend_browser_e2e"):
            value = old_evidence.get(key)
            if value:
                entry["evidence"][key] = value
        old_status = old.get("compatibility_status")
        differential_keys = ("rust_api_differential", "rust_wire_differential", "official_frontend_browser_e2e")
        if old_status == "supported" and all(entry["evidence"].get(key) for key in differential_keys):
            entry["compatibility_status"] = "supported"
        elif old_status == "partial" and any(entry["evidence"].get(key) for key in differential_keys):
            entry["compatibility_status"] = "partial"
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
        "compatibility_status_rules_valid": all(
            entry["compatibility_status"] == "unverified"
            or (
                entry["compatibility_status"] in ("partial", "supported")
                and any(entry["evidence"].get(key) for key in ("rust_api_differential", "rust_wire_differential", "official_frontend_browser_e2e"))
            )
            for entry in entries
        ),
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
            "evidence_rule": "partial requires one Rust differential; supported requires API, wire, and official-frontend evidence.",
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
        "checks": checks,
        "conclusion": "Docs scope and captured official pages are verified. No entry is compatibility-supported; Python traces are reference evidence only.",
    }
    BASELINE_PATH.write_text(json.dumps(baseline, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"matrix": MATRIX_PATH.as_posix(), "baseline": BASELINE_PATH.as_posix(), "summary": matrix["summary"], "checks": checks}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())