"""The strict picker-input contract: journey-pickers-v1.

This criterion judges the observation the committed collector
(pickers_capture.py) writes, against the Python 1.66.1 wire measured on
2026-10-26 with the official frontend and recorded in .codex/compatibility.md
(Picker inputs). The collector states no verdict; this module owns it:

* st.date_input carries its ISO defaults, the ten-year min/max window
  anchored on the value (each range endpoint its own side), isRange for a
  two-endpoint value and the "YYYY/MM/DD" display format;
* st.time_input carries the "HH:MM" default (whole-minute steps), the step
  seconds and the "24h" format;
* st.color_picker carries its "#RRGGBB" default;
* st.select_slider is a slider element with the SELECT_SLIDER type, the
  "%s" format, option-label indices (0..len-1, step 1, INT) and index
  defaults (the first option when unset);
* st.audio_input / st.camera_input carry label/visibility, audio adding
  the 16000 Hz sample rate; both report single-file uploader states;
* the committed slider interaction reports the measured label states
  ("medium" then "high") while every other widget echoes its state.

Widget ids are judged modulo the $$ID digest segment; the browser's
widget-state serialization order is normalized; at most one leading
main-container add_block at [0] is the Rust runtime's documented
divergence.
"""

from __future__ import annotations

import hashlib
import json
import pathlib
import re

PICKERS_CASE = "pickers-page"
PICKERS_CONTRACT = "journey-pickers-v1"

PICKERS_STAGES = [
    '01-load',
    '02-slider'
]

