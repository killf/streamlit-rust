"""The strict page-config contract: journey-pageconfig-v1.

This criterion judges the observation the committed collector
(pageconfig_capture.py) writes, against the Python 1.66.1 wire measured on
2026-10-26 with the official frontend and recorded in .codex/compatibility.md
(Page config). The collector states no verdict; this module owns it:

* exactly one page_config_changed ForwardMsg streams between the running
  status and the first delta, carrying the measured title, icon, WIDE
  layout, EXPANDED sidebar state and the three menu entries;
* the only element delta is the write at [0, 0] (an optional leading
  main-container block at [0] is the Rust runtime's documented divergence);
* the settled DOM shows the configured document title, the frontend-resolved
  Material-symbols favicon, the streamlit-wide root class and no exception,
  and the run finishes FINISHED_SUCCESSFULLY.
"""

from __future__ import annotations

import hashlib
import json
import pathlib
import re

PAGECONFIG_CASE = "pageconfig-page"
PAGECONFIG_CONTRACT = "journey-pageconfig-v1"

PAGECONFIG_STAGES = ["01-load"]

# The measured page_config_changed payload.
PAGECONFIG_FIELDS = {
    'title': 'Wide demo',
    'favicon': ':material/check_circle:',
    'layout': 'WIDE',
    'initialSidebarState': 'EXPANDED',
    'menuItems': {
        'getHelpUrl': 'https://docs.streamlit.io/',
        'reportABugUrl': 'https://github.com/streamlit/streamlit/issues',
        'aboutSectionMd': '### About text\nCreated with the reference fixture.'
    }
}

# The DOM projection the official frontend resolves, embedding id normalized.
PAGECONFIG_DOM = {
    'title': 'Wide demo',
    'favicons': [
        'shortcut icon https://fonts.gstatic.com/s/i/short-term/release/materialsymbolsrounded/check_circle/default/24px.svg'
    ],
    'wideClasses': [
        'DIV.stApp stAppEmbeddingId-<id> streamlit-wide st-emotion-cache-13k62yr e1vju3fw0'
    ],
    'mainClass': None,
    'appClasses': [
        'stAppViewContainer stAppViewContainer appview-container st-emotion-cache-1yiq2ps e87roqt0',
        'stMain stMain st-emotion-cache-170etyg e87roqt2'
    ],
    'sidebarExpanded': 0,
    'menuItems': [],
    'markdowns': [
        'configured'
    ],
    'exceptions': []
}

PAGECONFIG_SOURCE_FILES = {
    "python": "tests/reference/pageconfig_app.py",
    "native": "streamlit/examples/pageconfig.rs",
}

PAGECONFIG_REQUIRED = (
    "contract", "stage_set", "config_wire",
    "stream_shape", "dom_projection", "no_exceptions", "finishes",
    "png_sources",
)

_EMBED_ID = re.compile(r"stAppEmbeddingId-[a-z0-9]+")


def _record(checks, name, ok, expected, actual):
    checks.append({"step": PAGECONFIG_CASE, "check": name, "expected": expected, "actual": actual, "ok": bool(ok)})


def _need(condition, message):
    if not condition:
        raise ValueError(message)


def _stream(stage):
    """(kind, detail) of every config/delta frame, the optional leading main
    container block peeled off (the Rust side emits exactly one, the
    reference none)."""
    out = []
    stripped = 0
    for frame in stage.get("new_frames") or []:
        summary = frame.get("summary") or {}
        kind = summary.get("type")
        if kind == "delta":
            delta = summary.get("delta") or {}
            inner = delta.get("type")
            _need(inner in ("new_transient", "new_element", "add_block"), f"unexpected delta kind {inner!r}")
            if inner == "add_block" and (delta.get("path") or None) == [0] and (delta.get("block") or {}).get("id") == "main_container":
                stripped += 1
                _need(stripped <= 1, "more than one leading main-container block")
                continue
            out.append(("delta", {key: delta.get(key) for key in ("type", "path", "element", "body")}))
        elif kind == "page_config_changed":
            out.append(("page_config_changed", summary.get("page_config")))
        elif kind in ("new_session", "session_status_changed", "script_finished"):
            out.append((kind, None))
    return out


