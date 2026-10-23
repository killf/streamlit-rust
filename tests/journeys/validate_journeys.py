#!/usr/bin/env python3
"""Validate the compact Rust E2E journey manifest."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "tests/journeys/journeys.json"
STATUSES = {"not_run", "failed", "passed"}


def fail(errors: list[str], rule: str, message: str) -> None:
    errors.append(f"[{rule}] {message}")


def validate() -> list[str]:
    errors: list[str] = []
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if data.get("target_version") != "1.66.1":
        fail(errors, "R0", "target_version must be 1.66.1")
    journeys = data.get("journeys", [])
    if len(journeys) != 10:
        fail(errors, "R1", f"expected 10 journeys, found {len(journeys)}")
    if sum(len(journey.get("steps", [])) for journey in journeys) != 42:
        fail(errors, "R1", "expected 42 journey steps")
    root = ROOT / data.get("artifact_root", "tests/e2e")
    seen_journeys: set[str] = set()
    seen_steps: set[str] = set()
    for journey in journeys:
        jid = journey.get("id", "")
        if jid in seen_journeys:
            fail(errors, "R1", f"duplicate journey {jid}")
        seen_journeys.add(jid)
        status = journey.get("status")
        if status not in STATUSES:
            fail(errors, "R1", f"{jid}: invalid status {status!r}")
        steps = journey.get("steps", [])
        if not steps:
            fail(errors, "R1", f"{jid}: no steps")
        expected: list[Path] = []
        for step in steps:
            sid = step.get("id", "")
            if sid in seen_steps:
                fail(errors, "R2", f"duplicate step {sid}")
            seen_steps.add(sid)
            if not step.get("action") or not step.get("expectation"):
                fail(errors, "R2", f"{sid}: action and expectation are required")
            expected.append(root / jid / f"{sid}.png")
        reference = journey.get("python_reference_trace")
        if reference and not (ROOT / reference).is_file():
            fail(errors, "R3", f"{jid}: missing Python reference trace {reference}")
        for step in steps:
            step_reference = step.get("python_reference_trace")
            if step_reference and not (ROOT / step_reference).is_file():
                fail(
                    errors,
                    "R3",
                    f"{step.get('id')}: missing Python reference trace {step_reference}",
                )
        attempt_dir = root / jid
        present = sorted(path.relative_to(ROOT).as_posix() for path in attempt_dir.rglob("*") if path.is_file()) if attempt_dir.is_dir() else []
        if status == "not_run":
            if present:
                fail(errors, "R6", f"{jid}: not_run has attempt artifacts: {', '.join(present)}")
            if journey.get("attempt") or journey.get("failure"):
                fail(errors, "R6", f"{jid}: not_run has an attempt/failure record")
        elif status == "failed":
            failure = journey.get("failure") or {}
            if not present and not journey.get("attempt"):
                fail(errors, "R6", f"{jid}: failed journey has neither artifact nor attempt record")
            if not failure.get("reason"):
                fail(errors, "R6", f"{jid}: failed journey has no reason")
            declared = set(journey.get("linked_artifacts", []))
            undeclared = [path for path in present if path not in declared]
            if undeclared:
                fail(errors, "R6", f"{jid}: unlinked attempt artifacts: {', '.join(undeclared)}")
            waived = {entry.get("artifact"): entry for entry in journey.get("waived_evidence", [])}
            for path in expected:
                relative = path.relative_to(ROOT).as_posix()
                if not path.is_file() and (relative not in waived or not waived[relative].get("reason")):
                    fail(errors, "R6", f"{jid}: missing {relative} without reasoned waiver")
        elif status == "passed":
            verification = journey.get("verification") or {}
            for path in expected:
                if not path.is_file():
                    fail(errors, "R5", f"{jid}: missing {path.relative_to(ROOT)}")
            if not verification.get("method"):
                fail(errors, "R5", f"{jid}: passed journey has no verification method")
            if journey.get("waived_evidence"):
                fail(errors, "R5", f"{jid}: passed journey has waivers")
    for path in root.rglob("*") if root.is_dir() else []:
        if path.is_file():
            journey_id = path.relative_to(root).parts[0]
            if journey_id not in seen_journeys:
                fail(errors, "R6", f"orphan E2E artifact {path.relative_to(ROOT)}")
    return errors


def main() -> int:
    errors = validate()
    if not errors:
        print("10 journeys / 42 steps valid; failed partials retain evidence; no false pass")
        return 0
    for error in errors:
        print(error)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())