PICKERS_TIMELINE = {
    '01-load': [
        {
            'kind': 'rerun',
            'states': []
        },
        {
            'kind': 'new_session'
        },
        {
            'kind': 'session_status_changed'
        },
        {
            'kind': 'date_input',
            'widget': {
                'label': 'Start date',
                'default': [
                    '2025-01-15'
                ],
                'min': '2015-01-15',
                'max': '2035-01-15',
                'labelVisibility': {},
                'format': 'YYYY/MM/DD'
            },
            'path': [
                0,
                0
            ]
        },
        {
            'kind': 'date_input',
            'widget': {
                'label': 'Window',
                'default': [
                    '2025-01-15',
                    '2025-02-15'
                ],
                'min': '2015-01-15',
                'max': '2035-02-15',
                'isRange': True,
                'labelVisibility': {},
                'format': 'YYYY/MM/DD'
            },
            'path': [
                0,
                1
            ]
        },
        {
            'kind': 'time_input',
            'widget': {
                'label': 'Meeting',
                'default': '14:30',
                'labelVisibility': {},
                'step': '900',
                'format': '24h'
            },
            'path': [
                0,
                2
            ]
        },
        {
            'kind': 'color_picker',
            'widget': {
                'label': 'Accent',
                'default': '#FF5733',
                'labelVisibility': {}
            },
            'path': [
                0,
                3
            ]
        },
        {
            'kind': 'slider',
            'widget': {
                'label': 'Pick one',
                'format': '%s',
                'default': [
                    0.0
                ],
                'max': 2.0,
                'step': 1.0,
                'options': [
                    'low',
                    'medium',
                    'high'
                ],
                'labelVisibility': {},
                'type': 'SELECT_SLIDER'
            },
            'path': [
                0,
                4
            ]
        },
        {
            'kind': 'slider',
            'widget': {
                'label': 'Pick range',
                'format': '%s',
                'default': [
                    1.0,
                    3.0
                ],
                'max': 3.0,
                'step': 1.0,
                'options': [
                    'a',
                    'b',
                    'c',
                    'd'
                ],
                'labelVisibility': {},
                'type': 'SELECT_SLIDER'
            },
            'path': [
                0,
                5
            ]
        },
        {
            'kind': 'audio_input',
            'widget': {
                'label': 'Voice note',
                'labelVisibility': {},
                'sampleRate': 16000
            },
            'path': [
                0,
                6
            ]
        },
        {
            'kind': 'camera_input',
            'widget': {
                'label': 'Snapshot',
                'labelVisibility': {}
            },
            'path': [
                0,
                7
            ]
        },
        {
            'kind': 'script_finished'
        },
        {
            'kind': 'session_status_changed'
        }
    ],
    '02-slider': [
        {
            'kind': 'rerun',
            'states': [
                {
                    'id': '$$ID-accent',
                    'value_field': 'string_value',
                    'value': '#FF5733'
                },
                {
                    'id': '$$ID-meeting',
                    'value_field': 'string_value',
                    'value': '14:30'
                },
                {
                    'id': '$$ID-one',
                    'value_field': 'string_array_value',
                    'value': {
                        'data': "['medium']"
                    }
                },
                {
                    'id': '$$ID-range',
                    'value_field': 'string_array_value',
                    'value': {
                        'data': "['b', 'd']"
                    }
                },
                {
                    'id': '$$ID-shot',
                    'value_field': 'file_uploader_state_value',
                    'value': {}
                },
                {
                    'id': '$$ID-start',
                    'value_field': 'string_array_value',
                    'value': {
                        'data': "['2025-01-15']"
                    }
                },
                {
                    'id': '$$ID-window',
                    'value_field': 'string_array_value',
                    'value': {
                        'data': "['2025-01-15', '2025-02-15']"
                    }
                }
            ]
        },
        {
            'kind': 'new_session'
        },
        {
            'kind': 'session_status_changed'
        },
        {
            'kind': 'date_input',
            'widget': {
                'label': 'Start date',
                'default': [
                    '2025-01-15'
                ],
                'min': '2015-01-15',
                'max': '2035-01-15',
                'labelVisibility': {},
                'format': 'YYYY/MM/DD'
            },
            'path': [
                0,
                0
            ]
        },
        {
            'kind': 'date_input',
            'widget': {
                'label': 'Window',
                'default': [
                    '2025-01-15',
                    '2025-02-15'
                ],
                'min': '2015-01-15',
                'max': '2035-02-15',
                'isRange': True,
                'labelVisibility': {},
                'format': 'YYYY/MM/DD'
            },
            'path': [
                0,
                1
            ]
        },
        {
            'kind': 'time_input',
            'widget': {
                'label': 'Meeting',
                'default': '14:30',
                'labelVisibility': {},
                'step': '900',
                'format': '24h'
            },
            'path': [
                0,
                2
            ]
        },
        {
            'kind': 'color_picker',
            'widget': {
                'label': 'Accent',
                'default': '#FF5733',
                'labelVisibility': {}
            },
            'path': [
                0,
                3
            ]
        },
        {
            'kind': 'slider',
            'widget': {
                'label': 'Pick one',
                'format': '%s',
                'default': [
                    0.0
                ],
                'max': 2.0,
                'step': 1.0,
                'options': [
                    'low',
                    'medium',
                    'high'
                ],
                'labelVisibility': {},
                'type': 'SELECT_SLIDER'
            },
            'path': [
                0,
                4
            ]
        },
        {
            'kind': 'slider',
            'widget': {
                'label': 'Pick range',
                'format': '%s',
                'default': [
                    1.0,
                    3.0
                ],
                'max': 3.0,
                'step': 1.0,
                'options': [
                    'a',
                    'b',
                    'c',
                    'd'
                ],
                'labelVisibility': {},
                'type': 'SELECT_SLIDER'
            },
            'path': [
                0,
                5
            ]
        },
        {
            'kind': 'audio_input',
            'widget': {
                'label': 'Voice note',
                'labelVisibility': {},
                'sampleRate': 16000
            },
            'path': [
                0,
                6
            ]
        },
        {
            'kind': 'camera_input',
            'widget': {
                'label': 'Snapshot',
                'labelVisibility': {}
            },
            'path': [
                0,
                7
            ]
        },
        {
            'kind': 'script_finished'
        },
        {
            'kind': 'session_status_changed'
        },
        {
            'kind': 'rerun',
            'states': [
                {
                    'id': '$$ID-accent',
                    'value_field': 'string_value',
                    'value': '#FF5733'
                },
                {
                    'id': '$$ID-meeting',
                    'value_field': 'string_value',
                    'value': '14:30'
                },
                {
                    'id': '$$ID-one',
                    'value_field': 'string_array_value',
                    'value': {
                        'data': "['high']"
                    }
                },
                {
                    'id': '$$ID-range',
                    'value_field': 'string_array_value',
                    'value': {
                        'data': "['b', 'd']"
                    }
                },
                {
                    'id': '$$ID-shot',
                    'value_field': 'file_uploader_state_value',
                    'value': {}
                },
                {
                    'id': '$$ID-start',
                    'value_field': 'string_array_value',
                    'value': {
                        'data': "['2025-01-15']"
                    }
                },
                {
                    'id': '$$ID-window',
                    'value_field': 'string_array_value',
                    'value': {
                        'data': "['2025-01-15', '2025-02-15']"
                    }
                }
            ]
        },
        {
            'kind': 'new_session'
        },
        {
            'kind': 'session_status_changed'
        },
        {
            'kind': 'date_input',
            'widget': {
                'label': 'Start date',
                'default': [
                    '2025-01-15'
                ],
                'min': '2015-01-15',
                'max': '2035-01-15',
                'labelVisibility': {},
                'format': 'YYYY/MM/DD'
            },
            'path': [
                0,
                0
            ]
        },
        {
            'kind': 'date_input',
            'widget': {
                'label': 'Window',
                'default': [
                    '2025-01-15',
                    '2025-02-15'
                ],
                'min': '2015-01-15',
                'max': '2035-02-15',
                'isRange': True,
                'labelVisibility': {},
                'format': 'YYYY/MM/DD'
            },
            'path': [
                0,
                1
            ]
        },
        {
            'kind': 'time_input',
            'widget': {
                'label': 'Meeting',
                'default': '14:30',
                'labelVisibility': {},
                'step': '900',
                'format': '24h'
            },
            'path': [
                0,
                2
            ]
        },
        {
            'kind': 'color_picker',
            'widget': {
                'label': 'Accent',
                'default': '#FF5733',
                'labelVisibility': {}
            },
            'path': [
                0,
                3
            ]
        },
        {
            'kind': 'slider',
            'widget': {
                'label': 'Pick one',
                'format': '%s',
                'default': [
                    0.0
                ],
                'max': 2.0,
                'step': 1.0,
                'options': [
                    'low',
                    'medium',
                    'high'
                ],
                'labelVisibility': {},
                'type': 'SELECT_SLIDER'
            },
            'path': [
                0,
                4
            ]
        },
        {
            'kind': 'slider',
            'widget': {
                'label': 'Pick range',
                'format': '%s',
                'default': [
                    1.0,
                    3.0
                ],
                'max': 3.0,
                'step': 1.0,
                'options': [
                    'a',
                    'b',
                    'c',
                    'd'
                ],
                'labelVisibility': {},
                'type': 'SELECT_SLIDER'
            },
            'path': [
                0,
                5
            ]
        },
        {
            'kind': 'audio_input',
            'widget': {
                'label': 'Voice note',
                'labelVisibility': {},
                'sampleRate': 16000
            },
            'path': [
                0,
                6
            ]
        },
        {
            'kind': 'camera_input',
            'widget': {
                'label': 'Snapshot',
                'labelVisibility': {}
            },
            'path': [
                0,
                7
            ]
        },
        {
            'kind': 'script_finished'
        },
        {
            'kind': 'session_status_changed'
        },
        {
            'kind': 'rerun',
            'states': [
                {
                    'id': '$$ID-accent',
                    'value_field': 'string_value',
                    'value': '#FF5733'
                },
                {
                    'id': '$$ID-meeting',
                    'value_field': 'string_value',
                    'value': '14:30'
                },
                {
                    'id': '$$ID-one',
                    'value_field': 'string_array_value',
                    'value': {
                        'data': "['high']"
                    }
                },
                {
                    'id': '$$ID-range',
                    'value_field': 'string_array_value',
                    'value': {
                        'data': "['b', 'd']"
                    }
                },
                {
                    'id': '$$ID-shot',
                    'value_field': 'file_uploader_state_value',
                    'value': {}
                },
                {
                    'id': '$$ID-start',
                    'value_field': 'string_array_value',
                    'value': {
                        'data': "['2025-01-15']"
                    }
                },
                {
                    'id': '$$ID-window',
                    'value_field': 'string_array_value',
                    'value': {
                        'data': "['2025-01-15', '2025-02-15']"
                    }
                }
            ]
        },
        {
            'kind': 'new_session'
        },
        {
            'kind': 'session_status_changed'
        },
        {
            'kind': 'date_input',
            'widget': {
                'label': 'Start date',
                'default': [
                    '2025-01-15'
                ],
                'min': '2015-01-15',
                'max': '2035-01-15',
                'labelVisibility': {},
                'format': 'YYYY/MM/DD'
            },
            'path': [
                0,
                0
            ]
        },
        {
            'kind': 'date_input',
            'widget': {
                'label': 'Window',
                'default': [
                    '2025-01-15',
                    '2025-02-15'
                ],
                'min': '2015-01-15',
                'max': '2035-02-15',
                'isRange': True,
                'labelVisibility': {},
                'format': 'YYYY/MM/DD'
            },
            'path': [
                0,
                1
            ]
        },
        {
            'kind': 'time_input',
            'widget': {
                'label': 'Meeting',
                'default': '14:30',
                'labelVisibility': {},
                'step': '900',
                'format': '24h'
            },
            'path': [
                0,
                2
            ]
        },
        {
            'kind': 'color_picker',
            'widget': {
                'label': 'Accent',
                'default': '#FF5733',
                'labelVisibility': {}
            },
            'path': [
                0,
                3
            ]
        },
        {
            'kind': 'slider',
            'widget': {
                'label': 'Pick one',
                'format': '%s',
                'default': [
                    0.0
                ],
                'max': 2.0,
                'step': 1.0,
                'options': [
                    'low',
                    'medium',
                    'high'
                ],
                'labelVisibility': {},
                'type': 'SELECT_SLIDER'
            },
            'path': [
                0,
                4
            ]
        },
        {
            'kind': 'slider',
            'widget': {
                'label': 'Pick range',
                'format': '%s',
                'default': [
                    1.0,
                    3.0
                ],
                'max': 3.0,
                'step': 1.0,
                'options': [
                    'a',
                    'b',
                    'c',
                    'd'
                ],
                'labelVisibility': {},
                'type': 'SELECT_SLIDER'
            },
            'path': [
                0,
                5
            ]
        },
        {
            'kind': 'audio_input',
            'widget': {
                'label': 'Voice note',
                'labelVisibility': {},
                'sampleRate': 16000
            },
            'path': [
                0,
                6
            ]
        },
        {
            'kind': 'camera_input',
            'widget': {
                'label': 'Snapshot',
                'labelVisibility': {}
            },
            'path': [
                0,
                7
            ]
        },
        {
            'kind': 'script_finished'
        },
        {
            'kind': 'session_status_changed'
        }
    ]
}

