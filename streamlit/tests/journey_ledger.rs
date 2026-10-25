//! Fail-closed validation of the journey-manifest ledger.
//!
//! The ledger gate runs inside `cargo test` (this file); the former Python
//! `validate_journeys.py` was removed so repository tests stay in Rust except
//! where they must drive the pinned Python reference or a real Chrome.

use serde_json::Value;
use std::collections::HashSet;
use std::fs;
use std::path::{Path, PathBuf};

const STATUSES: [&str; 3] = ["not_run", "failed", "passed"];

fn repo_root() -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR")).join("..")
}

fn relative(root: &Path, path: &Path) -> String {
    path.strip_prefix(root).unwrap_or(path).to_string_lossy().to_string().replace('\\', "/")
}

// Python truthiness, so ported rules like `if journey.get("attempt")` keep
// their meaning for strings, arrays and objects.
fn truthy(value: &Value) -> bool {
    match value {
        Value::Null => false,
        Value::Bool(flag) => *flag,
        Value::Number(number) => number.as_f64().is_some_and(|n| n != 0.0),
        Value::String(text) => !text.is_empty(),
        Value::Array(items) => !items.is_empty(),
        Value::Object(fields) => !fields.is_empty(),
    }
}

fn field<'a>(value: &'a Value, name: &str) -> &'a Value {
    value.get(name).unwrap_or(&Value::Null)
}

fn walk_files(dir: &Path, files: &mut Vec<PathBuf>) {
    let Ok(entries) = fs::read_dir(dir) else {
        return;
    };
    for entry in entries.flatten() {
        let path = entry.path();
        if path.is_dir() {
            walk_files(&path, files);
        } else {
            files.push(path);
        }
    }
}