def pageconfig_checks(*, observation=None):
    checks = []
    verified = set()

    def mark(name):
        verified.add(name)
        _record(checks, name, True, "the measured 1.66.1 page-config wire", "contract verified")

    def fail(name, actual):
        _record(checks, name, False, "the measured 1.66.1 page-config wire", str(actual))

    try:
        _need(isinstance(observation, dict), "observation must be a dict")
        _need(observation.get("journey") == PAGECONFIG_CASE and observation.get("contract") == PAGECONFIG_CONTRACT,
              "missing versioned page-config contract identity")
        _need(bool(observation.get("scope")) and bool(observation.get("url")), "missing scope/url")
        mark("contract")

        stages = observation.get("stages")
        _need(isinstance(stages, list) and tuple(s.get("name") for s in stages) == tuple(PAGECONFIG_STAGES),
              f"stages must be exactly the {len(PAGECONFIG_STAGES)} measured stages in order")
        for stage in stages:
            _need(isinstance(stage.get("dom"), dict) and isinstance(stage.get("screenshot"), dict)
                  and isinstance(stage.get("new_frames"), list), f"stage {stage.get('name')} lacks dom/screenshot/new_frames")
        mark("stage_set")

        stream = _stream(stages[0])
        configs = [detail for kind, detail in stream if kind == "page_config_changed"]
        _need(len(configs) == 1, f"exactly one page_config_changed must stream, got {len(configs)}")
        _need(configs[0] == PAGECONFIG_FIELDS,
              f"the page config differs from the measured wire: {configs[0]}")
        first_delta = next(index for index, (kind, _) in enumerate(stream) if kind == "delta")
        config_at = next(index for index, (kind, _) in enumerate(stream) if kind == "page_config_changed")
        _need(config_at < first_delta, "the page config must stream before the first delta")
        running = [index for index, (kind, _) in enumerate(stream) if kind == "session_status_changed"]
        _need(any(index < config_at for index in running), "the page config must follow the running status")
        mark("config_wire")

        deltas = [detail for kind, detail in stream if kind == "delta"]
        _need(deltas == [{"type": "new_element", "path": [0, 0], "element": "markdown", "body": "configured"}],
              f"the element stream differs from the measured single write at [0, 0]: {deltas}")
        mark("stream_shape")

        page = (observation.get("url") or "").rstrip("/")
        dom_text = json.dumps(stages[0]["dom"], ensure_ascii=False)
        dom_text = dom_text.replace(page, "<page>")
        dom = json.loads(_EMBED_ID.sub("stAppEmbeddingId-<id>", dom_text))
        _need({key: dom.get(key) for key in PAGECONFIG_DOM} == PAGECONFIG_DOM,
              "the resolved DOM projection differs from the measured page")
        mark("dom_projection")

        _need(not ((stages[0]["dom"] or {}).get("exceptions") or []), "the page renders an exception")
        for frame in stages[0]["new_frames"]:
            delta = (frame.get("summary") or {}).get("delta") or {}
            _need(delta.get("element") != "exception", "the stream carries an exception element")
        mark("no_exceptions")

        finishes = [((frame.get("summary") or {}).get("script_finished") or {}).get("status")
                    for frame in stages[0]["new_frames"]
                    if (frame.get("summary") or {}).get("type") == "script_finished"]
        _need(finishes == [0], "the run must finish exactly once with FINISHED_SUCCESSFULLY")
        mark("finishes")

        root = pathlib.Path(observation.get("ipc_dir", ".")).resolve()
        for stage in stages:
            record = stage.get("screenshot") or {}
            _need(not pathlib.Path(record.get("file", "")).is_absolute(), "screenshot path must be relative")
            png = (root / record.get("file", "")).resolve()
            _need(png.is_relative_to(root) and png.is_file(), f"missing stage PNG {record.get('file')}")
            data = png.read_bytes()
            _need(data.startswith(b"\x89PNG\r\n\x1a\n") and hashlib.sha256(data).hexdigest() == record.get("sha256"),
                  f"stage PNG sha/magic mismatch for {record.get('file')}")
        mark("png_sources")
    except (ValueError, TypeError, KeyError, IndexError, OSError, AttributeError, StopIteration) as exc:
        for name in PAGECONFIG_REQUIRED:
            if name not in verified:
                fail(name, str(exc))
        return checks
    return checks


def pageconfig_result(*, observation=None):
    """Aggregate the contract checks the way the shared journey judge does."""
    checks = pageconfig_checks(observation=observation)
    failures = [check for check in checks if not check["ok"]]
    return {
        "checks": checks,
        "counts": {"expected": len(checks), "executed": len(checks), "asserted": len(checks) - len(failures)},
        "failures": failures,
        "ok": not failures and len(checks) == len(PAGECONFIG_REQUIRED),
    }
