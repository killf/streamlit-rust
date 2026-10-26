#!/usr/bin/env python3
"""Regenerate and verify the single official-docs compatibility matrix."""

from __future__ import annotations

import hashlib
import json
import re
import runpy
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


def verify_widget_capture(capture: dict, feature_id: str) -> None:
    """Replay the existing collector verdict for this API's operated widgets."""
    kind = {"st.selectbox": "selectbox", "st.slider": "slider", "st.checkbox": "checkbox"}.get(feature_id)
    if kind is None:
        raise ValueError("widget capture is only valid for the three input APIs")
    helpers = runpy.run_path(str(Path(__file__).resolve().parents[1] / "tests/reference/capture_browser_trace.py"))
    frames = capture.get("frames", [])
    interactions = capture.get("interactions", [])
    required = capture.get("required_cases", [])
    if (capture.get("failures") != [] or not required
            or helpers["suite_failures"](required, interactions)
            or capture.get("counts") != helpers["suite_counts"](required, interactions)):
        raise ValueError("incomplete widget capture suite")
    operated = [item for item in interactions if item.get("widget") == kind]
    if not operated:
        raise ValueError(f"no operated {kind} in widget capture")
    for item in operated:
        label, widget_id = item["label"], item["widget_id"]
        element = capture.get("wire_widgets", {}).get(f"{kind}|{label}", {})
        widget = element.get(kind, {})
        if (not widget_id or widget.get("id") != widget_id or widget.get("label") != label
                or not any(frame.get("direction") == "server->client"
                           and frame.get("decoded", {}).get("delta", {}).get("element") == kind
                           and frame["decoded"]["delta"].get("element_full") == element for frame in frames)):
            raise ValueError("operated widget lacks its full wire Element")
        start, end = item.get("state_frame"), item.get("completion_frame")
        if type(start) is not int or type(end) is not int or not 0 <= start < end < len(frames):
            raise ValueError("invalid widget operation frame window")
        if (not isinstance(item.get("action"), dict) or not item["action"].get("action")
                or frames[start].get("decoded", {}).get("message") != "BackMsg"
                or frames[end].get("direction") != "server->client"
                or frames[end].get("decoded", {}).get("type") != "script_finished"):
            raise ValueError("widget operation requires an action and real client/server frame types")
        request_id = frames[start].get("request_id")
        if not isinstance(request_id, str) or not request_id.strip() or frames[end].get("request_id") != request_id:
            raise ValueError("widget state/completion request IDs do not match")
        verdict = helpers["case_verdict"](
            {"kind": kind, "label": label}, frames,
            {"start": start, "end": end + 1, "widget": widget_id},
            item.get("action", {}), item.get("page_shows_before"), item.get("page_shows"))
        if (not verdict["ok"] or verdict["state_frame"] != start or verdict["completion_frame"] != end
                or verdict["wire_value"] != item.get("wire_value")
                or helpers["dom_value_for"](capture.get("dom_after", {}).get("markdown"), label) != item.get("page_shows")):
            raise ValueError(f"widget wire/action/DOM verdict failed for {label}")


