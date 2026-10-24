"""Unit tests for explicit artifact location mapping, not product evidence."""
import copy
import hashlib
import json
import pathlib
import sys
import tempfile
import pytest
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import forms_capture as capture


def record(path):
    data = path.read_bytes()
    return {"stored_file": path.relative_to(capture.ROOT).as_posix(), "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


@pytest.fixture
def bundle():
    parent = capture.ROOT / "target/forms-capture/artifact-map-unit"
    parent.mkdir(parents=True, exist_ok=True)
    folder = pathlib.Path(tempfile.mkdtemp(prefix="unit-", dir=parent))
    image = folder / "observed.png"
    image.write_bytes((capture.ROOT / "tests/browser/rust-forms-j05/png/form-j05-continuous-01-load.png").read_bytes())
    image_record = record(image)
    shot = {"file": "target/original-unavailable.png", "bytes": image_record["bytes"], "sha256": image_record["sha256"]}
    trace = {"frames": [{"synthetic_unit": True}], "cases": [{"case_id": "form-j05-continuous", "phases": [{"phase_id": "form-j05-continuous:type", "screenshot": shot}]}]}
    raw = folder / "trace.json";raw.write_text(json.dumps(trace), encoding="utf-8")
    source = folder / "source-unit.txt";source.write_bytes(b"synthetic unit source file")
    manifest = {"raw": record(raw), "files": [record(raw), image_record, record(source)], "path_map": [{"original_file": shot["file"], "case_id": "form-j05-continuous", "phase_id": "form-j05-continuous:type", **image_record}]}
    path = folder / "MANIFEST.json"
    return folder, raw, trace, manifest, path


def resolve(bundle):
    folder, raw, trace, manifest, path = bundle
    path.write_text(json.dumps(manifest), encoding="utf-8")
    return capture.resolve_artifact_manifest(trace, raw, path)


def test_mapping_changes_only_copy_png_file_and_preserves_original_bytes(bundle):
    folder, raw, trace, manifest, path = bundle
    before = copy.deepcopy(trace);original = raw.read_bytes()
    mapped, info = resolve(bundle)
    assert trace == before and raw.read_bytes() == original
    assert mapped["frames"] == before["frames"]
    shot = mapped["cases"][0]["phases"][0]["screenshot"]
    assert shot["file"] == manifest["path_map"][0]["stored_file"]
    assert shot["sha256"] == before["cases"][0]["phases"][0]["screenshot"]["sha256"]
    assert info["mapped_pngs"] == 1 and info["verified_files"] == 3
    shot["file"] = before["cases"][0]["phases"][0]["screenshot"]["file"]
    assert mapped == before  # PB/DOM/clocks/typed states and every other field intact.


@pytest.mark.parametrize("mutation", ["raw_hash", "raw_bytes", "png_hash", "wrong_phase", "wrong_case", "duplicate_map", "missing_map", "duplicate_file", "inventory_tamper", "png_tamper", "path_escape"])
def test_bad_or_incomplete_mapping_is_rejected(bundle, mutation):
    folder, raw, trace, manifest, path = bundle
    if mutation == "raw_hash": manifest["raw"]["sha256"] = "f" * 64
    if mutation == "raw_bytes": manifest["raw"]["bytes"] += 1
    if mutation == "png_hash": manifest["path_map"][0]["sha256"] = "f" * 64
    if mutation == "wrong_phase": manifest["path_map"][0]["phase_id"] = "form-j05-continuous:submit"
    if mutation == "wrong_case": manifest["path_map"][0]["case_id"] = "form-default-submit"
    if mutation == "duplicate_map": manifest["path_map"].append(copy.deepcopy(manifest["path_map"][0]))
    if mutation == "missing_map": manifest["path_map"] = []
    if mutation == "duplicate_file": manifest["files"].append(copy.deepcopy(manifest["files"][0]))
    if mutation == "inventory_tamper": (folder / "source-unit.txt").write_bytes(b"changed")
    if mutation == "png_tamper": (folder / "observed.png").write_bytes(b"changed")
    if mutation == "path_escape":
        escaped = folder.parent / (folder.name + "-outside.json");escaped.write_bytes(raw.read_bytes())
        manifest["raw"] = record(escaped)
    with pytest.raises((ValueError, KeyError)): resolve(bundle)


def test_manifest_cannot_be_used_for_another_same_bytes_raw_path(bundle):
    folder, raw, trace, manifest, path = bundle
    path.write_text(json.dumps(manifest), encoding="utf-8")
    another = folder / "another.json";another.write_bytes(raw.read_bytes())
    with pytest.raises(ValueError): capture.resolve_artifact_manifest(trace, another, path)


def test_csv_manifest_flag_cannot_silently_enter_capture(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["forms_capture.py", "--url", "http://unit.invalid", "--artifact-manifest", "unit.json"])
    with pytest.raises(SystemExit) as error: capture.main()
    assert error.value.code == 2


def test_extra_mapping_not_referenced_by_raw_is_rejected(bundle):
    folder, raw, trace, manifest, path = bundle
    extra = folder / "extra.png";extra.write_bytes((folder / "observed.png").read_bytes())
    entry = {**manifest["path_map"][0], **record(extra), "original_file": "unreferenced.png"}
    manifest["path_map"].append(entry)
    with pytest.raises(ValueError): resolve(bundle)


def test_parent_directory_path_escape_is_rejected(bundle):
    folder, raw, trace, manifest, path = bundle
    outside = folder.parent / (folder.name + "-parent.json");outside.write_bytes(raw.read_bytes())
    manifest["raw"] = record(outside)
    manifest["raw"]["stored_file"] = folder.relative_to(capture.ROOT).as_posix() + "/../" + outside.name
    with pytest.raises(ValueError): resolve(bundle)


def test_resolved_link_outside_bundle_is_rejected_without_privilege_skip(bundle, monkeypatch):
    folder, raw, trace, manifest, path = bundle
    outside = folder.parent / (folder.name + "-linked.json");outside.write_bytes(raw.read_bytes())
    alias = folder / "link.json"
    manifest["raw"] = {**record(raw), "stored_file": alias.relative_to(capture.ROOT).as_posix()}
    original = pathlib.Path.resolve
    def resolved(self, *args, **kwargs):
        return outside if self == alias else original(self, *args, **kwargs)
    monkeypatch.setattr(pathlib.Path, "resolve", resolved)
    with pytest.raises(ValueError): resolve(bundle)


@pytest.mark.parametrize("missing", [False, True])
def test_bad_manifest_prevents_pb_and_contract_replay(bundle, monkeypatch, capsys, missing):
    folder, raw, trace, manifest, path = bundle
    manifest["raw"]["sha256"] = "f" * 64
    path.write_text(json.dumps(manifest), encoding="utf-8")
    if missing: path = folder / "missing-manifest.json"
    def forbidden(*args, **kwargs): raise AssertionError("unbound artifacts must not be replayed")
    import forms_contract
    monkeypatch.setattr(capture, "require_decoder", lambda: None)
    monkeypatch.setattr(capture, "pb_trace_report", forbidden)
    monkeypatch.setattr(forms_contract, "verify_forms_text_input_contract", forbidden)
    assert capture.verify_trace(raw, case_ids=["form-j05-continuous"], j05_profile="csv-data-app", artifact_manifest=path) == 1
    report = json.loads(capsys.readouterr().out)
    assert report["ok"] is False and report["contract"]["checked_case_count"] == 0
    assert report["contract"]["failures"][0]["code"] == "artifact_manifest"
