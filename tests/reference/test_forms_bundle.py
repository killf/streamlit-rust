"""Fresh-checkout gates for selected forms evidence, never ignored caches."""
from __future__ import annotations

import copy
import hashlib
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests/browser"))
from forms_contract import CANONICAL_CASE_IDS, verify_forms_text_input_contract  # noqa: E402

def _verified_stored(bundle: pathlib.Path, record: dict) -> bytes:
    path = (ROOT / record["stored_file"]).resolve(strict=True)
    assert path.is_relative_to(bundle.resolve())
    data = path.read_bytes()
    assert len(data) == record["bytes"]
    assert hashlib.sha256(data).hexdigest() == record["sha256"]
    return data


def test_selected_forms_bundle_is_complete():
    bundle = ROOT / "tests/reference/reference-browser/forms-final"
    manifest = json.loads((bundle / "MANIFEST.json").read_text(encoding="utf-8"))
    raw = (bundle / "trace-forms.json").read_bytes()
    assert manifest["raw"] == {
        "file": "tests/reference/reference-browser/forms-final/trace-forms.json",
        "bytes": 1801839,
        "sha256": "a8ac7bb0c996eea0a9eedd22aabaf0cd34b5bd613abce390eb17f370745cebe0",
    }
    assert len(raw) == manifest["raw"]["bytes"]
    assert hashlib.sha256(raw).hexdigest() == manifest["raw"]["sha256"]
    observed = json.loads(raw)
    state = json.loads((bundle / "capture-state.json").read_text(encoding="utf-8"))
    assert state["complete"] is True
    assert type(state["process_exit_code"]) is int and state["process_exit_code"] == 0
    assert state["failure"] is None and state["active_case_id"] is None
    assert state["trace_sha256"] == hashlib.sha256(raw).hexdigest()
    assert state["completed_case_ids"] == list(CANONICAL_CASE_IDS)
    assert [case["case_id"] for case in observed["cases"]] == list(CANONICAL_CASE_IDS)
    screenshots = [phase["screenshot"] for case in observed["cases"] for phase in case["phases"]]
    expected = {(png["file"], png["bytes"], png["sha256"]) for png in screenshots}
    actual = {(png["file"], png["bytes"], png["sha256"]) for png in state["observed_png_files"]}
    assert len(expected) == len(screenshots) == len(actual) == len(state["observed_png_files"])
    assert expected == actual
    assert {path.resolve() for path in (bundle / "png").glob("*.png")} == {(ROOT / png["file"]).resolve() for png in screenshots}


def test_rust_j05_original_raw_and_explicit_path_map_pass_the_same_contract():
    bundle = ROOT / "tests/browser/rust-forms-j05"
    manifest = json.loads((bundle / "MANIFEST.json").read_text(encoding="utf-8"))
    payload = _verified_stored(bundle, manifest["raw"])
    assert hashlib.sha256(payload).hexdigest() == "9160ce04c3336a4de7b6ce997d9eb7988187313cfcc9c0e335d5708402bfd82c"
    observed = json.loads(payload)
    mapped = copy.deepcopy(observed)
    path_map = {entry["original_file"]: entry for entry in manifest["path_map"]}
    assert len(path_map) == len(manifest["path_map"]) == 6
    used = set()
    for case in mapped["cases"]:
        for phase in case["phases"]:
            png = phase["screenshot"]
            entry = path_map[png["file"]]
            assert (entry["case_id"], entry["phase_id"]) == (case["case_id"], phase["phase_id"])
            assert (entry["sha256"], entry["bytes"]) == (png["sha256"], png["bytes"])
            assert _verified_stored(bundle, entry).startswith(b"\x89PNG\r\n\x1a\n")
            used.add(png["file"])
            # Only the resolved artifact location changes in memory. Raw PB,
            # DOM, clocks and recorded hashes always come from original bytes.
            png["file"] = entry["stored_file"]
    assert used == set(path_map)
    fields = set()
    for entry in manifest["provenance_path_map"]:
        if entry["field"] == "runtime_source_set":
            continue
        original = observed["capture_provenance"][entry["field"]]
        assert (original["path"], original["bytes"], original["sha256"]) == (entry["original_file"], entry["bytes"], entry["sha256"])
        _verified_stored(bundle, entry)
        fields.add(entry["field"])
    assert fields == {"candidate_manifest", "runtime_config"}
    assert verify_forms_text_input_contract(mapped, case_ids=("form-j05-continuous",), require_png=True) == []