def verify_data_loop(capture: dict, feature_id: str, path: Path, root: Path, python: bool, reviewed: dict | None = None) -> None:
    """Audit only the published positive uploader/dataframe loop, using QA readers."""
    if feature_id not in ("st.file_uploader", "st.dataframe"):
        raise ValueError("data-loop evidence is only valid for uploader/dataframe")
    relative = ("tests/reference/reference-browser/data-loop/updates-strict/trace-data-loop.json" if python
                else "tests/browser/rust-data-loop/trace-data-loop.json")
    provenance = root / ("tests/reference/reference-browser/data-loop/README.md" if python else "tests/browser/rust-data-loop/README.md")
    lock = json.loads((root / "upstream.lock.json").read_text(encoding="utf-8"))
    record = (reviewed or {}).get(relative)
    if not isinstance(record, dict):
        raise ValueError("data-loop requires explicit reviewed provenance")
    version = lock["streamlit"]["version"]
    if (record.get("source_version") != "1.66.1" or record.get("target_version") != version
            or version != "1.66.1" or record.get("provenance") != provenance.relative_to(root).as_posix()
            or not re.fullmatch(r"[0-9a-f]{40}", str(record.get("reviewed_commit", "")))
            or record.get("provenance_sha256") != digest(provenance)):
        raise ValueError("data-loop reviewed provenance source/target version or source hash mismatch")
    if (path.resolve() != (root / relative).resolve() or capture.get("case") != "data-loop"
            or record.get("sha256") != digest(path)
            or capture != json.loads(path.read_text(encoding="utf-8"))):
        raise ValueError("data-loop is not the reviewed frozen raw bytes/summary")
    frames = capture.get("frames", [])
    sessions = [f["decoded"]["new_session"] for f in frames if f.get("decoded", {}).get("type") == "new_session"]
    if not sessions or any(not n.get("session_id") or (n.get("name") == "Streamlit Rust") == python for n in sessions):
        raise ValueError("data-loop NewSession identity mismatch")
    # These legacy raws omit runtime versions. Their explicit external source
    # attestation applies only to the exact reviewed bytes, never arbitrary input.
    observed_versions = [capture.get("versions", {}).get("streamlit")]
    for session in sessions:
        observed_versions.extend((session.get("streamlit_version"), session.get("environment_info", {}).get("streamlit_version"),
                                  session.get("initialize", {}).get("environment_info", {}).get("streamlit_version")))
    if any(value != record["source_version"] for value in observed_versions if value is not None):
        raise ValueError("data-loop explicit raw version contradicts reviewed source version")
    if not python:
        fingerprint = re.search(r"sha256 ([0-9a-fA-F]{64})", capture.get("capture", {}).get("binary", ""))
        if not fingerprint or fingerprint[1].lower() not in provenance.read_text(encoding="utf-8").lower():
            raise ValueError("data-loop binary provenance mismatch")
    helpers = runpy.run_path(str(Path(__file__).resolve().parents[1] / "tests/reference/capture_browser_trace.py"))
    driver = runpy.run_path(str(Path(__file__).resolve().parents[1] / "tests/browser/numeric_capture.py"))
    stages = capture.get("stages", [])
    cases = driver["DATA_LOOP_CASES"]
    if [stage.get("stage") for stage in stages] != ["after-upload", *[case["label"] for case in cases]]:
        raise ValueError("data-loop requires all distinct positive stages")
    if capture.get("upload", {}).get("uploaded") is not True or capture.get("file_action", {}).get("action") != "none":
        raise ValueError("data-loop requires a successful positive upload")
    urls_req = [f["decoded"]["file_urls_request"] for f in frames if f.get("decoded", {}).get("type") == "file_urls_request"]
    urls_res = [f["decoded"]["file_urls_response"] for f in frames if f.get("decoded", {}).get("type") == "file_urls_response"]
    infos = capture.get("file_uploader_state", {}).get("value_full", {}).get("uploadedFileInfo", [])
    if not urls_req or not urls_res or not infos:
        raise ValueError("data-loop lacks upload URL exchange or uploaded file state")
    state = capture["file_uploader_state"]
    if (not any(f.get("decoded", {}).get("delta", {}).get("element") == "file_uploader"
                and f["decoded"]["delta"].get("id") == state.get("id") for f in frames)
            or not any(state == item for f in frames for item in f.get("decoded", {}).get("rerun_script", {}).get("widget_states", []))):
        raise ValueError("data-loop uploaded file state is not bound to the wire uploader")
    for info in infos:
        url = info.get("fileUrls", {}).get("uploadUrl")
        if (not url or not info.get("name") or int(info.get("size", 0)) <= 0
                or not any(response.get("response_id") == request.get("request_id")
                           and info["name"] in request.get("file_names", [])
                           and any(item.get("file_id") == info.get("fileId") and item.get("upload_url") == url
                                   for item in response.get("file_urls", [])) for request in urls_req for response in urls_res)
                or not any(item.get("method") == "PUT" and item.get("status") == 204 and item.get("url", "").endswith(url)
                           and "multipart/form-data" in str(item.get("request_headers", {})).lower()
                           for item in capture.get("upload_requests", []))):
            raise ValueError("data-loop upload fields/PUT 204 mismatch")
    # Re-read each retained IPC and compare both summaries and decoded wire bytes.
    for stage in stages:
        table = stage.get("table", {})
        arrow = table.get("arrow") or {}
        ipc_path = (path.parent / arrow.get("file", "")).resolve()
        if ipc_path.parent != path.parent.resolve() or not ipc_path.is_file():
            raise ValueError("missing or unsafe data-loop IPC")
        actual = helpers["arrow_summary"](ipc_path.read_bytes())
        if ("arrow_error" in actual or any(actual.get(k) != arrow.get(k) for k in ("sha256", "bytes"))
                or any(actual.get(k) != table.get(k) for k in ("rows", "columns", "row_count"))):
            raise ValueError("data-loop retained Arrow mismatch (PyArrow is required)")
        cells = stage.get("dom", {}).get("table_cells", [])
        expected = [row.get(column) for row in actual["rows"] for column in actual["columns"]]
        if not expected or len(cells) != len(expected) or not all(helpers["_same_cell_value"](a, b) for a, b in zip(expected, cells)):
            raise ValueError("data-loop Arrow cells do not match actual DOM")
        wire = [f.get("decoded", {}).get("delta", {}).get("arrow", {}) for f in frames
                if f.get("decoded", {}).get("delta", {}).get("element") == "dataframe"]
        if not any(a.get("sha256") == actual["sha256"] and a.get("base64") == actual.get("base64")
                   and a.get("rows") == actual["rows"] and a.get("columns") == actual["columns"] for a in wire):
            raise ValueError("data-loop dataframe IPC not present in wire")
    verified = [stages[0]]
    for case, before, stage in zip(cases, stages, stages[1:]):
        window = stage.get("window", {})
        if (not isinstance(stage.get("action"), dict) or not stage["action"].get("action")
                or type(window.get("start")) is not int or type(window.get("end")) is not int
                or not 0 <= window["start"] < window["end"] <= len(frames)):
            raise ValueError("data-loop action/window missing")
        verdict = helpers["data_loop_verdict"](case, frames, window, stage["action"], before.get("dom"), stage.get("dom"))
        if not verdict["ok"] or verdict.get("result_digest") != stage["table"]["arrow"]["sha256"]:
            raise ValueError(f"data-loop action/Arrow/DOM mismatch: {verdict['problems']}")
        sent, done = frames[verdict["state_frame"]], frames[verdict["completion_frame"]]
        if not sent.get("request_id") or sent["request_id"] != done.get("request_id") or done.get("direction") != "server->client":
            raise ValueError("data-loop completion request ID mismatch")
        if not any(f.get("request_id") == sent["request_id"] and f.get("connection") == sent.get("connection")
                   and f.get("decoded", {}).get("delta", {}).get("element") == "dataframe"
                   and f["decoded"]["delta"].get("arrow", {}).get("sha256") == verdict["result_digest"]
                   for f in frames[window["start"]:window["end"]]):
            raise ValueError("data-loop Arrow is not on the operation connection")
        verified.append({**stage, "verdict": verdict})
    result = driver["data_loop_result"](verified, capture["upload"], capture["file_action"], [c["label"] for c in cases])
    if not result["ok"] or capture.get("failures") != [] or result["counts"] != capture.get("counts"):
        raise ValueError("data-loop actual counts/verdict mismatch")


