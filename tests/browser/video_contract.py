"""The strict video contract: journey-video-v1.

This criterion judges the observation the committed collector
(video_capture.py) writes, against the Python 1.66.1 wire measured on
2026-10-25 with the official frontend and recorded in .codex/compatibility.md
(Media route). The collector states no verdict; this module owns it:

* the page renders one Video element with the exact measured shape: the
  NATIVE type, the relative content-addressed URL and the stretch width
  inside the message (nothing at element level);
* the committed one-second sample is byte-identical across runtimes, so its
  address, the 206 Range response with `content-range: bytes 0-3604/3605`,
  and the served body digest are the exact measured ones;
* the DOM resolves the video through the official frontend with controls and
  no muted/loop/autoplay, no exception renders, and the run finishes
  FINISHED_SUCCESSFULLY.
"""

from __future__ import annotations

import hashlib
import pathlib

VIDEO_CASE = "video-page"
VIDEO_CONTRACT = "journey-video-v1"

VIDEO_STAGES = ["01-load"]

# The exact measured address of the committed sample.
VIDEO_URL = "/media/89d6baf253834c013e2bc52aab2354d4.mp4"
VIDEO_SAMPLE_SHA256 = "dcda48c8cec73a32406a184d635c41a324107f0f51a0cb0fe1124cc0791a19a6"

# The measured Video element.
VIDEO_ELEMENTS = [
 {
  "video": {
   "type": "NATIVE",
   "url": "/media/89d6baf253834c013e2bc52aab2354d4.mp4",
   "widthConfig": {
    "useStretch": True
   }
  }
 }
]

# The measured /media response shape.
VIDEO_HTTP = {
 "status": 206,
 "mime": "video/mp4",
 "content_type": "video/mp4",
 "accept_ranges": "bytes",
 "content_range": "bytes 0-3604/3605",
 "body_sha256": "dcda48c8cec73a32406a184d635c41a324107f0f51a0cb0fe1124cc0791a19a6",
 "body_length": 3605
}

# The DOM projection the official frontend resolves.
VIDEO_DOM = {
 "videos": [
  {
   "src": "<page>/media/89d6baf253834c013e2bc52aab2354d4.mp4",
   "controls": True,
   "muted": False,
   "loop": False,
   "autoplay": False,
   "testid": "stVideo"
  }
 ],
 "exceptions": []
}

# Application paths label the captured roles; source content is not a gate.
VIDEO_SOURCE_FILES = {
    "python": "tests/reference/video_app.py",
    "native": "streamlit/examples/video.rs",
}

VIDEO_REQUIRED = (
    "contract", "stage_set", "video_wire", "exact_address",
    "http_shape", "dom_projection", "no_exceptions", "finishes",
    "png_sources",
)


def _record(checks, name, ok, expected, actual):
    checks.append({"step": VIDEO_CASE, "check": name, "expected": expected, "actual": actual, "ok": bool(ok)})


def _need(condition, message):
    if not condition:
        raise ValueError(message)


def _video_elements(stage):
    out = []
    for frame in stage.get("new_frames") or []:
        delta = (frame.get("summary") or {}).get("delta") or {}
        if delta.get("type") == "new_element":
            out.append(delta.get("element_full"))
    return out


def _http_shape(stage):
    for record in stage.get("http") or []:
        if "/media/" not in record.get("url", ""):
            continue
        headers = record.get("headers") or {}
        body = record.get("body") or {}
        return {
            "status": record.get("status"),
            "mime": record.get("mime"),
            "content_type": headers.get("content-type") or headers.get("Content-Type"),
            "accept_ranges": headers.get("accept-ranges") or headers.get("Accept-Ranges"),
            "content_range": headers.get("content-range") or headers.get("Content-Range"),
            "body_sha256": body.get("sha256"),
            "body_length": body.get("length"),
        }
    return None


def video_checks(*, observation=None):
    import json as _json

    checks = []
    verified = set()

    def mark(name):
        verified.add(name)
        _record(checks, name, True, "the measured 1.66.1 video wire", "contract verified")

    def fail(name, actual):
        _record(checks, name, False, "the measured 1.66.1 video wire", str(actual))

    try:
        _need(isinstance(observation, dict), "observation must be a dict")
        _need(observation.get("journey") == VIDEO_CASE and observation.get("contract") == VIDEO_CONTRACT,
              "missing versioned video contract identity")
        _need(bool(observation.get("scope")) and bool(observation.get("url")), "missing scope/url")
        mark("contract")

        stages = observation.get("stages")
        _need(isinstance(stages, list) and tuple(s.get("name") for s in stages) == tuple(VIDEO_STAGES),
              f"stages must be exactly the {len(VIDEO_STAGES)} measured stages in order")
        for stage in stages:
            _need(isinstance(stage.get("dom"), dict) and isinstance(stage.get("screenshot"), dict)
                  and isinstance(stage.get("new_frames"), list) and isinstance(stage.get("http"), list),
                  f"stage {stage.get('name')} lacks dom/screenshot/new_frames/http")
        mark("stage_set")

        _need(_video_elements(stages[0]) == VIDEO_ELEMENTS, "the Video element differs from the measured wire")
        mark("video_wire")

        media_records = [record for record in stages[0].get("http") or [] if "/media/" in record.get("url", "")]
        _need(len(media_records) == 1, f"the page must make exactly one /media request, saw {len(media_records)}")
        media_record = media_records[0]
        _need(media_record.get("url", "").endswith(VIDEO_URL),
              "the sample must be requested under its exact measured address")
        mark("exact_address")
        shape = _http_shape(stages[0])
        _need(shape and shape.get("body_sha256") == VIDEO_SAMPLE_SHA256,
              "the served body is not the committed sample bytes")
        _need(shape == VIDEO_HTTP, "the /media response shape differs from the measured table")
        mark("http_shape")

        page = (observation.get("url") or "").rstrip("/")
        dom_text = _json.dumps({key: (stages[0]["dom"] or {}).get(key) for key in ("videos", "exceptions")}, ensure_ascii=False)
        dom_text = dom_text.replace(page, "<page>")
        _need(_json.loads(dom_text) == VIDEO_DOM, "the resolved DOM projection differs from the measured page")
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
        for name in VIDEO_REQUIRED:
            if name not in verified:
                fail(name, str(exc))
        return checks
    return checks


def video_result(*, observation=None):
    """Aggregate the contract checks the way the shared journey judge does."""
    checks = video_checks(observation=observation)
    failures = [check for check in checks if not check["ok"]]
    return {
        "checks": checks,
        "counts": {"expected": len(checks), "executed": len(checks), "asserted": len(checks) - len(failures)},
        "failures": failures,
        "ok": not failures and len(checks) == len(VIDEO_REQUIRED),
    }
