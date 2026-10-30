"""The strict media-route contract: journey-media-v1.

This criterion judges the observation the committed collector
(media_capture.py) writes, against the Python 1.66.1 wire measured on
2026-10-25 with the official frontend and recorded in .codex/compatibility.md
(Media route). The collector states no verdict; this module owns it:

* the page renders five elements with the exact measured shapes: the image
  list with a relative content-addressed URL and a content width, the audio
  element stretching inside its message, two metrics deriving direction and
  color from the delta sign, and the progress bar streaming one final-value
  delta (the reference's same-tick flush coalesces 50-then-75 into 75);
* the WAV is byte-identical across runtimes, so its address, range response
  and body digest are the exact measured ones; the PNG encodes per side
  (the reference deflates with PIL), so its address and body length ride
  the per-side encoding and only the response shape compares;
* GET /media/{file_id}.{ext} answers 200 with `accept-ranges: bytes` and the
  typed content type, and the browser's open-ended Range request answers
  206 with the measured `content-range`;
* the served PNG is decoded with an independent decoder (PIL) and its
  pixels equal the measured gradient: the per-side encoders differ, the
  rendered image does not;
* the DOM resolves both media URLs through the official frontend, both
  metrics read back their measured label/value/delta, the progressbar holds
  aria-valuenow 75, no exception renders, and the run finishes
  FINISHED_SUCCESSFULLY.
"""

from __future__ import annotations

import hashlib
import pathlib

MEDIA_CASE = "media-page"
MEDIA_CONTRACT = "journey-media-v1"

MEDIA_STAGES = ["01-load"]

# The exact measured address of the byte-identical WAV fixture.
MEDIA_WAV_URL = "/media/431dec53348c010fe7c4e0be3ac78ede.wav"

# The five first-render elements in stream order, media ids normalized per
# the contract above.
MEDIA_ELEMENTS = [
 {
  "imgs": {
   "imgs": [
    {
     "caption": "gradient",
     "url": "/media/<id>.png"
    }
   ]
  },
  "widthConfig": {
   "useContent": True
  }
 },
 {
  "audio": {
   "url": "/media/431dec53348c010fe7c4e0be3ac78ede.wav",
   "widthConfig": {
    "useStretch": True
   }
  }
 },
 {
  "metric": {
   "label": "Temperature",
   "body": "72 °F",
   "delta": "2 °F",
   "direction": "UP",
   "color": "GREEN",
   "labelVisibility": {}
  },
  "heightConfig": {
   "useContent": True
  },
  "widthConfig": {
   "useStretch": True
  }
 },
 {
  "metric": {
   "label": "Wind",
   "body": "8 mph",
   "delta": "-3 mph",
   "color": "GREEN",
   "labelVisibility": {}
  },
  "heightConfig": {
   "useContent": True
  },
  "widthConfig": {
   "useStretch": True
  }
 },
 {
  "progress": {
   "value": 75
  },
  "widthConfig": {
   "useStretch": True
  }
 }
]

# The measured /media response shapes, sorted by path.
MEDIA_HTTP = [
 {
  "path": "/media/431dec53348c010fe7c4e0be3ac78ede.wav",
  "status": 206,
  "mime": "audio/wav",
  "content_type": "audio/wav",
  "accept_ranges": "bytes",
  "content_range": "bytes 0-22093/22094",
  "body_sha256": "369b43b692e118c4a54b0a90c787bed3988ba4c94a8a68554268276d945436d2",
  "body_length": 22094
 },
 {
  "path": "/media/<id>.png",
  "status": 200,
  "mime": "image/png",
  "content_type": "image/png",
  "accept_ranges": "bytes",
  "content_range": None,
  "body_png": True
 }
]

# The DOM projection the official frontend resolves: media src (normalized),
# metric label/value/delta, progressbar aria value, exceptions.
MEDIA_DOM = {
 "images": [
  {
   "src": "<page>/media/<id>.png",
   "alt": None,
   "width": None,
   "testid": "stImageContainer"
  }
 ],
 "audios": [
  {
   "src": "<page>/media/431dec53348c010fe7c4e0be3ac78ede.wav",
   "controls": True
  }
 ],
 "metrics": [
  {
   "label": "Temperature",
   "value": "72 °F",
   "delta": "2 °F",
   "delta_class": "st-emotion-cache-18iyadg e3lvb7d5"
  },
  {
   "label": "Wind",
   "value": "8 mph",
   "delta": "-3 mph",
   "delta_class": "st-emotion-cache-18iyadg e3lvb7d5"
  }
 ],
 "progress": [
  {
   "testid": "stProgress",
   "role": None,
   "value": None,
   "text": ""
  },
  {
   "testid": None,
   "role": "progressbar",
   "value": "75",
   "text": ""
  }
 ],
 "exceptions": []
}