PICKERS_DOMS = {
    '01-load': {
        'dateInputs': [
            '2025-01-15',
            '2025-01-15'
        ],
        'timeInputs': [
            '14:30:00'
        ],
        'colorPickers': 1,
        'sliderThumbs': [
            'low',
            'b',
            'd'
        ],
        'audioInputs': 1,
        'cameraInputs': 1,
        'exceptions': []
    },
    '02-slider': {
        'dateInputs': [
            '2025-01-15',
            '2025-01-15'
        ],
        'timeInputs': [
            '14:30:00'
        ],
        'colorPickers': 1,
        'sliderThumbs': [
            'high',
            'b',
            'd'
        ],
        'audioInputs': 1,
        'cameraInputs': 1,
        'exceptions': []
    }
}

PICKERS_SOURCE_PINS = {
    "python": [
    'tests/reference/pickers_app.py',
    '0243f923d03c966dfe2c91f197f7ef9f631de7c397cbca55f17ebce3a6beb668'
],
    "native": [
    'streamlit/examples/pickers.rs',
    '3112cb6e5dbc4879a73054d66f88c9aa7c3f62b3ab394cbebd72667eb9b78e3d'
],
}

PICKERS_REQUIRED = (
    "contract", "stage_set", "source_pin", "timeline", "date_wire",
    "time_wire", "color_wire", "slider_wire", "media_input_wire",
    "interaction_wires", "dom_projection", "no_exceptions", "finishes",
    "png_sources",
)

