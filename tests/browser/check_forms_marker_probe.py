"""Check the real DOM selector and marker parsing using only local HTML."""
from __future__ import annotations

import argparse
import json
import re
import time

import forms_capture as capture
from forms_contract import _marker


def typed_markers(dom: dict) -> dict:
    values = {}
    for name, prefix in (("script_runs", "Script runs:"), ("pulses", "Pulses:"),
                         ("applied_note", "Applied note:")):
        matches = [text for text in dom["texts"] if text.startswith(prefix)]
        if len(matches) != 1:
            raise ValueError(f"{prefix}: expected one actual marker, observed {len(matches)}")
        value = _marker(dom, prefix)
        if value is None:
            raise ValueError(f"{prefix}: actual marker missing")
        if name != "applied_note":
            if re.fullmatch(r"0|[1-9][0-9]*", value) is None:
                raise ValueError(f"{prefix}: actual value is not a nonnegative integer")
            value = int(value)
        values[name] = value
    return values


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    output = capture.ROOT / args.out
    output.mkdir(parents=True, exist_ok=False)
    fixture = capture.ROOT / "tests/browser/forms_marker_fixture.html"
    profile = capture.ROOT / "target/forms-capture/chrome-profile"
    chrome = capture.start_chrome(capture.chrome_binary(), 60917, profile)
    recorder = None
    observations = []
    try:
        target = next(t for t in capture.page_targets(60917) if t.get("type") == "page")
        recorder = capture.CDP(target["webSocketDebuggerUrl"], label="forms-marker-fixture")
        recorder.start()
        page = capture.FormsPage(recorder)
        navigation = capture.agent_browser(
            "open", fixture.as_uri(), session="forms-marker-regression",
            profile=profile, cdp_port=60917,
        )
        for variant in ("valid", "missing-runs", "missing-pulses", "missing-applied",
                        "invalid-number", "wrong-prefix", "duplicate-root"):
            recorder.call("Page.navigate", {"url": fixture.as_uri() + "?variant=" + variant})
            time.sleep(0.2)
            dom = page.dom()
            if not isinstance(dom, dict):
                raise AssertionError("real DOM observation is missing")
            observation = {"variant": variant, "dom": dom}
            try:
                observation["typed"] = typed_markers(dom)
            except ValueError as error:
                observation["rejection"] = str(error)
            observations.append(observation)
        report = {"navigation": navigation, "observations": observations}
        (output / "observations.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        valid = observations[0]
        assert valid["dom"]["texts"] == ["Script runs: 1", "Pulses: 0", "Applied note:"]
        assert valid["typed"] == {"script_runs": 1, "pulses": 0, "applied_note": ""}
        for observation in observations[1:]:
            assert "rejection" in observation, observation["variant"]
        print(json.dumps([{k: v for k, v in o.items() if k != "dom"} for o in observations]))
    finally:
        if recorder is not None:
            recorder.stop()
        chrome.terminate()


if __name__ == "__main__":
    main()