# The decoded pixels and size of the served PNG, read with an independent
# decoder (PIL): the per-side encoders differ, the rendered gradient does not.
MEDIA_PNG_SIZE = [
 8,
 8
]
MEDIA_PNG_PIXELS = [
 [
  [
   0,
   4,
   8,
   255
  ],
  [
   16,
   20,
   24,
   255
  ],
  [
   32,
   36,
   40,
   255
  ],
  [
   48,
   52,
   56,
   255
  ],
  [
   64,
   68,
   72,
   255
  ],
  [
   80,
   84,
   88,
   255
  ],
  [
   96,
   100,
   104,
   255
  ],
  [
   112,
   116,
   120,
   255
  ]
 ],
 [
  [
   128,
   132,
   136,
   255
  ],
  [
   144,
   148,
   152,
   255
  ],
  [
   160,
   164,
   168,
   255
  ],
  [
   176,
   180,
   184,
   255
  ],
  [
   192,
   196,
   200,
   255
  ],
  [
   208,
   212,
   216,
   255
  ],
  [
   224,
   228,
   232,
   255
  ],
  [
   240,
   244,
   248,
   255
  ]
 ],
 [
  [
   0,
   4,
   8,
   255
  ],
  [
   16,
   20,
   24,
   255
  ],
  [
   32,
   36,
   40,
   255
  ],
  [
   48,
   52,
   56,
   255
  ],
  [
   64,
   68,
   72,
   255
  ],
  [
   80,
   84,
   88,
   255
  ],
  [
   96,
   100,
   104,
   255
  ],
  [
   112,
   116,
   120,
   255
  ]
 ],
 [
  [
   128,
   132,
   136,
   255
  ],
  [
   144,
   148,
   152,
   255
  ],
  [
   160,
   164,
   168,
   255
  ],
  [
   176,
   180,
   184,
   255
  ],
  [
   192,
   196,
   200,
   255
  ],
  [
   208,
   212,
   216,
   255
  ],
  [
   224,
   228,
   232,
   255
  ],
  [
   240,
   244,
   248,
   255
  ]
 ],
 [
  [
   0,
   4,
   8,
   255
  ],
  [
   16,
   20,
   24,
   255
  ],
  [
   32,
   36,
   40,
   255
  ],
  [
   48,
   52,
   56,
   255
  ],
  [
   64,
   68,
   72,
   255
  ],
  [
   80,
   84,
   88,
   255
  ],
  [
   96,
   100,
   104,
   255
  ],
  [
   112,
   116,
   120,
   255
  ]
 ],
 [
  [
   128,
   132,
   136,
   255
  ],
  [
   144,
   148,
   152,
   255
  ],
  [
   160,
   164,
   168,
   255
  ],
  [
   176,
   180,
   184,
   255
  ],
  [
   192,
   196,
   200,
   255
  ],
  [
   208,
   212,
   216,
   255
  ],
  [
   224,
   228,
   232,
   255
  ],
  [
   240,
   244,
   248,
   255
  ]
 ],
 [
  [
   0,
   4,
   8,
   255
  ],
  [
   16,
   20,
   24,
   255
  ],
  [
   32,
   36,
   40,
   255
  ],
  [
   48,
   52,
   56,
   255
  ],
  [
   64,
   68,
   72,
   255
  ],
  [
   80,
   84,
   88,
   255
  ],
  [
   96,
   100,
   104,
   255
  ],
  [
   112,
   116,
   120,
   255
  ]
 ],
 [
  [
   128,
   132,
   136,
   255
  ],
  [
   144,
   148,
   152,
   255
  ],
  [
   160,
   164,
   168,
   255
  ],
  [
   176,
   180,
   184,
   255
  ],
  [
   192,
   196,
   200,
   255
  ],
  [
   208,
   212,
   216,
   255
  ],
  [
   224,
   228,
   232,
   255
  ],
  [
   240,
   244,
   248,
   255
  ]
 ]
]

# Application paths label the captured roles; source content is not a gate.
MEDIA_SOURCE_FILES = {
    "python": "tests/reference/media_app.py",
    "native": "streamlit/examples/media.rs",
}

MEDIA_REQUIRED = (
    "contract", "stage_set", "element_wires", "wav_address",
    "http_shapes", "png_pixels", "dom_projection", "no_exceptions",
    "finishes", "png_sources",
)


def _record(checks, name, ok, expected, actual):
    checks.append({"step": MEDIA_CASE, "check": name, "expected": expected, "actual": actual, "ok": bool(ok)})


def _need(condition, message):
    if not condition:
        raise ValueError(message)


def _element_wires(stage):
    out = []
    for frame in stage.get("new_frames") or []:
        delta = (frame.get("summary") or {}).get("delta") or {}
        if delta.get("type") == "new_element":
            out.append(delta.get("element_full"))
    return out