_ID_SUB = re.compile(r"\$\$ID-[0-9a-f]{32}-")
WIDGET_KINDS = ("date_input", "time_input", "color_picker", "slider", "audio_input", "camera_input")


def _record(checks, name, ok, expected, actual):
    checks.append({"step": PICKERS_CASE, "check": name, "expected": expected, "actual": actual, "ok": bool(ok)})


def _need(condition, message):
    if not condition:
        raise ValueError(message)


def _normalized_state(state):
    state = {**state, "id": _ID_SUB.sub("$$ID-", state.get("id") or "")}
    state.pop("value_full", None)
    return state


def _sorted_states(states):
    return sorted((_normalized_state(state) for state in states), key=lambda state: (state["id"], state.get("value_field", "")))


def _timeline(stage):
    """The stage's normalized frames. The Rust runtime re-announces the
    main container at [0] at the head of every element batch (the
    reference never does); those blocks are the documented divergence and
    are stripped, any other block is a failure."""
    out = []
    for frame in stage.get("new_frames") or []:
        summary = frame.get("summary") or {}
        kind = summary.get("type")
        if kind == "delta":
            delta = summary.get("delta") or {}
            inner = delta.get("type")
            _need(inner in ("new_element", "add_block"), f"unexpected delta kind {inner!r}")
            if inner == "add_block" and (delta.get("path") or None) == [0] and (delta.get("block") or {}).get("id") == "main_container":
                continue
            if inner == "add_block":
                _need(False, f"unexpected block {sorted(delta.get('block') or {})}")
            name = delta.get("element")
            if name in WIDGET_KINDS:
                widget = {key: value for key, value in (delta.get("widget") or {}).items() if key != "id"}
                _need(delta.get("widget") is not None, f"{name} delta lacks its full widget")
                out.append({"kind": name, "widget": widget, "path": delta.get("path")})
            else:
                out.append({"kind": name, "body": delta.get("body"), "path": delta.get("path")})
        elif kind == "rerun_script":
            rerun = summary.get("rerun_script") or {}
            out.append({"kind": "rerun", "states": _sorted_states(rerun.get("widget_states") or [])})
        elif kind in ("new_session", "session_status_changed", "script_finished"):
            out.append({"kind": kind})
        else:
            _need(False, f"unexpected frame kind {kind!r}")
    return out


