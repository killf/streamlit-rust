"""Derive the precise M3 partial inventory from the compatibility matrix.

Every implemented/partial entry's limitations are carried verbatim (they are
the recorded, reviewed boundary statements); the categorizer only buckets
them for the scope decision. Output: compatibility/m3-partial-inventory.json.
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).parents[1]
MATRIX = ROOT / "compatibility/api-compatibility-matrix.json"

# Bucket rules: matched against the limitation text; a feature may carry more
# than one bucket. Buckets are decision aids, not verdicts.
EXTERNAL = re.compile(r"YouTube|iframe|external source|real network|provider|crates\.io|new machine|other platform|publish", re.I)
RUST_EXTENSION = re.compile(r"Rust extension|no pinned-Python|no Python oracle|headless", re.I)
UNMEASURED_PARAMS = re.compile(r"unmeasured|unobserved|unverified|remain open|not measured|not covered|untested|未测|remain un", re.I)


def main():
    matrix = json.loads(MATRIX.read_text(encoding="utf-8"))
    entries = []
    for entry in matrix["entries"]:
        if entry["implementation_status"] != "implemented" or entry["compatibility_status"] != "partial":
            continue
        limitations = entry.get("limitations", [])
        buckets = set()
        for item in limitations:
            if EXTERNAL.search(item):
                buckets.add("needs-external-source-or-environment")
            if RUST_EXTENSION.search(item):
                buckets.add("rust-extension-or-headless-bound")
            if UNMEASURED_PARAMS.search(item):
                buckets.add("unmeasured-parameters")
        entries.append({
            "feature_id": entry["feature_id"],
            "category": entry.get("category", ""),
            "buckets": sorted(buckets) or ["no-explicit-gap-stated"],
            "limitations": limitations,
        })
    summary = {
        "total_partial": len(entries),
        "by_bucket": {},
    }
    for entry in entries:
        for bucket in entry["buckets"]:
            summary["by_bucket"][bucket] = summary["by_bucket"].get(bucket, 0) + 1
    out = {
        "schema_version": 1,
        "generated_from": "compatibility/api-compatibility-matrix.json",
        "note": ("Machine-derived from the matrix limitations verbatim; buckets are "
                 "decision aids for the user's range confirmation, not status changes. "
                 "Regenerate with tools/export_m3_inventory.py after every matrix edit."),
        "summary": summary,
        "entries": sorted(entries, key=lambda item: item["feature_id"]),
    }
    (ROOT / "compatibility/m3-partial-inventory.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
