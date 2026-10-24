"""Authored compatibility progress survives regeneration; unsupported claims fail closed."""
import copy
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("verify_matrix", ROOT / "tools/verify_p0.py")
verify = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(verify)


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    docs = tmp_path / "cache"
    docs.mkdir()
    page = docs / "button.html"
    page.write_text("captured official button page", encoding="utf-8")
    url = "https://docs.streamlit.io/develop/api-reference/widgets/st.button"
    catalog = {
        "items": [{"id": "st.button", "category": "PAGE ELEMENTS/Input widgets", "canonicalurl": url}],
        "sources": [{"http_status": 200, "cache_path": "cache/button.html", "canonicalurl": url,
                     "sha256": verify.digest(page), "bytes": page.stat().st_size}],
        "counts": {"total_catalog_entries": 1}, "completed_at_utc": "2026-10-23",
        "docs_latest_version_label": "1.66.0", "target_server_frontend_version": "1.66.1",
        "counting_policy": "Test catalog, not exhaustive.",
    }
    catalog_path = docs / "catalog.json"
    catalog_path.write_text(json.dumps(catalog), encoding="utf-8")
    lock = tmp_path / "lock.json"
    lock.write_text(json.dumps({"rust_baseline_head": "initial", "documentation": {
        "cache_path": "cache", "catalog_path": "cache/catalog.json",
        "catalog_sha256": verify.digest(catalog_path)}}), encoding="utf-8")
    matrix = tmp_path / "matrix.json"
    for key, value in {"ROOT": tmp_path, "LOCK_PATH": lock, "MATRIX_PATH": matrix,
                       "BASELINE_PATH": tmp_path / "baseline.json", "TRACE_PATH": tmp_path / "missing.json"}.items():
        monkeypatch.setattr(verify, key, value)
    monkeypatch.setattr(verify, "rust_candidates", lambda: {})
    monkeypatch.setattr(verify, "vendor_status", lambda lock: {"status": "unverified"})
    verify.main()
    return tmp_path, matrix


def recorded_partial(root, matrix):
    source = root / "button.rs"
    source.write_text("fn button() {}", encoding="utf-8")
    api = root / "api-test.rs"
    api.write_text("#[test]\nfn button_trigger() {}", encoding="utf-8")
    for name, original in (("oracle.json", "tests/reference/reference-browser/closed-loop/trace.json"),
                           ("rust.json", "tests/browser/rust-smoke/trace-smoke.json")):
        (root / name).write_bytes((ROOT / original).read_bytes())
    data = json.loads(matrix.read_text(encoding="utf-8"))
    row = data["entries"][0]
    row.update(implementation_status="implemented", compatibility_status="partial", rust_source_path="button.rs",
               rust_plan="Return a one-shot trigger and render the default button.",
               compatibility_scope="Default button rendering and three clicks on one socket only.",
               limitations=["No disabled/callback/form or reconnect compatibility claim."])
    row["evidence"].update(python_browser_trace="oracle.json", rust_api_test="api-test.rs",
                           rust_wire_observation="rust.json", official_frontend_browser_e2e="rust.json")
    return data


def test_regeneration_preserves_bounded_partial_and_plan(workspace):
    root, matrix = workspace
    data = recorded_partial(root, matrix)
    expected = copy.deepcopy(data["entries"][0])
    matrix.write_text(json.dumps(data), encoding="utf-8")
    for _ in range(2):
        assert verify.main() == 0
        regenerated = json.loads(matrix.read_text(encoding="utf-8"))
        assert regenerated["entries"][0] == expected
        assert regenerated["summary"]["compatibility_status_counts"] == {"partial": 1}