def _entries(stage_timeline, kind):
    return [entry for entry in stage_timeline if entry["kind"] == kind]


def pickers_checks(*, observation=None):
    checks = []
    verified = set()

    def mark(name):
        verified.add(name)
        _record(checks, name, True, "the measured 1.66.1 picker wire", "contract verified")

    def fail(name, actual):
        _record(checks, name, False, "the measured 1.66.1 picker wire", str(actual))

    try:
        _need(isinstance(observation, dict), "observation must be a dict")
        _need(observation.get("journey") == PICKERS_CASE and observation.get("contract") == PICKERS_CONTRACT,
              "missing versioned pickers contract identity")
        _need(bool(observation.get("scope")) and bool(observation.get("url")), "missing scope/url")
        mark("contract")

        stages = observation.get("stages")
        _need(isinstance(stages, list) and tuple(s.get("name") for s in stages) == tuple(PICKERS_STAGES),
              f"stages must be exactly the {len(PICKERS_STAGES)} measured stages in order")
        for stage in stages:
            _need(isinstance(stage.get("dom"), dict) and isinstance(stage.get("screenshot"), dict)
                  and isinstance(stage.get("new_frames"), list), f"stage {stage.get('name')} lacks dom/screenshot/new_frames")
        mark("stage_set")

        source = observation.get("source") or {}
        side = "python" if observation.get("scope") == "PYTHON SIDE ONLY" else "native"
        path, pinned = PICKERS_SOURCE_PINS[side]
        _need(source.get("file") == path and source.get("sha256") == pinned,
              f"driven source is not the pinned {path} of this contract")
        mark("source_pin")

        timelines = {stage["name"]: _timeline(stage) for stage in stages}
        for name in PICKERS_STAGES:
            _need(timelines[name] == PICKERS_TIMELINE[name],
                  f"stage {name} frame timeline differs from the measured wire ({len(timelines[name])} frames)")
        mark("timeline")

        load = timelines["01-load"]
        dates = _entries(load, "date_input")
        _need(len(dates) == 2, f"the load must carry two date inputs, got {len(dates)}")
        _need(dates[0]["widget"] == {"label": "Start date", "default": ["2025-01-15"], "min": "2015-01-15",
                                      "max": "2035-01-15", "labelVisibility": {}, "format": "YYYY/MM/DD"},
              "the single date input carries its ISO default and ten-year window")
        _need(dates[1]["widget"] == {"label": "Window", "default": ["2025-01-15", "2025-02-15"], "min": "2015-01-15",
                                      "max": "2035-02-15", "isRange": True, "labelVisibility": {}, "format": "YYYY/MM/DD"},
              "the range date input anchors each endpoint's side of the window")
        mark("date_wire")

        times = _entries(load, "time_input")
        _need(len(times) == 1 and times[0]["widget"] == {"label": "Meeting", "default": "14:30",
                                                          "labelVisibility": {}, "step": "900", "format": "24h"},
              "the time input carries its HH:MM default, step and format")
        mark("time_wire")

        colors = _entries(load, "color_picker")
        _need(len(colors) == 1 and colors[0]["widget"] == {"label": "Accent", "default": "#FF5733", "labelVisibility": {}},
              "the color picker carries its #RRGGBB default")
        mark("color_wire")

        sliders = _entries(load, "slider")
        _need(len(sliders) == 2, f"the load must carry two select sliders, got {len(sliders)}")
        _need(sliders[0]["widget"] == {"label": "Pick one", "format": "%s", "default": [0.0], "max": 2.0,
                                        "step": 1.0, "options": ["low", "medium", "high"], "labelVisibility": {},
                                        "type": "SELECT_SLIDER"},
              "the single select slider defaults to the first option")
        _need(sliders[1]["widget"] == {"label": "Pick range", "format": "%s", "default": [1.0, 3.0], "max": 3.0,
                                        "step": 1.0, "options": ["a", "b", "c", "d"], "labelVisibility": {},
                                        "type": "SELECT_SLIDER"},
              "the range select slider carries its index pair")
        mark("slider_wire")

        audios = _entries(load, "audio_input")
        cameras = _entries(load, "camera_input")
        _need(len(audios) == 1 and audios[0]["widget"] == {"label": "Voice note", "labelVisibility": {}, "sampleRate": 16000},
              "the audio input carries its label and sample rate")
        _need(len(cameras) == 1 and cameras[0]["widget"] == {"label": "Snapshot", "labelVisibility": {}},
              "the camera input carries only label and visibility")
        mark("media_input_wire")

        slider_stage = timelines["02-slider"]
        reruns = _entries(slider_stage, "rerun")
        expected = _entries(PICKERS_TIMELINE["02-slider"], "rerun")
        _need(len(reruns) == len(expected) and all(a["states"] == b["states"] for a, b in zip(reruns, expected)),
              "the slider steps report exactly the measured state batches")
        labels = [state.get("value") for rerun in reruns for state in rerun["states"]
                  if state.get("id", "").endswith("-one") and state.get("value_field") == "string_array_value"]
        # The summarised string-array state carries its repr string.
        _need(len(labels) >= 2 and labels[0] == {"data": "['medium']"} and labels[-1] == {"data": "['high']"},
              f"the single slider steps low -> medium -> high, got {labels}")
        mark("interaction_wires")

        for stage in stages:
            name = stage["name"]
            _need({key: (stage["dom"] or {}).get(key) for key in PICKERS_DOMS[name]} == PICKERS_DOMS[name],
                  f"stage {name} resolved DOM projection differs from the measured page")
        mark("dom_projection")

        for stage in stages:
            _need(not ((stage["dom"] or {}).get("exceptions") or []), f"stage {stage['name']} renders an exception")
        mark("no_exceptions")

        for stage in stages:
            finishes = [((frame.get("summary") or {}).get("script_finished") or {}).get("status")
                        for frame in stage["new_frames"]
                        if (frame.get("summary") or {}).get("type") == "script_finished"]
            # The load finishes once; an interaction stage finishes once per
            # committed rerun, every one of them successful.
            _need(finishes and all(status == 0 for status in finishes),
                  f"stage {stage['name']} must finish FINISHED_SUCCESSFULLY, got {finishes}")
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
        for name in PICKERS_REQUIRED:
            if name not in verified:
                fail(name, str(exc))
        return checks
    return checks


def pickers_result(*, observation=None):
    """Aggregate the contract checks the way the shared journey judge does."""
    checks = pickers_checks(observation=observation)
    failures = [check for check in checks if not check["ok"]]
    return {
        "checks": checks,
        "counts": {"expected": len(checks), "executed": len(checks), "asserted": len(checks) - len(failures)},
        "failures": failures,
        "ok": not failures and len(checks) == len(PICKERS_REQUIRED),
    }
