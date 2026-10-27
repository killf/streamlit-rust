"""The strict chat contract: journey-chat-v1.

This criterion judges the observation the committed collector
(chat_capture.py) writes, against the Python 1.66.1 wire measured on
2026-10-26 with the official frontend and recorded in .codex/compatibility.md
(Chat elements). The collector states no verdict; this module owns it:

* st.chat_message streams a chat_message block (name, avatar defaulting to
  the name, ICON avatar type, allowEmpty, stretch width) with children at
  [slot, 0];
* st.chat_input is a trigger widget routed to the bottom root [3, 0]
  without consuming a main-flow slot, carrying the placeholder, the 200 MB
  upload cap, the 16000 Hz audio sample rate and the auto-position marker;
* the Enter commit round trips chat_input_value{data, file_uploader_state}
  and the submitted prompt drives the run's output (the echo) at the next
  main slot;
* the settled DOM shows both messages with their avatars, the input
  placeholder and no exception.

Widget ids are judged modulo the $$ID digest segment; at most one leading
main-container add_block at [0] is the Rust runtime's documented divergence.
"""

from __future__ import annotations

import hashlib
import json
import pathlib
import re

CHAT_CASE = "chat-page"
CHAT_CONTRACT = "journey-chat-v1"

CHAT_STAGES = [
    '01-load',
    '02-enter-commit'
]