@pytest.mark.parametrize("corruption", ["status", "missing", "empty", "no_oracle", "no_api", "no_ws", "no_ui", "no_scope", "supported", "supported_observation", "compatibility_status", "fake_capture"])
def test_unsupported_claim_is_rejected_without_rewriting(workspace, corruption):
    root, matrix = workspace
    data = recorded_partial(root, matrix)
    row = data["entries"][0]
    if corruption == "status":
        row["implementation_status"] = "done"
    elif corruption == "compatibility_status":
        row["compatibility_status"] = "passed"
    elif corruption == "missing":
        row["evidence"]["rust_api_test"] = "not-created.rs"
    elif corruption == "empty":
        row["evidence"]["official_frontend_browser_e2e"] = " "
    elif corruption.startswith("no_"):
        key = {"no_oracle": "python_browser_trace", "no_api": "rust_api_test", "no_ws": "rust_wire_observation", "no_ui": "official_frontend_browser_e2e"}.get(corruption)
        if key:
            del row["evidence"][key]
        else:
            row["compatibility_scope"] = ""
    elif corruption in ("supported", "supported_observation"):
        row["compatibility_status"] = "supported"  # Observations are not differentials.
        if corruption == "supported_observation":
            row["evidence"].update(rust_api_differential="rust.json", rust_wire_differential="rust.json")
    else:
        (root / "rust.json").write_text('{"frames": [], "steps": [], "failures": []}', encoding="utf-8")
    matrix.write_text(json.dumps(data), encoding="utf-8")
    before = matrix.read_bytes()
    with pytest.raises((ValueError, TypeError)):
        verify.main()
    assert matrix.read_bytes() == before


def test_unverified_stays_unverified_and_docs_tampering_fails(workspace):
    root, matrix = workspace
    assert verify.main() == 0
    row = json.loads(matrix.read_text(encoding="utf-8"))["entries"][0]
    assert row["implementation_status"] == "absent"
    assert row["compatibility_status"] == "unverified"
    (root / "cache/button.html").write_text("tampered", encoding="utf-8")
    with pytest.raises(SystemExit, match="lacks captured source"):
        verify.main()


@pytest.mark.parametrize("corruption", ["wrong_id", "deleted_row"])
def test_lost_previous_feature_rejected_without_changing_either_output(workspace, corruption):
    root, matrix = workspace
    data = recorded_partial(root, matrix)
    if corruption == "wrong_id":
        data["entries"][0]["feature_id"] = "st.buton"
        message = "unmatched previous feature IDs"
    else:
        data["entries"].clear()
        message = "previous matrix missing feature IDs under unchanged catalog"
    matrix.write_text(json.dumps(data), encoding="utf-8")
    baseline = root / "baseline.json"
    before = (matrix.read_bytes(), baseline.read_bytes())
    with pytest.raises(ValueError, match=message):
        verify.main()
    assert (matrix.read_bytes(), baseline.read_bytes()) == before


def test_five_frozen_partials_retain_scope_and_evidence():
    matrix = json.loads((ROOT / "compatibility/api-compatibility-matrix.json").read_text(encoding="utf-8"))
    ids = {"st.session_state", "st.info", "st.warning", "st.error", "st.success"}
    recorded = [row for row in matrix["entries"] if row["feature_id"] in ids]
    assert len(recorded) == 5
    for row in recorded:
        assert row["compatibility_status"] == "partial"
        generated = copy.deepcopy(row)
        generated.update(implementation_status="absent", compatibility_status="unverified")
        for _ in range(2):
            generated = verify.merge_progress(generated, row, ROOT)
            assert generated == row


@pytest.mark.parametrize("feature_id", ["st.session_state", "st.error"])
def test_status_oracle_cannot_substitute_for_another_api(workspace, feature_id):
    root, matrix = workspace
    data = recorded_partial(root, matrix)
    row = data["entries"][0]
    row["feature_id"] = feature_id
    oracle = json.loads((ROOT / "tests/reference/reference-browser/status/trace-status.json").read_text(encoding="utf-8"))
    if feature_id == "st.error":
        info = next(alert for case in oracle["cases"].values() for alert in case["alerts"]
                    if alert["wire"]["format"] == "INFO")
        oracle["cases"] = {"info_only": {"alerts": [info]}}
    (root / "oracle.json").write_text(json.dumps(oracle), encoding="utf-8")
    # Keep catalog and authored row IDs consistent, so the oracle guard itself
    # must reject these claims rather than an unmatched-ID check doing so.
    catalog_path = root / "cache/catalog.json"
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    catalog["items"][0]["id"] = feature_id
    catalog_path.write_text(json.dumps(catalog), encoding="utf-8")
    lock_path = root / "lock.json"
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    lock["documentation"]["catalog_sha256"] = verify.digest(catalog_path)
    lock_path.write_text(json.dumps(lock), encoding="utf-8")
    data["scope"]["catalog_sha256"] = verify.digest(catalog_path)
    matrix.write_text(json.dumps(data), encoding="utf-8")
    baseline = root / "baseline.json"
    before = (matrix.read_bytes(), baseline.read_bytes())
    message = "only valid for the four status APIs" if feature_id == "st.session_state" else "no rendered ERROR alert"
    with pytest.raises(ValueError, match=message):
        verify.main()
    assert (matrix.read_bytes(), baseline.read_bytes()) == before