def _http_shapes(stage):
    import re

    out = []
    for record in stage.get("http") or []:
        url = record.get("url", "")
        if "/media/" not in url:
            continue
        headers = record.get("headers") or {}
        entry = {
            "path": re.sub(r"^.*?/media/", "/media/", url),
            "status": record.get("status"),
            "mime": record.get("mime"),
            "content_type": headers.get("content-type") or headers.get("Content-Type"),
            "accept_ranges": headers.get("accept-ranges") or headers.get("Accept-Ranges"),
            "content_range": headers.get("content-range") or headers.get("Content-Range"),
        }
        body = record.get("body") or {}
        if entry["path"].endswith(".wav"):
            entry["body_sha256"] = body.get("sha256")
            entry["body_length"] = body.get("length")
        else:
            entry["path"] = re.sub(r"[0-9a-f]{32}", "<id>", entry["path"])
            entry["body_png"] = bool(body.get("length"))
        out.append(entry)
    out.sort(key=lambda entry: entry["path"])
    return out


def media_checks(*, observation=None):
    import json as _json
    import re as _re

    checks = []
    verified = set()

    def mark(name):
        verified.add(name)
        _record(checks, name, True, "the measured 1.66.1 media wire", "contract verified")

    def fail(name, actual):
        _record(checks, name, False, "the measured 1.66.1 media wire", str(actual))

    def normalize(text):
        def replace(match):
            if match.group(1) == "wav":
                return MEDIA_WAV_URL
            return "/media/<id>." + match.group(1)
        return _re.sub(r"/media/[0-9a-f]{32}\.([a-z0-9]+)", replace, text)

    try:
        _need(isinstance(observation, dict), "observation must be a dict")
        _need(observation.get("journey") == MEDIA_CASE and observation.get("contract") == MEDIA_CONTRACT,
              "missing versioned media contract identity")
        _need(bool(observation.get("scope")) and bool(observation.get("url")), "missing scope/url")
        mark("contract")

        stages = observation.get("stages")
        _need(isinstance(stages, list) and tuple(s.get("name") for s in stages) == tuple(MEDIA_STAGES),
              f"stages must be exactly the {len(MEDIA_STAGES)} measured stages in order")
        for stage in stages:
            _need(isinstance(stage.get("dom"), dict) and isinstance(stage.get("screenshot"), dict)
                  and isinstance(stage.get("new_frames"), list) and isinstance(stage.get("http"), list),
                  f"stage {stage.get('name')} lacks dom/screenshot/new_frames/http")
        mark("stage_set")

        wires = [_json.loads(normalize(_json.dumps(element, ensure_ascii=False))) for element in _element_wires(stages[0])]
        _need(wires == MEDIA_ELEMENTS, "the five element wires differ from the measured page")
        mark("element_wires")

        wav_urls = [entry for entry in _http_shapes(stages[0]) if entry["path"].endswith(".wav")]
        _need(len(wav_urls) == 1 and wav_urls[0]["path"] == MEDIA_WAV_URL
              and wav_urls[0]["body_sha256"] and wav_urls[0]["body_length"] == 22094,
              "the byte-identical WAV must be served under its exact measured address")
        mark("wav_address")

        _need(_http_shapes(stages[0]) == MEDIA_HTTP, "the /media response shapes differ from the measured table")
        mark("http_shapes")

        png_records = [record for record in stages[0].get("http") or [] if record.get("mime") == "image/png"]
        _need(len(png_records) == 1 and (png_records[0].get("body") or {}).get("data_b64"),
              "the trace must carry the served PNG bytes")
        if png_records and (png_records[0].get("body") or {}).get("data_b64"):
            import base64 as _base64
            import io as _io

            from PIL import Image

            image = Image.open(_io.BytesIO(_base64.b64decode(png_records[0]["body"]["data_b64"]))).convert("RGBA")
            _need(list(image.size) == MEDIA_PNG_SIZE, f"the served PNG decodes to {image.size}, not the measured {MEDIA_PNG_SIZE}")
            bitmap = image.load()
            pixels = [[[int(channel) for channel in bitmap[column, row]] for column in range(image.size[0])] for row in range(image.size[1])]
            _need(pixels == MEDIA_PNG_PIXELS, "the decoded PNG pixels differ from the measured gradient")
        mark("png_pixels")

        page = (observation.get("url") or "").rstrip("/")
        dom_text = _json.dumps({key: (stages[0]["dom"] or {}).get(key) for key in ("images", "audios", "metrics", "progress", "exceptions")}, ensure_ascii=False)
        dom_text = dom_text.replace(page, "<page>")
        _need(_json.loads(normalize(dom_text)) == MEDIA_DOM, "the resolved DOM projection differs from the measured page")
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
        for name in MEDIA_REQUIRED:
            if name not in verified:
                fail(name, str(exc))
        return checks
    return checks


def media_result(*, observation=None):
    """Aggregate the contract checks the way the shared journey judge does."""
    checks = media_checks(observation=observation)
    failures = [check for check in checks if not check["ok"]]
    return {
        "checks": checks,
        "counts": {"expected": len(checks), "executed": len(checks), "asserted": len(checks) - len(failures)},
        "failures": failures,
        "ok": not failures and len(checks) == len(MEDIA_REQUIRED),
    }