def merge_progress(entry: dict, old: dict | None, root: Path) -> dict:
    """Keep authored progress; generated docs authority is never overwritten."""
    if old is not None:
        if old.get("official_url") != entry["official_url"]:
            raise ValueError(f"official URL changed; review retained progress for {entry['feature_id']}")
        for key in ("implementation_status", "compatibility_status", "rust_plan", "compatibility_scope", "limitations", "rust_source_path", "not_applicable_reason"):
            if key in old:
                entry[key] = old[key]
        if not isinstance(old.get("evidence", {}), dict):
            raise ValueError("evidence must be an object")
        for key, value in old.get("evidence", {}).items():
            if key != "official_document_sha256":
                entry["evidence"][key] = value
    implementation = entry["implementation_status"]
    compatibility = entry["compatibility_status"]
    if implementation not in ("absent", "candidate", "implemented", "not_applicable") or compatibility not in ("unverified", "partial", "supported", "not_applicable"):
        raise ValueError(f"invalid status for {entry['feature_id']}")
    if "not_applicable" in (implementation, compatibility):
        # An inapplicability record is a reasoned closure, not an evidence
        # claim: the two statuses travel together, the reason is mandatory,
        # and no Rust implementation evidence may ride along.
        if (implementation, compatibility) != ("not_applicable", "not_applicable"):
            raise ValueError(f"not_applicable statuses must pair for {entry['feature_id']}")
        reason = entry.get("not_applicable_reason")
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError(f"not_applicable requires a reason for {entry['feature_id']}")
        if entry.get("rust_source_path"):
            raise ValueError(f"not_applicable cannot claim Rust source for {entry['feature_id']}")
        for key in ("python_browser_trace", "rust_api_test", "rust_wire_observation", "official_frontend_browser_e2e", "rust_api_differential", "rust_wire_differential"):
            if entry.get("evidence", {}).get(key):
                raise ValueError(f"not_applicable cannot carry Rust evidence ({key}) for {entry['feature_id']}")
    for key in ("rust_plan", "compatibility_scope"):
        if key in entry and (not isinstance(entry[key], str) or not entry[key].strip()):
            raise ValueError(f"empty {key}")
    if entry.get("rust_source_path") is not None:
        evidence_file(entry["rust_source_path"], root)
    for key, value in entry["evidence"].items():
        if key == "reviewed_captures":
            if not isinstance(value, dict):
                raise ValueError("reviewed captures must be explicit provenance records")
            continue
        # API identifiers (the alias rows' upstream targets), not file paths.
        if key in ("alias_target_python", "alias_target_native"):
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"empty alias target: {key}")
            continue
        if key == "official_document_sha256" or (key == "python_browser_trace" and value is None and compatibility in ("unverified", "not_applicable")):
            continue
        if isinstance(value, (list, tuple)):
            # Fixture lists: every member must resolve, fail-closed like a
            # single reference.
            if not value:
                raise ValueError(f"empty evidence list: {key}")
            for member in value:
                evidence_file(member, root)
        else:
            evidence_file(value, root)
    if compatibility not in ("unverified", "not_applicable"):
        for key in ("python_browser_trace", "rust_wire_observation", "official_frontend_browser_e2e"):
            path = evidence_file(entry["evidence"].get(key), root)
            capture = json.loads(path.read_text(encoding="utf-8"))
            if capture.get("kind") in ("python-reference-data-loop-trace", "rust-browser-data-loop-trace"):
                verify_data_loop(capture, entry["feature_id"], path, root, key == "python_browser_trace", entry["evidence"].get("reviewed_captures"))
                continue
            if capture.get("kind") in ("python-reference-widget-trace", "rust-browser-widget-trace") and "required_cases" in capture:
                verify_widget_capture(capture, entry["feature_id"])
                continue
            # The frozen status oracle records per-case decoded alerts and DOM,
            # rather than the generic browser collector's frames/steps layout.
            if key == "python_browser_trace" and capture.get("kind") == "python-reference-status-trace":
                expected_format = {"st.info": "INFO", "st.warning": "WARNING", "st.error": "ERROR", "st.success": "SUCCESS"}.get(entry["feature_id"])
                if expected_format is None:
                    raise ValueError("status oracle is only valid for the four status APIs")
                cases = capture.get("cases")
                if (capture.get("reference_version") != "1.66.1" or not isinstance(cases, dict) or not cases
                        or not all(isinstance(case.get("alerts"), list) for case in cases.values())
                        or not any(case["alerts"] for case in cases.values())):
                    raise ValueError("incomplete Python status case oracle")
                matched_format = False
                for case in cases.values():
                    for index, alert in enumerate(case["alerts"]):
                        wire = alert.get("wire", alert)
                        rendered_items = case.get("rendered_alerts", [])
                        rendered = alert.get("rendered") or (rendered_items[index] if index < len(rendered_items) else None)
                        if (wire.get("format") not in ("INFO", "WARNING", "ERROR", "SUCCESS")
                                or not isinstance(wire.get("body"), str)
                                or not isinstance(rendered, dict) or not isinstance(rendered.get("text"), str)
                                or not rendered["text"].strip()
                                or not isinstance(rendered.get("width_px", rendered.get("width")), (int, float))
                                or rendered.get("width_px", rendered.get("width")) <= 0):
                            raise ValueError("status oracle requires decoded alert and rendered observation")
                        matched_format |= wire["format"] == expected_format
                if not matched_format:
                    raise ValueError(f"status oracle has no rendered {expected_format} alert for {entry['feature_id']}")
                continue
            directions = {frame.get("direction") for frame in capture.get("frames", [])}
            if (capture.get("versions", {}).get("streamlit") != "1.66.1"
                    or not capture.get("steps") or capture.get("failures") != []
                    or not {"client->server", "server->client"} <= directions):
                # The journey chains (navigation, textelements, buttons,
                # pickers, display2, ...) publish the observation layout:
                # schema_version 1 with staged new_frames plus a manifest.
                stages = (capture.get("observation") or {}).get("stages")
                frames = [frame for stage in stages or [] for frame in stage.get("new_frames", [])]
                stage_directions = {frame.get("direction") for frame in frames}
                if (capture.get("schema_version") != 1 or capture.get("producer_error")
                        or not stages or not frames
                        or not {"client->server", "server->client"} <= stage_directions):
                    raise ValueError(f"incomplete browser/wire capture: {key}")
    if implementation not in ("absent", "not_applicable") and not entry.get("rust_source_path"):
        raise ValueError("candidate/implemented requires Rust source")
    if compatibility not in ("unverified", "not_applicable"):
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