@pytest.mark.parametrize("corruption", ["presence_only", "wrong_dom"])
def test_widget_presence_or_recorded_ok_cannot_replace_operated_dom(corruption):
    capture = json.loads((ROOT / "tests/browser/rust-widgets/trace-widgets.json").read_text(encoding="utf-8"))
    for feature in ("st.selectbox", "st.slider", "st.checkbox"):
        verify.verify_widget_capture(capture, feature)
    if corruption == "presence_only":
        capture["interactions"] = [item for item in capture["interactions"] if item["widget"] != "checkbox"]
        capture["required_cases"] = [item["label"] for item in capture["interactions"]]
        count = len(capture["interactions"])
        capture["counts"] = {"expected": count, "executed": count, "asserted": count}
        message = "no operated checkbox"
    else:
        capture["dom_after"]["markdown"] = [line.replace("Include unknown region: false", "Include unknown region: true")
                                                 for line in capture["dom_after"]["markdown"]]
        message = "widget wire/action/DOM verdict failed"
    with pytest.raises(ValueError, match=message):
        verify.verify_widget_capture(capture, "st.checkbox")


@pytest.mark.parametrize("feature", ["st.file_uploader", "st.dataframe"])
def test_published_positive_data_loop(feature):
    for python, relative in ((False, "tests/browser/rust-data-loop/trace-data-loop.json"),
                             (True, "tests/reference/reference-browser/data-loop/updates-strict/trace-data-loop.json")):
        path = ROOT / relative
        matrix = json.loads((ROOT / "compatibility/api-compatibility-matrix.json").read_text(encoding="utf-8"))
        reviewed = next(row for row in matrix["entries"] if row["feature_id"] == feature)["evidence"]["reviewed_captures"]
        verify.verify_data_loop(json.loads(path.read_text(encoding="utf-8")), feature, path, ROOT, python, reviewed)


@pytest.mark.parametrize("corruption", ["api", "action", "empty_dom", "forged_dom", "version", "group", "put", "arrow"])
def test_data_loop_wrong_or_missing_evidence_is_rejected_without_outputs(corruption):
    path = ROOT / "tests/browser/rust-data-loop/trace-data-loop.json"
    capture = json.loads(path.read_text(encoding="utf-8"))
    feature = "st.dataframe"
    if corruption == "api":
        feature = "st.altair_chart"
    elif corruption == "action":
        capture["stages"][1].pop("action")
    elif corruption == "empty_dom":
        capture["stages"][0]["dom"]["table_cells"] = []
    elif corruption == "forged_dom":
        capture["stages"][1]["dom"]["table_cells"][0] = "forged"
    elif corruption == "version":
        next(f["decoded"]["new_session"] for f in capture["frames"] if f["decoded"].get("type") == "new_session")["environment_info"] = {"streamlit_version": "1.65.0"}
    elif corruption == "group":
        capture["stages"][2]["table"] = copy.deepcopy(capture["stages"][1]["table"])
        capture["stages"][2]["dom"] = copy.deepcopy(capture["stages"][1]["dom"])
    elif corruption == "put":
        capture["upload_requests"][0]["status"] = 403
    else:
        capture["stages"][1]["table"]["rows"][0]["row_count"] = 999
    outputs = [ROOT / "compatibility/api-compatibility-matrix.json", ROOT / "compatibility/p0-baseline.json"]
    before = [output.read_bytes() for output in outputs]
    with pytest.raises(ValueError):
        matrix = json.loads(outputs[0].read_text(encoding="utf-8"))
        reviewed = next(row for row in matrix["entries"] if row["feature_id"] == "st.dataframe")["evidence"]["reviewed_captures"]
        verify.verify_data_loop(capture, feature, path, ROOT, False, reviewed)
    assert [output.read_bytes() for output in outputs] == before