# Per stage: the normalized frame timeline, the chat_input widget payload
# and the DOM projection.
CHAT_TIMELINE = {
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
            'kind': 'chat_message',
            'chat': {
                'name': 'user',
                'avatar': 'user',
                'avatarType': 'ICON'
            },
            'configs': {
                'allowEmpty': True,
                'widthConfig': {
                    'useStretch': True
                }
            },
            'path': [
                0,
                0
            ]
        },
        {
            'kind': 'markdown',
            'body': 'hello from user',
            'path': [
                0,
                0,
                0
            ]
        },
        {
            'kind': 'chat_message',
            'chat': {
                'name': 'assistant',
                'avatar': ':material/robot:',
                'avatarType': 'ICON'
            },
            'configs': {
                'allowEmpty': True,
                'widthConfig': {
                    'useStretch': True
                }
            },
            'path': [
                0,
                1
            ]
        },
        {
            'kind': 'markdown',
            'body': 'hello from assistant',
            'path': [
                0,
                1,
                0
            ]
        },
        {
            'kind': 'chat_input',
            'widget': {
                'placeholder': 'Say something',
                'maxUploadSizeMb': 200,
                'audioSampleRate': 16000,
                'isAutoPositionedAtBottom': True
            },
            'path': [
                3,
                0
            ]
        },
        {
            'kind': 'script_finished'
        },
        {
            'kind': 'session_status_changed'
        }
    ],
    '02-enter-commit': [
        {
            'kind': 'rerun',
            'states': [
                {
                    'id': '$$ID-None',
                    'value_field': 'chat_input_value',
                    'value': {
                        'data': 'hi',
                        'file_uploader_state': {}
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
            'kind': 'chat_message',
            'chat': {
                'name': 'user',
                'avatar': 'user',
                'avatarType': 'ICON'
            },
            'configs': {
                'allowEmpty': True,
                'widthConfig': {
                    'useStretch': True
                }
            },
            'path': [
                0,
                0
            ]
        },
        {
            'kind': 'markdown',
            'body': 'hello from user',
            'path': [
                0,
                0,
                0
            ]
        },
        {
            'kind': 'chat_message',
            'chat': {
                'name': 'assistant',
                'avatar': ':material/robot:',
                'avatarType': 'ICON'
            },
            'configs': {
                'allowEmpty': True,
                'widthConfig': {
                    'useStretch': True
                }
            },
            'path': [
                0,
                1
            ]
        },
        {
            'kind': 'markdown',
            'body': 'hello from assistant',
            'path': [
                0,
                1,
                0
            ]
        },
        {
            'kind': 'chat_input',
            'widget': {
                'placeholder': 'Say something',
                'maxUploadSizeMb': 200,
                'audioSampleRate': 16000,
                'isAutoPositionedAtBottom': True
            },
            'path': [
                3,
                0
            ]
        },
        {
            'kind': 'markdown',
            'body': 'echo: hi',
            'path': [
                0,
                2
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

CHAT_INPUTS = {
    '01-load': {
        'kind': 'chat_input',
        'widget': {
            'placeholder': 'Say something',
            'maxUploadSizeMb': 200,
            'audioSampleRate': 16000,
            'isAutoPositionedAtBottom': True
        },
        'path': [
            3,
            0
        ]
    },
    '02-enter-commit': {
        'kind': 'chat_input',
        'widget': {
            'placeholder': 'Say something',
            'maxUploadSizeMb': 200,
            'audioSampleRate': 16000,
            'isAutoPositionedAtBottom': True
        },
        'path': [
            3,
            0
        ]
    }
}

CHAT_DOMS = {
    '01-load': {
        'messages': [
            'face\n\nhello from user',
            'robot\n\nhello from assistant'
        ],
        'input': 'Say something',
        'markdowns': [],
        'exceptions': []
    },
    '02-enter-commit': {
        'messages': [
            'face\n\nhello from user',
            'robot\n\nhello from assistant'
        ],
        'input': 'Say something',
        'markdowns': [],
        'exceptions': []
    }
}

CHAT_SOURCE_FILES = {
    "python": "tests/reference/chat_app.py",
    "native": "streamlit/examples/chat.rs",
}

CHAT_REQUIRED = (
    "contract", "stage_set", "timeline", "chat_block_wire",
    "chat_input_wire", "submit_wire", "dom_projection", "no_exceptions",
    "finishes", "png_sources",
)

_ID_SUB = re.compile(r"\$\$ID-[0-9a-f]{32}-")


def _record(checks, name, ok, expected, actual):
    checks.append({"step": CHAT_CASE, "check": name, "expected": expected, "actual": actual, "ok": bool(ok)})


def _need(condition, message):
    if not condition:
        raise ValueError(message)


def _timeline(stage):
    """The stage's normalized frames, the optional leading main container
    peeled off (the Rust side emits exactly one, the reference none)."""
    out = []
    stripped = 0
    for frame in stage.get("new_frames") or []:
        summary = frame.get("summary") or {}
        kind = summary.get("type")
        if kind == "delta":
            delta = summary.get("delta") or {}
            inner = delta.get("type")
            _need(inner in ("new_element", "add_block"), f"unexpected delta kind {inner!r}")
            if inner == "add_block" and (delta.get("path") or None) == [0] and (delta.get("block") or {}).get("id") == "main_container":
                stripped += 1
                _need(stripped <= 1, "more than one leading main-container block")
                continue
            if inner == "add_block":
                block = delta.get("block") or {}
                chat = block.get("chatMessage")
                _need(chat is not None, f"unexpected block {sorted(block)}")
                rest = {key: value for key, value in block.items() if key != "chatMessage"}
                out.append({"kind": "chat_message", "chat": chat, "configs": rest, "path": delta.get("path")})
            else:
                name = delta.get("element")
                if name == "chat_input":
                    widget = delta.get("widget") or {}
                    _need(bool(widget), "chat_input delta lacks its full widget")
                    out.append({"kind": "chat_input", "widget": {key: value for key, value in widget.items() if key != "id"}, "path": delta.get("path")})
                else:
                    out.append({"kind": name, "body": delta.get("body"), "path": delta.get("path")})
        elif kind == "rerun_script":
            rerun = summary.get("rerun_script") or {}
            states = [{**state, "id": _ID_SUB.sub("$$ID-", state.get("id") or "")} for state in rerun.get("widget_states") or []]
            for state in states:
                state.pop("value_full", None)
            out.append({"kind": "rerun", "states": states})
        elif kind in ("new_session", "session_status_changed", "script_finished"):
            out.append({"kind": kind})
        else:
            _need(False, f"unexpected frame kind {kind!r}")
    return out


def chat_checks(*, observation=None):
    checks = []
    verified = set()

    def mark(name):
        verified.add(name)
        _record(checks, name, True, "the measured 1.66.1 chat wire", "contract verified")

    def fail(name, actual):
        _record(checks, name, False, "the measured 1.66.1 chat wire", str(actual))

    try:
        _need(isinstance(observation, dict), "observation must be a dict")
        _need(observation.get("journey") == CHAT_CASE and observation.get("contract") == CHAT_CONTRACT,
              "missing versioned chat contract identity")
        _need(bool(observation.get("scope")) and bool(observation.get("url")), "missing scope/url")
        mark("contract")

        stages = observation.get("stages")
        _need(isinstance(stages, list) and tuple(s.get("name") for s in stages) == tuple(CHAT_STAGES),
              f"stages must be exactly the {len(CHAT_STAGES)} measured stages in order")
        for stage in stages:
            _need(isinstance(stage.get("dom"), dict) and isinstance(stage.get("screenshot"), dict)
                  and isinstance(stage.get("new_frames"), list), f"stage {stage.get('name')} lacks dom/screenshot/new_frames")
        mark("stage_set")

        timelines = {stage["name"]: _timeline(stage) for stage in stages}
        for name in CHAT_STAGES:
            _need(timelines[name] == CHAT_TIMELINE[name],
                  f"stage {name} frame timeline differs from the measured wire ({len(timelines[name])} frames)")
        mark("timeline")

        load = timelines["01-load"]
        blocks = [entry for entry in load if entry["kind"] == "chat_message"]
        _need(len(blocks) == 2, f"the load must carry exactly two chat_message blocks, got {len(blocks)}")
        _need(blocks[0]["chat"] == {"name": "user", "avatar": "user", "avatarType": "ICON"},
              "the first chat block must default its avatar to the name")
        _need(blocks[1]["chat"] == {"name": "assistant", "avatar": ":material/robot:", "avatarType": "ICON"},
              "the second chat block must carry the explicit material avatar")
        for block in blocks:
            _need(block["configs"] == {"allowEmpty": True, "widthConfig": {"useStretch": True}},
                  "every chat block is allowEmpty with stretch width")
        _need([entry["path"] for entry in blocks] == [[0, 0], [0, 1]], "the chat blocks sit at consecutive slots")
        _need([entry["body"] for entry in load if entry["kind"] == "markdown"] == ["hello from user", "hello from assistant"],
              "the children stream inside the blocks")
        mark("chat_block_wire")

        for name in CHAT_STAGES:
            entries = [entry for entry in timelines[name] if entry["kind"] == "chat_input"]
            _need(len(entries) == 1, f"stage {name} must carry exactly one chat_input element")
            _need(entries[0]["widget"] == CHAT_INPUTS[name]["widget"], f"stage {name} chat_input widget differs from the measured wire")
            _need(entries[0]["path"] == [3, 0], "the chat input must sit at the bottom root [3, 0]")
        mark("chat_input_wire")

        commit = timelines["02-enter-commit"]
        reruns = [entry for entry in commit if entry["kind"] == "rerun"]
        expected_states = next(entry for entry in CHAT_TIMELINE["02-enter-commit"] if entry["kind"] == "rerun")["states"]
        _need(len(reruns) == 1 and reruns[0]["states"] == expected_states,
              "the Enter commit carries exactly the measured chat_input_value report")
        echoes = [entry for entry in commit if entry["kind"] == "markdown" and entry.get("body") == "echo: hi"]
        _need(len(echoes) == 1 and echoes[0]["path"] == [0, 2],
              "the submitted prompt drives the run's output at the next main slot")
        mark("submit_wire")

        for stage in stages:
            name = stage["name"]
            _need({key: (stage["dom"] or {}).get(key) for key in CHAT_DOMS[name]} == CHAT_DOMS[name],
                  f"stage {name} resolved DOM projection differs from the measured page")
        mark("dom_projection")

        for stage in stages:
            _need(not ((stage["dom"] or {}).get("exceptions") or []), f"stage {stage['name']} renders an exception")
        mark("no_exceptions")

        for stage in stages:
            finishes = [((frame.get("summary") or {}).get("script_finished") or {}).get("status")
                        for frame in stage["new_frames"]
                        if (frame.get("summary") or {}).get("type") == "script_finished"]
            _need(finishes == [0], f"stage {stage['name']} must finish exactly once FINISHED_SUCCESSFULLY")
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
        for name in CHAT_REQUIRED:
            if name not in verified:
                fail(name, str(exc))
        return checks
    return checks


def chat_result(*, observation=None):
    """Aggregate the contract checks the way the shared journey judge does."""
    checks = chat_checks(observation=observation)
    failures = [check for check in checks if not check["ok"]]
    return {
        "checks": checks,
        "counts": {"expected": len(checks), "executed": len(checks), "asserted": len(checks) - len(failures)},
        "failures": failures,
        "ok": not failures and len(checks) == len(CHAT_REQUIRED),
    }
