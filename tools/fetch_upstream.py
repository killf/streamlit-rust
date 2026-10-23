#!/usr/bin/env python3
"""Download and verify the locked Streamlit 1.66.1 artifacts.

Archives are content-addressed inputs under target/upstream/archives. This tool
never extracts a duplicate source tree; direct readers use archives explicitly.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
LOCK_PATH = ROOT / "upstream.lock.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download(url: str, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    request = Request(url, headers={"User-Agent": "streamlit-rust-baseline/1.0"})
    temporary = destination.with_suffix(destination.suffix + ".part")
    with urlopen(request) as response, temporary.open("wb") as handle:
        shutil.copyfileobj(response, handle, 1024 * 1024)
    temporary.replace(destination)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--download", action="store_true", help="download missing archives")
    args = parser.parse_args()

    lock = json.loads(LOCK_PATH.read_text(encoding="utf-8"))
    results = []
    failed = False
    for name, artifact in lock["artifacts"].items():
        archive = ROOT / artifact["cache_path"]
        resolved = archive.resolve()
        if ROOT.resolve() not in resolved.parents:
            print(f"{name}: unsafe cache path {artifact['cache_path']}", file=sys.stderr)
            return 2
        record = {"artifact": name, "path": artifact["cache_path"]}
        try:
            if not archive.is_file() and args.download:
                download(artifact["url"], archive)
                record["downloaded"] = True
            if not archive.is_file():
                raise FileNotFoundError(archive)
            actual_hash = sha256(archive)
            if actual_hash != artifact["sha256"] or archive.stat().st_size != artifact["bytes"]:
                raise ValueError(f"hash/size mismatch: {actual_hash}")
            record.update(verified=True, sha256=actual_hash)
        except Exception as error:
            failed = True
            record.update(verified=False, error=str(error))
        results.append(record)

    docs = lock["documentation"]
    catalog = ROOT / docs["catalog_path"]
    record = {"artifact": "official-docs-catalog", "path": docs["catalog_path"]}
    try:
        actual_hash = sha256(catalog)
        if actual_hash != docs["catalog_sha256"]:
            raise ValueError(f"hash mismatch: {actual_hash}")
        record.update(verified=True, sha256=actual_hash)
    except Exception as error:
        failed = True
        record.update(verified=False, error=str(error))
    results.append(record)

    print(json.dumps({"schema_version": 1, "results": results}, ensure_ascii=False, indent=2))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())