def test_unversioned_data_capture_without_reviewed_provenance_is_rejected():
    path = ROOT / "tests/browser/rust-data-loop/trace-data-loop.json"
    capture = json.loads(path.read_text(encoding="utf-8"))
    capture.pop("versions", None)
    for frame in capture["frames"]:
        session = frame.get("decoded", {}).get("new_session")
        if session is not None:
            session.pop("streamlit_version", None)
            session.pop("environment_info", None)
            session.get("initialize", {}).pop("environment_info", None)
    with pytest.raises(ValueError, match="reviewed provenance"):
        verify.verify_data_loop(capture, "st.dataframe", path, ROOT, False)


@pytest.mark.parametrize("corruption", ["unreviewed", "hash", "source_version", "missing_source", "missing_target", "provenance", "raw_tamper"])
def test_data_loop_reviewed_capture_binding_fails_closed(corruption, tmp_path):
    path = ROOT / "tests/browser/rust-data-loop/trace-data-loop.json"
    outputs = [ROOT / "compatibility/api-compatibility-matrix.json", ROOT / "compatibility/p0-baseline.json"]
    before = [p.read_bytes() for p in outputs]
    matrix = json.loads(before[0])
    reviewed = copy.deepcopy(next(row for row in matrix["entries"] if row["feature_id"] == "st.dataframe")["evidence"]["reviewed_captures"])
    record = reviewed[path.relative_to(ROOT).as_posix()]
    capture = json.loads(path.read_text(encoding="utf-8"))
    if corruption == "unreviewed":
        reviewed.clear()
    elif corruption == "hash":
        record["sha256"] = "0" * 64
    elif corruption == "source_version":
        record["source_version"] = "1.65.0"
    elif corruption == "missing_source":
        del record["source_version"]
    elif corruption == "missing_target":
        del record["target_version"]
    elif corruption == "provenance":
        del record["provenance"]
    else:
        capture["capture"]["unreviewed_change"] = True
        # Tamper a real copy's bytes, while retaining the reviewed old digest.
        relative = path.relative_to(ROOT)
        path = tmp_path / relative
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps(capture), encoding="utf-8")
        provenance = tmp_path / record["provenance"]
        provenance.write_bytes((ROOT / record["provenance"]).read_bytes())
        (tmp_path / "upstream.lock.json").write_bytes((ROOT / "upstream.lock.json").read_bytes())
    with pytest.raises(ValueError):
        verify.verify_data_loop(capture, "st.dataframe", path, tmp_path if corruption == "raw_tamper" else ROOT, False, reviewed)
    assert [p.read_bytes() for p in outputs] == before


def test_missing_source_provenance_aborts_generator_before_either_write(tmp_path, monkeypatch):
    matrix_path = tmp_path / "matrix.json"
    baseline_path = tmp_path / "baseline.json"
    matrix = json.loads((ROOT / "compatibility/api-compatibility-matrix.json").read_text(encoding="utf-8"))
    row = next(row for row in matrix["entries"] if row["feature_id"] == "st.dataframe")
    del row["evidence"]["reviewed_captures"]["tests/browser/rust-data-loop/trace-data-loop.json"]["source_version"]
    matrix_path.write_text(json.dumps(matrix), encoding="utf-8")
    baseline_path.write_bytes((ROOT / "compatibility/p0-baseline.json").read_bytes())
    monkeypatch.setattr(verify, "MATRIX_PATH", matrix_path)
    monkeypatch.setattr(verify, "BASELINE_PATH", baseline_path)
    before = (matrix_path.read_bytes(), baseline_path.read_bytes())
    with pytest.raises(ValueError, match="source/target version"):
        verify.main()
    assert (matrix_path.read_bytes(), baseline_path.read_bytes()) == before