fn validate(root: &Path) -> Vec<String> {
    let manifest = root.join("tests/journeys/journeys.json");
    let data: Value = match fs::read_to_string(&manifest) {
        Ok(text) => match serde_json::from_str(&text) {
            Ok(data) => data,
            Err(error) => return vec![format!("[R0] journeys.json is not valid JSON: {error}")],
        },
        Err(error) => return vec![format!("[R0] cannot read journeys.json: {error}")],
    };
    let mut errors: Vec<String> = Vec::new();
    if field(&data, "target_version") != "1.66.1" {
        errors.push("[R0] target_version must be 1.66.1".to_string());
    }
    let journeys = data.get("journeys").and_then(Value::as_array).cloned().unwrap_or_default();
    if journeys.len() != 10 {
        errors.push(format!("[R1] expected 10 journeys, found {}", journeys.len()));
    }
    let step_count: usize = journeys.iter().map(|journey| journey.get("steps").and_then(Value::as_array).map_or(0, Vec::len)).sum();
    if step_count != 43 {
        errors.push(format!("[R1] expected 43 journey steps, found {step_count}"));
    }
    let artifact_root = root.join(field(&data, "artifact_root").as_str().unwrap_or("tests/e2e"));
    let mut seen_journeys: HashSet<String> = HashSet::new();
    let mut seen_steps: HashSet<String> = HashSet::new();
    for journey in &journeys {
        let id = field(journey, "id").as_str().unwrap_or_default().to_string();
        if !seen_journeys.insert(id.clone()) {
            errors.push(format!("[R1] duplicate journey {id}"));
        }
        let status = field(journey, "status").as_str().unwrap_or_default();
        if !STATUSES.contains(&status) {
            errors.push(format!("[R1] {id}: invalid status {status:?}"));
        }
        let steps = journey.get("steps").and_then(Value::as_array).cloned().unwrap_or_default();
        if steps.is_empty() {
            errors.push(format!("[R1] {id}: no steps"));
        }
        let mut expected: Vec<PathBuf> = Vec::new();
        for step in &steps {
            let step_id = field(step, "id").as_str().unwrap_or_default().to_string();
            if !seen_steps.insert(step_id.clone()) {
                errors.push(format!("[R2] duplicate step {step_id}"));
            }
            if !truthy(field(step, "action")) || !truthy(field(step, "expectation")) {
                errors.push(format!("[R2] {step_id}: action and expectation are required"));
            }
            expected.push(artifact_root.join(&id).join(format!("{step_id}.png")));
            let trace = field(step, "python_reference_trace");
            if truthy(trace) && !root.join(trace.as_str().unwrap_or_default()).is_file() {
                errors.push(format!("[R3] {step_id}: missing Python reference trace {}", trace.as_str().unwrap_or_default()));
            }
        }
        let trace = field(journey, "python_reference_trace");
        if truthy(trace) && !root.join(trace.as_str().unwrap_or_default()).is_file() {
            errors.push(format!("[R3] {id}: missing Python reference trace {}", trace.as_str().unwrap_or_default()));
        }
        let attempt_dir = artifact_root.join(&id);
        let mut present: Vec<String> = Vec::new();
        if attempt_dir.is_dir() {
            let mut files = Vec::new();
            walk_files(&attempt_dir, &mut files);
            present = files.iter().map(|path| relative(root, path)).collect::<Vec<_>>();
            present.sort();
        }
        match status {
            "not_run" => {
                if !present.is_empty() {
                    errors.push(format!("[R6] {id}: not_run has attempt artifacts: {}", present.join(", ")));
                }
                if truthy(field(journey, "attempt")) || truthy(field(journey, "failure")) {
                    errors.push(format!("[R6] {id}: not_run has an attempt/failure record"));
                }
            }
            "failed" => {
                if present.is_empty() && !truthy(field(journey, "attempt")) {
                    errors.push(format!("[R6] {id}: failed journey has neither artifact nor attempt record"));
                }
                if !truthy(field(field(journey, "failure"), "reason")) {
                    errors.push(format!("[R6] {id}: failed journey has no reason"));
                }
                let declared: HashSet<&str> = journey.get("linked_artifacts").and_then(Value::as_array).map(|items| items.iter().filter_map(Value::as_str).collect()).unwrap_or_default();
                let undeclared: Vec<&str> = present.iter().map(String::as_str).filter(|path| !declared.contains(path)).collect();
                if !undeclared.is_empty() {
                    errors.push(format!("[R6] {id}: unlinked attempt artifacts: {}", undeclared.join(", ")));
                }
                let is_waived = |path: &str| {
                    journey
                        .get("waived_evidence")
                        .and_then(Value::as_array)
                        .is_some_and(|entries| entries.iter().any(|entry| field(entry, "artifact").as_str() == Some(path) && truthy(field(entry, "reason"))))
                };
                for path in &expected {
                    let rel = relative(root, path);
                    if !path.is_file() && !is_waived(&rel) {
                        errors.push(format!("[R6] {id}: missing {rel} without reasoned waiver"));
                    }
                }
            }
            "passed" => {
                for path in &expected {
                    if !path.is_file() {
                        errors.push(format!("[R5] {id}: missing {}", relative(root, path)));
                    }
                }
                if !truthy(field(field(journey, "verification"), "method")) {
                    errors.push(format!("[R5] {id}: passed journey has no verification method"));
                }
                if truthy(field(journey, "waived_evidence")) {
                    errors.push(format!("[R5] {id}: passed journey has waivers"));
                }
            }
            _ => {}
        }
    }
    if artifact_root.is_dir() {
        let mut files = Vec::new();
        walk_files(&artifact_root, &mut files);
        for path in files {
            let journey_id = path.strip_prefix(&artifact_root).ok().and_then(|rest| rest.iter().next()).map(|id| id.to_string_lossy().to_string()).unwrap_or_default();
            if !seen_journeys.contains(&journey_id) {
                errors.push(format!("[R6] orphan E2E artifact {}", relative(root, &path)));
            }
        }
    }
    errors
}

#[test]
fn journey_manifest_ledger_is_valid() {
    let errors = validate(&repo_root());
    assert!(errors.is_empty(), "journey ledger violations:\n{}", errors.join("\n"));
}
